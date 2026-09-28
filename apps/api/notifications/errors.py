"""Mã lỗi riêng của thông báo (B4-02 [2]); mã lõi ở `packages.core.error_codes`."""

from packages.core.errors import ERRORS

NOTIFICATION_NOT_INVITE = ERRORS.define("NOTIFICATION_NOT_INVITE", 422)
"""#22 trên thông báo không phải `projectInvite`."""
