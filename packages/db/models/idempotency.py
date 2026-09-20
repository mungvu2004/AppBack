"""Bảng `idempotency_records` — bộ nhớ của khoá `Idempotency-Key` (BE-00 §7, B0-06).

Đặt ở Postgres chứ không ở Redis: một lượt POST đã ghi dữ liệu thì bằng chứng "đã
làm rồi" phải bền vững đúng như dữ liệu đó, và phải **nằm trong cùng giao dịch**
với nghiệp vụ (`UPDATE … WHERE claim_token = :mine`). Redis `allkeys-lru` có thể
đuổi khoá và làm lượt lặp chạy lại cả tác dụng ngoài.

Vòng đời một dòng: `in_progress` (có `claim_token`, hạn thuê 30 s) → `completed`
(giữ status, `content_type`, thân ≤ 1 MiB) → lịch `purge_expired` xoá sau 24 giờ.
Hạn thuê hết mà lượt cũ chưa xong thì lượt mới **chiếm** dòng bằng token của nó;
lượt cũ hoàn tất 0 dòng và tự rollback.
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    CheckConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin

TABLE: Final = "idempotency_records"
KEY_PATTERN: Final = "^[A-Za-z0-9_-]{8,128}$"
"""Mẫu của header `Idempotency-Key`; DB giữ lại luật để dữ liệu rác không vào được bảng."""

STATE_IN_PROGRESS: Final = "in_progress"
STATE_COMPLETED: Final = "completed"

MAX_RESPONSE_BODY_BYTES: Final = 1024 * 1024
"""Thân lớn hơn không được lưu; lượt lặp của nó trả 500 `INTERNAL` (BE-00 §7)."""


class IdempotencyRecord(Base, TimestampMixin):
    """Một khoá idempotency của một người dùng trên một thao tác."""

    __tablename__ = TABLE

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64))
    method: Mapped[str] = mapped_column(String(10))
    route_template: Mapped[str] = mapped_column(String(255))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(CHAR(64))
    state: Mapped[str] = mapped_column(String(16))
    claim_token: Mapped[UUID] = mapped_column(postgresql.UUID(as_uuid=True))
    lease_until: Mapped[datetime]
    status_code: Mapped[int | None] = mapped_column(Integer, default=None)
    content_type: Mapped[str | None] = mapped_column(String(255), default=None)
    response_body: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
    expires_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("user_id", "method", "route_template", "key"),
        CheckConstraint(f"state IN ('{STATE_IN_PROGRESS}', '{STATE_COMPLETED}')", name="state"),
        CheckConstraint(f"key ~ '{KEY_PATTERN}'", name="key_format"),
        Index(f"ix_{TABLE}_expires_at", "expires_at"),
    )
