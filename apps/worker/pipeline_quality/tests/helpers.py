"""Dựng cảnh "lượt đứng ở `qualityCheck`" cho mọi test của `pipeline_quality` (B5-07, "Chữ ký chung").

Dùng lại cảnh `pipeline_persist` rồi chạy **lõi** `run_persist` thật (không mock, K23) để lượt
nhảy đúng tới bước này: bốn bước trước + `spatialDataBuild` đã `completed`, lớp AI đã ghi,
`persisted_revision` đã đặt. `run_persist` xếp `pipeline.quality.run` sau commit (K17) — dọn
nó khỏi hàng `pipeline.cpu` ngay trong hàm để test tự gọi `run_quality`/`fail_quality` mà
không có một message Celery thật trùng lặp chạy nền.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.pipeline_persist.service import run_persist
from apps.worker.pipeline_persist.tests.helpers import Arranged, open_run_at_build, put_layer, sample_built
from packages.core.clock import Clock
from packages.messaging.redis import broker_redis_sync
from packages.storage.port import ObjectStorage

__all__ = ["Arranged", "open_run_at_quality"]

_QUALITY_QUEUE: str = "pipeline.cpu"
"""Hàng mà `pipeline.quality.run` được xếp vào (`queue_for`, luật chung); dọn sau khi dựng cảnh."""


async def open_run_at_quality(
    maker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock
) -> Arranged:
    """Dựng lượt đứng ở `qualityCheck`, sẵn sàng cho `service.run_quality`/`fail_quality`.

    Gọi `run_persist` thật trên cảnh `open_run_at_build` + `layer.json` mẫu; sau khi lượt đã
    `persisted`, xoá message `pipeline.quality.run` mà nó vừa xếp lên `pipeline.cpu` (giao lặp
    không nguy hại cho B5-07, nhưng test không cần một worker Celery thật tiêu thụ nó).
    """
    arranged = await open_run_at_build(maker, clock, storage=storage)
    await put_layer(storage, arranged, sample_built(arranged.level_id).to_json())
    outcome = await run_persist(arranged.payload, sessionmaker=maker, storage=storage, clock=clock)
    assert outcome == "persisted", f"run_persist không ghi được cảnh nền: {outcome!r}"
    broker_redis_sync().delete(_QUALITY_QUEUE)
    return arranged
