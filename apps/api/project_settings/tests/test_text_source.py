"""NO-213: `notes` dùng `packages.core.text.clean_text` (tham số cho phép xuống dòng/tab), không chép."""

import inspect

from apps.api.project_settings import schemas


def test_project_settings_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai ký tự định hướng (U+200E…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "\u200e" not in source
    assert "\u202a" not in source
