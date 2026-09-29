"""Đọc độ dài từ chữ OCR, gương `parseLength` của FE (`src/domain/units/parse.ts:14-258`).

Chữ OCR không tin (K19): không `float()`, không `eval`, không tự sửa chữ thành số.
Chuỗi `48OO` bị loại và chỉ được *đánh dấu nghi* để người duyệt gõ lại; giá trị
không bao giờ được đoán. Giá trị tính bằng `Fraction` nên `3,5 m` ra đúng 3500.
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Final

DIMENSION_MAX_MM: Final = 1_000_000
"""Trần một chuỗi kích thước (1 km): lớn hơn là rác OCR, không phải mặt bằng."""

_MAX_SIGNIFICANT_DIGITS: Final = 15
_TYPOGRAPHIC_MINUS: Final = chr(0x2212)
"""Dấu trừ U+2212 mà bảng tính và bàn phím tạo ra; FE đổi nó thành `-` (parse.ts:66)."""
_UNIT_FACTORS: Final = {"mm": 1, "cm": 10, "dm": 100, "m": 1000}
_WHITESPACE: Final = re.compile(r"\s+")
_TRAILING_LETTERS: Final = re.compile(r"[a-z]+\Z")
_DIGITS: Final = re.compile(r"[0-9]+")
_NUMBER_BODY: Final = re.compile(r"[0-9.,]+")
_LOOKALIKES: Final = str.maketrans("OoQDIlLi|SsBZzG", "000011111558226")
"""Chữ OCR hay nhầm với số; chỉ để *nghi ngờ*, không bao giờ để sửa."""


@dataclass(frozen=True, slots=True)
class LengthReading:
    """Kết quả đọc một chuỗi: `value_mm` hợp lệ hoặc `None`; `suspicious` khi chuỗi trông như số bị nhầm chữ."""

    value_mm: int | None
    suspicious: bool


def _decimal_separator(body: str) -> str | None:
    """Dấu thập phân của thân số, hoặc `None` khi không có (`findDecimalSeparator`, parse.ts:99-120).

    Một dấu `.` đứng dạng `3.500` (đầu 1-3 số không bắt đầu `0`, đuôi đúng 3 số) là nhóm nghìn.
    """
    comma, dot = body.rfind(","), body.rfind(".")
    if comma >= 0 and dot >= 0:
        return "," if comma > dot else "."
    if comma >= 0:
        return "," if body.find(",") == comma else None
    if dot < 0 or body.find(".") != dot:
        return None
    head, tail = body[:dot], body[dot + 1 :]
    grouping = len(tail) == 3 and 1 <= len(head) <= 3 and not head.startswith("0")
    return None if grouping else "."


def _grouped_digits(text: str, separator: str | None) -> str | None:
    """Số nguyên trần từ `1.234.567`: nhóm đầu 1-3 số, các nhóm sau đúng 3 số (parse.ts:134-154)."""
    if separator is None:
        return text if _DIGITS.fullmatch(text) else None
    first, *rest = text.split(separator)
    if len(first) > 3 or not _DIGITS.fullmatch(first):
        return None
    if any(len(group) != 3 or not _DIGITS.fullmatch(group) for group in rest):
        return None
    return first + "".join(rest)


def _scan_number(body: str) -> tuple[str, int] | None:
    """Tách thân số thành `(chữ số, độ dài phần lẻ)`; sai ngữ pháp → `None` (`scanNumber`, parse.ts:157-190)."""
    if not _NUMBER_BODY.fullmatch(body):
        return None
    decimal = _decimal_separator(body)
    grouping = "." if decimal == "," else ("," if decimal == "." else ("." if "." in body else ","))
    integer, fraction = body, ""
    if decimal is not None:
        integer, _, fraction = body.rpartition(decimal)
        if not _DIGITS.fullmatch(fraction):
            return None
        integer = integer or "0"  # ",5" đọc là "0,5"
    digits = _grouped_digits(integer, grouping if grouping in integer else None)
    return None if digits is None else (digits + fraction, len(fraction))


def _split_unit(text: str) -> tuple[str, int] | None:
    """Tách hậu tố đơn vị: `(thân, hệ số mm)`; đơn vị lạ → `None`; không có đơn vị → mm (parse.ts:227-237)."""
    match = _TRAILING_LETTERS.search(text)
    if match is None:
        return text, 1
    factor = _UNIT_FACTORS.get(match.group())
    return (text[: match.start()], factor) if factor is not None else None


def parse_length_fraction(text: str) -> Fraction | None:
    """Giá trị mm đúng ngữ pháp `parseLength` của FE, chưa lọc nguyên/dương; sai ngữ pháp → `None`.

    Chuỗi nhiều hơn 15 chữ số có nghĩa bị từ chối như FE (double không giữ nổi).
    """
    squeezed = _WHITESPACE.sub("", text.replace(_TYPOGRAPHIC_MINUS, "-")).lower()
    negative = squeezed.startswith("-")
    body = squeezed[1:] if squeezed[:1] in ("+", "-") else squeezed
    unit = _split_unit(body)
    scanned = _scan_number(unit[0]) if unit and body else None
    if unit is None or scanned is None:
        return None
    digits, fraction_length = scanned
    significant = digits.lstrip("0")
    if len(significant) > _MAX_SIGNIFICANT_DIGITS:
        return None
    value = Fraction(int(significant or "0") * unit[1], 10**fraction_length)
    return -value if negative else value


def _whole_mm(text: str) -> int | None:
    """`parse_length_fraction` giữ lại khi là số nguyên trong `[1, DIMENSION_MAX_MM]`."""
    value = parse_length_fraction(text)
    if value is None or value.denominator != 1 or not 1 <= value <= DIMENSION_MAX_MM:
        return None
    return int(value)


def read_length(text: str) -> LengthReading:
    """Đọc một chuỗi kích thước; `suspicious` chỉ khi đọc hỏng mà thay chữ giống số thì ra giá trị hợp lệ.

    `48OO` → `(None, True)`, `PHONG NGU 1` → `(None, False)`. Chữ không bao giờ được thay vào kết quả (K19).
    """
    value = _whole_mm(text)
    if value is not None:
        return LengthReading(value, False)
    swapped = text.translate(_LOOKALIKES)
    return LengthReading(None, swapped != text and _whole_mm(swapped) is not None)


def parse_length_mm(text: str) -> int | None:
    """Số mm nguyên của chuỗi, hoặc `None`; bằng `read_length(text).value_mm`."""
    return read_length(text).value_mm
