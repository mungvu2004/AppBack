"""Hạn mức của module thư viện .glb (B2-06 [5], theo mẫu `apps/api/drawings/settings.py`).

Đọc **lười** qua `get_library_settings()`; test đổi trần bằng `monkeypatch.setenv` rồi
`reset_library_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class LibrarySettings(BaseSettings):
    """Trần số mục của #14 và tuổi tối đa của lần kiểm object trước khi lịch kiểm lại."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    library_list_max: PositiveInt = 500
    library_verify_after_s: PositiveInt = 3600


@cache
def get_library_settings() -> LibrarySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return LibrarySettings()


def reset_library_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_library_settings.cache_clear()
