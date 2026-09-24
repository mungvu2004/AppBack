"""Khoá tư vấn dùng chung của module tầng (BE-00 §7): một nguồn cho chuỗi khoá `floors:<project_id>`.

Tách khỏi `lookup.py` vì `jobs.py` (worker) không được nhập `apps.api.projects.parts` (qua
`lookup`): `parts.py` nhập `apps.api.core.auth` dưới `TYPE_CHECKING`, nhưng `lint-imports`
(grimp) tính cả cạnh có điều kiện là thật, nên nhập `lookup` từ `jobs.py` sẽ kéo `starlette`
vào và vỡ ranh giới "`apps.api.*.jobs` không nhập `fastapi`/`starlette`/`jwt`/`argon2`" (BE-00
§2.1). Module này chỉ nhập `sqlalchemy`, nên cả `lookup.py` (chủ, re-export) và `jobs.py`
(lịch dọn) đều nhập được, dùng chung đúng **một** hàm và một chuỗi khoá (R-07).
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_project_floors(db: AsyncSession, project_id: str) -> None:
    """Khoá tư vấn mutex theo dự án — đầu tiên trong thứ tự khoá của mọi route ghi và lịch dọn."""
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"floors:{project_id}"})
