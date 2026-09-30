"""Mã hỏng riêng của bước ghi kết quả pipeline (B5-06b [2]).

Hằng chuỗi, **không** `ERRORS.define`: không đi qua HTTP mà vào `Progress.error` qua `record_step`.
Mã artifact vắng/hỏng dùng lại của B5-05 (`apps.worker.pipeline_build.errors`).
"""

from typing import Final

PIPELINE_RESULT_INVALID: Final = "PIPELINE_RESULT_INVALID"
"""Trộn hoặc ghi lớp AI từ chối (`ValueError`, `AppError` `VALIDATION` do `RescaleError`)."""
