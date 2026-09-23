"""Cấu hình gửi thư (B1-03 [2]).

Đọc **lười** qua `get_mail_settings()` (B0-06 nhập mọi module của `apps.api` để dựng
schema khi chưa có biến môi trường nào — nạp module không được đọc settings ngay).
`mail_backend="memory"` chỉ hợp lệ ở `APP_ENV=test` (fail-closed, lỡ tay bật ở
production thì thư không bao giờ rời tiến trình mà không ai biết).
"""

from functools import cache
from typing import Annotated, Literal

from pydantic import Field, PositiveFloat, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.settings import get_core_settings

type MailBackend = Literal["smtp", "memory"]


class MailSettings(BaseSettings):
    """Backend gửi thư và tham số SMTP; thiếu tham số bắt buộc theo backend → lỗi lúc nạp."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    mail_backend: MailBackend = "smtp"
    smtp_host: str | None = None
    smtp_port: Annotated[int, Field(ge=1, le=65535)] = 587
    smtp_starttls: bool = True
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    mail_from: str | None = None
    smtp_timeout_s: PositiveFloat = 10

    @model_validator(mode="after")
    def _validate_backend(self) -> "MailSettings":
        """`memory` ngoài `APP_ENV=test`, `smtp` thiếu host/from, hoặc user/pass lệch cặp → lỗi."""
        if self.mail_backend == "memory" and get_core_settings().app_env != "test":
            raise ValueError("MAIL_BACKEND=memory chỉ dùng khi APP_ENV=test")
        if self.mail_backend == "smtp":
            if not self.smtp_host or not self.mail_from:
                raise ValueError("MAIL_BACKEND=smtp cần SMTP_HOST và MAIL_FROM")
            if bool(self.smtp_username) != bool(self.smtp_password):
                raise ValueError("SMTP_USERNAME và SMTP_PASSWORD phải cùng có hoặc cùng thiếu")
        return self


@cache
def get_mail_settings() -> MailSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return MailSettings()


def reset_mail_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi `get_mail_settings()` sau."""
    get_mail_settings.cache_clear()
