"""Bước dò cửa và đồ của worker `ml` (`openingAndFurnitureDetection`).

YOLOv8 ONNX cắt lát trên trang đã nắn và task `ml.infer.objects.detect`. **Không** xuất lại
task ở đây: sổ task chỉ nhận mỗi tên một lần, và `celery_main` đã nhập
`apps.ml.objects.tasks` qua `discover_submodules` (cùng lý do như `apps.ml.walls`).

Xuất lại tên công khai của `labels`, `tiles`, `detector` để mã dùng gói này nhập một chỗ;
`tasks` không nằm trong danh sách (lý do trên).
"""

from apps.ml.objects.detector import (
    COCO_CONFIDENCE_MIN,
    CONFIDENCE_MIN,
    MAX_DETECTIONS,
    MERGE_OVERLAP,
    NMS_IOU,
    YoloOnnxDetector,
    decode_tile,
    merge_candidates,
)
from apps.ml.objects.labels import ARTIFACT_LABELS, COCO_LABELS, PINNED_COCO_MODELS, check_labels, labels_for
from apps.ml.objects.tiles import Window, overlap_for, tile_windows

__all__ = [
    "ARTIFACT_LABELS",
    "COCO_CONFIDENCE_MIN",
    "COCO_LABELS",
    "CONFIDENCE_MIN",
    "MAX_DETECTIONS",
    "MERGE_OVERLAP",
    "NMS_IOU",
    "PINNED_COCO_MODELS",
    "Window",
    "YoloOnnxDetector",
    "check_labels",
    "decode_tile",
    "labels_for",
    "merge_candidates",
    "overlap_for",
    "tile_windows",
]
