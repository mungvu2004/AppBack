"""Payload task ML: mỗi luật một ca hỏng và một ca đạt; M05 số đo đơn điệu theo split."""

from collections.abc import Callable
from typing import Any, get_args

import pytest
from pydantic import ValidationError

from packages.core import object_keys
from packages.core.clock import SystemClock
from packages.core.ids import IdPrefix, new_id
from packages.core.object_keys import check_key, check_prefix
from packages.ml_contracts.payloads import (
    EvaluateVersionPayload,
    EvaluationDonePayload,
    InferStepPayload,
    MetricPoint,
    ModelRef,
    ObjectKey,
    StepResultPayload,
    TrainingFinishedPayload,
    TrainingHeartbeatPayload,
    TrainingLogPayload,
    TrainingMetricsPayload,
    TrainJobPayload,
)
from packages.ml_contracts.pinned import PINNED

SHA = "a" * 64


def some_id(prefix: IdPrefix) -> str:
    return new_id(prefix, SystemClock())


MDL = some_id("mdl")
RUN = some_id("run")
JOB = some_id("job")
UPLOAD = f"projects/{some_id('prj')}/floors/L-ABCDEFGHIJ/uploads/{some_id('upl')}/"
OTHER_UPLOAD = f"projects/{some_id('prj')}/floors/L-ABCDEFGHIJ/uploads/{some_id('upl')}/"


def classic(family: str = "wallSegmentation") -> ModelRef:
    return ModelRef(version_id=None, family=family, weights_key=None, pinned_name=None, checksum_sha256="")


def pinned_ref(name: str = "yolov8n") -> ModelRef:
    pin = PINNED[name]
    return ModelRef(
        version_id=MDL, family=pin.family, weights_key=None, pinned_name=name, checksum_sha256=str(pin.onnx_sha256)
    )


def storage_ref(family: str = "wallSegmentation", key: str | None = None) -> ModelRef:
    return ModelRef(
        version_id=MDL,
        family=family,
        weights_key=key or f"ml/models/{MDL}/model.onnx",
        pinned_name=None,
        checksum_sha256=SHA,
    )


def infer(**changes: Any) -> InferStepPayload:
    fields: dict[str, Any] = {
        "run_id": RUN,
        "step": "wallSegmentation",
        "page_key": f"{UPLOAD}pages/0.png",
        "width_px": 1600,
        "height_px": 1200,
        "artifact_prefix": f"{UPLOAD}runs/{RUN}/wallSegmentation/",
        "model": classic(),
    }
    return InferStepPayload(**(fields | changes))


# --- khoá object ----------------------------------------------------------------------


def test_object_key_rules_come_from_core() -> None:
    """NO-060: khoá và tiền tố khoá của payload đi qua đúng luật của `packages.core.object_keys`.

    Một nguồn với `packages.storage`; mẫu biên của luật nằm ở `packages/core/tests/test_object_keys.py`.
    """
    assert [validator.func for validator in get_args(ObjectKey)[1:]] == [check_key]
    prefix_validators = InferStepPayload.model_fields["artifact_prefix"].metadata
    assert [validator.func for validator in prefix_validators] == [check_prefix]
    with pytest.raises(ValidationError, match="khoá có đoạn rỗng"):
        infer(page_key=f"{UPLOAD}pages//0.png")


def test_upload_layout_comes_from_core(monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-077: trang và artifact cùng lượt tải lên kiểm bằng bố cục của `packages.core.object_keys`.

    Đột biến hàm dựng tiền tố lượt tải lên của lõi thì payload hợp lệ bị từ chối — gói không giữ
    bản tách riêng. Mẫu biên của bố cục nằm ở `packages/core/tests/test_object_keys.py`.
    """
    infer()
    monkeypatch.setattr(object_keys, "upload_prefix", lambda *_: "khac/")
    with pytest.raises(ValidationError, match="không nằm dưới một lượt tải lên"):
        infer()


# --- ModelRef -------------------------------------------------------------------------


def test_model_ref_forms_accept() -> None:
    assert classic().is_classic
    assert not pinned_ref("rapidocrRec").is_classic
    assert storage_ref().weights_key == f"ml/models/{MDL}/model.onnx"


@pytest.mark.parametrize(
    "build",
    [
        lambda: ModelRef(
            version_id=MDL, family="wallSegmentation", weights_key=None, pinned_name=None, checksum_sha256=""
        ),
        lambda: ModelRef(
            version_id=None, family="wallSegmentation", weights_key=None, pinned_name=None, checksum_sha256=SHA
        ),
        lambda: ModelRef(
            version_id=None, family="dimensionReading", weights_key=None, pinned_name="rapidocrRec", checksum_sha256=SHA
        ),
        lambda: ModelRef(
            version_id=MDL,
            family="dimensionReading",
            weights_key=None,
            pinned_name="rapidocrRec",
            checksum_sha256="A" * 64,
        ),
        lambda: ModelRef(
            version_id=MDL,
            family="wallSegmentation",
            weights_key=f"ml/models/{MDL}/m.onnx",
            pinned_name="mitB0",
            checksum_sha256=SHA,
        ),
        lambda: ModelRef(
            version_id=MDL, family="wallSegmentation", weights_key=None, pinned_name="mitB0", checksum_sha256=SHA
        ),
        lambda: ModelRef(
            version_id=MDL, family="dimensionReading", weights_key=None, pinned_name="yolov8n", checksum_sha256=SHA
        ),
        lambda: ModelRef(
            version_id=MDL, family="dimensionReading", weights_key=None, pinned_name="nope", checksum_sha256=SHA
        ),
        lambda: storage_ref(key=f"ml/models/{some_id('mdl')}/model.onnx"),
        lambda: storage_ref(key=f"ml/models/{MDL}/../x"),
        lambda: ModelRef(
            version_id="mdl_bad", family="wallSegmentation", weights_key=None, pinned_name=None, checksum_sha256=""
        ),
    ],
)
def test_model_ref_rejects(build: Callable[[], ModelRef]) -> None:
    with pytest.raises(ValidationError):
        build()


# --- InferStepPayload ------------------------------------------------------------------


def test_infer_step_accepts() -> None:
    payload = infer(px_per_paper_mm=100)
    assert payload.schema_version == 1
    infer(width_px=8000, height_px=5000)
    infer(
        step="openingAndFurnitureDetection",
        model=pinned_ref(),
        artifact_prefix=f"{UPLOAD}runs/{RUN}/openingAndFurnitureDetection/",
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"step": "dimensionReading"},
        {"artifact_prefix": f"{UPLOAD}runs/{RUN}/wallSegmentation"},
        {"artifact_prefix": f"{UPLOAD}runs/{some_id('run')}/wallSegmentation/"},
        {"artifact_prefix": f"{OTHER_UPLOAD}runs/{RUN}/wallSegmentation/"},
        {"page_key": "library/x/pages/0.png"},
        {"page_key": f"projects/{some_id('prj')}/floors/bad/uploads/{some_id('upl')}/pages/0.png"},
        {"page_key": f"{UPLOAD}pages/../0.png"},
        {"width_px": 0},
        {"width_px": 8001, "height_px": 5000},
        {"px_per_paper_mm": 0.5},
        {"px_per_paper_mm": float("nan")},
        {"run_id": "run_1"},
        {"schema_version": 2},
        {"unexpected": 1},
    ],
)
def test_infer_step_rejects(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        infer(**changes)


# --- StepResultPayload -----------------------------------------------------------------

KEYS = (f"{UPLOAD}runs/{RUN}/wallSegmentation/walls.json", f"{UPLOAD}runs/{RUN}/wallSegmentation/walls.png")


def test_step_result_accepts() -> None:
    StepResultPayload(run_id=RUN, step="wallSegmentation", status="completed", artifact_keys=KEYS, duration_ms=0)
    StepResultPayload(run_id=RUN, step="spatialDataBuild", status="failed", error_code="FILE_CORRUPT", duration_ms=5)
    StepResultPayload(run_id=RUN, step="dimensionReading", status="completed", model_version_id=MDL, duration_ms=1)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"error_code": "FILE_CORRUPT"},
        {"status": "failed", "error_code": "FILE_CORRUPT", "artifact_keys": KEYS},
        {"artifact_keys": KEYS[::-1]},
        {"artifact_keys": (KEYS[0], KEYS[0])},
        {"artifact_keys": tuple(f"k/{index}" for index in range(9))},
        {"error_code": "bad", "status": "failed"},
        {"step": "preprocess"},
        {"duration_ms": -1},
        {"model_version_id": "mdl_x"},
    ],
)
def test_step_result_rejects(changes: dict[str, Any]) -> None:
    fields: dict[str, Any] = {"run_id": RUN, "step": "wallSegmentation", "status": "completed", "duration_ms": 1}
    with pytest.raises(ValidationError):
        StepResultPayload(**(fields | changes))


# --- đánh giá --------------------------------------------------------------------------


def test_evaluate_version_rules() -> None:
    EvaluateVersionPayload(version_id=MDL, model=storage_ref())
    with pytest.raises(ValidationError, match="version_id"):
        EvaluateVersionPayload(version_id=some_id("mdl"), model=storage_ref())
    with pytest.raises(ValidationError, match="trọng số"):
        EvaluateVersionPayload(version_id=MDL, model=classic())


@pytest.mark.parametrize(
    ("status", "metrics", "code", "ok"),
    [
        ("completed", {"iou": 1.0}, None, True),
        ("completed", {"cer": 3.5}, None, True),
        ("failed", None, "MODEL_FORMAT_UNSUPPORTED", True),
        ("completed", {"iou": 0.5, "map50": 0.5}, None, False),
        ("completed", {}, None, False),
        ("completed", {"loss": 0.5}, None, False),
        ("completed", {"iou": 1.5}, None, False),
        ("completed", {"cer": -0.1}, None, False),
        ("completed", {"map50": float("inf")}, None, False),
        ("completed", None, None, False),
        ("completed", {"iou": 0.5}, "X_Y", False),
        ("failed", {"iou": 0.5}, "MODEL_FORMAT_UNSUPPORTED", False),
        ("failed", None, None, False),
    ],
)
def test_evaluation_done_rules(status: str, metrics: dict[str, float] | None, code: str | None, ok: bool) -> None:
    def build() -> EvaluationDonePayload:
        return EvaluationDonePayload(version_id=MDL, status=status, metrics=metrics, error_code=code)

    if ok:
        build()
    else:
        with pytest.raises(ValidationError):
            build()


# --- huấn luyện ------------------------------------------------------------------------


def test_train_job_rules() -> None:
    fields: dict[str, Any] = {
        "job_id": JOB,
        "family": "openingAndFurnitureDetection",
        "base_model": "yolov8s",
        "epochs": 300,
        "dataset_version_id": some_id("dsv"),
        "manifest_sha256": SHA,
    }
    TrainJobPayload(**fields)
    for changes in (
        {"base_model": "mitB0"},
        {"family": "dimensionReading"},
        {"epochs": 0},
        {"epochs": 301},
        {"manifest_sha256": "A" * 64},
        {"dataset_version_id": some_id("dst")},
    ):
        with pytest.raises(ValidationError):
            TrainJobPayload(**(fields | changes))


def test_heartbeat_rules() -> None:
    TrainingHeartbeatPayload(job_id=JOB, epoch=0, sent_at_ms=0)
    with pytest.raises(ValidationError):
        TrainingHeartbeatPayload(job_id=JOB, epoch=-1, sent_at_ms=0)


def point(step: int, split: str = "train", **values: Any) -> MetricPoint:
    return MetricPoint(step=step, epoch=1, split=split, recorded_at_ms=10, **(values or {"loss": 0.5}))


def test_training_metrics_payload_m05() -> None:
    """Bước tăng ngặt trong từng split; hai split đan nhau được; mọi điểm có mốc thời gian."""
    batch = TrainingMetricsPayload(
        job_id=JOB, points=(point(0), point(0, "validation"), point(1), point(3, "validation"))
    )
    assert [p.recorded_at_ms for p in batch.points] == [10, 10, 10, 10]
    for points in ((point(1), point(1)), (point(2), point(1)), (point(2, "validation"), point(1, "validation"))):
        with pytest.raises(ValidationError, match="tăng ngặt"):
            TrainingMetricsPayload(job_id=JOB, points=points)
    with pytest.raises(ValidationError):
        TrainingMetricsPayload(job_id=JOB, points=())
    with pytest.raises(ValidationError):
        TrainingMetricsPayload(job_id=JOB, points=tuple(point(step) for step in range(501)))
    TrainingMetricsPayload(job_id=JOB, points=tuple(point(step) for step in range(500)))


@pytest.mark.parametrize(
    ("values", "ok"),
    [
        ({"loss": 0.0}, True),
        ({"iou": 1.0, "map50": 0.0}, True),
        ({}, False),
        ({"loss": -0.1}, False),
        ({"loss": float("nan")}, False),
        ({"iou": 1.1}, False),
        ({"map50": -0.1}, False),
    ],
)
def test_metric_point_values(values: dict[str, Any], ok: bool) -> None:
    def build() -> MetricPoint:
        return MetricPoint(step=0, epoch=1, split="train", recorded_at_ms=0, **values)

    if ok:
        build()
    else:
        with pytest.raises(ValidationError):
            build()


def test_metric_point_epoch_starts_at_one() -> None:
    with pytest.raises(ValidationError):
        MetricPoint(step=0, epoch=0, split="train", recorded_at_ms=0, loss=1)


@pytest.mark.parametrize(
    ("template", "params", "ok"),
    [
        ("training_started", {"base_model": "yolov8n", "train": 10, "ratio": 0.5, "fast": True}, True),
        ("training_failed", {}, True),
        ("x" * 64, {}, True),
        ("x" * 65, {}, False),
        ("Training", {}, False),
        ("1abc", {}, False),
        ("ok", {"k": "x" * 201}, False),
        ("ok", {"k": "a\nb"}, False),
        ("ok", {"k": float("inf")}, False),
        ("ok", {"K": 1}, False),
        ("ok", {f"k{i}": i for i in range(17)}, False),
        ("ok", {"k": [1]}, False),
    ],
)
def test_training_log_rules(template: str, params: dict[str, Any], ok: bool) -> None:
    def build() -> TrainingLogPayload:
        return TrainingLogPayload(job_id=JOB, level="info", template=template, params=params)

    if ok:
        assert build().params == params
    else:
        with pytest.raises(ValidationError):
            build()


@pytest.mark.parametrize(
    ("changes", "ok"),
    [
        (
            {
                "status": "succeeded",
                "weights_key": "ml/models/a/w.onnx",
                "checksum_sha256": SHA,
                "metrics": {"map50": 0.4},
            },
            True,
        ),
        ({"status": "failed", "error_code": "DATASET_SPLIT_EMPTY"}, True),
        ({"status": "cancelled"}, True),
        (
            {"status": "succeeded", "weights_key": "ml/models/a/w.pt", "checksum_sha256": SHA, "metrics": {"iou": 0.4}},
            False,
        ),
        (
            {
                "status": "succeeded",
                "weights_key": "ml/datasets/a/w.onnx",
                "checksum_sha256": SHA,
                "metrics": {"iou": 0.4},
            },
            False,
        ),
        ({"status": "succeeded", "weights_key": "ml/models/a/w.onnx", "metrics": {"iou": 0.4}}, False),
        ({"status": "succeeded", "weights_key": "ml/models/a/w.onnx", "checksum_sha256": SHA}, False),
        ({"status": "succeeded", "checksum_sha256": SHA, "metrics": {"iou": 0.4}}, False),
        (
            {
                "status": "succeeded",
                "weights_key": "ml/models/a/w.onnx",
                "checksum_sha256": SHA,
                "metrics": {"iou": 0.4},
                "error_code": "BOOM",
            },
            False,
        ),
        ({"status": "failed"}, False),
        ({"status": "failed", "error_code": "BOOM", "metrics": {"iou": 0.4}}, False),
        ({"status": "cancelled", "error_code": "BOOM"}, False),
        ({"status": "cancelled", "checksum_sha256": SHA}, False),
    ],
)
def test_training_finished_rules(changes: dict[str, Any], ok: bool) -> None:
    def build() -> TrainingFinishedPayload:
        return TrainingFinishedPayload(job_id=JOB, **changes)

    if ok:
        build()
    else:
        with pytest.raises(ValidationError):
            build()
