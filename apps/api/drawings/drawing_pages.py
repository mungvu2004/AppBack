"""B2-04 **cài** cổng `drawing_pages` của B3-02 (BE-00 §2.2, dòng 133).

B3-02 hỏi "trang nào đang được dùng cho tầng này" để biết một tỉ lệ đã hiệu chỉnh còn
gắn đúng trang hay không (N16 `scaleStatus`). Câu trả lời nằm gọn trong `drawings`:
một dòng mỗi tầng, cột `page_key`.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.drawings import DrawingRow


class DrawingPages:
    """Phần tử của cổng; lớp chứ không hàm rời vì hợp đồng đòi một đối tượng có `load`."""

    async def load(self, db: AsyncSession, floor_pks: Sequence[int]) -> Mapping[int, str]:
        """`{floor_pk: page_key}` bằng **một** truy vấn; tầng chưa có bản vẽ vắng khoá."""
        if not floor_pks:
            return {}
        stmt = select(DrawingRow.floor_pk, DrawingRow.page_key).where(DrawingRow.floor_pk.in_(list(floor_pks)))
        return {pk: key for pk, key in (await db.execute(stmt)).all()}


PAGES: Final = (DrawingPages(),)
