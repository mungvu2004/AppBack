"""Cổng mở rộng của B2-01 mà B2-03 cắm vào: `project.floors`, `project.create_floors`
(`apps/api/projects/parts.py`, B2-03 [2] "Giao diện công khai", [6] "Hook `project.create_floors`").
"""

from collections.abc import Callable, Mapping, Sequence
from typing import Final, cast

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.core.wire import WireModel
from apps.api.floors.lookup import floor_outs_by_project, new_level_id
from apps.api.floors.schemas import (
    ELEVATION_MAX,
    ELEVATION_MIN,
    HEIGHT_MAX,
    HEIGHT_MIN,
    ORDER_MAX,
    ORDER_MIN,
    clean_mm,
    clean_name,
)
from apps.api.floors.settings import get_floors_settings
from apps.api.projects.parts import PROJECT_CREATE_FLOORS, PROJECT_FLOORS, CreateHook, FloorDraft, ViewPart
from apps.api.projects.summaries import register_floor
from packages.core.clock import Clock
from packages.core.error_codes import VALIDATION
from packages.db.models.floors import FloorRow


async def load_project_floors(db: AsyncSession, project_ids: Sequence[str]) -> Mapping[str, Sequence[WireModel]]:
    """`ViewPart` của `project.floors`: `app=None` (cổng `floor.drawings` dò toàn cục, dinh-chinh §1)."""
    loaded = await floor_outs_by_project(db, project_ids, app=None)
    return cast("Mapping[str, Sequence[WireModel]]", loaded)


def _checked_field[T](i: int, field: str, run: Callable[[], T]) -> T:
    """Chạy một hàm kiểm thuần; `ValueError` → 422 `VALIDATION` `field:"floors.<i>.<field>"`."""
    try:
        return run()
    except ValueError as exc:
        raise VALIDATION.error(field=f"floors.{i}.{field}") from exc


def _checked_draft(i: int, draft: FloorDraft) -> tuple[str, int, int, int]:
    """Tên + dải của một tầng nháp, kiểm lại bằng hàm thuần của `schemas.py` (R-07)."""
    name = _checked_field(i, "name", lambda: cast("str", clean_name(draft.name)))
    order = _checked_field(i, "order", lambda: clean_mm(draft.order, field="order", lo=ORDER_MIN, hi=ORDER_MAX))
    elevation = _checked_field(
        i, "elevationMm", lambda: clean_mm(draft.elevation_mm, field="elevationMm", lo=ELEVATION_MIN, hi=ELEVATION_MAX)
    )
    height = _checked_field(
        i, "heightMm", lambda: clean_mm(draft.height_mm, field="heightMm", lo=HEIGHT_MIN, hi=HEIGHT_MAX)
    )
    return name, order, elevation, height


async def create_project_floors(
    db: AsyncSession, project_id: str, floors: Sequence[FloorDraft], principal: Principal, clock: Clock
) -> None:
    """`CreateHook` của #25: tạo tầng nháp trong giao dịch của #25, sau khi dòng `projects` đã có.

    Ném (lỗi kiểm hay `unique_violation` không thể xảy ra vì `level_id` tự sinh) → rollback cả
    #25 (B2-03 [6]); không ghi nhật ký, không khoá tư vấn (dự án vừa tạo, chưa ai thấy).
    """
    if len(floors) > get_floors_settings().floors_max:
        raise VALIDATION.error(field="floors")
    for i, draft in enumerate(floors):
        name, order, elevation, height = _checked_draft(i, draft)
        level_id = new_level_id(clock)
        db.add(
            FloorRow(
                project_id=project_id,
                level_id=level_id,
                name=name,
                floor_order=order,
                elevation_mm=elevation,
                height_mm=height,
                created_by=principal.user_id,
            )
        )
        await db.flush()
        await register_floor(db, project_id=project_id, floor_level_id=level_id, floor_order=order)


PARTS: Final = (
    ViewPart(PROJECT_FLOORS, load_project_floors),
    CreateHook(PROJECT_CREATE_FLOORS, create_project_floors),
)
