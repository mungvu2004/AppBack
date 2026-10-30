"""Case của N41 `drawings_page_thumbnails` (Đ: C01 C06 C08) + quyền và tệp không phải PDF (UX41 U05).

Thân là byte PDF thô; route chỉ dựng ảnh rồi trả, không ghi gì nên không có C18.
"""

import base64

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.drawings.tests._upload_helpers import headers_of, make_stage, pdf_bytes, upload_png
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock

PNG_PREFIX = "data:image/png;base64,"
PDF_HEADERS = {"Content-Type": "application/pdf"}


def thumbnails_path(project_id: str) -> str:
    """Đường N41 của một dự án."""
    return f"/api/projects/{project_id}/drawings/page-thumbnails"


async def test_drawings_page_thumbnails__C01(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """PDF ba trang → ba `data:` URL PNG theo thứ tự trang."""
    stage = await make_stage(db_session)

    response = await api_client.post(
        thumbnails_path(stage.project_id), content=pdf_bytes(3), headers={**stage.headers, **PDF_HEADERS}
    )

    assert response.status_code == 200, response.text
    pages = response.json()["pages"]
    assert len(pages) == 3
    for page in pages:
        assert page.startswith(PNG_PREFIX)
        assert base64.b64decode(page.removeprefix(PNG_PREFIX)).startswith(b"\x89PNG")


async def test_drawings_page_thumbnails__C06(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Người ngoài dự án (vai `admin`) → 404 `resource:"project"`."""
    stage = await make_stage(db_session)
    outsider = await make_user(db_session, role="admin")
    await db_session.commit()

    response = await api_client.post(
        thumbnails_path(stage.project_id), content=pdf_bytes(2), headers={**headers_of(outsider), **PDF_HEADERS}
    )

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_drawings_page_thumbnails__C08(
    api_client: httpx.AsyncClient, db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án đã xoá mềm → 404, kể cả cho chính chủ."""
    owner = await make_user(db_session)
    project = await make_project(db_session, owner=owner, deleted_at=fake_clock.now())
    await db_session.commit()

    response = await api_client.post(
        thumbnails_path(project.id), content=pdf_bytes(2), headers={**headers_of(owner), **PDF_HEADERS}
    )

    assert response.status_code == 404
    assert response.json()["resource"] == "project"


async def test_drawings_page_thumbnails_viewer_forbidden(
    api_client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Vai `viewer` không có `floor.upload` → 403, cùng khoá với #5."""
    owner = await make_user(db_session)
    viewer = await make_user(db_session, role="viewer")
    project = await make_project(db_session, owner=owner, members=[viewer])
    await make_floor(db_session, project=project)
    await db_session.commit()

    response = await api_client.post(
        thumbnails_path(project.id), content=pdf_bytes(2), headers={**headers_of(viewer, role="viewer"), **PDF_HEADERS}
    )

    assert response.status_code == 403


async def test_drawings_page_thumbnails_not_pdf(api_client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    """Byte PNG → 422 `FILE_TYPE_MISMATCH`, không 500."""
    stage = await make_stage(db_session)

    response = await api_client.post(
        thumbnails_path(stage.project_id), content=upload_png(), headers={**stage.headers, **PDF_HEADERS}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "FILE_TYPE_MISMATCH"
