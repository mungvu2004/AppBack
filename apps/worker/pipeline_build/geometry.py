"""Tường, nối khe ô mở và ô mở (B5-05 [6] bước 3, 3b, 4); khung kiểu dùng chung do prep đặt.

Hình học chạy bằng `shapely` 2.x vector hoá: một `linestrings` cho mọi đường tim và một
`STRtree` **mỗi pha** (lọc khối cô lập, 3b, bước 4, hộp ô mở — 3b sửa hình học tại chỗ nên
cây của pha trước hết đúng), truy vấn theo lô (`dwithin`) — trần B5-01 là
20.000 tường và 5.000 hộp nên vòng Python qua mọi cặp tường là không chạy nổi.
Toạ độ mm: gốc trên-trái, y hướng xuống.
"""

import logging
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
    CORNER_OVERSHOOT_MM,
    DEFAULT_WALL_HEIGHT_MM,
    DIAGONAL_ALIGN_DEG,
    FAR_CLUSTER_AREA_SHARE,
    FAR_CLUSTER_GAP_MM,
    FAR_CLUSTER_LENGTH_SHARE,
    OPENING_GAP_MAX_MM,
    OPENING_MIN_WIDTH_MM,
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
_log = logging.getLogger(__name__)

_ALIGN_SIN: Final = math.sin(math.radians(2.0))
"""Lệch góc tối đa của cặp tường thẳng hàng (2°, B5-05 [6] 3b) đo bằng `|sin|` để khỏi `atan2`."""
_PERPENDICULAR_COS: Final = math.cos(math.radians(88.0))
"""Cặp tường vuông góc: `|cos|` của góc giữa hai hướng ≤ cos(88°), tức lệch 90° không quá 2°."""
_DIAGONAL_ALIGN_SIN: Final = math.sin(math.radians(DIAGONAL_ALIGN_DEG))
"""`_ALIGN_SIN` cho cặp tường chéo (`DIAGONAL_ALIGN_DEG`, BUG-IT-007)."""
_DIAGONAL_PERPENDICULAR_COS: Final = math.cos(math.radians(90.0 - DIAGONAL_ALIGN_DEG))
"""`_PERPENDICULAR_COS` cho cặp tường chéo (`DIAGONAL_ALIGN_DEG`, BUG-IT-007)."""
_DIAGONAL_MIN_SIN2: Final = math.sin(math.radians(2 * DIAGONAL_ALIGN_DEG))
"""Tường lệch trục gần nhất > `DIAGONAL_ALIGN_DEG` khi `|sin 2θ| = |2·ux·uy|` vượt số này."""
_MIN_DOUBLE_DOOR_MM: Final = 600
"""Cửa đôi hẹp hơn 600 mm là hộp bám sai tường, không phải cửa (B5-05 [6] bước 4)."""
# 3b (d): đầu tường lơ lửng nhìn thẳng gặp vách trong khe mặt-tới-mặt ≤ max(450, 3 x bề dày) → kéo tới chạm.
_DANGLE_REACH_MM: Final = 450
_DANGLE_REACH_THICKNESS: Final = 3
# Khe có tâm hộp ô mở → khe cửa, kéo xa tới 1200 mm (cửa đơn ≤ 1000 + mép); khe 2 m giữ nguyên.
_DANGLE_DOOR_REACH_MM: Final = 1200
# Đầu mút "chạm" tường khác khi cách tim ≤ ½ tổng bề dày + 10 mm (cùng thước của bộ đo F:/runs/r4-bd/tidy.py).
_TOUCH_SLACK_MM: Final = 10
# Luật WALL-OVERLAP của FE (AppFront rules/geometry): song song <= 5 độ chạm thân và chồng > 10 mm, hoặc tim cắt
# nhau cách mọi đầu > 50 mm. Lần kéo nào làm tăng số cặp như vậy bị hoàn lại.
_PARALLEL_SIN: Final = math.sin(math.radians(5.0))
_OVERLAP_MIN_MM: Final = 10
_JOINT_MM: Final = 50
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


def _clusters(segs: Sequence[_Seg]) -> list[list[int]]:
    """Cụm tường liên thông: hai tường chạm nhau khi tim cách ≤ nửa tổng bề dày + `WALL_JOIN_MM`."""
    geoms = _linestrings(segs)
    thickest = max(seg.measured_mm for seg in segs)
    near = _neighbours(STRtree(geoms), geoms, thickest + float(WALL_JOIN_MM))
    seen = [False] * len(segs)
    groups: list[list[int]] = []
    for root in range(len(segs)):
        if seen[root]:
            continue
        seen[root] = True
        group: list[int] = []
        queue = deque([root])
        while queue:
            index = queue.popleft()
            group.append(index)
            for other in near[index]:
                gap = (segs[index].measured_mm + segs[other].measured_mm) / 2 + WALL_JOIN_MM
                if not seen[other] and shapely.distance(geoms[index], geoms[other]) <= gap:
                    seen[other] = True
                    queue.append(other)
        groups.append(group)
    return groups


Box = tuple[float, float, float, float]


def _bbox(segs: Sequence[_Seg], group: Sequence[int]) -> Box:
    xs = [p.x for i in group for p in (segs[i].start, segs[i].end)]
    ys = [p.y for i in group for p in (segs[i].start, segs[i].end)]
    return (float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys)))


def _box_gap(a: Box, b: Box) -> float:
    """Khe ngắn nhất giữa hai hộp thẳng trục (0 khi chồng nhau)."""
    return math.hypot(max(b[0] - a[2], a[0] - b[2], 0.0), max(b[1] - a[3], a[1] - b[3], 0.0))


def _box_union(a: Box, b: Box) -> Box:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _box_area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def _drop_far_clusters(segs: list[_Seg], dropped: Counter[str]) -> list[_Seg]:
    """U57: bỏ cụm tường nhỏ nằm tách xa cụm chính (sơ đồ vị trí căn, logo ở góc brochure).

    Vùng chính = hộp cụm dài nhất, nới dần bằng mọi cụm có hộp cách vùng ≤ `FAR_CLUSTER_GAP_MM`
    (tường bị khe cửa cắt rời, ban công, cột sát căn). Cụm còn lại bị bỏ khi tổng dài <
    `FAR_CLUSTER_LENGTH_SHARE` tổng tường và hộp bao < `FAR_CLUSTER_AREA_SHARE` hộp vùng chính.
    Đếm vào `isolatedBlock`.
    """
    if len(segs) < 2:
        return segs
    groups = _clusters(segs)
    if len(groups) < 2:
        return segs
    lengths = [sum(_length(segs[i]) for i in group) for group in groups]
    boxes = [_bbox(segs, group) for group in groups]
    total = sum(lengths)
    # Vùng chính lớn dần: cụm dài nhất, rồi nuốt mọi cụm có hộp cách vùng ≤ khe (tường bị cửa cắt rời).
    region = boxes[max(range(len(groups)), key=lengths.__getitem__)]
    far = set(range(len(groups)))
    grown = True
    while grown:
        grown = False
        for index in sorted(far):
            if _box_gap(boxes[index], region) <= FAR_CLUSTER_GAP_MM:
                far.discard(index)
                region = _box_union(region, boxes[index])
                grown = True
    region_area = max(_box_area(region), 1.0)
    drop: set[int] = set()
    for index in far:
        small = _box_area(boxes[index]) < FAR_CLUSTER_AREA_SHARE * region_area
        if small and lengths[index] < FAR_CLUSTER_LENGTH_SHARE * total:
            drop.update(groups[index])
    if drop:
        dropped["isolatedBlock"] += len(drop)
        _log.info("pipeline_build_far_cluster_dropped", extra={"walls": len(drop)})
    return [seg for index, seg in enumerate(segs) if index not in drop]


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


def _diagonal(ua: tuple[float, float], ub: tuple[float, float]) -> bool:
    """Cả hai hướng lệch trục gần nhất > `DIAGONAL_ALIGN_DEG` (bản vẽ xoay chéo, BUG-IT-007)."""
    return min(abs(2 * ua[0] * ua[1]), abs(2 * ub[0] * ub[1])) > _DIAGONAL_MIN_SIN2


def _aligned(a: _Seg, b: _Seg) -> bool:
    """Thẳng hàng: lệch góc ≤ 2° (cặp chéo ≤ `DIAGONAL_ALIGN_DEG`) **và** lệch ngang ≤ ½ bề dày lớn hơn.

    Cặp thẳng trục đo hai đầu của `b` tới tim `a` (B5-05 [6] 3b). Cặp chéo đo khoảng lệch ngang giữa
    hai đầu mút gần nhau **vuông góc với hướng trung bình**: tim nhiễu 5° qua khe 900 đã lệch 78 mm
    nếu đo tới tim `a` kéo dài, còn hai đầu mút của một tường thật vẫn cùng một đường.
    """
    ua, ub = _unit(a), _unit(b)
    diagonal = _diagonal(ua, ub)
    if abs(ua[0] * ub[1] - ua[1] * ub[0]) > (_DIAGONAL_ALIGN_SIN if diagonal else _ALIGN_SIN):
        return False
    limit = max(a.thickness_mm, b.thickness_mm) / 2
    if not diagonal:
        return all(
            abs((point.x - a.start.x) * ua[1] - (point.y - a.start.y) * ua[0]) <= limit for point in (b.start, b.end)
        )
    ends = _near_ends(a, b)
    if ends is None:
        return False
    sign = 1.0 if ua[0] * ub[0] + ua[1] * ub[1] >= 0 else -1.0
    mx, my = ua[0] + sign * ub[0], ua[1] + sign * ub[1]
    dx, dy = ends[1].x - ends[0].x, ends[1].y - ends[0].y
    return abs(dx * my - dy * mx) / math.hypot(mx, my) <= limit


def _perpendicular(a: _Seg, b: _Seg) -> bool:
    """Vuông góc trong sai số 2° (cặp chéo `DIAGONAL_ALIGN_DEG`; dùng cho 3b-b: đầu mút chạm tim vách ngang)."""
    ua, ub = _unit(a), _unit(b)
    limit = _DIAGONAL_PERPENDICULAR_COS if _diagonal(ua, ub) else _PERPENDICULAR_COS
    return abs(ua[0] * ub[0] + ua[1] * ub[1]) <= limit


def _onto(line: _Seg, point: Point) -> Point:
    """Chân vuông góc của `point` trên đường thẳng chứa tim `line` (mm nguyên)."""
    along = _along(line, (point.x, point.y))
    unit = _unit(line)
    return Point(x=js_round(line.start.x + unit[0] * along), y=js_round(line.start.y + unit[1] * along))


def _absorb(keep: _Seg, drop: _Seg) -> None:
    """Gộp `drop` vào `keep`: hai đầu xa nhau nhất, `confidence` nhỏ hơn.

    Hai đầu chiếu lên tim của tường **dài hơn** (UX41-A): lấy thẳng hai đầu xa nhất của hai tường lệch
    ngang vài mm thì tường gộp nghiêng và rời đường trục mà vector hoá đã gióng chung.
    Bề dày: hai tường chồng nhau lấy bề dày lớn hơn (nhánh mảnh trùng tường dày); hai tường cách nhau
    một khe (nối qua cửa) lấy bề dày tường dài hơn — lấy lớn hơn thì vách bếp 2,8 m thành tường 200 chỉ
    vì đầu bên kia khe là mẩu cột 0,5 m.
    """
    pairs = [(p, q) for p in (keep.start, keep.end) for q in (drop.start, drop.end)]
    far = max(pairs, key=lambda pair: math.dist((pair[0].x, pair[0].y), (pair[1].x, pair[1].y)))
    base = keep if _length(keep) >= _length(drop) else drop
    k_low, k_high = sorted(_along(base, (p.x, p.y)) for p in (keep.start, keep.end))
    d_low, d_high = sorted(_along(base, (p.x, p.y)) for p in (drop.start, drop.end))
    apart = k_high < d_low or d_high < k_low
    keep.start, keep.end = _onto(base, far[0]), _onto(base, far[1])
    keep.thickness_mm = base.thickness_mm if apart else max(keep.thickness_mm, drop.thickness_mm)
    keep.measured_mm = base.measured_mm if apart else max(keep.measured_mm, drop.measured_mm)
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


def _along(seg: _Seg, point: tuple[float, float]) -> float:
    """Tham số dọc tim `seg` của điểm (mm, 0 tại `start`, `L` tại `end`)."""
    unit = _unit(seg)
    return (point[0] - seg.start.x) * unit[0] + (point[1] - seg.start.y) * unit[1]


def _foot_on_other(seg: _Seg, other: _Seg, reach: float = OPENING_GAP_MAX_MM) -> tuple[bool, Point] | None:
    """Đầu mút của `seg` cần kéo và chân trên tim `other`: `(là đầu end, chân)` hoặc `None`.

    Chỉ xét cặp vuông góc, nên hai đường không song song và định thức không bằng 0. Chân phải nằm
    trong đoạn `other` nới mỗi đầu `max(bề dày other, CORNER_OVERSHOOT_MM)` (tường lệch 0,75° hụt
    vách 29 mm, BUG-IT-001) và **ngoài** `seg`, cách đầu mút `0 < g ≤ reach`, và không
    trùng đầu mút còn lại (`Segment` cấm tường dài 0).
    """
    if not _perpendicular(seg, other):
        return None
    unit, other_unit = _unit(seg), _unit(other)
    dx, dy = other.start.x - seg.start.x, other.start.y - seg.start.y
    step = (dx * other_unit[1] - dy * other_unit[0]) / (unit[0] * other_unit[1] - unit[1] * other_unit[0])
    crossing = (seg.start.x + unit[0] * step, seg.start.y + unit[1] * step)
    slack = max(other.thickness_mm, CORNER_OVERSHOOT_MM)
    if not -slack <= _along(other, crossing) <= _length(other) + slack:
        return None
    foot = Point(x=js_round(crossing[0]), y=js_round(crossing[1]))
    if -reach <= step < 0 and foot != seg.end:
        return (False, foot)
    if _length(seg) < step <= _length(seg) + reach and foot != seg.start:
        return (True, foot)
    return None


def _clash(a: _Seg, b: _Seg) -> bool:
    """Cặp tường vi phạm WALL-OVERLAP của FE: chồng song song hoặc cắt xuyên thân (xem `_PARALLEL_SIN`)."""
    la, lb = _line(a), _line(b)
    ua, ub = _unit(a), _unit(b)
    if abs(ua[0] * ub[1] - ua[1] * ub[0]) <= _PARALLEL_SIN:
        if la.distance(lb) > (a.thickness_mm + b.thickness_mm) / 2:
            return False
        low, high = sorted(_along(a, (p.x, p.y)) for p in (b.start, b.end))
        return min(_length(a), high) - max(0.0, low) > _OVERLAP_MIN_MM
    at = la.intersection(lb)
    if at.geom_type != "Point":
        return False
    return all(math.dist((at.x, at.y), (p.x, p.y)) > _JOINT_MM for p in (a.start, a.end, b.start, b.end))


def _clashes(seg: _Seg, segs: Sequence[_Seg]) -> int:
    """Số tường sống khác mà `seg` chồng/cắt xuyên theo `_clash`."""
    return sum(other is not seg and other.alive and _clash(seg, other) for other in segs)


def _try_extend(seg: _Seg, other: _Seg, is_end: bool, foot: Point, segs: Sequence[_Seg]) -> bool:
    """Kéo đầu mút của `seg` tới `foot` (và `_stretch_to` vách `other`); tăng số cặp chồng/cắt → hoàn lại."""
    saved = (seg.start, seg.end, other.start, other.end)
    before = _clashes(seg, segs) + _clashes(other, segs)
    if is_end:
        seg.end = foot
    else:
        seg.start = foot
    _stretch_to(other, foot)
    if _clashes(seg, segs) + _clashes(other, segs) > before:
        seg.start, seg.end, other.start, other.end = saved
        return False
    return True


def _extend_once(seg: _Seg, others: Sequence[_Seg], boxes: _Boxes, segs: Sequence[_Seg]) -> bool:
    """3b (b) cho một tường: kéo đầu mút tới tim vách vuông góc đầu tiên mà khe có hộp."""
    for other in others:
        hit = _foot_on_other(seg, other)
        if hit is None:
            continue
        is_end, foot = hit
        if not boxes.covers(seg.end if is_end else seg.start, foot):
            continue
        if _try_extend(seg, other, is_end, foot, segs):
            return True
    return False


def _stretch_to(seg: _Seg, foot: Point) -> None:
    """Chân lố ra ngoài đoạn `seg` (trong dung sai của `_foot_on_other`) → kéo đầu gần chân tới chân.

    Góc khép kín thay vì hở vài chục mm; chân ở ngoài `[0, L]` nên cách đầu xa > 0, không thành dài 0.
    """
    along = _along(seg, (foot.x, foot.y))
    if along < 0:
        seg.start = foot
    elif along > _length(seg):
        seg.end = foot


def _extend_all(segs: list[_Seg], neighbours: list[set[int]], boxes: _Boxes, dropped: Counter[str]) -> None:
    """3b (b) cho mọi tường còn giữ; mỗi tường kéo nhiều nhất một đầu mút một lần."""
    for index, seg in enumerate(segs):
        if not seg.alive:
            continue
        others = [segs[other] for other in sorted(neighbours[index]) if segs[other].alive]
        if others and _extend_once(seg, others, boxes, segs):
            dropped["wallGapBridged"] += 1


def _line(seg: _Seg) -> LineString:
    """Tim `seg` thành `LineString` (mm)."""
    return LineString(((seg.start.x, seg.start.y), (seg.end.x, seg.end.y)))


def _dangling(seg: _Seg, tip: Point, segs: Sequence[_Seg]) -> bool:
    """Đầu mút `tip` không chạm tim tường sống nào khác (cách > ½ tổng bề dày + `_TOUCH_SLACK_MM`)."""
    point = shapely.points(tip.x, tip.y)
    return not any(
        other is not seg
        and other.alive
        and shapely.distance(point, _line(other)) <= (seg.thickness_mm + other.thickness_mm) / 2 + _TOUCH_SLACK_MM
        for other in segs
    )


def _blocked(seg: _Seg, other: _Seg, tip: Point, foot: Point, segs: Sequence[_Seg]) -> bool:
    """Khe từ `tip` tới mặt `other` cắt tim một tường sống thứ ba (không kéo xuyên tường)."""
    span = math.dist((tip.x, tip.y), (foot.x, foot.y))
    back = other.thickness_mm / 2
    if span <= back + 2:
        return False
    ux, uy = (foot.x - tip.x) / span, (foot.y - tip.y) / span
    gap = LineString(((tip.x + ux, tip.y + uy), (foot.x - ux * back, foot.y - uy * back)))
    return any(item.alive and item is not seg and item is not other and gap.intersects(_line(item)) for item in segs)


def _centre_in_gap(boxes: _Boxes, seg: _Seg, tip: Point, face: float) -> bool:
    """Đúng **một** tâm hộp ô mở trong khe: dọc `(0, face]` từ `tip`, ngang ≤ ½ bề dày + `OPENING_WALL_REACH_MM`.

    Hai hộp trở lên là không chắc (cửa của vách bên cạnh lọt vào dải, ch-09 lô gia) → giữ khe.
    """
    ux, uy = _unit(seg)
    if math.dist((tip.x, tip.y), (seg.start.x, seg.start.y)) < 1:
        ux, uy = -ux, -uy
    lateral = seg.thickness_mm / 2 + OPENING_WALL_REACH_MM
    inside = 0
    for x0, y0, x1, y1 in boxes.rects:
        dx, dy = (x0 + x1) / 2 - tip.x, (y0 + y1) / 2 - tip.y
        inside += 0 < dx * ux + dy * uy <= face and abs(dx * uy - dy * ux) <= lateral
    return inside == 1


def _reach_dangling(segs: list[_Seg], neighbours: Sequence[set[int]], boxes: _Boxes, dropped: Counter[str]) -> None:
    """3b (d): đầu lơ lửng còn lại → kéo theo phương tường tới tim vách vuông góc gần nhất phía trước.

    Khe mặt-tới-mặt ≤ max(`_DANGLE_REACH_MM`, `_DANGLE_REACH_THICKNESS` x bề dày) không cần hộp cửa; khe có
    tâm hộp ô mở (`_centre_in_gap`) tới `_DANGLE_DOOR_REACH_MM`: khe cửa trong bản vẽ là tường có ô mở, và
    bước 4 gắn hộp đó vào chính tường đã kéo. Vách phía trước bị tường khác chắn (`_blocked`) → giữ khe.
    """
    for index, seg in enumerate(segs):
        if not seg.alive:
            continue
        reach = max(_DANGLE_REACH_MM, _DANGLE_REACH_THICKNESS * seg.thickness_mm)
        best: dict[bool, tuple[float, Point, _Seg]] = {}
        for other in (segs[item] for item in sorted(neighbours[index])):
            hit = _foot_on_other(seg, other, max(reach, _DANGLE_DOOR_REACH_MM) + other.thickness_mm / 2)
            hit = hit if other.alive else None
            if hit is None:
                continue
            is_end, foot = hit
            tip = seg.end if is_end else seg.start
            gap = math.dist((tip.x, tip.y), (foot.x, foot.y))
            if is_end not in best or gap < best[is_end][0]:
                best[is_end] = (gap, foot, other)
        for is_end, (gap, foot, other) in best.items():
            tip = seg.end if is_end else seg.start
            face = gap - other.thickness_mm / 2
            if face > reach and not _centre_in_gap(boxes, seg, tip, face):
                continue
            if not _dangling(seg, tip, segs) or _blocked(seg, other, tip, foot, segs):
                continue
            if _try_extend(seg, other, is_end, foot, segs):
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
    """Bước 3b: gộp cặp thẳng hàng (a), kéo đầu mút tới vách (b), đầu lơ lửng (d), đoạn nối cặp còn lại (c)."""
    geoms = _linestrings(segs)
    tree = STRtree(geoms)
    lines = _Centrelines(tree, {seg.inputs[0]: slot for slot, seg in enumerate(segs)})
    neighbours = _neighbours(tree, geoms, float(OPENING_GAP_MAX_MM))
    _merge_aligned(segs, neighbours, boxes, lines, dropped)
    _extend_all(segs, neighbours, boxes, dropped)
    _reach_dangling(segs, neighbours, boxes, dropped)
    return _bridge_segments(segs, neighbours)


def _attach_walls(
    segs: Sequence[_Seg], geoms: Geoms, rects: Sequence[tuple[float, float, float, float]]
) -> list[int | None]:
    """Tường gắn cho mỗi hộp ô mở, `None` khi không tường nào với tới (bước 4).

    Ứng viên: tường mà **hộp** (không phải tâm) cách tim ≤ `thicknessMm / 2 + OPENING_WALL_REACH_MM`,
    0 khi tim cắt hộp — hộp thẳng trục của cửa xoay chéo là hộp vuông lớn, tâm xa tim (BUG-IT-003).
    Trong ứng viên chọn tường gần **tâm** hộp nhất, hoà lấy chỉ số nhỏ: cửa sát góc chạm cả vách
    vuông góc vẫn về tường nó nằm trên. Một truy vấn `dwithin` theo lô, khoảng cách vector hoá.
    """
    best: list[int | None] = [None] * len(rects)
    if not rects or not len(geoms):
        return best
    boxes = np.asarray(shapely.box(*np.asarray(rects).T), dtype=object)
    reach = np.asarray([seg.thickness_mm / 2 + OPENING_WALL_REACH_MM for seg in segs])
    sources, walls = STRtree(geoms).query(boxes, predicate="dwithin", distance=float(reach.max()))
    inside = shapely.distance(boxes[sources], geoms[walls]) <= reach[walls]
    centre = shapely.distance(shapely.centroid(boxes[sources]), geoms[walls])
    ranked = zip(centre[inside].tolist(), walls[inside].tolist(), sources[inside].tolist(), strict=True)
    for _, wall, source in sorted(ranked):
        if best[source] is None:
            best[source] = wall
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
    """Bước 4 cho một hộp đã biết tường: rộng = hình chiếu hộp lên tim, `offsetMm` kẹp trong tường.

    Rộng lấy từ hộp, kẹp ≤ `L` (BUG-IT-004: rộng cố định làm rơi ô mở trên tường ngắn và chồng cửa
    sổ kề nhau); hình chiếu < `OPENING_MIN_WIDTH_MM` là suy biến → rộng mặc định của `LABEL_TARGETS`
    kẹp về `L` khi `L ≥ OPENING_MIN_WIDTH_MM`, tường ngắn hơn → `openingTooWide` (BUG-IT-009).
    Cửa đôi không có mặc định: hẹp hơn 600 mm là `openingUnattached`.
    """
    target = LABEL_TARGETS[detection.label]
    if target.height_mm is None or target.sill_mm is None or target.swing is None:
        return None
    low, high = span
    length = _length(seg)
    # Hộp thẳng trục của ô mở trên tường lệch góc θ chiếu dài thêm bề dày · |sin 2θ| (review P2 LOG-02).
    ux, uy = _unit(seg)
    measured = min(js_round(high - low - seg.thickness_mm * abs(2 * ux * uy)), math.floor(length))
    if target.width_mm is None and measured < _MIN_DOUBLE_DOOR_MM:
        dropped["openingUnattached"] += 1
        return None
    width = target.width_mm if target.width_mm is not None and measured < OPENING_MIN_WIDTH_MM else measured
    if length < width:
        # BUG-IT-009: tường đủ chỗ cho một ô mở thật (≥ OPENING_MIN_WIDTH_MM) → kẹp rộng mặc định về chiều dài.
        if length < OPENING_MIN_WIDTH_MM:
            dropped["openingTooWide"] += 1
            return None
        width = math.floor(length)
    kind: Literal["door", "window"] = "window" if detection.label == "window" else "door"
    # Trần `floor`, không `js_round`: rộng kẹp `floor(L)` + làm tròn lên lố đầu tường 1 mm (review 2 P2 LOG-02).
    offset = min(max(js_round((low + high) / 2 - width / 2), 0), math.floor(length - width))
    return _Cand(wall, order, kind, offset, width, target.height_mm, target.sill_mm, target.swing, detection.confidence)


def _opening_candidates(
    segs: Sequence[_Seg],
    geoms: Geoms,
    detections: Sequence[DetectionPx],
    scaling: Scaling,
    dropped: Counter[str],
) -> list[_Cand]:
    """Bước 4: mỗi hộp ô mở → tường của `_attach_walls`; không tường nào với tới → `openingUnattached`."""
    chosen = [(order, det) for order, det in enumerate(detections) if det.label in _OPENING_LABELS]
    rects = [_rect(det.box, scaling) for _, det in chosen]
    attached = _attach_walls(segs, geoms, rects)
    cands: list[_Cand] = []
    for position, (order, detection) in enumerate(chosen):
        wall = attached[position]
        if wall is None:
            dropped["openingUnattached"] += 1
            continue
        span = _span_on_wall(rects[position], geoms[wall])
        cand = _candidate(order, detection, wall, segs[wall], span, dropped)
        if cand is not None:
            cands.append(cand)
    return cands


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
            detected_thickness_mm=max(1, js_round(seg.measured_mm)),
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
    segs = _drop_far_clusters(_drop_isolated(_measure_walls(walls, scaling, dropped), dropped), dropped)
    boxes = _opening_boxes(detections, scaling)
    bridges = _join_gaps(segs, boxes, dropped) if segs else ()
    live = [seg for seg in segs if seg.alive]
    input_to_wall = {index: position for position, seg in enumerate(live) for index in seg.inputs}
    geoms = _linestrings(live) if live else np.asarray([], dtype=object)
    cands = _resolve_overlaps(_opening_candidates(live, geoms, detections, scaling, dropped), dropped)
    built_walls, openings = _assemble(live, cands, level_id, clock)
    return WallSet(built_walls, openings, input_to_wall, bridges)
