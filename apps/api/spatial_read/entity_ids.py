"""Nhận và trả quyền sở hữu id thực thể trong một dự án (W4, B3-02 [6]).

`floor_entity_ids` là chỗ duy nhất cưỡng chế "id duy nhất toàn dự án": PK
`(project_id, entity_id)`. B3-03 gọi `claim_entity_ids` **trong** giao dịch ghi của mình,
ngay sau `UPDATE floor_documents`, và đổi kết quả khác rỗng thành 409 của nó — module này
không ném `AppError` vì nó cũng chạy trong ngữ cảnh worker (BE-00 §7).

Chống khoá chéo: mọi lệnh đụng nhiều dòng đều đi theo thứ tự `entity_id` tăng dần
(`ORDER BY` trong `SELECT … FOR UPDATE` và trong `INSERT … SELECT`), nên hai lượt ghi
song song xin khoá theo cùng một thứ tự và không thể chờ vòng (`40P01`).
"""

from collections.abc import Collection
from datetime import datetime, timedelta

from sqlalchemy import ARRAY, Text, delete, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.floors.settings import get_floors_settings
from packages.core.clock import Clock
from packages.db.models.floors import FloorRow
from packages.db.models.spatial import FloorEntityIdRow


async def _release(db: AsyncSession, *, project_id: str, floor_pk: int, removed: Collection[str]) -> None:
    """Trả lại id tầng mình không còn dùng; id của tầng khác trong danh sách bị bỏ qua.

    Khoá trước rồi mới `DELETE` (chứ không `DELETE` thẳng): `SELECT … ORDER BY entity_id
    FOR UPDATE` ép thứ tự khoá, còn `DELETE` một mình khoá theo kế hoạch của Postgres.
    """
    ids = sorted(set(removed))
    locked = (
        (
            await db.execute(
                select(FloorEntityIdRow.entity_id)
                .where(
                    FloorEntityIdRow.project_id == project_id,
                    FloorEntityIdRow.entity_id.in_(ids),
                    FloorEntityIdRow.floor_pk == floor_pk,
                )
                .order_by(FloorEntityIdRow.entity_id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if not locked:
        return
    await db.execute(
        delete(FloorEntityIdRow).where(
            FloorEntityIdRow.project_id == project_id, FloorEntityIdRow.entity_id.in_(list(locked))
        )
    )


async def _insert_new(db: AsyncSession, *, project_id: str, floor_pk: int, added: list[str], now: datetime) -> None:
    """Chèn mọi id mới bằng **một** câu; id đã có chủ (kể cả chính mình) rơi vào `DO NOTHING`."""
    entity_id = func.unnest(literal(added, ARRAY(Text))).column_valued("entity_id")
    source = select(literal(project_id), entity_id, literal(floor_pk), literal(now), literal(now)).order_by(entity_id)
    stmt = pg_insert(FloorEntityIdRow).from_select(
        ["project_id", "entity_id", "floor_pk", "created_at", "updated_at"], source
    )
    await db.execute(stmt.on_conflict_do_nothing())


async def claim_entity_ids(
    db: AsyncSession,
    *,
    project_id: str,
    floor_pk: int,
    removed: Collection[str],
    added: Collection[str],
    clock: Clock,
) -> tuple[str, ...]:
    """Nhận `added`, trả `removed`; trả về id **không** nhận được, sắp tăng (`()` khi trọn vẹn).

    Id đang thuộc tầng khác chỉ nhận lại được khi tầng ấy đã xoá mềm **quá**
    `FLOOR_RESTORE_WINDOW_S`: trong cửa sổ đó tầng cũ còn khôi phục được và phải giữ id
    của nó. `UPDATE … AND floor_pk = :chủ_cũ` không ăn dòng nào nghĩa là một lượt khác
    vừa nhận trước → xung đột, không thử lại.
    """
    now = clock.now()
    if removed:
        await _release(db, project_id=project_id, floor_pk=floor_pk, removed=removed)
    wanted = sorted(set(added))
    if not wanted:
        return ()
    await _insert_new(db, project_id=project_id, floor_pk=floor_pk, added=wanted, now=now)

    cutoff = now - timedelta(seconds=get_floors_settings().floor_restore_window_s)
    others = (
        await db.execute(
            select(FloorEntityIdRow.entity_id, FloorEntityIdRow.floor_pk, FloorRow.deleted_at)
            .join(FloorRow, FloorRow.pk == FloorEntityIdRow.floor_pk)
            .where(
                FloorEntityIdRow.project_id == project_id,
                FloorEntityIdRow.entity_id.in_(wanted),
                FloorEntityIdRow.floor_pk != floor_pk,
            )
            .order_by(FloorEntityIdRow.entity_id)
        )
    ).all()

    live = {row.entity_id for row in others if row.deleted_at is None or row.deleted_at >= cutoff}
    expired = [row for row in others if row.entity_id not in live]
    # Nhận lại phải là `UPDATE` **từng id** vì mỗi câu cần điều kiện `floor_pk = :chủ_cũ` riêng
    # của id đó. Đường này hiếm (chủ cũ đã xoá mềm quá cửa sổ) và `others` đã sắp theo
    # `entity_id`, nên thứ tự khoá vẫn cố định. Id không `RETURNING` về được nghĩa là một lượt
    # khác vừa nhận trước — thành xung đột, không thử lại.
    reclaimed: set[str] = set()
    for row in expired:
        taken = await db.execute(
            update(FloorEntityIdRow)
            .where(
                FloorEntityIdRow.project_id == project_id,
                FloorEntityIdRow.entity_id == row.entity_id,
                FloorEntityIdRow.floor_pk == row.floor_pk,
            )
            .values(floor_pk=floor_pk, updated_at=now)
            .returning(FloorEntityIdRow.entity_id)
        )
        reclaimed.update(taken.scalars())
    lost = {row.entity_id for row in expired} - reclaimed
    return tuple(sorted(live | lost))
