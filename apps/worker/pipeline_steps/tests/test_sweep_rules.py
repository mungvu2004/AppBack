"""Luật chọn lượt và gửi lại của `run_stuck_pipeline_sweep` (B5-06c [8] "sweep", "Hàng treo", "Tên hàng").

Tách khỏi `test_sweep_cases.py` vì những test này **không** mang mã case: chúng kiểm luật bên
trong lõi (hàng nào giữ lượt nào, bước nào gửi task nào), còn J01/J06/J07 kiểm dây lịch và lùi x
2. Bản dựng dùng chung (`arrange_run`, `set_idle`, `sweep`, hai fixture) nhập từ file kia — một
bản, không hai bản lệch nhau (R-02); `__all__` khai lại hai fixture để pytest thấy chúng.

"Hàng treo" dùng một `redis.asyncio.Redis` **lớp con** có `llen` chờ `asyncio.Event` không bao giờ đặt: đó
là cách duy nhất dựng cảnh broker treo mà không mock Redis (K23 — client vẫn thật, chỉ một lệnh bị
chặn). Trần "≤ 2 s" là trần của prompt chứ không phải hợp đồng hiệu năng, nên không gắn marker
`perf` (test ở đây không mang mã case, và `HANG_BUDGET_S` chỉ là `LLEN_TIMEOUT_S` + mép); số đo in
bằng `logging`.
"""

import asyncio
import logging
import time
from typing import Final, cast

import pytest
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from apps.worker.pipeline_orchestrate.pins import record_used
from apps.worker.pipeline_steps.errors import PIPELINE_RESULT_INVALID
from apps.worker.pipeline_steps.settings import get_steps_settings
from apps.worker.pipeline_steps.step_done import BUILD_STEP, BUILD_TASK, QUALITY_TASK
from apps.worker.pipeline_steps.sweep import CPU_QUEUE, ML_QUEUE, _requeue_one, run_stuck_pipeline_sweep
from apps.worker.pipeline_steps.tests import helpers
from apps.worker.pipeline_steps.tests.helpers import (
    BATCH,
    REQUEUE_AFTER_S,
    Maker,
    arrange_run,
    queued_tasks,
    read_count,
    run_row,
    set_idle,
    sweep,
)
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.redis import SyncRedis
from packages.messaging.settings import get_messaging_settings
from packages.ml_contracts.families import MODEL_FAMILIES
from packages.ml_contracts.payloads import InferStepPayload
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

clean_queues = helpers.clean_queues
sweep_env = helpers.sweep_env
"""Hai fixture của `helpers`, gán lại để pytest thấy chúng trong module này (R-02)."""


_log = logging.getLogger(__name__)

HANG_BUDGET_S: Final = 2.0
"""Trần của prompt cho một lượt quét khi `LLEN` treo (`LLEN_TIMEOUT_S` của hai lệnh song song + mép)."""
IDLE_S: Final = REQUEUE_AFTER_S + 60
"""Mốc im dùng cho mọi lượt ở file này: quá ngưỡng lần đầu (`step_requeue_count = 0`)."""

_START_TASK: Final = "pipeline.orchestrate.start"


class _HangingLlen(Redis):
    """Client Redis thật mà `llen` chặn ở một `asyncio.Event` không ai đặt, hay ném lỗi kết nối.

    Lớp con chứ không mock: mọi lệnh khác vẫn đi tới Redis thật, chỉ `llen` bị thay (K23).
    `fail` đặt sau khi dựng (`from_url` chuyển mọi kwargs cho `ConnectionPool`).
    """

    fail: bool = False
    calls: int = 0
    entered: asyncio.Event
    """Đặt ở lượt `llen` đầu; test gán trước khi gọi lõi (lớp con của `Redis` không có `__init__` riêng)."""

    async def llen(self, name: object) -> int:
        """Đếm lượt gọi rồi ném (`fail`) hay chờ vô hạn; không bao giờ trả số thật."""
        self.calls += 1
        self.entered.set()
        if self.fail:
            raise RedisConnectionError("broker không phục vụ được")
        await asyncio.Event().wait()
        return 0


async def _checkedout_while_blocked(pool: QueuePool, broker: _HangingLlen) -> int:
    """Số kết nối đang bị giữ, đo ngay khi `LLEN` đầu đã vào và chưa ai trả lời.

    Chờ bằng `broker.entered` chứ không vòng `asyncio.sleep` (ASYNC110): `asyncio.gather` đã xếp
    cả hai `LLEN` trước khi hàm này chạy, nên lúc event được đặt là lúc lõi đang treo ở Redis.
    """
    await asyncio.wait_for(broker.entered.wait(), HANG_BUDGET_S)
    return pool.checkedout()


async def test_sweep_resends_remaining_families_when_walls_used(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`used` đã có `wallSegmentation` → chỉ gửi lại hai họ còn lại (`queue_infer` bỏ họ đã xong)."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, used={"wallSegmentation": "classic"})
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    steps = {InferStepPayload.model_validate(body).step for body in queued_payloads(sweep_env, ML_QUEUE)}
    assert steps == {family for family in MODEL_FAMILIES if family != "wallSegmentation"}


async def test_sweep_resends_quality_check(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt kẹt ở `qualityCheck` → đúng một `pipeline.quality.run` mang `run_id` của nó."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="qualityCheck")
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    assert queued_tasks(sweep_env, CPU_QUEUE) == [QUALITY_TASK]
    payload = RunStepPayload.model_validate(queued_payloads(sweep_env, CPU_QUEUE)[0])
    assert payload.run_id == arranged.run_id


async def test_sweep_resends_preprocess_start(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt kẹt ở `preprocess` → đúng một `pipeline.orchestrate.start` (dùng lại `send_start_after_commit`)."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="preprocess")
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    assert queued_tasks(sweep_env, CPU_QUEUE) == [_START_TASK]
    payload = PipelineStartPayload.model_validate(queued_payloads(sweep_env, CPU_QUEUE)[0])
    assert (payload.run_id, payload.upload_id) == (arranged.run_id, arranged.upload_id)


async def test_sweep_resends_spatial_data_build(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt kẹt ở `spatialDataBuild` → đúng một `pipeline.build.run` qua `queue_build` dùng chung."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="spatialDataBuild")
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    assert queued_tasks(sweep_env, CPU_QUEUE) == [BUILD_TASK]


async def test_sweep_leaves_pending_runs(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt `pending` quá hạn là việc của B2-04: không gửi lại, số đếm không tăng."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="preprocess", status="pending")
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S * 10)

    await sweep(db_sessionmaker, fake_clock)

    assert (sweep_env.llen(CPU_QUEUE), sweep_env.llen(ML_QUEUE)) == (0, 0)
    assert await read_count(db_sessionmaker, arranged.run_id) == 0


async def test_sweep_holds_ml_runs_but_not_quality_when_infer_busy(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`ml.infer` còn việc + `batch=2`: hai lượt ML cũ bị giữ nhưng không chiếm suất lượt `qualityCheck`.

    Nếu lượt bị giữ chiếm suất `LIMIT` thì lượt `qualityCheck` (mới hơn) không bao giờ tới được —
    đó là bất biến "không chặn đầu lô" ([6] bước 2).
    """
    old_a = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    old_b = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    quality = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="qualityCheck")
    for run_id, idle in ((old_a.run_id, IDLE_S + 200), (old_b.run_id, IDLE_S + 100), (quality.run_id, IDLE_S)):
        await set_idle(db_sessionmaker, run_id, fake_clock, seconds=idle)
    send_task("ml.infer.walls.segment", RunStepPayload(run_id=old_a.run_id))

    await sweep(db_sessionmaker, fake_clock, batch=2)

    assert queued_tasks(sweep_env, CPU_QUEUE) == [QUALITY_TASK]
    assert await read_count(db_sessionmaker, old_a.run_id) == 0
    assert await read_count(db_sessionmaker, old_b.run_id) == 0
    assert await read_count(db_sessionmaker, quality.run_id) == 1


async def test_sweep_holds_every_run_when_cpu_busy(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`pipeline.cpu` còn việc → mọi lượt bị giữ (kết quả ML và mọi bước sau đi qua hàng này)."""
    ml_run = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    quality = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="qualityCheck")
    for run_id in (ml_run.run_id, quality.run_id):
        await set_idle(db_sessionmaker, run_id, fake_clock, seconds=IDLE_S)
    send_task(BUILD_TASK, RunStepPayload(run_id=ml_run.run_id))

    await sweep(db_sessionmaker, fake_clock)

    assert sweep_env.llen(ML_QUEUE) == 0
    assert queued_tasks(sweep_env, CPU_QUEUE) == [BUILD_TASK]
    assert await read_count(db_sessionmaker, ml_run.run_id) == 0
    assert await read_count(db_sessionmaker, quality.run_id) == 0


async def test_sweep_ignores_queues_past_run_max(
    sweep_env: SyncRedis,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quá `PIPELINE_RUN_MAX_S` từ `started_at` → xử lý tiếp dù `pipeline.cpu` còn việc."""
    monkeypatch.setenv("PIPELINE_RUN_MAX_S", "60")
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, step="qualityCheck")
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)
    send_task(BUILD_TASK, RunStepPayload(run_id=arranged.run_id))

    await sweep(db_sessionmaker, fake_clock)

    assert queued_tasks(sweep_env, CPU_QUEUE) == [QUALITY_TASK, BUILD_TASK]
    assert await read_count(db_sessionmaker, arranged.run_id) == 1


async def test_sweep_fails_run_without_matching_drawing(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Bước ML mà tầng không có bản vẽ của lượt tải này → `failed` `PIPELINE_RESULT_INVALID`."""
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock, with_drawing=False)
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code) == ("failed", PIPELINE_RESULT_INVALID)
    assert sweep_env.llen(ML_QUEUE) == 0


@pytest.mark.parametrize("fail", [False, True], ids=["treo", "connection_error"])
async def test_sweep_survives_unreadable_queue(
    sweep_env: SyncRedis,
    db_sessionmaker: Maker,
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    fail: bool,
) -> None:
    """`LLEN` treo hay ném → lõi trả trong `HANG_BUDGET_S`, pool rỗng, không lượt nào bị đụng.

    Pool **một** kết nối là phần chứng minh: nếu `_queue_busy` chạy trong một session thì
    `checkedout()` đo lúc hai `LLEN` còn treo là 1, và lượt `_candidates` sau đó cũng chết vì
    `db_pool_timeout_s=1` (khuôn `test_persist_k36.py`, K36). Hai hàng "còn việc" → mọi lượt giữ.

    Số pool chỉ đo được ở biến thể "treo": khi `llen` ném ngay thì không có khoảnh khắc nào để
    chụp, và `_candidates` sau đó giữ đúng một kết nối — biến thể đó chỉ kiểm lõi không chết.
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)
    settings = DatabaseSettings(database_url=db_url, db_pool_size=1, db_max_overflow=0, db_pool_timeout_s=1)
    engine: AsyncEngine = create_engine(settings)
    broker = cast("_HangingLlen", _HangingLlen.from_url(get_messaging_settings().redis_broker_url))
    broker.fail = fail
    broker.entered = asyncio.Event()
    started = time.monotonic()
    try:
        _, checked_out = await asyncio.gather(
            run_stuck_pipeline_sweep(create_sessionmaker(engine), broker, fake_clock, batch=BATCH),
            _checkedout_while_blocked(cast("QueuePool", engine.pool), broker),
        )
    finally:
        await broker.aclose()
        await engine.dispose()
    elapsed = time.monotonic() - started

    _log.info("sweep_hang_elapsed_s=%.3f fail=%s calls=%d", elapsed, fail, broker.calls)
    assert broker.calls == 2
    assert elapsed < HANG_BUDGET_S
    if not fail:
        assert checked_out == 0, "LLEN treo mà pool còn kết nối: lõi đọc Redis trong session (K36)"
    assert sweep_env.llen(ML_QUEUE) == 0
    assert await read_count(db_sessionmaker, arranged.run_id) == 0
    assert (await run_row(db_sessionmaker, arranged.run_id)).status == "running"


def test_queue_names_match_kombu_list_keys(sweep_env: SyncRedis) -> None:
    """`LLEN` của hai khoá lõi đọc đếm đúng thông điệp kombu đã xếp ([8] "Tên hàng").

    Chốt bằng số vì khoá danh sách của kombu phụ thuộc `priority_steps`/`sep` của Celery: `_base_conf`
    không khai hai tuỳ chọn đó nên khoá **là** tên hàng, và test này đổ ngay khi điều đó đổi.
    """
    send_task("ml.infer.walls.segment", RunStepPayload(run_id=new_id("run", SystemClock())))
    send_task(BUILD_TASK, RunStepPayload(run_id=new_id("run", SystemClock())))

    assert (sweep_env.llen(ML_QUEUE), sweep_env.llen(CPU_QUEUE)) == (1, 1)
    assert (ML_QUEUE, CPU_QUEUE) == ("ml.infer", "pipeline.cpu")


async def test_requeue_one_skips_run_that_changed_after_selection(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Hai cửa bỏ của `_requeue_one`: lượt không khoá được, và lượt mất dòng ghim.

    Gọi lõi con trực tiếp vì cả hai chỉ xảy ra khi trạng thái đổi **giữa** truy vấn chọn lô và
    `lock_run` — một lượt quét trọn vẹn không dựng được cảnh đó mà không chen vào giữa lõi.
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)
    settings = get_steps_settings()

    await _requeue_one(db_sessionmaker, "run_khong_co", fake_clock, settings)
    async with db_sessionmaker() as db:
        await db.execute(text("DELETE FROM pipeline_run_models WHERE run_id = :run_id"), {"run_id": arranged.run_id})
        await db.commit()
    await _requeue_one(db_sessionmaker, arranged.run_id, fake_clock, settings)

    assert (sweep_env.llen(ML_QUEUE), sweep_env.llen(CPU_QUEUE)) == (0, 0)
    assert (await run_row(db_sessionmaker, arranged.run_id)).status == "running"


async def test_sweep_keeps_run_whose_family_just_finished(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Một họ ML vừa xong (`record_used`) → lượt **không** im, dù hai `updated_at` đã quá ngưỡng.

    `pins.record_used` ghi bằng `text()` thuần nên `TimestampMixin.onupdate` không chạy: chỉ
    `last_used_at` nhảy. Nếu mốc im bỏ cột đó, quét bù gửi lại đúng suy luận **đang chạy** và đốt
    một lượt `step_requeue_count`. Test đi đường thật (`record_used`), không đặt tay cột nào.
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)
    async with db_sessionmaker() as db:
        await record_used(db, run_id=arranged.run_id, family=MODEL_FAMILIES[0], used="classic")
        await db.commit()

    await sweep(db_sessionmaker, fake_clock)

    assert (sweep_env.llen(ML_QUEUE), sweep_env.llen(CPU_QUEUE)) == (0, 0)
    assert await read_count(db_sessionmaker, arranged.run_id) == 0
    assert (await run_row(db_sessionmaker, arranged.run_id)).status == "running"


async def test_sweep_fails_build_step_without_matching_drawing(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`spatialDataBuild` mà tầng không có bản vẽ của lượt tải này → `queue_build` đánh `failed`.

    Khác `test_sweep_fails_run_without_matching_drawing`: ca đó đi nhánh ML của `_resend`, ca này
    đi `queue_build` của `step_done` (nhánh hỏng duy nhất của hàm dùng chung đó).
    """
    arranged = await arrange_run(
        db_sessionmaker, local_storage, fake_clock, step=BUILD_STEP, with_drawing=False, progress_percent=70
    )
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=IDLE_S)

    await sweep(db_sessionmaker, fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", PIPELINE_RESULT_INVALID, BUILD_STEP)
    assert (sweep_env.llen(ML_QUEUE), sweep_env.llen(CPU_QUEUE)) == (0, 0)
