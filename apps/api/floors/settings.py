"""Hạn mức của module tầng (B2-03 [5], theo mẫu `apps/api/projects/settings.py`).

Đọc **lười** qua `get_floors_settings()`; test C15 đổi `FLOORS_MAX` bằng
`monkeypatch.setenv` rồi `reset_floors_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class FloorsSettings(BaseSettings):
    """Trần tầng, cửa sổ khôi phục và tham số lịch dọn tầng đã xoá mềm."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    floors_max: PositiveInt = 50
    floor_restore_window_s: PositiveInt = 600
    floor_purge_after_d: PositiveInt = 30
    floor_purge_batch: PositiveInt = 100


@cache
def get_floors_settings() -> FloorsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return FloorsSettings()


def reset_floors_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_floors_settings.cache_clear()
