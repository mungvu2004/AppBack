"""N7b — lịch sử lượt chạy pipeline của một dự án, mới nhất trước (UIFIX-B7, N5-08).

Chỉ đọc `pipeline_runs` nối `floors`; tầng đã xoá mềm bị bỏ như N7. Cắt trang theo
`(created_at, id)` giảm dần — cùng khoá với index `floor_pk, created_at` của bảng.
"""

from datetime import datetime
from typing import Annotated, Final

from fastapi import Depends
from sqlalchemy import literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.deps import DbSession
from apps.api.core.pagination import PageParams, decode_cursor, encode_cursor, page_params
from apps.api.core.routing import protected_router
from apps.api.drawings.schemas import PipelineRunOut, PipelineRunPage
from apps.api.projects.access import require_project
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow

RUNS_OP: Final = "drawings_list_pipeline_runs"
"""`op` ký vào cursor: cursor của danh sách khác dùng ở đây → 422 `CURSOR_INVALID`."""

router = protected_router(tags=["drawings"])
RunsPage = Annotated[PageParams, Depends(page_params())]


async def list_pipeline_runs(db: AsyncSession, project_id: str, page: PageParams) -> PipelineRunPage:
    """Một trang lượt chạy của các tầng chưa xoá; lấy dư một dòng để biết còn trang sau."""
    stmt = (
        select(PipelineRunRow, FloorRow.level_id, FloorRow.name)
        .join(FloorRow, FloorRow.pk == PipelineRunRow.floor_pk)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
        .order_by(PipelineRunRow.created_at.desc(), PipelineRunRow.id.desc())
        .limit(page.limit + 1)
    )
    if page.cursor is not None:
        after = decode_cursor(page.cursor, RUNS_OP, {"project": project_id})
        stmt = stmt.where(
            tuple_(PipelineRunRow.created_at, PipelineRunRow.id)
            < tuple_(literal(datetime.fromisoformat(after["at"])), literal(str(after["id"])))
        )
    rows = (await db.execute(stmt)).all()
    has_more = len(rows) > page.limit
    rows = rows[: page.limit]
    items = [
        PipelineRunOut(
            run_id=run.id,
            upload_id=run.upload_id,
            floor_id=level_id,
            floor_name=name,
            status=run.status,
            step=run.current_step,
            progress_percent=run.progress_percent,
            error_code=run.error_code,
            created_at=run.created_at,
            updated_at=run.updated_at,
            started_at=run.started_at,
            ended_at=run.ended_at,
            superseded_by=run.superseded_by,
        )
        for run, level_id, name in rows
    ]
    last = rows[-1][0] if has_more and rows else None
    return PipelineRunPage(
        items=items,
        next_cursor=(
            encode_cursor(RUNS_OP, {"project": project_id}, {"at": last.created_at.isoformat(), "id": last.id})
            if last is not None
            else None
        ),
    )


@router.get("/projects/{project_id}/pipeline-runs", dependencies=[Depends(require_project())])
async def drawings_list_pipeline_runs(project_id: str, page: RunsPage, db: DbSession) -> PipelineRunPage:
    """N7b — các lượt chạy pipeline của dự án, mới nhất trước (thành viên đọc được)."""
    return await list_pipeline_runs(db, project_id, page)
