"""Tường, nối khe ô mở và ô mở (B5-05 [6] bước 3, 3b, 4); khung kiểu dùng chung do prep đặt.

Hình học chạy bằng `shapely` 2.x vector hoá: một `linestrings` cho mọi đường tim và một
`STRtree` **mỗi pha** (lọc khối cô lập, 3b, bước 4, hộp ô mở — 3b sửa hình học tại chỗ nên
cây của pha trước hết đúng), truy vấn theo lô (`dwithin`) — trần B5-01 là
20.000 tường và 5.000 hộp nên vòng Python qua mọi cặp tường là không chạy nổi.
Toạ độ mm: gốc trên-trái, y hướng xuống.
"""

import itertools
import logging
import math
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
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
    WALL_JOIN_MM,
)
from apps.worker.pipeline_build.ids import new_spatial_id
from apps.worker.pipeline_build.residual import PageRaster
from apps.worker.pipeline_build.swing import read_leaf
from packages.core.clock import Clock
from packages.domain.rules_ai import wall_side
from packages.domain.spatial import Opening, Point, Room, Segment, Wall, js_round
from packages.domain.spatial.thickness import snap_thickness
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
_MAX_SINGLE_LEAF_MM: Final = 1200
"""Cửa một cánh rộng hơn ngần này không có thật: đọc được cung mở mà rộng hơn → hai cánh (C3)."""
_SLIDING_MIN_MM: Final = 1500
"""Cửa đi không đọc được cung mở mà rộng ≥ ngần này là cửa lùa (C3)."""
_SPLIT_GAP_MM: Final = 60
_ENVELOPE_DOOR_MIN_MM: Final = 600
"""Khe thẳng hàng trên tường ngoài ≥ ngần này là cửa bộ dò bỏ sót (C5); hẹp hơn thì xây kín."""
_GUESSED_DOOR_CONFIDENCE: Final = 0.3
"""Cửa đoán từ khe tường ngoài, không đọc được cánh và hẹp hơn cửa lùa: tin thấp để người duyệt thấy (C5)."""
_INFERRED_DOOR_CONFIDENCE: Final = 0.5
"""Cửa đoán từ khe tường ngoài mà đọc được cánh hay đủ rộng thành cửa lùa (C5)."""
"""Hai ô mở cùng loại cùng tường cách nhau ≤ ngần này là một ô mở bị bộ dò cắt đôi (C4: 1400 + 600 cách 3-40 mm)."""
"""Cửa đôi hẹp hơn 600 mm là cửa đơn bị dò nhầm lớp: giữ thành cửa đơn (B11, chẩn đoán quy trình lần 2)."""
_OPENING_REACH_SHARE: Final = 0.25
"""Tầm gắn ô mở theo cỡ hộp: hộp rộng `w` với tới tường cách ≤ 0,25·w (vẫn không dưới ½ dày + 150 mm)."""
_GAP_PARALLEL_COS: Final = math.cos(math.radians(20.0))
"""Tường lệch hướng hộp ô mở ≤ 20° là cùng hướng: bước 3c không dựng tường qua khe (OPEN-ATTACH)."""
# 3b (d): đầu tường lơ lửng nhìn thẳng gặp vách trong khe mặt-tới-mặt ≤ max(450, 3 x bề dày) → kéo tới chạm.
_DANGLE_REACH_MM: Final = 450
_DANGLE_REACH_THICKNESS: Final = 3
# Khe có tâm hộp ô mở → khe cửa, kéo xa tới 1200 mm (cửa đơn ≤ 1000 + mép); khe 2 m giữ nguyên.
_DANGLE_DOOR_REACH_MM: Final = 1200
# 3b (e): mẩu tường ngắn chạy song song sát mặt một tường dày hơn (nét bậu cửa, nét kép) mà có đầu lơ lửng.
_HUG_STUB_MAX_MM: Final = 600
_HUG_FACE_MAX_MM: Final = 150
_HUG_COS_MIN: Final = math.cos(math.radians(10))
_HAIRLINE_MM: Final = 40
"""Bề dày đo dưới ngần này là nét mảnh (kính cửa lùa, nét ký hiệu), không phải tường; bậc chuẩn từng nâng lên 100."""
_NIB_MAX_MM: Final = 200
"""Mẩu ngắn hơn ngần này có đầu lơ lửng, không mang ô mở là vụn nét, không phải tường (C2)."""
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
    leaves: Mapping[str, tuple[float, float]] = MappingProxyType({})
    """Id ô mở → hướng cánh đọc từ nét vẽ, cho `swing.settle_reversed` sau khi có phòng (QT-SWING)."""


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
    leaf: tuple[float, float] | None = None
    """Hướng cánh tuyệt đối trên mặt bằng đọc từ nét vẽ (QT-SWING); `None` = chưa đọc được."""


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


def _hits(tree: STRtree, geom: shapely.Geometry) -> list[int]:
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
        thickness = snap_thickness(measured)
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


def _drop_hairlines(segs: list[_Seg], dropped: Counter[str]) -> list[_Seg]:
    """Bước 3: bỏ tường đo mỏng hơn `_HAIRLINE_MM` (đếm `isolatedBlock`).

    Chỉ khi bản vẽ có tường dày ≥ `_HAIRLINE_MM`: cả bản toàn nét mảnh là tỉ lệ sai, bỏ hết thì mất nhà.
    """
    kept = [seg for seg in segs if seg.measured_mm >= _HAIRLINE_MM]
    if not kept:
        return segs
    dropped["isolatedBlock"] += len(segs) - len(kept)
    return kept


def _inside(dup: _Seg, host: _Seg) -> bool:
    """`dup` song song (≤ 10°), đo mỏng hơn `host`, hai đầu cách tim `host` ≤ ½ dày, chiếu trong `host` ± ½ dày."""
    if host is dup or host.measured_mm <= dup.measured_mm:
        return False
    (ax, ay), (bx, by) = _unit(dup), _unit(host)
    if abs(ax * bx + ay * by) < _HUG_COS_MIN:
        return False
    half, span = host.thickness_mm / 2, _length(host)
    for tip in (dup.start, dup.end):
        along = (tip.x - host.start.x) * bx + (tip.y - host.start.y) * by
        side = abs((tip.x - host.start.x) * by - (tip.y - host.start.y) * bx)
        if not -half <= along <= span + half or side > half:
            return False
    return True


def _drop_inside_body(segs: list[_Seg], dropped: Counter[str]) -> list[_Seg]:
    """Bước 3: tường nằm trong thân một tường dày hơn (nét kính cửa lùa giữa tường 220) là nét trùng → bỏ.

    Không giới hạn dài, không tha khi chạm hộp ô mở: ô mở về tường chủ ở bước 4 (C2).
    """
    if not segs:
        return segs
    geoms = _linestrings(segs)
    near = _neighbours(STRtree(geoms), geoms, max(seg.thickness_mm for seg in segs) / 2)
    kept = [seg for index, seg in enumerate(segs) if not any(_inside(seg, segs[other]) for other in near[index])]
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
    if not isinstance(at, shapely.Point):
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


def _hugs(stub: _Seg, wall: _Seg) -> bool:
    """`stub` song song (≤ 10°) với `wall` dày hơn, cả hai đầu chiếu vào thân `wall`, mặt tới mặt ≤ 150 mm."""
    if wall is stub or not wall.alive or wall.thickness_mm <= stub.thickness_mm:
        return False
    (ax, ay), (bx, by) = _unit(stub), _unit(wall)
    if abs(ax * bx + ay * by) < _HUG_COS_MIN:
        return False
    span = _length(wall)
    for tip in (stub.start, stub.end):
        along = (tip.x - wall.start.x) * bx + (tip.y - wall.start.y) * by
        side = abs((tip.x - wall.start.x) * by - (tip.y - wall.start.y) * bx)
        if not 0 <= along <= span or side - (stub.thickness_mm + wall.thickness_mm) / 2 > _HUG_FACE_MAX_MM:
            return False
    return True


def _drop_hugging_stubs(segs: list[_Seg], neighbours: Sequence[set[int]], boxes: _Boxes, dropped: Counter[str]) -> None:
    """3b (e): bỏ mẩu ≤ 600 mm áp sát mặt tường dày hơn khi có đầu không chạm tường thứ ba và không mang ô mở.

    Mẩu như vậy không khép phòng nào (một đầu tự do) mà để lại đầu lơ lửng cách mặt tường 70-150 mm
    (WALL-DANGLING-END ở màn Quy chuẩn). Kéo theo trục không chạm được vì nó song song với tường kia.
    Tường chủ và tường chạm đầu mẩu đều cách mẩu < `OPENING_GAP_MAX_MM` nên chỉ dò trong `neighbours`.
    """
    for index, stub in enumerate(segs):
        if not stub.alive or _length(stub) > _HUG_STUB_MAX_MM or _hits(boxes.tree, _line(stub)):
            continue
        near = [segs[item] for item in sorted(neighbours[index])]
        host = next((wall for wall in near if _hugs(stub, wall)), None)
        if host is None:
            continue
        others = [seg for seg in near if seg is not host]
        if _dangling(stub, stub.start, others) or _dangling(stub, stub.end, others):
            stub.alive = False
            dropped["isolatedBlock"] += 1


def _drop_dangling_nibs(segs: list[_Seg], neighbours: Sequence[set[int]], boxes: _Boxes, dropped: Counter[str]) -> None:
    """3b (f): mẩu < `_NIB_MAX_MM` có đầu lơ lửng sau khi đã kéo (b, d), thân không chạm hộp ô mở → bỏ (C2).

    Thân nới thêm một bề dày khi dò hộp: mẩu cạnh khe cửa (má cửa) chạm mép hộp vẫn được giữ.
    """
    for index, nib in enumerate(segs):
        if not nib.alive or _length(nib) >= _NIB_MAX_MM or _hits(boxes.tree, _line(nib).buffer(nib.thickness_mm)):
            continue
        near = [segs[item] for item in sorted(neighbours[index])]
        if _dangling(nib, nib.start, near) or _dangling(nib, nib.end, near):
            nib.alive = False
            dropped["isolatedBlock"] += 1


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
    _drop_hugging_stubs(segs, neighbours, boxes, dropped)
    _drop_dangling_nibs(segs, neighbours, boxes, dropped)
    return _bridge_segments(segs, neighbours)


def _attach_walls(
    segs: Sequence[_Seg], geoms: Geoms, rects: Sequence[tuple[float, float, float, float]]
) -> list[list[int]]:
    """Tường ứng viên của mỗi hộp ô mở, gần tâm trước; rỗng khi không tường nào với tới (bước 4).

    Ứng viên: tường mà **hộp** (không phải tâm) cách tim ≤ max(`thicknessMm / 2 + OPENING_WALL_REACH_MM`,
    `_OPENING_REACH_SHARE` x cạnh dài hộp) — cửa sổ rộng vẽ lệch khỏi tim xa hơn 150 mm vẫn gắn,
    0 khi tim cắt hộp — hộp thẳng trục của cửa xoay chéo là hộp vuông lớn, tâm xa tim (BUG-IT-003).
    Xếp theo khoảng cách tới **tâm** hộp, hoà lấy chỉ số nhỏ: cửa sát góc chạm cả vách vuông góc vẫn về
    tường nó nằm trên. `_opening_candidates` chọn trong danh sách. Một truy vấn `dwithin` theo lô.
    """
    ranked: list[list[int]] = [[] for _ in rects]
    if not rects or not len(geoms):
        return ranked
    boxes = np.asarray(shapely.box(*np.asarray(rects).T), dtype=object)
    reach = np.asarray([seg.thickness_mm / 2 + OPENING_WALL_REACH_MM for seg in segs])
    box_reach = np.asarray([_OPENING_REACH_SHARE * max(r[2] - r[0], r[3] - r[1]) for r in rects])
    far = max(float(reach.max()), float(box_reach.max()))
    sources, walls = STRtree(geoms).query(boxes, predicate="dwithin", distance=far)
    inside = shapely.distance(boxes[sources], geoms[walls]) <= np.maximum(reach[walls], box_reach[sources])
    centre = shapely.distance(shapely.centroid(boxes[sources]), geoms[walls])
    hits = zip(centre[inside].tolist(), walls[inside].tolist(), sources[inside].tolist(), strict=True)
    for _, wall, source in sorted(hits):
        ranked[source].append(wall)
    return ranked


def _runs_along(rect: tuple[float, float, float, float], span: tuple[float, float], length: float) -> bool:
    """Hộp nằm dọc tường đủ dài: tường ≥ `OPENING_MIN_WIDTH_MM` và hình chiếu ≥ ½ cạnh dài của hộp.

    Mẩu tường má cửa (ngắn, thường vuông góc với hộp) thường gần tâm hộp hơn tường thật mà cửa nằm trên;
    gắn vào mẩu đó thì ô mở rơi `openingTooWide` hoặc lấy rộng mặc định chồng lên ô mở bên cạnh (OPEN-ATTACH).
    """
    long_side = max(rect[2] - rect[0], rect[3] - rect[1])
    return length >= OPENING_MIN_WIDTH_MM and span[1] - span[0] >= long_side / 2


def _gap_walls(segs: Sequence[_Seg], detections: Sequence[DetectionPx], scaling: Scaling) -> list[_Seg]:
    """Bước 3c: tường qua phần khe của hộp ô mở dài mà không tường cùng hướng nào phủ (OPEN-ATTACH).

    Mẩu má cửa vector hoá thành đoạn xiên ngắn, hay tường dừng ngay trước khe, thì 3b không nối được khe: cửa chỉ
    còn tường vuông góc hoặc một đầu tường thẳng hàng để gắn → rơi `openingTooWide` hoặc lấy rộng mặc định chồng
    lên ô mở bên cạnh. Có tường nằm dọc hộp (`_runs_along`, kể cả tường chéo xuyên hộp) thì không dựng. Dọc cạnh dài
    của hộp, bỏ khoảng mà tường với tới cùng hướng (lệch ≤ 20°) đã phủ; khoảng trống
    dài nhất ≥ `OPENING_MIN_WIDTH_MM` thành tim mới qua tâm hộp, bề dày và tin cậy của tường gần tâm nhất. Hộp cắt
    hộp đã dựng tường thì bỏ (cửa trùng); hộp gần vuông (cạnh dài < 2 lần cạnh ngắn) không rõ hướng nên không dựng.
    """
    if not segs:
        return []
    geoms = _linestrings(segs)
    rects = [_rect(det.box, scaling) for det in detections if det.label in _OPENING_LABELS]
    added: list[_Seg] = []
    used: list[tuple[float, float, float, float]] = []
    for rect, walls in zip(rects, _attach_walls(segs, geoms, rects), strict=True):
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        if not walls or max(width, height) < max(OPENING_MIN_WIDTH_MM, 2 * min(width, height)):
            continue
        if any(rect[0] < x1 and x0 < rect[2] and rect[1] < y1 and y0 < rect[3] for x0, y0, x1, y1 in used):
            continue
        if any(_runs_along(rect, *_placement(segs, geoms, {}, rect, wall)[2:]) for wall in walls):
            continue
        axis = 0 if width >= height else 1
        covered = [
            sorted((segs[wall].start.x, segs[wall].end.x) if axis == 0 else (segs[wall].start.y, segs[wall].end.y))
            for wall in walls
            if abs(_unit(segs[wall])[axis]) >= _GAP_PARALLEL_COS
        ]
        low, high = _longest_free(rect[axis], rect[axis + 2], covered)
        if high - low < OPENING_MIN_WIDTH_MM:
            continue
        mid = js_round((rect[1 - axis] + rect[3 - axis]) / 2)
        ends = (js_round(low), js_round(high))
        start, end = (
            (Point(x=ends[0], y=mid), Point(x=ends[1], y=mid))
            if axis == 0
            else (Point(x=mid, y=ends[0]), Point(x=mid, y=ends[1]))
        )
        near = segs[walls[0]]
        added.append(_Seg(start, end, near.thickness_mm, float(near.thickness_mm), near.confidence, ()))
        used.append(rect)
    return added


def _longest_free(low: float, high: float, covered: Sequence[Sequence[float]]) -> tuple[float, float]:
    """Khoảng con dài nhất của `[low, high]` không nằm trong khoảng `covered` nào (hoà: khoảng trước)."""
    best, cursor = (low, low), low
    for start, end in sorted((max(a, low), min(b, high)) for a, b in covered if b > low and a < high):
        if start - cursor > best[1] - best[0]:
            best = (cursor, start)
        cursor = max(cursor, end)
    return (cursor, high) if high - cursor > best[1] - best[0] else best


def _arc_chains(segs: Sequence[_Seg], arc_of: Sequence[int | None]) -> dict[int, tuple[int, ...]]:
    """Vị trí dây → mọi vị trí dây của cung chứa nó, theo thứ tự; chỉ cung `arcs.join_arcs` sẽ gộp.

    Cùng điều kiện gộp: mỗi dây còn là tường riêng một đầu vào, đủ mọi dây, số dây chẵn, nối đuôi nhau.
    """
    members: dict[int, list[tuple[int, int]]] = {}
    for slot, seg in enumerate(segs):
        if len(seg.inputs) == 1 and (arc := arc_of[seg.inputs[0]] if arc_of else None) is not None:
            members.setdefault(arc, []).append((seg.inputs[0], slot))
    total = Counter(arc for arc in arc_of if arc is not None)
    chains: dict[int, tuple[int, ...]] = {}
    for arc, pairs in members.items():
        order = tuple(slot for _, slot in sorted(pairs))
        linked = all(segs[one].end == segs[two].start for one, two in itertools.pairwise(order))
        if len(order) == total[arc] and not len(order) % 2 and linked:
            chains.update(dict.fromkeys(order, order))
    return chains


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
    length: float | None = None,
) -> _Cand | None:
    """Bước 4 cho một hộp đã biết tường: rộng = hình chiếu hộp lên tim, `offsetMm` kẹp trong tường.

    Rộng lấy từ hộp, kẹp ≤ `L` (BUG-IT-004: rộng cố định làm rơi ô mở trên tường ngắn và chồng cửa
    sổ kề nhau); hình chiếu < `OPENING_MIN_WIDTH_MM` là suy biến → rộng mặc định của `LABEL_TARGETS`
    kẹp về `L` khi `L ≥ OPENING_MIN_WIDTH_MM`, tường ngắn hơn → `openingTooWide` (BUG-IT-009).
    Cửa đôi hẹp hơn 600 mm là cửa đơn bị dò nhầm: giữ thành cửa đơn (mặc định `door`) thay vì bỏ.
    `length` thay chiều dài `seg` khi ô mở
    đo trên cả cung (`span` tính từ đầu cung, `wall` là dây đầu).
    """
    target = LABEL_TARGETS[detection.label]
    low, high = span
    length = _length(seg) if length is None else length
    # Hộp thẳng trục của ô mở trên tường lệch góc θ chiếu dài thêm bề dày · |sin 2θ| (review P2 LOG-02).
    ux, uy = _unit(seg)
    measured = min(js_round(high - low - seg.thickness_mm * abs(2 * ux * uy)), math.floor(length))
    if target.width_mm is None and measured < _MIN_DOUBLE_DOOR_MM:
        target = LABEL_TARGETS["door"]
    if target.height_mm is None or target.sill_mm is None or target.swing is None:
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


def _read_swing(cand: _Cand, seg: _Seg, page: PageRaster | None, scaling: Scaling) -> _Cand:
    """Cửa một cánh trên tường thẳng: bản lề + phía cánh từ nét vẽ (`swing.read_leaf`); không đọc được → giữ nguyên.

    C3: không đọc được cung (hay không có trang) mà rộng ≥ `_SLIDING_MIN_MM` → `"sliding"`; đọc được mà rộng hơn
    `_MAX_SINGLE_LEAF_MM` → `"double"` (vẫn giữ phía cánh cho `settle_reversed`).

    Khe `a → b` = `[offset, offset + rộng]` dọc tim tính từ `seg.start`, đổi về px trang. Bản lề ở `a` (phía đầu
    tường) → `"left"`, ở `b` → `"right"` (Pascal `hingesSide`, `swing.py`); hướng cánh lưu tuyệt đối để
    `settle_reversed` so với luật phía mở của FE.
    """
    if cand.kind != "door" or cand.swing != "left":
        return cand
    ux, uy = _unit(seg)
    scale = scaling.build

    def at(t: float) -> tuple[float, float]:
        return ((seg.start.x + ux * t) / scale, (seg.start.y + uy * t) / scale)

    leaf = None
    if page is not None:
        leaf = read_leaf(page, at(cand.offset_mm), at(cand.offset_mm + cand.width_mm), seg.measured_mm / 2 / scale)
    if leaf is None:
        # C3: không cung mở mà rộng ≥ 1,5 m → cửa lùa (trước đây giữ "left" theo nhãn).
        return replace(cand, swing="sliding") if cand.width_mm >= _SLIDING_MIN_MM else cand
    swing: SwingDirection = "right" if leaf.hinge_at_b else "left"
    if cand.width_mm > _MAX_SINGLE_LEAF_MM:
        swing = "double"
    return replace(cand, swing=swing, leaf=(-uy * leaf.side, ux * leaf.side))


def _opening_candidates(
    segs: Sequence[_Seg],
    geoms: Geoms,
    detections: Sequence[DetectionPx],
    scaling: Scaling,
    dropped: Counter[str],
    chains: Mapping[int, tuple[int, ...]],
    page: PageRaster | None = None,
) -> list[_Cand]:
    """Bước 4: mỗi hộp ô mở → tường đầu tiên trong ứng viên của `_attach_walls` mà hộp nằm dọc (`_runs_along`),
    không có thì tường gần tâm nhất; không tường nào với tới → `openingUnattached`.

    Cung: xem `_placement` — cửa ban công cong rộng hơn một dây 10° không bị kẹp về dây hay rơi `openingTooWide`.
    `page` (trang + mặt nạ tường) cho cửa một cánh đọc bản lề/phía cánh từ nét vẽ (`_read_swing`).
    """
    chosen = [(order, det) for order, det in enumerate(detections) if det.label in _OPENING_LABELS]
    rects = [_rect(det.box, scaling) for _, det in chosen]
    cands: list[_Cand] = []
    for rect, (order, detection), walls in zip(rects, chosen, _attach_walls(segs, geoms, rects), strict=True):
        if not walls:
            dropped["openingUnattached"] += 1
            continue
        places = [_placement(segs, geoms, chains, rect, wall) for wall in walls]
        # Tường đầu tiên hộp nằm dọc; không có thì tường gần tâm nhất như trước (OPEN-ATTACH).
        host, wall, span, length = next((place for place in places if _runs_along(rect, place[2], place[3])), places[0])
        cand = _candidate(order, detection, host, segs[wall], span, dropped, length)
        if cand is not None:
            # Cung (ô mở đo trên cả cung): chưa đọc nét, giữ chiều mở theo nhãn.
            cands.append(cand if host != wall or wall in chains else _read_swing(cand, segs[wall], page, scaling))
    return cands


def _placement(
    segs: Sequence[_Seg],
    geoms: Geoms,
    chains: Mapping[int, tuple[int, ...]],
    rect: tuple[float, float, float, float],
    wall: int,
) -> tuple[int, int, tuple[float, float], float]:
    """`(tường chủ, tường gắn, hình chiếu, chiều dài)` của hộp trên `wall`; dây của cung → chiếu lên cả cung.

    Hộp gắn vào dây của một cung (`chains`) chiếu lên cả cung, ô mở đặt trên dây đầu với `offsetMm` tính từ đầu
    cung (WALLS-ARC NO-432).
    """
    chain = chains.get(wall)
    if chain is None:
        return wall, wall, _span_on_wall(rect, geoms[wall]), _length(segs[wall])
    line = shapely.linestrings(
        [[segs[chain[0]].start.x, segs[chain[0]].start.y]] + [[segs[k].end.x, segs[k].end.y] for k in chain]
    )
    return chain[0], wall, _span_on_wall(rect, line), float(line.length)


def _overlaps(a: _Cand, b: _Cand) -> bool:
    """Hai ô mở cùng tường có khoảng `[offset, offset + rộng]` chồng nhau."""
    return a.wall == b.wall and a.offset_mm < b.offset_mm + b.width_mm and b.offset_mm < a.offset_mm + a.width_mm


def _resolve_overlaps(cands: Sequence[_Cand], dropped: Counter[str]) -> list[_Cand]:
    """Chồng khoảng cùng tường → giữ `confidence` cao hơn (hoà: đứng trước), còn lại `openingOverlap`; rồi gộp mảnh."""
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
    return _merge_split(kept, dropped)


def _merge_split(cands: Sequence[_Cand], dropped: Counter[str]) -> list[_Cand]:
    """C4: ô mở cùng loại cùng tường cách ≤ `_SPLIT_GAP_MM` → một khoảng, lấy thuộc tính của mảnh `confidence` cao hơn.

    Mảnh bị nhập đếm `openingOverlap`. Cửa bản lề gộp lại rộng hơn `_MAX_SINGLE_LEAF_MM` thành hai cánh.
    """
    merged: list[_Cand] = []
    for cand in sorted(cands, key=lambda item: (item.wall, item.kind, item.offset_mm)):
        prev = merged[-1] if merged else None
        if prev is None or (prev.wall, prev.kind) != (cand.wall, cand.kind):
            merged.append(cand)
            continue
        end = max(prev.offset_mm + prev.width_mm, cand.offset_mm + cand.width_mm)
        if cand.offset_mm - (prev.offset_mm + prev.width_mm) > _SPLIT_GAP_MM:
            merged.append(cand)
            continue
        lead = prev if prev.confidence >= cand.confidence else cand
        width = end - prev.offset_mm
        hinged = lead.swing in ("left", "right")
        swing: SwingDirection = "double" if hinged and width > _MAX_SINGLE_LEAF_MM else lead.swing
        order = min(prev.order, cand.order)
        merged[-1] = replace(lead, order=order, offset_mm=prev.offset_mm, width_mm=width, swing=swing)
        dropped["openingOverlap"] += 1
    return sorted(merged, key=lambda item: item.order)


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
    arc_of: Sequence[int | None] = (),
    page: PageRaster | None = None,
) -> WallSet:
    """Bước 3 + 3b + 3c + 4: tường mm, nối khe ô mở, tường qua khe cửa, ô mở; không sửa đối số vào.

    Chỉ nhãn `door|double_door|window` thành ô mở, nhãn khác bỏ qua **không** đếm (đồ đạc là
    việc của `rooms.build_furniture`). `dropped` cộng dồn tại chỗ theo khoá `DROPPED_KEYS`. `arc_of` (từ
    `arcs.explode_arcs`) cho biết đầu vào nào là dây của cùng một cung để ô mở đo trên cả cung. `page` bật đọc
    chiều mở cửa từ nét vẽ (QT-SWING, `swing.py`).
    """
    segs = _drop_hairlines(_measure_walls(walls, scaling, dropped), dropped)
    segs = _drop_inside_body(_drop_far_clusters(_drop_isolated(segs, dropped), dropped), dropped)
    boxes = _opening_boxes(detections, scaling)
    bridges = _join_gaps(segs, boxes, dropped) if segs else ()
    live = [seg for seg in segs if seg.alive]
    live += _gap_walls(live, detections, scaling)
    input_to_wall = {index: position for position, seg in enumerate(live) for index in seg.inputs}
    geoms = _linestrings(live) if live else np.asarray([], dtype=object)
    chains = _arc_chains(live, arc_of)
    cands = _resolve_overlaps(_opening_candidates(live, geoms, detections, scaling, dropped, chains, page), dropped)
    live, cands = _drop_bare_gap_walls(live, cands)
    built_walls, openings = _assemble(live, cands, level_id, clock)
    leaves = {opening.id: cand.leaf for opening, cand in zip(openings, cands, strict=True) if cand.leaf is not None}
    return WallSet(built_walls, openings, input_to_wall, bridges, MappingProxyType(leaves))


def _centreline(wall: Wall) -> LineString:
    """Tim `Wall` thành `LineString` (mm)."""
    line = wall.centreline
    return LineString(((line.start.x, line.start.y), (line.end.x, line.end.y)))


def _bridge_hosts(walls: Sequence[Wall], ends: tuple[Point, Point]) -> list[Wall]:
    """Tường có đầu mút trùng một đầu của đoạn nối (đoạn nối nối đúng hai đầu gần của cặp thẳng hàng)."""
    return [wall for wall in walls if {wall.centreline.start, wall.centreline.end} & set(ends)]


def _gap_door(
    start: Point, end: Point, thickness_mm: int, page: PageRaster | None, scaling: Scaling
) -> tuple[SwingDirection, float, tuple[float, float] | None]:
    """Chiều mở + tin cậy + hướng cánh của cửa đoán trên khe `start → end` (C5), cùng luật C3 của `_read_swing`."""
    span = math.dist((start.x, start.y), (end.x, end.y))
    ux, uy = (end.x - start.x) / span, (end.y - start.y) / span
    scale = scaling.build
    leaf = None
    if page is not None:
        a, b = (start.x / scale, start.y / scale), (end.x / scale, end.y / scale)
        leaf = read_leaf(page, a, b, thickness_mm / 2 / scale)
    if leaf is not None:
        swing: SwingDirection = "right" if leaf.hinge_at_b else "left"
        swing = "double" if span > _MAX_SINGLE_LEAF_MM else swing
        return swing, _INFERRED_DOOR_CONFIDENCE, (-uy * leaf.side, ux * leaf.side)
    if span >= _SLIDING_MIN_MM:
        return "sliding", _INFERRED_DOOR_CONFIDENCE, None
    return "left", _GUESSED_DOOR_CONFIDENCE, None


def _extend_host(
    walls: list[Wall],
    openings: list[Opening],
    lines: list[LineString],
    hosts: Sequence[Wall],
    ends: tuple[Point, Point],
) -> None:
    """Khe tường ngoài < `_ENVELOPE_DOOR_MIN_MM`: kéo một tường chủ tới đầu kia của khe (gộp, không thêm tường vụn).

    Ưu tiên tường có **cuối** ở khe (độ lệch ô mở tính từ đầu không đổi); không có thì dời đầu của tường đầu tiên và
    cộng phần kéo thêm vào `offsetMm` các ô mở của nó.
    """
    at_end = next((host for host in hosts if host.centreline.end in ends), None)
    host = hosts[0] if at_end is None else at_end
    index = next(position for position, wall in enumerate(walls) if wall.id == host.id)
    line = walls[index].centreline
    tip = line.start if at_end is None else line.end
    target = ends[1] if tip == ends[0] else ends[0]
    if at_end is not None:
        walls[index] = walls[index].model_copy(update={"centreline": Segment(start=line.start, end=target)})
    else:
        walls[index] = walls[index].model_copy(update={"centreline": Segment(start=target, end=line.end)})
        shift = js_round(math.dist((target.x, target.y), (tip.x, tip.y)))
        openings[:] = [
            item.model_copy(update={"offset_mm": item.offset_mm + shift}) if item.wall_id == host.id else item
            for item in openings
        ]
    lines[index] = _centreline(walls[index])


def close_envelope_gaps(
    wall_set: WallSet,
    rooms: Sequence[Room],
    *,
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    page: PageRaster | None = None,
) -> WallSet:
    """C5: đoạn nối khe thẳng hàng nằm trên **mặt ngoài** các phòng → tường qua khe (không đầu vào) thay vì bỏ hở.

    Phòng đã khép qua đoạn nối nên lớp tường hở đúng chỗ bộ dò bỏ sót cửa. Khe ≥ `_ENVELOPE_DOOR_MIN_MM` thành
    tường mang một cửa đi phủ cả khe (cánh đọc từ nét vẽ, rộng ≥ 1,5 m không cánh → lùa, còn lại cánh trái tin
    thấp); khe hẹp hơn: kéo một tường chủ khép khe (`_extend_host`).
    Khe trong nhà (hai bên đều là phòng) giữ hở: lối mở thật có tồn tại.
    Đoạn nối cắt tim tường khác (khe đã có tường qua khe 3c, hay vách chắn ngang) bỏ qua.
    """
    walls, openings = list(wall_set.walls), list(wall_set.openings)
    leaves = dict(wall_set.leaves)
    lines = [_centreline(wall) for wall in walls]
    door = LABEL_TARGETS["door"]
    for start, end in wall_set.bridges:
        span = math.dist((start.x, start.y), (end.x, end.y))
        hosts = _bridge_hosts(wall_set.walls, (start, end))
        ux, uy = (end.x - start.x) / span, (end.y - start.y) / span
        inner = LineString(((start.x + ux, start.y + uy), (end.x - ux, end.y - uy)))
        if not hosts or any(inner.intersects(line) for line in lines):
            continue
        thickness = max(host.thickness_mm for host in hosts)
        wall = Wall(
            id=hosts[0].id,
            level_id=level_id,
            centreline=Segment(start=start, end=end),
            thickness_mm=thickness,
            detected_thickness_mm=thickness,
            height_mm=DEFAULT_WALL_HEIGHT_MM,
            kind="partition",
            opening_ids=(),
            confidence=min(host.confidence for host in hosts),
            source="ai",
            reviewed=False,
        )
        if wall_side(wall, rooms) != "exterior":
            continue
        if span < _ENVELOPE_DOOR_MIN_MM:
            _extend_host(walls, openings, lines, hosts, (start, end))
            continue
        wall_id = new_spatial_id("wall", clock)
        wall = wall.model_copy(update={"id": wall_id})
        swing, confidence, leaf = _gap_door(start, end, thickness, page, scaling)
        opening = Opening(
            id=new_spatial_id("opening", clock),
            wall_id=wall_id,
            kind="door",
            offset_mm=0,
            width_mm=math.floor(span),
            height_mm=door.height_mm or 2200,
            sill_height_mm=door.sill_mm or 0,
            swing=swing,
            confidence=confidence,
            source="ai",
            reviewed=False,
        )
        wall = wall.model_copy(update={"opening_ids": (opening.id,)})
        openings.append(opening)
        if leaf is not None:
            leaves[opening.id] = leaf
        walls.append(wall)
        lines.append(_centreline(wall))
    return replace(wall_set, walls=tuple(walls), openings=tuple(openings), leaves=MappingProxyType(leaves))


def _drop_bare_gap_walls(segs: Sequence[_Seg], cands: Sequence[_Cand]) -> tuple[list[_Seg], list[_Cand]]:
    """Bỏ tường qua khe (bước 3c, không đầu vào) không còn ô mở nào: ô mở rơi thì tường đó bịt lối (OPEN-ATTACH).

    Tường qua khe nằm cuối `segs` nên bỏ chúng không dời chỉ số tường có đầu vào (`input_to_wall` giữ nguyên);
    `wall` của ô mở đánh lại theo vị trí mới.
    """
    hosts = {cand.wall for cand in cands}
    kept = [index for index, seg in enumerate(segs) if seg.inputs or index in hosts]
    position = {old: new for new, old in enumerate(kept)}
    return [segs[index] for index in kept], [replace(cand, wall=position[cand.wall]) for cand in cands]
