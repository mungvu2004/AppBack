"""Mã hỏng của lượt chạy bước dựng (B5-05 [2]).

Hằng chuỗi, **không** `ERRORS.define`: không đi qua HTTP mà vào `Progress.error` qua B5-06c.
"""

from typing import Final

PIPELINE_ARTIFACT_MISSING: Final = "PIPELINE_ARTIFACT_MISSING"
"""Artifact ML của một bước không có trong kho (`NOT_FOUND`)."""

PIPELINE_ARTIFACT_INVALID: Final = "PIPELINE_ARTIFACT_INVALID"
"""Artifact quá trần, JSON sai hợp đồng B5-01, hoặc `run_prefix` sai."""

PIPELINE_BUILD_INVALID: Final = "PIPELINE_BUILD_INVALID"
"""`build_layer` từ chối đầu vào (`ValueError`) hoặc lớp dựng ra có lỗi critical."""
