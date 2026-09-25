"""Cổng `drawing_scales` (BE-00 §2.2, dòng 132): mm trên mỗi pixel của từng tầng.

B2-04 chỉ **khai** cổng; B3-02 là module cài nó. Tách ra khỏi `view_parts.py` vì luật
W24 (`widthMm = max(1, round(width_px x s))`) còn được `drawing_pages` và các màn khác
dùng lại, và vì `view_parts.py` nhập `fastapi` gián tiếp qua `projects.parts`.

Chưa ai cài cổng, hay cổng không biết một tầng → tỉ lệ 1, tức là mm = pixel.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final, Protocol, cast

from apps.api.core import extensions

SUBMODULE: Final = "drawing_scales"
ATTR: Final = "SCALES"

NO_SCALE: Final = Decimal(1)
"""Tỉ lệ mặc định: chưa có cổng hoặc tầng vắng khoá thì mm chính là pixel (BE-00 §2.2)."""


class ScaleSource(Protocol):
    """Phần tử của `SCALES`: một lượt tải tỉ lệ theo lô cho nhiều tầng."""

    async def load(self, db: object, floor_pks: Sequence[int]) -> Mapping[int, Decimal]:
        """`{floor_pk: mm/pixel}`; tầng nào không biết thì vắng khoá chứ không trả 0."""
        ...


def _source(app: object | None) -> ScaleSource | None:
    """Phần tử duy nhất của cổng; hai module cùng cài → `RuntimeError` (BE-00 §2.2)."""
    found = [item for _, value in extensions.resolve(app, SUBMODULE, ATTR) for item in cast("Sequence[object]", value)]
    if len(found) > 1:
        raise RuntimeError(f"cổng {SUBMODULE} có {len(found)} phần tử, tối đa 1")
    return cast("ScaleSource", found[0]) if found else None


async def load_scales(db: object, floor_pks: Sequence[int], *, app: object | None = None) -> dict[int, Decimal]:
    """Tỉ lệ của cả lô tầng bằng **một** lượt gọi cổng; không cổng hay lô rỗng → `{}`.

    Trả `{}` chứ không `{pk: 1}`: người gọi đã phải có mặc định cho tầng vắng khoá
    (`scale_mm`), nên bịa sẵn khoá chỉ thêm một đường đi thứ hai cho cùng một luật.
    """
    source = _source(app)
    if source is None or not floor_pks:
        return {}
    return dict(await source.load(db, list(floor_pks)))


def scale_mm(pixels: int, scale: Decimal) -> int:
    """Luật W24: `max(1, round(px x mm/px))` — một bản vẽ không bao giờ rộng 0 mm."""
    return max(1, round(pixels * scale))
