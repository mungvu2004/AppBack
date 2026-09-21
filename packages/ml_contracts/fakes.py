"""Bộ giả của ba cổng suy luận (`ML_BACKEND=fake`, M01): trả đúng đáp án của trang tổng hợp.

Trang mang dấu đúng **và** khớp khổ (tổng kiểm của dấu gồm cả khổ, `read_marker`) → đáp
án `render_plan(seed)` ở cùng khổ; mọi ảnh khác, kể cả trang tổng hợp bị cắt → kết quả
rỗng. Cùng ảnh luôn cho cùng kết quả. Kết quả là mảng/tuple dùng chung (chỉ đọc).
"""

from functools import lru_cache

import numpy as np
from numpy.typing import NDArray

from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.ml_contracts.synthetic import SyntheticPlan, read_marker, render_plan

PLAN_CACHE_SIZE = 8


@lru_cache(maxsize=PLAN_CACHE_SIZE)
def _plan(seed: int, width_px: int, height_px: int) -> SyntheticPlan:
    """Đáp án đã vẽ, nhớ 8 trang gần nhất: ba bước của một lượt đọc cùng một trang."""
    return render_plan(seed, width_px=width_px, height_px=height_px)


def answer_for(image: NDArray[np.uint8]) -> SyntheticPlan | None:
    """Đáp án của ảnh khi nó là trang tổng hợp nguyên vẹn; không thì `None`.

    Tổng kiểm của dấu không bí mật: ai cũng dựng được dấu "đúng" trên một khổ mà
    `render_plan` không vẽ nổi. Khi đó không có đáp án nào — trả `None` như mọi ảnh lạ.
    """
    seed = read_marker(image)
    if seed is None:
        return None
    height, width = image.shape[:2]
    try:
        return _plan(seed, width, height)
    except ValueError:
        return None


class FakeWallSegmenter:
    """`WallSegmenter` giả: mặt nạ đáp án, hay mặt nạ rỗng cùng khổ."""

    def segment(self, image: NDArray[np.uint8]) -> NDArray[np.bool_]:
        """Mặt nạ tường `(H, W)`."""
        plan = answer_for(image)
        return np.zeros(image.shape[:2], dtype=np.bool_) if plan is None else plan.walls_mask


class FakeObjectDetector:
    """`ObjectDetector` giả: ô mở và đồ của đáp án."""

    def detect(self, image: NDArray[np.uint8]) -> tuple[DetectionPx, ...]:
        """Phát hiện của đáp án, hay rỗng."""
        plan = answer_for(image)
        return () if plan is None else plan.detections


class FakeTextReader:
    """`TextReader` giả: mọi chữ của đáp án (kích thước, nhãn phòng, khung tên)."""

    def read(self, image: NDArray[np.uint8]) -> tuple[TextPx, ...]:
        """Chữ của đáp án, hay rỗng."""
        plan = answer_for(image)
        return () if plan is None else plan.texts
