"""Bảng `users` và `refresh_sessions` của đăng nhập và phiên (B1-01, BE-00 §5, §6).

- `users`: email lưu bản `nfc(strip)` và bản `email_normalized` duy nhất **trong số dòng
  chưa xoá mềm** (B1-05 xoá mềm, người cũ không chặn email của người mới). Người `pending`
  chưa có mật khẩu (`password_hash` rỗng) cho tới khi nhận lời mời (B1-03). Cột hồ sơ
  (`job_title`, `phone`, `language`, `avatar_key`) tạo sẵn cho B1-04; B1-01 không ghi.
- `refresh_sessions`: một dòng một phiên, `id` là `sid` trong cookie và trong access token.
  Không lưu token bản rõ: chỉ SHA-256 của token hiện hành và token ngay trước (ân hạn
  30 s); token kế tiếp tính lại bằng HMAC khoá `refresh` (BE-00 §5, §6, K35).

Luật giá trị (vai, trạng thái, lý do thu hồi) giữ bằng `CHECK` ở DB, để một lệnh ghi sai
từ module khác hỏng ngay chứ không lọt thành dữ liệu rác.
"""

from datetime import datetime
from ipaddress import IPv4Address, IPv6Address
from typing import Final, Literal, get_args
from uuid import UUID

from sqlalchemy import CHAR, Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, SoftDeleteMixin, TimestampMixin, unique_active

USERS: Final = "users"
SESSIONS: Final = "refresh_sessions"

ROLES: Final = ("admin", "engineer", "viewer")
STATUSES: Final = ("active", "pending", "disabled")
LANGUAGES: Final = ("vi", "en")
RevokeReason = Literal[
    "logout", "reuse", "replaced", "password_change", "password_reset", "disabled", "deleted", "expired"
]
"""Lý do thu hồi phiên — nguồn duy nhất cho cả kiểu của hàm thu hồi lẫn `CHECK` của cột."""
REVOKE_REASONS: Final[tuple[str, ...]] = get_args(RevokeReason)
NAME_MAX: Final = 120
TOKEN_HASH_LEN: Final = 64


def one_of(column: str, values: tuple[str, ...]) -> str:
    """Biểu thức `CHECK` "cột thuộc tập giá trị" — model và migration dựng cùng một chuỗi."""
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


class User(Base, TimestampMixin, SoftDeleteMixin):
    """Một người dùng; vai và trạng thái là nguồn duy nhất của quyền (K34: không lấy từ token)."""

    __tablename__ = USERS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    email_normalized: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str | None] = mapped_column(Text, default=None)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    last_active_at: Mapped[datetime | None] = mapped_column(default=None)
    job_title: Mapped[str | None] = mapped_column(Text, default=None)
    phone: Mapped[str | None] = mapped_column(Text, default=None)
    language: Mapped[str] = mapped_column(Text, default="vi", server_default=text("'vi'"))
    avatar_key: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (
        unique_active("uq_users_email", "email_normalized"),
        CheckConstraint(one_of("role", ROLES), name="role"),
        CheckConstraint(one_of("status", STATUSES), name="status"),
        CheckConstraint(one_of("language", LANGUAGES), name="language"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint("token_version >= 0", name="token_version"),
    )


class RefreshSession(Base, TimestampMixin):
    """Một phiên refresh; thu hồi là đặt `revoked_at`, không xoá (lịch dọn xoá sau 1 ngày)."""

    __tablename__ = SESSIONS

    id: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{USERS}.id"))
    current_token_hash: Mapped[str] = mapped_column(CHAR(TOKEN_HASH_LEN))
    previous_token_hash: Mapped[str | None] = mapped_column(CHAR(TOKEN_HASH_LEN), default=None)
    rotated_at: Mapped[datetime | None] = mapped_column(default=None)
    remember: Mapped[bool] = mapped_column(Boolean)
    idle_expires_at: Mapped[datetime]
    absolute_expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    revoked_reason: Mapped[str | None] = mapped_column(Text, default=None)
    created_ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(postgresql.INET, default=None)

    __table_args__ = (
        CheckConstraint(one_of("revoked_reason", REVOKE_REASONS), name="revoked_reason"),
        # Thu hồi luôn kèm lý do và ngược lại: module khác (B1-03, B1-05) ghi thiếu một nửa là hỏng ngay.
        CheckConstraint("(revoked_at IS NULL) = (revoked_reason IS NULL)", name="revoked_pair"),
        # Phiên còn sống của một người: thu hồi hàng loạt (đổi mật khẩu, vô hiệu) và xoá cache.
        Index(f"ix_{SESSIONS}_user_id_live", "user_id", postgresql_where=text("revoked_at IS NULL")),
        # Hai điều kiện của lịch dọn (R-21): hết hạn tuyệt đối, và đã thu hồi.
        Index(f"ix_{SESSIONS}_absolute_expires_at", "absolute_expires_at"),
        Index(f"ix_{SESSIONS}_revoked_at", "revoked_at", postgresql_where=text("revoked_at IS NOT NULL")),
    )
