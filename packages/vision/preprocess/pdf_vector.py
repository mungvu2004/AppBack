"""Đọc **hình học vector** của một trang PDF bằng `pypdfium2` (không dựng ảnh).

Bản vẽ CAD xuất PDF giữ nguyên nét: tường là cặp nét song song hay hình chữ nhật tô đặc, thẳng
tuyệt đối và đúng bề dày. Module này chỉ đọc nét ra mảng số; chọn nét nào là tường là việc của
`packages.vision.walls.pdf_walls`. Mọi lời gọi PDFium nằm trong `PDF_LOCK` như `pdf.py`, dùng
chung `_open_document`/`_open_page` nên tệp hỏng/mã hoá cho đúng mã lỗi của đường dựng ảnh.
"""

import ctypes
import math
from dataclasses import dataclass
from typing import Final

import numpy as np
import pypdfium2 as pdfium  # type: ignore[import-untyped]  # pypdfium2 5.13 không có py.typed
import pypdfium2.raw as pdfium_c  # type: ignore[import-untyped]  # ctypes sinh tự động, không stub
from numpy.typing import NDArray

from packages.vision.preprocess.pdf import PDF_LOCK, _open_document, _open_page, _page_size_pt

__all__ = ["PdfPageVectors", "pdf_page_vectors"]

type Affine = tuple[float, float, float, float, float, float]
"""Ma trận PDF `(a, b, c, d, e, f)`, vector hàng: `(x, y) -> (ax + cy + e, bx + dy + f)`."""
type Row = tuple[float, float, float, float, float]

_IDENTITY: Final[Affine] = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
_MAX_FORM_DEPTH: Final = 8
"""Form XObject lồng sâu hơn ngần này thì bỏ — chặn tệp dựng ác ý lồng vô hạn (khối [7])."""
_MAX_SEGMENTS: Final = 200_000
"""Trần số đoạn thẳng đọc từ một trang (K13): bản CAD thật cỡ 10⁴-10⁵, vượt thì dừng đọc."""


@dataclass(frozen=True, slots=True)
class PdfPageVectors:
    """Hình học vector của một trang theo **point hiển thị**: gốc trên-trái, đã áp `/Rotate`.

    Cùng hệ với ảnh `render_pdf_page`: pixel = point hiển thị · `width_px / width_pt`.
    `segments` là mảng `(n, 5)`: `x0, y0, x1, y1, bề dày nét` (point) của mọi đoạn thẳng — nét vẽ
    lẫn cạnh vùng tô, kể cả `re`; đường cong Bézier (cung cửa) bị bỏ. `image_ratio`: tổng diện tích
    ảnh nhúng / diện tích trang (kẹp 1,0) — PDF quét có ≈ 1,0. `text`: lớp chữ (đọc `TL 1:N` không OCR).
    """

    width_pt: float
    height_pt: float
    segments: NDArray[np.float64]
    image_ratio: float
    text: str


def _compose(inner: Affine, outer: Affine) -> Affine:
    """`inner` rồi `outer` (vector hàng: `p · inner · outer`)."""
    a, b, c, d, e, f = inner
    a2, b2, c2, d2, e2, f2 = outer
    return (
        a * a2 + b * c2,
        a * b2 + b * d2,
        c * a2 + d * c2,
        c * b2 + d * d2,
        e * a2 + f * c2 + e2,
        e * b2 + f * d2 + f2,
    )


def _object_matrix(obj: ctypes.c_void_p) -> Affine:
    """Ma trận riêng của một page object (`FPDFPageObj_GetMatrix`); đọc hỏng → đơn vị."""
    m = pdfium_c.FS_MATRIX()
    if not pdfium_c.FPDFPageObj_GetMatrix(obj, ctypes.byref(m)):
        return _IDENTITY
    return (m.a, m.b, m.c, m.d, m.e, m.f)


def _path_segments(obj: ctypes.c_void_p, matrix: Affine, out: list[Row]) -> None:
    """Thêm các đoạn thẳng của một path vào `out`; đường cong và path vô hình (không nét, không tô) bị bỏ.

    `MoveTo` mở subpath, `LineTo` thêm đoạn, cờ `close` thêm đoạn khép về điểm đầu subpath — đúng
    cách PDFium lưu `re` (MoveTo + 3 LineTo + close). Bề dày nét nhân căn định thức của ma trận.
    """
    fill_mode, stroke = ctypes.c_int(0), ctypes.c_int(0)
    pdfium_c.FPDFPath_GetDrawMode(obj, ctypes.byref(fill_mode), ctypes.byref(stroke))
    if not fill_mode.value and not stroke.value:
        return
    width = ctypes.c_float(0.0)
    pdfium_c.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(width))
    a, b, c, d, e, f = matrix
    stroke_pt = float(width.value) * math.sqrt(abs(a * d - b * c)) if stroke.value else 0.0
    x, y = ctypes.c_float(0.0), ctypes.c_float(0.0)
    start: tuple[float, float] | None = None
    last: tuple[float, float] | None = None
    for index in range(pdfium_c.FPDFPath_CountSegments(obj)):
        seg = pdfium_c.FPDFPath_GetPathSegment(obj, index)
        pdfium_c.FPDFPathSegment_GetPoint(seg, ctypes.byref(x), ctypes.byref(y))
        point = (a * x.value + c * y.value + e, b * x.value + d * y.value + f)
        kind = pdfium_c.FPDFPathSegment_GetType(seg)
        if kind == pdfium_c.FPDF_SEGMENT_MOVETO:
            start = point
        elif kind == pdfium_c.FPDF_SEGMENT_LINETO and last is not None:
            out.append((*last, *point, stroke_pt))
        if pdfium_c.FPDFPathSegment_GetClose(seg) and start is not None and point != start:
            out.append((*point, *start, stroke_pt))
        last = point


def _walk_objects(container: ctypes.c_void_p, *, is_page: bool, parent: Affine, depth: int, out: list[Row]) -> float:
    """Duyệt page object (đệ quy vào Form XObject), gom đoạn thẳng; trả tổng diện tích ảnh nhúng (point²).

    Ảnh PDF là hình vuông đơn vị qua ma trận của nó nên diện tích = |định thức|.
    """
    if is_page:
        count, get = pdfium_c.FPDFPage_CountObjects(container), pdfium_c.FPDFPage_GetObject
    else:
        count, get = pdfium_c.FPDFFormObj_CountObjects(container), pdfium_c.FPDFFormObj_GetObject
    image_area = 0.0
    for index in range(count):
        if len(out) >= _MAX_SEGMENTS:
            break
        obj = get(container, index)
        kind = pdfium_c.FPDFPageObj_GetType(obj)
        matrix = _compose(_object_matrix(obj), parent)
        if kind == pdfium_c.FPDF_PAGEOBJ_PATH:
            _path_segments(obj, matrix, out)
        elif kind == pdfium_c.FPDF_PAGEOBJ_IMAGE:
            image_area += abs(matrix[0] * matrix[3] - matrix[1] * matrix[2])
        elif kind == pdfium_c.FPDF_PAGEOBJ_FORM and depth < _MAX_FORM_DEPTH:
            image_area += _walk_objects(obj, is_page=False, parent=matrix, depth=depth + 1, out=out)
    return image_area


def _display_transform(page: pdfium.PdfPage) -> tuple[Affine, float, float]:
    """Ma trận trang PDF → point hiển thị (gốc trên-trái, `/Rotate` theo chiều kim đồng hồ) và khổ hiển thị.

    Khung là `FPDF_GetPageBoundingBox` (CropBox giao MediaBox) — đúng khung PDFium dựng ảnh.
    """
    box = pdfium_c.FS_RECTF()
    pdfium_c.FPDF_GetPageBoundingBox(page.raw, ctypes.byref(box))
    width, height = box.right - box.left, box.top - box.bottom
    upright: Affine = (1.0, 0.0, 0.0, -1.0, -box.left, box.top)
    rotation = page.get_rotation() % 360
    if rotation == 90:
        return _compose(upright, (0.0, 1.0, -1.0, 0.0, height, 0.0)), height, width
    if rotation == 180:
        return _compose(upright, (-1.0, 0.0, 0.0, -1.0, width, height)), width, height
    if rotation == 270:
        return _compose(upright, (0.0, -1.0, 1.0, 0.0, 0.0, width)), height, width
    return upright, width, height


def pdf_page_vectors(data: bytes, page_index: int) -> PdfPageVectors:
    """Hình học vector của một trang (đoạn thẳng, diện tích ảnh nhúng, chữ); lỗi như `render_pdf_page`.

    Không dựng ảnh. Đọc tối đa `_MAX_SEGMENTS` đoạn, lồng Form tối đa `_MAX_FORM_DEPTH` tầng.
    """
    out: list[Row] = []
    with PDF_LOCK:
        pdf = _open_document(data)
        try:
            _page_size_pt(pdf, page_index)  # `page_index` ngoài khoảng → VALIDATION
            with _open_page(pdf, page_index) as page:
                display, width_pt, height_pt = _display_transform(page)
                image_area = _walk_objects(page.raw, is_page=True, parent=display, depth=0, out=out)
                textpage = page.get_textpage()
                try:
                    text = str(textpage.get_text_range())
                finally:
                    textpage.close()
        finally:
            pdf.close()
    segments = np.asarray(out, dtype=np.float64).reshape(-1, 5)
    image_ratio = min(1.0, image_area / max(width_pt * height_pt, 1e-9))
    return PdfPageVectors(float(width_pt), float(height_pt), segments, image_ratio, text)
