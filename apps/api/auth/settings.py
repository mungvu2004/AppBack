"""Cấu hình đăng nhập và phiên (B1-01 [5], BE-00 §5, §11).

Đọc **lười** qua `get_auth_settings()` ở lượt dùng đầu, không lúc nhập module: B0-06 nhập
mọi module của `apps.api` để quét mã lỗi và dựng schema khi không có biến môi trường nào,
còn test đổi hạn mức bằng `monkeypatch.setenv` rồi `reset_auth_settings_cache()`.

Hai trần lấy từ hiến chương, không phải khẩu vị: access token sống ≤ 10 phút và cache
`Principal` ≤ 5 s (hạ vai, vô hiệu có hiệu lực ≤ 5 s, BE-00 §5). Hồ sơ argon2 `test` chỉ
hợp lệ khi `APP_ENV=test` — lọt ra production là băm yếu cho mọi mật khẩu mới.
"""

from functools import cache
from typing import Annotated, Final, Literal

from pydantic import Field, PositiveInt, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.settings import get_core_settings

MAX_ACCESS_TOKEN_TTL_S: Final = 600
MAX_PRINCIPAL_CACHE_TTL_S: Final = 5

type Argon2Profile = Literal["rfc9106_low_memory", "test"]


class AuthSettings(BaseSettings):
    """Hạn mức, thời hạn token và hồ sơ băm; mọi giá trị nguyên dương (fail-closed)."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    access_token_ttl_s: Annotated[int, Field(ge=1, le=MAX_ACCESS_TOKEN_TTL_S)] = 600
    stream_token_ttl_s: PositiveInt = 600
    refresh_grace_s: PositiveInt = 30
    refresh_chain_lookback: PositiveInt = 32
    auth_principal_cache_ttl_s: Annotated[int, Field(ge=1, le=MAX_PRINCIPAL_CACHE_TTL_S)] = 5
    login_ip_limit: PositiveInt = 30
    login_ip_window_s: PositiveInt = 60
    login_failure_limit: PositiveInt = 5
    login_failure_window_s: PositiveInt = 900
    login_lock_s: PositiveInt = 60
    login_email_failure_limit: PositiveInt = 20
    login_email_failure_window_s: PositiveInt = 900
    refresh_fail_limit: PositiveInt = 20
    refresh_fail_window_s: PositiveInt = 60
    refresh_total_limit: PositiveInt = 300
    refresh_total_window_s: PositiveInt = 60
    argon2_profile: Argon2Profile = "rfc9106_low_memory"
    password_hash_concurrency: PositiveInt = 4

    @model_validator(mode="after")
    def _test_profile_only_in_test(self) -> "AuthSettings":
        """`ARGON2_PROFILE=test` (1 MiB, 1 vòng) ngoài `APP_ENV=test` → không khởi động."""
        if self.argon2_profile == "test" and get_core_settings().app_env != "test":
            raise ValueError("ARGON2_PROFILE=test chỉ dùng khi APP_ENV=test")
        return self


@cache
def get_auth_settings() -> AuthSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return AuthSettings()


def reset_auth_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_auth_settings.cache_clear()
