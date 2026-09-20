"""`migrate_check` — bước 6 của verify (BE-00 §6.1). Chạy Postgres thật (K23)."""

import os
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, Text, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db import migrate_check
from packages.db.migrate_check import SCRIPT_LOCATION, alembic_config, run_checks
from packages.testing.fixtures import db as db_fixtures

REVISION = '''\
"""{slug}"""

from collections.abc import Sequence

from alembic import op

revision: str = "{rev}"
down_revision: str | None = {down}
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    {upgrade}


def downgrade() -> None:
    {downgrade}
'''

BASELINE = "r20260920_b0_03"
THING = 'op.execute("CREATE TABLE thing (id integer PRIMARY KEY, code text)")'
DROP_THING = 'op.execute("DROP TABLE thing")'


def thing_metadata(extra_table: bool = False) -> MetaData:
    metadata = MetaData()
    Table("thing", metadata, Column("id", Integer, primary_key=True), Column("code", Text))
    if extra_table:
        Table("missing", metadata, Column("id", Integer, primary_key=True))
    return metadata


async def no_seed(session: AsyncSession, env: str) -> tuple[str, ...]:
    return ()


def insert_rows(count: int) -> Callable[[AsyncSession, str], Awaitable[tuple[str, ...]]]:
    async def seed(session: AsyncSession, env: str) -> tuple[str, ...]:
        for _ in range(count):
            await session.execute(text("INSERT INTO thing (id, code) SELECT coalesce(max(id), 0) + 1, 'x' FROM thing"))
        return ("thing",)

    return seed


async def rows_with_note(session: AsyncSession, env: str) -> tuple[str, ...]:
    """Seed idempotent, chạy khi cột `note` đã có (head đang áp dụng)."""
    await session.execute(
        text("INSERT INTO thing (id, code, note) VALUES (1, 'a', 'n'), (2, 'b', 'n') ON CONFLICT DO NOTHING")
    )
    return ("thing",)


@pytest.fixture
def migrations(tmp_path: Path) -> Path:
    directory = tmp_path / "migrations"
    (directory / "versions").mkdir(parents=True)
    for name in ("env.py", "script.py.mako"):
        shutil.copy(SCRIPT_LOCATION / name, directory / name)
    shutil.copy(SCRIPT_LOCATION / "versions" / f"{BASELINE}_baseline.py", directory / "versions")
    return directory


def add_revision(migrations: Path, rev: str, down: str | None, upgrade: str, downgrade: str = "pass") -> None:
    body = REVISION.format(
        slug=rev, rev=rev, down=f'"{down}"' if down else "None", upgrade=upgrade, downgrade=downgrade
    )
    (migrations / "versions" / f"{rev}_x.py").write_text(body, encoding="utf-8")


def failed_steps(results: list[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(name, detail) for name, detail in results if detail]


@pytest.fixture
def url(blank_db_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("DATABASE_URL", blank_db_url)  # run_checks đặt lại; monkeypatch trả về sau test
    return blank_db_url


async def test_good_migrations_pass(migrations: Path, url: str) -> None:
    add_revision(migrations, "r20260921_b9_01", BASELINE, THING, DROP_THING)
    results = await run_checks(alembic_config(migrations), url, metadata=thing_metadata(), seed_runner=no_seed)
    assert failed_steps(results) == []
    assert len(results) == 9


async def test_two_heads_fail_first_step(migrations: Path, url: str) -> None:
    add_revision(migrations, "r20260921_b9_01", BASELINE, THING, DROP_THING)
    add_revision(migrations, "r20260921_b9_02", None, "pass")
    results = await run_checks(alembic_config(migrations), url, metadata=thing_metadata(), seed_runner=no_seed)
    assert len(results) == 1
    assert "2 head" in results[0][1]


async def test_downgrade_leaving_table_fails(migrations: Path, url: str) -> None:
    # `IF NOT EXISTS` để lượt `upgrade head` sau khi downgrade vẫn chạy: bước hỏng phải là bước dọn.
    upgrade = 'op.execute("CREATE TABLE IF NOT EXISTS thing (id integer PRIMARY KEY, code text)")'
    add_revision(migrations, "r20260921_b9_01", BASELINE, upgrade, "pass")
    results = await run_checks(alembic_config(migrations), url, metadata=thing_metadata(), seed_runner=no_seed)
    failed = failed_steps(results)
    assert [name for name, _ in failed] == ["chỉ còn alembic_version"]
    assert "thing" in failed[0][1]


async def test_model_without_migration_fails(migrations: Path, url: str) -> None:
    add_revision(migrations, "r20260921_b9_01", BASELINE, THING, DROP_THING)
    results = await run_checks(
        alembic_config(migrations), url, metadata=thing_metadata(extra_table=True), seed_runner=no_seed
    )
    failed = failed_steps(results)
    assert [name for name, _ in failed] == ["model khớp DB"]
    assert "missing" in failed[0][1]


async def test_non_idempotent_seed_fails(migrations: Path, url: str) -> None:
    add_revision(migrations, "r20260921_b9_01", BASELINE, THING, DROP_THING)
    results = await run_checks(alembic_config(migrations), url, metadata=thing_metadata(), seed_runner=insert_rows(1))
    failed = failed_steps(results)
    assert [name for name, _ in failed] == ["seed ci hai lần"]
    assert "không idempotent" in failed[0][1]


async def test_revision_failing_on_existing_data(migrations: Path, url: str) -> None:
    """Revision mới nhất phải chạy được trên DB **có dữ liệu**, không chỉ DB trống."""
    add_revision(migrations, "r20260921_b9_01", BASELINE, THING, DROP_THING)
    add_revision(
        migrations,
        "r20260921_b9_02",
        "r20260921_b9_01",
        'op.execute("ALTER TABLE thing ADD COLUMN note text NOT NULL")',
        'op.execute("ALTER TABLE thing DROP COLUMN note")',
    )
    results = await run_checks(alembic_config(migrations), url, metadata=thing_metadata(), seed_runner=rows_with_note)
    failed = failed_steps(results)
    assert [name for name, _ in failed] == ["upgrade head trên DB có dữ liệu"]


def test_main_on_repo_migrations(url: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert migrate_check.main() == 0
    out = capsys.readouterr().out
    assert "migrate_check: đạt" in out
    assert out.count("đạt") == 10  # 9 bước con + dòng kết


def test_main_rejects_arguments(capsys: pytest.CaptureFixture[str]) -> None:
    assert migrate_check.main(["--fast"]) == 2
    assert "không nhận tham số" in capsys.readouterr().out


def test_main_starts_postgres_when_url_missing(
    blank_db_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stopped: list[bool] = []
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(migrate_check, "_start_postgres", lambda: (blank_db_url, lambda: stopped.append(True)))
    assert migrate_check.main() == 0
    assert stopped == [True]
    assert "migrate_check: đạt" in capsys.readouterr().out


def test_alembic_upgrade_restores_previous_database_url(blank_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture `db_template` chạy Alembic bằng biến môi trường; nó phải trả biến về như cũ."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://cũ:cũ@localhost:5432/cũ")
    db_fixtures._alembic_upgrade(blank_db_url)
    assert os.environ["DATABASE_URL"] == "postgresql+asyncpg://cũ:cũ@localhost:5432/cũ"
