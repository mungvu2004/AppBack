"""Cấu hình bước điều phối pipeline (B5-06a [5])."""

from functools import cache
from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict

from packages.vision.preprocess.types import DEFAULT_DPI, DEFAULT_MAX_PIXELS

MIB: Final = 1024 * 1024


class OrchestrateSettings(BaseSettings):
    """Trần của `start`: byte bản gốc đọc vào, byte trang PNG ghi ra, điểm ảnh, DPI dựng PDF.

    Đọc được từ biến môi trường `PIPELINE_*` (pydantic-settings không phân biệt hoa/thường), test
    (J03, U06) hạ trần bằng tham số `settings=`; mặc định trần ảnh và DPI là
    hằng của B2-05a để API (B2-05b) và worker dựng cùng một trang.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    pipeline_original_max_bytes: int = 100 * MIB
    pipeline_page_max_bytes: int = 128 * MIB
    pipeline_max_pixels: int = DEFAULT_MAX_PIXELS
    pipeline_pdf_dpi: float = DEFAULT_DPI


@cache
def get_orchestrate_settings() -> OrchestrateSettings:
    """`OrchestrateSettings` đọc một lần mỗi tiến trình."""
    return OrchestrateSettings()
