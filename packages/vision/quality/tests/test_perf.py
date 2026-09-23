"""Trần thời gian của chuỗi tiền xử lý đầy đủ ở đúng trần điểm ảnh (khối [6] "Hiệu năng").

Hai ca: ảnh quét tổng hợp 7.745 x 5.164 (≈ 40 MP, sát `DEFAULT_MAX_PIXELS`) và trang
PDF A1 ở 200 DPI. Đo **sau một lượt khởi động** để không tính vào ngân sách phần nạp
module, cấp phát lần đầu của OpenCV và mở thư viện PDFium.
"""

import logging
import time
from collections.abc import Callable, Sequence
from typing import Final

import numpy as np
import pytest

from packages.vision.preprocess.geometry import deskew, find_frame, rectify
from packages.vision.preprocess.pdf import render_pdf_page
from packages.vision.preprocess.raster import encode_png, load_raster
from packages.vision.preprocess.tests.drawing import make_drawing
from packages.vision.preprocess.tests.synthetic import Rect, make_pdf
from packages.vision.preprocess.types import DEFAULT_MAX_PIXELS, Quad, RgbImage
from packages.vision.quality.assess import assess

_LOG = logging.getLogger(__name__)

_BUDGET_S: Final = 12.0
_SCAN_W, _SCAN_H = 7745, 5164
_A1_PT: Final = (1684.0, 2384.0)
_DPI: Final = 200.0
_WARMUP_PX: Final = (240, 170)
_NOISE_SEED: Final = 20250923
_INK: Final = (0.0, 0.0, 0.0)
_SCAN_MIN_PX: Final = 39_000_000
_A1_MIN_PX: Final = 30_000_000
"""Sàn số điểm ảnh của hai ca: chốt phép đo thật sự chạy ở đúng trần, không co lén."""


def _scan_png(sigma: float) -> bytes:
    """Bản vẽ 7.745 x 5.164 phủ nhiễu Gauss sigma, mã hoá PNG — đầu vào của `load_raster`.

    Nhiễu lấy từ `default_rng(seed)` cố định nên mỗi lần chạy cho đúng một dãy byte,
    tức thời gian đo được so sánh được giữa các lượt.
    """
    drawing = make_drawing(_SCAN_W, _SCAN_H).astype(np.float64)
    noise = np.random.default_rng(_NOISE_SEED).normal(0.0, sigma, drawing.shape)
    noisy = np.asarray(np.clip(drawing + noise, 0.0, 255.0), dtype=np.uint8)
    return encode_png(RgbImage(noisy))


def _a1_pdf() -> bytes:
    """Trang PDF A1 (1.684 x 2.384 pt) có khung và hai mảng nét — nguồn của ca PDF."""
    width, height = _A1_PT
    border, thick = 0.05 * width, 0.004 * width
    rects: Sequence[Rect] = (
        (border, border, width - 2 * border, thick, _INK),
        (border, height - border - thick, width - 2 * border, thick, _INK),
        (border, border, thick, height - 2 * border, _INK),
        (width - border - thick, border, thick, height - 2 * border, _INK),
        (0.3 * width, 0.3 * height, 0.4 * width, thick, _INK),
        (0.5 * width, 0.3 * height, thick, 0.4 * height, _INK),
    )
    return make_pdf(1, size=_A1_PT, rects=rects)


def _timed[T](steps: list[tuple[str, float]], name: str, run: Callable[[], T]) -> T:
    """Chạy `run`, nối `(name, giây)` vào `steps`, trả nguyên kết quả."""
    start = time.perf_counter()
    result = run()
    steps.append((name, time.perf_counter() - start))
    return result


def _chain(load: Callable[[], RgbImage]) -> tuple[RgbImage, list[tuple[str, float]]]:
    """Chạy nạp/dựng → `find_frame` → `rectify` → `deskew` → `assess` → `encode_png`.

    `rectify` dùng khung tìm được, hoặc cả trang khi `find_frame` trả `None`, để chuỗi
    luôn đi qua đủ sáu bước dù ảnh không có khung. Trả ảnh đã nạp và `(tên bước, giây)`
    theo thứ tự, để ca đo chốt được cả kích thước thật lẫn thời gian.
    """
    steps: list[tuple[str, float]] = []
    image = _timed(steps, "load", load)
    assert image.width_px * image.height_px <= DEFAULT_MAX_PIXELS
    frame = _timed(steps, "find_frame", lambda: find_frame(image))
    quad = frame if frame is not None else _whole_page(image)
    _timed(steps, "rectify", lambda: rectify(image, quad))
    _timed(steps, "deskew", lambda: deskew(image))
    _timed(steps, "assess", lambda: assess(image))
    _timed(steps, "encode_png", lambda: encode_png(image, compress_level=1))
    return image, steps


def _whole_page(image: RgbImage) -> Quad:
    """Bốn góc của cả trang — khung thay thế khi `find_frame` không thấy khung nào."""
    w, h = float(image.width_px - 1), float(image.height_px - 1)
    return Quad(((0.0, 0.0), (w, 0.0), (w, h), (0.0, h)))


def _warm_up() -> None:
    """Một lượt chuỗi đầy đủ trên ảnh nhỏ: nạp module, mở PDFium, cấp phát lần đầu."""
    small = make_drawing(*_WARMUP_PX)
    _chain(lambda: RgbImage(small))
    render_pdf_page(make_pdf(1), 0, dpi=36.0)


def _log_steps(label: str, steps: Sequence[tuple[str, float]]) -> float:
    """In thời gian từng bước và tổng; trả tổng (giây)."""
    total = sum(seconds for _, seconds in steps)
    detail = "  ".join(f"{name}={seconds:.2f}s" for name, seconds in steps)
    _LOG.info("%s: %s  tổng=%.2fs (trần %.0fs)", label, detail, total, _BUDGET_S)
    return total


@pytest.fixture(scope="module")
def warm() -> None:
    """Lượt khởi động dùng chung cho mọi ca đo trong module."""
    _warm_up()


@pytest.mark.perf
@pytest.mark.usefixtures("warm")
def test_perf_full_chain_on_forty_megapixel_scan() -> None:
    """Ảnh quét 7.745 x 5.164 nhiễu Gauss sigma = 8 qua PNG: cả chuỗi dưới 12 giây."""
    data = _scan_png(8.0)
    image, steps = _chain(lambda: load_raster(data))
    assert image.width_px * image.height_px >= _SCAN_MIN_PX
    assert _log_steps("quét 40 MP sigma=8", steps) < _BUDGET_S


@pytest.mark.perf
@pytest.mark.usefixtures("warm")
def test_perf_full_chain_on_noisier_scan_is_only_logged() -> None:
    """Cùng ảnh với sigma = 24 (PNG nén kém hơn nhiều): chỉ in thời gian, không so trần."""
    data = _scan_png(24.0)
    image, steps = _chain(lambda: load_raster(data))
    assert image.width_px * image.height_px >= _SCAN_MIN_PX
    assert _log_steps("quét 40 MP sigma=24 (không so trần)", steps) > 0.0


@pytest.mark.perf
@pytest.mark.usefixtures("warm")
def test_perf_full_chain_on_a1_pdf_page() -> None:
    """Trang PDF A1 ở 200 DPI (≈ 31 MP): cả chuỗi dưới 12 giây."""
    data = _a1_pdf()
    image, steps = _chain(lambda: render_pdf_page(data, 0, dpi=_DPI))
    assert image.width_px * image.height_px >= _A1_MIN_PX
    assert _log_steps("PDF A1 @200 DPI", steps) < _BUDGET_S
