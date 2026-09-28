"""Trộn kết quả pipeline vào lớp hiện có mà không bao giờ sửa hay xoá mục đã duyệt (BE-00 §9, K21).

Hàm thuần: cùng đầu vào → cùng đầu ra, không sinh id mới, không đọc đồng hồ hay số
ngẫu nhiên (K18), nên B5-06b giao lặp thì lớp không đổi. B3-03 gọi trộn khi đang giữ
khoá tài liệu tầng nên mọi phép đối chiếu đi qua từ điển hay lưới ô, không so mọi cặp;
kết quả bằng hệt bản so mọi cặp (test đối chiếu với bản tham chiếu). Lỗi đầu vào
sai tiền điều kiện là `ValueError`, B5-06b coi là lỗi vĩnh viễn của lượt chạy.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from packages.domain.rules_ai.constants import MATCH_TOLERANCE_MM
from packages.domain.rules_ai.geometry import Bounds, CellKey, Xy, bounds_of, centroid, in_bounds, outline_contains
from packages.domain.spatial import (
    FieldChange,
    Furniture,
    Opening,
    Point,
    Room,
    SpatialLayer,
    Wall,
    diff_layers,
)

_Entity = Wall | Opening | Room | Furniture


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Kết quả trộn; thoả theo cấu trúc Protocol `MergeOutcome` của B3-03 (`layer`, `id_map` chỉ đọc).

    `changes` là `diff_layers(current, layer)` để B5-06b không tính lại; `dropped_ai_ids`
    theo thứ tự `ai`; `id_map` ánh xạ id tường/phòng AI bị bỏ vì trùng → id mục được giữ.
    """

    layer: SpatialLayer
    changes: tuple[FieldChange, ...]
    dropped_ai_ids: tuple[str, ...]
    id_map: Mapping[str, str]


def _level_ids(layer: SpatialLayer) -> set[str]:
    """`levelId` của mọi thực thể có trường đó (ô mở không có; nó theo tường chủ)."""
    members: tuple[Wall | Room | Furniture, ...] = (*layer.walls, *layer.rooms, *layer.furniture)
    return {entity.level_id for entity in members}


def _check_preconditions(current: SpatialLayer, ai: SpatialLayer) -> None:
    """Đầu vào của `ai` phải là đầu ra pipeline (`source="ai"`, chưa duyệt) và hai lớp cùng một tầng.

    Pipeline không được tạo mục đã duyệt (A5); lớp khác tầng là lỗi gọi, không trộn được.
    """
    bad = [entity.id for entity in ai.entities() if entity.source != "ai" or entity.reviewed]
    if bad:
        raise ValueError(f"lớp AI có mục không phải source=ai chưa duyệt: {bad[:3]}")
    levels = _level_ids(current) | _level_ids(ai)
    if len(levels) > 1:
        raise ValueError(f"hai lớp thuộc nhiều tầng khác nhau: {sorted(levels)}")


def _references(entity: _Entity) -> Iterable[str]:
    """Id mà thực thể trỏ tới: `opening.wallId`, `wall.openingIds`, `room.wallIds`, `furniture.roomId`."""
    if isinstance(entity, Opening):
        return (entity.wall_id,)
    if isinstance(entity, Wall):
        return entity.opening_ids
    if isinstance(entity, Room):
        return entity.wall_ids
    return () if entity.room_id is None else (entity.room_id,)


def _keep_ids(current: SpatialLayer) -> set[str]:
    """`K`: id thực thể đã duyệt hoặc do người vẽ, cộng phần đóng tham chiếu ("ghim").

    Bỏ phần ghim thì mục đã duyệt trỏ vào hư không và B3-03 từ chối ghi. Tham chiếu treo
    (id không có trong `current`) bị bỏ qua, không ném.
    """
    by_id: dict[str, _Entity] = {}
    for entity in current.entities():
        by_id.setdefault(entity.id, entity)
    keep = {entity.id for entity in current.entities() if entity.reviewed or entity.source == "human"}
    pending = list(keep)
    while pending:
        for ref in _references(by_id[pending.pop()]):
            if ref in by_id and ref not in keep:
                keep.add(ref)
                pending.append(ref)
    return keep


def _first_by_id[T: _Entity](items: Iterable[T]) -> dict[str, T]:
    """Từ điển id → phần tử; id trùng thì phần tử đứng trước (luật hoà của `current`)."""
    found: dict[str, T] = {}
    for item in items:
        found.setdefault(item.id, item)
    return found


def _near(first: Point, second: Point) -> bool:
    """Hai điểm cách nhau ≤ `MATCH_TOLERANCE_MM` (khoảng cách Euclid, so bằng số nguyên: không sai số thực)."""
    dx, dy = first.x - second.x, first.y - second.y
    return dx * dx + dy * dy <= MATCH_TOLERANCE_MM * MATCH_TOLERANCE_MM


def _same_run(first: Wall, second: Wall) -> bool:
    """Hai đầu mút cách hai đầu của tường kia ≤ dung sai, xét cả hai chiều."""
    a, b = first.centreline, second.centreline
    return (_near(a.start, b.start) and _near(a.end, b.end)) or (_near(a.start, b.end) and _near(a.end, b.start))


def _cell(point: Point) -> CellKey:
    """Ô lưới cạnh `MATCH_TOLERANCE_MM` chứa điểm; `//` làm tròn xuống cả số âm."""
    return point.x // MATCH_TOLERANCE_MM, point.y // MATCH_TOLERANCE_MM


class _WallMatcher:
    """Tìm tường `K` trùng một tường AI: cùng id, hoặc hai đầu mút trong dung sai (lưới ô, không so mọi cặp)."""

    def __init__(self, kept: Sequence[Wall]) -> None:
        """Mỗi tường `K` vào ô của **cả hai** đầu mút, kèm vị trí trong `current` để giữ luật hoà."""
        self._kept = kept
        self._by_id = _first_by_id(kept)
        self._cells: dict[CellKey, list[int]] = {}
        for position, wall in enumerate(kept):
            for end in (wall.centreline.start, wall.centreline.end):
                self._cells.setdefault(_cell(end), []).append(position)

    def match(self, wall: Wall) -> Wall | None:
        """Tường `K` trùng `wall`, hoặc `None`. Tra 3 x 3 ô quanh đầu mút thứ nhất (cách ≤ dung sai thì chênh ô ≤ 1)."""
        same_id = self._by_id.get(wall.id)
        if same_id is not None:
            return same_id
        cell_x, cell_y = _cell(wall.centreline.start)
        found: set[int] = set()
        for around_x in (cell_x - 1, cell_x, cell_x + 1):
            for around_y in (cell_y - 1, cell_y, cell_y + 1):
                found.update(self._cells.get((around_x, around_y), ()))
        for position in sorted(found):
            if _same_run(wall, self._kept[position]):
                return self._kept[position]
        return None


class _RoomMatcher:
    """Tìm phòng `K` trùng một phòng AI: cùng id, hoặc tâm diện tích của một bên nằm trong đường bao bên kia."""

    def __init__(self, kept: Sequence[Room]) -> None:
        """Tính tâm và hộp bao của mỗi phòng `K` một lần."""
        self._by_id = _first_by_id(kept)
        self._info = [(room, centroid(room.outline), bounds_of(room.outline)) for room in kept]

    def match(self, room: Room) -> Room | None:
        """Phòng `K` đầu tiên (theo `current`) trùng; chỉ gọi `outline_contains` khi tâm nằm trong hộp bao bên kia.

        Không dựng lưới theo hộp bao: 400 phòng 4 x 4,25 m ở lưới 50 mm là 2 triệu ô.
        """
        same_id = self._by_id.get(room.id)
        if same_id is not None:
            return same_id
        centre, bounds = centroid(room.outline), bounds_of(room.outline)
        # ponytail: so từng cặp phòng `K` x AI; `K` chỉ gồm phòng đã duyệt và phần ghim nên nhỏ.
        # Lên hàng nghìn phòng `K` thì thêm lưới 1.000 mm theo hộp bao.
        for kept, kept_centre, kept_bounds in self._info:
            if _centre_inside(centre, kept.outline, kept_bounds) or _centre_inside(kept_centre, room.outline, bounds):
                return kept
        return None


def _centre_inside(centre: Xy, outline: Sequence[Point], bounds: Bounds) -> bool:
    """Tâm nằm trong đường bao; hộp bao chặn trước vì `outline_contains` đắt hơn."""
    return in_bounds(bounds, *centre) and outline_contains(outline, *centre)


class _FurnitureMatcher:
    """Tìm đồ `K` trùng một đồ AI: cùng id, hoặc cùng `kind` và tâm AI nằm trong hộp của đồ `K` (tính cả biên)."""

    def __init__(self, kept: Sequence[Furniture]) -> None:
        """Nhóm đồ `K` theo `kind`, giữ thứ tự `current`."""
        self._by_id = _first_by_id(kept)
        self._by_kind: dict[str, list[Furniture]] = {}
        for item in kept:
            self._by_kind.setdefault(item.kind, []).append(item)

    def match(self, item: Furniture) -> Furniture | None:
        """Đồ `K` đầu tiên trùng, hoặc `None`."""
        same_id = self._by_id.get(item.id)
        if same_id is not None:
            return same_id
        for kept in self._by_kind.get(item.kind, ()):
            box = kept.bounding_box
            if box.min.x <= item.centre.x <= box.max.x and box.min.y <= item.centre.y <= box.max.y:
                return kept
        return None


def _rewire_wall(wall: Wall, dropped: set[str]) -> Wall:
    """Bỏ khỏi `openingIds` của tường AI những ô mở đã bị bỏ."""
    listed = tuple(opening_id for opening_id in wall.opening_ids if opening_id not in dropped)
    return wall if listed == wall.opening_ids else wall.model_copy(update={"opening_ids": listed})


def _rewire_room(room: Room, id_map: Mapping[str, str]) -> Room:
    """Đổi `wallIds` của phòng AI theo ánh xạ tường (tường bị bỏ luôn có ánh xạ)."""
    mapped = tuple(id_map.get(wall_id, wall_id) for wall_id in room.wall_ids)
    return room if mapped == room.wall_ids else room.model_copy(update={"wall_ids": mapped})


def _rewire_furniture(item: Furniture, id_map: Mapping[str, str]) -> Furniture:
    """Đổi `roomId` của đồ AI sang phòng được giữ khi phòng AI bị bỏ vì trùng."""
    if item.room_id is None or item.room_id not in id_map:
        return item
    return item.model_copy(update={"room_id": id_map[item.room_id]})


@dataclass(slots=True)
class _Survivors:
    """Bản AI còn lại sau bước 5: bốn danh sách, ánh xạ tường/phòng bị bỏ và id AI bị bỏ (theo thứ tự gặp)."""

    walls: list[Wall]
    openings: list[Opening]
    rooms: list[Room]
    furniture: list[Furniture]
    id_map: dict[str, str]
    dropped: set[str]


def _screen(ai: SpatialLayer, current: SpatialLayer, keep: set[str]) -> _Survivors:
    """Bước 5: đối chiếu tường, ô mở, phòng, đồ đạc của `ai` với thực thể `K` cùng loại; trùng thì bỏ.

    Tường chạy trước ô mở: ô mở có tường chủ đã ánh xạ sang tường `K` bị bỏ (không được thêm
    vào `openingIds` của tường giữ nguyên). Chỉ tường và phòng bị bỏ mới có ánh xạ id.
    """
    kept_opening_ids = {opening.id for opening in current.openings if opening.id in keep}
    out = _Survivors([], [], [], [], {}, set())
    walls = _WallMatcher([wall for wall in current.walls if wall.id in keep])
    for wall in ai.walls:
        target = walls.match(wall)
        if target is None:
            out.walls.append(wall)
        else:
            out.id_map[wall.id] = target.id
    for opening in ai.openings:
        if opening.id in kept_opening_ids or opening.wall_id in out.id_map:
            out.dropped.add(opening.id)
        else:
            out.openings.append(opening)
    rooms = _RoomMatcher([room for room in current.rooms if room.id in keep])
    for room in ai.rooms:
        target_room = rooms.match(room)
        if target_room is None:
            out.rooms.append(room)
        else:
            out.id_map[room.id] = target_room.id
    furniture = _FurnitureMatcher([item for item in current.furniture if item.id in keep])
    for item in ai.furniture:
        if furniture.match(item) is None:
            out.furniture.append(item)
        else:
            out.dropped.add(item.id)
    out.dropped.update(out.id_map)
    return out


def merge_pipeline_result(current: SpatialLayer, ai: SpatialLayer) -> MergeResult:
    """Trộn `ai` (đầu ra pipeline) vào `current`, đúng thứ tự bảy bước của B3-06 [6].

    Giữ nguyên vẹn `K` = mục đã duyệt hoặc do người vẽ cùng phần ghim (K21); bỏ mục AI cũ
    chưa duyệt; bỏ mục AI mới trùng `K`; nối lại tham chiếu của phần AI còn lại. Kết quả mỗi
    danh sách: phần tử `K` (thứ tự `current`) rồi bản AI còn lại (thứ tự `ai`).
    `ValueError` khi `ai` có mục không phải `source="ai"` chưa duyệt, hoặc hai lớp khác tầng.
    """
    _check_preconditions(current, ai)
    keep = _keep_ids(current)
    left = _screen(ai, current, keep)
    layer = SpatialLayer(
        walls=(*(w for w in current.walls if w.id in keep), *(_rewire_wall(w, left.dropped) for w in left.walls)),
        openings=(*(o for o in current.openings if o.id in keep), *left.openings),
        rooms=(*(r for r in current.rooms if r.id in keep), *(_rewire_room(r, left.id_map) for r in left.rooms)),
        furniture=(
            *(f for f in current.furniture if f.id in keep),
            *(_rewire_furniture(f, left.id_map) for f in left.furniture),
        ),
    )
    return MergeResult(
        layer=layer,
        changes=tuple(diff_layers(current, layer)),
        dropped_ai_ids=tuple(entity.id for entity in ai.entities() if entity.id in left.dropped),
        id_map=MappingProxyType(left.id_map),
    )
