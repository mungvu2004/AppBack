"""Test `rooms.build_rooms`, `rooms.build_furniture` (B5-05 [6] bước 5, 6; [8] mục Phòng, Đồ)."""

from collections import Counter
from collections.abc import Callable

import shapely

from apps.worker.pipeline_build.geometry import Scaling
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.rooms import _outline_points, build_furniture, build_rooms
from packages.domain.rules_ai import LOW_CONFIDENCE_CAP
from packages.domain.spatial import Point, Room, Segment, Wall, js_round, polygon_area_m2
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, TextPx
from packages.testing.fixtures.clock import FakeClock

_IDENTITY = Scaling(build=1.0, final=1.0)
LEVEL_ID = "L-0000000000000000000000000"


def _wall(
    clock: FakeClock,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    thickness: int = 100,
    confidence: float = 0.9,
) -> Wall:
    """Tường tay cho test: `id` từ `new_spatial_id`, không ô mở."""
    return Wall(
        id=new_spatial_id("wall", clock),
        level_id=LEVEL_ID,
        centreline=Segment(start=Point(x=start[0], y=start[1]), end=Point(x=end[0], y=end[1])),
        thickness_mm=thickness,
        height_mm=3600,
        kind="partition",
        opening_ids=(),
        confidence=confidence,
        source="ai",
        reviewed=False,
    )


def _grid_walls(clock: FakeClock, confidences: Callable[[int], float] | None = None) -> list[Wall]:
    """Lưới 2 phòng 3 m x 3 m (6000x3000 mm), tường giữa chia đôi (test lưới, wallIds, confidence)."""
    segments = [
        ((0, 0), (6000, 0)),
        ((0, 3000), (6000, 3000)),
        ((0, 0), (0, 3000)),
        ((6000, 0), (6000, 3000)),
        ((3000, 0), (3000, 3000)),
    ]
    conf = confidences or (lambda i: 0.9)
    return [_wall(clock, start, end, confidence=conf(i)) for i, (start, end) in enumerate(segments)]


def test_grid_gives_two_rooms_with_matching_area(fake_clock: FakeClock) -> None:
    """Lưới 2 phòng → 2 phòng, `areaM2 == float(polygon_area_m2(outline))`, tên `phòng 1`/`phòng 2` theo (y, x)."""
    walls = _grid_walls(fake_clock)
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 2
    assert [r.name for r in rooms] == ["phòng 1", "phòng 2"]
    for room in rooms:
        assert room.area_m2 == float(polygon_area_m2(room.outline))


def test_corner_gap_150_still_closes(fake_clock: FakeClock) -> None:
    """Khe góc `ROOM_SNAP_MM` (150) vẫn khép nhờ kéo dài hai đầu tường."""
    walls = [
        _wall(fake_clock, (0, 0), (4000, 0)),
        _wall(fake_clock, (4000, 0), (4000, 4000)),
        _wall(fake_clock, (4000, 4000), (0, 4000)),
        _wall(fake_clock, (0, 4000), (0, 150)),  # thiếu 150 mm tới góc (0, 0)
    ]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1


def test_corner_gap_400_gives_no_room(fake_clock: FakeClock) -> None:
    """Khe góc 400 mm > `ROOM_SNAP_MM` x 2 hướng → không khép, không phòng."""
    walls = [
        _wall(fake_clock, (0, 0), (4000, 0)),
        _wall(fake_clock, (4000, 0), (4000, 4000)),
        _wall(fake_clock, (4000, 4000), (0, 4000)),
        _wall(fake_clock, (0, 4000), (0, 400)),  # thiếu 400 mm tới góc (0, 0)
    ]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert rooms == ()


def test_door_gap_with_bridge_keeps_two_rooms(fake_clock: FakeClock) -> None:
    """Tường giữa cắt đôi bởi khe cửa 900 mm + `bridges` (như A trả bước 3b) → vẫn 2 phòng."""
    walls = [
        _wall(fake_clock, (0, 0), (6000, 0)),
        _wall(fake_clock, (0, 3000), (6000, 3000)),
        _wall(fake_clock, (0, 0), (0, 3000)),
        _wall(fake_clock, (6000, 0), (6000, 3000)),
        _wall(fake_clock, (3000, 0), (3000, 1000)),
        _wall(fake_clock, (3000, 1900), (3000, 3000)),
    ]
    bridges = ((Point(x=3000, y=1000), Point(x=3000, y=1900)),)
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, bridges, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 2


def test_text_phong_ngu_names_bedroom(fake_clock: FakeClock) -> None:
    """Chữ `PHONG NGU` trong phòng → `usage="bedroom"`, tên `phòng ngủ`."""
    walls = _grid_walls(fake_clock)
    texts = (TextPx(text="PHONG NGU", box=BoxPx(x_min=1000, y_min=1000, x_max=1400, y_max=1200), confidence=0.85),)
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), texts, level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    named = next(r for r in rooms if r.usage == "bedroom")
    assert named.name == "phòng ngủ"


def test_higher_confidence_non_room_label_does_not_override(fake_clock: FakeClock) -> None:
    """Thêm `3.600` (0,98, không phải nhãn phòng) cạnh `PHONG NGU` (0,85) → vẫn `bedroom`."""
    walls = _grid_walls(fake_clock)
    texts = (
        TextPx(text="PHONG NGU", box=BoxPx(x_min=1000, y_min=1000, x_max=1400, y_max=1200), confidence=0.85),
        TextPx(text="3.600", box=BoxPx(x_min=1000, y_min=1300, x_max=1300, y_max=1500), confidence=0.98),
    )
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), texts, level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    named = next(r for r in rooms if r.usage == "bedroom")
    assert named.name == "phòng ngủ"


def test_small_fragment_is_dropped_too_small(fake_clock: FakeClock) -> None:
    """Mảnh ~0,5 m² < `MIN_ROOM_AREA_M2` → `roomTooSmall`, không sinh phòng."""
    side = 700  # 0.7 x 0.7 m = 0.49 m^2
    walls = [
        _wall(fake_clock, (0, 0), (side, 0)),
        _wall(fake_clock, (side, 0), (side, side)),
        _wall(fake_clock, (side, side), (0, side)),
        _wall(fake_clock, (0, side), (0, 0)),
    ]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert rooms == ()
    assert dropped["roomTooSmall"] == 1


def test_wall_ids_and_confidence_take_minimum(fake_clock: FakeClock) -> None:
    """`wallIds` = 4 tường của phòng, `confidence` = nhỏ nhất trong số đó."""
    confidences = [0.9, 0.8, 0.7, 0.6]
    walls = [
        _wall(fake_clock, (0, 0), (4000, 0), confidence=confidences[0]),
        _wall(fake_clock, (4000, 0), (4000, 4000), confidence=confidences[1]),
        _wall(fake_clock, (4000, 4000), (0, 4000), confidence=confidences[2]),
        _wall(fake_clock, (0, 4000), (0, 0), confidence=confidences[3]),
    ]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1
    room = rooms[0]
    assert set(room.wall_ids) == {w.id for w in walls}
    assert room.confidence == min(confidences)


def test_room_without_walls_caps_confidence(fake_clock: FakeClock) -> None:
    """Phòng khép chỉ từ `bridges` (không tường) → `wallIds` rỗng, `confidence == LOW_CONFIDENCE_CAP`."""
    bridges = (
        (Point(x=0, y=0), Point(x=4000, y=0)),
        (Point(x=4000, y=0), Point(x=4000, y=4000)),
        (Point(x=4000, y=4000), Point(x=0, y=4000)),
        (Point(x=0, y=4000), Point(x=0, y=0)),
    )
    dropped: Counter[str] = Counter()
    rooms = build_rooms([], bridges, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1
    assert rooms[0].wall_ids == ()
    assert rooms[0].confidence == LOW_CONFIDENCE_CAP


def _room(fake_clock: FakeClock, corners: tuple[tuple[int, int], tuple[int, int]]) -> Room:
    """Một `Room` tay 4 điểm, không tường, phục vụ test `build_furniture`."""
    (x0, y0), (x1, y1) = corners
    outline = (Point(x=x0, y=y0), Point(x=x1, y=y0), Point(x=x1, y=y1), Point(x=x0, y=y1))
    return Room(
        id=new_spatial_id("room", fake_clock),
        level_id=LEVEL_ID,
        name="phòng 1",
        usage="other",
        outline=outline,
        area_m2=float(polygon_area_m2(outline)),
        wall_ids=(),
        confidence=0.9,
        source="ai",
        reviewed=False,
    )


def test_kitchen_cabinet_label_maps_to_camel_kind(fake_clock: FakeClock) -> None:
    """`kitchen_cabinet` → `Furniture.kind == "kitchenCabinet"`."""
    box = BoxPx(x_min=0, y_min=0, x_max=600, y_max=600)
    detections = (DetectionPx(label="kitchen_cabinet", box=box, confidence=0.9),)
    dropped: Counter[str] = Counter()
    items = build_furniture(detections, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(items) == 1
    assert items[0].kind == "kitchenCabinet"


def test_furniture_outside_room_dumps_without_room_id_key(fake_clock: FakeClock) -> None:
    """Đồ ngoài mọi phòng → `roomId = None`, `model_dump(..., exclude_none=True)` vắng khoá `roomId`."""
    room = _room(fake_clock, ((0, 0), (1000, 1000)))
    detections = (
        DetectionPx(label="chair", box=BoxPx(x_min=5000, y_min=5000, x_max=5600, y_max=5600), confidence=0.9),
    )
    dropped: Counter[str] = Counter()
    items = build_furniture(
        detections, (room,), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped
    )
    assert len(items) == 1
    dumped = items[0].model_dump(mode="json", by_alias=True, exclude_none=True)
    assert "roomId" not in dumped


def test_unknown_label_is_dropped(fake_clock: FakeClock) -> None:
    """Nhãn lạ ngoài bảng `LABEL_TARGETS` → `unknownLabel`, không sinh đồ."""
    detection = DetectionPx.model_construct(
        label="lamp",  # type: ignore[arg-type]  # bỏ qua kiểm Literal để dựng nhãn lạ
        box=BoxPx(x_min=0, y_min=0, x_max=600, y_max=600),
        confidence=0.9,
    )
    dropped: Counter[str] = Counter()
    items = build_furniture((detection,), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert items == ()
    assert dropped["unknownLabel"] == 1


def test_zero_width_box_is_furniture_empty(fake_clock: FakeClock) -> None:
    """Hộp mm rộng 0 sau `js_round` → `furnitureEmpty`, không sinh đồ."""
    detections = (
        DetectionPx(label="table", box=BoxPx(x_min=1000, y_min=1000, x_max=1000.4, y_max=2000), confidence=0.9),
    )
    dropped: Counter[str] = Counter()
    items = build_furniture(detections, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert items == ()
    assert dropped["furnitureEmpty"] == 1


def test_furniture_centre_is_js_rounded_midpoint(fake_clock: FakeClock) -> None:
    """`centre` = `js_round` trung điểm mm của hộp; `rotationDeg == 0.0`."""
    detections = (DetectionPx(label="bed", box=BoxPx(x_min=100, y_min=100, x_max=301, y_max=500), confidence=0.9),)
    dropped: Counter[str] = Counter()
    items = build_furniture(detections, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert items[0].centre == Point(x=js_round((100 + 301) / 2), y=js_round((100 + 500) / 2))
    assert items[0].rotation_deg == 0.0


def test_opening_labels_are_skipped_without_counting(fake_clock: FakeClock) -> None:
    """Nhãn `door`/`double_door`/`window` bỏ qua, không sinh đồ, không đếm `dropped`."""
    detections = (DetectionPx(label="door", box=BoxPx(x_min=0, y_min=0, x_max=900, y_max=200), confidence=0.9),)
    dropped: Counter[str] = Counter()
    items = build_furniture(detections, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert items == ()
    assert sum(dropped.values()) == 0


def test_furniture_inside_room_gets_room_id(fake_clock: FakeClock) -> None:
    """Đồ có tâm trong phòng → `roomId` là id phòng đầu tiên (thứ tự `rooms`) chứa tâm."""
    room = _room(fake_clock, ((0, 0), (4000, 4000)))
    detections = (
        DetectionPx(label="chair", box=BoxPx(x_min=1000, y_min=1000, x_max=1600, y_max=1600), confidence=0.9),
    )
    dropped: Counter[str] = Counter()
    items = build_furniture(
        detections, (room,), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped
    )
    assert items[0].room_id == room.id


def test_room_label_tie_keeps_earlier_higher_confidence(fake_clock: FakeClock) -> None:
    """Hai chữ hợp lệ cùng phòng: chữ có `confidence` không cao hơn không thay chữ đã chọn."""
    walls = _grid_walls(fake_clock)
    texts = (
        TextPx(text="PHONG NGU", box=BoxPx(x_min=1000, y_min=1000, x_max=1400, y_max=1200), confidence=0.9),
        TextPx(text="BEP", box=BoxPx(x_min=1000, y_min=1300, x_max=1400, y_max=1500), confidence=0.9),
    )
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), texts, level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    named = next(r for r in rooms if r.usage in ("bedroom", "kitchen"))
    assert named.usage == "bedroom"


def test_no_walls_and_no_bridges_gives_no_rooms(fake_clock: FakeClock) -> None:
    """Không tường, không `bridges` → không đường nào để khép, không phòng."""
    dropped: Counter[str] = Counter()
    rooms = build_rooms([], (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert rooms == ()


def test_outline_points_drops_closing_point_that_rounds_onto_the_first() -> None:
    """Điểm cuối làm tròn trùng điểm đầu → bỏ (`rooms.py` nhánh `deduped.pop()`).

    `polygonize` cho vành đã khép, nhưng sau `js_round` điểm cuối có thể rơi đúng vào điểm đầu
    mà trước khi làm tròn thì không; khi ấy vành phải còn 3 điểm, không phải 4 điểm trùng đầu-cuối.
    """
    polygon = shapely.Polygon([(0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.4, 0.4)])
    assert _outline_points(polygon) == [
        Point(x=0, y=0),
        Point(x=1000, y=0),
        Point(x=1000, y=1000),
    ]
