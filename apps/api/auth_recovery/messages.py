"""Thư mời và quên mật khẩu (B1-03 [6]).

`subject` là hằng tĩnh theo `purpose`, không bao giờ chứa dữ liệu người dùng (K11: một
`subject` dựng từ dữ liệu người nhập là chỗ chèn CRLF/HTML không kiểm được). Tên người
nhận và người mời chỉ vào phần **html** qua `html.escape`. Gốc link luôn từ
`get_core_settings().public_base_url` — không bao giờ từ header request (có thể giả mạo).
Tên sản phẩm người dùng thấy là "AppFront" (cùng tên header của app); giờ ghi theo giờ Việt Nam (G1-07, G2-11).
"""

import html
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

from packages.core.settings import get_core_settings
from packages.db.models.auth_recovery import TokenPurpose
from packages.mail.message import MailMessage

PRODUCT_NAME: Final = "AppFront"
VN_TZ: Final = ZoneInfo("Asia/Ho_Chi_Minh")
_DEADLINE_FMT: Final = "%H:%M ngày %d/%m/%Y (giờ Việt Nam)"
ROLE_LABELS: Final = {"admin": "Quản trị viên", "engineer": "Kỹ sư", "viewer": "Người xem"}
"""Nhãn vai tiếng Việt trong thư mời; vai lạ (CHECK không cho có) in nguyên mã."""


@dataclass(frozen=True, slots=True)
class _Content:
    """Nội dung tĩnh của một mục đích thư: tiêu đề, đường dẫn, câu dẫn tới link, câu cuối."""

    subject: str
    path: str
    intro: str
    outro: str


_CONTENT: dict[TokenPurpose, _Content] = {
    "invite": _Content(
        subject=f"Lời mời tham gia {PRODUCT_NAME}",
        path="/login/invitation",
        intro="Bấm vào liên kết dưới đây để đặt họ tên và mật khẩu cho tài khoản của bạn:",
        outro=(
            "Nếu bạn đã nhận thư mời trước đó, liên kết trong thư cũ không còn dùng được; "
            "hãy dùng liên kết trong thư này."
        ),
    ),
    "password_reset": _Content(
        subject=f"Yêu cầu đặt lại mật khẩu {PRODUCT_NAME}",
        path="/login/reset-password",
        intro=(
            f"Có yêu cầu đặt lại mật khẩu cho tài khoản {PRODUCT_NAME} của bạn. "
            "Bấm vào liên kết dưới đây để đặt mật khẩu mới:"
        ),
        outro="Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua thư này; mật khẩu hiện tại vẫn giữ nguyên.",
    ),
}


def format_deadline(expires_at: datetime) -> str:
    """Hạn dùng theo giờ Việt Nam kèm chú thích, ví dụ `21:24 ngày 18/10/2026 (giờ Việt Nam)`."""
    return expires_at.astimezone(VN_TZ).strftime(_DEADLINE_FMT)


def _invite_lead(*, role: str | None, inviter: str | None) -> str:
    """Câu đầu thư mời: ai mời (nếu biết) và vai gì (nếu biết); chưa escape."""
    who = f"{inviter} đã mời bạn" if inviter else "Bạn được mời"
    as_role = f" với vai {ROLE_LABELS.get(role, role)}" if role else ""
    return f"{who} tham gia {PRODUCT_NAME}{as_role}."


def build_token_mail(
    *,
    purpose: TokenPurpose,
    to: str,
    name: str,
    token: str,
    expires_at: datetime,
    role: str | None = None,
    inviter: str | None = None,
) -> MailMessage:
    """Dựng thư token một lần theo `purpose`; token bản rõ chỉ sống trong tham số này (K11).

    `role`/`inviter` chỉ dùng cho thư mời (thư đặt lại mật khẩu bỏ qua); `None` → câu không nêu phần đó.
    """
    content = _CONTENT[purpose]
    link = f"{get_core_settings().public_base_url}{content.path}#token={token}"
    deadline = f"Liên kết có hiệu lực đến {format_deadline(expires_at)}."
    lead = [_invite_lead(role=role, inviter=inviter)] if purpose == "invite" else []
    paragraphs = [f"Xin chào {name},", *lead, content.intro]
    text = "\n\n".join([*paragraphs, link, deadline, content.outro]) + "\n"
    body_html = "".join(
        [
            *(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs),
            f'<p><a href="{link}">{link}</a></p>',
            f"<p>{deadline}</p>",
            f"<p>{content.outro}</p>",
        ]
    )
    return MailMessage(to=to, subject=content.subject, text=text, html=body_html)
