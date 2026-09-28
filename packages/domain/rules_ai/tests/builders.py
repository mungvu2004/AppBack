"""Dựng thực thể và lớp cho test: id W4 đúng loại, trường chỉ nêu cái test cần đổi."""

from typing import Any, Final, Literal

from packages.domain.spatial import BoundingBox, Furniture, Opening, Point, Room, Segment, SpatialLayer, Wall

LEVEL: Final = "L-LEVEL000000"
SourceName = Literal["ai", "human"]


def eid(prefix: str, number: int) -> str:
    """Id W4 `<tiền tố>-T<9 chữ số>` (10 ký tự sau dấu gạch, đúng mẫu `[0-9A-Z]{10,64}`)."""
    return f"{prefix}-T{number:09d}"


def wid(number: int) -> str:
    """Id tường."""
    return eid("W", number)


def oid(number: int) -> str:
    """Id ô mở."""
    return eid("D", number)


def rid(number: int) -> str:
    """Id phòng."""
    return eid("R", number)


def fid(number: int) -> str:
    """Id đồ đạc."""
    return eid("F", number)


def review(source: SourceName = "ai", *, reviewed: bool = False, confidence: float = 0.82) -> dict[str, Any]:
    """Ba trường duyệt; mặc định là đầu ra AI chưa duyệt, tin cậy 0,82 như bộ mẫu A14."""
    return {"source": source, "reviewed": reviewed, "confidence": confidence}


def wall(
    number: int,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    kind: str = "partition",
    thickness: int = 100,
    opening_ids: tuple[str, ...] = (),
    level: str = LEVEL,
    **flags: Any,
) -> Wall:
    """Tường `W-T<number>` từ `start` tới `end`; `flags` đi vào `review`."""
    return Wall(
        id=wid(number),
        level_id=level,
        centreline=Segment(start=Point(x=start[0], y=start[1]), end=Point(x=end[0], y=end[1])),
        thickness_mm=thickness,
        height_mm=2700,
        kind=kind,
        opening_ids=opening_ids,
        **review(**flags),
    )


def opening(number: int, wall_number: int, *, kind: str = "window", **flags: Any) -> Opening:
    """Ô mở `D-T<number>` trên tường `W-T<wall_number>`."""
    return Opening(
        id=oid(number),
        wall_id=wid(wall_number),
        kind=kind,
        offset_mm=500,
        width_mm=900,
        height_mm=1200,
        sill_height_mm=900,
        swing="fixed",
        **review(**flags),
    )


def rectangle(low: tuple[int, int], high: tuple[int, int]) -> tuple[Point, ...]:
    """Đường bao chữ nhật ngược chiều kim đồng hồ, điểm đầu không lặp ở cuối."""
    return (
        Point(x=low[0], y=low[1]),
        Point(x=high[0], y=low[1]),
        Point(x=high[0], y=high[1]),
        Point(x=low[0], y=high[1]),
    )


def room(
    number: int,
    outline: tuple[Point, ...],
    *,
    wall_ids: tuple[str, ...] = (),
    level: str = LEVEL,
    **flags: Any,
) -> Room:
    """Phòng `R-T<number>` với đường bao cho trước (diện tích không quan trọng với luật)."""
    return Room(
        id=rid(number),
        level_id=level,
        name="Phòng",
        usage="other",
        outline=outline,
        area_m2=12.0,
        wall_ids=wall_ids,
        **review(**flags),
    )


def box_room(number: int, low: tuple[int, int], high: tuple[int, int], **kwargs: Any) -> Room:
    """Phòng chữ nhật `R-T<number>` từ `low` tới `high`."""
    return room(number, rectangle(low, high), **kwargs)


def furniture(
    number: int,
    centre: tuple[int, int],
    *,
    kind: str = "sanitaryFixture",
    size: int = 600,
    room_id: str | None = None,
    level: str = LEVEL,
    **flags: Any,
) -> Furniture:
    """Đồ đạc `F-T<number>` hộp vuông cạnh `size` quanh `centre`."""
    half = size // 2
    return Furniture(
        id=fid(number),
        level_id=level,
        room_id=room_id,
        kind=kind,
        centre=Point(x=centre[0], y=centre[1]),
        bounding_box=BoundingBox(
            min=Point(x=centre[0] - half, y=centre[1] - half), max=Point(x=centre[0] + half, y=centre[1] + half)
        ),
        rotation_deg=0.0,
        **review(**flags),
    )


def layer(
    *,
    walls: tuple[Wall, ...] = (),
    openings: tuple[Opening, ...] = (),
    rooms: tuple[Room, ...] = (),
    furniture_items: tuple[Furniture, ...] = (),
) -> SpatialLayer:
    """Lớp từ bốn danh sách; `openingIds` của tường **không** tự điền, test tự nêu."""
    return SpatialLayer(walls=walls, openings=openings, rooms=rooms, furniture=furniture_items)


def with_openings(walls: tuple[Wall, ...], openings: tuple[Opening, ...]) -> tuple[Wall, ...]:
    """Điền `openingIds` của mỗi tường theo các ô mở trỏ tới nó (thứ tự `openings`)."""
    return tuple(
        w.model_copy(update={"opening_ids": tuple(o.id for o in openings if o.wall_id == w.id)}) for w in walls
    )
