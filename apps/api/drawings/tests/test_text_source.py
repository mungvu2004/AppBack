"""NO-168/NO-169: ULID trần và luật `fileName` nằm ở `packages.core`, không chép lại."""

import inspect

from apps.api.drawings import drawings, schemas


def test_drawings_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai tập ký tự đảo chiều (U+202A…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "0x202A" not in source
    assert "\u202a" not in source


def test_drawings__page_key_reuses_core_new_ulid() -> None:
    """`new_page_key` lấy ULID từ `new_ulid`, không cắt tiền tố của `new_id`."""
    assert 'removeprefix("drw_")' not in inspect.getsource(drawings)
