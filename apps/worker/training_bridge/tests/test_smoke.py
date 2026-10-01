"""Test khói của cầu nối: chuỗi bốn thông điệp đi qua một worker Celery **thật** (B6-03a [8]).

Khác `test_tasks.py`/`test_finish.py` — nơi tài nguyên do test truyền vào — ở đây thân task
tự dựng `worker_sessionmaker()`, `open_storage()` và `SystemClock()`, đúng như tiến trình
worker. `process_env` chỉ trỏ biến môi trường sang DB test và kho trong `tmp_path`, nên
Postgres, Redis, kho vẫn là thật (K23); `db_sessionmaker` của fixture **không** vào task
("attached to a different loop").
"""

import asyncio
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from celery import Celery
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_jobs.settings import reset_training_settings_cache
from apps.worker.training_bridge.tasks import FINISHED_TASK, HEARTBEAT_TASK, LOG_TASK, METRICS_TASK
from apps.worker.training_bridge.tests._helpers import (
    METRIC,
    finished,
    heartbeat,
    log_line,
    metric_point,
    metrics,
    put_weights,
    seed_job,
    weights_key,
)
from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.admin_ml_jobs import TrainingJobRow, TrainingLogRow, TrainingMetricRow
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.payloads.training import LOG_TEMPLATES, trained_version_id
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures.messaging import WorkerFactory

DEFAULT_QUEUE = "default"
WORKER_WAIT_S = 20.0
POLL_S = 0.05


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của tiến trình worker: DB test riêng, kho local cùng gốc với `local_storage`."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-training-bridge-01")
    caches = (
        reset_settings_cache,
        reset_database_settings_cache,
        reset_storage_settings_cache,
        reset_training_settings_cache,
    )
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


def _process_maker() -> async_sessionmaker[AsyncSession]:
    """Sessionmaker trên DB mà biến môi trường của tiến trình đang trỏ tới."""
    return create_sessionmaker(create_engine(get_database_settings()))


async def _with_process_db(work: object) -> object:
    """Chạy một hàm nhận sessionmaker trên DB của tiến trình, rồi đóng engine."""
    maker = _process_maker()
    try:
        return await work(maker)  # type: ignore[operator] — người gọi luôn truyền một callable async
    finally:
        await maker.kw["bind"].dispose()


async def _seed(storage: LocalDiskStorage) -> str:
    """Một job `queued` trong DB của tiến trình, với object trọng số đã nằm trong kho."""

    async def work(maker: async_sessionmaker[AsyncSession]) -> str:
        """Dựng job rồi `put` trọng số của chính nó."""
        async with maker() as db:
            job = await seed_job(db, status="queued")
        await put_weights(storage, weights_key(job.id))
        return job.id

    return str(await _with_process_db(work))


async def _snapshot(job_id: str) -> tuple[str, str | None, int, int, str | None]:
    """`(status, result_model_version_id, số điểm, số dòng log, evaluation_status)` đọc bằng session mới."""

    async def work(maker: async_sessionmaker[AsyncSession]) -> tuple[str, str | None, int, int, str | None]:
        """Đọc lại cả bốn bảng sau khi worker đã commit."""
        async with maker() as db:
            job = await db.get(TrainingJobRow, job_id)
            assert job is not None
            points = await db.scalar(
                select(func.count()).select_from(TrainingMetricRow).where(TrainingMetricRow.job_id == job_id)
            )
            lines = await db.scalar(
                select(func.count()).select_from(TrainingLogRow).where(TrainingLogRow.job_id == job_id)
            )
            version = await db.get(ModelVersionRow, trained_version_id(job_id))
            return (
                job.status,
                job.result_model_version_id,
                int(points or 0),
                int(lines or 0),
                None if version is None else version.evaluation_status,
            )

    return await _with_process_db(work)  # type: ignore[return-value] — `work` trả đúng bộ năm giá trị


def _await_status(job_id: str, status: str) -> tuple[str, str | None, int, int, str | None]:
    """Chờ worker chốt job tới `status`, tối đa `WORKER_WAIT_S`; trả ảnh chụp cuối."""
    deadline = time.monotonic() + WORKER_WAIT_S
    snapshot = asyncio.run(_snapshot(job_id))
    while snapshot[0] != status and time.monotonic() < deadline:
        time.sleep(POLL_S)
        snapshot = asyncio.run(_snapshot(job_id))
    return snapshot


@pytest.mark.usefixtures("process_env")
def test_finish_training_job__J01_smoke(
    celery_test_app: Celery, celery_worker_factory: WorkerFactory, local_storage: LocalDiskStorage
) -> None:
    """Worker thật nhận `heartbeat` → `metrics` → `log` → `finished(succeeded)` như runner gửi.

    Qua session mới: job `succeeded` với bản `trained_version_id(job)` `pending`, N36 có điểm,
    N37 có dòng log — cả bốn task đi qua `worker_sessionmaker()` và kho thật của tiến trình.
    """
    job_id = asyncio.run(_seed(local_storage))
    template, spec = next(iter(LOG_TEMPLATES.items()))
    messages = (
        (HEARTBEAT_TASK, heartbeat(job_id, epoch=1)),
        (METRICS_TASK, metrics(job_id, metric_point(step=0, **{METRIC: 0.7}))),
        (LOG_TASK, log_line(job_id, template=template, params={name: "x" for name in spec.params})),
        (FINISHED_TASK, finished(job_id)),
    )

    with celery_worker_factory([DEFAULT_QUEUE]):
        for name, payload in messages:
            celery_test_app.send_task(name, args=[payload.model_dump(mode="json")], queue=DEFAULT_QUEUE)
        snapshot = _await_status(job_id, "succeeded")
    reset_database_settings_cache()

    assert snapshot == ("succeeded", trained_version_id(job_id), 1, 1, "pending")
