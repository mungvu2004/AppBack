"""Nguồn gợi ý "mực dư" (B4 vật sót): nét còn lại trên trang sau khi trừ tường, chữ, hộp YOLO và cung cửa.

Mảnh mực liền nhau cỡ một món đồ (0,3-3 m) trong căn hộ thành hộp `other` gợi ý cho người duyệt (S-13
vẽ nét đứt). Chỉ chạy trên trang nền trắng: bản tô màu sàn/gạch/thảm biến cả nền thành "mực". Bench căn hộ
28/10/2026 (8 bản nét, đáp án mù `key/final`): +4,5 vật thật, ~1,1 rác mỗi bản. Hàm thuần numpy/cv2, đơn vị px.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.ml_contracts.artifacts import MASK_MAX_PIXELS, decode_mask, read_png_header

Box = tuple[float, float, float, float]
"""`(x_min, y_min, x_max, y_max)` px."""

INK_GRAY: Final = 245
"""Điểm xám < 245 là mực: nét nội thất hay vẽ xám nhạt, ngưỡng 230 làm vỡ nét giường (ch-04: 62 % điểm ≥ 230)."""

WHITE_GRAY: Final = 250
MIN_WHITE_SHARE: Final = 0.5
"""Nền trắng = ≥ 50 % điểm trong căn hộ (trừ tường) sáng ≥ 250; bench: nét 0,63-0,88, màu 0,02-0,28."""

MIN_LONG_M: Final = 0.3
MAX_LONG_M: Final = 3.0
MIN_SHORT_M: Final = 0.25
"""Cạnh ngắn nhỏ hơn: số đo OCR sót, cánh cửa, nét đơn."""

MAX_ASPECT: Final = 8.0
"""Dẹt hơn: đường kích thước, nét thẳng."""

MAX_DENSITY: Final = 0.45
"""Mực/khung cao hơn: gạch chéo, khối đặc."""

MIN_INK_PX: Final = 40
MAX_SUGGESTIONS: Final = 15
"""Trần gợi ý mỗi trang, giữ mảnh nhiều mực nhất (bench: tối đa 14 ứng viên/bản)."""

OVERLAP_IOU: Final = 0.3
OVERLAP_CONTAIN: Final = 0.6
"""Gợi ý trùng hộp phát hiện (IoU ≥ 0,3 hay nằm ≥ 60 % trong nó) bị bỏ."""

_OPENING_LABELS: Final = frozenset({"door", "double_door", "window"})
_DOOR_LABELS: Final = frozenset({"door", "double_door"})


@dataclass(frozen=True, slots=True)
class PageRaster:
    """Trang đã nắn (xám `uint8`) và mặt nạ tường (`True` = tường) cùng khổ."""

    gray: NDArray[np.uint8]
    walls: NDArray[np.bool_]


def decode_page_raster(page_png: bytes, walls_png: bytes, *, width_px: int, height_px: int) -> PageRaster:
    """PNG trang + `walls.png` → `PageRaster`; khổ lệch, vượt `MASK_MAX_PIXELS` hay PNG hỏng → `ValueError`."""
    header = read_png_header(page_png)
    if (header.width, header.height) != (width_px, height_px) or width_px * height_px > MASK_MAX_PIXELS:
        raise ValueError(f"trang {header.width}x{header.height} px lệch khổ {width_px}x{height_px}")
    walls = decode_mask(walls_png, width_px=width_px, height_px=height_px)
    bgr = cv2.imdecode(np.frombuffer(page_png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("ảnh trang không giải được")
    return PageRaster(gray=np.asarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), dtype=np.uint8), walls=walls)


def _box_mask(shape: tuple[int, ...], boxes: Sequence[Box], pad: int) -> NDArray[np.uint8]:
    """Mặt nạ 0/1 của các hộp nới `pad` px, cắt theo mép ảnh."""
    mask = np.zeros(shape[:2], np.uint8)
    h, w = shape[:2]
    for x0, y0, x1, y1 in boxes:
        mask[max(int(y0) - pad, 0) : min(int(y1) + pad + 1, h), max(int(x0) - pad, 0) : min(int(x1) + pad + 1, w)] = 1
    return mask


def _door_squares(detections: Sequence[tuple[str, Box]]) -> list[Box]:
    """Hộp cửa YOLO chỉ ôm cánh; nới thành hình vuông bán kính = cạnh dài để che cung mở."""
    out = []
    for label, (x0, y0, x1, y1) in detections:
        if label in _DOOR_LABELS:
            cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0)
            out.append((cx - r, cy - r, cx + r, cy + r))
    return out


def _interior(barrier: NDArray[np.uint8], gap_px: float) -> NDArray[np.uint8]:
    """Vùng tường + ô mở bao kín: lấp từ bốn góc ảnh, phần không tới được là trong căn hộ.

    Đóng hình thái `gap_px` (~1 m) vá lỗ cửa YOLO sót trên tường bao. Không dùng đa giác phòng vì tách
    phòng còn sai nhiều.
    """
    k = max(int(gap_px) | 1, 3)
    closed = cv2.morphologyEx(barrier, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    flood = closed * 255
    h, w = flood.shape
    seed = np.zeros((h + 2, w + 2), np.uint8)
    for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if flood[y, x] == 0:
            cv2.floodFill(flood, seed, (x, y), 128)
    return cv2.erode((flood != 128).astype(np.uint8), np.ones((5, 5), np.uint8))


def _overlap(a: Box, b: Box) -> tuple[float, float]:
    """(IoU, phần diện tích của `a` nằm trong `b`)."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    union = area_a + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / max(union, 1e-9), inter / max(area_a, 1e-9)


def _component_box(stats: NDArray[np.int32], i: int, mm_per_px: float) -> Box | None:
    """Khung mảnh `i` nếu cỡ (mét) và độ dẹt giống một món đồ, còn lại `None`."""
    x, y, w, h = (int(v) for v in stats[i, :4])
    if max(w, h) / max(min(w, h), 1) > MAX_ASPECT:
        return None
    long_m, short_m = max(w, h) * mm_per_px / 1000, min(w, h) * mm_per_px / 1000
    if not MIN_LONG_M <= long_m <= MAX_LONG_M or short_m < MIN_SHORT_M:
        return None
    return (float(x), float(y), float(x + w), float(y + h))


def residual_ink_boxes(
    page: PageRaster, *, detections: Sequence[tuple[str, Box]], texts: Sequence[Box], mm_per_px: float
) -> list[Box]:
    """Hộp gợi ý từ mực dư, xếp theo số điểm mực giảm dần, tối đa `MAX_SUGGESTIONS`; trang có màu → `[]`.

    `detections`: mọi hộp (nhãn, hộp) của bộ dò — ô mở khép căn hộ, mọi hộp bị trừ khỏi mực và chặn gợi ý trùng.
    """
    gray, wall = page.gray, page.walls.astype(np.uint8)
    openings = [box for label, box in detections if label in _OPENING_LABELS]
    inside = _interior(wall | _box_mask(gray.shape, openings, 2), 1000 / mm_per_px)
    paper = gray[(inside > 0) & (wall == 0)]
    if paper.size == 0 or float((paper >= WHITE_GRAY).mean()) < MIN_WHITE_SHARE:
        return []
    removed = cv2.dilate(wall, np.ones((7, 7), np.uint8))
    removed |= _box_mask(gray.shape, texts, 2) | _box_mask(gray.shape, [box for _, box in detections], 3)
    removed |= _box_mask(gray.shape, _door_squares(detections), 0)
    residual = ((gray < INK_GRAY) & (removed == 0) & (inside > 0)).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(cv2.dilate(residual, np.ones((5, 5), np.uint8)))
    kept: list[tuple[int, Box]] = []
    for i in range(1, count):
        box = _component_box(stats, i, mm_per_px)
        if box is None:
            continue
        x0, y0, x1, y1 = (int(v) for v in box)
        ink = int(((labels[y0:y1, x0:x1] == i) & (residual[y0:y1, x0:x1] > 0)).sum())
        if ink < MIN_INK_PX or ink / ((x1 - x0) * (y1 - y0)) > MAX_DENSITY:
            continue
        if any(
            iou >= OVERLAP_IOU or inside_share >= OVERLAP_CONTAIN
            for iou, inside_share in (_overlap(box, other) for _, other in detections)
        ):
            continue
        kept.append((ink, box))
    kept.sort(key=lambda item: -item[0])
    return [box for _, box in kept[:MAX_SUGGESTIONS]]
