"""Bộ mẫu A14: chép đúng `createSampleBuilding()` của `src/domain/spatial/__fixtures__/sampleBuilding.ts`.

4 tầng, 48 tường, 16 ô mở (9 cửa đi, 7 cửa sổ), 21 đồ đạc, 14 phòng, 4 trục, 34
kích thước; cùng id, toạ độ, `APPROVED`/`DETECTED`. Chỉ `Note.createdAt` đổi từ
`+07:00` sang UTC `.sssZ` (HOP-DONG-MOI §4.1). Dựng bằng dict dạng dây rồi
`model_validate`, nên bộ mẫu cũng là một lượt kiểm mô hình.

Lệch đã biết (FE CLAUDE.md A14): `SAMPLE_TOTAL_AREA_M2` khai 248,60 m², nhưng 14
đường bao thật đều 4000 x 4250 mm nên đo ra 238,00 m²; giữ nguyên cả hai.
"""

from decimal import Decimal
from functools import cache
from typing import Final

from packages.domain.spatial.model import SpatialGraph, SpatialLayer

SAMPLE_TOTAL_AREA_M2: Final = Decimal("248.60")

_LEVEL_COUNT: Final = 4
_WALL_COUNT: Final = 48
_FURNITURE_COUNT: Final = 21
_ROOM_COUNT: Final = 14
_DIMENSION_COUNT: Final = 34
_DOOR_COUNT: Final = 9
_WINDOW_COUNT: Final = 7
_AXIS_COUNT: Final = 4
_LARGE_ROOM_AREA_M2: Final = 27.6
_SMALL_ROOM_AREA_M2: Final = 17.0
_LEVEL_HEIGHT_MM: Final = 3600
_WALL_LENGTH_MM: Final = 1000
_ROOM_WIDTH_MM: Final = 4000
_ROOM_DEPTH_MM: Final = 4250
_FURNITURE_SIZE_MM: Final = 800
_APPROVED: Final = {"confidence": 1.0, "reviewed": True, "source": "human"}
_DETECTED: Final = {"confidence": 0.82, "reviewed": False, "source": "ai"}


def _id(prefix: str, index: int) -> str:
    """Id ổn định như `sample*Id` của FE: `<tiền tố><6 chữ số>0` (`L-LEVEL` không có `0` cuối)."""
    return f"{prefix}{index:06d}" if prefix == "L-LEVEL" else f"{prefix}{index:06d}0"


def _level_of(index: int) -> str:
    """Tầng của thực thể thứ `index`, rải đều như `sampleLevelOf`."""
    return _id("L-LEVEL", index % _LEVEL_COUNT)


def _segment(x0: int, y0: int, x1: int, y1: int) -> dict[str, object]:
    """Đoạn thẳng dạng dây."""
    return {"start": {"x": x0, "y": y0}, "end": {"x": x1, "y": y1}}


def _openings() -> list[dict[str, object]]:
    """Cửa đi chiếm tường 0..8, cửa sổ chiếm tường 9..15."""
    doors = [
        {
            **_DETECTED,
            "id": _id("D-DOOR", i),
            "wallId": _id("W-WALL", i),
            "kind": "door",
            "offsetMm": 300,
            "widthMm": 900,
            "heightMm": 2200,
            "sillHeightMm": 0,
            "swing": "left",
        }
        for i in range(_DOOR_COUNT)
    ]
    windows = [
        {
            **_DETECTED,
            "id": _id("D-WNDW", i),
            "wallId": _id("W-WALL", _DOOR_COUNT + i),
            "kind": "window",
            "offsetMm": 500,
            "widthMm": 1200,
            "heightMm": 1400,
            "sillHeightMm": 900,
            "swing": "sliding",
        }
        for i in range(_WINDOW_COUNT)
    ]
    return doors + windows


def _walls(openings: list[dict[str, object]]) -> list[dict[str, object]]:
    """48 tường nối đuôi trên trục x; mỗi tường liệt kê ô mở trỏ về nó."""
    hosted: dict[object, list[object]] = {}
    for opening in openings:
        hosted.setdefault(opening["wallId"], []).append(opening["id"])
    return [
        {
            **_DETECTED,
            "id": _id("W-WALL", i),
            "levelId": _level_of(i),
            "centreline": _segment(i * _WALL_LENGTH_MM, 0, (i + 1) * _WALL_LENGTH_MM, 0),
            "thicknessMm": 220,
            "heightMm": _LEVEL_HEIGHT_MM,
            "kind": "partition",
            "openingIds": hosted.get(_id("W-WALL", i), []),
        }
        for i in range(_WALL_COUNT)
    ]


def _furniture() -> list[dict[str, object]]:
    """21 bàn; phòng `i % 4` nằm cùng tầng với đồ đạc thứ `i`."""
    half = _FURNITURE_SIZE_MM // 2
    return [
        {
            **_DETECTED,
            "id": _id("F-FURN", i),
            "levelId": _level_of(i),
            "roomId": _id("R-ROOM", i % _LEVEL_COUNT),
            "kind": "table",
            "centre": {"x": i * _WALL_LENGTH_MM + half, "y": half},
            "boundingBox": {
                "min": {"x": i * _WALL_LENGTH_MM, "y": 0},
                "max": {"x": i * _WALL_LENGTH_MM + _FURNITURE_SIZE_MM, "y": _FURNITURE_SIZE_MM},
            },
            "rotationDeg": 0.0,
        }
        for i in range(_FURNITURE_COUNT)
    ]


def _rooms() -> list[dict[str, object]]:
    """13 phòng khai 17,00 m² và một phòng khai 27,60 m², cùng đường bao 4000 x 4250 mm."""
    rooms: list[dict[str, object]] = []
    for i in range(_ROOM_COUNT):
        left, right = i * _ROOM_WIDTH_MM, (i + 1) * _ROOM_WIDTH_MM
        corners = ((left, 0), (right, 0), (right, _ROOM_DEPTH_MM), (left, _ROOM_DEPTH_MM))
        rooms.append(
            {
                **_APPROVED,
                "id": _id("R-ROOM", i),
                "levelId": _level_of(i),
                "name": f"Room {i}",
                "usage": "bedroom",
                "areaM2": _LARGE_ROOM_AREA_M2 if i == _ROOM_COUNT - 1 else _SMALL_ROOM_AREA_M2,
                "outline": [{"x": x, "y": y} for x, y in corners],
                "wallIds": [_id("W-WALL", i)],
            }
        )
    return rooms


def _annotations() -> dict[str, list[dict[str, object]]]:
    """Tầng, trục, kích thước và ghi chú của mẫu."""
    return {
        "levels": [
            {
                **_APPROVED,
                "id": _id("L-LEVEL", i),
                "name": f"Level {i}",
                "order": i,
                "elevationMm": i * _LEVEL_HEIGHT_MM,
                "heightMm": _LEVEL_HEIGHT_MM,
            }
            for i in range(_LEVEL_COUNT)
        ],
        "axes": [
            {
                **_APPROVED,
                "id": _id("A-AXIS", i),
                "levelId": _level_of(i),
                "label": chr(65 + i),
                "direction": "horizontal",
                "line": _segment(0, i * 3000, _WALL_COUNT * _WALL_LENGTH_MM, i * 3000),
            }
            for i in range(_AXIS_COUNT)
        ],
        "dimensions": [
            {
                **_DETECTED,
                "id": _id("M-DIMN", i),
                "levelId": _level_of(i),
                "kind": "linear",
                "referenceIds": [_id("W-WALL", i)],
                "valueMm": _WALL_LENGTH_MM,
                "line": _segment(i * _WALL_LENGTH_MM, -500, (i + 1) * _WALL_LENGTH_MM, -500),
            }
            for i in range(_DIMENSION_COUNT)
        ],
        "notes": [
            {
                **_APPROVED,
                "id": "note-1",
                "entityId": _id("W-WALL", 0),
                "body": "Đã đối chiếu với bản vẽ khảo sát.",
                "createdAt": "2026-08-13T02:00:00.000Z",
                "authorId": "U-1",
            }
        ],
    }


@cache
def sample_building() -> SpatialGraph:
    """Đồ thị mẫu A14, qua trọn kiểm của mô hình và `check_integrity` từng tầng không lỗi.

    Nhớ một bản: mô hình bất biến nên dùng chung an toàn; test cần phá thì dựng bản
    mới bằng `model_copy`/`model_validate`.
    """
    openings = _openings()
    return SpatialGraph.model_validate(
        {
            "building": {
                **_APPROVED,
                "name": "Chung cư Hoàng Anh",
                "address": "12 Nguyễn Huệ, Quận 1",
                "datumElevationMm": 0,
                "grossFloorAreaM2": float(SAMPLE_TOTAL_AREA_M2),
            },
            "walls": _walls(openings),
            "openings": openings,
            "furniture": _furniture(),
            "rooms": _rooms(),
            **_annotations(),
        }
    )


def sample_layer(level_index: int) -> SpatialLayer:
    """Lớp của tầng `level_index` (0..3): tường, phòng, đồ đạc của tầng đó + ô mở có tường chủ ở tầng đó."""
    if not 0 <= level_index < _LEVEL_COUNT:
        raise ValueError(f"mẫu A14 chỉ có tầng 0..{_LEVEL_COUNT - 1}")
    graph = sample_building()
    level_id = _id("L-LEVEL", level_index)
    walls = tuple(wall for wall in graph.walls if wall.level_id == level_id)
    wall_ids = {wall.id for wall in walls}
    return SpatialLayer(
        walls=walls,
        openings=tuple(opening for opening in graph.openings if opening.wall_id in wall_ids),
        rooms=tuple(room for room in graph.rooms if room.level_id == level_id),
        furniture=tuple(item for item in graph.furniture if item.level_id == level_id),
    )
