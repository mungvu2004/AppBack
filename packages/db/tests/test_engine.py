"""Engine, `session_scope`, `worker_sessionmaker` (BE-00 §2.2, §7)."""

import asyncio
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from packages.db.engine import create_engine, create_sessionmaker, session_scope, worker_sessionmaker
from packages.db.settings import DatabaseSettings, reset_database_settings_cache

CREATE_NOTE = "CREATE TABLE IF NOT EXISTS note (id serial PRIMARY KEY, body text NOT NULL)"


async def _rows(maker: async_sessionmaker[AsyncSession]) -> list[str]:
    async with maker() as session:  # session mới: đọc lại từ DB, không đọc identity map (K22)
        result = await session.execute(text("SELECT body FROM note ORDER BY id"))
        return [str(row[0]) for row in result.all()]


async def test_session_scope_commits(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with session_scope(db_sessionmaker) as session:
        await session.execute(text(CREATE_NOTE))
        await session.execute(text("INSERT INTO note (body) VALUES ('a')"))
    assert await _rows(db_sessionmaker) == ["a"]


async def _write_then_fail(maker: async_sessionmaker[AsyncSession]) -> None:
    async with session_scope(maker) as session:
        await session.execute(text("INSERT INTO note (body) VALUES ('b')"))
        raise RuntimeError("hỏng")


async def test_session_scope_rolls_back_on_exception(db_sessionmaker: async_sessionmaker[AsyncSession]) -> None:
    async with session_scope(db_sessionmaker) as session:
        await session.execute(text(CREATE_NOTE))
    with pytest.raises(RuntimeError, match="hỏng"):
        await _write_then_fail(db_sessionmaker)
    assert await _rows(db_sessionmaker) == []


async def test_rollback_before_write_returns_connection_to_pool(db_url: str) -> None:
    """Handler chờ lâu (băm mật khẩu) thì nhả kết nối trước, ghi tiếp vẫn commit được."""
    engine = create_engine(DatabaseSettings(database_url=db_url))
    maker = create_sessionmaker(engine)
    try:
        async with maker() as session:
            await session.execute(text(CREATE_NOTE))
            await session.commit()
            await session.execute(text("SELECT 1"))
            await session.rollback()
            assert cast("QueuePool", engine.pool).checkedout() == 0
            await session.execute(text("INSERT INTO note (body) VALUES ('c')"))
            await session.commit()
        assert await _rows(maker) == ["c"]
    finally:
        await engine.dispose()


def test_worker_sessionmaker_per_event_loop(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:

        async def twice() -> tuple[int, int]:
            first = worker_sessionmaker()
            await asyncio.sleep(0)
            return id(first), id(worker_sessionmaker())

        with asyncio.Runner() as runner:
            same_loop = runner.run(twice())
            again = runner.run(twice())  # task thứ hai trên cùng Runner: không lỗi "different loop"
        with asyncio.Runner() as other_runner:
            other_loop = other_runner.run(twice())
    finally:
        reset_database_settings_cache()
    assert same_loop[0] == same_loop[1] == again[0]
    assert other_loop[0] != same_loop[0]


async def test_worker_sessionmaker_works_against_real_database(db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_database_settings_cache()
    try:
        maker = worker_sessionmaker()
        async with session_scope(maker) as session:
            await session.execute(text(CREATE_NOTE))
            await session.execute(text("INSERT INTO note (body) VALUES ('worker')"))
        assert await _rows(maker) == ["worker"]
    finally:
        reset_database_settings_cache()
