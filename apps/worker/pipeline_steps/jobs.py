"""Hai lịch nền của điều phối bước (B5-06c [2], BE-00 §7 "khuôn lịch nền").

Hàm lịch chỉ dựng tài nguyên tiến trình rồi gọi lõi (`sweep`, `purge`), để test gọi lõi với
Postgres/Redis/kho thật và đồng hồ giả.
"""

from datetime import timedelta
from typing import Final

from apps.worker.pipeline_steps.purge import run_pipeline_artifact_purge
from apps.worker.pipeline_steps.settings import get_steps_settings
from apps.worker.pipeline_steps.sweep import run_stuck_pipeline_sweep
from packages.core.clock import Clock, SystemClock
from packages.db.engine import worker_sessionmaker
from packages.messaging import periodic
from packages.messaging.redis import broker_redis
from packages.storage.port import ObjectStorage

SWEEP_TASK: Final = "default.pipeline_steps.sweep_stuck_runs"
SWEEP_EVERY: Final = timedelta(minutes=5)
PURGE_TASK: Final = "default.pipeline_steps.purge_run_artifacts"
PURGE_EVERY: Final = timedelta(hours=24)


def _storage(clock: Clock) -> ObjectStorage:
    """Kho thật dựng từ biến môi trường; nhập trễ như `pipeline_orchestrate.tasks` (K22)."""
    from packages.storage.factory import create_storage
    from packages.storage.settings import get_storage_settings

    return create_storage(get_storage_settings(), None, clock)


@periodic(SWEEP_TASK, every=SWEEP_EVERY)
async def sweep_stuck_pipeline_runs() -> None:
    """Hàm lịch: quét bù lượt chạy kẹt bằng giờ thật."""
    batch = get_steps_settings().PIPELINE_SWEEP_BATCH
    await run_stuck_pipeline_sweep(worker_sessionmaker(), broker_redis(), SystemClock(), batch=batch)


@periodic(PURGE_TASK, every=PURGE_EVERY)
async def purge_pipeline_run_artifacts() -> None:
    """Hàm lịch: dọn artifact `runs/` quá hạn giữ."""
    clock = SystemClock()
    batch = get_steps_settings().PIPELINE_SWEEP_BATCH
    await run_pipeline_artifact_purge(worker_sessionmaker(), _storage(clock), clock, batch=batch)
