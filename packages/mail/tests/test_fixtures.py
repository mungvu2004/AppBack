"""`packages/testing/fixtures/mail.py`: `extract_token`, `MailpitInbox.wait_for`, máy chủ SMTP tối thiểu."""

import pytest

from packages.mail.message import MailMessage
from packages.mail.sender import SmtpMailer
from packages.mail.settings import get_mail_settings
from packages.testing.fixtures.mail import MailpitInbox, _RejectingSmtpServer, extract_token


def test_extract_token_from_mail_message() -> None:
    message = MailMessage(to="a@b.test", subject="s", text="bấm vào đây #token=abcDEF123 để tiếp tục", html="<p>x</p>")

    assert extract_token(message) == "abcDEF123"


def test_extract_token_from_mailpit_dict() -> None:
    mailpit_message = {"Text": "link https://appback.test/login/reset-password#token=xyz789\n"}

    assert extract_token(mailpit_message) == "xyz789"


def test_extract_token_missing_raises() -> None:
    message = MailMessage(to="a@b.test", subject="s", text="không có token nào ở đây", html="<p>x</p>")

    with pytest.raises(AssertionError):
        extract_token(message)


def test_extract_token_from_dict_without_text_key_raises() -> None:
    with pytest.raises(AssertionError):
        extract_token({})


def test_wait_for_times_out_when_no_message_matches(mailpit_inbox: MailpitInbox) -> None:
    with pytest.raises(AssertionError, match="không thấy thư"):
        mailpit_inbox.wait_for("khong-ai-nhan@appback.test", timeout_s=0.2)


def test_wait_for_skips_messages_to_other_recipients(mailpit_inbox: MailpitInbox) -> None:
    """Hộp thư có hai thư — Mailpit liệt kê thư mới nhất trước, nên thư đúng gửi **trước** để bị lướt qua khi tìm."""
    mailer = SmtpMailer(get_mail_settings())
    mailer.send(MailMessage(to="nguoi-can-tim@appback.test", subject="s1", text="t1", html="<p>t1</p>"))
    mailer.send(MailMessage(to="nguoi-khac@appback.test", subject="s2", text="t2", html="<p>t2</p>"))

    found = mailpit_inbox.wait_for("nguoi-can-tim@appback.test", timeout_s=5)

    assert found["Subject"] == "s1"


def test_rejecting_smtp_server_closes_while_waiting_for_a_connection() -> None:
    """Đóng ngay sau khi khởi động — luồng nền gần như chắc chắn đang kẹt trong `accept()` (nhánh OSError)."""
    server = _RejectingSmtpServer()
    server.start()

    server.close()
    server.join(timeout=2.0)

    assert not server.is_alive()
