"""Hạn mức của module phép đo (B2-07 [5], theo mẫu `apps/api/floors/settings.py`).

Đọc **lười** qua `get_measurements_settings()`; test đổi trần bằng `monkeypatch.setenv` rồi
`reset_measurements_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class MeasurementsSettings(BaseSettings):
    """Trần số phép đo, số điểm mỗi phép đo và tổng điểm mỗi dự án."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    measurements_max: PositiveInt = 1000
    measurement_points_max: PositiveInt = 200
    measurement_points_total_max: PositiveInt = 20000


@cache
def get_measurements_settings() -> MeasurementsSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return MeasurementsSettings()


def reset_measurements_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_measurements_settings.cache_clear()
