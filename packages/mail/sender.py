"""Gửi thư qua SMTP thật hoặc bộ nhớ (B1-03 [2]).

Ánh xạ lỗi SMTP dồn vào **một** hàm `_map_smtp_error` (R-19, R-07): mã 5xx của
`SMTPRecipientsRefused` là người nhận từ chối hẳn (`MailRejectedError`); mã 4xx ở
bất kỳ bước nào, mất kết nối, hay lỗi socket khi kết nối là tạm thời, thử lại được
(`MailTransientError`); lỗi SMTP khác (vd 535 sai tài khoản — lỗi cấu hình, không
phải lỗi thư) để nổi lên nguyên bản (R-16), người gọi (job) sẽ thấy exception lạ
và dừng thay vì thử lại vô ích. `MailTransientError`/`MailRejectedError` chỉ mang
mã SMTP, không mang địa chỉ hay thân thư (K11).
"""

import smtplib
import ssl
import threading
from email.message import EmailMessage
from typing import Protocol, cast

from packages.mail.message import MailMessage
from packages.mail.settings import MailSettings


class Mailer(Protocol):
    """Giao diện gửi thư đồng bộ dùng chung cho `SmtpMailer` và `MemoryMailer`."""

    def send(self, message: MailMessage) -> None:
        """Gửi một thư; ném `MailTransientError`/`MailRejectedError` khi SMTP từ chối."""
        ...


class MailTransientError(Exception):
    """Lỗi gửi thư thử lại được (mất kết nối, timeout, SMTP 4xx). Mang `smtp_code` để log."""

    def __init__(self, smtp_code: int | None = None) -> None:
        """Giữ `smtp_code` (không có thì `None`, vd mất kết nối) để log, không mang gì khác (K11)."""
        super().__init__(smtp_code)
        self.smtp_code = smtp_code


class MailRejectedError(Exception):
    """Người nhận bị SMTP từ chối hẳn (mã 5xx) — thử lại vô ích. Mang `smtp_code` để log."""

    def __init__(self, smtp_code: int | None = None) -> None:
        """Giữ `smtp_code` để log, không mang địa chỉ hay thân thư (K11)."""
        super().__init__(smtp_code)
        self.smtp_code = smtp_code


def _map_smtp_error(exc: Exception) -> Exception | None:
    """Ánh xạ một exception thô của `smtplib`/socket sang lỗi thư; `None` = để nổi lên nguyên bản."""
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = {code for code, _msg in exc.recipients.values()}
        if codes and all(500 <= code < 600 for code in codes):
            return MailRejectedError(next(iter(codes)) if len(codes) == 1 else None)
        if any(400 <= code < 500 for code in codes):
            return MailTransientError(next(iter(codes)) if len(codes) == 1 else None)
        return None
    if isinstance(exc, smtplib.SMTPResponseException):
        if 400 <= exc.smtp_code < 500:
            return MailTransientError(exc.smtp_code)
        return None
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return MailTransientError(None)
    if isinstance(exc, smtplib.SMTPException):
        return None
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return MailTransientError(None)
    return None


class SmtpMailer:
    """Gửi thư qua SMTP thật (Mailpit ở dev/CI, máy chủ thật ở production)."""

    def __init__(self, settings: MailSettings) -> None:
        """Giữ cấu hình SMTP đã xác thực; không mở kết nối ở đây (mở mỗi lượt `send`)."""
        # `MailSettings` đã bắt buộc smtp_host/mail_from khi backend="smtp" lúc nạp (model_validator);
        # cast thay vì kiểm lại để không viết nhánh không test được (R-14).
        self._settings = settings
        self._host = cast(str, settings.smtp_host)
        self._mail_from = cast(str, settings.mail_from)

    def send(self, message: MailMessage) -> None:
        """Mở kết nối, gửi một thư đa phần (text + html), đóng lại; lỗi ánh xạ qua `_map_smtp_error`."""
        s = self._settings
        try:
            with smtplib.SMTP(self._host, s.smtp_port, timeout=s.smtp_timeout_s) as client:
                if s.smtp_starttls:
                    client.starttls(context=ssl.create_default_context())
                if s.smtp_username and s.smtp_password:
                    client.login(s.smtp_username, s.smtp_password.get_secret_value())
                email_message = EmailMessage()
                email_message["From"] = self._mail_from
                email_message["To"] = message.to
                email_message["Subject"] = message.subject
                email_message.set_content(message.text)
                email_message.add_alternative(message.html, subtype="html")
                client.send_message(email_message)
        except Exception as exc:
            mapped = _map_smtp_error(exc)
            if mapped is None:
                raise
            raise mapped from exc


class MemoryMailer:
    """Mailer giả cho `APP_ENV=test`: gom thư vào `sent` (đọc được), khoá luồng (K23, K36 test)."""

    def __init__(self) -> None:
        """Dựng hộp `sent` rỗng, khoá riêng cho nó."""
        self._lock = threading.Lock()
        self.sent: list[MailMessage] = []

    def send(self, message: MailMessage) -> None:
        """Gom `message` vào `sent`; không gửi thật, không bao giờ ném lỗi."""
        with self._lock:
            self.sent.append(message)

    def reset(self) -> None:
        """Xoá `sent`; gọi ở đầu mỗi test để test trước không rò sang test sau."""
        with self._lock:
            self.sent.clear()


_memory_mailer = MemoryMailer()
"""Bản `MemoryMailer` duy nhất của tiến trình — `create_mailer` luôn trả cùng bản này."""


def create_mailer(settings: MailSettings) -> Mailer:
    """Dựng mailer theo `settings.mail_backend`: `smtp` → kết nối mới; `memory` → bản dùng chung."""
    if settings.mail_backend == "memory":
        return _memory_mailer
    return SmtpMailer(settings)
