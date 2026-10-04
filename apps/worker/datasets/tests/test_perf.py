"""Hiệu năng và K36 của task dựng dataset (B6-02 [8] "K36, hiệu năng").

Hai điều phải **đo**, không suy luận: 20 tầng trang 4.000 x 3.000 xong dưới 20 s trong container
verify, và không kết nối DB nào bị giữ trong lúc `put` đang chờ. Cái thứ hai đo bằng cách chặn
một lượt `put` lại rồi đọc `pool.checkedout()` của chính engine test — pool chỉ có 5 kết nối nên
giữ session qua lượt ghi kho sẽ treo cả lượt dựng chứ không chỉ làm nó chậm.

**Chỉ test có trần thời gian gắn `perf`** (BE-00 §12, 2026-09-29): từ FIX-112 bước 5 chạy
`pytest-xdist -n 6`, mỗi tiến trình chỉ còn ~1/6 CPU nên trần đồng hồ tường đo tuần tự không còn giữ
được — `elapsed < BUDGET_S` thuộc bước 5b (tuần tự, không coverage), số đo in bằng `logging`. Test K22/K36
(`checkedout() == 0`) chỉ chờ rộng `BLOCK_WAIT_S` chứ không khẳng định cận trên nên ở lại bước 5.

Độ phủ **không** dựa vào file này: mọi dòng của `tasks.py`/`jobs.py` mà hai test đây đi qua đều là
đường dựng bình thường, đã có test không-`perf` trong `test_tasks.py`/`test_jobs.py` gánh ở bước 5.
"""

import asyncio
import logging
import time

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from apps.worker.datasets.tasks import run_build_dataset_version
from apps.worker.datasets.tests._helpers import (
    AtPutStorage,
    approved_floor,
    make_scene,
    open_building_version,
    read_version,
)
from packages.messaging.redis import AsyncRedis
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import png_bytes
from packages.testing.fixtures.clock import FakeClock

_log = logging.getLogger(__name__)

Maker = async_sessionmaker[AsyncSession]

PAGE_WIDTH = 4000
PAGE_HEIGHT = 3000
FLOOR_COUNT = 20
BUDGET_S = 20.0
"""Trần [8]; đo **chỉ** lượt task, sau một lượt khởi động (nạp cv2, mở pool, nén lần đầu)."""

BLOCK_WAIT_S = 30.0


def _engine_of(maker: Maker) -> AsyncEngine:
    """Engine mà sessionmaker của test đang dùng — để đọc số kết nối đang bị giữ."""
    bind = maker.kw["bind"]
    assert isinstance(bind, AsyncEngine)
    return bind


@pytest.mark.perf
async def test_build_dataset_version__perf_twenty_large_pages(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """20 tầng trang 4.000 x 3.000 → một lượt dựng dưới `BUDGET_S` (dựng dữ liệu không tính).

    Chiều cao lệch một pixel mỗi tầng: `png_bytes` chỉ có IHDR nên hai trang cùng khổ trùng
    `sha256` và bị bỏ `duplicate_image` — ca đo cần đúng 20 mẫu được ghi thật.
    """
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        for index in range(FLOOR_COUNT):
            await approved_floor(db, local_storage, scene, fake_clock, page=png_bytes(PAGE_WIDTH, PAGE_HEIGHT + index))
        await db.commit()

    warm_up = await open_building_version(db_sessionmaker, fake_clock)
    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=warm_up)

    measured = await open_building_version(db_sessionmaker, fake_clock)
    started = time.monotonic()
    await run_build_dataset_version(db_sessionmaker, local_storage, fake_clock, version_id=measured)
    elapsed = time.monotonic() - started

    _log.info("build_dataset_version_elapsed_s=%.2f floors=%d", elapsed, FLOOR_COUNT)
    row = await read_version(db_sessionmaker, measured)
    assert sum((row.split_counts or {}).values()) == FLOOR_COUNT
    assert elapsed < BUDGET_S, f"lượt dựng {FLOOR_COUNT} tầng mất {elapsed:.1f}s, trần {BUDGET_S}s"


async def test_build_dataset_version__holds_no_connection_while_putting(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, safe_client: AsyncRedis
) -> None:
    """`put` đang bị chặn → `pool.checkedout() == 0`: không session nào bị giữ qua lượt ghi kho (K22, K36)."""
    async with db_sessionmaker() as db:
        scene = await make_scene(db)
        await approved_floor(db, local_storage, scene, fake_clock)
        await db.commit()
    version_id = await open_building_version(db_sessionmaker, fake_clock)
    entered, release = asyncio.Event(), asyncio.Event()

    async def block() -> None:
        """Báo test là lượt `put` đã bắt đầu, rồi đứng chờ ở đúng chỗ đó."""
        entered.set()
        await release.wait()

    blocking = AtPutStorage(local_storage, at_put=1, hook=block)
    pool = _engine_of(db_sessionmaker).pool
    assert isinstance(pool, QueuePool)

    build = asyncio.create_task(run_build_dataset_version(db_sessionmaker, blocking, fake_clock, version_id=version_id))
    try:
        await asyncio.wait_for(entered.wait(), timeout=BLOCK_WAIT_S)
        assert pool.checkedout() == 0
    finally:
        release.set()
        await build

    assert pool.checkedout() == 0
    assert (await read_version(db_sessionmaker, version_id)).status == "ready"
