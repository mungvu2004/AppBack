"""Luật khoá object của lõi (NO-060): mẫu biên chung của `storage` và `ml_contracts`, kèm thông báo."""

import pytest

from packages.core.object_keys import MAX_KEY_BYTES, check_key, check_prefix, is_segment

DOTS = "đoạn rỗng, '.' hay '..'"
CHARS = r"chỉ nhận \[A-Za-z0-9._-\]"


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ("", "khoá rỗng"),
        ("a/../b", DOTS),
        ("../secret", DOTS),
        ("a/./b", DOTS),
        ("./a", DOTS),
        ("a//b", DOTS),
        ("/a", DOTS),
        ("a/b/", DOTS),
        ("a\x00b", CHARS),
        ("a\x7fb", CHARS),
        ("a\\b", CHARS),
        ("a b", CHARS),
        ("khóa", CHARS),
        ("khóa", CHARS),
        ("tệp.png", CHARS),
        ("a" * (MAX_KEY_BYTES + 1), f"dài hơn {MAX_KEY_BYTES} byte"),
        ("é" * (MAX_KEY_BYTES // 2 + 1), f"dài hơn {MAX_KEY_BYTES} byte"),
        ("x.meta.json", r"kết thúc bằng \.meta\.json"),
        ("a/x.meta.json", r"kết thúc bằng \.meta\.json"),
    ],
)
def test_check_key_rejects_unsafe(bad: str, match: str) -> None:
    """Rỗng, đoạn chấm, ký tự ngoài ASCII an toàn (cả NFC lẫn NFD), quá trần byte, đuôi metadata."""
    with pytest.raises(ValueError, match=match):
        check_key(bad)


@pytest.mark.parametrize(
    "good", ["a", "ml/models/x/model.onnx", "projects/prj_A/x.png", "a/.../b", "a" * MAX_KEY_BYTES]
)
def test_check_key_accepts_safe(good: str) -> None:
    """Chạm trần đúng `MAX_KEY_BYTES` vẫn đạt; chỉ `.`/`..` là đoạn chấm, `...` là tên thường."""
    assert check_key(good) == good


@pytest.mark.parametrize(
    ("bad", "match"),
    [
        ("projects/prj_A", "tiền tố"),
        ("", "tiền tố"),
        ("/", "khoá rỗng"),
        ("projects/prj_A//", DOTS),
    ],
)
def test_check_prefix_requires_trailing_slash_and_valid_key(bad: str, match: str) -> None:
    """Tiền tố thiếu `/` cuối, hoặc phần trước `/` không phải khoá hợp lệ → `ValueError`."""
    with pytest.raises(ValueError, match=match):
        check_prefix(bad)


def test_check_prefix_accepts_valid_prefix() -> None:
    assert check_prefix("projects/prj_A/") == "projects/prj_A/"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("a", True), ("...", True), ("x.png", True), ("", False), (".", False), ("..", False), ("a/b", False)],
)
def test_is_segment(value: str, expected: bool) -> None:
    """Một đoạn không chứa `/` và không là đoạn chấm."""
    assert is_segment(value) is expected
