"""Case J01/J06 + khói lịch của `purge_pipeline_run_artifacts` (B5-06c [8] việc C).

Cảnh dùng chung: một lượt tải hoàn tất, một lượt chạy pipeline, một artifact dưới
`runs/{run}/`, một trang (`pages/0.png`) và tệp gốc — hai cái sau phải sống sót qua mọi
lượt dọn (chỉ `runs/` bị xoá).
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text

from apps.worker.pipeline_steps import jobs
from apps.worker.pipeline_steps.purge import run_pipeline_artifact_purge
from apps.worker.pipeline_steps.settings import reset_steps_settings_cache
from apps.worker.pipeline_steps.tests.helpers import RETENTION_S, Maker, Scene, build_scene
from packages.core.clock import Clock
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.settings import DatabaseSettings, reset_database_settings_cache
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures.clock import FakeClock


class _CountingDelete(LocalDiskStorage):
    """Kho đĩa thật, chỉ chèn thêm bộ đếm `delete_prefix` (J06: không gọi lần hai)."""

    def __init__(self, base: LocalDiskStorage) -> None:
        """Chép cấu hình của `base` — không dựng kho thứ hai (khuôn `_GatedRead`, B5-06b)."""
        self.__dict__.update(base.__dict__)
        self.calls = 0

    async def delete_prefix(self, prefix: str) -> None:
        """Đếm rồi uỷ lại cho kho thật."""
        self.calls += 1
        await super().delete_prefix(prefix)


@pytest.mark.asyncio(loop_scope="function")
async def test_purge_pipeline_run_artifacts__J01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Lượt `completed` 8 ngày: `runs/{run}/` mất, `pages/`/`original.*` còn, `artifacts_purged_at` có."""
    scene = await build_scene(
        db_sessionmaker, local_storage, fake_clock, status="completed", age=timedelta(seconds=RETENTION_S + 86400)
    )

    await run_pipeline_artifact_purge(db_sessionmaker, local_storage, fake_clock, batch=100)

    assert [info.key async for info in local_storage.list_prefix(scene.run_prefix)] == []
    assert await local_storage.stat(scene.page_key) is not None
    assert await local_storage.stat(scene.original_key) is not None
    async with db_sessionmaker() as db:
        purged_at = (
            await db.execute(
                text("SELECT artifacts_purged_at FROM pipeline_run_models WHERE run_id = :id"), {"id": scene.run_id}
            )
        ).scalar_one()
    assert purged_at is not None


@pytest.mark.asyncio(loop_scope="function")
async def test_purge_pipeline_run_artifacts__J06(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Chạy lại lượt dọn trên lượt đã dọn: không gọi `delete_prefix` lần hai (giao lặp)."""
    await build_scene(
        db_sessionmaker, local_storage, fake_clock, status="failed", age=timedelta(seconds=RETENTION_S + 86400)
    )
    counting = _CountingDelete(local_storage)

    await run_pipeline_artifact_purge(db_sessionmaker, counting, fake_clock, batch=100)
    assert counting.calls == 1
    await run_pipeline_artifact_purge(db_sessionmaker, counting, fake_clock, batch=100)
    assert counting.calls == 1


async def _seed_for_smoke(db_url: str, storage: LocalDiskStorage, clock: Clock) -> Scene:
    """Dựng cảnh trên một engine riêng, đóng lại trước khi hàm lịch thật mở engine của chính nó.

    Hàm lịch tự dựng `worker_sessionmaker()` trên vòng sự kiện riêng của nó (`run_maybe_async`/
    `Runner`); seed xong đóng hẳn engine này để không có `AsyncSession` nào sống sót sang vòng
    sự kiện khác (K36-kiểu, dù đây chỉ là seed, không phải lõi).
    """
    engine = create_engine(DatabaseSettings(database_url=db_url))
    try:
        maker = create_sessionmaker(engine)
        scene = await build_scene(maker, storage, clock, status="completed", age=timedelta(seconds=1))
        async with maker() as db:
            await db.execute(
                text("UPDATE pipeline_runs SET updated_at = :updated_at WHERE id = :run_id"),
                {"updated_at": datetime.now(UTC) - timedelta(seconds=RETENTION_S + 86400), "run_id": scene.run_id},
            )
            await db.commit()
        return scene
    finally:
        await engine.dispose()


def test_jobs_purge_pipeline_run_artifacts_smoke(
    db_url: str, local_storage: LocalDiskStorage, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Khói lịch nền: `jobs.purge_pipeline_run_artifacts()` gọi được, tự dựng tài nguyên từ env.

    Test **đồng bộ** (khuôn `admin_ml_registry/tests/test_jobs.py:test_purge_ml_model_orphans_smoke`):
    hàm lịch thật tự chạy `runner().run(...)` trên vòng sự kiện riêng của nó, lồng vào vòng của
    `pytest.mark.asyncio` sẽ ném "already running" — nên cảnh được dựng qua `asyncio.run` riêng,
    đóng xong mới gọi hàm lịch. Env trỏ đúng Postgres/kho (`DATABASE_URL`, `STORAGE_LOCAL_ROOT`
    cùng gốc `tmp_path/objects` của `local_storage`); `core_settings=None` trong `jobs._storage`
    nên kho local không đòi `PUBLIC_BASE_URL`.
    """
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    reset_storage_settings_cache()
    reset_database_settings_cache()
    reset_steps_settings_cache()
    try:
        scene = asyncio.run(_seed_for_smoke(db_url, local_storage, fake_clock))

        jobs.purge_pipeline_run_artifacts()

        assert not (tmp_path / "objects" / scene.run_artifact_key).exists()
    finally:
        reset_storage_settings_cache()
        reset_database_settings_cache()
        reset_steps_settings_cache()
