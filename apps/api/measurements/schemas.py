"""Model dây của phép đo (B2-07 [2], [6] "Số"); khớp `MeasurementRecordSchema` strict của FE.

Request kế thừa `WireRequest` (khoá lạ ở mọi độ sâu → 422). Response không có `body_sha256`,
`createdBy`, `updatedAt` (K01) và `z` vắng thì vắng khoá (W2, K02).
"""

from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, Field, ValidationInfo, field_validator, model_validator

from apps.api.core.wire import WireModel, WireRequest
from apps.api.measurements.settings import get_measurements_settings
from apps.api.measurements.text import Label
from packages.core.ids import is_measurement_id

type MeasurementMode = Literal["pointToPoint", "perpendicular", "height", "floorArea"]

Real = Annotated[float, Field(strict=True, allow_inf_nan=False)]
"""Số thực hữu hạn: nhận `1000` nguyên mà FE gửi, từ chối `bool`, chuỗi, `NaN`, `Infinity` (W3)."""

FLOOR_AREA_MIN_POINTS: Final = 3
OTHER_MIN_POINTS: Final = 2


def _check_measurement_id(value: str) -> str:
    """Id đúng `^MS-[0-9]{4,15}$`; 16 chữ số trở lên làm hỏng bộ sinh id của FE."""
    if not is_measurement_id(value):
        raise ValueError("id phải có dạng MS-<4 đến 15 chữ số>")
    return value


class NullFreeModel(WireModel):
    """Model lồng vừa vào vừa ra: khoá tuỳ chọn thì **vắng**, không nhận `null` (FE `.optional()`).

    `WireModel` đã bỏ `None` khi ra; thêm cổng vào để `{"z": null}` là 422 thay vì lặng lẽ
    bị coi như vắng.
    """

    @model_validator(mode="before")
    @classmethod
    def _reject_null(cls, data: Any) -> Any:
        """Khoá nào mang `null` → `ValueError` nêu tên khoá."""
        if isinstance(data, dict):
            nulls = sorted(str(key) for key, value in data.items() if value is None)
            if nulls:
                raise ValueError(f"không nhận null: {', '.join(nulls)}")
        return data


class MeasurementPoint(NullFreeModel):
    """Một điểm đã chấm; `z` vắng nghĩa là điểm trên cốt nền, không phải `z: 0`."""

    x: Real
    y: Real
    z: Real | None = None


class MeasurementRecordIn(WireRequest):
    """Thân #17: nguyên bản ghi do client sinh (POST không có `Idempotency-Key`)."""

    id: Annotated[str, AfterValidator(_check_measurement_id)]
    name: Label
    mode: MeasurementMode
    points: list[MeasurementPoint]
    raw_value_mm: Annotated[Real, Field(ge=0)]

    @field_validator("points")
    @classmethod
    def _check_point_count(cls, points: list[MeasurementPoint], info: ValidationInfo) -> list[MeasurementPoint]:
        """`floorArea` ≥ 3 điểm, chế độ khác ≥ 2, tối đa `MEASUREMENT_POINTS_MAX` (đọc lười lúc chạy)."""
        low = FLOOR_AREA_MIN_POINTS if info.data.get("mode") == "floorArea" else OTHER_MIN_POINTS
        high = get_measurements_settings().measurement_points_max
        if not low <= len(points) <= high:
            raise ValueError(f"points phải {low}-{high} điểm")
        return points


class MeasurementRecord(WireModel):
    """Bản ghi phép đo trả về (#16, #17)."""

    id: str
    name: str
    mode: MeasurementMode
    points: list[MeasurementPoint]
    raw_value_mm: float
