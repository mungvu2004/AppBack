"""Nhận diện loại tệp bằng nội dung (U08, U09, K14)."""

import pytest
from PIL import Image

from packages.vision.preprocess.sniff import SNIFF_BYTES, VisionKind, sniff_kind
from packages.vision.preprocess.tests import synthetic

_PNG = synthetic.encode(Image.new("RGB", (4, 3), (1, 2, 3)), "PNG")
_JPEG = synthetic.encode(Image.new("RGB", (4, 3), (1, 2, 3)), "JPEG")
_PDF = synthetic.make_pdf(2)
_GIF = synthetic.encode(Image.new("P", (4, 3)), "GIF")


@pytest.mark.parametrize(
    ("name", "declared_type", "data", "expected"),
    [
        ("plan.dwg", "application/acad", _PNG, "png"),
        ("plan.png", "image/png", _JPEG, "jpeg"),
        ("plan.txt", "text/plain", _PDF, "pdf"),
        ("plan.pdf", "application/pdf", b"\x00\x01\x02" + _PDF, "pdf"),
        ("plan.png", "image/png", b"AC1032" + b"\x00" * 16, "dwg"),
        ("plan.png", "image/png", _GIF, "unknown"),
        ("plan.png", "image/png", b"", "unknown"),
        ("plan.png", "image/png", _PNG[:4], "unknown"),
        ("plan.dwg", "application/acad", b"AC10", "unknown"),
        ("plan.dwg", "application/acad", b"AC10xy" + b"\x00" * 16, "unknown"),
    ],
)
def test_sniff_kind_u08_ignores_name_and_declared_type(
    name: str, declared_type: str, data: bytes, expected: VisionKind
) -> None:
    """Tên tệp và kiểu người gọi khai không tham gia: kết quả chỉ phụ thuộc byte."""
    assert sniff_kind(data) == expected, (name, declared_type)


def test_sniff_kind_u09_leading_garbage_pdf_still_counts_pages() -> None:
    """PDF có rác dẫn đường vẫn là `pdf` và vẫn đếm đúng số trang."""
    from packages.vision.preprocess.pdf import pdf_page_count

    data = b"\x00\x01\x02" + synthetic.make_pdf(3)
    assert sniff_kind(data) == "pdf"
    assert pdf_page_count(data) == 3


def test_sniff_kind_u09_pdf_marker_outside_window() -> None:
    """`%PDF-` nằm sau byte thứ 1.024 không được tính — chỉ phần đầu tệp được đọc."""
    assert sniff_kind(b"\x00" * SNIFF_BYTES + b"%PDF-1.4") == "unknown"
