"""Khoá `floors` của `run_persist`: người ghi cùng tầng chờ, và khoá giữ bao lâu (B5-06b [8] "Khoá").

Ba test, hai mục đích khác nhau:

- `test_persist_lock_blocks_concurrent_version`: **đúng/sai** — lõi dừng giữa bước 5 và 6 thì một
  session khác gọi `create_version` cùng tầng phải chờ, và thả ra thì nó xong chứ không chết vì
  `DB_LOCK_TIMEOUT_MS`. Không có trần đồng hồ tường nào là điều kiện đúng/sai (số đo chỉ ghi log),
  nên test này **không** mang marker `perf`.
- hai test `perf` còn lại chỉ **đo**: thời gian giữ khoá trên lớp toà mẫu (có trần 1 s của prompt) và
  trên lớp 20.000 tường (chỉ in số). Cả hai mang marker `perf` theo BE-00 §12 và không mang mã case.

Bọc chứ không mock (K23): hai lớp bọc dưới đây gọi chính `service.create_version`/`service.lock_run`
thật, chỉ chèn thêm một `asyncio.Event` và một mốc thời gian.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import RunRow, lock_run
from apps.api.versions.snapshots import VersionRow, create_version
from apps.worker.pipeline_build.build import BuiltLayer
from apps.worker.pipeline_build.constants import DROPPED_KEYS
from apps.worker.pipeline_persist import service
from apps.worker.pipeline_persist.tests.helpers import Arranged, open_run_at_build, put_layer, sample_built
from packages.core.ids import SPATIAL_PREFIX
from packages.domain.spatial.model import Point, Segment, SpatialLayer, Wall
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.spatial import make_floor_document
from packages.testing.fixtures.clock import FakeClock

type Maker = async_sessionmaker[AsyncSession]

WAIT_S: Final = 30.0
"""Trần **chờ** chống treo cho lõi và cho bên chờ khoá — không phải trần hiệu năng."""
BLOCKED_PROBE_S: Final = 0.5
"""Khoảng chờ để khẳng định bên kia **vẫn chưa** xong: đủ dài để một lượt `create_version` tự do xong."""
RELEASE_AFTER_S: Final = 1.0
"""Giữ khoá thêm bấy nhiêu trước khi thả, theo [8]: còn xa `DB_LOCK_TIMEOUT_MS` = 5 s."""
SAMPLE_HOLD_CEILING_S: Final = 1.0
"""Trần của prompt cho thời gian giữ khoá `floors` trên lớp toà mẫu ([8] "Khoá")."""
BIG_WALLS: Final = 20_000
"""Cỡ lớp của B5-05 ([8] "Khoá"): dựng lưới tường trực tiếp, không qua `build_layer` (quá chậm)."""
BIG_HOLD_DEBT_S: Final = 5.0
"""Vượt mức này trên lớp 20.000 tường thì ghi Nợ B3-06 — test chỉ in số, không khẳng định."""

_log = logging.getLogger(__name__)


def _wall_grid(level_id: str, count: int) -> SpatialLayer:
    """Lớp AI chỉ gồm `count` tường thẳng đứng cách nhau 1 m, mọi mục `source="ai"`, chưa duyệt.

    Dựng thẳng bằng `Wall(...)` thay vì `build_layer`: cần cỡ dữ liệu của B5-05 mà không phải trả
    giá suy luận hình học của nó (mục tiêu là đo thời gian **giữ khoá**, không đo bước dựng).
    """
    prefix = SPATIAL_PREFIX["wall"]
    return SpatialLayer(
        walls=tuple(
            Wall(
                id=f"{prefix}-AI{index:08d}",
                level_id=level_id,
                centreline=Segment(start=Point(x=index * 1000, y=0), end=Point(x=index * 1000, y=3000)),
                thickness_mm=100,
                height_mm=3000,
                kind="partition",
                opening_ids=(),
                confidence=0.9,
                source="ai",
                reviewed=False,
            )
            for index in range(count)
        ),
        openings=(),
        rooms=(),
        furniture=(),
    )


def _built(layer: SpatialLayer) -> BuiltLayer:
    """`BuiltLayer` quanh một lớp dựng tay; `dropped` đủ `DROPPED_KEYS` như `build_layer` trả."""
    return BuiltLayer(
        layer=layer,
        dimensions=(),
        scale_mm_per_px=Decimal("12"),
        scale_source="pipeline",
        dropped=dict.fromkeys(DROPPED_KEYS, 0),
    )


async def _arrange(
    maker: Maker,
    storage: LocalDiskStorage,
    clock: FakeClock,
    make_built: Callable[[str], BuiltLayer] | None = None,
) -> Arranged:
    """Lượt ở `spatialDataBuild`, tầng **đã có** dòng `floor_documents`, `layer.json` đã mồi.

    Tài liệu dựng trước bằng `make_floor_document` để bên chờ khoá gặp một dòng đã commit mà chờ
    `FOR UPDATE` trên đó — chờ một dòng người khác vừa chèn chưa commit là ca khác (chờ khoá index),
    không phải ca [8] muốn kiểm.
    """
    arranged = await open_run_at_build(maker, clock)
    async with maker() as db:
        await make_floor_document(db, floor_pk=arranged.floor_pk, clock=clock)
        await db.commit()
    build = make_built if make_built is not None else (lambda level: _built(sample_built(level).layer))
    await put_layer(storage, arranged, build(arranged.level_id).to_json())
    return arranged


async def _timed_hold(
    maker: Maker,
    storage: LocalDiskStorage,
    clock: FakeClock,
    payload: RunStepPayload,
    monkeypatch: pytest.MonkeyPatch,
) -> float:
    """Chạy lõi với `service.lock_run` bọc đo mốc và trả số giây khoá `floors` được giữ.

    Mốc `t0` lấy **sau** khi `lock_run` trả (khoá đã nằm trong tay giao dịch) và mốc cuối là lúc lõi
    trả — tức lúc giao dịch đã commit, nên khoảng giữa đúng bằng thời gian giữ khoá.
    """
    marks: list[float] = []

    async def timed(db: AsyncSession, *, run_id: str) -> RunRow | None:
        """Vỏ đo: gọi `lock_run` thật rồi ghi mốc; lượt trả `None` không có khoá nào để đo."""
        row = await lock_run(db, run_id=run_id)
        if row is not None:
            marks.append(time.monotonic())
        return row

    monkeypatch.setattr(service, "lock_run", timed)
    assert await service.run_persist(payload, sessionmaker=maker, storage=storage, clock=clock) == "persisted"
    assert len(marks) == 1
    return time.monotonic() - marks[0]


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_persist_lock_blocks_concurrent_version(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lõi dừng giữa bước 5 và 6 → `create_version` của session khác chờ, thả ra thì xong.

    Chặn ở lượt gọi `create_version` **thứ hai** (bước 6) vì lúc đó `write_layer` của bước 5 đã khoá
    xong dòng tài liệu: đúng cửa sổ mà [8] muốn kiểm. Bên chờ dùng `create_version` thật trên một
    session riêng của cùng pool — nó phải chưa xong sau `BLOCKED_PROBE_S`, rồi xong sau khi thả mà
    không ném `LockNotAvailable` của `DB_LOCK_TIMEOUT_MS`.
    """
    arranged = await _arrange(db_sessionmaker, local_storage, fake_clock)
    gate, at_step_six = asyncio.Event(), asyncio.Event()
    calls = 0

    async def gated(db: AsyncSession, **kwargs: object) -> VersionRow:
        """Vỏ chặn: lượt thứ hai báo `at_step_six` rồi chờ `gate` trước khi chụp phiên bản thật."""
        nonlocal calls
        calls += 1
        if calls == 2:
            at_step_six.set()
            await gate.wait()
        return await create_version(db, **kwargs)  # type: ignore[arg-type]  # vỏ trong suốt: kwargs của người gọi

    monkeypatch.setattr(service, "create_version", gated)

    async def other_writer() -> float:
        """`create_version` của một session khác trên cùng tầng; trả số giây nó phải chờ."""
        start = time.monotonic()
        async with db_sessionmaker() as db:
            await create_version(
                db,
                floor_pk=arranged.floor_pk,
                actor_id=arranged.uploader_id,
                actor_name="người ghi song song",
                note=None,
                clock=fake_clock,
            )
            await db.commit()
        return time.monotonic() - start

    core = asyncio.create_task(
        service.run_persist(arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    )
    waiter: asyncio.Task[float] | None = None
    try:
        await asyncio.wait_for(at_step_six.wait(), WAIT_S)
        waiter = asyncio.create_task(other_writer())
        await asyncio.sleep(BLOCKED_PROBE_S)
        assert not waiter.done(), "người ghi cùng tầng không chờ khoá của lõi"
        await asyncio.sleep(RELEASE_AFTER_S - BLOCKED_PROBE_S)
        gate.set()
        assert await asyncio.wait_for(core, WAIT_S) == "persisted"
        blocked_s = await asyncio.wait_for(waiter, WAIT_S)
        _log.info("lock_waiter_blocked_s=%.3f", blocked_s)
    finally:
        gate.set()  # không để lõi treo ở teardown khi một khẳng định trên đỏ
        for task in (core, waiter):
            if task is not None:
                task.cancel()


@pytest.mark.perf
@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_persist_lock_hold_sample_building(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lớp toà mẫu: giữ khoá `floors` dưới 1 s (trần của prompt [8]); số đo in bằng `logging`."""
    arranged = await _arrange(db_sessionmaker, local_storage, fake_clock)

    held_s = await _timed_hold(db_sessionmaker, local_storage, fake_clock, arranged.payload, monkeypatch)

    _log.info("lock_hold_sample_building_s=%.3f", held_s)
    assert held_s < SAMPLE_HOLD_CEILING_S


@pytest.mark.perf
@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_persist_lock_hold_20k_walls(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lớp 20.000 tường: chỉ **in** thời gian giữ khoá, không khẳng định trần (báo cáo [11] mục 4).

    Prompt không đặt trần cho cỡ này; vượt `BIG_HOLD_DEBT_S` là việc của B3-06 (`merge_pipeline_result`)
    nên ghi Nợ thay vì làm test đỏ — test đỏ ở đây chỉ nói lên phần cứng của máy chạy cổng.
    """
    arranged = await _arrange(
        db_sessionmaker, local_storage, fake_clock, lambda level: _built(_wall_grid(level, BIG_WALLS))
    )

    held_s = await _timed_hold(db_sessionmaker, local_storage, fake_clock, arranged.payload, monkeypatch)

    _log.info("lock_hold_20k_walls_s=%.3f no_debt=%s", held_s, held_s <= BIG_HOLD_DEBT_S)
