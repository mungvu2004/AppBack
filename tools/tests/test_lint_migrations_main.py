"""tools/lint_migrations.py — mẫu alembic, tên sai khuôn, contract đã đăng ký, main()."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools import lint_migrations
from tools.lint_migrations import Report, revision_of, run


def _write(dir_: Path, name: str, body: str) -> Path:
    path = dir_ / name
    path.write_text(body, encoding="utf-8")
    return path


def _rules(report: Report) -> set[str]:
    return {v.rule for v in report.violations}


def test_mẫu_alembic_annassign_đọc_được_revision(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "alembic_style.py",
        "from typing import Sequence, Union\n"
        "revision: str = 'r20260918_merge_w08_1'\n"
        "down_revision: Union[str, Sequence[str], None] = ('a', 'b')\n"
        "def upgrade() -> None:\n    pass\ndef downgrade() -> None:\n    pass\n",
    )
    assert run(tmp_path).ok
    assert revision_of(path) == "r20260918_merge_w08_1"


def test_revision_không_phải_chuỗi_hằng_hỏng(tmp_path: Path) -> None:
    _write(tmp_path, "dyn.py", 'X = "r20260918_b0_03"\nrevision = X\n')
    assert _rules(run(tmp_path)) == {'thiếu biến revision = "..."'}


def test_thiếu_biến_revision_hỏng(tmp_path: Path) -> None:
    _write(tmp_path, "norev.py", "def upgrade() -> None:\n    pass\n")
    assert _rules(run(tmp_path)) == {'thiếu biến revision = "..."'}


def test_lỗi_cú_pháp_hỏng(tmp_path: Path) -> None:
    path = _write(tmp_path, "broken.py", "def upgrade(:\n")
    assert _rules(run(tmp_path)) == {"lỗi cú pháp"}
    assert revision_of(path) is None


def test_hậu_tố_fix_sai_số_chữ_số_hỏng(tmp_path: Path) -> None:
    _write(tmp_path, "fix.py", 'revision = "r20260918_b0_03_fix01"\n')
    assert any("_fix" in v.detail for v in run(tmp_path).violations)


def test_mã_viết_hoa_sai_mẫu_hỏng(tmp_path: Path) -> None:
    _write(tmp_path, "upper.py", 'revision = "r20260918_B0_03"\n')
    assert any("sai mẫu revision r<" in v.detail for v in run(tmp_path).violations)


def test_create_index_bảng_tạo_cùng_revision_không_cần_concurrently(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "same.py",
        'revision = "r20260918_b0_03"\nfrom alembic import op\n'
        'def upgrade() -> None:\n    op.create_table("t")\n    op.create_index("ix", table_name="t", columns=["c"])\n',
    )
    assert run(tmp_path).ok


def test_create_index_table_name_kwarg_thiếu_concurrently_hỏng(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "kw.py",
        'revision = "r20260918_b0_03"\nfrom alembic import op\n'
        'def upgrade() -> None:\n    op.create_index("ix", table_name="old", columns=["c"])\n',
    )
    assert "create_index thiếu postgresql_concurrently=True" in _rules(run(tmp_path))


def test_alter_column_new_column_name_hỏng_nullable_true_đạt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "alter.py",
        'revision = "r20260918_b0_03"\nfrom alembic import op\n'
        "def upgrade() -> None:\n"
        '    op.alter_column("t", "a", nullable=True)\n'
        '    op.alter_column("t", "b", new_column_name="c")\n',
    )
    assert [v.detail for v in run(tmp_path).violations] == ["new_column_name"]


def _contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, upgrade: str, *, registered: bool = True) -> Report:
    """Lint một revision `# contract:` với thân `upgrade` cho trước; `registered` = tên có trong contracts.toml."""
    listed = '["r20260918_b0_03"]' if registered else "[]"
    contracts = _write(tmp_path, "contracts.toml", f"revisions = {listed}\n")
    monkeypatch.setattr(lint_migrations, "CONTRACTS_TOML", contracts)
    versions = tmp_path / "versions"
    versions.mkdir()
    _write(
        versions,
        "c.py",
        '# contract: bỏ cột cũ ở lần phát hành sau\nrevision = "r20260918_b0_03"\nfrom alembic import op\n'
        f"def upgrade() -> None:\n{upgrade}def downgrade() -> None:\n    pass\n",
    )
    return run(versions)


def test_contract_đã_đăng_ký_đạt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _contract(tmp_path, monkeypatch, "    pass\n").ok


def test_contract_đã_đăng_ký_được_phá_huỷ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FIX-038: đường contract của BE-00 §6.1 phải dùng được — drop/rename/NOT NULL không bị luật expand chặn."""
    upgrade = (
        '    op.execute("ALTER TABLE t RENAME CONSTRAINT ck_a TO ck_b")\n'
        '    op.drop_constraint("ck_c", "t")\n'
        '    op.alter_column("t", "a", nullable=False)\n'
        '    op.add_column("t", sa.Column("b", sa.Integer(), nullable=False))\n'
    )
    report = _contract(tmp_path, monkeypatch, upgrade)
    assert report.ok, report.violations


def test_contract_đã_đăng_ký_vẫn_kiểm_luật_không_phá_huỷ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Miễn hẹp: SQL không hằng, `batch_alter_table`, index khoá bảng vẫn hỏng trong revision contract."""
    upgrade = (
        '    op.drop_column("t", "a")\n'
        "    op.execute(sql)\n"
        '    op.batch_alter_table("t")\n'
        '    op.create_index("ix_t_c", "t", ["c"])\n'
    )
    report = _contract(tmp_path, monkeypatch, upgrade)
    assert {(v.rule, v.detail) for v in report.violations} == {
        ("execute đối số không phải hằng chuỗi", ""),
        ("thao tác cấm (§6.1)", "batch_alter_table"),
        ("create_index thiếu postgresql_concurrently=True", "t"),
    }


def test_contract_chưa_đăng_ký_không_được_phá_huỷ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upgrade = '    op.execute("ALTER TABLE t RENAME CONSTRAINT ck_a TO ck_b")\n'
    report = _contract(tmp_path, monkeypatch, upgrade, registered=False)
    assert _rules(report) == {"# contract: chưa đăng ký ở docs/contracts.toml", "execute chuỗi SQL cấm"}


@pytest.mark.parametrize("registered", [True, False])
def test_tên_thêm_vào_destructive_chỉ_được_miễn_cho_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, registered: bool
) -> None:
    """FIX-042: miễn cho contract đi theo `_DESTRUCTIVE_CALL_NAMES`; `batch_alter_table` ngoài tập nên vẫn hỏng."""
    names = {*lint_migrations._DESTRUCTIVE_CALL_NAMES, "drop_index"}
    monkeypatch.setattr(lint_migrations, "_DESTRUCTIVE_CALL_NAMES", names)
    upgrade = '    op.drop_index("ix_t_c")\n    op.batch_alter_table("t")\n'
    report = _contract(tmp_path, monkeypatch, upgrade, registered=registered)
    banned = sorted(v.detail for v in report.violations if v.rule == "thao tác cấm (§6.1)")
    assert banned == (["batch_alter_table"] if registered else ["batch_alter_table", "drop_index"])


def test_contracts_toml_thiếu_coi_như_rỗng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lint_migrations, "CONTRACTS_TOML", tmp_path / "khong-co.toml")
    _write(tmp_path, "c.py", '# contract: lý do\nrevision = "r20260918_b0_03"\n')
    assert _rules(run(tmp_path)) == {"# contract: chưa đăng ký ở docs/contracts.toml"}


def test_main_thư_mục_thiếu_trả_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert lint_migrations.main([str(tmp_path / "khong-co")]) == 0
    assert "0 revision" in capsys.readouterr().out


def test_main_đạt_và_hỏng(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "ok.py", 'revision = "r20260918_b0_03"\n')
    assert lint_migrations.main([str(tmp_path)]) == 0
    _write(tmp_path, "bad.py", 'revision = "r20260918_merge_w08_0"\n')
    assert lint_migrations.main([str(tmp_path)]) == 1
    assert "hỏng (2 revision)" in capsys.readouterr().out


def test_main_mặc_định_là_thư_mục_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(lint_migrations, "VERSIONS_DIR", tmp_path / "khong-co")
    monkeypatch.setattr("sys.argv", ["lint_migrations"])
    assert lint_migrations.main() == 0
