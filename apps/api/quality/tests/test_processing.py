"""Test xử lý ảnh có hàng (B2-05b [6] #31 bước 5, #32 bước 3-5, [8] Nắn/Hoàn tác/Hàng xử lý/U03/U07)."""

import asyncio
import threading
import time
from collections.abc import Iterator
from typing import Any

import numpy as np
import pytest

from apps.api.quality import processing
from apps.api.quality.errors import QUALITY_DRAWING_CHANGED
from apps.api.quality.geometry import Ratios, to_unrectified
from apps.api.quality.processing import ProcessedPage, process_corners, process_straighten
from apps.api.quality.settings import reset_quality_settings_cache
from apps.api.quality.tests._images import (
    a1_pdf,
    desk_shot,
    huge_png,
    jpeg_bytes,
    png_bytes,
    straight_drawing,
    tilted_drawing,
    truncated_png,
)
from packages.core.errors import AppError
from packages.vision.preprocess import (
    Homography,
    RgbImage,
    compose,
    deskew,
    load_raster,
    quad_from_ratios,
    rectify,
    render_pdf_page,
)
from packages.vision.preprocess.tests.synthetic import make_pdf
from packages.vision.quality import assess

INNER: Ratios = ((0.1, 0.1), (0.9, 0.12), (0.88, 0.9), (0.12, 0.9))
CALLS = 5
PDF_CORNERS: Ratios = ((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95))


@pytest.fixture(autouse=True)
def _fresh_state() -> Iterator[None]:
    """Mỗi test bắt đầu và kết thúc với cấu hình, semaphore, executor sạch."""
    reset_quality_settings_cache()
    processing.reset_processing_state()
    yield
    reset_quality_settings_cache()
    processing.reset_processing_state()


def _codes(page: ProcessedPage) -> set[str]:
    """Mã chất lượng trong báo cáo của trang."""
    return {f.code for f in page.report.findings}


def _assert_maps_corners(page: ProcessedPage, corners: Ratios, source: tuple[int, int]) -> None:
    """Homography đưa 4 góc nguồn về 4 góc của trang mới, lệch ≤ 1 px."""
    h = page.homography
    assert (h.source_width_px, h.source_height_px) == source
    assert (h.width_px, h.height_px) == (page.width_px, page.height_px)
    target = [(0, 0), (page.width_px, 0), (page.width_px, page.height_px), (0, page.height_px)]
    matrix = h.as_array()
    for (rx, ry), (tx, ty) in zip(corners, target, strict=True):
        v = matrix @ np.array([rx * source[0], ry * source[1], 1.0])
        assert abs(v[0] / v[2] - tx) <= 1.0
        assert abs(v[1] / v[2] - ty) <= 1.0


def _raised(exc: BaseException | None, code: str, status: int) -> AppError:
    """Khẳng định `exc` là `AppError` đúng mã và status."""
    assert isinstance(exc, AppError)
    assert (exc.code.code, exc.code.status) == (code, status)
    return exc


@pytest.mark.parametrize("encode", [png_bytes, jpeg_bytes], ids=["png", "jpeg"])
async def test_process_corners__raster_finds_frame(encode: Any) -> None:
    """Ảnh có khung chụp nghiêng: trang mới thấy khung, homography đưa góc nguồn về góc đích."""
    shot = desk_shot()
    data = encode(shot.pixels)
    before = assess(load_raster(data))
    assert "FRAME_NOT_FOUND" in {f.code for f in before.findings}
    page = await process_corners(data, kind="png", page_index=0, corner_ratios=shot.corners)
    assert "FRAME_NOT_FOUND" not in _codes(page)
    assert page.report.frame is not None
    _assert_maps_corners(page, shot.corners, (shot.pixels.shape[1], shot.pixels.shape[0]))
    decoded = load_raster(page.png)
    assert (decoded.width_px, decoded.height_px) == (page.width_px, page.height_px)


async def test_process_corners__pdf_page_index() -> None:
    """Gốc PDF: dựng đúng trang `page_index` ở DPI cấu hình, homography nguồn là kích thước trang dựng."""
    data = make_pdf(2, rects=((50.0, 50.0, 400.0, 600.0, (0.0, 0.0, 0.0)),))
    base = render_pdf_page(data, 1, dpi=200, max_pixels=40_000_000)
    page = await process_corners(data, kind="pdf", page_index=1, corner_ratios=PDF_CORNERS)
    _assert_maps_corners(page, PDF_CORNERS, (base.width_px, base.height_px))


async def test_process_corners__bad_quad_is_validation() -> None:
    """Góc lọt luật tỉ lệ nhưng quá nhỏ theo điểm ảnh → 422 `VALIDATION field="corners"`."""
    tiny: Ratios = ((0.4, 0.4), (0.41, 0.4), (0.41, 0.41), (0.4, 0.41))
    with pytest.raises(AppError) as info:
        await process_corners(png_bytes(straight_drawing()), kind="png", page_index=0, corner_ratios=tiny)
    assert _raised(info.value, "VALIDATION", 422).wire_params() == {"field": "corners"}


async def test_process_corners__undo_does_not_stack() -> None:
    """Nắn theo C1 rồi quay lại C0 (tỉ lệ trên trang chưa nắn) = dựng thẳng từ C0, không nắn chồng."""
    shot = desk_shot()
    data = png_bytes(shot.pixels)
    first = await process_corners(data, kind="png", page_index=0, corner_ratios=shot.corners)
    unrectified = to_unrectified(
        INNER, page_width_px=first.width_px, page_height_px=first.height_px, homography=first.homography
    )
    second = await process_corners(data, kind="png", page_index=0, corner_ratios=unrectified)
    assert second.png != first.png
    back = await process_corners(data, kind="png", page_index=0, corner_ratios=shot.corners)
    base = RgbImage(shot.pixels)
    direct = rectify(base, quad_from_ratios(shot.corners, base.width_px, base.height_px)).image
    assert np.array_equal(load_raster(back.png).pixels, direct.pixels)
    assert back.png == first.png


@pytest.mark.parametrize("angle", [4.0, 0.0])
async def test_process_straighten__skew_and_composition(angle: float) -> None:
    """Ảnh nghiêng 4° → skew mới < 0,5; ảnh thẳng giữ nguyên; homography = compose(H_deskew, H_cũ)."""
    png = png_bytes(tilted_drawing(angle))
    old = Homography.identity(1200, 850)
    before = assess(load_raster(png)).measurement.skew_deg
    page = await process_straighten(png, old_homography=old)
    assert abs(page.report.measurement.skew_deg) < 0.5
    assert abs(before) > 3.0 if angle else abs(before) < 0.5
    expected = compose(deskew(load_raster(png)).homography, old)
    assert page.homography == expected
    assert (page.width_px, page.height_px) == (expected.width_px, expected.height_px)


async def test_process_straighten__stale_homography_is_conflict() -> None:
    """Homography cũ lệch kích thước trang → 409 `QUALITY_DRAWING_CHANGED`."""
    png = png_bytes(tilted_drawing(4.0))
    with pytest.raises(AppError) as info:
        await process_straighten(png, old_homography=Homography.identity(999, 850))
    assert info.value.code is QUALITY_DRAWING_CHANGED


async def test_process_corners__U03_huge_declared_size() -> None:
    """PNG khai 20 000 x 20 000 → 422 `IMAGE_TOO_LARGE`, không giải mã."""
    with pytest.raises(AppError) as info:
        await process_corners(huge_png(), kind="png", page_index=0, corner_ratios=INNER)
    _raised(info.value, "IMAGE_TOO_LARGE", 422)


async def test_process_corners__U07_truncated_source() -> None:
    """Gốc cụt → 422 `FILE_CORRUPT`."""
    with pytest.raises(AppError) as info:
        await process_corners(truncated_png(), kind="png", page_index=0, corner_ratios=INNER)
    _raised(info.value, "FILE_CORRUPT", 422)


def _saturate(
    monkeypatch: pytest.MonkeyPatch, data: bytes, corners: Ratios, *, workers: int
) -> tuple[list[BaseException], int, set[str]]:
    """Năm lời gọi song song trên hàng `workers` chỗ, `rectify` chờ cổng; trả (lỗi bị từ chối, số lần chạy, tên luồng).

    Mỗi lần gọi dựng vòng sự kiện mới (`asyncio.run`) nên cũng kiểm semaphore theo vòng.
    """
    real = rectify
    gate = threading.Event()
    threads: list[str] = []

    def slow(*args: Any, **kwargs: Any) -> Any:
        """`rectify` chờ cổng trong luồng executor và ghi tên luồng đó."""
        threads.append(threading.current_thread().name)
        assert gate.wait(20)
        return real(*args, **kwargs)

    monkeypatch.setattr(processing, "rectify", slow)

    async def scenario() -> list[BaseException]:
        """5 lời gọi cùng lúc trên hai chỗ; trả các lỗi của lời bị từ chối."""
        tasks = [
            asyncio.create_task(process_corners(data, kind="png", page_index=0, corner_ratios=corners))
            for _ in range(CALLS)
        ]
        refused: set[asyncio.Task[ProcessedPage]] = set()
        while len(refused) < CALLS - workers:  # lời vượt số chỗ bị từ chối sau `quality_queue_wait_s`
            done, _ = await asyncio.wait(set(tasks) - refused, timeout=20, return_when=asyncio.FIRST_COMPLETED)
            assert done, "không lời gọi nào trả lời trong hạn"
            refused |= done
        gate.set()
        await asyncio.gather(*(set(tasks) - refused))
        return [e for e in (t.exception() for t in refused) if e is not None]

    rejected = asyncio.run(scenario())
    return rejected, len(threads), set(threads)


def test_process_corners__queue_full_and_new_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    """2 chỗ, 5 lời gọi: 2 chạy `rectify`, 3 nhận 503 `retry_after=2` và không việc nào chạy sau đó; lặp ở vòng mới."""
    monkeypatch.setenv("QUALITY_WORKERS", "2")
    monkeypatch.setenv("QUALITY_QUEUE_WAIT_S", "0.3")
    reset_quality_settings_cache()
    processing.reset_processing_state()
    shot = desk_shot()
    data = png_bytes(shot.pixels)
    for _ in range(2):  # vòng sự kiện thứ hai không được `RuntimeError` vì semaphore của vòng đầu
        rejected, ran, names = _saturate(monkeypatch, data, shot.corners, workers=2)
        assert ran == 2
        assert len(rejected) == 3
        for exc in rejected:
            assert _raised(exc, "DEPENDENCY_UNAVAILABLE", 503).retry_after == 2
        assert all(name.startswith("quality-imaging") for name in names)


def test_reset_processing_state__applies_new_workers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đổi `QUALITY_WORKERS` rồi reset thì hàng dựng lại theo số mới: 3 việc chạy đồng thời, 2 bị từ chối.

    Kiểm bằng hành vi công khai (số lần `rectify` chạy và tên luồng), không đọc trạng thái riêng của module.
    """
    monkeypatch.setenv("QUALITY_QUEUE_WAIT_S", "0.3")
    shot = desk_shot()
    data = png_bytes(shot.pixels)
    for workers in (2, 3):
        monkeypatch.setenv("QUALITY_WORKERS", str(workers))
        reset_quality_settings_cache()
        processing.reset_processing_state()
        rejected, ran, names = _saturate(monkeypatch, data, shot.corners, workers=workers)
        assert (ran, len(rejected)) == (workers, CALLS - workers)
        assert 1 < len(names) <= workers
        assert all(name.startswith("quality-imaging") for name in names)


@pytest.mark.perf
async def test_process_corners__a1_pdf_200dpi_timing() -> None:
    """In thời gian `process_corners` với PDF A1 200 DPI (R đo trần ở route, không so ở đây)."""
    started = time.perf_counter()
    page = await process_corners(a1_pdf(), kind="pdf", page_index=0, corner_ratios=PDF_CORNERS)
    print(f"process_corners A1 200dpi: {time.perf_counter() - started:.2f}s, {page.width_px}x{page.height_px}")
    assert page.width_px > 4000
