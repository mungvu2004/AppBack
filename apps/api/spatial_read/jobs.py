"""Lịch đối chiếu bảng đếm `default.spatial_read.reconcile_counts` (B3-02 [6], BE-00 §7).

`apps/worker` nhập module này để chạy beat nên nó không được kéo `fastapi`/`starlette`
(BE-00 §7 "luật hàm worker nhập"): chỉ nhập `counts`, `settings` và `packages.*`, không
nhập `apps.api.floors.lookup`. B3-03 ghi tài liệu và bảng đếm trong cùng giao dịch; lịch này
là lưới an toàn cho tầng mà một ghi ngoài đường ấy làm lệch.

Chỉ quét tầng chưa xoá có `floors.updated_at` trong cửa sổ nhìn lại: quét cả bảng mỗi
5 phút là tốn vô ích, còn tầng ngoài cửa sổ đã được lượt trước xét rồi.
"""

import logging
from datetime import timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.counts import recount_floor
from apps.api.spatial_read.settings import get_spatial_read_settings
from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.db.models.floors import FloorRow
from packages.messaging import periodic

_log: Final = logging.getLogger(__name__)

TASK_NAME: Final = "default.spatial_read.reconcile_counts"
EVERY: Final = timedelta(minutes=5)


async def _select_batch(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, batch: int, after: int
) -> list[int]:
    """`batch` `pk` tầng chưa xoá, `updated_at` trong cửa sổ, `pk > after` (keyset, không `OFFSET`)."""
    since = clock.now() - timedelta(seconds=get_spatial_read_settings().spatial_recount_lookback_s)
    stmt = (
        select(FloorRow.pk)
        .where(FloorRow.deleted_at.is_(None), FloorRow.updated_at >= since, FloorRow.pk > after)
        .order_by(FloorRow.pk)
        .limit(batch)
    )
    async with sessionmaker() as session:
        return list((await session.execute(stmt)).scalars())


async def run_count_reconcile(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int) -> int:
    """Đối chiếu mọi tầng trong cửa sổ theo lô; trả số tầng đã ghi lại bảng đếm."""
    written = 0
    after = 0
    while True:
        pks = await _select_batch(sessionmaker, clock, batch, after)
        for pk in pks:
            # Mỗi tầng một giao dịch ngắn (R-20): ôm cả lô sẽ giữ khoá FOR SHARE của mọi
            # tầng tới cuối và một tầng lỗi kéo cả lô lùi.
            async with sessionmaker() as session:
                if await recount_floor(session, floor_pk=pk, clock=clock):
                    written += 1
                await session.commit()
        if len(pks) < batch:
            break
        after = pks[-1]
    _log.info("count_reconcile_completed", extra={"written": written})
    return written


@periodic(TASK_NAME, every=EVERY)
async def reconcile_floor_counts() -> None:
    """Hàm lịch: chỉ dựng tài nguyên thật rồi gọi lõi (BE-00 §7 "khuôn lịch nền")."""
    await run_count_reconcile(
        worker_sessionmaker(), SystemClock(), batch=get_spatial_read_settings().spatial_recount_batch
    )
