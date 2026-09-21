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
from typing import Final

from packages.domain.spatial.model import MAX_SAFE_INTEGER, Point

_MM2_PER_M2: Final = 1_000_000
_AREA_ROUNDING: Final = 100
_CENTI: Final = Decimal("0.01")


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
