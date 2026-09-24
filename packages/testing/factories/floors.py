"""Factory tầng cho test (B2-03), theo mẫu `packages/testing/factories/projects.py`.

Ghi thẳng `floors` + dòng đếm (`summaries.register_floor`), không qua API; chỉ `flush`
như `make_project` — test còn ghi tiếp trong cùng giao dịch và tự quyết lúc commit.
"""

from typing import Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.floors.lookup import new_level_id
from apps.api.projects.summaries import register_floor
from packages.core.clock import SystemClock
from packages.core.text import nfc
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project

DEFAULT_NAME: Final = "Tầng thử"
DEFAULT_ELEVATION_MM: Final = 0


async def _active_floor_count(db: AsyncSession, project_id: str) -> int:
    """Số tầng chưa xoá của dự án — mặc định `order` của tầng mới là đặt ở cuối."""
    stmt = (
        select(func.count())
        .select_from(FloorRow)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
    )
    return (await db.execute(stmt)).scalar_one()


async def make_floor(
    db: AsyncSession,
    *,
    project: Project,
    level_id: str | None = None,
    name: str | None = None,
    order: int | None = None,
    height_mm: int = 3000,
) -> FloorRow:
    """Một tầng đã `flush`, kèm dòng đếm (`register_floor`); `order=None` → đặt ở cuối."""
    resolved_order = order if order is not None else await _active_floor_count(db, project.id)
    floor = FloorRow(
        project_id=project.id,
        level_id=level_id if level_id is not None else new_level_id(SystemClock()),
        name=nfc(name if name is not None else DEFAULT_NAME),
        floor_order=resolved_order,
        elevation_mm=DEFAULT_ELEVATION_MM,
        height_mm=height_mm,
        created_by=project.created_by,
    )
    db.add(floor)
    await db.flush()
    await register_floor(db, project_id=project.id, floor_level_id=floor.level_id, floor_order=resolved_order)
    return floor
