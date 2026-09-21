"""Suy tỉ lệ bản vẽ từ các chuỗi kích thước OCR đọc được: gương `inferScale` của `src/domain/units/scale.ts`.

Mỗi mẫu (độ dài pixel, độ dài thật) cho một tỉ số mm/px; mẫu lạc bị loại bằng MAD,
trung vị phần còn lại là đáp án. Chỉ có `mm_per_px` khi đủ mẫu **và** đủ tin cậy;
không thì trả lý do và `SCALE_UNRESOLVED`, không bao giờ tỉ lệ mặc định (K19).
Cùng phép tính số thực với FE, nên cùng con số.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

from packages.core.pipeline import PipelineCode
from packages.domain.scale.outliers import median, split_outliers
from packages.domain.scale.thresholds import SCALE_THRESHOLDS
from packages.domain.spatial.area import js_round

_RESULT_PRECISION: Final = 1e6  # sáu chữ số thập phân cho tin cậy và độ lệch, như `roundResult`

ScaleReason = Literal["tooFewSamples", "lowConfidence"]
ScaleRange = Literal["inRange", "belowRange", "aboveRange"]


@dataclass(frozen=True, slots=True)
class ScaleSample:
    """Một chuỗi kích thước OCR đọc: khoảng cách pixel trên ảnh đã nắn và độ dài mm ghi cạnh nó."""

    id: str
    pixel_length: float
    real_length_mm: float


@dataclass(frozen=True, slots=True)
class ScaleResult:
    """Kết quả suy tỉ lệ; `suggested_mm_per_px` chỉ để gợi ý khi hiệu chỉnh tay, không bao giờ để áp."""

    mm_per_px: float | None
    confidence: float
    reason: ScaleReason | None
    sample_count: int
    rejected_ids: tuple[str, ...]
    suggested_mm_per_px: float | None

    @property
    def code(self) -> PipelineCode | None:
        """`SCALE_UNRESOLVED` khi không suy được (mã nội bộ; trên dây là `scaleStatus`)."""
        return PipelineCode.SCALE_UNRESOLVED if self.mm_per_px is None else None


@dataclass(frozen=True, slots=True)
class ScaleAiDeviation:
    """Lệch tương đối có dấu giữa tỉ lệ người đặt và tỉ lệ AI (dương khi tỉ lệ người đặt lớn hơn)."""

    relative_deviation: float
    exceeds_limit: bool


def _round_result(value: float) -> float:
    """`roundResult` của FE: làm tròn sáu chữ số thập phân bằng `Math.round`."""
    return js_round(value * _RESULT_PRECISION) / _RESULT_PRECISION


def _ratio(sample: ScaleSample) -> float | None:
    """Tỉ số mm/px của mẫu dùng được: hai độ dài hữu hạn và > 0.

    Thêm so với FE: tỉ số tràn thành vô cực hay về 0 cũng coi là không dùng được
    (FE để lọt và trả tỉ lệ vô cực); với độ dài bản vẽ thật hai nhánh này không xảy ra.
    """
    lengths = (sample.pixel_length, sample.real_length_mm)
    if not all(math.isfinite(length) and length > 0 for length in lengths):
        return None
    ratio = sample.real_length_mm / sample.pixel_length
    return ratio if 0 < ratio < math.inf else None


def _confidence(kept: Sequence[float], centre: float) -> float:
    """Tin cậy trong `[0, 1]`: độ khít của mẫu quanh trung vị, kìm bớt khi ít mẫu (`scale.ts:180-190`)."""
    spread = median([abs(value - centre) for value in kept]) or 0.0
    spread_score = max(0.0, 1 - spread / centre / SCALE_THRESHOLDS.relative_spread_limit)
    count_score = min(1.0, len(kept) / SCALE_THRESHOLDS.confident_sample_count)
    weight = SCALE_THRESHOLDS.sample_count_weight
    return _round_result(spread_score * (1 - weight + weight * count_score))


def infer_scale(samples: Sequence[ScaleSample]) -> ScaleResult:
    """Suy tỉ lệ; mẫu không dùng được vào `rejected_ids` trước (thứ tự đầu vào), rồi mẫu lạc.

    `mm_per_px` chỉ khi giữ lại ≥ 3 mẫu và tin cậy ≥ 0.6; thiếu mẫu → `tooFewSamples`,
    tin cậy thấp → `lowConfidence`. "Lệch ≤ 15 %" không phải điều kiện ở đây mà là
    `compare_scale_to_ai_estimate`.
    """
    ratios = [_ratio(sample) for sample in samples]
    usable = [(sample, ratio) for sample, ratio in zip(samples, ratios, strict=True) if ratio is not None]
    split = split_outliers([ratio for _, ratio in usable], SCALE_THRESHOLDS.outlier_rejection)
    kept = [usable[index][1] for index in split.kept_indices]
    rejected_ids = (
        *(sample.id for sample, ratio in zip(samples, ratios, strict=True) if ratio is None),
        *(usable[index][0].id for index in split.rejected_indices),
    )
    centre = median(kept)
    confidence = 0.0 if centre is None else _confidence(kept, centre)
    reason: ScaleReason | None = None
    if centre is None or len(kept) < SCALE_THRESHOLDS.minimum_sample_count:
        reason = "tooFewSamples"
    elif confidence < SCALE_THRESHOLDS.minimum_confidence:
        reason = "lowConfidence"
    return ScaleResult(
        mm_per_px=centre if reason is None else None,
        confidence=confidence,
        reason=reason,
        sample_count=len(kept),
        rejected_ids=rejected_ids,
        suggested_mm_per_px=centre,
    )


def classify_scale_range(ratio: float) -> ScaleRange:
    """Tỉ lệ so với dải đọc được 1-200 mm/px (hai đầu tính là trong dải); chỉ để cảnh báo, không chặn."""
    if ratio < SCALE_THRESHOLDS.min_millimetres_per_pixel:
        return "belowRange"
    if ratio > SCALE_THRESHOLDS.max_millimetres_per_pixel:
        return "aboveRange"
    return "inRange"


def compare_scale_to_ai_estimate(manual: float, ai: float) -> ScaleAiDeviation:
    """So tỉ lệ người đặt với tỉ lệ AI ước lượng; vượt khi `|lệch| > 15 %` (đúng 15 % không vượt).

    AI ≤ 0 (ước lượng suy biến) → lệch 0, không chia cho nó. Đầu vào không hữu hạn → `ValueError`.
    """
    if ai <= 0:
        return ScaleAiDeviation(relative_deviation=0.0, exceeds_limit=False)
    deviation = _round_result((manual - ai) / ai)
    return ScaleAiDeviation(deviation, abs(deviation) > SCALE_THRESHOLDS.ai_deviation_limit)
