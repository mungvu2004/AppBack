"""Engine, session, và sessionmaker của worker (BE-00 §2.2, §7).

`worker_sessionmaker()` cache theo (vòng sự kiện đang chạy, `DATABASE_URL`): engine
asyncpg gắn với vòng lặp tạo ra nó, dùng lại ở vòng khác là "attached to a different
loop". Cache là `WeakKeyDictionary` nên vòng lặp bị thu hồi thì mục tự rụng; engine
của vòng đã đóng không `dispose()` được (không còn vòng để chạy), đây là engine sống
suốt đời tiến trình worker.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from packages.db.settings import DatabaseSettings, get_database_settings

_worker_makers: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, dict[str, async_sessionmaker[AsyncSession]]
] = weakref.WeakKeyDictionary()


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_s,
        pool_pre_ping=True,
        hide_parameters=True,  # lỗi SQL không kéo tham số (băm mật khẩu, email) vào log (K11)
        connect_args={
            "server_settings": {
                "statement_timeout": str(settings.db_statement_timeout_ms),
                "lock_timeout": str(settings.db_lock_timeout_ms),
                "timezone": "UTC",
                "application_name": "appback",
            }
        },
    )


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def session_scope(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Commit khi thoát bình thường, rollback khi có ngoại lệ (bỏ luôn callback J09)."""
    async with maker() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        await session.commit()


def worker_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Sessionmaker dùng chung cho task và lịch nền của vòng sự kiện đang chạy."""
    loop = asyncio.get_running_loop()
    by_url = _worker_makers.setdefault(loop, {})
    settings = get_database_settings()
    maker = by_url.get(settings.database_url)
    if maker is None:
        maker = create_sessionmaker(create_engine(settings))
        by_url[settings.database_url] = maker
    return maker
