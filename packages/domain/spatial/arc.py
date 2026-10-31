"""Tường cong: cung tròn tả bằng dây `start→end` và sagitta có dấu (quy ước `curveOffset` của Pascal).

Pháp tuyến dây `n = (-dy, dx) / L`; điểm giữa cung = trung điểm dây - sagitta · n; |sagitta| ≤ L/2 (cung ≤ 180°).
Hàm thuần trên toạ độ thực, dùng chung cho px (bước dựng tầng) và mm (mặt nạ huấn luyện).
"""

import math
from typing import Final

type XY = tuple[float, float]

ARC_STEP_DEG: Final = 10.0
"""Mỗi dây lấy mẫu quét ≤ ngần này độ (cùng bước chia cung của vector hoá tường, 5b)."""


def arc_points(start: XY, end: XY, sagitta: float, step_deg: float = ARC_STEP_DEG) -> list[XY]:
    """Các đỉnh đều nhau trên cung, kể cả hai đầu; số dây chẵn để đỉnh giữa là đỉnh cung. Tường thẳng → hai đầu.

    Cung quét `4·atan(2|s|/L)`; tâm nằm phía `+n` khi sagitta dương và cung quay ngược chiều kim đồng hồ (hệ toạ
    độ toán), đúng như `getWallArcData` của Pascal.
    """
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    if sagitta == 0 or length == 0:
        return [start, end]
    depth = min(abs(sagitta), length / 2)
    radius = length * length / (8 * depth) + depth / 2
    sweep = 4 * math.atan(2 * depth / length)
    sign = math.copysign(1.0, sagitta)
    nx, ny = -(by - ay) / length, (bx - ax) / length
    cx = (ax + bx) / 2 + nx * (radius - depth) * sign
    cy = (ay + by) / 2 + ny * (radius - depth) * sign
    count = 2 * max(1, math.ceil(math.degrees(sweep) / (2 * step_deg)))
    begin = math.atan2(ay - cy, ax - cx)
    inner = [begin + sign * sweep * k / count for k in range(1, count)]
    return [start, *((cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in inner), end]


def sagitta_through(start: XY, apex: XY, end: XY) -> float:
    """Sagitta có dấu của dây `start→end` khi `apex` là đỉnh cung (điểm giữa cung): khoảng cách có dấu tới dây."""
    (ax, ay), (bx, by) = start, end
    length = math.hypot(bx - ax, by - ay)
    nx, ny = -(by - ay) / length, (bx - ax) / length
    return -((apex[0] - (ax + bx) / 2) * nx + (apex[1] - (ay + by) / 2) * ny)
