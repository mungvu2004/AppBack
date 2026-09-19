"""tools/lint_migrations.py — [8]: mỗi thao tác cấm BE-00 §6.1, tên revision, merge, contract."""

from __future__ import annotations

from pathlib import Path

from tools.lint_migrations import Report, run


def _write(dir_: Path, name: str, body: str) -> None:
    (dir_ / name).write_text(body, encoding="utf-8")


def _rules(report: Report) -> set[str]:
    return {v.rule for v in report.violations}


def test_thư_mục_thiếu_trả_0_revision(tmp_path: Path) -> None:
    report = run(tmp_path / "khong-ton-tai")
    assert report.ok


def test_revision_hợp_lệ_đạt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ok.py",
        'revision = "r20260918_b0_03_fix001"\n'
        "down_revision = None\n"
        "from alembic import op\n"
        "import sqlalchemy as sa\n"
        "def upgrade() -> None:\n"
        '    op.create_table("widgets", sa.Column("id", sa.Integer()))\n'
        '    op.add_column("widgets", sa.Column("qty", sa.Integer(), nullable=False, server_default="0"))\n'
        "    with op.get_context().autocommit_block():\n"
        '        op.create_index("ix_w_qty", "other_table", ["qty"], postgresql_concurrently=True)\n'
        "def downgrade() -> None:\n"
        '    op.drop_table("widgets")\n',
    )
    report = run(tmp_path)
    assert report.ok, report.violations


def test_drop_table_ngoài_downgrade_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "bad.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        'def upgrade() -> None:\n    op.drop_table("x")\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "thao tác cấm (§6.1)" in _rules(report)


def test_drop_table_trong_downgrade_được_miễn(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "ok_down.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        "def upgrade() -> None:\n    pass\n"
        'def downgrade() -> None:\n    op.drop_table("x")\n',
    )
    report = run(tmp_path)
    assert report.ok


def test_hàm_phụ_gọi_từ_upgrade_vẫn_bị_bắt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "helper.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        'def _helper() -> None:\n    op.drop_column("x", "y")\n'
        "def upgrade() -> None:\n    _helper()\n"
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "thao tác cấm (§6.1)" in _rules(report)


def test_batch_alter_table_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "batch.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        'def upgrade() -> None:\n    op.batch_alter_table("x")\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "thao tác cấm (§6.1)" in _rules(report)


def test_concurrently_ngoài_autocommit_block_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "conc.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        "def upgrade() -> None:\n"
        '    op.create_index("ix", "other_table", ["c"], postgresql_concurrently=True)\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "create_index CONCURRENTLY ngoài autocommit_block" in _rules(report)


def test_sa_text_fstring_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "fstr.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        "def upgrade() -> None:\n"
        '    v = 1\n    op.execute(f"UPDATE x SET y = {v}")\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "execute đối số không phải hằng chuỗi" in _rules(report)


def test_sql_cấm_trong_chuỗi_hằng_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sql.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\nfrom alembic import op\n'
        "def upgrade() -> None:\n"
        '    op.execute("TRUNCATE x")\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "execute chuỗi SQL cấm" in _rules(report)


def test_contract_thiếu_trong_toml_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "contract.py",
        "# contract: sửa lược đồ theo yêu cầu pháp lý\n"
        'revision = "r20260918_b0_03"\ndown_revision = None\n'
        "def upgrade() -> None:\n    pass\n"
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)  # docs/contracts.toml thật của repo đang rỗng
    assert "# contract: chưa đăng ký ở docs/contracts.toml" in _rules(report)


def test_tên_33_ký_tự_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "long.py",
        'revision = "r20260918_this_is_33_characters_x"\ndown_revision = None\n'
        "def upgrade() -> None:\n    pass\ndef downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert any("vượt trần" in v.detail for v in report.violations)


def test_merge_hợp_lệ_1_và_2_đạt(tmp_path: Path) -> None:
    for k in (1, 2):
        _write(
            tmp_path,
            f"merge{k}.py",
            f'revision = "r20260918_merge_w08_{k}"\ndown_revision = None\n'
            "def upgrade() -> None:\n    pass\ndef downgrade() -> None:\n    pass\n",
        )
    report = run(tmp_path)
    assert report.ok


def test_merge_thiếu_k_hoặc_k_0_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "m1.py",
        'revision = "r20260918_merge_w08"\ndown_revision = None\n'
        "def upgrade() -> None:\n    pass\ndef downgrade() -> None:\n    pass\n",
    )
    _write(
        tmp_path,
        "m2.py",
        'revision = "r20260918_merge_w08_0"\ndown_revision = None\n'
        "def upgrade() -> None:\n    pass\ndef downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert len(report.violations) == 2
    assert all("sai mẫu revision merge" in v.detail for v in report.violations)


def test_add_column_not_null_thiếu_server_default_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "col.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\n'
        "from alembic import op\nimport sqlalchemy as sa\n"
        "def upgrade() -> None:\n"
        '    op.add_column("x", sa.Column("y", sa.Integer(), nullable=False))\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "add_column NOT NULL thiếu server_default" in _rules(report)


def test_alter_column_type_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "altertype.py",
        'revision = "r20260918_b0_03"\ndown_revision = None\n'
        "from alembic import op\nimport sqlalchemy as sa\n"
        "def upgrade() -> None:\n"
        '    op.alter_column("x", "y", type_=sa.String())\n'
        "def downgrade() -> None:\n    pass\n",
    )
    report = run(tmp_path)
    assert "alter_column cấm tham số" in _rules(report)
