"""Artifact của ba bước suy luận: JSON theo pixel của trang đã nắn, PNG mặt nạ tường.

Artifact nằm dưới `…/runs/{run}/{step}/` và đi qua ranh giới không tin (worker `ml` →
`pipeline.cpu`, BE-00 §7), nên mọi trường có trần: số hữu hạn, toạ độ trong
`[0, COORD_MAX_PX]`, số mục có trần, khoá lạ ở mọi cấp bị từ chối, và bộ giải JSON
từ chối thân quá `ARTIFACT_JSON_MAX_BYTES` **trước** khi parse. Đầu ra AI hợp trần mà
xấu (hộp ngoài tường, trùng) không phải việc của module này (BE-00 §9).
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.ml_contracts._png import (
    MASK_MAX_PIXELS,
    PngHeader,
    decode_mask,
    encode_mask,
    encode_rgb_png,
    read_png_header,
)
from packages.ml_contracts.families import ModelFamily
from packages.ml_contracts.labels import DetectionLabel

__all__ = [
    "ARTIFACT_JSON_MAX_BYTES",
    "COORD_MAX_PX",
    "MASK_MAX_PIXELS",
    "STEP_ARTIFACTS",
    "BoxPx",
    "DetectionPx",
    "FrozenModel",
    "ObjectsResult",
    "PngHeader",
    "PointPx",
    "TextPx",
    "TextResult",
    "WallPx",
    "WallsResult",
    "decode_mask",
    "encode_mask",
    "encode_rgb_png",
    "objects_from_json",
    "objects_to_json",
    "read_png_header",
    "text_from_json",
    "text_to_json",
    "walls_from_json",
    "walls_to_json",
]

COORD_MAX_PX: Final = 100_000
ARTIFACT_JSON_MAX_BYTES: Final = 16 * 1024 * 1024
MAX_WALLS: Final = 20_000
MAX_DETECTIONS: Final = 5_000
MAX_TEXTS: Final = 5_000

STEP_ARTIFACTS: Final[Mapping[ModelFamily, tuple[str, ...]]] = MappingProxyType(
    {
        "wallSegmentation": ("walls.json", "walls.png"),
        "openingAndFurnitureDetection": ("objects.json",),
        "dimensionReading": ("text.json",),
    }
)
"""Tên artifact mỗi bước được ghi (tên tương đối, người gọi ghép `artifact_prefix`)."""

Coordinate = Annotated[float, Field(ge=0, le=COORD_MAX_PX, allow_inf_nan=False)]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FrozenModel(BaseModel):
    """Gốc mọi model của gói (artifact, payload, dataset): bất biến, khoá lạ bị từ chối ở mọi cấp lồng."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class PointPx(FrozenModel):
    """Một điểm trên trang, đơn vị pixel (mép điểm ảnh, không phải tâm)."""

    x: Coordinate
    y: Coordinate


class BoxPx(FrozenModel):
    """Hộp thẳng trục, `min < max` ở cả hai chiều (hộp rỗng không phải phát hiện)."""

    x_min: Coordinate
    y_min: Coordinate
    x_max: Coordinate
    y_max: Coordinate

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        """Hộp suy biến hay lật ngược là đầu ra sai hợp đồng, không phải đầu ra xấu."""
        if not (self.x_min < self.x_max and self.y_min < self.y_max):
            raise ValueError("hộp phải có min < max ở cả hai chiều")
        return self


class WallPx(FrozenModel):
    """Đường tim một tường; hai đầu khác nhau, bề dày dương."""

    start: PointPx
    end: PointPx
    thickness_px: Annotated[float, Field(gt=0, le=COORD_MAX_PX, allow_inf_nan=False)]
    confidence: Confidence

    @model_validator(mode="after")
    def _not_a_point(self) -> Self:
        """Tường một điểm không có hướng, bước dựng tầng không dùng được."""
        if self.start == self.end:
            raise ValueError("đầu và cuối tường trùng nhau")
        return self


class DetectionPx(FrozenModel):
    """Một ô mở hay đồ đạc phát hiện được."""

    label: DetectionLabel
    box: BoxPx
    confidence: Confidence


class TextPx(FrozenModel):
    """Một chuỗi đọc được (kích thước, nhãn phòng) và hộp của nó."""

    text: Annotated[str, Field(min_length=1, max_length=64)]
    box: BoxPx
    confidence: Confidence


class WallsResult(FrozenModel):
    """`walls.json` của bước `wallSegmentation`."""

    schema_version: Literal[1] = 1
    walls: Annotated[tuple[WallPx, ...], Field(max_length=MAX_WALLS)]


class ObjectsResult(FrozenModel):
    """`objects.json` của bước `openingAndFurnitureDetection`."""

    schema_version: Literal[1] = 1
    detections: Annotated[tuple[DetectionPx, ...], Field(max_length=MAX_DETECTIONS)]


class TextResult(FrozenModel):
    """`text.json` của bước `dimensionReading`."""

    schema_version: Literal[1] = 1
    items: Annotated[tuple[TextPx, ...], Field(max_length=MAX_TEXTS)]


def _checked(data: bytes) -> bytes:
    """Trần byte **trước** khi parse: JSON khổng lồ không được cấp bộ nhớ cho cây đối tượng."""
    if len(data) > ARTIFACT_JSON_MAX_BYTES:
        raise ValueError(f"artifact JSON dài {len(data)} byte, trần {ARTIFACT_JSON_MAX_BYTES}")
    return data


def walls_to_json(result: WallsResult) -> bytes:
    """`walls.json` gọn (không khoảng trắng)."""
    return result.model_dump_json().encode()


def walls_from_json(data: bytes) -> WallsResult:
    """Giải `walls.json`; sai hợp đồng → `ValueError` (`ValidationError` là lớp con)."""
    return WallsResult.model_validate_json(_checked(data))


def objects_to_json(result: ObjectsResult) -> bytes:
    """`objects.json` gọn."""
    return result.model_dump_json().encode()


def objects_from_json(data: bytes) -> ObjectsResult:
    """Giải `objects.json`; sai hợp đồng → `ValueError`."""
    return ObjectsResult.model_validate_json(_checked(data))


def text_to_json(result: TextResult) -> bytes:
    """`text.json` gọn."""
    return result.model_dump_json().encode()


def text_from_json(data: bytes) -> TextResult:
    """Giải `text.json`; sai hợp đồng → `ValueError`."""
    return TextResult.model_validate_json(_checked(data))
