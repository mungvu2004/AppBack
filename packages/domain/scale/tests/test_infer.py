"""Suy tỉ lệ, dải tỉ lệ, so với AI: chép `scale.test.ts:37-48,79-159,224-280` và các ngưỡng."""

from dataclasses import asdict

import pytest

from packages.core.pipeline import PipelineCode
from packages.domain.scale import (
    SCALE_THRESHOLDS,
    ScaleAiDeviation,
    ScaleSample,
    classify_scale_range,
    compare_scale_to_ai_estimate,
    infer_scale,
)

TARGET_RATIO = 12

# Mười chuỗi kích thước của một tờ: tám mẫu quanh 12 mm/px trong 0,2 %; `M-009`
# khớp nhầm đường, `M-010` rơi một chữ số, cả hai lệch hơn ba lần.
TEN_READINGS = [
    ScaleSample("M-001", 400, 4800),
    ScaleSample("M-002", 200, 2402),
    ScaleSample("M-003", 350, 4193),
    ScaleSample("M-004", 500, 6010),
    ScaleSample("M-005", 250, 2995),
    ScaleSample("M-006", 600, 7212),
    ScaleSample("M-007", 300, 3600),
    ScaleSample("M-008", 450, 5405),
    ScaleSample("M-009", 120, 4800),
    ScaleSample("M-010", 800, 2400),
]


def test_thresholds_are_the_ten_fe_constants() -> None:
    """Đúng mười hằng của `scale.ts:30-67`."""
    assert asdict(SCALE_THRESHOLDS) == {
        "outlier_rejection": 3,
        "minimum_sample_count": 3,
        "minimum_confidence": 0.6,
        "confident_sample_count": 5,
        "relative_spread_limit": 0.05,
        "sample_count_weight": 0.5,
        "level_agreement_limit": 0.02,
        "min_millimetres_per_pixel": 1,
        "max_millimetres_per_pixel": 200,
        "ai_deviation_limit": 0.15,
    }


def test_ten_readings_infer_the_scale_and_drop_two() -> None:
    """Tám mẫu giữ, loại `M-009`, `M-010`; trung vị 12,005 (sai ≤ 0,05 so với 12), tin cậy cao."""
    result = infer_scale(TEN_READINGS)
    assert (result.sample_count, result.rejected_ids, result.reason, result.code) == (
        8,
        ("M-009", "M-010"),
        None,
        None,
    )
    assert result.mm_per_px is not None
    assert result.mm_per_px == pytest.approx(TARGET_RATIO, abs=0.05)
    assert result.mm_per_px == result.suggested_mm_per_px == pytest.approx(12.005)
    assert abs(400 * result.mm_per_px - 4800) / 4800 < 0.001
    assert SCALE_THRESHOLDS.minimum_confidence < result.confidence <= 1
    assert result.confidence == 0.982415


def test_two_readings_are_too_few() -> None:
    """Hai mẫu khớp nhau vẫn thiếu mẫu: không có tỉ lệ, gợi ý 12, `SCALE_UNRESOLVED`."""
    result = infer_scale([ScaleSample("M-001", 400, 4800), ScaleSample("M-002", 200, 2400)])
    assert (result.mm_per_px, result.reason, result.sample_count) == (None, "tooFewSamples", 2)
    assert result.suggested_mm_per_px == TARGET_RATIO
    assert result.code is PipelineCode.SCALE_UNRESOLVED


def test_disagreeing_readings_have_low_confidence() -> None:
    """Năm mẫu tản 10-14 mm/px: đủ mẫu mà tin cậy thấp → `lowConfidence`, gợi ý 12, không tỉ lệ mặc định (K19)."""
    lengths = [4000, 4400, 4800, 5200, 5600]
    result = infer_scale([ScaleSample(f"M-00{i}", 400, mm) for i, mm in enumerate(lengths, start=1)])
    assert (result.mm_per_px, result.reason, result.sample_count) == (None, "lowConfidence", 5)
    assert result.confidence < SCALE_THRESHOLDS.minimum_confidence
    assert result.suggested_mm_per_px == TARGET_RATIO
    assert result.code is PipelineCode.SCALE_UNRESOLVED


def test_unmeasurable_readings_are_rejected_first() -> None:
    """Mẫu 0 px và 0 mm bị loại trước, theo thứ tự đầu vào; ba mẫu còn lại đủ suy."""
    result = infer_scale(
        [
            ScaleSample("M-001", 400, 4800),
            ScaleSample("M-002", 200, 2400),
            ScaleSample("M-003", 300, 3600),
            ScaleSample("M-004", 0, 3600),
            ScaleSample("M-005", 250, 0),
        ]
    )
    assert (result.rejected_ids, result.sample_count, result.mm_per_px) == (("M-004", "M-005"), 3, TARGET_RATIO)


@pytest.mark.parametrize(
    ("pixel_length", "real_length_mm"),
    [(-400, 4800), (float("nan"), 4800), (400, float("inf")), (1e300, 1e-300), (1e-300, 1e300)],
)
def test_degenerate_readings_are_rejected(pixel_length: float, real_length_mm: float) -> None:
    """Âm, NaN, vô cực, và tỉ số tràn về 0 hay vô cực đều không dùng được."""
    good = [ScaleSample(f"M-00{i}", 400, 4800) for i in range(3)]
    result = infer_scale([*good, ScaleSample("M-BAD", pixel_length, real_length_mm)])
    assert (result.rejected_ids, result.mm_per_px) == (("M-BAD",), TARGET_RATIO)


def test_empty_input_does_not_throw() -> None:
    """Rỗng → tin cậy 0, gợi ý `None`, `SCALE_UNRESOLVED`."""
    result = infer_scale([])
    assert (result.confidence, result.sample_count, result.suggested_mm_per_px) == (0.0, 0, None)
    assert (result.reason, result.code) == ("tooFewSamples", PipelineCode.SCALE_UNRESOLVED)


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [(1.0, "inRange"), (12, "inRange"), (200.0, "inRange"), (0.5, "belowRange"), (250, "aboveRange")],
)
def test_classify_scale_range(ratio: float, expected: str) -> None:
    """Dải 1-200 mm/px, hai đầu tính là trong dải."""
    assert classify_scale_range(ratio) == expected


@pytest.mark.parametrize(
    ("manual", "ai", "expected"),
    [
        (12.3, 12, ScaleAiDeviation(0.025, False)),
        (9, 12, ScaleAiDeviation(-0.25, True)),
        (13.7, 12, ScaleAiDeviation(0.141667, False)),
        (13.9, 12, ScaleAiDeviation(0.158333, True)),
        (11.5, 10, ScaleAiDeviation(0.15, False)),
        (11.501, 10, ScaleAiDeviation(0.1501, True)),
        (8.5, 10, ScaleAiDeviation(-0.15, False)),
        (12, 0, ScaleAiDeviation(0.0, False)),
        (12, -3, ScaleAiDeviation(0.0, False)),
    ],
)
def test_compare_scale_to_ai_estimate(manual: float, ai: float, expected: ScaleAiDeviation) -> None:
    """Lệch có dấu; đúng 15 % không vượt, 15,01 % vượt; AI ≤ 0 → lệch 0, không chia."""
    assert compare_scale_to_ai_estimate(manual, ai) == expected


def test_compare_refuses_non_finite_manual_scale() -> None:
    """Tỉ lệ người đặt vô cực → `ValueError`, không trả lệch vô cực."""
    with pytest.raises(ValueError, match="không hữu hạn"):
        compare_scale_to_ai_estimate(float("inf"), 12)
