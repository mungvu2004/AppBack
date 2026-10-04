"""Chuẩn hoá chuỗi người nhập (BE-00 §6): NFC; email so qua `normalize_email` (C16)."""

import unicodedata
from typing import Final

_BIDI_OVERRIDE: Final = frozenset(chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
"""LRE/RLE/PDF/LRO/RLO và LRI/RLI/FSI/PDI: đảo chiều hiển thị, dùng để giả mạo tên."""
_BIDI_MARKS: Final = frozenset("‎‏")
"""LRM/RLM: không phải Cc; chỉ chặn khi người gọi đòi `bidi_marks=True`."""


def nfc(s: str) -> str:
    """`s` ở dạng NFC."""
    return unicodedata.normalize("NFC", s)


def normalize_email(s: str) -> str:
    """NFC, bỏ khoảng trắng hai đầu, `casefold` — khoá so email."""
    return nfc(s).strip().casefold()


def clean_text(value: str, *, bidi_marks: bool = False, allow_controls: str = "") -> str:
    """`nfc(value.strip())`; ký tự điều khiển (Cc) hay đảo chiều → `ValueError` nêu điểm mã.

    Nguồn duy nhất của luật Cc/bidi cho chuỗi người nhập (NO-169, NO-213). Độ dài và rỗng do
    người gọi kiểm (mỗi trường một trần). Khác biệt giữa các trường là tham số tường minh:
    `bidi_marks` chặn thêm LRM/RLM (tên dự án, ghi chú — giữ đúng luật cũ của chúng) và
    `allow_controls` miễn một số ký tự Cc (ghi chú cho xuống dòng/tab).
    """
    text = nfc(value.strip())
    blocked = _BIDI_OVERRIDE | _BIDI_MARKS if bidi_marks else _BIDI_OVERRIDE
    bad = next(
        (ch for ch in text if ch in blocked or (unicodedata.category(ch) == "Cc" and ch not in allow_controls)), None
    )
    if bad is not None:
        raise ValueError(f"chuỗi chứa ký tự cấm U+{ord(bad):04X}")
    return text
