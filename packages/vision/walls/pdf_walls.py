"""Tường đọc thẳng từ nét vector của PDF: tim thẳng tuyệt đối, bề dày đúng bằng khoảng cách hai mặt tường.

Đầu vào là `PdfPageVectors` (mọi đoạn thẳng của trang, point hiển thị) và một mặt nạ **bằng chứng**
cùng khổ ảnh dựng của trang (mặt nạ SegFormer của bước tường). Hình học lấy từ PDF, còn mặt nạ chỉ
làm trọng tài: mực nào là tường. Các bước:

1. Bỏ đoạn ngắn hơn `2 · bề dày nhỏ nhất`, gộp đoạn trùng (nét + cạnh vùng tô cùng chỗ).
2. Ghép **cặp đoạn song song** (lệch ≤ `_ANGLE_TOL_DEG`) cách nhau trong khoảng bề dày tường hợp lý
   và chồng nhau dọc trục ≥ `_MIN_OVERLAP_RATIO` lần khoảng cách — hình chữ nhật tô đặc cho cặp cạnh
   dài của nó, tường vẽ hai nét cho cặp mặt tường; nét gạch chéo (hatch) ngắn so với bề dày nên rớt.
3. Trọng tài: tỉ lệ điểm trên tim rơi vào mặt nạ ≥ `_MIN_AGREEMENT` (bỏ cặp đường kích thước, cặp
   mặt tường của hai phòng kề nhau, khe giữa hai tường).
4. Bỏ ứng viên chồng dải lên ứng viên tốt hơn (tường ba nét cho hai cặp), nối đoạn thẳng hàng cách
   nhau ≤ bề dày (mặt trong bị tường ngăn cắt ở chữ T), kéo/cắt đầu tường về tim tường vuông góc.

Bề dày cho phép lấy từ tỉ lệ `1:N` (tham số hay ghi chú `TL 1:N` trong lớp chữ PDF) — không có thì
dùng khoảng theo mm giấy rộng hơn. Trả `None` (người gọi lùi về đường raster) khi trang là ảnh quét
hay không đủ tường qua trọng tài.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from packages.vision.dimensions.lengths import parse_scale_note
from packages.vision.preprocess.pdf_vector import PdfPageVectors
from packages.vision.walls.types import WallSegment

__all__ = ["VectorWalls", "vector_walls"]

PT_PER_MM: Final = 72.0 / 25.4
WALL_MM_RANGE: Final = (60.0, 450.0)
"""Bề dày tường thật (mm) khi biết tỉ lệ: dưới vách 100 một chút tới trên tường 400; > 450 là cột."""
PAPER_MM_RANGE: Final = (0.4, 9.0)
"""Bề dày trên giấy (mm) khi không biết tỉ lệ: vách 100 ở 1:250 tới tường 450 ở 1:50."""
_ANGLE_TOL_DEG: Final = 0.5
_BIN_DEG: Final = 0.5
_MIN_OVERLAP_RATIO: Final = 2.0
_MIN_AGREEMENT: Final = 0.6
_MAX_IMAGE_RATIO: Final = 0.5
"""Ảnh nhúng phủ ≥ ngần này trang → PDF quét/ảnh trong PDF, không đọc nét."""
MIN_WALLS: Final = 4
"""Ít hơn ngần này tường qua trọng tài thì không tin đường vector (trang không phải mặt bằng vector)."""
_SAMPLES: Final = (8, 256)


@dataclass(frozen=True, slots=True)
class VectorWalls:
    """Tường theo pixel ảnh dựng của trang, tỉ lệ đã dùng, và số cặp ứng viên trước trọng tài."""

    walls: tuple[WallSegment, ...]
    scale_n: int | None
    candidates: int


@dataclass(slots=True)
class _Wall:
    """Tường đang dựng (point hiển thị): hướng đơn vị `u`, tim `offset` theo pháp tuyến, khoảng `s0..s1` dọc `u`."""

    u: tuple[float, float]
    offset: float
    s0: float
    s1: float
    thickness: float
    score: float

    @property
    def normal(self) -> tuple[float, float]:
        """Pháp tuyến đơn vị (xoay `u` 90°)."""
        return (-self.u[1], self.u[0])

    def point(self, s: float) -> tuple[float, float]:
        """Điểm trên tim tại toạ độ dọc trục `s`."""
        nx, ny = self.normal
        return (self.u[0] * s + nx * self.offset, self.u[1] * s + ny * self.offset)


def _thickness_range_pt(scale_n: int | None) -> tuple[float, float]:
    """Khoảng bề dày (point giấy) theo tỉ lệ `1:N`, hay theo mm giấy khi không biết tỉ lệ."""
    if scale_n is None:
        return PAPER_MM_RANGE[0] * PT_PER_MM, PAPER_MM_RANGE[1] * PT_PER_MM
    return WALL_MM_RANGE[0] / scale_n * PT_PER_MM, WALL_MM_RANGE[1] / scale_n * PT_PER_MM


def _clean(segments: NDArray[np.float64], min_len: float) -> NDArray[np.float64]:
    """Đoạn đủ dài, đầu mút xếp thứ tự và bỏ trùng (sai khác < 0,01 pt) — `(n, 4)`."""
    seg = segments[:, :4]
    seg = seg[np.hypot(seg[:, 2] - seg[:, 0], seg[:, 3] - seg[:, 1]) >= min_len]
    swap = (seg[:, 0] > seg[:, 2]) | ((seg[:, 0] == seg[:, 2]) & (seg[:, 1] > seg[:, 3]))
    seg[swap] = seg[swap][:, [2, 3, 0, 1]]
    return np.unique(np.round(seg, 2), axis=0)


def _pairs(seg: NDArray[np.float64], t_min: float, t_max: float) -> list[_Wall]:
    """Mọi cặp đoạn gần song song cách nhau `[t_min, t_max]` và chồng nhau đủ dài → ứng viên tường.

    Chia góc thành ngăn `_BIN_DEG`; mỗi ngăn so với chính nó và ngăn kế (vòng qua 180°) theo một hướng
    tham chiếu chung, nên lệch dấu pháp tuyến quanh 0°/180° không làm sai `offset`. Trong nhóm, xếp
    theo `offset` rồi `searchsorted` cửa sổ bề dày — không so mọi cặp.
    """
    theta = np.mod(np.arctan2(seg[:, 3] - seg[:, 1], seg[:, 2] - seg[:, 0]), np.pi)
    n_bins = round(180 / _BIN_DEG)
    bins = np.minimum((np.degrees(theta) / _BIN_DEG).astype(int), n_bins - 1)
    members: dict[int, list[int]] = defaultdict(list)
    for index, b in enumerate(bins.tolist()):
        members[b].append(index)
    seen: set[tuple[int, int]] = set()
    walls: list[_Wall] = []
    tol = math.radians(_ANGLE_TOL_DEG)
    for b in sorted(members):
        idx = np.asarray(members[b] + members.get((b + 1) % n_bins, []), dtype=np.int64)
        ref = math.radians((b + 0.5) * _BIN_DEG)
        u = (math.cos(ref), math.sin(ref))
        rho = (-u[1] * (seg[idx, 0] + seg[idx, 2]) + u[0] * (seg[idx, 1] + seg[idx, 3])) / 2
        pa = u[0] * seg[idx, 0] + u[1] * seg[idx, 1]
        pb = u[0] * seg[idx, 2] + u[1] * seg[idx, 3]
        s0, s1 = np.minimum(pa, pb), np.maximum(pa, pb)
        order = np.argsort(rho, kind="stable")
        idx, rho, s0, s1 = idx[order], rho[order], s0[order], s1[order]
        lo = np.searchsorted(rho, rho + t_min, side="left")
        hi = np.searchsorted(rho, rho + t_max, side="right")
        for k in np.flatnonzero(hi > lo).tolist():
            js = np.arange(lo[k], hi[k])
            gap = rho[js] - rho[k]
            start = np.maximum(s0[js], s0[k])
            end = np.minimum(s1[js], s1[k])
            dtheta = np.abs(theta[idx[js]] - theta[idx[k]])
            ok = (end - start >= _MIN_OVERLAP_RATIO * gap) & (np.minimum(dtheta, np.pi - dtheta) <= tol)
            for j in np.flatnonzero(ok).tolist():
                key = (min(int(idx[k]), int(idx[js[j]])), max(int(idx[k]), int(idx[js[j]])))
                if key not in seen:
                    seen.add(key)
                    walls.append(_wall_of(seg[key[0]], seg[key[1]]))
    return walls


def _wall_of(a: NDArray[np.float64], b: NDArray[np.float64]) -> _Wall:
    """Tường của cặp đoạn `a`, `b` theo **đúng** hướng trung bình của hai đoạn (không theo ngăn góc).

    Tim = trung bình hai đường, bề dày = khoảng cách hai đường theo pháp tuyến chung, khoảng = phần chồng.
    """
    da = (a[2] - a[0], a[3] - a[1])
    db = (b[2] - b[0], b[3] - b[1])
    if da[0] * db[0] + da[1] * db[1] < 0:
        db = (-db[0], -db[1])
    ux, uy = da[0] / math.hypot(*da) + db[0] / math.hypot(*db), da[1] / math.hypot(*da) + db[1] / math.hypot(*db)
    norm = math.hypot(ux, uy)
    u = (ux / norm, uy / norm)
    rho_a = (-u[1] * (a[0] + a[2]) + u[0] * (a[1] + a[3])) / 2
    rho_b = (-u[1] * (b[0] + b[2]) + u[0] * (b[1] + b[3])) / 2
    sa = sorted((u[0] * a[0] + u[1] * a[1], u[0] * a[2] + u[1] * a[3]))
    sb = sorted((u[0] * b[0] + u[1] * b[1], u[0] * b[2] + u[1] * b[3]))
    return _Wall(
        u, float(rho_a + rho_b) / 2, float(max(sa[0], sb[0])), float(min(sa[1], sb[1])), float(abs(rho_b - rho_a)), 0.0
    )


def _agreement(wall: _Wall, evidence: NDArray[np.bool_], sx: float, sy: float) -> float:
    """Tỉ lệ điểm mẫu trên tim (đổi sang pixel) rơi vào mặt nạ bằng chứng; ngoài ảnh tính là không."""
    height, width = evidence.shape
    length_px = (wall.s1 - wall.s0) * max(sx, sy)
    count = int(min(max(length_px, _SAMPLES[0]), _SAMPLES[1]))
    s = np.linspace(wall.s0, wall.s1, count)
    nx, ny = wall.normal
    xs = np.floor((wall.u[0] * s + nx * wall.offset) * sx).astype(int)
    ys = np.floor((wall.u[1] * s + ny * wall.offset) * sy).astype(int)
    inside = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    hits = np.zeros(count, dtype=bool)
    hits[inside] = evidence[ys[inside], xs[inside]]
    return float(hits.mean())


def _relative(a: _Wall, b: _Wall) -> tuple[float, float, float] | None:
    """`b` theo hệ của `a` khi hai tường gần song song: `(offset, s0, s1)` của `b`; không song song → `None`."""
    dot = a.u[0] * b.u[0] + a.u[1] * b.u[1]
    if abs(dot) < math.cos(math.radians(2.0)):
        return None
    pa, pb = b.point(b.s0), b.point(b.s1)
    nx, ny = a.normal
    offset = (nx * (pa[0] + pb[0]) + ny * (pa[1] + pb[1])) / 2
    sa = a.u[0] * pa[0] + a.u[1] * pa[1]
    sb = a.u[0] * pb[0] + a.u[1] * pb[1]
    return offset, min(sa, sb), max(sa, sb)


def _suppress(walls: list[_Wall]) -> list[_Wall]:
    """Giữ ứng viên tốt nhất (điểm trọng tài, rồi dài) khi dải hai ứng viên chồng nhau quá nửa chiều dài.

    ponytail: O(n · giữ lại); bản vẽ hàng nghìn tường vẫn nhanh, cần nhanh hơn thì chia lưới theo góc.
    """
    kept: list[_Wall] = []
    for wall in sorted(walls, key=lambda w: (-w.score, -(w.s1 - w.s0))):
        length = wall.s1 - wall.s0
        clash = False
        for other in kept:
            rel = _relative(other, wall)
            if rel is None:
                continue
            offset, s0, s1 = rel
            band = abs(offset - other.offset) < (wall.thickness + other.thickness) / 2 * 0.9
            if band and min(s1, other.s1) - max(s0, other.s0) > 0.5 * length:
                clash = True
                break
        if not clash:
            kept.append(wall)
    return kept


def _merge(walls: list[_Wall]) -> list[_Wall]:
    """Nối tường thẳng hàng, cùng bề dày (±15 %), cách nhau ≤ bề dày lớn hơn — lặp tới khi không nối được nữa."""
    merged = list(walls)
    changed = True
    while changed:
        changed = False
        for i, a in enumerate(merged):
            for j in range(i + 1, len(merged)):
                b = merged[j]
                rel = _relative(a, b)
                t = max(a.thickness, b.thickness)
                if rel is None or abs(a.thickness - b.thickness) > 0.15 * t or abs(rel[0] - a.offset) > 0.25 * t:
                    continue
                if max(rel[1], a.s0) - min(rel[2], a.s1) > t:
                    continue
                total = (a.s1 - a.s0) + (rel[2] - rel[1])
                thickness = (a.thickness * (a.s1 - a.s0) + b.thickness * (rel[2] - rel[1])) / total
                score = (a.score * (a.s1 - a.s0) + b.score * (rel[2] - rel[1])) / total
                merged[i] = _Wall(a.u, a.offset, min(a.s0, rel[1]), max(a.s1, rel[2]), thickness, score)
                del merged[j]
                changed = True
                break
            if changed:
                break
    return merged


def _close_corners(walls: list[_Wall]) -> None:
    """Kéo/cắt đầu tường về tim tường cắt ngang khi đầu nằm trong dải bề dày của tường đó (góc L, chữ T).

    Hình chữ nhật tô đặc chồng góc cho đầu tường ở mặt ngoài; tường hai nét dừng ở mặt trong — cả hai
    đều lệch tim tường kia ≤ một bề dày. Chỉ dời đầu dọc trục của chính nó nên tim vẫn thẳng.
    """
    for wall in walls:
        for end in ("s0", "s1"):
            s = getattr(wall, end)
            px, py = wall.point(s)
            best: float | None = None
            for other in walls:
                cross = wall.u[0] * other.normal[0] + wall.u[1] * other.normal[1]
                if other is wall or abs(cross) < math.sin(math.radians(60.0)):
                    continue
                dist = other.normal[0] * px + other.normal[1] * py - other.offset
                along = other.u[0] * px + other.u[1] * py
                reach = other.thickness
                if abs(dist) > other.thickness or not other.s0 - reach <= along <= other.s1 + reach:
                    continue
                target = s - dist / cross
                if best is None or abs(target - s) < abs(best - s):
                    best = target
            if best is not None and (end == "s0" and best < wall.s1 or end == "s1" and best > wall.s0):
                setattr(wall, end, best)


def vector_walls(
    vectors: PdfPageVectors,
    *,
    width_px: int,
    height_px: int,
    evidence: NDArray[np.bool_],
    scale_n: int | None = None,
) -> VectorWalls | None:
    """Tường của trang vector theo pixel ảnh dựng `width_px x height_px`; `None` = lùi về đường raster.

    `evidence` là mặt nạ tường cùng khổ ảnh dựng (SegFormer). `scale_n` thiếu thì đọc `TL 1:N` trong
    lớp chữ PDF. `None` khi ảnh nhúng phủ ≥ `_MAX_IMAGE_RATIO` trang hay ít hơn `MIN_WALLS` tường qua
    trọng tài. Cùng đầu vào → cùng kết quả (không ngẫu nhiên, thứ tự xếp ổn định).
    """
    if vectors.image_ratio >= _MAX_IMAGE_RATIO or evidence.shape != (height_px, width_px):
        return None
    if scale_n is None:
        scale_n = parse_scale_note([vectors.text])
    t_min, t_max = _thickness_range_pt(scale_n)
    seg = _clean(vectors.segments, _MIN_OVERLAP_RATIO * t_min)
    candidates = _pairs(seg, t_min, t_max)
    sx, sy = width_px / vectors.width_pt, height_px / vectors.height_pt
    for wall in candidates:
        wall.score = _agreement(wall, evidence, sx, sy)
    judged = [w for w in candidates if w.score >= _MIN_AGREEMENT]
    walls = _merge(_suppress(judged))
    if len(walls) < MIN_WALLS:
        return None
    _close_corners(walls)
    out = []
    for wall in sorted(walls, key=lambda w: (round(w.point(w.s0)[1], 2), round(w.point(w.s0)[0], 2))):
        (x0, y0), (x1, y1) = wall.point(wall.s0), wall.point(wall.s1)
        out.append(
            WallSegment(
                start=(round(x0 * sx, 2), round(y0 * sy, 2)),
                end=(round(x1 * sx, 2), round(y1 * sy, 2)),
                thickness_px=round(wall.thickness * (sx + sy) / 2, 2),
                confidence=round(min(1.0, wall.score), 3),
            )
        )
    return VectorWalls(walls=tuple(out), scale_n=scale_n, candidates=len(candidates))
