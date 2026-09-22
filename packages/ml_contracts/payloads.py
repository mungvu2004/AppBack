"""Payload task ML: suy luận theo bước, đánh giá phiên bản, huấn luyện (BE-00 §7, §9).

Mọi payload đi qua hàng đợi là **không tin** (worker `ml` không được tin, B5-06c kiểm
lượt dưới khoá): id đúng tiền tố qua `is_id`, SHA-256 64 hex thường, khoá object theo
luật B0-04, và mọi luật chéo trường ở validator. Sai → `ValidationError`; `define_task`
coi đó là thông điệp độc (J08).

Luật khoá object lấy từ `packages.core.object_keys` — cùng một nguồn với `packages.storage`
(gói không được nhập `storage`, [9] B5-01; NO-060).
"""

import itertools
import math
import re
from collections.abc import Mapping
from typing import Annotated, Final, Literal, Self, get_args

from pydantic import AfterValidator, Field, model_validator

from packages.core.ids import IdPrefix, is_id, is_spatial_id
from packages.core.object_keys import check_key, check_prefix
from packages.ml_contracts.artifacts import MASK_MAX_PIXELS, FrozenModel
from packages.ml_contracts.families import BASE_MODELS, MetricName, ModelFamily, TrainableFamily
from packages.ml_contracts.pinned import PINNED

MODELS_PREFIX: Final = "ml/models/"
MAX_ARTIFACT_KEYS: Final = 8
MAX_METRIC_POINTS: Final = 500
MAX_LOG_PARAMS: Final = 16
MAX_LOG_PARAM_CHARS: Final = 200

StepId = ModelFamily | Literal["spatialDataBuild"]
_METRIC_NAMES: Final = frozenset(get_args(MetricName))
_UNIT_METRICS: Final = frozenset({"iou", "map50"})


def _id_of(prefix: IdPrefix) -> AfterValidator:
    """Validator `<tiền tố>_<ULID>` qua `packages.core.ids.is_id`."""

    def check(value: str) -> str:
        """Trả lại chính id khi đúng mẫu; sai → `ValueError` (Pydantic đổi thành lỗi trường)."""
        if not is_id(prefix, value):
            raise ValueError(f"id phải có dạng {prefix}_<ULID>")
        return value

    return AfterValidator(check)


RunId = Annotated[str, _id_of("run")]
ModelVersionId = Annotated[str, _id_of("mdl")]
JobId = Annotated[str, _id_of("job")]
DatasetVersionId = Annotated[str, _id_of("dsv")]
ObjectKey = Annotated[str, AfterValidator(check_key)]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ErrorCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{2,63}$")]
Millis = Annotated[int, Field(ge=0)]
UnitMetric = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class MlPayload(FrozenModel):
    """Gốc mọi payload ML; `schema_version` là số `define_task` so (J08)."""

    schema_version: Literal[1] = 1


def check_metrics(metrics: Mapping[str, float]) -> None:
    """Đúng một số đo `iou|map50|cer`, hữu hạn; `iou`/`map50` trong `[0, 1]`, `cer ≥ 0` (HOP-DONG-MOI §8)."""
    if len(metrics) != 1 or not set(metrics) <= _METRIC_NAMES:
        raise ValueError("metrics phải có đúng một khoá iou | map50 | cer")
    ((name, value),) = metrics.items()
    if not math.isfinite(value) or value < 0 or (name in _UNIT_METRICS and value > 1):
        raise ValueError(f"số đo {name} ngoài dải: {value}")


class ModelRef(FrozenModel):
    """Model của một bước, ghim ở đầu lượt pipeline (BE-00 §9). Đúng một trong ba dạng.

    - **cổ điển**: `version_id`, `weights_key`, `pinned_name` đều `None`, `checksum_sha256 = ""`
      (họ tường chưa có bản kích hoạt: đường lùi `classic_wall_mask`);
    - **ghim**: `pinned_name` ∈ `PINNED`, cùng họ, có ONNX (`onnx_sha256` khác `None`);
    - **storage**: `weights_key` dưới `ml/models/{version_id}/`.
    """

    version_id: ModelVersionId | None
    family: ModelFamily
    weights_key: ObjectKey | None
    pinned_name: str | None
    checksum_sha256: str

    @property
    def is_classic(self) -> bool:
        """Không có model nào để nạp."""
        return self.pinned_name is None and self.weights_key is None

    @model_validator(mode="after")
    def _one_form(self) -> Self:
        """Đúng một dạng; dạng có model phải có `version_id` và checksum 64 hex."""
        if self.is_classic:
            if self.version_id is not None or self.checksum_sha256 != "":
                raise ValueError("dạng cổ điển không có version_id và checksum rỗng")
            return self
        if self.version_id is None or not re.fullmatch(r"[0-9a-f]{64}", self.checksum_sha256):
            raise ValueError("model ghim hay storage cần version_id và checksum 64 hex thường")
        if self.pinned_name is not None and self.weights_key is not None:
            raise ValueError("chỉ một trong pinned_name, weights_key")
        if self.pinned_name is not None:
            pin = PINNED.get(self.pinned_name)
            if pin is None or pin.family != self.family or pin.onnx_sha256 is None:
                raise ValueError(f"bản ghim {self.pinned_name!r} không có ONNX cho họ {self.family}")
        elif not str(self.weights_key).startswith(f"{MODELS_PREFIX}{self.version_id}/"):
            raise ValueError("weights_key phải nằm dưới ml/models/{version_id}/")
        return self


def _upload_prefix(key: str) -> str:
    """`projects/{prj}/floors/{L-…}/uploads/{upl}/` đứng đầu khoá; sai → `ValueError`."""
    parts = key.split("/")
    if (
        len(parts) < 7
        or parts[0::2][:3] != ["projects", "floors", "uploads"]
        or not is_id("prj", parts[1])
        or not is_spatial_id("level", parts[3])
        or not is_id("upl", parts[5])
    ):
        raise ValueError(f"khoá không nằm dưới một lượt tải lên: {key!r}")
    return "/".join(parts[:6]) + "/"


class InferStepPayload(MlPayload):
    """Một bước suy luận trên trang đã nắn (task `ml.infer.*`, B5-02…B5-04)."""

    run_id: RunId
    step: ModelFamily
    page_key: ObjectKey
    width_px: Annotated[int, Field(ge=1)]
    height_px: Annotated[int, Field(ge=1)]
    artifact_prefix: Annotated[str, AfterValidator(check_prefix)]
    model: ModelRef
    px_per_paper_mm: Annotated[float, Field(ge=1, le=100, allow_inf_nan=False)] | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        """Bước = họ model; trang và artifact cùng lượt tải lên; khổ trong trần mặt nạ."""
        if self.step != self.model.family:
            raise ValueError("step phải trùng model.family")
        expected = f"{_upload_prefix(self.page_key)}runs/{self.run_id}/{self.step}/"
        if self.artifact_prefix != expected:
            raise ValueError("artifact_prefix phải là <lượt tải lên>/runs/{run_id}/{step}/ của chính trang")
        if self.width_px * self.height_px > MASK_MAX_PIXELS:
            raise ValueError(f"khổ trang vượt {MASK_MAX_PIXELS} điểm")
        return self


class StepResultPayload(MlPayload):
    """Kết quả một bước gửi `pipeline.orchestrate.step_done` (B5-06c); B5-05 gửi cả `spatialDataBuild`."""

    run_id: RunId
    step: StepId
    status: Literal["completed", "failed"]
    artifact_keys: Annotated[tuple[ObjectKey, ...], Field(max_length=MAX_ARTIFACT_KEYS)] = ()
    error_code: ErrorCode | None = None
    model_version_id: ModelVersionId | None = None
    duration_ms: Millis

    @model_validator(mode="after")
    def _status_rules(self) -> Self:
        """`failed` ⇔ có mã, và khi đó không có khoá; khoá sắp tăng ngặt (không trùng)."""
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("failed ⇔ có error_code")
        if self.status == "failed" and self.artifact_keys:
            raise ValueError("bước failed không có artifact")
        if any(a >= b for a, b in itertools.pairwise(self.artifact_keys)):
            raise ValueError("artifact_keys phải sắp tăng, không trùng")
        return self


class EvaluateVersionPayload(MlPayload):
    """Đánh giá một phiên bản model trên tập kiểm cố định (B6-01 gửi, B6-04b chạy)."""

    version_id: ModelVersionId
    model: ModelRef

    @model_validator(mode="after")
    def _matches(self) -> Self:
        """Model phải là chính phiên bản cần đánh giá, và phải có trọng số."""
        if self.model.is_classic or self.model.version_id != self.version_id:
            raise ValueError("model phải có trọng số và cùng version_id")
        return self


class EvaluationDonePayload(MlPayload):
    """Kết quả đánh giá: `completed` ⇒ đúng một số đo; `failed` ⇒ chỉ mã."""

    version_id: ModelVersionId
    status: Literal["completed", "failed"]
    metrics: dict[str, float] | None = None
    error_code: ErrorCode | None = None

    @model_validator(mode="after")
    def _status_rules(self) -> Self:
        """Số đo và mã loại trừ nhau theo trạng thái."""
        if self.status == "completed":
            if self.metrics is None or self.error_code is not None:
                raise ValueError("completed cần metrics, không mã")
            check_metrics(self.metrics)
        elif self.metrics is not None or self.error_code is None:
            raise ValueError("failed chỉ mang error_code")
        return self


class TrainJobPayload(MlPayload):
    """Khởi chạy một job huấn luyện (hàng `ml.training`)."""

    job_id: JobId
    family: TrainableFamily
    base_model: str
    epochs: Annotated[int, Field(ge=1, le=300)]
    dataset_version_id: DatasetVersionId
    manifest_sha256: Sha256

    @model_validator(mode="after")
    def _base_of_family(self) -> Self:
        """`base_model` phải thuộc họ (HOP-DONG-MOI §8 `TRAINING_BASE_MODELS`)."""
        if self.base_model not in BASE_MODELS[self.family]:
            raise ValueError(f"base_model {self.base_model!r} không thuộc họ {self.family}")
        return self


class TrainingHeartbeatPayload(MlPayload):
    """Nhịp tim tiến trình huấn luyện (J07 dựa vào nó)."""

    job_id: JobId
    epoch: Annotated[int, Field(ge=0)]
    sent_at_ms: Millis


class MetricPoint(FrozenModel):
    """Một điểm số đo; ít nhất một số đo, `loss ≥ 0`, `iou`/`map50` trong `[0, 1]`."""

    step: Annotated[int, Field(ge=0)]
    epoch: Annotated[int, Field(ge=1)]
    split: Literal["train", "validation"]
    recorded_at_ms: Millis
    loss: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    iou: UnitMetric | None = None
    map50: UnitMetric | None = None

    @model_validator(mode="after")
    def _has_value(self) -> Self:
        """Điểm không số đo nào thì FE không vẽ được (`TrainingMetricPointSchema`)."""
        if self.loss is None and self.iou is None and self.map50 is None:
            raise ValueError("cần ít nhất một số đo")
        return self


class TrainingMetricsPayload(MlPayload):
    """Lô số đo: 1-500 điểm, `step` tăng ngặt trong từng `split` (M05)."""

    job_id: JobId
    points: Annotated[tuple[MetricPoint, ...], Field(min_length=1, max_length=MAX_METRIC_POINTS)]

    @model_validator(mode="after")
    def _monotonic(self) -> Self:
        """Bước lùi hay lặp trong cùng split là số đo hỏng, cầu nối không được ghi."""
        last: dict[str, int] = {}
        for point in self.points:
            if point.step <= last.get(point.split, -1):
                raise ValueError(f"step phải tăng ngặt trong split {point.split}")
            last[point.split] = point.step
        return self


def _param_value(value: str | int | float | bool) -> str | int | float | bool:
    """Tham số log: chuỗi ≤ 200 ký tự in được, số hữu hạn (BE-00 §9 mẫu log)."""
    if isinstance(value, str) and (len(value) > MAX_LOG_PARAM_CHARS or not value.isprintable()):
        raise ValueError(f"tham số chuỗi phải in được và ≤ {MAX_LOG_PARAM_CHARS} ký tự")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("tham số số phải hữu hạn")
    return value


LogKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")]
LogValue = Annotated[str | int | float | bool, AfterValidator(_param_value)]


class TrainingLogPayload(MlPayload):
    """Một dòng log huấn luyện: khoá mẫu câu + tham số; câu tiếng Việt dựng ở B6-03a."""

    job_id: JobId
    level: Literal["info", "warning", "error"]
    template: LogKey
    params: Annotated[dict[LogKey, LogValue], Field(max_length=MAX_LOG_PARAMS)]


class TrainingFinishedPayload(MlPayload):
    """Kết thúc job: `succeeded` ⇒ trọng số `.onnx` + checksum + một số đo; `failed` ⇒ chỉ mã."""

    job_id: JobId
    status: Literal["succeeded", "failed", "cancelled"]
    weights_key: ObjectKey | None = None
    checksum_sha256: Sha256 | None = None
    metrics: dict[str, float] | None = None
    error_code: ErrorCode | None = None

    @model_validator(mode="after")
    def _status_rules(self) -> Self:
        """Mỗi trạng thái mang đúng bộ trường của nó; `cancelled` không mang gì."""
        produced = (self.weights_key, self.checksum_sha256, self.metrics)
        if self.status == "succeeded":
            key = self.weights_key or ""
            if self.error_code is not None or not (key.startswith(MODELS_PREFIX) and key.endswith(".onnx")):
                raise ValueError("succeeded cần weights_key .onnx dưới ml/models/, không mã")
            if self.checksum_sha256 is None or self.metrics is None:
                raise ValueError("succeeded cần checksum_sha256 và metrics")
            check_metrics(self.metrics)
        elif any(value is not None for value in produced) or (self.status == "failed") != (self.error_code is not None):
            raise ValueError(f"{self.status} không mang trọng số/số đo; failed ⇔ có error_code")
        return self
