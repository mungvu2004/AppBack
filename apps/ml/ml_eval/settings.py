"""Trần của hộp cát đánh giá: `ML_EVAL_MAX_BYTES` (`RLIMIT_AS` của tiến trình con), `ML_EVAL_TIMEOUT_S`.

Đọc lại mỗi lần gọi, không `cache`: rẻ (hai biến môi trường), và cache cài đặt dùng chung
từng rò giữa module test dưới xdist (B6-03b). Hộp cát nhận giá trị qua tiến trình cha.
"""

from typing import Annotated, Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DEFAULT_MAX_BYTES", "DEFAULT_TIMEOUT_S", "MlEvalSettings", "get_eval_settings"]

DEFAULT_MAX_BYTES: Final = 4 * 1024**3
DEFAULT_TIMEOUT_S: Final = 1800.0


class MlEvalSettings(BaseSettings):
    """`ML_EVAL_MAX_BYTES` 4 GiB, `ML_EVAL_TIMEOUT_S` 1800 (khối [2]); test hạ cả hai."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    ml_eval_max_bytes: Annotated[int, Field(gt=0)] = DEFAULT_MAX_BYTES
    ml_eval_timeout_s: Annotated[float, Field(gt=0)] = DEFAULT_TIMEOUT_S


def get_eval_settings() -> MlEvalSettings:
    """Cài đặt đọc từ môi trường lúc gọi."""
    return MlEvalSettings()
