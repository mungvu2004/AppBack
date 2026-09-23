"""Bảng `one_time_tokens` — token dùng một lần cho mời và quên mật khẩu (B1-03, BE-00 §5).

Chỉ lưu `token_hash` (SHA-256) và `nonce`: không bao giờ có bản rõ trong DB (K11).
Partial unique `ACTIVE_UNIQUE` giữ đúng một token còn hiệu lực mỗi `(user_id, purpose)`;
`issue_token` (`apps/api/auth_recovery/tokens.py`) dựa vào tên hằng này để so với
`unique_violation()` khi hai giao dịch song song cùng vô hiệu token cũ.
"""

from datetime import datetime
from typing import Final, Literal, get_args

from sqlalchemy import CHAR, CheckConstraint, ForeignKey, Index, LargeBinary, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import USERS, one_of

TABLE: Final = "one_time_tokens"

TOKEN_PURPOSES: Final = ("invite", "password_reset")
TokenPurpose = Literal["invite", "password_reset"]
assert set(get_args(TokenPurpose)) == set(TOKEN_PURPOSES)  # noqa: S101 — hai khai báo phải khớp nhau

TOKEN_HASH_LEN: Final = 64
NONCE_LEN: Final = 16

ACTIVE_UNIQUE: Final = f"uq_{TABLE}_user_id_purpose"


class OneTimeToken(Base, TimestampMixin):
    """Một token một lần; `used_at`/`superseded_at` rỗng và `expires_at > now` là còn hiệu lực."""

    __tablename__ = TABLE

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{USERS}.id"))
    purpose: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(CHAR(TOKEN_HASH_LEN), unique=True)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None] = mapped_column(default=None)
    superseded_at: Mapped[datetime | None] = mapped_column(default=None)
    sent_at: Mapped[datetime | None] = mapped_column(default=None)

    __table_args__ = (
        CheckConstraint(one_of("purpose", TOKEN_PURPOSES), name="purpose"),
        CheckConstraint(f"octet_length(nonce) = {NONCE_LEN}", name="nonce_length"),
        Index(
            ACTIVE_UNIQUE,
            "user_id",
            "purpose",
            unique=True,
            postgresql_where=text("used_at IS NULL AND superseded_at IS NULL"),
        ),
        Index(f"ix_{TABLE}_sent_at_created_at", "sent_at", "created_at", postgresql_where=text("sent_at IS NULL")),
    )
