"""Luật dùng chung của cổng: tên tệp trong header và `Content-Type` theo `kind`."""

import pytest

from packages.storage.port import DEFAULT_CONTENT_TYPE, FALLBACK_FILENAME, content_disposition, content_type_of
from packages.storage.sniff import Kind


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("bản vẽ tầng 1.png", "ban ve tang 1.png"),
        ("../../etc/passwd", "etcpasswd"),
        ('a"b|c.png', "abc.png"),
        ("...", FALLBACK_FILENAME),
        ("正文", FALLBACK_FILENAME),
        ("a" * 200, "a" * 100),
    ],
)
def test_content_disposition_sanitises_the_ascii_name(filename: str, expected: str) -> None:
    """Phần ASCII chỉ giữ ký tự an toàn; bản đầy đủ đi ở `filename*` đã percent-encode."""
    header = content_disposition("attachment", filename)

    assert header.startswith(f'attachment; filename="{expected}"')
    assert "filename*=UTF-8''" in header
    assert "|" not in header.split("filename*=")[0]


def test_content_disposition_without_filename() -> None:
    assert content_disposition("inline", None) == "inline"


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("png", "image/png"), ("jpeg", "image/jpeg"), ("pdf", DEFAULT_CONTENT_TYPE), (None, DEFAULT_CONTENT_TYPE)],
)
def test_content_type_of(kind: Kind | None, expected: str) -> None:
    assert content_type_of(kind) == expected
