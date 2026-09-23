"""Test bộ đếm SQL dùng chung của `apps/api/projects/tests`."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.tests.sql_count import count_sql


async def test_count_sql_counts_statements_inside_block_only(db_session: AsyncSession) -> None:
    """Đếm đúng câu chạy trong khối; câu chạy sau khi ra khối không bị tính."""
    with count_sql() as counter:
        await db_session.execute(text("SELECT 1"))
        await db_session.execute(text("SELECT 2"))
    await db_session.execute(text("SELECT 3"))
    assert counter.count == 2
    assert counter.statements == ["SELECT 1", "SELECT 2"]


async def test_count_sql_detaches_listener_when_block_raises(db_session: AsyncSession) -> None:
    """Khối ném lỗi vẫn gỡ bộ nghe: bộ đếm cũ không tăng thêm."""
    with pytest.raises(RuntimeError), count_sql() as counter:
        raise RuntimeError("boom")
    await db_session.execute(text("SELECT 1"))
    assert counter.count == 0
