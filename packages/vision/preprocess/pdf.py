"""Đọc PDF bằng `pypdfium2`: đếm trang, khổ trang, dựng trang thành ảnh RGB.

PDFium là thư viện toàn cục **không an toàn luồng**: mọi lời gọi vào nó — mở,
đọc khổ, dựng, đóng — nằm trong `PDF_LOCK` cấp module (khối [9]). Khoá giữ suốt
một thao tác chứ không từng lời gọi, vì tài liệu và trang là trạng thái sống của
thư viện. Tài liệu và trang luôn đóng trong `finally`.
"""

import math
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Final

import numpy as np
import pypdfium2 as pdfium  # type: ignore[import-untyped]  # pypdfium2 5.13 không có py.typed
import pypdfium2.raw as pdfium_c  # type: ignore[import-untyped]  # ctypes sinh tự động, không stub
from numpy.typing import NDArray

from packages.vision.preprocess.errors import VisionError
from packages.vision.preprocess.geometry import cap_pixels
from packages.vision.preprocess.sniff import sniff_kind
from packages.vision.preprocess.types import DEFAULT_DPI, DEFAULT_MAX_PIXELS, RgbImage

PDF_LOCK: Final = threading.Lock()
"""Khoá toàn tiến trình cho pdfium; không lời gọi pdfium nào được nằm ngoài nó."""

POINTS_PER_INCH: Final = 72.0

# `_open_pdf` của pypdfium2 5.13 ném `PdfiumError` kèm `err_code` = `FPDF_GetLastError()`
# khi số trang < 1. Chỉ mật khẩu/bảo mật — và `SUCCESS`, tức tệp đọc được nhưng 0 trang —
# là "không đọc nổi"; FILE/FORMAT/UNKNOWN là tệp hỏng (U04, U07).
_UNREADABLE_ERR_CODES: Final = frozenset(
    (pdfium_c.FPDF_ERR_SUCCESS, pdfium_c.FPDF_ERR_PASSWORD, pdfium_c.FPDF_ERR_SECURITY)
)


def _open_document(data: bytes) -> pdfium.PdfDocument:
    """Mở tài liệu bằng mật khẩu người dùng rỗng; **phải** gọi khi đang giữ `PDF_LOCK`.

    Không phải PDF theo `sniff_kind` → `FILE_TYPE_MISMATCH`. PDF có `/Encrypt` mà
    PDFium mở được bằng mật khẩu rỗng (chỉ đặt mật khẩu chủ) đi tiếp bình thường.
    """
    if sniff_kind(data) != "pdf":
        raise VisionError("FILE_TYPE_MISMATCH")
    try:
        return pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        unreadable = exc.err_code in _UNREADABLE_ERR_CODES
        raise VisionError("PDF_UNREADABLE" if unreadable else "FILE_CORRUPT") from exc


def pdf_page_count(data: bytes) -> int:
    """Số trang của PDF; lỗi như `_open_document`."""
    with PDF_LOCK:
        pdf = _open_document(data)
        try:
            return len(pdf)
        finally:
            pdf.close()


@contextmanager
def _open_page(pdf: pdfium.PdfDocument, page_index: int) -> Iterator[pdfium.PdfPage]:
    """Mở một trang, đóng nó trong `finally`, và đổi **mọi** lỗi pdfium thành `FILE_CORRUPT`.

    Một chỗ dùng chung cho cả hai đường chạm trang (R-07, R-19): không chỉ `FPDF_LoadPage`
    mà cả `get_size`, `render`, `to_numpy` cùng lớp rủi ro, vì khối [7] coi mọi `bytes` là
    do kẻ xấu dựng. Trang có `/Type` sai làm `FPDF_LoadPage` trả NULL và `pypdfium2` ném
    `PdfiumError` với `err_code = None` — chỉ đường mở tài liệu mới có `err_code`, nên ở
    đây không phân loại theo mã mà coi hết là tệp hỏng. Gọi khi đang giữ `PDF_LOCK`.
    """
    try:
        page = pdf[page_index]
        try:
            yield page
        finally:
            page.close()
    except pdfium.PdfiumError as exc:
        raise VisionError("FILE_CORRUPT") from exc


def _page_size_pt(pdf: pdfium.PdfDocument, page_index: int) -> tuple[float, float]:
    """Khổ trang `(rộng, cao)` theo point, đã áp `/Rotate`; giữ `PDF_LOCK` khi gọi.

    `page_index` ngoài `[0, số trang)` → `VALIDATION` với `field="pageIndex"`.
    """
    if not 0 <= page_index < len(pdf):
        raise VisionError("VALIDATION", field="pageIndex")
    with _open_page(pdf, page_index) as page:
        width_pt, height_pt = page.get_size()
        return float(width_pt), float(height_pt)


def pdf_page_size_pt(data: bytes, page_index: int) -> tuple[float, float]:
    """Khổ trang theo point **không dựng ảnh** — cùng chiều với ảnh `render_pdf_page` trả.

    Dùng để ước lượng kích thước đầu ra (và chọn `dpi`) trước khi bỏ công dựng.
    """
    with PDF_LOCK:
        pdf = _open_document(data)
        try:
            return _page_size_pt(pdf, page_index)
        finally:
            pdf.close()


def effective_dpi(width_pt: float, height_pt: float, dpi: float, max_pixels: int) -> float:
    """DPI thật sau khi hạ để khổ trang không vượt `max_pixels` (U06).

    Vừa trần thì giữ nguyên `dpi`; không thì `dpi · sqrt(max_pixels / số điểm ảnh)`
    làm tròn **xuống** 0,01 — làm tròn xuống để kết quả không bao giờ vượt trần vì
    sai số số thực. Khổ lớn là chuyện bình thường của bản vẽ, không phải lỗi.
    """
    pixels = (width_pt * dpi / POINTS_PER_INCH) * (height_pt * dpi / POINTS_PER_INCH)
    if pixels <= max_pixels:
        return float(dpi)
    return math.floor(dpi * math.sqrt(max_pixels / pixels) * 100.0) / 100.0


def _render_page(pdf: pdfium.PdfDocument, page_index: int, scale: float) -> NDArray[np.uint8]:
    """Dựng trang trên nền trắng ra mảng RGB 8-bit **đã chép khỏi** bộ đệm của pdfium.

    Phải chép: bộ đệm bitmap chết cùng trang, giữ view vào nó là đọc bộ nhớ đã giải
    phóng. `rev_byteorder=True` để pdfium ghi thẳng thứ tự RGB thay vì BGR.
    """
    with _open_page(pdf, page_index) as page:
        bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255), rev_byteorder=True)
        return np.array(bitmap.to_numpy()[:, :, :3], dtype=np.uint8)


def render_pdf_page(
    data: bytes,
    page_index: int,
    *,
    dpi: float = DEFAULT_DPI,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> RgbImage:
    """Dựng một trang PDF thành ảnh RGB nền trắng, đã áp `/Rotate` của trang.

    `dpi` bị hạ theo `effective_dpi` trước khi dựng (khỏi cấp phát bitmap khổng lồ),
    rồi ảnh đi qua Trần đầu ra `cap_pixels` vì pdfium làm tròn **lên** số điểm ảnh
    nên có thể vượt trần vài pixel. Lỗi như `_open_document` và `_page_size_pt`.
    """
    with PDF_LOCK:
        pdf = _open_document(data)
        try:
            width_pt, height_pt = _page_size_pt(pdf, page_index)
            scale = effective_dpi(width_pt, height_pt, dpi, max_pixels) / POINTS_PER_INCH
            pixels = _render_page(pdf, page_index, scale)
        finally:
            pdf.close()
    capped, _sx, _sy = cap_pixels(pixels, max_pixels)
    return RgbImage(np.ascontiguousarray(capped, dtype=np.uint8))
