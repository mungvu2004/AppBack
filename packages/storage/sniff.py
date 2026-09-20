"""Nhận loại tệp bằng **magic bytes** (BE-00 §8, K14).

Không bao giờ suy loại từ đuôi tệp hay `Content-Type` người gọi khai: hai thứ đó
chỉ là dữ liệu để lưu, `kind` luôn tính lại từ nội dung.
"""

from typing import Final, Literal, cast

Kind = Literal["png", "jpeg", "pdf", "dwg", "glb", "safetensors", "unknown"]
ImageKind = Literal["png", "jpeg"]

KINDS: Final = frozenset(("png", "jpeg", "pdf", "dwg", "glb", "safetensors", "unknown"))
IMAGE_KINDS: Final = frozenset(("png", "jpeg"))

SNIFF_BYTES: Final = 64
"""Số byte đầu cần cho `sniff` (đủ cho mọi chữ ký dưới đây)."""

# Trần độ dài phần đầu JSON của safetensors; lớn hơn là tệp hỏng hoặc không phải.
SAFETENSORS_MAX_HEADER: Final = 100 * 1024 * 1024

_SIGNATURES: Final[tuple[tuple[bytes, Kind], ...]] = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"%PDF-", "pdf"),
    (b"AC10", "dwg"),
)


def sniff(head: bytes) -> Kind:
    """`head` = `SNIFF_BYTES` byte đầu của tệp, hoặc **toàn bộ** tệp nếu nó ngắn hơn.

    Tệp ngắn hơn `SNIFF_BYTES` được kiểm thêm độ dài (U07: safetensors khai phần
    đầu dài hơn phần còn lại là tệp cụt → `unknown`).
    """
    for signature, kind in _SIGNATURES:
        if head.startswith(signature):
            return kind
    if head[:4] == b"glTF" and int.from_bytes(head[4:8], "little") == 2:
        return "glb"
    if head[8:9] == b"{":
        length = int.from_bytes(head[:8], "little")
        whole_file = len(head) < SNIFF_BYTES
        if 1 <= length <= SAFETENSORS_MAX_HEADER and not (whole_file and length > len(head) - 8):
            return "safetensors"
    return "unknown"


def as_kind(value: str) -> Kind:
    """Chuỗi đọc từ metadata của kho → `Kind`; giá trị lạ coi như `unknown`."""
    return cast("Kind", value) if value in KINDS else "unknown"
