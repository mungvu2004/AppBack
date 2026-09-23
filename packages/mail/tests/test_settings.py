"""`MailSettings`: thiếu tham số bắt buộc theo backend hoặc backend sai môi trường → hỏng lúc nạp."""

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from packages.core.settings import reset_settings_cache
from packages.mail.settings import MailSettings, get_mail_settings, reset_mail_settings_cache

APP_URL = "https://appback.test"
_ENV_NAMES = (
    "MAIL_BACKEND",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_STARTTLS",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "MAIL_FROM",
    "SMTP_TIMEOUT_S",
)


@pytest.fixture(autouse=True)
def mail_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Môi trường sạch của gói thư; `APP_ENV=test` (test tự đổi khi cần)."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", APP_URL)
    monkeypatch.setenv("SECRET_KEY", "secret-du-dai-cho-cau-hinh-b1-03")
    for name in _ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    reset_settings_cache()
    reset_mail_settings_cache()
    yield
    reset_settings_cache()
    reset_mail_settings_cache()


def smtp_settings(**overrides: object) -> MailSettings:
    """`MailSettings` backend SMTP hợp lệ, cho phép ghi đè từng trường để kiểm một luật."""
    fields: dict[str, object] = {"mail_backend": "smtp", "smtp_host": "mailpit", "mail_from": "no-reply@appback.test"}
    fields.update(overrides)
    return MailSettings(**fields)  # type: ignore[arg-type]  # dựng cấu hình từ dict linh hoạt cho test


def test_smtp_is_the_default_backend() -> None:
    assert smtp_settings().mail_backend == "smtp"


def test_smtp_backend_needs_a_host() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        smtp_settings(smtp_host=None)


def test_smtp_backend_needs_a_from_address() -> None:
    with pytest.raises(ValidationError, match="SMTP_HOST"):
        smtp_settings(mail_from=None)


def test_smtp_username_without_password_fails() -> None:
    with pytest.raises(ValidationError, match="SMTP_USERNAME"):
        smtp_settings(smtp_username="bot")


def test_smtp_password_without_username_fails() -> None:
    with pytest.raises(ValidationError, match="SMTP_USERNAME"):
        smtp_settings(smtp_password="s3cret")  # noqa: S106 — mật khẩu giả của test


def test_smtp_username_and_password_together_is_fine() -> None:
    settings = smtp_settings(smtp_username="bot", smtp_password="s3cret")  # noqa: S106 — mật khẩu giả của test

    assert settings.smtp_username == "bot"
    assert settings.smtp_password is not None
    assert settings.smtp_password.get_secret_value() == "s3cret"


def test_smtp_port_out_of_range_fails() -> None:
    with pytest.raises(ValidationError):
        smtp_settings(smtp_port=0)


def test_memory_backend_in_dev_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "dev")
    reset_settings_cache()

    with pytest.raises(ValidationError, match="MAIL_BACKEND=memory"):
        MailSettings(mail_backend="memory")


def test_memory_backend_in_test_env_is_fine() -> None:
    assert MailSettings(mail_backend="memory").mail_backend == "memory"


def test_get_mail_settings_reads_env_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAIL_BACKEND", "memory")

    assert get_mail_settings().mail_backend == "memory"
    monkeypatch.setenv("MAIL_BACKEND", "smtp")
    assert get_mail_settings().mail_backend == "memory"

    reset_mail_settings_cache()
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.setenv("MAIL_FROM", "no-reply@appback.test")
    assert get_mail_settings().mail_backend == "smtp"
