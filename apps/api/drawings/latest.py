"""N7 — lượt tải mới nhất của từng tầng (`HOP-DONG-MOI.md:243`, B2-04 [6] "N7").

Màn xử lý mở lên cần biết theo dõi `uploadId` nào cho mỗi tầng. "Mới nhất" là theo
**lượt chạy** chứ không theo lượt tải: một init bỏ dở (chưa có lượt chạy) không được che
lượt tải đang chạy pipeline, còn khi U2 hỏng và người dùng chạy lại pipeline trên U1 thì
U1 lại là mục của tầng. Tầng chưa có lượt chạy nào mới rơi về lượt tải mới nhất khác
`rejected`.

Tất cả nằm trong **một** câu: `DISTINCT ON (floors.pk)` chọn ứng viên của mỗi tầng, câu
ngoài sắp và cắt trang theo `(floor_order, floors.pk)` — thứ tự `Floor.order` của H1.
"""

from collections.abc import Sequence
from typing import Annotated, Any, Final

from fastapi import Depends
from sqlalchemy import Row, Select, or_, select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import DbSession
from apps.api.core.pagination import PageParams, decode_cursor, encode_cursor, page_params
from apps.api.core.routing import protected_router
from apps.api.drawings.drawings import drawing_url
from apps.api.drawings.schemas import LatestFloorUploadOut, LatestFloorUploadPage
from apps.api.drawings.urls import signer
from apps.api.projects.access import require_project
from packages.db.models.drawings import DrawingRow, PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow

LATEST_OP: Final = "drawings_list_latest_uploads"
"""`op` ký vào cursor: cursor của danh sách khác dùng ở đây → 422 `CURSOR_INVALID`."""

MAX_LIMIT: Final = 200

router = protected_router(tags=["drawings"])
LatestPage = Annotated[PageParams, Depends(page_params(MAX_LIMIT))]


def _candidates(project_id: str) -> Select[Any]:
    """Một ứng viên mỗi tầng chưa xoá: `DISTINCT ON (floors.pk)` trên `uploads` của tầng.

    Thứ tự trong `DISTINCT ON` **là** luật chọn: ứng viên có lượt chạy đứng trước
    (`nulls_last` trên `run.created_at`), rồi lượt chạy mới nhất, rồi lượt tải mới nhất.
    Tầng không có lượt chạy nào thì `rejected` bị loại — nó chưa bao giờ là ảnh của tầng.
    """
    latest_run = (
        select(PipelineRunRow.created_at.label("run_created_at"), PipelineRunRow.id.label("run_id"))
        .where(PipelineRunRow.upload_id == UploadRow.id)
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(1)
        .lateral("latest_run")
    )
    return (
        select(
            FloorRow.level_id.label("floor_id"),
            FloorRow.name.label("floor_name"),
            FloorRow.floor_order.label("floor_order"),
            FloorRow.pk.label("floor_pk"),
            UploadRow.id.label("upload_id"),
            DrawingRow.page_key.label("page_key"),
        )
        .select_from(FloorRow)
        .join(UploadRow, UploadRow.floor_pk == FloorRow.pk)
        .outerjoin(latest_run, true())
        .outerjoin(DrawingRow, (DrawingRow.floor_pk == FloorRow.pk) & (DrawingRow.upload_id == UploadRow.id))
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
        .where(or_(latest_run.c.run_id.is_not(None), UploadRow.status != "rejected"))
        .distinct(FloorRow.pk)
        .order_by(
            FloorRow.pk,
            latest_run.c.run_created_at.desc().nulls_last(),
            latest_run.c.run_id.desc().nulls_last(),
            UploadRow.created_at.desc(),
            UploadRow.id.desc(),
        )
    )


async def _page_rows(db: AsyncSession, project_id: str, page: PageParams) -> Sequence[Row[Any]]:
    """Trang ứng viên đã sắp `(floor_order, pk)`, lấy dư **một** dòng để biết còn trang sau."""
    picked = _candidates(project_id).subquery("picked")
    stmt = select(picked).order_by(picked.c.floor_order, picked.c.floor_pk).limit(page.limit + 1)
    if page.cursor is not None:
        after = decode_cursor(page.cursor, LATEST_OP, {"project": project_id})
        stmt = stmt.where(tuple_(picked.c.floor_order, picked.c.floor_pk) > tuple_(after["order"], after["pk"]))
    return (await db.execute(stmt)).all()


async def list_latest_uploads(db: AsyncSession, project_id: str, page: PageParams) -> LatestFloorUploadPage:
    """N7: một trang "tầng → lượt tải đang theo dõi", sắp theo `Floor.order`.

    `sourceImageUrl` chỉ có khi bản vẽ **đang dùng** của tầng đúng là của lượt tải này:
    ảnh của một lượt cũ không còn mô tả cái người dùng đang chờ.
    """
    rows = await _page_rows(db, project_id, page)
    has_more = len(rows) > page.limit
    rows = rows[: page.limit]
    storage = signer()
    items = [
        LatestFloorUploadOut(
            floor_id=row.floor_id,
            floor_name=row.floor_name,
            upload_id=row.upload_id,
            source_image_url=await drawing_url(storage, row.page_key) if row.page_key is not None else None,
        )
        for row in rows
    ]
    last = rows[-1] if rows else None
    return LatestFloorUploadPage(
        items=items,
        next_cursor=(
            encode_cursor(LATEST_OP, {"project": project_id}, {"order": last.floor_order, "pk": last.floor_pk})
            if has_more and last is not None
            else None
        ),
    )


@router.get("/projects/{project_id}/drawings/uploads/latest", dependencies=[Depends(require_project())])
async def drawings_list_latest_uploads(project_id: str, page: LatestPage, db: DbSession) -> LatestFloorUploadPage:
    """N7 — lượt tải mới nhất của từng tầng chưa xoá, sắp theo `Floor.order`."""
    return await list_latest_uploads(db, project_id, page)
