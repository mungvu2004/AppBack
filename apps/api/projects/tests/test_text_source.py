"""NO-213: `clean_text` của dự án là vỏ mỏng quanh `packages.core.text`, không giữ tập ký tự riêng."""

import inspect

from apps.api.projects import schemas


def test_projects_schemas__reuses_core_text() -> None:
    """`schemas.py` không tự khai ký tự định hướng (U+200E…) — gọi `packages.core.text`."""
    source = inspect.getsource(schemas)
    assert "\u200e" not in source
    assert "\u202a" not in source
