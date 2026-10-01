"""Luật ngưỡng/giới hạn của `run_pipeline_artifact_purge` (B5-06c [8] việc C, không phải case J).

Dùng chung `build_scene` của `test_purge_cases` — một cảnh, khác `status`/`age` mỗi test.
"""

import asyncio
import logging
from datetime import timedelta
from typing import cast

import pytest
from sqlalchemy.pool import QueuePool

from apps.worker.pipeline_steps.purge import run_pipeline_artifact_purge
from apps.worker.pipeline_steps.tests.helpers import RETENTION_S, Maker, build_scene
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock

_log = logging.getLogger(__name__)

WAIT_S = 30.0
"""Trần chờ chống treo của test K36 — không phải trần hiệu năng (không mang marker `perf`)."""


async def _still_has_artifacts(storage: LocalDiskStorage, prefix: str) -> bool:
    """`True` nếu còn ít nhất một object dưới `prefix` — tiện khẳng định "chưa dọn"."""
    async for _ in storage.list_prefix(prefix):
        return True
    return False


@pytest.mark.asyncio(loop_scope="function")
async def test_completed_run_under_retention_is_kept(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt `completed` mới 6 ngày (< 7 ngày hạn giữ): `runs/` còn nguyên, chưa đánh dấu dọn."""
    scene = await build_scene(db_sessionmaker, local_storage, fake_clock, status="completed", age=timedelta(days=6))

    await run_pipeline_artifact_purge(db_sessionmaker, local_storage, fake_clock, batch=100)

    assert await _still_has_artifacts(local_storage, scene.run_prefix)


@pytest.mark.asyncio(loop_scope="function")
async def test_running_run_old_is_kept(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt còn `running` dù đã 8 ngày: chưa kết thúc nên không dọn (chỉ `completed|failed`)."""
    scene = await build_scene(
        db_sessionmaker, local_storage, fake_clock, status="running", age=timedelta(seconds=RETENTION_S + 86400)
    )

    await run_pipeline_artifact_purge(db_sessionmaker, local_storage, fake_clock, batch=100)

    assert await _still_has_artifacts(local_storage, scene.run_prefix)


@pytest.mark.asyncio(loop_scope="function")
async def test_failed_run_over_retention_is_purged(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt `failed` quá hạn giữ cũng bị dọn, không chỉ `completed`."""
    scene = await build_scene(
        db_sessionmaker, local_storage, fake_clock, status="failed", age=timedelta(seconds=RETENTION_S + 86400)
    )

    await run_pipeline_artifact_purge(db_sessionmaker, local_storage, fake_clock, batch=100)

    assert not await _still_has_artifacts(local_storage, scene.run_prefix)


@pytest.mark.asyncio(loop_scope="function")
async def test_batch_limits_rows_purged_per_call(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """`batch=2` trên ba lượt đến hạn: chỉ hai bị dọn trong một lượt gọi."""
    scenes = [
        await build_scene(
            db_sessionmaker, local_storage, fake_clock, status="completed", age=timedelta(seconds=RETENTION_S + 86400)
        )
        for _ in range(3)
    ]

    await run_pipeline_artifact_purge(db_sessionmaker, local_storage, fake_clock, batch=2)

    purged = [not await _still_has_artifacts(local_storage, scene.run_prefix) for scene in scenes]
    assert sum(purged) == 2


class _GatedDelete(LocalDiskStorage):
    """Kho đĩa thật, `delete_prefix` báo `opened` rồi chờ `released` (khuôn `_GatedRead`, B5-06b K36)."""

    def __init__(self, base: LocalDiskStorage, *, opened: asyncio.Event, released: asyncio.Event) -> None:
        """Chép cấu hình của `base` — không dựng kho thứ hai."""
        self.__dict__.update(base.__dict__)
        self._opened = opened
        self._released = released

    async def delete_prefix(self, prefix: str) -> None:
        """Dừng ở ngưỡng cửa: test kiểm pool xong mới cho xoá thật."""
        self._opened.set()
        await self._released.wait()
        await super().delete_prefix(prefix)


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_prefix_holds_no_db_connection(
    db_url: str, db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """K36: lúc `delete_prefix` đang chờ, pool một kết nối có `checkedout() == 0` (session đã đóng).

    Pool `DB_POOL_SIZE=1` là bằng chứng: nếu lõi còn giữ session trong lúc gọi kho thì
    `checkedout()` là 1, và chính câu `UPDATE … mark_artifacts_purged` sau đó sẽ treo đến khi
    `db_pool_timeout_s` hết hạn (một lỗi, hai dấu hiệu).
    """
    scene = await build_scene(
        db_sessionmaker, local_storage, fake_clock, status="completed", age=timedelta(seconds=RETENTION_S + 86400)
    )
    settings = DatabaseSettings(database_url=db_url, db_pool_size=1, db_max_overflow=0, db_pool_timeout_s=1)
    engine = create_engine(settings)
    try:
        maker = create_sessionmaker(engine)
        opened, released = asyncio.Event(), asyncio.Event()
        gated = _GatedDelete(local_storage, opened=opened, released=released)

        core = asyncio.create_task(run_pipeline_artifact_purge(maker, gated, fake_clock, batch=100))
        try:
            await asyncio.wait_for(opened.wait(), WAIT_S)
            checked_out = cast("QueuePool", engine.pool).checkedout()
            _log.info("k36_checkedout_while_deleting=%d", checked_out)
            assert checked_out == 0
            released.set()
            await asyncio.wait_for(core, WAIT_S)
        finally:
            released.set()
            core.cancel()
    finally:
        await engine.dispose()

    assert not await _still_has_artifacts(local_storage, scene.run_prefix)
