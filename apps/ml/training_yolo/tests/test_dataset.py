"""`build_yolo_dataset`: lát ảnh, cắt hộp theo lát, lát nền, `data.yaml` (B6-04b khối [8] "Dataset")."""

from pathlib import Path

import numpy as np
import pytest
import yaml

from apps.ml.objects.labels import ARTIFACT_LABELS
from apps.ml.training_runner.errors import DATASET_SPLIT_EMPTY, TrainingStopped
from apps.ml.training_segformer.errors import DATASET_SAMPLE_INVALID
from apps.ml.training_yolo import dataset as dataset_module
from apps.ml.training_yolo.dataset import build_yolo_dataset
from apps.ml.training_yolo.tests.support import write_micro_dataset
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, ObjectsResult, objects_to_json
from packages.ml_contracts.datasets import Split
from packages.ml_contracts.labels import OBJECT_LABELS
from packages.vision.preprocess import encode_png
from packages.vision.preprocess.types import RgbImage

_NEVER_CANCELLED = lambda: False  # noqa: E731 — callable trạng thái cố định, dùng lặp lại trong test


def _write_sample(
    data_dir: Path,
    split: Split,
    sample_id: str,
    *,
    width: int,
    height: int,
    detections: tuple[DetectionPx, ...] = (),
) -> None:
    """Ghi `data_dir/split/sample_id/{image.png, objects.json}` một mẫu tự dựng (không `render_plan`)."""
    sample_dir = data_dir / split / sample_id
    sample_dir.mkdir(parents=True)
    pixels = np.zeros((height, width, 3), dtype=np.uint8)
    (sample_dir / "image.png").write_bytes(encode_png(RgbImage(pixels)))
    (sample_dir / "objects.json").write_bytes(objects_to_json(ObjectsResult(detections=detections)))


def _box_detection(x_min: float, y_min: float, x_max: float, y_max: float, *, label: str = "door") -> DetectionPx:
    """Một hộp phát hiện hợp lệ cho test; `confidence` không ảnh hưởng tới dataset."""
    return DetectionPx(label=label, box=BoxPx(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max), confidence=0.9)


def _minimal_dataset(data_dir: Path) -> None:
    """Train + validation tối thiểu: mỗi split một lát duy nhất chứa trọn một hộp (không bị bỏ)."""
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))
    _write_sample(data_dir, "validation", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))


def test_label_line_format_and_class_index(tmp_path: Path) -> None:
    """Dòng nhãn 6 chữ số thập phân, `cls` đúng chỉ số `OBJECT_LABELS.index("door")`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=640, height=480, detections=(_box_detection(100, 100, 200, 180),))
    _write_sample(data_dir, "validation", "s0000", width=640, height=480, detections=(_box_detection(0, 0, 640, 480),))

    result = build_yolo_dataset(data_dir, work_dir, tile_px=640, keep_every=1, cancelled=_NEVER_CANCELLED)

    label_file = next((work_dir / "labels" / "train").glob("*.txt"))
    line = label_file.read_text(encoding="utf-8").strip()
    cls, cx, cy, w, h = line.split()
    assert int(cls) == OBJECT_LABELS.index("door")
    for value in (cx, cy, w, h):
        assert len(value.split(".")[1]) == 6
    assert cx == "0.234375"
    assert cy == "0.291667"
    assert result.train_tiles == 1


def test_box_straddling_tile_kept_at_ten_percent(tmp_path: Path) -> None:
    """Hộp cắt còn đúng 10% diện tích gốc, mỗi cạnh ≥ 2px → giữ."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(40, 0, 140, 50),))
    _minimal_dataset_validation_only(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=100, keep_every=1, cancelled=_NEVER_CANCELLED)

    assert result.train_tiles == 1
    assert result.skipped_boxes == 0


def test_box_straddling_tile_dropped_at_five_percent(tmp_path: Path) -> None:
    """Hộp cắt còn 5% diện tích gốc (< 10%) → bỏ; không còn lát chứa hộp → `DATASET_SPLIT_EMPTY`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(40, 0, 240, 50),))
    _minimal_dataset_validation_only(data_dir)

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=100, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SPLIT_EMPTY


def test_clipped_edge_one_pixel_dropped(tmp_path: Path) -> None:
    """Cạnh sau cắt 1px (< 2px) → bỏ dù diện tích đạt ngưỡng."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(49, 0, 59, 50),))
    _minimal_dataset_validation_only(data_dir)

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=100, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SPLIT_EMPTY


def test_clipped_edge_two_pixels_kept(tmp_path: Path) -> None:
    """Cạnh sau cắt đúng 2px → giữ."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(48, 0, 58, 50),))
    _minimal_dataset_validation_only(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=100, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert result.train_tiles == 1


def test_other_label_dropped_and_counted(tmp_path: Path) -> None:
    """Nhãn `other` bị bỏ, `skipped_boxes` đếm đúng một lần; hộp hợp lệ cùng mẫu vẫn giữ."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(
        data_dir,
        "train",
        "s0000",
        width=50,
        height=50,
        detections=(_box_detection(0, 0, 50, 50, label="door"), _box_detection(0, 0, 50, 50, label="other")),
    )
    _minimal_dataset_validation_only(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=100, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert result.skipped_boxes == 1
    assert result.train_tiles == 1


def test_background_tiles_kept_every_fourth_per_split(tmp_path: Path) -> None:
    """Lát nền giữ theo `k % keep_every == 0`, đếm riêng mỗi split (`keep_every=4`)."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))
    _write_sample(data_dir, "train", "s0001", width=180, height=50, detections=())
    _minimal_dataset_validation_only(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=4, cancelled=_NEVER_CANCELLED)

    # s0000: 1 lát tiền cảnh. s0001: 5 lát nền (tile_windows(180,50,tile_px=50,...)), giữ k=0,4 → 2.
    assert result.train_tiles == 1 + 2


def test_data_yaml_roundtrip(tmp_path: Path) -> None:
    """`yaml.safe_load` đọc lại đúng `names = ARTIFACT_LABELS`, `train`/`val`, `path`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _minimal_dataset(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)

    manifest = yaml.safe_load(result.yaml_path.read_text(encoding="utf-8"))
    assert manifest["names"] == list(ARTIFACT_LABELS)
    assert manifest["train"] == "images/train"
    assert manifest["val"] == "images/val"
    assert manifest["path"] == str(work_dir)


def test_validation_split_empty_raises(tmp_path: Path) -> None:
    """Thư mục `validation/` thiếu hẳn → `DATASET_SPLIT_EMPTY`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SPLIT_EMPTY


def test_split_with_only_background_tiles_raises(tmp_path: Path) -> None:
    """Split không có lát nào chứa hộp (toàn lát nền) → `DATASET_SPLIT_EMPTY`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=())
    _minimal_dataset_validation_only(data_dir)

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SPLIT_EMPTY


def test_image_over_pixel_cap_is_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ảnh vượt `DEFAULT_MAX_PIXELS` (vá nhỏ qua thuộc tính module) → `DATASET_SAMPLE_INVALID`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    monkeypatch.setattr(dataset_module, "DEFAULT_MAX_PIXELS", 100)
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SAMPLE_INVALID


def test_corrupt_objects_json_is_invalid(tmp_path: Path) -> None:
    """`objects.json` không giải được → `DATASET_SAMPLE_INVALID`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    sample_dir = data_dir / "train" / "s0000"
    sample_dir.mkdir(parents=True)
    pixels = np.zeros((50, 50, 3), dtype=np.uint8)
    (sample_dir / "image.png").write_bytes(encode_png(RgbImage(pixels)))
    (sample_dir / "objects.json").write_bytes(b"not json")

    with pytest.raises(PermanentError) as excinfo:
        build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert excinfo.value.code == DATASET_SAMPLE_INVALID


def test_cancelled_after_first_sample_raises_training_stopped(tmp_path: Path) -> None:
    """`cancelled()` hỏi sau mỗi mẫu; đúng ngay sau mẫu đầu → `TrainingStopped`, không đọc tiếp."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _write_sample(data_dir, "train", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))
    _write_sample(data_dir, "train", "s0001", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))
    _minimal_dataset_validation_only(data_dir)

    with pytest.raises(TrainingStopped):
        build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=lambda: True)


def test_does_not_read_test_split(tmp_path: Path) -> None:
    """`test/` hỏng (ảnh rác) không được đọc — dataset vẫn dựng được từ `train`/`validation`."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    _minimal_dataset(data_dir)
    bad = data_dir / "test" / "s0000"
    bad.mkdir(parents=True)
    (bad / "image.png").write_bytes(b"not a png")
    (bad / "objects.json").write_bytes(b"not json")

    result = build_yolo_dataset(data_dir, work_dir, tile_px=50, keep_every=1, cancelled=_NEVER_CANCELLED)
    assert result.train_tiles == 1
    assert result.validation_tiles == 1


def test_real_micro_dataset_produces_tiles(tmp_path: Path) -> None:
    """Dataset vi mô thật (`write_micro_dataset`, `tile_px=320`, `keep_every=4`) → cả hai split có lát."""
    data_dir, work_dir = tmp_path / "data", tmp_path / "work"
    write_micro_dataset(data_dir)

    result = build_yolo_dataset(data_dir, work_dir, tile_px=320, keep_every=4, cancelled=_NEVER_CANCELLED)

    assert result.train_tiles > 0
    assert result.validation_tiles > 0


def _minimal_dataset_validation_only(data_dir: Path) -> None:
    """Validation tối thiểu hợp lệ (một lát trọn hộp), dùng khi `train` là tâm điểm của test."""
    _write_sample(data_dir, "validation", "s0000", width=50, height=50, detections=(_box_detection(0, 0, 50, 50),))
