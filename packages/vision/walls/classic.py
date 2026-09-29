"""Mask tường cổ điển bằng ngưỡng Otsu + mở hình thái (B5-02 [6], việc B).

Không mô hình học máy: ngưỡng xám BT.601 rồi Otsu tách mực, mở hình thái loại nét mảnh
hơn bề dày tường tối thiểu (chữ, đường kích thước, cung cửa). Gói này không nhập
`ml_contracts`/`messaging`/`storage`/`db`/`apps.*`.
"""

from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.types import RgbImage

_MIN_THICKNESS_PX_FLOOR: Final = 3
_WALL_MM: Final = 110.0
_PAPER_SCALE: Final = 1.1
_EDGE_TO_WALL_RATIO: Final = 270.0
_THICKNESS_FRACTION: Final = 0.6


def default_min_thickness_px(width_px: int, height_px: int, px_per_paper_mm: float | None = None) -> int:
    """Bề dày tối thiểu (px) coi là tường: nửa bề dày vách 110 mm, sàn tại 3 px.

    Có `px_per_paper_mm` (tỉ lệ trang đã biết, vd 1:100 → 1,1 mm giấy cho vách 110 mm):
    `max(3, floor(0.6 x 1,1 x px_per_paper_mm))`. Không có (ước theo cạnh ngắn ảnh, vách
    110 mm ≈ 1/270 cạnh ngắn — `thresholds.ts:12-17`): `max(3, floor(0.6 x min(w, h) / 270))`.
    """
    if px_per_paper_mm is not None:
        raw = _THICKNESS_FRACTION * _PAPER_SCALE * px_per_paper_mm
    else:
        raw = _THICKNESS_FRACTION * min(width_px, height_px) / _EDGE_TO_WALL_RATIO
    return max(_MIN_THICKNESS_PX_FLOOR, int(np.floor(raw)))


def classic_wall_mask(img: RgbImage, *, min_thickness_px: int) -> NDArray[np.bool_]:
    """Mực (tối) → `True` sau ngưỡng Otsu, rồi mở hình thái `k x k` xoá nét mảnh hơn tường.

    `min_thickness_px < 1` → `ValueError` (không có kernel hợp lệ). Không sửa `img.pixels`:
    `cv2.cvtColor`/`cv2.threshold`/`cv2.morphologyEx` đều nhận mảng và trả mảng mới.
    """
    if min_thickness_px < 1:
        raise ValueError(f"min_thickness_px phải ≥ 1, nhận {min_thickness_px}")
    gray = cv2.cvtColor(img.pixels, cv2.COLOR_RGB2GRAY)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (min_thickness_px, min_thickness_px))
    opened = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    return opened.astype(np.bool_)
