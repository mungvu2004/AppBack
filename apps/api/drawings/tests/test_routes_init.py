"""Case của #5 `drawings_init_upload` (CASE §2.2 T-init + `cases.toml` `extra`).

Postgres, Redis và kho local thật: `api_client` chạy app thật nên mọi khẳng định "đã ghi"
đọc lại qua session khác (K22). Không test nào ở đây gửi byte: #5 chỉ khai kích thước, nên
`chunk_count` suy ra từ `UPLOAD_CHUNK_BYTES` mặc định là đủ.
"""

import unicodedata
from typing import Final

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.drawings.settings import get_drawings_settings, reset_drawings_settings_cache
from apps.api.drawings.tests._upload_helpers import headers_of, init_body, init_path, make_stage
from packages.db.models.drawings import UploadRow
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.access import assert_one_activity

NFD_NAME: Final = unicodedata.normalize("NFD", "mặt-bằng.png")


async def _upload_row(sessionmaker: async_sessionmaker[AsyncSession], upload_id: str) -> UploadRow:
    """Dòng `uploads` đọc lại bằng session mới (K22)."""
    async with sessionmaker() as session:
        return (await session.execute(select(UploadRow).where(UploadRow.id == upload_id))).scalar_one()


async def test_drawings_init_upload__C01(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Init hợp lệ → 200 `Progress` `pending` và một dòng `uploads` `receiving`."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=3000)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 200, response.text
    wire = response.json()
    assert wire["status"] == "pending"
    assert wire["step"] == "preprocess"
    assert wire["progressPercent"] == 0
    row = await _upload_row(db_sessionmaker, wire["id"])
    assert row.status == "receiving"
    assert row.declared_size_bytes == 3000
    expected = -(-3000 // get_drawings_settings().upload_chunk_bytes)
    assert row.chunk_count == expected


async def test_drawings_init_upload__C02(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`sizeBytes = 0` → 422 `VALIDATION` kèm `field` (luật của schema)."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=0)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"
    assert response.json()["field"] == "sizeBytes"


async def test_drawings_init_upload__C03(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Khoá lạ trong thân → 422 `VALIDATION` (`WireRequest` `extra="forbid"`)."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, unknownKey="x")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION"


async def test_drawings_init_upload__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người ngoài dự án (vai `admin`) → 404 `resource:"project"`, không 403."""
    stage = await make_stage(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000)

    path = init_path(stage.project_id, stage.level_id)
    response = await api_client.post(path, json=body, headers=headers_of(outsider))

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_drawings_init_upload__C07(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Thành viên vai `viewer` (vai mạnh nhất không có `floor.upload`) → 403."""
    owner = await make_user(db_session)
    viewer = await make_user(db_session, role="viewer")
    project = await make_project(db_session, owner=owner, members=[viewer])
    floor = await make_floor(db_session, project=project)
    await db_session.commit()
    body = init_body(project.id, floor.level_id, size_bytes=1000)

    path = init_path(project.id, floor.level_id)
    response = await api_client.post(path, json=body, headers=headers_of(viewer, role="viewer"))

    assert response.status_code == 403


async def test_drawings_init_upload__C08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tầng không có (hoặc đã xoá mềm) → 404 `resource:"floor"`."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, "L-DEADBEEF12", size_bytes=1000)

    path = init_path(stage.project_id, "L-DEADBEEF12")
    response = await api_client.post(path, json=body, headers=stage.headers)

    assert response.status_code == 404
    assert response.json()["resource"] == "floor"


async def test_drawings_init_upload__C11(
    api_client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quá `DRAWINGS_INIT_RATE_LIMIT` → 429 `RATE_LIMITED` kèm `Retry-After`."""
    monkeypatch.setenv("DRAWINGS_INIT_RATE_LIMIT", "1")
    reset_drawings_settings_cache()
    stage = await make_stage(db_session)
    path = init_path(stage.project_id, stage.level_id)
    try:
        first = await api_client.post(
            path, json=init_body(stage.project_id, stage.level_id, size_bytes=1000), headers=stage.headers
        )
        second = await api_client.post(
            path, json=init_body(stage.project_id, stage.level_id, size_bytes=2000), headers=stage.headers
        )
    finally:
        reset_drawings_settings_cache()

    assert first.status_code == 200, first.text
    assert second.status_code == 429
    assert second.json()["code"] == "RATE_LIMITED"
    assert second.headers["Retry-After"]


async def test_drawings_init_upload__C21(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`projectId` trong thân khác đường → 422 `PATH_BODY_MISMATCH`, không ghi gì."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, projectId="prj_00000000000000000000000000")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "PATH_BODY_MISMATCH"


async def test_drawings_init_upload__C16(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`fileName` gửi NFD được lưu NFC (chuỗi người nhập, `cases.toml` `extra`)."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, file_name=NFD_NAME)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 200, response.text
    row = await _upload_row(db_sessionmaker, response.json()["id"])
    assert row.file_name == unicodedata.normalize("NFC", NFD_NAME)
    assert row.file_name != NFD_NAME


async def test_drawings_init_upload__C18(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Một dòng `activity_log` `floor.upload` với `objectCode` = `level_id` của tầng."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 200, response.text
    await assert_one_activity(
        db_sessionmaker,
        actor_id=stage.scene.user.id,
        kind=ActivityKind.FLOOR_UPLOAD,
        object_code=stage.level_id,
    )


async def test_drawings_init_upload__U05(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`pageIndex != 0` cho một ảnh → 422 `VALIDATION` `field:"pageIndex"`."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, pageIndex=2)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["field"] == "pageIndex"


async def test_drawings_init_upload__U08(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`mimeType` khai lệch đuôi tệp → 422 `FILE_TYPE_MISMATCH`."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, mimeType="application/pdf")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "FILE_TYPE_MISMATCH"


async def test_drawings_init_upload__U09(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`File.type` rỗng của trình duyệt được nhận; magic bytes quyết ở #7."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, mimeType="")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 200, response.text
    row = await _upload_row(db_sessionmaker, response.json()["id"])
    assert row.declared_type == ""
    assert row.sniffed_kind is None


async def test_drawings_init_upload__U12(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Tệp `.dwg` → 422 `CAD_NOT_SUPPORTED` ngay ở init."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, file_name="nha.dwg", mimeType="image/vnd.dwg")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "CAD_NOT_SUPPORTED"


async def test_init_rejects_size_above_cap(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """`sizeBytes` quá `UPLOAD_MAX_BYTES` → 413 (`src/lib/upload/validate.ts:41-47`)."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=get_drawings_settings().upload_max_bytes + 1)

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 413
    assert response.json()["code"] == "PAYLOAD_TOO_LARGE"


async def test_init_rejects_unknown_extension(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Đuôi ngoài `.png/.jpg/.jpeg/.pdf` → 422 `FILE_TYPE_MISMATCH`."""
    stage = await make_stage(db_session)
    body = init_body(stage.project_id, stage.level_id, size_bytes=1000, file_name="ban-ve.tiff", mimeType="image/tiff")

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 422
    assert response.json()["code"] == "FILE_TYPE_MISMATCH"


async def test_init_accepts_page_index_for_pdf(
    api_client: httpx.AsyncClient, db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`pageIndex` khác 0 hợp lệ với PDF; số trang thật chỉ kiểm được ở #7."""
    stage = await make_stage(db_session)
    body = init_body(
        stage.project_id,
        stage.level_id,
        size_bytes=1000,
        file_name="ho-so.pdf",
        mimeType="application/pdf",
        pageIndex=3,
    )

    response = await api_client.post(init_path(stage.project_id, stage.level_id), json=body, headers=stage.headers)

    assert response.status_code == 200, response.text
    row = await _upload_row(db_sessionmaker, response.json()["id"])
    assert row.page_index == 3
