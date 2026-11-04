"""Gộp khúc tường thẳng hàng chạm nhau thành một tường, một bề dày (WALL-RUN).

Vector hoá đo bề dày từng nhánh xương riêng và chỉ gộp khúc có bề dày gần nhau (`_PIECE_THICKNESS_RATIO`); bước 3b
chỉ nối khe có hộp ô mở. Một cạnh nhà thẳng vì thế ra 3-5 khúc chạm nhau, mỗi khúc một bậc bề dày (bench-3d f-22:
mép trên 300/200/150/200/300; 459/493 tầng bench có cặp như vậy). Ở đây, sau luật hậu xử lý (đã biết `kind`), các
khúc AI chưa duyệt, thẳng, cùng `kind`, thẳng hàng và chạm nhau (khe ≤ `_TOUCH_MM`) thành một tường: tim của khúc dài
nhất, bề dày = trung vị (trọng số độ dài) của bề dày đo rồi bắt bậc **một lần**, ô mở đặt lại theo tim mới.

Cùng `kind` giữ tách tường bao 220 với vách 100 nối thẳng qua chữ T (C1 của vector hoá): một bên là `envelope`,
một bên `partition`.

Khúc thật sự khác bề dày không gộp (`_thickness_runs`): cạnh f-22 400/150/220/400 là bê tông hai đầu, tường mỏng giữa;
trung vị của cả cạnh ra 400 và phủ gần 4 m tường 150-220. Gộp dọc đường đến khi bậc cao / bậc thấp vượt `_TIER_RATIO`.
"""

import itertools
import math
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np
import shapely

from packages.domain.spatial import Dimension, Opening, Point, Segment, SpatialLayer, Wall, js_round
from packages.domain.spatial.thickness import snap_thickness

__all__ = ["merge_wall_runs"]

_TOUCH_MM: Final = 10
"""Hai khúc cùng đường hở nhau ≤ ngần này (mm) là chạm nhau; khe cửa hẹp nhất 600 mm nên không bị lấp."""
_ALIGN_SIN: Final = math.sin(math.radians(2.0))
"""Lệch hướng ≤ 2° là cùng hướng (như `geometry._aligned`)."""
_SWAPPED: Final[Mapping[str, str]] = {"left": "right", "right": "left"}
"""Chiều mở tính theo hướng tim: khúc ngược hướng tường gộp thì cánh trái thành phải."""
_TIER_RATIO: Final = 1.5
"""Hai bậc chuẩn hơn nhau quá tỉ số này là hai đoạn tường khác nhau: 150-220, 200-300 gộp; 100-200, 220-400 không."""
_SLIVER_MM: Final = 600
"""Khúc không dài hơn khe cửa hẹp nhất là vụn đo ở chữ T: theo dãy đang gộp, không cắt dãy. Cột 800 mm vẫn tách."""


def _mergeable(wall: Wall) -> bool:
    """Tường AI chưa duyệt, thẳng, dài > 0: chỉ thứ máy dựng mới được gộp (K21)."""
    line = wall.centreline
    return wall.source == "ai" and not wall.reviewed and wall.curve_offset_mm == 0 and line.start != line.end


def _unit(wall: Wall) -> tuple[float, float]:
    """Hướng đơn vị của tim (tường dài 0 đã bị `_mergeable` loại)."""
    line = wall.centreline
    dx, dy = line.end.x - line.start.x, line.end.y - line.start.y
    length = math.hypot(dx, dy)
    return dx / length, dy / length


def _length(wall: Wall) -> float:
    """Chiều dài tim (mm)."""
    line = wall.centreline
    return math.dist((line.start.x, line.start.y), (line.end.x, line.end.y))


def _along(origin: Point, unit: tuple[float, float], point: Point) -> float:
    """Tham số của `point` chiếu lên đường qua `origin` theo `unit` (mm)."""
    return (point.x - origin.x) * unit[0] + (point.y - origin.y) * unit[1]


def _joins(a: Wall, b: Wall) -> bool:
    """Cùng `kind`, cùng hướng, hai đầu `b` cách tim `a` ≤ ½ bề dày lớn hơn, hai khoảng chiếu hở nhau ≤ `_TOUCH_MM`."""
    if a.kind != b.kind:
        return False
    ua, ub = _unit(a), _unit(b)
    if abs(ua[0] * ub[1] - ua[1] * ub[0]) > _ALIGN_SIN:
        return False
    origin = a.centreline.start
    limit = max(a.thickness_mm, b.thickness_mm) / 2
    ends = (b.centreline.start, b.centreline.end)
    if any(abs((p.x - origin.x) * ua[1] - (p.y - origin.y) * ua[0]) > limit for p in ends):
        return False
    a_low, a_high = sorted(_along(origin, ua, p) for p in (a.centreline.start, a.centreline.end))
    b_low, b_high = sorted(_along(origin, ua, p) for p in ends)
    return max(a_low, b_low) - min(a_high, b_high) <= _TOUCH_MM


def _measured(wall: Wall) -> float:
    """Bề dày đo (mm), chưa có thì lấy bề dày đang đặt."""
    return float(wall.detected_thickness_mm or wall.thickness_mm)


def _thickness_runs(members: Sequence[int], walls: Sequence[Wall]) -> list[list[int]]:
    """Cắt một nhóm thẳng hàng thành các dãy liền nhau theo `_TIER_RATIO`; khúc ≤ `_SLIVER_MM` không tính vào bậc."""
    first = walls[members[0]]
    origin, unit = first.centreline.start, _unit(first)

    def position(index: int) -> float:
        """Đầu gần của khúc trên đường chung."""
        line = walls[index].centreline
        return min(_along(origin, unit, line.start), _along(origin, unit, line.end))

    runs: list[list[int]] = []
    tiers: list[int] = []
    for index in sorted(members, key=position):
        wall = walls[index]
        spread = tiers + ([snap_thickness(_measured(wall))] if _length(wall) > _SLIVER_MM else [])
        if runs and (not spread or max(spread) / min(spread) <= _TIER_RATIO):
            runs[-1].append(index)
            tiers = spread
        else:
            runs.append([index])
            tiers = spread[-1:]
    return runs


def _groups(walls: Sequence[Wall]) -> list[list[int]]:
    """Dãy chỉ số tường gộp được: union-find trên cặp `_joins` (tra cặp qua `STRtree` đầu mút), cắt theo bề dày."""
    candidates = [index for index, wall in enumerate(walls) if _mergeable(wall)]
    if len(candidates) < 2:
        return []
    parent: dict[int, int] = {}

    def root(item: int) -> int:
        """Đại diện nhóm (nén đường đi); chỉ tường đã thành cặp mới vào `parent`."""
        parent.setdefault(item, item)
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    lines = [walls[index].centreline for index in candidates]
    coords = np.array([[(s.start.x, s.start.y), (s.end.x, s.end.y)] for s in lines], dtype=float)
    tree = shapely.STRtree(np.asarray(shapely.linestrings(coords), dtype=object))
    # Hộp quanh mỗi đầu, cạnh = khe chạm + nửa bề dày lớn nhất: khúc lệch tim (≤ ½ bề dày) vẫn thành cặp ứng viên.
    # Chỉ so hộp bao (không đo khoảng cách thật): `_joins` soát lại từng cặp còn sau bộ lọc.
    reach = _TOUCH_MM + max(walls[index].thickness_mm for index in candidates) / 2
    ends = coords.reshape(-1, 2)
    tip_idx, near = tree.query(
        shapely.box(ends[:, 0] - reach, ends[:, 1] - reach, ends[:, 0] + reach, ends[:, 1] + reach)
    )
    # Lọc theo lô trước vòng Python (trần 20 000 tường: mỗi đầu chạm cả tường của nó và mọi vách ở nút): khác tường,
    # cùng `kind`, cùng hướng — `_joins` chỉ còn soát lệch tim và khe của vài cặp thẳng hàng.
    slot = tip_idx // 2
    unit = coords[:, 1] - coords[:, 0]
    unit /= np.hypot(unit[:, 0], unit[:, 1])[:, None]
    kinds = np.array([walls[index].kind for index in candidates])
    cross = unit[slot, 0] * unit[near, 1] - unit[slot, 1] * unit[near, 0]
    keep = (slot != near) & (kinds[slot] == kinds[near]) & (np.abs(cross) <= _ALIGN_SIN)
    for slot_a, slot_b in zip(slot[keep].tolist(), near[keep].tolist(), strict=True):
        a, b = candidates[slot_a], candidates[slot_b]
        if root(a) != root(b) and _joins(walls[a], walls[b]):
            parent[root(a)] = root(b)
    groups: dict[int, list[int]] = {}
    for index in sorted(parent):
        groups.setdefault(root(index), []).append(index)
    return [run for members in groups.values() for run in _thickness_runs(members, walls) if len(run) > 1]


def _weighted_median(values: Sequence[float], weights: Sequence[float]) -> float:
    """Trung vị có trọng số: giá trị nhỏ nhất mà tổng trọng số tới nó ≥ nửa tổng."""
    pairs = sorted(zip(values, weights, strict=True))
    half, total = sum(weights) / 2, 0.0
    for value, weight in pairs:
        total += weight
        if total >= half:
            return value
    return pairs[-1][0]


def _merged(members: Sequence[Wall], openings: Mapping[str, Opening]) -> tuple[Wall, list[Opening]] | None:
    """Một tường thay cả nhóm (id, tim, `kind` của khúc dài nhất) và các ô mở của nhóm đặt lại trên tim đó.

    `None` (giữ nguyên các khúc) khi nhóm không nằm trọn trên tim khúc dài nhất (chuỗi cặp `_joins` lệch dần: cạnh gãy
    nhẹ, không kéo thẳng) hay ô mở đặt lại chồng nhau/lố khỏi tường (hai khúc chồng nhau cùng mang một cửa).
    """
    lead = max(members, key=_length)
    unit, origin = _unit(lead), lead.centreline.start
    limit = max(wall.thickness_mm for wall in members) / 2
    tips = [p for wall in members for p in (wall.centreline.start, wall.centreline.end)]
    if any(abs((p.x - origin.x) * unit[1] - (p.y - origin.y) * unit[0]) > limit for p in tips):
        return None
    ends = [_along(origin, unit, p) for wall in members for p in (wall.centreline.start, wall.centreline.end)]
    low, high = min(ends), max(ends)
    start = Point(x=js_round(origin.x + unit[0] * low), y=js_round(origin.y + unit[1] * low))
    end = Point(x=js_round(origin.x + unit[0] * high), y=js_round(origin.y + unit[1] * high))
    measured = _weighted_median([_measured(wall) for wall in members], [_length(wall) for wall in members])
    placed: list[tuple[int, Opening]] = []
    for wall in members:
        own = _unit(wall)
        flipped = own[0] * unit[0] + own[1] * unit[1] < 0
        # Đầu gần `start` của khúc tính theo tim mới: khúc cùng chiều là `offset`, ngược chiều là `offset + width`.
        shift = _along(start, unit, wall.centreline.start)
        for opening_id in wall.opening_ids:
            opening = openings[opening_id]
            near = opening.offset_mm + (opening.width_mm if flipped else 0)
            offset = max(0, js_round(shift - near if flipped else shift + near))
            swing = _SWAPPED.get(opening.swing, opening.swing) if flipped else opening.swing
            placed.append(
                (offset, opening.model_copy(update={"wall_id": lead.id, "offset_mm": offset, "swing": swing}))
            )
    placed.sort(key=lambda item: item[0])
    edges = [(offset, offset + opening.width_mm) for offset, opening in placed]
    if any(b[0] < a[1] for a, b in itertools.pairwise(edges)) or (edges and edges[-1][1] > high - low):
        return None
    wall = lead.model_copy(
        update={
            "centreline": Segment(start=start, end=end),
            "thickness_mm": snap_thickness(measured),
            "detected_thickness_mm": max(1, js_round(measured)),
            "confidence": min(wall.confidence for wall in members),
            "opening_ids": tuple(opening.id for _, opening in placed),
        }
    )
    return wall, [opening for _, opening in placed]


def _renamed(ids: Sequence[str], alias: Mapping[str, str]) -> tuple[str, ...]:
    """Id tường đổi sang id tường gộp, bỏ trùng, giữ thứ tự gặp đầu."""
    return tuple(dict.fromkeys(alias.get(item, item) for item in ids))


def merge_wall_runs(
    layer: SpatialLayer, dimensions: Sequence[Dimension] = ()
) -> tuple[SpatialLayer, tuple[Dimension, ...]]:
    """Gộp khúc thẳng hàng chạm nhau (xem docstring module); `wallIds` của phòng và `referenceIds` đổi theo.

    Không nhóm nào gộp được thì lớp ra bằng lớp vào. Tường gộp nằm ở vị trí khúc đầu tiên của nhóm trong `layer.walls`.
    """
    groups = _groups(layer.walls)
    by_id = {opening.id: opening for opening in layer.openings}
    alias: dict[str, str] = {}
    replaced: dict[int, Wall | None] = {}
    moved: dict[str, Opening] = {}
    for members in groups:
        merged = _merged([layer.walls[index] for index in members], by_id)
        if merged is None:
            continue
        run, placed = merged
        for index in members:
            alias[layer.walls[index].id] = run.id
            replaced[index] = None
        replaced[members[0]] = run
        moved.update((opening.id, opening) for opening in placed)
    if not replaced:
        return layer, tuple(dimensions)
    walls = tuple(
        kept for index, original in enumerate(layer.walls) if (kept := replaced.get(index, original)) is not None
    )
    rooms = tuple(room.model_copy(update={"wall_ids": _renamed(room.wall_ids, alias)}) for room in layer.rooms)
    openings = tuple(moved.get(opening.id, opening) for opening in layer.openings)
    dims = tuple(dim.model_copy(update={"reference_ids": _renamed(dim.reference_ids, alias)}) for dim in dimensions)
    return layer.model_copy(update={"walls": walls, "openings": openings, "rooms": rooms}), dims
