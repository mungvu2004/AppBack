"""documents_pages_regions

Revision ID: r20261027_p1_h1_documents
Revises: r20261026_b4_02_p0_11
Create Date: 2026-10-27

Expand (BE-00 §6.1, Strategy B H1): ba bảng `documents`, `document_pages`, `drawing_regions`; `uploads` nới
`floor_pk` thành NULL được, thêm `document_pk`, `region_id` và CHECK "có tầng hoặc có tài liệu, đúng một".
CHECK mới thêm NOT VALID rồi VALIDATE (không khoá ghi suốt lượt quét); hai index tạo CONCURRENTLY.

Downgrade XOÁ mọi upload tài liệu (`document_pk IS NOT NULL`, mất dữ liệu tải lên chưa gán tầng) vì
`floor_pk` phải trở lại NOT NULL; rồi bỏ index, CHECK, cột, ba bảng. Hằng chép tay từ
`packages/db/models/documents.py`, không nhập module model.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20261027_p1_h1_documents"
down_revision: str | None = "r20261026_b4_02_p0_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DOCUMENTS: Final = "documents"
PAGES: Final = "document_pages"
REGIONS: Final = "drawing_regions"
UPLOADS: Final = "uploads"
UPLOAD_CHECK: Final = f"ck_{UPLOADS}_floor_or_document"
UPLOAD_LINKS: Final = (("document_pk", DOCUMENTS, "CASCADE"), ("region_id", REGIONS, "SET NULL"))


def _timestamps() -> list[sa.Column[datetime]]:
    """Hai cột `created_at`/`updated_at` của `TimestampMixin`."""
    return [
        sa.Column(name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
        for name in ("created_at", "updated_at")
    ]


def upgrade() -> None:
    """Tạo ba bảng tài liệu rồi mở rộng `uploads` (cột, CHECK NOT VALID → VALIDATE, index CONCURRENTLY)."""
    op.create_table(
        DOCUMENTS,
        sa.Column("pk", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("sniffed_kind", sa.Text(), nullable=True),
        sa.Column("original_key", sa.Text(), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'uploading'"), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('uploading', 'analyzing', 'ready', 'failed')", name=op.f(f"ck_{DOCUMENTS}_status")
        ),
        sa.CheckConstraint(
            "page_count IS NULL OR page_count BETWEEN 1 AND 20", name=op.f(f"ck_{DOCUMENTS}_page_count")
        ),
        sa.CheckConstraint("(status = 'failed') = (error_code IS NOT NULL)", name=op.f(f"ck_{DOCUMENTS}_error")),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f(f"fk_{DOCUMENTS}_project_id_projects"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("pk", name=op.f(f"pk_{DOCUMENTS}")),
        sa.UniqueConstraint("id", name=op.f(f"uq_{DOCUMENTS}_id")),
    )
    op.create_index(op.f(f"ix_{DOCUMENTS}_project_id"), DOCUMENTS, ["project_id"])
    op.create_table(
        PAGES,
        sa.Column("pk", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("document_pk", sa.BigInteger(), nullable=False),
        sa.Column("page_index", sa.Integer(), nullable=False),
        sa.Column("preview_key", sa.Text(), nullable=True),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
        sa.CheckConstraint("page_index >= 0", name=op.f(f"ck_{PAGES}_index")),
        sa.ForeignKeyConstraint(
            ["document_pk"], [f"{DOCUMENTS}.pk"], name=op.f(f"fk_{PAGES}_document_pk_{DOCUMENTS}"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("pk", name=op.f(f"pk_{PAGES}")),
        sa.UniqueConstraint("document_pk", "page_index", name=op.f("uq_document_pages_document_page")),
    )
    op.create_table(
        REGIONS,
        sa.Column("pk", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("page_pk", sa.BigInteger(), nullable=False),
        *(sa.Column(name, sa.Float(), nullable=False) for name in ("x0", "y0", "x1", "y1")),
        sa.Column("drawing_type", sa.Text(), nullable=False),
        sa.Column("type_source", sa.Text(), nullable=False),
        sa.Column("type_signals", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'proposed'"), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "0 <= x0 AND x0 < x1 AND x1 <= 1 AND 0 <= y0 AND y0 < y1 AND y1 <= 1", name=op.f(f"ck_{REGIONS}_box")
        ),
        sa.CheckConstraint(
            "drawing_type IN ('floorPlan', 'section', 'elevation', 'detail', 'other', 'unknown')",
            name=op.f(f"ck_{REGIONS}_type"),
        ),
        sa.CheckConstraint("type_source IN ('ai', 'user')", name=op.f(f"ck_{REGIONS}_type_source")),
        sa.CheckConstraint("source IN ('ai', 'user')", name=op.f(f"ck_{REGIONS}_source")),
        sa.CheckConstraint("status IN ('proposed', 'confirmed')", name=op.f(f"ck_{REGIONS}_status")),
        sa.ForeignKeyConstraint(
            ["page_pk"], [f"{PAGES}.pk"], name=op.f(f"fk_{REGIONS}_page_pk_{PAGES}"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"], ["floors.pk"], name=op.f(f"fk_{REGIONS}_floor_pk_floors"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("pk", name=op.f(f"pk_{REGIONS}")),
        sa.UniqueConstraint("id", name=op.f(f"uq_{REGIONS}_id")),
    )
    op.create_index(op.f(f"ix_{REGIONS}_page_pk"), REGIONS, ["page_pk"])

    op.alter_column(UPLOADS, "floor_pk", existing_type=sa.BigInteger(), nullable=True)
    for column, referred, ondelete in UPLOAD_LINKS:
        op.add_column(UPLOADS, sa.Column(column, sa.BigInteger(), nullable=True))
        op.create_foreign_key(
            op.f(f"fk_{UPLOADS}_{column}_{referred}"), UPLOADS, referred, [column], ["pk"], ondelete=ondelete
        )
    op.execute(
        "ALTER TABLE uploads ADD CONSTRAINT ck_uploads_floor_or_document "
        "CHECK ((floor_pk IS NULL) <> (document_pk IS NULL)) NOT VALID"
    )
    op.execute("ALTER TABLE uploads VALIDATE CONSTRAINT ck_uploads_floor_or_document")
    with op.get_context().autocommit_block():
        for column, _, _ in UPLOAD_LINKS:
            op.create_index(op.f(f"ix_{UPLOADS}_{column}"), UPLOADS, [column], postgresql_concurrently=True)


def downgrade() -> None:
    """Xoá upload tài liệu (mất dữ liệu), trả `floor_pk` về NOT NULL, bỏ index/CHECK/cột rồi ba bảng."""
    op.execute("DELETE FROM uploads WHERE document_pk IS NOT NULL")
    op.drop_constraint(op.f(UPLOAD_CHECK), UPLOADS, type_="check")
    for column, referred, _ in UPLOAD_LINKS:
        op.drop_index(op.f(f"ix_{UPLOADS}_{column}"), table_name=UPLOADS)
        op.drop_constraint(op.f(f"fk_{UPLOADS}_{column}_{referred}"), UPLOADS, type_="foreignkey")
        op.drop_column(UPLOADS, column)
    op.alter_column(UPLOADS, "floor_pk", existing_type=sa.BigInteger(), nullable=False)
    op.drop_table(REGIONS)
    op.drop_table(PAGES)
    op.drop_table(DOCUMENTS)
