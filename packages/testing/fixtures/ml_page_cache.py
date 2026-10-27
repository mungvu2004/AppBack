"""Xoá cache trang đã giải của `apps.ml.runtime.tasks_util` trước mỗi test (PERF-03 P21).

Không nhập `apps.ml` (cv2 nặng): chỉ xoá khi module đã được test nào đó nạp.
"""

import sys

import pytest


@pytest.fixture(autouse=True)
def _clear_ml_page_cache() -> None:
    """Cache trang sống theo tiến trình: test sau không được thấy trang test trước để lại."""
    module = sys.modules.get("apps.ml.runtime.tasks_util")
    if module is not None:
        module.clear_page_cache()
