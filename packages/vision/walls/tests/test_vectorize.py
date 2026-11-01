"""Vector hoá tường trên mặt nạ dựng bằng OpenCV (B5-02 khối [8], việc A).

Mặt nạ dựng tay nên đáp án biết trước: mọi khẳng định về số đoạn, đầu mút và bề dày
đều so với hình đã vẽ, không so với ảnh chụp kết quả.
"""

import itertools
import math
import threading

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.walls.types import VectorizeResult, WallSegment
from packages.vision.walls.vectorize import (
    _absorb_corner_diagonals,
    _arc_chords,
    _finalise,
    _Graph,
    _join_arcs,
    _merge_line_pieces,
    _off_node,
    _seated,
    _Seg,
    _straighten_jogs,
    keep_longest,
    vectorize,
    vectorize_with_stats,
)

THICK = 12
"""Bề dày tường mẫu (px); đủ dày để `distanceTransform` cho trung vị ổn định."""
SHAPE = (300, 400)
"""`(cao, rộng)` của khung vẽ mẫu."""


def _canvas(shape: tuple[int, int] = SHAPE) -> NDArray[np.uint8]:
    """Khung vẽ `uint8` rỗng."""
    return np.zeros(shape, np.uint8)


def _draw(canvas: NDArray[np.uint8], start: tuple[int, int], end: tuple[int, int]) -> None:
    """Một thanh dày `THICK`: thanh thẳng trục vẽ bằng `cv2.rectangle` để hai mút đúng
    toạ độ yêu cầu (`cv2.line` nới mút thêm ½ bề dày), thanh chéo vẫn dùng `cv2.line`."""
    half = THICK // 2
    if start[0] == end[0]:
        cv2.rectangle(canvas, (start[0] - half, start[1]), (end[0] + half - 1, end[1]), 1, cv2.FILLED)
    elif start[1] == end[1]:
        cv2.rectangle(canvas, (start[0], start[1] - half), (end[0], end[1] + half - 1), 1, cv2.FILLED)
    else:
        cv2.line(canvas, start, end, 1, THICK)


def _bars(*points: tuple[tuple[int, int], tuple[int, int]], shape: tuple[int, int] = SHAPE) -> NDArray[np.bool_]:
    """Mặt nạ bool gồm các thanh dày `THICK` nối từng cặp điểm `(x, y)`."""
    canvas = _canvas(shape)
    for start, end in points:
        _draw(canvas, start, end)
    return np.asarray(canvas > 0)


def _ends(walls: tuple[WallSegment, ...]) -> list[tuple[float, float]]:
    """Mọi đầu mút của các đoạn, để tìm góc chung."""
    return [point for wall in walls for point in (wall.start, wall.end)]


def _shares(walls: tuple[WallSegment, ...], count: int, tol: float = 1.0) -> int:
    """Số điểm được đúng `count` đoạn dùng chung (trong sai số `tol` px)."""
    points = _ends(walls)
    seen: list[tuple[float, float]] = []
    for point in points:
        if not any(math.dist(point, other) <= tol for other in seen):
            seen.append(point)
    return sum(1 for hub in seen if sum(1 for p in points if math.dist(p, hub) <= tol) == count)


def test_horizontal_bar_gives_one_segment() -> None:
    """Thanh ngang → một đoạn, hai mút đúng chỗ (± 2 px), bề dày đo ≈ `THICK`."""
    walls = vectorize(_bars(((50, 150), (350, 150))))
    assert len(walls) == 1
    assert abs(walls[0].start[0] - 50.0) <= 2.0
    assert abs(walls[0].end[0] - 350.0) <= 2.0
    assert abs(walls[0].thickness_px - THICK) <= 1.0


def test_corner_gives_two_segments_sharing_the_corner() -> None:
    """Góc chữ L → hai đoạn dùng chung đúng một đầu mút ở góc."""
    walls = vectorize(_bars(((60, 60), (60, 240)), ((60, 240), (340, 240))))
    assert len(walls) == 2
    assert _shares(walls, 2) == 1


def test_tee_gives_two_segments_meeting_on_the_through_wall() -> None:
    """Chữ T → tường xuyên một đoạn ngang, chân chữ T dừng trên tim tường xuyên."""
    walls = vectorize(_bars(((40, 120), (360, 120)), ((200, 120), (200, 260))))
    assert len(walls) == 2
    through = max(walls, key=lambda w: w.end[0] - w.start[0])
    stem = min(walls, key=lambda w: w.end[0] - w.start[0])
    assert through.start[1] == through.end[1]
    assert abs(stem.start[1] - through.start[1]) <= 1.0
    assert through.start[0] <= stem.start[0] <= through.end[0]


def test_cross_gives_two_segments() -> None:
    """Chữ thập → hai đoạn xuyên nút (gộp thẳng hàng qua giao điểm)."""
    walls = vectorize(_bars(((40, 150), (360, 150)), ((200, 40), (200, 260))))
    assert len(walls) == 2


def test_rectangle_frame_gives_four_segments_and_four_corners() -> None:
    """Khung chữ nhật (vòng kín) → bốn đoạn, bốn góc mỗi góc hai đoạn dùng chung."""
    corners = [(60, 60), (340, 60), (340, 240), (60, 240)]
    walls = vectorize(_bars(*zip(corners, corners[1:] + corners[:1], strict=True)))
    assert len(walls) == 4
    assert _shares(walls, 2, tol=2.0) == 4


def test_bar_tilted_three_degrees_is_snapped_horizontal() -> None:
    """Thanh lệch 3° (≤ 5°) bị ép về ngang."""
    drop = round(300 * math.tan(math.radians(3.0)))
    walls = vectorize(_bars(((50, 150), (350, 150 + drop))))
    assert len(walls) == 1
    assert walls[0].start[1] == walls[0].end[1]


def test_bar_tilted_thirty_degrees_keeps_its_angle() -> None:
    """Thanh lệch 30° giữ góc (± 1°), không ép trục."""
    drop = round(250 * math.tan(math.radians(30.0)))
    walls = vectorize(_bars(((70, 60), (320, 60 + drop))))
    assert len(walls) == 1
    angle = math.degrees(math.atan2(walls[0].end[1] - walls[0].start[1], walls[0].end[0] - walls[0].start[0]))
    assert abs(abs(angle) - 30.0) <= 1.0


def test_isolated_block_is_dropped_as_short() -> None:
    """Khối vuông cô lập cỡ bề dày tường không thành tường, đếm một `short`."""
    canvas = _canvas()
    cv2.rectangle(canvas, (100, 100), (100 + THICK - 1, 100 + THICK - 1), 1, cv2.FILLED)
    result = vectorize_with_stats(np.asarray(canvas > 0))
    assert result.walls == ()
    assert result.dropped["short"] == 1


def test_single_pixel_skeleton_is_counted_short() -> None:
    """Xương một điểm không hàng xóm (ô 3x3) không được làm vỡ bước dò vòng kín."""
    canvas = _canvas()
    cv2.rectangle(canvas, (100, 100), (102, 102), 1, cv2.FILLED)
    result = vectorize_with_stats(np.asarray(canvas > 0))
    assert result.walls == ()
    assert result.dropped["short"] == 1


def test_isolated_block_beside_a_wall_keeps_the_wall() -> None:
    """Cụm xương cô lập cạnh tường: tường vẫn ra, cụm kia đếm `short`."""
    canvas = _canvas()
    _draw(canvas, (40, 60), (360, 60))
    cv2.rectangle(canvas, (100, 200), (102, 202), 1, cv2.FILLED)
    result = vectorize_with_stats(np.asarray(canvas > 0))
    assert len(result.walls) == 1
    assert result.dropped["short"] == 1


def test_spur_branch_is_pruned() -> None:
    """Gai 1 px nhô khỏi mặt tường (đầu tự do trên biên mặt nạ) là râu thinning: bị cắt.

    Nét 4 px trước đây là cùng hình với vách thật thu nhỏ (NO-288), nên mẫu râu là nét 1 px.
    """
    canvas = _canvas()
    _draw(canvas, (40, 150), (360, 150))
    cv2.line(canvas, (200, 150), (200, 158), 1, 1)
    result = vectorize_with_stats(np.asarray(canvas > 0))
    assert result.dropped["spur"] > 0
    assert len(result.walls) == 1


def test_empty_mask_gives_no_walls() -> None:
    """Mặt nạ rỗng → không đoạn nào, `dropped` đủ hai khoá bằng 0."""
    result = vectorize_with_stats(np.zeros(SHAPE, np.bool_))
    assert result.walls == ()
    assert result.dropped == {"spur": 0, "short": 0}


def test_three_dimensional_mask_is_rejected() -> None:
    """Mảng 3 chiều → `ValueError`."""
    with pytest.raises(ValueError, match="2 chiều"):
        vectorize(np.zeros((4, 4, 3), np.bool_))


def test_non_boolean_mask_is_rejected() -> None:
    """Mảng không phải bool → `ValueError`."""
    with pytest.raises(ValueError, match="bool"):
        vectorize(np.zeros(SHAPE, np.uint8))


def test_confidence_stays_in_unit_range() -> None:
    """Độ tin của mọi đoạn nằm trong [0, 1]."""
    walls = vectorize(_bars(((40, 120), (360, 120)), ((200, 120), (200, 260))))
    assert walls
    assert all(0.0 <= wall.confidence <= 1.0 for wall in walls)


def test_two_calls_give_the_same_result() -> None:
    """Hai lần gọi trên cùng mặt nạ cho cùng kết quả (tất định)."""
    mask = _bars(((60, 60), (60, 240)), ((60, 240), (340, 240)))
    assert vectorize(mask) == vectorize(mask)


def test_rotating_the_mask_keeps_the_segment_count() -> None:
    """Xoay mặt nạ 90° không đổi số đoạn."""
    mask = _bars(((40, 120), (360, 120)), ((200, 120), (200, 260)))
    assert len(vectorize(np.ascontiguousarray(np.rot90(mask)))) == len(vectorize(mask))


def test_wall_touching_the_border_stays_inside_the_image() -> None:
    """Tường chạm mép ảnh: mọi đầu mút bị kẹp trong khung ảnh."""
    height, width = SHAPE
    walls = vectorize(_bars(((0, 150), (width - 1, 150))))
    assert walls
    for point in _ends(walls):
        assert 0.0 <= point[0] <= width - 1
        assert 0.0 <= point[1] <= height - 1


def test_diagonal_pair_averages_the_shared_endpoint() -> None:
    """Hai thanh chéo nối nhau vẫn ra đoạn, độ tin trong [0, 1]."""
    walls = vectorize(_bars(((40, 40), (200, 130)), ((200, 130), (360, 220))))
    assert len(walls) >= 1
    assert all(0.0 <= wall.confidence <= 1.0 for wall in walls)


def _stub(index: int, length: float) -> WallSegment:
    """Đoạn ngang dài `length` ở hàng `index`, để thử `keep_longest` không cần ảnh."""
    return WallSegment(start=(0.0, float(index)), end=(length, float(index)), thickness_px=10.0, confidence=1.0)


def test_keep_longest_drops_the_shortest_segment() -> None:
    """Vượt `MAX_WALLS` một đoạn → bỏ đoạn ngắn nhất, kết quả sắp theo `(start, end)`."""
    walls = tuple(_stub(i, 100.0 + i) for i in range(20_001))
    kept = keep_longest(walls)
    assert len(kept) == 20_000
    assert walls[0] not in kept
    assert kept == tuple(sorted(kept, key=lambda w: (w.start, w.end)))


def test_keep_longest_passes_short_lists_through() -> None:
    """Danh sách dưới trần đi qua nguyên vẹn."""
    walls = (_stub(0, 50.0), _stub(1, 60.0))
    assert keep_longest(walls) == walls


def _stub_on_outer_wall(
    mm_per_px: float, partition_mm: int, face_mm: int, outer_mm: int = 220
) -> tuple[NDArray[np.bool_], int, int]:
    """Tường bao `outer_mm` nằm ngang, vách `partition_mm` chĩa xuống dài `face_mm` từ mặt trong rồi hở.

    Giống đoạn vách giữa tường bao và khe cửa của `render_plan` (cửa cách tim vách ≥ 300 mm).
    Trả mặt nạ, bề dày vách (px) và `y` mép dưới của vách.
    """
    outer = math.floor(outer_mm / mm_per_px + 0.5)
    partition = math.floor(partition_mm / mm_per_px + 0.5)
    face = math.floor(face_mm / mm_per_px + 0.5)
    mask = np.zeros((300, 600), np.bool_)
    mask[60 : 60 + outer, 50:550] = True
    left = 300 - partition // 2
    mask[60 + outer : 60 + outer + face, left : left + partition] = True
    return mask, partition, 60 + outer + face


@pytest.mark.parametrize("mm_per_px", [8.0, 10.0, 12.5])
@pytest.mark.parametrize("partition_mm", [110, 150])
@pytest.mark.parametrize("face_mm", [120, 150, 190])
def test_vectorize__short_thin_wall_on_thick_wall_is_kept(mm_per_px: float, partition_mm: int, face_mm: int) -> None:
    """Vách 110/150 mm ngắn chạm tường bao 220 mm là tường thật, không bị cắt như râu thinning."""
    mask, partition, bottom = _stub_on_outer_wall(mm_per_px, partition_mm, face_mm)
    stubs = [w for w in vectorize(mask) if w.start[0] == w.end[0] and abs(w.start[0] - 300) <= partition]
    assert stubs, "mất vách ngắn"
    assert abs(max(w.end[1] for w in stubs) - bottom) <= 3.0


@pytest.mark.parametrize("mm_per_px", [8.0, 12.5])
def test_vectorize__very_thin_wall_on_very_thick_wall_is_kept(mm_per_px: float) -> None:
    """Vách 100 mm chạm tường 400 mm (T/J ≈ 0,2, mọi ngưỡng tỉ lệ đều cắt) vẫn là tường."""
    mask, partition, bottom = _stub_on_outer_wall(mm_per_px, 100, 190, outer_mm=400)
    stubs = [w for w in vectorize(mask) if w.start[0] == w.end[0] and abs(w.start[0] - 300) <= partition]
    assert stubs, "mất vách ngắn"
    assert abs(max(w.end[1] for w in stubs) - bottom) <= 3.0


_JUNCTION_SELF_LOOP: tuple[str, ...] = (
    ".....#########",
    "....##########",
    "....##########",
    "...###########",
    "...###########",
    "...###########",
    "...###########",
    "..############",
    "..############",
    "..############",
    "....##########",
    ".......#######",
    "........######",
    "........######",
    "........######",
    "........######",
)
"""Mặt nạ SegFormer 16 x 14 cắt từ trang CubiCasa `high_quality_architectural-7809` quanh (45, 113).

Bỏ râu xong còn một điểm xương nối hai điểm của cùng một cụm giao: nhánh đi từ nút về chính nút
đó, cho đoạn dài 0 có hai đầu cùng một khoá, mà đoạn tường giữ lại vẫn dùng khoá ấy.
"""


def test_vectorize__branch_back_to_its_own_junction_terminates() -> None:
    """Đoạn ngắn có hai đầu cùng khoá không làm `_drop_short` lặp mãi (trang thật từng treo > 30 phút).

    Chạy trong luồng nền có hạn 10 s: lỗi cũ quay vô hạn trong `_resolve`, test phải đỏ chứ không treo cổng.
    """
    mask = np.array([[cell == "#" for cell in row] for row in _JUNCTION_SELF_LOOP])
    result: list[VectorizeResult] = []
    worker = threading.Thread(target=lambda: result.append(vectorize_with_stats(mask)), daemon=True)
    worker.start()
    worker.join(timeout=10.0)
    assert result, "vectorize_with_stats không xong trong 10 s"
    assert result[0].walls


def test_finalise__ends_that_collapse_after_rounding_are_dropped() -> None:
    """BUG-P09-008: hai đầu lệch < 0.005 px bằng nhau sau làm tròn → bỏ và tính vào `short`."""
    key = (0, 0, 0)
    seg = _Seg(615.1201, 720.2501, 615.1203, 720.2499, 4.0, 0.9, key, key)
    walls, short = _finalise([seg], (1000, 1000))
    assert walls == ()
    assert short == 1


def _axis_aligned(wall: WallSegment) -> bool:
    """Đoạn nằm đúng ngang hay đúng dọc."""
    return wall.start[0] == wall.end[0] or wall.start[1] == wall.end[1]


def test_vectorize__snapped_wall_stays_vertical_at_a_diagonal_corner() -> None:
    """K-02: thanh lệch 3° (đã ép dọc) nối thanh chéo 28° — nút dọc + chéo không kéo lệch thanh dọc lại."""
    walls = vectorize(_bars(((100, 240), (109, 70)), ((109, 70), (330, 190))))
    assert len(walls) == 2
    upright = max(walls, key=lambda w: abs(w.end[1] - w.start[1]))
    assert upright.start[0] == upright.end[0]
    assert _shares(walls, 2) == 1


def test_vectorize__corner_chamfer_is_absorbed_on_an_orthogonal_plan() -> None:
    """K-02: vát chéo ngắn (< 3 x bề dày) ở góc chữ L của bản vẽ vuông góc → hai tường gặp nhau đúng góc."""
    walls = vectorize(_bars(((72, 60), (360, 60)), ((60, 72), (60, 260)), ((60, 72), (72, 60))))
    assert len(walls) == 2
    assert all(_axis_aligned(wall) for wall in walls)
    assert _shares(walls, 2) == 1


def test_vectorize__short_diagonal_stub_at_a_corner_is_dropped() -> None:
    """K-02: râu chéo ngắn chĩa ra từ góc chữ L (một đầu tự do) bị bỏ và đếm `short`."""
    result = vectorize_with_stats(_bars(((60, 60), (60, 240)), ((60, 240), (340, 240)), ((60, 240), (45, 262))))
    assert len(result.walls) == 2
    assert all(_axis_aligned(wall) for wall in result.walls)
    assert result.dropped["short"] >= 1


def test_vectorize__kinked_wall_still_reaches_the_through_wall() -> None:
    """K-02: vách dọc bẻ chéo ngắn ngay trước tường xuyên → vách vẫn dọc và chạm tim tường xuyên."""
    walls = vectorize(_bars(((40, 60), (360, 60)), ((180, 260), (180, 84)), ((180, 84), (192, 60))))
    assert len(walls) == 2
    assert all(_axis_aligned(wall) for wall in walls)
    stem = max(walls, key=lambda w: abs(w.end[1] - w.start[1]))
    through = max(walls, key=lambda w: abs(w.end[0] - w.start[0]))
    assert abs(min(stem.start[1], stem.end[1]) - through.start[1]) <= 2.0


def test_vectorize__isolated_short_diagonal_is_dropped_on_an_orthogonal_plan() -> None:
    """Vụn chéo cô lập (< 3 x bề dày) cạnh khung vuông góc bị bỏ; tường chéo dài vẫn giữ (thử 30° ở trên)."""
    corners = [(60, 60), (340, 60), (340, 240), (60, 240)]
    frame = list(zip(corners, corners[1:] + corners[:1], strict=True))
    result = vectorize_with_stats(_bars(*frame, ((150, 140), (170, 160))))
    assert len(result.walls) == 4
    assert result.dropped["short"] >= 1


def test_finalise__duplicate_segment_keeps_the_more_confident_one() -> None:
    """K-02 (BITG/EM8D): hai đoạn cùng hai đầu mút (kể cả ngược chiều) → giữ một, độ tin cao hơn."""
    low = _Seg(10.0, 10.0, 60.0, 40.0, 4.0, 0.6, (0, 0, 0), (0, 1, 0))
    high = _Seg(60.0, 40.0, 10.0, 10.0, 8.0, 0.9, (0, 1, 0), (0, 0, 0))
    walls, short = _finalise([low, high], (100, 100))
    assert len(walls) == 1
    assert walls[0].confidence == 0.9
    assert short == 0


def _column_room(column: int, side: int) -> NDArray[np.bool_]:
    """Phòng vuông cạnh `side` (tim tường), cột đặc `column` x `column` ở bốn góc, áp mặt ngoài tường."""
    canvas = _canvas()
    half, low, high = THICK // 2, 60, 60 + side
    corners = [(low, low), (high, low), (high, high), (low, high)]
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        _draw(canvas, min(start, end), max(start, end))
    for x, y in corners:
        left = x - half if x == low else x + half - column
        top = y - half if y == low else y + half - column
        cv2.rectangle(canvas, (left, top), (left + column - 1, top + column - 1), 1, cv2.FILLED)
    return np.asarray(canvas > 0)


@pytest.mark.parametrize("column", [20, 24, 28])
@pytest.mark.parametrize("side", [50, 100])
def test_vectorize__room_with_corner_columns_is_all_orthogonal(column: int, side: int) -> None:
    """UX41: cột tô đặc to hơn tường ở bốn góc không đẻ vụn chéo; ra đúng bốn tường ngang/dọc khép góc."""
    walls = vectorize(_column_room(column, side))
    assert all(_axis_aligned(wall) for wall in walls), walls
    assert len(walls) == 4
    assert _shares(walls, 2, tol=2.0) == 4


def test_vectorize__short_wall_pulled_by_a_column_stays_horizontal() -> None:
    """UX41: vách ngắn (~3,5 x bề dày) từ cột lệch tâm tới khe cửa — trọng tâm nút kéo lệch ~7°, vẫn phải ngang."""
    canvas = _canvas()
    half = THICK // 2
    _draw(canvas, (40, 40), (360, 40))
    _draw(canvas, (100, 40), (100, 260))
    cv2.rectangle(canvas, (88, 142), (111, 165), 1, cv2.FILLED)
    cv2.rectangle(canvas, (100, 150 - half), (140, 150 + half - 1), 1, cv2.FILLED)
    walls = vectorize(np.asarray(canvas > 0))
    assert all(_axis_aligned(wall) for wall in walls), walls
    stub = next(w for w in walls if w.start[1] == w.end[1] and abs(w.start[1] - 150) <= 3.0)
    assert abs(stub.start[0] - 100) <= 2.0
    assert abs(stub.end[0] - 140) <= 3.0


@pytest.mark.parametrize(("end", "angle"), [((350, 300), 45.0), ((350, 135), 10.0)])
def test_vectorize__real_diagonal_stays_diagonal_on_an_orthogonal_plan(end: tuple[int, int], angle: float) -> None:
    """UX41: tường chéo 45° và tường chéo thoải dài (lệch ngang ≈ 3 x bề dày) trong khung vuông góc giữ góc."""
    corners = [(40, 40), (760, 40), (760, 560), (40, 560)]
    frame = list(zip(corners, corners[1:] + corners[:1], strict=True))
    walls = vectorize(_bars(*frame, ((150, 100), end), shape=(600, 800)))
    diagonal = [wall for wall in walls if not _axis_aligned(wall)]
    assert len(diagonal) == 1
    dx, dy = diagonal[0].end[0] - diagonal[0].start[0], diagonal[0].end[1] - diagonal[0].start[1]
    assert abs(math.degrees(math.atan2(abs(dy), abs(dx))) - angle) <= 1.0


def _tilt(wall: WallSegment) -> float:
    """Góc lệch trục gần nhất của đoạn (độ, trong `[-45, 45)`)."""
    angle = math.degrees(math.atan2(wall.end[1] - wall.start[1], wall.end[0] - wall.start[0]))
    return (angle + 45.0) % 90.0 - 45.0


def _rotated(points: list[tuple[float, float]], degrees: float, centre: tuple[float, float]) -> list[tuple[int, int]]:
    """Xoay các điểm quanh `centre` rồi làm tròn về px."""
    cos, sin = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    cx, cy = centre
    return [
        (round(cx + (x - cx) * cos - (y - cy) * sin), round(cy + (x - cx) * sin + (y - cy) * cos)) for x, y in points
    ]


def test_vectorize__room_rotated_two_degrees_keeps_its_own_axes() -> None:
    """UX41-A: phòng quét lệch 2° ra bốn tường trên hệ trục **của nó** (2° ± 0,3°), bốn góc khép kín."""
    corners = _rotated([(80, 60), (320, 60), (320, 240), (80, 240)], 2.0, (200, 150))
    canvas = _canvas()
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        cv2.line(canvas, start, end, 1, THICK)
    walls = vectorize(np.asarray(canvas > 0))
    assert len(walls) == 4
    assert all(abs(_tilt(wall) - 2.0) <= 0.3 for wall in walls), [_tilt(wall) for wall in walls]
    assert _shares(walls, 2, tol=0.5) == 4


def test_vectorize__collinear_walls_across_a_door_gap_share_one_line() -> None:
    """UX41-A: hai đoạn ngang hai bên khe cửa lệch tim 4 px (< ½ bề dày) → cùng một `y`, dù không chung đầu mút."""
    walls = vectorize(_bars(((40, 150), (180, 150)), ((240, 154), (360, 154))))
    assert len(walls) == 2
    assert {wall.start[1] for wall in walls} == {wall.end[1] for wall in walls}
    assert len({wall.start[1] for wall in walls}) == 1


def test_vectorize__parallel_walls_one_thickness_apart_stay_separate() -> None:
    """UX41-A: hai đoạn ngang tim cách nhau đúng một bề dày là hai đường tường, không gộp toạ độ."""
    walls = vectorize(_bars(((40, 150), (180, 150)), ((240, 150 + THICK), (360, 150 + THICK))))
    assert len(walls) == 2
    ys = sorted(wall.start[1] for wall in walls)
    assert abs(ys[1] - ys[0] - THICK) <= 1.0


def test_vectorize__tee_stopping_half_a_thickness_short_reaches_the_through_wall() -> None:
    """UX41-A: vách đứng dừng cách mặt tường ngang ½ bề dày (mặt nạ hở) → đầu mút đặt đúng lên tim tường ngang."""
    canvas = _canvas()
    _draw(canvas, (40, 60), (360, 60))
    cv2.rectangle(canvas, (200 - THICK // 2, 60 + THICK // 2 + THICK // 2), (200 + THICK // 2 - 1, 260), 1, cv2.FILLED)
    walls = vectorize(np.asarray(canvas > 0))
    through = next(wall for wall in walls if wall.start[1] == wall.end[1])
    stem = next(wall for wall in walls if wall.start[0] == wall.end[0])
    assert min(stem.start[1], stem.end[1]) == through.start[1]


def test_vectorize__diagonal_stays_diagonal_in_a_rotated_room() -> None:
    """UX41-A: tường chéo 45° thật trong phòng lệch 2° vẫn chéo (≈ 47°), không bị ép trục."""
    corners = _rotated([(60, 40), (740, 40), (740, 560), (60, 560)], 2.0, (400, 300))
    diag = _rotated([(150, 100), (350, 300)], 2.0, (400, 300))
    canvas = _canvas((600, 800))
    for start, end in [*zip(corners, corners[1:] + corners[:1], strict=True), (diag[0], diag[1])]:
        cv2.line(canvas, start, end, 1, THICK)
    walls = vectorize(np.asarray(canvas > 0))
    diagonal = [wall for wall in walls if abs(abs(_tilt(wall)) - 2.0) > 1.0]
    assert len(diagonal) == 1
    dx, dy = diagonal[0].end[0] - diagonal[0].start[0], diagonal[0].end[1] - diagonal[0].start[1]
    assert abs(math.degrees(math.atan2(abs(dy), abs(dx))) - 47.0) <= 1.5


def _piece(ax: float, ay: float, bx: float, by: float, thickness: float, keys: tuple[int, int], axis: str) -> _Seg:
    """`_Seg` dựng tay cho bước 10c/10d: khoá `(1, k, 0)` theo cặp số cho sẵn."""
    return _Seg(ax, ay, bx, by, thickness, 0.9, (1, keys[0], 0), (1, keys[1], 0), axis)


def _spans(segs: list[_Seg]) -> list[tuple[float, float, float, float, float]]:
    """Toạ độ và bề dày, sắp xếp để so không phụ thuộc thứ tự."""
    return sorted((s.ax, s.ay, s.bx, s.by, s.thickness) for s in segs)


def test_merge_line_pieces__touching_overlapping_and_contained() -> None:
    """Khúc chạm/chồng cùng bề dày gộp một; khúc mảnh nằm trong bỏ; cột dày, khúc khác dày, khe cửa giữ riêng."""
    segs = [
        _piece(0, 50, 40, 50, 10, (1, 2), "h"),
        _piece(40, 50, 90, 50, 11, (2, 3), "h"),  # chạm, 10/11 → gộp
        _piece(85, 50, 120, 50, 10, (4, 5), "h"),  # chồng → gộp
        _piece(10, 50, 30, 50, 9, (6, 7), "h"),  # nằm trong, mảnh hơn → bỏ
        _piece(60, 50, 70, 50, 30, (8, 9), "h"),  # cột dày nằm trong → giữ
        _piece(120, 50, 160, 50, 20, (5, 10), "h"),  # chạm nhưng dày gấp đôi → riêng
        _piece(200, 50, 240, 50, 20, (11, 12), "h"),  # cách khe cửa → riêng
        _piece(0, 0, 30, 40, 10, (13, 14), "d"),  # chéo đi qua nguyên vẹn
        _piece(300, 0, 300, 40, 10, (15, 16), "v"),
    ]
    out = _merge_line_pieces(segs)
    assert len(out) == 6
    merged = next(s for s in out if s.axis == "h" and s.ax == 0)
    assert (merged.bx, merged.a_key, merged.b_key) == (120, (1, 1, 0), (1, 5, 0))
    assert 10.0 < merged.thickness < 11.0
    assert sorted((s.ax, s.bx) for s in out if s.axis == "h") == [(0, 120), (60, 70), (120, 160), (200, 240)]


def test_straighten_jogs__z_becomes_one_line_and_l_corner_follows() -> None:
    """Chữ Z lệch 12 px (≤ 1,5 bề dày): đoạn ngắn lên tim đoạn dài, chéo bỏ, góc L ở đầu kia dời theo."""
    top = _piece(50, 0, 100, 0, 10, (0, 1), "h")
    short = _piece(100, 0, 100, 40, 10, (1, 2), "v")
    diag = _piece(100, 40, 112, 60, 10, (2, 3), "d")
    long_ = _piece(112, 60, 112, 200, 10, (3, 4), "v")
    out = _merge_line_pieces(_straighten_jogs([top, short, diag, long_]))
    assert all(s.axis != "d" for s in out)
    assert _spans(out) == [(50, 0, 112, 0, 10), (112, 0, 112, 200, 10)]


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param([], id="offset-too-wide"),
        pytest.param([_piece(140, 40, 160, 40, 10, (2, 9), "h")], id="junction-at-diag-end"),
    ],
)
def test_straighten_jogs__real_offsets_and_junctions_kept(extra: list[_Seg]) -> None:
    """Lệch 40 px (> 1,5 bề dày) là hai tường thật; đầu chéo nối hai tường là giao thật → giữ đoạn chéo."""
    offset = 40 if not extra else 12
    segs = [
        _piece(100, 0, 100, 40, 10, (1, 2), "v"),
        _piece(100, 40, 100 + offset, 60, 10, (2, 3), "d"),
        _piece(100 + offset, 60, 100 + offset, 300, 10, (3, 4), "v"),
        *extra,
    ]
    assert sum(s.axis == "d" for s in _straighten_jogs(segs)) == 1


@pytest.mark.parametrize(
    "segs",
    [
        pytest.param(
            [
                _piece(100, 30, 100, 40, 10, (1, 2), "v"),
                _piece(100, 40, 112, 20, 10, (2, 3), "d"),
                _piece(112, 20, 112, 200, 10, (3, 4), "v"),
            ],
            id="would-flip",
        ),
        pytest.param(
            [
                _piece(0, 40, 100, 40, 10, (1, 2), "h"),
                _piece(100, 40, 112, 60, 10, (2, 3), "d"),
                _piece(112, 60, 112, 200, 10, (3, 4), "v"),
            ],
            id="h-then-v",
        ),
        pytest.param(
            [
                _piece(100, 0, 100, 40, 10, (1, 2), "v"),
                _piece(100, 40, 106, 50, 10, (2, 3), "d"),
                _piece(106, 50, 112, 60, 10, (3, 4), "d"),
                _piece(112, 60, 112, 200, 10, (4, 5), "v"),
            ],
            id="diag-chain",
        ),
        pytest.param(
            [
                _piece(0, 0, 300, 200, 10, (1, 2), "d"),
                _piece(300, 200, 312, 220, 10, (2, 3), "d"),
                _piece(312, 220, 312, 240, 10, (3, 4), "v"),
            ],
            id="not-orthogonal",
        ),
    ],
)
def test_straighten_jogs__left_alone(segs: list[_Seg]) -> None:
    """Không nắn: đoạn ngắn sẽ đổi chiều, hai tường khác trục (góc L), chuỗi chéo, bản vẽ không vuông góc."""
    before = _spans(segs)
    assert _spans(_straighten_jogs(segs)) == before


def _room_with_box(
    *marks: tuple[tuple[int, int], tuple[int, int]], box: tuple[int, int, int, int]
) -> NDArray[np.bool_]:
    """Phòng 280 x 180 (tim) tường `THICK`, hộp `box = (trái, trên, phải, dưới)` vách 6 px, nét chéo 3 px `marks`."""
    corners = [(60, 60), (340, 60), (340, 240), (60, 240)]
    canvas = _canvas()
    for start, end in zip(corners, corners[1:] + corners[:1], strict=True):
        _draw(canvas, min(start, end), max(start, end))
    left, top, right, bottom = box
    cv2.rectangle(canvas, (left, top), (right, bottom), 1, 6)
    for start, end in marks:
        cv2.line(canvas, start, end, 1, 3)
    return np.asarray(canvas > 0)


@pytest.mark.parametrize(
    ("box", "marks"),
    [
        ((280, 60, 340, 120), [((280, 60), (340, 120)), ((340, 60), (280, 120))]),
        ((280, 60, 340, 120), [((280, 120), (340, 60))]),
        ((150, 120, 200, 170), [((150, 120), (200, 170)), ((200, 120), (150, 170))]),
    ],
)
def test_vectorize__shaft_box_cross_marks_are_not_walls(
    box: tuple[int, int, int, int], marks: list[tuple[tuple[int, int], tuple[int, int]]]
) -> None:
    """Hộp kỹ thuật gạch chéo (X hay một nét) ở góc phòng hay giữa phòng: không ra tường xiên, vách hộp còn đủ."""
    walls = vectorize(_room_with_box(*marks, box=box))
    assert all(_axis_aligned(wall) for wall in walls), walls
    left, top, right, bottom = box
    inside = [
        w for w in walls if all(left - 3 <= x <= right + 3 and top - 3 <= y <= bottom + 3 for x, y in _ends((w,)))
    ]
    assert all(math.dist(w.start, w.end) >= 0.8 * min(right - left, bottom - top) for w in inside), inside


def test_vectorize__chamfer_inside_a_small_box_stays_diagonal() -> None:
    """Vát góc thật trong ô nhỏ (đầu nằm giữa cạnh ô, không ở góc hay tâm) không bị coi là ký hiệu hộp."""
    walls = vectorize(_room_with_box(((280, 90), (310, 60)), box=(250, 60, 340, 150)))
    assert sum(1 for wall in walls if not _axis_aligned(wall)) == 1


def _bay(*points: tuple[int, int]) -> NDArray[np.bool_]:
    """Ba cạnh phòng vuông góc mở bên phải, nối bằng đường `points` từ (300, 50) tới (300, 350); nét dày 10 px."""
    canvas = np.zeros((420, 520), np.uint8)
    for start, end in [
        ((50, 50), (300, 50)),
        ((50, 50), (50, 350)),
        ((50, 350), (300, 350)),
        *itertools.pairwise(points),
    ]:
        cv2.line(canvas, start, end, 1, 10)
    return np.asarray(canvas > 0)


def _apex(wall: WallSegment) -> tuple[float, float]:
    """Điểm giữa cung theo quy ước `sagitta_px`: trung điểm dây - sagitta · n, `n = (-dy, dx) / L`."""
    (ax, ay), (bx, by) = wall.start, wall.end
    length = math.dist(wall.start, wall.end)
    nx, ny = -(by - ay) / length, (bx - ax) / length
    return ((ax + bx) / 2 - wall.sagitta_px * nx, (ay + by) / 2 - wall.sagitta_px * ny)


@pytest.mark.parametrize(("sweep", "least"), [(90, 80), (180, 150)])
def test_vectorize__circular_wall_becomes_one_curved_wall(sweep: int, least: int) -> None:
    """Tường cong là MỘT tường có sagitta: hai đầu và đỉnh cung nằm trên đường tròn vẽ, quét gần hết cung vẽ.

    Hai đầu cung sát nút giao bị xén thành đoạn thẳng ngắn nên góc quét đo được nhỏ hơn cung vẽ đôi chút.
    """
    canvas = np.asarray(_bay(), np.uint8)
    cv2.ellipse(canvas, (300, 200), (150, 150), 0, -90, -90 + sweep, 1, 10)
    if sweep == 90:
        cv2.line(canvas, (450, 200), (300, 350), 1, 10)
    (wall,) = [wall for wall in vectorize(canvas > 0) if wall.sagitta_px]
    for point in (wall.start, wall.end, _apex(wall)):
        assert abs(math.dist(point, (300, 200)) - 150) <= 1.5, wall
    turned = 4 * math.degrees(math.atan(2 * abs(wall.sagitta_px) / math.dist(wall.start, wall.end)))
    assert least <= turned <= sweep + 2


def test_join_arcs__splits_a_chain_sweeping_past_170_degrees() -> None:
    """Chuỗi dây quét 200° (sagitta không tả được cung > 180°) → hai tường cong cùng đường tròn, nối nhau ở giữa."""
    points = [(100 * math.cos(math.radians(a)), 100 * math.sin(math.radians(a))) for a in range(0, 201, 10)]
    keys = [(0, 0, 0), *((2, 0, k) for k in range(len(points) - 2)), (0, 0, 1)]
    chords = [
        _Seg(*one, *two, 8.0, 0.9, keys[k], keys[k + 1], arc=True)
        for k, (one, two) in enumerate(itertools.pairwise(points))
    ]
    arcs = _join_arcs(chords)
    assert len(arcs) == 2
    assert (arcs[0].bx, arcs[0].by) == (arcs[1].ax, arcs[1].ay)
    for arc in arcs:
        wall = WallSegment((arc.ax, arc.ay), (arc.bx, arc.by), 8.0, 0.9, arc.sagitta)
        assert math.dist(_apex(wall), (0.0, 0.0)) == pytest.approx(100.0, abs=0.5)


def test_join_arcs__lone_arc_chord_stays_straight() -> None:
    """Dây cung còn trơ một mình (hai dây kề đã mất) không có cung để gộp: giữ là tường thẳng."""
    chord = _Seg(0.0, 0.0, 10.0, 0.0, 8.0, 0.9, (2, 0, 0), (2, 0, 1), arc=True)
    assert _join_arcs([chord]) == [chord]


@pytest.mark.parametrize(("key", "kept"), [((0, 3, 0), 8), ((1, 3, 0), 20)])
def test_off_node__drops_skeleton_within_one_thickness_of_a_junction_end(key: tuple[int, int, int], kept: int) -> None:
    """Đầu cuối là nút giao (khoá loại 0): bỏ điểm xương trong 1 bề dày quanh nó; đỉnh DP thường giữ đủ."""
    seg = _Seg(0.0, 0.0, 19.0, 0.0, 11.0, 0.9, (1, 3, 1), key)
    inner = np.stack([np.arange(20), np.zeros(20)], axis=1).astype(np.int32)
    assert len(_off_node(seg, inner)) == kept


def test_seated__free_arc_end_lands_on_the_wall_body_it_sits_in() -> None:
    """Đầu cung lơ lửng trong thân tường dọc (cách tim 13 < ½ tổng bề dày) → lên tim; đầu đã chung nút giữ nguyên."""
    chord = _Seg(700.0, 900.0, 782.0, 865.0, 24.0, 0.9, (2, 0, 1), (0, 2, 0), arc=True)
    stub = _Seg(795.0, 800.0, 795.0, 888.0, 24.0, 0.9, (0, 1, 0), (0, 5, 0), "v")
    far = _Seg(900.0, 100.0, 900.0, 300.0, 24.0, 0.9, (0, 6, 0), (0, 7, 0), "v")
    assert _seated((782.0, 865.0), 24.0, [chord], [chord, stub, far]) == (795.0, 865.0)
    assert _seated((795.0, 800.0), 24.0, [chord], [chord, stub, far]) == (795.0, 800.0)
    assert _seated((600.0, 950.0), 24.0, [chord], [chord, stub, far]) == (600.0, 950.0)


def test_finalise__curved_wall_flips_sagitta_with_its_ends_and_keeps_its_straight_twin() -> None:
    """Đảo đầu → đổi dấu sagitta (cung không đổi); tường thẳng chung hai đầu với cung vẫn giữ (khác ô gộp)."""
    keys = ((0, 0, 0), (0, 0, 1))
    arc = _Seg(200.0, 50.0, 100.0, 50.0, 8.0, 0.9, *keys, arc=True, sagitta=-20.0)
    line = _Seg(100.0, 50.0, 200.0, 50.0, 8.0, 0.9, *keys)
    walls, short = _finalise([arc, line], (200, 300))
    assert short == 0
    assert sorted(w.sagitta_px for w in walls) == [0.0, 20.0]
    assert _apex(next(w for w in walls if w.sagitta_px)) == (150.0, 30.0)


def test_vectorize__faceted_bay_keeps_its_corners() -> None:
    """Bow-window gãy góc (45°, bốn cạnh lệch hướng) không bị nắn thành cung: giữ đúng số cạnh và đỉnh."""
    walls = vectorize(_bay((300, 50), (371, 121), (371, 279), (300, 350)))
    assert len(walls) == 6
    assert sum(1 for wall in walls if not _axis_aligned(wall)) == 2


def test_absorb_corner_diagonals__filled_shaft_drops_both_v_arms() -> None:
    """Hộp gen bị mặt nạ tô đặc (ch-13 bench): hai cạnh dọc của khối đã chụm một nút, hai nhánh chéo xuống góc
    đáy bị hút như vụn góc — trước đây `_clash` thấy hai cạnh dọc lệch nhau nên chặn, để lại tường xiên chữ V."""
    apex, left, right = (1, 27, 2), (1, 31, 2), (1, 21, 3)
    segs = [
        _Seg(250.0, 378.0, 347.0, 378.0, 6.0, 0.9, (1, 31, 1), left, "h"),
        _Seg(405.0, 378.0, 365.0, 378.0, 6.0, 0.9, (1, 21, 1), right, "h"),
        _Seg(350.0, 351.0, 350.0, 360.0, 4.0, 0.9, (0, 0, 0), apex, "v"),
        _Seg(361.5, 352.0, 361.5, 360.0, 8.0, 0.9, (0, 0, 0), apex, "v"),
        _Seg(365.0, 378.0, 356.7, 371.7, 10.0, 0.9, right, apex, "d"),
        _Seg(347.0, 378.0, 356.7, 371.7, 11.0, 0.9, left, apex, "d"),
    ]
    empty = np.zeros(0, np.int32)
    graph = _Graph(empty, empty, empty, np.zeros((1, 2)), np.zeros(1, np.bool_), np.zeros(1), [])
    kept, short, _ = _absorb_corner_diagonals(segs, graph)
    assert [seg.axis for seg in kept] == ["h", "h", "v", "v"]
    assert short == 0
    assert len({seg.b_key for seg in kept}) == 1


def _arc_run(radius: float, sweep_deg: float, thickness: float = 10.0) -> tuple[list[_Seg], NDArray[np.float64]]:
    """Ba đoạn DP dây cung tâm (200, 200) quét `sweep_deg` cùng điểm xương mỗi 1° trên cung."""
    angles = np.radians(np.linspace(0.0, sweep_deg, int(sweep_deg) + 1))
    points = np.stack([200.0 + radius * np.cos(angles), 200.0 + radius * np.sin(angles)], axis=1)
    picks = [(float(x), float(y)) for x, y in (points[round(k * (len(points) - 1) / 3)] for k in range(4))]
    run = [
        _Seg(a[0], a[1], b[0], b[1], thickness, 1.0, (1, 0, k), (1, 0, k + 1), "d")
        for k, (a, b) in enumerate(itertools.pairwise(picks))
    ]
    return run, points


@pytest.mark.parametrize(
    ("radius", "sweep", "chords"),
    [(150.0, 90.0, 9), (30.0, 90.0, None), (150.0, 20.0, None), (45.0, 60.0, None)],
)
def test_arc_chords__thresholds(radius: float, sweep: float, chords: int | None) -> None:
    """Cung đủ rộng chia dây đều trên đường tròn; bán kính < 4 bề dày (góc bo quanh cột), quét < 30°
    hay cung ngắn < 5 bề dày thì giữ đoạn DP (`None`)."""
    run, points = _arc_run(radius, sweep)
    out = _arc_chords(0, run, points, np.ones((400, 400), np.bool_), itertools.count())
    if chords is None:
        assert out is None
        return
    assert out is not None
    assert len(out) == chords
    assert all(seg.arc for seg in out)
    assert (out[0].a_key, out[-1].b_key) == (run[0].a_key, run[-1].b_key)
    for seg in out:
        assert abs(math.dist((seg.bx, seg.by), (200.0, 200.0)) - radius) <= 1e-6


def test_vectorize__room_wide_diagonal_is_not_a_box_mark() -> None:
    """Đường chéo nối hai góc của cả một phòng (rộng > `_BOX_MAX_RATIO` lần bề dày) là tường thật, giữ."""
    corners = [(60, 60), (340, 60), (340, 240), (60, 240)]
    frame = list(zip(corners, corners[1:] + corners[:1], strict=True))
    walls = vectorize(_bars(*frame, ((60, 60), (340, 240))))
    diagonal = sum(math.dist(wall.start, wall.end) for wall in walls if not _axis_aligned(wall))
    assert diagonal >= 0.9 * math.hypot(280, 180)


def _dp_run(vertices: list[tuple[float, float]], points: list[tuple[float, float]]) -> tuple[list[_Seg], np.ndarray]:
    """Chuỗi đoạn DP qua `vertices` (bề dày 10) và điểm xương `points` của nó."""
    keys = [(0, 0, 0), *((1, 0, k) for k in range(len(vertices) - 2)), (0, 0, 1)]
    run = [
        _Seg(*one, *two, 10.0, 0.9, keys[k], keys[k + 1]) for k, (one, two) in enumerate(itertools.pairwise(vertices))
    ]
    return run, np.asarray(points, np.float64)


def test_arc_chords__chamfered_corner_stays_a_polyline() -> None:
    """Vát góc 45° tường dày: đoạn DP vốn thẳng, đường tròn không khớp rõ hơn chúng → không thành cung (NO-434)."""
    vertices = [(50.0, 50.0), (50.0, 150.0), (90.0, 190.0), (190.0, 190.0)]
    points = [
        (x + (bx - x) * k / 40, y + (by - y) * k / 40)
        for (x, y), (bx, by) in itertools.pairwise(vertices)
        for k in range(40)
    ]
    run, skeleton = _dp_run(vertices, points)
    assert _arc_chords(0, run, skeleton, np.ones((300, 300), np.bool_), itertools.count()) is None


def test_arc_chords__points_on_a_circle_still_become_an_arc() -> None:
    """Điểm xương trên đường tròn, ba đoạn DP là dây: đường tròn khớp hơn hẳn → chia lại thành cung."""
    angles = [math.radians(180 - 30 * k) for k in range(4)]
    vertices = [(150 + 100 * math.cos(a), 150 - 100 * math.sin(a)) for a in angles]
    points = [
        (150 + 100 * math.cos(math.radians(a)), 150 - 100 * math.sin(math.radians(a))) for a in range(180, 89, -1)
    ]
    run, skeleton = _dp_run(vertices, points)
    assert _arc_chords(0, run, skeleton, np.ones((300, 300), np.bool_), itertools.count())
