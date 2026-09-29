"""Vector hoá mặt nạ tường nhị phân thành các đoạn tim (B5-02 khối [6]).

Xương hoá Zhang-Suen rồi dựng đồ thị 8 hướng trên **điểm xương**: nút là điểm bậc 1
hoặc cụm điểm bậc ≥ 3 kề nhau, nhánh là chuỗi điểm bậc 2 giữa hai nút. Làm trên danh
sách điểm chứ không quét lưới nên chi phí theo số điểm xương, không theo số điểm ảnh (K28).
Bề dày lấy từ `distanceTransform` nên là số đo thật, **không** làm tròn về bộ chuẩn
(việc đó của B5-05). Gói không nhập `ml_contracts`/`apps.*`, không đọc biến môi trường.
Mọi bước chỉ phụ thuộc mặt nạ đầu vào nên kết quả tất định.
"""

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
_SPUR_TIP_RATIO: Final = 0.5
"""Đầu tự do của nhánh cụt phải mảnh hơn ngần này lần nút giao mới coi là râu thinning.

Đo trên `render_plan(104)`: đoạn tường thật cạnh khe cửa dài 28,4 px ≤ 2 x 16,0 nhưng đầu
tự do có distance 9,0 (mặt tường thật) nên giữ; râu ở chỗ nhô ra có distance 2,0 so với nút
giao 6,4 nên bỏ. Không có điều kiện này thì tường cạnh cửa biến mất (khối [8], khe ô mở).
"""
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

    def length(self) -> float:
        """Độ dài đường tim hiện tại."""
        return math.hypot(self.bx - self.ax, self.by - self.ay)


def _skeletonize(mask: NDArray[np.bool_]) -> NDArray[np.bool_]:
    """Xương Zhang-Suen của mặt nạ; `skimage.morphology` chưa có chú kiểu nên bọc một chỗ.

    Chép sang bộ đệm ghi được vì `skeletonize` ghi tại chỗ, còn mặt nạ đáp án của
    `render_plan` là mảng chỉ đọc.
    """
    thinned = skeletonize(np.array(mask, dtype=np.bool_), method="zhang")  # type: ignore[no-untyped-call]
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

    Thêm điều kiện đầu tự do phải nằm ở góc chứ không ở mặt tường (`_SPUR_TIP_RATIO`):
    đoạn tường thật còn lại cạnh một khe cửa cũng ngắn, bỏ nó là mất tường thật.
    """
    head, tail = int(graph.node_of[path[0]]), int(graph.node_of[path[-1]])
    if head == tail or graph.node_leaf[head] == graph.node_leaf[tail]:
        return False
    junction, tip = (tail, head) if graph.node_leaf[head] else (head, tail)
    if graph.node_dist[tip] >= _SPUR_TIP_RATIO * graph.node_dist[junction]:
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
            )
        )
    return segments


def _snap_axis(seg: _Seg) -> str:
    """Ép về ngang/dọc khi lệch trục ≤ 5°, tại toạ độ trung bình; > 5° giữ góc (bước 7)."""
    angle = math.degrees(math.atan2(abs(seg.by - seg.ay), abs(seg.bx - seg.ax)))
    if angle <= _AXIS_TOL_DEG:
        seg.ay = seg.by = (seg.ay + seg.by) / 2.0
        return "h"
    if angle >= 90.0 - _AXIS_TOL_DEG:
        seg.ax = seg.bx = (seg.ax + seg.bx) / 2.0
        return "v"
    return "d"


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


def _drop_short(segs: list[_Seg]) -> tuple[list[_Seg], int]:
    """Bỏ đoạn ngắn hơn bề dày của nó (bước 10); trả số đoạn thật sự mất.

    Đoạn ngắn mà **hai** đầu đều nối đoạn khác chỉ là vát góc do `approxPolyDP` cắt
    khúc cua vuông: nó được hấp thụ (nhập hai khoá làm một để hai đoạn kia gặp nhau ở
    giao điểm, bước 8) chứ không phải tường bị mất, nên không đếm vào `short`.
    """
    uses = Counter(key for seg in segs for key in (seg.a_key, seg.b_key))
    alias: dict[_Key, _Key] = {}
    keep: list[_Seg] = []
    short = 0
    for seg in segs:
        if seg.length() >= seg.thickness:
            keep.append(seg)
        elif uses[seg.a_key] > 1 and uses[seg.b_key] > 1:
            alias[seg.b_key] = seg.a_key
        else:
            short += 1
    for seg in keep:
        seg.a_key = _resolve(alias, seg.a_key)
        seg.b_key = _resolve(alias, seg.b_key)
    return keep, short


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


def _shared_point(ends: list[tuple[_Seg, bool]]) -> tuple[float, float]:
    """Giao điểm hai đường tim khi có cả ngang lẫn dọc, không thì trung bình các đầu mút."""
    horizontal = next((s for s, _ in ends if s.axis == "h"), None)
    vertical = next((s for s, _ in ends if s.axis == "v"), None)
    if horizontal is not None and vertical is not None:
        return (vertical.ax, horizontal.ay)
    return (
        sum(s.ax if head else s.bx for s, head in ends) / len(ends),
        sum(s.ay if head else s.by for s, head in ends) / len(ends),
    )


def _place_shared(shared: dict[_Key, list[tuple[_Seg, bool]]]) -> None:
    """Đặt lại **mọi** đầu mút dùng chung sau khi đã ép trục và gộp (bước 8)."""
    for ends in shared.values():
        if len(ends) < 2:
            continue
        point = _shared_point(ends)
        for seg, head in ends:
            _set_end(seg, head, point)


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
    """Kẹp biên, bỏ đoạn suy biến, làm tròn và sắp theo `(start, end)` (bước 9-11)."""
    walls: list[WallSegment] = []
    short = 0
    for seg in segs:
        start = _clamp((seg.ax, seg.ay), shape)
        end = _clamp((seg.bx, seg.by), shape)
        if start == end:
            short += 1
            continue
        if end < start:
            start, end = end, start
        walls.append(
            WallSegment(
                start=(round(start[0], 2), round(start[1], 2)),
                end=(round(end[0], 2), round(end[1], 2)),
                thickness_px=round(seg.thickness, 2),
                confidence=round(min(1.0, max(0.0, seg.conf)), 3),
            )
        )
    return tuple(sorted(walls, key=lambda w: (w.start, w.end))), short


def vectorize_with_stats(mask: NDArray[np.bool_]) -> VectorizeResult:
    """Vector hoá mặt nạ tường thành đoạn tim kèm số phần tử đã bỏ.

    `dropped` luôn có đủ hai khoá `spur` (nhánh cụt, bước 4) và `short` (đoạn ngắn hơn
    bề dày, hay cụm xương không còn nhánh, bước 10). Mặt nạ rỗng → không đoạn nào.
    Mảng không phải bool 2 chiều → `ValueError`.
    """
    _validate(mask)
    if not mask.any():
        return VectorizeResult(walls=(), dropped={"spur": 0, "short": 0})
    dist: NDArray[np.float32] = np.asarray(cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 5), np.float32)
    skel = _skeletonize(mask)
    graph, spur = _prune_spurs(skel, dist)
    short = _lonely_clusters(skel, graph)
    raw = [seg for index, path in enumerate(graph.branches) for seg in _branch_segments(index, path, graph, dist, mask)]
    for seg in raw:
        seg.axis = _snap_axis(seg)
    fused, tiny = _drop_short([_fuse(members) for members in _groups(raw)])
    shared = _ends_by_key(fused)
    _place_shared(shared)
    _extend_leaves(shared, graph)
    walls, dropped_short = _finalise(fused, mask.shape)
    return VectorizeResult(walls=walls, dropped={"spur": spur, "short": short + tiny + dropped_short})


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
