"""NO-168/NO-169: ULID trần và luật Cc/bidi của `/api/me` nằm ở `packages.core`, không chép lại."""

import inspect

from apps.api.me import router, schemas


def test_me_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai tập ký tự đảo chiều (U+202A…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "0x202A" not in source
    assert "\u202a" not in source


def test_me_router__reuses_core_new_ulid() -> None:
    """Tên object ảnh đại diện lấy ULID từ `new_ulid`, không cắt tiền tố của `new_id`."""
    assert '.split("_", 1)' not in inspect.getsource(router)
