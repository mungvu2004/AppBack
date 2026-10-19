"""Test `apps/api/auth_recovery/messages.py`: link, escape tên, không rò dữ liệu vào subject (B1-03 [6])."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from apps.api.auth_recovery.messages import build_token_mail
from packages.core.settings import reset_settings_cache
from packages.testing.fixtures.storage import PUBLIC_BASE_URL, STORAGE_SECRET

EXPIRES_AT = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
TOKEN = "token-gia-lap-01"  # noqa: S105 — token giả của test


@pytest.fixture(autouse=True)
def _core_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """`get_core_settings()` cần `APP_ENV`/`PUBLIC_BASE_URL`/`SECRET_KEY` để đọc được (B0-06)."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    monkeypatch.setenv("SECRET_KEY", STORAGE_SECRET)
    reset_settings_cache()
    yield
    reset_settings_cache()


def test_build_token_mail_invite_link_and_subject() -> None:
    message = build_token_mail(purpose="invite", to="a@b.test", name="Nguyễn Văn A", token=TOKEN, expires_at=EXPIRES_AT)

    assert message.to == "a@b.test"
    assert message.subject == "Lời mời tham gia AppFront"
    assert "Nguyễn Văn A" not in message.subject
    link = f"{PUBLIC_BASE_URL}/login/invitation#token={TOKEN}"
    assert link in message.text
    assert link in message.html
    assert "10:04 ngày 02/01/2026 (giờ Việt Nam)" in message.text  # 03:04 UTC + 7
    assert "UTC" not in message.text
    assert "AppBack" not in message.text + message.html
    assert "Bạn được mời tham gia AppFront." in message.text
    assert "liên kết trong thư cũ không còn dùng được" in message.text


def test_build_token_mail_invite_names_role_and_inviter() -> None:
    """Thư mời nêu người mời và vai (G2-11); tên người mời escape trong html."""
    message = build_token_mail(
        purpose="invite",
        to="a@b.test",
        name="a",
        token=TOKEN,
        expires_at=EXPIRES_AT,
        role="engineer",
        inviter="Lê <Minh>",
    )

    assert "Lê <Minh> đã mời bạn tham gia AppFront với vai Kỹ sư." in message.text
    assert "Lê &lt;Minh&gt; đã mời bạn" in message.html


def test_build_token_mail_invite_role_without_inviter() -> None:
    """Không biết người mời (đã xoá) → câu vô danh, vẫn nêu vai."""
    message = build_token_mail(
        purpose="invite", to="a@b.test", name="a", token=TOKEN, expires_at=EXPIRES_AT, role="viewer"
    )

    assert "Bạn được mời tham gia AppFront với vai Người xem." in message.text


def test_build_token_mail_password_reset_link() -> None:
    message = build_token_mail(purpose="password_reset", to="a@b.test", name="A", token=TOKEN, expires_at=EXPIRES_AT)

    link = f"{PUBLIC_BASE_URL}/login/reset-password#token={TOKEN}"
    assert link in message.text
    assert link in message.html
    assert message.subject == "Yêu cầu đặt lại mật khẩu AppFront"
    assert "Có yêu cầu đặt lại mật khẩu cho tài khoản AppFront của bạn." in message.text
    assert "Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua thư này" in message.text
    assert "10:04 ngày 02/01/2026 (giờ Việt Nam)" in message.text
    assert "đã mời bạn" not in message.text


def test_build_token_mail_password_reset_ignores_invite_fields() -> None:
    """`role`/`inviter` truyền nhầm vào thư đặt lại mật khẩu không lọt vào thư."""
    message = build_token_mail(
        purpose="password_reset",
        to="a@b.test",
        name="A",
        token=TOKEN,
        expires_at=EXPIRES_AT,
        role="admin",
        inviter="X",
    )

    assert "Quản trị viên" not in message.text
    assert "X đã mời" not in message.text


def test_build_token_mail_escapes_name_in_html_only() -> None:
    evil_name = "<script>alert(1)</script>"

    message = build_token_mail(purpose="invite", to="a@b.test", name=evil_name, token=TOKEN, expires_at=EXPIRES_AT)

    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html
    assert evil_name in message.text  # thân text không phải HTML, không cần escape
