"""So khớp hai mặt nạ nhị phân bằng giao/hợp điểm ảnh (B5-02 [6], việc B).

Dùng để chấm chất lượng `classic_wall_mask` so với đáp án tổng hợp, không phụ thuộc
`ml_contracts`.
"""

import numpy as np
from numpy.typing import NDArray


def mask_overlap(pred: NDArray[np.bool_], truth: NDArray[np.bool_]) -> tuple[int, int]:
    """Số điểm ảnh giao và hợp của hai mặt nạ; khác hình → `ValueError`."""
    if pred.shape != truth.shape:
        raise ValueError(f"mask khác hình: {pred.shape} vs {truth.shape}")
    intersection = int(np.count_nonzero(pred & truth))
    union = int(np.count_nonzero(pred | truth))
    return intersection, union


def mask_iou(pred: NDArray[np.bool_], truth: NDArray[np.bool_]) -> float:
    """Tỉ số giao/hợp; hai mặt nạ đều rỗng (hợp = 0) → coi là khớp tuyệt đối, trả `1.0`."""
    intersection, union = mask_overlap(pred, truth)
    if union == 0:
        return 1.0
    return intersection / union
