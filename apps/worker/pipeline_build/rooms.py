"""Phòng và đồ đạc từ tường đã dựng (B5-05 [6] bước 5, 6).

Toạ độ vào của `build_rooms`/`build_furniture` đã là mm (`Wall`, `bridges`) trừ hộp/chữ của
`build_furniture`/tên phòng vẫn còn px, đổi bằng `scaling`. Toàn hàm thuần, không sửa đối số.
"""

import math
from collections import Counter
from collections.abc import Sequence

import numpy as np
import shapely

from apps.worker.pipeline_build.constants import (
    MIN_ROOM_AREA_M2,
    ROOM_GAP_CLOSE_MIN_COS,
    ROOM_GAP_CLOSE_MM,
    ROOM_SNAP_MM,
)
from apps.worker.pipeline_build.geometry import Geoms, Scaling
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.core.clock import Clock
from packages.domain.rules_ai import LOW_CONFIDENCE_CAP
from packages.domain.spatial import BoundingBox, Furniture, Point, Room, Wall, js_round, polygon_area_m2
from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.ml_contracts.labels import LABEL_TARGETS
from packages.vision.dimensions.rooms import ROOM_USAGE_NAMES, RoomLabel, RoomUsage, match_room_label, name_rooms

_OPENING_LABELS = frozenset({"door", "double_door", "window"})
_SOFA_LONG_MM = 1400
_SOFA_SHORT_MM = (600, 1100)
_BED_SHORT_MM = (900, 2000)
_BED_LONG_MM = (1900, 2200)
"""U34: khung mm (cạnh ngắn, cạnh dài) để sửa nhãn YOLO `chair`/`other` theo kích thước thật."""
_NO_BED_USAGES = frozenset({"livingRoom", "kitchen", "bathroom", "corridor", "loggia"})
"""Phòng không đặt giường: bộ sofa + bàn trà ở phòng khách cũng cỡ giường (ch-13)."""
"""Nhãn ô mở: bỏ qua ở `build_furniture`, không đếm vào `dropped` (đã dựng ở bước 4)."""

_USAGE_PRIORITY: tuple[RoomUsage, ...] = (
    "other",
    "stairwell",
    "corridor",
    "utility",
    "loggia",
    "bathroom",
    "kitchen",
    "bedroom",
    "livingRoom",
)
"""Thứ tự tăng dần: công năng đứng sau thắng khi một phòng có nhiều nhãn (sảnh, kho, WC là phần phụ)."""

_DOOR_REACH_MM = 300.0
"""Khoảng lệch cho phép giữa hộp cửa và khe (cánh cửa vẽ cạnh tường, hộp không trùng tim tường)."""

_DOOR_SPAN_RATIO = (0.6, 1.8)
"""Khe cửa dài 0,6-1,8 lần cạnh dài hộp cửa (hộp chỉ ôm cánh, khe tính tới tim tường hai bên)."""

_PARALLEL_COS = 0.9
"""Tường gần song song khe (|cos| ≥ 0,9) bắn tia theo hướng ra của nó: đầu tường nằm trong hộp cửa sổ thì tâm hộp
có thể ở phía thân tường."""

_RIM_DEPTH_MM = 6000.0
"""Lô gia nằm trong 6 m tính từ biên bao: chỉ chia ô bằng đường trong dải đó."""

_RIM_M2 = (1.5, 15.0)
_RIM_FILL = 0.7
_RIM_WALLED = 0.5
"""Mảnh trống ở rìa thành lô gia khi 1,5-15 m², ≥ 70 % hộp bao, ≥ 3 cạnh hộp bao sát đường khép ≥ 50 %."""

_SEED_RAY_MM = 6000
"""Tia của phòng mọc từ nhãn dài nhất 6 m: xa hơn là chữ nằm ngoài căn hộ (tên bản vẽ, ghi chú)."""

_SEED_MAX_M2 = 40.0
"""Phòng mọc từ nhãn lớn hơn là hộp tràn qua chỗ thiếu tường, không dựng."""

_KITCHEN_RUN_MM = 2000
"""Dãy tủ bếp: cạnh dài hộp ≥ 2 m (bàn lavabo phòng tắm 0,6-1,2 m; bench: 1,5 m còn 2 phòng tắm thành bếp)."""

_BATHROOM_MAX_M2 = 10.0
"""Phòng có thiết bị vệ sinh mà rộng hơn là phòng ngủ có WC riêng hay bếp có chậu rửa, không phải phòng tắm."""

_BEDROOM_MIN_M2 = 6.0
_BEDROOM_MAX_M2 = 25.0
"""Tủ áo trong phòng 6-25 m² mới là phòng ngủ: nhỏ hơn là kho / phòng thay đồ, lớn hơn là phòng khách có kệ tủ.

Giường trong phòng ≥ 6 m² là phòng ngủ trước mọi luật khác: thiết bị vệ sinh dò nhầm (ghế, bàn học) không biến
phòng ngủ thành phòng tắm (H-08 ch-01: phòng ngủ 9,5 m² thành "phòng tắm 3")."""

_DINING_LABELS = frozenset({"table", "chair"})
"""Tủ bếp (kể cả ngắn) cùng bàn/ghế ăn trong phòng > 10 m² → bếp; tủ áo cạnh tủ bếp không làm phòng ngủ.

Dãy tủ đo ở tỉ lệ đoán (`project_default`) có thể ngắn hơn `_KITCHEN_RUN_MM`: H-08 ch-01 khu khách-bếp-ăn có
tủ bếp 2,1 m (1,8 m ở tỉ lệ đoán) và một kệ dò thành tủ áo nên thành "phòng ngủ"."""

_CLOSER_TRIM_MM = 1.0
"""Cắt bớt mỗi đầu đoạn nối khe khi xét cắt tường: chạm đúng đầu mút (chân chữ T) không tính là cắt."""


def _extend(wall: Wall, amount: float) -> shapely.LineString:
    """Đường tim `wall` kéo dài `amount` mm về mỗi đầu, theo hướng tường (bước 5)."""
    start, end = wall.centreline.start, wall.centreline.end
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    return shapely.LineString(
        [(start.x - ux * amount, start.y - uy * amount), (end.x + ux * amount, end.y + uy * amount)]
    )


def _gap_closers(walls: Sequence[Wall], bridges: Sequence[tuple[Point, Point]]) -> list[shapely.LineString]:
    """Đoạn nối khe góc/chữ T không có hộp ô mở (BUG-IT-008), để khép phòng; tường không đổi.

    Đầu tường tự do = không chạm tim tường khác hay `bridges` trong `ROOM_SNAP_MM`. Mỗi đầu tự do nối tới điểm gần nhất
    trên tim tường khác cách ≤ `ROOM_GAP_CLOSE_MM`, lệch hướng ra của đầu tường không quá `ROOM_GAP_CLOSE_MIN_COS`;
    bỏ đoạn cắt tim tường/`bridges` khác, giữ đoạn ngắn nhất. Tra theo
    lô bằng `STRtree` (không O(n²), trần B5-01 20 000 tường); đoạn chọn lố 1 mm qua tim đích để `unary_union` cắt nút.
    """
    if len(walls) < 2:
        return []
    starts = np.array([(w.centreline.start.x, w.centreline.start.y) for w in walls], dtype=float)
    ends = np.array([(w.centreline.end.x, w.centreline.end.y) for w in walls], dtype=float)
    centrelines: Geoms = np.asarray(shapely.linestrings(np.stack([starts, ends], axis=1)), dtype=object)
    bridge_lines = [shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges]
    obstacles: Geoms = np.asarray([*centrelines.tolist(), *bridge_lines], dtype=object)
    obstacle_tree = shapely.STRtree(obstacles)
    tips: Geoms = np.asarray(shapely.points(np.concatenate([starts, ends])), dtype=object)
    owner = np.tile(np.arange(len(walls)), 2)
    tip_idx, near = obstacle_tree.query(tips, predicate="dwithin", distance=ROOM_SNAP_MM)
    touching = np.zeros(len(tips), dtype=np.bool_)
    touching[tip_idx[near != owner[tip_idx]]] = True
    free = np.flatnonzero(~touching)
    free_idx, target = shapely.STRtree(centrelines).query(tips[free], predicate="dwithin", distance=ROOM_GAP_CLOSE_MM)
    tip = free[free_idx]
    other = target != owner[tip]
    tip, target = tip[other], target[other]
    if tip.size == 0:
        return []
    coords = shapely.get_coordinates(shapely.shortest_line(tips[tip], centrelines[target])).reshape(-1, 2, 2)
    head, foot = coords[:, 0], coords[:, 1]
    length = np.hypot(*(foot - head).T)
    unit = (foot - head) / length[:, None]
    trimmed: Geoms = np.asarray(
        shapely.linestrings(np.stack([head + unit * _CLOSER_TRIM_MM, foot - unit * _CLOSER_TRIM_MM], axis=1)),
        dtype=object,
    )
    seg_idx, blocker = obstacle_tree.query(trimmed, predicate="intersects")
    outward = np.concatenate([starts - ends, ends - starts])[tip]
    outward /= np.hypot(*outward.T)[:, None]
    blocked = np.einsum("ij,ij->i", unit, outward) < ROOM_GAP_CLOSE_MIN_COS
    blocked[seg_idx[blocker != target[seg_idx]]] = True
    valid = np.flatnonzero(~blocked)
    order = valid[np.lexsort((length[valid], tip[valid]))]
    _, first = np.unique(tip[order], return_index=True)
    chosen = order[first]
    tails = foot[chosen] + unit[chosen] * _CLOSER_TRIM_MM
    closers: Geoms = np.asarray(shapely.linestrings(np.stack([head[chosen], tails], axis=1)), dtype=object)
    return [shapely.LineString(line) for line in closers.tolist()]


def _outline_points(polygon: shapely.Polygon) -> list[Point]:
    """Vành ngoài của `polygon` thành điểm mm `js_round`, bỏ điểm trùng liên tiếp và điểm khép."""
    points = [Point(x=js_round(x), y=js_round(y)) for x, y in polygon.exterior.coords[:-1]]
    deduped: list[Point] = []
    for point in points:
        if not deduped or deduped[-1] != point:
            deduped.append(point)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def _door_closers(
    walls: Sequence[Wall], detections: Sequence[DetectionPx], scaling: Scaling
) -> list[shapely.LineString]:
    """Đoạn khép khe cửa đi và cửa sổ theo hộp dò được, kể cả khe giữa một góc tường và tường đối diện (đầu ở góc
    không là đầu tự do nên `_gap_closers` bỏ qua). Cửa sổ tính vì vách kính, cửa lô gia vẽ nét mảnh: model tường
    một lớp bỏ sót, phòng ngủ tràn ra lô gia (bench căn hộ ch-08).

    Mỗi ô mở: từ mọi đầu tường cách tâm hộp ≤ cạnh dài + `_DOOR_REACH_MM`, bắn tia dọc cạnh dài của hộp (về phía tâm,
    hay theo hướng ra của tường khi tường gần song song khe — `_PARALLEL_COS`) tới tim tường đầu tiên không chứa đầu
    đó. Giữ đoạn: dài `_DOOR_SPAN_RATIO` lần cạnh dài (cận dưới so với phần hộp còn phía trước đầu tường nằm trong
    hộp: hộp cửa sổ ôm cả mẩu tường đã dò); không nằm đè tường quá nửa; lệch ngang khỏi tâm hộp ≤
    min(`_DOOR_REACH_MM`, 1/4 cạnh dài) + nửa cạnh ngắn; đi qua gần tâm hộp (≤ nửa cạnh dài + `_DOOR_REACH_MM`).
    Lấy đoạn ngắn nhất. Hộp lệch tim tường vài chục mm (cánh cửa vẽ cạnh
    tường) vẫn khép được, việc mà phép phủ hộp của 3b không làm được.
    """
    openings = [d for d in detections if d.label in _OPENING_LABELS]
    if not openings or len(walls) < 2:
        return []
    centrelines = [
        shapely.LineString([(w.centreline.start.x, w.centreline.start.y), (w.centreline.end.x, w.centreline.end.y)])
        for w in walls
    ]
    tree = shapely.STRtree(centrelines)
    tips = [(w.centreline.start, w.centreline.end, i) for i, w in enumerate(walls)]
    tips += [(w.centreline.end, w.centreline.start, i) for i, w in enumerate(walls)]
    tip_points = shapely.STRtree([shapely.Point(p.x, p.y) for p, _, _ in tips])
    closers: list[shapely.LineString] = []
    for door in openings:
        low = scaling.point(door.box.x_min, door.box.y_min)
        high = scaling.point(door.box.x_max, door.box.y_max)
        width, height = high.x - low.x, high.y - low.y
        length, short = max(width, height), min(width, height)
        if length <= 0:
            continue
        axis = (1.0, 0.0) if width >= height else (0.0, 1.0)
        centre = shapely.Point((low.x + high.x) / 2, (low.y + high.y) / 2)
        best: shapely.LineString | None = None
        for slot in tip_points.query(centre.buffer(length + _DOOR_REACH_MM)):
            tip, base, owner = tips[int(slot)]
            run = math.hypot(tip.x - base.x, tip.y - base.y)
            along = ((tip.x - base.x) * axis[0] + (tip.y - base.y) * axis[1]) / run if run else 0.0
            if abs(along) >= _PARALLEL_COS:
                towards = 1.0 if along > 0 else -1.0
            else:
                towards = 1.0 if (centre.x - tip.x) * axis[0] + (centre.y - tip.y) * axis[1] >= 0 else -1.0
            far = (high.x if towards > 0 else low.x) if axis[0] else (high.y if towards > 0 else low.y)
            ahead = (far - (tip.x if axis[0] else tip.y)) * towards
            offset = abs((centre.y - tip.y) * axis[0] + (centre.x - tip.x) * axis[1])
            if ahead <= 0 or offset > min(_DOOR_REACH_MM, length / 4) + short / 2:
                continue
            gap = min(ahead, length)
            reach = length * _DOOR_SPAN_RATIO[1] + ROOM_SNAP_MM
            end = (tip.x + towards * axis[0] * reach, tip.y + towards * axis[1] * reach)
            ray = shapely.LineString([(tip.x, tip.y), end])
            origin = shapely.Point(tip.x, tip.y)
            hits = [
                origin.distance(ray.intersection(centrelines[int(i)]))
                for i in tree.query(ray, predicate="intersects")
                if int(i) != owner and centrelines[int(i)].distance(origin) > ROOM_SNAP_MM
            ]
            if not hits:
                continue
            span = min(hits)
            if not _DOOR_SPAN_RATIO[0] * gap <= span <= _DOOR_SPAN_RATIO[1] * length:
                continue
            foot = (tip.x + towards * axis[0] * (span + 1), tip.y + towards * axis[1] * (span + 1))
            segment = shapely.LineString([(tip.x, tip.y), foot])
            if segment.distance(centre) > length / 2 + _DOOR_REACH_MM:
                continue
            walled = shapely.union_all([centrelines[int(i)] for i in tree.query(segment.buffer(ROOM_SNAP_MM))])
            if segment.intersection(walled.buffer(ROOM_SNAP_MM)).length > segment.length / 2:
                continue
            if best is None or segment.length < best.length:
                best = segment
        if best is not None:
            closers.append(best)
    return closers


def _room_lines(
    walls: Sequence[Wall],
    bridges: Sequence[tuple[Point, Point]],
    detections: Sequence[DetectionPx] = (),
    scaling: Scaling | None = None,
) -> list[shapely.LineString]:
    """Mọi đường khép phòng: tường kéo dài `ROOM_SNAP_MM`, `bridges`, `_gap_closers` và `_door_closers`."""
    lines: list[shapely.LineString] = [_extend(wall, ROOM_SNAP_MM) for wall in walls]
    lines.extend(shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges)
    lines.extend(_gap_closers(walls, bridges))
    if scaling is not None:
        lines.extend(_door_closers(walls, detections, scaling))
    return lines


def _room_outlines(lines: Sequence[shapely.LineString]) -> list[list[Point]]:
    """Mọi vành ngoài khép được từ `lines` (`polygonize`)."""
    if not lines:
        return []
    merged = shapely.unary_union(lines)
    segments = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    polygons = shapely.polygonize(segments)
    return [_outline_points(polygon) for polygon in polygons.geoms]


def _seeded_outlines(
    lines: Sequence[shapely.LineString],
    rooms: Sequence[Sequence[Point]],
    labels: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[list[Point]]:
    """Phòng mọc từ nhãn chữ nằm ngoài mọi phòng đã khép (lô gia biên ngoài là lan can, không gian mở hở cửa).

    Bốn tia ngang/dọc từ tâm chữ tới đường khép gần nhất hay biên bao lồi của tường (thay lan can), dài ≤
    `_SEED_RAY_MM`; đủ bốn phía mới dựng hộp, trừ các phòng đã có, giữ mảnh chứa tâm chữ. Nhãn đã nằm trong một
    phòng (kể cả phòng vừa mọc) bị bỏ qua. Phòng và đường tra bằng `STRtree` (K18: 5 000 chữ x 20 000 tường).
    """
    seeds = [centre for label, centre in zip(labels, centres, strict=True) if label is not None]
    if not lines or not seeds:
        return []
    hull = shapely.convex_hull(shapely.MultiLineString(list(lines)))
    if not isinstance(hull, shapely.Polygon):
        return []
    obstacles = shapely.STRtree([*lines, hull.exterior])
    closed = [shapely.Polygon([(p.x, p.y) for p in outline]) for outline in rooms if len(outline) >= 3]
    closed_tree = shapely.STRtree(closed)
    grown: list[shapely.Polygon] = []
    seeded: list[list[Point]] = []
    for centre in seeds:
        point = shapely.Point(centre.x, centre.y)
        if (
            not hull.contains(point)
            or len(closed_tree.query(point, predicate="within"))
            or any(g.contains(point) for g in grown)
        ):
            continue
        reach: list[float] = []
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ray = shapely.LineString(
                [(centre.x, centre.y), (centre.x + dx * _SEED_RAY_MM, centre.y + dy * _SEED_RAY_MM)]
            )
            near = obstacles.query(ray, predicate="intersects")
            if len(near):
                reach.append(
                    float(min(shapely.distance(point, ray.intersection(obstacles.geometries[i])) for i in near))
                )
        if len(reach) < 4:
            continue
        left, right, up, down = reach
        box = shapely.box(centre.x - left, centre.y - up, centre.x + right, centre.y + down)
        blockers = [closed[i] for i in closed_tree.query(box, predicate="intersects")] + grown
        free = box.difference(shapely.unary_union(blockers)) if blockers else box
        parts = list(free.geoms) if hasattr(free, "geoms") else [free]
        piece = next((part for part in parts if isinstance(part, shapely.Polygon) and part.intersects(point)), None)
        if piece is None or piece.area / 1e6 > _SEED_MAX_M2:
            continue
        seeded.append(_outline_points(shapely.Polygon(piece.exterior)))
        grown.append(piece)
    return seeded


def _rim_outlines(lines: Sequence[shapely.LineString], rooms: Sequence[Sequence[Point]]) -> list[list[Point]]:
    """Lô gia không có nhãn: ô do đường khép và biên bao lồi của chúng chia ra (mặt ngoài lan can thay bằng biên bao),
    chưa thuộc phòng nào, chạm biên bao, rộng `_RIM_M2`, gần chữ nhật (≥ `_RIM_FILL` hộp bao) và ≥ 3 cạnh hộp bao có
    ≥ `_RIM_WALLED` sát đường khép (phần lồi của biên bao ngoài căn hộ chỉ sát tường một hai mặt).

    Chỉ chia ô bằng đường trong `_RIM_DEPTH_MM` quanh biên bao, tra phòng và đường bằng `STRtree` (K18: trần
    20 000 tường không được gộp toàn bộ).
    """
    if not lines:
        return []
    hull = shapely.convex_hull(shapely.MultiLineString(list(lines)))
    if not isinstance(hull, shapely.Polygon):
        return []
    line_tree = shapely.STRtree(list(lines))
    near_rim = [lines[int(i)] for i in line_tree.query(hull.exterior.buffer(_RIM_DEPTH_MM), predicate="intersects")]
    polygons = [shapely.Polygon([(p.x, p.y) for p in o]) for o in rooms if len(o) >= 3]
    room_tree = shapely.STRtree(polygons)
    rim = hull.exterior.buffer(ROOM_SNAP_MM)
    merged = shapely.unary_union([*near_rim, hull.exterior])
    faces = shapely.polygonize(list(merged.geoms) if hasattr(merged, "geoms") else [merged])
    found: list[list[Point]] = []
    for face in faces.geoms:
        if not isinstance(face, shapely.Polygon):
            continue
        if not _RIM_M2[0] <= face.area / 1e6 <= _RIM_M2[1] or not face.intersects(rim):
            continue
        overlap = sum(face.intersection(polygons[int(i)]).area for i in room_tree.query(face, predicate="intersects"))
        if overlap > 0.5 * face.area:
            continue
        x0, y0, x1, y1 = face.bounds
        if face.area < _RIM_FILL * (x1 - x0) * (y1 - y0):
            continue
        near = face.buffer(ROOM_SNAP_MM)
        walls = shapely.unary_union([lines[int(i)] for i in line_tree.query(near, predicate="intersects")])
        near_walls = walls.buffer(ROOM_SNAP_MM)
        sides = [
            shapely.LineString(side)
            for side in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)))
        ]
        if sum(side.intersection(near_walls).length >= _RIM_WALLED * side.length for side in sides) < 3:
            continue
        found.append(_outline_points(shapely.Polygon(face.exterior)))
    return found


def _wall_id_lists(walls: Sequence[Wall], outlines: Sequence[Sequence[Point]]) -> list[tuple[str, ...]]:
    """`wallIds` của mỗi `outline`: tường có trung điểm cách biên ≤ `ROOM_SNAP_MM`, thứ tự `walls`.

    Một `STRtree` trên trung điểm tường, tra theo lô bằng biên các phòng (K18: không O(n²)).
    """
    if not walls or not outlines:
        return [() for _ in outlines]
    midpoints = [
        shapely.Point(
            (wall.centreline.start.x + wall.centreline.end.x) / 2,
            (wall.centreline.start.y + wall.centreline.end.y) / 2,
        )
        for wall in walls
    ]
    tree = shapely.STRtree(midpoints)
    boundaries = [shapely.LinearRing([(p.x, p.y) for p in outline]) for outline in outlines]
    room_idx, wall_idx = tree.query(boundaries, predicate="dwithin", distance=ROOM_SNAP_MM)
    buckets: list[list[int]] = [[] for _ in outlines]
    for room, wall in zip(room_idx, wall_idx, strict=True):
        buckets[room].append(wall)
    return [tuple(walls[i].id for i in sorted(bucket)) for bucket in buckets]


def _text_centres(texts: Sequence[TextPx], scaling: Scaling) -> list[Point]:
    """Tâm hộp chữ đổi sang mm (`scaling.point`), cùng thứ tự `texts`."""
    return [scaling.point((t.box.x_min + t.box.x_max) / 2, (t.box.y_min + t.box.y_max) / 2) for t in texts]


def _room_labels(
    outlines: Sequence[Sequence[Point]],
    texts: Sequence[TextPx],
    parsed: Sequence[RoomLabel | None],
    centres: Sequence[Point],
) -> list[RoomLabel | None]:
    """Nhãn phòng của mỗi `outline` từ chữ trong biên có `match_room_label`.

    Nhiều nhãn trong một phòng (không gian mở "khách + bếp + sảnh", phòng ngủ có WC riêng) → công năng chính theo
    `_USAGE_PRIORITY`, rồi `confidence` cao nhất, hoà thì chữ đứng trước.
    """
    tree = shapely.STRtree([shapely.Polygon([(p.x, p.y) for p in outline]) for outline in outlines])
    best: list[tuple[tuple[int, float], RoomLabel] | None] = [None for _ in outlines]
    for text, label, centre in zip(texts, parsed, centres, strict=True):
        if label is None:
            continue
        key = (_USAGE_PRIORITY.index(label.usage), text.confidence)
        for room in tree.query(shapely.Point(centre.x, centre.y), predicate="within"):
            current = best[int(room)]
            if current is None or key > current[0]:
                best[int(room)] = (key, label)
    return [None if item is None else item[1] for item in best]


def _fixture_labels(
    outlines: Sequence[Sequence[Point]],
    areas_m2: Sequence[float],
    detections: Sequence[DetectionPx],
    scaling: Scaling,
) -> list[RoomLabel | None]:
    """Công năng suy từ đồ đạc dò được trong biên, cho phòng không có nhãn chữ (bản vẽ không ghi tên, chữ "WC" nhỏ
    OCR bỏ sót), theo thứ tự: giường và ≥ `_BEDROOM_MIN_M2` → phòng ngủ; dãy tủ bếp dài ≥ `_KITCHEN_RUN_MM` → bếp;
    thiết bị vệ sinh/buồng tắm đứng và ≤ `_BATHROOM_MAX_M2` → phòng tắm; máy giặt (không kèm thiết bị vệ sinh) và
    ≤ `_BATHROOM_MAX_M2` → lô-gia; tủ bếp + bàn/ghế ăn và > `_BATHROOM_MAX_M2` → bếp; tủ áo (không kèm tủ bếp) và
    `_BEDROOM_MIN_M2`-`_BEDROOM_MAX_M2` → phòng ngủ; không có gì → `None`.

    Tủ bếp ngắn không tính: model hay dò bàn lavabo phòng tắm thành `kitchen_cabinet` (bench căn hộ 27/10/2026).
    """
    found_in: list[set[str]] = [set() for _ in outlines]
    polygons = [shapely.Polygon([(p.x, p.y) for p in outline]) for outline in outlines]
    tree = shapely.STRtree(polygons)
    for d in detections:
        centre = scaling.point((d.box.x_min + d.box.x_max) / 2, (d.box.y_min + d.box.y_max) / 2)
        label: str = d.label
        if label == "kitchen_cabinet":
            long_side = scaling.mm(max(d.box.x_max - d.box.x_min, d.box.y_max - d.box.y_min))
            label = "kitchen_run" if long_side >= _KITCHEN_RUN_MM else label
        for room in tree.query(shapely.Point(centre.x, centre.y), predicate="within"):
            found_in[int(room)].add(label)
    labels: list[RoomLabel | None] = []
    for found, area_m2 in zip(found_in, areas_m2, strict=True):
        cabinet = bool(found & {"kitchen_cabinet", "kitchen_run"})
        if "bed" in found and area_m2 >= _BEDROOM_MIN_M2:
            usage: RoomUsage | None = "bedroom"
        elif "kitchen_run" in found:
            usage = "kitchen"
        elif found & {"sanitary_fixture", "shower"} and area_m2 <= _BATHROOM_MAX_M2:
            usage = "bathroom"
        elif "washing_machine" in found and area_m2 <= _BATHROOM_MAX_M2:
            usage = "loggia"
        elif cabinet and found & _DINING_LABELS and area_m2 > _BATHROOM_MAX_M2:
            usage = "kitchen"
        elif "wardrobe" in found and not cabinet and _BEDROOM_MIN_M2 <= area_m2 <= _BEDROOM_MAX_M2:
            usage = "bedroom"
        else:
            usage = None
        labels.append(None if usage is None else RoomLabel(usage, ROOM_USAGE_NAMES[usage]))
    return labels


def build_rooms(
    walls: Sequence[Wall],
    bridges: Sequence[tuple[Point, Point]],
    texts: Sequence[TextPx],
    *,
    detections: Sequence[DetectionPx] = (),
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
) -> tuple[Room, ...]:
    """Phòng từ khép kín của tường + `bridges` + đoạn nối khe `_gap_closers` (B5-05 [6] bước 5, lệch BUG-IT-008).

    Tên: nhãn chữ trong phòng, không có thì suy từ đồ đạc (`_fixture_labels`). Mảnh dưới `MIN_ROOM_AREA_M2` →
    `roomTooSmall`. Cạnh phòng khép bằng đoạn nối khe không có tường thật, nên luật FE
    `ROOM-NOT-CLOSED` vẫn gắn cờ nó — đúng, vì tường ở đó thật sự thiếu.
    """
    parsed = [match_room_label(text.text) for text in texts]
    centres = _text_centres(texts, scaling)
    lines = _room_lines(walls, bridges, detections, scaling)
    closed = _room_outlines(lines)
    seeded = _seeded_outlines(lines, closed, parsed, centres)
    rims = _rim_outlines(lines, [*closed, *seeded])
    rim_keys = {tuple(outline) for outline in rims}
    kept: list[tuple[list[Point], float]] = []
    for outline in [*closed, *seeded, *rims]:
        area_m2 = float(polygon_area_m2(outline)) if len(outline) >= 3 else 0.0
        if len(outline) < 3 or area_m2 < MIN_ROOM_AREA_M2:
            dropped["roomTooSmall"] += 1
            continue
        kept.append((outline, area_m2))
    kept.sort(key=lambda item: (min(p.y for p in item[0]), min(p.x for p in item[0])))
    outlines = [outline for outline, _ in kept]
    wall_ids = _wall_id_lists(walls, outlines)
    wall_by_id = {wall.id: wall for wall in walls}
    from_text = _room_labels(outlines, texts, parsed, centres)
    from_fixtures = _fixture_labels(outlines, [area for _, area in kept], detections, scaling)
    loggia = RoomLabel("loggia", ROOM_USAGE_NAMES["loggia"])
    from_rim = [loggia if tuple(outline) in rim_keys else None for outline in outlines]
    labels = name_rooms(
        [text or rim or fixture for text, rim, fixture in zip(from_text, from_rim, from_fixtures, strict=True)]
    )
    rooms = []
    for (outline, area_m2), ids, label in zip(kept, wall_ids, labels, strict=True):
        confidences = [wall_by_id[i].confidence for i in ids]
        rooms.append(
            Room(
                id=new_spatial_id("room", clock),
                level_id=level_id,
                name=label.name,
                usage=label.usage,
                outline=tuple(outline),
                area_m2=area_m2,
                wall_ids=ids,
                confidence=min(confidences) if confidences else LOW_CONFIDENCE_CAP,
                source="ai",
                reviewed=False,
            )
        )
    return tuple(rooms)


def _first_room_id(tree: shapely.STRtree, rooms: Sequence[Room], centre: Point) -> str | None:
    """Id phòng đầu tiên (thứ tự `rooms`) chứa `centre`, hoặc `None`."""
    candidates = tree.query(shapely.Point(centre.x, centre.y), predicate="within")
    if len(candidates) == 0:
        return None
    return rooms[int(min(candidates))].id


def build_furniture(
    detections: Sequence[DetectionPx],
    rooms: Sequence[Room],
    *,
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
    scale_trusted: bool = True,
) -> tuple[Furniture, ...]:
    """Đồ đạc từ phát hiện (B5-05 [6] bước 6); ô mở bỏ qua không đếm, nhãn lạ → `unknownLabel`.

    Nhãn `chair`/`other` được sửa theo kích thước mm ở tỉ lệ `final` (`relabel_by_size`, U34); tỉ lệ
    chưa tin (`scale_trusted=False`) thì vẫn sửa nhưng hạ `confidence` về `LOW_CONFIDENCE_CAP`.
    """
    tree = shapely.STRtree([shapely.Polygon([(p.x, p.y) for p in room.outline]) for room in rooms]) if rooms else None
    items = []
    for detection in detections:
        if detection.label in _OPENING_LABELS:
            continue
        target = LABEL_TARGETS.get(detection.label)
        if target is None or target.category != "furniture":
            dropped["unknownLabel"] += 1
            continue
        box_min = scaling.point(detection.box.x_min, detection.box.y_min)
        box_max = scaling.point(detection.box.x_max, detection.box.y_max)
        if box_max.x - box_min.x == 0 or box_max.y - box_min.y == 0:
            dropped["furnitureEmpty"] += 1
            continue
        centre = Point(x=js_round((box_min.x + box_max.x) / 2), y=js_round((box_min.y + box_max.y) / 2))
        room_id = _first_room_id(tree, rooms, centre) if tree is not None else None
        box = detection.box
        kind, variant = relabel_by_size(
            target.domain_kind,
            (box.x_max - box.x_min) * scaling.final,
            (box.y_max - box.y_min) * scaling.final,
            room_usage=next((room.usage for room in rooms if room.id == room_id), None),
        )
        confidence = detection.confidence
        if variant is not None and not scale_trusted:
            confidence = min(confidence, LOW_CONFIDENCE_CAP)
        items.append(
            Furniture(
                id=new_spatial_id("furniture", clock),
                level_id=level_id,
                room_id=room_id,
                kind=kind,
                variant=variant,
                centre=centre,
                bounding_box=BoundingBox(min=box_min, max=box_max),
                rotation_deg=0.0,
                confidence=confidence,
                source="ai",
                reviewed=False,
            )
        )
    return tuple(items)


def relabel_by_size(
    kind: str, width_mm: float, height_mm: float, *, room_usage: str | None = None
) -> tuple[str, str | None]:
    """`(kind, variant)` sau khi xét kích thước thật (U34); không đổi thì `variant=None`.

    `chair`/`other` cỡ giường (ngắn 900-2000, dài 1900-2200) → `bed`; `chair` dài ≥ 1400, ngắn
    600-1100 → `chair` + `variant="sofa"` (hợp đồng không có `kind` sofa; thư viện xếp sofa vào nhóm ghế).
    Xét giường trước: món 1043 x 2075 mm khớp cả hai khung; không thành giường trong phòng
    `_NO_BED_USAGES`. Nhãn khác (bàn, tủ bếp…) giữ nguyên.
    """
    short, long = sorted((width_mm, height_mm))
    bed_sized = _BED_SHORT_MM[0] <= short <= _BED_SHORT_MM[1] and _BED_LONG_MM[0] <= long <= _BED_LONG_MM[1]
    if bed_sized and kind in ("chair", "other") and room_usage not in _NO_BED_USAGES:
        return "bed", "bed"
    if kind == "chair" and long >= _SOFA_LONG_MM and _SOFA_SHORT_MM[0] <= short <= _SOFA_SHORT_MM[1]:
        return "chair", "sofa"
    return kind, None
