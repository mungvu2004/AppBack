"""Bảng `property_templates`: khuôn thuộc tính đặt sẵn của một dự án (B2-07 [5]).

Khuôn thuộc về dự án (`scope: "project"` là hằng của dây, không có cột). `fields` lưu đúng
khoá camelCase như trên dây, chỉ những khoá người dùng đã đặt (vắng vẫn vắng).
"""

from typing import Any, Final

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.db.models.projects import PROJECTS

PROPERTY_TEMPLATES: Final = "property_templates"
NAME_MAX: Final = 120
OBJECT_KINDS: Final = ("wall", "opening", "room", "furniture")


class PropertyTemplateRow(Base, TimestampMixin):
    """Một khuôn; `created_by` là `sub` người tạo (K05), không FK."""

    __tablename__ = PROPERTY_TEMPLATES

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    object_kind: Mapped[str] = mapped_column(Text)
    fields: Mapped[Any] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint(one_of("object_kind", OBJECT_KINDS), name="object_kind"),
        # #28 đọc theo dự án, `created_at ASC, id ASC`.
        Index(f"ix_{PROPERTY_TEMPLATES}_project_id_created_at_id", "project_id", "created_at", "id"),
    )
