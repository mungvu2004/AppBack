"""Nắn tim và bề dày tường theo chính nét mực của trang (UX41-B2, U19).

Bề dày của `vectorize` là `2 x distanceTransform` trên mặt nạ: tường vẽ bằng hai nét viền thì đó là
mép ngoài tới mép ngoài, dày hơn thật đúng một bề rộng nét (240 mm đo ra ~272 mm, bắt bậc 300). Bản vẽ
ghi kích thước tường từ **tim nét tới tim nét**, nên đọc lại trên ảnh xám: cắt vài lát ngang tường ở
60 % giữa đường, tìm cặp nét viền (hay một dải tô đặc), lấy trung vị khi các lát đồng thuận.

Chỉ dùng `numpy` + `cv2`, không biết `_Seg` của `vectorize` (tránh nhập vòng): đầu vào là đường
tường thẳng trục trong hệ trục **của bản vẽ** (`Frame` quay về toạ độ ảnh). Không đủ chứng cứ thì
trả `None` để tường giữ nguyên số đo mặt nạ.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

__all__ = ["AxisWall", "Frame", "LineFit", "fit_profile", "refine_line"]

_MID_SHARE: Final = 0.6
"""Chỉ lấy lát cắt trong ngần này phần giữa chiều dài: hai đầu là nút giao, cột, khe cửa."""
_PROFILES: Final = 9
"""Số lát cắt tối đa mỗi đoạn; mỗi lát là trung bình `_ROWS_PER_PROFILE` hàng liền nhau (bớt nhiễu JPEG)."""
_ROWS_PER_PROFILE: Final = 2
_STEP_PX: Final = 0.5
"""Bước lấy mẫu ngang tường (px), nội suy song tuyến; mép nét nội suy tiếp nên sai số dưới 0,5 px."""
_MIN_PROFILES: Final = 3
_AGREE_SHARE: Final = 0.6
"""Ít nhất ngần này phần số lát (kể cả lát hỏng) phải khớp trung vị, không thì giữ số đo mặt nạ."""
_TOL_PX: Final = 1.0
_TOL_RATIO: Final = 0.15
"""Sai lệch cho phép giữa các lát: `max(_TOL_PX, _TOL_RATIO x bề dày mặt nạ)`."""
_MIN_CONTRAST: Final = 60.0
"""Giấy trừ mực tối nhất của lát (thang 0-255) dưới ngần này là trang nhạt/nhiễu: lát hỏng."""
_SPAN_RANGE: Final = (0.55, 1.45)
"""Mép ngoài tới mép ngoài của cách đọc phải nằm trong dải này lần bề dày mặt nạ."""
_MAX_SHIFT_RATIO: Final = 0.5
"""Tim mới lệch tim mặt nạ quá ngần này lần bề dày (nhỏ nhất của đường) thì không tin."""
_MAX_GROW_RATIO: Final = 1.25
"""Bề dày mực lớn hơn ngần này lần bề dày mặt nạ thì không tin (mặt nạ vốn đo dư)."""
_PAPER_PERCENTILE: Final = 90.0

type _Cand = tuple[float, float, float]
"""Một cách đọc của lát: `(|span - bề dày mặt nạ|, tim lệch, bề dày)`."""


@dataclass(frozen=True, slots=True)
class Frame:
    """Hệ trục bản vẽ: quay `tilt_deg` (độ, chiều `atan2` của ảnh) quanh `centre` thì về toạ độ ảnh."""

    tilt_deg: float
    centre: tuple[float, float]


@dataclass(frozen=True, slots=True)
class AxisWall:
    """Một đoạn tường thẳng trục trong hệ `Frame`: tim `value` (`y` của ngang, `x` của dọc), chạy `lo..hi`."""

    axis: Literal["h", "v"]
    value: float
    lo: float
    hi: float
    thickness: float


@dataclass(frozen=True, slots=True)
class LineFit:
    """Tim mới của cả đường và bề dày mới từng đoạn (`None`: đoạn đó giữ bề dày mặt nạ)."""

    value: float
    thicknesses: tuple[float | None, ...]


def _runs(dark: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """Các dải `True` liền nhau `(đầu, cuối)` (cả hai đầu tính)."""
    edges = np.diff(np.concatenate(([0], dark.astype(np.int8), [0])))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1) - 1
    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def _crossing(profile: NDArray[np.float64], inside: int, outside: int, level: float) -> float:
    """Vị trí (theo số mẫu, có phần lẻ) mép nét cắt mức `level` giữa mẫu `inside` (tối) và `outside` (sáng).

    `inside < level <= outside` theo cách tách dải nên mẫu số dương và phần lẻ trong `(0, 1]`.
    """
    a, b = float(profile[inside]), float(profile[outside])
    return inside + (outside - inside) * (level - a) / (b - a)


def fit_profile(
    profile: NDArray[np.float64], offsets: NDArray[np.float64], thickness: float
) -> tuple[float, float] | None:
    """Một lát cắt → `(tim lệch, bề dày)` theo đơn vị của `offsets`; không đọc được thì `None`.

    Lát đứng một mình: lấy cách đọc có span gần bề dày mặt nạ nhất trong `_candidates`.
    """
    found = _candidates(profile, offsets, thickness)
    return None if not found else (min(found)[1], min(found)[2])


def _candidates(
    profile: NDArray[np.float64], offsets: NDArray[np.float64], thickness: float
) -> list[_Cand]:
    """Mọi cách đọc hợp lệ của một lát: `(|span - bề dày mặt nạ|, tim lệch, bề dày)`.

    Ngưỡng nửa sâu giữa giấy và mực tối nhất tách các dải tối. Ứng viên: một dải (tường tô đặc, bề dày
    là bề rộng dải) hay một cặp dải (tường viền hai nét, bề dày là khoảng **tim** hai nét, đúng cách bản
    vẽ ghi kích thước). Giữ ứng viên có mép ngoài-mép ngoài gần bề dày mặt nạ nhất, tim cách tim mặt nạ
    ≤ ½ bề dày: đường kích thước hay nét đồ đạc song song làm cặp rộng quá nên không kéo được tường.
    Dải chạm mép cửa sổ lấy mẫu bị cắt cụt nên không làm ứng viên.
    """
    paper = float(np.percentile(profile, _PAPER_PERCENTILE))
    ink = float(profile.min())
    if paper - ink < _MIN_CONTRAST:
        return []
    level = (paper + ink) / 2.0
    step = float(offsets[1] - offsets[0])
    last = len(profile) - 1
    bands: list[tuple[float, float, float]] = []
    for start, end in _runs(profile < level):
        if start == 0 or end == last:
            continue
        left = _crossing(profile, start, start - 1, level)
        right = _crossing(profile, end, end + 1, level)
        idx = np.arange(start, end + 1)
        weight = paper - profile[idx]
        centre = float(np.sum(weight * idx) / np.sum(weight))
        bands.append((left, right, centre))
    found: list[_Cand] = []
    for i, first in enumerate(bands):
        for second in bands[i:]:
            span = (second[1] - first[0]) * step
            if first is second:
                mid, width = (first[0] + first[1]) / 2.0, span
            else:
                mid, width = (first[2] + second[2]) / 2.0, (second[2] - first[2]) * step
            offset = float(offsets[0]) + mid * step
            if not _SPAN_RANGE[0] * thickness <= span <= _SPAN_RANGE[1] * thickness:
                continue
            if abs(offset) > 0.5 * thickness:
                continue
            found.append((abs(span - thickness), offset, width))
    return found


def _strip(gray: NDArray[np.uint8], wall: AxisWall, frame: Frame) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Ảnh xám lấy mẫu trên dải ±1 bề dày quanh 60 % giữa tường: `(hàng dọc tường x cột ngang tường, offsets)`."""
    length = wall.hi - wall.lo
    margin = 0.5 * (1.0 - _MID_SHARE) * length
    along = np.arange(wall.lo + margin, wall.hi - margin + 1e-9, 1.0)
    reach = math.ceil(wall.thickness)
    offsets = np.arange(-reach, reach + 1e-9, _STEP_PX)
    s, t = np.meshgrid(along, wall.value + offsets, indexing="ij")
    fx, fy = (s, t) if wall.axis == "h" else (t, s)
    cos, sin = math.cos(math.radians(frame.tilt_deg)), math.sin(math.radians(frame.tilt_deg))
    cx, cy = frame.centre
    ix = cx + (fx - cx) * cos - (fy - cy) * sin
    iy = cy + (fx - cx) * sin + (fy - cy) * cos
    sampled = cv2.remap(
        gray, ix.astype(np.float32), iy.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
    )
    return np.asarray(sampled, np.float64), offsets


def _profiles(gray: NDArray[np.uint8], wall: AxisWall, frame: Frame) -> tuple[list[tuple[float, float]], int]:
    """Kết quả đọc được của từng lát `(tim tuyệt đối, bề dày)` và tổng số lát đã cắt (kể cả lát hỏng)."""
    strip, offsets = _strip(gray, wall, frame)
    count = min(_PROFILES, strip.shape[0] // _ROWS_PER_PROFILE)
    if count < _MIN_PROFILES:
        return [], 0
    chunks = np.array_split(strip[: count * _ROWS_PER_PROFILE], count)
    per = [_candidates(chunk.mean(axis=0), offsets, wall.thickness) for chunk in chunks]
    flat = [cand for cands in per for cand in cands]
    if not flat:
        return [], count
    tol = max(_TOL_PX, _TOL_RATIO * wall.thickness)

    def near(cands: list[_Cand], ref: _Cand) -> list[_Cand]:
        return [c for c in cands if abs(c[1] - ref[1]) <= tol and abs(c[2] - ref[2]) <= tol]

    # Mặt nạ hay phủ cả nét đứt/nét kề song song nên "span gần mặt nạ nhất" từng lát dễ ghép nhầm cặp
    # (villa UX41: nét đứt + một nét tường). Cặp nét tường thật có ở gần mọi lát, nét đứt thì không:
    # neo vào cách đọc được nhiều lát ủng hộ nhất (hoà thì span gần mặt nạ nhất), mỗi lát lấy cách đọc gần neo.
    anchor = max(flat, key=lambda c: (sum(bool(near(cands, c)) for cands in per), -c[0]))
    fits: list[tuple[float, float]] = []
    for cands in per:
        pick = min(near(cands, anchor) or cands, default=None)
        if pick is not None:
            fits.append((wall.value + pick[1], pick[2]))
    return fits, count


def _consensus(fits: Sequence[tuple[float, float]], total: int, tol: float) -> tuple[float, float] | None:
    """Trung bình các lát khớp trung vị (cả tim lẫn bề dày lệch ≤ `tol`); quá ít lát khớp → `None`."""
    if not fits:
        return None
    centres = np.array([fit[0] for fit in fits])
    widths = np.array([fit[1] for fit in fits])
    inliers = (np.abs(centres - np.median(centres)) <= tol) & (np.abs(widths - np.median(widths)) <= tol)
    if int(inliers.sum()) < max(_MIN_PROFILES, math.ceil(_AGREE_SHARE * total)):
        return None
    return float(centres[inliers].mean()), float(widths[inliers].mean())


def refine_line(gray: NDArray[np.uint8], walls: Sequence[AxisWall], frame: Frame) -> LineFit | None:
    """Tim chung + bề dày từng đoạn của **một đường** tường (các đoạn cùng trục, cùng `value`).

    Tim lấy đồng thuận trên mọi lát của cả đường để các nút chung vẫn thẳng hàng; không đồng thuận hay
    dời quá ½ bề dày mặt nạ → `None` (cả đường giữ nguyên). Bề dày từng đoạn lấy đồng thuận trên lát của
    riêng đoạn đó và tim phải khớp tim chung; đoạn ngắn hay lệch thì `None` (giữ bề dày mặt nạ).
    """
    per_wall = [_profiles(gray, wall, frame) for wall in walls]
    smallest = min(wall.thickness for wall in walls)
    tol = max(_TOL_PX, _TOL_RATIO * smallest)
    # Cả đường chỉ cần đồng thuận về tim: vách 100 và tường 200 cùng một trục vẫn là một đường.
    pooled = [(centre, 0.0) for fits, _ in per_wall for centre, _ in fits]
    line = _consensus(pooled, sum(total for _, total in per_wall), tol)
    if line is None or abs(line[0] - walls[0].value) > _MAX_SHIFT_RATIO * smallest:
        # Cả đường không đồng thuận (lát nhiễu ở một đoạn): tim giữ nguyên, đoạn nào tự đồng thuận
        # quanh tim cũ vẫn lấy bề dày mực.
        line = (walls[0].value, 0.0)
    thicknesses: list[float | None] = []
    for wall, (fits, total) in zip(walls, per_wall, strict=True):
        own = _consensus(fits, total, max(_TOL_PX, _TOL_RATIO * wall.thickness))
        ok = own is not None and abs(own[0] - line[0]) <= tol and 0.0 < own[1] <= _MAX_GROW_RATIO * wall.thickness
        thicknesses.append(own[1] if ok and own is not None else None)
    if all(width is None for width in thicknesses) and line[0] == walls[0].value:
        return None
    return LineFit(value=line[0], thicknesses=tuple(thicknesses))
