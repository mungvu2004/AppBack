"""Model dây của N32-N37 (B6-03a [2]) — gương `adminMl.ts`, HOP-DONG-MOI §8.

Ba luật của FE mà lớp này giữ thay cho `service.py`:

- **K01**: dây không bao giờ mang `lastHeartbeatAt`, `artifactsPurgedAt`, `requeueCount`
  — ba cột ấy là chuyện riêng của cầu nối và ba lịch;
- **K02/W2**: `currentEpoch`, `startedAt`, `endedAt`, `resultModelVersionId`,
  `failureCode` chỉ xuất khi có giá trị — `WireModel` bỏ trường `None` nên chúng tự
  rơi ra ở trạng thái chưa tới;
- `datasetVersionId` sai mẫu `dsv_` phải là 422 `VALIDATION` `field:"datasetVersionId"`
  (không 404): id nằm trong **thân** N33, nên nó là lỗi trường, không phải tài nguyên.
"""

from functools import partial
from typing import Annotated, cast

from pydantic import AfterValidator, Field

from apps.api.core.pagination import CursorPage
from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from packages.core.ids import check_id
from packages.db.models.admin_ml_jobs import EPOCHS_MAX, TrainingJobRow, TrainingLogRow, TrainingMetricRow
from packages.ml_contracts.families import TrainableFamily

DatasetVersionId = Annotated[str, AfterValidator(partial(check_id, "dsv"))]
"""`dsv_<ULID>` trong thân N33; `ValueError` của lõi thành 422 `field:"datasetVersionId"`."""

Epochs = Annotated[int, Field(ge=1, le=EPOCHS_MAX)]
"""1-300 như CHECK `epochs_range` của bảng và refine `TrainingJobSchema`."""


class TrainingJobOut(WireModel):
    """`TrainingJobSchema`: trường theo trạng thái, không cột của cầu nối (K01, K02)."""

    base_model: str
    created_at: WireDatetime
    creator_id: str
    current_epoch: int | None = None
    dataset_version_id: str
    ended_at: WireDatetime | None = None
    epochs: int
    failure_code: str | None = None
    family: TrainableFamily
    id: str
    result_model_version_id: str | None = None
    started_at: WireDatetime | None = None
    status: str


class TrainingMetricPointOut(WireModel):
    """`TrainingMetricPointSchema`: ít nhất một số đo; hai số đo lạ của họ khác vắng."""

    epoch: int
    iou: float | None = None
    loss: float | None = None
    map50: float | None = None
    recorded_at: WireDatetime
    split: str
    step: int


class TrainingLogLineOut(WireModel):
    """`TrainingLogLineSchema`: `message` đã dựng từ mẫu câu, không `dedupeSha` (K01)."""

    at: WireDatetime
    level: str
    message: str
    seq: int


TrainingJobPage = CursorPage[TrainingJobOut]
"""N32 — mới nhất trước, `(family, status)` gắn vào cursor."""

TrainingMetricPage = CursorPage[TrainingMetricPointOut]
"""N36 — `step` tăng; `nextCursor` là chuỗi số dùng lại làm `since`."""

TrainingLogPage = CursorPage[TrainingLogLineOut]
"""N37 — `seq` tăng; `nextCursor` cùng luật với N36."""


class CreateTrainingJobIn(WireRequest):
    """Thân N33; khoá lạ → 422 `VALIDATION` (C03).

    `baseModel` chỉ là `str` ở đây: nó phải ra 422 `TRAINING_BASE_MODEL_MISMATCH`
    (mã riêng của [2]), không phải 422 `VALIDATION` của một `Literal` — nên luật
    "thuộc `BASE_MODELS[family]`" nằm ở `service.create_job`.
    """

    base_model: str
    dataset_version_id: DatasetVersionId
    epochs: Epochs
    family: TrainableFamily


class CancelTrainingJobIn(WireRequest):
    """Thân N35 là `{}`; khoá lạ → 422 `VALIDATION` (C03), không bị bỏ qua."""


def job_out(row: TrainingJobRow) -> TrainingJobOut:
    """Dòng `training_jobs` → `TrainingJobOut`; bỏ `last_heartbeat_at`, `artifacts_purged_at`,
    `requeue_count`, `updated_at` (K01)."""
    return TrainingJobOut(
        base_model=row.base_model,
        created_at=row.created_at,
        creator_id=row.creator_id,
        current_epoch=row.current_epoch,
        dataset_version_id=row.dataset_version_id,
        ended_at=row.ended_at,
        epochs=row.epochs,
        failure_code=row.failure_code,
        family=cast("TrainableFamily", row.family),
        id=row.id,
        result_model_version_id=row.result_model_version_id,
        started_at=row.started_at,
        status=row.status,
    )


def metric_point_out(row: TrainingMetricRow) -> TrainingMetricPointOut:
    """Dòng `training_metrics` → `TrainingMetricPointOut`; bỏ `job_id` (đã ở đường dẫn)."""
    return TrainingMetricPointOut(
        epoch=row.epoch,
        iou=row.iou,
        loss=row.loss,
        map50=row.map50,
        recorded_at=row.recorded_at,
        split=row.split,
        step=row.step,
    )


def log_line_out(row: TrainingLogRow) -> TrainingLogLineOut:
    """Dòng `training_logs` → `TrainingLogLineOut`; bỏ `job_id`, `dedupe_sha` (K01)."""
    return TrainingLogLineOut(at=row.at, level=row.level, message=row.message, seq=row.seq)
