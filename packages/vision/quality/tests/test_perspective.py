"""G3-35: méo hình thang và "không đo được" không còn bị xếp "Tốt" (ảnh tổng hợp numpy/OpenCV)."""

import cv2
import numpy as np
from numpy.typing import NDArray

from packages.vision.preprocess.geometry import estimate_skew, working_gray
from packages.vision.preprocess.types import RgbImage
from packages.vision.quality import assess
from packages.vision.quality.thresholds import classify_perspective

_W, _H = 1600, 1200
_WHITE = (255, 255, 255)


def _plan() -> NDArray[np.uint8]:
    """Bản vẽ thẳng: khung chữ nhật + vài tường dọc/ngang, nét đen trên nền trắng."""
    img = np.full((_H, _W, 3), 255, dtype=np.uint8)
    cv2.rectangle(img, (150, 150), (_W - 150, _H - 150), (0, 0, 0), 5)
    for x in (500, 800, 1100):
        cv2.line(img, (x, 150), (x, _H - 150), (0, 0, 0), 4)
    for y in (450, 750):
        cv2.line(img, (150, y), (_W - 150, y), (0, 0, 0), 4)
    return img


def _rotated(angle_deg: float) -> NDArray[np.uint8]:
    """Bản vẽ xoay đều `angle_deg` quanh tâm, nền trắng."""
    matrix = cv2.getRotationMatrix2D((_W / 2, _H / 2), angle_deg, 1.0)
    return np.asarray(cv2.warpAffine(_plan(), matrix, (_W, _H), borderValue=_WHITE), dtype=np.uint8)


def _trapezoid(inset_px: float) -> NDArray[np.uint8]:
    """Bản vẽ méo hình thang: mép trên co vào `inset_px` mỗi bên (ảnh chụp chếch)."""
    src = np.array([(0, 0), (_W, 0), (_W, _H), (0, _H)], dtype=np.float32)
    dst = np.array([(inset_px, 0), (_W - inset_px, 0), (_W, _H), (0, _H)], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    return np.asarray(cv2.warpPerspective(_plan(), matrix, (_W, _H), borderValue=_WHITE), dtype=np.uint8)


def _codes(pixels: NDArray[np.uint8]) -> list[str]:
    """Mã phát hiện của `assess` trên ảnh đã cho."""
    return [finding.code for finding in assess(RgbImage(pixels)).findings]


def test_straight_plan_is_measured_and_not_perspective() -> None:
    """Thẳng: đo được, hội tụ ≈ 0, không mã nghiêng/phối cảnh/không đo được."""
    estimate = estimate_skew(working_gray(RgbImage(_plan())))
    assert estimate.is_measured
    assert estimate.perspective_deg is not None
    assert estimate.perspective_deg <= 1.0
    codes = _codes(_plan())
    assert not {"SKEW_DETECTED", "SKEW_NOT_MEASURED", "PERSPECTIVE_DETECTED"} & set(codes)


def test_rotated_plan_is_skew_not_perspective() -> None:
    """Xoay 3°: báo nghiêng ≈ 3°, mọi đoạn nghiêng cùng góc nên không báo phối cảnh."""
    estimate = estimate_skew(working_gray(RgbImage(_rotated(3.0))))
    assert abs(abs(estimate.angle_deg) - 3.0) < 0.3
    assert estimate.perspective_deg is not None
    assert estimate.perspective_deg <= 1.0
    codes = _codes(_rotated(3.0))
    assert "SKEW_DETECTED" in codes
    assert "PERSPECTIVE_DETECTED" not in codes


def test_trapezoid_plan_reports_perspective_despite_zero_skew() -> None:
    """Hình thang: trung vị góc ≈ 0° (mép ±θ triệt nhau) nhưng báo `PERSPECTIVE_DETECTED`, mức khác `good`."""
    pixels = _trapezoid(90.0)
    estimate = estimate_skew(working_gray(RgbImage(pixels)))
    assert abs(estimate.angle_deg) <= 0.5
    assert estimate.perspective_deg is not None
    assert estimate.perspective_deg > 2.0
    report = assess(RgbImage(pixels))
    finding = next(f for f in report.findings if f.code == "PERSPECTIVE_DETECTED")
    assert finding.severity in {"attention", "poor"}
    assert finding.metrics["perspectiveDeg"] > 2.0
    assert report.level != "good"


def test_blank_page_is_not_measured_not_good() -> None:
    """Thiếu dữ liệu (trang trắng): `is_measured` sai, phát `SKEW_NOT_MEASURED`, mức khác `good`."""
    pixels = np.full((_H, _W, 3), 255, dtype=np.uint8)
    estimate = estimate_skew(working_gray(RgbImage(pixels)))
    assert not estimate.is_measured
    assert estimate.perspective_deg is None
    report = assess(RgbImage(pixels))
    assert "SKEW_NOT_MEASURED" in [f.code for f in report.findings]
    assert "PERSPECTIVE_DETECTED" not in [f.code for f in report.findings]
    assert report.level != "good"


def test_classify_perspective_boundaries() -> None:
    """`None` và ≤ 1° → good; (1, 5) → attention; ≥ 5 → poor."""
    assert classify_perspective(None) == "good"
    assert classify_perspective(1.0) == "good"
    assert classify_perspective(1.01) == "attention"
    assert classify_perspective(4.99) == "attention"
    assert classify_perspective(5.0) == "poor"
