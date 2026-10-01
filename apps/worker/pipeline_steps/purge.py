"""Lõi lịch dọn artifact `runs/` của lượt đã kết thúc (B5-06c [6] "run_pipeline_artifact_purge")."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock
from packages.storage.port import ObjectStorage


async def run_pipeline_artifact_purge(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, batch: int
) -> None:
    """Xoá `run_prefix(…)` của lượt `completed|failed` quá hạn giữ, rồi đánh dấu đã dọn."""
    raise NotImplementedError  # việc C thay thân hàm
