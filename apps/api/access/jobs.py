"""Lịch dọn nhật ký hoạt động (BE-00 §7 "Dọn rác", chủ B1-02).

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.core`,
`packages.db`, `packages.messaging` — không `fastapi`, `starlette`, `jwt`, `argon2`
(BE-00 §2.1). Giữ 180 ngày trước khi xoá: nhật ký hoạt động là bằng chứng ai đã làm
gì, không có trần vòng lặp (khác `auth.jobs.MAX_BATCHES`) vì prompt đòi "lặp tới khi
hết" — vòng dừng khi một lô xoá ít hơn kích lô.
"""

import logging
from datetime import timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.models.access import ActivityLog
from packages.messaging import periodic

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.access.purge_activity"
EVERY: Final = timedelta(hours=24)
RETENTION: Final = timedelta(days=180)
ACTIVITY_PURGE_BATCH: Final = 5_000


async def run_purge_activity(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = ACTIVITY_PURGE_BATCH
) -> int:
    """Xoá dòng `activity_log` cũ hơn `RETENTION` theo lô, một `commit` mỗi lô; trả tổng số dòng đã xoá."""
    cutoff = clock.now() - RETENTION
    removed = 0
    batches = 0
    async with sessionmaker() as session:
        while True:
            doomed = select(ActivityLog.id).where(ActivityLog.at < cutoff).limit(batch)
            # `Result` chung không khai `rowcount`; lệnh DML luôn trả `CursorResult`.
            result = cast(
                "CursorResult[Any]",
                await session.execute(delete(ActivityLog).where(ActivityLog.id.in_(doomed))),
            )
            await session.commit()
            batches += 1
            removed += result.rowcount
            if result.rowcount < batch:
                break
    _log.info("activity_purged", extra={"removed": removed, "batches": batches})
    return removed


@periodic(TASK_NAME, every=EVERY)
async def purge_activity() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "Khuôn lịch nền")."""
    await run_purge_activity(worker_sessionmaker(), SystemClock())
