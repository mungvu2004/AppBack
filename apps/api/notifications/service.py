"""`notify` và truy vấn của #19-#22 (B4-02 [6]).

`notify` chạy trong giao dịch của người gọi và **không commit**; XADD nằm ở callback sau commit (K17), chỉ bằng
`publish_once` (K18/K32). Callback không ghi DB (K36): `stream_id` do lịch quét bù ghi. Module này không nhập
`fastapi`, `jwt`, `argon2` — B5-06b (worker) gọi `notify` từ đây.
"""

import logging
import re
from functools import cache
from typing import Final

from sqlalchemy import ColumnElement, exists, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.notifications.errors import NOTIFICATION_NOT_INVITE
from apps.api.notifications.kinds import FLOOR_PLACES, KINDS, PLACES
from apps.api.notifications.messages import clean_label
from apps.api.notifications.payload import notification_wire
from apps.api.notifications.settings import get_notifications_settings
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.errors import AppError
from packages.core.ids import is_id, new_id
from packages.db.hooks import on_after_commit
from packages.db.models.notifications import INVITE_PLACE, NotificationRow
from packages.db.models.projects import Project, ProjectMembership
from packages.messaging.redis import streams_redis_sync
from packages.messaging.settings import get_messaging_settings
from packages.messaging.streams import SyncEventBus, user_stream

_log: Final = logging.getLogger(__name__)

DEDUPE_KEY_RE: Final = re.compile(r"[A-Za-z0-9:._-]{1,200}")
DEDUPE_PREFIX: Final = "notifications:"


def dedupe_scope(dedupe_key: str) -> str:
    """Khoá khử trùng Redis của một thông báo; lịch quét bù phải dùng đúng chuỗi này (K32)."""
    return DEDUPE_PREFIX + dedupe_key


@cache
def _sync_bus(broker_url: str) -> SyncEventBus:
    """Bus đồng bộ dựng lười, một cái cho mỗi URL broker: callback sau commit chạy ngoài vòng sự kiện (pool chia được).

    Khoá theo URL để đổi `REDIS_BROKER_URL` (test, cấu hình nóng) tự dựng bus mới, không giữ client tới Redis cũ.
    """
    return SyncEventBus(streams_redis_sync())


def visible_to_owner() -> ColumnElement[bool]:
    """Luật ẩn của #19: dự án chưa xoá mềm **và** người nhận còn là thành viên (tương quan với `NotificationRow`)."""
    return exists().where(
        Project.id == NotificationRow.project_id,
        Project.deleted_at.is_(None),
        ProjectMembership.project_id == Project.id,
        ProjectMembership.user_id == NotificationRow.user_id,
    )


def _check(*, kind: str, place: str, floor_level_id: str | None, dedupe_key: str, message: str) -> None:
    """Sai bất kỳ luật nào của [6] bước 1 → `ValueError` (lỗi lập trình, không phải lỗi người dùng)."""
    if kind not in KINDS:
        raise ValueError(f"kind lạ: {kind!r}")
    if place not in PLACES:
        raise ValueError(f"place lạ: {place!r}")
    if place in FLOOR_PLACES and not floor_level_id:
        raise ValueError(f"place {place!r} cần floor_level_id")
    if kind == "projectInvite" and place != INVITE_PLACE:
        raise ValueError(f"projectInvite chỉ đi với place {INVITE_PLACE!r}")
    if DEDUPE_KEY_RE.fullmatch(dedupe_key) is None:
        raise ValueError(f"dedupe_key sai mẫu: {dedupe_key!r}")
    if not message.strip():
        raise ValueError("message không được rỗng")


def _required_label(value: str, field: str) -> str:
    """`clean_label` cho trường bắt buộc; rỗng sau làm sạch → `ValueError`."""
    cleaned = clean_label(value)
    if not cleaned:
        raise ValueError(f"{field} rỗng sau khi làm sạch")
    return cleaned


def _publish_after_commit(db: AsyncSession, row: NotificationRow) -> None:
    """Chụp dạng dây **trong** giao dịch (callback chạy ngoài vòng sự kiện), phát sau commit.

    Lỗi Redis chỉ được ghi log: dòng đã commit, lịch quét bù sẽ phát và ghi `stream_id` (J10).
    """
    wire, stream, scope = notification_wire(row), user_stream(row.user_id), dedupe_scope(row.dedupe_key)
    notification_id, ttl_s = row.id, get_notifications_settings().notifications_dedupe_ttl_s

    def publish() -> None:
        """XADD đúng một lần theo `dedupe_key`; không ghi DB."""
        try:
            _sync_bus(get_messaging_settings().redis_broker_url).publish_once(stream, scope, wire, ttl_s=ttl_s)
        except AppError:
            _log.warning("notification_publish_failed", extra={"notification_id": notification_id})

    on_after_commit(db, publish)


async def notify(
    db: AsyncSession,
    *,
    user_id: str,
    kind: str,
    place: str,
    project_id: str,
    project_name: str,
    object_label: str,
    message: str,
    dedupe_key: str,
    clock: Clock,
    floor_level_id: str | None = None,
    excerpt: str | None = None,
) -> NotificationRow | None:
    """Tạo một thông báo trong giao dịch của người gọi; trả dòng mới, hoặc `None` khi `dedupe_key` đã có.

    Dòng đã có mà chưa có `stream_id` (task giao lại sau khi commit mà chưa kịp phát) vẫn được đăng ký phát.
    """
    _check(kind=kind, place=place, floor_level_id=floor_level_id, dedupe_key=dedupe_key, message=message)
    now = clock.now()
    stmt = (
        pg_insert(NotificationRow)
        .values(
            id=new_id("ntf", clock),
            user_id=user_id,
            kind=kind,
            place=place,
            project_id=project_id,
            project_name=_required_label(project_name, "project_name"),
            floor_level_id=floor_level_id,
            object_label=_required_label(object_label, "object_label"),
            message=message,
            excerpt=(clean_label(excerpt) or None) if excerpt is not None else None,
            is_read=False,
            dedupe_key=dedupe_key,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=[NotificationRow.dedupe_key])
        .returning(NotificationRow)
        .execution_options(populate_existing=True)
    )
    created = (await db.execute(stmt)).scalar_one_or_none()
    if created is not None:
        _publish_after_commit(db, created)
        return created
    existing = (await db.execute(select(NotificationRow).where(NotificationRow.dedupe_key == dedupe_key))).scalar_one()
    if existing.stream_id is None:
        _publish_after_commit(db, existing)
    return None


async def list_notifications(db: AsyncSession, user_id: str) -> list[NotificationRow]:
    """#19: dòng của `user_id` còn hiện, mới nhất trước, tối đa `NOTIFICATIONS_LIST_MAX`."""
    stmt = (
        select(NotificationRow)
        .where(NotificationRow.user_id == user_id, visible_to_owner())
        .order_by(NotificationRow.created_at.desc(), NotificationRow.id.desc())
        .limit(get_notifications_settings().notifications_list_max)
    )
    return list((await db.execute(stmt)).scalars())


async def mark_read(db: AsyncSession, user_id: str, ids: list[str], clock: Clock) -> None:
    """#20: đánh dấu đã đọc; id lạ hoặc của người khác bị bỏ qua vì `user_id` nằm trong điều kiện."""
    await db.execute(
        update(NotificationRow)
        .where(NotificationRow.user_id == user_id, NotificationRow.id.in_(ids), NotificationRow.is_read.is_(False))
        .values(is_read=True, updated_at=clock.now())
    )


async def mark_all_read(db: AsyncSession, user_id: str, clock: Clock) -> None:
    """#21: mọi dòng chưa đọc của người gọi, kể cả dòng đang bị ẩn ở #19."""
    await db.execute(
        update(NotificationRow)
        .where(NotificationRow.user_id == user_id, NotificationRow.is_read.is_(False))
        .values(is_read=True, updated_at=clock.now())
    )


async def accept_invite(db: AsyncSession, user_id: str, notification_id: str, clock: Clock) -> NotificationRow:
    """#22, idempotent: 404 nếu không thấy (sai mẫu, của người khác, bị ẩn), 422 nếu không phải lời mời.

    Không đổi thành viên hay vai (N3 đã thêm); chỉ đánh dấu đã đọc khi đang chưa đọc.
    """
    if not is_id("ntf", notification_id):
        raise NOT_FOUND.error(resource="notification")
    stmt = select(NotificationRow).where(
        NotificationRow.id == notification_id, NotificationRow.user_id == user_id, visible_to_owner()
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NOT_FOUND.error(resource="notification")
    if row.kind != "projectInvite":
        raise NOTIFICATION_NOT_INVITE.error()
    if not row.is_read:
        row.is_read = True
        row.updated_at = clock.now()
        await db.flush()
    return row
