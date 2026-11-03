"""Diện tích bằng công thức dây giày, cho **cùng con số** với `src/domain/rooms/area.ts`.

Hai luật của FE: cộng bằng mm² nguyên rồi đổi đơn vị một lần; làm tròn một lần, ở
cuối, về hai chữ số, nửa làm tròn lên như `Math.round`. `round()` dựng sẵn làm tròn
kiểu ngân hàng và `Decimal` tính đúng hơn FE, nên cả hai cho số khác FE; ở đây giữ
nguyên phép tính số thực của FE rồi mới đổi sang `Decimal` (cột `numeric(12,2)`).
"""

import math
from collections.abc import Iterable, Sequence
from decimal import Decimal
from itertools import pairwise
from statistics import median
from typing import Final

from packages.domain.spatial.model import MAX_SAFE_INTEGER, Point, Wall

_MM2_PER_M2: Final = 1_000_000
_AREA_ROUNDING: Final = 100
_CENTI: Final = Decimal("0.01")
_PARALLEL_SIN: Final = 0.09
"""Tường "nằm trên" một cạnh phòng khi lệch hướng ≤ ~5° (sin) và cách cạnh ≤ một bề dày tường."""


def js_round(x: float) -> int:
    """`Math.round` của JS: số nguyên gần nhất, nửa làm tròn về phía +∞; `ValueError` khi không hữu hạn.

    Không dùng `math.floor(x + 0.5)`: phép cộng tự làm tròn sai ở `0.49999999999999994`
    và ở số lẻ ≥ 2^52 (ra số chẵn kế tiếp), còn `Math.round` thì không.
    """
    if not math.isfinite(x):
        raise ValueError(f"không làm tròn được số không hữu hạn: {x}")
    floor = math.floor(x)
    return floor + 1 if x - floor >= 0.5 else floor


def signed_area_mm2(outline: Sequence[Point]) -> float:
    """Diện tích có dấu, mm², chưa làm tròn; âm khi đường bao đi theo chiều kim đồng hồ.

    Dưới ba điểm → `0.0`. Tổng chéo tính bằng `int`; sau **mỗi** bước mà vượt
    `2^53 - 1` → `ValueError` (FE ném `RangeError` ở cùng chỗ, vì số thực hết cộng
    chính xác). Khác FE duy nhất khi một tích riêng lẻ vượt 2^53 mà tổng không vượt:
    FE làm tròn tích đó, ở đây tính đúng; toạ độ mặt bằng thật không chạm tới.
    """
    if len(outline) < 3:
        return 0.0
    total = 0
    for start, end in pairwise((*outline, outline[0])):
        total += start.x * end.y - end.x * start.y
        if abs(total) > MAX_SAFE_INTEGER:
            raise ValueError("tổng dây giày vượt 2^53 - 1 mm², số thực không còn cộng chính xác")
    return total / 2


def _publish_m2(area_mm2: float) -> Decimal:
    """Đổi mm² không âm sang m² và làm tròn một lần như `roundArea` của FE; không bao giờ `-0.00`."""
    return (Decimal(js_round(area_mm2 / _MM2_PER_M2 * _AREA_ROUNDING)) / _AREA_ROUNDING).quantize(_CENTI)


def polygon_area_m2(outline: Sequence[Point]) -> Decimal:
    """Diện tích một phòng, m², hai chữ số; chiều đường bao không đổi kết quả (`computeArea`)."""
    return _publish_m2(abs(signed_area_mm2(outline)))


def total_area_m2(outlines: Iterable[Sequence[Point]]) -> Decimal:
    """Tổng nhiều phòng: cộng mm² chưa làm tròn rồi làm tròn **một lần** (`area.ts:204-207`).

    Cộng bằng vòng lặp như `reduce` của FE, không `sum()`: từ 3.12 `sum()` của số
    thực cộng bù Neumaier, nên với tổng vượt 2^53 sẽ lệch FE ở chữ số cuối.
    """
    total = 0.0
    for outline in outlines:
        total += abs(signed_area_mm2(outline))
    return _publish_m2(total)


def _half_thickness(start: Point, end: Point, walls: Sequence[Wall], fallback: float) -> float:
    """Nửa bề dày tường chồng dài nhất lên cạnh `start→end` (song song, cách ≤ một bề dày); không có → `fallback`."""
    length = math.hypot(end.x - start.x, end.y - start.y)
    ux, uy = (end.x - start.x) / length, (end.y - start.y) / length
    best, half = 0.0, fallback
    for wall in walls:
        a, b = wall.centreline.start, wall.centreline.end
        wall_len = math.hypot(b.x - a.x, b.y - a.y)
        if abs(ux * (b.y - a.y) - uy * (b.x - a.x)) > _PARALLEL_SIN * wall_len:
            continue
        mid_x, mid_y = (a.x + b.x) / 2 - start.x, (a.y + b.y) / 2 - start.y
        if abs(ux * mid_y - uy * mid_x) > wall.thickness_mm:
            continue
        t0 = ux * (a.x - start.x) + uy * (a.y - start.y)
        t1 = ux * (b.x - start.x) + uy * (b.y - start.y)
        overlap = min(max(t0, t1), length) - max(min(t0, t1), 0.0)
        if overlap > best:
            best, half = overlap, wall.thickness_mm / 2
    return half


def clear_area_m2(outline: Sequence[Point], walls: Sequence[Wall]) -> Decimal:
    """Diện tích thông thủy: đường bao (tim tường) lùi vào nửa bề dày tường của từng cạnh, làm tròn như `areaM2`.

    Cạnh không có tường nằm trên → nửa bề dày trung vị của `walls` (cả tầng); tầng không tường → không lùi.
    Đỉnh mới là giao của hai cạnh kề đã lùi; cạnh kề thẳng hàng thì lấy đầu cạnh sau.
    """
    gross = signed_area_mm2(outline)
    if gross == 0:
        return _publish_m2(0.0)
    sign = 1.0 if gross > 0 else -1.0
    fallback = median(wall.thickness_mm for wall in walls) / 2 if walls else 0.0
    lines: list[tuple[float, float, float, float]] = []
    for start, end in pairwise((*outline, outline[0])):
        if start == end:
            continue
        length = math.hypot(end.x - start.x, end.y - start.y)
        ux, uy = (end.x - start.x) / length, (end.y - start.y) / length
        half = _half_thickness(start, end, walls, fallback)
        # Pháp tuyến vào trong: bên trái chiều đi khi đường bao ngược chiều kim đồng hồ (diện tích dương).
        lines.append((start.x - sign * uy * half, start.y + sign * ux * half, ux, uy))
    corners: list[tuple[float, float]] = []
    for (px, py, ux, uy), (qx, qy, vx, vy) in pairwise((lines[-1], *lines)):
        cross = ux * vy - uy * vx
        if abs(cross) < 1e-9:
            corners.append((qx, qy))
            continue
        t = ((qx - px) * vy - (qy - py) * vx) / cross
        corners.append((px + ux * t, py + uy * t))
    ring = list(pairwise((*corners, corners[0])))
    # Cạnh lùi xong đổi chiều = phòng hẹp hơn bề dày tường ở đó → coi như không còn sàn thông thủy.
    # ponytail: phòng lõm có một cạnh ngắn bị nuốt cũng về 0; cần chính xác hơn thì cắt đa giác (shapely) ở worker.
    if any(
        (x1 - x0) * ux + (y1 - y0) * uy < 0 for ((x0, y0), (x1, y1)), (_, _, ux, uy) in zip(ring, lines, strict=True)
    ):
        return _publish_m2(0.0)
    net = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in ring) / 2 * sign
    return _publish_m2(min(max(net, 0.0), abs(gross)))
