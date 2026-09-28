"""Hạn mức của đường ghi lớp và của lịch gộp nhật ký (B3-03 [5], mẫu `apps/api/spatial_read/settings.py`).

Đọc **lười** qua `get_spatial_write_settings()`; test đổi bằng `monkeypatch.setenv` rồi
`reset_spatial_write_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class SpatialWriteSettings(BaseSettings):
    """Số lần thử lại khi thua đua, trần mục 409, và cửa sổ/cỡ lô của lịch gộp nhật ký."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    spatial_write_attempts: PositiveInt = 3
    spatial_conflict_changes_max: PositiveInt = 5000
    spatial_log_compact_after_days: PositiveInt = 30
    spatial_log_compact_batch: PositiveInt = 5000


@cache
def get_spatial_write_settings() -> SpatialWriteSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return SpatialWriteSettings()


def reset_spatial_write_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_spatial_write_settings.cache_clear()
