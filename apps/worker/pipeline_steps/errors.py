"""Mã hỏng riêng của điều phối bước pipeline (B5-06c [2]).

Hằng chuỗi, **không** `ERRORS.define`: không đi qua HTTP mà vào `Progress.error` qua
`record_step`. Mã khác tới từ bước ML, B5-05, B0-05.
"""

from typing import Final

PIPELINE_STEP_TIMEOUT: Final = "PIPELINE_STEP_TIMEOUT"
"""Quét bù đã gửi lại bước hiện tại đủ `PIPELINE_STEP_REQUEUE_MAX` lần mà lượt vẫn im."""
MODEL_PIN_MISMATCH: Final = "MODEL_PIN_MISMATCH"
"""Bước ML báo `model_version_id` khác bản đã ghim cho họ đó."""
PIPELINE_RESULT_INVALID: Final = "PIPELINE_RESULT_INVALID"
"""Kết quả bước sai hình: khoá artifact ngoài lượt, thiếu khoá, mã lỗi sai mẫu, bản vẽ không khớp."""
