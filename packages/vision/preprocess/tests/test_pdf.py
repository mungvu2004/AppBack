"""Đếm trang, khổ trang, dựng trang PDF (U04, U06, U07) và an toàn luồng của pdfium."""

import math
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from PIL import Image

from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.pdf import effective_dpi, pdf_page_count, pdf_page_size_pt, render_pdf_page
from packages.vision.preprocess.tests import synthetic

_RED = (1.0, 0.0, 0.0)
_RED_SQUARE: list[synthetic.Rect] = [(0.0, 0.0, 200.0, 200.0, _RED)]
_INDEXED_CALLS: list[Callable[[bytes, int], object]] = [render_pdf_page, pdf_page_size_pt]


def test_pdf_page_count_three_pages() -> None:
    """Số trang lấy từ PDFium, không từ `/Count` khai trong tệp."""
    assert pdf_page_count(synthetic.make_pdf(3)) == 3


def test_pdf_page_count_u04_zero_pages() -> None:
    """`/Count 0`: tệp hợp lệ nhưng không có trang nào để đọc → `PDF_UNREADABLE`."""
    with pytest.raises(VisionError) as excinfo:
        pdf_page_count(synthetic.make_pdf(0))
    assert str(excinfo.value) == "PDF_UNREADABLE"


def test_pdf_page_count_u04_owner_password_only() -> None:
    """Chỉ đặt mật khẩu chủ: PDFium mở được bằng mật khẩu người dùng rỗng → xử lý bình thường."""
    data = synthetic.make_pdf(2, encrypt="owner_only", rects=_RED_SQUARE)
    assert pdf_page_count(data) == 2
    assert render_pdf_page(data, 0).width_px > 0


def test_pdf_page_count_u04_user_password() -> None:
    """Có mật khẩu người dùng → không mở nổi, và đó là lỗi bảo mật chứ không phải tệp hỏng."""
    with pytest.raises(VisionError) as excinfo:
        pdf_page_count(synthetic.make_pdf(1, encrypt="user_password"))
    assert str(excinfo.value) == "PDF_UNREADABLE"


def test_pdf_page_count_u07_header_then_garbage() -> None:
    """`%PDF-1.4` rồi rác: nhận là PDF nhưng không có cấu trúc → `FILE_CORRUPT`."""
    with pytest.raises(VisionError) as excinfo:
        pdf_page_count(b"%PDF-1.4\n" + b"\x01\x02\x03garbage" * 40)
    assert str(excinfo.value) == "FILE_CORRUPT"


def _count_or_code(data: bytes) -> int | str:
    """Số trang, hoặc mã lỗi nếu không đọc nổi — cho test chấp nhận đúng hai kết cục."""
    try:
        return pdf_page_count(data)
    except VisionError as error:
        return str(error)


def test_pdf_page_count_u07_truncated_half() -> None:
    """PDF thật cắt 50 %: hoặc đếm được, hoặc `FILE_CORRUPT` — không ngoại lệ lạ nào lọt ra."""
    data = synthetic.make_pdf(4, rects=_RED_SQUARE)
    outcome = _count_or_code(data[: len(data) // 2])
    assert outcome == "FILE_CORRUPT" or (isinstance(outcome, int) and outcome > 0)


def test_pdf_page_count_file_type_mismatch() -> None:
    """Tệp không phải PDF không bao giờ được đưa vào PDFium."""
    png = synthetic.encode(Image.new("RGB", (4, 4), (0, 0, 0)), "PNG")
    with pytest.raises(VisionError) as excinfo:
        pdf_page_count(png)
    assert str(excinfo.value) == "FILE_TYPE_MISMATCH"


def test_pdf_page_size_pt_a4() -> None:
    """Khổ trang trả theo point của PDFium, không qua bước dựng ảnh."""
    width_pt, height_pt = pdf_page_size_pt(synthetic.make_pdf(1), 0)
    assert (width_pt, height_pt) == pytest.approx((595.0, 842.0), abs=0.01)


def test_pdf_rotate_90_swaps_page_and_image() -> None:
    """`/Rotate 90` hoán đổi rộng/cao của **cả** khổ trang lẫn ảnh dựng ra."""
    upright = synthetic.make_pdf(1, rects=_RED_SQUARE)
    rotated = synthetic.make_pdf(1, rotate=90, rects=_RED_SQUARE)
    assert pdf_page_size_pt(rotated, 0) == pytest.approx(pdf_page_size_pt(upright, 0)[::-1], abs=0.01)
    straight_image, turned_image = render_pdf_page(upright, 0, dpi=36), render_pdf_page(rotated, 0, dpi=36)
    assert (turned_image.width_px, turned_image.height_px) == (straight_image.height_px, straight_image.width_px)


def test_render_pdf_page_red_square_lands_bottom_left() -> None:
    """Ô vuông đỏ vẽ ở gốc PDF (dưới-trái) phải ra đúng góc dưới-trái của ảnh."""
    image = render_pdf_page(synthetic.make_pdf(1, rects=_RED_SQUARE), 0, dpi=72)
    pixels = image.pixels
    assert pixels[image.height_px - 10, 10] == pytest.approx(np.array([255, 0, 0]), abs=2)
    assert pixels[10, image.width_px - 10] == pytest.approx(np.array([255, 255, 255]), abs=2)


@pytest.mark.parametrize("size", [(5000.0, 5000.0), (4999.7, 5000.3)])
def test_render_pdf_page_u06_huge_page(size: tuple[float, float]) -> None:
    """Trang khổ khổng lồ chỉ bị hạ DPI, không bị từ chối; ảnh sát trần và giữ tỉ lệ."""
    max_pixels = 4_000_000
    image = render_pdf_page(synthetic.make_pdf(1, size=size, rects=_RED_SQUARE), 0, max_pixels=max_pixels)
    pixel_count = image.width_px * image.height_px
    assert pixel_count <= max_pixels
    assert pixel_count >= 0.98 * max_pixels
    assert image.width_px / image.height_px == pytest.approx(size[0] / size[1], rel=0.01)


@pytest.mark.parametrize("call", _INDEXED_CALLS)
def test_pdf_page_index_out_of_range(call: Callable[[bytes, int], object]) -> None:
    """`page_index` ngoài `[0, số trang)` là lỗi của người gọi, gắn với trường `pageIndex`."""
    data = synthetic.make_pdf(3)
    with pytest.raises(VisionError) as excinfo:
        call(data, 3)
    assert str(excinfo.value) == "VALIDATION"
    assert excinfo.value.field == "pageIndex"


def test_render_pdf_page_file_type_mismatch() -> None:
    """Dựng một tệp không phải PDF → `FILE_TYPE_MISMATCH`."""
    with pytest.raises(VisionError) as excinfo:
        render_pdf_page(b"not a pdf at all", 0)
    assert str(excinfo.value) == "FILE_TYPE_MISMATCH"


def test_render_pdf_page_concurrent_threads_agree() -> None:
    """8 luồng dựng cùng lúc: `PDF_LOCK` giữ pdfium đúng một người dùng, kết quả bằng nhau."""
    data = synthetic.make_pdf(1, rects=_RED_SQUARE)
    with ThreadPoolExecutor(max_workers=8) as pool:
        images = [result.pixels for result in pool.map(lambda _: render_pdf_page(data, 0, dpi=72), range(8))]
    assert all(np.array_equal(images[0], other) for other in images[1:])


@pytest.mark.parametrize(
    ("width_pt", "height_pt", "dpi", "max_pixels", "expected"),
    [
        (595.0, 842.0, 200.0, 40_000_000, 200.0),
        (5000.0, 5000.0, 200.0, 4_000_000, 28.8),
        (1684.0, 2384.0, 200.0, 1_000_000, 35.93),
    ],
)
def test_effective_dpi_u06(width_pt: float, height_pt: float, dpi: float, max_pixels: int, expected: float) -> None:
    """Vừa trần thì giữ nguyên DPI; vượt thì hạ và làm tròn **xuống** 0,01."""
    result = effective_dpi(width_pt, height_pt, dpi, max_pixels)
    assert result == pytest.approx(expected, abs=1e-9)
    assert math.floor(width_pt * result / 72.0) * math.floor(height_pt * result / 72.0) <= max_pixels


def _pdf_with_broken_last_page(pages: int) -> bytes:
    """PDF `pages` trang mà đối tượng trang **cuối** mang `/Type/Bad` thay vì `/Type/Page`.

    Thay đúng số byte (`/Type/Page` và `/Type/Bad ` đều 10 byte) nên bảng `xref` vẫn trỏ
    đúng offset: pdfium mở được tài liệu và đếm đủ trang, chỉ chết khi nạp chính trang đó.
    """
    data = synthetic.make_pdf(pages)
    old, new = b"/Type/Page/Parent", b"/Type/Bad /Parent"
    assert len(old) == len(new)
    head, sep, tail = data.rpartition(old)
    assert sep, "không thấy đối tượng trang để phá"
    return head + new + tail


def test_pdf_u07_broken_page() -> None:
    """Trang sai `/Type` → `FILE_CORRUPT`, không để `PdfiumError` lọt ra khỏi gói.

    `FPDF_LoadPage` trả NULL nên `pypdfium2` ném `PdfiumError("Failed to load page.")` với
    `err_code = None`; khối [2] đòi lỗi của gói là `VisionError`, khối [8] đòi "không ngoại
    lệ lạ lọt ra". Tài liệu vẫn mở được nên ca này chạm đúng đường mà PDF cắt đôi không
    chạm tới (pdfium sửa chữa được tệp cụt và hỏng ngay ở bước mở).
    """
    data = _pdf_with_broken_last_page(3)
    assert pdf_page_count(data) == 3
    for call in _INDEXED_CALLS:
        with pytest.raises(VisionError) as excinfo:
            call(data, 2)
        assert str(excinfo.value) == "FILE_CORRUPT"


def test_pdf_u07_broken_page_leaves_other_pages_usable() -> None:
    """Một trang hỏng không làm hỏng các trang còn lại: trang 0 vẫn đọc khổ và dựng được."""
    data = _pdf_with_broken_last_page(3)
    assert pdf_page_size_pt(data, 0) == pytest.approx(synthetic.A4_PT, abs=0.01)
    image = render_pdf_page(data, 0, dpi=36.0)
    assert image.width_px > 0
    assert image.height_px > 0
