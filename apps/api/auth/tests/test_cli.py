"""`python -m apps.api.auth.cli create-admin` (BE-00 §5): mã thoát 0/2/3, mật khẩu không lộ."""

import asyncio
import getpass
import io
import logging
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import cli
from apps.api.auth.passwords import verify_password
from packages.db.models.auth import User

REPO_ROOT: Final = Path(__file__).resolve().parents[4]
PASSWORD: Final = "mat-khau-admin-dau-tien"  # noqa: S105 — mật khẩu giả của test


async def _run(argv: list[str], monkeypatch: pytest.MonkeyPatch, stdin: str = PASSWORD + "\n") -> int:
    """Chạy `main` trong luồng riêng (nó tự `asyncio.run`), stdin là chuỗi cho trước."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    return await asyncio.to_thread(cli.main, argv)


def _create(email: str, name: str = "Quản trị viên") -> list[str]:
    """Tham số của một lượt `create-admin` đọc mật khẩu từ stdin."""
    return ["create-admin", "--email", email, "--name", name, "--password-stdin"]


async def test_create_admin_exits_0_and_prints_the_id(
    auth_env: None,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tạo admin `active` với mật khẩu băm từ stdin, in `usr_…`; mật khẩu không có trong stdout hay log."""
    caplog.set_level(logging.DEBUG)
    assert await _run(_create("  Admin@Cty.vn "), monkeypatch) == 0
    out, err = capsys.readouterr()
    user = (await db_session.execute(select(User).where(User.email_normalized == "admin@cty.vn"))).scalar_one()
    assert out == f"{user.id}\n"
    assert (user.email, user.role, user.status, user.name) == ("Admin@Cty.vn", "admin", "active", "Quản trị viên")
    assert await verify_password(user.password_hash, PASSWORD)
    assert PASSWORD not in out + err + caplog.text


async def test_existing_email_exits_3(
    auth_env: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Email đã có (khác hoa thường vẫn là trùng, C16) → thoát 3, không tạo dòng thứ hai."""
    assert await _run(_create("root@example.com"), monkeypatch) == 0
    assert await _run(_create("ROOT@example.com"), monkeypatch) == 3
    assert "đã có" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "stdin"),
    [
        (_create("admin@localhost"), PASSWORD + "\n"),
        (_create("root@example.com"), "ngan\n"),
        (_create("root@example.com", name="   "), PASSWORD + "\n"),
        (_create("root@example.com", name="x" * 121), PASSWORD + "\n"),
    ],
    ids=["email", "mat-khau-ngan", "ten-rong", "ten-dai"],
)
async def test_invalid_input_exits_2(
    auth_env: None, monkeypatch: pytest.MonkeyPatch, argv: list[str], stdin: str
) -> None:
    """Email sai `validate_wire_email`, mật khẩu < 8 ký tự, tên rỗng hay dài quá 120 → thoát 2."""
    assert await _run(argv, monkeypatch, stdin) == 2


async def test_password_can_come_from_getpass(
    auth_env: None, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Không `--password-stdin` → hỏi bằng `getpass` (không hiện chữ), không đọc stdin."""
    monkeypatch.setattr(getpass, "getpass", lambda prompt: PASSWORD)
    argv = ["create-admin", "--email", "hoi@example.com", "--name", "Hỏi"]
    assert await _run(argv, monkeypatch, stdin="") == 0
    user = (await db_session.execute(select(User).where(User.email_normalized == "hoi@example.com"))).scalar_one()
    assert await verify_password(user.password_hash, PASSWORD)


def test_module_entry_point_exits_2_on_a_bad_email() -> None:
    """`python -m apps.api.auth.cli` thật: email sai thoát 2 trước khi chạm DB hay stdin."""
    completed = subprocess.run(
        [sys.executable, "-m", "apps.api.auth.cli", "create-admin", "--email", "x@localhost", "--name", "A"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 2
    assert completed.stdout == ""
