"""Bảng `design_concepts`: các lượt "AI chọn phong cách + đồ nội thất" của một dự án (AID-01, N47-N48).

Một dòng là một "phong cách sinh riêng cho căn"; không ghi gì vào tài liệu bản vẽ. `input_key` là
sha256 của đầu vào (kiểu hoặc "auto", revision mọi tầng, phiên bản thư viện, vật liệu, prompt):
chỉ mục duy nhất một phần `uq_design_concepts_active` cho mỗi (dự án, khoá) tối đa một lượt
`queued|running`, nên hai lượt cùng đầu vào không gọi AI hai lần.
"""

from datetime import datetime
from typing import Any, Final

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.projects import PROJECTS

DESIGN_CONCEPTS: Final = "design_concepts"
DESIGN_STYLE_IDS: Final = (
    "japandi",
    "scandinavian",
    "modern-min",
    "modern-lux",
    "indochine",
    "wabi-sabi",
    "industrial",
    "tropical",
    "korean-min",
    "neoclassic",
    "midcentury",
    "rustic",
)
DESIGN_CONCEPT_STATUSES: Final = ("queued", "running", "done", "failed")

_STYLE_CHECK: Final = "style_id IS NULL OR style_id IN (" + ", ".join(f"'{s}'" for s in DESIGN_STYLE_IDS) + ")"


class DesignConceptRow(Base, TimestampMixin):
    """Một lượt; `created_by` `None` = lượt tự chạy sau pipeline. Xoá cứng dự án thì dòng đi theo."""

    __tablename__ = DESIGN_CONCEPTS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"))
    style_id: Mapped[str | None] = mapped_column(Text, default=None)
    suggested: Mapped[bool] = mapped_column(Boolean)
    input_key: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text, default=None)
    result: Mapped[Any] = mapped_column(JSONB, default=None, nullable=True)
    usage: Mapped[Any] = mapped_column(JSONB, default=None, nullable=True)
    created_by: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status_values"),
        CheckConstraint(_STYLE_CHECK, name="style_values"),
        Index(f"ix_{DESIGN_CONCEPTS}_project_id_id", "project_id", "id"),
        Index(
            f"uq_{DESIGN_CONCEPTS}_active",
            "project_id",
            "input_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
