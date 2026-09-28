"""Luật hậu xử lý đầu ra AI: thiết bị áp tường (luật 1) và cửa sổ chỉ trên tường ngoài (luật 2).

Gương `FIXTURE-OFF-WALL` và `WINDOW-ON-INNER-WALL` của FE (`fitout/index.ts`) để luật QC
không bắn trên đầu ra AI. Chỉ đụng thực thể `source="ai"` và `reviewed=False` (K21);
không đặt `reviewed`, không đổi `source`, không tạo id. Hàm thuần và idempotent.

Trang thật có tới 20.000 tường và 5.000 phòng, nên cả hai luật tra qua lưới ô
`GRID_CELL_MM`. Chỉ mục chỉ cắt ứng viên xa chắc chắn không đổi quyết định: kết quả
bằng hệt bản quét hết (test đối chiếu với bản tham chiếu).
"""

import math
from collections.abc import Sequence

from packages.domain.rules_ai.constants import (
    FIXTURE_SNAP_REACH_MM,
    GRID_CELL_MM,
    LOW_CONFIDENCE_CAP,
    WALL_HUGGING_KINDS,
    WALL_HUGGING_TOLERANCE_MM,
)
from packages.domain.rules_ai.geometry import (
    CellKey,
    Nearest,
    WallSide,
    bounds_of,
    cell_keys,
    in_bounds,
    nearest_probe,
    outline_contains,
    wall_side_by,
)
from packages.domain.spatial import BoundingBox, Furniture, Opening, Point, Room, SpatialLayer, Wall, js_round


def _editable(entity: Wall | Opening | Furniture) -> bool:
    """Chỉ mục AI chưa duyệt được đổi; mục của người hay đã duyệt đi ra nguyên vẹn (K21)."""
    return entity.source == "ai" and not entity.reviewed


def _capped[T: (Wall, Opening, Furniture)](entity: T) -> T:
    """Hạ `confidence` xuống trần `LOW_CONFIDENCE_CAP` bằng `min`, nên lượt thứ hai không hạ thêm."""
    if entity.confidence <= LOW_CONFIDENCE_CAP:
        return entity
    return entity.model_copy(update={"confidence": LOW_CONFIDENCE_CAP})


class _WallIndex:
    """Lưới ô các tường, mỗi tường vào mọi ô chạm hộp bao hai đầu mút nở `thicknessMm / 2 + FIXTURE_SNAP_REACH_MM`.

    Tường ngoài các ô mà hộp đồ chạm có `gap > FIXTURE_SNAP_REACH_MM` (mọi điểm dò cách
    hộp bao của tường quá tầm), nên bỏ chúng không đổi quyết định.
    """

    def __init__(self, walls: Sequence[Wall]) -> None:
        """Dựng lưới một lần cho cả lượt `apply_post_rules`."""
        self.walls = walls
        self._cells: dict[CellKey, list[int]] = {}
        for position, wall in enumerate(walls):
            line = wall.centreline
            low_x, low_y, high_x, high_y = bounds_of((line.start, line.end))
            reach = wall.thickness_mm / 2 + FIXTURE_SNAP_REACH_MM
            for key in cell_keys((low_x - reach, low_y - reach, high_x + reach, high_y + reach), GRID_CELL_MM):
                self._cells.setdefault(key, []).append(position)

    def candidates(self, box: BoundingBox) -> list[int]:
        """Vị trí các tường có thể trong tầm với của hộp, theo thứ tự `walls` (giữ luật hoà)."""
        found: set[int] = set()
        for key in cell_keys((box.min.x, box.min.y, box.max.x, box.max.y), GRID_CELL_MM):
            found.update(self._cells.get(key, ()))
        return sorted(found)

    def nearest(self, box: BoundingBox) -> tuple[float, Nearest] | None:
        """Khe tới mặt tường gần nhất và điểm dò tương ứng, hoà thì tường đứng trước; `None` khi không có ứng viên."""
        best: tuple[float, Nearest] | None = None
        for position in self.candidates(box):
            wall = self.walls[position]
            near = nearest_probe(box, wall)
            gap = max(0.0, near.distance - wall.thickness_mm / 2)
            if best is None or gap < best[0]:
                best = gap, near
        return best


def _shifted(box: BoundingBox, dx: int, dy: int) -> BoundingBox:
    """Hộp dời `(dx, dy)`."""
    return BoundingBox(min=Point(x=box.min.x + dx, y=box.min.y + dy), max=Point(x=box.max.x + dx, y=box.max.y + dy))


def _snap_fixture(item: Furniture, index: _WallIndex) -> Furniture:
    """Luật 1 cho một đồ đạc: dời sát mặt tường gần nhất khi khe trong `(50, 300]` mm, kèm hạ tin cậy.

    Vector dời `(f - p) x gap / d` với `p` là điểm dò gần nhất (khoảng cách `d`), `f` chân
    đường vuông góc; làm tròn từng thành phần bằng `js_round`. Ngoài khoảng đó giữ nguyên:
    ≤ 50 là đã áp tường, > 300 là sai phòng, việc của người duyệt.
    """
    found = index.nearest(item.bounding_box)
    if found is None or not WALL_HUGGING_TOLERANCE_MM < found[0] <= FIXTURE_SNAP_REACH_MM:
        return item
    gap, near = found
    dx = js_round((near.foot[0] - near.probe[0]) * gap / near.distance)
    dy = js_round((near.foot[1] - near.probe[1]) * gap / near.distance)
    moved = item.model_copy(
        update={
            "centre": Point(x=item.centre.x + dx, y=item.centre.y + dy),
            "bounding_box": _shifted(item.bounding_box, dx, dy),
        }
    )
    return _capped(moved)


def _snap_fixtures(layer: SpatialLayer) -> tuple[Furniture, ...]:
    """Luật 1 cho cả lớp; thứ tự đồ đạc giữ nguyên. Không dựng chỉ mục khi không có đồ nào đủ điều kiện."""
    eligible = [_editable(item) and item.kind in WALL_HUGGING_KINDS for item in layer.furniture]
    if not any(eligible):
        return layer.furniture
    index = _WallIndex(layer.walls)
    return tuple(
        _snap_fixture(item, index) if flag else item for item, flag in zip(layer.furniture, eligible, strict=True)
    )


class _RoomIndex:
    """Lưới ô các phòng theo hộp bao (tính một lần); điểm chỉ thử `outline_contains` với phòng có hộp chứa điểm.

    Điểm ngoài hộp bao chắc chắn ngoài đường bao, nên kết quả bằng hệt quét mọi phòng.
    """

    def __init__(self, rooms: Sequence[Room]) -> None:
        """Dựng lưới: mỗi phòng vào mọi ô chạm hộp bao của nó."""
        self._entries = [(room.outline, bounds_of(room.outline)) for room in rooms]
        self._cells: dict[CellKey, list[int]] = {}
        for position, (_, bounds) in enumerate(self._entries):
            for key in cell_keys(bounds, GRID_CELL_MM):
                self._cells.setdefault(key, []).append(position)

    def contains(self, x: float, y: float) -> bool:
        """Có phòng nào chứa điểm `(x, y)` không."""
        key = math.floor(x // GRID_CELL_MM), math.floor(y // GRID_CELL_MM)
        for position in self._cells.get(key, ()):
            outline, bounds = self._entries[position]
            if in_bounds(bounds, x, y) and outline_contains(outline, x, y):
                return True
        return False


def _envelope(wall: Wall) -> Wall:
    """Tường được phân loại lại thành `envelope`, tin cậy hạ về trần (không lật im lặng)."""
    return _capped(wall.model_copy(update={"kind": "envelope"}))


def _is_target(opening: Opening, host: Wall) -> bool:
    """Cửa sổ AI chưa duyệt trên tường chưa phải `envelope`: đối tượng của luật 2."""
    return opening.kind == "window" and _editable(opening) and host.kind != "envelope"


def _fix_windows(layer: SpatialLayer) -> tuple[tuple[Wall, ...], tuple[Opening, ...]]:
    """Luật 2: cửa sổ AI chưa duyệt trên tường chưa phải `envelope`, quyết một lần cho mỗi tường chủ.

    `exterior` mà tường chủ AI chưa duyệt → tường thành `envelope`. `interior`, hoặc
    tường chủ không được đổi → giữ cửa sổ, hạ tin cậy của nó; không xoá, không đổi thành
    cửa đi (việc của người duyệt). `unknown` (chưa có phòng) → giữ nguyên.
    """
    walls: dict[str, Wall] = {}
    for wall in layer.walls:
        walls.setdefault(wall.id, wall)
    rooms = _RoomIndex(layer.rooms)
    sides: dict[str, WallSide] = {}
    promoted: set[str] = set()
    openings: list[Opening] = []
    for opening in layer.openings:
        host = walls.get(opening.wall_id)
        if host is None or not _is_target(opening, host):
            openings.append(opening)
            continue
        if host.id not in sides:
            sides[host.id] = wall_side_by(host, rooms.contains)
        side = sides[host.id]
        if side == "exterior" and _editable(host):
            promoted.add(host.id)
            openings.append(opening)
        else:
            openings.append(opening if side == "unknown" else _capped(opening))
    return tuple(_envelope(w) if w.id in promoted else w for w in layer.walls), tuple(openings)


def apply_post_rules(layer: SpatialLayer) -> SpatialLayer:
    """Áp luật 1 rồi luật 2 lên lớp vừa dựng từ pipeline; trả lớp mới, không sửa `layer`.

    Idempotent: `f(f(x)) == f(x)`, vì luật 1 đưa khe về ≤ 50 và hạ tin cậy bằng `min`,
    luật 2 chỉ đổi tường thành `envelope` (bị bỏ qua từ lượt sau) hoặc hạ tin cậy bằng `min`.
    Luật 1 chỉ dời đồ và luật 2 không đổi hình học nên hai luật độc lập về chỉ mục.
    """
    furniture = _snap_fixtures(layer)
    walls, openings = _fix_windows(layer)
    return SpatialLayer(walls=walls, openings=openings, rooms=layer.rooms, furniture=furniture)
