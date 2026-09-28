"""Model dây của khuôn thuộc tính (B2-07 [2]); khớp `PropertyTemplateSchema` strict của FE.

Bốn nhánh theo `objectKind`, mỗi nhánh một `fields` strict với **mọi khoá tuỳ chọn** (vắng
vẫn vắng, không `null`). Enum đúng `src/domain/spatial/types.ts`; mm là số nguyên (W3, K20).
"""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from apps.api.measurements.schemas import NullFreeModel, Real
from apps.api.measurements.text import Label

PositiveMm = Annotated[int, Field(strict=True, gt=0)]
NonNegativeMm = Annotated[int, Field(strict=True, ge=0)]
Degrees = Annotated[Real, Field(ge=0, lt=360)]


class WallFields(NullFreeModel):
    """`fields` của tường."""

    height_mm: PositiveMm | None = None
    thickness_mm: PositiveMm | None = None
    kind: Literal["loadBearing", "partition", "envelope"] | None = None


class OpeningFields(NullFreeModel):
    """`fields` của ô mở (cửa, cửa sổ)."""

    height_mm: PositiveMm | None = None
    width_mm: PositiveMm | None = None
    sill_height_mm: NonNegativeMm | None = None
    swing: Literal["left", "right", "double", "sliding", "fixed"] | None = None


class RoomFields(NullFreeModel):
    """`fields` của phòng; không có tên vì mỗi phòng cần tên riêng."""

    usage: (
        Literal["livingRoom", "bedroom", "kitchen", "bathroom", "corridor", "stairwell", "utility", "other"] | None
    ) = None


class FurnitureFields(NullFreeModel):
    """`fields` của đồ nội thất; không có hộp bao vì nó gắn với một chỗ đặt cụ thể."""

    kind: Literal["table", "chair", "bed", "wardrobe", "kitchenCabinet", "sanitaryFixture", "stair", "other"] | None = (
        None
    )
    rotation_deg: Degrees | None = None


class WallDraft(WireRequest):
    """Thân #29 nhánh tường."""

    object_kind: Literal["wall"]
    name: Label
    fields: WallFields


class OpeningDraft(WireRequest):
    """Thân #29 nhánh ô mở."""

    object_kind: Literal["opening"]
    name: Label
    fields: OpeningFields


class RoomDraft(WireRequest):
    """Thân #29 nhánh phòng."""

    object_kind: Literal["room"]
    name: Label
    fields: RoomFields


class FurnitureDraft(WireRequest):
    """Thân #29 nhánh nội thất."""

    object_kind: Literal["furniture"]
    name: Label
    fields: FurnitureFields


PropertyTemplateDraft = Annotated[
    WallDraft | OpeningDraft | RoomDraft | FurnitureDraft, Field(discriminator="object_kind")
]


class _TemplateOut(WireModel):
    """Năm khoá chung của mọi nhánh ra; `scope` là hằng `project` (không có cột)."""

    id: str
    name: str
    project_id: str
    created_at: WireDatetime
    scope: Literal["project"] = "project"


class WallTemplate(_TemplateOut):
    """Khuôn tường."""

    object_kind: Literal["wall"]
    fields: WallFields


class OpeningTemplate(_TemplateOut):
    """Khuôn ô mở."""

    object_kind: Literal["opening"]
    fields: OpeningFields


class RoomTemplate(_TemplateOut):
    """Khuôn phòng."""

    object_kind: Literal["room"]
    fields: RoomFields


class FurnitureTemplate(_TemplateOut):
    """Khuôn nội thất."""

    object_kind: Literal["furniture"]
    fields: FurnitureFields


PropertyTemplate = Annotated[
    WallTemplate | OpeningTemplate | RoomTemplate | FurnitureTemplate, Field(discriminator="object_kind")
]

TEMPLATE_ADAPTER: TypeAdapter[PropertyTemplate] = TypeAdapter(PropertyTemplate)
"""Dựng nhánh ra đúng theo `objectKind` của dòng đã lưu."""
