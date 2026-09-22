"""Đọc lại `activity_log` cho test của mọi chủ route (B1-02, C18).

Nhận `async_sessionmaker`, không `AsyncSession` đơn: chủ route thường gọi qua
`make_api_client` (HTTP), nên dòng nhật ký được commit trên session của app, khác
session của test — đọc lại phải mở **session mới** để thấy đúng những gì đã commit,
giống `activity_rows`. Chỉ mã test được nhập file này (BE-01 [9]); không có tác dụng
phụ lúc nhập, vì `conftest.py` gốc nạp mọi file trong thư mục này như plugin pytest.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from packages.db.models.access import ActivityLog


@dataclass(frozen=True, slots=True)
class ActivityRow:
    """Một dòng `activity_log` đọc lại, bất biến."""

    id: int
    actor_id: str
    kind: str
    object_code: str
    object_label: str
    project_id: str | None
    at: datetime


def _to_row(log: ActivityLog) -> ActivityRow:
    """Chuyển một `ActivityLog` (thực thể SQLAlchemy, có thể hết hạn) sang `ActivityRow` bất biến."""
    return ActivityRow(
        id=log.id,
        actor_id=log.actor_id,
        kind=log.kind,
        object_code=log.object_code,
        object_label=log.object_label,
        project_id=log.project_id,
        at=log.at,
    )


async def activity_rows(
    sessionmaker: async_sessionmaker[AsyncSession], *, actor_id: str | None = None, kind: ActivityKind | None = None
) -> list[ActivityRow]:
    """Đọc lại `activity_log` qua session mới, lọc tuỳ chọn theo `actor_id`/`kind`, sắp theo `(at, id)`."""
    stmt = select(ActivityLog)
    if actor_id is not None:
        stmt = stmt.where(ActivityLog.actor_id == actor_id)
    if kind is not None:
        stmt = stmt.where(ActivityLog.kind == kind.value)
    stmt = stmt.order_by(ActivityLog.at, ActivityLog.id)
    async with sessionmaker() as session:
        result = await session.execute(stmt)
        return [_to_row(log) for log in result.scalars().all()]


async def assert_one_activity(
    sessionmaker: async_sessionmaker[AsyncSession], *, actor_id: str, kind: ActivityKind, object_code: str
) -> ActivityRow:
    """Khẳng định đúng **một** dòng khớp `(actor_id, kind, object_code)`; trả dòng đó.

    Hỏng (0 hoặc ≥2 dòng) → `AssertionError` liệt kê mọi dòng cùng `actor_id`/`kind`
    để dễ so lệch `object_code` mà không cần thêm truy vấn.
    """
    rows = await activity_rows(sessionmaker, actor_id=actor_id, kind=kind)
    matches = [row for row in rows if row.object_code == object_code]
    if len(matches) != 1:
        raise AssertionError(
            f"kỳ vọng đúng 1 dòng actor_id={actor_id!r} kind={kind!r} object_code={object_code!r}, "
            f"thấy {len(matches)}; các dòng cùng actor/kind: {rows!r}"
        )
    return matches[0]
