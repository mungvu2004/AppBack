"""Hạn mức xử lý ảnh của module chất lượng (B2-05b [5], theo mẫu `apps/api/drawings/settings.py`).

Đọc **lười** qua `get_quality_settings()`; test đổi trần bằng `monkeypatch.setenv` rồi
`reset_quality_settings_cache()` (và `processing.reset_processing_state()` khi đổi số chỗ).
"""

from functools import cache

from pydantic import PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class QualitySettings(BaseSettings):
    """Trần điểm ảnh, DPI, hàng xử lý và ngưỡng hình học góc."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    quality_max_pixels: PositiveInt = 40_000_000
    quality_pdf_dpi: PositiveInt = 200
    quality_workers: PositiveInt = 2
    quality_queue_wait_s: PositiveFloat = 2
    quality_min_quad_area: PositiveFloat = 0.05
    quality_corner_eps: PositiveFloat = 0.002
    quality_skew_min_deg: PositiveFloat = 0.1
    quality_page_max_bytes: PositiveInt = 134_217_728


@cache
def get_quality_settings() -> QualitySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return QualitySettings()


def reset_quality_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_quality_settings.cache_clear()
