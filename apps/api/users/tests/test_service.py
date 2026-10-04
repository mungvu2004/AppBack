"""Hàm thuần và cấu hình của `apps/api/users/service.py` (không cần app, không cần DB)."""

import logging

import pytest

from apps.api.users import service
from apps.api.users.service import WriteScope, get_users_settings, reset_users_settings_cache
from packages.core.errors import AppError
from packages.db.models.auth import User


def _user(user_id: str, *, status: str = "active") -> User:
    """`User` trong bộ nhớ (không qua DB) đủ trường mà hàm thuần đọc."""
    return User(id=user_id, email=f"{user_id}@example.com", email_normalized=f"{user_id}@example.com", status=status)


@pytest.mark.parametrize(
    ("admins", "code"), [(("usr_a",), "USER_LAST_ADMIN"), (("usr_a", "usr_b"), "USER_SELF_MODIFICATION")]
)
def test_forbid_self_reports_last_admin_first(admins: tuple[str, ...], code: str) -> None:
    """Tự sửa mình: admin `active` duy nhất → `USER_LAST_ADMIN`, còn admin khác → `USER_SELF_MODIFICATION` (NO-206)."""
    scope = WriteScope(actor_id="usr_a", target=_user("usr_a"), admins=admins)
    with pytest.raises(AppError) as caught:
        scope.forbid_self()
    assert caught.value.code.code == code


def test_forbid_self_allows_another_target() -> None:
    """Mục tiêu là người khác → không ném, kể cả khi người thực hiện là admin duy nhất."""
    WriteScope(actor_id="usr_a", target=_user("usr_b"), admins=("usr_a",)).forbid_self()


def test_pending_or_taken_rejects_missing_and_non_pending() -> None:
    """Đọc lại không thấy người, hay thấy người `active` → `USER_EMAIL_TAKEN`; `pending` → trả nguyên người đó."""
    pending = _user("usr_p", status="pending")
    assert service._pending_or_taken(pending) is pending
    for found in (None, _user("usr_x")):
        with pytest.raises(AppError) as caught:
            service._pending_or_taken(found)
        assert caught.value.code.code == "USER_EMAIL_TAKEN"


def test_settings_defaults_and_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định 1000/1000/200/50; đổi biến môi trường chỉ có hiệu lực sau `reset_users_settings_cache`."""
    reset_users_settings_cache()
    settings = get_users_settings()
    assert (settings.users_list_max, settings.user_memberships_max, settings.user_activity_max) == (1000, 1000, 200)
    assert settings.invite_batch_max == 50
    monkeypatch.setenv("INVITE_BATCH_MAX", "3")
    assert get_users_settings().invite_batch_max == 50
    reset_users_settings_cache()
    assert get_users_settings().invite_batch_max == 3
    monkeypatch.delenv("INVITE_BATCH_MAX")
    reset_users_settings_cache()


def test_warn_orphans_logs_each_project(caplog: pytest.LogCaptureFixture) -> None:
    """Mỗi dự án mồ côi một dòng cảnh báo `project_orphaned` có id dự án và id người bị xoá."""
    with caplog.at_level(logging.WARNING, logger=service.__name__):
        service._warn_orphans(["prj_1", "prj_2"], "usr_x")
    logged = [(r.getMessage(), r.__dict__["projectId"], r.__dict__["userId"]) for r in caplog.records]
    assert logged == [("project_orphaned", "prj_1", "usr_x"), ("project_orphaned", "prj_2", "usr_x")]
