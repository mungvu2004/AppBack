"""Ảnh tổng hợp cho test B2-05b, dựng lúc chạy (không commit nhị phân); R dùng lại.

Chữ ký công khai: `png_bytes(pixels)`, `jpeg_bytes(pixels)`, `straight_drawing(w, h)`,
`tilted_drawing(angle_deg, w, h)`, `desk_shot(w, h) -> DeskShot(pixels, corners)`,
`a1_pdf()`, `huge_png()`, `truncated_png()`. Dựa trên bộ dựng của B2-05a
(`packages/vision/preprocess/tests/{drawing,synthetic}.py`), không sửa chúng.
"""

from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from apps.api.quality.geometry import Ratios
from packages.vision.preprocess import RgbImage, encode_png, quad_to_ratios
from packages.vision.preprocess.tests.drawing import make_drawing, on_desk, rotate
from packages.vision.preprocess.tests.synthetic import encode, make_pdf, png_declaring

A1_PT: Final = (1684.0, 2384.0)
"""Khổ A1 theo point (594 x 841 mm)."""


@dataclass(frozen=True)
class DeskShot:
    """Ảnh chụp bản vẽ trên mặt bàn xám và 4 góc mép giấy thật (tỉ lệ khung ảnh, TL→TR→BR→BL)."""

    pixels: NDArray[np.uint8]
    corners: Ratios


def png_bytes(pixels: NDArray[np.uint8]) -> bytes:
    """Mảng RGB → byte PNG."""
    return encode_png(RgbImage(pixels))


def jpeg_bytes(pixels: NDArray[np.uint8]) -> bytes:
    """Mảng RGB → byte JPEG chất lượng cao (nét đen vẫn đủ để tìm khung)."""
    return encode(Image.fromarray(pixels), "JPEG", quality=95)


def straight_drawing(width_px: int = 1200, height_px: int = 850) -> NDArray[np.uint8]:
    """Bản vẽ có khung, thẳng."""
    return make_drawing(width_px, height_px, frame=True)


def tilted_drawing(angle_deg: float, width_px: int = 1200, height_px: int = 850) -> NDArray[np.uint8]:
    """Bản vẽ có khung xoay `angle_deg`°."""
    return rotate(straight_drawing(width_px, height_px), angle_deg)


def desk_shot(width_px: int = 1200, height_px: int = 850) -> DeskShot:
    """Bản vẽ có khung nắn phối cảnh lên mặt bàn xám lớn hơn tờ giấy 4/3 lần; góc thật là mép giấy.

    Một vạch đen ngoài mép giấy (trên mặt bàn) làm nét nằm ngoài khung, nên ảnh gốc **không**
    tìm được khung (`FRAME_NOT_FOUND`); nắn theo mép giấy loại vạch đó và khung hiện ra.
    """
    desk_w, desk_h = width_px * 4 // 3, height_px * 4 // 3
    pixels, _frame, paper = on_desk(straight_drawing(width_px, height_px), desk_px=(desk_w, desk_h))
    y = round(desk_h * 0.985)
    cv2.line(pixels, (round(desk_w * 0.04), y), (round(desk_w * 0.96), y), (0, 0, 0), 6)
    r = quad_to_ratios(paper, desk_w, desk_h)
    return DeskShot(pixels, (r[0], r[1], r[2], r[3]))


def a1_pdf() -> bytes:
    """PDF một trang A1 (200 DPI ≈ 31 triệu điểm ảnh) có nội dung bản vẽ chứ không phải trang trắng.

    Khung ngoài, lưới tường dày, và hai hàng vạch kích thước: đủ nét để `find_frame`, `deskew`
    và `assess` làm việc thật khi đo thời gian (ca perf), không chỉ dựng trang trống.
    """
    width, height = A1_PT
    ink = (0.0, 0.0, 0.0)
    border, thick = 0.05 * width, 0.004 * width
    rects = [
        (border, border, width - 2 * border, thick, ink),
        (border, height - border - thick, width - 2 * border, thick, ink),
        (border, border, thick, height - 2 * border, ink),
        (width - border - thick, border, thick, height - 2 * border, ink),
    ]
    for index in range(1, 12):  # tường dọc
        x = border + index * (width - 2 * border) / 12
        rects.append((x, 0.2 * height, thick, 0.6 * height, ink))
    for index in range(1, 8):  # tường ngang
        y = 0.2 * height + index * 0.6 * height / 8
        rects.append((border * 2, y, width - 4 * border, thick, ink))
    for index in range(60):  # vạch kích thước
        x = border * 2 + index * (width - 4 * border) / 60
        rects.append((x, 0.12 * height, thick / 2, 0.02 * height, ink))
        rects.append((x, 0.86 * height, thick / 2, 0.02 * height, ink))
    return make_pdf(1, size=A1_PT, rects=rects)


def noisy_scan_png(width_px: int = 7745, height_px: int = 5164, sigma: float = 8.0) -> bytes:
    """Ảnh quét ≈ 40 MP: bản vẽ có khung phủ nhiễu Gauss `sigma` (seed cố định), mã hoá PNG.

    Ca nặng nhất của #31: PNG lớn phải giải mã, nắn và đo ở sát trần `QUALITY_MAX_PIXELS`.
    """
    drawing = straight_drawing(width_px, height_px).astype(np.float64)
    noise = np.random.default_rng(20250923).normal(0.0, sigma, drawing.shape)
    return png_bytes(np.asarray(np.clip(drawing + noise, 0.0, 255.0), dtype=np.uint8))


def huge_png() -> bytes:
    """PNG khai 20 000 x 20 000, chỉ có đầu tệp (U03)."""
    return png_declaring(20_000, 20_000)


def truncated_png() -> bytes:
    """PNG hợp lệ bị cắt còn nửa tệp (U07)."""
    data = png_bytes(straight_drawing())
    return data[: len(data) // 2]
