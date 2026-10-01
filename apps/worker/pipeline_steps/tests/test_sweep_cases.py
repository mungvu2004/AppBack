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
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import pytest
from PIL import Image
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import reset_sync_bus_cache, start_run
from apps.api.drawings.tests._helpers import make_scene
from apps.worker.pipeline_steps import jobs
from apps.worker.pipeline_steps.errors import PIPELINE_STEP_TIMEOUT
from apps.worker.pipeline_steps.settings import reset_steps_settings_cache
from apps.worker.pipeline_steps.sweep import CPU_QUEUE, ML_QUEUE, run_stuck_pipeline_sweep
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.db.settings import reset_database_settings_cache
from packages.messaging.redis import SyncRedis, broker_redis, broker_redis_sync
from packages.messaging.streams import EventBus, upload_stream
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import make_complete_upload, make_drawing
from packages.testing.factories.pipeline_orchestrate import make_run_pins
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.vision.preprocess.tests.synthetic import encode

type Maker = async_sessionmaker[AsyncSession]

_log = logging.getLogger(__name__)

REQUEUE_AFTER_S: Final = 600
"""`PIPELINE_STEP_REQUEUE_AFTER_S` mặc định của `StepsSettings`; test đặt mốc im quanh số này."""
BATCH: Final = 10


@dataclass(frozen=True, slots=True)
class Arranged:
    """Một lượt `running` đã ghim, có bản vẽ hiện hành — điểm xuất phát mọi test quét bù."""

    run_id: str
    upload_id: str
    floor_pk: int


def png(width: int = 48, height: int = 32) -> bytes:
    """Một PNG thật nhỏ nhất đủ để `make_drawing` đọc được kích thước."""
    return encode(Image.new("RGB", (width, height), "white"), "PNG")


async def arrange_run(
    maker: Maker,
    storage: LocalDiskStorage,
    clock: FakeClock,
    *,
    step: str = "wallSegmentation",
    status: str = "running",
    used: dict[ModelFamily, str] | None = None,
    requeue_count: int = 0,
    with_drawing: bool = True,
    level_id: str | None = None,
    progress_percent: int = 5,
) -> Arranged:
    """Lượt chạy ở `step` với `status`, dòng ghim và (tuỳ chọn) bản vẽ hiện hành đã commit.

    `start_run` mở lượt `pending` ở `preprocess`; bước, trạng thái và `progress_percent` đặt bằng
    `UPDATE` vì không có lõi nào đẩy lượt tới giữa chuỗi mà không gửi thông điệp. Mặc định 5 là
    trọng số của `preprocess` — đúng số `Progress` của một lượt vừa vào `wallSegmentation`.

    Cả giao dịch nằm trong `drop_after_commit()`: `start_run` tự hẹn một `pipeline.orchestrate.start`
    sau commit (`runs.py:132`), mà thông điệp đó vừa làm `pipeline.cpu` "còn việc" (lõi giữ mọi
    lượt) vừa lẫn vào phần đếm hàng của test. Bỏ nó đi **là** cảnh cần dựng: thông điệp đã mất.
    """
    with drop_after_commit():
        return await _arrange(
            maker,
            storage,
            clock,
            step=step,
            status=status,
            used=used,
            requeue_count=requeue_count,
            with_drawing=with_drawing,
            level_id=level_id,
            progress_percent=progress_percent,
        )


async def _arrange(
    maker: Maker,
    storage: LocalDiskStorage,
    clock: FakeClock,
    *,
    step: str,
    status: str,
    used: dict[ModelFamily, str] | None,
    requeue_count: int,
    with_drawing: bool,
    level_id: str | None,
    progress_percent: int,
) -> Arranged:
    """Thân của `arrange_run`, tách ra để `drop_after_commit()` bọc đúng một khối `async with`."""
    async with maker() as db:
        scene = await make_scene(db, level_id=level_id)
        upload = await make_complete_upload(
            db, storage, project=scene.project, floor=scene.floor, data=png(), file_name="plan.png"
        )
        if with_drawing:
            await make_drawing(db, storage, upload=upload, png=png())
        run = await start_run(db, upload_id=upload.id, clock=clock)
        await make_run_pins(db, run_id=run.id, used=used, step_requeue_count=requeue_count)
        await db.execute(
            update(PipelineRunRow)
            .where(PipelineRunRow.id == run.id)
            .values(status=status, current_step=step, started_at=clock.now(), progress_percent=progress_percent)
        )
        await db.commit()
    await after_commit_idle(db)
    placed = await read_run(maker, run.id)
    assert (placed.status, placed.current_step) == (status, step), "bản dựng không đặt được lượt vào đúng bước"
    return Arranged(run_id=run.id, upload_id=upload.id, floor_pk=scene.floor.pk)


async def set_idle(maker: Maker, run_id: str, clock: FakeClock, *, seconds: float) -> datetime:
    """Đặt hai `updated_at` **và** `started_at` về một mốc cố định rồi `fake_clock.set` tới `mốc + seconds`.

    Trả mốc im đã **đọc lại** từ DB: giờ của Postgres và của `fake_clock` không cùng nguồn, nên
    chỉ giá trị đọc lại mới dùng được để tính ngưỡng ([8]). `started_at` đi cùng mốc vì nếu không,
    `now - started_at` vượt `PIPELINE_RUN_MAX_S` và mọi luật giữ theo hàng bị bỏ qua.
    """
    mark = datetime(2026, 3, 1, 12, tzinfo=UTC)
    async with maker() as db:
        await db.execute(
            update(PipelineRunRow).where(PipelineRunRow.id == run_id).values(updated_at=mark, started_at=mark)
        )
        await db.execute(
            update(PipelineRunModelsRow).where(PipelineRunModelsRow.run_id == run_id).values(updated_at=mark)
        )
        await db.commit()
        stmt = text(
            "SELECT greatest(r.updated_at, m.updated_at) FROM pipeline_runs r"
            " JOIN pipeline_run_models m ON m.run_id = r.id WHERE r.id = :run_id"
        )
        read_back = cast("datetime", (await db.execute(stmt, {"run_id": run_id})).scalar_one())
    clock.set(read_back + timedelta(seconds=seconds))
    _log.info("sweep_test_idle", extra={"run_id": run_id, "idle_s": seconds, "mark": read_back.isoformat()})
    return read_back


async def read_run(maker: Maker, run_id: str) -> PipelineRunRow:
    """Dòng `pipeline_runs` trên session mới (trạng thái đã commit, không cache identity map)."""
    async with maker() as db:
        return (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()


async def read_count(maker: Maker, run_id: str) -> int:
    """`step_requeue_count` hiện tại của lượt."""
    async with maker() as db:
        stmt = select(PipelineRunModelsRow.step_requeue_count).where(PipelineRunModelsRow.run_id == run_id)
        return (await db.execute(stmt)).scalar_one()


async def progress_events(bus: EventBus, upload_id: str) -> list[tuple[object, object, object]]:
    """`(status, step, progressPercent)` của mọi `Progress` trên luồng của một lượt tải."""
    events = await bus.read_after(upload_stream(upload_id), "0-0")
    return [(e.data["status"], e.data["step"], e.data["progressPercent"]) for e in events]


async def sweep(maker: Maker, clock: FakeClock, *, batch: int = BATCH) -> None:
    """Một lượt quét với client Redis riêng, đóng lại sau (lõi không đóng `broker` của người gọi)."""
    broker = broker_redis()
    try:
        await run_stuck_pipeline_sweep(maker, broker, clock, batch=batch)
    finally:
        await broker.aclose()


@pytest.fixture
def clean_queues(messaging_env: None) -> Iterator[SyncRedis]:
    """Hai hàng dùng chung cả phiên; `DEL` trước **và** sau mỗi test (BE-00 §12, test song song)."""
    client = broker_redis_sync()
    client.delete(ML_QUEUE, CPU_QUEUE)
    yield client
    client.delete(ML_QUEUE, CPU_QUEUE)


@pytest.fixture
def sweep_env(
    clean_queues: SyncRedis, db_url: str, monkeypatch: pytest.MonkeyPatch, local_storage: LocalDiskStorage
) -> Iterator[SyncRedis]:
    """Biến môi trường để hàm lịch dựng đúng DB/broker của test; cache đọc lại hai đầu."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    reset_steps_settings_cache()
    reset_sync_bus_cache()
    yield clean_queues
    reset_database_settings_cache()
    reset_steps_settings_cache()
    reset_sync_bus_cache()


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
        events = await progress_events(event_bus, arranged.upload_id)
        assert events[-1] == ("running", "wallSegmentation", 5), f"lượt {attempt + 1} phải phát lại Progress"

    # Ngay dưới ngưỡng lùi lượt 2 → không gửi lại (lùi thật sự x 2, không phải hằng).
    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=REQUEUE_AFTER_S * 2 - 1)
    sweep_env.delete(ML_QUEUE, CPU_QUEUE)
    await sweep(db_sessionmaker, fake_clock)
    assert sweep_env.llen(ML_QUEUE) == 0
    assert await read_count(db_sessionmaker, arranged.run_id) == 3

    await set_idle(db_sessionmaker, arranged.run_id, fake_clock, seconds=REQUEUE_AFTER_S * 8 + 1)
    await sweep(db_sessionmaker, fake_clock)

    row = await read_run(db_sessionmaker, arranged.run_id)
    _log.info("sweep_test_requeue_marks", extra={"run_id": arranged.run_id, "idle_s": marks})
    assert sweep_env.llen(ML_QUEUE) == 0
    assert (row.status, row.error_code, row.current_step) == ("failed", PIPELINE_STEP_TIMEOUT, "wallSegmentation")
    assert row.ended_at is None
    assert marks == [601, 1201, 2401]
