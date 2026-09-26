"""`python -m apps.api.spatial_read.cli check-documents` (B3-02 [6], FIX.md luật 6)."""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read import cli
from apps.api.spatial_read.settings import reset_spatial_read_settings_cache
from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.db.models.spatial import FloorDocumentRow
from packages.db.seeds import apply_seeds
from packages.db.settings import reset_database_settings_cache

REPO_ROOT: Final = Path(__file__).resolve().parents[4]


@pytest.fixture
def cli_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`DATABASE_URL` của CLI trỏ vào database thật của test; cache settings sạch cả hai đầu."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", str(int(GATE_CONNECT_TIMEOUT_S)))
    reset_database_settings_cache()
    reset_spatial_read_settings_cache()
    yield
    reset_database_settings_cache()
    reset_spatial_read_settings_cache()


async def _run(argv: list[str]) -> int:
    """Chạy `main` trong luồng riêng (nó tự `asyncio.run`, không dùng được vòng của test)."""
    return await asyncio.to_thread(cli.main, argv)


async def _seeded(db: AsyncSession) -> list[int]:
    """Chạy seed rồi trả `floor_pk` của các tài liệu, tăng dần."""
    await apply_seeds(db, "ci")
    await db.commit()
    rows = await db.execute(text("SELECT floor_pk FROM floor_documents ORDER BY floor_pk"))
    return [pk for (pk,) in rows.all()]


async def test_clean_seed_exits_0(cli_env: None, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]) -> None:
    """Seed sạch → thoát 0 và không in gì."""
    assert len(await _seeded(db_session)) == 4
    assert await _run(["check-documents"]) == 0
    assert capsys.readouterr().out == ""


async def test_corrupt_rows_are_printed_and_exit_1(
    cli_env: None,
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Khoá lạ và `schema_version=2` (ghi bằng SQL) → in đúng hai `floor_pk`, thoát 1, qua nhiều lô."""
    pks = await _seeded(db_session)
    await db_session.execute(
        text("UPDATE floor_documents SET document = document || '{\"stray\": 1}'::jsonb WHERE floor_pk = :pk"),
        {"pk": pks[1]},
    )
    await db_session.execute(
        update(FloorDocumentRow).where(FloorDocumentRow.floor_pk == pks[3]).values(schema_version=2)
    )
    await db_session.commit()
    monkeypatch.setenv("SPATIAL_RECOUNT_BATCH", "1")
    reset_spatial_read_settings_cache()

    assert await _run(["check-documents"]) == 1
    assert capsys.readouterr().out.split() == [str(pks[1]), str(pks[3])]


def test_bad_arguments_exit_2(cli_env: None) -> None:
    """Thiếu lệnh con → argparse thoát 2 trước khi chạm DB."""
    with pytest.raises(SystemExit) as raised:
        cli.main([])
    assert raised.value.code == 2


def test_module_runs_as_a_script(db_url: str) -> None:
    """`python -m apps.api.spatial_read.cli` thật (tiến trình con): DB rỗng → thoát 0."""
    env = {
        "DATABASE_URL": db_url,
        "DB_CONNECT_TIMEOUT_S": str(int(GATE_CONNECT_TIMEOUT_S)),
        "PYTHONPATH": str(REPO_ROOT),
    }
    done = subprocess.run(
        [sys.executable, "-m", "apps.api.spatial_read.cli", "check-documents"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env={**os.environ, **env},
        timeout=60,
        check=False,
    )
    assert done.returncode == 0, done.stderr
