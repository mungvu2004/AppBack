"""Bảng `versions`: lịch sử phiên bản theo tầng (B3-04 [5]).

Một dòng là một lần chụp `floor_documents` của một tầng. Dòng **không bao giờ bị xoá**:
khi quá trần lưu giữ, `create_version` chỉ đặt `snapshot = NULL` (siêu dữ liệu còn để
lịch sử liền mạch); dòng chỉ mất theo `ON DELETE CASCADE` khi tầng hoặc dự án bị xoá cứng.

`creator_id` dùng lại `CHANGED_BY_RE` của nhật ký thay đổi — cùng một tập người ghi
(`usr_…` hoặc `system:pipeline`), nên không có bản chép thứ hai của regex.
"""

from typing import Any, Final

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.floors import FLOORS
from packages.db.models.projects import PROJECTS
from packages.db.models.spatial import CHANGED_BY_RE

VERSIONS: Final = "versions"


class VersionRecord(Base, TimestampMixin):
    """Một phiên bản tầng; `snapshot` lồng `{schemaVersion, scaleMmPerPx?, document}` hoặc NULL khi đã gỡ."""

    __tablename__ = VERSIONS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    floor_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer)
    floor_revision: Mapped[int] = mapped_column(BigInteger)
    creator_id: Mapped[str] = mapped_column(Text)
    creator_name: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text, default=None)
    label: Mapped[str | None] = mapped_column(Text, default=None)
    snapshot: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True), default=None)
    restored_from_id: Mapped[str | None] = mapped_column(Text, default=None)
    restore_base_revision: Mapped[int | None] = mapped_column(BigInteger, default=None)

    __table_args__ = (
        CheckConstraint("sequence > 0", name="sequence_positive"),
        CheckConstraint("floor_revision >= 0", name="floor_revision_non_negative"),
        CheckConstraint(f"creator_id ~ '{CHANGED_BY_RE}'", name="creator_id_format"),
        CheckConstraint("char_length(creator_name) > 0", name="creator_name_not_empty"),
        CheckConstraint("note IS NULL OR char_length(note) >= 1", name="note_not_empty"),
        CheckConstraint("label IS NULL OR char_length(label) BETWEEN 1 AND 60", name="label_length"),
        # Cũng phục vụ `ORDER BY sequence DESC` của N17 và `max(sequence)` của `create_version`.
        UniqueConstraint("floor_pk", "sequence"),
    )
