"""Cài cổng `drawing_scales` của B2-04 (BE-00 §2.2): mm trên mỗi pixel của từng tầng.

B2-04 quy đổi px → mm cho `Drawing.widthMm`/`heightMm` (W24) và cần tỉ lệ của nhiều tầng
cùng lúc; tỉ lệ ấy sống ở `floor_documents.scale_mm_per_px`, bảng của B3-02. Cổng là cách
hai module nói chuyện mà không ai nhập ai: `apps.api.drawings` không biết bảng này, còn
module này không nhập `apps.api.drawings`.

Chỉ trả tầng **có** tỉ lệ. Tầng chưa có tài liệu, hay `scale_source='none'` (CHECK của DB
buộc tỉ lệ NULL), vắng khoá — người gọi đã có mặc định `NO_SCALE`, nên trả 0 hay 1 ở đây
chỉ thêm một đường đi thứ hai cho cùng một luật.

Module này nhập được trong ngữ cảnh worker: không `fastapi`, không `starlette`.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.spatial import FloorDocumentRow


class SpatialScales:
    """Phần tử duy nhất của cổng: một truy vấn cho cả lô, không N+1."""

    async def load(self, db: AsyncSession, floor_pks: Sequence[int]) -> Mapping[int, Decimal]:
        """`{floor_pk: mm/pixel}` bằng **một** truy vấn; giữ `Decimal` của `numeric(12,6)`.

        Không đổi sang `float` ở đây: B2-04 nhân tỉ lệ với số pixel rồi mới làm tròn (W24),
        và một phép nhân nhị phân trung gian đủ để lệch một mm ở bản vẽ khổ lớn.
        """
        stmt = select(FloorDocumentRow.floor_pk, FloorDocumentRow.scale_mm_per_px).where(
            FloorDocumentRow.floor_pk.in_(list(floor_pks)), FloorDocumentRow.scale_mm_per_px.is_not(None)
        )
        return {floor_pk: scale for floor_pk, scale in (await db.execute(stmt)).all()}


SCALES: Final = (SpatialScales(),)
"""Cổng `drawing_scales` (BE-00 §2.2 cho tối đa 1 phần tử toàn hệ thống)."""
