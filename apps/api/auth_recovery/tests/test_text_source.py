"""NO-169: luật Cc/bidi của `fullName` (N10) nằm ở `packages.core.text`, không chép lại."""

import inspect

from apps.api.auth_recovery import router


def test_auth_recovery_router__reuses_core_text() -> None:
    """`router.py` không tự khai tập ký tự đảo chiều (U+202A…) — gọi `packages.core.text`."""
    source = inspect.getsource(router)
    assert "0x202A" not in source
    assert "\u202a" not in source
