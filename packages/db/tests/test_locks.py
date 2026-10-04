"""NO-247: khoá tư vấn theo dự án dùng chung ở `packages.db.locks`, trên Postgres thật (K23)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.locks import lock_project_scope


async def test_lock_project_scope__holds_one_advisory_lock_until_commit(db_session: AsyncSession) -> None:
    """Gọi một lần giữ đúng một khoá tư vấn cấp giao dịch của phiên này (tới hết giao dịch)."""
    await lock_project_scope(db_session, "templates", "prj_01J0000000000000000000000Z")
    held = await db_session.scalar(
        text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted")
    )
    assert held == 1
