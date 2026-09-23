"""Đọc và khoá tầng (B2-03 [2], [6] "Khoá", "Dựng `Floor`"); tên công khai chốt ở
`dinh-chinh.md` §9. Không nhập `fastapi`/`starlette`: `jobs.py` của lịch dọn và mã
worker gọi thẳng module này (BE-00 §7 "Hàm worker nhập").
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.parts import FLOOR_DRAWINGS, view_part
from apps.api.projects.wire import DrawingOut, FloorOut
from packages.core.clock import Clock
from packages.core.ids import new_id
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary


async def _drawings_of(
    db: AsyncSession, pks: Sequence[int], *, app: object | None
) -> Mapping[str, Sequence[DrawingOut]]:
    """Một lượt `view_part(FLOOR_DRAWINGS)` cho cả lô, khoá `str(pk)`; chưa ai cài → rỗng."""
    part = view_part(FLOOR_DRAWINGS, app=app)
    if part is None or not pks:
        return {}
    # `ViewPart` của `FLOOR_DRAWINGS` khai `DrawingOut` (parts.py); sai kiểu hỏng ngay ở
    # test của B2-04, như `_project_outs` (B2-01 service.py) làm với `PROJECT_FLOORS`.
    loaded = await part.load(db, [str(pk) for pk in pks])
    return cast("Mapping[str, Sequence[DrawingOut]]", loaded)


def _floor_out(row: FloorRow, area_m2: Decimal | None, drawings: Mapping[str, Sequence[DrawingOut]]) -> FloorOut:
    """`FloorOut` của một dòng; `area_m2` `Decimal` → `float` làm tròn 2 chữ số, `NULL` → vắng."""
    return FloorOut(
        id=row.level_id,
        name=row.name,
        order=row.floor_order,
        elevation_mm=row.elevation_mm,
        height_mm=row.height_mm,
        area_m2=float(round(area_m2, 2)) if area_m2 is not None else None,
        drawings=list(drawings.get(str(row.pk), ())),
    )


async def _load_floor_outs(
    db: AsyncSession, project_ids: Sequence[str], *, floor_pks: Sequence[int] | None = None, app: object | None = None
) -> dict[str, list[FloorOut]]:
    """Lõi dùng chung của `floor_outs` và `floor_outs_by_project` (dinh-chinh §9, R-07).

    Một truy vấn `floors` ⟕ `project_floor_summaries` cho cả lô `project_ids`, chỉ tầng
    chưa xoá, sắp `(project_id, floor_order, pk)`; số câu SQL không đổi theo số tầng hay
    số dự án. Trả **mọi** id được hỏi, kể cả dự án không tầng nào (`[]`).
    """
    result: dict[str, list[FloorOut]] = {project_id: [] for project_id in project_ids}
    if not project_ids:
        return result
    stmt = (
        select(FloorRow, ProjectFloorSummary.area_m2)
        .outerjoin(
            ProjectFloorSummary,
            and_(
                ProjectFloorSummary.project_id == FloorRow.project_id,
                ProjectFloorSummary.floor_level_id == FloorRow.level_id,
            ),
        )
        .where(FloorRow.project_id.in_(project_ids), FloorRow.deleted_at.is_(None))
        .order_by(FloorRow.project_id, FloorRow.floor_order, FloorRow.pk)
    )
    if floor_pks is not None:
        stmt = stmt.where(FloorRow.pk.in_(floor_pks))
    rows = (await db.execute(stmt)).all()
    drawings = await _drawings_of(db, [row.FloorRow.pk for row in rows], app=app)
    for row in rows:
        floor_row: FloorRow = row.FloorRow
        result[floor_row.project_id].append(_floor_out(floor_row, row.area_m2, drawings))
    return result


async def floor_outs_by_project(
    db: AsyncSession, project_ids: Sequence[str], *, app: object | None = None
) -> dict[str, list[FloorOut]]:
    """`FloorOut` chưa xoá của mỗi dự án trong `project_ids` (cổng `project.floors` của B2-01)."""
    return await _load_floor_outs(db, list(project_ids), app=app)


async def floor_outs(
    db: AsyncSession, *, project_id: str, floor_pks: Sequence[int] | None = None, app: object | None = None
) -> list[FloorOut]:
    """`FloorOut` chưa xoá của một dự án, lọc `floor_pks` nếu có (lọc trong SQL, không ở Python)."""
    return (await _load_floor_outs(db, [project_id], floor_pks=floor_pks, app=app))[project_id]


async def get_floor(db: AsyncSession, *, project_id: str, level_id: str, for_update: bool = False) -> FloorRow | None:
    """Tầng chưa xoá của dự án theo `level_id`; `for_update=True` khoá dòng (`FOR UPDATE`)."""
    stmt = select(FloorRow).where(
        FloorRow.project_id == project_id, FloorRow.level_id == level_id, FloorRow.deleted_at.is_(None)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return (await db.execute(stmt)).scalar_one_or_none()


async def lock_project_floors(db: AsyncSession, project_id: str) -> None:
    """Khoá tư vấn mutex theo dự án (BE-00 §7): đầu tiên trong thứ tự khoá của mọi route ghi
    và bước xoá của lịch dọn — trước `SELECT … FOR UPDATE` trên `floors`, trước `summaries.*`,
    trước `touch_project`. Chỉ module này dùng khoá tên `floors:<project_id>`.
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"floors:{project_id}"})


def new_level_id(clock: Clock) -> str:
    """`level_id` mới, `is_spatial_id("level", …)` đúng (dinh-chinh §7): `L-` + thân ULID của `new_id`.

    `packages/core/ids.py` (B0-02) không có hàm sinh ULID trần và không được sửa (K27);
    đường nâng cấp là thêm `new_ulid` vào B0-02 (ghi nợ).
    """
    return "L-" + new_id("job", clock).split("_", 1)[1]
