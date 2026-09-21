"""Lịch dọn bản ghi idempotency hết hạn (BE-00 §7 "Dọn rác", chủ B0-06).

Module này bị `apps/worker` nhập để chạy beat, nên nó **không** được nhập
`fastapi`/`starlette` (BE-00 §2.1 `apps.api.*.jobs`) — vì vậy nó dùng thẳng model
chứ không đi qua `apps.api.core.idempotency`.

Xoá theo lô có trần vòng lặp: một `DELETE` không `LIMIT` trên bảng đã tồn đọng
nhiều ngày sẽ giữ khoá lâu và làm mọi lượt nhận việc chờ theo (R-21).
"""

import logging
from datetime import timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.models.idempotency import IdempotencyRecord
from packages.messaging import periodic

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.idempotency.purge_expired"
EVERY: Final = timedelta(hours=1)
BATCH: Final = 1000
MAX_BATCHES: Final = 100
"""Trần vòng lặp: một lượt lịch xoá tối đa `BATCH * MAX_BATCHES` dòng, lượt sau làm tiếp."""


async def run_purge_expired_idempotency(
    sessionmaker: async_sessionmaker[AsyncSession],
    clock: Clock,
    *,
    batch: int = BATCH,
) -> int:
    """Xoá dòng quá `expires_at`, trả số dòng đã xoá."""
    now = clock.now()
    removed = 0
    async with sessionmaker() as session:
        for _ in range(MAX_BATCHES):
            doomed = select(IdempotencyRecord.id).where(IdempotencyRecord.expires_at <= now).limit(batch)
            # `Result` chung không khai `rowcount`; lệnh DML luôn trả `CursorResult`.
            result = cast(
                "CursorResult[Any]",
                # Kiểm lại hạn trong chính `DELETE`: giữa lượt chọn và lượt xoá, `begin` có thể đã
                # chiếm lại dòng (gia hạn `expires_at`) — xoá nó là làm lượt đang chạy nhận 503.
                await session.execute(
                    delete(IdempotencyRecord).where(
                        IdempotencyRecord.id.in_(doomed), IdempotencyRecord.expires_at <= now
                    )
                ),
            )
            await session.commit()
            removed += result.rowcount
            if result.rowcount < batch:
                break
    _log.info("idempotency_purged", extra={"removed": removed})
    return removed


@periodic(TASK_NAME, every=EVERY)
async def purge_expired_idempotency() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "Khuôn lịch nền")."""
    await run_purge_expired_idempotency(worker_sessionmaker(), SystemClock())
