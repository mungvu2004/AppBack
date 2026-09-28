"""Hình học của luật hậu xử lý AI: gương `fitout/index.ts` và `rooms/area.ts` của FE, cùng con số với FE.

Toàn hàm thuần trên mô hình B3-01, không sửa đối số. Toạ độ ra cho mô hình là `int`
qua `js_round` của B3-01 (không `round()` dựng sẵn: làm tròn ngân hàng lệch FE).
Điểm dò và tâm là `float` vì chỉ dùng để so sánh, không bao giờ ghi vào mô hình.
"""

import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from operator import attrgetter
from typing import Literal

from packages.domain.rules_ai.constants import EXTERIOR_PROBE_MM
from packages.domain.spatial import BoundingBox, Point, Room, Wall, signed_area_mm2

WallSide = Literal["exterior", "interior", "unknown"]
Xy = tuple[float, float]
CellKey = tuple[int, int]
Bounds = tuple[int, int, int, int]
"""Hộp bao `(min_x, min_y, max_x, max_y)` của một tập điểm."""


@dataclass(frozen=True, slots=True)
class Nearest:
    """Điểm dò gần đường tim nhất: khoảng cách `distance`, điểm dò `probe`, chân đường vuông góc `foot`."""

    distance: float
    probe: Xy
    foot: Xy


def probe_points(box: BoundingBox) -> tuple[Xy, ...]:
    """Năm điểm dò của `gapToWallFace`: bốn góc theo thứ tự `min`, `(max.x, min.y)`, `max`, `(min.x, max.y)`, rồi tâm.

    Thứ tự quyết luật hoà (điểm dò đứng trước thắng), nên không được đổi.
    """
    low, high = box.min, box.max
    return (
        (low.x, low.y),
        (high.x, low.y),
        (high.x, high.y),
        (low.x, high.y),
        ((low.x + high.x) / 2, (low.y + high.y) / 2),
    )


def _foot_on_segment(point: Xy, start: Point, end: Point) -> Xy:
    """Chân đường vuông góc từ `point` xuống đoạn `start-end`, kẹp vào hai đầu mút (`distancePointToSegment`).

    Đoạn dài 0 không xảy ra: mô hình `Segment` đã chặn.
    """
    run_x, run_y = end.x - start.x, end.y - start.y
    along = ((point[0] - start.x) * run_x + (point[1] - start.y) * run_y) / (run_x * run_x + run_y * run_y)
    along = min(1.0, max(0.0, along))
    return start.x + along * run_x, start.y + along * run_y


def nearest_probe(box: BoundingBox, wall: Wall) -> Nearest:
    """Điểm dò gần đường tim của `wall` nhất; hoà thì điểm dò đứng trước (`min` giữ phần tử gặp đầu)."""
    start, end = wall.centreline.start, wall.centreline.end
    measured = []
    for probe in probe_points(box):
        foot = _foot_on_segment(probe, start, end)
        measured.append(Nearest(math.hypot(probe[0] - foot[0], probe[1] - foot[1]), probe, foot))
    return min(measured, key=attrgetter("distance"))


def gap_to_wall_face(box: BoundingBox, wall: Wall) -> float:
    """Khe từ hộp tới **mặt** tường, mm: khoảng cách gần nhất tới đường tim trừ nửa bề dày, không âm.

    Thiết bị chạm mặt tường chứ không chạm đường tim; nằm trong thân tường thì khe
    là 0 chứ không âm (`fitout/index.ts:187-202`).
    """
    return max(0.0, nearest_probe(box, wall).distance - wall.thickness_mm / 2)


def outline_contains(outline: Sequence[Point], x: float, y: float) -> bool:
    """Điểm `(x, y)` trong đường bao hay không: bắn tia về phía đông, đếm giao (`outlineContains`, `area.ts:278-297`).

    Điểm đúng trên cạnh không được hứa bên nào, giống FE; test khoá đúng hành vi đó.
    """
    inside = False
    previous = outline[-1]
    for current in outline:
        if (previous.y > y) != (current.y > y):
            crossing = previous.x + ((y - previous.y) / (current.y - previous.y)) * (current.x - previous.x)
            if x < crossing:
                inside = not inside
        previous = current
    return inside


def centroid(outline: Sequence[Point]) -> Xy:
    """Tâm diện tích của đường bao (`computeCentroid`, `area.ts:235-270`).

    Đường bao suy biến (diện tích gần 0) rơi về trung bình các đỉnh như FE.
    `ValueError` từ `signed_area_mm2` khi tổng dây giày vượt 2^53 - 1.
    """
    double_area = 2 * signed_area_mm2(outline)
    count = len(outline)
    if abs(double_area) <= 0.001:
        return sum(p.x for p in outline) / count, sum(p.y for p in outline) / count
    weighted_x = weighted_y = 0
    previous = outline[-1]
    for current in outline:
        cross = previous.x * current.y - current.x * previous.y
        weighted_x += (previous.x + current.x) * cross
        weighted_y += (previous.y + current.y) * cross
        previous = current
    return weighted_x / (3 * double_area), weighted_y / (3 * double_area)


def bounds_of(points: Iterable[Point]) -> Bounds:
    """Hộp bao của một tập điểm không rỗng."""
    xs, ys = zip(*((p.x, p.y) for p in points), strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def in_bounds(bounds: Bounds, x: float, y: float) -> bool:
    """`(x, y)` nằm trong hộp bao, tính cả biên."""
    return bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]


def cell_keys(bounds: tuple[float, float, float, float], cell_mm: int) -> Iterator[CellKey]:
    """Mọi ô lưới cạnh `cell_mm` mà hộp `bounds` chạm tới; khoá `(x // cell, y // cell)` làm tròn xuống cả số âm."""
    first_x, first_y = math.floor(bounds[0] // cell_mm), math.floor(bounds[1] // cell_mm)
    last_x, last_y = math.floor(bounds[2] // cell_mm), math.floor(bounds[3] // cell_mm)
    for cell_x in range(first_x, last_x + 1):
        for cell_y in range(first_y, last_y + 1):
            yield cell_x, cell_y


def wall_side_by(wall: Wall, contains: Callable[[float, float], bool]) -> WallSide:
    """Phân loại tường theo hai điểm dò hai bên; `contains(x, y)` hỏi "điểm này nằm trong phòng nào đó không".

    Tách khỏi `wall_side` để luật 2 hỏi qua chỉ mục phòng mà cùng một công thức:
    đúng một bên trong phòng → `exterior`, hai bên → `interior`, không bên nào → `unknown`.
    """
    line = wall.centreline
    run_x, run_y = line.end.x - line.start.x, line.end.y - line.start.y
    length = math.hypot(run_x, run_y)
    reach = wall.thickness_mm / 2 + EXTERIOR_PROBE_MM
    mid_x, mid_y = (line.start.x + line.end.x) / 2, (line.start.y + line.end.y) / 2
    shift_x, shift_y = -run_y / length * reach, run_x / length * reach
    inside = contains(mid_x + shift_x, mid_y + shift_y) + contains(mid_x - shift_x, mid_y - shift_y)
    if inside == 0:
        return "unknown"
    return "exterior" if inside == 1 else "interior"


def wall_side(wall: Wall, rooms: Iterable[Room]) -> WallSide:
    """Tường nằm ngoài, trong, hay chưa rõ so với các phòng của lớp (bản quét hết mọi phòng)."""
    outlines = [room.outline for room in rooms]

    def contains(x: float, y: float) -> bool:
        """Có phòng nào chứa điểm không."""
        return any(outline_contains(outline, x, y) for outline in outlines)

    return wall_side_by(wall, contains)
