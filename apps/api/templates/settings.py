"""Hạn mức của module khuôn thuộc tính (B2-07 [5]); cùng cách đọc lười như `measurements`."""

from functools import cache

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class TemplatesSettings(BaseSettings):
    """Trần số khuôn mỗi dự án."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    templates_max: PositiveInt = 500


@cache
def get_templates_settings() -> TemplatesSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần."""
    return TemplatesSettings()


def reset_templates_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_templates_settings.cache_clear()
