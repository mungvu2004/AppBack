"""Bảng `library_items`: danh mục mẫu nội thất .glb dùng chung (B2-06 [5]).

`id` là slug ổn định (khoá đối tượng trong storage suy ra từ nó). Seed chỉ ghi danh tính;
kích thước, tệp và mốc thời gian do lịch `publish_library_assets` điền sau khi object có thật,
nên mọi cột đó NULL được và CHECK `published` chặn "đã công bố" mà thiếu số đo hay khoá object.

`owner_id` FK `users.id` với `ON DELETE RESTRICT`: v1 luôn NULL (mục của hệ thống); nếu v2 có
mục của người dùng thì xoá cứng người đó không được lặng lẽ biến mục riêng thành mục chung
(`SET NULL` làm đúng điều đó) hay xoá mất mục (`CASCADE`). Người dùng vốn chỉ bị xoá mềm.
"""

from datetime import datetime
from typing import Final

from sqlalchemy import CHAR, BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import USERS, one_of

LIBRARY_ITEMS: Final = "library_items"
ID_MAX: Final = 64
ID_PATTERN: Final = "^[a-z0-9]+(-[a-z0-9]+)*$"
NAME_MAX: Final = 120
GROUPS: Final = ("table", "chair", "bed", "sofa", "storage", "sanitary", "kitchen", "technical")
SHA256_LEN: Final = 64


class LibraryItemRow(Base, TimestampMixin):
    """Một mẫu trong thư viện; công bố = `published_at` có giá trị, gỡ = `retired_at` có giá trị."""

    __tablename__ = LIBRARY_ITEMS

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    item_group: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer)
    owner_id: Mapped[str | None] = mapped_column(Text, ForeignKey(f"{USERS}.id", ondelete="RESTRICT"), default=None)
    width_mm: Mapped[int | None] = mapped_column(Integer, default=None)
    depth_mm: Mapped[int | None] = mapped_column(Integer, default=None)
    height_mm: Mapped[int | None] = mapped_column(Integer, default=None)
    triangle_count: Mapped[int | None] = mapped_column(Integer, default=None)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, default=None)
    model_key: Mapped[str | None] = mapped_column(Text, default=None)
    model_sha256: Mapped[str | None] = mapped_column(CHAR(SHA256_LEN), default=None)
    preview_key: Mapped[str | None] = mapped_column(Text, default=None)
    preview_sha256: Mapped[str | None] = mapped_column(CHAR(SHA256_LEN), default=None)
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    verified_at: Mapped[datetime | None] = mapped_column(default=None)
    retired_at: Mapped[datetime | None] = mapped_column(default=None)

    __table_args__ = (
        CheckConstraint(f"id ~ '{ID_PATTERN}'", name="id_format"),
        CheckConstraint(f"char_length(id) <= {ID_MAX}", name="id_length"),
        CheckConstraint(f"char_length(name) BETWEEN 1 AND {NAME_MAX}", name="name_length"),
        CheckConstraint(one_of("item_group", GROUPS), name="item_group"),
        # Đã công bố thì đủ năm số dương và có object mô hình (K22). COALESCE: `NULL > 0` là NULL, CHECK cho qua.
        CheckConstraint(
            "published_at IS NULL OR (COALESCE(width_mm, 0) > 0 AND COALESCE(depth_mm, 0) > 0"
            " AND COALESCE(height_mm, 0) > 0"
            " AND COALESCE(triangle_count, 0) > 0 AND COALESCE(file_size_bytes, 0) > 0"
            " AND model_key IS NOT NULL AND model_sha256 IS NOT NULL)",
            name="published",
        ),
        CheckConstraint("(preview_key IS NULL) = (preview_sha256 IS NULL)", name="preview_pair"),
        # Danh sách công khai: chỉ mục đang công bố, theo thứ tự hiển thị.
        Index(
            f"ix_{LIBRARY_ITEMS}_sort_order_id_live",
            "sort_order",
            "id",
            postgresql_where=text("published_at IS NOT NULL AND retired_at IS NULL"),
        ),
    )
