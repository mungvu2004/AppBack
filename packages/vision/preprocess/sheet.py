"""Vùng vẽ của một tờ bản vẽ: bỏ khung tên (cột phải, dải dưới) và nét viền chạy suốt sát mép.

Tờ CAD xuất ảnh có viền giấy và khung tên (tên công ty, người vẽ, tỉ lệ, ngày): model tường đọc
các nét kẻ ô của chúng thành tường và sinh phòng giả (bench căn hộ 26/10/2026: ch-03 ra 9 phòng
giả ở khung tên). Ở đây chỉ dùng hình học nét kẻ, không đọc chữ: vạch ngăn khung tên là đường
chạy suốt chiều cao (hay chiều rộng) trang, và vùng sau nó là bảng có nhiều đường kẻ suốt bề
ngang của chính nó. Hàm thuần, tất định.
"""

from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.geometry import rectify
from packages.vision.preprocess.types import DEFAULT_MAX_PIXELS, Quad, RgbImage

INK_DELTA: Final = 55
"""Nét kẻ khung = tối hơn màu nền phổ biến nhất >= 55 mức (đường xám CAD ~200 trên nền 255)."""
FULL_RATIO: Final = 0.85
"""Đường "chạy suốt" dài >= 85 % cạnh trang (chừa chỗ đường bị chữ, ký hiệu cắt ngang)."""
_RUN_GAP_PX: Final = 2
"""Đoạn mực nối qua chỗ hở <= 2 px."""
_STRIP_FROM: Final = 0.65
_STRIP_TO: Final = 0.97
"""Vạch ngăn khung tên nằm ở 65-97 % bề rộng (cột phải) hay chiều cao (dải dưới)."""
_STRIP_MAX: Final = 0.35
"""Khung tên chiếm <= 35 % trang."""
_CELL_RATIO: Final = 0.8
_CELL_LINES_MIN: Final = 3
"""Vùng sau vạch là khung tên khi có >= 3 đường kẻ suốt >= 80 % bề ngang của nó (ô bảng)."""
_BORDER_BAND: Final = 0.04
"""Nét viền nằm trong 4 % sát mép vùng còn lại."""
_PAD_PX: Final = 3
"""Cắt lùi vào trong 3 px khỏi mỗi vạch để nét vạch (đã nhoè) không còn ở mép.

Không cần chặn "vùng vẽ quá nhỏ": khung tên <= 35 % mỗi chiều và viền chỉ trong 4 % sát mép, nên
vùng còn lại luôn > 40 % trang."""

Ink = NDArray[np.bool_]
Box = tuple[int, int, int, int]


def _longest_runs(ink: Ink) -> NDArray[np.int64]:
    """Độ dài đoạn mực dài nhất của từng **cột** (nối qua chỗ hở <= `_RUN_GAP_PX`)."""
    width = ink.shape[1]
    best = np.zeros(width, dtype=np.int64)
    current = np.zeros(width, dtype=np.int64)
    miss = np.zeros(width, dtype=np.int64)
    for row in ink:
        miss = np.where(row, 0, miss + 1)
        current = np.where(row, current + 1, np.where(miss <= _RUN_GAP_PX, current, 0))
        np.maximum(best, current, out=best)
    return best


def _full_lines(ink: Ink, low: int, high: int, ratio: float) -> list[int]:
    """Toạ độ (giữa nhóm) các **cột** `low <= x < high` có đoạn mực >= `ratio` chiều cao; cột sát nhau gộp một."""
    runs = _longest_runs(ink)
    found = [x for x in range(max(low, 0), min(high, ink.shape[1])) if runs[x] >= ratio * ink.shape[0]]
    groups: list[list[int]] = []
    for x in found:
        if groups and x - groups[-1][-1] <= 2:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [sum(g) // len(g) for g in groups]


def _title_divider(ink: Ink) -> int | None:
    """Cột của vạch ngăn khung tên bên phải (`ink` đã xoay sẵn cho dải dưới), hay `None`.

    Lấy vạch trái nhất trong 65-97 % bề rộng mà vùng bên phải hẹp <= 35 % và là bảng: có
    >= `_CELL_LINES_MIN` đường ngang kẻ suốt bề rộng của vùng đó, không kể đường trong dải
    `_BORDER_BAND` sát mép trên/dưới (nét viền).
    """
    height, width = ink.shape
    band = _BORDER_BAND * height
    for x in _full_lines(ink, int(_STRIP_FROM * width), int(_STRIP_TO * width), FULL_RATIO):
        strip = ink[:, x + _PAD_PX :]
        if strip.shape[1] == 0 or width - x > _STRIP_MAX * width:
            continue
        rows = _full_lines(np.ascontiguousarray(strip.T), 0, height, _CELL_RATIO)
        cells = [y for y in rows if band < y < height - band]  # nét viền trên/dưới cắt ngang mọi dải: không là ô
        if len(cells) >= _CELL_LINES_MIN:
            return x
    return None


def _border_inset(ink: Ink) -> Box:
    """Hộp bên trong các nét viền chạy suốt nằm trong `_BORDER_BAND` sát bốn mép của `ink`."""
    height, width = ink.shape
    band_x, band_y = int(_BORDER_BAND * width), int(_BORDER_BAND * height)
    columns = _full_lines(ink, 0, width, FULL_RATIO)
    rows = _full_lines(np.ascontiguousarray(ink.T), 0, height, FULL_RATIO)
    left = [x for x in columns if x < band_x]
    right = [x for x in columns if x >= width - band_x]
    top = [y for y in rows if y < band_y]
    bottom = [y for y in rows if y >= height - band_y]
    return (
        max(left) + _PAD_PX if left else 0,
        max(top) + _PAD_PX if top else 0,
        min(right) - _PAD_PX if right else width,
        min(bottom) - _PAD_PX if bottom else height,
    )


def drawing_box(gray: NDArray[np.uint8]) -> Box | None:
    """Hộp `(x0, y0, x1, y1)` của vùng vẽ trong ảnh xám `(H, W)`; không có gì để bỏ: `None`.

    Thứ tự: khung tên cột phải, rồi dải dưới (trên phần còn lại), rồi nét viền sát mép.
    """
    background = int(np.argmax(np.bincount(gray.ravel(), minlength=256)))
    ink = np.asarray(gray <= background - INK_DELTA)
    height, width = ink.shape
    right = _title_divider(ink)
    x1 = right - _PAD_PX if right is not None else width
    bottom = _title_divider(np.ascontiguousarray(ink[:, :x1].T))
    y1 = bottom - _PAD_PX if bottom is not None else height
    box = _border_inset(ink[:y1, :x1])
    return None if box == (0, 0, width, height) else box


def drawing_quad(img: RgbImage, frame: Quad | None, *, max_pixels: int = DEFAULT_MAX_PIXELS) -> Quad | None:
    """Khung `frame` (hay cả trang khi `None`) thu về vùng vẽ, trong toạ độ ảnh `img`; không bỏ được gì: `frame`.

    Dò trên trang đã nắn theo `frame` (khung thẳng trục thì là cắt, không nội suy), rồi đưa bốn góc
    hộp vùng vẽ ngược về ảnh gốc qua nghịch đảo homography — nên bước nắn sau cùng chỉ nắn một lần.
    """
    if frame is None:
        base_pixels, back = img.pixels, np.eye(3)
    else:
        base = rectify(img, frame, max_pixels=max_pixels)
        base_pixels, back = base.image.pixels, np.linalg.inv(base.homography.as_array())
    box = drawing_box(np.asarray(cv2.cvtColor(base_pixels, cv2.COLOR_RGB2GRAY), dtype=np.uint8))
    if box is None:
        return frame
    x0, y0, x1, y1 = box
    corners = np.array([[x0, y0, 1.0], [x1, y0, 1.0], [x1, y1, 1.0], [x0, y1, 1.0]]).T
    mapped = back @ corners
    points = [(float(mapped[0, k] / mapped[2, k]), float(mapped[1, k] / mapped[2, k])) for k in range(4)]
    return Quad((points[0], points[1], points[2], points[3]))
