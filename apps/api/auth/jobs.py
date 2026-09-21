"""Lịch dọn phiên refresh (BE-00 §7 "Dọn rác", chủ B1-01).

`apps/worker` nhập module này để chạy beat, nên nó chỉ nhập `packages.core`, `packages.db`,
`packages.messaging` — không `fastapi`, `starlette`, `jwt`, `argon2` (BE-00 §2.1).

Giữ phiên chết thêm `RETENTION` (1 ngày) trước khi xoá: dòng thu hồi vì dùng lại là bằng
chứng khi người dùng hỏi "vì sao tôi bị đăng xuất". Xoá theo lô có trần vòng lặp (R-21).
"""

import logging
from datetime import timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.models.auth import RefreshSession
from packages.messaging import periodic

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.auth.purge_sessions"
EVERY: Final = timedelta(hours=1)
RETENTION: Final = timedelta(days=1)
BATCH: Final = 1000
MAX_BATCHES: Final = 100
"""Trần vòng lặp: một lượt lịch xoá tối đa `BATCH * MAX_BATCHES` dòng, lượt sau làm tiếp."""


async def run_purge_sessions(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = BATCH
) -> int:
    """Xoá phiên hết hạn tuyệt đối hay đã thu hồi quá `RETENTION`; trả số dòng đã xoá."""
    cutoff = clock.now() - RETENTION
    dead = or_(RefreshSession.absolute_expires_at < cutoff, RefreshSession.revoked_at < cutoff)
    removed = 0
    async with sessionmaker() as session:
        for _ in range(MAX_BATCHES):
            doomed = select(RefreshSession.id).where(dead).limit(batch)
            # `Result` chung không khai `rowcount`; lệnh DML luôn trả `CursorResult`.
            result = cast(
                "CursorResult[Any]",
                await session.execute(delete(RefreshSession).where(RefreshSession.id.in_(doomed))),
            )
            await session.commit()
            removed += result.rowcount
            if result.rowcount < batch:
                break
    _log.info("auth_sessions_purged", extra={"removed": removed})
    return removed


@periodic(TASK_NAME, every=EVERY)
async def purge_sessions() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "Khuôn lịch nền")."""
    await run_purge_sessions(worker_sessionmaker(), SystemClock())
