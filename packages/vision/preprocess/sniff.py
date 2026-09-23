"""Nhận loại tệp của gói ảnh bằng **magic bytes** (K14, BE-00 §8).

Trùng ý với `packages/storage/sniff.py`, nhưng R-06/R-07 không áp dụng được:
`.importlinter` (hợp đồng `domain-vision-isolated`) cấm `packages.vision` nhập
`packages.storage`, nên không có module chung nào hai bên cùng nhập được. Bản
này chỉ nhận 5 loại gói ảnh cần và nhận `pdf` **lệch đầu tệp** (PDF thật hay có
vài byte rác dẫn đường), khác bản kho vốn chỉ so tiền tố.
"""

from typing import Final, Literal

VisionKind = Literal["png", "jpeg", "pdf", "dwg", "unknown"]

SNIFF_BYTES: Final = 1024
"""Chỉ 1.024 byte đầu tham gia nhận diện; phần còn lại của tệp không được đọc."""

_PNG_SIGNATURE: Final = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE: Final = b"\xff\xd8\xff"
_DWG_SIGNATURE: Final = b"AC10"
_PDF_MARKER: Final = b"%PDF-"


def sniff_kind(data: bytes) -> VisionKind:
    """Loại tệp suy từ nội dung; đuôi tệp và `Content-Type` người gọi khai không tham gia.

    PNG (8 byte chữ ký), JPEG (`FF D8 FF`) và DWG (`AC10` + 2 chữ số) phải nằm ở
    byte 0; `%PDF-` chỉ cần nằm đâu đó trong 1.024 byte đầu. Mọi thứ khác, kể cả
    tệp rỗng hay cụt trước khi đủ chữ ký, là `unknown` (fail-closed, R-17).
    """
    head = data[:SNIFF_BYTES]
    if head.startswith(_PNG_SIGNATURE):
        return "png"
    if head.startswith(_JPEG_SIGNATURE):
        return "jpeg"
    if head.startswith(_DWG_SIGNATURE) and len(head) >= 6 and head[4:6].isdigit():
        return "dwg"
    if _PDF_MARKER in head:
        return "pdf"
    return "unknown"
