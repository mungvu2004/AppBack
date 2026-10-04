"""Cấu hình CSDL (BE-00 §2.1). Nơi **duy nhất** đọc `DATABASE_URL`.

Module khác nhận engine hay sessionmaker qua `packages.db.engine`, không tự đọc DSN.
"""

from functools import cache
from typing import Final, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.core.settings import PLACEHOLDER_MARKER

DRIVER: Final = "postgresql+asyncpg://"


class DatabaseSettings(BaseSettings):
    """Cấu hình đọc từ biến môi trường: DatabaseSettings."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None, hide_input_in_errors=True)

    database_url: str
    app_env: Literal["dev", "test", "ci", "staging", "production"] | None = None
    """`APP_ENV` chỉ để từ chối DSN mẫu ở staging/production; thiếu thì không kiểm."""
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_s: int = 5
    # Trần bắt tay kết nối, đặt tường minh vì asyncpg im lặng dùng 60 s của riêng nó (R-24).
    # Đường phục vụ request phải hỏng nhanh, không chờ hết trần của thư viện.
    db_connect_timeout_s: int = 10
    db_statement_timeout_ms: int = 10000
    db_lock_timeout_ms: int = 5000
    db_after_commit_workers: int = 8

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, value: str) -> str:
        """Hàm của cấu hình: asyncpg driver."""
        if not value.startswith(DRIVER):
            raise ValueError(f"DATABASE_URL phải bắt đầu bằng {DRIVER}")
        return value

    @model_validator(mode="after")
    def _no_placeholder_dsn(self) -> "DatabaseSettings":
        """Ở staging/production, DSN còn `change-me` (mẫu của `env.example`) là cấu hình chưa sửa (SEC-041)."""
        if self.app_env in ("staging", "production") and PLACEHOLDER_MARKER in self.database_url.casefold():
            raise ValueError(f"DATABASE_URL còn giá trị mẫu {PLACEHOLDER_MARKER} ở staging/production")
        return self


@cache
def get_database_settings() -> DatabaseSettings:
    """Hàm của cấu hình: get database settings."""
    return DatabaseSettings()


def reset_database_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_database_settings.cache_clear()
