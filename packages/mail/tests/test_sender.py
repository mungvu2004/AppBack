"""`SmtpMailer`, `MemoryMailer`, `create_mailer` và ánh xạ lỗi SMTP (B1-03 [2])."""

import smtplib
import socket
import threading
from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest

from packages.mail.message import MailMessage
from packages.mail.sender import (
    MailRejectedError,
    MailTransientError,
    MemoryMailer,
    SmtpMailer,
    _map_smtp_error,
    create_mailer,
)
from packages.mail.settings import MailSettings, get_mail_settings
from packages.testing.fixtures.mail import MailpitInbox
from packages.testing.fixtures.services import refused_url

MESSAGE = MailMessage(
    to="nguoi-nhan@appback.test", subject="chào bạn", text="xin chào #token=abc123", html="<p>xin chào</p>"
)


def _settings(**overrides: object) -> MailSettings:
    fields: dict[str, object] = {
        "mail_backend": "smtp",
        "smtp_host": "127.0.0.1",
        "mail_from": "no-reply@appback.test",
        "smtp_starttls": False,
        "smtp_timeout_s": 2,
    }
    fields.update(overrides)
    return MailSettings(**fields)  # type: ignore[arg-type]  # dựng cấu hình từ dict linh hoạt cho test


# --- Gửi thật qua Mailpit -----------------------------------------------------------------


def test_send_via_mailpit_reaches_the_inbox(mailpit_inbox: MailpitInbox) -> None:
    """`mailpit_inbox` đã đặt `MAIL_BACKEND`/`SMTP_HOST`/`SMTP_PORT` qua env — đọc lại từ đó."""
    mailer = SmtpMailer(get_mail_settings())
    mailer.send(MESSAGE)

    delivered = mailpit_inbox.wait_for(MESSAGE.to, timeout_s=5)
    assert delivered["Subject"] == MESSAGE.subject
    assert "xin chào" in delivered["Text"]
    assert "<p>xin chào</p>" in delivered["HTML"]


# --- Lỗi mất kết nối / timeout → thử lại được ---------------------------------------------


def test_send_to_closed_port_is_transient() -> None:
    parts = urlsplit(refused_url("smtp"))
    mailer = SmtpMailer(_settings(smtp_host=parts.hostname, smtp_port=parts.port))

    with pytest.raises(MailTransientError):
        mailer.send(MESSAGE)


# --- Máy chủ SMTP tối thiểu trả 550 (miễn K23, chỉ J03) ------------------------------------


def test_send_rejected_by_smtp_550(smtp_reject_server: tuple[str, int]) -> None:
    host, port = smtp_reject_server
    mailer = SmtpMailer(_settings(smtp_host=host, smtp_port=port))

    with pytest.raises(MailRejectedError) as excinfo:
        mailer.send(MESSAGE)
    assert excinfo.value.smtp_code == 550


# --- STARTTLS/AUTH mà máy chủ không hỗ trợ là lỗi cấu hình, không phải lỗi thư (R-16) ------


def test_starttls_requested_but_unsupported_bubbles(smtp_reject_server: tuple[str, int]) -> None:
    """`smtp_reject_server` không quảng cáo STARTTLS ở EHLO — `client.starttls()` hỏng cục bộ, không qua mạng."""
    host, port = smtp_reject_server
    mailer = SmtpMailer(_settings(smtp_host=host, smtp_port=port, smtp_starttls=True))

    with pytest.raises(smtplib.SMTPException):
        mailer.send(MESSAGE)


def test_login_requested_but_unsupported_bubbles(smtp_reject_server: tuple[str, int]) -> None:
    """`smtp_reject_server` không quảng cáo AUTH ở EHLO — `client.login()` hỏng cục bộ."""
    host, port = smtp_reject_server
    mailer = SmtpMailer(
        _settings(smtp_host=host, smtp_port=port, smtp_username="bot", smtp_password="s3cret")  # noqa: S106
    )

    with pytest.raises(smtplib.SMTPException):
        mailer.send(MESSAGE)


# --- Máy chủ con 4xx dựng trong file test (không thêm fixture mới) -------------------------


class _TransientSmtpServer(threading.Thread):
    """Trả `451` cho `RCPT TO` — máy chủ dùng chỉ trong test này, không đưa vào fixture chung."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self._sock.settimeout(1.0)
        self.host, self.port = self._sock.getsockname()
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            with conn:
                conn.settimeout(5.0)
                conn.sendall(b"220 transient ready\r\n")
                buffer = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        return
                    buffer += chunk
                    while b"\r\n" in buffer:
                        line, buffer = buffer.split(b"\r\n", 1)
                        if line.upper().startswith(b"RCPT TO"):
                            conn.sendall(b"451 try again later\r\n")
                        elif line.upper().startswith(b"QUIT"):
                            conn.sendall(b"221 bye\r\n")
                            return
                        else:
                            conn.sendall(b"250 ok\r\n")

    def close(self) -> None:
        self._stop_event.set()
        self._sock.close()


@pytest.fixture
def transient_smtp_server() -> Iterator[tuple[str, int]]:
    server = _TransientSmtpServer()
    server.start()
    try:
        yield server.host, server.port
    finally:
        server.close()
        server.join(timeout=2.0)


def test_send_with_4xx_response_is_transient(transient_smtp_server: tuple[str, int]) -> None:
    host, port = transient_smtp_server
    mailer = SmtpMailer(_settings(smtp_host=host, smtp_port=port))

    with pytest.raises(MailTransientError) as excinfo:
        mailer.send(MESSAGE)
    assert excinfo.value.smtp_code == 451


# --- Ánh xạ lỗi (_map_smtp_error), kiểm trực tiếp mọi nhánh --------------------------------


def test_map_all_5xx_recipients_refused_is_rejected() -> None:
    exc = smtplib.SMTPRecipientsRefused({"a@b.test": (550, b"no"), "c@d.test": (553, b"no")})

    mapped = _map_smtp_error(exc)

    assert isinstance(mapped, MailRejectedError)
    assert mapped.smtp_code is None  # nhiều người nhận, không có một mã duy nhất


def test_single_5xx_recipient_refused_keeps_its_code() -> None:
    exc = smtplib.SMTPRecipientsRefused({"a@b.test": (550, b"no")})

    mapped = _map_smtp_error(exc)

    assert isinstance(mapped, MailRejectedError)
    assert mapped.smtp_code == 550


def test_any_4xx_recipient_refused_is_transient() -> None:
    exc = smtplib.SMTPRecipientsRefused({"a@b.test": (550, b"no"), "c@d.test": (451, b"try again")})

    mapped = _map_smtp_error(exc)

    assert isinstance(mapped, MailTransientError)


def test_empty_recipients_refused_bubbles() -> None:
    assert _map_smtp_error(smtplib.SMTPRecipientsRefused({})) is None


def test_4xx_response_exception_is_transient() -> None:
    mapped = _map_smtp_error(smtplib.SMTPResponseException(452, b"insufficient storage"))

    assert isinstance(mapped, MailTransientError)
    assert mapped.smtp_code == 452


def test_5xx_response_exception_other_than_recipients_refused_bubbles() -> None:
    """535 sai tài khoản là lỗi cấu hình, không phải lỗi thư — để nổi lên (R-16)."""
    assert _map_smtp_error(smtplib.SMTPResponseException(535, b"bad credentials")) is None


def test_server_disconnected_is_transient() -> None:
    assert isinstance(_map_smtp_error(smtplib.SMTPServerDisconnected("gone")), MailTransientError)


def test_generic_smtp_exception_bubbles() -> None:
    assert _map_smtp_error(smtplib.SMTPException("lỗi lạ")) is None


@pytest.mark.parametrize("exc", [ConnectionRefusedError("refused"), TimeoutError("timeout"), OSError("os")])
def test_connection_level_errors_are_transient(exc: Exception) -> None:
    assert isinstance(_map_smtp_error(exc), MailTransientError)


def test_unrelated_exception_bubbles() -> None:
    assert _map_smtp_error(ValueError("không liên quan")) is None


# --- MemoryMailer / create_mailer -----------------------------------------------------------


def test_memory_mailer_collects_and_resets(memory_mailer: MemoryMailer) -> None:
    memory_mailer.send(MESSAGE)

    assert memory_mailer.sent == [MESSAGE]

    memory_mailer.reset()
    assert memory_mailer.sent == []


def test_create_mailer_memory_returns_the_same_instance(memory_mailer: MemoryMailer) -> None:
    first = create_mailer(get_mail_settings())
    second = create_mailer(get_mail_settings())

    assert first is second is memory_mailer


def test_create_mailer_smtp_returns_a_new_smtp_mailer() -> None:
    settings = _settings()

    mailer = create_mailer(settings)

    assert isinstance(mailer, SmtpMailer)
