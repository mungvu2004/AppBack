"""Tường cong: cung tròn tả bằng dây `start→end` và sagitta có dấu (quy ước `curveOffset` của Pascal).

Pháp tuyến dây `n = (-dy, dx) / L`; điểm giữa cung = trung điểm dây - sagitta · n; |sagitta| ≤ L/2 (cung ≤ 180°).
Hàm thuần trên toạ độ thực, dùng chung cho px (bước dựng tầng) và mm (mặt nạ huấn luyện).
"""

import math
from typing import Final

type XY = tuple[float, float]

ARC_STEP_DEG: Final = 10.0
"""Mỗi dây lấy mẫu quét ≤ ngần này độ (cùng bước chia cung của vector hoá tường, 5b)."""


def _circle(start: XY, end: XY, sagitta: float) -> tuple[float, float, float, float, float, float]:
    """`(cx, cy, bán kính, góc đầu, chiều quay ±1, góc quét)` của cung; tâm phía `+n` khi sagitta dương."""
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    depth = min(abs(sagitta), length / 2)
    radius = length * length / (8 * depth) + depth / 2
    sign = math.copysign(1.0, sagitta)
    nx, ny = -(by - ay) / length, (bx - ax) / length
    cx = (ax + bx) / 2 + nx * (radius - depth) * sign
    cy = (ay + by) / 2 + ny * (radius - depth) * sign
    return cx, cy, radius, math.atan2(ay - cy, ax - cx), sign, 4 * math.atan(2 * depth / length)


def arc_points(start: XY, end: XY, sagitta: float, step_deg: float = ARC_STEP_DEG) -> list[XY]:
    """Các đỉnh đều nhau trên cung, kể cả hai đầu; số dây chẵn để đỉnh giữa là đỉnh cung. Tường thẳng → hai đầu.

    Cung quét `4·atan(2|s|/L)`; tâm nằm phía `+n` khi sagitta dương và cung quay ngược chiều kim đồng hồ (hệ toạ
    độ toán), đúng như `getWallArcData` của Pascal.
    """
    if sagitta == 0 or start == end:
        return [start, end]
    cx, cy, radius, begin, sign, sweep = _circle(start, end, sagitta)
    count = 2 * max(1, math.ceil(math.degrees(sweep) / (2 * step_deg)))
    inner = [begin + sign * sweep * k / count for k in range(1, count)]
    return [start, *((cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in inner), end]


def span_points(
    start: XY, end: XY, sagitta: float, low: float, high: float, step_deg: float = ARC_STEP_DEG
) -> list[XY]:
    """Các đỉnh của đoạn tường từ `low` tới `high` (độ dài dọc tường tính từ `start`, như `offsetMm` của ô mở).

    Tường thẳng → hai đầu đoạn trên dây; tường cong → các đỉnh đều trên cung, mỗi dây quét ≤ `step_deg`.
    """
    (ax, ay), (bx, by) = start, end
    if sagitta == 0 or start == end:
        length = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / length, (by - ay) / length
        return [(ax + ux * low, ay + uy * low), (ax + ux * high, ay + uy * high)]
    cx, cy, radius, begin, sign, _ = _circle(start, end, sagitta)
    count = max(1, math.ceil(math.degrees((high - low) / radius) / step_deg))
    angles = [begin + sign * (low + (high - low) * k / count) / radius for k in range(count + 1)]
    return [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]


def foot_on_arc(point: XY, start: XY, end: XY, sagitta: float) -> XY:
    """Điểm trên cung (tường cong, `sagitta` khác 0) gần `point` nhất: chân bán kính nếu nằm trong góc quét, không thì
    đầu mút gần hơn."""
    cx, cy, radius, begin, sign, sweep = _circle(start, end, sagitta)
    angle = math.atan2(point[1] - cy, point[0] - cx)
    if (sign * (angle - begin)) % math.tau <= sweep:
        return cx + radius * math.cos(angle), cy + radius * math.sin(angle)
    return min((start, end), key=lambda tip: math.hypot(point[0] - tip[0], point[1] - tip[1]))


def sagitta_through(start: XY, apex: XY, end: XY) -> float:
    """Sagitta có dấu của dây `start→end` khi `apex` là đỉnh cung (điểm giữa cung): khoảng cách có dấu tới dây."""
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    nx, ny = -(by - ay) / length, (bx - ax) / length
    return -((apex[0] - (ax + bx) / 2) * nx + (apex[1] - (ay + by) / 2) * ny)
