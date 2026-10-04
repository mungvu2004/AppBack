"""Model dây của N5/N6 (B2-02 [2]): thân ghi `ProjectSettingsBodyIn` và response `ProjectSettingsOut`.

Số thập phân **vào** dưới dạng số JSON (bool và chuỗi bị từ chối), đổi qua `Decimal(str(x))` rồi
kiểm dải trên số thô rồi làm tròn `ROUND_HALF_UP` (NO-214); **ra** là `float` (số JSON, không chuỗi, W3).
"""

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, BeforeValidator, Field, StringConstraints

from apps.api.core.wire import WireModel, WireRequest
from apps.api.project_settings.read import ProjectSettingsValue
from packages.core.text import clean_text

BuildingType = Literal["residential", "commercial", "industrial", "mixed", "other"]
LengthUnit = Literal["mm", "m"]

NOTES_MAX: Final = 500
_ALLOWED_CONTROLS: Final = "\n\t"


def _clean_notes(value: Any) -> Any:
    """Trim + NFC; ký tự điều khiển (trừ xuống dòng và tab) hay định hướng → `ValueError` (422 `field`)."""
    if not isinstance(value, str):
        return value
    try:
        return clean_text(value, bidi_marks=True, allow_controls=_ALLOWED_CONTROLS)
    except ValueError as exc:
        raise ValueError(f"ghi chú: {exc}") from exc


def _to_decimal(value: Any) -> Decimal:
    """`bool`/chuỗi/không hữu hạn → `ValueError`; còn lại `Decimal(str(x))` chưa làm tròn."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("phải là số")
    if not math.isfinite(value):
        raise ValueError("phải là số hữu hạn")
    return Decimal(str(value))


def _rounded(places: int) -> AfterValidator:
    """Làm tròn `places` chữ số `ROUND_HALF_UP` **sau** khi `Field(ge, le)` đã kiểm số thô (NO-214).

    `-0.0004` thô bị dải chặn 422 thay vì làm tròn ra `-0.000` rồi lọt; `-0.0` thô qua dải
    nhưng được chuẩn hoá thành `0` không dấu để dây và băm (`body_digest`) không phân biệt `-0.000`.
    """
    exponent = Decimal(1).scaleb(-places)

    def quantize(value: Decimal) -> Decimal:
        """Làm tròn về `exponent`; số không có dấu âm → `abs`."""
        rounded = value.quantize(exponent, rounding=ROUND_HALF_UP)
        return abs(rounded) if rounded.is_zero() else rounded

    return AfterValidator(quantize)


type Notes = Annotated[str, BeforeValidator(_clean_notes), StringConstraints(min_length=1, max_length=NOTES_MAX)]
type Confidence = Annotated[Decimal, BeforeValidator(_to_decimal), Field(ge=0, le=1), _rounded(3)]
type ScaleMmPerPx = Annotated[Decimal, BeforeValidator(_to_decimal), Field(ge=Decimal("0.01"), le=1000), _rounded(6)]


class ProjectSettingsBodyIn(WireRequest):
    """Thân của N6: mọi trường bắt buộc trừ `notes` (vắng = xoá ghi chú, đây là PUT thay thế)."""

    building_type: BuildingType
    notes: Notes | None = None
    length_unit: LengthUnit
    snap_tolerance_mm: Annotated[int, Field(strict=True, ge=1, le=120)]
    confidence_threshold: Confidence
    default_scale_mm_per_px: ScaleMmPerPx


class ProjectSettingsWriteIn(WireRequest):
    """`{baseVersion, body}` của N6 (W20) — cùng dạng `versioned(ProjectSettingsBodyIn)` nhưng có kiểu tĩnh.

    Thiếu `baseVersion` bị khung chặn 428 trước Pydantic; khoá lạ trong `body` → 422 `body.<khoá>` (C03).
    """

    base_version: Annotated[int, Field(strict=True, ge=0)]
    body: ProjectSettingsBodyIn


class ProjectSettingsOut(WireModel):
    """Cài đặt đã lưu kèm `revision`; `notes` NULL → vắng (W2)."""

    revision: int
    building_type: str
    notes: str | None = None
    length_unit: str
    snap_tolerance_mm: int
    confidence_threshold: float
    default_scale_mm_per_px: float

    @classmethod
    def of(cls, value: ProjectSettingsValue) -> "ProjectSettingsOut":
        """Dựng response từ giá trị đọc được; `Decimal` → `float` (số JSON)."""
        return cls(
            revision=value.revision,
            building_type=value.building_type,
            notes=value.notes,
            length_unit=value.length_unit,
            snap_tolerance_mm=value.snap_tolerance_mm,
            confidence_threshold=float(value.confidence_threshold),
            default_scale_mm_per_px=float(value.default_scale_mm_per_px),
        )
