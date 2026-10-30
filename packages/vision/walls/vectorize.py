"""Vector hoá mặt nạ tường nhị phân thành các đoạn tim (B5-02 khối [6]).

Xương hoá Zhang-Suen rồi dựng đồ thị 8 hướng trên **điểm xương**: nút là điểm bậc 1
hoặc cụm điểm bậc ≥ 3 kề nhau, nhánh là chuỗi điểm bậc 2 giữa hai nút. Làm trên danh
sách điểm chứ không quét lưới nên chi phí theo số điểm xương, không theo số điểm ảnh (K28).
Bề dày lấy từ `distanceTransform` nên là số đo thật, **không** làm tròn về bộ chuẩn
(việc đó của B5-05). Gói không nhập `ml_contracts`/`apps.*`, không đọc biến môi trường.
Mọi bước chỉ phụ thuộc mặt nạ đầu vào nên kết quả tất định.
"""

import bisect
import itertools
import math
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray
from skimage.morphology import skeletonize

from packages.vision.walls.ink_refine import AxisWall, Frame, refine_line
from packages.vision.walls.types import PointPx, VectorizeResult, WallSegment

_OFFSETS: Final = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
_AXIS_TOL_DEG: Final = 5.0
"""Lệch trục tối đa còn ép về ngang/dọc (bước 7)."""
_MERGE_ANGLE_DEG: Final = 2.0
"""Lệch hướng tối đa giữa hai đoạn còn coi là thẳng hàng (bước 8)."""
_MIN_EPSILON: Final = 1.5
_EPSILON_RATIO: Final = 0.25
_SPUR_RATIO: Final = 2.0
"""Nhánh cụt dài hơn ngần này lần distance tại nút giao thì là tường thật (bước 4)."""
_SPUR_TIP_PX: Final = 1.7
"""Đầu tự do của râu thinning nằm trên điểm biên mặt nạ: distance ≤ ngần này (px) mới là râu.

`DIST_L2` mask 5 cho điểm biên 1,0 hay 1,4; tâm dải mảnh nhất còn sau phép mở `k ≥ 3`
có distance 2,0, vách 110 mm trên `render_plan` có 4,0-7,0. 1,7 nằm giữa khoảng trống
lượng tử (1,4; 2,0) nên không sát số đo nào. Tiêu chí tỉ lệ `T/J < 0,5` cũ cắt nhầm vách
110 mm chạm tường bao 220 mm (T/J = 0,40) và mọi vách rất mảnh chạm tường rất dày (NO-288).
"""
_AXIS_SHARE: Final = 0.85
"""Bản vẽ có ≥ ngần này tổng độ dài tường ngang/dọc thì coi là bản vẽ vuông góc (bước 7, 10b)."""
_AXIS_OFFSET_RATIO: Final = 1.0
"""Bản vẽ vuông góc: hai đầu lệch ngang ≤ ngần này lần bề dày đoạn thì ép trục, bất kể góc (bước 7).

Nút giao (cột tô đặc, cụm giao) có trọng tâm lệch khỏi tim tường tới ½ bề dày, cột to hơn tường
áp mặt thì (cột - tường)/2: đoạn 1,2 m của tường 300 mm nghiêng ~7° dù tường thật thẳng trục.
Tường chéo thật lệch ngang gấp nhiều lần bề dày (tường 1,5 m lệch 1 m, tường 300 mm).
"""
_AXIS_OFFSET_SLOPE: Final = 0.5
"""Luật lệch ngang chỉ áp khi lệch ngang ≤ ngần này lần phần dọc trục (≈ 26,6°, bước 7).

Đoạn gần 45° ngắn cỡ bề dày là vát góc DP cắt qua cột/khối giao: để `_absorb_corner_diagonals`
xử lý theo nút, ép trục nó chỉ đẻ thêm mẩu ngang/dọc chồng lên góc.
"""
_CORNER_DIAG_RATIO: Final = 3.0
"""Đoạn chéo ngắn hơn ngần này lần bề dày của nó trên bản vẽ vuông góc là vụn ở góc (bước 10b)."""
_DOMINANT_WINDOW_DEG: Final = 10.0
"""Đoạn lệch trục gần nhất ≤ ngần này mới góp vào ước lượng hướng chủ đạo của bản vẽ (bước 7a)."""
_DOMINANT_MIN_DEG: Final = 0.5
"""Hướng chủ đạo lệch trục ảnh dưới ngần này thì coi như thẳng ảnh, không xoay (bước 7a)."""
_DOMINANT_FAMILY_SHARE: Final = 0.15
"""Mỗi họ (gần ngang, gần dọc) phải chiếm ≥ ngần này độ dài mới xoay: thanh lẻ không có hệ trục riêng."""
_FREE_END_REACH_RATIO: Final = 1.5
"""Đầu mút riêng cách tim tường vuông góc ≤ ngần này lần bề dày lớn hơn thì đặt lên tim (bước 9b).

Tim tới tim 1,5 bề dày = hụt (lố) mặt tường tới 1 bề dày; khe cửa hẹp nhất (600 mm) gấp ≥ 2,7 lần
tường 220 mm nên đầu mút cạnh khe cửa không bị kéo qua khe.
"""
_LINE_CLUSTER_RATIO: Final = 0.5
"""Đoạn cùng trục có toạ độ tim cách nhau ≤ ngần này lần bề dày nhỏ nhất là một đường tường (bước 8b)."""
MAX_WALLS: Final = 20_000
"""Trần số tường của `WallsResult` (B5-01); `keep_longest` cắt về đúng trần này."""

_Key = tuple[int, int, int]
"""Khoá đầu mút dùng chung: `(0, node_id, 0)` cho nút, `(1, branch, vertex)` cho đỉnh DP."""


@dataclass(frozen=True, slots=True)
class _Graph:
    """Đồ thị xương đã dựng xong: toạ độ điểm, nút và nhánh.

    `node_of[i]` là id nút của điểm xương `i` (hay -1). `node_leaf` đánh dấu nút bậc ≤ 1 —
    chỉ nút này mới làm đầu cụt ở bước 4 và mới được kéo dài ở bước 9.
    """

    ys: NDArray[np.int32]
    xs: NDArray[np.int32]
    node_of: NDArray[np.int32]
    node_xy: NDArray[np.float64]
    node_leaf: NDArray[np.bool_]
    node_dist: NDArray[np.float64]
    branches: list[NDArray[np.int32]]


@dataclass(slots=True)
class _Seg:
    """Một đoạn đang dựng; toạ độ còn đổi qua các bước ép trục, gộp, đặt lại đầu mút."""

    ax: float
    ay: float
    bx: float
    by: float
    thickness: float
    conf: float
    a_key: _Key
    b_key: _Key
    axis: str = "d"
    fit_deg: float = math.nan
    """Góc (độ) đường thẳng khớp các điểm xương giữa đoạn (bỏ 1 bề dày mỗi đầu); `nan` khi quá ngắn."""

    def length(self) -> float:
        """Độ dài đường tim hiện tại."""
        return math.hypot(self.bx - self.ax, self.by - self.ay)


def _skeletonize(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Xương Zhang-Suen của mặt nạ; `skimage.morphology` chưa có chú kiểu nên bọc một chỗ.

    Chép sang bộ đệm ghi được vì `skeletonize` ghi tại chỗ, còn mặt nạ đáp án của
    `render_plan` là mảng chỉ đọc.
    """
    thinned = skeletonize(  # type: ignore[no-untyped-call]  # skimage chưa có chú kiểu
        np.array(mask, dtype=np.bool_),
        method="zhang",
    )
    return np.asarray(thinned, dtype=np.bool_)


def _validate(mask: NDArray[np.bool_]) -> None:
    """Biên tin cậy: chỉ nhận mảng bool 2 chiều; khác đi thì `ValueError` (bước 1)."""
    if mask.ndim != 2:
        raise ValueError(f"mặt nạ phải 2 chiều, nhận {mask.ndim} chiều")
    if mask.dtype != np.bool_:
        raise ValueError(f"mặt nạ phải kiểu bool, nhận {mask.dtype}")


def _neighbours(skel: NDArray[np.bool_]) -> tuple[NDArray[np.int32], NDArray[np.int32], NDArray[np.int32]]:
    """`(ys, xs, nbr)` của điểm xương; `nbr[i]` là 8 chỉ số láng giềng (-1 nếu trống)."""
    rows, cols = np.nonzero(skel)
    ys, xs = rows.astype(np.int32), cols.astype(np.int32)
    idx = np.full(skel.shape, -1, np.int32)
    idx[ys, xs] = np.arange(ys.size, dtype=np.int32)
    pad = np.pad(idx, 1, constant_values=-1)
    nbr = np.stack([pad[ys + 1 + dy, xs + 1 + dx] for dy, dx in _OFFSETS], axis=1)
    return ys, xs, nbr


def _label_nodes(
    shape: tuple[int, int],
    ys: NDArray[np.int32],
    xs: NDArray[np.int32],
    degree: NDArray[np.int32],
    dist: NDArray[np.float32],
) -> tuple[NDArray[np.int32], list[list[float]], list[bool], list[float]]:
    """Gộp cụm điểm giao kề nhau thành một nút ở trọng tâm; điểm bậc ≤ 1 thành nút riêng."""
    node_of = np.full(ys.size, -1, np.int32)
    junction = degree >= 3
    jmask = np.zeros(shape, np.uint8)
    jmask[ys[junction], xs[junction]] = 1
    count, labels = cv2.connectedComponents(jmask, connectivity=8)
    node_of[junction] = labels[ys[junction], xs[junction]] - 1
    lone = degree <= 1
    node_of[lone] = np.arange(count - 1, count - 1 + int(lone.sum()), dtype=np.int32)
    total = count - 1 + int(lone.sum())
    seen = node_of >= 0
    sizes = np.bincount(node_of[seen], minlength=total)
    cx = np.bincount(node_of[seen], weights=xs[seen], minlength=total) / sizes
    cy = np.bincount(node_of[seen], weights=ys[seen], minlength=total) / sizes
    radius = np.zeros(total, np.float64)
    np.maximum.at(radius, node_of[seen], dist[ys[seen], xs[seen]])
    leaf = np.zeros(total, np.bool_)
    leaf[node_of[lone]] = True
    return node_of, [[float(x), float(y)] for x, y in zip(cx, cy, strict=True)], leaf.tolist(), radius.tolist()


def _walk(start: int, first: int, node_of: NDArray[np.int32], nbr: NDArray[np.int32]) -> list[int]:
    """Đi theo chuỗi điểm bậc 2 từ `start` qua `first` tới nút kế tiếp; trả cả hai đầu."""
    path = [start, first]
    prev, cur = start, first
    while node_of[cur] < 0:
        step = next((int(c) for c in nbr[cur].tolist() if c >= 0 and c != prev), -1)
        if step < 0:
            break
        prev, cur = cur, step
        path.append(step)
    return path


def _trace_branches(node_of: NDArray[np.int32], nbr: NDArray[np.int32]) -> list[NDArray[np.int32]]:
    """Mọi nhánh giữa hai nút, mỗi nhánh đúng một lần (đánh dấu cả chiều ngược lại)."""
    used: set[tuple[int, int]] = set()
    branches: list[NDArray[np.int32]] = []
    for point in np.flatnonzero(node_of >= 0).tolist():
        for step in nbr[point].tolist():
            same_node = step >= 0 and node_of[step] >= 0 and node_of[step] == node_of[point]
            if step < 0 or same_node or (point, step) in used:
                continue
            path = _walk(point, step, node_of, nbr)
            used.add((point, step))
            used.add((path[-1], path[-2]))
            branches.append(np.asarray(path, np.int32))
    return branches


def _close_loops(
    node_of: NDArray[np.int32],
    nbr: NDArray[np.int32],
    branches: list[NDArray[np.int32]],
    nodes: tuple[list[list[float]], list[bool], list[float]],
    points: tuple[NDArray[np.int32], NDArray[np.int32]],
    dist: NDArray[np.float32],
) -> None:
    """Vòng kín không nút: lấy điểm `(y, x)` nhỏ nhất làm nút rồi đi hết vòng (bước 3).

    Chỉ chuỗi bậc 2 mới còn sót lại ở đây; điểm đã là nút mà không nhánh nào chạm tới là
    cụm xương cô lập (ô vuông nhỏ), `_lonely_clusters` đếm nó vào `short` ở bước 10.
    """
    node_xy, leaf, radius = nodes
    ys, xs = points
    covered = node_of >= 0
    for path in branches:
        covered[path] = True
    rest = np.flatnonzero(~covered)
    while rest.size:
        seed = int(rest[0])
        node_of[seed] = len(node_xy)
        node_xy.append([float(xs[seed]), float(ys[seed])])
        leaf.append(False)
        radius.append(float(dist[ys[seed], xs[seed]]))
        step = next(int(c) for c in nbr[seed].tolist() if c >= 0)
        cycle = _walk(seed, step, node_of, nbr)
        covered[cycle] = True
        branches.append(np.asarray(cycle, np.int32))
        rest = np.flatnonzero(~covered)


def _build_graph(skel: NDArray[np.bool_], dist: NDArray[np.float32]) -> _Graph:
    """Dựng đồ thị xương đầy đủ (nút, nhánh, vòng kín) cho mặt nạ xương hiện tại."""
    ys, xs, nbr = _neighbours(skel)
    degree = (nbr >= 0).sum(axis=1).astype(np.int32)
    node_of, node_xy, leaf, radius = _label_nodes(skel.shape, ys, xs, degree, dist)
    branches = _trace_branches(node_of, nbr)
    _close_loops(node_of, nbr, branches, (node_xy, leaf, radius), (ys, xs), dist)
    return _Graph(
        ys=ys,
        xs=xs,
        node_of=node_of,
        node_xy=np.asarray(node_xy, np.float64).reshape(-1, 2),
        node_leaf=np.asarray(leaf, np.bool_),
        node_dist=np.asarray(radius, np.float64),
        branches=branches,
    )


def _path_length(graph: _Graph, path: NDArray[np.int32]) -> float:
    """Độ dài chuỗi điểm xương (tổng khoảng cách giữa các điểm liên tiếp)."""
    dx = np.diff(graph.xs[path].astype(np.float64))
    dy = np.diff(graph.ys[path].astype(np.float64))
    return float(np.hypot(dx, dy).sum())


def _is_spur(graph: _Graph, path: NDArray[np.int32]) -> bool:
    """Nhánh cụt: đúng một đầu là nút bậc ≤ 1, dài ≤ 2 x distance tại nút giao (bước 4).

    Thêm điều kiện đầu tự do nằm trên biên mặt nạ (`_SPUR_TIP_PX`): râu Zhang-Suen chạy ra
    góc nên đầu nó có distance ≈ 1; vách thật ngắn (cạnh khe cửa) dừng giữa bề dày của nó.
    """
    head, tail = int(graph.node_of[path[0]]), int(graph.node_of[path[-1]])
    if head == tail or graph.node_leaf[head] == graph.node_leaf[tail]:
        return False
    junction, tip = (tail, head) if graph.node_leaf[head] else (head, tail)
    if graph.node_dist[tip] > _SPUR_TIP_PX:
        return False
    return bool(_path_length(graph, path) <= _SPUR_RATIO * graph.node_dist[junction])


def _prune_spurs(skel: NDArray[np.bool_], dist: NDArray[np.float32]) -> tuple[_Graph, int]:
    """Bỏ nhánh cụt tới khi ổn định; trả đồ thị cuối và số nhánh đã bỏ."""
    spur = 0
    while True:
        graph = _build_graph(skel, dist)
        victims = [path for path in graph.branches if _is_spur(graph, path)]
        if not victims:
            return graph, spur
        for path in victims:
            node_id = graph.node_of[path]
            drop = path[(node_id < 0) | graph.node_leaf[node_id]]
            skel[graph.ys[drop], graph.xs[drop]] = False
        spur += len(victims)


def _lonely_clusters(skel: NDArray[np.bool_], graph: _Graph) -> int:
    """Cụm xương không còn nhánh nào sau bước 4 (khối vuông, cột) — đếm vào `short`."""
    count, labels = cv2.connectedComponents(skel.astype(np.uint8), connectivity=8)
    alive = {int(labels[graph.ys[path[0]], graph.xs[path[0]]]) for path in graph.branches}
    return count - 1 - len(alive)


def _vertex_positions(pts: NDArray[np.int32], approx: NDArray[np.int32]) -> list[int]:
    """Vị trí của từng đỉnh `approxPolyDP` trong chuỗi điểm gốc (DP luôn giữ lại điểm gốc).

    Tra bằng bảng chứ không quét tuần tự: chế độ khép kín trả đỉnh bắt đầu từ chỗ bất kỳ.
    """
    lookup: dict[tuple[int, int], int] = {}
    for position, point in enumerate(pts.tolist()):
        lookup.setdefault((point[0], point[1]), position)
    return [lookup[(int(vertex[0]), int(vertex[1]))] for vertex in approx]


def _confidence(mask: NDArray[np.bool_], start: tuple[float, float], end: tuple[float, float]) -> float:
    """Tỉ lệ mẫu mỗi 1 px dọc đường tim nằm trong mặt nạ (bước 6)."""
    height, width = mask.shape
    steps = max(2, int(math.dist(start, end)) + 1)
    ratio = np.linspace(0.0, 1.0, steps)
    sx = np.clip(np.rint(start[0] + (end[0] - start[0]) * ratio).astype(np.int32), 0, width - 1)
    sy = np.clip(np.rint(start[1] + (end[1] - start[1]) * ratio).astype(np.int32), 0, height - 1)
    return float(mask[sy, sx].mean())


def _vertex_keys(index: int, count: int, path: NDArray[np.int32], graph: _Graph, loop: bool) -> list[_Key]:
    """Khoá dùng chung của từng đỉnh: id nút ở hai đầu nhánh, vị trí đỉnh DP ở giữa.

    Vòng kín do `_close_loops` mở không dính nhánh nào khác nên mọi đỉnh dùng khoá đỉnh DP.
    """
    keys: list[_Key] = [(1, index, k) for k in range(count)]
    if not loop:
        keys[0] = (0, int(graph.node_of[path[0]]), 0)
        keys[-1] = (0, int(graph.node_of[path[-1]]), 0)
    return keys


def _vertex_coords(
    positions: list[int], path: NDArray[np.int32], graph: _Graph, loop: bool
) -> list[tuple[float, float]]:
    """Toạ độ từng đỉnh: trọng tâm nút ở hai đầu nhánh hở, điểm xương ở các đỉnh còn lại."""
    coords = [(float(graph.xs[path[i]]), float(graph.ys[path[i]])) for i in positions]
    if not loop:
        for slot, point in ((0, int(path[0])), (-1, int(path[-1]))):
            node = int(graph.node_of[point])
            coords[slot] = (float(graph.node_xy[node, 0]), float(graph.node_xy[node, 1]))
    return coords


def _vertex_pairs(count: int, loop: bool) -> list[tuple[int, int]]:
    """Cặp đỉnh của từng đoạn; vòng kín nối cả đỉnh cuối về đỉnh đầu."""
    if loop:
        return [(k, (k + 1) % count) for k in range(count)]
    return [(k, k + 1) for k in range(count - 1)]


def _branch_segments(
    index: int,
    path: NDArray[np.int32],
    graph: _Graph,
    dist: NDArray[np.float32],
    mask: NDArray[np.bool_],
) -> list[_Seg]:
    """Xấp xỉ một nhánh bằng `approxPolyDP` rồi đo bề dày và độ tin từng đoạn (bước 5-6).

    Vòng kín chạy DP ở chế độ khép kín: đỉnh đa giác khi đó không phụ thuộc điểm xuất
    phát, nếu không thì đúng cái góc nằm ở chỗ bắt đầu bị nuốt mất.
    """
    loop = bool(path[0] == path[-1]) and path.size > 2
    ring = path[:-1] if loop else path
    px, py = graph.xs[ring], graph.ys[ring]
    pts = np.stack([px, py], axis=1).astype(np.int32)
    thickness = 2.0 * dist[py, px].astype(np.float64)
    epsilon = max(_MIN_EPSILON, _EPSILON_RATIO * float(np.median(thickness)))
    approx = np.asarray(cv2.approxPolyDP(pts.reshape(-1, 1, 2), epsilon, loop), np.int32).reshape(-1, 2)
    positions = _vertex_positions(pts, approx)
    keys = _vertex_keys(index, len(positions), ring, graph, loop)
    coords = _vertex_coords(positions, ring, graph, loop)
    segments: list[_Seg] = []
    for head, tail in _vertex_pairs(len(positions), loop):
        i, j = positions[head], positions[tail]
        if i == j:
            continue
        span = thickness[i : j + 1] if i < j else np.concatenate((thickness[i:], thickness[: j + 1]))
        inner = pts[i : j + 1] if i < j else np.concatenate((pts[i:], pts[: j + 1]))
        segments.append(
            _Seg(
                ax=coords[head][0],
                ay=coords[head][1],
                bx=coords[tail][0],
                by=coords[tail][1],
                thickness=float(np.median(span)),
                conf=_confidence(mask, coords[head], coords[tail]),
                a_key=keys[head],
                b_key=keys[tail],
                fit_deg=_fit_deg(inner, float(np.median(span))),
            )
        )
    return segments


def _fit_deg(points: NDArray[np.int32], thickness: float) -> float:
    """Góc (độ) của `cv2.fitLine` qua điểm xương giữa đoạn, bỏ 1 bề dày mỗi đầu (bước 7a).

    Đầu mút đoạn là trọng tâm nút giao, lệch tim tới ½ bề dày: góc theo hai đầu của cạnh phòng 240 px
    xoay 2° ra 1,4°. Điểm xương giữa cạnh nằm trên tim nên khớp đúng góc. Còn < 5 điểm thì `nan`.
    """
    trim = math.ceil(thickness)
    inner = points[trim : len(points) - trim]
    if len(inner) < 5:
        return math.nan
    vx, vy = (float(v) for v in cv2.fitLine(inner.astype(np.float32), cv2.DIST_L2, 0, 0.01, 0.01).ravel()[:2])
    return math.degrees(math.atan2(vy, vx))


def _axis_of(seg: _Seg, offset_ratio: float) -> str:
    """Trục của đoạn: lệch ≤ 5°, hay lệch ngang ≤ `offset_ratio` x bề dày và ≤ ½ phần dọc trục."""
    dx, dy = abs(seg.bx - seg.ax), abs(seg.by - seg.ay)
    angle = math.degrees(math.atan2(dy, dx))
    reach = offset_ratio * seg.thickness
    if angle <= _AXIS_TOL_DEG or dy <= min(reach, _AXIS_OFFSET_SLOPE * dx):
        return "h"
    if angle >= 90.0 - _AXIS_TOL_DEG or dx <= min(reach, _AXIS_OFFSET_SLOPE * dy):
        return "v"
    return "d"


def _mostly_orthogonal(segs: list[_Seg], axes: list[str]) -> bool:
    """≥ `_AXIS_SHARE` tổng độ dài là đoạn ngang/dọc theo `axes` (cùng thứ tự với `segs`).

    Không tính đoạn chéo ngắn hơn `_CORNER_DIAG_RATIO` x bề dày: đó là vụn góc ở cột/khối giao, không
    phải dấu hiệu bản vẽ có tường chéo. Phòng nhỏ có cột to ở bốn góc từng có vụn chéo chiếm > 15 %.
    """
    counted = [
        (seg, axis)
        for seg, axis in zip(segs, axes, strict=True)
        if axis != "d" or seg.length() >= _CORNER_DIAG_RATIO * seg.thickness
    ]
    total = sum(seg.length() for seg, _ in counted)
    straight = sum(seg.length() for seg, axis in counted if axis != "d")
    return total > 0.0 and straight >= _AXIS_SHARE * total


def _snap_axes(segs: list[_Seg]) -> None:
    """Ép ngang/dọc tại toạ độ trung bình hai đầu; còn lại giữ góc (bước 7).

    Luật 5° luôn áp. Luật lệch ngang (`_AXIS_OFFSET_RATIO`) chỉ thêm khi bản vẽ đã vuông góc theo
    luật 5° (`_AXIS_SHARE`): bản vẽ có nhiều tường chéo/cong giữ nguyên như cũ, không bị nắn mẩu
    cung gần tiếp tuyến hay tường chéo ngắn. Đo tỉ lệ bằng luật 5° chứ không luật rộng để chính
    các mẩu nghiêng không tự kéo bản vẽ qua ngưỡng.
    """
    axes = [_axis_of(seg, 0.0) for seg in segs]
    if _mostly_orthogonal(segs, axes):
        axes = [_axis_of(seg, _AXIS_OFFSET_RATIO) for seg in segs]
    for seg, axis in zip(segs, axes, strict=True):
        seg.axis = axis
        if axis == "h":
            seg.ay = seg.by = (seg.ay + seg.by) / 2.0
        elif axis == "v":
            seg.ax = seg.bx = (seg.ax + seg.bx) / 2.0


def _dominant_angle(segs: list[_Seg]) -> float:
    """Góc (độ) của hệ trục riêng bản vẽ so với trục ảnh; 0 khi không xoay (bước 7a, UX41-A).

    Bản quét xoay 1-3° thì luật 5° ép từng đoạn về trục **ảnh** ở toạ độ trung bình, góc lệch
    nhau vài px. Lấy các đoạn dài (≥ 3 x bề dày) lệch trục gần nhất ≤ 10°: trung vị có trọng số độ
    dài (một tường chéo 10° không kéo cả bản vẽ), rồi trung bình trọng số các đoạn cách trung vị
    ≤ 1° cho mịn. Không xoay khi lệch < 0,5°, khi một họ ngang/dọc chiếm < 15 % (thanh lẻ) hay
    khi các đoạn gần trục chưa đủ `_AXIS_SHARE` tổng độ dài (bản vẽ không vuông góc).
    """
    near: list[tuple[float, float, int]] = []
    total = 0.0
    for seg in segs:
        length = seg.length()
        if length < _CORNER_DIAG_RATIO * seg.thickness:
            continue
        total += length
        angle = (
            seg.fit_deg if not math.isnan(seg.fit_deg) else math.degrees(math.atan2(seg.by - seg.ay, seg.bx - seg.ax))
        )
        tilt = (angle + 45.0) % 90.0 - 45.0
        if abs(tilt) <= _DOMINANT_WINDOW_DEG:
            near.append((tilt, length, round((angle - tilt) / 90.0) % 2))
    near_total = sum(length for _, length, _ in near)
    if not near or near_total < _AXIS_SHARE * total:
        return 0.0
    family_min = min(sum(length for _, length, fam in near if fam == family) for family in (0, 1))
    if family_min < _DOMINANT_FAMILY_SHARE * near_total:
        return 0.0
    ranked = sorted(near)
    acc = 0.0
    median = ranked[-1][0]
    for tilt, length, _ in ranked:
        acc += length
        if acc >= near_total / 2.0:
            median = tilt
            break
    close = [(tilt, length) for tilt, length, _ in near if abs(tilt - median) <= 1.0]
    angle = sum(tilt * length for tilt, length in close) / sum(length for _, length in close)
    return angle if abs(angle) >= _DOMINANT_MIN_DEG else 0.0


def _rotate(segs: list[_Seg], angle_deg: float, centre: tuple[float, float]) -> None:
    """Xoay tại chỗ mọi đầu mút quanh `centre` một góc `angle_deg` (độ, cùng chiều `atan2` của ảnh)."""
    if angle_deg == 0.0:
        return
    cos, sin = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
    cx, cy = centre
    for seg in segs:
        ax, ay, bx, by = seg.ax - cx, seg.ay - cy, seg.bx - cx, seg.by - cy
        seg.ax, seg.ay = cx + ax * cos - ay * sin, cy + ax * sin + ay * cos
        seg.bx, seg.by = cx + bx * cos - by * sin, cy + bx * sin + by * cos


def _line_value(seg: _Seg) -> float:
    """Toạ độ tim của đoạn đã ép trục: `y` của đoạn ngang, `x` của đoạn dọc."""
    return seg.ay if seg.axis == "h" else seg.ax


def _set_line(seg: _Seg, value: float) -> None:
    """Đặt toạ độ tim của đoạn đã ép trục (cả hai đầu)."""
    if seg.axis == "h":
        seg.ay = seg.by = value
    else:
        seg.ax = seg.bx = value


def _cluster_lines(segs: list[_Seg]) -> None:
    """Bước 8b: đoạn ngang (dọc) có tim cách nhau ≤ ½ bề dày nhỏ nhất → một đường, một toạ độ.

    Không cần chung đầu mút: hai bên khe cửa, hai phòng trên cùng một trục lưới. Xếp theo toạ độ,
    cụm mới khi cách đoạn **đầu** cụm quá ngưỡng (không nối chuỗi trôi dần); toạ độ chung là trung bình
    trọng số độ dài. Hai tường song song cách nhau một bề dày vượt ngưỡng nên vẫn tách.
    """
    for axis in ("h", "v"):
        group: list[_Seg] = []
        for seg in [*sorted((s for s in segs if s.axis == axis), key=_line_value), None]:
            if group and (
                seg is None
                or _line_value(seg) - _line_value(group[0])
                > _LINE_CLUSTER_RATIO * min(member.thickness for member in [*group, seg])
            ):
                value = _weighted(group, [_line_value(m) for m in group], [m.length() for m in group])
                for member in group:
                    _set_line(member, value)
                group = []
            if seg is not None:
                group.append(seg)


def _snap_free_ends(shared: dict[_Key, list[tuple[_Seg, bool]]], segs: list[_Seg]) -> None:
    """Bước 9b: đầu mút riêng của đoạn ngang/dọc hụt mặt tường vuông góc ≤ 1 bề dày → đặt lên tim đó.

    Lố qua tim chỉ cắt khi đầu mút còn trong thân tường (≤ ½ tổng hai bề dày, vụn kéo lá ở bước 9):
    mẩu tường dài hơn thế sau chữ T là vách thật tới mép khe cửa (seed 104 của `render_plan`).

    Chữ T có nút bị `_fuse` nuốt vào tường xuyên, đầu lá đã kéo ở bước 9, góc L hở: đầu mút còn cách
    giao điểm vài px. Chỉ xét tường vuông góc mà tầm (nới `_FREE_END_REACH_RATIO` bề dày) phủ đầu mút;
    chọn tim gần nhất; không dời nếu đoạn đổi chiều hay thành dài 0.
    """
    # Chỉ mục tim theo trục: mỗi đầu mút chỉ xét tường vuông góc có tim trong tầm lớn nhất, không quét cả
    # `segs` (lưới 141x150 thanh: 21 150 đoạn, O(n²) mất 38 s). Tim không đổi trong vòng lặp: `_set_end` chỉ
    # dời đầu mút dọc theo đoạn. Hoà khoảng cách thì giữ tường đứng trước trong `segs` như bản quét cũ.
    by_axis: dict[str, list[tuple[float, int, _Seg]]] = {"h": [], "v": []}
    for index, wall in enumerate(segs):
        if wall.axis in by_axis:
            by_axis[wall.axis].append((_line_value(wall), index, wall))
    lines = {axis: [item[0] for item in sorted(items)] for axis, items in by_axis.items()}
    walls = {axis: sorted(items) for axis, items in by_axis.items()}
    thickest = max((seg.thickness for seg in segs), default=0.0)
    for ends in shared.values():
        if len(ends) != 1 or ends[0][0].axis == "d":
            continue
        seg, head = ends[0]
        point = [seg.ax, seg.ay] if head else [seg.bx, seg.by]
        anchor = (seg.bx, seg.by) if head else (seg.ax, seg.ay)
        along = 1 if seg.axis == "v" else 0
        other = "h" if seg.axis == "v" else "v"
        widest = max(0.5 * (seg.thickness + thickest), _FREE_END_REACH_RATIO * max(seg.thickness, thickest))
        lo = bisect.bisect_left(lines[other], point[along] - widest)
        hi = bisect.bisect_right(lines[other], point[along] + widest)
        best: tuple[float, int, float] | None = None
        for line, index, wall in walls[other][lo:hi]:
            overshoot = (line - anchor[along]) * (point[along] - line) > 0.0
            reach = (
                0.5 * (seg.thickness + wall.thickness)
                if overshoot
                else _FREE_END_REACH_RATIO * max(seg.thickness, wall.thickness)
            )
            low, high = sorted(((wall.ax, wall.ay)[1 - along], (wall.bx, wall.by)[1 - along]))
            gap = abs(point[along] - line)
            covered = low - reach <= point[1 - along] <= high + reach
            if covered and 0.0 < gap <= reach and (best is None or (gap, index) < best[:2]):
                best = (gap, index, line)
        if best is None or (point[along] - anchor[along]) * (best[2] - anchor[along]) <= 0.0:
            continue
        point[along] = best[2]
        _set_end(seg, head, (point[0], point[1]))


def _direction(seg: _Seg) -> tuple[float, float]:
    """Vector đơn vị hướng đoạn; đoạn suy biến trả `(1, 0)` để phép chiếu vẫn xác định."""
    dx, dy = seg.bx - seg.ax, seg.by - seg.ay
    norm = math.hypot(dx, dy)
    return (1.0, 0.0) if norm == 0.0 else (dx / norm, dy / norm)


def _collinear(one: _Seg, other: _Seg) -> bool:
    """Thẳng hàng: lệch hướng ≤ 2° và lệch ngang ≤ ½ bề dày lớn hơn (bước 8)."""
    ux, uy = _direction(one)
    vx, vy = _direction(other)
    if math.degrees(math.acos(min(1.0, abs(ux * vx + uy * vy)))) > _MERGE_ANGLE_DEG:
        return False
    mx, my = (other.ax + other.bx) / 2.0, (other.ay + other.by) / 2.0
    offset = abs((mx - one.ax) * uy - (my - one.ay) * ux)
    return offset <= 0.5 * max(one.thickness, other.thickness)


def _root(parent: list[int], item: int) -> int:
    """Đại diện nhóm trong union-find (có nén đường đi)."""
    while parent[item] != item:
        parent[item] = parent[parent[item]]
        item = parent[item]
    return item


def _groups(segs: list[_Seg]) -> list[list[_Seg]]:
    """Gom các đoạn chung nút và thẳng hàng thành một nhóm (tường liền qua chữ T, chữ +)."""
    parent = list(range(len(segs)))
    incident: defaultdict[_Key, list[int]] = defaultdict(list)
    for i, seg in enumerate(segs):
        incident[seg.a_key].append(i)
        incident[seg.b_key].append(i)
    for members in incident.values():
        for i, j in itertools.combinations(members, 2):
            if _collinear(segs[i], segs[j]):
                parent[_root(parent, i)] = _root(parent, j)
    buckets: defaultdict[int, list[_Seg]] = defaultdict(list)
    for i, seg in enumerate(segs):
        buckets[_root(parent, i)].append(seg)
    return list(buckets.values())


def _weighted(members: list[_Seg], values: list[float], weights: list[float]) -> float:
    """Trung bình có trọng số độ dài; nhóm suy biến (tổng độ dài 0) lấy trung bình thường."""
    total = sum(weights)
    if total == 0.0:
        return sum(values) / len(members)
    return sum(v * w for v, w in zip(values, weights, strict=True)) / total


def _fuse(members: list[_Seg]) -> _Seg:
    """Một nhóm thẳng hàng → một đoạn xuyên nút; toạ độ trục lấy trung bình trọng số độ dài."""
    lead = max(members, key=_Seg.length)
    ux, uy = _direction(lead)
    ends = [(s.ax, s.ay, s.a_key) for s in members] + [(s.bx, s.by, s.b_key) for s in members]
    projected = sorted(ends, key=lambda e: e[0] * ux + e[1] * uy)
    (ax, ay, a_key), (bx, by, b_key) = projected[0], projected[-1]
    weights = [s.length() for s in members]
    fused = _Seg(
        ax=ax,
        ay=ay,
        bx=bx,
        by=by,
        thickness=_weighted(members, [s.thickness for s in members], weights),
        conf=_weighted(members, [s.conf for s in members], weights),
        a_key=a_key,
        b_key=b_key,
        axis=lead.axis,
    )
    if fused.axis == "h":
        fused.ay = fused.by = _weighted(members, [s.ay for s in members], weights)
    elif fused.axis == "v":
        fused.ax = fused.bx = _weighted(members, [s.ax for s in members], weights)
    return fused


def _resolve(alias: dict[_Key, _Key], key: _Key) -> _Key:
    """Khoá đại diện sau khi đã nhập các khoá của đoạn vát góc bị bỏ."""
    while key in alias:
        key = alias[key]
    return key


def _drop_short(segs: list[_Seg], graph: _Graph) -> tuple[list[_Seg], int]:
    """Bỏ đoạn ngắn hơn bề dày của nó (bước 10); trả số đoạn thật sự mất.

    Đoạn ngắn mà **hai** đầu đều nối đoạn khác chỉ là vát góc do `approxPolyDP` cắt
    khúc cua vuông: nó được hấp thụ (nhập hai khoá làm một để hai đầu kia gặp nhau ở
    giao điểm, bước 8) chứ không phải tường bị mất, nên không đếm vào `short`.
    Đoạn một đầu là lá riêng, đầu kia không phải lá được tính cả phần bước 9 sẽ kéo dài ở
    đầu lá (distance tại đó): vách ngắn chạm tường dày không bị bỏ chỉ vì xương hụt ½
    bề dày ở đầu tự do (NO-288).
    Nhập theo gốc nhóm như union-find: hai khoá đã chung nhóm (nhánh đi từ nút về chính nút
    đó cho đoạn có `a_key == b_key`, hay vài đoạn ngắn khép vòng) thì không nối nữa, nên
    `alias` không bao giờ có chu trình để `_resolve` quay mãi.
    """
    uses = Counter(key for seg in segs for key in (seg.a_key, seg.b_key))
    alias: dict[_Key, _Key] = {}
    keep: list[_Seg] = []
    short = 0
    for seg in segs:
        if seg.length() + _leaf_reach(seg, uses, graph) >= seg.thickness:
            keep.append(seg)
        elif uses[seg.a_key] > 1 and uses[seg.b_key] > 1:
            head, tail = _resolve(alias, seg.a_key), _resolve(alias, seg.b_key)
            if head != tail:
                alias[tail] = head
        else:
            short += 1
    for seg in keep:
        seg.a_key = _resolve(alias, seg.a_key)
        seg.b_key = _resolve(alias, seg.b_key)
    return keep, short


def _leaf_reach(seg: _Seg, uses: Counter[_Key], graph: _Graph) -> float:
    """Phần `_extend_leaves` sẽ kéo dài đoạn: distance tại đầu lá riêng khi đầu kia không phải lá.

    Đầu kia là nút giao hay đỉnh DP — kể cả nút giao chữ T mà `_fuse` đã nuốt khoá của tường
    xuyên nên chỉ còn đoạn này dùng. Đoạn cô lập (hai đầu đều lá) không được cộng, bỏ như cũ.
    """
    for leaf, other in ((seg.a_key, seg.b_key), (seg.b_key, seg.a_key)):
        other_is_leaf = other[0] == 0 and bool(graph.node_leaf[other[1]])
        if uses[leaf] == 1 and leaf[0] == 0 and graph.node_leaf[leaf[1]] and not other_is_leaf:
            return float(graph.node_dist[leaf[1]])
    return 0.0


def _ends_by_key(segs: list[_Seg]) -> dict[_Key, list[tuple[_Seg, bool]]]:
    """Mọi đầu mút theo khoá dùng chung; `True` nghĩa là đầu `a` của đoạn."""
    shared: defaultdict[_Key, list[tuple[_Seg, bool]]] = defaultdict(list)
    for seg in segs:
        shared[seg.a_key].append((seg, True))
        shared[seg.b_key].append((seg, False))
    return shared


def _set_end(seg: _Seg, head: bool, point: tuple[float, float]) -> None:
    """Gán toạ độ cho đầu `a` (khi `head`) hay đầu `b` của đoạn."""
    if head:
        seg.ax, seg.ay = point
    else:
        seg.bx, seg.by = point


def _shared_point(ends: list[tuple[_Seg, bool]], pin: tuple[float, float] | None = None) -> tuple[float, float]:
    """`x` của đoạn dọc, `y` của đoạn ngang có mặt tại nút; trục nào thiếu lấy `pin`, không thì trung bình.

    Lấy riêng từng toạ độ chứ không chỉ khi đủ cặp ngang + dọc: nút dọc + chéo mà lấy trung bình
    cả `x` thì đoạn dọc đã ép trục bị kéo lệch lại (K-02, vách lệch 2,6°). `_align_shared_axes`
    đã cho mọi đoạn ngang (dọc) chung nút cùng một `y` (`x`), nên đoạn nào cũng cho cùng giá trị.
    """
    horizontal = next((s for s, _ in ends if s.axis == "h"), None)
    vertical = next((s for s, _ in ends if s.axis == "v"), None)
    fallback = pin or (
        sum(s.ax if head else s.bx for s, head in ends) / len(ends),
        sum(s.ay if head else s.by for s, head in ends) / len(ends),
    )
    return (
        vertical.ax if vertical is not None else fallback[0],
        horizontal.ay if horizontal is not None else fallback[1],
    )


def _place_shared(shared: dict[_Key, list[tuple[_Seg, bool]]], pins: dict[_Key, tuple[float, float]]) -> None:
    """Đặt lại **mọi** đầu mút dùng chung (và đầu đã ghim ở bước 10b) sau khi ép trục và gộp (bước 8)."""
    for key, ends in shared.items():
        if len(ends) < 2 and key not in pins:
            continue
        point = _shared_point(ends, pins.get(key))
        for seg, head in ends:
            _set_end(seg, head, point)


def _align_shared_axes(segs: list[_Seg]) -> None:
    """Đoạn ngang (dọc) nối nhau qua đầu mút chung → cùng một `y` (`x`), trung bình trọng số độ dài.

    Hai đoạn ngang chỉ chung khoá sau khi `_drop_short`/bước 10b nhập khoá thì không qua `_fuse`,
    nên còn lệch nhau vài px; không gióng lại thì `_place_shared` kéo một đầu và đoạn ngắn hơn nghiêng.
    """
    for axis in ("h", "v"):
        lines = [seg for seg in segs if seg.axis == axis]
        parent = list(range(len(lines)))
        first: dict[_Key, int] = {}
        for i, seg in enumerate(lines):
            for key in (seg.a_key, seg.b_key):
                parent[_root(parent, i)] = _root(parent, first.setdefault(key, i))
        buckets: defaultdict[int, list[_Seg]] = defaultdict(list)
        for i, seg in enumerate(lines):
            buckets[_root(parent, i)].append(seg)
        for group in buckets.values():
            weights = [seg.length() for seg in group]
            if axis == "h":
                value = _weighted(group, [seg.ay for seg in group], weights)
                for seg in group:
                    seg.ay = seg.by = value
            else:
                value = _weighted(group, [seg.ax for seg in group], weights)
                for seg in group:
                    seg.ax = seg.bx = value


def _clash(members: list[_Seg]) -> bool:
    """Nhập nút sẽ ép hai đoạn ngang (dọc) cách nhau > ½ bề dày về cùng một đường: không được nhập."""
    for axis in ("h", "v"):
        lines = [seg for seg in members if seg.axis == axis]
        values = [seg.ay if axis == "h" else seg.ax for seg in lines]
        if lines and max(values) - min(values) > 0.5 * max(seg.thickness for seg in lines):
            return True
    return False


def _end_of(seg: _Seg, key: _Key, alias: dict[_Key, _Key]) -> tuple[float, float]:
    """Toạ độ đầu mút của `seg` mang khoá (đã quy về đại diện) `key`."""
    return (seg.ax, seg.ay) if _resolve(alias, seg.a_key) == key else (seg.bx, seg.by)


def _absorb_corner_diagonals(
    segs: list[_Seg], graph: _Graph
) -> tuple[list[_Seg], int, dict[_Key, tuple[float, float]]]:
    """Bước 10b: bản vẽ vuông góc → bỏ hay hấp thụ đoạn chéo ngắn (< 3 x bề dày) ở góc (K-02).

    Chỉ chạy khi ≥ 85 % tổng độ dài là ngang/dọc; tường chéo dài giữ nguyên. Từng đoạn, ngắn trước:
    - hai đầu đều nối đoạn khác → nhập hai khoá như vát góc của `_drop_short` (trừ khi `_clash`);
    - một đầu là nút giao không còn ai dùng (khoá chữ T đã bị `_fuse` nuốt) → các đoạn ở đầu kia
      dời sang khoá đó và ghim nó ở toạ độ cũ, để tường vẫn chạm tường xuyên;
    - một đầu tự do khác (lá, đỉnh DP mồ côi) → râu chéo, bỏ và đếm `short`;
    - không đầu nào nối → bỏ, đếm `short`.
    Trả các đoạn còn lại (khoá đã quy về đại diện), số đoạn bỏ và điểm ghim theo khoá.
    """
    if not _mostly_orthogonal(segs, [seg.axis for seg in segs]):
        return segs, 0, {}
    incident: defaultdict[_Key, list[_Seg]] = defaultdict(list)
    for seg in segs:
        incident[seg.a_key].append(seg)
        incident[seg.b_key].append(seg)
    alias: dict[_Key, _Key] = {}
    pins: dict[_Key, tuple[float, float]] = {}
    gone: set[int] = set()
    short = 0
    candidates = [seg for seg in segs if seg.axis == "d" and seg.length() < _CORNER_DIAG_RATIO * seg.thickness]
    for seg in sorted(candidates, key=_Seg.length):
        head, tail = _resolve(alias, seg.a_key), _resolve(alias, seg.b_key)
        if head == tail:
            continue
        near_head = [s for s in incident[head] if s is not seg]
        near_tail = [s for s in incident[tail] if s is not seg]
        if near_head and near_tail:
            # Đoạn nối thẳng cùng hai khoá sẽ thành dài 0 khi nhập; hai đường cùng trục lệch xa thì bị ép.
            if {id(s) for s in near_head} & {id(s) for s in near_tail} or _clash(near_head + near_tail):
                continue
            survivor, merged = head, tail
        elif near_head or near_tail:
            free = tail if near_head else head
            if free[0] == 0 and not graph.node_leaf[free[1]]:
                survivor, merged = free, (head if near_head else tail)
                pins[free] = _end_of(seg, free, alias)
            else:
                survivor = merged = free
        else:
            survivor = merged = head
        incident[head], incident[tail] = near_head, near_tail
        gone.add(id(seg))
        if survivor == merged:
            short += 1
            continue
        alias[merged] = survivor
        incident[survivor] = incident[survivor] + incident.pop(merged)
        if merged in pins:
            pins.setdefault(survivor, pins.pop(merged))
    keep = [seg for seg in segs if id(seg) not in gone]
    for seg in keep:
        seg.a_key = _resolve(alias, seg.a_key)
        seg.b_key = _resolve(alias, seg.b_key)
    return keep, short, pins


def _extend_leaves(shared: dict[_Key, list[tuple[_Seg, bool]]], graph: _Graph) -> None:
    """Đầu mút bậc 1 riêng của một đoạn: kéo dài thêm distance tại đó (bước 9).

    Xương Zhang-Suen dừng cách mặt tường ½ bề dày nên không kéo thì tường luôn ngắn hụt.
    """
    for key, ends in shared.items():
        if len(ends) != 1 or key[0] != 0 or not graph.node_leaf[key[1]]:
            continue
        seg, head = ends[0]
        ux, uy = _direction(seg)
        reach = float(graph.node_dist[key[1]])
        sign = -1.0 if head else 1.0
        base = (seg.ax, seg.ay) if head else (seg.bx, seg.by)
        _set_end(seg, head, (base[0] + sign * ux * reach, base[1] + sign * uy * reach))


def _clamp(point: tuple[float, float], shape: tuple[int, int]) -> PointPx:
    """Kẹp đầu mút vào `[0, w - 1] x [0, h - 1]` (bước 9)."""
    height, width = shape
    return (min(max(point[0], 0.0), width - 1.0), min(max(point[1], 0.0), height - 1.0))


def _finalise(segs: list[_Seg], shape: tuple[int, int]) -> tuple[tuple[WallSegment, ...], int]:
    """Kẹp biên, làm tròn, bỏ đoạn suy biến SAU làm tròn và sắp theo `(start, end)` (bước 9-11).

    Hai đoạn cùng hai đầu mút (hai nhánh xương song song giữa cùng hai nút, K-02) chỉ giữ một:
    độ tin cao hơn, hoà thì dày hơn. Không đếm vào `short` vì không mất tường nào.
    """
    walls: dict[tuple[int, int, int, int], WallSegment] = {}
    short = 0
    for seg in segs:
        a = _clamp((seg.ax, seg.ay), shape)
        b = _clamp((seg.bx, seg.by), shape)
        start = (round(a[0], 2), round(a[1], 2))
        end = (round(b[0], 2), round(b[1], 2))
        if start == end:  # so sau khi làm tròn: hai đầu lệch < 0.005 px thành trùng nhau
            short += 1
            continue
        if end < start:
            start, end = end, start
        wall = WallSegment(
            start=start,
            end=end,
            thickness_px=round(seg.thickness, 2),
            confidence=round(min(1.0, max(0.0, seg.conf)), 3),
        )
        # ponytail: lưới 1 px, cặp trùng nằm vắt qua mép ô làm tròn thì sót; cần thì so láng giềng.
        slot = (round(start[0]), round(start[1]), round(end[0]), round(end[1]))
        kept = walls.get(slot)
        if kept is None or (wall.confidence, wall.thickness_px) > (kept.confidence, kept.thickness_px):
            walls[slot] = wall
    return tuple(sorted(walls.values(), key=lambda w: (w.start, w.end))), short


def _refine_from_ink(segs: list[_Seg], gray: NDArray[np.uint8], frame: Frame) -> list[tuple[_Seg, float]]:
    """Bước 8c (UX41-B2): dời tim từng **đường** ngang/dọc về giữa nét mực; trả bề dày mực để gán sau.

    Chạy sau `_cluster_lines` nên các đoạn một đường có cùng toạ độ và dời cùng nhau, rồi `_place_shared`
    đặt lại mọi nút chung trên tim mới. Bề dày chỉ gán sau bước 9b vì tầm bắt đầu mút của `_snap_free_ends`
    đã chỉnh theo bề dày mặt nạ. Đoạn chéo và đường thiếu chứng cứ giữ nguyên (xem `ink_refine`).
    """
    lines: defaultdict[tuple[str, float], list[_Seg]] = defaultdict(list)
    for seg in segs:
        if seg.axis != "d":
            lines[(seg.axis, _line_value(seg))].append(seg)
    widths: list[tuple[_Seg, float]] = []
    for (axis, value), members in lines.items():
        walls = [
            AxisWall("h", value, min(m.ax, m.bx), max(m.ax, m.bx), m.thickness)
            if axis == "h"
            else AxisWall("v", value, min(m.ay, m.by), max(m.ay, m.by), m.thickness)
            for m in members
        ]
        fit = refine_line(gray, walls, frame)
        if fit is None:
            continue
        for member, width in zip(members, fit.thicknesses, strict=True):
            _set_line(member, fit.value)
            if width is not None:
                widths.append((member, width))
    return widths


def vectorize_with_stats(mask: NDArray[np.bool_], page_gray: NDArray[np.uint8] | None = None) -> VectorizeResult:
    """Vector hoá mặt nạ tường thành đoạn tim kèm số phần tử đã bỏ.

    `dropped` luôn có đủ hai khoá `spur` (nhánh cụt, bước 4) và `short` (đoạn ngắn hơn
    bề dày, hay cụm xương không còn nhánh, bước 10). Mặt nạ rỗng → không đoạn nào.
    Mảng không phải bool 2 chiều → `ValueError`. Có `page_gray` (ảnh xám `uint8` cùng khổ trang)
    thì tim và bề dày tường thẳng trục đọc lại từ nét mực (bước 8c); khác khổ → `ValueError`.
    """
    _validate(mask)
    if page_gray is not None and (page_gray.shape != mask.shape or page_gray.dtype != np.uint8):
        raise ValueError("page_gray phải là ảnh xám uint8 cùng khổ mặt nạ")
    if not mask.any():
        return VectorizeResult(walls=(), dropped={"spur": 0, "short": 0})
    dist: NDArray[np.float32] = np.asarray(cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5), np.float32)
    skel = _skeletonize(mask)
    graph, spur = _prune_spurs(skel, dist)
    short = _lonely_clusters(skel, graph)
    raw = [seg for index, path in enumerate(graph.branches) for seg in _branch_segments(index, path, graph, dist, mask)]
    tilt = _dominant_angle(raw)
    centre = ((mask.shape[1] - 1) / 2.0, (mask.shape[0] - 1) / 2.0)
    _rotate(raw, -tilt, centre)
    _snap_axes(raw)
    fused, tiny = _drop_short([_fuse(members) for members in _groups(raw)], graph)
    fused, corner, pins = _absorb_corner_diagonals(fused, graph)
    _align_shared_axes(fused)
    _cluster_lines(fused)
    widths = [] if page_gray is None else _refine_from_ink(fused, page_gray, Frame(tilt, centre))
    shared = _ends_by_key(fused)
    _place_shared(shared, pins)
    _extend_leaves(shared, graph)
    _snap_free_ends(shared, fused)
    for seg, width in widths:
        seg.thickness = width
    _rotate(fused, tilt, centre)
    walls, dropped_short = _finalise(fused, mask.shape)
    return VectorizeResult(walls=walls, dropped={"spur": spur, "short": short + tiny + corner + dropped_short})


def vectorize(mask: NDArray[np.bool_]) -> tuple[WallSegment, ...]:
    """Chỉ lấy các đoạn tường của `vectorize_with_stats` (bỏ phần thống kê)."""
    return vectorize_with_stats(mask).walls


def keep_longest(walls: Sequence[WallSegment], limit: int = MAX_WALLS) -> tuple[WallSegment, ...]:
    """Giữ `limit` đoạn dài nhất (hoà theo `(start, end)`), trả theo thứ tự `(start, end)`.

    Dùng khi số đoạn vượt trần `MAX_WALLS` của `WallsResult`: bỏ đoạn ngắn nhất trước.
    """
    if len(walls) <= limit:
        return tuple(walls)
    ranked = sorted(walls, key=lambda w: (-math.dist(w.start, w.end), w.start, w.end))
    return tuple(sorted(ranked[:limit], key=lambda w: (w.start, w.end)))
