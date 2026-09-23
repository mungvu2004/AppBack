"""Thư mời và quên mật khẩu (B1-03 [6]).

`subject` là hằng tĩnh theo `purpose`, không bao giờ chứa dữ liệu người dùng (K11: một
`subject` dựng từ dữ liệu người nhập là chỗ chèn CRLF/HTML không kiểm được). Tên người
nhận chỉ vào phần **html** qua `html.escape`. Gốc link luôn từ
`get_core_settings().public_base_url` — không bao giờ từ header request (có thể giả mạo).
"""

import html
from dataclasses import dataclass
from datetime import datetime

from packages.core.settings import get_core_settings
from packages.db.models.auth_recovery import TokenPurpose
from packages.mail.message import MailMessage

_DEADLINE_FMT = "%H:%M %d/%m/%Y UTC"


@dataclass(frozen=True, slots=True)
class _Content:
    """Nội dung tĩnh của một mục đích thư: tiêu đề, đường dẫn, câu mở đầu."""

    subject: str
    path: str
    intro: str


_CONTENT: dict[TokenPurpose, _Content] = {
    "invite": _Content(
        subject="Lời mời tham gia AppBack",
        path="/login/invitation",
        intro="bạn được mời tham gia AppBack. Bấm vào liên kết dưới đây để thiết lập tài khoản:",
    ),
    "password_reset": _Content(
        subject="Yêu cầu đặt lại mật khẩu AppBack",
        path="/login/reset-password",
        intro="có yêu cầu đặt lại mật khẩu cho tài khoản AppBack. Bấm vào liên kết dưới đây để đặt mật khẩu mới:",
    ),
}


def build_token_mail(*, purpose: TokenPurpose, to: str, name: str, token: str, expires_at: datetime) -> MailMessage:
    """Dựng thư token một lần theo `purpose`; token bản rõ chỉ sống trong tham số này (K11)."""
    content = _CONTENT[purpose]
    link = f"{get_core_settings().public_base_url}{content.path}#token={token}"
    deadline = expires_at.strftime(_DEADLINE_FMT)
    text = f"Xin chào {name},\n\n{content.intro}\n\n{link}\n\nLiên kết có hiệu lực đến {deadline}.\n"
    safe_name = html.escape(name)
    body_html = (
        f"<p>Xin chào {safe_name},</p>"
        f"<p>{content.intro}</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>Liên kết có hiệu lực đến {deadline}.</p>"
    )
    return MailMessage(to=to, subject=content.subject, text=text, html=body_html)
