"""tools/coverage_gate.py — [8]: biên 89,99/90,00; tập file bị chạm; cấu hình riêng; chú thích né cổng."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools import coverage_gate as cg

PRAGMA = "pragma: no " + "cover"
TYPE_IGNORE = "type: " + "ignore"


def _summary(covered: int, total: int, cov_branch: int = 0, total_branch: int = 0) -> dict[str, int]:
    """Tóm tắt coverage giả với số dòng/nhánh đã cho."""
    return {
        "covered_lines": covered,
        "num_statements": total,
        "covered_branches": cov_branch,
        "num_branches": total_branch,
    }


def _cov_json(files: dict[str, Any], totals: dict[str, int]) -> dict[str, Any]:
    """Nội dung `coverage.json` giả."""
    return {"files": files, "totals": totals}


def _fake_repo(tmp_path: Path) -> Path:
    """Dựng cây repo tối thiểu (packages/core, apps/api, tools, đều có `__init__.py`)."""
    (tmp_path / "packages" / "core").mkdir(parents=True)
    (tmp_path / "packages" / "core" / "__init__.py").write_text('"""x"""\n', encoding="utf-8")
    (tmp_path / "apps" / "api").mkdir(parents=True)
    (tmp_path / "apps" / "api" / "__init__.py").write_text('"""x"""\n', encoding="utf-8")
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / "tools" / "__init__.py").write_text('"""x"""\n', encoding="utf-8")
    return tmp_path


class TestUnitOf:
    """`unit_of`: ánh xạ đường tương đối sang đơn vị."""

    def test_package(self) -> None:
        """Tệp dưới `packages/<gói>/` thuộc đơn vị `packages/<gói>`."""
        assert cg.unit_of("packages/core/errors.py") == "packages/core"

    def test_app_module(self) -> None:
        """Tệp dưới module của app thuộc `apps/<app>/<module>`."""
        assert cg.unit_of("apps/api/auth/router.py") == "apps/api/auth"

    def test_app_file_thẳng(self) -> None:
        """Tệp nằm thẳng trong `apps/<app>/` thuộc `apps/<app>`."""
        assert cg.unit_of("apps/api/main.py") == "apps/api"

    def test_tools_một_đơn_vị(self) -> None:
        """Mọi tệp dưới `tools/` là một đơn vị `tools`."""
        assert cg.unit_of("tools/coverage_gate.py") == "tools"
        assert cg.unit_of("tools/verify/steps.py") == "tools"

    def test_file_gốc_packages_apps_không_là_đơn_vị(self) -> None:
        """Tệp gốc của `packages/`, `apps/` không thuộc đơn vị nào."""
        assert cg.unit_of("packages/__init__.py") is None
        assert cg.unit_of("apps/__init__.py") is None

    def test_deploy_một_đơn_vị(self) -> None:
        """Mọi tệp dưới `deploy/` (kể cả shell, Dockerfile) thuộc đơn vị `deploy` (NO-350)."""
        assert cg.unit_of("deploy/docker/verify.Dockerfile") == "deploy"
        assert cg.unit_of("deploy/scripts/tests/test_deploy.py") == "deploy"
        assert cg.unit_of("tests/e2e/test_flow.py") == "tests"

    def test_ngoài_gốc_none(self) -> None:
        """Đường ngoài các gốc đơn vị trả `None`."""
        assert cg.unit_of("docs/charter/BE-00.md") is None


class TestThresholds:
    """`check_thresholds`: biên 90%, nhánh worker, tập tệp bị chạm."""

    def _run(
        self, tmp_path: Path, files: dict[str, Any], totals: dict[str, int], branch: str, changed: list[str]
    ) -> cg.Report:
        """Chạy `check_thresholds` trên dữ liệu giả, trả báo cáo."""
        report = cg.Report()
        cg.check_thresholds(_cov_json(files, totals), branch, changed, report)
        return report

    def test_biên_89_99_hỏng(self, tmp_path: Path) -> None:
        """89,99% dòng tổng thì hỏng."""
        files = {"packages/core/x.py": {"summary": _summary(8999, 10000)}}
        totals = _summary(8999, 10000)
        r = self._run(tmp_path, files, totals, "integration", [])
        assert any("tổng" in f.rule for f in r.findings)

    def test_biên_90_00_đạt(self, tmp_path: Path) -> None:
        """90,00% dòng tổng thì đạt."""
        files = {"packages/core/x.py": {"summary": _summary(9000, 10000)}}
        totals = _summary(9000, 10000)
        r = self._run(tmp_path, files, totals, "integration", [])
        assert r.ok

    def test_0_nhánh_tính_100(self, tmp_path: Path) -> None:
        """Không có nhánh nào thì % nhánh tính 100."""
        files = {"packages/core/x.py": {"summary": _summary(10, 10, 0, 0)}}
        totals = _summary(10, 10, 0, 0)
        r = self._run(tmp_path, files, totals, "integration", [])
        assert r.ok

    def test_nhánh_worker_chỉ_tính_đơn_vị_bị_chạm(self, tmp_path: Path) -> None:
        """Nhánh worker chỉ nêu đơn vị bị chạm, không nêu đơn vị khác."""
        files = {
            "packages/core/x.py": {"summary": _summary(0, 10)},
            "packages/domain/y.py": {"summary": _summary(10, 10)},
        }
        totals = _summary(10, 20)
        # tổng 50% sẽ hỏng "tổng"; ta chỉ kiểm rằng core (bị chạm) cũng bị nêu, domain (không bị chạm) thì không
        r = self._run(tmp_path, files, totals, "worker", ["packages/core/x.py"])
        assert any("packages/core" in f.detail for f in r.findings)
        assert not any("packages/domain" in f.detail for f in r.findings)

    def test_tập_file_bị_chạm_bỏ_file_0_câu_lệnh(self, tmp_path: Path) -> None:
        """Tệp 0 câu lệnh bị bỏ khỏi tập tệp bị chạm."""
        files = {
            "packages/core/x.py": {"summary": _summary(0, 0)},  # 0 câu lệnh — bỏ
            "packages/core/y.py": {"summary": _summary(10, 10)},
        }
        totals = _summary(10, 10)
        r = self._run(tmp_path, files, totals, "worker", ["packages/core/x.py", "packages/core/y.py"])
        assert r.ok

    def test_tập_file_bị_chạm_dưới_90_hỏng(self, tmp_path: Path) -> None:
        """Tập tệp bị chạm dưới 90% thì hỏng."""
        files = {
            "packages/core/x.py": {"summary": _summary(1, 10)},
        }
        totals = _summary(1, 10)
        r = self._run(tmp_path, files, totals, "worker", ["packages/core/x.py"])
        assert any("tập file bị chạm" in f.rule for f in r.findings)

    def test_file_đã_xoá_khỏi_coverage_bị_bỏ(self, tmp_path: Path) -> None:
        """Tệp bị chạm không còn trong coverage (đã xoá) thì bị bỏ qua."""
        files = {"packages/core/y.py": {"summary": _summary(10, 10)}}
        totals = _summary(10, 10)
        r = self._run(tmp_path, files, totals, "worker", ["packages/core/deleted.py"])
        assert r.ok


class TestForbiddenStructure:
    """Các kiểm cấu trúc: tệp cấm, chú thích né cổng, pyproject, vị trí test, `__init__.py`, `addopts`."""

    def test_coveragerc_bị_cấm(self, tmp_path: Path) -> None:
        """`.coveragerc` bị cấm."""
        root = _fake_repo(tmp_path)
        (root / "packages" / ".coveragerc").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_files(root, report)
        assert any(".coveragerc" in f.detail for f in report.findings)

    def test_conftest_ngoài_gốc_bị_cấm(self, tmp_path: Path) -> None:
        """`conftest.py` ngoài gốc bị cấm."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "conftest.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_files(root, report)
        assert any(f.rule == "conftest.py ngoài gốc" for f in report.findings)

    def test_conftest_gốc_không_bị_cấm(self, tmp_path: Path) -> None:
        """`conftest.py` gốc được phép."""
        root = _fake_repo(tmp_path)
        (root / "conftest.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_files(root, report)
        assert report.ok

    def test_pragma_no_cover_bị_cấm(self, tmp_path: Path) -> None:
        """Chú thích loại trừ độ phủ bị bắt."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "x.py").write_text(f"x = 1  # {PRAGMA}\n", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_text(root, report)
        assert any("pragma" in f.detail for f in report.findings)

    def test_type_ignore_không_mã_không_bị_bắt_ở_đây(self, tmp_path: Path) -> None:
        """`type: ignore` không mã do ruff bắt, không phải coverage_gate (K24)."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "x.py").write_text(f"x = 1  # {TYPE_IGNORE}\n", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_text(root, report)
        assert report.ok

    def test_no_type_check_bị_cấm(self, tmp_path: Path) -> None:
        """`typing.no_type_check` bị cấm."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "x.py").write_text(
            "import typing\n@typing.no_type_check\ndef f(): pass\n", encoding="utf-8"
        )
        report = cg.Report()
        cg.check_forbidden_text(root, report)
        assert any("no_type_check" in f.detail for f in report.findings)

    def test_tools_được_miễn_quét_nội_dung(self, tmp_path: Path) -> None:
        """Mã dưới `tools/` được miễn quét nội dung."""
        root = _fake_repo(tmp_path)
        (root / "tools" / "x.py").write_text(f"x = 1  # {PRAGMA}\n", encoding="utf-8")
        report = cg.Report()
        cg.check_forbidden_text(root, report)
        assert report.ok

    def test_pyproject_thành_viên_có_bảng_lạ_hỏng(self, tmp_path: Path) -> None:
        """`pyproject.toml` thành viên có bảng `[tool.ruff]` thì hỏng."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "pyproject.toml").write_text(
            '[project]\nname = "x"\n[tool.ruff]\nline-length = 100\n', encoding="utf-8"
        )
        report = cg.Report()
        cg.check_member_pyproject_tables(root, report)
        assert any("ruff" in str(f.detail) for f in report.findings)

    def test_pyproject_thành_viên_hợp_lệ_đạt(self, tmp_path: Path) -> None:
        """`pyproject.toml` thành viên chỉ có `[tool.uv]` thì đạt."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "pyproject.toml").write_text(
            '[project]\nname = "x"\n[tool.uv]\npackage = false\n', encoding="utf-8"
        )
        report = cg.Report()
        cg.check_member_pyproject_tables(root, report)
        assert report.ok

    def test_test_file_ngoài_tests_hỏng(self, tmp_path: Path) -> None:
        """`test_*.py` ngoài thư mục `tests/` thì hỏng."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "test_x.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_test_files_location(root, report)
        assert not report.ok

    def test_test_file_trong_tests_đạt(self, tmp_path: Path) -> None:
        """`test_*.py` trong `tests/` có `__init__.py` thì đạt."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "tests").mkdir()
        (root / "packages" / "core" / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (root / "packages" / "core" / "tests" / "test_x.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_test_files_location(root, report)
        cg.check_missing_init(root, report)
        assert report.ok

    def test_thư_mục_thiếu_init_hỏng(self, tmp_path: Path) -> None:
        """Thư mục có `.py` mà thiếu `__init__.py` thì hỏng."""
        root = _fake_repo(tmp_path)
        (root / "packages" / "core" / "sub").mkdir()
        (root / "packages" / "core" / "sub" / "x.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_missing_init(root, report)
        assert not report.ok

    def test_migrations_versions_miễn_init(self, tmp_path: Path) -> None:
        """`migrations/versions` được miễn `__init__.py`."""
        root = _fake_repo(tmp_path)
        vdir = root / "packages" / "core" / "migrations" / "versions"
        vdir.mkdir(parents=True)
        (vdir / "r1.py").write_text("", encoding="utf-8")
        report = cg.Report()
        cg.check_missing_init(root, report)
        assert report.ok

    def test_addopts_cov_bị_cấm(self, tmp_path: Path) -> None:
        """`--cov` trong `addopts` bị cấm."""
        root = _fake_repo(tmp_path)
        (root / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "--cov=packages"\n', encoding="utf-8"
        )
        report = cg.Report()
        cg.check_addopts_no_cov(root, report)
        assert not report.ok

    def test_addopts_không_cov_đạt(self, tmp_path: Path) -> None:
        """`addopts` không có `--cov` thì đạt."""
        root = _fake_repo(tmp_path)
        (root / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "-m \\"not gpu\\""\n', encoding="utf-8"
        )
        report = cg.Report()
        cg.check_addopts_no_cov(root, report)
        assert report.ok


def test_thư_mục_cấm_khác_setup_cfg_tox_ini(tmp_path: Path) -> None:
    """`tox.ini` (và các cấu hình riêng khác) bị cấm."""
    root = _fake_repo(tmp_path)
    (root / "packages" / "core" / "tox.ini").write_text("", encoding="utf-8")
    report = cg.Report()
    cg.check_forbidden_files(root, report)
    assert not report.ok
