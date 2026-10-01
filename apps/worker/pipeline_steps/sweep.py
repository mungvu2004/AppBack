"""Lõi lịch quét bù lượt chạy kẹt (B5-06c [6] "run_stuck_pipeline_sweep", BE-00 §7 "Chuỗi nhiều bước")."""

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock


async def run_stuck_pipeline_sweep(
    sessionmaker: async_sessionmaker[AsyncSession], broker: AsyncRedis, clock: Clock, *, batch: int
) -> None:
    """Gửi lại bước đang dở của lượt im quá ngưỡng; hết trần → `PIPELINE_STEP_TIMEOUT`."""
    raise NotImplementedError  # việc B thay thân hàm
