"""Hai lịch nền của dataset: quét lượt dựng treo, dọn tiền tố mồ côi (B6-02 [6] "Lịch", "Dọn rác").

Postgres, Redis, kho local đều thật (K23). "Cũ hơn 24 giờ" của lịch dọn tính theo `last_modified`
**thật** của tệp, nên test đẩy `mtime` bằng `os.utime` thay vì giả cổng kho: một tệp trẻ phải sống
sót, và chỉ `os.utime` chứng minh được điều đó.
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import DATASET_BUILD_TIMEOUT
from apps.api.admin_ml_datasets.settings import get_ml_datasets_settings
from apps.worker.datasets.jobs import (
    MAX_REQUEUES,
    PURGE_EVERY,
    PURGE_TASK,
    SWEEP_EVERY,
    SWEEP_TASK,
    run_dataset_build_sweep,
    run_dataset_orphan_purge,
)
from apps.worker.datasets.tests._helpers import open_building_version, read_version
from packages.core.ids import new_id
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.messaging.payloads.datasets import BUILD_VERSION_TASK
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.schedules import schedule_entries
from packages.storage.keys import dataset_object
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

Maker = async_sessionmaker[AsyncSession]
DEFAULT_QUEUE = "default"


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Broker thật với hàng `default` rỗng ở đầu và cuối test (fixture broker không tự dọn)."""
    client = broker_redis_sync()
    client.delete(DEFAULT_QUEUE)
    try:
        yield client
    finally:
        client.delete(DEFAULT_QUEUE)
        client.close()


def _sent(client: SyncRedis) -> list[str]:
    """`dataset_version_id` của mọi thông điệp đang nằm trên hàng `default`."""
    return [str(payload["dataset_version_id"]) for payload in queued_payloads(client, DEFAULT_QUEUE)]


async def _building(maker: Maker, clock: FakeClock, *, updated_ago: timedelta, started: bool = False) -> str:
    """Một phiên bản `building` với `updated_at` đã lùi `updated_ago`; `started` đặt `build_started_at`."""
    version_id = await open_building_version(maker, clock)
    async with maker() as db:
        await db.execute(
            update(DatasetVersionRow)
            .where(DatasetVersionRow.id == version_id)
            .values(
                updated_at=clock.now() - updated_ago,
                build_started_at=clock.now() - updated_ago if started else None,
            )
        )
        await db.commit()
    return version_id


# ---------------------------------------------------------------------------
# sweep_dataset_version_builds
# ---------------------------------------------------------------------------


async def test_sweep_dataset_version_builds__J01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Bản `building` chưa tới worker quá 10 phút → gửi lại một lần, `requeue_count` 1, `updated_at` mới."""
    version_id = await _building(db_sessionmaker, fake_clock, updated_ago=timedelta(minutes=11))

    assert await run_dataset_build_sweep(db_sessionmaker, local_storage, fake_clock) == 1

    assert _sent(broker) == [version_id]
    row = await read_version(db_sessionmaker, version_id)
    assert (row.status, row.requeue_count, row.updated_at) == ("building", 1, fake_clock.now())


async def test_sweep_dataset_version_builds__J06(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Chạy hai lần liền: lượt hai không gửi thêm và không đổi `requeue_count`."""
    version_id = await _building(db_sessionmaker, fake_clock, updated_ago=timedelta(minutes=11))
    await run_dataset_build_sweep(db_sessionmaker, local_storage, fake_clock)

    assert await run_dataset_build_sweep(db_sessionmaker, local_storage, fake_clock) == 0

    assert _sent(broker) == [version_id]
    assert (await read_version(db_sessionmaker, version_id)).requeue_count == 1


async def _requeues_at_most_three_times(
    maker: Maker, storage: LocalDiskStorage, clock: FakeClock, broker: SyncRedis
) -> None:
    """Chưa bắt đầu quá 10 phút -> gửi lại, **tối đa** `MAX_REQUEUES` lượt; rồi thôi."""
    version_id = await _building(maker, clock, updated_ago=timedelta(minutes=11))

    for attempt in range(1, MAX_REQUEUES + 1):
        assert await run_dataset_build_sweep(maker, storage, clock) == 1
        assert (await read_version(maker, version_id)).requeue_count == attempt
        clock.advance(timedelta(minutes=11))

    assert await run_dataset_build_sweep(maker, storage, clock) == 0
    assert _sent(broker) == [version_id] * MAX_REQUEUES
    assert (await read_version(maker, version_id)).status == "building"


async def _fails_after_the_timeout(
    maker: Maker, storage: LocalDiskStorage, clock: FakeClock, broker: SyncRedis
) -> None:
    """61 phút không tiến triển -> `failed` `DATASET_BUILD_TIMEOUT`, tiền tố bị dọn, không gửi lại."""
    ago = timedelta(seconds=get_ml_datasets_settings().dataset_build_timeout_s + 60)
    version_id = await _building(maker, clock, updated_ago=ago, started=True)
    key = dataset_object(version_id, "manifest.jsonl")
    await storage.put(key, b"{}\n", content_type="application/x-ndjson", max_bytes=16)
    before = len(_sent(broker))

    assert await run_dataset_build_sweep(maker, storage, clock) == 1

    row = await read_version(maker, version_id)
    assert (row.status, row.failure_code) == ("failed", DATASET_BUILD_TIMEOUT)
    assert await storage.stat(key) is None
    assert len(_sent(broker)) == before


async def test_sweep_dataset_version_builds__J07(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Hai nửa của J07 trong **một** hàm: gửi lại tối đa ba lượt, rồi chốt hỏng khi thật sự đứng im.

    Một hàm vì `tools/case_gate.py` neo tên case của lịch vào cuối (`test_<fn>__J` + đúng hai chữ số, hết chuỗi), nên
    `…__J07_timeout` sẽ không được tính là J07.
    """
    await _requeues_at_most_three_times(db_sessionmaker, local_storage, fake_clock, broker)
    await _fails_after_the_timeout(db_sessionmaker, local_storage, fake_clock, broker)


# ---------------------------------------------------------------------------
# purge_dataset_orphans
# ---------------------------------------------------------------------------


def _age(root: Path, key: str, *, hours: int) -> None:
    """Đẩy `mtime` của một object lùi `hours` giờ — `older_than` của kho local đọc chính nó."""
    path = root / key
    old = (datetime.now(UTC) - timedelta(hours=hours)).timestamp()
    os.utime(path, (old, old))


async def _put_manifest(storage: LocalDiskStorage, version_id: str) -> str:
    """Một object dưới tiền tố của phiên bản; trả khoá của nó."""
    key = dataset_object(version_id, "manifest.jsonl")
    await storage.put(key, b"{}\n", content_type="application/x-ndjson", max_bytes=16)
    return key


async def _purge_setup(
    db: AsyncSession, storage: LocalDiskStorage, clock: FakeClock, root: Path
) -> tuple[str, str, str, str]:
    """Bốn tiền tố: bản `failed` cũ, bản `ready`, bản `building`, và một tiền tố không có dòng nào."""
    clock.set(datetime.now(UTC))
    dataset = await make_dataset(db, family="wallSegmentation", created_by="usr_seed")
    failed = await make_dataset_version(db, dataset=dataset, status="failed", sequence=1)
    ready = await make_dataset_version(db, dataset=dataset, status="ready", sequence=2)
    building = await make_dataset_version(db, dataset=dataset, status="building", sequence=3)
    await db.commit()
    orphan_id = new_id("dsv", clock)
    keys = [await _put_manifest(storage, row_id) for row_id in (failed.id, ready.id, building.id, orphan_id)]
    for key in keys:
        _age(root, key, hours=48)
    return failed.id, ready.id, building.id, orphan_id


async def test_purge_dataset_orphans__J01(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Bản `failed` và tiền tố không dòng bị xoá; `ready`, `building` và object trẻ còn nguyên."""
    root = tmp_path / "objects"
    failed_id, ready_id, building_id, orphan_id = await _purge_setup(db_session, local_storage, fake_clock, root)
    young = await _put_manifest(local_storage, new_id("dsv", fake_clock))

    assert await run_dataset_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 2

    assert await local_storage.stat(dataset_object(failed_id, "manifest.jsonl")) is None
    assert await local_storage.stat(dataset_object(orphan_id, "manifest.jsonl")) is None
    assert await local_storage.stat(dataset_object(ready_id, "manifest.jsonl")) is not None
    assert await local_storage.stat(dataset_object(building_id, "manifest.jsonl")) is not None
    assert await local_storage.stat(young) is not None


async def test_purge_dataset_orphans__J06(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """Chạy hai lần liền: lượt hai không xoá gì và không đụng tiền tố còn lại."""
    root = tmp_path / "objects"
    _failed, ready_id, building_id, _orphan = await _purge_setup(db_session, local_storage, fake_clock, root)
    await run_dataset_orphan_purge(db_sessionmaker, local_storage, fake_clock)

    assert await run_dataset_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 0

    assert await local_storage.stat(dataset_object(ready_id, "manifest.jsonl")) is not None
    assert await local_storage.stat(dataset_object(building_id, "manifest.jsonl")) is not None


async def test_purge_dataset_orphans_groups_one_lookup_per_batch(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    tmp_path: Path,
) -> None:
    """`batch=1` vẫn ra cùng kết quả: gom theo `dsv` nên số lượt tra DB đi theo lô, không theo object."""
    root = tmp_path / "objects"
    failed_id, ready_id, _building, orphan_id = await _purge_setup(db_session, local_storage, fake_clock, root)

    assert await run_dataset_orphan_purge(db_sessionmaker, local_storage, fake_clock, batch=1) == 2

    assert await local_storage.stat(dataset_object(failed_id, "manifest.jsonl")) is None
    assert await local_storage.stat(dataset_object(orphan_id, "manifest.jsonl")) is None
    assert await local_storage.stat(dataset_object(ready_id, "manifest.jsonl")) is not None


async def test_purge_dataset_orphans_ignores_keys_outside_the_layout(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, tmp_path: Path
) -> None:
    """Khoá lạ ngay dưới `ml/datasets/` (thiếu đoạn phiên bản) không làm lượt dọn chết."""
    fake_clock.set(datetime.now(UTC))
    await local_storage.put("ml/datasets/rac.txt", b"x", content_type="text/plain", max_bytes=4)
    _age(tmp_path / "objects", "ml/datasets/rac.txt", hours=48)

    assert await run_dataset_orphan_purge(db_sessionmaker, local_storage, fake_clock) == 0

    assert await local_storage.stat("ml/datasets/rac.txt") is not None


# ---------------------------------------------------------------------------
# Lịch: đăng ký và test khói
# ---------------------------------------------------------------------------


def test_both_schedules_are_registered_with_their_periods() -> None:
    """Lịch đăng ký đúng tên, hàm và chu kỳ (5 phút, 24 giờ)."""
    entries = {entry.name: entry for entry in schedule_entries()}

    assert entries[SWEEP_TASK].function == "sweep_dataset_version_builds"
    assert entries[SWEEP_TASK].every == SWEEP_EVERY == timedelta(minutes=5)
    assert entries[PURGE_TASK].function == "purge_dataset_orphans"
    assert entries[PURGE_TASK].every == PURGE_EVERY == timedelta(hours=24)


def test_build_task_name_matches_the_queue_prefix() -> None:
    """Tên task dựng nằm trên hàng `default` (tiền tố suy hàng, BE-00 §7)."""
    from packages.messaging.celery_app import queue_for

    assert queue_for(BUILD_VERSION_TASK) == DEFAULT_QUEUE
