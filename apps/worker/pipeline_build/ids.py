"""Id thực thể không gian do BE sinh (W4, G14): `<chữ>-<base36 HOA 25 ký tự>`."""

import secrets
import string
from datetime import UTC, datetime, timedelta
from typing import Final

from packages.core.clock import Clock
from packages.core.ids import SPATIAL_PREFIX, SpatialKind

_BASE36: Final = string.digits + string.ascii_uppercase
_BODY_LEN: Final = 25
"""`36**25 > 2**128`: 25 chữ số base36 chứa đủ mọi ULID 128 bit."""
_EPOCH: Final = datetime(1970, 1, 1, tzinfo=UTC)
_MS_LIMIT: Final = 1 << 48


def new_spatial_id(kind: SpatialKind, clock: Clock) -> str:
    """ULID 128 bit (48 bit ms của `clock.now()` + 80 bit `secrets`, như B0-02) viết base36 HOA.

    Đệm `0` đủ 25 ký tự nên thứ tự chuỗi theo thứ tự thời gian; không tất định theo tầng hay
    thứ tự gọi. ms ngoài `[0, 2**48)` → `ValueError`. Kết quả đạt `is_spatial_id(kind, …)`.
    """
    ms = (clock.now() - _EPOCH) // timedelta(milliseconds=1)
    if not 0 <= ms < _MS_LIMIT:
        raise ValueError(f"ULID không biểu diễn được mốc {ms} ms")
    value = (ms << 80) | secrets.randbits(80)
    digits = []
    for _ in range(_BODY_LEN):
        value, digit = divmod(value, 36)
        digits.append(_BASE36[digit])
    return f"{SPATIAL_PREFIX[kind]}-{''.join(reversed(digits))}"
