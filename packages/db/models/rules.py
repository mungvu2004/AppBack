"""Bảng `rule_configs`: cấu hình luật một dự án, có `revision` cho ghi có version (B3-05 [5], W20).

Không dòng nào tồn tại cho tới lần ghi đầu; `apps/api/rules` trả `revision 0` khi chưa có dòng. `overrides` là
jsonb đúng như đã kiểm ở tầng danh mục. `last_writer_id` (`sub`, không FK vì người có thể bị xoá) và
`last_body_sha256` cho phép nhận ra lượt ghi lặp (C09b). Xoá cứng dự án thì dòng đi theo (CASCADE).
"""

from typing import Any, Final

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import CHAR, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.projects import PROJECTS

RULE_CONFIGS: Final = "rule_configs"


class RuleConfigRow(Base, TimestampMixin):
    """Cấu hình luật của một dự án; khoá chính là `project_id`."""

    __tablename__ = RULE_CONFIGS

    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"), primary_key=True)
    revision: Mapped[int] = mapped_column(BigInteger)
    overrides: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    last_writer_id: Mapped[str | None] = mapped_column(Text, default=None)
    last_body_sha256: Mapped[str | None] = mapped_column(CHAR(64), default=None)

    __table_args__ = (CheckConstraint("revision >= 0", name="revision_min"),)
