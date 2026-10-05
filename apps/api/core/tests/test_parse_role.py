"""NO-188: một hàm ép chuỗi về `Role`, dùng ở `core.auth` và `auth.sessions`."""

import pytest

from apps.api.auth import sessions
from apps.api.core import auth


def test_parse_role__valid_and_unknown() -> None:
    """Vai hợp lệ trả nguyên; vai lạ → `ValueError`."""
    assert auth.parse_role("admin") == "admin"
    with pytest.raises(ValueError, match="vai lạ"):
        auth.parse_role("root")


def test_sessions__reuses_core_parse_role() -> None:
    """`sessions.py` không có `_role` riêng — nhập `parse_role` của `core.auth`."""
    assert vars(sessions)["parse_role"] is auth.parse_role
