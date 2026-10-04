"""Chuỗi người nhập của phép đo và khuôn (B2-07 [6] "Chuỗi người nhập").

Một nguồn cho luật tên: `templates` nhập lại `Label`, không chép (R-07).
"""

from typing import Annotated, Final

from pydantic import AfterValidator

from packages.core.text import clean_text

NAME_MAX: Final = 120


def clean_label(value: str, *, max_len: int = NAME_MAX) -> str:
    """`nfc(strip)`, rồi 1..`max_len` ký tự, không ký tự điều khiển (Cc) hay đảo chiều.

    Lưu NFC ngay ở biên (K20, C16). Sai luật → `ValueError`: chạy trong validator của
    Pydantic nên thành 422 `VALIDATION` đúng `field` của trường gọi nó.
    """
    text = clean_text(value)
    if not 1 <= len(text) <= max_len:
        raise ValueError(f"phải 1-{max_len} ký tự sau chuẩn hoá")
    return text


Label = Annotated[str, AfterValidator(clean_label)]
"""Kiểu trường `name` của phép đo và khuôn."""
