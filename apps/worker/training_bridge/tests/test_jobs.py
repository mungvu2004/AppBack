"""Ba lịch của job huấn luyện: mất nhịp tim, gửi lại hàng chờ, dọn artifact (B6-03a [6], [8] "Lịch").

Postgres, Redis (broker + `safe_redis`), kho local đều thật (K23). Mỗi test tự đặt/xoá
`claim_key` qua `safe_redis_sync()` trên hàng `SAFE_DB` — khác hàng broker `queued_payloads`
đọc, nên hai fixture `broker`/`safe_client` tách rời.
"""

import asyncio
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.redis import RedisContainer  # type: ignore[import-untyped] — gói không có stub kiểu

from apps.api.admin_ml_jobs.settings import get_training_settings
from apps.worker.training_bridge import jobs as jobs_module
from apps.worker.training_bridge.errors import TRAINING_DISPATCH_STALLED, TRAINING_HEARTBEAT_LOST
from apps.worker.training_bridge.jobs import (
    MAX_REQUEUE_ATTEMPTS,
    PURGE_EVERY,
    PURGE_TASK,
    REQUEUE_EVERY,
    REQUEUE_TASK,
    RUNNER_START_TASK,
    SWEEP_EVERY,
    SWEEP_TASK,
    purge_training_job_artifacts,
    requeue_training_jobs,
    run_purge_training_job_artifacts,
    run_requeue_training_jobs,
    run_sweep_lost_training_jobs,
    sweep_lost_training_jobs,
)
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.db.settings import reset_database_settings_cache
from packages.messaging.celery_app import queue_for
from packages.messaging.payloads.training import cancel_key, claim_key, trained_version_id
from packages.messaging.redis import SyncRedis, broker_redis_sync, safe_redis_sync
from packages.messaging.schedules import schedule_entries
from packages.messaging.settings import reset_messaging_settings_cache
from packages.storage.keys import model_artifact
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from apps.worker.training_bridge.tests._helpers import process_maker, worker_process_env
from packages.testing.factories.admin_ml_jobs import make_training_job
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads
from packages.testing.fixtures.services import ephemeral_redis

Maker = async_sessionmaker[AsyncSession]
TRAINING_QUEUE = "ml.training"
FAMILY = "wallSegmentation"
SEED_USER = "usr_seed"


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Broker thật với hàng `ml.training` rỗng ở đầu và cuối test."""
    client = broker_redis_sync()
    client.delete(TRAINING_QUEUE)
    try:
        yield client
    finally:
        client.delete(TRAINING_QUEUE)
        client.close()


@pytest.fixture
def safe_client(messaging_env: None) -> Iterator[SyncRedis]:
    """Client `safe_redis` đồng bộ để đặt/xoá `claim_key`, `cancel_key` trong test."""
    client = safe_redis_sync()
    try:
        yield client
    finally:
        client.close()


def _kill_redis(monkeypatch: pytest.MonkeyPatch) -> RedisContainer:
    """Trỏ `REDIS_BROKER_URL` sang một Redis `noeviction` riêng rồi dừng ngay — mọi lệnh sau đều lỗi kết nối.

    Gọi **giữa** một test (không phải fixture): fixture dựng xong trước khi thân test chạy,
    nên đổi `REDIS_BROKER_URL` qua fixture sẽ đè luôn `claim_key` đã đặt ở broker thật từ đầu
    test (khuôn `apps/api/notifications/tests/test_notify.py:199`, nhưng áp dụng muộn hơn).
    """
    container = ephemeral_redis("noeviction")
    url = f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    monkeypatch.setenv("REDIS_BROKER_URL", url)
    reset_messaging_settings_cache()
    container.stop()
    return container


def _sent(client: SyncRedis) -> list[str]:
    """`job_id` của mọi thông điệp đang nằm trên hàng `ml.training`."""
    return [str(payload["job_id"]) for payload in queued_payloads(client, TRAINING_QUEUE)]


async def _ready_dataset_version(db: AsyncSession) -> str:
    """Một dataset + phiên bản `ready` (có `manifest_sha256`) để job trỏ tới."""
    dataset = await make_dataset(db, family=FAMILY, created_by=SEED_USER)
    version = await make_dataset_version(db, dataset=dataset, status="ready", sequence=1)
    return version.id


async def _read_job(maker: Maker, job_id: str) -> TrainingJobRow:
    """Đọc lại một dòng job bằng session riêng (không dùng lại session đã ghi)."""
    async with maker() as db:
        stmt = select(TrainingJobRow).where(TrainingJobRow.id == job_id)
        return (await db.execute(stmt)).scalar_one()


def _cancel_key_set(client: SyncRedis, job_id: str) -> bool:
    """`cancel_key` của job đã được `arm_cancel_key` đặt."""
    return client.get(cancel_key(job_id)) is not None


# ---------------------------------------------------------------------------
# sweep_lost_training_jobs
# ---------------------------------------------------------------------------


async def test_sweep_lost_training_jobs__J01(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, safe_client: SyncRedis
) -> None:
    """Job `running` mất nhịp tim quá hạn, claim vắng → `failed` `TRAINING_HEARTBEAT_LOST`, `cancel_key` được đặt."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    timeout = get_training_settings().training_heartbeat_timeout_s
    stale = fake_clock.now() - timedelta(seconds=timeout + 60)
    job = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )

    assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 1

    row = await _read_job(db_sessionmaker, job.id)
    assert (row.status, row.failure_code, row.ended_at) == ("failed", TRAINING_HEARTBEAT_LOST, fake_clock.now())
    assert _cancel_key_set(safe_client, job.id)


async def test_sweep_lost_training_jobs__J06(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, safe_client: SyncRedis
) -> None:
    """Chạy hai lần liền: lượt hai không đổi gì."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    timeout = get_training_settings().training_heartbeat_timeout_s
    stale = fake_clock.now() - timedelta(seconds=timeout + 60)
    job = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )
    await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock)

    assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, job.id)).status == "failed"


async def test_sweep_lost_training_jobs__J07(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    fake_clock: FakeClock,
    safe_client: SyncRedis,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """J07: claim vắng → `cancelled`; claim còn → không đổi; Redis chết → không job nào đổi."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    timeout = get_training_settings().training_heartbeat_timeout_s
    stale = fake_clock.now() - timedelta(seconds=timeout + 60)
    lost = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="cancelling",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )
    claimed = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )
    safe_client.set(claim_key(claimed.id), "1")

    with caplog.at_level(logging.INFO, logger="apps.worker.training_bridge.jobs"):
        assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 1

    assert (await _read_job(db_sessionmaker, lost.id)).status == "cancelled"
    assert (await _read_job(db_sessionmaker, claimed.id)).status == "running"
    assert any(record.getMessage() == "training_heartbeat_late" for record in caplog.records)

    second_lost = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )
    _kill_redis(monkeypatch)
    with caplog.at_level(logging.WARNING, logger="apps.worker.training_bridge.jobs"):
        assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 0
    assert (await _read_job(db_sessionmaker, second_lost.id)).status == "running"
    assert any(record.getMessage() == "training_sweep_skipped" for record in caplog.records)


async def test_sweep_lost_training_jobs_rolls_back_one_job_when_arm_cancel_key_fails(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    messaging_env: None,
) -> None:
    """`arm_cancel_key` lỗi cho một job → chỉ job đó không đổi, lượt vẫn trả đúng số job còn lại đã chốt."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    timeout = get_training_settings().training_heartbeat_timeout_s
    stale = fake_clock.now() - timedelta(seconds=timeout + 60)
    broken = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )

    async def _broken_arm_cancel_key(job_id: str) -> None:
        """Giả Redis lỗi đúng lúc đặt `cancel_key` — khuôn `arm_cancel_key` thật, chỉ đổi phần ném lỗi."""
        raise RuntimeError("redis lỗi")

    monkeypatch.setattr("apps.worker.training_bridge.jobs.arm_cancel_key", _broken_arm_cancel_key)

    assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, broken.id)).status == "running"


async def test_sweep_lost_training_jobs_skips_a_row_another_beat_already_finished(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    messaging_env: None,
) -> None:
    """Giữa lúc đọc lô và lúc khoá dòng, một beat khác đã chốt job → `SELECT … FOR UPDATE` không khớp, bỏ (K18)."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    timeout = get_training_settings().training_heartbeat_timeout_s
    stale = fake_clock.now() - timedelta(seconds=timeout + 60)
    job = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="running",
        created_at=stale - timedelta(minutes=1),
        started_at=stale - timedelta(minutes=1),
        last_heartbeat_at=stale,
    )
    real_claims_present = jobs_module._claims_present  # noqa: SLF001 — mô phỏng beat khác chen vào giữa lượt

    async def _claims_present_then_race(job_ids: list[str]) -> dict[str, bool] | None:
        """`_claims_present` thật, nhưng đổi trạng thái của job ngay trước khi trả — giả một beat khác đã chốt nó."""
        async with db_sessionmaker() as db:
            await db.execute(update(TrainingJobRow).where(TrainingJobRow.id == job.id).values(status="cancelling"))
            await db.commit()
        return await real_claims_present(job_ids)

    monkeypatch.setattr(jobs_module, "_claims_present", _claims_present_then_race)

    assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, job.id)).status == "cancelling"


# ---------------------------------------------------------------------------
# requeue_training_jobs
# ---------------------------------------------------------------------------


async def test_requeue_training_jobs__J01(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, broker: SyncRedis, safe_client: SyncRedis
) -> None:
    """Claim có → không gửi; bảy lượt → sáu lần gửi rồi `TRAINING_DISPATCH_STALLED`, `cancel_key` được đặt."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    job = await make_training_job(db_session, dataset_version_id=dsv, status="queued", created_at=fake_clock.now())
    settings = get_training_settings()

    safe_client.set(claim_key(job.id), "1")
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s + 1))
    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0
    assert _sent(broker) == []
    safe_client.delete(claim_key(job.id))

    for attempt in range(1, MAX_REQUEUE_ATTEMPTS + 1):
        assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 1
        assert (await _read_job(db_sessionmaker, job.id)).requeue_count == attempt
        fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s * (2**attempt) + 1))

    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 1

    row = await _read_job(db_sessionmaker, job.id)
    assert (row.status, row.failure_code) == ("failed", TRAINING_DISPATCH_STALLED)
    assert _sent(broker) == [job.id] * MAX_REQUEUE_ATTEMPTS
    assert _cancel_key_set(safe_client, job.id)
    assert queue_for(RUNNER_START_TASK) == TRAINING_QUEUE


async def test_requeue_training_jobs__J06(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, broker: SyncRedis
) -> None:
    """Chạy hai lần liền: lượt hai không gửi thêm (vừa gửi lại nên chưa quá hạn mới)."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    job = await make_training_job(db_session, dataset_version_id=dsv, status="queued", created_at=fake_clock.now())
    settings = get_training_settings()
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s + 1))
    await run_requeue_training_jobs(db_sessionmaker, fake_clock)

    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0

    assert _sent(broker) == [job.id]
    assert (await _read_job(db_sessionmaker, job.id)).requeue_count == 1


async def test_requeue_training_jobs_skips_the_whole_batch_when_redis_is_down(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Redis chết trước khi đọc `claim_key` → không job nào đổi (bỏ cả lượt, giống sweep J07)."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    job = await make_training_job(db_session, dataset_version_id=dsv, status="queued", created_at=fake_clock.now())
    settings = get_training_settings()
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s + 1))
    _kill_redis(monkeypatch)

    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, job.id)).requeue_count == 0


async def test_requeue_training_jobs_rolls_back_when_arm_cancel_key_fails_at_the_stall(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    messaging_env: None,
) -> None:
    """`arm_cancel_key` lỗi lúc chốt `TRAINING_DISPATCH_STALLED` → job vẫn `queued`, không đổi."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    settings = get_training_settings()
    job = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="queued",
        created_at=fake_clock.now(),
        requeue_count=MAX_REQUEUE_ATTEMPTS,
    )
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s * (2**MAX_REQUEUE_ATTEMPTS) + 1))

    async def _broken_arm_cancel_key(job_id: str) -> None:
        """Giả Redis lỗi đúng lúc đặt `cancel_key` — khuôn `arm_cancel_key` thật, chỉ đổi phần ném lỗi."""
        raise RuntimeError("redis lỗi")

    monkeypatch.setattr("apps.worker.training_bridge.jobs.arm_cancel_key", _broken_arm_cancel_key)

    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, job.id)).status == "queued"


async def test_requeue_training_jobs_skips_a_row_another_beat_already_requeued(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    messaging_env: None,
) -> None:
    """Giữa lúc đọc lô và lúc khoá dòng, một beat khác đã gửi lại job → không đụng lần nữa (K18)."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    job = await make_training_job(db_session, dataset_version_id=dsv, status="queued", created_at=fake_clock.now())
    settings = get_training_settings()
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s + 1))
    real_claims_present = jobs_module._claims_present  # noqa: SLF001 — mô phỏng beat khác chen vào giữa lượt

    async def _claims_present_then_race(job_ids: list[str]) -> dict[str, bool] | None:
        """`_claims_present` thật, nhưng đổi trạng thái của job ngay trước khi trả — giả một beat khác đã gửi lại nó."""
        async with db_sessionmaker() as db:
            await db.execute(
                update(TrainingJobRow)
                .where(TrainingJobRow.id == job.id)
                .values(status="running", started_at=fake_clock.now())
            )
            await db.commit()
        return await real_claims_present(job_ids)

    monkeypatch.setattr(jobs_module, "_claims_present", _claims_present_then_race)

    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0

    assert (await _read_job(db_sessionmaker, job.id)).status == "running"


async def test_requeue_training_jobs_raises_when_the_dataset_has_no_manifest(
    db_session: AsyncSession, db_sessionmaker: Maker, fake_clock: FakeClock, messaging_env: None
) -> None:
    """Dataset trỏ tới chưa `ready` (chưa có `manifest_sha256`) → lỗi lập trình lộ ra ngay, không âm thầm gửi rác."""
    fake_clock.set(datetime.now(UTC))
    dataset = await make_dataset(db_session, family=FAMILY, created_by=SEED_USER)
    building = await make_dataset_version(db_session, dataset=dataset, status="building", sequence=1)
    job = await make_training_job(
        db_session, dataset_version_id=building.id, status="queued", created_at=fake_clock.now()
    )
    settings = get_training_settings()
    fake_clock.advance(timedelta(seconds=settings.training_requeue_after_s + 1))

    with pytest.raises(RuntimeError, match="manifest_sha256"):
        await run_requeue_training_jobs(db_sessionmaker, fake_clock)

    assert (await _read_job(db_sessionmaker, job.id)).requeue_count == 0


async def test_sweep_requeue_and_purge_are_no_ops_without_candidates(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Không job nào khớp điều kiện → cả ba lịch trả 0 ngay, không chạm Redis/kho."""
    fake_clock.set(datetime.now(UTC))

    assert await run_sweep_lost_training_jobs(db_sessionmaker, fake_clock) == 0
    assert await run_requeue_training_jobs(db_sessionmaker, fake_clock) == 0
    assert await run_purge_training_job_artifacts(db_sessionmaker, local_storage, fake_clock) == 0


# ---------------------------------------------------------------------------
# purge_training_job_artifacts
# ---------------------------------------------------------------------------


def _artifact_key(job_id: str) -> str:
    """Khoá object trọng số dưới tiền tố artifact của job (`model_artifact`, không viết tay chuỗi)."""
    return model_artifact(trained_version_id(job_id), "weights.onnx")


async def test_purge_training_job_artifacts__J01(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    messaging_env: None,
    safe_client: SyncRedis,
) -> None:
    """Artifact của job `failed` quá hạn bị xoá; job `succeeded` và job có claim còn nguyên."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    purge_after = get_training_settings().training_purge_after_s
    ended = fake_clock.now() - timedelta(seconds=purge_after + 60)

    failed = await make_training_job(
        db_session, dataset_version_id=dsv, status="failed", created_at=ended - timedelta(minutes=1), ended_at=ended
    )
    claimed_failed = await make_training_job(
        db_session, dataset_version_id=dsv, status="failed", created_at=ended - timedelta(minutes=1), ended_at=ended
    )
    safe_client.set(claim_key(claimed_failed.id), "1")
    succeeded_model = await _make_succeeded_model(db_session)
    succeeded = await make_training_job(
        db_session,
        dataset_version_id=dsv,
        status="succeeded",
        created_at=ended - timedelta(minutes=1),
        ended_at=ended,
        result_model_version_id=succeeded_model,
    )

    failed_key, succeeded_key = _artifact_key(failed.id), _artifact_key(succeeded.id)
    claimed_key = _artifact_key(claimed_failed.id)
    await local_storage.put(failed_key, b"w", content_type="application/octet-stream", max_bytes=16)
    await local_storage.put(succeeded_key, b"w", content_type="application/octet-stream", max_bytes=16)
    await local_storage.put(claimed_key, b"w", content_type="application/octet-stream", max_bytes=16)

    assert await run_purge_training_job_artifacts(db_sessionmaker, local_storage, fake_clock) == 1

    assert await local_storage.stat(failed_key) is None
    assert await local_storage.stat(succeeded_key) is not None
    assert await local_storage.stat(claimed_key) is not None
    row = await _read_job(db_sessionmaker, failed.id)
    assert row.artifacts_purged_at == fake_clock.now()


async def test_purge_training_job_artifacts__J06(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    messaging_env: None,
) -> None:
    """Chạy hai lần liền: lượt hai không xoá gì thêm."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    purge_after = get_training_settings().training_purge_after_s
    ended = fake_clock.now() - timedelta(seconds=purge_after + 60)
    failed = await make_training_job(
        db_session, dataset_version_id=dsv, status="failed", created_at=ended - timedelta(minutes=1), ended_at=ended
    )
    key = _artifact_key(failed.id)
    await local_storage.put(key, b"w", content_type="application/octet-stream", max_bytes=16)
    await run_purge_training_job_artifacts(db_sessionmaker, local_storage, fake_clock)

    assert await run_purge_training_job_artifacts(db_sessionmaker, local_storage, fake_clock) == 0

    assert await local_storage.stat(key) is None


async def test_purge_training_job_artifacts_skips_the_whole_batch_when_redis_is_down(
    db_session: AsyncSession,
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    messaging_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redis chết trước khi đọc `claim_key` → không artifact nào bị xoá."""
    fake_clock.set(datetime.now(UTC))
    dsv = await _ready_dataset_version(db_session)
    purge_after = get_training_settings().training_purge_after_s
    ended = fake_clock.now() - timedelta(seconds=purge_after + 60)
    failed = await make_training_job(
        db_session, dataset_version_id=dsv, status="failed", created_at=ended - timedelta(minutes=1), ended_at=ended
    )
    key = _artifact_key(failed.id)
    await local_storage.put(key, b"w", content_type="application/octet-stream", max_bytes=16)
    _kill_redis(monkeypatch)

    assert await run_purge_training_job_artifacts(db_sessionmaker, local_storage, fake_clock) == 0

    assert await local_storage.stat(key) is not None


async def _make_succeeded_model(db: AsyncSession) -> str:
    """Id một bản model thật cho job `succeeded` trỏ tới (`result_model_version_id` có FK tới `model_versions`)."""
    row = await make_model_version(db, family=FAMILY, status="completed")
    return row.id


# ---------------------------------------------------------------------------
# Lịch: đăng ký và test khói
# ---------------------------------------------------------------------------


def test_training_job_schedules_are_registered_with_their_periods() -> None:
    """Ba lịch đăng ký đúng tên, hàm và chu kỳ (1', 5', 1h)."""
    entries = {entry.name: entry for entry in schedule_entries()}

    assert entries[SWEEP_TASK].function == "sweep_lost_training_jobs"
    assert entries[SWEEP_TASK].every == SWEEP_EVERY == timedelta(minutes=1)
    assert entries[REQUEUE_TASK].function == "requeue_training_jobs"
    assert entries[REQUEUE_TASK].every == REQUEUE_EVERY == timedelta(minutes=5)
    assert entries[PURGE_TASK].function == "purge_training_job_artifacts"
    assert entries[PURGE_TASK].every == PURGE_EVERY == timedelta(hours=1)


@pytest.fixture
def process_env(db_url: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường của một tiến trình lịch — cùng một bản với test khói của task (`_helpers`)."""
    with worker_process_env(db_url, tmp_path, monkeypatch):
        yield


async def _seed_stale_running() -> str:
    """Một job `running` đã mất nhịp tim, trong DB của tiến trình."""
    maker = process_maker()
    engine = maker.kw["bind"]
    try:
        clock = FakeClock(datetime.now(UTC))
        async with maker() as db:
            dsv = await _ready_dataset_version(db)
            timeout = get_training_settings().training_heartbeat_timeout_s
            stale = clock.now() - timedelta(seconds=timeout + 60)
            job = await make_training_job(
                db,
                dataset_version_id=dsv,
                status="running",
                created_at=stale - timedelta(minutes=1),
                started_at=stale - timedelta(minutes=1),
                last_heartbeat_at=stale,
            )
        return job.id
    finally:
        await engine.dispose()


async def _seed_overdue_queued() -> str:
    """Một job `queued` đứng im quá hạn gửi lại, trong DB của tiến trình."""
    maker = process_maker()
    engine = maker.kw["bind"]
    try:
        clock = FakeClock(datetime.now(UTC) - timedelta(seconds=get_training_settings().training_requeue_after_s + 60))
        async with maker() as db:
            dsv = await _ready_dataset_version(db)
            job = await make_training_job(db, dataset_version_id=dsv, status="queued", created_at=clock.now())
        return job.id
    finally:
        await engine.dispose()


async def _seed_purgeable_failed() -> tuple[str, str]:
    """Một job `failed` quá hạn dọn, trong DB của tiến trình; trả `(job_id, dataset_version_id)`."""
    maker = process_maker()
    engine = maker.kw["bind"]
    try:
        clock = FakeClock(datetime.now(UTC))
        ended = clock.now() - timedelta(seconds=get_training_settings().training_purge_after_s + 60)
        async with maker() as db:
            dsv = await _ready_dataset_version(db)
            job = await make_training_job(
                db, dataset_version_id=dsv, status="failed", created_at=ended - timedelta(minutes=1), ended_at=ended
            )
        return job.id, dsv
    finally:
        await engine.dispose()


async def _read_status(job_id: str) -> tuple[str, str | None]:
    """`(status, failure_code)` đọc lại từ DB của tiến trình."""
    maker = process_maker()
    engine = maker.kw["bind"]
    try:
        async with maker() as db:
            stmt = select(TrainingJobRow.status, TrainingJobRow.failure_code).where(TrainingJobRow.id == job_id)
            status, code = (await db.execute(stmt)).one()
            return str(status), None if code is None else str(code)
    finally:
        await engine.dispose()


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_sweep_lost_training_jobs_smoke(broker: SyncRedis) -> None:
    """Hàm lịch thật (`SystemClock`, `worker_sessionmaker`) chốt `failed` một job mất nhịp tim."""
    job_id = asyncio.run(_seed_stale_running())

    sweep_lost_training_jobs()
    reset_database_settings_cache()

    assert asyncio.run(_read_status(job_id)) == ("failed", TRAINING_HEARTBEAT_LOST)


@pytest.mark.usefixtures("process_env", "celery_test_app")
def test_requeue_training_jobs_smoke(broker: SyncRedis) -> None:
    """Hàm lịch thật gửi lại một job `queued` đứng im quá hạn."""
    job_id = asyncio.run(_seed_overdue_queued())

    requeue_training_jobs()
    reset_database_settings_cache()

    assert _sent(broker) == [job_id]


@pytest.mark.usefixtures("process_env", "messaging_env")
def test_purge_training_job_artifacts_smoke(local_storage: LocalDiskStorage, tmp_path: Path) -> None:
    """Hàm lịch thật mở kho của tiến trình và xoá artifact của job `failed` quá hạn."""
    job_id, _dsv = asyncio.run(_seed_purgeable_failed())
    key = _artifact_key(job_id)
    asyncio.run(local_storage.put(key, b"w", content_type="application/octet-stream", max_bytes=16))

    purge_training_job_artifacts()
    reset_database_settings_cache()

    assert not (tmp_path / "objects" / key).exists()
