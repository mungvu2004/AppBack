"""Hình học góc trang của #31/#32: kiểm góc người chọn, so góc, quy góc về trang chưa nắn.

Thuần tính toán trên tỉ lệ `[0, 1]` (hệ ảnh, y hướng xuống); không đụng DB hay ảnh.
"""

import math
from collections.abc import Mapping, Sequence
from typing import Final

import numpy as np

from apps.api.quality.errors import QUALITY_DRAWING_CHANGED
from packages.core.error_codes import VALIDATION
from packages.core.errors import AppError
from packages.vision.preprocess import Homography, VisionError

Ratios = tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
"""Bốn góc TL→TR→BR→BL theo tỉ lệ `[0, 1]` của trang."""

_MAX_CONDITION: Final = 1e12
_MIN_W: Final = 1e-9
_DIGITS: Final = 6


def _bad_corners() -> AppError:
    """Lỗi 422 `VALIDATION field="corners"` — một mã cho mọi luật vì FE chỉ tô lại vùng chọn."""
    return VALIDATION.error(field="corners")


def _is_pair(point: object) -> bool:
    """Điểm là cặp hai số hữu hạn (không bool)."""
    return (
        isinstance(point, tuple | list)
        and len(point) == 2
        and all(isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) for v in point)
    )


def _crosses(pts: Sequence[tuple[float, float]]) -> list[float]:
    """Bốn tích có hướng của các cặp cạnh liên tiếp (dương = rẽ phải trên hệ y hướng xuống)."""
    out = []
    for i in range(4):
        (ax, ay), (bx, by), (cx, cy) = pts[i], pts[(i + 1) % 4], pts[(i + 2) % 4]
        out.append((bx - ax) * (cy - by) - (by - ay) * (cx - bx))
    return out


def _area(pts: Sequence[tuple[float, float]]) -> float:
    """Diện tích tứ giác theo công thức dây giày (không dấu)."""
    total = sum(pts[i][0] * pts[(i + 1) % 4][1] - pts[(i + 1) % 4][0] * pts[i][1] for i in range(4))
    return abs(total) / 2.0


def validate_corner_ratios(points: Sequence[tuple[float, float]], *, min_area: float, eps: float) -> Ratios:
    """Kiểm 4 góc người chọn: trong `[0, 1]`, lồi không tự cắt, đúng thứ tự, đủ diện tích.

    Thứ tự bắt buộc TL→TR→BR→BL theo chiều kim đồng hồ và **không** tự sắp lại: FE đã sắp,
    góc lệch thứ tự là lỗi của client. Mọi vi phạm → 422 `VALIDATION field="corners"`.

    Điểm đầu là TL khi `x + y` của nó không quá `min(x + y)` của bốn điểm cộng `eps`. Dùng
    dung sai chứ không so sánh chặt vì tứ giác xoay 45° (hình thoi) có **hai** đỉnh hoà
    "trên-trái" (`(0.5, 0)` và `(0, 0.5)`): cả hai đều là cách bắt đầu hợp lệ theo chiều
    kim đồng hồ, và bắt một trong hai làm TL sẽ loại nhầm bản vẽ xoay (NO-227). `eps` là
    `QUALITY_CORNER_EPS`, truyền vào như `min_area` để hàm này thuần.
    """
    if len(points) != 4 or not all(_is_pair(p) for p in points):
        raise _bad_corners()
    pts = [(float(x), float(y)) for x, y in points]
    if not all(0.0 <= v <= 1.0 for p in pts for v in p):
        raise _bad_corners()
    if not all(c > 0 for c in _crosses(pts)):  # cùng dấu dương: lồi, không tự cắt, thuận chiều kim đồng hồ
        raise _bad_corners()
    sums = [x + y for x, y in pts]
    if sums[0] > min(sums) + eps:  # điểm đầu phải là TL (hoặc hoà TL trong `eps`)
        raise _bad_corners()
    if _area(pts) < min_area:
        raise _bad_corners()
    return (pts[0], pts[1], pts[2], pts[3])


def corners_match(a: Sequence[tuple[float, float]], b: Sequence[tuple[float, float]], eps: float) -> bool:
    """Hai bộ góc trùng nhau khi mọi toạ độ lệch ≤ `eps`; khác số điểm thì không trùng."""
    if len(a) != len(b):
        return False
    return all(abs(p - q) <= eps for pa, pb in zip(a, b, strict=True) for p, q in zip(pa, pb, strict=True))


def to_unrectified(ratios: Ratios, *, page_width_px: int, page_height_px: int, homography: Homography) -> Ratios:
    """Góc trên trang đang hiển thị → tỉ lệ trên trang **chưa nắn** (để không nắn chồng).

    Nhân nghịch đảo `homography.matrix` (chia toạ độ thuần nhất) rồi chia kích thước nguồn;
    kẹp `[0, 1]`, làm tròn 6 chữ số. Ma trận suy biến hoặc điểm ra vô cực →
    409 `QUALITY_DRAWING_CHANGED` (homography đã lưu không còn dùng được).
    """
    matrix = homography.as_array()
    if np.linalg.cond(matrix) > _MAX_CONDITION:  # ma trận suy biến cho cond = inf, nên `inv` dưới đây không ném
        raise QUALITY_DRAWING_CHANGED.error()
    inverse = np.linalg.inv(matrix)
    page = np.array([(x * page_width_px, y * page_height_px, 1.0) for x, y in ratios], dtype=np.float64)
    moved = page @ inverse.T
    w = moved[:, 2]
    if not np.all(np.isfinite(moved)) or np.any(np.abs(w) < _MIN_W):
        raise QUALITY_DRAWING_CHANGED.error()
    scale = np.array([homography.source_width_px, homography.source_height_px], dtype=np.float64)
    source = moved[:, :2] / w[:, None] / scale
    p = [(float(x), float(y)) for x, y in np.round(np.clip(source, 0.0, 1.0), _DIGITS).tolist()]
    return (p[0], p[1], p[2], p[3])


def parse_homography(data: Mapping[str, object]) -> Homography:
    """Homography đã lưu (JSON) → đối tượng; hỏng → 409 `QUALITY_DRAWING_CHANGED`, không phải 422."""
    try:
        return Homography.from_json(data)
    except VisionError as exc:
        raise QUALITY_DRAWING_CHANGED.error() from exc
