"""Bảng bề dày tường chuẩn và phép bắt bậc: gương `src/domain/walls/cleanup.ts:70` của FE.

Dùng chung cho bước dựng (px → mm) và cho đổi tỉ lệ (`packages/domain/scale/rescale.py`),
để cùng một số đo luôn ra cùng một bậc.
"""

from typing import Final

STANDARD_THICKNESSES_MM: Final = (100, 150, 200, 220, 300, 400)
"""Bề dày chuẩn FE bắt tường về (`src/domain/walls/cleanup.ts:70`); hoà lấy số nhỏ hơn."""


def snap_thickness(measured_mm: float) -> int:
    """Bề dày đo → phần tử gần nhất của `STANDARD_THICKNESSES_MM`; hoà lấy số nhỏ hơn."""
    return min(STANDARD_THICKNESSES_MM, key=lambda value: (abs(value - measured_mm), value))
