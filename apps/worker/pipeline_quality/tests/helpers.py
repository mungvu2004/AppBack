"""Dựng cảnh "lượt đứng ở `qualityCheck`" cho mọi test của `pipeline_quality` (B5-07, "Chữ ký chung").

Dùng lại cảnh `pipeline_persist` rồi chạy **lõi** `run_persist` thật (không mock, K23) để lượt
nhảy đúng tới bước này: bốn bước trước + `spatialDataBuild` đã `completed`, lớp AI đã ghi,
`persisted_revision` đã đặt. `run_persist` xếp `pipeline.quality.run` sau commit (K17) — dọn
nó khỏi hàng `pipeline.cpu` ngay trong hàm để test tự gọi `run_quality`/`fail_quality` mà
không có một message Celery thật trùng lặp chạy nền.
"""

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.ml.runtime.settings import reset_ml_settings_cache
from apps.ml.runtime.tasks_util import reset_infer_context
from apps.worker.pipeline_build.tasks import reset_build_context
from apps.worker.pipeline_orchestrate.tasks import reset_orchestrate_storage
from apps.worker.pipeline_persist.service import run_persist
from apps.worker.pipeline_persist.tasks import reset_persist_storage
from apps.worker.pipeline_persist.tests.helpers import Arranged, open_run_at_build, put_layer, sample_built
from apps.worker.pipeline_quality.tasks import reset_quality_storage
from packages.core.clock import Clock
from packages.core.settings import reset_settings_cache
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import broker_redis_sync
from packages.storage.port import ObjectStorage
from packages.storage.settings import reset_storage_settings_cache

__all__ = ["Arranged", "open_run_at_quality", "process_env"]

_TASK_RESETS = (
    reset_build_context,
    reset_orchestrate_storage,
    reset_persist_storage,
    reset_quality_storage,
    reset_infer_context,
)
"""Danh sách `reset_*` **đầy đủ** (R-02): mọi tiến trình worker trong một dây e2e, kể cả ML."""


@pytest_asyncio.fixture(loop_scope="function")
async def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Môi trường một tiến trình duy nhất cho task thật (và app thật khi e2e cần), dùng chung
    giữa `test_runtime.py` (B) và `tests/e2e/test_pipeline_e2e.py` (C) — gom theo R-02.

    Task tự đọc biến môi trường trên vòng sự kiện của chính nó (không truyền fixture object
    vào task). Thiếu `reset_infer_context` làm lượt e2e thứ hai đọc kho ML cũ (C2).
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-pipeline-quality-01")
    monkeypatch.delenv("SECRET_KEY_PREVIOUS", raising=False)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", "10")
    monkeypatch.setenv("METRICS_PORT", "0")
    monkeypatch.setenv("ML_BACKEND", "fake")
    caches = (
        reset_settings_cache,
        reset_database_settings_cache,
        reset_storage_settings_cache,
        reset_ml_settings_cache,
    )
    for reset in caches:
        reset()
    for reset in _TASK_RESETS:
        reset()
    yield
    for reset in _TASK_RESETS:
        reset()
    for reset in caches:
        reset()

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
