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

from packages.core.errors import MISSING, RemoteFieldChange, VersionEntityType
from packages.db.models.spatial import FloorChangeLogRow

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
