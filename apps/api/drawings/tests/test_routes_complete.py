"""Case của #7 `drawings_complete_upload` (T-complete: C01 C06 C08 C14 C21 U07 U10 U11 + C18).

C10 là case "+ngoài" nên phải có test **riêng** của op (CASE §2.2): hai test cuối đếm
thông điệp `pipeline.cpu` trên Redis thật — lặp có khoá và lặp không khoá (như FE) đều chỉ
được xếp **một** lượt `pipeline.orchestrate.start`.
"""

import asyncio
import logging
from collections.abc import Iterator
from typing import Any, Final

import httpx
import pytest
from fastapi import FastAPI
from redis import Redis as SyncRedis
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.drawings.settings import reset_drawings_settings_cache
from apps.api.drawings.tests._helpers import sync_bus_reset as sync_bus_reset
from apps.api.drawings.tests._upload_helpers import (
    SMALL_CHUNK_BYTES,
    GatedStorage,
    Stage,
    broken_pdf_bytes,
    chunk_body,
    chunks_path,
    complete_path,
    headers_of,
    init_body,
    init_path,
    make_stage,
    pdf_bytes,
    png_bytes,
    send_chunks,
    split,
    upload_through,
)
from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.messaging import broker_redis_sync
from packages.messaging.settings import get_messaging_settings
from packages.storage.keys import upload_prefix
from packages.storage.port import ObjectStorage
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.messaging import queued_payloads

CPU_QUEUE: Final = "pipeline.cpu"
GATE_WAIT_S: Final = 10.0


@pytest.fixture(autouse=True)
def small_chunks(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`UPLOAD_CHUNK_BYTES = 1 KiB`: các case của #7 cần nhiều khúc, không cần nhiều byte."""
    monkeypatch.setenv("UPLOAD_CHUNK_BYTES", str(SMALL_CHUNK_BYTES))
    reset_drawings_settings_cache()
    yield
    reset_drawings_settings_cache()


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Client Redis của broker; hàng `pipeline.cpu` dọn trước và sau vì broker là session-scope."""
    client = broker_redis_sync(get_messaging_settings())
    client.delete(CPU_QUEUE)
    yield client
    client.delete(CPU_QUEUE)
    client.close()


async def _start(client: httpx.AsyncClient, stage: Stage, data: bytes, **overrides: Any) -> str:
    """#5 cho một tệp; trả `upload_id`."""
    body = init_body(stage.project_id, stage.level_id, size_bytes=len(data), **overrides)
    response = await client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)
    assert response.status_code == 200, response.text
    return str(response.json()["id"])


async def _upload_row(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str) -> UploadRow:
    """Dòng `uploads` đọc lại bằng session mới (K22)."""
    async with sessionmaker() as session:
        return (await session.execute(select(UploadRow).where(UploadRow.id == upload_id))).scalar_one()


async def _run_count(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str) -> int:
    """Số lượt chạy của một lượt tải — C14 đòi đúng một."""
    async with sessionmaker() as session:
        stmt = select(func.count()).select_from(PipelineRunRow).where(PipelineRunRow.upload_id == upload_id)
        return int((await session.execute(stmt)).scalar_one())


async def test_drawings_complete_upload__C01(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    sync_bus_reset: None,
) -> None:
    """Tệp đủ khúc → 200 `Progress` `pending`, dòng `complete` và `original.png` trong kho."""
    stage = await make_stage(db_session)
    data = png_bytes(2500)

    upload_id, response = await upload_through(api_client, stage, data)

    assert response.status_code == 200, response.text
    assert response.json() == {"id": upload_id, "status": "pending", "step": "preprocess", "progressPercent": 0}
    row = await _upload_row(db_sessionmaker, upload_id)
    assert row.status == "complete"
    assert row.sniffed_kind == "png"
    assert row.original_key is not None
    stored = await local_storage.stat(row.original_key)
    assert stored is not None
    assert stored.size == len(data)
    assert await _run_count(db_sessionmaker, upload_id) == 1


async def test_drawings_complete_upload__C06(
    api_client: httpx.AsyncClient, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Người ngoài dự án → 404 `resource:"project"`."""
    stage = await make_stage(db_session)
    upload_id = await _start(api_client, stage, png_bytes(600))
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await api_client.post(
        complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=headers_of(outsider)
    )

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_drawings_complete_upload__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Lượt tải không tồn tại → 404 `resource:"upload"`."""
    stage = await make_stage(db_session)
    missing = "upl_00000000000000000000000000"

    response = await api_client.post(
        complete_path(stage.project_id, missing), json={"uploadId": missing}, headers=stage.headers
    )

    assert response.status_code == 404
    assert response.json()["resource"] == "upload"


async def test_drawings_complete_upload__C14(
    api_app: FastAPI,
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
) -> None:
    """Hai #7 song song → cả hai 200, **một** lượt chạy và **một** dòng nhật ký."""
    stage = await make_stage(db_session)
    data = png_bytes(1500)
    upload_id = await _start(api_client, stage, data)
    for response in await send_chunks(api_client, stage, upload_id, split(data)):
        assert response.status_code == 200, response.text

    path = complete_path(stage.project_id, upload_id)
    body = {"uploadId": upload_id}
    async with make_api_client(api_app) as client_a, make_api_client(api_app) as client_b:
        first, second = await asyncio.gather(
            client_a.post(path, json=body, headers=stage.headers),
            client_b.post(path, json=body, headers=stage.headers),
        )

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert await _run_count(db_sessionmaker, upload_id) == 1
    rows = await activity_rows(db_sessionmaker, actor_id=stage.scene.user.id, kind=ActivityKind.FLOOR_UPLOAD_COMPLETE)
    assert len(rows) == 1


async def test_drawings_complete_upload__C21(
    api_client: httpx.AsyncClient, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """`uploadId` trong thân khác đường → 422 `PATH_BODY_MISMATCH`."""
    stage = await make_stage(db_session)
    upload_id = await _start(api_client, stage, png_bytes(600))

    response = await api_client.post(
        complete_path(stage.project_id, upload_id),
        json={"uploadId": "upl_00000000000000000000000000"},
        headers=stage.headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "PATH_BODY_MISMATCH"


async def test_drawings_complete_upload__U07(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    sync_bus_reset: None,
) -> None:
    """PNG thiếu `IEND` → 422 `FILE_CORRUPT`, dòng `rejected` và **không còn** `original.*`."""
    stage = await make_stage(db_session)
    data = png_bytes(1500, truncated=True)

    upload_id, response = await upload_through(api_client, stage, data)

    assert response.status_code == 422
    assert response.json()["code"] == "FILE_CORRUPT"
    row = await _upload_row(db_sessionmaker, upload_id)
    assert row.status == "rejected"
    assert row.rejected_code == "FILE_CORRUPT"
    assert row.original_key is None
    assert await local_storage.stat(f"{_prefix(stage, upload_id)}original.png") is None


def _prefix(stage: Stage, upload_id: str) -> str:
    """Tiền tố object của một lượt tải (`keys.upload_prefix`)."""
    return upload_prefix(stage.project_id, stage.level_id, upload_id)


async def test_drawings_complete_upload__U10(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
) -> None:
    """Thiếu khúc → 422 `UPLOAD_INCOMPLETE` kèm `count`, lượt tải vẫn `receiving`."""
    stage = await make_stage(db_session)
    data = png_bytes(SMALL_CHUNK_BYTES * 3)
    upload_id = await _start(api_client, stage, data)
    pieces = split(data)
    assert len(pieces) == 3
    for response in await send_chunks(api_client, stage, upload_id, pieces[:1]):
        assert response.status_code == 200, response.text

    result = await api_client.post(
        complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=stage.headers
    )

    assert result.status_code == 422
    assert result.json()["code"] == "UPLOAD_INCOMPLETE"
    assert result.json()["count"] == 2
    assert (await _upload_row(db_sessionmaker, upload_id)).status == "receiving"


async def test_drawings_complete_upload__U11(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
) -> None:
    """Tổng byte thật khác `sizeBytes` khai → 422 `UPLOAD_SIZE_MISMATCH`, giữ `receiving`."""
    stage = await make_stage(db_session)
    upload_id = await _start(api_client, stage, b"x" * 900)
    for response in await send_chunks(api_client, stage, upload_id, [png_bytes(500)[:500]]):
        assert response.status_code == 200, response.text

    result = await api_client.post(
        complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=stage.headers
    )

    assert result.status_code == 422
    assert result.json()["code"] == "UPLOAD_SIZE_MISMATCH"
    assert (await _upload_row(db_sessionmaker, upload_id)).status == "receiving"


async def test_drawings_complete_upload__C18(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
) -> None:
    """Một dòng `activity_log` `floor.upload_complete`, actor lấy từ token."""
    stage = await make_stage(db_session)

    _, response = await upload_through(api_client, stage, png_bytes(900))

    assert response.status_code == 200, response.text
    rows = await activity_rows(db_sessionmaker, actor_id=stage.scene.user.id, kind=ActivityKind.FLOOR_UPLOAD_COMPLETE)
    assert len(rows) == 1
    assert rows[0].object_code == stage.level_id


async def test_drawings_complete_upload__C10_queue_once(
    api_client: httpx.AsyncClient, db_session: AsyncSession, broker: SyncRedis, sync_bus_reset: None
) -> None:
    """Lặp `Idempotency-Key` → cùng response và **một** thông điệp `pipeline.cpu`."""
    stage = await make_stage(db_session)
    data = png_bytes(900)
    upload_id = await _start(api_client, stage, data)
    for response in await send_chunks(api_client, stage, upload_id, split(data)):
        assert response.status_code == 200, response.text

    headers = {**stage.headers, "Idempotency-Key": "b2-04-complete-once"}
    path = complete_path(stage.project_id, upload_id)
    first = await api_client.post(path, json={"uploadId": upload_id}, headers=headers)
    second = await api_client.post(path, json={"uploadId": upload_id}, headers=headers)

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json() == second.json()
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


async def test_drawings_complete_upload__C10_no_key_replay(
    api_client: httpx.AsyncClient, db_session: AsyncSession, broker: SyncRedis, sync_bus_reset: None
) -> None:
    """FE gửi lại #7 **không** `Idempotency-Key` → vẫn đúng một thông điệp (bước 1 của [6])."""
    stage = await make_stage(db_session)
    data = png_bytes(900)
    upload_id = await _start(api_client, stage, data)
    for response in await send_chunks(api_client, stage, upload_id, split(data)):
        assert response.status_code == 200, response.text

    path = complete_path(stage.project_id, upload_id)
    first = await api_client.post(path, json={"uploadId": upload_id}, headers=stage.headers)
    second = await api_client.post(path, json={"uploadId": upload_id}, headers=stage.headers)

    assert (first.status_code, second.status_code) == (200, 200), (first.text, second.text)
    assert first.json() == second.json()
    assert len(queued_payloads(broker, CPU_QUEUE)) == 1


# ---------------------------------------------------------------------------
# Nhánh lỗi của bước 3-7 (PDF không đọc được, và dữ liệu đổi giữa chừng)
# ---------------------------------------------------------------------------


async def test_complete_rejects_unreadable_pdf(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    sync_bus_reset: None,
) -> None:
    """PDF có mật khẩu người dùng → 422 `PDF_UNREADABLE` (mã của gói ảnh đi thẳng ra dây)."""
    stage = await make_stage(db_session)

    upload_id, response = await upload_through(
        api_client, stage, pdf_bytes(1, encrypt="user_password"), file_name="ho-so.pdf", mime_type="application/pdf"
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "PDF_UNREADABLE"
    assert (await _upload_row(db_sessionmaker, upload_id)).rejected_code == "PDF_UNREADABLE"


async def test_complete_logs_pdfium_cause_for_corrupt_pdf(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    caplog: pytest.LogCaptureFixture,
    sync_bus_reset: None,
) -> None:
    """NO-124: `FILE_CORRUPT` do `PdfiumError` ghi `__cause__` mức warning trước khi trả W7."""
    caplog.set_level(logging.WARNING, logger="apps.api.drawings.complete")
    stage = await make_stage(db_session)

    _, response = await upload_through(
        api_client, stage, broken_pdf_bytes(), file_name="ho-so.pdf", mime_type="application/pdf"
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "FILE_CORRUPT"
    causes = [record.__dict__["cause"] for record in caplog.records if record.msg == "pdf_page_count_failed"]
    assert len(causes) == 1
    assert "PdfiumError" in causes[0]


async def _gated_complete(
    client: httpx.AsyncClient, app: FastAPI, stage: Stage, upload_id: str
) -> tuple[GatedStorage, "asyncio.Task[httpx.Response]"]:
    """Bắt đầu #7 và dừng nó lại đúng lúc đang ghi `original.*` (ngoài giao dịch)."""
    gated = GatedStorage(app.state.storage, only="original")
    app.state.storage = gated
    task = asyncio.create_task(
        client.post(complete_path(stage.project_id, upload_id), json={"uploadId": upload_id}, headers=stage.headers)
    )
    await asyncio.wait_for(gated.entered.wait(), GATE_WAIT_S)
    return gated, task


async def _ready_upload(client: httpx.AsyncClient, stage: Stage, data: bytes) -> str:
    """#5 + mọi #6 cho một tệp; lượt tải sẵn sàng cho #7."""
    upload_id = await _start(client, stage, data)
    for response in await send_chunks(client, stage, upload_id, split(data)):
        assert response.status_code == 200, response.text
    return upload_id


async def test_complete_conflicts_when_a_chunk_is_replaced(
    api_app: FastAPI, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Khúc bị ghi đè trong lúc #7 đang nối tệp → 409 `UPLOAD_CHUNKS_CHANGED` (FE thử lại)."""
    stage = await make_stage(db_session)
    data = png_bytes(900)
    async with make_api_client(api_app) as client:
        upload_id = await _ready_upload(client, stage, data)
        gated, task = await _gated_complete(client, api_app, stage, upload_id)
        replaced = await client.post(
            chunks_path(stage.project_id, upload_id), json=chunk_body(data[:-1] + b"Z", 0), headers=stage.headers
        )
        gated.release.set()
        response = await asyncio.wait_for(task, GATE_WAIT_S)

    assert replaced.status_code == 200, replaced.text
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "UPLOAD_CHUNKS_CHANGED"


async def test_complete_404_when_floor_is_deleted_midway(
    api_app: FastAPI, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Tầng bị xoá mềm trong lúc #7 đang ghi kho → 404 `resource:"floor"`, không ghi gì."""
    stage = await make_stage(db_session)
    data = png_bytes(900)
    async with make_api_client(api_app) as client:
        upload_id = await _ready_upload(client, stage, data)
        gated, task = await _gated_complete(client, api_app, stage, upload_id)
        await db_session.execute(
            update(FloorRow).where(FloorRow.pk == stage.scene.floor.pk).values(deleted_at=func.now())
        )
        await db_session.commit()
        gated.release.set()
        response = await asyncio.wait_for(task, GATE_WAIT_S)

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "floor"


async def test_complete_404_when_upload_is_deleted_midway(
    api_app: FastAPI, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Lượt tải bị lịch dọn xoá trong lúc #7 đang ghi kho → 404 `resource:"upload"`."""
    stage = await make_stage(db_session)
    data = png_bytes(900)
    async with make_api_client(api_app) as client:
        upload_id = await _ready_upload(client, stage, data)
        gated, task = await _gated_complete(client, api_app, stage, upload_id)
        await db_session.execute(delete(UploadRow).where(UploadRow.id == upload_id))
        await db_session.commit()
        gated.release.set()
        response = await asyncio.wait_for(task, GATE_WAIT_S)

    assert response.status_code == 404, response.text
    assert response.json()["resource"] == "upload"


async def test_reject_survives_upload_deleted_midway(
    api_app: FastAPI, db_session: AsyncSession, sync_bus_reset: None
) -> None:
    """Tệp hỏng **và** lượt tải biến mất giữa chừng → vẫn trả 422 W7, không 500."""
    stage = await make_stage(db_session)
    data = png_bytes(900, truncated=True)
    async with make_api_client(api_app) as client:
        upload_id = await _ready_upload(client, stage, data)
        gated, task = await _gated_complete(client, api_app, stage, upload_id)
        await db_session.execute(delete(UploadRow).where(UploadRow.id == upload_id))
        await db_session.commit()
        gated.release.set()
        response = await asyncio.wait_for(task, GATE_WAIT_S)

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "FILE_CORRUPT"
