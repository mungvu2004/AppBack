"""K36: `run_persist` không giữ kết nối CSDL nào trong lúc đọc `layer.json` (B5-06b [8] "K36").

Bằng chứng đòi một pool **một** kết nối: `DB_POOL_SIZE=1`, `DB_MAX_OVERFLOW=0`,
`DB_POOL_TIMEOUT_S=1`. Kho bọc dừng ngay trước khúc đầu của `open_read`; lúc đó
`engine.pool.checkedout()` phải là 0 — lõi đã đóng session của bước 1 trước khi chạm kho. Bọc chứ
không mock (K23): lớp bọc kế thừa chính `local_storage` thật và chỉ chèn một `asyncio.Event`.

Không có trần đồng hồ tường nào là điều kiện đúng/sai ở đây, nên test không mang marker `perf`;
`WAIT_S` chỉ để một lõi treo thành test đỏ chứ không phải treo cổng.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Final, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from apps.worker.pipeline_persist import service
from apps.worker.pipeline_persist.tests.helpers import open_run_at_build, put_layer, sample_built
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE
from packages.testing.fixtures.clock import FakeClock

type Maker = async_sessionmaker[AsyncSession]

WAIT_S: Final = 30.0
"""Trần **chờ** chống treo cho cả hai chặng của test (mở kho, lõi trả) — không phải trần hiệu năng."""

_log = logging.getLogger(__name__)


class _GatedRead(LocalDiskStorage):
    """Kho đĩa thật, `open_read` báo `opened` rồi chờ `released` trước khi nhả khúc đầu tiên.

    Mượn nguyên cấu hình của kho gốc (khuôn `_FlakyPut` của B5-06a) để không dựng kho thứ hai —
    dữ liệu test mồi vào đâu thì đọc ra từ đó.
    """

    def __init__(self, base: LocalDiskStorage, *, opened: asyncio.Event, released: asyncio.Event) -> None:
        """Chép cấu hình của `base`; hai `Event` thuộc vòng sự kiện của test đang chạy."""
        self.__dict__.update(base.__dict__)
        self._opened = opened
        self._released = released

    async def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Dừng ở ngưỡng cửa: test kiểm pool xong mới thả cho đọc thật."""
        self._opened.set()
        await self._released.wait()
        async for chunk in super().open_read(key, chunk_size=chunk_size):
            yield chunk


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_persist_holds_no_session_while_reading_storage(
    db_url: str, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Pool một kết nối: lúc `open_read` đang chờ, `checkedout() == 0`; thả ra → `persisted`.

    Pool một kết nối là phần **chứng minh**: nếu lõi còn giữ session của bước 1 thì `checkedout()`
    là 1, và chính lượt `session_scope` của bước 3 sau đó cũng sẽ chết vì `db_pool_timeout_s=1` —
    hai dấu hiệu cho cùng một lỗi. `messaging_env` vì bước 10 gửi `pipeline.quality.run` qua broker
    thật sau commit.
    """
    settings = DatabaseSettings(database_url=db_url, db_pool_size=1, db_max_overflow=0, db_pool_timeout_s=1)
    engine = create_engine(settings)
    maker = create_sessionmaker(engine)
    try:
        arranged = await open_run_at_build(maker, fake_clock)
        await put_layer(local_storage, arranged, sample_built(arranged.level_id).to_json())
        opened, released = asyncio.Event(), asyncio.Event()
        gated = _GatedRead(local_storage, opened=opened, released=released)

        core = asyncio.create_task(
            service.run_persist(arranged.payload, sessionmaker=maker, storage=gated, clock=fake_clock)
        )
        try:
            await asyncio.wait_for(opened.wait(), WAIT_S)
            # `AsyncEngine.pool` khai kiểu `Pool` cơ sở; `create_engine` luôn cho `QueuePool` (pool_size/overflow).
            checked_out = cast("QueuePool", engine.pool).checkedout()
            _log.info("k36_checkedout_while_reading=%d", checked_out)
            assert checked_out == 0
            released.set()
            assert await asyncio.wait_for(core, WAIT_S) == "persisted"
        finally:
            released.set()  # lõi không bao giờ treo ở teardown, kể cả khi khẳng định trên đỏ
            core.cancel()
    finally:
        await engine.dispose()
