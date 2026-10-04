"""Vector hoá tường trên mặt nạ dựng bằng OpenCV (B5-02 khối [8], việc A).

Mặt nạ dựng tay nên đáp án biết trước: mọi khẳng định về số đoạn, đầu mút và bề dày
đều so với hình đã vẽ, không so với ảnh chụp kết quả.
"""

import math

import cv2
import numpy as np
import pytest
from numpy.typing import NDArray

from packages.vision.walls.types import WallSegment
from packages.vision.walls.vectorize import keep_longest, vectorize, vectorize_with_stats

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
    walls = vectorize(_bars(((50, 150), (350, 150))))
    assert len(walls) == 1
    assert abs(walls[0].start[0] - 50.0) <= 2.0
    assert abs(walls[0].end[0] - 350.0) <= 2.0
    assert abs(walls[0].thickness_px - THICK) <= 1.0


def test_corner_gives_two_segments_sharing_the_corner() -> None:
    walls = vectorize(_bars(((60, 60), (60, 240)), ((60, 240), (340, 240))))
    assert len(walls) == 2
    assert _shares(walls, 2) == 1


def test_tee_gives_two_segments_meeting_on_the_through_wall() -> None:
    walls = vectorize(_bars(((40, 120), (360, 120)), ((200, 120), (200, 260))))
    assert len(walls) == 2
    through = max(walls, key=lambda w: w.end[0] - w.start[0])
    stem = min(walls, key=lambda w: w.end[0] - w.start[0])
    assert through.start[1] == through.end[1]
    assert abs(stem.start[1] - through.start[1]) <= 1.0
    assert through.start[0] <= stem.start[0] <= through.end[0]


def test_cross_gives_two_segments() -> None:
    walls = vectorize(_bars(((40, 150), (360, 150)), ((200, 40), (200, 260))))
    assert len(walls) == 2


def test_rectangle_frame_gives_four_segments_and_four_corners() -> None:
    corners = [(60, 60), (340, 60), (340, 240), (60, 240)]
    walls = vectorize(_bars(*zip(corners, corners[1:] + corners[:1], strict=True)))
    assert len(walls) == 4
    assert _shares(walls, 2, tol=2.0) == 4


def test_bar_tilted_three_degrees_is_snapped_horizontal() -> None:
    drop = round(300 * math.tan(math.radians(3.0)))
    walls = vectorize(_bars(((50, 150), (350, 150 + drop))))
    assert len(walls) == 1
    assert walls[0].start[1] == walls[0].end[1]


def test_bar_tilted_thirty_degrees_keeps_its_angle() -> None:
    drop = round(250 * math.tan(math.radians(30.0)))
    walls = vectorize(_bars(((70, 60), (320, 60 + drop))))
    assert len(walls) == 1
    angle = math.degrees(math.atan2(walls[0].end[1] - walls[0].start[1], walls[0].end[0] - walls[0].start[0]))
    assert abs(abs(angle) - 30.0) <= 1.0


def test_isolated_block_is_dropped_as_short() -> None:
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
    result = vectorize_with_stats(np.zeros(SHAPE, np.bool_))
    assert result.walls == ()
    assert result.dropped == {"spur": 0, "short": 0}


def test_three_dimensional_mask_is_rejected() -> None:
    with pytest.raises(ValueError, match="2 chiều"):
        vectorize(np.zeros((4, 4, 3), np.bool_))


def test_non_boolean_mask_is_rejected() -> None:
    with pytest.raises(ValueError, match="bool"):
        vectorize(np.zeros(SHAPE, np.uint8))


def test_confidence_stays_in_unit_range() -> None:
    walls = vectorize(_bars(((40, 120), (360, 120)), ((200, 120), (200, 260))))
    assert walls
    assert all(0.0 <= wall.confidence <= 1.0 for wall in walls)


def test_two_calls_give_the_same_result() -> None:
    mask = _bars(((60, 60), (60, 240)), ((60, 240), (340, 240)))
    assert vectorize(mask) == vectorize(mask)


def test_rotating_the_mask_keeps_the_segment_count() -> None:
    mask = _bars(((40, 120), (360, 120)), ((200, 120), (200, 260)))
    assert len(vectorize(np.ascontiguousarray(np.rot90(mask)))) == len(vectorize(mask))


def test_wall_touching_the_border_stays_inside_the_image() -> None:
    height, width = SHAPE
    walls = vectorize(_bars(((0, 150), (width - 1, 150))))
    assert walls
    for point in _ends(walls):
        assert 0.0 <= point[0] <= width - 1
        assert 0.0 <= point[1] <= height - 1


def test_diagonal_pair_averages_the_shared_endpoint() -> None:
    walls = vectorize(_bars(((40, 40), (200, 130)), ((200, 130), (360, 220))))
    assert len(walls) >= 1
    assert all(0.0 <= wall.confidence <= 1.0 for wall in walls)


def _stub(index: int, length: float) -> WallSegment:
    """Đoạn ngang dài `length` ở hàng `index`, để thử `keep_longest` không cần ảnh."""
    return WallSegment(start=(0.0, float(index)), end=(length, float(index)), thickness_px=10.0, confidence=1.0)


def test_keep_longest_drops_the_shortest_segment() -> None:
    walls = tuple(_stub(i, 100.0 + i) for i in range(20_001))
    kept = keep_longest(walls)
    assert len(kept) == 20_000
    assert walls[0] not in kept
    assert kept == tuple(sorted(kept, key=lambda w: (w.start, w.end)))


def test_keep_longest_passes_short_lists_through() -> None:
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
