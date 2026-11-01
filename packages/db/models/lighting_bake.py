"""Bảng `lighting_bakes`: các lượt bake ánh sáng GLB của một dự án (LB-01, N42-N44).

Mỗi dự án có tối đa một lượt đang chạy (`queued|running`) — chỉ mục duy nhất một phần
`uq_lighting_bakes_active` chặn lượt thứ hai ở DB, API trả 409 `LIGHTING_BAKE_IN_PROGRESS`.
Tệp vào/ra nằm trong kho object dưới `lighting_bake_prefix(project_id, bake_id)`.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.projects import PROJECTS

LIGHTING_BAKES: Final = "lighting_bakes"
LIGHTING_BAKE_STATUSES: Final = ("queued", "running", "done", "failed")
ACTIVE_STATUSES: Final = ("queued", "running")


class LightingBakeRow(Base, TimestampMixin):
    """Một lượt bake; xoá cứng dự án thì dòng đi theo (CASCADE)."""

    __tablename__ = LIGHTING_BAKES

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"))
    created_by: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    failure_code: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'failed')", name="status_values"),
        Index(f"ix_{LIGHTING_BAKES}_project_id_id", "project_id", "id"),
        Index(
            f"uq_{LIGHTING_BAKES}_active",
            "project_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
    )
