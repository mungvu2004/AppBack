"""Schema dây của `/api/me` (B1-04 [2], HOP-DONG-MOI §3, BE-00 §3.1).

`fullName`/`jobTitle` cấm ký tự điều khiển (Cc) và ký tự đảo chiều song hướng
(K01, W2) — luật nằm ở `packages.core.text.clean_text`, dùng chung với mọi module (NO-169).
"""

from typing import Annotated, Final, Literal

from pydantic import Field, field_validator, model_validator

from apps.api.auth.passwords import MIN_PASSWORD_LENGTH
from apps.api.core.wire import WireModel, WireRequest
from apps.api.me.avatar import MAX_BASE64_LEN
from packages.core.text import clean_text, nfc

FULL_NAME_MAX: Final = 120
PHONE_MAX: Final = 32
_UPDATE_KEYS: Final = frozenset({"full_name", "job_title", "phone", "language"})


class MeSchema(WireModel):
    """Response N11/N12/N14 (HOP-DONG-MOI §3); trường tuỳ chọn vắng khi `None` (W2, K02)."""

    email: str
    full_name: str
    job_title: str | None = None
    phone: str | None = None
    language: Literal["vi", "en"]
    avatar_url: str | None = None


class UpdateMeBody(WireRequest):
    """Thân N12: `UpdateMeSchema`; ≥ 1 khoá, mọi khoá vắng giữ nguyên giá trị cũ."""

    full_name: str | None = None
    job_title: str | None = None
    phone: str | None = None
    language: Literal["vi", "en"] | None = None

    @field_validator("full_name")
    @classmethod
    def _validate_full_name(cls, value: str | None) -> str:
        """NFC + trim; `null` tường minh, rỗng (kể cả toàn khoảng trắng), > 120 ký tự, hay ký tự cấm → 422.

        Không như `jobTitle`/`phone`, `fullName` ánh xạ cột `NOT NULL` (1-120 ký tự) — `null`
        tường minh bị từ chối chứ không lặng lẽ coi như vắng khoá (`language` cũng vậy, cùng lý
        do gốc: NO-165, R-19 — mọi khoá của `_COLUMN_OF` ánh xạ cột `NOT NULL` đều chặn `null`).
        """
        if value is None:
            raise ValueError("fullName không được null")
        normalized = clean_text(value)
        if not 1 <= len(normalized) <= FULL_NAME_MAX:
            raise ValueError("fullName sai định dạng")
        return normalized

    @field_validator("job_title")
    @classmethod
    def _validate_job_title(cls, value: str | None) -> str | None:
        """NFC + trim; toàn khoảng trắng coi như `''` (xoá cột); > 120 ký tự hay ký tự cấm → 422."""
        if value is None:
            return None
        normalized = clean_text(value)
        if len(normalized) > FULL_NAME_MAX:
            raise ValueError("jobTitle sai định dạng")
        return normalized

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, value: str | None) -> str | None:
        """NFC + trim; toàn khoảng trắng coi như `''` (xoá cột); > 32 ký tự → 422."""
        if value is None:
            return None
        normalized = nfc(value).strip()
        if len(normalized) > PHONE_MAX:
            raise ValueError("phone quá dài")
        return normalized

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: Literal["vi", "en"] | None) -> Literal["vi", "en"]:
        """`null` tường minh không hợp lệ (cột `language` `NOT NULL`, như `fullName`) → 422 (NO-165, R-19)."""
        if value is None:
            raise ValueError("language không được null")
        return value

    @model_validator(mode="after")
    def _at_least_one_key(self) -> "UpdateMeBody":
        """Thân không khoá nào → 422 `VALIDATION` không kèm `field`."""
        if not self.model_fields_set & _UPDATE_KEYS:
            raise ValueError("thân không có khoá nào")
        return self


class ChangePasswordBody(WireRequest):
    """Thân N13: `{currentPassword, newPassword}`."""

    current_password: Annotated[str, Field(min_length=1)]
    new_password: Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH)]


class ReplaceAvatarBody(WireRequest):
    """Thân N14: `{mimeType, contentBase64}`."""

    mime_type: Literal["image/png", "image/jpeg"]
    content_base64: Annotated[str, Field(min_length=1, max_length=MAX_BASE64_LEN)]
