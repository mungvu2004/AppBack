"""Luồng đầy đủ #5 → #6 → #7, khử trùng init, #7 từ chối và hai phép đo của K36.

Mọi test ở đây chạy trên app thật với Postgres, Redis và kho thật; không mock gì. Hai test
cuối là phép đo chứ không phải khẳng định hành vi: một #6 đang ghi kho **không** được giữ
kết nối DB (`pool.checkedout() == 0`, #8 vẫn trả dưới 1 s), và #7 của một tệp 100 MiB trên
MinIO thật phải xong dưới 15 s (K28: quá 15 s thì route phải thành job).
"""

import asyncio
import hashlib
import time
from collections.abc import Iterator
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier
from apps.api.drawings.tests._helpers import sync_bus_reset as sync_bus_reset
from apps.api.drawings.tests._upload_helpers import (
    GatedStorage,
    Stage,
    chunk_body,
    chunks_path,
    complete_path,
    init_body,
    init_path,
    jpeg_bytes,
    make_stage,
    pdf_bytes,
    progress_path,
    split,
    upload_png,
    upload_through,
)
from apps.api.drawings.uploads import chunk_key
from packages.core.settings import get_core_settings
from packages.db.models.drawings import UploadChunkRow, UploadRow
from packages.db.settings import reset_database_settings_cache
from packages.storage.port import ObjectStorage
from packages.testing.factories.drawings import make_upload
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock

MIB: Final = 1024 * 1024
BIG_FILE_BYTES: Final = 12 * MIB
HUGE_FILE_BYTES: Final = 100 * MIB
CHUNK_WAIT_S: Final = 10.0
PROGRESS_BUDGET_S: Final = 1.0
COMPLETE_BUDGET_S: Final = 15.0


async def _upload_row(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str) -> UploadRow:
    """Dòng `uploads` đọc lại bằng **session mới** — bằng chứng đã ghi bền (K22)."""
    async with sessionmaker() as session:
        return (await session.execute(select(UploadRow).where(UploadRow.id == upload_id))).scalar_one()


# ---------------------------------------------------------------------------
# Luồng đầy đủ
# ---------------------------------------------------------------------------


async def test_full_flow_png_three_chunks_keeps_sha256(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    sync_bus_reset: None,
) -> None:
    """PNG 12 MiB đi qua ba khúc 5 MiB và về lại **đúng từng byte** ở `original.png`."""
    stage = await make_stage(db_session)
    data = upload_png(BIG_FILE_BYTES)
    assert len(split(data)) == 3

    upload_id, response = await upload_through(api_client, stage, data)

    assert response.status_code == 200, response.text
    row = await _upload_row(db_sessionmaker, upload_id)
    assert row.original_key is not None
    stored = await local_storage.stat(row.original_key)
    assert stored is not None
    assert stored.sha256 == hashlib.sha256(data).hexdigest()


async def test_full_flow_pdf_page_index_one(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    sync_bus_reset: None,
) -> None:
    """PDF nhiều trang với `pageIndex: 1` → 200 và `original.pdf` đúng SHA-256."""
    stage = await make_stage(db_session)
    data = pdf_bytes(3)

    upload_id, response = await upload_through(
        api_client, stage, data, file_name="ho-so.pdf", mime_type="application/pdf", page_index=1
    )

    assert response.status_code == 200, response.text
    row = await _upload_row(db_sessionmaker, upload_id)
    assert row.sniffed_kind == "pdf"
    assert row.original_key is not None
    stored = await local_storage.stat(row.original_key)
    assert stored is not None
    assert stored.sha256 == hashlib.sha256(data).hexdigest()


async def test_full_flow_accepts_blank_mime_and_jpeg(
    api_client: httpx.AsyncClient, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """`mimeType: ""` và đuôi `.jpeg` → 200 (U09): magic bytes ở #7 mới quyết."""
    stage = await make_stage(db_session)

    _, response = await upload_through(api_client, stage, jpeg_bytes(4000), file_name="ban-ve.jpeg", mime_type="")

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Khử trùng init
# ---------------------------------------------------------------------------


async def test_init_twice_in_window_reuses_one_upload(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Hai init giống hệt nhau, tuần tự → **một** lượt tải (FE thử lại không có khoá)."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=4000)
    path = init_path(stage.project_id, stage.level_id)

    first = await api_client.post(path, json=body, headers=stage.headers)
    second = await api_client.post(path, json=body, headers=stage.headers)

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json()["id"] == second.json()["id"]


async def test_init_twice_in_parallel_reuses_one_upload(
    api_app: FastAPI, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Hai init song song → vẫn một lượt tải: khoá tầng xếp hàng hai lượt chèn."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=4000)
    path = init_path(stage.project_id, stage.level_id)

    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        first, second = await asyncio.gather(
            client_a.post(path, json=body, headers=stage.headers),
            client_b.post(path, json=body, headers=stage.headers),
        )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json()["id"] == second.json()["id"]
    async with db_sessionmaker() as session:
        stmt = select(UploadRow.id).where(UploadRow.floor_pk == stage.scene.floor.pk)
        assert len(list((await session.execute(stmt)).scalars())) == 1


async def test_init_after_first_chunk_starts_a_new_upload(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Lượt cũ đã nhận khúc → init thứ hai là một lượt tải **mới**, không ghi đè."""
    stage = await make_stage(db_session)
    data = upload_png(3000)
    body = init_body(stage.project_id, stage.level_id, size_bytes=len(data))
    path = init_path(stage.project_id, stage.level_id)

    first = await api_client.post(path, json=body, headers=stage.headers)
    assert first.status_code == 200, first.text
    upload_id = first.json()["id"]
    chunk = await api_client.post(
        chunks_path(stage.project_id, upload_id), json=chunk_body(data, 0), headers=stage.headers
    )
    assert chunk.status_code == 200, chunk.text
    second = await api_client.post(path, json=body, headers=stage.headers)

    assert second.status_code == 200, second.text
    assert second.json()["id"] != upload_id


# ---------------------------------------------------------------------------
# #7 từ chối
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("file_name", "mime_type", "data", "code", "page_index"),
    [
        ("ban-ve.png", "image/png", pdf_bytes(1), "FILE_TYPE_MISMATCH", None),
        ("ban-ve.png", "image/png", b"AC1015" + b"\x00" * 600, "CAD_NOT_SUPPORTED", None),
        ("ho-so.pdf", "application/pdf", pdf_bytes(3), "VALIDATION", 5),
        ("ho-so.pdf", "application/pdf", pdf_bytes(21), "VALIDATION", 0),
    ],
    ids=["pdf-named-png", "dwg-content", "page-index-past-end", "too-many-pages"],
)
async def test_complete_rejects_and_records_code(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
    file_name: str,
    mime_type: str,
    data: bytes,
    code: str,
    page_index: int | None,
) -> None:
    """Tệp không dùng được → 422 W7 và một dòng `rejected` đọc lại được qua session mới."""
    stage = await make_stage(db_session)

    upload_id, response = await upload_through(
        api_client, stage, data, file_name=file_name, mime_type=mime_type, page_index=page_index
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == code
    row = await _upload_row(db_sessionmaker, upload_id)
    assert row.status == "rejected"
    assert row.rejected_code == code


async def test_rejected_upload_reads_failed_and_replays_without_effect(
    api_client: httpx.AsyncClient, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Sau khi từ chối: #8 trả `failed` có `error`, và #7 lặp lại → 200 không tác dụng."""
    stage = await make_stage(db_session)

    upload_id, rejected = await upload_through(api_client, stage, pdf_bytes(1))
    assert rejected.status_code == 422, rejected.text

    progress = await api_client.get(progress_path(stage.project_id, upload_id), headers=stage.headers)
    replay = await api_client.post(
        complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=stage.headers
    )

    assert progress.status_code == 200, progress.text
    assert progress.json()["status"] == "failed"
    assert progress.json()["error"] == "FILE_TYPE_MISMATCH"
    assert replay.status_code == 200, replay.text
    assert replay.json() == progress.json()


@pytest.mark.parametrize(
    ("file_name", "mime_type", "data"),
    [
        ("ban-ve.jpeg", "image/jpeg", jpeg_bytes(trailing=200 * 1024)),
        ("ho-so.pdf", "application/pdf", pdf_bytes(1, leading_garbage=3)),
    ],
    ids=["jpeg-trailing-bytes", "pdf-leading-garbage"],
)
async def test_complete_accepts_tolerated_files(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    sync_bus_reset: None,
    file_name: str,
    mime_type: str,
    data: bytes,
) -> None:
    """Rác sau `FF D9` và rác trước `%PDF-` là chuyện thường của máy quét — vẫn nhận ([8])."""
    stage = await make_stage(db_session)

    _, response = await upload_through(api_client, stage, data, file_name=file_name, mime_type=mime_type)

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# K36 — pool nhỏ và phép đo
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_pool_app(api_env: None, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    """App thật với `DB_POOL_SIZE=1`: một request giữ kết nối là mọi request khác chờ (K36)."""
    monkeypatch.setenv("DB_POOL_SIZE", "1")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DB_POOL_TIMEOUT_S", "1")
    reset_database_settings_cache()
    yield create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock)
    reset_database_settings_cache()


async def test_chunk_upload_does_not_hold_the_pool__K36(
    tiny_pool_app: FastAPI, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """#6 đang `put` → pool rỗng và #8 vẫn trả dưới 1 s trên app chỉ có **một** kết nối."""
    stage = await make_stage(db_session)
    data = upload_png(3000)
    async with make_api_client(tiny_pool_app) as client:
        gated = GatedStorage(tiny_pool_app.state.storage)
        tiny_pool_app.state.storage = gated
        init = await client.post(
            init_path(stage.project_id, stage.level_id),
            json=init_body(stage.project_id, stage.level_id, size_bytes=len(data)),
            headers=stage.headers,
        )
        assert init.status_code == 200, init.text
        upload_id = init.json()["id"]

        chunk = asyncio.create_task(
            client.post(chunks_path(stage.project_id, upload_id), json=chunk_body(data, 0), headers=stage.headers)
        )
        await asyncio.wait_for(gated.entered.wait(), CHUNK_WAIT_S)
        assert tiny_pool_app.state.engine.pool.checkedout() == 0

        started = time.perf_counter()
        progress = await client.get(progress_path(stage.project_id, upload_id), headers=stage.headers)
        elapsed = time.perf_counter() - started
        gated.release.set()
        chunk_response = await asyncio.wait_for(chunk, CHUNK_WAIT_S)

    assert progress.status_code == 200, progress.text
    assert chunk_response.status_code == 200, chunk_response.text
    print(f"K36 #8 trong lúc #6 đang ghi kho: {elapsed:.3f} s")
    assert elapsed < PROGRESS_BUDGET_S


async def _seed_chunks(db: AsyncSession, storage: ObjectStorage, stage: Stage, data: bytes) -> UploadRow:
    """Mồi thẳng một lượt tải đủ khúc vào DB và kho: phép đo chỉ tính thời gian của #7."""
    upload = await make_upload(db, project=stage.scene.project, floor=stage.scene.floor, size_bytes=len(data))
    for index, piece in enumerate(split(data)):
        sha256 = hashlib.sha256(piece).hexdigest()
        key = chunk_key(stage.project_id, stage.level_id, upload.id, index, sha256)
        await storage.put(key, piece, content_type="application/octet-stream", max_bytes=len(piece))
        db.add(
            UploadChunkRow(upload_id=upload.id, chunk_index=index, size_bytes=len(piece), sha256=sha256, object_key=key)
        )
    await db.commit()
    return upload


async def test_complete_100_mib_on_minio_under_budget__K28(
    api_app: FastAPI,
    db_session: AsyncSession,
    s3_storage: ObjectStorage,
    sync_bus_reset: None,
) -> None:
    """#7 của một tệp 100 MiB trên MinIO thật xong dưới 15 s (quá thì phải thành job, K28)."""
    stage = await make_stage(db_session)
    data = upload_png(HUGE_FILE_BYTES)
    upload = await _seed_chunks(db_session, s3_storage, stage, data)

    async with make_api_client(api_app) as client:
        api_app.state.storage = s3_storage
        started = time.perf_counter()
        response = await client.post(
            complete_path(stage.project_id, upload.id), json={"uploadId": upload.id}, headers=stage.headers
        )
        elapsed = time.perf_counter() - started

    assert response.status_code == 200, response.text
    print(f"K28 #7 100 MiB trên MinIO: {elapsed:.2f} s")
    assert elapsed < COMPLETE_BUDGET_S
