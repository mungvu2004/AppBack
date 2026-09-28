"""Mã lỗi riêng của module khuôn thuộc tính (B2-07 [2])."""

from packages.core.errors import ERRORS

TEMPLATE_LIMIT_REACHED = ERRORS.define("TEMPLATE_LIMIT_REACHED", 422)
"""#29: dự án đã đủ `TEMPLATES_MAX` khuôn."""
