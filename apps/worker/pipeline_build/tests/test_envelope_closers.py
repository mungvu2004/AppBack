"""C5 mở rộng (BENCH3D-15): đoạn khép phòng của `build_rooms` nằm ở mặt ngoài thành tường vỏ (`close_envelope_gaps`).

Tường dựng tay ở mm (không qua `build_walls` nên bước 3b không tự khép khe); phòng 6 x 4 m góc trên-trái (1000, 1000).
"""

from collections import Counter
from collections.abc import Sequence
from typing import Any

import cv2
import numpy as np
import pytest

from apps.worker.pipeline_build.geometry import RoomCloser, Scaling, WallSet, build_walls, close_envelope_gaps
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.residual import PageRaster
from apps.worker.pipeline_build.rooms import build_rooms
from apps.worker.pipeline_build.tests.test_geometry_openings import _box_with_top_gap, det
from apps.worker.pipeline_build.tests.test_rooms import LEVEL_ID, _wall
from packages.domain.spatial import Opening, Point, Room, Wall
from packages.ml_contracts.artifacts import DetectionPx
from packages.testing.fixtures.clock import FakeClock

_MM = Scaling(1.0, 1.0)


def _room_box(clock: FakeClock, top_end: int) -> list[Wall]:
    """Phòng (1000, 1000)-(7000, 5000): tường trên dừng ở `x = top_end`, tường phải có đầu tự do ở góc (chữ L hở)."""
    return [
        _wall(clock, (1000, 1000), (top_end, 1000)),
        _wall(clock, (7000, 1000), (7000, 5000)),
        _wall(clock, (7000, 5000), (1000, 5000)),
        _wall(clock, (1000, 5000), (1000, 1000)),
    ]


def _envelope(
    walls: Sequence[Wall],
    clock: FakeClock,
    *,
    detections: Sequence[DetectionPx] = (),
    page: PageRaster | None = None,
    scaling: Scaling = _MM,
    openings: Sequence[Opening] = (),
) -> tuple[WallSet, tuple[Room, ...], list[RoomCloser]]:
    """`build_rooms` (nhận closers) → `close_envelope_gaps`, như `build._assembled`."""
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": scaling, "clock": clock}
    closers: list[RoomCloser] = []
    rooms = build_rooms(walls, (), (), detections=detections, dropped=Counter(), closers_out=closers, **shared)
    wall_set = WallSet(walls=tuple(walls), openings=tuple(openings), input_to_wall={}, bridges=())
    return close_envelope_gaps(wall_set, rooms, page=page, closers=closers, **shared), rooms, closers


def test_close_envelope_gaps__short_corner_gap_extends_the_aligned_host(fake_clock: FakeClock) -> None:
    """Góc chữ L hở 500 mm: phòng khép bằng đoạn nối góc → tường trên kéo tới tường phải, không thêm tường."""
    result, rooms, closers = _envelope(_room_box(fake_clock, 6500), fake_clock)
    assert len(rooms) == 1
    assert [(closer.start, closer.label) for closer in closers] == [(Point(x=6500, y=1000), None)]
    assert len(result.walls) == 4
    assert result.walls[0].centreline.end.x in (7000, 7001)
    assert result.openings == ()


def test_close_envelope_gaps__long_corner_gap_becomes_solid_wall(fake_clock: FakeClock) -> None:
    """Góc chữ L hở 800 mm, không hộp, không trang → tường đặc mới phủ đúng khe (không đoán cửa đi)."""
    result, _, _ = _envelope(_room_box(fake_clock, 6200), fake_clock)
    assert len(result.walls) == 5
    gap = result.walls[-1]
    assert gap.centreline.start == Point(x=6200, y=1000)
    assert gap.centreline.end.x in (7000, 7001)
    assert (gap.opening_ids, result.openings) == ((), ())


def test_close_envelope_gaps__window_box_on_gap_becomes_window_wall(fake_clock: FakeClock) -> None:
    """Khe 1200 có hộp cửa sổ: đoạn khép của hộp đi trước → tường mang cửa sổ; đoạn góc trùng khe bị bỏ (W4)."""
    window = det("window", 5800, 950, 7000, 1050)
    result, _, closers = _envelope(_room_box(fake_clock, 5800), fake_clock, detections=[window])
    assert [closer.label for closer in closers] == ["window", None]
    assert len(result.walls) == 5
    (opening,) = result.openings
    assert (opening.kind, opening.sill_height_mm, opening.confidence) == ("window", 900, 0.5)
    assert opening.width_mm >= 1200
    assert result.walls[-1].opening_ids == (opening.id,)


def test_close_envelope_gaps__door_box_gap_reads_door(fake_clock: FakeClock) -> None:
    """Khe 900 có hộp cửa đi: tường qua khe mang cửa đi (chiều mở đoán như C5)."""
    door = det("door", 6100, 950, 7000, 1050)
    result, _, _ = _envelope(_room_box(fake_clock, 6100), fake_clock, detections=[door])
    (opening,) = result.openings
    assert opening.kind == "door"


@pytest.mark.parametrize(
    ("near_offset", "added"),
    [pytest.param(4300, 0, id="box-already-placed"), pytest.param(1000, 1, id="far-opening")],
)
def test_close_envelope_gaps__box_already_an_opening_is_skipped(
    near_offset: int, added: int, fake_clock: FakeClock
) -> None:
    """Hộp đã thành ô mở trên tường cạnh khe (tâm ≤ nửa khe + 300 mm) → không thêm ô mở thứ hai; khe vẫn khép bằng
    tường đặc của đoạn góc trùng khe."""
    walls = _room_box(fake_clock, 5800)
    placed = Opening(
        id=new_spatial_id("opening", fake_clock),
        wall_id=walls[0].id,
        kind="window",
        offset_mm=near_offset,
        width_mm=600,
        height_mm=1400,
        sill_height_mm=900,
        swing="sliding",
        confidence=0.8,
        source="ai",
        reviewed=False,
    )
    stray = placed.model_copy(
        update={"id": new_spatial_id("opening", fake_clock), "wall_id": new_spatial_id("wall", fake_clock)}
    )
    window = det("window", 5800, 950, 7000, 1050)
    result, _, _ = _envelope(walls, fake_clock, detections=[window], openings=[placed, stray])
    assert len(result.walls) == 5
    assert len(result.openings) == 2 + added


def _glass_page(kind: str) -> PageRaster:
    """Trang 10 mm/px quanh khe 1200 mm của tường trên (px x 580-700, y = 100): hai nét kính, khối đặc, hay trống."""
    gray = np.full((520, 720), 255, np.uint8)
    if kind == "glass":
        cv2.line(gray, (575, 98), (705, 98), 0, 1)
        cv2.line(gray, (575, 102), (705, 102), 0, 1)
    elif kind == "solid":
        cv2.rectangle(gray, (575, 95), (705, 105), 0, -1)
    return PageRaster(gray=gray, walls=np.zeros_like(gray, dtype=bool))


@pytest.mark.parametrize(
    ("kind", "window"),
    [pytest.param("glass", True, id="glazing"), pytest.param("solid", False, id="fill"), pytest.param("blank", False)],
)
def test_close_envelope_gaps__glazing_strokes_make_a_window(kind: str, window: bool, fake_clock: FakeClock) -> None:
    """Khe 1200 không hộp: ≥ 2 nét mảnh dọc khe → cửa sổ tin 0,3; khối mực liền hay trang trống → tường đặc."""
    result, _, _ = _envelope(
        _room_box(fake_clock, 5800), fake_clock, page=_glass_page(kind), scaling=Scaling(10.0, 10.0)
    )
    assert len(result.walls) == 5
    assert [(item.kind, item.confidence) for item in result.openings] == ([("window", 0.3)] if window else [])


def test_close_envelope_gaps__glazing_needs_a_page_matching_the_mask(fake_clock: FakeClock) -> None:
    """Mặt nạ tường lệch khổ trang → không đọc nét kính, khe thành tường đặc."""
    page = _glass_page("glass")
    skewed = PageRaster(gray=page.gray, walls=np.zeros((10, 10), dtype=bool))
    result, _, _ = _envelope(_room_box(fake_clock, 5800), fake_clock, page=skewed, scaling=Scaling(10.0, 10.0))
    assert result.openings == ()


def test_close_envelope_gaps__glazing_band_off_page_is_ignored(fake_clock: FakeClock) -> None:
    """Dải bề dày tràn mép trang: hàng ra ngoài không tính là nét → tường đặc."""
    tiny = PageRaster(gray=np.full((101, 720), 255, np.uint8), walls=np.zeros((101, 720), dtype=bool))
    result, _, _ = _envelope(_room_box(fake_clock, 5800), fake_clock, page=tiny, scaling=Scaling(10.0, 10.0))
    assert len(result.walls) == 5
    assert result.openings == ()


@pytest.mark.parametrize("usage", ["bedroom", "loggia"])
def test_close_envelope_gaps__shared_edge_between_rooms_stays_open(usage: str, fake_clock: FakeClock) -> None:
    """Vách giữa dừng 800 mm trước tường trên (chữ T): đoạn khép chia hai phòng nhưng nằm trong nhà → không thành vách,
    kể cả khi một bên là lô gia (lối khách - lô gia, khách - bếp giữ mở)."""
    walls = [*_room_box(fake_clock, 7000), _wall(fake_clock, (4000, 5000), (4000, 1800))]
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": Scaling(1.0, 1.0), "clock": fake_clock}
    closers: list[RoomCloser] = []
    rooms = build_rooms(walls, (), (), dropped=Counter(), closers_out=closers, **shared)
    assert len(rooms) == 2
    assert closers
    rooms = (rooms[0].model_copy(update={"usage": usage}), *rooms[1:])
    wall_set = WallSet(walls=tuple(walls), openings=(), input_to_wall={}, bridges=())
    result = close_envelope_gaps(wall_set, rooms, closers=closers, **shared)
    assert result.walls == tuple(walls)


def test_close_envelope_gaps__courtyard_between_rooms_not_sealed(fake_clock: FakeClock) -> None:
    """Sân trong/giếng trời giữa hai phòng: đoạn qua miệng sân không bên nào là phòng → không bịt.

    Sân rộng 5 m — hơn khe tối đa mà đường bao căn tự khép (4 m), nên dải giữa không thành phòng.
    """
    left = [((0, 0), (3000, 0)), ((3000, 0), (3000, 4000)), ((3000, 4000), (0, 4000)), ((0, 4000), (0, 0))]
    right = [
        ((8000, 0), (11000, 0)),
        ((11000, 0), (11000, 4000)),
        ((11000, 4000), (8000, 4000)),
        ((8000, 4000), (8000, 0)),
    ]
    walls = [_wall(fake_clock, start, end) for start, end in [*left, *right]]
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": Scaling(1.0, 1.0), "clock": fake_clock}
    rooms = build_rooms(walls, (), (), dropped=Counter(), **shared)
    assert len(rooms) == 2
    mouth = RoomCloser(Point(x=3000, y=4000), Point(x=8000, y=4000), "door")
    wall_set = WallSet(walls=tuple(walls), openings=(), input_to_wall={}, bridges=())
    result = close_envelope_gaps(wall_set, rooms, closers=[mouth], **shared)
    assert (result.walls, result.openings) == (tuple(walls), ())


def test_close_envelope_gaps__closer_without_owner_wall_skipped(fake_clock: FakeClock) -> None:
    """Đoạn khép không xuất phát từ đầu tường nào (tường đã bị kéo bởi khe trước) → bỏ, không đoán bề dày."""
    walls = _room_box(fake_clock, 7000)
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": Scaling(1.0, 1.0), "clock": fake_clock}
    rooms = build_rooms(walls, (), (), dropped=Counter(), **shared)
    stray = RoomCloser(Point(x=3000, y=1000), Point(x=3000, y=1500))
    wall_set = WallSet(walls=tuple(walls), openings=(), input_to_wall={}, bridges=())
    assert close_envelope_gaps(wall_set, rooms, closers=[stray], **shared).walls == tuple(walls)


@pytest.mark.parametrize(
    ("usage", "door"),
    [
        pytest.param("loggia", False),
        pytest.param("utility", False),
        pytest.param("other", False),
        pytest.param("bedroom", True),
    ],
)
def test_close_envelope_gaps__no_guessed_door_into_loggia(usage: str, door: bool, fake_clock: FakeClock) -> None:
    """R2': khe 1600 trên tường ngoài của lô gia/kỹ thuật/khác → tường đặc qua khe; phòng ở → cửa đi lùa như cũ."""
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": Scaling(1.0, 1.0), "clock": fake_clock}
    wall_set = build_walls(_box_with_top_gap(2000, 3600), [], dropped=Counter(), **shared)
    rooms = build_rooms(wall_set.walls, wall_set.bridges, (), dropped=Counter(), **shared)
    rooms = tuple(room.model_copy(update={"usage": usage}) for room in rooms)
    result = close_envelope_gaps(wall_set, rooms, **shared)
    gap = result.walls[-1]
    assert (gap.centreline.start, gap.centreline.end) == (Point(x=2000, y=0), Point(x=3600, y=0))
    assert [opening.swing for opening in result.openings] == (["sliding"] if door else [])
    assert bool(gap.opening_ids) is door


@pytest.mark.parametrize(
    ("host", "kind", "offset", "added"),
    [
        pytest.param(0, "window", 5200, 1, id="perpendicular-window-near-corner"),
        pytest.param(1, "window", 0, 1, id="aligned-window-other-kind"),
        pytest.param(1, "door", 0, 0, id="aligned-door-touching-gap"),
    ],
)
def test_close_envelope_gaps__duplicate_needs_same_kind_on_aligned_wall(
    host: int, kind: str, offset: int, added: int, fake_clock: FakeClock
) -> None:
    """Khe cửa đi 1000 ở tường phải (x = 7000, y 1000-2000): cửa sổ tâm (6500, 1000) trên tường trên vuông góc hay cửa
    sổ cạnh khe không chặn cửa đi của hộp (Codex r3 #4); cửa đi cùng loại trên tường phải chạm khe → coi là trùng."""
    walls = [
        _wall(fake_clock, (1000, 1000), (7000, 1000)),
        _wall(fake_clock, (7000, 2000), (7000, 5000)),
        _wall(fake_clock, (7000, 5000), (1000, 5000)),
        _wall(fake_clock, (1000, 5000), (1000, 1000)),
    ]
    placed = Opening(
        id=new_spatial_id("opening", fake_clock),
        wall_id=walls[host].id,
        kind=kind,
        offset_mm=offset,
        width_mm=600 if kind == "window" else 900,
        height_mm=1400 if kind == "window" else 2100,
        sill_height_mm=900 if kind == "window" else 0,
        swing="sliding" if kind == "window" else "left",
        confidence=0.8,
        source="ai",
        reviewed=False,
    )
    door = det("door", 6950, 1000, 7050, 2000)
    result, _, closers = _envelope(walls, fake_clock, detections=[door], openings=[placed])
    assert "door" in [closer.label for closer in closers]
    assert len(result.openings) == 1 + added
    assert [opening.kind for opening in result.openings[1:]] == ["door"] * added


def _window_on(wall: Wall, clock: FakeClock) -> Opening:
    """Cửa sổ 1 m giữa tường qua khe 3c."""
    return Opening(
        id=new_spatial_id("opening", clock),
        wall_id=wall.id,
        kind="window",
        offset_mm=300,
        width_mm=1000,
        height_mm=1400,
        sill_height_mm=900,
        swing="sliding",
        confidence=0.8,
        source="ai",
        reviewed=False,
    )


@pytest.mark.parametrize(
    ("bridged_end", "shoulders"),
    [
        pytest.param(6300, [(4000, 4700), (6300, 7000)], id="two-shoulders"),
        pytest.param(6950, [(4000, 4700)], id="sliver-under-piece-min"),
    ],
)
def test_close_envelope_gaps__closer_skips_part_under_bridged_wall(
    bridged_end: int, shoulders: list[tuple[int, int]], fake_clock: FakeClock
) -> None:
    """Khe 3000 mặt ngoài, tường qua khe 3c mang cửa sổ phủ 4700→`bridged_end` (`build_rooms` không thấy nó nên đoạn
    khép cả khe, nhãn hộp cửa sổ): chỉ dựng phần còn hở ≥ 100 mm, không chồng tường 3c, không thêm ô mở."""
    walls = _room_box(fake_clock, 4000)
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": _MM, "clock": fake_clock}
    rooms = build_rooms([*walls, _wall(fake_clock, (4000, 1000), (7000, 1000))], (), (), dropped=Counter(), **shared)
    closers = [RoomCloser(Point(x=4000, y=1000), Point(x=7000, y=1000), "window")]
    bridged = _wall(fake_clock, (4700, 1007), (bridged_end, 1007))
    window = _window_on(bridged, fake_clock)
    bridged = bridged.model_copy(update={"opening_ids": (window.id,)})
    wall_set = WallSet(walls=(*walls, bridged), openings=(window,), input_to_wall={}, bridges=())
    result = close_envelope_gaps(wall_set, rooms, closers=closers, **shared)
    added = result.walls[5:]
    assert [(wall.centreline.start.x, min(wall.centreline.end.x, 7000)) for wall in added] == shoulders
    assert all(wall.opening_ids == () and wall.thickness_mm == 100 for wall in added)
    assert result.openings == (window,)


def test_close_envelope_gaps__closer_crossing_a_wall_still_skipped(fake_clock: FakeClock) -> None:
    """Đoạn khép cắt ngang thân một tường (không song song) → bỏ cả đoạn như cũ, không chia vai."""
    walls = _room_box(fake_clock, 4000)
    shared: dict[str, Any] = {"level_id": LEVEL_ID, "scaling": _MM, "clock": fake_clock}
    rooms = build_rooms([*walls, _wall(fake_clock, (4000, 1000), (7000, 1000))], (), (), dropped=Counter(), **shared)
    closers = [RoomCloser(Point(x=4000, y=1000), Point(x=7000, y=1000))]
    across = _wall(fake_clock, (5500, 500), (5500, 1500))
    wall_set = WallSet(walls=(*walls, across), openings=(), input_to_wall={}, bridges=())
    result = close_envelope_gaps(wall_set, rooms, closers=closers, **shared)
    assert result.walls == (*walls, across)


def test_close_envelope_gaps__no_wall_across_paper_between_units(fake_clock: FakeClock) -> None:
    """B4 (BENCH3D-20): hai căn thẳng hàng cách khe giấy 2 m (> `FAR_CLUSTER_GAP_MM`) là hai vùng: đoạn khép phòng
    qua khe không thành tường, nên lớp tường vẫn là hai vùng tách rời (`MULTIPLE_PLANS` thấy được)."""
    # tường trên/dưới thò 500 mm qua vách đầu hồi: đầu tự do thẳng hàng với tường căn kia, build_rooms khép qua khe
    unit_a = [
        _wall(fake_clock, (0, 0), (6000, 0)),
        _wall(fake_clock, (5500, 0), (5500, 5000)),
        _wall(fake_clock, (6000, 5000), (0, 5000)),
        _wall(fake_clock, (0, 5000), (0, 0)),
    ]
    unit_b = [
        _wall(fake_clock, (8000, 0), (14000, 0)),
        _wall(fake_clock, (14000, 0), (14000, 5000)),
        _wall(fake_clock, (14000, 5000), (8000, 5000)),
        _wall(fake_clock, (8500, 5000), (8500, 0)),
    ]
    result, _rooms, closers = _envelope(unit_a + unit_b, fake_clock)

    def spans_gap(start: Point, end: Point) -> bool:
        return min(start.x, end.x) < 6500 and max(start.x, end.x) > 7500

    assert any(spans_gap(closer.start, closer.end) for closer in closers)  # build_rooms khép qua khe
    assert not any(spans_gap(wall.centreline.start, wall.centreline.end) for wall in result.walls)
