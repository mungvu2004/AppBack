"""Fixture gửi thư (B1-03 [6]): `memory_mailer`, `mailpit_inbox`, `extract_token`, `smtp_reject_server`.

Chỉ dùng trong test — không nhập từ mã nghiệp vụ (R-28). `mailpit_inbox` dùng
Mailpit **thật** qua fixture `mailpit` (K23); `smtp_reject_server` là máy chủ SMTP
tối thiểu tự viết trên socket cục bộ, **miễn đích danh K23** — Mailpit không trả
mã 550 nếu không đổi cấu hình dịch vụ của B0-01, nên J03 (người nhận bị từ chối
hẳn) không dựng được bằng dịch vụ thật.
"""

from __future__ import annotations

import contextlib
import json
import re
import socket
import threading
import time
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest

from packages.core.settings import reset_settings_cache
from packages.mail.message import MailMessage
from packages.mail.sender import MemoryMailer, create_mailer
from packages.mail.settings import get_mail_settings, reset_mail_settings_cache
from packages.testing.fixtures.storage import PUBLIC_BASE_URL, STORAGE_SECRET

HTTP_TIMEOUT_S = 5.0
POLL_INTERVAL_S = 0.1
_TOKEN_RE = re.compile(r"#token=([^\s\"'<>]{1,512})")


@pytest.fixture
def memory_mailer(monkeypatch: pytest.MonkeyPatch) -> Iterator[MemoryMailer]:
    """`MemoryMailer` sạch, `MAIL_BACKEND=memory`.

    `MailSettings` chỉ chấp nhận `memory` khi `APP_ENV=test` (fail-closed) và validator
    đọc `CoreSettings` lúc đó — nên cũng cần `APP_ENV`, `PUBLIC_BASE_URL`, `SECRET_KEY`
    hợp lệ dù test không đụng gì tới chúng (dùng lại hằng của `storage.py` cho nhất quán).
    """
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    monkeypatch.setenv("SECRET_KEY", STORAGE_SECRET)
    monkeypatch.setenv("MAIL_BACKEND", "memory")
    reset_settings_cache()
    reset_mail_settings_cache()
    mailer = create_mailer(get_mail_settings())
    assert isinstance(mailer, MemoryMailer)  # noqa: S101 — fixture tự kiểm bất biến của mình
    mailer.reset()
    yield mailer
    reset_mail_settings_cache()
    reset_settings_cache()


def _http_get(url: str) -> Any:
    """`GET url` rồi giải JSON — gọi API Mailpit cục bộ."""
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 — URL cục bộ của fixture
        return json.load(resp)


def _http_delete(url: str) -> None:
    """`DELETE url`, không đọc thân trả về — dọn hộp thư Mailpit."""
    request = urllib.request.Request(url, method="DELETE")  # noqa: S310 — URL cục bộ của fixture
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as resp:  # noqa: S310 — URL cục bộ của fixture
        resp.read()


@dataclass(slots=True)
class MailpitInbox:
    """Hộp thư Mailpit của một test: `messages()` đọc lại, `wait_for()` đợi thư tới `to`."""

    http_base: str

    def clear(self) -> None:
        """`DELETE /api/v1/messages` — dọn hộp thư trước test."""
        _http_delete(f"{self.http_base}/api/v1/messages")

    def messages(self) -> list[dict[str, Any]]:
        """Mỗi thư trong hộp, tóm tắt cộng thân text/html (`/api/v1/messages` rồi `/api/v1/message/{ID}`)."""
        summary = _http_get(f"{self.http_base}/api/v1/messages")
        result = []
        for item in summary["messages"]:
            result.append(_http_get(f"{self.http_base}/api/v1/message/{item['ID']}"))
        return result

    def wait_for(self, to: str, timeout_s: float) -> dict[str, Any]:
        """Đợi có thư tới địa chỉ `to`, hỏi lặp có trần; hết hạn → `AssertionError` nêu rõ."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for message in self.messages():
                addresses = {entry.get("Address") for entry in message.get("To", [])}
                if to in addresses:
                    return message
            time.sleep(POLL_INTERVAL_S)
        raise AssertionError(f"không thấy thư tới {to} trong {timeout_s}s")


@pytest.fixture
def mailpit_inbox(mailpit: tuple[str, int, int], monkeypatch: pytest.MonkeyPatch) -> Iterator[MailpitInbox]:
    """`SmtpMailer` trỏ vào Mailpit thật; trả hộp thư đã dọn sạch trước test."""
    host, smtp_port, http_port = mailpit
    monkeypatch.setenv("MAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", host)
    monkeypatch.setenv("SMTP_PORT", str(smtp_port))
    monkeypatch.setenv("SMTP_STARTTLS", "false")
    monkeypatch.setenv("MAIL_FROM", "no-reply@appback.test")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    reset_mail_settings_cache()
    inbox = MailpitInbox(f"http://{host}:{http_port}")
    inbox.clear()
    yield inbox
    inbox.clear()  # Mailpit là dịch vụ dùng chung cả lượt chạy — không để thư rớt sang test khác
    reset_mail_settings_cache()


def extract_token(message: MailMessage | dict[str, Any]) -> str:
    """Lấy token sau `#token=` trong thân text; nhận cả `MailMessage` và thư Mailpit (khoá `Text`)."""
    text = message.text if isinstance(message, MailMessage) else str(message.get("Text", ""))
    match = _TOKEN_RE.search(text)
    if match is None:
        raise AssertionError("không thấy #token= trong thân thư")
    return match.group(1)


class _RejectingSmtpServer(threading.Thread):
    """Máy chủ SMTP tối thiểu: 220 chào, 250 cho EHLO/HELO/MAIL FROM, **550** cho RCPT TO, 221 cho QUIT.

    Chỉ cho test J03 (miễn K23 — xem docstring module). `accept`/`recv` chặn không trần
    thời gian riêng: `close()` đóng socket, mỗi lời gọi chặn đó nhận **`OSError` ngay**
    (không phải phải chờ hết một trần), nên dừng lúc nào cũng qua đúng một đường (R-24
    vẫn giữ qua trần đọc 5 s của từng kết nối con, tránh treo mãi nếu client không nói gì).
    """

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(1)
        self.host, self.port = self._sock.getsockname()

    def run(self) -> None:
        """Vòng `accept` chính của luồng: một kết nối một lượt, dừng sạch khi `close()` gọi tới."""
        while True:
            try:
                conn, _addr = self._sock.accept()
            except OSError:
                return  # close() đóng socket lắng nghe — dừng sạch
            with conn:
                conn.settimeout(5.0)
                self._serve(conn)

    def _serve(self, conn: socket.socket) -> None:
        """Đọc từng dòng lệnh SMTP của một kết nối, trả lời qua `_reply_for` tới khi `QUIT` hay mất kết nối."""
        conn.sendall(b"220 smtp-reject ready\r\n")
        buffer = b""
        while True:
            try:
                chunk = conn.recv(4096)
            except OSError:
                return
            if not chunk:
                return
            buffer += chunk
            while b"\r\n" in buffer:
                line, buffer = buffer.split(b"\r\n", 1)
                conn.sendall(self._reply_for(line))
                if line.upper().startswith(b"QUIT"):
                    return

    @staticmethod
    def _reply_for(line: bytes) -> bytes:
        """250 mọi lệnh trừ `RCPT TO` (550) và `QUIT` (221)."""
        upper = line.upper()
        if upper.startswith(b"RCPT TO"):
            return b"550 mailbox unavailable\r\n"
        if upper.startswith(b"QUIT"):
            return b"221 bye\r\n"
        return b"250 ok\r\n"

    def close(self) -> None:
        """Đánh thức `accept()` đang chặn (`shutdown` — Linux đánh thức được, riêng `close` thì không đảm bảo)."""
        with contextlib.suppress(OSError):  # đã đóng, hoặc chưa từng nhận kết nối nào để shutdown
            self._sock.shutdown(socket.SHUT_RDWR)
        self._sock.close()


@pytest.fixture
def smtp_reject_server() -> Iterator[tuple[str, int]]:
    """`(host, port)` của `_RejectingSmtpServer`; đóng sạch khi test xong."""
    server = _RejectingSmtpServer()
    server.start()
    try:
        yield server.host, server.port
    finally:
        server.close()
        server.join(timeout=2.0)
