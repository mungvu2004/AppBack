"""Cấu hình bước dựng lớp không gian (B5-05 [5])."""

from functools import cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class PipelineBuildSettings(BaseSettings):
    """`PIPELINE_ARTIFACT_MAX_BYTES`: trần byte gom mỗi artifact ML khi đọc (bằng trần B5-01).

    Hằng cố định, không đọc từ biến môi trường: `ClassVar` để pydantic-settings không coi
    nó là một trường cấu hình.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    PIPELINE_ARTIFACT_MAX_BYTES: ClassVar[int] = 16_777_216


@cache
def get_pipeline_build_settings() -> PipelineBuildSettings:
    """`PipelineBuildSettings` đọc một lần mỗi tiến trình."""
    return PipelineBuildSettings()


def reset_pipeline_build_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_pipeline_build_settings.cache_clear()
