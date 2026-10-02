"""Dataset lát YOLO từ ảnh + `objects.json` của mỗi mẫu train/validation (B6-04b khối [6] "Dataset").

Đọc trực tiếp `data_dir/{train,validation}/{sample_id}/{image.png,objects.json}`, mẫu sắp theo
tên (tái lập); không đọc `test/`. Cắt hộp theo lát bằng numpy trên toàn mảng `(n, 4)` của một
mẫu, không vòng Python hộp x lát x điểm ảnh (K28). `names` của `data.yaml` là `ARTIFACT_LABELS`
(11 nhãn, quyết định "Lệch khỏi prompt" của điều phối B6-04b): chỉ số lớp hộp vẫn theo
`OBJECT_LABELS.index` (0..9, trùng `ARTIFACT_LABELS.index`), lớp 10 `other` không bao giờ có hộp.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import yaml
from numpy.typing import NDArray

from apps.ml.objects.labels import ARTIFACT_LABELS
from apps.ml.objects.tiles import Window, overlap_for, tile_windows
from apps.ml.training_runner.errors import DATASET_SPLIT_EMPTY, TrainingStopped
from apps.ml.training_segformer.errors import DATASET_SAMPLE_INVALID
from packages.messaging.tasks import PermanentError
from packages.ml_contracts.artifacts import DetectionPx, objects_from_json
from packages.ml_contracts.datasets import Split
from packages.ml_contracts.labels import OBJECT_LABELS
from packages.vision.preprocess import DEFAULT_MAX_PIXELS, VisionError, encode_png, load_raster
from packages.vision.preprocess.types import RgbImage

__all__ = ["YoloDataset", "build_yolo_dataset"]

_MIN_BOX_AREA_FRACTION: Final = 0.1
_MIN_BOX_EDGE_PX: Final = 2
_OUTPUT_SPLIT: Final[dict[Split, str]] = {"train": "train", "validation": "val"}


@dataclass(frozen=True, slots=True)
class YoloDataset:
    """Dataset lát đã ghi ra `work_dir`, sẵn cho `ultralytics.YOLO.train(data=yaml_path)`."""

    yaml_path: Path
    train_tiles: int
    validation_tiles: int
    skipped_boxes: int


def _sample_dirs(split_dir: Path) -> tuple[Path, ...]:
    """Thư mục mẫu của một split, sắp theo tên; split thiếu/rỗng trả rỗng (gọi nơi báo lỗi)."""
    if not split_dir.is_dir():
        return ()
    return tuple(sorted(child for child in split_dir.iterdir() if child.is_dir()))


def _read_sample(sample_dir: Path) -> tuple[RgbImage, tuple[DetectionPx, ...]]:
    """Ảnh + hộp của một mẫu; PNG hỏng/vượt trần điểm ảnh, `objects.json` hỏng → `DATASET_SAMPLE_INVALID`."""
    try:
        image = load_raster((sample_dir / "image.png").read_bytes(), max_pixels=DEFAULT_MAX_PIXELS)
        objects = objects_from_json((sample_dir / "objects.json").read_bytes())
    except (OSError, VisionError, ValueError) as exc:
        raise PermanentError(DATASET_SAMPLE_INVALID) from exc
    return image, objects.detections


def _valid_boxes(detections: Sequence[DetectionPx]) -> tuple[NDArray[np.float64], NDArray[np.int64], int]:
    """Hộp của mẫu có `label` thuộc `OBJECT_LABELS`, dạng `(n, 4)` xyxy + chỉ số lớp; số hộp bỏ."""
    label_index: Final[dict[str, int]] = {label: i for i, label in enumerate(OBJECT_LABELS)}
    kept_boxes: list[tuple[float, float, float, float]] = []
    kept_classes: list[int] = []
    skipped = 0
    for det in detections:
        cls = label_index.get(det.label)
        if cls is None:
            skipped += 1
            continue
        kept_boxes.append((det.box.x_min, det.box.y_min, det.box.x_max, det.box.y_max))
        kept_classes.append(cls)
    boxes = np.array(kept_boxes, dtype=np.float64).reshape(-1, 4)
    classes = np.array(kept_classes, dtype=np.int64)
    return boxes, classes, skipped


def _clip_to_window(
    boxes: NDArray[np.float64], classes: NDArray[np.int64], window: Window
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Hộp cắt theo `window`, giữ khi diện tích cắt ≥ 10% diện tích gốc và mỗi cạnh cắt ≥ 2px.

    Trả hộp chuẩn hoá theo **cỡ lát thật** `(cx, cy, w, h) ∈ [0, 1]` và lớp tương ứng.
    """
    if boxes.shape[0] == 0:
        return boxes.reshape(0, 4), classes
    wx0, wy0 = float(window.x), float(window.y)
    wx1, wy1 = wx0 + window.width, wy0 + window.height
    ix0 = np.maximum(boxes[:, 0], wx0)
    iy0 = np.maximum(boxes[:, 1], wy0)
    ix1 = np.minimum(boxes[:, 2], wx1)
    iy1 = np.minimum(boxes[:, 3], wy1)
    iw, ih = ix1 - ix0, iy1 - iy0
    box_area = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    inter_area = np.clip(iw, 0, None) * np.clip(ih, 0, None)
    keep = (iw >= _MIN_BOX_EDGE_PX) & (ih >= _MIN_BOX_EDGE_PX) & (inter_area >= _MIN_BOX_AREA_FRACTION * box_area)
    cx = (ix0[keep] + ix1[keep]) / 2 - wx0
    cy = (iy0[keep] + iy1[keep]) / 2 - wy0
    norm = np.stack([cx / window.width, cy / window.height, iw[keep] / window.width, ih[keep] / window.height], axis=1)
    return norm, classes[keep]


def _write_tile(
    image: RgbImage,
    window: Window,
    boxes_norm: NDArray[np.float64],
    classes: NDArray[np.int64],
    images_dir: Path,
    labels_dir: Path,
    name: str,
) -> None:
    """Ghi `images_dir/{name}.png` (K13: `encode_png`, không `cv2.imwrite`) và `labels_dir/{name}.txt`."""
    tile = image.pixels[window.y : window.y + window.height, window.x : window.x + window.width]
    (images_dir / f"{name}.png").write_bytes(encode_png(RgbImage(tile)))
    lines = [
        f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
        for cls, (cx, cy, w, h) in zip(classes.tolist(), boxes_norm.tolist(), strict=True)
    ]
    text = "\n".join(lines) + ("\n" if lines else "")
    (labels_dir / f"{name}.txt").write_text(text, encoding="utf-8")


def _process_split(
    data_dir: Path,
    split: Split,
    images_dir: Path,
    labels_dir: Path,
    *,
    tile_px: int,
    keep_every: int,
    cancelled: Callable[[], bool],
) -> tuple[int, int]:
    """Lát hết một split; trả `(số lát đã ghi, số hộp bỏ)`.

    Split thiếu/rỗng hoặc không lát nào chứa hộp → `PermanentError(DATASET_SPLIT_EMPTY)`.
    """
    sample_dirs = _sample_dirs(data_dir / split)
    if not sample_dirs:
        raise PermanentError(DATASET_SPLIT_EMPTY)
    overlap = overlap_for(tile_px)
    tiles_written = fg_tiles = skipped_boxes = background_count = 0
    for sample_dir in sample_dirs:
        image, detections = _read_sample(sample_dir)
        boxes, classes, skipped = _valid_boxes(detections)
        skipped_boxes += skipped
        height, width = image.pixels.shape[:2]
        windows = tile_windows(width, height, tile_px=tile_px, overlap_px=overlap)
        for i, window in enumerate(windows):
            norm_boxes, norm_classes = _clip_to_window(boxes, classes, window)
            name = f"{sample_dir.name}_{i}"
            if norm_classes.size:
                _write_tile(image, window, norm_boxes, norm_classes, images_dir, labels_dir, name)
                tiles_written += 1
                fg_tiles += 1
            elif background_count % keep_every == 0:
                _write_tile(image, window, norm_boxes, norm_classes, images_dir, labels_dir, name)
                tiles_written += 1
                background_count += 1
            else:
                background_count += 1
        if cancelled():
            raise TrainingStopped
    if fg_tiles == 0:
        raise PermanentError(DATASET_SPLIT_EMPTY)
    return tiles_written, skipped_boxes


def build_yolo_dataset(
    data_dir: Path, work_dir: Path, *, tile_px: int, keep_every: int, cancelled: Callable[[], bool]
) -> YoloDataset:
    """Lát `data_dir/{train,validation}` vào `work_dir/{images,labels}/{train,val}` + `data.yaml`.

    Không tự dọn `work_dir` (trainer tạo và xoá). Ném `PermanentError(DATASET_SPLIT_EMPTY |
    DATASET_SAMPLE_INVALID)`, `TrainingStopped` khi `cancelled()` đúng sau một mẫu.
    """
    dirs = {
        split: {
            "images": work_dir / "images" / out,
            "labels": work_dir / "labels" / out,
        }
        for split, out in _OUTPUT_SPLIT.items()
    }
    for paths in dirs.values():
        paths["images"].mkdir(parents=True, exist_ok=True)
        paths["labels"].mkdir(parents=True, exist_ok=True)
    train_tiles, train_skipped = _process_split(
        data_dir,
        "train",
        dirs["train"]["images"],
        dirs["train"]["labels"],
        tile_px=tile_px,
        keep_every=keep_every,
        cancelled=cancelled,
    )
    val_tiles, val_skipped = _process_split(
        data_dir,
        "validation",
        dirs["validation"]["images"],
        dirs["validation"]["labels"],
        tile_px=tile_px,
        keep_every=keep_every,
        cancelled=cancelled,
    )
    yaml_path = work_dir / "data.yaml"
    manifest = {"path": str(work_dir), "train": "images/train", "val": "images/val", "names": list(ARTIFACT_LABELS)}
    yaml_path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    return YoloDataset(
        yaml_path=yaml_path,
        train_tiles=train_tiles,
        validation_tiles=val_tiles,
        skipped_boxes=train_skipped + val_skipped,
    )
