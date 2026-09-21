"""Thống kê bền cho mẫu đọc từ bản vẽ: gương `src/domain/units/outliers.ts`.

OCR sai theo kiểu rất riêng: đa số mẫu lệch nhau dưới một phần trăm, vài mẫu hỏng
lệch cả bậc độ lớn. Trung vị và độ lệch tuyệt đối trung vị (MAD) đứng yên tới khi
quá nửa số mẫu hỏng, nên dùng chúng thay cho trung bình và độ lệch chuẩn. Kết quả
trả **chỉ số**, để người gọi lần ra mẫu bị loại.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

_MAD_TO_SIGMA: Final = 0.6745  # hằng của phương pháp, không phải ngưỡng chỉnh được
_MEAN_DEVIATION_TO_SIGMA: Final = 1.2533


@dataclass(frozen=True, slots=True)
class OutlierSplit:
    """Mẫu giữ và mẫu loại (chỉ số theo thứ tự gốc), trung vị (`None` khi rỗng) và MAD của mọi mẫu."""

    kept_indices: tuple[int, ...]
    rejected_indices: tuple[int, ...]
    median: float | None
    absolute_deviation: float


def _middle(values: Sequence[float]) -> float:
    """Trung vị của dãy không rỗng; chẵn thì trung bình hai phần tử giữa."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def median(values: Sequence[float]) -> float | None:
    """Trung vị; `None` khi rỗng."""
    return _middle(values) if values else None


def _mean(values: Sequence[float]) -> float:
    """Trung bình của dãy không rỗng, cộng tuần tự như `reduce` của FE (không `sum()` cộng bù của 3.12)."""
    total = 0.0
    for value in values:
        total += value
    return total / len(values)


def split_outliers(values: Sequence[float], threshold: float) -> OutlierSplit:
    """Tách mẫu gần trung vị khỏi mẫu quá xa: loại khi `|v - trung vị| / spread > threshold`.

    `spread = MAD / 0.6745`; MAD bằng 0 (đa số mẫu trùng nhau) thì dùng trung bình
    độ lệch x 1.2533 để vẫn bắt được một mẫu lạc; mọi mẫu bằng nhau thì không loại
    mẫu nào. `threshold` ≤ 0 hay không hữu hạn → `ValueError`.
    """
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError(f"ngưỡng loại mẫu phải dương và hữu hạn: {threshold}")
    if not values:
        return OutlierSplit((), (), None, 0.0)
    centre = _middle(values)
    distances = [abs(value - centre) for value in values]
    deviation = _middle(distances)
    spread = deviation / _MAD_TO_SIGMA if deviation > 0 else _mean(distances) * _MEAN_DEVIATION_TO_SIGMA
    kept = [spread == 0 or distance / spread <= threshold for distance in distances]
    return OutlierSplit(
        kept_indices=tuple(index for index, keep in enumerate(kept) if keep),
        rejected_indices=tuple(index for index, keep in enumerate(kept) if not keep),
        median=centre,
        absolute_deviation=deviation,
    )
