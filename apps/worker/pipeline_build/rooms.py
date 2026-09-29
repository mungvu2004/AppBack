"""Phòng và đồ đạc từ tường đã dựng (B5-05 [6] bước 5, 6).

Toạ độ vào của `build_rooms`/`build_furniture` đã là mm (`Wall`, `bridges`) trừ hộp/chữ của
`build_furniture`/tên phòng vẫn còn px, đổi bằng `scaling`. Toàn hàm thuần, không sửa đối số.
"""

import math
from collections import Counter
from collections.abc import Sequence

import shapely

from apps.worker.pipeline_build.constants import MIN_ROOM_AREA_M2, ROOM_SNAP_MM
from apps.worker.pipeline_build.geometry import Scaling
from apps.worker.pipeline_build.ids import new_spatial_id
from packages.core.clock import Clock
from packages.domain.rules_ai import LOW_CONFIDENCE_CAP, outline_contains
from packages.domain.spatial import BoundingBox, Furniture, Point, Room, Wall, js_round, polygon_area_m2
from packages.ml_contracts.artifacts import DetectionPx, TextPx
from packages.ml_contracts.labels import LABEL_TARGETS
from packages.vision.dimensions.rooms import RoomLabel, match_room_label, name_rooms

_OPENING_LABELS = frozenset({"door", "double_door", "window"})
"""Nhãn ô mở: bỏ qua ở `build_furniture`, không đếm vào `dropped` (đã dựng ở bước 4)."""


def _extend(wall: Wall, amount: float) -> shapely.LineString:
    """Đường tim `wall` kéo dài `amount` mm về mỗi đầu, theo hướng tường (bước 5)."""
    start, end = wall.centreline.start, wall.centreline.end
    dx, dy = end.x - start.x, end.y - start.y
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    return shapely.LineString(
        [(start.x - ux * amount, start.y - uy * amount), (end.x + ux * amount, end.y + uy * amount)]
    )


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


def _room_outlines(walls: Sequence[Wall], bridges: Sequence[tuple[Point, Point]]) -> list[list[Point]]:
    """Mọi vành ngoài khép được từ tường kéo dài `ROOM_SNAP_MM` + `bridges` (`unary_union`, `polygonize`)."""
    lines: list[shapely.LineString] = [_extend(wall, ROOM_SNAP_MM) for wall in walls]
    lines.extend(shapely.LineString([(a.x, a.y), (b.x, b.y)]) for a, b in bridges)
    if not lines:
        return []
    merged = shapely.unary_union(lines)
    segments = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    polygons = shapely.polygonize(segments)
    return [_outline_points(polygon) for polygon in polygons.geoms]


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
    outlines: Sequence[Sequence[Point]], texts: Sequence[TextPx], centres: Sequence[Point]
) -> list[RoomLabel | None]:
    """Nhãn phòng của mỗi `outline`: chữ trong biên có `match_room_label`, `confidence` cao nhất, hoà đứng trước."""
    parsed = [match_room_label(text.text) for text in texts]
    labels: list[RoomLabel | None] = []
    for outline in outlines:
        best: RoomLabel | None = None
        best_confidence = -1.0
        for text, label, centre in zip(texts, parsed, centres, strict=True):
            if label is None or not outline_contains(outline, centre.x, centre.y):
                continue
            if text.confidence > best_confidence:
                best, best_confidence = label, text.confidence
        labels.append(best)
    return labels


def build_rooms(
    walls: Sequence[Wall],
    bridges: Sequence[tuple[Point, Point]],
    texts: Sequence[TextPx],
    *,
    level_id: str,
    scaling: Scaling,
    clock: Clock,
    dropped: Counter[str],
) -> tuple[Room, ...]:
    """Phòng từ khép kín của tường + `bridges` (B5-05 [6] bước 5); mảnh dưới `MIN_ROOM_AREA_M2` → `roomTooSmall`."""
    kept: list[tuple[list[Point], float]] = []
    for outline in _room_outlines(walls, bridges):
        area_m2 = float(polygon_area_m2(outline)) if len(outline) >= 3 else 0.0
        if len(outline) < 3 or area_m2 < MIN_ROOM_AREA_M2:
            dropped["roomTooSmall"] += 1
            continue
        kept.append((outline, area_m2))
    kept.sort(key=lambda item: (min(p.y for p in item[0]), min(p.x for p in item[0])))
    outlines = [outline for outline, _ in kept]
    wall_ids = _wall_id_lists(walls, outlines)
    wall_by_id = {wall.id: wall for wall in walls}
    labels = name_rooms(_room_labels(outlines, texts, _text_centres(texts, scaling)))
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
