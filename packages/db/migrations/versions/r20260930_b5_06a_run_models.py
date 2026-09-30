"""run_models

Revision ID: r20260930_b5_06a
Revises: r20260929_b6_02
Create Date: 2026-09-30

Một bảng `pipeline_run_models` (B5-06a [5], BE-00 §6.1): expand thuần, một FK
`pipeline_run_models.run_id → pipeline_runs.id`. Hằng số (tên bảng) **chép tay** từ
`packages/db/models/pipeline_orchestrate.py`, theo đúng khuôn `r20260929_b6_02_ml_datasets.py`:
migration không nhập module model.

Luật expand/contract: BE-00 §6.1 (`tools/lint_migrations.py` chặn drop/rename/NOT NULL).
"""

from collections.abc import Sequence
from typing import Final

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "r20260930_b5_06a"
down_revision: str | None = "r20260929_b6_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PIPELINE_RUNS: Final = "pipeline_runs"
PIPELINE_RUN_MODELS: Final = "pipeline_run_models"


def upgrade() -> None:
    """Expand: một bảng, một FK CASCADE, hai CHECK, một index một phần."""
    op.create_table(
        PIPELINE_RUN_MODELS,
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("pinned", JSONB(), nullable=False),
        sa.Column("used", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("persisted_revision", sa.BigInteger(), nullable=True),
        sa.Column("step_requeue_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifacts_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "persisted_revision IS NULL OR persisted_revision >= 0",
            name=op.f(f"ck_{PIPELINE_RUN_MODELS}_persisted_revision_min"),
        ),
        sa.CheckConstraint("step_requeue_count >= 0", name=op.f(f"ck_{PIPELINE_RUN_MODELS}_step_requeue_count_min")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            [f"{PIPELINE_RUNS}.id"],
            name=op.f(f"fk_{PIPELINE_RUN_MODELS}_run_id_{PIPELINE_RUNS}"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name=f"pk_{PIPELINE_RUN_MODELS}"),
    )
    op.create_index(
        f"ix_{PIPELINE_RUN_MODELS}_run_id_not_purged",
        PIPELINE_RUN_MODELS,
        ["run_id"],
        postgresql_where=sa.text("artifacts_purged_at IS NULL"),
    )


def downgrade() -> None:
    """Bỏ bảng (kéo theo FK, CHECK, index)."""
    op.drop_table(PIPELINE_RUN_MODELS)
