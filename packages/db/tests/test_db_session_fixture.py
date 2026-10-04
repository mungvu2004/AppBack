"""Luật đọc lại DB của fixture `db_session` (NO-235). Postgres thật (K23)."""

import pytest
from sqlalchemy import Integer, MetaData, Text, select, text, update
from sqlalchemy.exc import MissingGreenlet
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _Base(DeclarativeBase):
    """Metadata riêng của test: bảng không lẫn vào `Base.metadata` của app."""

    metadata = MetaData()


class Thing(_Base):
    """Một dòng ORM mà test giữ trong tay qua lượt ghi của "request" khác."""

    __tablename__ = "no235_thing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(Text)


async def _thing_then_foreign_write(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> Thing:
    """Dựng đúng đường của test HTTP: test giữ đối tượng, request ghi qua phiên khác.

    Sau `commit` test còn `SELECT` một lần — giao dịch tự mở (autobegin) đang treo khi request ghi,
    đúng chỗ người viết test với tay tới `rollback()` để thấy dữ liệu mới.
    """
    await db_session.execute(text("CREATE TABLE IF NOT EXISTS no235_thing (id integer PRIMARY KEY, code text)"))
    thing = Thing(id=1, code="a")
    db_session.add(thing)
    await db_session.commit()
    await db_session.execute(select(Thing))
    async with db_sessionmaker() as request:
        await request.execute(update(Thing).where(Thing.id == 1).values(code="b"))
        await request.commit()
    return thing


async def test_db_session__rollback_expires_loaded_instances(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Bẫy NO-235: `rollback()` hết hạn mọi instance, lần đọc thuộc tính kế nạp lười → `MissingGreenlet`."""
    thing = await _thing_then_foreign_write(db_session, db_sessionmaker)
    await db_session.rollback()
    with pytest.raises(MissingGreenlet):
        _ = thing.code


async def test_db_session__commit_then_refresh_sees_foreign_write(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Đường đúng mà docstring `db_session` ghi: `commit()` giữ instance, `refresh()` lấy giá trị mới."""
    thing = await _thing_then_foreign_write(db_session, db_sessionmaker)
    await db_session.commit()
    assert (thing.id, thing.code) == (1, "a")
    await db_session.refresh(thing)
    assert thing.code == "b"
