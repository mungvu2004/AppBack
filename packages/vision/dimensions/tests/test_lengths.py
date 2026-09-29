"""Đọc độ dài: 24 ca của FE, luật nguyên/dương, ca OCR nghi ngờ và các biên của ngữ pháp."""

from fractions import Fraction

import pytest

from packages.vision.dimensions import (
    DIMENSION_MAX_MM,
    LengthReading,
    parse_length_fraction,
    parse_length_mm,
    read_length,
)

NBSP = chr(0xA0)
MINUS = chr(0x2212)

# Chép từ `src/domain/units/__tests__/parse.test.ts:27-52`: (chuỗi, giá trị FE hoặc None).
FE_TABLE = [
    ("3,5", "3.5"),  # :28
    ("3.5", "3.5"),  # :29
    ("3500 mm", "3500"),  # :30
    ("3,5 m", "3500"),  # :31
    ("350cm", "3500"),  # :32
    ("35 DM", "3500"),  # :33
    ("3.500", "3500"),  # :34
    ("1.234.567", "1234567"),  # :35
    ("1,234.5", "1234.5"),  # :36
    ("3 500 mm", "3500"),  # :37
    ("-250 mm", "-250"),  # :38
    ("+3500", "3500"),  # :39
    ("", None),  # :40
    ("   ", None),  # :41
    ("abc", None),  # :42
    ("3,5,5", None),  # :43
    ("3,", None),  # :44
    ("1e3", None),  # :45
    ("0x10", None),  # :46
    ("3.5abc", None),  # :47
    ("3500 km", None),  # :48
    ("mm", None),  # :49
    ("-", None),  # :50
    ("12.34.5", None),  # :51
]


def test_fe_table_has_24_cases() -> None:
    """Đủ 24 ca của bảng FE (12 nhận, 12 từ chối)."""
    assert len(FE_TABLE) == 24
    assert sum(expected is None for _, expected in FE_TABLE) == 12


@pytest.mark.parametrize(("text", "expected"), FE_TABLE)
def test_fe_table_matches_parse_length_fraction(text: str, expected: str | None) -> None:
    """`parse_length_fraction` cho đúng giá trị FE, kể cả giá trị lẻ và âm mà luật nguyên sẽ loại."""
    assert parse_length_fraction(text) == (None if expected is None else Fraction(expected))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("3,5 m", 3500),
        ("3.500", 3500),
        ("1.234.567", None),  # đúng ngữ pháp nhưng vượt DIMENSION_MAX_MM
        ("3,5", None),
        ("1,234.5", None),
        ("-250 mm", None),
        ("+3500", 3500),
        ("35 DM", 3500),
        ("3 600", 3600),
        (f"{NBSP}3{NBSP}600 mm", 3600),
        (f"{MINUS}250", None),
        ("0", None),
        ("0,5 m", 500),
        ("2000000", None),
        (str(DIMENSION_MAX_MM), DIMENSION_MAX_MM),
        (str(DIMENSION_MAX_MM + 1), None),
        ("1", 1),
        ("abc", None),
    ],
)
def test_integer_rule(text: str, expected: int | None) -> None:
    """Chỉ số nguyên trong `[1, DIMENSION_MAX_MM]` thành `value_mm`, còn lại `None`."""
    assert parse_length_mm(text) == expected
    assert read_length(text).value_mm == expected


def test_one_million_grouped_is_accepted() -> None:
    """`1.000.000` là nhóm nghìn hợp lệ và đúng bằng trần."""
    assert parse_length_mm("1.000.000") == DIMENSION_MAX_MM


@pytest.mark.parametrize(
    ("text", "value"),
    [
        (".5", Fraction(1, 2)),
        ("0.500", Fraction(1, 2)),
        ("1.2345", Fraction(12345, 10000)),
        ("12,50 cm", Fraction(125)),
        ("-0", Fraction(0)),
        ("000000000000000000003", Fraction(3)),
        ("999999999999999", Fraction(999999999999999)),
    ],
)
def test_fraction_boundaries(text: str, value: Fraction) -> None:
    """Biên ngữ pháp: `.5`, `0.500` (thập phân vì đầu bắt đầu 0), số 0 đầu không tính chữ số có nghĩa."""
    assert parse_length_fraction(text) == value


@pytest.mark.parametrize("text", ["1234567890123456", "1,2345678901234567", "1.234.567.890.123.456", ".500.", "1.23.4"])
def test_fraction_rejects_broken_numbers(text: str) -> None:
    """16 chữ số có nghĩa, nhóm nghìn sai hay dấu treo → `None`."""
    assert parse_length_fraction(text) is None


def test_long_zero_run_does_not_hit_int_digit_limit() -> None:
    """Chuỗi 0 đầu rất dài không làm `int()` vượt trần đổi chuỗi sang số của Python."""
    assert parse_length_fraction("0" * 5000 + "5") == Fraction(5)


@pytest.mark.parametrize(
    ("text", "suspicious"),
    [
        ("48OO", True),
        ("3.6OO", True),
        ("PHONG NGU 1", False),
        ("1e3", False),
        ("0x10", False),
        ("12.34.5", False),
        ("S000", True),
        ("l2OO", True),
        ("B00", True),
        ("2ZG0", True),
        ("", False),
        ("-250 mm", False),
        ("2000000", False),
        ("2OOOOOO", False),  # thay xong vẫn vượt trần
    ],
)
def test_ocr_cases_flag_but_never_repair(text: str, suspicious: bool) -> None:
    """Chuỗi nhầm chữ → không có giá trị, chỉ nghi; chuỗi không phải số → không nghi (K19)."""
    assert read_length(text) == LengthReading(None, suspicious)


def test_valid_text_is_never_suspicious() -> None:
    """Đọc được thì `suspicious` luôn `False`."""
    assert read_length("3 600") == LengthReading(3600, False)
