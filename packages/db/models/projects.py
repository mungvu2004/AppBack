"""Ba bảng nền của dự án: `projects`, `project_memberships`, `project_floor_summaries` (B2-01 [5]).

- `projects` xoá **mềm** (`deleted_at`): lịch dọn `default.projects.purge_deleted` mới xoá
  cứng sau 30 ngày, nên membership và bảng đếm phải sống tới lúc đó — mọi FK tới
  `projects.id` dùng `ON DELETE CASCADE` để lượt xoá cứng ấy là **một** lệnh `DELETE`.
- `project_floor_summaries` là bảng **đếm theo tầng** (HOP-DONG-MOI §2 N1): N1 suy
  `floorCount`, `areaM2`, `status`, `defaultFloorId` bằng một `GROUP BY` trên bảng này,
  không đọc jsonb của tầng. `hidden` giữ số của tầng đã gỡ để khôi phục không mất đếm;
  chỉ `project_rollups` bỏ dòng ẩn.
- Không có luật tên dự án duy nhất (BE-00 §6, B2-01 [6]): hai lượt tạo cùng tên đều 201.

CHECK ở đây là tầng phòng thủ cuối cho các module ghi (B2-03, B3-03, B5-06a/b) — nơi báo
lỗi cho người dùng là `summaries.py`, không phải DB.
"""

from decimal import Decimal
from typing import Final

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, SoftDeleteMixin, TimestampMixin, area_column
from packages.db.models.auth import USERS, one_of

PROJECTS: Final = "projects"
MEMBERSHIPS: Final = "project_memberships"
FLOOR_SUMMARIES: Final = "project_floor_summaries"

PIPELINE_STATES: Final = ("none", "pending", "running", "failed", "completed")
"""Trạng thái lượt pipeline mới nhất của một tầng — nguồn duy nhất cho CHECK, `summaries` và test."""


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """Một dự án; `created_by` là `sub` của người tạo (K05), không phải giá trị client gửi."""

    __tablename__ = PROJECTS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text, default=None)
    address: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(Text)


class ProjectMembership(Base, TimestampMixin):
    """Một người là thành viên một dự án; `added_by` là `usr_…` hoặc `system:cli` (nên không có FK).

    Không xoá mềm: gỡ thành viên là xoá dòng (B2-02, B1-05). Index `(user_id)` phục vụ
    hướng đọc ngược — "dự án của người này" ở #23, N1 và `count_projects_of_users`.
    """

    __tablename__ = MEMBERSHIPS

    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{USERS}.id"), primary_key=True)
    added_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (Index(f"ix_{MEMBERSHIPS}_user_id", "user_id"),)


class ProjectFloorSummary(Base, TimestampMixin):
    """Số đếm của **một tầng** trong một dự án; `floor_level_id` là id thực thể tầng (W4).

    Không FK tới bảng tầng: bảng ấy ra đời ở B2-03 và dòng đếm phải tồn tại được cả khi tầng
    đã bị gỡ (`hidden=true`, giữ số để khôi phục).
    """

    __tablename__ = FLOOR_SUMMARIES

    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"), primary_key=True)
    floor_level_id: Mapped[str] = mapped_column(Text, primary_key=True)
    floor_order: Mapped[int] = mapped_column(Integer)
    walls_total: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    walls_reviewed: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    area_m2: Mapped[Decimal | None] = area_column(default=None)
    has_upload: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    pipeline_state: Mapped[str] = mapped_column(Text, default="none", server_default=text("'none'"))
    hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    __table_args__ = (
        # Một CHECK cho cả ba luật đếm: số âm và "đã duyệt > tổng" đều là dữ liệu vô nghĩa.
        CheckConstraint("walls_reviewed >= 0 AND walls_reviewed <= walls_total", name="walls_reviewed_range"),
        CheckConstraint(one_of("pipeline_state", PIPELINE_STATES), name="pipeline_state"),
    )
