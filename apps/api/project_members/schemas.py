"""Thân request của N3 (B2-02 [2]): `{email}` strict, email qua `validate_wire_email` (K37)."""

from pydantic import field_validator

from apps.api.auth.emails import validate_wire_email
from apps.api.core.wire import WireRequest


class AddMemberBody(WireRequest):
    """N3: email của người được thêm; sai dạng → 422 `VALIDATION` `field:"email"`."""

    email: str

    @field_validator("email")
    @classmethod
    def _wire_email(cls, value: str) -> str:
        """Chỉ nhận đúng tập email của zod của FE; chuỗi ngoài ASCII (chữ s dài, dấu Kelvin, `ánh@…`) bị loại."""
        return validate_wire_email(value)
