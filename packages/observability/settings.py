"""`ObservabilitySettings` — cổng và hạn mức của exporter `/metrics` (BE-00 §11)."""

from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    """Đọc lười qua `get_observability_settings()`, một lần mỗi tiến trình."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    metrics_host: str = "0.0.0.0"  # noqa: S104 — cổng nội bộ, compose không công bố (BE-00 §11)
    metrics_port: int = 9464
    """0 = tắt exporter."""
    metrics_max_series: int = 1000


@cache
def get_observability_settings() -> ObservabilitySettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return ObservabilitySettings()


def reset_observability_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_observability_settings.cache_clear()
