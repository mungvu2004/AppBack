"""Việc của N32-N37 (B6-03a [6]); `router.py` chỉ chuyển tham số vào đây.

Ba quyết định của module:

- **N33 không khoá gì**: bản `ready` là bất biến (B6-02), nên đọc `dataset_versions` +
  `datasets` thường là đủ; chỉ N35 cần `FOR UPDATE` vì nó đổi trạng thái (K18);
- **`cancel_key` đặt trước commit** (N35): Redis hỏng thì giao dịch phải rollback để job
  không bao giờ mang `cancelling` mà runner không thấy khoá huỷ. Ngược lại `send_task`
  của N33 nằm **sau** commit (K17) — một thông điệp mồ côi vô hại, một job huỷ mà runner
  không biết thì không;
- **N36/N37 giữ `nextCursor`** tới hết cửa sổ muộn: vòng polling của FE dừng khi tab ẩn,
  nên cursor vắng là FE ngừng đọc vĩnh viễn ([1]).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from sqlalchemy import asc, desc, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.admin_ml_jobs.errors import (
    DATASET_FAMILY_MISMATCH,
    DATASET_VERSION_NOT_READY,
    TRAINING_BASE_MODEL_MISMATCH,
    TRAINING_JOB_NOT_CANCELLABLE,
)
from apps.api.admin_ml_jobs.schemas import (
    TrainingJobOut,
    TrainingJobPage,
    TrainingLogPage,
    TrainingMetricPage,
    job_out,
    log_line_out,
    metric_point_out,
)
from apps.api.admin_ml_jobs.settings import TrainingSettings, get_training_settings
from apps.api.core.auth import Principal
from apps.api.core.pagination import PageParams, decode_cursor, encode_cursor
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND, VALIDATION
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.db.hooks import on_after_commit
from packages.db.models.admin_ml_datasets import DatasetRow, DatasetVersionRow
from packages.db.models.admin_ml_jobs import (
    METRIC_SPLITS,
    TRAINING_JOB_STATUSES,
    TrainingJobRow,
    TrainingLogRow,
    TrainingMetricRow,
)
from packages.messaging.celery_app import send_task
from packages.messaging.payloads.training import cancel_key
from packages.messaging.redis import safe_redis
from packages.ml_contracts.families import BASE_MODELS, TRAINABLE_FAMILIES, TrainableFamily
from packages.ml_contracts.payloads import TrainJobPayload

LIST_JOBS_OP: Final = "ml_list_jobs"
JOB_RESOURCE: Final = "trainingJob"
DATASET_VERSION_RESOURCE: Final = "datasetVersion"

TRAINING_START_TASK: Final = "ml.training.runner.start"
"""Task của runner B6-03b, gửi **theo tên** (hàng `ml.training` suy từ tiền tố)."""

NO_CANCEL_STATUSES: Final = ("cancelling", "cancelled")
"""N35 trên hai trạng thái này là 200 không tác dụng: không activity, không đặt lại TTL."""

CANCELLABLE_STATUSES: Final = ("queued", "running")
"""Hai trạng thái N35 đổi được; ba trạng thái cuối → 409."""


def _job_not_found() -> AppError:
    """404 `NOT_FOUND` `resource:"trainingJob"` — id sai mẫu cũng 404, không 422."""
    return NOT_FOUND.error(resource=JOB_RESOURCE)


async def _get_job(db: AsyncSession, job_id: str, *, for_update: bool = False) -> TrainingJobRow:
    """Một job; không có → 404. `for_update=True` chỉ cho N35 (đổi trạng thái dưới khoá)."""
    stmt = select(TrainingJobRow).where(TrainingJobRow.id == job_id)
    if for_update:
        stmt = stmt.with_for_update()
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise _job_not_found()
    return row


async def list_jobs(db: AsyncSession, *, family: str | None, status: str | None, page: PageParams) -> TrainingJobPage:
    """N32 — mới nhất trước, cursor `(created_at, id)`; `family`/`status` lạ → 422 `field`."""
    if family is not None and family not in TRAINABLE_FAMILIES:
        raise VALIDATION.error(field="family")
    if status is not None and status not in TRAINING_JOB_STATUSES:
        raise VALIDATION.error(field="status")
    filters = {"family": family, "status": status}
    stmt = select(TrainingJobRow)
    if family is not None:
        stmt = stmt.where(TrainingJobRow.family == family)
    if status is not None:
        stmt = stmt.where(TrainingJobRow.status == status)
    if page.cursor is not None:
        position = decode_cursor(page.cursor, LIST_JOBS_OP, filters)
        after = (datetime.fromisoformat(str(position["createdAt"])), str(position["id"]))
        stmt = stmt.where(tuple_(TrainingJobRow.created_at, TrainingJobRow.id) < after)
    stmt = stmt.order_by(desc(TrainingJobRow.created_at), desc(TrainingJobRow.id)).limit(page.limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    items = rows[: page.limit]
    more = len(rows) > page.limit
    last = {"createdAt": items[-1].created_at.isoformat(), "id": items[-1].id} if more else None
    return TrainingJobPage(
        items=[job_out(row) for row in items],
        next_cursor=encode_cursor(LIST_JOBS_OP, filters, last) if last is not None else None,
    )


async def read_job(db: AsyncSession, *, job_id: str) -> TrainingJobOut:
    """N34 — một job; không có hay id sai mẫu → 404 `resource:"trainingJob"`."""
    return job_out(await _get_job(db, job_id))


async def _ready_version(db: AsyncSession, *, dataset_version_id: str, family: str) -> DatasetVersionRow:
    """Bản dataset dùng được cho N33: có thật, `ready`, đúng họ — ba câu trả lời lỗi riêng.

    Đọc **không khoá**: bản `ready` không đổi nữa, nên khoá chỉ thêm tranh chấp ([6]).
    `manifest_sha256` vắng được xếp cùng "chưa `ready`" (CHECK của bảng buộc nó đi kèm
    `ready`, nên nhánh này chỉ là cổng kiểu cho `TrainJobPayload`).
    """
    stmt = (
        select(DatasetVersionRow, DatasetRow.family)
        .join(DatasetRow, DatasetRow.id == DatasetVersionRow.dataset_id)
        .where(DatasetVersionRow.id == dataset_version_id)
    )
    found = (await db.execute(stmt)).first()
    if found is None:
        raise NOT_FOUND.error(resource=DATASET_VERSION_RESOURCE)
    version, dataset_family = found
    if version.status != "ready" or version.manifest_sha256 is None:
        raise DATASET_VERSION_NOT_READY.error()
    if dataset_family != family:
        raise DATASET_FAMILY_MISMATCH.error()
    return version


async def create_job(
    db: AsyncSession,
    *,
    family: TrainableFamily,
    dataset_version_id: str,
    base_model: str,
    epochs: int,
    principal: Principal,
    clock: Clock,
) -> TrainingJobOut:
    """N33 — chèn `queued`, gửi `ml.training.runner.start` **sau commit** (K17).

    `creator_id` lấy từ `Principal` của request, không bao giờ từ thân (K05).
    """
    if base_model not in BASE_MODELS[family]:
        raise TRAINING_BASE_MODEL_MISMATCH.error()
    version = await _ready_version(db, dataset_version_id=dataset_version_id, family=family)
    now = clock.now()
    job = TrainingJobRow(
        id=new_id("job", clock),
        family=family,
        dataset_version_id=version.id,
        base_model=base_model,
        epochs=epochs,
        status="queued",
        creator_id=principal.user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.flush()
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.TRAINING_CREATE,
        object_code=job.id,
        object_label=family,
        clock=clock,
    )
    payload = TrainJobPayload(
        job_id=job.id,
        family=family,
        base_model=base_model,
        epochs=epochs,
        dataset_version_id=version.id,
        manifest_sha256=version.manifest_sha256,
    )
    on_after_commit(db, lambda: send_task(TRAINING_START_TASK, payload))
    return job_out(job)


async def _arm_cancel_key(job_id: str, settings: TrainingSettings) -> None:
    """Đặt `cancel_key` TTL `TRAINING_CANCEL_TTL_S`; Redis lỗi → ngoại lệ (gọi trước commit).

    Client dựng tại chỗ chứ không lấy `app.state`: cầu nối và ba lịch cũng đặt khoá này
    bằng `safe_redis()`, và test "Redis dừng" đổi `REDIS_BROKER_URL` giữa phiên.
    """
    client = safe_redis()
    try:
        await client.set(cancel_key(job_id), "1", ex=settings.training_cancel_ttl_s)
    finally:
        await client.aclose()


async def cancel_job(db: AsyncSession, *, job_id: str, principal: Principal, clock: Clock) -> TrainingJobOut:
    """N35 — `queued` → `cancelled`, `running` → `cancelling`; cả hai đặt `cancel_key` trước commit.

    `cancelling|cancelled` → 200 không tác dụng (K18: không activity, không gia hạn TTL);
    `succeeded|failed` → 409 `TRAINING_JOB_NOT_CANCELLABLE`.
    """
    job = await _get_job(db, job_id, for_update=True)
    if job.status in NO_CANCEL_STATUSES:
        return job_out(job)
    if job.status not in CANCELLABLE_STATUSES:
        raise TRAINING_JOB_NOT_CANCELLABLE.error()
    if job.status == "queued":
        job.status = "cancelled"
        job.ended_at = clock.now()
    else:
        job.status = "cancelling"
    await _arm_cancel_key(job.id, get_training_settings())
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=ActivityKind.TRAINING_CANCEL,
        object_code=job.id,
        object_label=job.family,
        clock=clock,
    )
    return job_out(job)


def _past_late_window(job: TrainingJobRow, now: datetime, settings: TrainingSettings) -> bool:
    """Job đã kết thúc **quá** cửa sổ muộn — điều kiện cần cho `nextCursor` vắng."""
    if job.ended_at is None:
        return False
    return (now - job.ended_at).total_seconds() > settings.training_late_window_s


async def _held_step(db: AsyncSession, job: TrainingJobRow, now: datetime, settings: TrainingSettings) -> int | None:
    """Bước lớn nhất còn có thể nhận `split` khác, nên chưa được trả ([6] N36).

    Giữ khi job chưa kết thúc, hoặc đã kết thúc trong cửa sổ muộn mà bước lớn nhất chưa
    đủ `train` **và** `validation`. `None` = không giữ gì (trả hết tới bước cuối).
    """
    if _past_late_window(job, now, settings):
        return None
    top = (
        await db.execute(select(func.max(TrainingMetricRow.step)).where(TrainingMetricRow.job_id == job.id))
    ).scalar_one()
    if top is None:
        return None
    if job.ended_at is None:
        return int(top)
    splits = (
        await db.execute(
            select(TrainingMetricRow.split).where(TrainingMetricRow.job_id == job.id, TrainingMetricRow.step == top)
        )
    ).scalars()
    return int(top) if set(splits) != set(METRIC_SPLITS) else None


def _whole_steps(rows: Sequence[TrainingMetricRow], limit: int) -> list[TrainingMetricRow]:
    """`limit` hàng đầu, kéo thêm hết `split` của bước cuối trang.

    Cắt giữa một bước thì lượt sau (`since` = bước cuối trang) mất `split` còn lại vĩnh
    viễn, vì N36 loại trừ `since`.
    """
    page = list(rows[:limit])
    if not page:
        return page
    last_step = page[-1].step
    page.extend(row for row in rows[limit:] if row.step == last_step)
    return page


async def list_job_metrics(
    db: AsyncSession, *, job_id: str, since: int, limit: int, clock: Clock
) -> TrainingMetricPage:
    """N36 — `step > since`, sắp `(step, split)`; job đọc **trước** (404 trước mọi hàng)."""
    job = await _get_job(db, job_id)
    settings = get_training_settings()
    now = clock.now()
    held = await _held_step(db, job, now, settings)
    stmt = select(TrainingMetricRow).where(TrainingMetricRow.job_id == job.id, TrainingMetricRow.step > since)
    if held is not None:
        stmt = stmt.where(TrainingMetricRow.step < held)
    # `limit + splits + 1`: đủ để kéo trọn bước cuối trang (tối đa `splits - 1` hàng nữa)
    # **và** còn một hàng dư để biết phía sau còn dữ liệu (`nextCursor`).
    stmt = stmt.order_by(asc(TrainingMetricRow.step), asc(TrainingMetricRow.split)).limit(
        limit + len(METRIC_SPLITS) + 1
    )
    rows = list((await db.execute(stmt)).scalars().all())
    items = _whole_steps(rows, limit)
    position = items[-1].step if items else since
    exhausted = _past_late_window(job, now, settings) and len(rows) == len(items)
    return TrainingMetricPage(
        items=[metric_point_out(row) for row in items], next_cursor=None if exhausted else str(position)
    )


async def list_job_logs(db: AsyncSession, *, job_id: str, since: int, limit: int, clock: Clock) -> TrainingLogPage:
    """N37 — `seq > since`, sắp `seq`; `nextCursor` cùng luật cửa sổ muộn với N36.

    Không có luật "giữ hàng cuối" như N36: một `seq` là một dòng trọn vẹn, không chờ
    `split` thứ hai tới.
    """
    job = await _get_job(db, job_id)
    settings = get_training_settings()
    now = clock.now()
    stmt = (
        select(TrainingLogRow)
        .where(TrainingLogRow.job_id == job.id, TrainingLogRow.seq > since)
        .order_by(asc(TrainingLogRow.seq))
        .limit(limit + 1)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    items = rows[:limit]
    position = items[-1].seq if items else since
    exhausted = _past_late_window(job, now, settings) and len(rows) == len(items)
    return TrainingLogPage(items=[log_line_out(row) for row in items], next_cursor=None if exhausted else str(position))
