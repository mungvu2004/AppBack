"""Ảnh tổng hợp cho test B2-05b, dựng lúc chạy (không commit nhị phân); R dùng lại.

Chữ ký công khai: `png_bytes(pixels)`, `jpeg_bytes(pixels)`, `straight_drawing(w, h)`,
`tilted_drawing(angle_deg, w, h)`, `desk_shot(w, h) -> DeskShot(pixels, corners)`,
`a1_pdf()`, `huge_png()`, `truncated_png()`. Dựa trên bộ dựng của B2-05a
(`packages/vision/preprocess/tests/{drawing,synthetic}.py`), không sửa chúng.

Mọi hàm ở đây là **hàm thuần của tham số** (không seed ngẫu nhiên trừ `noisy_scan_png`, mà
nó cũng ghim seed), nên bản dựng được nhớ theo tham số cho cả tiến trình `pytest`. Số đo
một lượt dựng, cỡ của test route (PERF-01 BE-12): `png_bytes` **16,15 ms**, `truncated_png`
17,80 ms, `desk_shot()` 6,17 ms, `tilted_drawing` 1,49 ms, `desk_shot(600, 420)` 0,95 ms,
`straight_drawing()` 0,42 ms, `a1_pdf()` 0,48 ms. Đắt nhất — và gọi nhiều nhất — là `png_bytes`:
`_route_helpers.make_image_floor` gọi nó một lần **mỗi tầng mỗi test** trên cùng một ảnh mẫu.
`noisy_scan_png` (≈40 MP) và `huge_png` (0,01 ms) **không** nhớ: cái đầu chỉ có một người gọi
nên nhớ không mua được gì mà giữ chục MB, cái sau đã gần như không tốn gì.

Hàm trả `bytes` thì nhớ thẳng (bất biến). Hàm trả mảng numpy trả **bản sao** của bản nhớ
(`pixels.copy()` đo được 0,071 ms): người gọi sửa tại chỗ — như chính `desk_shot` vẽ thêm
một vạch bằng `cv2.line` — không được làm bẩn bản nhớ của test sau.
"""

import hashlib
from dataclasses import dataclass
from functools import cache
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

_PNG_BY_CONTENT: Final[dict[tuple[tuple[int, ...], bytes], bytes]] = {}
"""Byte PNG theo (cỡ mảng, vân tay nội dung) — sổ của `png_bytes`."""


@dataclass(frozen=True)
class DeskShot:
    """Ảnh chụp bản vẽ trên mặt bàn xám và 4 góc mép giấy thật (tỉ lệ khung ảnh, TL→TR→BR→BL)."""

    pixels: NDArray[np.uint8]
    corners: Ratios


def png_bytes(pixels: NDArray[np.uint8]) -> bytes:
    """Mảng RGB → byte PNG, nhớ theo **nội dung** mảng.

    Không nhớ được bằng `functools.cache` (mảng numpy không băm được), nên khoá là
    `(shape, blake2b(bytes))`. Vân tay tốn 2,29 ms so với 16,15 ms của lượt mã hoá, nên lượt
    thứ hai trên cùng ảnh rẻ đi ~14 ms. Giữ vân tay chứ không giữ chính 1,3 MB mảng byte:
    sáu tiến trình `pytest -n` mỗi tiến trình một sổ, bộ nhớ là thứ khan nhất của máy chạy cổng.
    `shape` nằm trong khoá vì hai mảng khác cỡ có thể cùng dãy byte mà PNG ra khác nhau.
    """
    key = (pixels.shape, hashlib.blake2b(pixels.tobytes(), digest_size=16).digest())
    cached = _PNG_BY_CONTENT.get(key)
    if cached is None:
        cached = _PNG_BY_CONTENT[key] = encode_png(RgbImage(pixels))
    return cached


def jpeg_bytes(pixels: NDArray[np.uint8]) -> bytes:
    """Mảng RGB → byte JPEG chất lượng cao (nét đen vẫn đủ để tìm khung)."""
    return encode(Image.fromarray(pixels), "JPEG", quality=95)


@cache
def _straight_drawing(width_px: int, height_px: int) -> NDArray[np.uint8]:
    """Bản dựng gốc của `straight_drawing` — người gọi công khai lấy bản sao."""
    return make_drawing(width_px, height_px, frame=True)


def straight_drawing(width_px: int = 1200, height_px: int = 850) -> NDArray[np.uint8]:
    """Bản vẽ có khung, thẳng."""
    return _straight_drawing(width_px, height_px).copy()


@cache
def _tilted_drawing(angle_deg: float, width_px: int, height_px: int) -> NDArray[np.uint8]:
    """Bản dựng gốc của `tilted_drawing` — người gọi công khai lấy bản sao."""
    return rotate(straight_drawing(width_px, height_px), angle_deg)


def tilted_drawing(angle_deg: float, width_px: int = 1200, height_px: int = 850) -> NDArray[np.uint8]:
    """Bản vẽ có khung xoay `angle_deg`°."""
    return _tilted_drawing(angle_deg, width_px, height_px).copy()


@cache
def _desk_shot(width_px: int, height_px: int) -> DeskShot:
    """Bản dựng gốc của `desk_shot` — người gọi công khai lấy bản sao của `pixels`."""
    desk_w, desk_h = width_px * 4 // 3, height_px * 4 // 3
    pixels, _frame, paper = on_desk(straight_drawing(width_px, height_px), desk_px=(desk_w, desk_h))
    y = round(desk_h * 0.985)
    cv2.line(pixels, (round(desk_w * 0.04), y), (round(desk_w * 0.96), y), (0, 0, 0), 6)
    r = quad_to_ratios(paper, desk_w, desk_h)
    return DeskShot(pixels, (r[0], r[1], r[2], r[3]))


def desk_shot(width_px: int = 1200, height_px: int = 850) -> DeskShot:
    """Bản vẽ có khung nắn phối cảnh lên mặt bàn xám lớn hơn tờ giấy 4/3 lần; góc thật là mép giấy.

    Một vạch đen ngoài mép giấy (trên mặt bàn) làm nét nằm ngoài khung, nên ảnh gốc **không**
    tìm được khung (`FRAME_NOT_FOUND`); nắn theo mép giấy loại vạch đó và khung hiện ra.
    """
    shot = _desk_shot(width_px, height_px)
    return DeskShot(shot.pixels.copy(), shot.corners)


@cache
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


@cache
def truncated_png() -> bytes:
    """PNG hợp lệ bị cắt còn nửa tệp (U07)."""
    data = png_bytes(straight_drawing())
    return data[: len(data) // 2]
