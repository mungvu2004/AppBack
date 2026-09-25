"""Cổng mời `ProjectInviteSink` và ranh giới import của module (B2-02 [2], [8])."""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.project_members import sinks
from apps.api.project_members.sinks import invite_sink
from apps.api.project_members.tests.support import SINKS_SUBMODULE, RecordingSink
from packages.core.clock import SystemClock
from packages.core.settings import reset_settings_cache

PACKAGE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = PACKAGE_DIR.parent.parent.parent


def _app() -> Any:
    """Chỗ treo `override`: `extensions` chỉ cần một object bất kỳ."""
    return type("App", (), {})()


@pytest.fixture(autouse=True)
def _test_env(storage_env: None) -> None:
    """`extensions.override` chỉ chạy khi `APP_ENV=test`; `storage_env` đặt biến ấy (B0-04)."""


def test_invite_sink__none_installed_is_noop() -> None:
    """Không module nào cắm → sink no-op dùng được (chưa B4-02 vẫn chạy)."""
    app = _app()
    extensions.override(app, SINKS_SUBMODULE, [])
    assert isinstance(invite_sink(app=app), sinks._NoopSink)


async def test_invite_sink__noop_accepts_the_call(db_session: AsyncSession) -> None:
    """Sink no-op nhận đúng chữ ký của cổng và không làm gì."""
    await sinks._NoopSink().on_member_added(
        db_session, project_id="p", project_name="n", user_id="u", actor_id="a", clock=SystemClock()
    )


def test_invite_sink__no_override_discovers_real_modules() -> None:
    """`app=None` → dò thật; trên nhánh này chưa module nào có `invite_sinks.py` → no-op."""
    assert isinstance(invite_sink(), sinks._NoopSink)


def test_invite_sink__single_is_used() -> None:
    """Đúng một sink trong một module → chính nó."""
    app, sink = _app(), RecordingSink()
    extensions.override(app, SINKS_SUBMODULE, [("mot", [sink])])
    assert invite_sink(app=app) is sink


def test_invite_sink__two_modules_raise() -> None:
    """Hai module cùng export `SINKS` (tổng 2) → `RuntimeError`."""
    app = _app()
    extensions.override(app, SINKS_SUBMODULE, [("mot", [RecordingSink()]), ("hai", [RecordingSink()])])
    with pytest.raises(RuntimeError, match="chỉ được cắm một"):
        invite_sink(app=app)


def test_invite_sink__two_in_one_module_raise() -> None:
    """Tổng đếm qua phần tử: một module xuất hai sink cũng là hai."""
    app = _app()
    extensions.override(app, SINKS_SUBMODULE, [("mot", (RecordingSink(), RecordingSink()))])
    with pytest.raises(RuntimeError, match="chỉ được cắm một"):
        invite_sink(app=app)


def test_invite_sink__non_sequence_raises() -> None:
    """`SINKS` không phải list/tuple → `RuntimeError` (khai sai)."""
    app = _app()
    extensions.override(app, SINKS_SUBMODULE, [("mot", RecordingSink())])
    with pytest.raises(RuntimeError, match="list hoặc tuple"):
        invite_sink(app=app)


def test_override_only_in_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """`override` ở `APP_ENV=dev` → `RuntimeError`."""
    monkeypatch.setenv("APP_ENV", "dev")
    reset_settings_cache()
    try:
        with pytest.raises(RuntimeError, match="APP_ENV=test"):
            extensions.override(_app(), SINKS_SUBMODULE, [])
    finally:
        monkeypatch.undo()
        reset_settings_cache()


def test_boundary__sinks_import_without_web_libraries() -> None:
    """Nhập `sinks` và gọi `invite_sink()` khi `fastapi`, `jwt`, `argon2` bị chặn → không lỗi (B4-02 nhập nó)."""
    code = (
        "import sys\n"
        "for name in ('fastapi', 'jwt', 'argon2'):\n"
        "    sys.modules[name] = None\n"
        "from apps.api.project_members.sinks import invite_sink\n"
        "invite_sink()\n"
    )
    result = subprocess.run(  # noqa: S603 — mã cố định của test, không nhận đầu vào ngoài
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=60, check=False
    )
    assert result.returncode == 0, result.stderr


def test_boundary__init_is_docstring_only() -> None:
    """`__init__.py` chỉ có docstring."""
    tree = ast.parse((PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8"))
    assert len(tree.body) == 1
    stmt = tree.body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Constant)
    assert isinstance(stmt.value.value, str)
