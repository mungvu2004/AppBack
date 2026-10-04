"""Hai lịch nền của thông báo (BE-00 §7 "khuôn lịch nền"; B4-02 [6] "Lịch").

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.*` và `apps.api.notifications.{service,
settings}` — không `fastapi`, `starlette`, `jwt`, `argon2` (BE-00 §2.1, K36). Lõi `run_*` nhận tài nguyên qua đối số
để test dùng Postgres/Redis thật; hàm lịch chỉ dựng tài nguyên rồi gọi lõi. Mọi lần gọi Redis nằm **ngoài** session
DB (K36): đọc ứng viên → đóng session → XADD → session ngắn ghi `stream_id`.
"""

import logging
from datetime import timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, Select, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.notifications.payload import notification_wire
from apps.api.notifications.service import dedupe_scope, visible_to_owner
from apps.api.notifications.settings import get_notifications_settings
from packages.core.clock import Clock, SystemClock
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.models.notifications import NotificationRow
from packages.messaging import periodic, streams_redis
from packages.messaging.streams import EventBus, user_stream

_log: Final = logging.getLogger(__name__)

PUBLISH_TASK: Final = "default.notifications.publish_unsent_notifications"
PUBLISH_EVERY: Final = timedelta(minutes=1)
TRIM_TASK: Final = "default.notifications.trim_notifications"
TRIM_EVERY: Final = timedelta(hours=1)

type _Unsent = tuple[str, str, str, dict[str, object]]
"""(id, user_id, dedupe_key, dạng dây) — chụp trong session để dùng được sau khi session đóng."""


async def _unsent_batch(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, batch: int) -> list[_Unsent]:
    """Tối đa `batch` dòng chưa có `stream_id`, tuổi trong khoảng (`UNSENT_WINDOW_S`, `UNSENT_AFTER_S`], cũ trước."""
    settings, now = get_notifications_settings(), clock.now()
    stmt = (
        select(NotificationRow)
        .where(
            NotificationRow.stream_id.is_(None),
            NotificationRow.created_at > now - timedelta(seconds=settings.notifications_unsent_window_s),
            NotificationRow.created_at <= now - timedelta(seconds=settings.notifications_unsent_after_s),
        )
        .order_by(NotificationRow.created_at, NotificationRow.id)
        .limit(batch)
    )
    async with sessionmaker() as session:
        rows = (await session.execute(stmt)).scalars()
        return [(row.id, row.user_id, row.dedupe_key, notification_wire(row)) for row in rows]


async def run_notification_publish(
    sessionmaker: async_sessionmaker[AsyncSession], bus: EventBus, clock: Clock, *, batch: int
) -> int:
    """Quét bù: phát dòng chưa có `stream_id` và ghi id lại; trả số dòng đã ghi `stream_id`.

    `publish_once` cùng khoá khử trùng với `notify`: dòng đã được phát thì nhận lại id cũ, **không** XADD lần hai
    (K32). Idempotent (J06): lượt sau không thấy dòng đã có `stream_id`. Dòng cũ hơn cửa sổ không phát nữa.
    """
    ttl_s = get_notifications_settings().notifications_dedupe_ttl_s
    sent: list[tuple[str, str]] = []
    for notification_id, user_id, dedupe_key, wire in await _unsent_batch(sessionmaker, clock, batch):
        stream_id = await bus.publish_once(user_stream(user_id), dedupe_scope(dedupe_key), wire, ttl_s=ttl_s)
        sent.append((notification_id, stream_id))
    async with session_scope(sessionmaker) as session:
        for notification_id, stream_id in sent:
            await session.execute(
                update(NotificationRow)
                .where(NotificationRow.id == notification_id, NotificationRow.stream_id.is_(None))
                .values(stream_id=stream_id)
            )
    _log.info("notifications_published", extra={"published": len(sent)})
    return len(sent)


async def _delete_batches(
    sessionmaker: async_sessionmaker[AsyncSession], doomed: Select[tuple[str]], batch: int
) -> int:
    """Xoá theo lô `batch` các id mà `doomed` (câu `SELECT id` chưa có `LIMIT`) chọn ra, một commit mỗi lô."""
    removed = 0
    while True:
        async with session_scope(sessionmaker) as session:
            # `Result` chung không khai `rowcount`; lệnh DML luôn trả `CursorResult`.
            result = cast(
                "CursorResult[Any]",
                await session.execute(delete(NotificationRow).where(NotificationRow.id.in_(doomed.limit(batch)))),
            )
        removed += result.rowcount
        if result.rowcount < batch:
            return removed


async def run_notification_trim(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int) -> int:
    """Dọn: dòng ẩn theo luật #19 cũ hơn `HIDDEN_PURGE_AFTER_S` trước, rồi mỗi người giữ `KEEP_MAX` dòng mới nhất.

    Bước 1 đi trước để dòng ẩn cũ không chiếm chỗ của dòng #19 còn hiện. Idempotent (J06); trả tổng số dòng đã xoá.
    """
    settings = get_notifications_settings()
    cutoff = clock.now() - timedelta(seconds=settings.notifications_hidden_purge_after_s)
    hidden = select(NotificationRow.id).where(NotificationRow.created_at < cutoff, ~visible_to_owner())
    # R-05: chỉ xếp hạng người vượt trần (index `(user_id, created_at, id)` phục vụ `GROUP BY`), không cả bảng mỗi lô.
    over_cap = (
        select(NotificationRow.user_id)
        .group_by(NotificationRow.user_id)
        .having(func.count() > settings.notifications_keep_max)
    )
    ranked = select(
        NotificationRow.id,
        func.row_number()
        .over(
            partition_by=NotificationRow.user_id,
            order_by=(NotificationRow.created_at.desc(), NotificationRow.id.desc()),
        )
        .label("rn"),
    ).where(NotificationRow.user_id.in_(over_cap)).subquery()
    overflow = select(ranked.c.id).where(ranked.c.rn > settings.notifications_keep_max)
    removed = await _delete_batches(sessionmaker, hidden, batch)
    removed += await _delete_batches(sessionmaker, overflow, batch)
    _log.info("notifications_trimmed", extra={"removed": removed})
    return removed


@periodic(PUBLISH_TASK, every=PUBLISH_EVERY)
async def publish_unsent_notifications() -> None:
    """Hàm lịch: dựng bus thật rồi gọi lõi (BE-00 §7 "khuôn lịch nền")."""
    client = streams_redis()
    try:
        await run_notification_publish(
            worker_sessionmaker(),
            EventBus(client),
            SystemClock(),
            batch=get_notifications_settings().notifications_sweep_batch,
        )
    finally:
        await client.aclose()


@periodic(TRIM_TASK, every=TRIM_EVERY)
async def trim_notifications() -> None:
    """Hàm lịch: gọi lõi dọn với `worker_sessionmaker()`."""
    await run_notification_trim(
        worker_sessionmaker(), SystemClock(), batch=get_notifications_settings().notifications_sweep_batch
    )
