"""Bản tham chiếu **quét hết / so mọi cặp** của luật và trộn, viết độc lập với mã có chỉ mục.

Chỉ dùng để đối chiếu: chậm có chủ ý (O(n·m)), viết thẳng theo chữ của B3-06 [6] từ
đầu, chỉ tái dùng nguyên hàm hình học đã có test riêng (`nearest_probe`, `outline_contains`,
`centroid`, `wall_side`).
"""

import math

from packages.domain.rules_ai.geometry import centroid, nearest_probe, outline_contains, wall_side
from packages.domain.rules_ai.merge import Removed
from packages.domain.rules_ai.orient import orient_furniture, world_box
from packages.domain.spatial import (
    BoundingBox,
    Furniture,
    Opening,
    Point,
    Roof,
    Room,
    Segment,
    SpatialLayer,
    Wall,
    js_round,
)

TOLERANCE = 50
CAP = 0.5
NO_REMOVALS = Removed()


def _can_edit(entity: Wall | Opening | Furniture) -> bool:
    """AI chưa duyệt."""
    return entity.source == "ai" and entity.reviewed is False


def _cap(entity: Wall | Opening | Furniture) -> dict[str, float]:
    """Cập nhật hạ tin cậy bằng `min`."""
    return {"confidence": min(entity.confidence, CAP)}


def ref_fixture(item: Furniture, walls: tuple[Wall, ...]) -> Furniture:
    """Luật 1 cho một đồ: quét mọi tường, tường đứng trước thắng khi hoà."""
    best = None
    for wall in walls:
        near = nearest_probe(world_box(item), wall)
        gap = max(0.0, near.distance - wall.thickness_mm / 2)
        if best is None or gap < best[0]:
            best = (gap, near)
    if best is None or not 50 < best[0] <= 300:
        return item
    gap, near = best
    dx = js_round((near.foot[0] - near.probe[0]) * gap / near.distance)
    dy = js_round((near.foot[1] - near.probe[1]) * gap / near.distance)
    box = item.bounding_box
    return item.model_copy(
        update={
            "centre": Point(x=item.centre.x + dx, y=item.centre.y + dy),
            "bounding_box": BoundingBox(
                min=Point(x=box.min.x + dx, y=box.min.y + dy), max=Point(x=box.max.x + dx, y=box.max.y + dy)
            ),
            **_cap(item),
        }
    )


def _ref_beside(op: Opening, host: Wall, rooms: tuple[Room, ...], reach: float | None = None) -> list[Room | None]:
    """Phòng đầu tiên chứa mỗi điểm dò hai bên tâm ô mở (nửa bề dày + 150 mm, hay `reach` từ tim), quét mọi phòng."""
    s, e = host.centreline.start, host.centreline.end
    length = math.dist((s.x, s.y), (e.x, e.y))
    ux, uy = (e.x - s.x) / length, (e.y - s.y) / length
    t = op.offset_mm + op.width_mm / 2
    reach = host.thickness_mm / 2 + 150 if reach is None else reach
    cx, cy = s.x + ux * t, s.y + uy * t
    points = ((cx - uy * reach, cy + ux * reach), (cx + uy * reach, cy - ux * reach))
    return [next((r for r in rooms if outline_contains(r.outline, x, y)), None) for x, y in points]


def _ref_sliding(op: Opening, host: Wall, layer: SpatialLayer) -> bool:
    """Cửa sổ ≥ 1400 trên tường thẳng giữa một phòng và lô gia chưa có cửa đi nối sang phòng khác, lô gia còn ở điểm
    cách tim tường 800 mm (hay xa hơn nếu tường dày)."""
    if op.width_mm < 1400 or host.curve_offset_mm:
        return False
    sides = _ref_beside(op, host, layer.rooms)
    if None in sides:
        return False
    entered = set()
    for door in layer.openings:
        wall = next((w for w in layer.walls if w.id == door.wall_id), None)
        if door.kind == "door" and wall is not None and not wall.curve_offset_mm:
            around = _ref_beside(door, wall, layer.rooms)
            if None not in around:
                entered |= {r.id for r in around if r is not None}
    deep = _ref_beside(op, host, layer.rooms, max(800, host.thickness_mm / 2 + 150))
    return any(
        r is not None and r.usage == "loggia" and r.id not in entered and d is r
        for r, d in zip(sides, deep, strict=True)
    )


def ref_apply_post_rules(layer: SpatialLayer) -> SpatialLayer:
    """Luật 1 rồi luật 2 (cửa lùa ra lô gia trước), quét mọi tường và mọi phòng (không chỉ mục)."""
    furniture = tuple(
        ref_fixture(item, layer.walls)
        if _can_edit(item) and item.kind in ("sanitaryFixture", "kitchenCabinet")
        else item
        for item in layer.furniture
    )
    promoted: set[str] = set()
    openings = []
    for op in layer.openings:
        host = next((w for w in layer.walls if w.id == op.wall_id), None)
        if op.kind != "window" or not _can_edit(op) or host is None or host.kind == "envelope":
            openings.append(op)
            continue
        if _ref_sliding(op, host, layer):
            door = {"kind": "door", "swing": "sliding", "height_mm": 2200, "sill_height_mm": 0}
            openings.append(op.model_copy(update={**door, **_cap(op)}))
            continue
        side = wall_side(host, layer.rooms)
        if side == "exterior" and _can_edit(host):
            promoted.add(host.id)
            openings.append(op)
        elif side == "unknown":
            openings.append(op)
        else:
            openings.append(op.model_copy(update=_cap(op)))
    walls = tuple(
        w.model_copy(update={"kind": "envelope", **_cap(w)}) if w.id in promoted and _can_edit(w) else w
        for w in layer.walls
    )
    walls = tuple(
        w.model_copy(update={"kind": "envelope"})
        if layer.rooms
        and w.kind == "partition"
        and _can_edit(w)
        and _can_edit(next(x for x in walls if x.id == w.id))
        and wall_side(w, layer.rooms) == "exterior"
        else w
        for w in walls
    )
    furniture = orient_furniture(furniture, lambda _box: layer.walls, _can_edit)
    return SpatialLayer(walls=walls, openings=tuple(openings), rooms=layer.rooms, furniture=furniture)


def _dist_ok(a: Point, b: Point) -> bool:
    """Cách nhau ≤ 50 mm (Euclid)."""
    return math.hypot(a.x - b.x, a.y - b.y) <= TOLERANCE


def _wall_match(a: Segment, k: Segment) -> bool:
    """Trùng đầu mút, cả hai chiều."""
    s, e, ks, ke = a.start, a.end, k.start, k.end
    return (_dist_ok(s, ks) and _dist_ok(e, ke)) or (_dist_ok(s, ke) and _dist_ok(e, ks))


def _room_match(a: tuple[Point, ...], k: tuple[Point, ...]) -> bool:
    """Tâm bên này trong đường bao bên kia (quét đầy đủ, không hộp bao)."""
    ca, ck = centroid(a), centroid(k)
    return outline_contains(k, *ca) or outline_contains(a, *ck)


def _furniture_match(a: Furniture, k: Furniture) -> bool:
    """Cùng kind, tâm AI trong hộp `K`."""
    box = k.bounding_box
    return a.kind == k.kind and box.min.x <= a.centre.x <= box.max.x and box.min.y <= a.centre.y <= box.max.y


def _refs(entity: Wall | Opening | Room | Furniture | Roof) -> list[str]:
    """Các id thực thể trỏ tới."""
    if isinstance(entity, Opening):
        return [entity.wall_id]
    if isinstance(entity, Wall):
        return list(entity.opening_ids)
    if isinstance(entity, Room):
        return list(entity.wall_ids)
    return [entity.room_id] if isinstance(entity, Furniture) and entity.room_id else []


def ref_keep(current: SpatialLayer) -> set[str]:
    """`K` bằng lặp tới điểm dừng, quét mọi thực thể mỗi vòng."""
    everything = current.entities()
    keep = {e.id for e in everything if e.reviewed or e.source == "human" or e.edited}
    changed = True
    while changed:
        changed = False
        for entity in everything:
            if entity.id in keep:
                for ref in _refs(entity):
                    if ref not in keep and any(o.id == ref for o in everything):
                        keep.add(ref)
                        changed = True
    return keep


def ref_merge(
    current: SpatialLayer, ai: SpatialLayer, removed: Removed = NO_REMOVALS
) -> tuple[SpatialLayer, tuple[str, ...], dict[str, str], tuple[str, ...]]:
    """Trộn theo chữ của [6] bước 2-7 và bia mộ H2, so mọi cặp.

    Trả `(layer, dropped_ai_ids, id_map, suppressed_ids)`.
    """
    keep = ref_keep(current)
    live = {e.id for e in current.entities()}
    gone_walls = [(i, seg) for i, seg in removed.walls if i not in live]
    gone_rooms = [(i, outline) for i, outline in removed.rooms if i not in live]
    suppressed: list[str] = []
    k_walls = [w for w in current.walls if w.id in keep]
    k_openings = [o for o in current.openings if o.id in keep]
    k_rooms = [r for r in current.rooms if r.id in keep]
    k_furniture = [f for f in current.furniture if f.id in keep]
    id_map: dict[str, str] = {}
    dropped: list[str] = []
    new_walls, new_rooms, new_furniture, new_openings = [], [], [], []
    for w in ai.walls:
        hit = next((k for k in k_walls if k.id == w.id), None) or next(
            (k for k in k_walls if _wall_match(w.centreline, k.centreline)), None
        )
        if hit:
            id_map[w.id] = hit.id
        elif any(i == w.id or _wall_match(w.centreline, seg) for i, seg in gone_walls):
            suppressed.append(w.id)
        else:
            new_walls.append(w)
    for o in ai.openings:
        if any(k.id == o.id for k in k_openings) or o.wall_id in id_map or o.wall_id in suppressed:
            dropped.append(o.id)
        else:
            new_openings.append(o)
    for r in ai.rooms:
        room_hit = next((k for k in k_rooms if k.id == r.id), None) or next(
            (k for k in k_rooms if _room_match(r.outline, k.outline)), None
        )
        if room_hit:
            id_map[r.id] = room_hit.id
        elif any(i == r.id or _room_match(r.outline, outline) for i, outline in gone_rooms):
            suppressed.append(r.id)
        else:
            new_rooms.append(r)
    for f in ai.furniture:
        if any(k.id == f.id or _furniture_match(f, k) for k in k_furniture):
            dropped.append(f.id)
        else:
            new_furniture.append(f)
    gone = set(dropped) | set(id_map) | set(suppressed)
    layer = SpatialLayer(
        walls=(
            *k_walls,
            *(
                w.model_copy(update={"opening_ids": tuple(i for i in w.opening_ids if i not in gone)})
                for w in new_walls
            ),
        ),
        openings=(*k_openings, *new_openings),
        rooms=(
            *k_rooms,
            *(
                r.model_copy(update={"wall_ids": tuple(id_map.get(i, i) for i in r.wall_ids if i not in suppressed)})
                for r in new_rooms
            ),
        ),
        furniture=(
            *k_furniture,
            *(
                f.model_copy(
                    update={
                        "room_id": None
                        if f.room_id in suppressed
                        else (id_map.get(f.room_id, f.room_id) if f.room_id else None)
                    }
                )
                for f in new_furniture
            ),
        ),
    )
    return (
        layer,
        tuple(e.id for e in ai.entities() if e.id in gone),
        id_map,
        tuple(e.id for e in ai.entities() if e.id in suppressed),
    )
