"""Bộ dựng bản vẽ tổng hợp cho test: không commit ảnh nhị phân, dựng lúc chạy.

Hoàn toàn tất định (không số ngẫu nhiên) nên ngưỡng trong test ổn định giữa các
lần chạy. Việc gộp B2-05a dùng lại module này cho 7 ảnh của `assess` và test hiệu
năng, nên `make_drawing`, `rotate`, `on_desk` giữ nguyên chữ ký.
"""

from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.geometry import order_corners
from packages.vision.preprocess.types import Point, Quad

FRAME_MARGIN: Final = 0.03
"""Lề khung bản vẽ so với mép giấy; `on_desk` suy ra góc khung từ hằng này."""

_BLACK: Final = (0, 0, 0)
_WALL_INSET: Final = 0.16
_DIM_INSET_WITH_FRAME: Final = 0.09
_DIM_INSET_NO_FRAME: Final = 0.05
_DIM_STEP: Final = 0.04
_DESK_QUAD: Final = ((0.09, 0.05), (0.93, 0.10), (0.90, 0.94), (0.06, 0.90))
"""Bốn góc giấy trên mặt bàn theo tỉ lệ khung ảnh — phối cảnh nghiêng cố định."""


def _rect(canvas: NDArray[np.uint8], box: tuple[int, int, int, int], thickness: int) -> None:
    """Vẽ khung chữ nhật đen `(x0, y0, x1, y1)`."""
    cv2.rectangle(canvas, (box[0], box[1]), (box[2], box[3]), _BLACK, thickness)


def _dimension_lines(
    canvas: NDArray[np.uint8], box: tuple[int, int, int, int], inset: tuple[int, int], thickness: int
) -> None:
    """Hai đường kích thước (một dọc, một ngang) kèm vạch đầu mút, ở `inset` tính từ mép ảnh.

    Đặt ngoài tường bao khi bản vẽ không có khung, để `find_frame` thấy tứ giác
    tường bao **không** bao hết nét và trả `None`.
    """
    tick = max(6, thickness * 5)
    x, y = inset
    cv2.line(canvas, (x, box[1]), (x, box[3]), _BLACK, thickness)
    cv2.line(canvas, (box[0], y), (box[2], y), _BLACK, thickness)
    for end in (box[1], box[3]):
        cv2.line(canvas, (x - tick, end), (x + tick, end), _BLACK, thickness)
    for end in (box[0], box[2]):
        cv2.line(canvas, (end, y - tick), (end, y + tick), _BLACK, thickness)


def make_drawing(width_px: int = 2400, height_px: int = 1700, *, frame: bool = True) -> NDArray[np.uint8]:
    """Bản vẽ trên giấy trắng: khung nét dày (lề 3 %), tường bao, tường trong, đường kích thước.

    `frame=False` bỏ khung và đẩy hai cặp đường kích thước ra **ngoài** tường bao —
    khi đó không tứ giác nào vừa đủ lớn vừa bao ≥ 97 % nét, nên `find_frame` trả `None`.
    Trả mảng `(H, W, 3)` uint8 RGB (nét đen nên RGB và BGR trùng nhau).
    """
    canvas = np.full((height_px, width_px, 3), 255, dtype=np.uint8)
    thickness = max(3, width_px // 300)
    if frame:
        margin_x, margin_y = round(width_px * FRAME_MARGIN), round(height_px * FRAME_MARGIN)
        _rect(canvas, (margin_x, margin_y, width_px - margin_x, height_px - margin_y), thickness)
    wall_x, wall_y = round(width_px * _WALL_INSET), round(height_px * _WALL_INSET)
    walls = (wall_x, wall_y, width_px - wall_x, height_px - wall_y)
    _rect(canvas, walls, thickness)
    split_x, split_y = round(width_px * 0.5), round(height_px * 0.62)
    cv2.line(canvas, (split_x, walls[1]), (split_x, split_y), _BLACK, thickness)
    cv2.line(canvas, (split_x, split_y), (walls[2], split_y), _BLACK, thickness)
    cv2.line(canvas, (round(width_px * 0.3), walls[1]), (round(width_px * 0.3), walls[3]), _BLACK, thickness)
    base = _DIM_INSET_WITH_FRAME if frame else _DIM_INSET_NO_FRAME
    thin = max(2, thickness // 3)
    for step in (0.0, _DIM_STEP):
        inset = (round(width_px * (base + step)), round(height_px * (base + step)))
        _dimension_lines(canvas, walls, inset, thin)
    return canvas


def rotate(pixels: NDArray[np.uint8], angle_deg: float) -> NDArray[np.uint8]:
    """Xoay quanh tâm, giữ nguyên kích thước, nền trắng — nguồn nghiêng chuẩn của test dấu góc."""
    height, width = int(pixels.shape[0]), int(pixels.shape[1])
    matrix = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), angle_deg, 1.0)
    turned = cv2.warpAffine(
        pixels,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255.0, 255.0, 255.0),
    )
    return np.asarray(turned, dtype=np.uint8)


def _transform(matrix: NDArray[np.float64], points: list[Point]) -> Quad:
    """Đưa 4 điểm qua phép phối cảnh rồi sắp lại theo thứ tự chuẩn."""
    source = np.array([points], dtype=np.float32)
    moved = cv2.perspectiveTransform(source, matrix)[0]
    return order_corners([(float(x), float(y)) for x, y in moved])


def on_desk(
    pixels: NDArray[np.uint8], *, desk_px: tuple[int, int] | None = None, desk_gray: int = 110
) -> tuple[NDArray[np.uint8], Quad, Quad]:
    """Đặt tờ giấy lên mặt bàn xám bằng một phép phối cảnh nghiêng cố định.

    Trả `(ảnh, góc khung vẽ, góc mép giấy)`; góc khung suy ra từ `FRAME_MARGIN`
    nên chỉ đúng với ảnh do `make_drawing(frame=True)` dựng. `desk_px` mặc định
    bằng kích thước tờ giấy.
    """
    height, width = int(pixels.shape[0]), int(pixels.shape[1])
    desk_w, desk_h = desk_px if desk_px is not None else (width, height)
    paper = [(0.0, 0.0), (width - 1.0, 0.0), (width - 1.0, height - 1.0), (0.0, height - 1.0)]
    dest = [(x * desk_w, y * desk_h) for x, y in _DESK_QUAD]
    matrix = np.asarray(
        cv2.getPerspectiveTransform(np.array(paper, dtype=np.float32), np.array(dest, dtype=np.float32)),
        dtype=np.float64,
    )
    warped = cv2.warpPerspective(
        pixels,
        matrix,
        (desk_w, desk_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(float(desk_gray),) * 3,
    )
    margin_x, margin_y = round(width * FRAME_MARGIN), round(height * FRAME_MARGIN)
    frame = [
        (float(margin_x), float(margin_y)),
        (float(width - margin_x), float(margin_y)),
        (float(width - margin_x), float(height - margin_y)),
        (float(margin_x), float(height - margin_y)),
    ]
    return np.asarray(warped, dtype=np.uint8), _transform(matrix, frame), _transform(matrix, paper)
