"""Cấu hình điều phối bước và quét bù (B5-06c [5])."""

from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class StepsSettings(BaseSettings):
    """Ngưỡng quét bù và giữ artifact; đọc được từ biến môi trường để test hạ trần."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    PIPELINE_STEP_REQUEUE_AFTER_S: int = 600
    PIPELINE_STEP_REQUEUE_MAX: int = 3
    PIPELINE_RUN_MAX_S: int = 21600
    PIPELINE_ARTIFACT_RETENTION_S: int = 604800
    PIPELINE_SWEEP_BATCH: int = 100


@cache
def get_steps_settings() -> StepsSettings:
    """`StepsSettings` đọc một lần mỗi tiến trình."""
    return StepsSettings()


def reset_steps_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_steps_settings.cache_clear()
