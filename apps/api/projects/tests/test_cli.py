"""`python -m apps.api.projects.cli add-member` (B2-01 [2]): mã thoát 0/1, không ghi nhật ký."""

import asyncio
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects import cli
from packages.db.engine import GATE_CONNECT_TIMEOUT_S
from packages.db.models.projects import ProjectMembership
from packages.db.settings import reset_database_settings_cache
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.access import activity_rows

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
DELETED_AT = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def cli_env(db_url: str, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`DATABASE_URL` của CLI trỏ vào database thật của test; cache settings sạch cả hai đầu."""
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", str(int(GATE_CONNECT_TIMEOUT_S)))
    reset_database_settings_cache()
    yield
    reset_database_settings_cache()


async def _run(argv: list[str]) -> int:
    """Chạy `main` trong luồng riêng (nó tự `asyncio.run`, không dùng được vòng của test)."""
    return await asyncio.to_thread(cli.main, argv)


def _add(project_id: str, email: str) -> list[str]:
    """Tham số của một lượt `add-member`."""
    return ["add-member", "--project", project_id, "--email", email]


async def test_add_member_exits_0_and_writes_a_system_cli_row(
    cli_env: None,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Thêm được → thoát 0, dòng membership có `added_by="system:cli"`, **0** dòng nhật ký."""
    owner = await make_user(db_session)
    guest = await make_user(db_session, email="Khach@Cty.VN")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()

    assert await _run(_add(project.id, "khach@cty.vn")) == 0
    assert project.id in capsys.readouterr().out
    async with db_sessionmaker() as fresh:
        row = (
            await fresh.execute(
                select(ProjectMembership).where(
                    ProjectMembership.project_id == project.id, ProjectMembership.user_id == guest.id
                )
            )
        ).scalar_one()
        assert row.added_by == "system:cli"
    assert await activity_rows(db_sessionmaker) == []


async def test_adding_the_same_member_twice_exits_0(
    cli_env: None, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Lệnh idempotent: người vốn đã là thành viên vẫn thoát 0, không ném."""
    owner = await make_user(db_session)
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    assert await _run(_add(project.id, owner.email)) == 0
    assert "đã là thành viên" in capsys.readouterr().out


async def test_unknown_email_exits_1(
    cli_env: None, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Email không có người dùng nào (hay người đã xoá mềm) → thoát 1, câu tiếng Việt ra stderr."""
    owner = await make_user(db_session)
    gone = await make_user(db_session)
    gone.deleted_at = DELETED_AT
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    assert await _run(_add(project.id, "khong-ai@example.com")) == 1
    assert await _run(_add(project.id, gone.email)) == 1
    assert "không có người dùng" in capsys.readouterr().err


async def test_unknown_project_exits_1(
    cli_env: None, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dự án lạ, hay dự án đã xoá mềm → thoát 1."""
    owner = await make_user(db_session)
    removed = await make_project(db_session, owner=owner, deleted_at=DELETED_AT)
    await db_session.commit()
    assert await _run(_add("prj_khong-co", owner.email)) == 1
    assert await _run(_add(removed.id, owner.email)) == 1
    assert "không có dự án" in capsys.readouterr().err


async def test_disabled_user_exits_1(
    cli_env: None, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    """Người bị vô hiệu không được thêm vào dự án nào → thoát 1."""
    owner = await make_user(db_session)
    blocked = await make_user(db_session, status="disabled")
    project = await make_project(db_session, owner=owner)
    await db_session.commit()
    assert await _run(_add(project.id, blocked.email)) == 1
    assert "vô hiệu" in capsys.readouterr().err


def test_module_entry_point_exits_2_without_arguments() -> None:
    """`python -m apps.api.projects.cli` thật: thiếu `--project` → argparse thoát 2, chưa chạm DB."""
    completed = subprocess.run(
        [sys.executable, "-m", "apps.api.projects.cli", "add-member", "--email", "a@example.com"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
