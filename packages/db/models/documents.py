"""Ba bảng tài liệu chưa gán tầng (Strategy B H1, PHASE-1-CONTRACT §2): `documents`, `document_pages`, `drawing_regions`.

Một tài liệu (PDF/ảnh nhiều bản vẽ) tải lên trước, tách trang, đề xuất vùng; người dùng xác nhận
vùng nào thuộc tầng nào. CHECK là tầng phòng thủ cuối, nơi báo lỗi cho người dùng là
`apps/api/documents`. Tọa độ vùng là tỉ lệ `[0, 1]` trên trang **chưa** nắn.
"""

from typing import Final, Literal, get_args

from sqlalchemy import BigInteger, CheckConstraint, Float, ForeignKey, Identity, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base, TimestampMixin
from packages.db.models.auth import one_of
from packages.db.models.floors import FLOORS
from packages.db.models.projects import PROJECTS

DOCUMENTS: Final = "documents"
DOCUMENT_PAGES: Final = "document_pages"
DRAWING_REGIONS: Final = "drawing_regions"

DocumentStatus = Literal["uploading", "analyzing", "ready", "failed"]
DrawingType = Literal["floorPlan", "section", "elevation", "detail", "other", "unknown"]
Origin = Literal["ai", "user"]
RegionStatus = Literal["proposed", "confirmed"]

DOCUMENT_STATUSES: Final[tuple[str, ...]] = get_args(DocumentStatus)
DRAWING_TYPES: Final[tuple[str, ...]] = get_args(DrawingType)
ORIGINS: Final[tuple[str, ...]] = get_args(Origin)
REGION_STATUSES: Final[tuple[str, ...]] = get_args(RegionStatus)
MAX_PAGES: Final = 20


class DocumentRow(Base, TimestampMixin):
    """Một tài liệu tải lên cho dự án, chưa gán tầng; `created_by` là `sub` người tải (K05), không FK."""

    __tablename__ = DOCUMENTS

    pk: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    id: Mapped[str] = mapped_column(Text, unique=True)
    project_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{PROJECTS}.id", ondelete="CASCADE"), index=True)
    file_name: Mapped[str] = mapped_column(Text)
    sniffed_kind: Mapped[str | None] = mapped_column(Text, default=None)
    original_key: Mapped[str | None] = mapped_column(Text, default=None)
    page_count: Mapped[int | None] = mapped_column(Integer, default=None)
    status: Mapped[str] = mapped_column(Text, server_default=text("'uploading'"), default="uploading")
    error_code: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("status", DOCUMENT_STATUSES), name="status"),
        CheckConstraint(f"page_count IS NULL OR page_count BETWEEN 1 AND {MAX_PAGES}", name="page_count"),
        CheckConstraint("(status = 'failed') = (error_code IS NOT NULL)", name="error"),
    )


class DocumentPageRow(Base):
    """Một trang của tài liệu; `(document_pk, page_index)` duy nhất."""

    __tablename__ = DOCUMENT_PAGES

    pk: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{DOCUMENTS}.pk", ondelete="CASCADE"))
    page_index: Mapped[int] = mapped_column(Integer)
    preview_key: Mapped[str | None] = mapped_column(Text, default=None)
    width_px: Mapped[int | None] = mapped_column(Integer, default=None)
    height_px: Mapped[int | None] = mapped_column(Integer, default=None)

    __table_args__ = (
        CheckConstraint("page_index >= 0", name="index"),
        UniqueConstraint("document_pk", "page_index", name="uq_document_pages_document_page"),
    )


class DrawingRegionRow(Base, TimestampMixin):
    """Một vùng bản vẽ trên trang (hộp chữ nhật tỉ lệ), đề xuất bởi AI hay người dùng vẽ."""

    __tablename__ = DRAWING_REGIONS

    pk: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    id: Mapped[str] = mapped_column(Text, unique=True)
    page_pk: Mapped[int] = mapped_column(BigInteger, ForeignKey(f"{DOCUMENT_PAGES}.pk", ondelete="CASCADE"), index=True)
    x0: Mapped[float] = mapped_column(Float)
    y0: Mapped[float] = mapped_column(Float)
    x1: Mapped[float] = mapped_column(Float)
    y1: Mapped[float] = mapped_column(Float)
    drawing_type: Mapped[str] = mapped_column(Text)
    type_source: Mapped[str] = mapped_column(Text)
    type_signals: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), default=list)
    source: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'proposed'"), default="proposed")
    floor_pk: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(f"{FLOORS}.pk", ondelete="SET NULL"), default=None
    )
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), default=1)

    __table_args__ = (
        CheckConstraint("0 <= x0 AND x0 < x1 AND x1 <= 1 AND 0 <= y0 AND y0 < y1 AND y1 <= 1", name="box"),
        CheckConstraint(one_of("drawing_type", DRAWING_TYPES), name="type"),
        CheckConstraint(one_of("type_source", ORIGINS), name="type_source"),
        CheckConstraint(one_of("source", ORIGINS), name="source"),
        CheckConstraint(one_of("status", REGION_STATUSES), name="status"),
    )
