"""Test `apps.ml.objects.labels` (B5-03 khối [8], phần A)."""

import pytest

from apps.ml.objects.labels import (
    ARTIFACT_LABELS,
    COCO_LABELS,
    PINNED_COCO_MODELS,
    check_labels,
    class_count,
    labels_for,
    pipeline_labels,
)
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.ml_contracts.labels import DETECTION_LABELS
from packages.ml_contracts.payloads import ModelRef


def _model_ref(*, pinned_name: str | None) -> ModelRef:
    """`ModelRef` dạng ghim (khi `pinned_name` cho) hay dạng storage, cho `labels_for`."""
    version_id = new_id("mdl", SystemClock())
    if pinned_name is not None:
        return ModelRef(
            version_id=version_id,
            family="openingAndFurnitureDetection",
            weights_key=None,
            pinned_name=pinned_name,
            checksum_sha256="1e252b7363e1936a0f06a40c221f144f65e86ae8ef01c96e71f7fb33cc3a334d",
        )
    return ModelRef(
        version_id=version_id,
        family="openingAndFurnitureDetection",
        weights_key=f"ml/models/{version_id}/model.onnx",
        pinned_name=None,
        checksum_sha256="a" * 64,
    )


def test_artifact_labels__match_detection_labels() -> None:
    """`ARTIFACT_LABELS` bằng đúng `DETECTION_LABELS` của B5-01."""
    assert ARTIFACT_LABELS == DETECTION_LABELS


_V3_LABELS = (
    "door",
    "double_door",
    "window",
    "table",
    "chair",
    "bed",
    "wardrobe",
    "kitchen_cabinet",
    "sanitary_fixture",
    "stair",
    "other",
)


def test_labels_for__eleven_class_model_keeps_v3_mapping() -> None:
    """Model 11 lớp (v3) đọc đúng 11 nhãn cũ theo thứ tự cũ, không thấy lớp mới."""
    assert labels_for(_model_ref(pinned_name=None), 11) == _V3_LABELS


def test_labels_for__thirteen_class_model_maps_new_ids() -> None:
    """Model 13 lớp: id 0..10 như v3, id 11 `washing_machine`, id 12 `shower`."""
    labels = labels_for(_model_ref(pinned_name=None), 13)
    assert labels[:11] == _V3_LABELS
    assert labels[11:] == ("washing_machine", "shower")
    assert pipeline_labels(_model_ref(pinned_name=None), 13)[11:] == ("washing_machine", "shower")
    assert len(pipeline_labels(_model_ref(pinned_name=None), 11)) == 11


class _Out:
    def __init__(self, shape: list[object]) -> None:
        self.shape = shape


class _Session:
    def __init__(self, *shapes: list[object]) -> None:
        self._outs = [_Out(s) for s in shapes]

    def get_outputs(self) -> list[_Out]:
        return self._outs


def test_class_count__reads_output_channels() -> None:
    """`(1, 4+N, A)` → N; hình dạng lạ hoặc kênh động → `None` (detector tự từ chối)."""
    assert class_count(_Session([1, 15, "anchors"])) == 11
    assert class_count(_Session([1, 17, 8400])) == 13
    assert class_count(_Session([1, "c", 8400])) is None
    assert class_count(_Session([1, 15])) is None
    assert class_count(_Session([1, 15, 8], [1, 15, 8])) is None


def test_coco_labels__eighty_entries_six_mapped() -> None:
    """`COCO_LABELS` đúng 80 phần tử, chỉ 6 chỉ số khối [6] khác `None`."""
    assert len(COCO_LABELS) == 80
    mapped = {i: v for i, v in enumerate(COCO_LABELS) if v is not None}
    assert mapped == {
        56: "chair",
        57: "other",
        59: "bed",
        60: "table",
        61: "sanitary_fixture",
        71: "sanitary_fixture",
    }


def test_labels_for__pinned_yolo_returns_coco_labels_object() -> None:
    """Model ghim `yolov8n`/`yolov8s` (COCO gốc) → `labels_for` trả đúng `COCO_LABELS`."""
    ref = _model_ref(pinned_name="yolov8n")
    assert ref.pinned_name in PINNED_COCO_MODELS
    assert labels_for(ref) is COCO_LABELS


def test_labels_for__storage_model_returns_artifact_labels() -> None:
    """Model dạng storage (đã huấn luyện) → `labels_for` trả `ARTIFACT_LABELS`."""
    ref = _model_ref(pinned_name=None)
    assert labels_for(ref) is ARTIFACT_LABELS


def test_check_labels__unknown_label_raises() -> None:
    """Nhãn ngoài `ARTIFACT_LABELS` và khác `None` → `ValueError`."""
    with pytest.raises(ValueError, match="ngoài ARTIFACT_LABELS"):
        check_labels(["door", "not_a_real_label"])


def test_check_labels__none_and_valid_labels_pass() -> None:
    """`None` và nhãn hợp lệ đều qua được, không ném."""
    check_labels([None, "door", "other", None])


def test_pipeline_labels__drops_stair_only() -> None:
    """Bước pipeline bỏ `stair` (đổi thành `None`), các nhãn khác giữ nguyên chỉ số."""
    labels = pipeline_labels(_model_ref(pinned_name=None))
    assert len(labels) == len(ARTIFACT_LABELS)
    assert "stair" not in labels
    assert [label for label in ARTIFACT_LABELS if label != "stair"] == [label for label in labels if label is not None]
    assert pipeline_labels(_model_ref(pinned_name="yolov8n")) == COCO_LABELS
