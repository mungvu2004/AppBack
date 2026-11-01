"""Tường cong qua bước dựng tầng: nổ thành dây trước bước 3, gộp lại thành một `Wall` cong sau bước 6.

Bước 3-6 (nối khe, gắn ô mở, dựng phòng) chỉ hiểu đoạn thẳng. Thay vì dạy từng bước hình học về cung, mỗi
`WallPx` cong được chia thành dây đều (như vector hoá trả trước khi có `sagitta_px`), các bước chạy y hệt, rồi
`join_arcs` gộp dây của cùng một cung thành một tường có `curveOffsetMm`. Dây nào bị bước 3b gộp với tường khác,
bị bỏ hay đứt nối thì cung đó giữ nguyên các dây thẳng (không đoán).
"""

import itertools
import math
from collections.abc import Sequence
from typing import Final

from apps.worker.pipeline_build.geometry import WallSet
from packages.domain.spatial.arc import ARC_STEP_DEG, arc_points, sagitta_through
from packages.domain.spatial.area import js_round
from packages.domain.spatial.model import Opening, Room, Wall
from packages.ml_contracts.artifacts import PointPx, WallPx

_MIN_CHORD_THICKNESS: Final = 1.5
"""Dây nổ từ cung dài ≥ ngần này lần bề dày (cùng ngưỡng chia cung của vector hoá, bước 5b)."""


def explode_arcs(walls: Sequence[WallPx]) -> tuple[tuple[WallPx, ...], tuple[int | None, ...]]:
    """Mỗi tường cong → các dây thẳng đều (số dây chẵn); trả dây và tường cong gốc của từng dây (`None` = thẳng)."""
    out: list[WallPx] = []
    arc_of: list[int | None] = []
    for index, wall in enumerate(walls):
        if wall.sagitta_px == 0:
            out.append(wall)
            arc_of.append(None)
            continue
        chord = math.dist((wall.start.x, wall.start.y), (wall.end.x, wall.end.y))
        depth = abs(wall.sagitta_px)
        radius = chord * chord / (8 * depth) + depth / 2
        # Như 5b: dây ≤ 10° nhưng không ngắn hơn 1,5 bề dày, kẻo ô mở trên cung bị kẹp về dây quá ngắn rồi rơi.
        step = max(ARC_STEP_DEG, math.degrees(_MIN_CHORD_THICKNESS * wall.thickness_px / radius))
        points = arc_points((wall.start.x, wall.start.y), (wall.end.x, wall.end.y), wall.sagitta_px, step)
        for (ax, ay), (bx, by) in itertools.pairwise(points):
            out.append(
                WallPx(
                    start=PointPx(x=max(0.0, ax), y=max(0.0, ay)),
                    end=PointPx(x=max(0.0, bx), y=max(0.0, by)),
                    thickness_px=wall.thickness_px,
                    confidence=wall.confidence,
                )
            )
            arc_of.append(index)
    return tuple(out), tuple(arc_of)


def _chain(walls: Sequence[Wall], positions: Sequence[int]) -> bool:
    """Các tường ở `positions` nối đuôi nhau đúng thứ tự: cuối tường trước trùng đầu tường sau."""
    return all(walls[one].centreline.end == walls[two].centreline.start for one, two in itertools.pairwise(positions))


def _merged(chords: Sequence[Wall]) -> Wall:
    """Một tường cong từ các dây (số chẵn, đỉnh giữa là đỉnh cung); giữ id, bề dày của dây đầu."""
    start, end = chords[0].centreline.start, chords[-1].centreline.end
    apex = chords[len(chords) // 2].centreline.start
    half = math.floor(math.hypot(end.x - start.x, end.y - start.y) / 2)
    sagitta = js_round(sagitta_through((start.x, start.y), (apex.x, apex.y), (end.x, end.y)))
    lengths = [_length(w) for w in chords]
    confidence = sum(w.confidence * k for w, k in zip(chords, lengths, strict=True)) / sum(lengths)
    return chords[0].model_copy(
        update={
            "centreline": chords[0].centreline.model_copy(update={"end": end}),
            "curve_offset_mm": max(-half, min(half, sagitta)),
            "confidence": round(confidence, 3),
            "opening_ids": tuple(opening for w in chords for opening in w.opening_ids),
        }
    )


def _length(wall: Wall) -> float:
    """Chiều dài dây tim của `wall` (mm)."""
    line = wall.centreline
    return math.dist((line.start.x, line.start.y), (line.end.x, line.end.y))


def _shifted(opening: Opening, offsets: dict[str, tuple[str, float]]) -> Opening:
    """Ô mở trên một dây → cùng ô mở trên tường cong: đổi `wallId`, `offsetMm` cộng chiều dài các dây trước."""
    if opening.wall_id not in offsets:
        return opening
    wall_id, before = offsets[opening.wall_id]
    return opening.model_copy(update={"wall_id": wall_id, "offset_mm": js_round(opening.offset_mm + before)})


def join_arcs(
    wall_set: WallSet, rooms: Sequence[Room], arc_of: Sequence[int | None]
) -> tuple[WallSet, tuple[Room, ...]]:
    """Gộp dây của từng cung thành một tường cong; ô mở, `wallIds` của phòng và `input_to_wall` đánh lại theo.

    Cung chỉ gộp khi mỗi dây còn là một tường riêng (không gộp với đầu vào khác), các dây nối đuôi đúng thứ tự
    và số dây chẵn (đỉnh giữa là đỉnh cung). Không có tường cong → trả nguyên đối số.
    """
    if all(arc is None for arc in arc_of):
        return wall_set, tuple(rooms)
    walls = wall_set.walls
    inputs_of: dict[int, list[int]] = {}
    for index, position in wall_set.input_to_wall.items():
        inputs_of.setdefault(position, []).append(index)
    arcs: dict[int, list[int]] = {}
    for index, arc in enumerate(arc_of):
        if arc is not None:
            arcs.setdefault(arc, []).append(index)
    replace: dict[int, Wall] = {}
    absorbed: dict[int, int] = {}
    offsets: dict[str, tuple[str, float]] = {}
    for indices in arcs.values():
        positions = [wall_set.input_to_wall.get(index) for index in indices]
        if any(p is None or inputs_of[p] != [i] for p, i in zip(positions, indices, strict=True)):
            continue
        kept = [p for p in positions if p is not None]
        if len(kept) % 2 or not _chain(walls, kept):
            continue
        chords = [walls[p] for p in kept]
        merged = _merged(chords)
        replace[kept[0]] = merged
        before = 0.0
        for position, chord in zip(kept, chords, strict=True):
            absorbed[position] = kept[0]
            offsets[chord.id] = (merged.id, before)
            before += _length(chord)
    if not replace:
        return wall_set, tuple(rooms)
    renumber: dict[int, int] = {}
    new_walls: list[Wall] = []
    for position, wall in enumerate(walls):
        head = absorbed.get(position, position)
        if head == position:
            renumber[position] = len(new_walls)
            new_walls.append(replace.get(position, wall))
    ids = {chord_id: wall_id for chord_id, (wall_id, _) in offsets.items()}
    new_rooms = tuple(
        room.model_copy(update={"wall_ids": tuple(dict.fromkeys(ids.get(w, w) for w in room.wall_ids))})
        for room in rooms
    )
    joined = WallSet(
        tuple(new_walls),
        tuple(_shifted(opening, offsets) for opening in wall_set.openings),
        {index: renumber[absorbed.get(position, position)] for index, position in wall_set.input_to_wall.items()},
        wall_set.bridges,
    )
    return joined, new_rooms
