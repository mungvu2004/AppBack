"""Cấu hình nền (BE-00 §2.1, §5). Chỉ đọc biến môi trường, không đọc `.env`.

`SECRET_KEY` chỉ được đọc ở `packages/core/keys.py`; module khác nhận khoá con qua
`current_key`/`verification_keys`.
"""

from functools import cache
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_SECRET_BYTES = 32


def _check_secret(value: str) -> None:
    if len(value.encode("utf-8")) < MIN_SECRET_BYTES:
        raise ValueError(f"khoá bí mật phải dài ≥ {MIN_SECRET_BYTES} byte UTF-8")


class CoreSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    app_env: Literal["dev", "test", "ci", "staging", "production"]
    public_base_url: str
    secret_key: SecretStr
    # Phân cách dấu phẩy, bỏ khoảng trắng hai đầu mỗi phần tử (khoá không chứa dấu phẩy).
    secret_key_previous: Annotated[tuple[SecretStr, ...], NoDecode] = ()
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True

    @field_validator("public_base_url")
    @classmethod
    def _absolute_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("PUBLIC_BASE_URL phải là URL tuyệt đối http(s)")
        if value.endswith("/") or parts.query or parts.fragment:
            raise ValueError("PUBLIC_BASE_URL không có '/' cuối, query hay fragment")
        return value

    @field_validator("secret_key")
    @classmethod
    def _secret_length(cls, value: SecretStr) -> SecretStr:
        _check_secret(value.get_secret_value())
        return value

    @field_validator("secret_key_previous", mode="before")
    @classmethod
    def _split_previous(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("secret_key_previous")
    @classmethod
    def _previous_length(cls, value: tuple[SecretStr, ...]) -> tuple[SecretStr, ...]:
        for item in value:
            _check_secret(item.get_secret_value())
        return value

    @model_validator(mode="after")
    def _https_outside_dev(self) -> "CoreSettings":
        if self.app_env in ("staging", "production") and not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL phải dùng https ở staging/production")
        return self


@cache
def get_core_settings() -> CoreSettings:
    return CoreSettings()


def reset_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi `get_core_settings()` sau."""
    get_core_settings.cache_clear()
