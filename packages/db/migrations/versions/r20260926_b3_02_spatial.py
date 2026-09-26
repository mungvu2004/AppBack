"""spatial

Revision ID: r20260926_b3_02
Revises: r20260925_b2_04
Create Date: 2026-09-26

Ba bảng của lớp không gian (B3-02 [5], BE-00 §6.1): expand thuần, không đụng bảng nào đang
có. Hằng số chép tay từ `packages/db/models/spatial.py`, không nhập module model (BE-00
§6.1: migration phải tự đứng vững kể cả khi model sau này đổi).

Mọi FK tới `projects.id`, `floors.pk` là `ON DELETE CASCADE` (như `r20260923_b2_03_floors.py`):
xoá cứng một dự án hay một tầng là **một** lệnh `DELETE`.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r20260926_b3_02"
down_revision: str | None = "r20260925_b2_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FLOOR_DOCUMENTS: Final = "floor_documents"
FLOOR_CHANGE_LOG: Final = "floor_change_log"
FLOOR_ENTITY_IDS: Final = "floor_entity_ids"
PROJECTS: Final = "projects"
FLOORS: Final = "floors"

_SCALE_SOURCE: Final = "scale_source IN ('human', 'pipeline', 'project_default', 'none')"
_ENTITY_TYPE: Final = "entity_type IN ('vertex', 'wall', 'door', 'window', 'furniture', 'room', 'dimension')"
_CHANGED_BY: Final = "changed_by ~ '^(usr_[0-9A-HJKMNP-TV-Z]{26}|system:pipeline)$'"


def _timestamps() -> tuple[sa.Column[datetime], ...]:
    """Hai cột của `TimestampMixin` — ba bảng dùng chung, khai một lần."""
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def _create_floor_documents() -> None:
    """`floor_documents`: một dòng mỗi tầng (`floor_pk` vừa là PK vừa là FK)."""
    op.create_table(
        FLOOR_DOCUMENTS,
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), nullable=False),
        sa.Column("document", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scale_mm_per_px", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("scale_source", sa.Text(), nullable=False),
        sa.Column("scale_page_key", sa.Text(), nullable=True),
        sa.Column("last_writer_id", sa.Text(), nullable=True),
        sa.Column("last_body_sha256", sa.CHAR(length=64), nullable=True),
        sa.Column("last_base_revision", sa.BigInteger(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("revision >= 0", name=op.f(f"ck_{FLOOR_DOCUMENTS}_revision_non_negative")),
        sa.CheckConstraint("schema_version >= 1", name=op.f(f"ck_{FLOOR_DOCUMENTS}_schema_version_positive")),
        sa.CheckConstraint(
            "scale_mm_per_px IS NULL OR scale_mm_per_px > 0",
            name=op.f(f"ck_{FLOOR_DOCUMENTS}_scale_mm_per_px_positive"),
        ),
        sa.CheckConstraint(_SCALE_SOURCE, name=op.f(f"ck_{FLOOR_DOCUMENTS}_scale_source")),
        sa.CheckConstraint(
            "(scale_source = 'none') = (scale_mm_per_px IS NULL)",
            name=op.f(f"ck_{FLOOR_DOCUMENTS}_scale_source_matches_scale"),
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"],
            [f"{FLOORS}.pk"],
            name=op.f(f"fk_{FLOOR_DOCUMENTS}_floor_pk_{FLOORS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("floor_pk", name=f"pk_{FLOOR_DOCUMENTS}"),
    )


def _create_floor_change_log() -> None:
    """`floor_change_log` + hai index của F-08 (theo bản ghi, và lịch sử một trường)."""
    op.create_table(
        FLOOR_CHANGE_LOG,
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("removed", sa.Boolean(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.Text(), nullable=False),
        sa.Column("changed_by_name", sa.Text(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("revision >= 0", name=op.f(f"ck_{FLOOR_CHANGE_LOG}_revision_non_negative")),
        sa.CheckConstraint(_ENTITY_TYPE, name=op.f(f"ck_{FLOOR_CHANGE_LOG}_entity_type")),
        sa.CheckConstraint("removed = (value IS NULL)", name=op.f(f"ck_{FLOOR_CHANGE_LOG}_removed_matches_value")),
        sa.CheckConstraint(
            "value IS NULL OR jsonb_typeof(value) <> 'null'",
            name=op.f(f"ck_{FLOOR_CHANGE_LOG}_value_not_json_null"),
        ),
        sa.CheckConstraint(_CHANGED_BY, name=op.f(f"ck_{FLOOR_CHANGE_LOG}_changed_by_format")),
        sa.CheckConstraint("changed_by_name <> ''", name=op.f(f"ck_{FLOOR_CHANGE_LOG}_changed_by_name_not_empty")),
        sa.ForeignKeyConstraint(
            ["floor_pk"],
            [f"{FLOORS}.pk"],
            name=op.f(f"fk_{FLOOR_CHANGE_LOG}_floor_pk_{FLOORS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{FLOOR_CHANGE_LOG}"),
    )
    op.create_index(f"ix_{FLOOR_CHANGE_LOG}_floor_pk_revision", FLOOR_CHANGE_LOG, ["floor_pk", "revision"])
    op.create_index(
        f"ix_{FLOOR_CHANGE_LOG}_floor_pk_entity_id_field_revision",
        FLOOR_CHANGE_LOG,
        ["floor_pk", "entity_id", "field", "revision"],
    )


def _create_floor_entity_ids() -> None:
    """`floor_entity_ids`: PK ghép `(project_id, entity_id)` là luật "id duy nhất toàn dự án" (W4)."""
    op.create_table(
        FLOOR_ENTITY_IDS,
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("floor_pk", sa.BigInteger(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["project_id"],
            [f"{PROJECTS}.id"],
            name=op.f(f"fk_{FLOOR_ENTITY_IDS}_project_id_{PROJECTS}"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["floor_pk"],
            [f"{FLOORS}.pk"],
            name=op.f(f"fk_{FLOOR_ENTITY_IDS}_floor_pk_{FLOORS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "entity_id", name=f"pk_{FLOOR_ENTITY_IDS}"),
    )
    op.create_index(f"ix_{FLOOR_ENTITY_IDS}_floor_pk", FLOOR_ENTITY_IDS, ["floor_pk"])


def upgrade() -> None:
    """Expand: ba bảng mới, không bảng nào phụ thuộc bảng kia nên thứ tự chỉ để đọc cho quen."""
    _create_floor_documents()
    _create_floor_change_log()
    _create_floor_entity_ids()


def downgrade() -> None:
    """Bỏ ba bảng theo thứ tự ngược; index đi theo `DROP TABLE`."""
    op.drop_table(FLOOR_ENTITY_IDS)
    op.drop_table(FLOOR_CHANGE_LOG)
    op.drop_table(FLOOR_DOCUMENTS)
