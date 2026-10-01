"""Factory job huấn luyện cho test (B6-03a), theo mẫu `packages/testing/factories/admin_ml_datasets.py`.

Ghi thẳng `training_jobs`, không qua N33: test cần mọi trạng thái (`running` có `started_at`,
`failed` có `failure_code`, `succeeded` có bản model) mà một lượt API thật không dựng được.
Mọi CHECK của bảng được tôn trọng; `succeeded` cần `result_model_version_id` của một bản có
thật (`make_model_version`) — truyền vào, factory không tự dựng.

Có `commit`: route/worker đọc bằng session khác. `created_at`/`updated_at` đặt tường minh để
test phân trang và lịch (`updated_at` của `requeue_training_jobs`) xếp được thứ tự.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.errors import SYSTEM_PIPELINE
from packages.core.ids import new_id
from packages.db.models.admin_ml_jobs import FINISHED_STATUSES, TrainingJobRow
from packages.ml_contracts.families import BASE_MODELS, TrainableFamily

_STARTED_STATUSES = frozenset({"running", "cancelling", "succeeded"})


async def make_training_job(
    db: AsyncSession,
    *,
    dataset_version_id: str,
    family: TrainableFamily = "openingAndFurnitureDetection",
    status: str = "queued",
    base_model: str | None = None,
    epochs: int = 3,
    current_epoch: int | None = None,
    result_model_version_id: str | None = None,
    failure_code: str | None = None,
    creator_id: str | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    last_heartbeat_at: datetime | None = None,
    requeue_count: int = 0,
) -> TrainingJobRow:
    """Một dòng `training_jobs` đã `commit`, tôn trọng CHECK theo `status`.

    `running|cancelling|succeeded` tự đặt `started_at = created_at` nếu không truyền; trạng
    thái cuối tự đặt `ended_at`; `failed` tự điền `failure_code` giả. `base_model` mặc định
    là model gốc đầu tiên của họ.
    """
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    start = started_at if started_at is not None or status not in _STARTED_STATUSES else at
    end = ended_at if ended_at is not None or status not in FINISHED_STATUSES else (start or at)
    code = failure_code if failure_code is not None or status != "failed" else "TRAINING_HEARTBEAT_LOST"
    row = TrainingJobRow(
        id=new_id("job", clock),
        family=family,
        dataset_version_id=dataset_version_id,
        base_model=base_model if base_model is not None else BASE_MODELS[family][0],
        epochs=epochs,
        status=status,
        current_epoch=current_epoch,
        result_model_version_id=result_model_version_id,
        failure_code=code,
        started_at=start,
        ended_at=end,
        last_heartbeat_at=last_heartbeat_at,
        requeue_count=requeue_count,
        creator_id=creator_id if creator_id is not None else SYSTEM_PIPELINE,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.commit()
    return row
