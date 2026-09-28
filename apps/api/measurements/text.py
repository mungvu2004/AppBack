"""Chuỗi người nhập của phép đo và khuôn (B2-07 [6] "Chuỗi người nhập").

Một nguồn cho luật tên: `templates` nhập lại `Label`, không chép (R-07).
"""

import unicodedata
from typing import Annotated, Final

from pydantic import AfterValidator

from packages.core.text import nfc

NAME_MAX: Final = 120
_BIDI: Final = frozenset(chr(c) for c in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
"""U+202A-202E, U+2066-2069: ký tự đảo chiều, dùng để giả mạo tên hiển thị."""


def clean_label(value: str, *, max_len: int = NAME_MAX) -> str:
    """`nfc(strip)`, rồi 1..`max_len` ký tự, không ký tự điều khiển (Cc) hay đảo chiều.

    Lưu NFC ngay ở biên (K20, C16). Sai luật → `ValueError`: chạy trong validator của
    Pydantic nên thành 422 `VALIDATION` đúng `field` của trường gọi nó.
    """
    text = nfc(value.strip())
    if not 1 <= len(text) <= max_len:
        raise ValueError(f"phải 1-{max_len} ký tự sau chuẩn hoá")
    bad = next((ch for ch in text if ch in _BIDI or unicodedata.category(ch) == "Cc"), None)
    if bad is not None:
        raise ValueError(f"chứa ký tự cấm U+{ord(bad):04X}")
    return text


Label = Annotated[str, AfterValidator(clean_label)]
"""Kiểu trường `name` của phép đo và khuôn."""
