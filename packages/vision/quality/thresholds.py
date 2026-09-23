"""Ngưỡng và phân loại ba mức chất lượng ảnh — gương `thresholds.ts:52-139` (T-04).

Bốn ngưỡng và bốn hàm `classify_*` phải khớp tuyệt đối `src/domain/quality/thresholds.ts`
(FE là nguồn duy nhất quyết định ba mức); lý lẽ vật lý đằng sau mỗi con số nằm ở đó,
không chép lại ở đây để tránh hai nguồn cùng một sự thật lệch nhau.
"""

from collections.abc import Sequence
from typing import Final, Literal

RESOLUTION_GOOD_SHORT_EDGE_PX: Final = 2000
RESOLUTION_ATTENTION_SHORT_EDGE_PX: Final = 1200
SKEW_GOOD_DEG: Final = 0.5
SKEW_ATTENTION_DEG: Final = 5
CONTRAST_GOOD_SCORE: Final = 0.75
CONTRAST_ATTENTION_SCORE: Final = 0.45
NOISE_GOOD_SCORE: Final = 0.2
NOISE_ATTENTION_SCORE: Final = 0.4

Level = Literal["good", "attention", "poor"]

_LEVEL_RANK: Final[dict[Level, int]] = {"good": 0, "attention": 1, "poor": 2}


def classify_resolution(short_edge_px: float) -> Level:
    """Cạnh ngắn (px) → mức; ngưỡng nằm đúng biên thuộc mức tốt hơn (`thresholds.ts:153-159`)."""
    if short_edge_px >= RESOLUTION_GOOD_SHORT_EDGE_PX:
        return "good"
    return "attention" if short_edge_px >= RESOLUTION_ATTENTION_SHORT_EDGE_PX else "poor"


def classify_skew(skew_deg: float) -> Level:
    """Độ nghiêng (độ) → mức, theo trị tuyệt đối: âm và dương như nhau (`thresholds.ts:162-170`)."""
    magnitude = abs(skew_deg)
    if magnitude <= SKEW_GOOD_DEG:
        return "good"
    return "attention" if magnitude < SKEW_ATTENTION_DEG else "poor"


def classify_contrast(score: float) -> Level:
    """Điểm tương phản `[0, 1]` → mức, cao hơn là tốt hơn (`thresholds.ts:172-178`)."""
    if score >= CONTRAST_GOOD_SCORE:
        return "good"
    return "attention" if score >= CONTRAST_ATTENTION_SCORE else "poor"


def classify_noise(score: float) -> Level:
    """Điểm nhiễu `[0, 1]` → mức, thang chạy ngược: thấp hơn là tốt hơn (`thresholds.ts:181-187`)."""
    if score <= NOISE_GOOD_SCORE:
        return "good"
    return "attention" if score <= NOISE_ATTENTION_SCORE else "poor"


def worst_level(levels: Sequence[Level]) -> Level:
    """Mức tệ nhất trong danh sách; rỗng → `"good"` (`thresholds.ts:220-225`)."""
    worst: Level = "good"
    for level in levels:
        if _LEVEL_RANK[level] > _LEVEL_RANK[worst]:
            worst = level
    return worst
