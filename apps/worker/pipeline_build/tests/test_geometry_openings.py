"""Bước 3b và 4 của `build_walls`: nối khe ô mở, gắn ô mở (B5-05 [8] "Ô mở").

Mỗi ca dựng tay `WallPx`/`DetectionPx` với `Scaling(1.0, 1.0)` nên px = mm và số đo đọc thẳng
ra mong đợi; tường đặt ở `y = 1000` để mọi toạ độ không âm.
"""

from collections import Counter

from apps.worker.pipeline_build.geometry import Scaling, WallSet, build_walls
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.tests.test_geometry_walls import wall_px
from packages.domain.spatial import Point
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, WallPx
from packages.ml_contracts.labels import DetectionLabel
from packages.testing.fixtures.clock import FakeClock


def det(label: DetectionLabel, x0: float, y0: float, x1: float, y1: float, confidence: float = 0.8) -> DetectionPx:
    """`DetectionPx` gọn cho test: nhãn và hộp px."""
    return DetectionPx(label=label, box=BoxPx(x_min=x0, y_min=y0, x_max=x1, y_max=y1), confidence=confidence)


def run(walls: list[WallPx], detections: list[DetectionPx], clock: FakeClock, dropped: Counter[str]) -> WallSet:
    """Gọi `build_walls` với `level_id` hợp mẫu W4 và tỉ lệ 1 mm/px."""
    return build_walls(
        walls,
        detections,
        level_id=new_spatial_id("level", clock),
        scaling=Scaling(1.0, 1.0),
        clock=clock,
        dropped=dropped,
    )


def test_build_walls__door_on_wall_gets_offset_and_defaults(fake_clock: FakeClock) -> None:
    """Cửa đi trên tường: 900 x 2200, bậu 0, `left`, `offsetMm` tới mép trái, có trong `openingIds`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("door", 1000, 950, 1900, 1050)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.kind, opening.width_mm, opening.height_mm, opening.sill_height_mm) == ("door", 900, 2200, 0)
    assert (opening.swing, opening.offset_mm, opening.source, opening.reviewed) == ("left", 1000, "ai", False)
    assert result.walls[0].opening_ids == (opening.id,)
    assert opening.wall_id == result.walls[0].id


def test_build_walls__window_uses_label_defaults(fake_clock: FakeClock) -> None:
    """Cửa sổ: 1200 x 1400, bậu 900, `sliding`, `kind` `window`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("window", 1000, 950, 2200, 1050)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.kind, opening.width_mm, opening.height_mm) == ("window", 1200, 1400)
    assert (opening.sill_height_mm, opening.swing) == (900, "sliding")


def test_build_walls__double_door_width_from_box(fake_clock: FakeClock) -> None:
    """`double_door` không có rộng mặc định: lấy `js_round(b - a)` của hộp chiếu lên tim."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("double_door", 1000, 950, 2600, 1050)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.kind, opening.width_mm, opening.swing, opening.offset_mm) == ("door", 1600, "double", 1000)


def test_build_walls__double_door_past_wall_end_dropped(fake_clock: FakeClock) -> None:
    """Hộp cửa đôi gần hết ra ngoài đầu tường: `b - a < 600` → `openingUnattached`, không ném."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("double_door", 3900, 950, 4100, 1050)], fake_clock, dropped)
    assert result.openings == ()
    assert dropped["openingUnattached"] == 1


def test_build_walls__gap_with_door_box_bridged(fake_clock: FakeClock) -> None:
    """Tường 4.000 bị khe cửa 900 chia hai đoạn, khe có hộp → một tường và một cửa (3b-a)."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 1550, 1000), wall_px(2450, 1000, 4000, 1000)],
        [det("door", 1550, 950, 2450, 1050)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 1
    assert dropped["wallGapBridged"] == 1
    assert result.input_to_wall == {0: 0, 1: 0}
    (opening,) = result.openings
    assert abs(opening.offset_mm - 1550) <= 20


def test_build_walls__three_segments_reach_fixed_point(fake_clock: FakeClock) -> None:
    """Tường bị **hai** khe cửa chia ba đoạn → một tường (hàng đợi ứng viên lặp tới điểm bất động)."""
    dropped: Counter[str] = Counter()
    result = run(
        [
            wall_px(0, 1000, 1550, 1000),
            wall_px(2450, 1000, 4000, 1000),
            wall_px(4900, 1000, 6500, 1000),
        ],
        [det("door", 1550, 950, 2450, 1050), det("door", 4000, 950, 4900, 1050)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 1
    assert dropped["wallGapBridged"] == 2
    assert len(result.openings) == 2
    assert result.input_to_wall == {0: 0, 1: 0, 2: 0}


def test_build_walls__endpoint_pulled_to_perpendicular_centreline(fake_clock: FakeClock) -> None:
    """3b-b: khe 100 giữa đầu mút và tim vách vuông góc có hộp → kéo đầu mút tới tim vách."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 1900, 1000), wall_px(2000, 1000, 2000, 4000)],
        [det("door", 1900, 950, 2000, 1050)],
        fake_clock,
        dropped,
    )
    assert dropped["wallGapBridged"] == 1
    assert result.walls[0].centreline.end == Point(x=2000, y=1000)


def test_build_walls__aligned_gap_without_box_becomes_bridge(fake_clock: FakeClock) -> None:
    """3b-c: cặp thẳng hàng có khe mà không hộp → giữ cả hai, đoạn nối vào `WallSet.bridges`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 1550, 1000), wall_px(2450, 1000, 4000, 1000)], [], fake_clock, dropped)
    assert len(result.walls) == 2
    assert dropped["wallGapBridged"] == 0
    assert result.bridges == ((Point(x=1550, y=1000), Point(x=2450, y=1000)),)


def test_build_walls__door_near_perpendicular_partition_picks_right_wall(fake_clock: FakeClock) -> None:
    """Cửa 900 cách mặt vách vuông góc 50 mm vẫn gắn vào tường nó nằm trên (tâm hộp gần tim hơn)."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 4000, 1000), wall_px(2000, 1000, 2000, 4000)],
        [det("door", 2100, 950, 3000, 1050)],
        fake_clock,
        dropped,
    )
    (opening,) = result.openings
    assert opening.wall_id == result.walls[0].id
    assert result.walls[1].opening_ids == ()


def test_build_walls__box_far_from_wall_unattached(fake_clock: FakeClock) -> None:
    """Tâm hộp cách tim 400 mm > `thicknessMm / 2 + OPENING_WALL_REACH_MM` → `openingUnattached`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("door", 1000, 1350, 1900, 1450)], fake_clock, dropped)
    assert result.openings == ()
    assert dropped["openingUnattached"] == 1


def test_build_walls__wall_shorter_than_door_too_wide(fake_clock: FakeClock) -> None:
    """Tường 800 mm không chứa nổi cửa 900 → `openingTooWide`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 800, 1000)], [det("door", 0, 950, 800, 1050)], fake_clock, dropped)
    assert result.openings == ()
    assert dropped["openingTooWide"] == 1


def test_build_walls__overlapping_openings_keep_higher_confidence(fake_clock: FakeClock) -> None:
    """Hai hộp chồng khoảng trên cùng tường → giữ `confidence` cao hơn, còn lại `openingOverlap`."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 4000, 1000)],
        [
            det("door", 1000, 950, 1900, 1050, 0.6),
            det("door", 1100, 950, 2000, 1050, 0.9),
            det("door", 1200, 950, 2100, 1050, 0.5),
        ],
        fake_clock,
        dropped,
    )
    (opening,) = result.openings
    assert opening.confidence == 0.9
    assert dropped["openingOverlap"] == 2


def test_build_walls__furniture_labels_ignored_without_counting(fake_clock: FakeClock) -> None:
    """Nhãn đồ đạc không thành ô mở và **không** vào `dropped` (việc của `build_furniture`)."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 4000, 1000)], [det("bed", 1000, 950, 1900, 1050)], fake_clock, dropped)
    assert result.openings == ()
    assert dropped == Counter()


def test_build_walls__openings_without_walls_all_unattached(fake_clock: FakeClock) -> None:
    """Không tường nào còn lại: mọi hộp ô mở thành `openingUnattached`, không ném."""
    dropped: Counter[str] = Counter()
    result = run([], [det("door", 1000, 950, 1900, 1050)], fake_clock, dropped)
    assert (result.walls, result.openings) == ((), ())
    assert dropped["openingUnattached"] == 1


def test_build_walls__gap_crossed_by_other_wall_not_merged(fake_clock: FakeClock) -> None:
    """Khe cắt tim vách vuông góc → không gộp; hai đầu được kéo tới tim vách đó (3b-a chặn, 3b-b nhận)."""
    dropped: Counter[str] = Counter()
    result = run(
        [
            wall_px(0, 1000, 1550, 1000),
            wall_px(2450, 1000, 4000, 1000),
            wall_px(2000, 500, 2000, 1500),
        ],
        [det("door", 1550, 950, 2450, 1050)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 3
    assert dropped["wallGapBridged"] == 2
    assert result.walls[0].centreline.end == Point(x=2000, y=1000)
    assert result.walls[1].centreline.start == Point(x=2000, y=1000)


def test_build_walls__perpendicular_gap_without_box_not_pulled(fake_clock: FakeClock) -> None:
    """3b-b chỉ kéo khi khe có hộp: không hộp thì đầu mút giữ nguyên."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 1900, 1000), wall_px(2000, 1000, 2000, 4000)], [], fake_clock, dropped)
    assert dropped["wallGapBridged"] == 0
    assert result.walls[0].centreline.end == Point(x=1900, y=1000)


def test_build_walls__perpendicular_wall_too_short_not_pulled(fake_clock: FakeClock) -> None:
    """Chân vuông góc rơi ngoài đoạn vách (vách không vươn tới) → không kéo đầu mút."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 1550, 1000), wall_px(2000, 2000, 2000, 3000)], [], fake_clock, dropped)
    assert dropped["wallGapBridged"] == 0
    assert result.walls[0].centreline.end == Point(x=1550, y=1000)


def test_build_walls__equidistant_walls_pick_lowest_index(fake_clock: FakeClock) -> None:
    """Tâm hộp cách hai tường song song đúng bằng nhau → hoà lấy tường đứng trước."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 4000, 1000), wall_px(0, 1400, 4000, 1400)],
        [det("door", 1000, 1150, 1900, 1250)],
        fake_clock,
        dropped,
    )
    (opening,) = result.openings
    assert opening.wall_id == result.walls[0].id
    assert result.walls[1].opening_ids == ()
