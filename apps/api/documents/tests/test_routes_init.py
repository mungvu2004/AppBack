"""Case của N39 `documents_init_upload` (CASE §2.2 T-init) và `service.mark_uploaded`.

Postgres, Redis thật qua `api_client`; mọi khẳng định "đã ghi" đọc lại bằng session mới (K22).
"""

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.documents.service import mark_uploaded
from apps.api.documents.tests._helpers import init_body, init_path, make_stage
from apps.api.drawings.settings import get_drawings_settings, reset_drawings_settings_cache
from apps.api.projects.tests.test_routes_common import headers_of
from packages.db.models.documents import DocumentPageRow, DocumentRow
from packages.db.models.drawings import UploadRow
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project


async def _rows(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str) -> tuple[UploadRow, DocumentRow]:
    """Dòng `uploads` và tài liệu của nó, đọc bằng session mới."""
    async with sessionmaker() as session:
        upload = (await session.execute(select(UploadRow).where(UploadRow.id == upload_id))).scalar_one()
        stmt = select(DocumentRow).where(DocumentRow.pk == upload.document_pk)
        return upload, (await session.execute(stmt)).scalar_one()


async def _post(client: httpx.AsyncClient, project_id: str, headers: dict[str, str], **body: Any) -> httpx.Response:
    """Gửi N39 với thân `init_body(**body)`."""
    return await client.post(init_path(project_id), json=init_body(**body), headers=headers)


async def test_documents_init_upload__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Init hợp lệ → 201; một tài liệu `uploading` và một upload `receiving` không tầng (H1)."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, size_bytes=3000)

    assert response.status_code == 201, response.text
    wire = response.json()
    chunk_bytes = get_drawings_settings().upload_chunk_bytes
    assert wire["chunkSizeBytes"] == chunk_bytes
    assert wire["chunkCount"] == -(-3000 // chunk_bytes)
    upload, document = await _rows(db_sessionmaker, wire["uploadId"])
    assert (upload.floor_pk, upload.page_index, upload.status) == (None, 0, "receiving")
    assert (document.id, document.status, document.project_id) == (wire["documentId"], "uploading", stage.project.id)


async def test_documents_init_upload__no_floor_needed(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Dự án 0 tầng vẫn 201 — tài liệu tải lên trước khi có tầng nào."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers)

    assert response.status_code == 201, response.text
    assert response.json()["documentId"].startswith("doc_")


async def test_documents_init_upload__C02(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`sizeBytes = 0` → 422 `VALIDATION` `field:"sizeBytes"`."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, size_bytes=0)

    assert response.status_code == 422
    assert response.json()["field"] == "sizeBytes"


async def test_documents_init_upload__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION`."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, unknownKey="x")

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_documents_init_upload__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người ngoài dự án (vai `admin`) → 404 `resource:"project"`, không 403."""
    stage = await make_stage(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await _post(api_client, stage.project.id, headers_of(outsider))

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_documents_init_upload__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thành viên `viewer` (không có `floor.upload`) → 403."""
    owner = await make_user(db_session)
    viewer = await make_user(db_session, role="viewer")
    project = await make_project(db_session, owner=owner, members=[viewer])
    await db_session.commit()

    response = await _post(api_client, project.id, headers_of(viewer, role="viewer"))

    assert response.status_code == 403


async def test_documents_init_upload__C11(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quá trần hạn mức init → 429 `RATE_LIMITED` kèm `Retry-After`."""
    monkeypatch.setenv("DRAWINGS_INIT_RATE_LIMIT", "1")
    reset_drawings_settings_cache()
    stage = await make_stage(db_session)
    try:
        first = await _post(api_client, stage.project.id, stage.headers)
        second = await _post(api_client, stage.project.id, stage.headers)
    finally:
        reset_drawings_settings_cache()

    assert first.status_code == 201, first.text
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"
    assert second.headers["Retry-After"]


async def test_documents_init_upload__C21(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`projectId` trong thân khác đường → 422 `PATH_BODY_MISMATCH` (guard W21 chạy trước schema), không ghi."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, projectId="prj_00000000000000000000000000")

    assert response.status_code == 422
    assert response.json()["code"] == "PATH_BODY_MISMATCH"


async def test_documents_init_upload__U05(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`pageIndex` không có ở N39 (tài liệu tách mọi trang) → 422 `VALIDATION`."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, pageIndex=2)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_documents_init_upload__U08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`mimeType` khai lệch đuôi tệp → 422 `FILE_TYPE_MISMATCH` (luật #5)."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, mimeType="image/png")

    assert response.status_code == 422
    assert response.json()["code"] == "FILE_TYPE_MISMATCH"


async def test_documents_init_upload__U09(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`mimeType` rỗng được nhận; magic bytes quyết ở #7."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, mimeType="")

    assert response.status_code == 201, response.text
    upload, _ = await _rows(db_sessionmaker, response.json()["uploadId"])
    assert upload.declared_type == ""


async def test_documents_init_upload__U12(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tệp `.dwg` → 422 `CAD_NOT_SUPPORTED`."""
    stage = await make_stage(db_session)

    response = await _post(api_client, stage.project.id, stage.headers, file_name="nha.dwg", mimeType="image/vnd.dwg")

    assert response.status_code == 422
    assert response.json()["code"] == "CAD_NOT_SUPPORTED"


async def test_documents_init_upload__rejects_size_above_cap(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`sizeBytes` quá `UPLOAD_MAX_BYTES` → 413 như #5."""
    stage = await make_stage(db_session)

    response = await _post(
        api_client, stage.project.id, stage.headers, size_bytes=get_drawings_settings().upload_max_bytes + 1
    )

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_mark_uploaded_sets_analyzing_and_pages_once(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`mark_uploaded` ghi kết quả #7 lên tài liệu, upsert trang; gọi lại không nhân đôi trang (J06)."""
    stage = await make_stage(db_session)
    wire = (await _post(api_client, stage.project.id, stage.headers)).json()

    for _ in range(2):
        await mark_uploaded(db_session, upload_id=wire["uploadId"], page_count=2, sniffed_kind="pdf", original_key="k")

    stmt = select(DocumentRow).where(DocumentRow.id == wire["documentId"])
    document = (await db_session.execute(stmt)).scalar_one()
    assert (document.status, document.page_count, document.sniffed_kind) == ("analyzing", 2, "pdf")
    assert document.original_key == "k"
    pages = await db_session.execute(
        select(DocumentPageRow.page_index).where(DocumentPageRow.document_pk == document.pk)
    )
    assert sorted(pages.scalars()) == [0, 1]
