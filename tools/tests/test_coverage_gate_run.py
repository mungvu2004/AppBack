"""tools/coverage_gate.py — đọc VERIFY_CHANGED, cấu hình coverage hiệu lực, run()/main()."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools import coverage_gate as cg

REAL_ROOT = Path(__file__).resolve().parent.parent.parent


def _summary(covered: int, total: int) -> dict[str, int]:
    return {"covered_lines": covered, "num_statements": total, "covered_branches": 0, "num_branches": 0}


def _fake_repo(root: Path, covered: int) -> Path:
    for pkg in ("packages/core", "apps/api", "tools"):
        (root / pkg).mkdir(parents=True)
        (root / pkg / "__init__.py").write_text('"""x"""\n', encoding="utf-8")
    (root / "pyproject.toml").write_text((REAL_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
    data: dict[str, Any] = {
        "files": {"packages/core/x.py": {"summary": _summary(covered, 10)}},
        "totals": _summary(covered, 10),
    }
    (root / "coverage.json").write_text(json.dumps(data), encoding="utf-8")
    return root


def _pyproject_variant(tmp_path: Path, old: str, new: str) -> Path:
    text = (REAL_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert old in text
    (tmp_path / "pyproject.toml").write_text(text.replace(old, new), encoding="utf-8")
    return tmp_path


def _config_keys(root: Path) -> list[str]:
    report = cg.Report()
    cg.check_coverage_config(root, report)
    return [f.detail.split(":")[0] for f in report.findings]


def test_load_changed_files_chuẩn_hoá_đường(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_CHANGED", "packages\\core\\x.py\n\n  tools/a.py  \n")
    assert cg.load_changed_files() == ["packages/core/x.py", "tools/a.py"]


def test_cấu_hình_coverage_thật_đúng_d() -> None:
    assert _config_keys(REAL_ROOT) == []


def test_exclude_also_thêm_một_dòng_hỏng(tmp_path: Path) -> None:
    root = _pyproject_variant(tmp_path, '    "@overload",\n', '    "@overload",\n    "raise NotImplementedError",\n')
    assert _config_keys(root) == ["exclude_also"]


def test_branch_tắt_hỏng(tmp_path: Path) -> None:
    assert _config_keys(_pyproject_variant(tmp_path, "branch = true", "branch = false")) == ["branch"]


def test_omit_thêm_mẫu_hỏng(tmp_path: Path) -> None:
    root = _pyproject_variant(tmp_path, 'omit = ["*/tests/*"', 'omit = ["apps/*", "*/tests/*"')
    assert _config_keys(root) == ["run_omit (omit)"]


def test_run_đạt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_BRANCH", "worker")
    monkeypatch.setenv("VERIFY_CHANGED", "packages/core/x.py")
    report = cg.run(_fake_repo(tmp_path, 10))
    assert report.ok, report.findings


def test_run_thiếu_coverage_json_hỏng(tmp_path: Path) -> None:
    root = _fake_repo(tmp_path, 10)
    (root / "coverage.json").unlink()
    assert [f.rule for f in cg.run(root).findings] == ["thiếu coverage.json"]


def test_main_đạt_và_hỏng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("VERIFY_BRANCH", "integration")
    monkeypatch.setattr(cg, "REPO_ROOT", _fake_repo(tmp_path / "ok", 10))
    assert cg.main() == 0
    monkeypatch.setattr(cg, "REPO_ROOT", _fake_repo(tmp_path / "bad", 5))
    assert cg.main() == 1
    assert "độ phủ dòng tổng < 90%" in capsys.readouterr().out


def test_bảng_ngoài_project_tool_ở_pyproject_thành_viên_hỏng(tmp_path: Path) -> None:
    root = _fake_repo(tmp_path, 10)
    (root / "apps" / "api" / "pyproject.toml").write_text(
        '[project]\nname = "x"\n[build-system]\nrequires = []\n', encoding="utf-8"
    )
    report = cg.Report()
    cg.check_member_pyproject_tables(root, report)
    assert [f.rule for f in report.findings] == ["bảng ngoài luật ở pyproject thành viên"]


def test_mypy_ignore_errors_và_no_branch_bị_cấm(tmp_path: Path) -> None:
    root = _fake_repo(tmp_path, 10)
    (root / "packages" / "core" / "a.py").write_text("# mypy: ignore-errors\n", encoding="utf-8")
    (root / "apps" / "api" / "b.py").write_text("if x:  # pragma: no branch\n    pass\n", encoding="utf-8")
    report = cg.Report()
    cg.check_forbidden_text(root, report)
    assert len(report.findings) == 2


def test_paths_lệch_hỏng(tmp_path: Path) -> None:
    root = _pyproject_variant(tmp_path, '    "/app",\n', "")
    assert _config_keys(root) == ["paths"]
