"""Môi trường Alembic (BE-00 §6.1).

- DSN lấy từ `DatabaseSettings` (`DATABASE_URL`), không đặt trong `alembic.ini`.
- `statement_timeout=0`: tạo index trên bảng lớn lâu hơn trần của API. `lock_timeout`
  **giữ nguyên**: migration chờ khoá quá lâu thì hỏng sớm, không treo cả dịch vụ.
- `compare_type`, `compare_server_default`: `migrate_check` so model với DB.
- `transaction_per_migration`: revision dùng `autocommit_block()` (CREATE INDEX
  CONCURRENTLY) không kéo theo revision khác.
"""

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from packages.db.base import Base
from packages.db.models import load_all_models
from packages.db.settings import get_database_settings


def _configure(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    settings = get_database_settings()
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        connect_args={
            "server_settings": {
                "statement_timeout": "0",
                "lock_timeout": str(settings.db_lock_timeout_ms),
                "timezone": "UTC",
                "application_name": "appback-alembic",
            }
        },
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_configure)
    finally:
        await engine.dispose()


def run() -> None:
    load_all_models()
    if context.is_offline_mode():
        raise RuntimeError("Alembic offline không dùng ở AppBack: mọi lượt chạy cần kết nối thật")
    asyncio.run(_run_async())


run()
