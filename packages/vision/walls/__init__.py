"""Tách tường thuần numpy/OpenCV: mặt nạ cổ điển, vector hoá đường tim, độ đo mặt nạ.

Không nhập `packages.ml_contracts` (B6-04a dùng lại khi không có worker `ml`); kiểu kết
quả là `WallSegment`, `apps.ml.walls` đổi sang `WallPx`. Nhập gói không có tác dụng phụ.
"""

from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.metrics import mask_iou, mask_overlap
from packages.vision.walls.types import VectorizeResult, WallSegment
from packages.vision.walls.vectorize import keep_longest, vectorize, vectorize_with_stats

__all__ = [
    "VectorizeResult",
    "WallSegment",
    "classic_wall_mask",
    "default_min_thickness_px",
    "keep_longest",
    "mask_iou",
    "mask_overlap",
    "vectorize",
    "vectorize_with_stats",
]
