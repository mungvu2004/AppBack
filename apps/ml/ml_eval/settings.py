"""Trần của hộp cát đánh giá: `ML_EVAL_MAX_BYTES` (`RLIMIT_AS` của tiến trình con), `ML_EVAL_TIMEOUT_S`.

Đọc lại mỗi lần gọi, không `cache`: rẻ (hai biến môi trường), và cache cài đặt dùng chung
từng rò giữa module test dưới xdist (B6-03b). Hộp cát nhận giá trị qua tiến trình cha.
"""

from typing import Annotated, Final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DEFAULT_MAX_BYTES", "DEFAULT_TIMEOUT_S", "MlEvalSettings", "get_eval_settings"]

DEFAULT_MAX_BYTES: Final = 10 * 1024**3
DEFAULT_TIMEOUT_S: Final = 3000.0


class MlEvalSettings(BaseSettings):
    """`ML_EVAL_MAX_BYTES` 10 GiB, `ML_EVAL_TIMEOUT_S` 3000 (khối [2] đặt 4 GiB / 1800); test hạ cả hai.

    Nâng vì SegFormer-B2 (105 MB ONNX, 2026-10-22): ORT cấp một khối 768 MiB → hỏng dưới
    `RLIMIT_AS` 4 GiB; lượt chấm đủ mất ~21 phút CPU 4 luồng (đỉnh ~5,2 GiB cả container).
    3000 s vẫn dưới `TASK_SOFT_TIME_LIMIT_S` 3300 của task cha.
    """

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    ml_eval_max_bytes: Annotated[int, Field(gt=0)] = DEFAULT_MAX_BYTES
    ml_eval_timeout_s: Annotated[float, Field(gt=0)] = DEFAULT_TIMEOUT_S


def get_eval_settings() -> MlEvalSettings:
    """Cài đặt đọc từ môi trường lúc gọi."""
    return MlEvalSettings()
