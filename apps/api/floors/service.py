"""Nghiệp vụ 5 thao tác tầng (B2-03 [6]).

Thứ tự khoá của mọi route ghi (BE-00 §7, B2-03 [6]): `lock_project_floors` → dòng `floors`
cần ghi `FOR UPDATE` theo `pk` → `summaries.*` → `touch_project` cuối cùng. Mọi bất biến
(trùng id, trần tầng, tập tầng) kiểm **sau** khoá tư vấn, trong giao dịch ghi.
"""

from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.core.auth import Principal
from apps.api.floors.errors import FLOOR_ID_TAKEN, FLOOR_LIMIT_REACHED, FLOOR_REORDER_MISMATCH
from apps.api.floors.lookup import floor_outs, get_floor, lock_project_floors
from apps.api.floors.schemas import FloorCreateIn, FloorPatchIn
from apps.api.floors.settings import get_floors_settings
from apps.api.projects.summaries import register_floor, set_floor_orders, touch_project, unregister_floor
from apps.api.projects.wire import FloorOut
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND, PATH_BODY_MISMATCH
from packages.db.errors import unique_violation
from packages.db.models.floors import FloorRow


async def _locked_rows(db: AsyncSession, project_id: str, level_id: str) -> list[FloorRow]:
    """Mọi dòng (kể cả đã xoá) của `(project_id, level_id)`, khoá `FOR UPDATE` (bước 1 của #10)."""
    stmt = select(FloorRow).where(FloorRow.project_id == project_id, FloorRow.level_id == level_id).with_for_update()
    return list((await db.execute(stmt)).scalars().all())


async def _active_count(db: AsyncSession, project_id: str) -> int:
    """Số tầng chưa xoá của dự án (bước 3 của #10)."""
    stmt = (
        select(func.count())
        .select_from(FloorRow)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
    )
    return (await db.execute(stmt)).scalar_one()


def _restorable(rows: Sequence[FloorRow], cutoff: datetime) -> FloorRow | None:
    """Dòng xoá mềm gần nhất còn trong cửa sổ khôi phục, nếu có (bước 4 của #10)."""
    return next((row for row in rows if row.deleted_at is not None and row.deleted_at >= cutoff), None)


def _apply_restore(row: FloorRow, body: FloorCreateIn) -> None:
    """Khôi phục một dòng xoá mềm: bỏ ẩn, ghi lại nội dung theo thân, giữ nguyên `pk`."""
    row.deleted_at = None
    row.name = body.name
    row.floor_order = body.order
    row.elevation_mm = body.elevation_mm
    row.height_mm = body.height_mm


async def _insert_floor(db: AsyncSession, project_id: str, body: FloorCreateIn, principal: Principal) -> FloorRow:
    """Chèn dòng tầng mới (bước 5 của #10); vi phạm unique đua với lượt khác → 409 `FLOOR_ID_TAKEN`."""
    row = FloorRow(
        project_id=project_id,
        level_id=body.id,
        name=body.name,
        floor_order=body.order,
        elevation_mm=body.elevation_mm,
        height_mm=body.height_mm,
        created_by=principal.user_id,
    )
    db.add(row)
    try:
        await db.flush()
    except IntegrityError as exc:
        if unique_violation(exc) is None:
            raise
        raise FLOOR_ID_TAKEN.error(field="id") from exc
    return row


async def create_floor(
    db: AsyncSession, project_id: str, body: FloorCreateIn, principal: Principal, clock: Clock, *, app: object | None
) -> FloorOut:
    """#10: khôi phục tầng xoá mềm trong cửa sổ hoặc chèn mới; 201 (B2-03 [6])."""
    settings = get_floors_settings()
    await lock_project_floors(db, project_id)
    rows = await _locked_rows(db, project_id, body.id)
    if any(row.deleted_at is None for row in rows):
        raise FLOOR_ID_TAKEN.error(field="id")
    if await _active_count(db, project_id) >= settings.floors_max:
        raise FLOOR_LIMIT_REACHED.error()
    cutoff = clock.now() - timedelta(seconds=settings.floor_restore_window_s)
    restorable = _restorable(rows, cutoff)
    if restorable is not None:
        _apply_restore(restorable, body)
        row = restorable
    else:
        row = await _insert_floor(db, project_id, body, principal)
    await register_floor(
        db, project_id=project_id, floor_level_id=body.id, floor_order=body.order, restored=restorable is not None
    )
    await touch_project(db, project_id=project_id, clock=clock)
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.FLOOR_CREATE,
        object_code=body.id,
        object_label=body.name,
        clock=clock,
        project_id=project_id,
    )
    return (await floor_outs(db, project_id=project_id, floor_pks=[row.pk], app=app))[0]


async def delete_floor(
    db: AsyncSession, project_id: str, level_id: str, principal: Principal, clock: Clock, *, app: object | None
) -> FloorOut:
    """#11: xoá mềm; thân trả về là ảnh chụp **ngay trước** khi xoá (B2-03 [6])."""
    await lock_project_floors(db, project_id)
    row = await get_floor(db, project_id=project_id, level_id=level_id, for_update=True)
    if row is None:
        raise NOT_FOUND.error(resource="floor")
    snapshot = (await floor_outs(db, project_id=project_id, floor_pks=[row.pk], app=app))[0]
    row.deleted_at = clock.now()
    await unregister_floor(db, project_id=project_id, floor_level_id=level_id)
    await touch_project(db, project_id=project_id, clock=clock)
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.FLOOR_DELETE,
        object_code=level_id,
        object_label=snapshot.name,
        clock=clock,
        project_id=project_id,
    )
    return snapshot


async def list_floors(db: AsyncSession, project_id: str, *, app: object | None) -> list[FloorOut]:
    """#12: mọi tầng chưa xoá của dự án, `(floor_order, pk)` (B2-03 [6])."""
    return await floor_outs(db, project_id=project_id, app=app)


async def _active_rows_locked(db: AsyncSession, project_id: str) -> list[FloorRow]:
    """Mọi tầng chưa xoá của dự án, khoá `FOR UPDATE` theo `pk` (bước khoá của #13)."""
    stmt = (
        select(FloorRow)
        .where(FloorRow.project_id == project_id, FloorRow.deleted_at.is_(None))
        .order_by(FloorRow.pk)
        .with_for_update()
    )
    return list((await db.execute(stmt)).scalars().all())


def _changed_orders(rows: Sequence[FloorRow], floor_ids: Sequence[str]) -> dict[str, int]:
    """`level_id -> vị trí mới` chỉ cho những dòng có `floor_order` thật sự đổi."""
    positions = {level_id: i for i, level_id in enumerate(floor_ids)}
    return {row.level_id: positions[row.level_id] for row in rows if row.floor_order != positions[row.level_id]}


async def reorder_floors(
    db: AsyncSession,
    project_id: str,
    project_name: str,
    floor_ids: Sequence[str],
    principal: Principal,
    clock: Clock,
    *,
    app: object | None,
) -> list[FloorOut]:
    """#13: `floor_order` = vị trí trong `floor_ids`; chỉ ghi khi có dòng đổi (B2-03 [6])."""
    await lock_project_floors(db, project_id)
    rows = await _active_rows_locked(db, project_id)
    if {row.level_id for row in rows} != set(floor_ids):
        raise FLOOR_REORDER_MISMATCH.error(field="floorIds")
    changed = _changed_orders(rows, floor_ids)
    if changed:
        for row in rows:
            if row.level_id in changed:
                row.floor_order = changed[row.level_id]
        await set_floor_orders(db, project_id=project_id, orders=changed)
        await touch_project(db, project_id=project_id, clock=clock)
        await record_activity(
            db,
            actor_id=principal.user_id,
            kind=ActivityKind.FLOOR_REORDER,
            object_code=project_id,
            object_label=project_name,
            clock=clock,
            project_id=project_id,
        )
    return await floor_outs(db, project_id=project_id, app=app)


def _check_path_body_id(level_id: str, body_id: str | None) -> None:
    """`id` của thân #34 khác `{floor_id}` trên đường → 422 `PATH_BODY_MISMATCH`; bằng thì bỏ qua."""
    if body_id is not None and body_id != level_id:
        raise PATH_BODY_MISMATCH.error(field="id")


def _changed_fields(row: FloorRow, body: FloorPatchIn) -> dict[str, object]:
    """Khoá có mặt trong thân #34 mà khác hiện trạng; `{}` hay giá trị trùng → rỗng."""
    candidates = {
        "name": body.name,
        "order": body.order,
        "elevation_mm": body.elevation_mm,
        "height_mm": body.height_mm,
    }
    current = {
        "name": row.name,
        "order": row.floor_order,
        "elevation_mm": row.elevation_mm,
        "height_mm": row.height_mm,
    }
    return {field: value for field, value in candidates.items() if value is not None and value != current[field]}


def _apply_changes(row: FloorRow, changes: dict[str, object]) -> None:
    """Ghi các khoá đã đổi lên dòng; `order` dây ↔ `floor_order` của model."""
    for field, value in changes.items():
        setattr(row, "floor_order" if field == "order" else field, value)


async def patch_floor(
    db: AsyncSession,
    project_id: str,
    level_id: str,
    body: FloorPatchIn,
    principal: Principal,
    clock: Clock,
    *,
    app: object | None,
) -> FloorOut:
    """#34: last-write-wins; `{}` hay giá trị không đổi → 200 không ghi, không nhật ký (B2-03 [6])."""
    _check_path_body_id(level_id, body.id)
    await lock_project_floors(db, project_id)
    row = await get_floor(db, project_id=project_id, level_id=level_id, for_update=True)
    if row is None:
        raise NOT_FOUND.error(resource="floor")
    changes = _changed_fields(row, body)
    if changes:
        _apply_changes(row, changes)
        if "order" in changes:
            await set_floor_orders(db, project_id=project_id, orders={level_id: row.floor_order})
        await touch_project(db, project_id=project_id, clock=clock)
        await record_activity(
            db,
            actor_id=principal.user_id,
            kind=ActivityKind.FLOOR_EDIT,
            object_code=level_id,
            object_label=row.name,
            clock=clock,
            project_id=project_id,
        )
    return (await floor_outs(db, project_id=project_id, floor_pks=[row.pk], app=app))[0]
