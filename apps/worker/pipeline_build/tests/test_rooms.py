"""Test `rooms.build_rooms`, `rooms.build_furniture` (B5-05 [6] bước 5, 6; [8] mục Phòng, Đồ)."""

from collections import Counter
from collections.abc import Callable

import shapely

from apps.worker.pipeline_build.constants import ROOM_GAP_CLOSE_MM
from apps.worker.pipeline_build.geometry import Scaling
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.rooms import (
    _door_closers,
    _gap_closers,
    _outline_points,
    build_furniture,
    build_rooms,
    room_confidence,
)
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
    """Lưới 2 phòng → 2 phòng, `areaM2 == float(polygon_area_m2(outline))`, tên `phòng khác`/`phòng khác 2`."""
    walls = _grid_walls(fake_clock)
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 2
    assert [r.name for r in rooms] == ["phòng khác", "phòng khác 2"]
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


def _square_with_corner_gap(clock: FakeClock, gap: float) -> list[Wall]:
    """Phòng 4 m x 4 m, tường trái dừng cách góc (0, 0) `gap` mm, không hộp ô mở (BUG-IT-008)."""
    return [
        _wall(clock, (0, 0), (4000, 0)),
        _wall(clock, (4000, 0), (4000, 4000)),
        _wall(clock, (4000, 4000), (0, 4000)),
        _wall(clock, (0, 4000), (0, gap)),
    ]


def test_build_rooms__corner_gap_400_closes(fake_clock: FakeClock) -> None:
    """Khe góc chữ L 400 mm (> `ROOM_SNAP_MM`, ≤ `ROOM_GAP_CLOSE_MM`), không hộp → nối đầu tự do, 1 phòng 16 m²."""
    walls = _square_with_corner_gap(fake_clock, 400)
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1
    assert abs(rooms[0].area_m2 - 16.0) < 0.01


def test_build_rooms__corner_gap_over_limit_gives_no_room(fake_clock: FakeClock) -> None:
    """Khe góc `ROOM_GAP_CLOSE_MM` + 100 → không đoạn nối; khe ở mặt ngoài nên đường bao căn vẫn giữ phòng (không
    còn tường nào khác để khép)."""
    walls = _square_with_corner_gap(fake_clock, ROOM_GAP_CLOSE_MM + 100)
    assert _gap_closers(walls, ()) == []
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1


def test_build_rooms__t_junction_gap_closes(fake_clock: FakeClock) -> None:
    """Tường giữa dừng cách tường trên 500 mm (khe chữ T, không hộp) → nối tới tim tường trên, 2 phòng."""
    walls = [*_grid_walls(fake_clock)[:4], _wall(fake_clock, (3000, 500), (3000, 3000))]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 2


def test_build_rooms__closer_crossing_other_wall_not_added(fake_clock: FakeClock) -> None:
    """Đoạn nối khe góc 400 mm cắt tim một tường khác (y = 200) → bỏ; chỉ còn nối tới chính tường đó."""
    walls = [*_square_with_corner_gap(fake_clock, 400), _wall(fake_clock, (-500, 200), (200, 200))]
    assert all(min(y for _, y in closer.coords) > 150 for closer in _gap_closers(walls, ()))


def test_build_rooms__sideways_stub_does_not_split_room(fake_clock: FakeClock) -> None:
    """Vách cụt song song tường trên, cách 800 mm: nối ngang lệch 90° (< `ROOM_GAP_CLOSE_MIN_COS`) → vẫn 1 phòng.

    Hai đầu cách tường bên 2500 mm (> `ROOM_GAP_EVIDENCE_MM`): khe chữ T chĩa thẳng ≤ 2400 mm nay khép (QT-ROOMS3)."""
    walls = [*_grid_walls(fake_clock)[:4], _wall(fake_clock, (2500, 800), (3500, 800))]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1


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


def test_wall_ids_and_confidence_from_factors(fake_clock: FakeClock) -> None:
    """`wallIds` = 4 tường của phòng; `confidence` theo B12, không theo tường: không tên 0,4, kín, tỉ lệ tin."""
    walls = [
        _wall(fake_clock, (0, 0), (4000, 0), confidence=0.9),
        _wall(fake_clock, (4000, 0), (4000, 4000), confidence=0.8),
        _wall(fake_clock, (4000, 4000), (0, 4000), confidence=0.7),
        _wall(fake_clock, (0, 4000), (0, 0), confidence=0.6),
    ]
    dropped: Counter[str] = Counter()
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=dropped)
    assert len(rooms) == 1
    assert set(rooms[0].wall_ids) == {w.id for w in walls}
    assert rooms[0].confidence == 0.4


def test_room_confidence_factors() -> None:
    """B12: tích nguồn tên, max(0,5; 1 - phần khe), 0,7 khi tỉ lệ không tin."""
    assert room_confidence("text", 0.0, scale_trusted=True) == 1.0
    assert room_confidence("text", 0.3, scale_trusted=True) == 0.7
    assert room_confidence("inferred", 0.0, scale_trusted=False) == 0.42
    assert room_confidence("none", 0.9, scale_trusted=True) == 0.2


def test_labelled_room_confidence_drops_with_untrusted_scale(fake_clock: FakeClock) -> None:
    """Phòng kín có nhãn chữ: 1,0 khi tỉ lệ tin; `scale_trusted=False` → 0,7; mặc định theo `build != final`."""
    walls = _grid_walls(fake_clock)[:4]
    texts = (TextPx(text="PHONG NGU", box=BoxPx(x_min=1000, y_min=1000, x_max=1400, y_max=1200), confidence=0.85),)
    confidences = [
        room.confidence
        for scaling, trusted in ((_IDENTITY, None), (_IDENTITY, False), (Scaling(build=1.0, final=1.2), None))
        for room in build_rooms(
            walls,
            (),
            texts,
            level_id=LEVEL_ID,
            scaling=scaling,
            clock=fake_clock,
            dropped=Counter(),
            scale_trusted=trusted,
        )
    ]
    assert confidences == [1.0, 0.7, 0.7]


def test_build_rooms__aligned_gap_over_limit_closes(fake_clock: FakeClock) -> None:
    """Tường trên đứt 2000 mm (> `ROOM_GAP_CLOSE_MM`), hai đoạn thẳng hàng → khép (B9), 1 phòng 16 m², tin < 1."""
    walls = [
        _wall(fake_clock, (0, 0), (1000, 0)),
        _wall(fake_clock, (3000, 0), (4000, 0)),
        _wall(fake_clock, (4000, 0), (4000, 4000)),
        _wall(fake_clock, (4000, 4000), (0, 4000)),
        _wall(fake_clock, (0, 4000), (0, 0)),
    ]
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter())
    assert len(rooms) == 1
    assert abs(rooms[0].area_m2 - 16.0) < 0.01
    assert rooms[0].confidence < 0.4


def test_build_rooms__corner_gap_over_limit_closes_with_opening(fake_clock: FakeClock) -> None:
    """Khe góc 2000 mm không thẳng hàng: hộp cửa đi trong khe → khép (`_door_closers`); không hộp → không đoạn nối."""
    door = DetectionPx(label="door", box=BoxPx(x_min=0, y_min=0, x_max=100, y_max=2000), confidence=0.9)
    walls = _square_with_corner_gap(fake_clock, 2000)
    assert _gap_closers(walls, ()) == []
    assert [len(_door_closers(walls, boxes, _IDENTITY)) for boxes in ((door,), ())] == [1, 0]
    rooms = build_rooms(
        walls, (), (), detections=(door,), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter()
    )
    assert len(rooms) == 1


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


def _box(x0: float, y0: float, x1: float, y1: float) -> BoxPx:
    """Hộp px (ở `_IDENTITY` cũng là mm)."""
    return BoxPx(x_min=x0, y_min=y0, x_max=x1, y_max=y1)


def _text(text: str, x: float, y: float, confidence: float = 0.9) -> TextPx:
    """Chữ OCR hộp 400 x 200 tâm `(x, y)`."""
    return TextPx(text=text, box=_box(x - 200, y - 100, x + 200, y + 100), confidence=confidence)


def _usages(
    walls: list[Wall], texts: tuple[TextPx, ...], detections: tuple[DetectionPx, ...], clock: FakeClock
) -> list[str]:
    """`usage` các phòng theo thứ tự (y, x) của `build_rooms`."""
    rooms = build_rooms(
        walls, (), texts, detections=detections, level_id=LEVEL_ID, scaling=_IDENTITY, clock=clock, dropped=Counter()
    )
    return [room.usage for room in rooms]


def test_fixtures_name_unlabelled_rooms(fake_clock: FakeClock) -> None:
    """Không có chữ: thiết bị vệ sinh trong phòng 9 m² → phòng tắm; dãy tủ bếp 2,4 m → bếp."""
    detections = (
        DetectionPx(label="sanitary_fixture", box=_box(500, 500, 900, 900), confidence=0.8),
        DetectionPx(label="kitchen_cabinet", box=_box(3200, 200, 5600, 800), confidence=0.8),
    )
    assert _usages(_grid_walls(fake_clock), (), detections, fake_clock) == ["bathroom", "kitchen"]


def test_shower_names_bathroom_and_washer_names_loggia(fake_clock: FakeClock) -> None:
    """Buồng tắm đứng trong phòng 9 m² → phòng tắm; máy giặt (không thiết bị vệ sinh) → lô-gia."""
    detections = (
        DetectionPx(label="shower", box=_box(500, 500, 1400, 1400), confidence=0.8),
        DetectionPx(label="washing_machine", box=_box(3500, 500, 4100, 1100), confidence=0.8),
    )
    assert _usages(_grid_walls(fake_clock), (), detections, fake_clock) == ["bathroom", "loggia"]


def _nine_grid(clock: FakeClock) -> list[Wall]:
    """Lưới 3 x 3 phòng 3 x 3 m; phòng giữa (thứ 5 theo (y, x)) không chạm mặt ngoài."""
    rows = [((0, k), (9000, k)) for k in (0, 3000, 6000, 9000)]
    columns = [((k, 0), (k, 9000)) for k in (0, 3000, 6000, 9000)]
    return [_wall(clock, start, end) for start, end in [*rows, *columns]]


def test_washer_in_bathroom_keeps_bathroom(fake_clock: FakeClock) -> None:
    """Máy giặt đặt trong WC giữa nhà (thường gặp ở căn hộ VN) không đổi phòng tắm thành lô-gia."""
    detections = (
        DetectionPx(label="sanitary_fixture", box=_box(3500, 3500, 3900, 3900), confidence=0.8),
        DetectionPx(label="washing_machine", box=_box(4500, 3500, 5100, 4100), confidence=0.8),
    )
    assert _usages(_nine_grid(fake_clock), (), detections, fake_clock)[4] == "bathroom"


def test_washer_and_sink_on_the_facade_name_loggia(fake_clock: FakeClock) -> None:
    """Lô gia mặt ngoài: chậu giặt (dò thành thiết bị vệ sinh) + máy giặt → lô gia; có buồng tắm đứng → phòng tắm."""
    sink = DetectionPx(label="sanitary_fixture", box=_box(3500, 500, 3900, 900), confidence=0.8)
    washer = DetectionPx(label="washing_machine", box=_box(4500, 500, 5100, 1100), confidence=0.8)
    shower = DetectionPx(label="shower", box=_box(4500, 2000, 5300, 2800), confidence=0.8)
    assert _usages(_grid_walls(fake_clock), (), (sink, washer), fake_clock)[1] == "loggia"
    assert _usages(_grid_walls(fake_clock), (), (sink, washer, shower), fake_clock)[1] == "bathroom"


def _bedroom_and_side_room(clock: FakeClock) -> list[Wall]:
    """Hộp 5 x 2,5 m chia ở x = 3 m: phòng trái 7,5 m², phòng phải 2 x 2,5 m = 5 m² (cả hai trên mặt ngoài)."""
    segments = [((0, 0), (5000, 0)), ((0, 2500), (5000, 2500)), ((0, 0), (0, 2500)), ((5000, 0), (5000, 2500))]
    return [_wall(clock, start, end) for start, end in [*segments, ((3000, 0), (3000, 2500))]]


def test_unlabelled_facade_room_becomes_loggia_unless_it_has_a_bed(fake_clock: FakeClock) -> None:
    """Tầng có nhãn chữ: phòng không tên 5 m² có ≥ 3 m mặt ngoài → lô gia (nguồn suy); có giường → không.

    Tầng không có nhãn chữ nào thì không đoán (`test_grid_gives_two_rooms_with_matching_area`).
    """
    texts = (_text("PHONG NGU", 1500, 1250),)
    rooms = _rooms_with_texts(_bedroom_and_side_room(fake_clock), texts, (), fake_clock)
    assert [(room.usage, room.name) for room in rooms] == [("bedroom", "phòng ngủ"), ("loggia", "lô gia")]
    assert rooms[1].confidence < rooms[0].confidence
    bed = (DetectionPx(label="bed", box=_box(3200, 200, 4800, 2300), confidence=0.9),)
    assert _usages(_bedroom_and_side_room(fake_clock), texts, bed, fake_clock) == ["bedroom", "other"]


def _rooms_with_texts(
    walls: list[Wall], texts: tuple[TextPx, ...], detections: tuple[DetectionPx, ...], clock: FakeClock
) -> tuple[Room, ...]:
    """`build_rooms` ở `_IDENTITY` với chữ và đồ đạc."""
    return build_rooms(
        walls, (), texts, detections=detections, level_id=LEVEL_ID, scaling=_IDENTITY, clock=clock, dropped=Counter()
    )


def test_bed_in_a_merged_region_over_25_m2_is_not_a_bedroom(fake_clock: FakeClock) -> None:
    """Vùng gộp khách-bếp 40 m² có giường (bench-3d cn-19) không thành phòng ngủ."""
    walls = [
        _wall(fake_clock, (0, 0), (8000, 0)),
        _wall(fake_clock, (0, 5000), (8000, 5000)),
        _wall(fake_clock, (0, 0), (0, 5000)),
        _wall(fake_clock, (8000, 0), (8000, 5000)),
    ]
    bed = (DetectionPx(label="bed", box=_box(500, 500, 2100, 2500), confidence=0.9),)
    assert _usages(walls, (), bed, fake_clock) == ["other"]


def test_wardrobe_alone_in_7_m2_is_not_a_bedroom(fake_clock: FakeClock) -> None:
    """Tủ áo trong phòng 3,5 x 2 m = 7 m² (kho, phòng thay đồ: bench-3d ch-06, cn-05) không thành phòng ngủ."""
    walls = [
        _wall(fake_clock, (0, 0), (3500, 0)),
        _wall(fake_clock, (0, 2000), (3500, 2000)),
        _wall(fake_clock, (0, 0), (0, 2000)),
        _wall(fake_clock, (3500, 0), (3500, 2000)),
    ]
    wardrobe = (DetectionPx(label="wardrobe", box=_box(500, 500, 1500, 1100), confidence=0.8),)
    assert _usages(walls, (), wardrobe, fake_clock) == ["other"]


def test_short_cabinet_and_big_wardrobe_room_name_nothing(fake_clock: FakeClock) -> None:
    """Tủ bếp ngắn (lavabo 1 m) không là bếp; thiết bị vệ sinh ở phòng > 10 m² không là phòng tắm."""
    walls = [
        _wall(fake_clock, (0, 0), (8000, 0)),
        _wall(fake_clock, (0, 4000), (8000, 4000)),
        _wall(fake_clock, (0, 0), (0, 4000)),
        _wall(fake_clock, (8000, 0), (8000, 4000)),
    ]
    detections = (
        DetectionPx(label="kitchen_cabinet", box=_box(500, 500, 1500, 1000), confidence=0.8),
        DetectionPx(label="sanitary_fixture", box=_box(2000, 500, 2400, 900), confidence=0.8),
    )
    assert _usages(walls, (), detections, fake_clock) == ["other"]


def test_wardrobe_names_bedroom_only_in_bedroom_sizes(fake_clock: FakeClock) -> None:
    """Tủ áo trong phòng 9 m² → phòng ngủ; trong phòng 32 m² (phòng khách có kệ) → không."""
    big = [
        _wall(fake_clock, (0, 0), (8000, 0)),
        _wall(fake_clock, (0, 4000), (8000, 4000)),
        _wall(fake_clock, (0, 0), (0, 4000)),
        _wall(fake_clock, (8000, 0), (8000, 4000)),
    ]
    wardrobe = (DetectionPx(label="wardrobe", box=_box(500, 500, 1500, 1100), confidence=0.8),)
    assert _usages(_grid_walls(fake_clock), (), wardrobe, fake_clock)[0] == "bedroom"
    assert _usages(big, (), wardrobe, fake_clock) == ["other"]


def test_bed_names_bedroom_before_a_stray_sanitary_fixture(fake_clock: FakeClock) -> None:
    """Giường + thiết bị vệ sinh dò nhầm trong phòng 9 m² → phòng ngủ, không phải phòng tắm (H-08)."""
    detections = (
        DetectionPx(label="bed", box=_box(500, 500, 2100, 2500), confidence=0.9),
        DetectionPx(label="sanitary_fixture", box=_box(2300, 2300, 2700, 2700), confidence=0.3),
    )
    assert _usages(_grid_walls(fake_clock), (), detections, fake_clock)[0] == "bedroom"


def test_short_cabinet_with_dining_set_names_kitchen_not_bedroom(fake_clock: FakeClock) -> None:
    """Khu khách-bếp 32 m²: tủ bếp 1,8 m + bàn ăn + kệ dò thành tủ áo → bếp, không phải phòng ngủ (H-08); rộng hơn
    `_OPEN_SPACE_M2` trên tầng chưa có phòng khách nên thành phòng khách."""
    walls = [
        _wall(fake_clock, (0, 0), (8000, 0)),
        _wall(fake_clock, (0, 4000), (8000, 4000)),
        _wall(fake_clock, (0, 0), (0, 4000)),
        _wall(fake_clock, (8000, 0), (8000, 4000)),
    ]
    detections = (
        DetectionPx(label="kitchen_cabinet", box=_box(500, 500, 2300, 1100), confidence=0.9),
        DetectionPx(label="table", box=_box(3000, 1500, 4400, 2300), confidence=0.7),
        DetectionPx(label="wardrobe", box=_box(6000, 3000, 6600, 3600), confidence=0.6),
    )
    assert _usages(walls, (), detections, fake_clock) == ["livingRoom"]


def test_text_label_wins_over_fixtures(fake_clock: FakeClock) -> None:
    """Chữ `PHONG NGU` thắng thiết bị vệ sinh cùng phòng (WC riêng trong phòng ngủ)."""
    texts = (_text("PHONG NGU", 1500, 1500),)
    detections = (DetectionPx(label="sanitary_fixture", box=_box(500, 500, 900, 900), confidence=0.8),)
    assert _usages(_grid_walls(fake_clock), texts, detections, fake_clock)[0] == "bedroom"


def test_main_usage_wins_among_labels_of_one_room(fake_clock: FakeClock) -> None:
    """Không gian mở có `TIEN SANH` (0,99) và `PHONG KHACH` (0,7) → phòng khách, không phải hành lang."""
    texts = (_text("TIEN SANH", 1000, 1000, 0.99), _text("PHONG KHACH", 2000, 2000, 0.7))
    assert _usages(_grid_walls(fake_clock), texts, (), fake_clock)[0] == "livingRoom"


def test_label_outside_closed_rooms_seeds_a_loggia(fake_clock: FakeClock) -> None:
    """Lô gia ba mặt tường, mặt ngoài là lan can (không tường): nhãn `LO GIA` dựng phòng tới biên bao của tường.

    Hai phòng 3 x 3 m; trên mỗi phòng một dải 1,5 m chỉ có tường dưới (chung) và tường bên, mặt trên là lan can.
    """
    segments = [
        ((0, 1500), (6000, 1500)),
        ((0, 4500), (6000, 4500)),
        ((0, 0), (0, 4500)),
        ((6000, 0), (6000, 4500)),
        ((3000, 0), (3000, 4500)),
    ]
    walls = [_wall(fake_clock, start, end) for start, end in segments]
    rooms = build_rooms(
        walls,
        (),
        (_text("LO GIA", 4500, 750),),
        level_id=LEVEL_ID,
        scaling=_IDENTITY,
        clock=fake_clock,
        dropped=Counter(),
    )
    loggia = next(room for room in rooms if room.usage == "loggia" and min(p.x for p in room.outline) >= 3000)
    assert loggia.name.startswith("lô gia")
    assert loggia.area_m2 == 4.95  # 3 x 1,65 m: biên bao lồi của tường đã kéo dài `ROOM_SNAP_MM` 150 mm


def test_label_with_an_open_side_seeds_nothing(fake_clock: FakeClock) -> None:
    """Nhãn ngoài biên bao lồi của tường (tên bản vẽ, ghi chú) không dựng phòng."""
    texts = (_text("PHONG NGU", 1500, 9000),)
    assert len(_usages(_grid_walls(fake_clock), texts, (), fake_clock)) == 2


def _rooms_of(walls: list[Wall], detections: tuple[DetectionPx, ...], clock: FakeClock) -> tuple[Room, ...]:
    """`build_rooms` không chữ, `_IDENTITY`."""
    return build_rooms(
        walls, (), (), detections=detections, level_id=LEVEL_ID, scaling=_IDENTITY, clock=clock, dropped=Counter()
    )


def test_door_box_closes_gap_between_a_corner_and_a_wall(fake_clock: FakeClock) -> None:
    """Vách giữa dừng ở góc chữ L cách tường trên 900 mm (đầu ở góc, không tự do): hộp cửa lệch tim 70 mm vẫn khép."""
    segments = [
        ((0, 0), (6000, 0)),
        ((0, 3000), (6000, 3000)),
        ((0, 0), (0, 3000)),
        ((6000, 0), (6000, 3000)),
        ((3000, 900), (3000, 3000)),
        ((2500, 900), (3000, 900)),  # cách tường trái 2500 mm > `ROOM_GAP_EVIDENCE_MM`: khe chữ T không khép
    ]
    walls = [_wall(fake_clock, start, end) for start, end in segments]
    door = (DetectionPx(label="door", box=_box(2900, 100, 2960, 800), confidence=0.7),)
    assert len(_rooms_of(walls, (), fake_clock)) == 1
    assert len(_rooms_of(walls, door, fake_clock)) == 2


def test_window_box_closes_glass_partition_from_a_stub_inside_it(fake_clock: FakeClock) -> None:
    """Vách kính y = 2000 chỉ còn mẩu tường 0-500 nằm trong hộp cửa sổ (tâm hộp ở phía thân tường): vẫn khép tới
    tường phải 3000 (bench căn hộ ch-08, phòng ngủ tràn ra lô gia)."""
    segments = [
        ((0, 0), (3000, 0)),
        ((0, 5000), (3000, 5000)),
        ((0, 0), (0, 5000)),
        ((3000, 0), (3000, 5000)),
        ((0, 2000), (500, 2000)),
    ]
    walls = [_wall(fake_clock, start, end) for start, end in segments]
    window = (DetectionPx(label="window", box=_box(0, 1950, 3000, 2050), confidence=0.7),)
    assert len(_rooms_of(walls, (), fake_clock)) == 1
    assert len(_rooms_of(walls, window, fake_clock)) == 2


def test_walled_rim_strip_becomes_a_loggia(fake_clock: FakeClock) -> None:
    """Dải 3 x 1,5 m trên phòng phải có tường dưới và hai bên, không nhãn: thành `lô gia` (mặt trên là lan can)."""
    segments = [
        ((0, 1500), (6000, 1500)),
        ((0, 4500), (6000, 4500)),
        ((0, 1500), (0, 4500)),
        ((6000, 0), (6000, 4500)),
        ((3000, 0), (3000, 4500)),
    ]
    rooms = _rooms_of([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
    loggias = [room for room in rooms if room.usage == "loggia"]
    assert [room.name for room in loggias] == ["lô gia"]
    assert loggias[0].area_m2 == 4.5  # đường bao căn qua đầu tường bên; biên bao lồi của `_rim_outlines` lố 150 mm


def test_hull_notch_walled_on_two_sides_is_not_a_room(fake_clock: FakeClock) -> None:
    """Mặt bằng chữ L: góc khuyết 3 x 3 m trong biên bao chỉ sát tường hai mặt → không dựng lô gia."""
    segments = [
        ((0, 0), (6000, 0)),
        ((0, 0), (0, 6000)),
        ((6000, 0), (6000, 3000)),
        ((3000, 3000), (6000, 3000)),
        ((3000, 3000), (3000, 6000)),
        ((0, 6000), (3000, 6000)),
        ((0, 3000), (3000, 3000)),
    ]
    rooms = _rooms_of([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
    assert [room.usage for room in rooms] == ["other", "other"]


def _room_with_stub(clock: FakeClock) -> list[Wall]:
    """Hộp 8 x 5 m, vách cụt từ tường trên xuống 3 m giữa phòng (khe 2 m > `ROOM_GAP_CLOSE_MM`, không tự khép)."""
    corners = [(0, 0), (8000, 0), (8000, 5000), (0, 5000)]
    walls = [_wall(clock, a, b) for a, b in zip(corners, corners[1:] + corners[:1], strict=True)]
    return [*walls, _wall(clock, (4000, 0), (4000, 3000))]


def test_two_labels_split_room_along_stub_wall(fake_clock: FakeClock) -> None:
    """UX-04: hai nhãn tên phòng trong một vùng → cắt dọc vách cụt kéo dài; một nhãn thì không cắt."""
    texts = (_text("phòng khách", 2000, 2500), _text("bếp", 6000, 2500))
    assert sorted(_usages(_room_with_stub(fake_clock), texts, (), fake_clock)) == ["kitchen", "livingRoom"]
    assert _usages(_room_with_stub(fake_clock), texts[:1], (), fake_clock) == ["livingRoom"]


def _square(clock: FakeClock, side: int) -> list[Wall]:
    """Một phòng vuông cạnh `side` mm."""
    return [
        _wall(clock, (0, 0), (side, 0)),
        _wall(clock, (0, side), (side, side)),
        _wall(clock, (0, 0), (0, side)),
        _wall(clock, (side, 0), (side, side)),
    ]


def test_wardrobe_with_washer_or_short_wardrobe_is_not_bedroom(fake_clock: FakeClock) -> None:
    """Tủ áo cạnh máy giặt/thiết bị vệ sinh (phòng 16 m²) hay tủ áo ngắn < 900 mm không làm phòng ngủ."""
    wardrobe = DetectionPx(label="wardrobe", box=_box(500, 500, 1500, 1100), confidence=0.8)
    washer = DetectionPx(label="washing_machine", box=_box(2000, 500, 2600, 1100), confidence=0.8)
    toilet = DetectionPx(label="sanitary_fixture", box=_box(2000, 2000, 2400, 2400), confidence=0.8)
    short = DetectionPx(label="wardrobe", box=_box(500, 500, 1100, 1100), confidence=0.8)
    walls = _square(fake_clock, 4000)
    assert _usages(walls, (), (wardrobe,), fake_clock) == ["bedroom"]
    assert _usages(walls, (), (wardrobe, washer), fake_clock) == ["other"]
    assert _usages(walls, (), (wardrobe, toilet), fake_clock) == ["other"]
    assert _usages(walls, (), (short,), fake_clock) == ["other"]


def test_furniture_goes_to_room_with_largest_overlap(fake_clock: FakeClock) -> None:
    """B8: tâm hộp trên biên A (theo tâm: không phòng) nhưng hộp giao phòng A nhất → phòng A, không `suggested`."""
    room_a = _room(fake_clock, ((0, 0), (4000, 4000)))
    room_b = _room(fake_clock, ((4000, 0), (8000, 1000)))
    detections = (DetectionPx(label="table", box=_box(3000, 0, 5000, 4000), confidence=0.9),)
    items = build_furniture(
        detections, (room_a, room_b), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter()
    )
    assert (items[0].room_id, items[0].suggested) == (room_a.id, False)


def test_furniture_outside_the_flat_is_suggested(fake_clock: FakeClock) -> None:
    """B8: đồ xa căn (sơ đồ vị trí) → `suggested`, không xoá; đồ sát mép phòng trong 300 mm → giữ."""
    room = _room(fake_clock, ((0, 0), (1000, 1000)))
    detections = (
        DetectionPx(label="table", box=_box(5000, 5000, 5600, 5600), confidence=0.9),
        DetectionPx(label="table", box=_box(1050, 0, 1450, 400), confidence=0.9),
    )
    items = build_furniture(
        detections, (room,), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter()
    )
    assert [item.suggested for item in items] == [True, False]


def test_gap_closers__long_t_gap_closes_only_head_on(fake_clock: FakeClock) -> None:
    """QT-ROOMS3 (NO-435): tường giữa dừng cách tường trên 1800 mm (> `ROOM_GAP_CLOSE_MM`), chĩa thẳng vào nó → một
    đoạn nối 1800 mm; vách chĩa chéo (chân đoạn lệch ngang) hay góc chữ L hở hai đầu tự do → không nối."""
    frame = _grid_walls(fake_clock)[:4]
    head_on = _gap_closers([*frame, _wall(fake_clock, (3000, 1800), (3000, 3000))], ())
    slanted = _gap_closers([*frame, _wall(fake_clock, (3000, 1800), (4000, 3000))], ())
    open_corner = _gap_closers(_square_with_corner_gap(fake_clock, 2000), ())
    assert [round(line.length) for line in head_on] == [1801]
    assert slanted == []
    assert open_corner == []


def _fragment_walls(clock: FakeClock) -> list[Wall]:
    """Phòng 4 m x 4 m, góc phải dưới có ô 1 m x 1,5 m (1,5 m²) ngăn bằng một tường dọc và một `bridges` ngang."""
    return [
        _wall(clock, (0, 0), (4000, 0)),
        _wall(clock, (4000, 0), (4000, 4000)),
        _wall(clock, (4000, 4000), (0, 4000)),
        _wall(clock, (0, 4000), (0, 0)),
        _wall(clock, (3000, 0), (3000, 1500)),
    ]


_FRAGMENT_BRIDGE = ((Point(x=3000, y=1500), Point(x=4000, y=1500)),)


def test_build_rooms__unlabelled_fragment_merges_across_bridge(fake_clock: FakeClock) -> None:
    """QT-ROOMS3: mảnh 1,5 m² không nhãn chung với phòng lớn 1 m cạnh chỉ có `bridges` (vách ảo) → gộp, 16 m²."""
    rooms = build_rooms(
        _fragment_walls(fake_clock),
        _FRAGMENT_BRIDGE,
        (),
        level_id=LEVEL_ID,
        scaling=_IDENTITY,
        clock=fake_clock,
        dropped=Counter(),
    )
    assert [round(room.area_m2, 2) for room in rooms] == [16.0]
    assert rooms[0].area_m2 == float(polygon_area_m2(rooms[0].outline))


def test_build_rooms__labelled_or_walled_fragment_is_kept(fake_clock: FakeClock) -> None:
    """QT-ROOMS3: mảnh nhỏ có nhãn chữ ("WC") giữ dù chung vách ảo; mảnh không nhãn mà cạnh chung là tường thật giữ."""
    wc = (TextPx(text="WC", box=BoxPx(x_min=3400, y_min=600, x_max=3600, y_max=800), confidence=0.9),)
    labelled = build_rooms(
        _fragment_walls(fake_clock),
        _FRAGMENT_BRIDGE,
        wc,
        level_id=LEVEL_ID,
        scaling=_IDENTITY,
        clock=fake_clock,
        dropped=Counter(),
    )
    walled = build_rooms(
        [*_fragment_walls(fake_clock), _wall(fake_clock, (3000, 1500), (4000, 1500))],
        (),
        (),
        level_id=LEVEL_ID,
        scaling=_IDENTITY,
        clock=fake_clock,
        dropped=Counter(),
    )
    assert sorted(round(room.area_m2, 2) for room in labelled) == [1.5, 14.5]
    assert sorted(round(room.area_m2, 2) for room in walled) == [1.5, 14.5]


def test_build_rooms__sliver_merges_into_longest_shared_side(fake_clock: FakeClock) -> None:
    """QT-ROOMS3: dải 6 m x 0,3 m (1,8 m², rộng < `_SLIVER_WIDTH_MM`) kín tường → gộp vào phòng kề, 1 phòng."""
    walls = [*_grid_walls(fake_clock)[:4], _wall(fake_clock, (0, 300), (6000, 300))]
    rooms = build_rooms(walls, (), (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter())
    assert [round(room.area_m2, 2) for room in rooms] == [18.0]


def test_build_rooms__fragment_closing_a_ring_is_kept(fake_clock: FakeClock) -> None:
    """QT-ROOMS3: gộp mảnh 2 m² vào phòng chữ C quanh một phòng giữa sẽ thành vành có lỗ → bỏ gộp, giữ 3 phòng."""
    outer = [(0, 0), (6000, 0), (6000, 6000), (0, 6000)]
    inner = [(2000, 2000), (4000, 2000), (4000, 4000), (2000, 4000)]
    walls = [
        *(_wall(fake_clock, a, b) for a, b in zip(outer, outer[1:] + outer[:1], strict=True)),
        *(_wall(fake_clock, a, b) for a, b in zip(inner, inner[1:] + inner[:1], strict=True)),
        _wall(fake_clock, (2500, 4000), (2500, 6000)),
    ]
    bridges = ((Point(x=3500, y=4000), Point(x=3500, y=6000)),)
    rooms = build_rooms(walls, bridges, (), level_id=LEVEL_ID, scaling=_IDENTITY, clock=fake_clock, dropped=Counter())
    assert sorted(round(room.area_m2, 2) for room in rooms) == [2.0, 4.0, 30.0]


def test_small_room_without_a_door_is_a_shaft(fake_clock: FakeClock) -> None:
    """Ô 1 x 1,2 m không cửa giữa tường → `utility` "hộp kỹ thuật"; ô 1 x 2,2 m có hộp cửa đi → giữ "phòng khác"."""
    shaft = _rooms_of(_box_room(fake_clock, 1200), (), fake_clock)
    assert [(room.usage, room.name) for room in shaft] == [("utility", "hộp kỹ thuật")]
    door = (DetectionPx(label="door", box=_box(1000, 600, 1100, 1400), confidence=0.9),)
    closet = _rooms_of(_box_room(fake_clock, 2200), door, fake_clock)
    assert [(room.usage, room.name) for room in closet] == [("other", "phòng khác")]


def _box_room(clock: FakeClock, depth: int) -> list[Wall]:
    """Phòng 1000 x `depth` mm."""
    corners = [(0, 0), (1000, 0), (1000, depth), (0, depth)]
    return [_wall(clock, a, b) for a, b in zip(corners, corners[1:] + corners[:1], strict=True)]


def _walls_of(clock: FakeClock, segments: list[tuple[tuple[int, int], tuple[int, int]]]) -> list[Wall]:
    """Tường tay từ danh sách đoạn."""
    return [_wall(clock, start, end) for start, end in segments]


def test_narrow_facade_room_is_a_loggia_on_a_level_named_only_by_fixtures(fake_clock: FakeClock) -> None:
    """Tầng không chữ, có giường: phòng 2 x 2,5 m mặt ngoài → lô gia; sâu 2,5 m thì không (kho, phòng phụ)."""
    bed = (DetectionPx(label="bed", box=_box(500, 200, 2100, 2300), confidence=0.9),)
    assert _usages(_bedroom_and_side_room(fake_clock), (), bed, fake_clock) == ["bedroom", "loggia"]
    deep = _walls_of(
        fake_clock,
        [
            ((0, 0), (5500, 0)),
            ((0, 3000), (5500, 3000)),
            ((0, 0), (0, 3000)),
            ((5500, 0), (5500, 3000)),
            ((3000, 0), (3000, 3000)),
        ],
    )
    assert _usages(deep, (), bed, fake_clock) == ["bedroom", "other"]


def test_recessed_loggia_off_the_convex_hull_is_found_by_its_exposed_side(fake_clock: FakeClock) -> None:
    """Lô gia 4 x 1,3 m lõm vào giữa mặt nhà (cách biên bao lồi > 300 mm): cạnh 4 m không giáp phòng nào → lô gia."""
    walls = _walls_of(
        fake_clock,
        [
            ((0, 0), (10000, 0)),
            ((0, 4000), (3000, 4000)),
            ((7000, 4000), (10000, 4000)),
            ((0, 0), (0, 4000)),
            ((10000, 0), (10000, 4000)),
            ((3000, 0), (3000, 4000)),
            ((7000, 0), (7000, 4000)),
            ((3000, 2500), (7000, 2500)),
            ((3000, 3800), (7000, 3800)),
        ],
    )
    beds = tuple(DetectionPx(label="bed", box=_box(x, 500, x + 1600, 2600), confidence=0.9) for x in (500, 7500))
    assert _usages(walls, (), beds, fake_clock) == ["bedroom", "other", "bedroom", "loggia"]


def _two_20_m2_rooms(clock: FakeClock) -> list[Wall]:
    """Hai phòng 5 x 4 m = 20 m² cạnh nhau."""
    return _walls_of(
        clock,
        [
            ((0, 0), (10000, 0)),
            ((0, 4000), (10000, 4000)),
            ((0, 0), (0, 4000)),
            ((10000, 0), (10000, 4000)),
            ((5000, 0), (5000, 4000)),
        ],
    )


def test_wide_kitchen_or_hall_is_the_living_room_unless_the_level_has_one(fake_clock: FakeClock) -> None:
    """Tầng chưa có phòng khách: "bếp" 20 m² (dãy tủ bếp) và "sảnh" 20 m² → phòng khách; đã có thì giữ bếp."""
    run = (DetectionPx(label="kitchen_cabinet", box=_box(200, 200, 2600, 800), confidence=0.8),)
    rooms = _rooms_with_texts(_two_20_m2_rooms(fake_clock), (), run, fake_clock)
    assert [(room.usage, room.name) for room in rooms] == [("livingRoom", "phòng khách"), ("other", "phòng khác")]
    hall = (_text("SANH", 7500, 2000),)
    lobby = _rooms_with_texts(_two_20_m2_rooms(fake_clock), hall, (), fake_clock)
    assert [room.usage for room in lobby] == ["other", "livingRoom"]
    assert lobby[1].confidence < 1.0  # tên trái chữ trên bản vẽ là suy đoán, không mang tin cậy của chữ
    living = (_text("PHONG KHACH", 7500, 2000),)
    assert _usages(_two_20_m2_rooms(fake_clock), living, run, fake_clock) == ["kitchen", "livingRoom"]


def test_largest_unnamed_room_of_a_read_level_is_the_living_room(fake_clock: FakeClock) -> None:
    """Tầng có phòng ngủ (giường) mà không phòng khách: phòng không tên 20 m² → phòng khách; tầng chưa đọc được gì
    thì giữ "phòng khác" (`test_bed_in_a_merged_region_over_25_m2_is_not_a_bedroom`)."""
    walls = _walls_of(
        fake_clock,
        [
            ((0, 0), (8000, 0)),
            ((0, 4000), (8000, 4000)),
            ((0, 0), (0, 4000)),
            ((8000, 0), (8000, 4000)),
            ((3000, 0), (3000, 4000)),
        ],
    )
    bed = (DetectionPx(label="bed", box=_box(500, 500, 2100, 2600), confidence=0.9),)
    rooms = _rooms_with_texts(walls, (), bed, fake_clock)
    assert [room.usage for room in rooms] == ["bedroom", "livingRoom"]
    assert rooms[1].confidence < 1.0


def test_long_narrow_hall_stays_a_hall(fake_clock: FakeClock) -> None:
    """Hành lang 14 x 1,5 m = 21 m² có chữ, tầng không phòng khách: hẹp nên vẫn là hành lang, tin cậy của chữ."""
    walls = _box_walls(fake_clock, 14000, 1500)
    rooms = _rooms_with_texts(walls, (_text("HANH LANG", 7000, 750),), (), fake_clock)
    assert [(room.usage, room.name) for room in rooms] == [("corridor", "hành lang")]
    assert rooms[0].confidence == 1.0


def test_level_named_only_by_geometry_gets_no_living_room_guess(fake_clock: FakeClock) -> None:
    """Không chữ, không đồ: hộp kỹ thuật 2 m² (chỉ suy từ hình học) không làm tầng "đã đọc được", phòng 20 m² vẫn
    là "phòng khác"."""
    walls = _walls_of(
        fake_clock,
        [
            ((0, 0), (6000, 0)),
            ((0, 4000), (5000, 4000)),
            ((0, 0), (0, 4000)),
            ((5000, 0), (5000, 4000)),
            ((6000, 0), (6000, 2000)),
            ((5000, 2000), (6000, 2000)),
        ],
    )
    rooms = _rooms_with_texts(walls, (), (), fake_clock)
    assert [(room.usage, room.name) for room in rooms] == [("other", "phòng khác"), ("utility", "hộp kỹ thuật")]


def _box_walls(clock: FakeClock, width: int, depth: int) -> list[Wall]:
    """Phòng hộp `width` x `depth` mm."""
    corners = [(0, 0), (width, 0), (width, depth), (0, depth)]
    return [_wall(clock, a, b) for a, b in zip(corners, corners[1:] + corners[:1], strict=True)]


def _rooms_with(
    walls: list[Wall], texts: tuple[TextPx, ...], clock: FakeClock, *detections: DetectionPx
) -> tuple[Room, ...]:
    """`build_rooms` với chữ và hộp dò, `_IDENTITY`."""
    return build_rooms(
        walls, (), texts, detections=detections, level_id=LEVEL_ID, scaling=_IDENTITY, clock=clock, dropped=Counter()
    )


def _holding(rooms: tuple[Room, ...], x: float, y: float) -> list[Room]:
    """Phòng chứa điểm `(x, y)`."""
    point = shapely.Point(x, y)
    return [room for room in rooms if shapely.Polygon([(p.x, p.y) for p in room.outline]).contains(point)]


def _open_corner_living(clock: FakeClock) -> list[Wall]:
    """Khách 10 x 6 m hở góc dưới phải (tường dưới dừng ở 8 m, tường phải ở 4 m: góc chữ L hở hai đầu tự do,
    `_gap_closers` không khép) — vách kính góc mà model tường bỏ sót."""
    segments = [((0, 0), (10000, 0)), ((0, 0), (0, 6000)), ((0, 6000), (8000, 6000)), ((10000, 0), (10000, 4000))]
    return [_wall(clock, start, end) for start, end in segments]


def test_envelope__living_over_40_m2_open_to_the_facade_is_kept(fake_clock: FakeClock) -> None:
    """Không gian khách 60 m² hở mặt ngoài: không nhãn vẫn thành phòng; nhãn khách (hạt > 40 m²) đặt đúng tên."""
    walls = _open_corner_living(fake_clock)
    rooms = _rooms_with(walls, (), fake_clock)
    assert len(rooms) == 1
    assert _holding(rooms, 5000, 3000) == list(rooms)
    assert 55 < rooms[0].area_m2 < 61
    named = _rooms_with(walls, (_text("PHONG KHACH", 5000, 3000),), fake_clock)
    assert [room.usage for room in named] == ["livingRoom"]


def test_envelope__open_court_wider_than_closing_stays_outside(fake_clock: FakeClock) -> None:
    """Mặt bằng chữ U 14 x 9 m, sân hở 5 x 4 m ở cạnh trên (rộng hơn 2·`_ENVELOPE_CLOSE_MM`): sân không thành phòng,
    khách hở góc dưới phải vẫn dựng và không ôm sân."""
    segments = [
        ((0, 0), (4500, 0)),
        ((9500, 0), (14000, 0)),
        ((4500, 0), (4500, 4000)),
        ((4500, 4000), (9500, 4000)),
        ((9500, 4000), (9500, 0)),
        ((0, 0), (0, 9000)),
        ((14000, 0), (14000, 7000)),
        ((0, 9000), (12000, 9000)),
    ]
    rooms = _rooms_with([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
    assert _holding(rooms, 7000, 2000) == []
    assert len(_holding(rooms, 7000, 6500)) == 1
    assert len(rooms) == 1


def test_envelope__recessed_loggia_open_on_one_side_is_a_loggia(fake_clock: FakeClock) -> None:
    """Lô gia 3,5 x 1,5 m lõm giữa hai khối (khối phải nhô xa hơn nên lô gia không nằm trên biên bao lồi), mặt ngoài
    là lan can: thành `lô gia`."""
    segments = [
        ((0, 0), (9000, 0)),
        ((0, 6000), (9000, 6000)),
        ((0, -1500), (0, 6000)),
        ((9000, -3000), (9000, 6000)),
        ((0, -1500), (3000, -1500)),
        ((3000, -1500), (3000, 0)),
        ((6500, -3000), (6500, 0)),
        ((6500, -3000), (9000, -3000)),
    ]
    rooms = _rooms_with([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
    loggias = _holding(rooms, 4750, -750)
    assert [room.usage for room in loggias] == ["loggia"]
    assert 5.0 < loggias[0].area_m2 < 6.0


def test_envelope__long_hall_open_at_one_end_is_not_a_loggia(fake_clock: FakeClock) -> None:
    """Hành lang 9 x 1,4 m hở một đầu: là phòng, không thành lô gia (chỉ đầu hẹp hở); lô gia 3 x 1,4 m hở đầu hẹp vẫn
    là lô gia."""
    for length, usages in ((9000, ["other"]), (3000, ["loggia"])):
        segments = [((0, 0), (length, 0)), ((0, 1400), (length, 1400)), ((0, 0), (0, 1400))]
        rooms = _rooms_with([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
        assert [room.usage for room in rooms] == usages


def test_envelope__unread_bedroom_and_wc_open_to_the_facade_are_named_by_fixtures(fake_clock: FakeClock) -> None:
    """Phòng ngủ 3,5 x 3 m và WC 1,8 x 2,4 m hở mặt ngoài (vách kính), không chữ OCR: giường → phòng ngủ, thiết bị vệ
    sinh → phòng tắm (đồ đạc thắng cờ lô gia nông của đường bao)."""
    segments = [
        ((0, 0), (9300, 0)),
        ((0, 3000), (4000, 3000)),
        ((0, 0), (0, 3000)),
        ((4000, 0), (4000, 3000)),
        ((7500, 0), (7500, 3000)),
        ((9300, 0), (9300, 2400)),
    ]
    walls = [_wall(fake_clock, start, end) for start, end in segments]
    bed = DetectionPx(label="bed", box=_box(5000, 500, 6600, 2500), confidence=0.8)
    toilet = DetectionPx(label="sanitary_fixture", box=_box(8100, 300, 8700, 900), confidence=0.8)
    rooms = _rooms_with(walls, (), fake_clock, bed, toilet)
    assert [room.usage for room in _holding(rooms, 5750, 1500)] == ["bedroom"]
    assert [room.usage for room in _holding(rooms, 8400, 1200)] == ["bathroom"]


def test_envelope__band_wrapping_the_flat_is_not_a_room(fake_clock: FakeClock) -> None:
    """Mép bàn/khung ảnh dò thành tường chữ U quanh căn 8 x 6 m (hai phòng), hở góc dưới phải: vành 2 m giữa căn và
    khung ôm cả căn (`_ENVELOPE_WRAP`) nên không thành phòng."""
    segments = [
        ((0, 0), (12000, 0)),
        ((0, 0), (0, 8000)),
        ((0, 8000), (10500, 8000)),
        ((12000, 0), (12000, 6500)),
        ((2000, 0), (2000, 6000)),
        ((10000, 0), (10000, 6000)),
        ((2000, 6000), (10000, 6000)),
        ((6000, 0), (6000, 6000)),
    ]
    rooms = _rooms_with([_wall(fake_clock, start, end) for start, end in segments], (), fake_clock)
    assert sorted(room.area_m2 for room in rooms) == [24.0, 24.0]
