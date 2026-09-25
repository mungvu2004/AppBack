"""Model dây của N5/N6 (B2-02 [2]): thân ghi `ProjectSettingsBodyIn` và response `ProjectSettingsOut`.

Số thập phân **vào** dưới dạng số JSON (bool và chuỗi bị từ chối), đổi qua `Decimal(str(x))` rồi
làm tròn `ROUND_HALF_UP` trước khi kiểm dải; **ra** là `float` (số JSON, không chuỗi, W3).
"""

import math
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, Any, Final, Literal

from pydantic import BeforeValidator, Field, StringConstraints

from apps.api.core.wire import WireModel, WireRequest
from apps.api.project_settings.read import ProjectSettingsValue
from packages.core.text import nfc

BuildingType = Literal["residential", "commercial", "industrial", "mixed", "other"]
LengthUnit = Literal["mm", "m"]

NOTES_MAX: Final = 500
_BIDI: Final = frozenset("‎‏‪‫‬‭‮⁦⁧⁨⁩")
_ALLOWED_CONTROLS: Final = frozenset("\n\t")


def _clean_notes(value: Any) -> Any:
    """Trim + NFC; ký tự điều khiển (trừ xuống dòng và tab) hay định hướng → `ValueError` (422 `field`)."""
    if not isinstance(value, str):
        return value
    text = nfc(value.strip())
    bad = next(
        (ch for ch in text if ch in _BIDI or (unicodedata.category(ch) == "Cc" and ch not in _ALLOWED_CONTROLS)), None
    )
    if bad is not None:
        raise ValueError(f"ghi chú chứa ký tự điều khiển hoặc định hướng U+{ord(bad):04X}")
    return text


def _rounded(places: int) -> BeforeValidator:
    """Bộ kiểm cho số thập phân: chỉ nhận số JSON, làm tròn `places` chữ số `ROUND_HALF_UP`."""
    exponent = Decimal(1).scaleb(-places)

    def convert(value: Any) -> Decimal:
        """`bool`/chuỗi/không hữu hạn → `ValueError`; còn lại `Decimal(str(x))` đã làm tròn."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("phải là số")
        if not math.isfinite(value):
            raise ValueError("phải là số hữu hạn")
        return Decimal(str(value)).quantize(exponent, rounding=ROUND_HALF_UP)

    return BeforeValidator(convert)


type Notes = Annotated[str, BeforeValidator(_clean_notes), StringConstraints(min_length=1, max_length=NOTES_MAX)]
type Confidence = Annotated[Decimal, _rounded(3), Field(ge=0, le=1)]
type ScaleMmPerPx = Annotated[Decimal, _rounded(6), Field(ge=Decimal("0.01"), le=1000)]


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
