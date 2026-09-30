"""Cấu hình bước điều phối pipeline (B5-06a [5])."""

from functools import cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.vision.preprocess.types import DEFAULT_DPI, DEFAULT_MAX_PIXELS

MIB = 1024 * 1024


class OrchestrateSettings(BaseSettings):
    """Trần của `start`: byte bản gốc đọc vào, byte trang PNG ghi ra, điểm ảnh, DPI dựng PDF.

    Đọc được từ biến môi trường để test (J03, U06) hạ trần; mặc định trần ảnh và DPI là
    hằng của B2-05a để API (B2-05b) và worker dựng cùng một trang.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    PIPELINE_ORIGINAL_MAX_BYTES: int = 100 * MIB
    PIPELINE_PAGE_MAX_BYTES: int = 128 * MIB
    PIPELINE_MAX_PIXELS: int = DEFAULT_MAX_PIXELS
    PIPELINE_PDF_DPI: float = DEFAULT_DPI


@cache
def get_orchestrate_settings() -> OrchestrateSettings:
    """`OrchestrateSettings` đọc một lần mỗi tiến trình."""
    return OrchestrateSettings()


def reset_orchestrate_settings_cache() -> None:
    """Chỉ cho test và CLI: đọc lại biến môi trường ở lần gọi sau."""
    get_orchestrate_settings.cache_clear()
