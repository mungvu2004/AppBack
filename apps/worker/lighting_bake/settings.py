"""Cài đặt worker nướng ánh sáng: đường Blender, trần thời gian, tham số nướng, trần byte đầu ra.

Đọc lại mỗi lần gọi, không `cache` (khuôn `apps/ml/ml_eval/settings.py`): rẻ, và test hạ được.
"""

from typing import Annotated, Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["BakeSettings", "get_bake_settings"]

DEFAULT_BLENDER_BIN: Final = "/opt/blender/blender"
DEFAULT_TIMEOUT_S: Final = 3000.0
"""Dưới `TASK_SOFT_TIME_LIMIT_S` 3300 của task, để worker tự giết Blender trước Celery."""


class BakeSettings(BaseSettings):
    """`BLENDER_BIN`, `BAKE_TIMEOUT_S`, `BAKE_SIZE`, `BAKE_SAMPLES`, `BAKE_CUT_M`, `BAKE_MAX_OUTPUT_BYTES`."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    blender_bin: str = DEFAULT_BLENDER_BIN
    bake_timeout_s: Annotated[float, Field(gt=0)] = DEFAULT_TIMEOUT_S
    bake_size: Annotated[int, Field(ge=256, le=8192)] = 2048
    bake_samples: Annotated[int, Field(ge=1, le=4096)] = 128
    bake_cut_m: Annotated[float, Field(ge=0)] = 1.0
    bake_max_output_bytes: Annotated[int, Field(gt=0)] = 256 * 1024 * 1024


def get_bake_settings() -> BakeSettings:
    """Cài đặt đọc từ môi trường lúc gọi."""
    return BakeSettings()
