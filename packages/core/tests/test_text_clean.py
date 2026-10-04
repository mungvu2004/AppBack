"""NO-169/NO-213: `clean_text` — một hàm chuẩn hoá/kiểm chuỗi người nhập cho mọi module."""

import pytest

from packages.core.text import clean_text, first_forbidden_char


def test_clean_text__trims_and_composes_nfc() -> None:
    """Trim rồi NFC: `e` + dấu sắc rời thành `é` một điểm mã."""
    assert clean_text("  e\u0301  ") == "\u00e9"


@pytest.mark.parametrize("char", ["\x00", "\x1f", "\x7f", "\n", "\t", "\u202a", "\u202e", "\u2066", "\u2069"])
def test_clean_text__rejects_cc_and_bidi_override(char: str) -> None:
    """Cc và U+202A-202E/U+2066-2069 bị chặn mặc định, thông báo nêu điểm mã."""
    with pytest.raises(ValueError, match=r"U\+"):
        clean_text(f"ab{char}cd")


@pytest.mark.parametrize("char", ["\u200e", "\u200f"])
def test_clean_text__bidi_marks_only_when_asked(char: str) -> None:
    """LRM/RLM (U+200E/200F) lọt mặc định; `bidi_marks=True` chặn."""
    assert clean_text(f"a{char}b") == f"a{char}b"
    with pytest.raises(ValueError, match=r"U\+"):
        clean_text(f"a{char}b", bidi_marks=True)


def test_clean_text__allow_controls_is_explicit() -> None:
    """`allow_controls="\n\t"` cho xuống dòng/tab (ghi chú); ký tự Cc khác vẫn bị chặn."""
    assert clean_text("a\nb\tc", allow_controls="\n\t") == "a\nb\tc"
    with pytest.raises(ValueError, match=r"U\+0000"):
        clean_text("a\x00b", allow_controls="\n\t")


def test_first_forbidden_char__reports_first_or_none() -> None:
    """`first_forbidden_char` trả ký tự cấm đầu tiên; chuỗi sạch → `None`."""
    assert first_forbidden_char("abc") is None
    assert first_forbidden_char("a\x00b\u202ec") == "\x00"
    assert first_forbidden_char("a\u200eb") is None
    assert first_forbidden_char("a\u200eb", bidi_marks=True) == "\u200e"
