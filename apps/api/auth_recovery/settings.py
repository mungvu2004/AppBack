"""Cấu hình mời và quên mật khẩu (B1-03 [5], BE-00 §5, §11).

Đọc **lười** qua `get_recovery_settings()` (mẫu `apps/api/auth/settings.py`): B0-06 nhập
mọi module của `apps.api` khi không có biến môi trường nào, test đổi hạn mức bằng
`monkeypatch.setenv` rồi `reset_recovery_settings_cache()`. Mọi giá trị nguyên dương
(fail-closed, R-17).
"""

from functools import cache
from typing import Annotated

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RecoverySettings(BaseSettings):
    """TTL token, hạn mức chống dò, và lịch dọn/gửi lại — theo prompt §5."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    invite_ttl_h: Annotated[int, Field(gt=0)] = 168
    password_reset_ttl_min: Annotated[int, Field(gt=0)] = 60
    password_reset_cooldown_min: Annotated[int, Field(gt=0)] = 15
    recovery_ip_limit: Annotated[int, Field(gt=0)] = 10
    recovery_ip_window_s: Annotated[int, Field(gt=0)] = 900
    token_purge_after_d: Annotated[int, Field(gt=0)] = 7
    resend_unsent_after_s: Annotated[int, Field(gt=0)] = 120


@cache
def get_recovery_settings() -> RecoverySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return RecoverySettings()


def reset_recovery_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_recovery_settings.cache_clear()
