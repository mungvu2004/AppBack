"""`python -m packages.db.migrate_check` — bước 6 của verify (BE-00 §6.1, §12).

Vòng kiểm: đúng 1 head → `upgrade head` → seed hai lần (số dòng không đổi) →
`downgrade -1` → `upgrade head` (revision mới nhất chạy trên DB **có dữ liệu**) →
`downgrade base` (không còn bảng nào ngoài `alembic_version`) → `upgrade head` →
model khớp DB → tên `CHECK` khớp model (`compare_metadata` không so `CHECK`, FIX-036).

Không có `DATABASE_URL` thì tự dựng `postgres:16-alpine` bằng Testcontainers (nhập
lười trong hàm; `packages.db` không nhập `packages.testing`).

Lệnh Alembic chạy trong **luồng khác**: `env.py` gọi `asyncio.run`, không chạy được
bên trong vòng sự kiện của hàm này.
"""

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, Final

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Column, Connection, MetaData, Table, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema

from packages.db.base import Base
from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.db.models import load_all_models
from packages.db.seeds import apply_seeds
from packages.db.settings import reset_database_settings_cache

ALEMBIC_INI: Final = Path(__file__).resolve().parent / "alembic.ini"
SCRIPT_LOCATION: Final = Path(__file__).resolve().parent / "migrations"
SEED_ENV: Final = "ci"
# Cùng ảnh với packages/testing/fixtures/services.py (không nhập được từ mã không phải test).
POSTGRES_IMAGE: Final = "postgres:16-alpine"
# `to_regclass` phân giải tên bảng theo search_path, như DDL của model (không ghi schema) đã tạo.
_DB_CHECK_NAMES: Final = text(
    "SELECT conname FROM pg_constraint WHERE contype = 'c' AND conrelid = ANY("
    "SELECT to_regclass(qualified)::oid FROM unnest(CAST(:tables AS text[])) AS t(qualified))"
)

SeedRunner = Callable[[AsyncSession, str], Awaitable[Any]]
# Một bước của vòng kiểm: "" nếu đạt, không thì lý do hỏng.
Step = Callable[[], Awaitable[str]]


def _say(text: str) -> None:
    print(text)  # noqa: T201 — cổng in bảng con ra stdout


def _noop() -> None:
    """Không có container nào để dừng (DATABASE_URL đã có sẵn)."""


def alembic_config(script_location: Path | str | None = None) -> Config:
    """Config trỏ tới `alembic.ini` của repo, `script_location` tuyệt đối."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(script_location or SCRIPT_LOCATION))
    return config


async def _table_counts(session: AsyncSession) -> dict[str, int]:
    rows = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name <> 'alembic_version'"
        )
    )
    counts = {}
    for (table,) in rows.all():
        total = await session.execute(text(f'SELECT count(*) FROM "{table}"'))  # noqa: S608 — tên bảng từ catalog
        counts[str(table)] = int(total.scalar_one())
    return counts


def _compare(connection: Connection, metadata: MetaData) -> list[Any]:
    context = MigrationContext.configure(connection, opts={"compare_type": True, "compare_server_default": True})
    return list(compare_metadata(context, metadata))


def _check_name_drift(connection: Connection, metadata: MetaData) -> str:
    """So tên `CHECK` của model với DB trên các bảng của `metadata`; "" nếu khớp, không thì tên thừa/thiếu.

    `compare_metadata` không so `CHECK`, nên tên lặp tiền tố (`ck_t_ck_t_x`: revision truyền tên đủ
    tiền tố mà không bọc `op.f(...)`, NO-057) lọt qua "model khớp DB". Tên model dựng bằng
    `format_constraint` của dialect: đúng quy ước và đúng cách cắt tên > 63 ký tự như DDL (tên cần
    ngoặc kép trả về có ngoặc nên hiện lệch — quy ước chỉ sinh chữ thường). `CHECK` của domain
    (`conrelid = 0`), của bảng ngoài metadata, và `CHECK` mà DDL của dialect không phát (gắn với kiểu
    native: `Boolean`/`Enum(create_constraint=True)` trên Postgres, NO-070) không xét.
    """
    preparer = connection.dialect.identifier_preparer
    tables = list(metadata.tables.values())
    # `CHECK` khai trong `Column(...)` nằm ở `column.constraints`, không ở `table.constraints`.
    owners: list[Table | Column[Any]] = [*tables, *(column for table in tables for column in table.columns)]
    # R-05: `_should_create_for_compiler` là API riêng của SQLAlchemy, đúng cổng mà
    # `DDLCompiler.create_table_constraints` dùng để bỏ `CHECK` (xét `_create_rule`, `ddl_if`). Ngưỡng: đã
    # đọc mã của 2.0.54 (`uv.lock`); bản sau đổi tên thì bước ném `AttributeError` (đỏ, không xanh giả) và
    # `test_check_bound_to_native_type_passes` đỏ. Đường nâng cấp: so với tên do `create_all` tạo ở schema tạm.
    # Trình biên dịch chỉ cần mang dialect; `CreateSchema` là lệnh DDL rẻ nhất có kiểu (`DDL(...)` chưa gõ kiểu).
    ddl = connection.dialect.ddl_compiler(connection.dialect, CreateSchema("public"))
    checks = [
        c
        for owner in owners
        for c in owner.constraints
        if isinstance(c, CheckConstraint) and c._should_create_for_compiler(ddl)
    ]
    # `None` (CHECK không tên mà quy ước không dựng được tên) thành "None": hiện ra như một tên thiếu.
    in_model = {str(preparer.format_constraint(check)) for check in checks}
    rows = connection.execute(_DB_CHECK_NAMES, {"tables": [table.fullname for table in tables]})
    in_db = {str(name) for (name,) in rows}
    extra, missing = sorted(in_db - in_model), sorted(in_model - in_db)
    return "" if not extra and not missing else f"CHECK thừa trong DB: {extra}; thiếu trong DB: {missing}"


async def _one_head(config: Config) -> str:
    """Cây revision có đúng một head; hai head là hai nhánh chưa rebase (BE-00 §6.1)."""
    heads = ScriptDirectory.from_config(config).get_heads()
    return "" if len(heads) == 1 else f"{len(heads)} head: {', '.join(heads) or 'không có'}"


async def _alembic(action: Callable[[Config, str], None], config: Config, revision: str) -> str:
    """Chạy `command.upgrade`/`command.downgrade` ở luồng khác (`env.py` gọi `asyncio.run`); lỗi nổi lên."""
    await asyncio.to_thread(action, config, revision)
    return ""


async def _seed_twice(engine: AsyncEngine, seed_runner: SeedRunner) -> str:
    """Seed `SEED_ENV` hai lần: số dòng mọi bảng sau lượt hai phải bằng sau lượt một (idempotent)."""
    async with AsyncSession(engine) as session:
        await seed_runner(session, SEED_ENV)
        await session.commit()
        first = await _table_counts(session)
        await seed_runner(session, SEED_ENV)
        await session.commit()
        second = await _table_counts(session)
    drift = {name: (first[name], second[name]) for name in first if first[name] != second[name]}
    return "" if not drift else f"seed không idempotent: {drift}"


async def _only_version_table(engine: AsyncEngine) -> str:
    """Sau `downgrade base` không còn bảng nào ngoài `alembic_version`: mọi `downgrade()` dọn đủ."""
    async with AsyncSession(engine) as session:
        counts = await _table_counts(session)
    return "" if not counts else f"còn bảng: {', '.join(sorted(counts))}"


async def _metadata_matches(engine: AsyncEngine, target: MetaData) -> str:
    """`compare_metadata` (kiểu, default phía server) giữa `target` và DB không ra khác biệt nào."""
    async with engine.connect() as connection:
        diffs = await connection.run_sync(_compare, target)
    return "" if not diffs else f"{len(diffs)} khác biệt: {diffs}"


async def _check_names_match(engine: AsyncEngine, target: MetaData) -> str:
    """Tên `CHECK` của `target` khớp DB (`_check_name_drift`, FIX-036)."""
    async with engine.connect() as connection:
        return await connection.run_sync(_check_name_drift, target)


def _steps(config: Config, engine: AsyncEngine, target: MetaData, seed_runner: SeedRunner) -> list[tuple[str, Step]]:
    """Mười bước theo đúng thứ tự vòng kiểm của BE-00 §6.1; tên bước là chuỗi cổng in ra."""
    return [
        ("đúng 1 head", lambda: _one_head(config)),
        ("upgrade head", lambda: _alembic(command.upgrade, config, "head")),
        (f"seed {SEED_ENV} hai lần", lambda: _seed_twice(engine, seed_runner)),
        ("downgrade -1", lambda: _alembic(command.downgrade, config, "-1")),
        ("upgrade head trên DB có dữ liệu", lambda: _alembic(command.upgrade, config, "head")),
        ("downgrade base", lambda: _alembic(command.downgrade, config, "base")),
        ("chỉ còn alembic_version", lambda: _only_version_table(engine)),
        ("upgrade head lại", lambda: _alembic(command.upgrade, config, "head")),
        ("model khớp DB", lambda: _metadata_matches(engine, target)),
        ("tên CHECK khớp model", lambda: _check_names_match(engine, target)),
    ]


async def _run_step(run: Step) -> str:
    """Lý do hỏng của bước, "" nếu đạt; ngoại lệ của bước thành lý do (`repr`), không nổi ra khỏi cổng."""
    try:
        return await run()
    except Exception as exc:  # noqa: BLE001 — migration hỏng là kết quả của cổng, không phải sự cố của nó
        return repr(exc)


async def run_checks(
    config: Config,
    url: str,
    *,
    metadata: MetaData | None = None,
    seed_runner: SeedRunner = apply_seeds,
) -> list[tuple[str, str]]:
    """Trả danh sách (tên bước, "" nếu đạt | lý do hỏng); dừng ở bước hỏng đầu tiên.

    Đặt luôn `DATABASE_URL = url` để Alembic (`env.py`) và engine ở đây dùng **cùng** DB.
    """
    os.environ["DATABASE_URL"] = url
    reset_database_settings_cache()
    target = metadata if metadata is not None else Base.metadata
    results: list[tuple[str, str]] = []
    engine = create_async_engine(url, poolclass=NullPool, connect_args={"timeout": GATE_CONNECT_TIMEOUT_S})
    try:
        for name, run in _steps(config, engine, target, seed_runner):
            detail = await _run_step(run)
            results.append((name, detail))
            if detail:
                break
    finally:
        await engine.dispose()
    return results


def _start_postgres() -> tuple[str, Callable[[], None]]:
    # testcontainers 4.13 không có py.typed, cũng không có gói stub
    from testcontainers.postgres import PostgresContainer  # type: ignore[import-untyped]

    container = PostgresContainer(POSTGRES_IMAGE, driver="asyncpg")
    container.start()
    return str(container.get_connection_url()), container.stop


def main(argv: list[str] | None = None) -> int:
    if argv:
        _say(f"migrate_check không nhận tham số: {' '.join(argv)}")
        return 2
    load_all_models()
    url = os.environ.get("DATABASE_URL")
    stop: Callable[[], None] = _noop
    if not url:
        url, stop = _start_postgres()
        os.environ["DATABASE_URL"] = url
        reset_database_settings_cache()
    try:
        results = asyncio.run(run_checks(alembic_config(), url))
    finally:
        stop()
    for name, detail in results:
        _say(f"  {name:<36} {'đạt' if not detail else 'hỏng'}{f' — {detail}' if detail else ''}")
    failed = [name for name, detail in results if detail]
    _say(f"migrate_check: {'đạt' if not failed else 'hỏng'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
