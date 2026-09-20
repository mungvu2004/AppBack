"""Cấu hình CSDL (BE-00 §2.1). Nơi **duy nhất** đọc `DATABASE_URL`.

Module khác nhận engine hay sessionmaker qua `packages.db.engine`, không tự đọc DSN.
"""

from functools import cache
from typing import Final

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DRIVER: Final = "postgresql+asyncpg://"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    database_url: str
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_s: int = 5
    db_statement_timeout_ms: int = 10000
    db_lock_timeout_ms: int = 5000
    db_after_commit_workers: int = 8

    @field_validator("database_url")
    @classmethod
    def _asyncpg_driver(cls, value: str) -> str:
        if not value.startswith(DRIVER):
            raise ValueError(f"DATABASE_URL phải bắt đầu bằng {DRIVER}")
        return value


@cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


def reset_database_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_database_settings.cache_clear()
