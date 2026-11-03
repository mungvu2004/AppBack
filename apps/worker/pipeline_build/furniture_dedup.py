"""Lọc đồ trùng sau luật hậu xử lý (BENCH3D-26): một vật bị nhận hai lần, hoặc hai hộp khác loại đè nhau.

Chạy một chỗ trong `build._attempt`, sau `apply_post_rules` (hộp đã bắt tường, đã quay; so bằng `world_box`). Chỉ xét
đồ AI chưa duyệt (K21): thảm người đặt dưới giường AI không phải trùng. Đo bằng hai tỉ lệ vì chúng trả lời hai câu khác:

- IoU (giao / hợp): hai hộp cỡ gần nhau phủ cùng một chỗ, tức là cùng một vật.
- IoM (giao / hộp nhỏ hơn): hộp nhỏ nằm gọn trong hộp lớn. Một mình nó **không** nói là trùng: đèn trên bàn, gối trên
  giường, ghế kê dưới bàn đều có IoM 1 và IoU rất nhỏ. Vì vậy IoM chỉ có hiệu lực với cặp không thể chồng thật: cùng
  loại (trừ `_NESTABLE`), hoặc cả hai đều đặt cố định trên sàn (`_FLOOR_FIXED`: bồn cầu trên giường).

Bỏ món nào: đồ thật hơn gợi ý; cùng một chỗ (IoU đạt ngưỡng) → đúng công năng phòng, rồi độ tin; lồng nhau (IoU dưới
ngưỡng) → bỏ hộp nhỏ, không xét độ tin vì mất hộp lớn là mất món thật (vòi độ tin 0,64 trong bồn tắm 0,37), trừ khi chỉ
hộp nhỏ đúng công năng phòng (chậu lavabo trong hộp "tủ bếp" ở phòng tắm).

Riêng chậu trong dãy tủ ngoài phòng tắm không bỏ: đó là chậu bếp thật và AppFront không bày lại khi phòng đã có tủ. Món
thành chậu mỏng (`variant="sink"`, `heightMm` 20, đúng dạng `SINK` của `sceneFurnish.ts`), `toPascal.sinkFolderOf` dựng
tủ chứa nó thành mẫu có chậu. Chậu mỏng không còn là cặp trùng nên chạy lại không đổi gì.

Đồ ngoài khối nhà không xử lý ở đây: `rooms.build_furniture` đã gắn `suggested` (không xoá vì chưa chắc phòng đã đủ).
"""

import logging
from collections.abc import Mapping, Sequence
from typing import Final, NamedTuple

import numpy as np
import shapely

from packages.domain.rules_ai.orient import world_box
from packages.domain.rules_ai.post_rules import _editable
from packages.domain.spatial import Furniture, SpatialLayer

__all__ = ["dedupe_furniture"]

_log = logging.getLogger(__name__)

SAME_KIND_IOU: Final = 0.5
"""Cùng loại, IoU từ đây: cùng một vật bị nhận hai lần."""
SAME_KIND_NESTED_IOM: Final = 0.8
"""Cùng loại (trừ `_NESTABLE`), hộp nhỏ nằm ≥ ngần này trong hộp lớn: hai bồn tắm lồng nhau không có thật."""
CROSS_KIND_IOU: Final = 0.6
"""Khác loại, IoU từ đây: cùng một chỗ bị gán hai nhãn. Thấp hơn thì tủ lạnh `other` trong dãy tủ bếp ngắn cũng dính."""
FIXED_NESTED_IOM: Final = 0.8
"""Khác loại, cả hai thuộc `_FLOOR_FIXED`, hộp nhỏ nằm ≥ ngần này trong hộp lớn: gối nhận thành bồn cầu trên giường."""
THIN_SINK_MM: Final = 20
"""Bề dày chậu mỏng: `SINK` của `sceneFurnish.ts`; `isThinSink` nhận khi < 300 mm."""

_NESTABLE: Final = frozenset({"other", "chair"})
"""Cùng loại lồng nhau vẫn có thể là hai món: `other` hỗn tạp; ghế ăn thật trong hộp "ghế dài" bao cả hàng (ch-10)."""
_FLOOR_FIXED: Final = frozenset({"sanitaryFixture", "shower", "washingMachine", "kitchenCabinet", "bed", "wardrobe"})
"""Đồ cố định trên sàn, không nằm trên/dưới món khác. `other`, `chair`, `table` thì được (đèn, gối, ghế dưới bàn)."""
_REAL_IN_RUN: Final = (frozenset({"wardrobe", "kitchenCabinet"}), frozenset({"washingMachine", "kitchenCabinet"}))
"""Tủ cao nhãn `wardrobe`, máy giặt âm tủ nằm trong hộp bao của dãy tủ (hộp chữ L rỗng phần góc): hai món thật."""
_HOME: Final[Mapping[str, frozenset[str]]] = {
    "bathroom": frozenset({"sanitaryFixture", "shower", "washingMachine"}),
    "kitchen": frozenset({"kitchenCabinet"}),
    "bedroom": frozenset({"bed", "wardrobe"}),
}
"""Loại đồ đúng với công năng phòng."""

_Key = tuple[int, int, int, int, str, float]
"""Khoá nội dung của món (hộp thế giới, loại, độ tin): phá hoà không phụ thuộc thứ tự danh sách."""


class _Pair(NamedTuple):
    """Một cặp trùng; thứ tự trường là thứ tự xét: IoU cao trước, hoà theo nội dung, chỉ số chỉ cho hai món y hệt."""

    negative_iou: float
    small_key: _Key
    big_key: _Key
    small: int
    big: int


class _Plan(NamedTuple):
    """Kết quả xét một tầng, theo chỉ số món."""

    dropped: dict[int, int]
    """`{món bị bỏ: món giữ}`."""
    sinks: dict[int, int]
    """`{món thành chậu mỏng: dãy tủ chứa nó}`."""


def _duplicate(a: Furniture, b: Furniture, iou: float, iom: float) -> bool:
    """Hai hộp đang giao có phải cặp trùng không, theo các ngưỡng ở trên; chậu mỏng không bao giờ là cặp trùng."""
    if a.variant == "sink" or b.variant == "sink":
        return False
    if a.kind == b.kind:
        return iou >= SAME_KIND_IOU or (a.kind not in _NESTABLE and iom >= SAME_KIND_NESTED_IOM)
    both_fixed = a.kind in _FLOOR_FIXED and b.kind in _FLOOR_FIXED and {a.kind, b.kind} not in _REAL_IN_RUN
    return iou >= CROSS_KIND_IOU or (both_fixed and iom >= FIXED_NESTED_IOM)


def _at_home(item: Furniture, usage: str | None) -> bool:
    """Loại đồ đúng công năng phòng của nó."""
    return usage is not None and item.kind in _HOME.get(usage, ())


def _sink_in_run(items: Sequence[Furniture], usages: Sequence[str | None], pair: _Pair) -> bool:
    """Thiết bị vệ sinh lồng trong dãy tủ, không dính phòng tắm (ở phòng tắm đó là tủ lavabo, đã có luật bỏ tủ)."""
    small, big = items[pair.small], items[pair.big]
    return (
        small.kind == "sanitaryFixture"
        and big.kind == "kitchenCabinet"
        and small.suggested == big.suggested
        and -pair.negative_iou < CROSS_KIND_IOU
        and "bathroom" not in (usages[pair.small], usages[pair.big])
    )


def _loser(items: Sequence[Furniture], usages: Sequence[str | None], pair: _Pair) -> int:
    """Chỉ số món bị bỏ trong cặp trùng; luật ở đầu tệp, hoà hẳn thì bỏ món có khoá nội dung lớn hơn."""
    a, b = items[pair.small], items[pair.big]
    if a.suggested != b.suggested:
        return pair.small if a.suggested else pair.big
    home_a, home_b = _at_home(a, usages[pair.small]), _at_home(b, usages[pair.big])
    if -pair.negative_iou < (SAME_KIND_IOU if a.kind == b.kind else CROSS_KIND_IOU):
        return pair.big if home_a and not home_b else pair.small
    if home_a != home_b:
        return pair.big if home_a else pair.small
    if a.confidence != b.confidence:
        return pair.small if a.confidence < b.confidence else pair.big
    return pair.small if pair.small_key > pair.big_key else pair.big


def find_duplicates(items: Sequence[Furniture], usages: Sequence[str | None]) -> _Plan:
    """Xét mọi cặp giao nhau: cặp IoU cao trước, món đã bỏ không loại thêm ai (chuỗi A-B-C mất một), rồi đổi chậu."""
    boxes = [world_box(item) for item in items]
    keys = [
        (box.min.x, box.min.y, box.max.x, box.max.y, item.kind, item.confidence)
        for box, item in zip(boxes, items, strict=True)
    ]
    x0, y0, x1, y1 = np.array([key[:4] for key in keys], dtype=np.float64).T
    shapes = shapely.box(x0, y0, x1, y1)
    left, right = shapely.STRtree(shapes).query(shapes, predicate="intersects")
    areas = (x1 - x0) * (y1 - y0)
    # Lọc theo lô trước vòng Python: hộp diện tích 0 và cặp dưới mọi ngưỡng không tới được `_duplicate`.
    distinct = (left < right) & (areas[left] > 0) & (areas[right] > 0)
    left, right = left[distinct], right[distinct]
    width = np.minimum(x1[left], x1[right]) - np.maximum(x0[left], x0[right])
    depth = np.minimum(y1[left], y1[right]) - np.maximum(y0[left], y0[right])
    ious = width * depth / (areas[left] + areas[right] - width * depth)
    ioms = width * depth / np.minimum(areas[left], areas[right])
    near = (ious >= min(SAME_KIND_IOU, CROSS_KIND_IOU)) | (ioms >= min(SAME_KIND_NESTED_IOM, FIXED_NESTED_IOM))
    pairs = []
    for i, j, iou, iom in zip(*(values[near].tolist() for values in (left, right, ious, ioms)), strict=True):
        if _editable(items[i]) and _editable(items[j]) and _duplicate(items[i], items[j], iou, iom):
            small, big = (i, j) if (areas[i], keys[i]) <= (areas[j], keys[j]) else (j, i)
            pairs.append(_Pair(-iou, keys[small], keys[big], small, big))
    pairs.sort()
    dropped: dict[int, int] = {}
    sink_pairs = []
    for pair in pairs:
        if _sink_in_run(items, usages, pair):
            sink_pairs.append(pair)
        elif pair.small not in dropped and pair.big not in dropped:
            loser = _loser(items, usages, pair)
            dropped[loser] = pair.big if loser == pair.small else pair.small
    sinks = {pair.small: pair.big for pair in sink_pairs if pair.small not in dropped and pair.big not in dropped}
    return _Plan(dropped, sinks)


def dedupe_furniture(layer: SpatialLayer) -> SpatialLayer:
    """Lớp sau khi bỏ đồ trùng và đổi chậu theo các luật ở đầu tệp; không có gì để đổi thì trả nguyên `layer`."""
    if len(layer.furniture) < 2:
        return layer
    usage_of = {room.id: room.usage for room in layer.rooms}
    usages = [usage_of.get(item.room_id or "") for item in layer.furniture]
    plan = find_duplicates(layer.furniture, usages)
    if not plan.dropped and not plan.sinks:
        return layer
    # Không thêm khoá vào `BuiltLayer.dropped`: bộ 12 khoá được kiểm khi đọc lại layer.json đã lưu.
    _log.info("pipeline_build_furniture_deduped", extra={"dropped": len(plan.dropped), "sinks": len(plan.sinks)})
    kept = tuple(
        item.model_copy(update={"variant": "sink", "height_mm": THIN_SINK_MM}) if index in plan.sinks else item
        for index, item in enumerate(layer.furniture)
        if index not in plan.dropped
    )
    return layer.model_copy(update={"furniture": kept})
