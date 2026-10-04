"""Thước đo chữ kích thước dùng chung cho test OCR (NO-349): một nguồn cho mọi bộ đọc được chấm.

Chữ kích thước của `render_plan` có dạng `1.234`; một chữ đáp án được tính là đọc đúng khi có mục
đọc ra **đúng chuỗi** mà tâm hộp lệch tâm đáp án dưới `DIMENSION_NEAR_PX` theo cả hai trục.
"""

import re
from collections.abc import Iterable
from typing import Final

from packages.ml_contracts.artifacts import TextPx

__all__ = ["DIMENSION_NEAR_PX", "DIMENSION_RE", "dimension_hits"]

DIMENSION_RE: Final = re.compile(r"[0-9]{1,3}(\.[0-9]{3})*")
DIMENSION_NEAR_PX: Final = 25


def dimension_hits(found: Iterable[tuple[float, float, str]], answers: Iterable[TextPx]) -> tuple[int, int]:
    """`(đọc đúng, tổng)` chữ kích thước của `answers` so với các mục `(tâm x, tâm y, chuỗi)` đọc được."""
    items = list(found)
    hits = total = 0
    for answer in answers:
        if not DIMENSION_RE.fullmatch(answer.text):
            continue
        total += 1
        cx, cy = (answer.box.x_min + answer.box.x_max) / 2, (answer.box.y_min + answer.box.y_max) / 2
        hits += any(
            abs(x - cx) < DIMENSION_NEAR_PX and abs(y - cy) < DIMENSION_NEAR_PX and text == answer.text
            for x, y, text in items
        )
    return hits, total
