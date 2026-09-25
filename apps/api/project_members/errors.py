"""Mã lỗi riêng của thành viên dự án (B2-02 [2]); mã lõi ở `packages.core.error_codes`."""

from packages.core.errors import ERRORS

MEMBER_USER_UNAVAILABLE = ERRORS.define("MEMBER_USER_UNAVAILABLE", 422)
"""N3: email không có tài khoản chưa xoá mềm **hoặc** tài khoản `disabled`; cùng một thân, ném kèm `field="email"`."""

MEMBER_LAST_EDITOR = ERRORS.define("MEMBER_LAST_EDITOR", 422)
"""N4: gỡ người cuối còn `project.settings.edit` theo vai hiện tại (dự án sẽ mồ côi)."""
