"""Lọc đồ trùng sau luật hậu xử lý (BENCH3D-26): một vật bị nhận hai lần, hoặc hai hộp khác loại đè nhau.

Chạy một chỗ trong `build._attempt`, sau `apply_post_rules` (hộp đã bắt tường, đã quay; so bằng `world_box`). Chỉ xét
đồ AI chưa duyệt (K21): thảm người đặt dưới giường AI không phải trùng. Đo bằng hai tỉ lệ vì chúng trả lời hai câu khác:

- IoU (giao / hợp): hai hộp cỡ gần nhau phủ cùng một chỗ, tức là cùng một vật.
- IoM (giao / hộp nhỏ hơn): hộp nhỏ nằm gọn trong hộp lớn. Một mình nó **không** nói là trùng: đèn trên bàn, gối trên
  giường, ghế kê dưới bàn đều có IoM 1 và IoU rất nhỏ. Vì vậy IoM chỉ có hiệu lực với cặp không thể chồng thật: cùng
  loại (trừ `other`, nhóm hỗn tạp), hoặc cả hai đều đặt cố định trên sàn (`_FLOOR_FIXED`: bồn cầu trên giường).

Bỏ món nào: đồ thật hơn gợi ý; cùng một chỗ (IoU đạt ngưỡng) → đúng công năng phòng, rồi độ tin; lồng nhau (IoU dưới
ngưỡng) → bỏ hộp nhỏ, không xét độ tin vì mất hộp lớn là mất món thật (vòi độ tin 0,64 trong bồn tắm 0,37; chậu trong
dãy tủ), trừ khi chỉ hộp nhỏ đúng công năng phòng (chậu lavabo trong hộp "tủ bếp" ở phòng tắm).

Đồ ngoài khối nhà không xử lý ở đây: `rooms.build_furniture` đã gắn `suggested` (không xoá vì chưa chắc phòng đã đủ).
"""

from collections.abc import Mapping, Sequence
from typing import Final

import shapely

from packages.domain.rules_ai.orient import world_box
from packages.domain.spatial import Furniture, SpatialLayer

__all__ = ["dedupe_furniture", "find_duplicates"]

SAME_KIND_IOU: Final = 0.5
"""Cùng loại, IoU từ đây: cùng một vật bị nhận hai lần."""
SAME_KIND_NESTED_IOM: Final = 0.8
"""Cùng loại (trừ `other`), hộp nhỏ nằm ≥ ngần này trong hộp lớn: hai bồn tắm lồng nhau không có thật."""
CROSS_KIND_IOU: Final = 0.6
"""Khác loại, IoU từ đây: cùng một chỗ bị gán hai nhãn. Thấp hơn thì tủ lạnh `other` trong dãy tủ bếp ngắn cũng dính."""
FIXED_NESTED_IOM: Final = 0.8
"""Khác loại, cả hai thuộc `_FLOOR_FIXED`, hộp nhỏ nằm ≥ ngần này trong hộp lớn: gối nhận thành bồn cầu trên giường."""

_FLOOR_FIXED: Final = frozenset({"sanitaryFixture", "shower", "washingMachine", "kitchenCabinet", "bed", "wardrobe"})
"""Đồ cố định trên sàn, không nằm trên/dưới món khác. `other`, `chair`, `table` thì được (đèn, gối, ghế dưới bàn)."""
_TALL_IN_RUN: Final = frozenset({"wardrobe", "kitchenCabinet"})
"""Tủ cao/tủ lạnh nhãn `wardrobe` nằm trong hộp bao của dãy tủ chữ L: hộp bao rỗng phần góc nên đây là hai món thật."""
_HOME: Final[Mapping[str, frozenset[str]]] = {
    "bathroom": frozenset({"sanitaryFixture", "shower", "washingMachine"}),
    "kitchen": frozenset({"kitchenCabinet"}),
    "bedroom": frozenset({"bed", "wardrobe"}),
}
"""Loại đồ đúng với công năng phòng."""


def _editable(item: Furniture) -> bool:
    """Chỉ đồ AI chưa duyệt mới được xét (K21)."""
    return item.source == "ai" and not item.reviewed


def _duplicate(a: Furniture, b: Furniture, iou: float, iom: float) -> bool:
    """Hai hộp đang giao có phải cặp trùng không, theo các ngưỡng ở trên."""
    if a.kind == b.kind:
        return iou >= SAME_KIND_IOU or (a.kind != "other" and iom >= SAME_KIND_NESTED_IOM)
    both_fixed = a.kind in _FLOOR_FIXED and b.kind in _FLOOR_FIXED and {a.kind, b.kind} != _TALL_IN_RUN
    return iou >= CROSS_KIND_IOU or (both_fixed and iom >= FIXED_NESTED_IOM)


def _at_home(item: Furniture, usage: str | None) -> bool:
    """Loại đồ đúng công năng phòng của nó."""
    return usage is not None and item.kind in _HOME.get(usage, ())


def _loser(items: Sequence[Furniture], usages: Sequence[str | None], small: int, big: int, iou: float) -> int:
    """Chỉ số món bị bỏ trong cặp trùng `small` (hộp nhỏ hơn) / `big`; luật ở đầu tệp, hoà thì bỏ món đứng sau."""
    a, b = items[small], items[big]
    if a.suggested != b.suggested:
        return small if a.suggested else big
    home_a, home_b = _at_home(a, usages[small]), _at_home(b, usages[big])
    if iou < (SAME_KIND_IOU if a.kind == b.kind else CROSS_KIND_IOU):
        return big if home_a and not home_b else small
    if home_a != home_b:
        return big if home_a else small
    if a.confidence != b.confidence:
        return small if a.confidence < b.confidence else big
    return max(small, big)


def find_duplicates(items: Sequence[Furniture], usages: Sequence[str | None]) -> dict[int, int]:
    """`{món bị bỏ: món giữ}` theo chỉ số; xét cặp IoU cao trước, món đã bỏ không loại thêm ai (chuỗi A-B-C mất một)."""
    boxes = [world_box(item) for item in items]
    areas = [(b.max.x - b.min.x) * (b.max.y - b.min.y) for b in boxes]
    shapes = [shapely.box(b.min.x, b.min.y, b.max.x, b.max.y) for b in boxes]
    left, right = shapely.STRtree(shapes).query(shapes, predicate="intersects")
    pairs = []
    for i, j in zip(left.tolist(), right.tolist(), strict=True):
        if i >= j or not (_editable(items[i]) and _editable(items[j])) or not (areas[i] and areas[j]):
            continue
        p, q = boxes[i], boxes[j]
        common = (min(p.max.x, q.max.x) - max(p.min.x, q.min.x)) * (min(p.max.y, q.max.y) - max(p.min.y, q.min.y))
        iou = common / (areas[i] + areas[j] - common)
        if _duplicate(items[i], items[j], iou, common / min(areas[i], areas[j])):
            small, big = (i, j) if areas[i] <= areas[j] else (j, i)
            pairs.append((-iou, small, big))
    dropped: dict[int, int] = {}
    for negative_iou, small, big in sorted(pairs):
        if small not in dropped and big not in dropped:
            loser = _loser(items, usages, small, big, -negative_iou)
            dropped[loser] = big if loser == small else small
    return dropped


def dedupe_furniture(layer: SpatialLayer) -> SpatialLayer:
    """Lớp sau khi bỏ đồ trùng theo các luật ở đầu tệp; không có gì để bỏ thì trả nguyên `layer`."""
    if len(layer.furniture) < 2:
        return layer
    usage_of = {room.id: room.usage for room in layer.rooms}
    usages = [usage_of.get(item.room_id or "") for item in layer.furniture]
    dropped = find_duplicates(layer.furniture, usages)
    if not dropped:
        return layer
    kept = tuple(item for index, item in enumerate(layer.furniture) if index not in dropped)
    return layer.model_copy(update={"furniture": kept})
