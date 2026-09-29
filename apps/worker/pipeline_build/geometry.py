"""Tường, nối khe ô mở và ô mở (B5-05 [6] bước 3, 3b, 4); khung kiểu dùng chung do prep đặt.

Hình học chạy bằng `shapely` 2.x vector hoá: một `linestrings` cho mọi đường tim và một
`STRtree` **mỗi pha** (lọc khối cô lập, 3b, bước 4, hộp ô mở — 3b sửa hình học tại chỗ nên
cây của pha trước hết đúng), truy vấn theo lô (`dwithin`, `query_nearest`) — trần B5-01 là
20.000 tường và 5.000 hộp nên vòng Python qua mọi cặp tường là không chạy nổi.
Toạ độ mm: gốc trên-trái, y hướng xuống.
"""

import math
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import shapely
from numpy.typing import NDArray
from shapely import LineString, STRtree

from apps.worker.pipeline_build.constants import (
    DEFAULT_WALL_HEIGHT_MM,
    OPENING_GAP_MAX_MM,
    OPENING_WALL_REACH_MM,
    STANDARD_THICKNESSES_MM,
    WALL_JOIN_MM,
)
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.core.clock import Clock
from packages.domain.spatial import Opening, Point, Segment, Wall, js_round
from packages.ml_contracts.artifacts import BoxPx, DetectionPx, WallPx
from packages.ml_contracts.labels import LABEL_TARGETS, SwingDirection

Geoms = NDArray[np.object_]

_ALIGN_SIN: Final = math.sin(math.radians(2.0))
"""Lệch góc tối đa của cặp tường thẳng hàng (2°, B5-05 [6] 3b) đo bằng `|sin|` để khỏi `atan2`."""
_PERPENDICULAR_COS: Final = math.cos(math.radians(88.0))
"""Cặp tường vuông góc: `|cos|` của góc giữa hai hướng ≤ cos(88°), tức lệch 90° không quá 2°."""
_MIN_DOUBLE_DOOR_MM: Final = 600
"""Cửa đôi hẹp hơn 600 mm là hộp bám sai tường, không phải cửa (B5-05 [6] bước 4)."""
_OPENING_LABELS: Final[frozenset[str]] = frozenset({"door", "double_door", "window"})
"""Chỉ ba nhãn này thành ô mở; nhãn đồ đạc là việc của `rooms.build_furniture`, không đếm ở đây."""


@dataclass(frozen=True, slots=True)
class Scaling:
    """Hai tỉ lệ của một lượt dựng (mm/px): `build` = `s_dựng`, `final` = `s` ghi ra dây.

    Bước 3-8 đổi px → mm bằng `build`; `final` chỉ dùng để thấy trước tường sẽ suy biến sau
    `rescale_unreviewed(build → final)` (bước 3, `project_default`).
    """

    build: float
    final: float

    def mm(self, value_px: float) -> int:
        """Độ dài/toạ độ px → mm nguyên ở `s_dựng` (`js_round`, K20)."""
        return js_round(value_px * self.build)

    def point(self, x_px: float, y_px: float) -> Point:
        """Điểm px → `Point` mm ở `s_dựng`."""
        return Point(x=self.mm(x_px), y=self.mm(y_px))


@dataclass(frozen=True, slots=True)
class WallSet:
    """Đầu ra bước 3-4 cho bước 5 (phòng) và bước 7 (kích thước).

    `walls` đã có `openingIds`; `input_to_wall[j]` = chỉ số trong `walls` của tường đầu vào `j`
    còn giữ (tường gộp ở 3b: cả hai `j` trỏ về tường gộp; tường bị bỏ: vắng khoá);
    `bridges` = đoạn nối khe thẳng hàng không gộp (mm), chỉ để khép phòng, không ghi ra lớp.
    """

    walls: tuple[Wall, ...]
    openings: tuple[Opening, ...]
    input_to_wall: Mapping[int, int]
    bridges: tuple[tuple[Point, Point], ...]


@dataclass(slots=True)
class _Seg:
    """Tường đang dựng ở mm, sửa tại chỗ trong 3b.

    `inputs` = mọi chỉ số trong `walls` đã gộp vào (dựng `input_to_wall`), `measured_mm` là bề dày
    **đo** chưa bắt về chuẩn (ngưỡng khối cô lập), `alive` tắt khi bị tường khác hấp thu.
    """

    start: Point
    end: Point
    thickness_mm: int
    measured_mm: float
    confidence: float
    inputs: tuple[int, ...]
    alive: bool = True


@dataclass(frozen=True, slots=True)
class _Cand:
    """Ô mở ứng viên trước khi xử chồng khoảng; `order` là thứ tự trong `detections`."""

    wall: int
    order: int
    kind: Literal["door", "window"]
    offset_mm: int
    width_mm: int
    height_mm: int
    sill_mm: int
    swing: SwingDirection
    confidence: float


@dataclass(frozen=True, slots=True)
class _Boxes:
    """Hộp ô mở (mm) cùng `STRtree` của chúng: trả lời câu hỏi khe nào có hộp cửa (3b)."""

    rects: tuple[tuple[float, float, float, float], ...]
    tree: STRtree

    def covers(self, start: Point, end: Point) -> bool:
        """Một hộp phủ ≥ 50 % chiều dài khe `start→end` khi chiếu lên trục khe."""
        span = math.dist((start.x, start.y), (end.x, end.y))
        if span <= 0:
            return False
        unit = ((end.x - start.x) / span, (end.y - start.y) / span)
        gap = LineString(((start.x, start.y), (end.x, end.y)))
        return any(_projection_covers(self.rects[index], start, unit, span) for index in _hits(self.tree, gap))


@dataclass(frozen=True, slots=True)
class _Centrelines:
    """Tim tường lúc vào 3b + `STRtree`: kiểm khe có cắt tim một tường **khác** hay không.

    Tường gộp ở 3b là hợp của các tường vào trên cùng đường thẳng, nên tra trên tập lúc vào
    vẫn đúng và khỏi dựng lại cây sau mỗi lần gộp.
    """

    tree: STRtree
    slot_by_input: Mapping[int, int]

    def crosses(self, start: Point, end: Point, inputs: Sequence[int]) -> bool:
        """Khe cắt tim tường nào ngoài các tường vào `inputs` (hai đầu khe nằm trên chính chúng)."""
        skip = {self.slot_by_input[index] for index in inputs}
        gap = LineString(((start.x, start.y), (end.x, end.y)))
        return any(index not in skip for index in _hits(self.tree, gap))


def _hits(tree: STRtree, geom: LineString) -> list[int]:
    """Chỉ số các hình trong cây giao với `geom` (một truy vấn, không quét tuyến tính)."""
    return [int(index) for index in tree.query(geom, predicate="intersects")]


def _projection_covers(
    rect: tuple[float, float, float, float], origin: Point, unit: tuple[float, float], span: float
) -> bool:
    """Hình chiếu hộp `rect` lên trục `unit` từ `origin` phủ ≥ 50 % đoạn `[0, span]`."""
    values = [(x - origin.x) * unit[0] + (y - origin.y) * unit[1] for x in rect[0::2] for y in rect[1::2]]
    low, high = max(min(values), 0.0), min(max(values), span)
    return high - low >= 0.5 * span


def _unit(seg: _Seg) -> tuple[float, float]:
    """Hướng đơn vị của tim tường (tường dài 0 đã bị bỏ ở bước 3 nên không chia cho 0)."""
    length = _length(seg)
    return ((seg.end.x - seg.start.x) / length, (seg.end.y - seg.start.y) / length)


def _length(seg: _Seg) -> float:
    """Chiều dài tim tường (mm, số thực để so với bề dày đo)."""
    return math.dist((seg.start.x, seg.start.y), (seg.end.x, seg.end.y))


def _linestrings(segs: Sequence[_Seg]) -> Geoms:
    """Mọi tim tường thành mảng `LineString` trong **một** lần gọi `shapely.linestrings`."""
    coords = [[[seg.start.x, seg.start.y], [seg.end.x, seg.end.y]] for seg in segs]
    return np.asarray(shapely.linestrings(coords), dtype=object)


def _neighbours(tree: STRtree, geoms: Geoms, distance: float) -> list[set[int]]:
    """Một truy vấn `dwithin` theo lô: các hình khác cách mỗi hình ≤ `distance`."""
    result: list[set[int]] = [set() for _ in range(len(geoms))]
    sources, targets = tree.query(geoms, predicate="dwithin", distance=distance)
    for source, target in zip(sources.tolist(), targets.tolist(), strict=True):
        if source != target:
            result[source].add(target)
    return result


def _snap_thickness(measured_mm: float) -> int:
    """Bề dày đo → phần tử gần nhất của `STANDARD_THICKNESSES_MM`; hoà lấy số nhỏ hơn."""
    return min(STANDARD_THICKNESSES_MM, key=lambda value: (abs(value - measured_mm), value))


def _degenerate_final(p0: Point, p1: Point, thickness_mm: int, scaling: Scaling) -> bool:
    """`project_default`: tường sẽ suy biến sau `rescale_unreviewed(s_dựng → s)` (bước 3).

    Dựng ở `s_dựng` rồi mới đổi về `s`, nên tường 0,3 px phải bị bỏ **ngay** — không thì
    `rescale_unreviewed` gặp `Segment` dài 0 và ném.
    """
    if scaling.build == scaling.final:
        return False
    ratio = scaling.final / scaling.build
    scaled = [(js_round(point.x * ratio), js_round(point.y * ratio)) for point in (p0, p1)]
    return scaled[0] == scaled[1] or js_round(thickness_mm * ratio) == 0


def _measure_walls(walls: Sequence[WallPx], scaling: Scaling, dropped: Counter[str]) -> list[_Seg]:
    """Bước 3: px → mm theo thứ tự đầu vào, bỏ tường suy biến, bắt bề dày về bảng chuẩn."""
    segs: list[_Seg] = []
    for index, wall in enumerate(walls):
        p0 = scaling.point(wall.start.x, wall.start.y)
        p1 = scaling.point(wall.end.x, wall.end.y)
        measured = wall.thickness_px * scaling.build
        thickness = _snap_thickness(measured)
        if p0 == p1 or _degenerate_final(p0, p1, thickness, scaling):
            dropped["wallZeroLength"] += 1
            continue
        segs.append(_Seg(p0, p1, thickness, measured, wall.confidence, (index,)))
    return segs


def _drop_isolated(segs: list[_Seg], dropped: Counter[str]) -> list[_Seg]:
    """Bước 3: khối dài ≤ bề dày đo mà không tường nào khác cách tim ≤ `WALL_JOIN_MM` là khối cô lập."""
    if not segs:
        return segs
    geoms = _linestrings(segs)
    near = _neighbours(STRtree(geoms), geoms, float(WALL_JOIN_MM))
    kept = [seg for index, seg in enumerate(segs) if _length(seg) > seg.measured_mm or near[index]]
    dropped["isolatedBlock"] += len(segs) - len(kept)
    return kept


def _rect(box: BoxPx, scaling: Scaling) -> tuple[float, float, float, float]:
    """Hộp px → `(x_min, y_min, x_max, y_max)` mm (`BoxPx` đã bảo đảm `min < max`)."""
    low = scaling.point(box.x_min, box.y_min)
    high = scaling.point(box.x_max, box.y_max)
    return (float(low.x), float(low.y), float(high.x), float(high.y))


def _opening_boxes(detections: Sequence[DetectionPx], scaling: Scaling) -> _Boxes:
    """Hộp của riêng nhãn `door|double_door|window` đổi sang mm, dựng cây một lần."""
    rects = tuple(_rect(det.box, scaling) for det in detections if det.label in _OPENING_LABELS)
    return _Boxes(rects, STRtree([shapely.box(*rect) for rect in rects]))


def _near_ends(a: _Seg, b: _Seg) -> tuple[Point, Point] | None:
    """Cặp đầu mút gần nhau nhất của hai tường, chỉ khi khe `0 < g ≤ OPENING_GAP_MAX_MM`."""
    pairs = [(p, q) for p in (a.start, a.end) for q in (b.start, b.end)]
    best = min(pairs, key=lambda pair: math.dist((pair[0].x, pair[0].y), (pair[1].x, pair[1].y)))
    gap = math.dist((best[0].x, best[0].y), (best[1].x, best[1].y))
    return best if 0 < gap <= OPENING_GAP_MAX_MM else None


def _aligned(a: _Seg, b: _Seg) -> bool:
    """Thẳng hàng: lệch góc ≤ 2° **và** hai đầu của `b` lệch ngang ≤ ½ bề dày lớn hơn."""
    ua, ub = _unit(a), _unit(b)
    if abs(ua[0] * ub[1] - ua[1] * ub[0]) > _ALIGN_SIN:
        return False
    limit = max(a.thickness_mm, b.thickness_mm) / 2
    return all(
        abs((point.x - a.start.x) * ua[1] - (point.y - a.start.y) * ua[0]) <= limit for point in (b.start, b.end)
    )


def _perpendicular(a: _Seg, b: _Seg) -> bool:
    """Vuông góc trong sai số 2° (dùng cho 3b-b: đầu mút chạm tim vách ngang)."""
    ua, ub = _unit(a), _unit(b)
    return abs(ua[0] * ub[0] + ua[1] * ub[1]) <= _PERPENDICULAR_COS


def _absorb(keep: _Seg, drop: _Seg) -> None:
    """Gộp `drop` vào `keep`: hai đầu xa nhau nhất, bề dày lớn hơn, `confidence` nhỏ hơn."""
    pairs = [(p, q) for p in (keep.start, keep.end) for q in (drop.start, drop.end)]
    far = max(pairs, key=lambda pair: math.dist((pair[0].x, pair[0].y), (pair[1].x, pair[1].y)))
    keep.start, keep.end = far
    keep.thickness_mm = max(keep.thickness_mm, drop.thickness_mm)
    keep.measured_mm = max(keep.measured_mm, drop.measured_mm)
    keep.confidence = min(keep.confidence, drop.confidence)
    keep.inputs = keep.inputs + drop.inputs
    drop.alive = False


def _mergeable(a: _Seg, b: _Seg, boxes: _Boxes, lines: _Centrelines) -> bool:
    """Cặp thẳng hàng, khe trong trần, khe không cắt tim tường khác, khe có hộp → gộp được."""
    ends = _near_ends(a, b)
    if ends is None or not _aligned(a, b):
        return False
    if lines.crosses(ends[0], ends[1], a.inputs + b.inputs):
        return False
    return boxes.covers(ends[0], ends[1])


def _merge_aligned(
    segs: list[_Seg],
    neighbours: list[set[int]],
    boxes: _Boxes,
    lines: _Centrelines,
    dropped: Counter[str],
) -> None:
    """3b (a): gộp cặp thẳng hàng có khe mang hộp, lặp tới **điểm bất động** bằng hàng đợi ứng viên.

    Tường bị hai khe cửa chia ba đoạn phải về một tường, nên sau mỗi lần gộp tường gộp được đưa
    lại vào hàng đợi cùng mọi láng giềng của cả hai tường cũ.
    """
    queue = deque((low, high) for low, near in enumerate(neighbours) for high in near if low < high)
    while queue:
        low, high = sorted(queue.popleft())
        if low == high or not (segs[low].alive and segs[high].alive):
            continue
        if not _mergeable(segs[low], segs[high], boxes, lines):
            continue
        _absorb(segs[low], segs[high])
        neighbours[low] |= neighbours[high]
        neighbours[low].discard(low)
        queue.extend((low, other) for other in neighbours[low] if segs[other].alive)
        dropped["wallGapBridged"] += 1


def _within(seg: _Seg, point: tuple[float, float]) -> bool:
    """Điểm nằm trong đoạn `seg` theo tham số dọc tim (`[0, L]`)."""
    unit = _unit(seg)
    along = (point[0] - seg.start.x) * unit[0] + (point[1] - seg.start.y) * unit[1]
    return 0 <= along <= _length(seg)


def _foot_on_other(seg: _Seg, other: _Seg) -> tuple[bool, Point] | None:
    """Đầu mút của `seg` cần kéo và chân trên tim `other`: `(là đầu end, chân)` hoặc `None`.

    Chỉ xét cặp vuông góc, nên hai đường không song song và định thức không bằng 0. Chân phải nằm
    trong đoạn `other` và **ngoài** `seg`, cách đầu mút `0 < g ≤ OPENING_GAP_MAX_MM`, và không trùng
    đầu mút còn lại (`Segment` cấm tường dài 0).
    """
    if not _perpendicular(seg, other):
        return None
    unit, other_unit = _unit(seg), _unit(other)
    dx, dy = other.start.x - seg.start.x, other.start.y - seg.start.y
    step = (dx * other_unit[1] - dy * other_unit[0]) / (unit[0] * other_unit[1] - unit[1] * other_unit[0])
    crossing = (seg.start.x + unit[0] * step, seg.start.y + unit[1] * step)
    if not _within(other, crossing):
        return None
    foot = Point(x=js_round(crossing[0]), y=js_round(crossing[1]))
    if -OPENING_GAP_MAX_MM <= step < 0 and foot != seg.end:
        return (False, foot)
    if _length(seg) < step <= _length(seg) + OPENING_GAP_MAX_MM and foot != seg.start:
        return (True, foot)
    return None


def _extend_once(seg: _Seg, others: Sequence[_Seg], boxes: _Boxes) -> bool:
    """3b (b) cho một tường: kéo đầu mút tới tim vách vuông góc đầu tiên mà khe có hộp."""
    for other in others:
        hit = _foot_on_other(seg, other)
        if hit is None:
            continue
        is_end, foot = hit
        if not boxes.covers(seg.end if is_end else seg.start, foot):
            continue
        if is_end:
            seg.end = foot
        else:
            seg.start = foot
        return True
    return False


def _extend_all(segs: list[_Seg], neighbours: list[set[int]], boxes: _Boxes, dropped: Counter[str]) -> None:
    """3b (b) cho mọi tường còn giữ; mỗi tường kéo nhiều nhất một đầu mút một lần."""
    for index, seg in enumerate(segs):
        if not seg.alive:
            continue
        others = [segs[other] for other in sorted(neighbours[index]) if segs[other].alive]
        if others and _extend_once(seg, others, boxes):
            dropped["wallGapBridged"] += 1


def _bridge_segments(segs: Sequence[_Seg], neighbours: Sequence[set[int]]) -> tuple[tuple[Point, Point], ...]:
    """3b (c): cặp thẳng hàng còn khe mà không gộp → đoạn nối hai đầu gần, chỉ để khép phòng."""
    pairs = [
        (low, high)
        for low, near in enumerate(neighbours)
        for high in sorted(near)
        if low < high and segs[low].alive and segs[high].alive
    ]
    found = (_near_ends(segs[low], segs[high]) for low, high in pairs if _aligned(segs[low], segs[high]))
    return tuple(ends for ends in found if ends is not None)


def _join_gaps(segs: list[_Seg], boxes: _Boxes, dropped: Counter[str]) -> tuple[tuple[Point, Point], ...]:
    """Bước 3b: gộp cặp thẳng hàng (a), kéo đầu mút tới vách (b), đoạn nối cho cặp còn lại (c)."""
    geoms = _linestrings(segs)
    tree = STRtree(geoms)
    lines = _Centrelines(tree, {seg.inputs[0]: slot for slot, seg in enumerate(segs)})
    neighbours = _neighbours(tree, geoms, float(OPENING_GAP_MAX_MM))
    _merge_aligned(segs, neighbours, boxes, lines, dropped)
    _extend_all(segs, neighbours, boxes, dropped)
    return _bridge_segments(segs, neighbours)


def _nearest_walls(tree: STRtree, points: Geoms) -> list[tuple[int, float] | None]:
    """Một `query_nearest` theo lô: `(tường gần nhất, khoảng cách)` mỗi tâm hộp, hoà lấy chỉ số nhỏ."""
    best: list[tuple[int, float] | None] = [None] * len(points)
    if not len(points):
        return best
    pairs, distances = tree.query_nearest(points, all_matches=True, return_distance=True)
    for source, wall, distance in zip(pairs[0].tolist(), pairs[1].tolist(), distances.tolist(), strict=True):
        current = best[source]
        if current is None or wall < current[0]:
            best[source] = (wall, distance)
    return best


def _span_on_wall(rect: tuple[float, float, float, float], line: LineString) -> tuple[float, float]:
    """Chiếu 4 góc hộp lên tim tường → `[a, b]` đã kẹp về `[0, L]` (tham số dọc tim, mm)."""
    values = [float(shapely.line_locate_point(line, shapely.points(x, y))) for x in rect[0::2] for y in rect[1::2]]
    return (min(values), max(values))


def _candidate(
    order: int,
    detection: DetectionPx,
    wall: int,
    seg: _Seg,
    span: tuple[float, float],
    dropped: Counter[str],
) -> _Cand | None:
    """Bước 4 cho một hộp đã biết tường: kích thước theo `LABEL_TARGETS`, `offsetMm` kẹp trong tường."""
    target = LABEL_TARGETS[detection.label]
    if target.height_mm is None or target.sill_mm is None or target.swing is None:
        return None
    low, high = span
    width = target.width_mm if target.width_mm is not None else js_round(high - low)
    if width < _MIN_DOUBLE_DOOR_MM:
        dropped["openingUnattached"] += 1
        return None
    length = _length(seg)
    if length < width:
        dropped["openingTooWide"] += 1
        return None
    kind: Literal["door", "window"] = "window" if detection.label == "window" else "door"
    offset = min(max(js_round((low + high) / 2 - width / 2), 0), js_round(length - width))
    return _Cand(wall, order, kind, offset, width, target.height_mm, target.sill_mm, target.swing, detection.confidence)


def _opening_candidates(
    segs: Sequence[_Seg],
    geoms: Geoms,
    detections: Sequence[DetectionPx],
    scaling: Scaling,
    dropped: Counter[str],
) -> list[_Cand]:
    """Bước 4: mỗi hộp ô mở → tường gần nhất theo tâm; ngoài tầm với → `openingUnattached`."""
    chosen = [(order, det) for order, det in enumerate(detections) if det.label in _OPENING_LABELS]
    rects = [_rect(det.box, scaling) for _, det in chosen]
    centres = _centres(rects)
    nearest = _nearest_walls(STRtree(geoms), centres) if len(geoms) else [None] * len(rects)
    cands: list[_Cand] = []
    for position, (order, detection) in enumerate(chosen):
        found = nearest[position]
        if found is None or found[1] > segs[found[0]].thickness_mm / 2 + OPENING_WALL_REACH_MM:
            dropped["openingUnattached"] += 1
            continue
        span = _span_on_wall(rects[position], geoms[found[0]])
        cand = _candidate(order, detection, found[0], segs[found[0]], span, dropped)
        if cand is not None:
            cands.append(cand)
    return cands


def _centres(rects: Sequence[tuple[float, float, float, float]]) -> Geoms:
    """Tâm mọi hộp thành mảng `Point` trong một lần gọi (vector hoá cho `query_nearest`)."""
    if not rects:
        return np.asarray([], dtype=object)
    coords = [[(rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2] for rect in rects]
    return np.asarray(shapely.points(coords), dtype=object)


def _overlaps(a: _Cand, b: _Cand) -> bool:
    """Hai ô mở cùng tường có khoảng `[offset, offset + rộng]` chồng nhau."""
    return a.wall == b.wall and a.offset_mm < b.offset_mm + b.width_mm and b.offset_mm < a.offset_mm + a.width_mm


def _resolve_overlaps(cands: Sequence[_Cand], dropped: Counter[str]) -> list[_Cand]:
    """Chồng khoảng cùng tường → giữ `confidence` cao hơn (hoà: đứng trước), còn lại `openingOverlap`."""
    kept: list[_Cand] = []
    for cand in cands:
        clashes = [other for other in kept if _overlaps(other, cand)]
        if any(other.confidence >= cand.confidence for other in clashes):
            dropped["openingOverlap"] += 1
            continue
        losers = {other.order for other in clashes}
        kept = [other for other in kept if other.order not in losers]
        dropped["openingOverlap"] += len(losers)
        kept.append(cand)
    return sorted(kept, key=lambda item: item.order)


def _assemble(
    segs: Sequence[_Seg], cands: Sequence[_Cand], level_id: str, clock: Clock
) -> tuple[tuple[Wall, ...], tuple[Opening, ...]]:
    """Dựng `Wall` (id mới, `openingIds` theo thứ tự `detections`) và `Opening` tương ứng."""
    wall_ids = [new_spatial_id("wall", clock) for _ in segs]
    openings = tuple(
        Opening(
            id=new_spatial_id("opening", clock),
            wall_id=wall_ids[cand.wall],
            kind=cand.kind,
            offset_mm=cand.offset_mm,
            width_mm=cand.width_mm,
            height_mm=cand.height_mm,
            sill_height_mm=cand.sill_mm,
            swing=cand.swing,
            confidence=cand.confidence,
            source="ai",
            reviewed=False,
        )
        for cand in cands
    )
    per_wall: list[list[str]] = [[] for _ in segs]
    for opening, cand in zip(openings, cands, strict=True):
        per_wall[cand.wall].append(opening.id)
    walls = tuple(
        Wall(
            id=wall_ids[index],
            level_id=level_id,
            centreline=Segment(start=seg.start, end=seg.end),
            thickness_mm=seg.thickness_mm,
            height_mm=DEFAULT_WALL_HEIGHT_MM,
            kind="partition",
            opening_ids=tuple(per_wall[index]),
            confidence=seg.confidence,
            source="ai",
            reviewed=False,
        )
        for index, seg in enumerate(segs)
    )
    return walls, openings


def build_walls(
    walls: Sequence[WallPx],
    detections: Sequence[DetectionPx],
    *,
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
) -> WallSet:
    """Bước 3 + 3b + 4: tường mm, nối khe ô mở, ô mở; không sửa đối số vào.

    Chỉ nhãn `door|double_door|window` thành ô mở, nhãn khác bỏ qua **không** đếm (đồ đạc là
    việc của `rooms.build_furniture`). `dropped` cộng dồn tại chỗ theo khoá `DROPPED_KEYS`.
    """
    segs = _drop_isolated(_measure_walls(walls, scaling, dropped), dropped)
    boxes = _opening_boxes(detections, scaling)
    bridges = _join_gaps(segs, boxes, dropped) if segs else ()
    live = [seg for seg in segs if seg.alive]
    input_to_wall = {index: position for position, seg in enumerate(live) for index in seg.inputs}
    geoms = _linestrings(live) if live else np.asarray([], dtype=object)
    cands = _resolve_overlaps(_opening_candidates(live, geoms, detections, scaling, dropped), dropped)
    built_walls, openings = _assemble(live, cands, level_id, clock)
    return WallSet(built_walls, openings, input_to_wall, bridges)
