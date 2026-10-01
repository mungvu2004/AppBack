"""`finish_training_job`: J01, J03, J06, J09, trọng số không tin được và K36 (B6-03a [8]).

Kho là `local_storage` thật; `stat` chỉ bị **bọc** để chặn một lượt (K36) chứ không bị thay
bằng kho giả. Lõi `run_finish_training_job` nhận session factory, kho và `Clock` tiêm vào.
"""

import asyncio
import threading
from typing import Any

import pytest
from celery import Celery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_jobs.settings import reset_training_settings_cache
from apps.worker.training_bridge import tasks
from apps.worker.training_bridge.errors import MODEL_CHECKSUM_MISMATCH, TRAINING_METRICS_MISSING
from apps.worker.training_bridge.tasks import FINISHED_TASK, run_finish_training_job
from apps.worker.training_bridge.tests._helpers import (
    METRIC,
    WEIGHTS_NAME,
    finished,
    put_weights,
    read_job,
    seed_job,
    weights_key,
)
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.db.models.admin_ml_registry import ModelVersionRow
from packages.messaging.payloads.training import cancel_key, trained_version_id
from packages.messaging.redis import safe_redis
from packages.storage.keys import model_artifact
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectInfo, ObjectStorage
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("messaging_env")

_OTHER_JOB_VERSION = "mdl_01KB60100000000000000000ZZ"


class _BlockingStatStorage:
    """Kho thật với **một** lượt `stat` bị chặn — để đo K36 (không giữ kết nối DB khi chạm kho)."""

    def __init__(self, inner: ObjectStorage, entered: threading.Event, release: threading.Event) -> None:
        """Giữ kho thật cùng hai cờ: `entered` báo đã vào `stat`, `release` cho phép đi tiếp."""
        self._inner = inner
        self._entered = entered
        self._release = release

    async def stat(self, key: str) -> ObjectInfo | None:
        """Báo đã vào `stat`, chờ test thả, rồi gọi kho thật."""
        self._entered.set()
        await asyncio.to_thread(self._release.wait)
        return await self._inner.stat(key)

    def __getattr__(self, name: str) -> Any:  # chuyển tiếp nguyên vẹn mọi phương thức khác của kho
        """Mọi phương thức khác đi thẳng xuống kho thật."""
        return getattr(self._inner, name)


async def weighted_job(db: AsyncSession, storage: ObjectStorage, clock: FakeClock) -> tuple[TrainingJobRow, str]:
    """Một job `running` và object trọng số đúng mẫu đã nằm trong kho.

    Là hàm chứ không phải fixture: fixture async của repo chạy trên vòng sự kiện phạm vi
    session (`asyncio_default_fixture_loop_scope`), còn test chạy trên vòng của riêng nó —
    một engine mở ở fixture sẽ "attached to a different loop" khi test dùng lại.
    """
    job = await seed_job(db, clock=clock)
    await put_weights(storage, weights_key(job.id))
    return job, weights_key(job.id)


@pytest.mark.asyncio
async def test_finish_training_job__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`succeeded` hợp lệ: job chốt, bản `trained_version_id` `pending`, một lượt xin đánh giá."""
    job, key = await weighted_job(db_session, local_storage, fake_clock)

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key))

    row = await read_job(db_session, job.id)
    version = await db_session.get(ModelVersionRow, trained_version_id(job.id))
    expected = ("succeeded", trained_version_id(job.id), fake_clock.now())
    assert (row.status, row.result_model_version_id, row.ended_at) == expected
    assert version is not None
    assert (version.evaluation_status, version.evaluation_attempts, version.training_job_id) == ("pending", 1, job.id)


@pytest.mark.asyncio
async def test_finish_training_job__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Gửi lại `finished`: job đã kết thúc → bỏ, một bản duy nhất, `attempts` không tăng."""
    job, key = await weighted_job(db_session, local_storage, fake_clock)
    payload = finished(job.id, key=key)
    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, payload)

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, payload)

    version = await db_session.get(ModelVersionRow, trained_version_id(job.id))
    assert version is not None
    assert version.evaluation_attempts == 1
    assert await safe_redis().get(cancel_key(job.id)) is not None


@pytest.mark.asyncio
async def test_finish_training_job__J03(
    db_session: AsyncSession, celery_test_app: Celery, fake_clock: FakeClock
) -> None:
    """Payload sai schema là thông điệp độc: `define_task` từ chối trước thân, job không đổi."""
    job = await seed_job(db_session, clock=fake_clock)

    result = celery_test_app.tasks[FINISHED_TASK].apply(args=({"schema_version": 1, "job_id": job.id},))

    assert result.successful()
    assert (await read_job(db_session, job.id)).status == "running"


@pytest.mark.asyncio
async def test_finish_training_job__J09(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lỗi **sau** `register_trained_version`, **trước** commit → rollback: không bản, job không đổi."""
    job, key = await weighted_job(db_session, local_storage, fake_clock)

    async def _boom(*_args: object, **_kwargs: object) -> bool:
        """Mô phỏng một lỗi giữa giao dịch (J09)."""
        raise RuntimeError("vỡ giữa giao dịch")

    monkeypatch.setattr(tasks, "request_evaluation", _boom)

    with pytest.raises(RuntimeError):
        await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key))

    assert await db_session.get(ModelVersionRow, trained_version_id(job.id)) is None
    assert (await read_job(db_session, job.id)).status == "running"


@pytest.mark.asyncio
async def test_finish_succeeded_while_cancelling_records_cancelled(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`succeeded` tới khi job đang `cancelling` → `cancelled`, không bản model nào được ghi."""
    job = await seed_job(db_session, status="cancelling", clock=fake_clock)
    await put_weights(local_storage, weights_key(job.id))

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id))

    assert (await read_job(db_session, job.id)).status == "cancelled"
    assert await db_session.get(ModelVersionRow, trained_version_id(job.id)) is None
    assert await safe_redis().get(cancel_key(job.id)) is not None


@pytest.mark.asyncio
async def test_finish_failed_from_queued_sets_both_timestamps(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`failed` từ `queued`: `started_at = ended_at = now`, mã lỗi của runner đi thẳng vào job."""
    job = await seed_job(db_session, status="queued", clock=fake_clock)

    await run_finish_training_job(
        db_sessionmaker, local_storage, fake_clock, finished(job.id, status="failed", error_code="TRAINER_CRASHED")
    )

    row = await read_job(db_session, job.id)
    assert (row.status, row.failure_code) == ("failed", "TRAINER_CRASHED")
    assert row.started_at == row.ended_at == fake_clock.now()


@pytest.mark.asyncio
async def test_finish_cancelled_from_cancelling_arms_the_cancel_key(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`cancelled` từ `cancelling`: `cancel_key` đặt trước commit (runner có thể còn sống)."""
    job = await seed_job(db_session, status="cancelling", clock=fake_clock)

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id, status="cancelled"))

    assert (await read_job(db_session, job.id)).status == "cancelled"
    assert await safe_redis().get(cancel_key(job.id)) is not None


@pytest.mark.asyncio
async def test_finish_of_missing_job_is_ignored(
    db_sessionmaker: async_sessionmaker[AsyncSession], local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Job không còn → bỏ im lặng, không ngoại lệ."""
    await run_finish_training_job(
        db_sessionmaker, local_storage, fake_clock, finished("job_01KB60100000000000000000ZZ", status="cancelled")
    )


@pytest.mark.parametrize(
    ("name", "other_job"),
    [("weights.onnx", False), ("weights-nothex.onnx", False), (WEIGHTS_NAME, True)],
    ids=["no_token", "bad_token", "other_job_prefix"],
)
@pytest.mark.asyncio
async def test_finish_rejects_weights_keys_outside_the_contract(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    name: str,
    other_job: bool,
) -> None:
    """Tên sai mẫu hay tiền tố của job khác → `failed` `MODEL_CHECKSUM_MISMATCH`, không bản model."""
    job = await seed_job(db_session, clock=fake_clock)
    key = model_artifact(_OTHER_JOB_VERSION if other_job else trained_version_id(job.id), name)
    await put_weights(local_storage, key)

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key))

    row = await read_job(db_session, job.id)
    assert (row.status, row.failure_code) == ("failed", MODEL_CHECKSUM_MISMATCH)
    assert await db_session.get(ModelVersionRow, trained_version_id(job.id)) is None


@pytest.mark.asyncio
async def test_finish_rejects_a_missing_object(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Khoá đúng mẫu nhưng object không có trong kho → `MODEL_CHECKSUM_MISMATCH`."""
    job = await seed_job(db_session, clock=fake_clock)

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id))

    assert (await read_job(db_session, job.id)).failure_code == MODEL_CHECKSUM_MISMATCH


@pytest.mark.asyncio
async def test_finish_rejects_a_checksum_mismatch(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`sha256` kho đo lại lệch `checksum_sha256` của runner → `MODEL_CHECKSUM_MISMATCH`."""
    job, key = await weighted_job(db_session, local_storage, fake_clock)

    await run_finish_training_job(
        db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key, checksum="0" * 64)
    )

    assert (await read_job(db_session, job.id)).failure_code == MODEL_CHECKSUM_MISMATCH


@pytest.mark.asyncio
async def test_finish_rejects_weights_above_the_size_cap(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Object quá trần `TRAINING_WEIGHTS_MAX_BYTES` (hạ bằng env) → `MODEL_CHECKSUM_MISMATCH`."""
    job, key = await weighted_job(db_session, local_storage, fake_clock)
    monkeypatch.setenv("TRAINING_WEIGHTS_MAX_BYTES", "1")
    reset_training_settings_cache()
    try:
        await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key))
    finally:
        monkeypatch.delenv("TRAINING_WEIGHTS_MAX_BYTES")
        reset_training_settings_cache()

    assert (await read_job(db_session, job.id)).failure_code == MODEL_CHECKSUM_MISMATCH


@pytest.mark.asyncio
async def test_finish_rejects_metrics_of_another_family(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`metrics` không đúng khoá `FAMILY_METRIC[family]` → `failed` `TRAINING_METRICS_MISSING`.

    Lệch khỏi prompt: `metrics == {}` không dựng được payload (`check_metrics` của B5-01 đòi
    đúng một khoá), nên ca này dùng số đo của **họ khác** — cùng nhánh mã, cùng mã lỗi.
    """
    job, key = await weighted_job(db_session, local_storage, fake_clock)
    assert METRIC != "iou"

    await run_finish_training_job(
        db_sessionmaker, local_storage, fake_clock, finished(job.id, key=key, metric_values={"iou": 0.5})
    )

    row = await read_job(db_session, job.id)
    assert (row.status, row.failure_code) == ("failed", TRAINING_METRICS_MISSING)
    assert await db_session.get(ModelVersionRow, trained_version_id(job.id)) is None


@pytest.mark.asyncio
async def test_finish_does_not_hold_a_db_connection_while_statting_weights(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """K36: trong lúc `stat` bị chặn, pool của engine không giữ kết nối nào.

    Session của chính test cũng mượn từ pool ấy, nên phải đóng sau khi dựng dữ liệu —
    nếu không thì phép đếm đo kết nối của test, không phải của cầu nối.
    """
    job, key = await weighted_job(db_session, local_storage, fake_clock)
    await db_session.close()
    entered, release = threading.Event(), threading.Event()
    storage = _BlockingStatStorage(local_storage, entered, release)
    engine = db_sessionmaker.kw["bind"]
    done = finished(job.id, key=key)
    running = asyncio.create_task(
        run_finish_training_job(db_sessionmaker, storage, fake_clock, done)  # type: ignore[arg-type] — bọc kho thật
    )
    await asyncio.to_thread(entered.wait)

    checked_out = engine.pool.checkedout()
    release.set()
    await running

    assert checked_out == 0


@pytest.mark.asyncio
async def test_finish_succeeded_from_queued_sets_started_and_ended_together(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`finished(succeeded)` tới **trước** nhịp tim đầu: job `queued` thành `succeeded`.

    Runner có thể xong trước khi nhịp tim đầu tới ([8] "Cầu nối" gạch 3); job khi ấy chưa có
    `started_at`, nên cầu nối đặt `started_at = ended_at = now` và bản model vẫn được ghi.
    """
    job = await seed_job(db_session, status="queued", clock=fake_clock)
    await put_weights(local_storage, weights_key(job.id))

    await run_finish_training_job(db_sessionmaker, local_storage, fake_clock, finished(job.id))

    row = await read_job(db_session, job.id)
    assert (row.status, row.result_model_version_id) == ("succeeded", trained_version_id(job.id))
    assert row.started_at == row.ended_at == fake_clock.now()
