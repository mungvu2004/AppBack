"""Ma trận case J của `orchestrate_pipeline_step_done` (B5-06c việc A, [8]).

J01/J06/J09/J10 gọi thẳng lõi `run_pipeline_step_done` (nhanh, đọc được khẳng định DB);
J01_smoke và J08 đi qua task thật vì chúng kiểm đúng dây `define_task` → hàng `pipeline.cpu`
và đường thông điệp độc. Dịch vụ thật (K23): Postgres, Redis, kho đĩa `local_storage`.
"""

import asyncio
import logging
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.progress import progress_wire
from apps.api.project_settings.read import read_settings
from apps.worker.pipeline_build.artifacts import layer_key
from apps.worker.pipeline_orchestrate.pins import load_pins, mark_persisted
from apps.worker.pipeline_steps import step_done as core
from apps.worker.pipeline_steps import tasks
from apps.worker.pipeline_steps.settings import get_steps_settings
from apps.worker.pipeline_steps.step_done import BUILD_STEP, run_pipeline_step_done
from apps.worker.pipeline_steps.sweep import _IDLE_MARK, CPU_QUEUE
from apps.worker.pipeline_steps.tests import helpers
from apps.worker.pipeline_steps.tests.helpers import (
    deliver_ml,
    open_run_at_ml,
    put_ml_artifacts,
    step_result,
    steps_seen,
    sweep,
)
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.db.hooks import after_commit_idle
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import SyncRedis
from packages.messaging.streams import EventBus, upload_stream
from packages.ml_contracts.families import FAMILY_STEP, ModelFamily
from packages.ml_contracts.payloads import StepResultPayload
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.testing.fixtures.messaging import queued_payloads

type Maker = async_sessionmaker[AsyncSession]

WALLS: Final[ModelFamily] = "wallSegmentation"
OBJECTS: Final[ModelFamily] = "openingAndFurnitureDetection"
TEXTS: Final[ModelFamily] = "dimensionReading"

_log = logging.getLogger(__name__)

clean_queues = helpers.clean_queues
"""Fixture hai hàng của `helpers`, gán lại để pytest thấy nó trong module này (R-02)."""


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường một tiến trình worker thật (khuôn `pipeline_orchestrate/tests/test_start_cases.py`).

    Task tự dựng `worker_sessionmaker()` từ `DATABASE_URL`, không mượn engine của fixture
    `db_sessionmaker` (engine đó gắn vòng sự kiện pytest-asyncio — dùng chéo vòng là lỗi).
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-pipeline-steps-step-done-01")
    caches = (reset_settings_cache, reset_database_settings_cache, reset_storage_settings_cache)
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_step_done__J01(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_queues: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Ba bước ML về **không** theo thứ tự rồi `spatialDataBuild`: chuỗi `Progress`, một `build`, một `persist`.

    Khẳng định cốt lõi của [8] J01: kết quả `dimensionReading` tới trước không phát sự kiện nào
    (lượt vẫn đứng ở `wallSegmentation`), và lượt giao cuối đẩy **hai** bước trong một commit.
    """
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, clean_queues)
    before = len(await event_bus.read_after(upload_stream(arranged.upload_id), "0-0"))

    await deliver_ml(db_sessionmaker, local_storage, arranged, TEXTS, fake_clock)
    assert await steps_seen(event_bus, arranged.upload_id, after=before) == []

    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)
    assert await steps_seen(event_bus, arranged.upload_id, after=before) == [("running", OBJECTS, 35)]

    await deliver_ml(db_sessionmaker, local_storage, arranged, OBJECTS, fake_clock)
    sequence = await steps_seen(event_bus, arranged.upload_id, after=before)
    _log.info("j01_progress=%s", sequence)
    assert sequence == [("running", OBJECTS, 35), ("running", TEXTS, 55), ("running", BUILD_STEP, 70)]

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
        scale = (await read_settings(db, arranged.project_id)).default_scale_mm_per_px
        wire = await progress_wire(db, arranged.upload_id)
    assert pins is not None
    assert set(pins.used) == {WALLS, OBJECTS, TEXTS}
    assert pins.used[WALLS] == "classic"
    assert pins.step_requeue_count == 0
    assert (wire["status"], wire["step"], wire["progressPercent"]) == ("running", BUILD_STEP, 70)
    builds = queued_payloads(clean_queues, CPU_QUEUE)
    assert [m["run_id"] for m in builds] == [arranged.run_id], builds
    assert (Decimal(str(builds[0]["fallback_mm_per_px"])), builds[0]["width_px"]) == (scale, arranged.width_px)

    clean_queues.delete(CPU_QUEUE)
    built = step_result(arranged, BUILD_STEP, artifact_keys=(layer_key(arranged.run_prefix),))
    await run_pipeline_step_done(built, sessionmaker=db_sessionmaker, clock=fake_clock)
    persists = queued_payloads(clean_queues, CPU_QUEUE)
    assert [m["run_id"] for m in persists] == [arranged.run_id], persists

    async with db_sessionmaker() as db:
        await mark_persisted(db, run_id=arranged.run_id, revision=3)
        await db.commit()
    clean_queues.delete(CPU_QUEUE)
    await run_pipeline_step_done(built, sessionmaker=db_sessionmaker, clock=fake_clock)
    assert queued_payloads(clean_queues, CPU_QUEUE) == []


async def two_ml_steps_done(
    maker: Maker, storage: LocalDiskStorage, clock: FakeClock, client: SyncRedis
) -> StepResultPayload:
    """Lượt đã có kết quả tường và ô mở; trả payload `dimensionReading` cho lượt giao cuối."""
    arranged = await open_run_at_ml(maker, storage, clock, client)
    for family in (WALLS, OBJECTS):
        await deliver_ml(maker, storage, arranged, family, clock)
    keys = await put_ml_artifacts(storage, arranged, TEXTS)
    client.delete(CPU_QUEUE)
    return step_result(arranged, FAMILY_STEP[TEXTS], artifact_keys=keys)


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_orchestrate_pipeline_step_done__J01_smoke(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_queues: SyncRedis,
) -> None:
    """Task thật qua `apply` (bước sau đi **cùng** hàng `pipeline.cpu`, nên không chạy worker).

    Test đồng bộ: `define_task` chạy thân async bằng vòng sự kiện riêng của tiến trình worker,
    không lồng được vào vòng của pytest-asyncio. Không gọi `after_commit_idle`: `create_celery`
    của app thử đặt `DB_AFTER_COMMIT_INLINE=1` nên callback sau commit chạy tại chỗ.
    """
    payload = asyncio.run(two_ml_steps_done(db_sessionmaker, local_storage, fake_clock, clean_queues))

    result = tasks.orchestrate_pipeline_step_done.apply(args=[payload.model_dump(mode="json")])

    assert result.successful(), result.traceback
    assert [m["run_id"] for m in queued_payloads(clean_queues, CPU_QUEUE)] == [payload.run_id]


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_step_done__J06(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_queues: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Giao lặp cùng một `completed`: `used` không đổi, không `Progress` mới, vẫn một `build`."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, clean_queues)
    for family in (WALLS, OBJECTS, TEXTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)
    before = len(await event_bus.read_after(upload_stream(arranged.upload_id), "0-0"))

    await deliver_ml(db_sessionmaker, local_storage, arranged, OBJECTS, fake_clock)

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert set(pins.used) == {WALLS, OBJECTS, TEXTS}
    assert await steps_seen(event_bus, arranged.upload_id, after=before) == []
    assert [m["run_id"] for m in queued_payloads(clean_queues, CPU_QUEUE)] == [arranged.run_id]


@pytest.mark.usefixtures("celery_test_app")
def test_orchestrate_pipeline_step_done__J08(caplog: pytest.LogCaptureFixture) -> None:
    """Bước lạ và `schema_version` 2 đều bị `define_task` loại trước khi vào thân → `poison_message`."""
    bad = {"run_id": "run_01J0000000000000000000000", "step": "lạ", "status": "completed", "duration_ms": 1}
    with caplog.at_level(logging.WARNING):
        strange = tasks.orchestrate_pipeline_step_done.apply(args=[bad])
        future = tasks.orchestrate_pipeline_step_done.apply(args=[{**bad, "step": BUILD_STEP, "schema_version": 2}])
    assert strange.successful()
    assert future.successful()
    assert caplog.text.count("poison_message") == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_step_done__J09(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, clean_queues: SyncRedis
) -> None:
    """Rollback sau `record_step`: không `pipeline.build.run` nào rời tiến trình (J09, BE-00 §7).

    Gọi thân giao dịch trực tiếp để điều khiển commit/rollback — đó đúng là bất biến cần kiểm:
    mọi việc gửi đi đều treo ở `on_after_commit`, không có `send_task` nào trong giao dịch.
    """
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, clean_queues)
    for family in (WALLS, OBJECTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)
    keys = await put_ml_artifacts(local_storage, arranged, TEXTS)
    payload = step_result(arranged, FAMILY_STEP[TEXTS], artifact_keys=keys)
    clean_queues.delete(CPU_QUEUE)

    async with db_sessionmaker() as db:
        assert await core._step_done(db, payload, fake_clock) is True
        await db.rollback()
    await after_commit_idle(db)

    assert queued_payloads(clean_queues, CPU_QUEUE) == []
    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert TEXTS not in pins.used


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_step_done__J10(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    clean_queues: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Callback bị bỏ (`drop_after_commit`) → giao lại không gửi; lõi quét bù mới gửi `build`.

    Đây là lý do `step_done` **không** gửi lại khi giao lặp: bước đã đẩy rồi, nên chỉ quét bù
    (sở hữu số đếm lùi) được phép xếp lại bước hiện tại.
    """
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, clean_queues)
    for family in (WALLS, OBJECTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)
    clean_queues.delete(CPU_QUEUE)

    with drop_after_commit():
        await deliver_ml(db_sessionmaker, local_storage, arranged, TEXTS, fake_clock)
    assert queued_payloads(clean_queues, CPU_QUEUE) == []

    await deliver_ml(db_sessionmaker, local_storage, arranged, TEXTS, fake_clock)
    assert queued_payloads(clean_queues, CPU_QUEUE) == []

    async with db_sessionmaker() as db:
        mark = (await db.execute(_IDLE_MARK, {"run_id": arranged.run_id})).scalar_one()
    after_s = get_steps_settings().PIPELINE_STEP_REQUEUE_AFTER_S
    fake_clock.set(mark + timedelta(seconds=after_s + 1))
    await sweep(db_sessionmaker, fake_clock, batch=10)

    assert [m["run_id"] for m in queued_payloads(clean_queues, CPU_QUEUE)] == [arranged.run_id]
    events = await event_bus.read_after(upload_stream(arranged.upload_id), "0-0")
    last = events[-1].data
    assert (last["status"], last["step"], last["progressPercent"]) == ("running", BUILD_STEP, 70)


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_fail_pipeline_step_done_runs_core_on_process_loop(caplog: pytest.LogCaptureFixture) -> None:
    """`on_failed` đồng bộ mà `define_task` gọi: lõi chạy trên vòng sự kiện của tiến trình worker.

    Lượt không tồn tại là ca rẻ nhất đi hết đường dây đồng bộ → `runner()` → lõi: không cần
    sân khấu nào, và khẳng định đúng điều cần: `on_failed` **không** ném với kết quả muộn.
    """
    missing = StepResultPayload(run_id=new_id("run", SystemClock()), step=BUILD_STEP, status="completed", duration_ms=1)

    with caplog.at_level(logging.INFO):
        tasks.fail_pipeline_step_done(missing, "RETRY_EXHAUSTED")

    assert "pipeline_result_ignored" in caplog.text
