"""packages.mail — gửi thư (mời, đặt lại mật khẩu)."""

from packages.mail.message import MailMessage
from packages.mail.sender import (
    Mailer,
    MailRejectedError,
    MailTransientError,
    MemoryMailer,
    SmtpMailer,
    create_mailer,
)
from packages.mail.settings import MailSettings, get_mail_settings, reset_mail_settings_cache

__all__ = [
    "MailMessage",
    "MailRejectedError",
    "MailSettings",
    "MailTransientError",
    "Mailer",
    "MemoryMailer",
    "SmtpMailer",
    "create_mailer",
    "get_mail_settings",
    "reset_mail_settings_cache",
]
