"""B2-04 cài cổng `floor.drawings` của B2-01 (`apps/api/projects/parts.py`).

Một lô tầng → `{str(floor_pk): [DrawingOut]}`, bằng **một** truy vấn `drawings` cộng
**một** lượt `load_scales` cho cả lô: `floor_outs` của B2-03 gọi cổng này cho mọi tầng
của mọi dự án trong N1, nên N+1 ở đây là N+1 của cả màn danh sách.

`DrawingOut.scale` cố ý để trống: tỉ lệ đã nằm trong `widthMm`/`heightMm` (W24), còn
trường `scale` trên dây là của #35/N16 (B3-02), không phải của bản vẽ.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.wire import WireModel
from apps.api.drawings.drawings import drawing_url
from apps.api.drawings.scales import NO_SCALE, load_scales, scale_mm
from apps.api.drawings.urls import signer
from apps.api.projects.parts import FLOOR_DRAWINGS, ViewPart
from apps.api.projects.wire import DrawingOut
from packages.db.models.drawings import DrawingRow


async def load(
    db: AsyncSession, keys: Sequence[str], *, app: object | None = None
) -> Mapping[str, Sequence[WireModel]]:
    """Bản vẽ đang dùng của từng tầng; khoá là `str(floors.pk)` như `lookup._drawings_of` gửi.

    `app` là keyword-only có mặc định nên chữ ký vẫn khớp `ViewPart.load`; `lookup.py`
    không truyền nó (→ cổng tỉ lệ dò toàn cục), test truyền `app=api_app` để `override`.
    Tầng chưa có bản vẽ vắng khoá — `lookup.py` đọc khoá thiếu thành `[]`.
    """
    pks = [int(key) for key in keys]
    if not pks:
        return {}
    rows = list((await db.execute(select(DrawingRow).where(DrawingRow.floor_pk.in_(pks)))).scalars().all())
    scales = await load_scales(db, [row.floor_pk for row in rows], app=app)
    storage = signer()
    out: dict[str, Sequence[WireModel]] = {}
    for row in rows:
        scale = scales.get(row.floor_pk, NO_SCALE)
        out[str(row.floor_pk)] = [
            DrawingOut(
                id=row.id,
                name=row.name,
                url=await drawing_url(storage, row.page_key),
                width_mm=scale_mm(row.width_px, scale),
                height_mm=scale_mm(row.height_px, scale),
                uploaded_at=row.uploaded_at,
                uploader_id=row.uploader_id,
            )
        ]
    return out


PARTS: Final = (ViewPart(FLOOR_DRAWINGS, load),)
