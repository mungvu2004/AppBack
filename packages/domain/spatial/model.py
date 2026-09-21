"""Mô hình đồ thị không gian: gương `src/domain/spatial/types.ts` và ràng buộc zod `src/api/schemas/spatial.ts`.

Mọi thứ BE dựng từ các lớp này phải giải mã được ở FE (W1, W3, W4). Xuất dây bằng
`model_dump(mode="json", by_alias=True, exclude_none=True)`: trường tuỳ chọn vắng
thì vắng khoá, không bao giờ `null` (W2, K02).

A5 (`source="ai"` kèm `reviewed=True`) **không** kiểm ở đây: B3-03 cần trả
`REVIEW_BY_AI_FORBIDDEN` thay cho `VALIDATION`, nên dùng `kinds.ai_reviewed_ids`.
"""

import unicodedata
from typing import Annotated, Final, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    model_validator,
)
from pydantic.alias_generators import to_camel

from packages.core.ids import SPATIAL_PREFIX, SpatialKind, is_spatial_id
from packages.core.instants import parse_wire
from packages.core.text import nfc

MAX_SAFE_INTEGER: Final = 2**53 - 1
"""`Number.MAX_SAFE_INTEGER`: FE cộng số nguyên bằng số thực chính xác tới đây."""

# Ký tự đảo chiều hiển thị (U+202A-U+202E, U+2066-U+2069): đổi thứ tự chữ trên màn
# mà không đổi byte, nên tên phòng có thể hiện khác cái đã lưu.
_BIDI_CONTROLS: Final = frozenset(map(chr, (*range(0x202A, 0x202F), *range(0x2066, 0x206A))))


class DomainModel(BaseModel):
    """Gốc của mọi mô hình miền: bất biến, cấm khoá lạ (W1), khoá dây camelCase.

    Không bật `strict` toàn cục: jsonb đọc ra `list`, còn strict từ chối `list` cho
    trường `tuple`. Kiểu chặt đặt theo từng trường (`Mm`, `StrictBool`…).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", alias_generator=to_camel, populate_by_name=True)


def _spatial_id(kind: SpatialKind | None) -> AfterValidator:
    """Kiểm id W4 bằng `is_spatial_id` của lõi: đúng `kind`, hoặc loại bất kỳ khi `kind` là `None`."""
    kinds = tuple(SPATIAL_PREFIX) if kind is None else (kind,)

    def check(value: str) -> str:
        """Trả nguyên id khi đạt mẫu, không thì `ValueError` (pydantic gói thành lỗi của trường)."""
        if not any(is_spatial_id(candidate, value) for candidate in kinds):
            raise ValueError(f"id không đúng mẫu W4 của {kind or 'thực thể không gian'}")
        return value

    return AfterValidator(check)


def _human_text(value: str) -> str:
    """Chuỗi người nhập (BE-00 §6): lưu NFC, không rỗng, không ký tự điều khiển hay đảo chiều."""
    text = nfc(value)
    if not text:
        raise ValueError("chuỗi rỗng")
    if any(unicodedata.category(char) == "Cc" or char in _BIDI_CONTROLS for char in text):
        raise ValueError("chuỗi chứa ký tự điều khiển hoặc ký tự đảo chiều")
    return text


def _wire_instant(value: str) -> str:
    """Ngày giờ dây W3 (`.sssZ`), kiểm bằng `parse_wire` nhưng giữ nguyên chuỗi."""
    parse_wire(value)
    return value


SafeInt = Annotated[StrictInt, Field(ge=-MAX_SAFE_INTEGER, le=MAX_SAFE_INTEGER)]
Mm = SafeInt
"""Độ dài mm nguyên (W3, K20): `1.5`, `True`, `"12"` đều hỏng."""
PositiveMm = Annotated[Mm, Field(gt=0)]
NonNegativeMm = Annotated[Mm, Field(ge=0)]
SquareMetres = Annotated[StrictFloat, Field(ge=0, allow_inf_nan=False)]
"""`float`, không `Decimal`: `mode="json"` xuất `Decimal` thành chuỗi, `z.number()` hỏng cả lớp."""
Confidence = Annotated[StrictFloat, Field(ge=0, le=1, allow_inf_nan=False)]
Degrees = Annotated[StrictFloat, Field(ge=0, lt=360, allow_inf_nan=False)]
HumanText = Annotated[StrictStr, AfterValidator(_human_text)]
NonEmptyStr = Annotated[StrictStr, Field(min_length=1)]
WireInstant = Annotated[StrictStr, AfterValidator(_wire_instant)]
EntityIdStr = Annotated[StrictStr, _spatial_id(None)]
LevelIdStr = Annotated[StrictStr, _spatial_id("level")]
WallIdStr = Annotated[StrictStr, _spatial_id("wall")]
OpeningIdStr = Annotated[StrictStr, _spatial_id("opening")]
FurnitureIdStr = Annotated[StrictStr, _spatial_id("furniture")]
RoomIdStr = Annotated[StrictStr, _spatial_id("room")]
AxisIdStr = Annotated[StrictStr, _spatial_id("axis")]
DimensionIdStr = Annotated[StrictStr, _spatial_id("dimension")]


class Reviewed(DomainModel):
    """Ba trường duyệt mọi thực thể mang (`ReviewMetadata`); `reviewed=True` chỉ do người đặt (A5)."""

    confidence: Confidence
    source: Literal["ai", "human"]
    reviewed: StrictBool


class Point(DomainModel):
    """Điểm trên mặt bằng, mm."""

    x: Mm
    y: Mm


class Segment(DomainModel):
    """Đoạn thẳng thật sự có chiều dài: `start` trùng `end` là tường không tồn tại."""

    start: Point
    end: Point

    @model_validator(mode="after")
    def _has_length(self) -> Self:
        """Hai đầu phải khác nhau."""
        if self.start == self.end:
            raise ValueError("đoạn thẳng dài 0")
        return self


class BoundingBox(DomainModel):
    """Hộp bao đúng chiều: `max` không nhỏ hơn `min` trên cả hai trục."""

    min: Point
    max: Point

    @model_validator(mode="after")
    def _not_inverted(self) -> Self:
        """`max ≥ min` trên cả hai trục; hộp suy biến thành một điểm vẫn đạt."""
        if self.max.x < self.min.x or self.max.y < self.min.y:
            raise ValueError("hộp bao lộn ngược")
        return self


class Building(Reviewed):
    """Công trình; `datumElevationMm` có dấu (tầng hầm nằm dưới mốc)."""

    name: HumanText
    address: HumanText | None = None
    datum_elevation_mm: Mm
    gross_floor_area_m2: SquareMetres | None = None


class Level(Reviewed):
    """Một tầng; tầng chưa hiệu chỉnh thì vắng `scaleMillimetresPerPixel` (W24)."""

    id: LevelIdStr
    name: HumanText
    order: SafeInt
    elevation_mm: Mm
    height_mm: PositiveMm
    area_m2: SquareMetres | None = None
    scale_millimetres_per_pixel: Annotated[StrictFloat, Field(gt=0, allow_inf_nan=False)] | None = None


class Wall(Reviewed):
    """Một đoạn tường trên một tầng, đo theo đường tim."""

    id: WallIdStr
    level_id: LevelIdStr
    centreline: Segment
    thickness_mm: PositiveMm
    height_mm: PositiveMm
    kind: Literal["loadBearing", "partition", "envelope"]
    opening_ids: tuple[OpeningIdStr, ...]


class Opening(Reviewed):
    """Ô mở (cửa đi hoặc cửa sổ) khoét trong một tường; `offsetMm` tính từ đầu đường tim."""

    id: OpeningIdStr
    wall_id: WallIdStr
    kind: Literal["door", "window"]
    offset_mm: NonNegativeMm
    width_mm: PositiveMm
    height_mm: PositiveMm
    sill_height_mm: NonNegativeMm
    swing: Literal["left", "right", "double", "sliding", "fixed"]


class Furniture(Reviewed):
    """Đồ đạc đặt trên mặt bằng; `roomId` vắng khi chưa gắn phòng."""

    id: FurnitureIdStr
    level_id: LevelIdStr
    room_id: RoomIdStr | None = None
    kind: Literal["table", "chair", "bed", "wardrobe", "kitchenCabinet", "sanitaryFixture", "stair", "other"]
    centre: Point
    bounding_box: BoundingBox
    rotation_deg: Degrees


class Room(Reviewed):
    """Phòng khép kín; điểm đầu không lặp ở cuối nên ít nhất ba điểm."""

    id: RoomIdStr
    level_id: LevelIdStr
    name: HumanText
    usage: Literal["livingRoom", "bedroom", "kitchen", "bathroom", "corridor", "stairwell", "utility", "other"]
    outline: Annotated[tuple[Point, ...], Field(min_length=3)]
    area_m2: SquareMetres
    wall_ids: tuple[WallIdStr, ...]


class Axis(Reviewed):
    """Trục định vị; v1 `axes` luôn rỗng trên dây nhưng mẫu A14 có bốn trục."""

    id: AxisIdStr
    level_id: LevelIdStr
    label: HumanText
    direction: Literal["horizontal", "vertical"]
    line: Segment


class Dimension(Reviewed):
    """Chuỗi kích thước; `referenceIds` được rỗng (kích thước người tự vẽ chưa gắn thực thể)."""

    id: DimensionIdStr
    level_id: LevelIdStr
    kind: Literal["linear", "chain", "radial", "angular", "elevation"]
    reference_ids: tuple[EntityIdStr, ...]
    line: Segment
    value_mm: Mm
    override_value_mm: Mm | None = None

    @model_validator(mode="after")
    def _positive_unless_elevation(self) -> Self:
        """`kind ≠ elevation` ⇒ `valueMm > 0`: cao độ được 0 hay âm (cốt nền, tầng hầm), chiều dài 0 là OCR hỏng."""
        if self.kind != "elevation" and self.value_mm <= 0:
            raise ValueError("valueMm phải > 0 khi kind khác elevation")
        return self


class Note(Reviewed):
    """Ghi chú gắn vào một thực thể; `id` ngoài bảng tiền tố nên là chuỗi tự do."""

    id: NonEmptyStr
    entity_id: EntityIdStr
    body: HumanText
    created_at: WireInstant
    author_id: NonEmptyStr


class SpatialLayer(DomainModel):
    """Bốn danh sách của một tầng, đúng `SpatialLayerSchema` (N16, #35)."""

    walls: tuple[Wall, ...]
    openings: tuple[Opening, ...]
    rooms: tuple[Room, ...]
    furniture: tuple[Furniture, ...]

    def entities(self) -> tuple[Wall | Opening | Room | Furniture, ...]:
        """Mọi thực thể theo thứ tự cố định `walls → openings → rooms → furniture` (toàn vẹn, diff)."""
        return (*self.walls, *self.openings, *self.rooms, *self.furniture)


class SpatialGraph(DomainModel):
    """Đồ thị của cả công trình (N15); danh sách chỉ trỏ nhau qua id, không lồng."""

    building: Building
    levels: tuple[Level, ...]
    walls: tuple[Wall, ...]
    openings: tuple[Opening, ...]
    furniture: tuple[Furniture, ...]
    rooms: tuple[Room, ...]
    axes: tuple[Axis, ...]
    dimensions: tuple[Dimension, ...]
    notes: tuple[Note, ...]
