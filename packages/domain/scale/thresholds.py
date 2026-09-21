"""Mười ngưỡng suy tỉ lệ, đúng `SCALE_THRESHOLDS` của `src/domain/units/scale.ts:30-67`."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ScaleThresholds:
    """Chính sách suy tỉ lệ ở một chỗ; đổi một ngưỡng là đổi cả FE lẫn BE."""

    outlier_rejection: float = 3  # z-score cải biên quá mức này là OCR đọc hỏng
    minimum_sample_count: int = 3  # ít mẫu dùng được hơn thì phải đặt tỉ lệ tay
    minimum_confidence: float = 0.6  # tin cậy thấp hơn thì không tự áp tỉ lệ
    confident_sample_count: int = 5  # từ số mẫu này, số mẫu thôi kìm tin cậy
    relative_spread_limit: float = 0.05  # độ tản tương đối làm tin cậy về 0
    sample_count_weight: float = 0.5  # phần tin cậy do số mẫu quyết định
    level_agreement_limit: float = 0.02  # lệch tỉ lệ giữa hai tầng đáng cảnh báo
    min_millimetres_per_pixel: float = 1  # dưới mức này là đọc sai, không phải ảnh nét hơn
    max_millimetres_per_pixel: float = 200  # trên mức này tường 110 mm hẹp hơn nửa pixel
    ai_deviation_limit: float = 0.15  # lệch giữa tỉ lệ người đặt và tỉ lệ AI đáng cảnh báo


SCALE_THRESHOLDS: Final = ScaleThresholds()
