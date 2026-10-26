"""Bảng tài liệu/trang/vùng và CHECK mới của `uploads` trên Postgres thật (K23, Strategy B H1)."""

from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.documents import DocumentPageRow, DocumentRow
from packages.db.models.drawings import UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.testing.factories.auth import make_user
from packages.testing.factories.documents import make_document, make_region, make_region_upload
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project


async def _scene(db: AsyncSession) -> tuple[Project, FloorRow, DocumentRow, DocumentPageRow]:
    """Dự án + tầng + tài liệu một trang đã `flush`."""
    project = await make_project(db, owner=await make_user(db))
    floor = await make_floor(db, project=project, order=0)
    document = await make_document(db, project=project)
    page = (await db.execute(select(DocumentPageRow).where(DocumentPageRow.document_pk == document.pk))).scalar_one()
    return project, floor, document, page


@pytest.mark.parametrize("box", [(0.5, 0.1, 0.5, 0.6), (0.6, 0.1, 0.5, 0.6), (0.1, 0.1, 1.01, 0.6), (-0.1, 0, 1, 1)])
async def test_documents_model__region_bbox_check(db_session: AsyncSession, box: tuple[float, ...]) -> None:
    """Hộp suy biến (x0 ≥ x1) hay ra ngoài `[0, 1]` → `ck_drawing_regions_box`; hộp đủ trang đi qua."""
    _, _, _, page = await _scene(db_session)
    await make_region(db_session, page=page, box=(0, 0, 1, 1))
    with pytest.raises(IntegrityError, match="ck_drawing_regions_box"):
        await make_region(db_session, page=page, box=box)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "constraint"),
    [
        ("drawing_type", "plan", "ck_drawing_regions_type"),
        ("type_source", "ml", "ck_drawing_regions_type_source"),
        ("source", "ml", "ck_drawing_regions_source"),
        ("status", "done", "ck_drawing_regions_status"),
        ("doc_status", "done", "ck_documents_status"),
        ("doc_error", "failed", "ck_documents_error"),
        ("page_count", 21, "ck_documents_page_count"),
    ],
)
async def test_documents_model__type_checks(
    db_session: AsyncSession, field: str, value: Any, constraint: str
) -> None:
    """Giá trị ngoài tập của loại bản vẽ, nguồn, trạng thái → `IntegrityError` đúng CHECK."""
    _, _, document, page = await _scene(db_session)
    region = await make_region(db_session, page=page)
    match field:
        case "doc_status":
            document.status = value
        case "doc_error":
            document.status = value  # `failed` mà không có `error_code`
        case "page_count":
            document.page_count = value
        case _:
            setattr(region, field, value)
    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


@pytest.mark.parametrize(("with_floor", "with_document"), [(False, False), (True, True)])
async def test_uploads__floor_or_document_check(
    db_session: AsyncSession, with_floor: bool, with_document: bool
) -> None:
    """Upload thiếu cả tầng lẫn tài liệu, hay có cả hai → `ck_uploads_floor_or_document`."""
    project, floor, document, _ = await _scene(db_session)
    db_session.add(_upload(project, floor_pk=floor.pk if with_floor else None, document=document if with_document else None))
    with pytest.raises(IntegrityError, match="ck_uploads_floor_or_document"):
        await db_session.flush()


async def test_uploads__floor_or_document_check_accepts_one(db_session: AsyncSession) -> None:
    """Upload tài liệu (không tầng) và upload vùng (có tầng, có `region_id`) đều ghi được."""
    project, floor, document, page = await _scene(db_session)
    db_session.add(_upload(project, floor_pk=None, document=document))
    region = await make_region(db_session, page=page, floor=floor)
    upload = await make_region_upload(db_session, region=region, floor=floor)
    assert (upload.region_id, upload.original_key, upload.document_pk) == (region.pk, document.original_key, None)


async def test_documents_model__page_unique(db_session: AsyncSession) -> None:
    """Trùng `(document_pk, page_index)` → `uq_document_pages_document_page`."""
    _, _, document, _ = await _scene(db_session)
    db_session.add(DocumentPageRow(document_pk=document.pk, page_index=0))
    with pytest.raises(IntegrityError, match="uq_document_pages_document_page"):
        await db_session.flush()


def _upload(project: Project, *, floor_pk: int | None, document: DocumentRow | None) -> UploadRow:
    """Một `UploadRow` hợp lệ trừ cặp `floor_pk`/`document_pk` đang thử."""
    return UploadRow(
        id=new_id("upl", SystemClock()),
        project_id=project.id,
        floor_pk=floor_pk,
        document_pk=document.pk if document else None,
        file_name="tai-lieu.pdf",
        declared_size_bytes=1024,
        declared_type="application/pdf",
        page_index=0,
        chunk_count=1,
        status="receiving",
        created_by=project.created_by,
    )
