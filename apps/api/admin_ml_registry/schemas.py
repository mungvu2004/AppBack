"""Model dây của N23-N27 (B6-01 [2]) — gương `src/api/schemas/adminMl.ts`, HOP-DONG-MOI §8.

Ba luật của FE mà hai hàm chuyển ở cuối file giữ thay cho `service.py`/`upload.py`:

- **K01**: dây không bao giờ mang `weightsKey`, `pinnedName`, `evaluationAttempts`,
  `evaluationErrorCode` — bốn cột ấy là chuyện nội bộ của registry;
- **K02/W2**: trường vắng thì **vắng**, không `null`; `WireModel` bỏ trường `None` nên
  `metrics`, `trainingJobId`, `datasetVersionId`, `activeVersionId` tự rơi ra;
- `metrics` ⇔ `completed` và chứa **đúng** khoá `FAMILY_METRIC[family]` — dòng DB lệch luật
  ấy là lỗi dữ liệu, `ValueError` chứ không phải 422 của người gọi (CHECK của bảng đã chặn).
"""

from collections.abc import Mapping
from typing import Annotated, Final, cast

from pydantic import AfterValidator, Field

from apps.api.admin_ml_registry.registry import clean_label
from apps.api.core.pagination import CursorPage
from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from packages.db.models.admin_ml_registry import (
    SHA256_PATTERN,
    EvaluationStatus,
    ModelFamilyRow,
    ModelVersionRow,
    WeightsFormat,
)
from packages.ml_contracts.families import FAMILY_METRIC, ModelFamily

COMPLETED: Final = "completed"
"""Trạng thái duy nhất có `metrics` (bản sao luật ⇔ của `ModelVersionSchema`)."""


Label = Annotated[str, AfterValidator(clean_label)]
"""Nhãn người nhập; luật chuẩn hoá nằm ở `registry.clean_label` (một bản cho cả worker)."""
Sha256 = Annotated[str, Field(pattern=SHA256_PATTERN)]


class ModelMetricsOut(WireModel):
    """`ModelMetricsSchema`: ba khoá tuỳ chọn, thực tế đúng **một** khoá của họ có mặt."""

    cer: float | None = None
    iou: float | None = None
    map50: float | None = None


class ModelFamilyOut(WireModel):
    """`ModelFamilySchema`. Vắng `activeVersionId` = họ tường đang chạy đường cổ điển."""

    active_version_id: str | None = None
    family: ModelFamily
    revision: int


class ModelVersionOut(WireModel):
    """`ModelVersionSchema`: một bản trọng số như quản trị thấy nó."""

    checksum_sha256: str
    created_at: WireDatetime
    creator_id: str
    dataset_version_id: str | None = None
    evaluation_status: EvaluationStatus
    family: ModelFamily
    id: str
    label: str
    metrics: ModelMetricsOut | None = None
    training_job_id: str | None = None
    weights_format: WeightsFormat


ModelFamilyPage = CursorPage[ModelFamilyOut]
"""N23 — `ModelFamilyPageSchema`; đủ ba họ nên không bao giờ có `nextCursor`."""

ModelVersionPage = CursorPage[ModelVersionOut]
"""N25 — `ModelVersionPageSchema`, mới nhất trước."""


class SetActiveModelVersionBody(WireRequest):
    """Thân trong của N24: `versionId` **bắt buộc**, `null` là lựa chọn có chủ đích.

    Họ nằm trên đường dẫn, nên luật "`null` chỉ cho `wallSegmentation`" không kiểm được ở
    đây — `service.py` trả 422 `MODEL_VERSION_FAMILY_MISMATCH` (`adminMl.ts:30-34`).
    """

    version_id: str | None


class SetActiveModelVersionIn(WireRequest):
    """`{baseVersion, body}` của N24 (W20) — cùng dạng `versioned(...)` nhưng có kiểu tĩnh.

    Thiếu `baseVersion` bị khung chặn 428 trước Pydantic; khoá lạ ở vỏ ngoài hay trong `body`
    → 422 `VALIDATION` với `field` là khoá ấy (C03).
    """

    base_version: Annotated[int, Field(strict=True, ge=0)]
    body: SetActiveModelVersionBody


class CreateModelVersionMetadata(WireRequest):
    """Phần `metadata` của multipart N26; khoá lạ → 422 `VALIDATION` (C03).

    Không phải thân của route: `upload.py` tự giải JSON của phần thứ nhất rồi dựng lớp này,
    nên lỗi trường đi ra dưới dạng 422 có `field` do chính module ném.
    """

    checksum_sha256: Sha256
    family: ModelFamily
    label: Label
    weights_format: WeightsFormat


def metrics_out(family: str, metrics: Mapping[str, float] | None) -> ModelMetricsOut | None:
    """`metrics` của một bản → `ModelMetricsOut`, hay `None` khi bản chưa `completed`.

    Đòi đúng khoá của họ: một dòng mang `iou` cho họ `dimensionReading` sẽ qua CHECK của bảng
    (nó chỉ kiểm `metrics` ⇔ `completed`) nhưng làm zod của FE từ chối cả trang, nên chặn ở đây.
    """
    if metrics is None:
        return None
    expected = FAMILY_METRIC[cast("ModelFamily", family)]
    if set(metrics) != {expected}:
        raise ValueError(f"metrics của họ {family} phải có đúng khoá {expected!r}, nhận {sorted(metrics)}")
    return ModelMetricsOut(**{expected: float(metrics[expected])})


def version_out(row: ModelVersionRow) -> ModelVersionOut:
    """Dòng `model_versions` → `ModelVersionOut`; bỏ mọi cột nội bộ (K01).

    `family`, `evaluation_status`, `weights_format` `cast` về `Literal`: nơi bảo đảm tập giá
    trị là CHECK của bảng, không phải kiểu Python của cột `Text`.
    """
    return ModelVersionOut(
        checksum_sha256=row.checksum_sha256,
        created_at=row.created_at,
        creator_id=row.creator_id,
        dataset_version_id=row.dataset_version_id,
        evaluation_status=cast("EvaluationStatus", row.evaluation_status),
        family=cast("ModelFamily", row.family),
        id=row.id,
        label=row.label,
        metrics=metrics_out(row.family, row.metrics),
        training_job_id=row.training_job_id,
        weights_format=cast("WeightsFormat", row.weights_format),
    )


def family_out(row: ModelFamilyRow) -> ModelFamilyOut:
    """Dòng `model_families` → `ModelFamilyOut`; `active_version_id` NULL thì khoá vắng (W2)."""
    return ModelFamilyOut(
        active_version_id=row.active_version_id,
        family=cast("ModelFamily", row.family),
        revision=row.revision,
    )
