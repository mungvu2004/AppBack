"""Chiều mở cửa đi một cánh đọc từ nét vẽ: cánh (đoạn thẳng vuông tường) + cung 1/4 tròn quanh bản lề (QT-SWING).

Trước đây `Opening.swing` lấy theo nhãn YOLO (`door` → luôn `"left"`) và `reversed` luôn `False`: cửa 3D mở sai
phía, sai bản lề. Ở đây thử 4 giả thuyết (bản lề ở đầu `a`/`b` của khe x cánh về phía `+n`/`-n`), lấy mẫu
dọc nét cánh và nét cung mỗi giả thuyết trên ảnh mực (trang xám < `INK_GRAY`, trừ mặt nạ tường, nới vài px), chọn
giả thuyết phủ mực nhiều nhất khi nó đủ chắc; không chắc → `None` để nơi gọi giữ giá trị cũ.

Đổi sang ngữ nghĩa FE (`AppFront/src/lib/pascal/toPascal.ts` `doorLeafOf` + `swingDirection.ts`, Pascal
`nodes/src/door/floorplan.ts`):

- `swing="left"` ⇔ Pascal `hingesSide:'left'` ⇔ bản lề ở mép khe phía `centreline.start` của tường
  (`cx - dir·w/2`); `"right"` ⇔ bản lề ở mép phía `centreline.end`.
- Phía cánh: Pascal `inward` = cánh quét sang pháp tuyến TRÁI `n = (-dy, dx)/L` của trục (mặt bằng, y xuống trang).
  FE không lưu phía mở mà tính bằng luật `swingDirectionOf` (tường bao → mở vào nhà; cửa trong → phòng không phải
  hành lang, hoà thì phòng nhỏ hơn); `reversed=True` đảo kết quả luật. Nên `reversed = (phía đọc được ≠ phía luật)`,
  tính sau khi có phòng (`settle_reversed`, port đúng luật FE).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from apps.worker.pipeline_build.residual import INK_GRAY, PageRaster
from packages.domain.spatial import Opening, Point, Room, SpatialLayer, Wall

Vec = tuple[float, float]

MIN_WIDTH_PX: Final = 12.0
"""Khe hẹp hơn: quá ít điểm ảnh để phân biệt cung với nét khác."""

MIN_ARC_HIT: Final = 0.35
MIN_LEAF_HIT: Final = 0.5
"""Giả thuyết thắng phải có mực dưới ≥ 35 % điểm mẫu cung và ≥ 50 % điểm mẫu cánh (cung thường vẽ nhạt, nét đứt)."""

MIN_MARGIN: Final = 0.15
"""Điểm thắng phải hơn giả thuyết nhì ≥ 0,15: hai giả thuyết sát nhau (cửa đôi, đường kích thước) → không đoán."""

_LEAF_FROM: Final = 0.15
"""Bỏ đoạn cánh sát mặt tường (≤ 15 % rộng): ở đó là nét khung/ghi chú chung cho mọi giả thuyết."""

_PROBE_MM: Final = 300.0
"""Khoảng dò phòng hai bên mặt tường, như `SWING_PROBE_MM` của FE."""


@dataclass(frozen=True, slots=True)
class Leaf:
    """Cánh đọc được: `hinge_at_b` = bản lề ở đầu `b` của khe; `side` = +1 cánh về phía `n`, -1 phía `-n`."""

    hinge_at_b: bool
    side: int


def _ink(page: PageRaster, x0: int, y0: int, x1: int, y1: int, radius: int) -> NDArray[np.bool_]:
    """Mực trong khung `[x0, x1) x [y0, y1)` (đã cắt theo trang), trừ tường, nới `radius` px."""
    ink = (page.gray[y0:y1, x0:x1] < INK_GRAY) & ~page.walls[y0:y1, x0:x1]
    size = 2 * radius + 1
    return np.asarray(cv2.dilate(ink.astype(np.uint8), np.ones((size, size), np.uint8)) > 0)


def _hit(ink: NDArray[np.bool_], origin: Vec, points: NDArray[np.float64]) -> float:
    """Tỉ lệ điểm mẫu (px trang) rơi vào mực; điểm ra ngoài khung tính trượt."""
    cols = np.rint(points[:, 0] - origin[0]).astype(int)
    rows = np.rint(points[:, 1] - origin[1]).astype(int)
    inside = (cols >= 0) & (rows >= 0) & (cols < ink.shape[1]) & (rows < ink.shape[0])
    hits = np.zeros(len(points), bool)
    hits[inside] = ink[rows[inside], cols[inside]]
    return float(hits.mean())


def read_leaf(page: PageRaster, a: Vec, b: Vec, half_thickness: float) -> Leaf | None:
    """Đọc bản lề + phía cánh của cửa một cánh có khe `a → b` (px, trên tim tường), tường dày `2·half_thickness` px.

    Mỗi giả thuyết: bản lề `h` (đầu `a` hay `b`) dời ra mặt tường `h + s·n·t`, cánh là đoạn vuông tường dài `w`
    (bỏ 15 % sát tường), cung tâm bản lề bán kính `w` từ mép kia tới đầu cánh (mẫu ở 8°-82°). `None` khi khe quá
    hẹp, trang lệch khổ mặt nạ, hay không giả thuyết nào đủ `MIN_*` và hơn nhì `MIN_MARGIN`.
    """
    if page.gray.shape != page.walls.shape:
        return None
    ax, ay = a
    bx, by = b
    width = math.hypot(bx - ax, by - ay)
    if width < MIN_WIDTH_PX:
        return None
    ux, uy = (bx - ax) / width, (by - ay) / width
    nx, ny = -uy, ux
    reach = width + half_thickness + 4
    height, cols = page.gray.shape
    x0 = max(0, math.floor(min(ax, bx) - reach))
    y0 = max(0, math.floor(min(ay, by) - reach))
    x1 = min(cols, math.ceil(max(ax, bx) + reach) + 1)
    y1 = min(height, math.ceil(max(ay, by) + reach) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    ink = _ink(page, x0, y0, x1, y1, max(2, round(0.05 * width)))
    depths = np.linspace(_LEAF_FROM, 1.0, 24) * width
    angles = np.radians(np.linspace(8.0, 82.0, 32))
    scores: list[tuple[float, float, float, bool, int]] = []
    for hinge_at_b in (False, True):
        hx, hy = (bx, by) if hinge_at_b else (ax, ay)
        # Từ bản lề nhìn về mép kia của khe.
        tx, ty = (-ux, -uy) if hinge_at_b else (ux, uy)
        for side in (1, -1):
            px, py = hx + side * nx * half_thickness, hy + side * ny * half_thickness
            sx, sy = side * nx, side * ny
            leaf = np.column_stack((px + sx * depths, py + sy * depths))
            arc = np.column_stack(
                (
                    px + width * (tx * np.cos(angles) + sx * np.sin(angles)),
                    py + width * (ty * np.cos(angles) + sy * np.sin(angles)),
                )
            )
            leaf_hit, arc_hit = _hit(ink, (x0, y0), leaf), _hit(ink, (x0, y0), arc)
            scores.append(((leaf_hit + arc_hit) / 2, leaf_hit, arc_hit, hinge_at_b, side))
    scores.sort(reverse=True)
    best, runner = scores[0], scores[1]
    if best[1] < MIN_LEAF_HIT or best[2] < MIN_ARC_HIT or best[0] - runner[0] < MIN_MARGIN:
        return None
    return Leaf(hinge_at_b=best[3], side=best[4])


def _inside(p: Vec, outline: Sequence[Point]) -> bool:
    """Điểm trong đa giác (tia ngang, chẵn-lẻ) — như `insideOutline` của FE."""
    inside = False
    j = len(outline) - 1
    for i, a in enumerate(outline):
        b = outline[j]
        if (a.y > p[1]) != (b.y > p[1]) and p[0] < (b.x - a.x) * (p[1] - a.y) / (b.y - a.y) + a.x:
            inside = not inside
        j = i
    return inside


def rule_side(opening: Opening, wall: Wall, rooms: Sequence[Room]) -> int:
    """Port `swingDirectionOf` (FE): +1 = `inward` (pháp tuyến trái của tim), -1 = `outward`."""
    start, end = wall.centreline.start, wall.centreline.end
    length = math.hypot(end.x - start.x, end.y - start.y)
    if not length > 0:
        return 1
    dx, dy = (end.x - start.x) / length, (end.y - start.y) / length
    along = opening.offset_mm + opening.width_mm / 2
    reach = wall.thickness_mm / 2 + _PROBE_MM

    def room_at(sign: int) -> Room | None:
        p = (start.x + dx * along - dy * reach * sign, start.y + dy * along + dx * reach * sign)
        return next(
            (r for r in rooms if r.level_id == wall.level_id and r.finish != "decking" and _inside(p, r.outline)), None
        )

    left, right = room_at(1), room_at(-1)
    if left is None or right is None:
        return -1 if right is not None else 1
    if (left.usage == "corridor") != (right.usage == "corridor"):
        return -1 if left.usage == "corridor" else 1
    return -1 if right.area_m2 < left.area_m2 else 1


def settle_reversed(layer: SpatialLayer, leaves: Mapping[str, Vec]) -> SpatialLayer:
    """Đặt `reversed=True` cho cửa có phía cánh đọc được (`leaves`: id ô mở → hướng cánh tuyệt đối trên mặt bằng)
    khác phía luật FE tính trên phòng của `layer`; ô mở/tường không còn trong lớp thì bỏ qua."""
    if not leaves:
        return layer
    walls = {wall.id: wall for wall in layer.walls}
    openings = []
    for opening in layer.openings:
        vec = leaves.get(opening.id)
        wall = walls.get(opening.wall_id)
        if vec is not None and wall is not None:
            start, end = wall.centreline.start, wall.centreline.end
            seen = 1 if (end.y - start.y) * -vec[0] + (end.x - start.x) * vec[1] > 0 else -1
            if seen != rule_side(opening, wall, layer.rooms):
                opening = opening.model_copy(update={"reversed": True})
        openings.append(opening)
    return layer.model_copy(update={"openings": tuple(openings)})
