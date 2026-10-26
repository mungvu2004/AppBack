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
"""Tủ áo trong phòng 6-25 m² mới là phòng ngủ: nhỏ hơn là kho / phòng thay đồ, lớn hơn là phòng khách có kệ tủ."""

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


def _room_lines(walls: Sequence[Wall], bridges: Sequence[tuple[Point, Point]]) -> list[shapely.LineString]:
    """Mọi đường khép phòng: tường kéo dài `ROOM_SNAP_MM`, `bridges` và `_gap_closers`."""
    lines: list[shapely.LineString] = [_extend(wall, ROOM_SNAP_MM) for wall in walls]
    lines.extend(shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges)
    lines.extend(_gap_closers(walls, bridges))
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
    OCR bỏ sót), theo thứ tự: dãy tủ bếp dài ≥ `_KITCHEN_RUN_MM` → bếp; thiết bị vệ sinh và ≤ `_BATHROOM_MAX_M2` →
    phòng tắm; tủ áo và `_BEDROOM_MIN_M2`-`_BEDROOM_MAX_M2` → phòng ngủ; không có gì → `None`.

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
        if "kitchen_run" in found:
            usage: RoomUsage | None = "kitchen"
        elif "sanitary_fixture" in found and area_m2 <= _BATHROOM_MAX_M2:
            usage = "bathroom"
        elif "wardrobe" in found and _BEDROOM_MIN_M2 <= area_m2 <= _BEDROOM_MAX_M2:
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
    lines = _room_lines(walls, bridges)
    closed = _room_outlines(lines)
    seeded = _seeded_outlines(lines, closed, parsed, centres)
    kept: list[tuple[list[Point], float]] = []
    for outline in [*closed, *seeded]:
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
    labels = name_rooms([text or fixture for text, fixture in zip(from_text, from_fixtures, strict=True)])
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
) -> tuple[Furniture, ...]:
    """Đồ đạc từ phát hiện (B5-05 [6] bước 6); ô mở bỏ qua không đếm, nhãn lạ → `unknownLabel`."""
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
        items.append(
            Furniture(
                id=new_spatial_id("furniture", clock),
                level_id=level_id,
                room_id=_first_room_id(tree, rooms, centre) if tree is not None else None,
                kind=target.domain_kind,
                centre=centre,
                bounding_box=BoundingBox(min=box_min, max=box_max),
                rotation_deg=0.0,
                confidence=detection.confidence,
                source="ai",
                reviewed=False,
            )
        )
    return tuple(items)
