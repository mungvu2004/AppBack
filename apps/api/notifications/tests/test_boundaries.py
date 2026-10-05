"""Ranh giới import, cấu hình và `__init__` của module thông báo (B4-02 [8] "Nhập", [5])."""

import ast
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from pydantic import ValidationError

from apps.api.notifications.schemas import NotificationMarkReadBody
from apps.api.notifications.settings import NotificationsSettings, get_notifications_settings
from apps.api.notifications.tests.support import settings_env
from packages.testing.boundary import WORKER_BLOCKED

PACKAGE_DIR: Final = Path(__file__).resolve().parent.parent
REPO_ROOT: Final = PACKAGE_DIR.parent.parent.parent
WORKER_MODULES: Final = ("service", "payload", "messages", "kinds", "settings", "jobs", "invite_sinks")


@pytest.mark.parametrize("module", WORKER_MODULES)
def test_boundary__worker_modules_import_without_web_libraries(module: str) -> None:
    """Nhập được khi 5 gói web/mật mã (ranh giới `.importlinter`) bị chặn trong `sys.modules` (BE-00 §7)."""
    code = (
        "import sys\n"
        f"for name in {WORKER_BLOCKED!r}:\n"
        "    sys.modules[name] = None\n"
        f"import apps.api.notifications.{module}\n"
    )
    result = subprocess.run(  # noqa: S603 — mã cố định của test, không nhận đầu vào ngoài
        [sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120, check=False
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


def test_settings__defaults() -> None:
    """Mặc định đúng khối [5]."""
    settings = NotificationsSettings()
    assert (
        settings.notifications_list_max,
        settings.notifications_mark_max,
        settings.notifications_keep_max,
        settings.notifications_dedupe_ttl_s,
        settings.notifications_unsent_after_s,
        settings.notifications_unsent_window_s,
        settings.notifications_sweep_batch,
        settings.notifications_hidden_purge_after_s,
    ) == (200, 200, 200, 86400, 120, 43200, 500, 2592000)


def test_settings__window_twice_must_fit_in_dedupe_ttl() -> None:
    """`UNSENT_WINDOW_S x 2 > DEDUPE_TTL_S` → hỏng lúc nạp; đúng bằng thì qua."""
    with pytest.raises(ValidationError, match="UNSENT_WINDOW_S"):
        NotificationsSettings(notifications_unsent_window_s=43201)
    assert NotificationsSettings(notifications_unsent_window_s=43200).notifications_unsent_window_s == 43200


def test_settings__env_override_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Biến môi trường được đọc một lần mỗi tiến trình; xoá cache mới đọc lại."""
    with settings_env(monkeypatch, list_max="3"):
        assert get_notifications_settings().notifications_list_max == 3
        assert get_notifications_settings() is get_notifications_settings()
    assert get_notifications_settings().notifications_list_max == 200


def test_mark_body__schema_max_items_is_the_settings_default() -> None:
    """`maxItems` của `openapi.json` cùng một nguồn với mặc định `notifications_mark_max`."""
    schema = NotificationMarkReadBody.model_json_schema()
    assert schema["properties"]["ids"]["maxItems"] == NotificationsSettings().notifications_mark_max
