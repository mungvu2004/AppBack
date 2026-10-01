"""Lõi task `pipeline.quality.run` (B5-07 [6]): kiểm lớp đã ghi, ghi `quality.json`, đóng lượt.

Chủ: việc A. Prep chỉ dựng chữ ký để B (test runtime) và C (e2e) viết ngay từ phút 0.
"""

from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from packages.core.clock import Clock
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.storage.port import ObjectStorage

QualityOutcome = Literal["completed", "skipped"]
"""Kết quả một lượt giao: đã đóng lượt, hay bỏ qua (lượt muộn, bị thay, chưa ghi lớp, giao lặp)."""


async def run_quality(
    payload: RunStepPayload,
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: Clock,
) -> QualityOutcome:
    """Kiểm chất lượng một lượt theo B5-07 [6] bước 1 tới 4; chủ: việc A."""
    raise NotImplementedError


async def fail_quality(
    payload: RunStepPayload,
    code: str,
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    clock: Clock,
) -> None:
    """`on_failed`: đánh hỏng bước `qualityCheck` với mã đã cho (K33); chủ: việc A."""
    raise NotImplementedError
