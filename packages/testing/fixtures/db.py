"""Fixture Postgres thật cho test (B0-03; K23: không SQLite, không mock).

- `db_template` (phiên): một database đã `upgrade head`, **không** seed.
- `db_url` (mỗi test): `CREATE DATABASE … TEMPLATE` từ bản trên — nhanh hơn chạy lại
  Alembic, và mỗi test có dữ liệu riêng.
- `blank_db_url` (mỗi test): database rỗng, chưa migrate — cho test của `migrate_check`.
- `drop_after_commit()`: bỏ callback J09 để dựng J10 ("commit xong rồi chết").

Fixture async gắn `loop_scope="function"`: engine asyncpg thuộc về vòng sự kiện tạo ra
nó, mà test chạy ở vòng theo hàm.
"""

import asyncio
import os
import secrets
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.hooks import DROP_ENV
from packages.db.migrate_check import alembic_config
from packages.db.settings import DatabaseSettings, reset_database_settings_cache

TEMPLATE_DB = "appback_template"


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{name}", "", ""))


async def _admin(url: str, statements: list[str]) -> None:
    # Đường connect nhiều nhất của cả bộ test (mỗi test một `CREATE`/`DROP DATABASE`), nên
    # cũng chịu trần cổng thay vì 60 s mặc định của asyncpg (NO-002).
    engine = create_async_engine(
        _with_database(url, "postgres"),
        isolation_level="AUTOCOMMIT",
        connect_args={"timeout": GATE_CONNECT_TIMEOUT_S},
    )
    try:
        async with engine.connect() as connection:
            for statement in statements:
                await connection.execute(text(statement))
    finally:
        await engine.dispose()


def _create_database(url: str, name: str, template: str | None = None) -> None:
    suffix = f' TEMPLATE "{template}"' if template else ""
    asyncio.run(_admin(url, [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)', f'CREATE DATABASE "{name}"{suffix}']))


def _drop_database(url: str, name: str) -> None:
    asyncio.run(_admin(url, [f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)']))


def _alembic_upgrade(url: str) -> None:
    from alembic import command  # nhập tại chỗ: giữ thời gian thu thập test thấp

    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    reset_database_settings_cache()  # env.py đọc `DatabaseSettings`, mà nó có cache
    try:
        command.upgrade(alembic_config(), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        reset_database_settings_cache()


@pytest.fixture(scope="session")
def db_template(postgres_url: str) -> Iterator[str]:
    """Database mẫu đã migrate; `db_url` nhân bản từ nó."""
    _create_database(postgres_url, TEMPLATE_DB)
    template_url = _with_database(postgres_url, TEMPLATE_DB)
    _alembic_upgrade(template_url)
    yield template_url
    _drop_database(postgres_url, TEMPLATE_DB)


@pytest.fixture
def db_url(postgres_url: str, db_template: str) -> Iterator[str]:
    name = f"t_{secrets.token_hex(8)}"
    _create_database(postgres_url, name, template=TEMPLATE_DB)
    yield _with_database(postgres_url, name)
    _drop_database(postgres_url, name)


@pytest.fixture
def blank_db_url(postgres_url: str) -> Iterator[str]:
    """Database rỗng, chưa chạy Alembic (test của `migrate_check`)."""
    name = f"b_{secrets.token_hex(8)}"
    _create_database(postgres_url, name)
    yield _with_database(postgres_url, name)
    _drop_database(postgres_url, name)


@pytest_asyncio.fixture(loop_scope="function")
async def db_sessionmaker(db_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    # Pool nhỏ: mỗi test một database, Postgres dùng chung không phải giữ hàng trăm kết nối.
    # Trần bắt tay của đường cổng, không phải 10 s của đường request (NO-036, cùng lý do `_admin`).
    settings = DatabaseSettings(
        database_url=db_url, db_pool_size=5, db_max_overflow=0, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)
    )
    engine = create_engine(settings)
    try:
        yield create_sessionmaker(engine)
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="function")
async def db_session(db_sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with db_sessionmaker() as session:
        yield session


@contextmanager
def drop_after_commit() -> Iterator[None]:
    """J10: commit vẫn bền vững nhưng callback sau commit **không** chạy.

    Cờ cấp tiến trình (biến môi trường) nên có hiệu lực cả trong luồng `celery_worker`.
    """
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("drop_after_commit() chỉ dùng khi APP_ENV=test")
    previous = os.environ.get(DROP_ENV)
    os.environ[DROP_ENV] = "1"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(DROP_ENV, None)
        else:
            os.environ[DROP_ENV] = previous
