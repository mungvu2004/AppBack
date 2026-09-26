"""Hạn mức của lịch đối chiếu bảng đếm (B3-02 [5], theo mẫu `apps/api/floors/settings.py`).

Đọc **lười** qua `get_spatial_read_settings()`; test đổi bằng `monkeypatch.setenv` rồi
`reset_spatial_read_settings_cache()`.
"""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class SpatialReadSettings(BaseSettings):
    """Cửa sổ nhìn lại và cỡ lô của `default.spatial_read.reconcile_counts`."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    spatial_recount_lookback_s: PositiveInt = 900
    spatial_recount_batch: PositiveInt = 200


@cache
def get_spatial_read_settings() -> SpatialReadSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return SpatialReadSettings()


def reset_spatial_read_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_spatial_read_settings.cache_clear()
