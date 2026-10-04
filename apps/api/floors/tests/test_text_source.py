"""NO-168/NO-169: ULID trần và luật tên tầng nằm ở `packages.core`, không chép lại."""

import inspect

from apps.api.floors import lookup, schemas


def test_floors_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai tập ký tự đảo chiều (U+202A…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "0x202A" not in source
    assert "\u202a" not in source


def test_floors_lookup__reuses_core_new_ulid() -> None:
    """`new_level_id` lấy thân ULID từ `new_ulid`, không cắt tiền tố của `new_id`."""
    assert '.split("_", 1)' not in inspect.getsource(lookup)
