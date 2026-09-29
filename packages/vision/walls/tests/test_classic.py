"""Mask cổ điển: giữ tường, bỏ nét mảnh hơn `min_thickness_px` (B5-02 [8], việc B)."""

import cv2
import numpy as np
import pytest

from packages.vision.preprocess.types import RgbImage
from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.metrics import mask_iou

_WALL_THICKNESS_PX = 12
_MIN_THICKNESS_PX = 11  # lẻ, < wall: k chẵn lệch tâm 1 px trong cv2 (opening chẵn), k = wall xoá hết
_SIZE = (400, 300)  # (width, height)


def _synthetic_page() -> tuple[RgbImage, np.ndarray]:
    """Trang trắng: tường 12 px dày, chữ dày 2, đường kích thước 1 px, cung cửa mảnh."""
    width, height = _SIZE
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    wall_mask = np.zeros((height, width), dtype=np.bool_)
    y0, y1 = 100, 100 + _WALL_THICKNESS_PX
    canvas[y0:y1, 20:380] = (0, 0, 0)
    wall_mask[y0:y1, 20:380] = True
    x0, x1 = 150, 150 + _WALL_THICKNESS_PX
    canvas[40:260, x0:x1] = (0, 0, 0)
    wall_mask[40:260, x0:x1] = True
    cv2.putText(canvas, "3200", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    cv2.line(canvas, (20, 90), (380, 90), (0, 0, 0), 1)
    cv2.ellipse(canvas, (200, 260), (40, 40), 0, 0, 90, (0, 0, 0), 1)
    return RgbImage(canvas), wall_mask


def test_classic_wall_mask_keeps_walls_drops_thin_strokes() -> None:
    """Tường dày 12 px còn nguyên; chữ, đường kích thước, cung cửa (mảnh hơn k) mất."""
    img, wall_mask = _synthetic_page()
    before = img.pixels.copy()
    mask = classic_wall_mask(img, min_thickness_px=_MIN_THICKNESS_PX)
    assert mask_iou(mask, wall_mask) >= 0.95
    assert np.array_equal(img.pixels, before)


def test_classic_wall_mask_rejects_non_positive_thickness() -> None:
    """`min_thickness_px < 1` → `ValueError`."""
    img, _ = _synthetic_page()
    with pytest.raises(ValueError, match="min_thickness_px"):
        classic_wall_mask(img, min_thickness_px=0)


@pytest.mark.parametrize(
    ("width_px", "height_px", "px_per_paper_mm", "expected"),
    [
        (1600, 1200, None, 3),
        (7745, 5164, None, 11),
        (4677, 6623, 7.87, 5),
    ],
)
def test_default_min_thickness_px(width_px: int, height_px: int, px_per_paper_mm: float | None, expected: int) -> None:
    """Ba tổ hợp khổ/tỉ lệ trong hợp đồng cho đúng ngưỡng bề dày."""
    assert default_min_thickness_px(width_px, height_px, px_per_paper_mm) == expected


def test_default_min_thickness_px_matches_walls_on_large_page() -> None:
    """`k` từ `px_per_paper_mm=7,87` trên trang 4.677x6.623 vẫn giữ vách dày 9 px (IoU ≥ 0,95)."""
    width, height = 4677, 6623
    thickness = 9
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    wall_mask = np.zeros((height, width), dtype=np.bool_)
    y0, y1 = 3000, 3000 + thickness
    canvas[y0:y1, 200:4400] = (0, 0, 0)
    wall_mask[y0:y1, 200:4400] = True
    k = default_min_thickness_px(width, height, px_per_paper_mm=7.87)
    mask = classic_wall_mask(RgbImage(canvas), min_thickness_px=k)
    assert mask_iou(mask, wall_mask) >= 0.95
