"""Phân vùng bố cục trang baseline: tách các khối bản vẽ trên một trang (thiết kế Phase 1 H3 bước 2).

Thuần OpenCV, không ML: nhị phân hoá Otsu, bỏ đường khung giấy, giãn để nối nét trong một
bản vẽ, lấy thành phần liên thông đủ lớn, gộp hộp chồng nhau, nới lề. Không có hộp nào →
một vùng phủ cả trang để người dùng tự vẽ lại.
"""

from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

# Ngưỡng tinh chỉnh trên bench (tỉ lệ so với cạnh/diện tích trang).
FRAME_LINE_RATIO: Final = 0.6  # nét ngang/dọc dài ≥ 60 % cạnh trang = đường khung giấy
DILATE_RATIO: Final = 0.015  # nhân giãn ~1,5 % cạnh dài: nối nét trong một bản vẽ
MIN_AREA_RATIO: Final = 0.04  # bỏ khối có hộp nhỏ hơn 4 % trang
MERGE_OVERLAP_RATIO: Final = 0.3  # giao > 30 % diện tích hộp nhỏ hơn → gộp
PAD_RATIO: Final = 0.01  # nới mỗi cạnh 1 % chiều tương ứng

type GrayImage = NDArray[np.uint8]  # (H, W)
type RgbImage = NDArray[np.uint8]  # (H, W, 3)
_Rect = tuple[int, int, int, int]  # x0, y0, x1, y1 pixel, x1/y1 loại trừ


@dataclass(frozen=True, slots=True)
class Box:
    """Hộp chữ nhật theo tỉ lệ trang 0..1, `x0 < x1`, `y0 < y1`."""

    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        """Chốt `0 ≤ x0 < x1 ≤ 1` và `0 ≤ y0 < y1 ≤ 1`; sai → `ValueError` (lỗi lập trình bên gọi)."""
        if not (0.0 <= self.x0 < self.x1 <= 1.0 and 0.0 <= self.y0 < self.y1 <= 1.0):
            raise ValueError(f"Box ngoài 0..1 hoặc rỗng: {self}")


_FULL_PAGE: Final = Box(0.0, 0.0, 1.0, 1.0)


def segment_page(image: GrayImage | RgbImage) -> tuple[Box, ...]:
    """Tách trang thành các vùng bản vẽ; thứ tự trên→dưới rồi trái→phải theo `(y0, x0)`.

    Ảnh `uint8` xám `(H, W)` hoặc RGB `(H, W, 3)`. Không tìm được khối nào → `(Box(0, 0, 1, 1),)`.
    ponytail: hai mặt bằng chạm nhau (nét nối liền sau khi giãn) ra một hộp; người dùng vẽ lại.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    h, w = gray.shape
    ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1].astype(np.uint8, copy=False)
    ink = cv2.subtract(ink, _frame_lines(ink)).astype(np.uint8, copy=False)
    k = max(1, round(DILATE_RATIO * max(h, w)))
    ink = cv2.dilate(ink, np.ones((k, k), np.uint8)).astype(np.uint8, copy=False)
    _, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    rects = [
        (int(x), int(y), int(x + bw), int(y + bh)) for x, y, bw, bh, _ in stats[1:] if bw * bh >= MIN_AREA_RATIO * h * w
    ]
    boxes = [_to_box(r, w, h) for r in _merge(rects)]
    return tuple(sorted(boxes, key=lambda b: (b.y0, b.x0))) or (_FULL_PAGE,)


def _frame_lines(ink: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Mặt nạ nét ngang/dọc dài ≥ `FRAME_LINE_RATIO` cạnh trang (khung giấy) bằng mở hình thái."""
    h, w = ink.shape
    masks = [
        # borderValue=0: ngoài ảnh là giấy trắng; mặc định erode coi biên là mực nên nét chạm mép bị xoá như khung.
        cv2.morphologyEx(ink, cv2.MORPH_OPEN, np.ones(shape, np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
        for shape in ((1, max(1, int(FRAME_LINE_RATIO * w))), (max(1, int(FRAME_LINE_RATIO * h)), 1))
    ]
    return cv2.bitwise_or(masks[0], masks[1]).astype(np.uint8, copy=False)


def _merge(rects: list[_Rect]) -> list[_Rect]:
    """Gộp lặp mọi cặp hộp có phần giao > `MERGE_OVERLAP_RATIO` diện tích hộp nhỏ hơn đến khi ổn định.

    ponytail: quét cặp O(n²) mỗi vòng; n là số khối trên một trang (vài chục), đủ nhanh.
    """
    rects = list(rects)
    merged = True
    while merged:
        merged = False
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                inter = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
                smaller = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
                if inter > MERGE_OVERLAP_RATIO * smaller:
                    rects[i] = (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
                    del rects[j]
                    merged = True
                    break
            if merged:
                break
    return rects


def _to_box(rect: _Rect, w: int, h: int) -> Box:
    """Hộp pixel → `Box` tỉ lệ, nới `PAD_RATIO` mỗi cạnh rồi kẹp vào 0..1."""
    x0, y0, x1, y1 = rect
    return Box(
        max(0.0, x0 / w - PAD_RATIO),
        max(0.0, y0 / h - PAD_RATIO),
        min(1.0, x1 / w + PAD_RATIO),
        min(1.0, y1 / h + PAD_RATIO),
    )
