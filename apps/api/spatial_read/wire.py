"""Model **response** của #33, N15, N16 — một lớp cho mỗi schema FE (B3-02 [2]).

Soi gương `S:api/schemas/spatial.ts`, `spatialGraph.ts`, `spatialLayer.ts` ở commit ghim
và HOP-DONG-MOI §4.1. Ba luật hay quên:

- **m² và tỉ lệ là `float`, không `Decimal`** (K01): zod khai `z.number()`, còn Pydantic in
  `Decimal` ra **chuỗi** JSON. Cột `numeric` phải đổi kiểu ở đúng biên này;
- **trường tuỳ chọn vắng khoá, không `null`** (W2, K02): `WireModel` tự bỏ `None`, nên mọi
  trường tuỳ chọn khai `| None = None` chứ không `KeepNull`;
- **mm là số nguyên** (B3-01 `Mm`): `int`, không `float` — `12.5` trên dây là dấu hiệu ai đó
  nhân tỉ lệ mà quên làm tròn.

Mô hình miền B3-01 đã dump ra đúng hình dạng dây (`by_alias`, `exclude_none`), nên
`layer_out`/`dimensions_out` chỉ `model_validate` lại: một lượt kiểm thật sự chứ không phải
phép chép trường bằng tay, và một trường thêm vào miền mà quên khai ở đây sẽ đỏ ngay.

Module này nằm trong nhóm được nhập `fastapi` (B3-02 [2]: trừ `router`, `graph`, `wire`,
`cli`) nhưng thực tế không cần — nó chỉ nhập `apps.api.core.wire`.
"""

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field

from apps.api.core.wire import WireDatetime, WireModel
from packages.domain.spatial import Dimension, SpatialLayer

Millimetres = int
"""Mọi toạ độ và kích thước hình học là **số nguyên** milimét (`S:domain/spatial/types.ts`)."""

SquareMetres = Annotated[float, Field(ge=0)]
"""Diện tích trên dây là `z.number().nonnegative()`; `Decimal` của DB đổi sang `float` ở biên."""


class _ReviewedOut(WireModel):
    """Ba trường duyệt mà mọi thực thể mang (`reviewMetadataShape`, HOP-DONG-MOI §4.1).

    Không kiểm A5 (`source='ai'` + `reviewed=True`) ở đây: luật ấy do B3-01 giữ lúc
    `model_validate` tài liệu, và lặp lại phép kiểm ở lớp dây sẽ thành hai nguồn luật.
    """

    confidence: Annotated[float, Field(ge=0, le=1)]
    source: Literal["ai", "human"]
    reviewed: bool


class PointOut(WireModel):
    """Một điểm trên mặt bằng, mm nguyên."""

    x: Millimetres
    y: Millimetres


class SegmentOut(WireModel):
    """Đoạn thẳng hai đầu; `segmentSchema` của FE chặn đoạn dài 0 mm."""

    start: PointOut
    end: PointOut


class BoundingBoxOut(WireModel):
    """Hộp bao của một món đồ đạc."""

    min: PointOut
    max: PointOut


class WallOut(_ReviewedOut):
    """`WallSchema` — một đoạn tường đo theo đường tim."""

    id: str
    level_id: str
    centreline: SegmentOut
    thickness_mm: Millimetres
    height_mm: Millimetres
    kind: Literal["loadBearing", "partition", "envelope"]
    opening_ids: list[str]


class OpeningOut(_ReviewedOut):
    """`OpeningSchema` — cửa đi hay cửa sổ khoét trong một tường."""

    id: str
    wall_id: str
    kind: Literal["door", "window"]
    offset_mm: Millimetres
    width_mm: Millimetres
    height_mm: Millimetres
    sill_height_mm: Millimetres
    swing: Literal["left", "right", "double", "sliding", "fixed"]


class RoomOut(_ReviewedOut):
    """`RoomSchema` — phòng khép kín; `areaM2` do server tính từ `outline` (W18)."""

    id: str
    level_id: str
    name: str
    usage: Literal["livingRoom", "bedroom", "kitchen", "bathroom", "corridor", "stairwell", "utility", "other"]
    outline: Annotated[list[PointOut], Field(min_length=3)]
    area_m2: SquareMetres
    wall_ids: list[str]


class FurnitureOut(_ReviewedOut):
    """`FurnitureSchema` — `roomId` **vắng khoá** khi món đồ chưa gắn phòng (C17)."""

    id: str
    level_id: str
    room_id: str | None = None
    kind: Literal["table", "chair", "bed", "wardrobe", "kitchenCabinet", "sanitaryFixture", "stair", "other"]
    centre: PointOut
    bounding_box: BoundingBoxOut
    rotation_deg: Annotated[float, Field(ge=0, lt=360)]


class LevelOut(_ReviewedOut):
    """`LevelSchema` — một tầng; `id` là `Floor.id` của #12/#33, không phải một mã thứ hai.

    Tầng chưa hiệu chỉnh vắng `scaleMillimetresPerPixel`; tỉ lệ "tạm" vẫn gửi nhưng N16 kèm
    `scaleStatus: 'unresolved'` (HOP-DONG-MOI §4.2).
    """

    id: str
    name: str
    order: int
    elevation_mm: Millimetres
    height_mm: Millimetres
    area_m2: SquareMetres | None = None
    scale_millimetres_per_pixel: Annotated[float, Field(gt=0)] | None = None


class BuildingOut(_ReviewedOut):
    """`BuildingSchema` — `datumElevationMm` **có dấu** (tầng hầm nằm dưới mốc `+0.000`)."""

    name: str
    address: str | None = None
    datum_elevation_mm: Millimetres
    gross_floor_area_m2: SquareMetres | None = None


class AxisOut(_ReviewedOut):
    """`AxisSchema` — trục định vị; v1 danh sách luôn rỗng nhưng hình dạng vẫn phải đúng."""

    id: str
    level_id: str
    label: str
    direction: Literal["horizontal", "vertical"]
    line: SegmentOut


class DimensionOut(_ReviewedOut):
    """`DimensionSchema` — chuỗi kích thước; `referenceIds` **được rỗng**."""

    id: str
    level_id: str
    kind: Literal["linear", "chain", "radial", "angular", "elevation"]
    reference_ids: list[str]
    line: SegmentOut
    value_mm: Millimetres
    override_value_mm: Millimetres | None = None


class NoteOut(_ReviewedOut):
    """`NoteSchema` — ghi chú gắn vào một thực thể; v1 `notes` luôn rỗng ở N15."""

    id: str
    entity_id: str
    body: str
    created_at: WireDatetime
    author_id: str


class SpatialLayerOut(WireModel):
    """`SpatialLayerSchema` — bốn danh sách của **một** tầng."""

    walls: list[WallOut]
    openings: list[OpeningOut]
    rooms: list[RoomOut]
    furniture: list[FurnitureOut]


class SpatialGraphOut(WireModel):
    """`SpatialGraphSchema` — cả công trình; v1 `axes: []`, `notes: []`."""

    building: BuildingOut
    levels: list[LevelOut]
    walls: list[WallOut]
    openings: list[OpeningOut]
    furniture: list[FurnitureOut]
    rooms: list[RoomOut]
    axes: list[AxisOut]
    dimensions: list[DimensionOut]
    notes: list[NoteOut]


class FloorRevisionOut(WireModel):
    """`FloorRevisionSchema` — đủ để mở một lượt `PUT` có version lên đúng tầng ấy (#35)."""

    floor_id: str
    revision: Annotated[int, Field(ge=0)]


class SpatialGraphDocumentOut(WireModel):
    """N15 — đồ thị cộng bảng `revision`; zod refine hai danh sách là **song ánh**."""

    graph: SpatialGraphOut
    floor_revisions: list[FloorRevisionOut]


class FloorLayerDocumentOut(WireModel):
    """N16 — lớp của một tầng; `scaleStatus` vắng khi tỉ lệ do người đặt hay chưa có (W24)."""

    revision: Annotated[int, Field(ge=0)]
    level: LevelOut
    scale_status: Literal["unresolved"] | None = None
    layer: SpatialLayerOut
    axes: list[AxisOut]
    dimensions: list[DimensionOut]


def layer_out(layer: SpatialLayer) -> SpatialLayerOut:
    """Lớp miền → lớp dây, đi qua `model_validate` để lệch trường nào là đỏ ngay chỗ này."""
    return SpatialLayerOut.model_validate(layer.model_dump(mode="json", by_alias=True, exclude_none=True))


def dimensions_out(dimensions: Sequence[Dimension]) -> list[DimensionOut]:
    """Kích thước miền → dây, cùng đường kiểm với `layer_out`."""
    return [
        DimensionOut.model_validate(dimension.model_dump(mode="json", by_alias=True, exclude_none=True))
        for dimension in dimensions
    ]
