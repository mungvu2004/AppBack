"""Luật 4 — hướng đồ: gương `orientDetected.ts` của FE, cộng luật chọn cạnh tựa khi hai trục đều có tường.

YOLO chỉ cho hộp thẳng trục nên bước dựng đặt `rotation_deg = 0` cho mọi món. Quy ước K1: mặt
trước là +y riêng, 0° nhìn xuống trang (S), 90° → W, 180° → N, 270° → E. `bounding_box` là khung
riêng chưa xoay, nên quay 90°/270° thì hoán hai cạnh quanh tâm để hộp thế giới vẫn phủ đúng chỗ.

Chỉ đụng đồ AI chưa duyệt còn 0°. Ghế quay vào bàn (rồi quầy `kitchenCabinet`) gần nhất trong
900 mm; không có thì như đồ tựa tường. Đồ tựa tường quay lưng về mặt tường thẳng trục gần nhất
trong 600 mm; khi cả hai trục đều có tường: giường, bồn cầu tựa cạnh ngắn; dãy tủ, tủ áo, kệ TV,
lavabo, sofa tựa cạnh dài; còn lại lấy tường gần hơn. Không có tường gần thì giữ 0°.
"""

from collections.abc import Callable, Sequence
from typing import Final

from packages.domain.spatial import BoundingBox, Furniture, Point, Wall

SEAT_TO_TABLE_MM: Final = 900
"""Khe tối đa từ ghế tới mép bàn/quầy: `SEAT_TO_TABLE_MM`, `orientDetected.ts`."""

BACK_TO_WALL_MM: Final = 600
"""Khe tối đa từ lưng món tới mặt tường: `BACK_TO_WALL_MM`, `orientDetected.ts`."""

AXIS_TOLERANCE: Final = 0.18
"""Tường lệch trục quá chừng này (tan ≈ 10°) thì bỏ qua: `AXIS_TOLERANCE`, `orientDetected.ts`."""

_HUGGING_KINDS: Final = frozenset({"bed", "wardrobe", "sanitaryFixture", "washingMachine", "kitchenCabinet"})
_HUGGING_VARIANTS: Final = frozenset({"tv", "fridge", "shelves", "cabinet", "sofa"})
_SHORT_SIDE: Final = frozenset({"bed", "wc"})
"""Đầu giường, két nước bồn cầu nằm ở cạnh ngắn."""
_LONG_SIDE: Final = frozenset({"kitchenCabinet", "wardrobe", "tv", "basin", "sofa", "shelves", "cabinet"})
"""Dãy tủ, tủ áo, kệ TV, lavabo, sofa dựa lưng bằng cạnh dài."""

Facing = tuple[int, int]
"""Hướng mặt trước, đơn vị theo trục: `(0, 1)` là S."""

_DEG: Final[dict[Facing, float]] = {(0, 1): 0.0, (-1, 0): 90.0, (0, -1): 180.0, (1, 0): 270.0}
"""`furnitureFacingDeg` (placement.ts) trên bốn hướng trục."""


def world_box(item: Furniture) -> BoundingBox:
    """Hộp thế giới: khung riêng quay 90°/270° thì hoán hai cạnh quanh tâm, còn lại giữ nguyên."""
    box = item.bounding_box
    if item.rotation_deg % 180 != 90:
        return box
    return _swapped(box)


def _swapped(box: BoundingBox) -> BoundingBox:
    """Hộp cùng tâm (lệch ≤ 1 mm khi cạnh lẻ, toạ độ là số nguyên), hai cạnh hoán đổi."""
    width, depth = box.max.x - box.min.x, box.max.y - box.min.y
    x0 = (box.min.x + box.max.x - depth) // 2
    y0 = (box.min.y + box.max.y - width) // 2
    return BoundingBox(min=Point(x=x0, y=y0), max=Point(x=x0 + depth, y=y0 + width))


def _gap(a: BoundingBox, b: BoundingBox) -> float:
    """Khe Euclid giữa hai hộp, 0 khi chồng."""
    gx = max(0.0, b.min.x - a.max.x, a.min.x - b.max.x)
    gy = max(0.0, b.min.y - a.max.y, a.min.y - b.max.y)
    return float((gx * gx + gy * gy) ** 0.5)


def _toward_table(seat: BoundingBox, table: BoundingBox) -> Facing:
    """Hướng ghế nhìn vào bàn: theo cạnh bàn mà ghế đứng ngoài xa hơn (như FE)."""
    dx = (seat.min.x + seat.max.x - table.min.x - table.max.x) / 2
    dy = (seat.min.y + seat.max.y - table.min.y - table.max.y) / 2
    out_x = abs(dx) - (table.max.x - table.min.x) / 2
    out_y = abs(dy) - (table.max.y - table.min.y) / 2
    if out_x > out_y:
        return (-1 if dx > 0 else 1), 0
    return 0, (-1 if dy > 0 else 1)


def _nearest_target(seat: Furniture, targets: Sequence[Furniture]) -> Furniture | None:
    """Bàn/quầy cùng tầng gần ghế nhất trong 900 mm; hoà thì món sau thắng (như FE `<=`)."""
    best: Furniture | None = None
    best_gap = float(SEAT_TO_TABLE_MM)
    box = world_box(seat)
    for target in targets:
        if target.level_id != seat.level_id:
            continue
        gap = _gap(box, world_box(target))
        if gap <= best_gap:
            best, best_gap = target, gap
    return best


def _wall_facings(box: BoundingBox, walls: Sequence[Wall]) -> tuple[tuple[float, Facing] | None, ...]:
    """Tường ngang gần nhất và tường dọc gần nhất trong 600 mm: `(khe, hướng vào phòng)` cho mỗi trục.

    Gương `intoRoomFromWall` của FE nhưng giữ riêng từng trục để chọn cạnh tựa.
    """
    # ponytail: chỉ tường thẳng gần thẳng trục, tường xiên/cong bị bỏ qua như FE.
    best: list[tuple[float, Facing] | None] = [None, None]
    mx, my = (box.min.x + box.max.x) / 2, (box.min.y + box.max.y) / 2
    for wall in walls:
        if wall.curve_offset_mm:
            continue
        start, end = wall.centreline.start, wall.centreline.end
        dx, dy = end.x - start.x, end.y - start.y
        horizontal = abs(dy) <= abs(dx) * AXIS_TOLERANCE
        if not horizontal and abs(dx) > abs(dy) * AXIS_TOLERANCE:
            continue
        if horizontal:
            u0, u1, v0, v1, vm = box.min.x, box.max.x, box.min.y, box.max.y, my
            a0, a1, at = min(start.x, end.x), max(start.x, end.x), (start.y + end.y) / 2
        else:
            u0, u1, v0, v1, vm = box.min.y, box.max.y, box.min.x, box.max.x, mx
            a0, a1, at = min(start.y, end.y), max(start.y, end.y), (start.x + end.x) / 2
        if min(u1, a1) - max(u0, a0) <= 0:
            continue
        after = at > vm
        half = wall.thickness_mm / 2
        gap = at - half - v1 if after else v0 - (at + half)
        slot = 0 if horizontal else 1
        current = best[slot]
        if gap > BACK_TO_WALL_MM or gap < -(v1 - v0) / 2 or (current is not None and gap > current[0]):
            continue
        sign = -1 if after else 1
        best[slot] = gap, ((0, sign) if horizontal else (sign, 0))
    return tuple(best)


def _back_to_wall(item: Furniture, box: BoundingBox, walls: Sequence[Wall]) -> Facing | None:
    """Hướng mặt trước khi lưng tựa tường; `None` khi không có tường thẳng trục trong 600 mm."""
    horizontal, vertical = _wall_facings(box, walls)
    if horizontal is None or vertical is None:
        found = horizontal or vertical
        return None if found is None else found[1]
    role = item.variant if item.variant in _SHORT_SIDE | _LONG_SIDE else item.kind
    width, depth = box.max.x - box.min.x, box.max.y - box.min.y
    if role in _SHORT_SIDE | _LONG_SIDE and width != depth:
        # Hộp hẹp theo x thì cạnh ngắn nằm ngang, song song tường ngang.
        want_horizontal = (width < depth) == (role in _SHORT_SIDE)
        return horizontal[1] if want_horizontal else vertical[1]
    return horizontal[1] if horizontal[0] <= vertical[0] else vertical[1]


def _turned(item: Furniture, facing: Facing) -> Furniture:
    """Món quay về `facing`; 0° thì trả nguyên món, 90°/270° hoán hai cạnh hộp."""
    rotation = _DEG[facing]
    if rotation == 0:
        return item
    box = _swapped(item.bounding_box) if rotation in (90.0, 270.0) else item.bounding_box
    return item.model_copy(update={"rotation_deg": rotation, "bounding_box": box})


def orient_furniture(
    furniture: Sequence[Furniture],
    walls_near: Callable[[BoundingBox], Sequence[Wall]],
    editable: Callable[[Furniture], bool],
) -> tuple[Furniture, ...]:
    """Luật 4 cho cả danh sách; cùng thứ tự, cùng id, chỉ `rotation_deg` (và hộp riêng) đổi.

    `walls_near(box)` trả các tường (cùng tầng hay không, lọc ở đây) có thể trong 600 mm của hộp.
    Ghế tìm bàn/quầy theo hộp thế giới nên lượt hai cho cùng quyết định (idempotent).
    """
    tables = [f for f in furniture if f.kind == "table"]
    bars = [f for f in furniture if f.kind == "kitchenCabinet"]
    result: list[Furniture] = []
    for item in furniture:
        if not editable(item) or item.rotation_deg != 0:
            result.append(item)
            continue
        box = item.bounding_box
        walls = [w for w in walls_near(box) if w.level_id == item.level_id]
        facing: Facing | None = None
        if item.kind == "chair" and item.variant != "sofa":
            target = _nearest_target(item, tables) or _nearest_target(item, bars)
            facing = _back_to_wall(item, box, walls) if target is None else _toward_table(box, world_box(target))
        elif item.kind in _HUGGING_KINDS or item.variant in _HUGGING_VARIANTS:
            facing = _back_to_wall(item, box, walls)
        result.append(item if facing is None else _turned(item, facing))
    return tuple(result)
