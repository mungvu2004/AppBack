"""Bước 3b và 4 của `build_walls`: nối khe ô mở, gắn ô mở (B5-05 [8] "Ô mở").

Mỗi ca dựng tay `WallPx`/`DetectionPx` với `Scaling(1.0, 1.0)` nên px = mm và số đo đọc thẳng
ra mong đợi; tường đặt ở `y = 1000` để mọi toạ độ không âm.
"""

import math
from collections import Counter

import pytest

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


def test_build_walls__short_wall_keeps_door_clamped_to_length(fake_clock: FakeClock) -> None:
    """Tường 800 mm, hộp cửa 1.000 phủ quá hai đầu: rộng = hình chiếu kẹp về 800, không `openingTooWide`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(100, 1000, 900, 1000)], [det("door", 0, 950, 1000, 1050)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.width_mm, opening.offset_mm) == (800, 0)
    assert dropped["openingTooWide"] == 0


@pytest.mark.parametrize("length", [800, 500, 300])
def test_build_walls__degenerate_projection_clamped_to_short_wall(length: int, fake_clock: FakeClock) -> None:
    """BUG-IT-009: hộp gần hết ra ngoài đầu tường: hình chiếu 100 < 300 → mặc định 900 > L ≥ 300 → kẹp về L."""
    dropped: Counter[str] = Counter()
    box = det("door", length - 100, 950, length + 900, 1050)
    result = run([wall_px(0, 1000, length, 1000)], [box], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.width_mm, opening.offset_mm) == (length, 0)
    assert dropped["openingTooWide"] == 0


def test_build_walls__clamped_opening_stays_inside_diagonal_wall(fake_clock: FakeClock) -> None:
    """Review 2 P2: tường chéo L ≈ 476,6 → rộng kẹp 476; `offsetMm` trần `floor(L - 476) = 0` để không lố đầu tường."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 0, 337, 337)], [det("door", 300, 300, 700, 700)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.width_mm, opening.offset_mm) == (476, 0)
    assert opening.offset_mm + opening.width_mm <= math.hypot(337, 337)


def test_build_walls__wall_under_min_width_too_wide(fake_clock: FakeClock) -> None:
    """Tường 250 < `OPENING_MIN_WIDTH_MM`: không đủ chỗ cho ô mở thật → vẫn `openingTooWide`."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 1000, 250, 1000)], [det("door", 150, 950, 1150, 1050)], fake_clock, dropped)
    assert result.openings == ()
    assert dropped["openingTooWide"] == 1


def test_build_walls__clamped_openings_on_short_wall_overlap(fake_clock: FakeClock) -> None:
    """Hai hộp suy biến ở hai đầu tường 500: cả hai kẹp về 500 → chồng nhau, giữ `confidence` cao, `openingOverlap`."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(1000, 1000, 1500, 1000)],
        [det("door", 1400, 950, 2400, 1050, 0.7), det("door", 100, 950, 1100, 1050, 0.9)],
        fake_clock,
        dropped,
    )
    (opening,) = result.openings
    assert (opening.width_mm, opening.offset_mm) == (500, 0)
    assert dropped["openingOverlap"] == 1
    assert dropped["openingTooWide"] == 0


def test_build_walls__width_from_box_projection(fake_clock: FakeClock) -> None:
    """Rộng ô mở lấy từ hộp chiếu lên tim, không phải `LABEL_TARGETS`: cửa 800, cửa sổ 600."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 4000, 1000)],
        [det("door", 1000, 950, 1800, 1050), det("window", 2500, 950, 3100, 1050)],
        fake_clock,
        dropped,
    )
    door, window = result.openings
    assert (door.width_mm, door.offset_mm, door.height_mm) == (800, 1000, 2200)
    assert (window.width_mm, window.offset_mm, window.sill_height_mm) == (600, 2500, 900)


def test_build_walls__adjacent_windows_do_not_overlap(fake_clock: FakeClock) -> None:
    """Hai cửa sổ 600 cách nhau 100 mm: rộng theo hộp nên không chồng (trước đây 1.200 mỗi cái → `openingOverlap`)."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 4000, 1000)],
        [det("window", 1000, 950, 1600, 1050), det("window", 1700, 950, 2300, 1050)],
        fake_clock,
        dropped,
    )
    assert [(o.offset_mm, o.width_mm) for o in result.openings] == [(1000, 600), (1700, 600)]
    assert dropped["openingOverlap"] == 0


@pytest.mark.parametrize(
    ("cross", "expected_cross"),
    [
        ((3855, 2900, 7000, 2900), (Point(x=3826, y=2900), Point(x=7000, y=2900))),
        ((1000, 2900, 3797, 2900), (Point(x=1000, y=2900), Point(x=3826, y=2900))),
    ],
)
def test_build_walls__corner_gap_closed_when_crossing_just_outside(
    cross: tuple[float, float, float, float], expected_cross: tuple[Point, Point], fake_clock: FakeClock
) -> None:
    """BUG-IT-001 (G2): chỗ giao lố đầu vách ngang 29 mm (≤ 150) → kéo tường tới chân, vách kéo theo, cửa gắn."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(3826, 0, 3826, 2000), wall_px(*cross)],
        [det("door", 3776, 2000, 3876, 2900)],
        fake_clock,
        dropped,
    )
    assert dropped["wallGapBridged"] == 1
    assert result.walls[0].centreline.end == Point(x=3826, y=2900)
    assert (result.walls[1].centreline.start, result.walls[1].centreline.end) == expected_cross
    (opening,) = result.openings
    assert (opening.wall_id, opening.offset_mm, opening.width_mm) == (result.walls[0].id, 2000, 900)


def test_build_walls__crossing_far_outside_cross_wall_not_pulled(fake_clock: FakeClock) -> None:
    """Chỗ giao cách đầu vách ngang 274 mm > `max(bề dày, 150)` → không kéo, cả hai tường giữ nguyên."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(3826, 0, 3826, 2000), wall_px(4100, 2900, 7000, 2900)],
        [det("door", 3776, 2000, 3876, 2900)],
        fake_clock,
        dropped,
    )
    assert dropped["wallGapBridged"] == 0
    assert result.walls[0].centreline.end == Point(x=3826, y=2000)
    assert result.walls[1].centreline.start == Point(x=4100, y=2900)


def test_build_walls__diagonal_wall_attaches_axis_aligned_box(fake_clock: FakeClock) -> None:
    """BUG-IT-003: tường 45°, hộp thẳng trục có tâm cách tim 354 mm > 200 nhưng tim cắt hộp → gắn.

    Hình chiếu 4 góc lên tim chéo: `(5400 - 3600) / √2 ≈ 1272,8`, trừ phần bề dày chiếu thêm `100 · |sin 90°|`
    → rộng 1173; `offsetMm` = tâm hình chiếu 3181,9 - 586,5 ≈ 2595.
    """
    dropped: Counter[str] = Counter()
    result = run([wall_px(0, 0, 4000, 4000)], [det("door", 1700, 1900, 2300, 3100)], fake_clock, dropped)
    (opening,) = result.openings
    assert (opening.wall_id, opening.width_mm, opening.offset_mm) == (result.walls[0].id, 1173, 2595)
    assert dropped["openingUnattached"] == 0


def test_build_walls__diagonal_adjacent_windows_keep_true_width(fake_clock: FakeClock) -> None:
    """Review P2 LOG-02: hai cửa sổ thật 900 cách 100 mm trên tường 45° (bề dày 100).

    Hộp thẳng trục của mỗi cửa sổ là tâm ± 500/√2; hình chiếu dài 1.000 = 900 + bề dày → trừ lại còn 900,
    nên không chồng nhau (trước đó 1.000 mỗi cái → cái sau `openingOverlap`).
    """
    half = 500 / math.sqrt(2)
    centres = [2000 / math.sqrt(2), 3000 / math.sqrt(2)]
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 0, 4000, 4000)],
        [det("window", c - half, c - half, c + half, c + half) for c in centres],
        fake_clock,
        dropped,
    )
    assert [(o.offset_mm, o.width_mm) for o in result.openings] == [(1550, 900), (2550, 900)]
    assert dropped["openingOverlap"] == 0


def test_build_walls__corner_box_touching_two_walls_picks_centre_nearest(fake_clock: FakeClock) -> None:
    """Hộp cửa sát góc chạm cả vách vuông góc (đứng trước): cùng khoảng cách hộp 0 → chọn tường gần tâm."""
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(2000, 1000, 2000, 4000), wall_px(0, 1000, 4000, 1000)],
        [det("door", 2000, 950, 2900, 1050)],
        fake_clock,
        dropped,
    )
    (opening,) = result.openings
    assert (opening.wall_id, opening.offset_mm, opening.width_mm) == (result.walls[1].id, 2000, 900)
    assert result.walls[0].opening_ids == ()


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


def _on_diagonal(t: float, angle_deg: float, length: float) -> tuple[float, float, float, float]:
    """Tường dài `length` theo góc `angle_deg`, bắt đầu tại điểm cách (1000, 1000) một đoạn `t` trên đường 45°."""
    x0, y0 = 1000 + t / math.sqrt(2), 1000 + t / math.sqrt(2)
    rad = math.radians(angle_deg)
    return (x0, y0, x0 + length * math.cos(rad), y0 + length * math.sin(rad))


def _reversed(wall: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """Đảo chiều tim tường (đầu ↔ cuối)."""
    return (wall[2], wall[3], wall[0], wall[1])


@pytest.mark.parametrize(("label", "gap", "flip"), [("door", 900, False), ("window", 1200, False), ("door", 900, True)])
def test_build_walls__diagonal_noisy_gap_joined(
    label: DetectionLabel, gap: int, flip: bool, fake_clock: FakeClock
) -> None:
    """BUG-IT-007 (G5 xoay 45°): hai tường 43° và 47° hai bên khe ô mở trên đường 45° → gộp một tường.

    Lệch nhau 4° > 2° nên trước đây không gộp; hai đầu mút gần cùng nằm trên đường 45° (lệch ngang 0
    theo hướng trung bình). Hộp thẳng trục của ô mở rộng `gap`, bề dày 100: nửa cạnh `(gap/2 + 50)/√2`;
    rộng ô mở ≈ `gap` (hình chiếu trừ phần bề dày), `flip` = tường sau vẽ ngược chiều.
    """
    a = _reversed(_on_diagonal(1500, 43 + 180, 1500))
    b = _on_diagonal(1500 + gap, 47, 1500)
    centre = 1000 + (1500 + gap / 2) / math.sqrt(2)
    half = (gap / 2 + 50) / math.sqrt(2)
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(*a), wall_px(*(_reversed(b) if flip else b))],
        [det(label, centre - half, centre - half, centre + half, centre + half)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 1
    assert dropped["wallGapBridged"] == 1
    (opening,) = result.openings
    assert abs(opening.width_mm - gap) <= 30
    assert abs(opening.offset_mm - 1500) <= 30
    assert dropped["openingTooWide"] == 0


def test_build_walls__orthogonal_three_degrees_not_joined(fake_clock: FakeClock) -> None:
    """Bản vẽ thẳng trục giữ 2° của B5-05 [6] 3b: tường 0° và 3° có hộp cửa ở khe → không gộp."""
    rad = math.radians(3)
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(0, 1000, 1550, 1000), wall_px(2450, 1000, 2450 + 1550 * math.cos(rad), 1000 + 1550 * math.sin(rad))],
        [det("door", 1550, 950, 2450, 1050)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 2
    assert dropped["wallGapBridged"] == 0


def test_build_walls__diagonal_side_shifted_gap_not_joined(fake_clock: FakeClock) -> None:
    """Hai tường 45° song song lệch ngang 200 mm (> ½ bề dày) qua khe có hộp → không gộp, không đoạn nối."""
    shift = 200 / math.sqrt(2)
    b = _on_diagonal(2400, 45, 1500)
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(*_on_diagonal(0, 45, 1500)), wall_px(b[0] + shift, b[1] - shift, b[2] + shift, b[3] - shift)],
        [det("door", 1700, 1700, 2500, 2500)],
        fake_clock,
        dropped,
    )
    assert len(result.walls) == 2
    assert dropped["wallGapBridged"] == 0
    assert result.bridges == ()


def test_build_walls__diagonal_touching_walls_no_bridge(fake_clock: FakeClock) -> None:
    """Hai tường 45° nối đầu chạm đầu (khe 0): không phải cặp khe → không gộp, không đoạn nối."""
    dropped: Counter[str] = Counter()
    result = run([wall_px(1000, 1000, 2000, 2000), wall_px(2000, 2000, 3000, 3000)], [], fake_clock, dropped)
    assert len(result.walls) == 2
    assert result.bridges == ()


def test_build_walls__diagonal_endpoint_pulled_to_near_perpendicular(fake_clock: FakeClock) -> None:
    """3b-b chéo: tường 42° hụt 100 mm trước vách 135° (lệch 93°, ngoài 2° nhưng trong 5°) có hộp → kéo tới tim vách."""
    rad = math.radians(42)
    end = (3000 - 100 * math.cos(rad), 3000 - 100 * math.sin(rad))
    start = (end[0] - 2000 * math.cos(rad), end[1] - 2000 * math.sin(rad))
    reach = 1500 / math.sqrt(2)
    dropped: Counter[str] = Counter()
    result = run(
        [wall_px(*start, *end), wall_px(3000 + reach, 3000 - reach, 3000 - reach, 3000 + reach)],
        [det("door", 2900, 2900, 3050, 3050)],
        fake_clock,
        dropped,
    )
    assert dropped["wallGapBridged"] == 1
    pulled = result.walls[0].centreline.end
    assert abs(pulled.x - 3000) <= 2
    assert abs(pulled.y - 3000) <= 2
