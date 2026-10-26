"""Factory tài liệu chưa gán tầng cho test (Strategy B H1, PHASE-1-CONTRACT §2), theo mẫu `drawings.py`.

Ghi thẳng `documents`/`document_pages`/`drawing_regions`/`uploads`, không qua API, không ghi kho
object. Chỉ `flush` — test còn ghi tiếp trong cùng giao dịch.
"""

from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.ids import new_id, new_ulid
from packages.db.models.documents import DocumentPageRow, DocumentRow, DrawingRegionRow
from packages.db.models.drawings import UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.storage.keys import document_original, document_page_preview

DEFAULT_FILE_NAME: Final = "tai-lieu.pdf"
PAGE_SIZE_PX: Final = (1200, 800)


async def make_document(db: AsyncSession, *, project: Project, status: str = "ready", pages: int = 1) -> DocumentRow:
    """Một tài liệu PDF đã `flush` cùng `pages` trang có ảnh xem trước; `failed` mang sẵn `error_code`."""
    document_id = f"doc_{new_ulid(SystemClock())}"
    document = DocumentRow(
        id=document_id,
        project_id=project.id,
        file_name=DEFAULT_FILE_NAME,
        sniffed_kind="pdf",
        original_key=document_original(project.id, document_id, "pdf"),
        page_count=pages,
        status=status,
        error_code="ANALYZE_FAILED" if status == "failed" else None,
        created_by=project.created_by,
    )
    db.add(document)
    await db.flush()
    width, height = PAGE_SIZE_PX
    db.add_all(
        DocumentPageRow(
            document_pk=document.pk,
            page_index=index,
            preview_key=document_page_preview(project.id, document_id, index),
            width_px=width,
            height_px=height,
        )
        for index in range(pages)
    )
    await db.flush()
    return document


async def make_region(
    db: AsyncSession,
    *,
    page: DocumentPageRow,
    box: tuple[float, float, float, float] = (0.1, 0.1, 0.5, 0.5),
    drawing_type: str = "floorPlan",
    floor: FloorRow | None = None,
    status: str = "proposed",
) -> DrawingRegionRow:
    """Một vùng AI đề xuất trên `page`, hộp `(x0, y0, x1, y1)` tỉ lệ; đã `flush`."""
    x0, y0, x1, y1 = box
    region = DrawingRegionRow(
        id=f"reg_{new_ulid(SystemClock())}",
        page_pk=page.pk,
        x0=x0,
        y0=y0,
        x1=x1,
        y1=y1,
        drawing_type=drawing_type,
        type_source="ai",
        source="ai",
        status=status,
        floor_pk=floor.pk if floor else None,
    )
    db.add(region)
    await db.flush()
    return region


async def make_region_upload(db: AsyncSession, *, region: DrawingRegionRow, floor: FloorRow) -> UploadRow:
    """Upload `complete` của một vùng gán vào `floor` như N43 tạo: dùng chung tệp gốc của tài liệu."""
    page = await db.get_one(DocumentPageRow, region.page_pk)
    document = await db.get_one(DocumentRow, page.document_pk)
    upload = UploadRow(
        id=new_id("upl", SystemClock()),
        project_id=document.project_id,
        floor_pk=floor.pk,
        region_id=region.pk,
        file_name=document.file_name,
        declared_size_bytes=1024,
        declared_type="application/pdf",
        sniffed_kind=document.sniffed_kind,
        page_index=page.page_index,
        chunk_count=1,
        status="complete",
        original_key=document.original_key,
        created_by=document.created_by,
    )
    db.add(upload)
    await db.flush()
    return upload
