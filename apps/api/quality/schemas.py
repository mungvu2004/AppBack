"""Model trên dây của #30-#32 (B2-05b [2]): `ImageQualityAssessment` của FE và hai thân ghi.

Response dùng `WireModel` nên trường tuỳ chọn `None` **vắng** khỏi JSON, không thành `null`
(W2, K02). `expectedConfidence` không khai: v1 không có mô hình dự báo, FE coi nó tuỳ chọn.

Kiểm lồi, thứ tự và diện tích của bốn góc **không** ở đây: chúng cần cấu hình
(`QUALITY_MIN_QUAD_AREA`) nên thuộc `geometry.validate_corner_ratios`.
"""

from typing import Literal

from pydantic import Field

from apps.api.core.wire import WireModel, WireRequest

Ratio = Field(ge=0, le=1)
"""Tỉ lệ 0..1 của khung ảnh — cùng miền `ratioSchema` của FE (`quality.ts:43`)."""


class CornerOut(WireModel):
    """Một điểm của khung bản vẽ, tỉ lệ của ảnh ở `sourceUrl`."""

    x_ratio: float = Ratio
    y_ratio: float = Ratio


class RegionOut(WireModel):
    """Vùng một phát hiện neo vào (`quality.ts:84`)."""

    x_ratio: float = Ratio
    y_ratio: float = Ratio
    width_ratio: float = Ratio
    height_ratio: float = Ratio


class FindingOut(WireModel):
    """Một phát hiện; `id` ổn định giữa các lượt đọc cùng trang ([2] "finding.id")."""

    id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    severity: Literal["good", "attention", "poor"]
    region: RegionOut


class MeasurementOut(WireModel):
    """Bốn số đo thô (`quality.ts:115`)."""

    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)
    skew_deg: float
    contrast_score: float = Ratio
    noise_score: float = Ratio


class FrameOut(WireModel):
    """Khung bản vẽ: `corners` chỉ khi tìm thấy và chưa được áp vào trang."""

    is_found: bool
    corners: list[CornerOut] | None = Field(default=None, min_length=4, max_length=4)


class FloorQualityOut(WireModel):
    """Kết quả của một tầng có bản vẽ; `measurement`, `frame` chỉ có khi `is_measured`."""

    floor_id: str = Field(min_length=1)
    floor_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    is_measured: bool
    findings: list[FindingOut]
    measurement: MeasurementOut | None = None
    frame: FrameOut | None = None


class QualityAssessmentOut(WireModel):
    """Cả dự án một lượt: `floor_id` luôn thuộc `floors`, `floors` ≥ 1 phần tử."""

    project_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    floors: list[FloorQualityOut] = Field(min_length=1)


class CornerIn(WireRequest):
    """Một góc người dùng chọn (`DrawingCornersInputSchema`)."""

    x_ratio: float = Ratio
    y_ratio: float = Ratio


class SetCornersIn(WireRequest):
    """Thân #31: đúng bốn góc; thứ tự và hình học do `geometry` kiểm."""

    corners: list[CornerIn] = Field(min_length=4, max_length=4)


class StraightenIn(WireRequest):
    """Thân #32: object rỗng; khoá lạ bị `extra="forbid"` chặn (422)."""
