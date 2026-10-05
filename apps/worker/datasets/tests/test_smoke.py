"""Test khói của task và hai lịch: chạy đúng đường thật của tiến trình worker (BE-00 §7).

Khác `test_tasks.py`/`test_jobs.py` — nơi tài nguyên do test truyền vào — ở đây hàm được gọi
**không tham số**, đúng như beat và worker gọi nó: `SystemClock`, `worker_sessionmaker()`,
`open_storage()` và `runner()` thật. `process_env` chỉ trỏ biến môi trường của tiến trình sang DB
test và kho trong `tmp_path`, nên vẫn là Postgres, Redis, kho thật (K23).
"""

import asyncio
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import DATASET_EMPTY
from apps.api.admin_ml_datasets.settings import reset_ml_datasets_settings_cache
from apps.worker.datasets.jobs import purge_dataset_orphans, sweep_dataset_version_builds
from apps.worker.datasets.tasks import version_prefix
from apps.worker.datasets.tests._helpers import open_building_version
from packages.core.ids import new_id
from packages.core.settings import reset_settings_cache
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.settings import get_database_settings, reset_database_settings_cache
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.storage.keys import dataset_object, dataset_version_prefix
from packages.storage.local import LocalDiskStorage
from packages.storage.settings import reset_storage_settings_cache
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

DEFAULT_QUEUE = "default"
STALLED_AGO = timedelta(minutes=30)
OLD_HOURS = 48


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Broker thật với hàng `default` rỗng ở đầu và cuối test."""
    client = broker_redis_sync()
    client.delete(DEFAULT_QUEUE)
    try:
        yield client
    finally:
        client.delete(DEFAULT_QUEUE)
        client.close()


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của tiến trình worker: DB test riêng, kho local cùng gốc với `local_storage`."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://appback.test")
    monkeypatch.setenv("SECRET_KEY", "fixture-secret-for-ml-datasets-jobs-01")
    caches = (
        reset_settings_cache,
        reset_database_settings_cache,
        reset_storage_settings_cache,
        reset_ml_datasets_settings_cache,
    )
    for reset in caches:
        reset()
    yield
    for reset in caches:
        reset()


def _process_maker() -> async_sessionmaker[AsyncSession]:
    """Sessionmaker trên DB mà biến môi trường của tiến trình đang trỏ tới."""
    return create_sessionmaker(create_engine(get_database_settings()))


async def _seed_building(*, stalled: bool) -> str:
    """Một bản `building` trong DB của tiến trình; `stalled` đẩy `updated_at` về quá hạn gửi lại."""
    maker = _process_maker()
    engine = maker.kw["bind"]
    try:
        clock = FakeClock(datetime.now(UTC))
        version_id = await open_building_version(maker, clock)
        if stalled:
            async with maker() as db:
                row = await db.get(DatasetVersionRow, version_id)
                assert row is not None
                row.updated_at = clock.now() - STALLED_AGO
                await db.commit()
        return version_id
    finally:
        await engine.dispose()


async def _read_status(version_id: str) -> tuple[str, str | None]:
    """`(status, failure_code)` đọc lại từ DB của tiến trình."""
    maker = _process_maker()
    engine = maker.kw["bind"]
    try:
        async with maker() as db:
            stmt = select(DatasetVersionRow.status, DatasetVersionRow.failure_code).where(
                DatasetVersionRow.id == version_id
            )
            status, code = (await db.execute(stmt)).one()
            return str(status), None if code is None else str(code)
    finally:
        await engine.dispose()


def _age(root: Path, key: str, *, hours: int) -> None:
    """Đẩy `mtime` của một object lùi `hours` giờ — `older_than` của kho local đọc chính nó."""
    old = (datetime.now(UTC) - timedelta(hours=hours)).timestamp()
    os.utime(root / key, (old, old))


def _sent(client: SyncRedis) -> list[str]:
    """`dataset_version_id` của mọi thông điệp đang nằm trên hàng `default`."""
    return [str(payload["dataset_version_id"]) for payload in queued_payloads(client, DEFAULT_QUEUE)]


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_sweep_dataset_version_builds_smoke(broker: SyncRedis) -> None:
    """Hàm lịch thật gửi lại một bản `building` quá hạn."""
    version_id = asyncio.run(_seed_building(stalled=True))

    sweep_dataset_version_builds()
    reset_database_settings_cache()

    assert _sent(broker) == [version_id]


@pytest.mark.usefixtures("process_env")
def test_purge_dataset_orphans_smoke(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Hàm lịch thật mở kho của tiến trình và xoá tiền tố mồ côi cũ."""
    version_id = new_id("dsv", FakeClock(datetime.now(UTC)))
    key = dataset_object(version_id, "manifest.jsonl")
    asyncio.run(local_storage.put(key, b"{}\n", content_type="application/x-ndjson", max_bytes=16))
    _age(tmp_path / "objects", key, hours=OLD_HOURS)

    purge_dataset_orphans()
    reset_database_settings_cache()

    assert not (tmp_path / "objects" / version_prefix(version_id)).exists()


@pytest.mark.usefixtures("process_env")
def test_build_dataset_version_smoke(celery_test_app: object, broker: SyncRedis) -> None:
    """Task thật: không tầng nào đạt → `DATASET_EMPTY`, và `on_failed` chốt `failed` trên cùng vòng sự kiện.

    Đây là ca duy nhất đi qua `build_dataset_version` → `open_storage` → `_on_build_failed` →
    `runner()` đúng như worker chạy; mọi test khác gọi lõi với tài nguyên của test.
    """
    version_id = asyncio.run(_seed_building(stalled=False))

    result = celery_test_app.tasks[BUILD_VERSION_TASK].apply(  # type: ignore[attr-defined]  # `tasks` là mapping động
        args=({"schema_version": 1, "dataset_version_id": version_id},)
    )
    reset_database_settings_cache()

    assert result.successful()
    assert asyncio.run(_read_status(version_id)) == ("failed", DATASET_EMPTY)


def test_version_prefix__follows_storage_keys() -> None:
    """NO-263: tiền tố phiên bản là `keys.dataset_version_prefix` (kiểm `dsv_`), không f-string chép bố cục."""
    version_id = "dsv_01ARZ3NDEKTSV4RRFFQ69G5FHB"
    assert version_prefix(version_id) == dataset_version_prefix(version_id)
    with pytest.raises(ValueError, match="dsv_"):
        version_prefix("khong-phai-dsv")
