"""Khoá tư vấn theo dự án dùng chung cho phép đo và khuôn (B2-07 [6] "Khoá", BE-00 §7)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def lock_project_scope(db: AsyncSession, scope: str, project_id: str) -> None:
    """Khoá mutex `<scope>:<project_id>` đến hết giao dịch.

    Mọi kiểm trùng id và trần phải chạy **sau** lời gọi này: hai request song song cùng
    id, hoặc cùng chạm trần, tuần tự hoá ở đây thay vì cùng thấy "chưa có".
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": f"{scope}:{project_id}"})
