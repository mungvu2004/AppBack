"""Ma trận J của lịch `sweep_stuck_pipeline_runs` (B5-06c [8] mục "sweep_stuck_pipeline_runs").

Lõi `run_stuck_pipeline_sweep` gọi **thẳng** với `db_sessionmaker`, `local_storage`, `fake_clock`,
`broker_redis()`: dịch vụ thật (K23), nhưng không qua Celery worker — `define_task` là hợp đồng
B0-05 đã có test riêng. `__J01` chỉ gọi hàm lịch `jobs.sweep_stuck_pipeline_runs` để chốt dây
`@periodic` → lõi.

**Mốc im là giờ của DB, không của `fake_clock`**: `set_step_requeue` đi qua `onupdate=func.now()`
của `TimestampMixin`, nên sau mỗi lượt quét `pipeline_run_models.updated_at` nhảy tới giờ thật.
Vì thế mọi test ở đây đặt `updated_at` bằng SQL rồi **đọc lại** giá trị và `fake_clock.set` theo
nó ([8]) — không giả định hai đồng hồ trùng nhau.

Hàm dựng (`arrange_run`, `set_idle`, `drain`) công khai cho `test_sweep_rules.py` nhập: một bản
dựng dùng chung, không hai bản lệch nhau (R-02). `tests/helpers.py` của việc A tới sau nhánh này.
"""

import asyncio
import logging

from sqlalchemy import text

from apps.worker.pipeline_steps import jobs
from apps.worker.pipeline_steps.errors import PIPELINE_STEP_TIMEOUT
from apps.worker.pipeline_steps.sweep import CPU_QUEUE, ML_QUEUE
from apps.worker.pipeline_steps.tests import helpers
from apps.worker.pipeline_steps.tests.helpers import (
    REQUEUE_AFTER_S,
    Maker,
    arrange_run,
    read_count,
    run_row,
    set_idle,
    steps_seen,
    sweep,
)
from packages.messaging.redis import SyncRedis
from packages.messaging.streams import EventBus
from packages.ml_contracts.families import MODEL_FAMILIES
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock

_log = logging.getLogger(__name__)

clean_queues = helpers.clean_queues
sweep_env = helpers.sweep_env
"""Hai fixture của `helpers`, gán lại để pytest thấy chúng trong module này (R-02)."""


async def test_sweep_stuck_pipeline_runs__J01(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Dây lịch: `jobs.sweep_stuck_pipeline_runs()` gửi lại bước ML của một lượt im 11 phút.

    Hàm lịch dùng `SystemClock`, nên mốc im phải cũ theo **giờ thật**: `updated_at` đặt về
    `now() - 11 phút` bằng chính `now()` của DB.
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(
            text("UPDATE pipeline_runs SET updated_at = now() - interval '11 minutes' WHERE id = :run_id"),
            {"run_id": arranged.run_id},
        )
        await db.execute(
            text("UPDATE pipeline_run_models SET updated_at = now() - interval '11 minutes' WHERE run_id = :run_id"),
            {"run_id": arranged.run_id},
        )
        await db.commit()

    # Hàm lịch là task Celery đồng bộ (`run_maybe_async` tự mở vòng sự kiện), nên phải gọi ngoài
    # vòng sự kiện của test — `asyncio.to_thread` cho nó một luồng không có loop.
    await asyncio.to_thread(jobs.sweep_stuck_pipeline_runs)

    assert sweep_env.llen(ML_QUEUE) == len(MODEL_FAMILIES)
    assert await read_count(db_sessionmaker, arranged.run_id) == 1


async def test_sweep_stuck_pipeline_runs__J06(
    sweep_env: SyncRedis, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Giao lặp: hai lượt quét ở **cùng** mốc giờ gửi lại đúng một lần.

    Lượt quét thứ hai thấy `updated_at` mới (do `set_step_requeue`) nên lượt chưa im lại đủ lâu.
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=REQUEUE_AFTER_S + 60)

    await sweep(db_sessionmaker, fake_clock)
    sent_once = sweep_env.llen(ML_QUEUE)
    await sweep(db_sessionmaker, fake_clock)

    assert sent_once == len(MODEL_FAMILIES)
    assert sweep_env.llen(ML_QUEUE) == len(MODEL_FAMILIES)
    assert await read_count(db_sessionmaker, arranged.run_id) == 1


async def test_sweep_stuck_pipeline_runs__J07(
    sweep_env: SyncRedis,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    event_bus: EventBus,
) -> None:
    """Lùi x 2 rồi hết trần: ba lượt gửi lại, lượt thứ tư đánh `PIPELINE_STEP_TIMEOUT`.

    `arrange_run` dựng trong `drop_after_commit()` nên không thông điệp nào ra hàng — đúng cảnh
    thông điệp bước hiện tại mất mà DB vẫn `running`, là lý do lịch này tồn tại. In mốc gửi lại
    (giây tính từ lúc im) của từng lượt bằng `logging` ([11] mục 3).
    """
    arranged = await arrange_run(db_sessionmaker, local_storage, fake_clock)
    assert (sweep_env.llen(ML_QUEUE), sweep_env.llen(CPU_QUEUE)) == (0, 0), "bản dựng không được gửi gì"
    marks: list[float] = []

    for attempt in range(3):
        idle = REQUEUE_AFTER_S * 2**attempt + 1
        await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=idle)
        sweep_env.delete(ML_QUEUE, CPU_QUEUE)
        await sweep(db_sessionmaker, fake_clock)
        marks.append(idle)
        assert sweep_env.llen(ML_QUEUE) == len(MODEL_FAMILIES), f"lượt {attempt + 1} phải gửi ba họ"
        assert await read_count(db_sessionmaker, arranged.run_id) == attempt + 1
        events = await steps_seen(event_bus, arranged.upload_id, after=0)
        assert events[-1] == ("running", "wallSegmentation", 5), f"lượt {attempt + 1} phải phát lại Progress"

    # Ngay dưới ngưỡng lùi lượt 2 → không gửi lại (lùi thật sự x 2, không phải hằng).
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=REQUEUE_AFTER_S * 2 - 1)
    sweep_env.delete(ML_QUEUE, CPU_QUEUE)
    await sweep(db_sessionmaker, fake_clock)
    assert sweep_env.llen(ML_QUEUE) == 0
    assert await read_count(db_sessionmaker, arranged.run_id) == 3

    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=REQUEUE_AFTER_S * 8 + 1)
    await sweep(db_sessionmaker, fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    _log.info("sweep_test_requeue_marks", extra={"run_id": arranged.run_id, "idle_s": marks})
    assert sweep_env.llen(ML_QUEUE) == 0
    assert (row.status, row.error_code, row.current_step) == ("failed", PIPELINE_STEP_TIMEOUT, "wallSegmentation")
    assert row.ended_at is None
    assert marks == [601, 1201, 2401]
