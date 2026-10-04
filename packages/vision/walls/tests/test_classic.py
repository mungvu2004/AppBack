"""Mask cổ điển: giữ tường, bỏ nét mảnh hơn `min_thickness_px` (B5-02 [8], việc B)."""

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.preprocess.types import RgbImage
from packages.vision.walls.classic import classic_wall_mask, default_min_thickness_px
from packages.vision.walls.metrics import mask_iou

_WALL_THICKNESS_PX = 12
_MIN_THICKNESS_PX = 11  # < bề dày tường 12 px, > mọi nét chữ, đường kích thước, cung cửa
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


@pytest.mark.parametrize("k", [2, 4, 6, 8, 10])
def test_classic_wall_mask__even_kernel_keeps_band_in_place(k: int) -> None:
    """`k` chẵn không dời mặt nạ: dải 12 px ngang và dọc ra đúng chỗ cũ, không lệch 1 px."""
    canvas = np.full((120, 160, 3), 255, dtype=np.uint8)
    truth = np.zeros((120, 160), dtype=np.bool_)
    truth[40:52, 20:140] = True
    truth[10:110, 90:102] = True
    canvas[truth] = (0, 0, 0)
    mask = classic_wall_mask(RgbImage(canvas), min_thickness_px=k)
    assert np.array_equal(mask, truth)


def _wall_with_openings() -> tuple[RgbImage, NDArray[np.bool_]]:
    """Tường dọc 14 px: khe cửa sổ (3 nét 1 px dọc theo tường) và khe cửa đi (trống) trên ảnh.

    Đáp án như `render_plan`: cửa sổ vẫn là tường, cửa đi là khe.
    """
    canvas = np.full((300, 120, 3), 255, dtype=np.uint8)
    truth = np.zeros((300, 120), dtype=np.bool_)
    truth[10:290, 50:64] = True
    truth[200:240, 50:64] = False
    canvas[truth] = (0, 0, 0)
    truth[60:140, 50:64] = True
    for column in (50, 57, 63):
        canvas[60:140, column] = (0, 0, 0)
    return RgbImage(canvas), truth


def test_classic_wall_mask__window_gap_bridged_door_gap_kept() -> None:
    """Khe cửa sổ thành tường trọn bề dày; khe cửa đi (không nét) vẫn hở."""
    img, truth = _wall_with_openings()
    mask = classic_wall_mask(img, min_thickness_px=3)
    assert np.array_equal(mask, truth)


def test_classic_wall_mask__single_line_between_walls_is_not_wall() -> None:
    """Một nét 1 px nối hai tường (đường trục, bệ cửa) không được lấp thành tường."""
    canvas = np.full((200, 200, 3), 255, dtype=np.uint8)
    truth = np.zeros((200, 200), dtype=np.bool_)
    truth[20:180, 40:52] = True
    truth[20:180, 140:152] = True
    canvas[truth] = (0, 0, 0)
    canvas[100, 52:140] = (0, 0, 0)
    mask = classic_wall_mask(RgbImage(canvas), min_thickness_px=3)
    assert np.array_equal(mask, truth)


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
