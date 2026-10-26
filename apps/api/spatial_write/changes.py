"""Đọc `floor_change_log` để dựng thân 409 `VERSION_CONFLICT` (W20, B3-03 [6]).

FE cần biết **hiện trạng** của từng trường người khác đã đổi, không cần lịch sử: mỗi
`(entity_id, field)` chỉ một mục, mang giá trị mới nhất. `DISTINCT ON` làm việc ấy bằng
**một** truy vấn (N+1 ở đây là một tầng 3.000 tường nhân số trường). Cắt bớt thì bỏ mục
**cũ** nhất: mục mới nhất là thứ người dùng đang nhìn thấy lệch.

Phép cắt nằm trong SQL, không trong Python: một 409 ở `baseVersion 0` trên tầng đã có
~28.000 dòng nhật ký thì `LIMIT` ở Postgres trả 5.000 dòng, còn cắt ở Python phải nạp cả
28.000. `SPATIAL_CONFLICT_CHANGES_MAX` vì thế chặn **việc phải làm**, không chỉ thân trả về.

Module nhập được trong ngữ cảnh worker (BE-00 §7): không `fastapi`, không phần HTTP của
`apps.api.core`.
"""

from typing import Any, cast

from sqlalchemy import Row, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.errors import MISSING, SYSTEM_PIPELINE, RemoteFieldChange, VersionEntityType
from packages.db.models.spatial import FloorChangeLogRow
from packages.domain.rules_ai import Removed
from packages.domain.spatial import DELETED, Point, Segment, vertex_id

_COLUMNS = (
    FloorChangeLogRow.id,
    FloorChangeLogRow.revision,
    FloorChangeLogRow.entity_id,
    FloorChangeLogRow.entity_type,
    FloorChangeLogRow.field,
    FloorChangeLogRow.value,
    FloorChangeLogRow.removed,
    FloorChangeLogRow.changed_at,
    FloorChangeLogRow.changed_by,
    FloorChangeLogRow.changed_by_name,
)
"""Đúng các cột `RemoteFieldChange` cần: thực thể ORM kéo theo cả dòng và một identity map vô ích."""


async def remote_changes_since(
    db: AsyncSession, *, floor_pk: int, base_revision: int, limit: int
) -> tuple[RemoteFieldChange, ...]:
    """Thay đổi của tầng sau `base_revision`, mỗi trường một mục, sắp theo `(revision, id)` tăng.

    Giữ `limit` mục **mới nhất**: `DISTINCT ON` là subquery, `ORDER BY revision DESC, id DESC
    LIMIT` cắt ngay trong SQL, rồi `reversed` đưa về thứ tự `(revision, id)` **tăng** của dây.
    `max(limit, 0)` vì `LIMIT` âm là lỗi SQL, còn `limit == 0` phải ra rỗng.

    Dòng `removed` (trường bị gỡ, thực thể bị xoá) ra `MISSING` chứ không `None`:
    `RemoteFieldChange` cấm `None` và dây W20 vắng khoá `value`.
    """
    newest = (
        select(*_COLUMNS)
        .where(FloorChangeLogRow.floor_pk == floor_pk, FloorChangeLogRow.revision > base_revision)
        .distinct(FloorChangeLogRow.entity_id, FloorChangeLogRow.field)
        .order_by(
            FloorChangeLogRow.entity_id,
            FloorChangeLogRow.field,
            FloorChangeLogRow.revision.desc(),
            FloorChangeLogRow.id.desc(),
        )
        .subquery()
    )
    newest_first = select(newest).order_by(newest.c.revision.desc(), newest.c.id.desc()).limit(max(limit, 0))
    rows = (await db.execute(newest_first)).all()
    return tuple(_change(row) for row in reversed(rows))


def _change(row: Row[Any]) -> RemoteFieldChange:
    """Một dòng nhật ký → mục W20; `changed_at` là `timestamptz` nên đã có múi giờ UTC."""
    return RemoteFieldChange(
        entity_id=row.entity_id,
        # CHECK `ck_floor_change_log_entity_type` giữ tập giá trị; đây chỉ là cầu kiểu tĩnh.
        entity_type=cast("VersionEntityType", row.entity_type),
        field=row.field,
        value=MISSING if row.removed else row.value,
        changed_at=row.changed_at,
        changed_by=row.changed_by,
        changed_by_name=row.changed_by_name,
    )


async def human_removals(db: AsyncSession, *, floor_pk: int) -> Removed:
    """Tường/phòng người đã xoá kèm hình học cuối — "bia mộ" để lượt pipeline không dựng lại (H2 Phase 0).

    Hai truy vấn, không N+1. Một: dòng **mới nhất** mỗi id tường/phòng (`DISTINCT ON
    (entity_id)`), giữ id mà dòng đó là `__deleted__` do người ghi — xoá rồi ghi lại cùng id
    thì dòng mới nhất không còn là `__deleted__`. Hai: giá trị mới nhất của `x`/`y` hai đầu
    tường và `outline` của phòng (index `(floor_pk, entity_id, field, revision)`). Lịch gộp
    chỉ xoá dòng đã bị dòng mới hơn cùng `(entity_id, field)` che, nên cả hai còn sau gộp.
    Thiếu dữ liệu hình học thì bỏ mục đó; id còn sống không lọc ở đây (merge lọc).
    """
    newest = (
        select(
            FloorChangeLogRow.entity_id,
            FloorChangeLogRow.entity_type,
            FloorChangeLogRow.field,
            FloorChangeLogRow.changed_by,
        )
        .where(FloorChangeLogRow.floor_pk == floor_pk, FloorChangeLogRow.entity_type.in_(("wall", "room")))
        .distinct(FloorChangeLogRow.entity_id)
        .order_by(FloorChangeLogRow.entity_id, FloorChangeLogRow.revision.desc(), FloorChangeLogRow.id.desc())
        .subquery()
    )
    deleted = (
        await db.execute(
            select(newest.c.entity_id, newest.c.entity_type)
            .where(newest.c.field == DELETED, newest.c.changed_by != SYSTEM_PIPELINE)
            .order_by(newest.c.entity_id)
        )
    ).all()
    if not deleted:
        return Removed()
    wall_ids = [row.entity_id for row in deleted if row.entity_type == "wall"]
    room_ids = [row.entity_id for row in deleted if row.entity_type == "room"]
    keys = [vertex_id(wall_id, end) for wall_id in wall_ids for end in ("start", "end")] + room_ids
    values = (
        await db.execute(
            select(FloorChangeLogRow.entity_id, FloorChangeLogRow.field, FloorChangeLogRow.value)
            .where(
                FloorChangeLogRow.floor_pk == floor_pk,
                FloorChangeLogRow.entity_id.in_(keys),
                FloorChangeLogRow.field.in_(("x", "y", "outline")),
                FloorChangeLogRow.removed.is_(False),
            )
            .distinct(FloorChangeLogRow.entity_id, FloorChangeLogRow.field)
            .order_by(
                FloorChangeLogRow.entity_id,
                FloorChangeLogRow.field,
                FloorChangeLogRow.revision.desc(),
                FloorChangeLogRow.id.desc(),
            )
        )
    ).all()
    latest: dict[tuple[str, str], Any] = {(row.entity_id, row.field): row.value for row in values}
    return Removed(
        walls=tuple(
            (wall_id, Segment(start=start, end=end))
            for wall_id in wall_ids
            if (start := _vertex(latest, vertex_id(wall_id, "start"))) is not None
            and (end := _vertex(latest, vertex_id(wall_id, "end"))) is not None
        ),
        rooms=tuple(
            (room_id, tuple(Point.model_validate(point) for point in latest[(room_id, "outline")]))
            for room_id in room_ids
            if (room_id, "outline") in latest
        ),
    )


def _vertex(latest: dict[tuple[str, str], Any], key: str) -> Point | None:
    """Đầu tường từ giá trị mới nhất của `x` và `y`; thiếu một trong hai → `None`."""
    x, y = latest.get((key, "x")), latest.get((key, "y"))
    return None if x is None or y is None else Point(x=x, y=y)
