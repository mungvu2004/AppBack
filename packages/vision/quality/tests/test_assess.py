"""Bảy ảnh tổng hợp của khối [8] "Phát hiện": mã, mức, vùng và tính nhất quán với ngưỡng."""

import logging

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.preprocess.tests.drawing import make_drawing, rotate
from packages.vision.preprocess.types import RgbImage
from packages.vision.quality.assess import (
    QUALITY_CODES,
    Finding,
    QualityReport,
    _bbox_region,
    assess,
    measure,
)
from packages.vision.quality.metrics import WHOLE_IMAGE, Region
from packages.vision.quality.thresholds import (
    Level,
    classify_contrast,
    classify_noise,
    classify_resolution,
    classify_skew,
    worst_level,
)

_LOG = logging.getLogger(__name__)
_CLEAN_W, _CLEAN_H = 2400, 2000
_SMALL_W, _SMALL_H = 1240, 900
_PALE_INK, _PALE_CORNER_INK = 110, 175


def _clean() -> NDArray[np.uint8]:
    """Bản vẽ sạch 2.400 x 2.000 có khung — ảnh nền của mọi biến thể dưới đây.

    Cạnh ngắn đúng `RESOLUTION_GOOD_SHORT_EDGE_PX`, không phải 1.700 như khối [8] viết:
    1.700 < 2.000 nên `classify_resolution` cho `attention`, tức ảnh "sạch" đó vẫn có
    một phát hiện. Ngưỡng FE là nguồn duy nhất nên ảnh đổi, ngưỡng giữ nguyên.
    """
    return make_drawing(_CLEAN_W, _CLEAN_H)


def _shrunk() -> NDArray[np.uint8]:
    """Ảnh sạch thu về 1.240 x 900: cạnh ngắn 900 < 1.200 nên độ phân giải `poor`."""
    resized = cv2.resize(_clean(), (_SMALL_W, _SMALL_H), interpolation=cv2.INTER_AREA)
    return np.asarray(resized, dtype=np.uint8)


def _compressed_range(pixels: NDArray[np.uint8], keep: float) -> NDArray[np.uint8]:
    """Nén dải xám về phía trắng: `255 - (255 - v) * keep`, giữ nguyên hình, giảm tương phản."""
    squeezed = 255.0 - (255.0 - pixels.astype(np.float64)) * keep
    return np.asarray(np.clip(squeezed, 0.0, 255.0).round(), dtype=np.uint8)


def _pale_corner() -> NDArray[np.uint8]:
    """Nét nhạt đều `_PALE_INK` cả ảnh, riêng ô góc trên-trái nhạt hơn hẳn (`_PALE_CORNER_INK`).

    Nâng nét bằng `np.maximum` (giấy vẫn 255) nên điểm tương phản đọc thẳng ra được:
    cả ảnh `(255 - 110) / 255 = 0,569` → `attention`, ô góc `(255 - 175) / 255 = 0,314`
    → ô tệ nhất. Nhạt **một ô thôi** thì trung vị toàn ảnh gần như không đổi và
    `LOW_CONTRAST` không hề sinh ra, nên phải nhạt đều rồi mới nhấn một ô.
    """
    pixels = np.maximum(_clean(), _PALE_INK)
    height, width = pixels.shape[0], pixels.shape[1]
    corner = pixels[: height // 4, : width // 4]
    pixels[: height // 4, : width // 4] = np.maximum(corner, _PALE_CORNER_INK)
    return np.asarray(pixels, dtype=np.uint8)


def _salt_pepper(ratio: float) -> NDArray[np.uint8]:
    """Rắc đốm đen 1 px lên ảnh sạch, tất định: lưới đều bước `round(1/sqrt(ratio))`.

    Không dùng số ngẫu nhiên nên số thành phần liên thông nhỏ, và do đó `noise_score`,
    lặp lại y hệt giữa các lần chạy.
    """
    pixels = _clean()
    step = max(1, round((1.0 / ratio) ** 0.5))
    pixels[::step, ::step] = 0
    return pixels


_IMAGES: dict[str, NDArray[np.uint8]] = {
    "clean": _clean(),
    "shrunk": _shrunk(),
    "skew_3_4": rotate(_clean(), 3.4),
    "skew_6": rotate(_clean(), 6.0),
    "no_frame": make_drawing(_CLEAN_W, _CLEAN_H, frame=False),
    "low_contrast": _compressed_range(_clean(), 0.4),
    "pale_corner": _pale_corner(),
    "salt_pepper": _salt_pepper(0.02),
}


def _report(name: str) -> QualityReport:
    """Báo cáo chất lượng của ảnh mẫu `name`."""
    return assess(RgbImage(_IMAGES[name]))


def _finding(report: QualityReport, code: str) -> Finding:
    """Phát hiện mang mã `code`; không có → `AssertionError` kèm danh sách mã thật."""
    found = [f for f in report.findings if f.code == code]
    assert found, f"thiếu {code}, có {[f.code for f in report.findings]}"
    return found[0]


def _codes(report: QualityReport) -> list[str]:
    """Danh sách mã theo đúng thứ tự trong báo cáo."""
    return [f.code for f in report.findings]


def test_assess_clean_image_has_no_findings() -> None:
    """Ảnh sạch 2.400 x 2.000 có khung: không phát hiện, mức `good`, khung tìm được."""
    report = _report("clean")
    assert _codes(report) == []
    assert report.level == "good"
    assert report.frame is not None
    assert report.measurement.width_px == _CLEAN_W
    assert report.measurement.height_px == _CLEAN_H


def test_assess_low_resolution_is_poor() -> None:
    """Thu về 1.240 x 900 → `RESOLUTION_TOO_LOW` mức `poor`, vùng cả ảnh, `shortEdgePx`."""
    finding = _finding(_report("shrunk"), "RESOLUTION_TOO_LOW")
    assert finding.severity == "poor"
    assert finding.region == WHOLE_IMAGE
    assert dict(finding.metrics) == {"shortEdgePx": float(_SMALL_H)}


def test_assess_mild_skew_is_attention() -> None:
    """Xoay 3,4° → `SKEW_DETECTED` mức `attention`; `skewDeg` khớp số đo đã làm tròn."""
    report = _report("skew_3_4")
    finding = _finding(report, "SKEW_DETECTED")
    assert finding.severity == "attention"
    assert dict(finding.metrics) == {"skewDeg": report.measurement.skew_deg}
    assert 3.2 <= report.measurement.skew_deg <= 3.6


def test_assess_strong_skew_is_poor() -> None:
    """Xoay 6° (≥ `SKEW_ATTENTION_DEG`) → `SKEW_DETECTED` mức `poor`."""
    report = _report("skew_6")
    assert _finding(report, "SKEW_DETECTED").severity == "poor"
    assert 5.0 <= abs(report.measurement.skew_deg) <= 6.5


def test_assess_skew_region_is_inside_image() -> None:
    """Vùng `SKEW_DETECTED` là hộp bao các đoạn đã dùng, không rỗng và nằm trọn trong ảnh."""
    region = _finding(_report("skew_3_4"), "SKEW_DETECTED").region
    assert region.width_ratio > 0.0
    assert region.height_ratio > 0.0
    assert region.x_ratio + region.width_ratio <= 1.0 + 1e-9
    assert region.y_ratio + region.height_ratio <= 1.0 + 1e-9


def test_assess_missing_frame_is_attention() -> None:
    """Bản vẽ không khung → `FRAME_NOT_FOUND` `attention`, vùng chừa 2 % mép, `metrics` rỗng."""
    report = _report("no_frame")
    finding = _finding(report, "FRAME_NOT_FOUND")
    assert report.frame is None
    assert finding.severity == "attention"
    assert finding.region == Region(0.02, 0.02, 0.96, 0.96)
    assert dict(finding.metrics) == {}


def test_assess_low_contrast_is_reported() -> None:
    """Nén dải xám còn 40 % → `LOW_CONTRAST`; `contrastScore` khớp số đo đã làm tròn."""
    report = _report("low_contrast")
    finding = _finding(report, "LOW_CONTRAST")
    assert dict(finding.metrics) == {"contrastScore": report.measurement.contrast_score}
    assert report.measurement.contrast_score < 0.75


def test_assess_pale_corner_region_is_that_cell() -> None:
    """Chỉ một góc nhạt → vùng `LOW_CONTRAST` là đúng ô góc trên-trái của lưới 4x4."""
    region = _finding(_report("pale_corner"), "LOW_CONTRAST").region
    assert region.x_ratio == pytest.approx(0.0)
    assert region.y_ratio == pytest.approx(0.0)
    assert region.width_ratio == pytest.approx(0.25, abs=0.01)
    assert region.height_ratio == pytest.approx(0.25, abs=0.01)


def test_assess_salt_pepper_is_poor_noise() -> None:
    """Muối tiêu 2 % → `HIGH_NOISE` mức `poor`; `noiseScore` khớp số đo đã làm tròn."""
    report = _report("salt_pepper")
    finding = _finding(report, "HIGH_NOISE")
    assert finding.severity == "poor"
    assert dict(finding.metrics) == {"noiseScore": report.measurement.noise_score}
    assert report.measurement.noise_score > 0.4


def _expected_levels(report: QualityReport) -> dict[str, Level]:
    """Mức mà bốn hàm phân loại cho ra trên chính `measurement` đã làm tròn của báo cáo."""
    m = report.measurement
    return {
        "RESOLUTION_TOO_LOW": classify_resolution(min(m.width_px, m.height_px)),
        "SKEW_DETECTED": classify_skew(m.skew_deg),
        "LOW_CONTRAST": classify_contrast(m.contrast_score),
        "HIGH_NOISE": classify_noise(m.noise_score),
    }


@pytest.mark.parametrize("name", sorted(_IMAGES))
def test_assess_severity_matches_classifiers_on_rounded_measurement(name: str) -> None:
    """Mức mỗi phát hiện = hàm phân loại chạy trên `measurement` đã làm tròn, và ngược lại.

    Chốt điều kiện của khối [6]: BE phân loại trên chính số lên dây, nên `classifyMetric`
    của FE chạy trên cùng số đó ra cùng mức; mã chỉ xuất hiện khi mức khác `good`.
    """
    report = _report(name)
    expected = _expected_levels(report)
    for finding in report.findings:
        if finding.code == "FRAME_NOT_FOUND":
            assert finding.severity == "attention"
            continue
        assert finding.severity == expected[finding.code]
    for code, level in expected.items():
        assert (code in _codes(report)) == (level != "good"), f"{name}: {code} lệch mức {level}"


@pytest.mark.parametrize("name", sorted(_IMAGES))
def test_assess_findings_follow_quality_codes_order(name: str) -> None:
    """Thứ tự phát hiện cố định như `QUALITY_CODES`, mỗi mã tối đa một mục, `level` = tệ nhất."""
    report = _report(name)
    codes = _codes(report)
    assert codes == [c for c in QUALITY_CODES if c in codes]
    assert len(codes) == len(set(codes))
    assert report.level == worst_level([f.severity for f in report.findings])


def test_assess_metrics_mapping_is_read_only() -> None:
    """`Finding.metrics` chỉ đọc: gán vào nó ném `TypeError`, số đo đã chốt không sửa được."""
    finding = _finding(_report("shrunk"), "RESOLUTION_TOO_LOW")
    with pytest.raises(TypeError):
        finding.metrics["shortEdgePx"] = 1.0  # type: ignore[index]  # cố ý gán vào Mapping chỉ đọc để chốt TypeError


def test_measure_matches_assess_measurement() -> None:
    """`measure` trả đúng `Measurement` mà `assess` đặt trong báo cáo (một nguồn số đo)."""
    image = RgbImage(_IMAGES["skew_3_4"])
    assert measure(image) == assess(image).measurement


def test_report_table_of_seven_images() -> None:
    """In bảng số đo, mã và mức của bảy ảnh (khối [8]); chốt mỗi ảnh cho đúng một báo cáo."""
    _LOG.info("%-13s %11s %8s %10s %7s  %s", "ảnh", "kích thước", "nghiêng", "tương phản", "nhiễu", "phát hiện")
    for name in sorted(_IMAGES):
        report = _report(name)
        m = report.measurement
        detail = ", ".join(f"{f.code}={f.severity}" for f in report.findings) or "-"
        _LOG.info(
            "%-13s %5dx%-5d %8.2f %10.3f %7.3f  %s (%s)",
            name,
            m.width_px,
            m.height_px,
            m.skew_deg,
            m.contrast_score,
            m.noise_score,
            detail,
            report.level,
        )
        assert report.measurement.width_px > 0


def test_bbox_region_falls_back_to_whole_image() -> None:
    """`segments_bbox is None` → vùng cả ảnh; nhánh dự phòng này `assess` không tới được.

    Dưới 4 đoạn thì `estimate_skew` trả góc `0.0`, tức mức `good`, tức không sinh
    `SKEW_DETECTED` — nên luật "`None` → cả ảnh" của khối [6] chỉ chốt được bằng cách
    gọi thẳng hàm đổi hộp bao.
    """
    assert _bbox_region(None, 100, 50) == WHOLE_IMAGE
    assert _bbox_region((10.0, 5.0, 60.0, 25.0), 100, 50) == Region(0.1, 0.1, 0.5, 0.4)
