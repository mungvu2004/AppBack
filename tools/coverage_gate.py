"""Cổng độ phủ — BE-00 §12 bước 5, cài đúng B0-01 [6]G.

Đọc `coverage.json` (sinh bởi `coverage json`), `VERIFY_CHANGED` (đường dẫn đổi,
mỗi dòng một đường, tương đối gốc repo), `VERIFY_BRANCH` (`worker|integration`).
In bảng, thoát khác 0 khi có luật hỏng. Không đọc mạng, không sửa file nào.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Một mục `files[...]["summary"]` / `totals` của coverage.json
Summary = dict[str, Any]

THRESHOLD = 90.0
REPO_ROOT = Path(__file__).resolve().parent.parent
COVERAGE_JSON = Path(os.environ.get("COVERAGE_JSON_FILE", "coverage.json"))

SOURCE_ROOTS = ("packages", "apps", "tools")

EXPECTED_RUN_OMIT = ["*/tests/*", "packages/db/migrations/*"]
EXPECTED_PATHS = {"source": [".", "/tmp/w", "/app", "/home/runner/work/*/AppBack"]}
EXPECTED_EXCLUDE_ALSO = ["if TYPE_CHECKING:", "@overload", r"^\s*\.\.\.$"]

FORBIDDEN_CONFIG_BASENAMES = {
    ".coveragerc",
    "setup.cfg",
    "tox.ini",
    "pytest.ini",
    "mypy.ini",
    "ruff.toml",
    ".ruff.toml",
}

# \s* thay vì khoảng trắng thật để chính các file trong tools/ không tự khớp
# luật của mình khi bị quét (xem test_coverage_gate.py).
_FORBIDDEN_TEXT_PATTERNS = [
    re.compile(r"#\s*pragma\s*:\s*no\s*cover", re.IGNORECASE),
    re.compile(r"#\s*pragma\s*:\s*no\s*branch", re.IGNORECASE),
    re.compile(r"#\s*mypy\s*:\s*ignore-errors"),
    re.compile(r"@(\w+\.)?no_type_check\b"),
]

# Các file/thư mục gốc mà B0-01 dựng sẵn — chỉ quét bên trong chúng, không quét
# toàn bộ /tmp/w (tránh dính rác cục bộ không thuộc repo, vd thư mục ghi chú
# ngoài [10] deliverables).
SCAN_DIRS = ("packages", "apps", "tools", "deploy", "docs", "tests")


@dataclass
class Finding:
    """Một vi phạm: tên luật và chi tiết để in ra."""
    rule: str
    detail: str


@dataclass
class Report:
    """Kết quả cổng: các vi phạm (`findings`) và số đo in kèm (`numbers`)."""
    findings: list[Finding] = field(default_factory=list)
    numbers: list[str] = field(default_factory=list)  # số đo in kèm, không ảnh hưởng đạt/hỏng

    def add(self, rule: str, detail: str) -> None:
        """Thêm một vi phạm `rule`/`detail` vào báo cáo."""
        self.findings.append(Finding(rule, detail))

    @property
    def ok(self) -> bool:
        """Đạt khi không có vi phạm nào."""
        return not self.findings


def _iter_files(root: Path) -> Iterator[Path]:
    """Duyệt mọi tệp dưới các thư mục của `SCAN_DIRS` (bỏ thư mục không tồn tại)."""
    for base in SCAN_DIRS:
        d = root / base
        if not d.is_dir():
            continue
        yield from (p for p in d.rglob("*") if p.is_file())


def check_forbidden_files(root: Path, report: Report) -> None:
    """Cấm tệp cấu hình công cụ riêng và `conftest.py` ngoài gốc."""
    for p in _iter_files(root):
        if p.name in FORBIDDEN_CONFIG_BASENAMES:
            report.add("cấu hình riêng bị cấm", str(p.relative_to(root)))
        if p.name == "conftest.py" and p != root / "conftest.py":
            report.add("conftest.py ngoài gốc", str(p.relative_to(root)))


def check_forbidden_text(root: Path, report: Report) -> None:
    """Cấm chú thích né cổng trong mã `.py` ngoài `tools/` (tools/ được nhắc tới các mẫu cấm)."""
    # tools/ giữ chính mã ba công cụ cổng — chúng được phép NHẮC tới các mẫu
    # cấm (làm hằng regex), nên loại khỏi vùng quét nội dung.
    for p in _iter_files(root):
        if p.suffix != ".py":
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        if rel.parts[0] == "tools":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for pattern in _FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(text):
                report.add("chú thích né cổng", f"{rel}: {pattern.pattern}")


def check_member_pyproject_tables(root: Path, report: Report) -> None:
    """Cấm bảng ngoài `project`/`tool.uv` trong `pyproject.toml` của gói/app thành viên."""
    for base in ("packages", "apps"):
        d = root / base
        if not d.is_dir():
            continue
        for member in sorted(d.iterdir()):
            pyproj = member / "pyproject.toml"
            if not pyproj.is_file():
                continue
            data = tomllib.loads(pyproj.read_text(encoding="utf-8"))
            extra = sorted(set(data) - {"project", "tool"})
            if extra:
                report.add("bảng ngoài luật ở pyproject thành viên", f"{pyproj.relative_to(root)}: {extra}")
            tool = data.get("tool", {})
            extra_tool = sorted(set(tool) - {"uv"})
            if extra_tool:
                report.add("bảng [tool.*] lạ ở pyproject thành viên", f"{pyproj.relative_to(root)}: {extra_tool}")


def check_addopts_no_cov(root: Path, report: Report) -> None:
    """Cấm `--cov` trong `addopts` của pytest (độ phủ chỉ bật ở bước 5)."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("addopts", "")
    if "--cov" in addopts:
        report.add("--cov trong addopts", addopts)


def check_test_files_location(root: Path, report: Report) -> None:
    """Mọi `test_*.py` phải nằm dưới một thư mục `tests/`."""
    for p in _iter_files(root):
        if p.suffix != ".py" or not p.name.startswith("test_"):
            continue
        rel = p.relative_to(root)
        if "tests" not in rel.parts[:-1]:
            report.add("test_*.py ngoài thư mục tests/", str(rel))


def check_missing_init(root: Path, report: Report) -> None:
    """Mọi thư mục có `.py` phải có `__init__.py` (trừ `migrations/versions`)."""
    dirs_with_py: set[Path] = set()
    for p in _iter_files(root):
        if p.suffix == ".py":
            dirs_with_py.add(p.parent)
    for d in sorted(dirs_with_py):
        rel = d.relative_to(root)
        if "migrations" in rel.parts and "versions" in rel.parts:
            continue
        if not (d / "__init__.py").exists():
            report.add("thư mục có .py thiếu __init__.py", str(rel))


def check_coverage_config(root: Path, report: Report) -> None:
    """Đối chiếu cấu hình coverage đang nạp với giá trị bắt buộc [6]D."""
    import coverage

    cwd = Path.cwd()
    try:
        os.chdir(root)
        cfg = coverage.Coverage().config
    finally:
        os.chdir(cwd)

    checks = {
        "branch": (cfg.branch, True),
        "parallel": (cfg.parallel, True),
        "relative_files": (cfg.relative_files, True),
        "patch": (cfg.patch, ["subprocess"]),
        "source": (cfg.source, list(SOURCE_ROOTS)),
        "run_omit (omit)": (cfg.run_omit, EXPECTED_RUN_OMIT),
        "exclude_also": (cfg.exclude_also, EXPECTED_EXCLUDE_ALSO),
        "paths": (cfg.paths, EXPECTED_PATHS),
    }
    for key, (actual, expected) in checks.items():
        if actual != expected:
            report.add("cấu hình coverage lệch [6]D", f"{key}: {actual!r} != {expected!r}")


# ---------------------------------------------------------------------------
# Ngưỡng số theo đơn vị / tập file bị chạm
# ---------------------------------------------------------------------------


def unit_of(rel_path: str) -> str | None:
    """Đơn vị (gói/app/thư mục gốc) của một đường tương đối; `None` nếu không thuộc đơn vị nào.

    `deploy` và `tests` là đơn vị dù ngoài `[tool.coverage.run] source`: bước 5b chọn test `perf` theo
    đơn vị bị chạm (NO-350); độ phủ của đơn vị không có tệp đo được là 100% (`Totals` rỗng), không đỏ.
    """
    parts = Path(rel_path).parts
    if not parts:
        return None
    # file nằm thẳng dưới packages/ hay apps/ (vd __init__.py gốc) không thuộc đơn vị nào
    if parts[0] == "packages" and len(parts) >= 3:
        return f"packages/{parts[1]}"
    if parts[0] == "apps" and len(parts) >= 3:
        # file nằm thẳng trong apps/<app>/ (len==3, không có thư mục module) thuộc apps/<app>
        return f"apps/{parts[1]}" if len(parts) <= 3 else f"apps/{parts[1]}/{parts[2]}"
    if parts[0] in ("tools", "deploy", "tests"):
        return parts[0]
    return None


@dataclass
class Totals:
    """Tổng dòng/nhánh đã phủ và tổng số, tính % cho một đơn vị hoặc toàn bộ."""
    covered_lines: int = 0
    num_statements: int = 0
    covered_branches: int = 0
    num_branches: int = 0

    def add(self, summary: Summary) -> None:
        """Cộng các số dòng/nhánh của một tóm tắt coverage vào tổng."""
        self.covered_lines += summary.get("covered_lines", 0)
        self.num_statements += summary.get("num_statements", 0)
        self.covered_branches += summary.get("covered_branches", 0)
        self.num_branches += summary.get("num_branches", 0)

    @property
    def line_pct(self) -> float:
        """% dòng đã phủ; 100 khi không có câu lệnh nào."""
        return 100.0 if self.num_statements == 0 else 100.0 * self.covered_lines / self.num_statements

    @property
    def branch_pct(self) -> float:
        """% nhánh đã phủ; 100 khi không có nhánh nào."""
        return 100.0 if self.num_branches == 0 else 100.0 * self.covered_branches / self.num_branches


def _norm(p: str) -> str:
    """Đổi dấu `\` thành `/` để so đường tương đối giữa Windows và Linux."""
    return p.replace("\\", "/")


def load_changed_files() -> list[str]:
    """Các tệp bị chạm, đọc từ biến môi trường `VERIFY_CHANGED` (mỗi dòng một đường)."""
    raw = os.environ.get("VERIFY_CHANGED", "")
    return [_norm(line.strip()) for line in raw.splitlines() if line.strip()]


def check_thresholds(coverage_data: dict[str, Any], branch: str, changed: list[str], report: Report) -> None:
    """Kiểm ngưỡng 90% dòng/nhánh: tổng, từng đơn vị bị chạm và tập tệp bị chạm."""
    files: dict[str, dict[str, Any]] = {_norm(k): v for k, v in coverage_data.get("files", {}).items()}
    totals_summary = coverage_data.get("totals", {})

    overall = Totals()
    overall.add(totals_summary)
    report.numbers.append(f"tổng: dòng {overall.line_pct:.2f}% · nhánh {overall.branch_pct:.2f}%")
    if overall.line_pct < THRESHOLD:
        report.add("độ phủ dòng tổng < 90%", f"{overall.line_pct:.2f}%")
    if overall.branch_pct < THRESHOLD:
        report.add("độ phủ nhánh tổng < 90%", f"{overall.branch_pct:.2f}%")

    units: dict[str, Totals] = {}
    for path, info in files.items():
        u = unit_of(path)
        if u is None:
            continue
        units.setdefault(u, Totals()).add(info.get("summary", {}))

    if branch == "integration":
        touched_units = set(units)
    else:
        touched_units = set()
        for c in changed:
            u = unit_of(c)
            if u is not None:
                touched_units.add(u)

    for u in sorted(touched_units):
        t = units.get(u, Totals())
        report.numbers.append(f"{u}: dòng {t.line_pct:.2f}% · nhánh {t.branch_pct:.2f}%")
        if t.line_pct < THRESHOLD:
            report.add("độ phủ dòng đơn vị bị chạm < 90%", f"{u}: {t.line_pct:.2f}%")
        if t.branch_pct < THRESHOLD:
            report.add("độ phủ nhánh đơn vị bị chạm < 90%", f"{u}: {t.branch_pct:.2f}%")

    if branch != "integration":
        flat = Totals()
        for c in changed:
            entry = files.get(c)
            if entry is None:
                continue  # đã xoá, hoặc bị omit khỏi coverage
            summary = entry.get("summary", {})
            if summary.get("num_statements", 0) == 0:
                continue  # 0 câu lệnh — bỏ
            flat.add(summary)
        report.numbers.append(f"tập file bị chạm: dòng {flat.line_pct:.2f}% · nhánh {flat.branch_pct:.2f}%")
        if flat.line_pct < THRESHOLD:
            report.add("độ phủ dòng tập file bị chạm < 90%", f"{flat.line_pct:.2f}%")
        if flat.branch_pct < THRESHOLD:
            report.add("độ phủ nhánh tập file bị chạm < 90%", f"{flat.branch_pct:.2f}%")


# ---------------------------------------------------------------------------


def run(root: Path) -> Report:
    """Chạy mọi kiểm tra cấu trúc rồi kiểm ngưỡng trên `coverage.json`, trả `Report`."""
    report = Report()
    check_forbidden_files(root, report)
    check_forbidden_text(root, report)
    check_member_pyproject_tables(root, report)
    check_addopts_no_cov(root, report)
    check_test_files_location(root, report)
    check_missing_init(root, report)
    check_coverage_config(root, report)

    cov_path = root / COVERAGE_JSON if not COVERAGE_JSON.is_absolute() else COVERAGE_JSON
    if not cov_path.is_file():
        report.add("thiếu coverage.json", str(cov_path))
    else:
        data = json.loads(cov_path.read_text(encoding="utf-8"))
        branch = os.environ.get("VERIFY_BRANCH", "worker")
        changed = load_changed_files()
        check_thresholds(data, branch, changed, report)

    return report


def main() -> int:
    """Điểm vào dòng lệnh: in số đo và vi phạm, thoát 0 khi đạt, 1 khi hỏng."""
    report = run(REPO_ROOT)
    for line in report.numbers:
        print(f"  {line}")
    if report.ok:
        print("coverage_gate: đạt")
        return 0
    print("coverage_gate: hỏng")
    for f in report.findings:
        print(f"  - [{f.rule}] {f.detail}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
