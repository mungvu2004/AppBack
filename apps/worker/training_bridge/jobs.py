"""Ba lịch nền của job huấn luyện: mất nhịp tim, gửi lại hàng chờ, dọn artifact (B6-03a [6]).

Lõi (`run_…`) tách khỏi hàm lịch để test truyền đồng hồ, sessionmaker, storage của test;
hàm lịch chỉ dựng tài nguyên thật. `apps/worker` nhập module này để chạy beat, nên nó chỉ
được nhập `packages.*`, `apps.api.admin_ml_jobs.*`, `apps.api.admin_ml_datasets.*`,
`apps.api.library.*` và `apps.worker.training_bridge.*` — không `fastapi`/`starlette`,
không `apps.ml` (K, B6-03b cùng đợt).

- `sweep_lost_training_jobs` (1'): job `running|cancelling` có nhịp tim quá hạn **và**
  `claim_key` vắng → chốt `failed`/`cancelled`. Claim còn → chỉ log, không đổi (runner có
  thể chỉ chậm gửi nhịp tim).
- `requeue_training_jobs` (5'): job `queued` đứng im quá `training_requeue_after_s x
  2^requeue_count` **và** `claim_key` vắng → gửi lại tối đa sáu lượt, hết lượt mà vẫn quá
  hạn → `failed` `TRAINING_DISPATCH_STALLED`.
- `purge_training_job_artifacts` (1h): job `failed|cancelled` đã `ended_at` quá
  `training_purge_after_s`, chưa dọn, `claim_key` vắng → xoá tiền tố artifact (K36: ngoài
  giao dịch) rồi ghi `artifacts_purged_at`. `succeeded` không bao giờ bị đụng.

Mọi lịch đọc `claim_key` bằng `safe_redis()` **trước** khi đổi job nào; Redis lỗi thì bỏ cả
lượt (không job nào đổi) và log `training_sweep_skipped` — tránh chốt nhầm một job mà runner
đang giữ nhưng chỉ vì Redis tạm mất đã coi như mồ côi. Mỗi job đổi trạng thái trong **một**
giao dịch riêng với `SELECT … FOR UPDATE` rồi kiểm lại điều kiện dưới khoá (K18, idempotent):
hai beat chồng nhau hay beat chạy lại trên cùng lô không đổi một job hai lần.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Final, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.worker.training_bridge.errors import TRAINING_DISPATCH_STALLED, TRAINING_HEARTBEAT_LOST
from apps.worker.training_bridge.settings import get_training_settings
from apps.worker.training_bridge.tasks import arm_cancel_key, open_storage
from packages.core.clock import Clock, SystemClock
from packages.core.object_keys import model_prefix
from packages.db.engine import session_scope, worker_sessionmaker
from packages.db.hooks import after_commit_idle, on_after_commit
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.models.admin_ml_jobs import TrainingJobRow
from packages.messaging import periodic, safe_redis, send_task
from packages.messaging.payloads.training import claim_key, trained_version_id
from packages.messaging.redis import DEPENDENCY_ERRORS
from packages.ml_contracts.families import TrainableFamily
from packages.ml_contracts.payloads import TrainJobPayload
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

SWEEP_TASK: Final = "default.training_bridge.sweep_lost_training_jobs"
SWEEP_EVERY: Final = timedelta(minutes=1)
REQUEUE_TASK: Final = "default.training_bridge.requeue_training_jobs"
REQUEUE_EVERY: Final = timedelta(minutes=5)
PURGE_TASK: Final = "default.training_bridge.purge_training_job_artifacts"
PURGE_EVERY: Final = timedelta(hours=1)

RUNNER_START_TASK: Final = "ml.training.runner.start"

SWEEP_BATCH: Final = 100
REQUEUE_BATCH: Final = 100
PURGE_BATCH: Final = 500

MAX_REQUEUE_ATTEMPTS: Final = 6
"""Sau sáu lượt gửi lại mà job vẫn `queued`, vấn đề không phải thông điệp bị trễ nữa."""

_RUNNING_TO: Final = ("failed", TRAINING_HEARTBEAT_LOST)
_CANCELLING_TO: Final = ("cancelled", None)
_LOST_TRANSITION: Final = {"running": _RUNNING_TO, "cancelling": _CANCELLING_TO}


async def _claims_present(job_ids: Sequence[str]) -> dict[str, bool] | None:
    """`claim_key` của cả lô (không rỗng) bằng một lượt `MGET`; `None` khi **Redis** lỗi (bỏ cả lượt).

    Chỉ `DEPENDENCY_ERRORS` thành `None`: một lỗi khác (thiếu `REDIS_BROKER_URL` ở tiến trình
    beat, bug trong lô) phải nổi lên, vì nuốt nó biến cả ba lịch thành "luôn trả 0" im lặng và
    quy sai nguyên nhân cho Redis. Client dựng mới mỗi lượt nên đóng lại trong `finally` (R-24).
    """
    client = safe_redis()
    try:
        values = await client.mget([claim_key(job_id) for job_id in job_ids])
    except DEPENDENCY_ERRORS as exc:
        _log.warning("training_claim_read_failed", extra={"error": type(exc).__name__})
        return None
    finally:
        await client.aclose()
    return dict(zip(job_ids, (value is not None for value in values), strict=True))


def _log_skip(schedule: str) -> None:
    """Redis lỗi ở đầu lượt: không job nào bị đụng, beat sau thử lại."""
    _log.warning("training_sweep_skipped", extra={"schedule": schedule})


async def _finish_lost_job(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, job_id: str, status: str, cutoff: datetime
) -> bool:
    """Chốt một job `running|cancelling` mất nhịp tim, dưới khoá, trong giao dịch riêng.

    Kiểm lại cả `status` và cửa sổ nhịp tim dưới khoá (K18): job đã đổi hay vừa báo nhịp
    tim mới giữa lúc đọc lô và lúc khoá dòng thì không bị đụng. `arm_cancel_key` lỗi →
    rollback chỉ job này, lượt vẫn tiếp tục với các job khác.
    """
    to_status, failure_code = _LOST_TRANSITION[status]
    now = clock.now()
    async with sessionmaker() as db:
        stmt = (
            select(TrainingJobRow)
            .where(TrainingJobRow.id == job_id, TrainingJobRow.status == status)
            .where(func.coalesce(TrainingJobRow.last_heartbeat_at, TrainingJobRow.started_at) < cutoff)
            .with_for_update()
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            await db.rollback()
            return False
        row.status = to_status
        row.failure_code = failure_code
        row.ended_at = now
        try:
            await arm_cancel_key(job_id)
        except DEPENDENCY_ERRORS as exc:
            await db.rollback()
            _log.warning(
                "training_heartbeat_lost_cancel_key_failed",
                extra={"job_id": job_id, "error": type(exc).__name__},
            )
            return False
        await db.commit()
    return True


async def run_sweep_lost_training_jobs(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = SWEEP_BATCH
) -> int:
    """Một lượt quét job mất nhịp tim; trả số job đã chốt `failed`/`cancelled`."""
    settings = get_training_settings()
    cutoff = clock.now() - timedelta(seconds=settings.training_heartbeat_timeout_s)
    stmt = (
        select(TrainingJobRow.id, TrainingJobRow.status)
        .where(TrainingJobRow.status.in_(("running", "cancelling")))
        .where(func.coalesce(TrainingJobRow.last_heartbeat_at, TrainingJobRow.started_at) < cutoff)
        .order_by(TrainingJobRow.created_at, TrainingJobRow.id)
        .limit(batch)
    )
    async with sessionmaker() as db:
        candidates = (await db.execute(stmt)).all()
    if not candidates:
        return 0
    claims = await _claims_present([row.id for row in candidates])
    if claims is None:
        _log_skip("sweep_lost_training_jobs")
        return 0
    finished = 0
    for row in candidates:
        if claims[row.id]:
            _log.info("training_heartbeat_late", extra={"job_id": row.id})
            continue
        if await _finish_lost_job(sessionmaker, clock, row.id, row.status, cutoff):
            finished += 1
    return finished


async def _dispatch_training_run(db: AsyncSession, row: TrainingJobRow) -> None:
    """Đăng ký gửi `RUNNER_START_TASK` **sau** commit (K17); `manifest_sha256` ghim của dataset."""
    manifest_stmt = select(DatasetVersionRow.manifest_sha256).where(DatasetVersionRow.id == row.dataset_version_id)
    manifest_sha256 = (await db.execute(manifest_stmt)).scalar_one()
    if manifest_sha256 is None:
        raise RuntimeError(f"dataset {row.dataset_version_id!r} chưa có manifest_sha256")
    payload = TrainJobPayload(
        job_id=row.id,
        family=cast(TrainableFamily, row.family),
        base_model=row.base_model,
        epochs=row.epochs,
        dataset_version_id=row.dataset_version_id,
        manifest_sha256=manifest_sha256,
    )
    on_after_commit(db, lambda: send_task(RUNNER_START_TASK, payload))


async def _process_requeue_job(sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, job_id: str) -> bool:
    """Một job `queued` quá hạn, trong giao dịch riêng: gửi lại hay chốt `TRAINING_DISPATCH_STALLED`.

    Trả `True` nếu job được xử lý (gửi lại hoặc chốt hỏng), `False` nếu điều kiện không còn
    đúng dưới khoá (K18) hay Redis lỗi lúc đặt `cancel_key`.
    """
    settings = get_training_settings()
    now = clock.now()
    async with sessionmaker() as db:
        stmt = (
            select(TrainingJobRow)
            .where(TrainingJobRow.id == job_id, TrainingJobRow.status == "queued")
            .with_for_update()
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if row is None:
            await db.rollback()
            return False
        threshold = timedelta(seconds=settings.training_requeue_after_s * (2**row.requeue_count))
        if now - row.updated_at < threshold:
            await db.rollback()
            return False
        if row.requeue_count < MAX_REQUEUE_ATTEMPTS:
            row.requeue_count += 1
            await _dispatch_training_run(db, row)
        else:
            row.status = "failed"
            row.failure_code = TRAINING_DISPATCH_STALLED
            row.ended_at = now
            try:
                await arm_cancel_key(job_id)
            except DEPENDENCY_ERRORS as exc:
                await db.rollback()
                _log.warning(
                    "training_dispatch_stalled_cancel_key_failed",
                    extra={"job_id": job_id, "error": type(exc).__name__},
                )
                return False
        session = db
        await db.commit()
    await after_commit_idle(session)
    return True


async def run_requeue_training_jobs(
    sessionmaker: async_sessionmaker[AsyncSession], clock: Clock, *, batch: int = REQUEUE_BATCH
) -> int:
    """Một lượt gửi lại job `queued` đứng im; trả số job đã xử lý (gửi lại hoặc chốt hỏng)."""
    now = clock.now()
    settings = get_training_settings()
    oldest_possible = timedelta(seconds=settings.training_requeue_after_s)
    stmt = (
        select(TrainingJobRow.id)
        .where(TrainingJobRow.status == "queued", TrainingJobRow.updated_at < now - oldest_possible)
        .order_by(TrainingJobRow.created_at, TrainingJobRow.id)
        .limit(batch)
    )
    async with sessionmaker() as db:
        job_ids = list((await db.execute(stmt)).scalars().all())
    if not job_ids:
        return 0
    claims = await _claims_present(job_ids)
    if claims is None:
        _log_skip("requeue_training_jobs")
        return 0
    processed = 0
    for job_id in job_ids:
        if claims[job_id]:
            continue
        if await _process_requeue_job(sessionmaker, clock, job_id):
            processed += 1
    return processed


async def _purge_one(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, job_id: str
) -> bool:
    """Xoá tiền tố artifact của một job rồi ghi `artifacts_purged_at`; trả `False` nếu đã dọn trước đó.

    `delete_prefix` chạy **ngoài** giao dịch (K36): không có kết nối DB nào bị giữ trong lúc
    gọi storage. `UPDATE … WHERE artifacts_purged_at IS NULL` tự idempotent dưới khoá hàng
    của Postgres, không cần `SELECT … FOR UPDATE` riêng.
    """
    await storage.delete_prefix(model_prefix(trained_version_id(job_id)))
    async with session_scope(sessionmaker) as db:
        result = await db.execute(
            update(TrainingJobRow)
            .where(TrainingJobRow.id == job_id, TrainingJobRow.artifacts_purged_at.is_(None))
            .values(artifacts_purged_at=clock.now())
        )
    return cast("CursorResult[Any]", result).rowcount > 0


async def run_purge_training_job_artifacts(
    sessionmaker: async_sessionmaker[AsyncSession], storage: ObjectStorage, clock: Clock, *, batch: int = PURGE_BATCH
) -> int:
    """Một lượt dọn artifact của job `failed|cancelled` đã quá hạn; trả số job đã dọn."""
    settings = get_training_settings()
    cutoff = clock.now() - timedelta(seconds=settings.training_purge_after_s)
    stmt = (
        select(TrainingJobRow.id)
        .where(TrainingJobRow.status.in_(("failed", "cancelled")))
        .where(TrainingJobRow.ended_at < cutoff, TrainingJobRow.artifacts_purged_at.is_(None))
        .order_by(TrainingJobRow.created_at, TrainingJobRow.id)
        .limit(batch)
    )
    async with sessionmaker() as db:
        job_ids = list((await db.execute(stmt)).scalars().all())
    if not job_ids:
        return 0
    claims = await _claims_present(job_ids)
    if claims is None:
        _log_skip("purge_training_job_artifacts")
        return 0
    purged = 0
    for job_id in job_ids:
        if claims[job_id]:
            continue
        if await _purge_one(sessionmaker, storage, clock, job_id):
            purged += 1
    return purged


@periodic(SWEEP_TASK, every=SWEEP_EVERY)
async def sweep_lost_training_jobs() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi quét job mất nhịp tim."""
    clock = SystemClock()
    finished = await run_sweep_lost_training_jobs(worker_sessionmaker(), clock)
    _log.info("training_heartbeat_sweep", extra={"finished": finished})


@periodic(REQUEUE_TASK, every=REQUEUE_EVERY)
async def requeue_training_jobs() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi gửi lại job `queued` đứng im."""
    clock = SystemClock()
    processed = await run_requeue_training_jobs(worker_sessionmaker(), clock)
    _log.info("training_requeue", extra={"processed": processed})


@periodic(PURGE_TASK, every=PURGE_EVERY)
async def purge_training_job_artifacts() -> None:
    """Hàm lịch: dựng tài nguyên thật rồi gọi lõi dọn artifact của job đã kết thúc."""
    clock = SystemClock()
    deleted = await run_purge_training_job_artifacts(worker_sessionmaker(), open_storage(clock), clock)
    _log.info("training_artifact_purge", extra={"deleted": deleted})
