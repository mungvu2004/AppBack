# contract: đổi tên hai CHECK lặp tiền tố của idempotency_records về tên của model (NO-057)
"""check_names

Revision ID: r20260921_b0_06_fix037
Revises: r20260921_b1_01
Create Date: 2026-09-21 17:50:08.540054+00:00

FIX-037 (NO-057): `r20260920_b0_06` truyền `name=f"ck_{TABLE}_…"` mà không bọc `op.f(...)`, nên quy
ước `ck_%(table_name)s_%(constraint_name)s` của `Base.metadata` ghép tiền tố lần hai. Revision đã hợp
nhất thì không sửa tại chỗ; đổi tên là thao tác phá huỷ nên đi revision contract (BE-00 §6.1, có tên
trong `docs/contracts.toml`). `RENAME CONSTRAINT` chỉ sửa catalog, không quét hay kiểm lại dữ liệu.
Chuỗi SQL viết hằng từng câu: lint chặn SQL không phải hằng chuỗi, kể cả trong revision contract.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "r20260921_b0_06_fix037"
down_revision: str | None = "r20260921_b1_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Contract: tên trong DB về đúng tên model sinh (`ck_idempotency_records_state`, `…_key_format`)."""
    op.execute(
        "ALTER TABLE idempotency_records "
        "RENAME CONSTRAINT ck_idempotency_records_ck_idempotency_records_state TO ck_idempotency_records_state"
    )
    op.execute(
        "ALTER TABLE idempotency_records "
        "RENAME CONSTRAINT ck_idempotency_records_ck_idempotency_records_key_format "
        "TO ck_idempotency_records_key_format"
    )


def downgrade() -> None:
    """Trả hai tên về đúng như `r20260920_b0_06` để lại: lùi một bước là về đúng lược đồ trước đó."""
    op.execute(
        "ALTER TABLE idempotency_records "
        "RENAME CONSTRAINT ck_idempotency_records_state TO ck_idempotency_records_ck_idempotency_records_state"
    )
    op.execute(
        "ALTER TABLE idempotency_records "
        "RENAME CONSTRAINT ck_idempotency_records_key_format "
        "TO ck_idempotency_records_ck_idempotency_records_key_format"
    )
