"""Ràng buộc mô hình (B3-01 [6], [8]): mỗi luật một ca hỏng và một ca biên đạt; xuất dây không `null`."""

import json
import unicodedata
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from packages.domain.spatial import (
    Axis,
    BoundingBox,
    Building,
    Dimension,
    Furniture,
    Level,
    Note,
    Opening,
    Point,
    Room,
    Segment,
    SpatialGraph,
    Wall,
    sample_building,
)

MAX_SAFE = 2**53 - 1
GRAPH = sample_building()


def wire(model: BaseModel) -> dict[str, Any]:
    """Dạng dây: camelCase, bỏ trường vắng (W2)."""
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def segment(x0: int, y0: int, x1: int, y1: int) -> dict[str, Any]:
    """Đoạn thẳng dạng dây."""
    return {"start": {"x": x0, "y": y0}, "end": {"x": x1, "y": y1}}


BASES: dict[type[BaseModel], dict[str, Any]] = {
    Building: wire(GRAPH.building),
    Level: wire(GRAPH.levels[0]),
    Wall: wire(GRAPH.walls[0]),
    Opening: wire(GRAPH.openings[0]),
    Furniture: wire(GRAPH.furniture[0]),
    Room: wire(GRAPH.rooms[0]),
    Axis: wire(GRAPH.axes[0]),
    Dimension: wire(GRAPH.dimensions[0]),
    Note: wire(GRAPH.notes[0]),
}

# (model, khoá dây, giá trị): giá trị biên còn đạt.
ACCEPTED = [
    (Wall, "thicknessMm", 1),
    (Wall, "heightMm", 1),
    (Wall, "centreline", segment(-MAX_SAFE, 0, MAX_SAFE, 0)),
    (Wall, "openingIds", []),
    (Opening, "offsetMm", 0),
    (Opening, "sillHeightMm", 0),
    (Opening, "widthMm", 1),
    (Furniture, "rotationDeg", 0),
    (Furniture, "rotationDeg", 359.999),
    (Furniture, "boundingBox", {"min": {"x": 5, "y": 5}, "max": {"x": 5, "y": 5}}),
    (Furniture, "confidence", 0),
    (Furniture, "confidence", 1),
    (Room, "outline", [{"x": 0, "y": 0}, {"x": 10, "y": 0}, {"x": 0, "y": 10}]),
    (Room, "areaM2", 0),
    (Level, "heightMm", 1),
    (Level, "scaleMillimetresPerPixel", 0.5),
    (Level, "elevationMm", -3000),
    (Building, "datumElevationMm", -1200),
    (Dimension, "referenceIds", []),
    (Dimension, "referenceIds", ["R-ROOM0000000", "L-LEVEL000000"]),
    (Dimension, "valueMm", 1),
    (Note, "id", "note-1"),
    (Note, "entityId", "R-ROOM0000000"),
]

# (model, khoá dây, giá trị): mỗi dòng một ràng buộc bị phá.
REJECTED = [
    (Wall, "thicknessMm", 0),
    (Wall, "thicknessMm", 1.5),
    (Wall, "thicknessMm", True),
    (Wall, "thicknessMm", "12"),
    (Wall, "heightMm", -1),
    (Wall, "centreline", segment(0, 0, 2**53, 0)),
    (Wall, "centreline", segment(-(2**53), 0, 0, 0)),
    (Wall, "centreline", segment(7, 7, 7, 7)),
    (Wall, "kind", "curtain"),
    (Wall, "id", "W-1"),
    (Wall, "id", "R-ROOM0000000"),
    (Wall, "id", "W-wall0000000"),
    (Wall, "levelId", "W-WALL0000000"),
    (Wall, "openingIds", ["W-WALL0000000"]),
    (Wall, "colour", "red"),
    (Opening, "offsetMm", -1),
    (Opening, "sillHeightMm", -1),
    (Opening, "widthMm", 0),
    (Opening, "heightMm", 0),
    (Opening, "kind", "hatch"),
    (Opening, "wallId", "D-DOOR0000000"),
    (Furniture, "rotationDeg", 360),
    (Furniture, "rotationDeg", -0.1),
    (Furniture, "boundingBox", {"min": {"x": 5, "y": 0}, "max": {"x": 4, "y": 9}}),
    (Furniture, "boundingBox", {"min": {"x": 0, "y": 5}, "max": {"x": 9, "y": 4}}),
    (Furniture, "confidence", 1.0000001),
    (Furniture, "confidence", -0.01),
    (Furniture, "confidence", float("nan")),
    (Furniture, "confidence", "0.5"),
    (Furniture, "reviewed", "true"),
    (Furniture, "source", "robot"),
    (Furniture, "roomId", "abc"),
    (Room, "outline", [{"x": 0, "y": 0}, {"x": 10, "y": 0}]),
    (Room, "areaM2", -0.01),
    (Room, "areaM2", float("inf")),
    (Room, "wallIds", ["F-FURN0000000"]),
    (Room, "name", ""),
    (Room, "name", "Phòng‮khách"),
    (Room, "name", "Phòng⁦khách"),
    (Room, "name", "Phòng\x07khách"),
    (Room, "name", "Phòng\nkhách"),
    (Level, "heightMm", 0),
    (Level, "order", 1.0),
    (Level, "scaleMillimetresPerPixel", 0),
    (Level, "scaleMillimetresPerPixel", float("inf")),
    (Level, "areaM2", float("nan")),
    (Level, "id", "L-1"),
    (Building, "grossFloorAreaM2", -1),
    (Building, "address", ""),
    (Axis, "line", segment(0, 0, 0, 0)),
    (Axis, "direction", "diagonal"),
    (Dimension, "valueMm", 0),
    (Dimension, "referenceIds", ["abc"]),
    (Dimension, "kind", "arc"),
    (Note, "createdAt", "2026-08-13T09:00:00+07:00"),
    (Note, "createdAt", "2026-08-13T02:00:00Z"),
    (Note, "createdAt", "2026-13-13T02:00:00.000Z"),
    (Note, "id", ""),
    (Note, "authorId", ""),
    (Note, "entityId", "note-1"),
]


def _with(model: type[BaseModel], key: str, value: object) -> dict[str, Any]:
    """Bản dây mẫu của `model` với một khoá đổi giá trị."""
    return {**BASES[model], key: value}


@pytest.mark.parametrize(("model", "key", "value"), ACCEPTED)
def test_boundary_value_is_accepted(model: type[BaseModel], key: str, value: object) -> None:
    """Giá trị ở đúng biên của ràng buộc vẫn đạt."""
    model.model_validate(_with(model, key, value))


@pytest.mark.parametrize(("model", "key", "value"), REJECTED)
def test_broken_constraint_is_rejected(model: type[BaseModel], key: str, value: object) -> None:
    """Mỗi ràng buộc của [6] hỏng thành `ValidationError` (B3-03 đổi thành 422 `VALIDATION`)."""
    with pytest.raises(ValidationError):
        model.model_validate(_with(model, key, value))


def test_elevation_dimension_may_be_zero_or_negative() -> None:
    """`valueMm > 0` miễn cho `elevation` (cốt nền, tầng hầm); `linear` bằng 0 thì hỏng."""
    elevation = {**BASES[Dimension], "kind": "elevation"}
    assert Dimension.model_validate({**elevation, "valueMm": 0}).value_mm == 0
    assert Dimension.model_validate({**elevation, "valueMm": -3000}).value_mm == -3000
    with pytest.raises(ValidationError, match="valueMm"):
        Dimension.model_validate({**BASES[Dimension], "valueMm": 0})


def test_segment_and_box_constructed_in_python_are_checked() -> None:
    """Luật hình học chạy cả khi dựng bằng tên trường Python, không chỉ từ dây."""
    with pytest.raises(ValidationError, match="dài 0"):
        Segment(start=Point(x=1, y=1), end=Point(x=1, y=1))
    with pytest.raises(ValidationError, match="lộn ngược"):
        BoundingBox(min=Point(x=2, y=0), max=Point(x=1, y=0))


def test_human_text_is_stored_nfc() -> None:
    """Tên nhập dạng NFD được lưu NFC (BE-00 §6)."""
    decomposed = unicodedata.normalize("NFD", "Phòng khách")
    assert decomposed != "Phòng khách"
    room = Room.model_validate(_with(Room, "name", decomposed))
    assert room.name == "Phòng khách"


def test_created_at_keeps_the_wire_string() -> None:
    """`createdAt` kiểm bằng `parse_wire` nhưng giữ nguyên chuỗi `.sssZ`."""
    assert GRAPH.notes[0].created_at == "2026-08-13T02:00:00.000Z"


def test_area_is_a_json_number() -> None:
    """`areaM2` là số trong JSON; chuỗi (như `Decimal` xuất ra) làm `z.number()` hỏng cả lớp."""
    text = json.dumps(wire(GRAPH.rooms[0]))
    assert json.loads(text)["areaM2"] == 17.0
    assert '"areaM2": 17.0' in text


def test_absent_optional_field_is_absent_not_null() -> None:
    """Đồ đạc chưa gắn phòng: khoá `roomId` vắng, không `null` (W2, K02)."""
    loose = Furniture.model_validate({key: v for key, v in BASES[Furniture].items() if key != "roomId"})
    assert loose.room_id is None
    assert "roomId" not in wire(loose)


def _nulls(value: object) -> int:
    """Số `None` ở mọi độ sâu của một giá trị JSON."""
    if isinstance(value, dict):
        return sum(_nulls(item) for item in value.values())
    if isinstance(value, list):
        return sum(_nulls(item) for item in value)
    return int(value is None)


def test_sample_building_wire_round_trip() -> None:
    """Khứ hồi dây của cả mẫu A14 bằng nhau và JSON không có `null` nào."""
    payload = json.loads(json.dumps(wire(GRAPH)))
    assert _nulls(payload) == 0
    assert SpatialGraph.model_validate(payload) == GRAPH
