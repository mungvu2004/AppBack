"""Xử lý ảnh của #31/#32 (B2-05b [6]): nắn theo góc, dựng thẳng, trên hàng xử lý có trần.

Ảnh chỉ được xử lý trong `ThreadPoolExecutor` riêng của module, sau khi giữ được một chỗ
của semaphore **theo vòng sự kiện** (BE-00 §7, K28, K36); không giữ kết nối DB ở đây.
Chờ chỗ quá `quality_queue_wait_s` → 503 và **chưa** gửi việc. Không `wait_for` quanh
`run_in_executor`: huỷ chờ không dừng được luồng, chỉ làm lộ chỗ.

Các hàm B2-05a được nhập vào **tên cấp module** (`rectify`, `deskew`, …) và gọi qua tên đó,
để test đo hàng chờ thay được bằng `monkeypatch.setattr(processing, "rectify", ...)`.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Final

from apps.api.quality.errors import QUALITY_DRAWING_CHANGED
from apps.api.quality.geometry import Ratios
from apps.api.quality.settings import QualitySettings, get_quality_settings
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.vision.preprocess import (
    Homography,
    RgbImage,
    VisionError,
    compose,
    deskew,
    encode_png,
    load_raster,
    quad_from_ratios,
    rectify,
    render_pdf_page,
)
from packages.vision.quality import QualityReport, assess

RETRY_AFTER_S: Final = 2
"""`Retry-After` của 503 khi hàng đầy (prompt [6] bước 5)."""

_executor: ThreadPoolExecutor | None = None
_slots: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = weakref.WeakKeyDictionary()


@dataclass(frozen=True)
class ProcessedPage:
    """Trang mới: PNG, kích thước, báo cáo chất lượng và homography **trang chưa nắn → trang mới**."""

    png: bytes
    width_px: int
    height_px: int
    report: QualityReport
    homography: Homography


def _pool(workers: int) -> ThreadPoolExecutor:
    """Executor riêng của module, dựng lười ở lượt đầu với `quality_workers` luồng."""
    global _executor  # một executor mỗi tiến trình, như `apps/api/auth/passwords.py`
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="quality-imaging")
    return _executor


def _semaphore(workers: int) -> asyncio.Semaphore:
    """Semaphore của vòng đang chạy: `asyncio.Semaphore` gắn vào vòng đầu phải chờ nên không dùng chung được."""
    loop = asyncio.get_running_loop()
    slots = _slots.get(loop)
    if slots is None:
        slots = asyncio.Semaphore(workers)
        _slots[loop] = slots
    return slots


def reset_processing_state() -> None:
    """Chỉ cho test: bỏ semaphore và executor để `quality_workers` mới có hiệu lực."""
    global _executor
    _slots.clear()
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None


@asynccontextmanager
async def _slot(settings: QualitySettings) -> AsyncIterator[None]:
    """Giữ một chỗ; quá `quality_queue_wait_s` → 503 `retry_after=2` (chưa gửi việc), `release` trong `finally`."""
    slots = _semaphore(settings.quality_workers)
    try:
        await asyncio.wait_for(slots.acquire(), settings.quality_queue_wait_s)
    except TimeoutError as exc:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=RETRY_AFTER_S) from exc
    try:
        yield
    finally:
        slots.release()


async def _offload[ResultT](settings: QualitySettings, fn: Callable[[], ResultT]) -> ResultT:
    """Chạy `fn` trên executor riêng sau khi giữ chỗ; `VisionError` → `AppError` 422 mã đó."""
    async with _slot(settings):
        try:
            return await asyncio.get_running_loop().run_in_executor(_pool(settings.quality_workers), fn)
        except VisionError as exc:
            raise exc.to_app_error() from exc


def _finish(image: RgbImage, homography: Homography) -> ProcessedPage:
    """Đo chất lượng và mã hoá PNG của trang mới."""
    report = assess(image)
    return ProcessedPage(encode_png(image), image.width_px, image.height_px, report, homography)


def _corners_job(data: bytes, kind: str, page_index: int, ratios: Ratios, settings: QualitySettings) -> ProcessedPage:
    """Trang chưa nắn (raster hoặc PDF) → `rectify` theo góc tỉ lệ → đo → PNG. Chạy trong executor."""
    limit = settings.quality_max_pixels
    if kind == "pdf":
        base = render_pdf_page(data, page_index, dpi=settings.quality_pdf_dpi, max_pixels=limit)
    else:
        base = load_raster(data, max_pixels=limit)
    result = rectify(base, quad_from_ratios(ratios, base.width_px, base.height_px), max_pixels=limit)
    return _finish(result.image, result.homography)


def _straighten_job(page_png: bytes, old: Homography, settings: QualitySettings) -> ProcessedPage:
    """Trang đang dùng → `deskew` → nối với homography cũ → đo → PNG. Chạy trong executor.

    `compose` chỉ ném `VALIDATION` khi homography cũ lệch kích thước trang: không phải lỗi
    của người gọi mà là dữ liệu đã đổi → 409.
    """
    limit = settings.quality_max_pixels
    result = deskew(load_raster(page_png, max_pixels=limit), max_pixels=limit)
    try:
        homography = compose(result.homography, old)
    except VisionError as exc:
        raise QUALITY_DRAWING_CHANGED.error() from exc
    return _finish(result.image, homography)


async def process_corners(data: bytes, *, kind: str, page_index: int, corner_ratios: Ratios) -> ProcessedPage:
    """#31: nắn lại từ trang **chưa nắn** theo góc tỉ lệ; `kind` ∈ `png|jpeg|pdf`, `page_index` chỉ cho PDF.

    Góc suy ra sai (`rectify`) → 422 `VALIDATION field="corners"`; ảnh vượt trần → 422
    `IMAGE_TOO_LARGE`; tệp hỏng → 422 `FILE_CORRUPT`; hàng đầy → 503.
    """
    settings = get_quality_settings()
    return await _offload(settings, lambda: _corners_job(data, kind, page_index, corner_ratios, settings))


async def process_straighten(page_png: bytes, *, old_homography: Homography) -> ProcessedPage:
    """#32: dựng thẳng trang đang dùng; homography mới = `compose(H_deskew, old_homography)`.

    Homography cũ lệch kích thước trang → 409 `QUALITY_DRAWING_CHANGED`.
    """
    settings = get_quality_settings()
    return await _offload(settings, lambda: _straighten_job(page_png, old_homography, settings))
