"""Điều phối 8 bước cổng verify TRONG container — BE-00 §12, B0-01 [6]C.

Chạy bằng `exec uv run python -m tools.verify.steps <việc> [...]` từ
`tools/verify/in_container.sh`, cwd đã là `/tmp/w` (bản chép của `/src`).
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.charter import merged_prompts
from tools.coverage_gate import unit_of
from tools.lint_migrations import MERGE_REVISION_RE, revision_of
from tools.lint_migrations import main as lint_migrations_main

REPO_ROOT = Path.cwd()
OUT_DIR = Path(os.environ.get("VERIFY_OUT_DIR", "/src-out"))
WORK_DIR = Path(os.environ.get("VERIFY_WORK_DIR", "/work"))

STATUS_OK = "đạt"
STATUS_FAIL = "hỏng"
STATUS_SKIP = "chưa chạy"
STATUS_NA = "không áp dụng"

_NAME_UNSAFE_RE = re.compile(r"[^a-z0-9_-]")


def normalize_verify_name(name: str) -> str:
    """Cùng thuật toán chuẩn hoá `VERIFY_NAME` của `tools/verify/run.sh` (`[a-z0-9_-]`)."""
    return _NAME_UNSAFE_RE.sub("-", name.lower())


@dataclass
class StepOutcome:
    number: str
    name: str
    status: str
    detail: str = ""


def _run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess[str]:
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=REPO_ROOT, text=True, **kw)


def _touched_units() -> set[str]:
    changed = [line.strip() for line in os.environ.get("VERIFY_CHANGED", "").splitlines() if line.strip()]
    return {u for u in (unit_of(c) for c in changed) if u is not None}


def _gate_status(condition_file: Path, owner: str) -> str | None:
    """None = chạy thật; STATUS_NA / STATUS_FAIL = kết quả cố định (BE-01 [6]C)."""
    if condition_file.is_file():
        return None
    if owner in merged_prompts(REPO_ROOT):
        return STATUS_FAIL
    return STATUS_NA


def _print_table(outcomes: list[StepOutcome]) -> None:
    print()
    print(f"{'#':>3} | {'Bước':<28} | {'Trạng thái':<14} | Chi tiết")
    print("-" * 90)
    for o in outcomes:
        print(f"{o.number:>3} | {o.name:<28} | {o.status:<14} | {o.detail}")
    print()


# ---------------------------------------------------------------------------
# 8 bước
# ---------------------------------------------------------------------------


def step_ruff_format() -> StepOutcome:
    r = _run(["ruff", "format", "--check", "."])
    return StepOutcome("1", "ruff format --check", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


def step_ruff_check() -> StepOutcome:
    r = _run(["ruff", "check", "."])
    return StepOutcome("2", "ruff check", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


def step_mypy() -> StepOutcome:
    r = _run(["mypy"])
    return StepOutcome("3", "mypy --strict", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


def step_lint_imports() -> StepOutcome:
    r = _run(["lint-imports"])
    return StepOutcome("4", "lint-imports", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


def step_coverage() -> StepOutcome:
    steps = [
        ["coverage", "run", "-m", "pytest"],
        ["coverage", "combine"],
        ["coverage", "json"],
    ]
    for cmd in steps:
        r = _run(cmd)
        if r.returncode != 0:
            return StepOutcome("5", "coverage run -m pytest", STATUS_FAIL, "pytest hoặc coverage hỏng")
    r = _run([sys.executable, "-m", "tools.coverage_gate"])
    return StepOutcome("5", "coverage run -m pytest → coverage_gate", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


_PERF_EXPR = "perf and not gpu"
_CASE_IN_NAME_RE = re.compile(r"__[A-Z]\d{2}[a-z]?(?:_|\[|$)")


def perf_case_named(node_ids: list[str]) -> list[str]:
    """Test `perf` mang tên case (`__<caseid>`) → hỏng: case phải tính ở bước 5, dưới coverage."""
    return [n for n in node_ids if _CASE_IN_NAME_RE.search(n.rsplit("::", 1)[-1])]


def _collect_perf(paths: list[str]) -> list[str]:
    # --junitxml riêng: addopts ghi /tmp/junit.xml, collect-only không được đè junit của bước 5
    r = _run(
        ["pytest", "--collect-only", "-q", "-m", _PERF_EXPR, "--junitxml=/tmp/junit-collect.xml", *paths],
        capture_output=True,
    )
    return [line.strip() for line in r.stdout.splitlines() if "::" in line]


def step_perf() -> StepOutcome:
    name = "pytest -m perf → case_gate"
    integration = os.environ.get("VERIFY_BRANCH") == "integration"
    # integration: mọi testpaths (paths rỗng); worker: chỉ đơn vị bị chạm
    paths = [] if integration else [u for u in sorted(_touched_units()) if (REPO_ROOT / u).is_dir()]
    perf_ids = _collect_perf(paths) if integration or paths else []

    bad = perf_case_named(perf_ids)
    if bad:
        return StepOutcome("5b", name, STATUS_FAIL, f"test perf mang tên case: {', '.join(bad)}")

    detail = f"perf: {len(perf_ids)} test"
    if perf_ids:
        r = _run(["pytest", "-m", _PERF_EXPR, "--junitxml=/tmp/junit-perf.xml", *paths])
        if r.returncode != 0:
            return StepOutcome("5b", name, STATUS_FAIL, "test perf hỏng")
    elif not integration:
        detail = "perf: 0 đơn vị bị chạm"

    r = _run([sys.executable, "-m", "tools.case_gate"])
    return StepOutcome("5b", name, STATUS_OK if r.returncode == 0 else STATUS_FAIL, detail)


def step_migrations() -> StepOutcome:
    gated = _gate_status(REPO_ROOT / "packages" / "db" / "migrate_check.py", "B0-03")
    if gated is not None:
        return StepOutcome("6", "lint_migrations → migrate_check", gated)
    r1 = _run([sys.executable, "-m", "tools.lint_migrations"])
    if r1.returncode != 0:
        return StepOutcome("6", "lint_migrations → migrate_check", STATUS_FAIL, "lint_migrations hỏng")
    r2 = _run([sys.executable, "-m", "packages.db.migrate_check"])
    return StepOutcome("6", "lint_migrations → migrate_check", STATUS_OK if r2.returncode == 0 else STATUS_FAIL)


def step_contract() -> StepOutcome:
    gated = _gate_status(REPO_ROOT / "tools" / "contract" / "check.py", "B0-07")
    if gated is not None:
        return StepOutcome("7", "H1 H3 H4 H5 (tools.contract.check)", gated)
    r = _run([sys.executable, "-m", "tools.contract.check"])
    return StepOutcome("7", "H1 H3 H4 H5 (tools.contract.check)", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


def step_openapi() -> StepOutcome:
    gated = _gate_status(REPO_ROOT / "apps" / "api" / "core" / "openapi.py", "B0-06")
    if gated is not None:
        return StepOutcome("8", "openapi", gated)
    cmd = [sys.executable, "-m", "apps.api.core.openapi", "--out", "/tmp/openapi.json"]
    if os.environ.get("VERIFY_BRANCH") == "integration":
        cmd += ["--compare", "openapi.json"]
    r = _run(cmd)
    return StepOutcome("8", "openapi", STATUS_OK if r.returncode == 0 else STATUS_FAIL)


# Tên hiển thị cho dòng "chưa chạy" (bước chưa được gọi thì không có StepOutcome riêng)
_STEP_LABELS = {
    "1": "ruff format --check",
    "2": "ruff check",
    "3": "mypy --strict",
    "4": "lint-imports",
    "5": "coverage run -m pytest → coverage_gate",
    "5b": "pytest -m perf → case_gate",
    "6": "lint_migrations → migrate_check",
    "7": "H1 H3 H4 H5 (tools.contract.check)",
    "8": "openapi",
}

_ALL_STEPS = [
    ("1", step_ruff_format),
    ("2", step_ruff_check),
    ("3", step_mypy),
    ("4", step_lint_imports),
    ("5", step_coverage),
    ("5b", step_perf),
    ("6", step_migrations),
    ("7", step_contract),
    ("8", step_openapi),
]


def run_steps(steps: Sequence[tuple[str, Callable[[], StepOutcome]]], wanted: set[str] | None) -> list[StepOutcome]:
    """Chạy tuần tự, dừng ở bước hỏng đầu — bước sau ghi 'chưa chạy'. Thuần, dễ test."""
    outcomes: list[StepOutcome] = []
    failed = False
    for number, fn in steps:
        if wanted is not None and number not in wanted:
            continue
        if failed:
            outcomes.append(StepOutcome(number, _STEP_LABELS.get(number, number), STATUS_SKIP))
            continue
        outcome = fn()
        outcomes.append(outcome)
        if outcome.status == STATUS_FAIL:
            failed = True
    return outcomes


def cmd_verify(args: argparse.Namespace) -> int:
    wanted = set(args.steps.split(",")) if args.steps else None
    outcomes = run_steps(_ALL_STEPS, wanted)
    # Chép cả khi có bước hỏng: lúc đỏ là lúc người điều phối cần xem mẫu nhất.
    export_contract_samples()
    _print_table(outcomes)
    return 1 if any(o.status == STATUS_FAIL for o in outcomes) else 0


# ---------------------------------------------------------------------------
# Việc khác — [2]
# ---------------------------------------------------------------------------


def _clean_dir(d: Path) -> Path:
    """Thư mục ra của một việc: xoá sạch nội dung trước khi ghi ([6]C).

    `run.sh` bind-mount thư mục host **đúng vào** `/src-out/<việc>` (`lock`, `openapi`,
    `merge-heads`, `contract-samples`), mà mount point thì không gỡ được (EBUSY, NO-001).
    Vì vậy chỉ xoá **từng mục con**, giữ chính `d`, và để lỗi xoá nổi lên: sót một file
    cũ là `merge-heads` chép nhầm revision cũ ra ngoài (NO-008).
    """
    d.mkdir(parents=True, exist_ok=True)
    for child in d.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    return d


def export_contract_samples() -> None:
    """Chép mẫu golden của lượt ra `/src-out/contract-samples` (ENV §2, NO-043).

    Không đặt `CONTRACT_SAMPLES_DIR` (chạy ngoài cổng) → không làm gì. Đặt mà chưa test nào
    ghi mẫu → thư mục ra rỗng, để không còn mẫu của lượt trước làm người đọc nhầm.
    """
    source = os.environ.get("CONTRACT_SAMPLES_DIR")
    if not source:
        return
    dest = _clean_dir(OUT_DIR / "contract-samples")
    if Path(source).is_dir():
        shutil.copytree(source, dest, dirs_exist_ok=True)


def cmd_lock(_args: argparse.Namespace) -> int:
    # in_container.sh đã chạy `uv lock` (không --upgrade) rồi `uv sync --locked`.
    dest = _clean_dir(OUT_DIR / "lock")
    shutil.copy2(REPO_ROOT / "uv.lock", dest / "uv.lock")
    print(f"đã ghi {dest / 'uv.lock'}")
    return 0


def cmd_openapi(_args: argparse.Namespace) -> int:
    if not (REPO_ROOT / "apps" / "api" / "core" / "openapi.py").is_file():
        print("openapi: thiếu apps/api/core/openapi.py — chủ B0-06 chưa hợp nhất", file=sys.stderr)
        return 1
    dest = _clean_dir(OUT_DIR / "openapi")
    return _run([sys.executable, "-m", "apps.api.core.openapi", "--out", str(dest / "openapi.json")]).returncode


def _alembic_heads(alembic_ini: Path) -> list[str]:
    r = _run(["alembic", "-c", str(alembic_ini), "heads"], capture_output=True)
    return [line.split()[0] for line in r.stdout.splitlines() if line.strip()]


def cmd_merge_heads(args: argparse.Namespace) -> int:
    name: str = args.name
    if not MERGE_REVISION_RE.match(name):
        print(f"merge-heads: '{name}' sai mẫu r<yyyymmdd>_merge_w<nn>_<k>", file=sys.stderr)
        return 1

    alembic_ini = REPO_ROOT / "packages" / "db" / "alembic.ini"
    if not alembic_ini.is_file():
        print("merge-heads: thiếu packages/db/alembic.ini — chủ B0-03 chưa hợp nhất", file=sys.stderr)
        return 1

    versions_dir = REPO_ROOT / "packages" / "db" / "migrations" / "versions"
    before = sorted(versions_dir.glob("*.py")) if versions_dir.is_dir() else []
    if name in {revision_of(p) for p in before}:
        print(f"merge-heads: '{name}' đã là revision có sẵn", file=sys.stderr)
        return 1

    heads = _alembic_heads(alembic_ini)
    if len(heads) < 2:
        print(f"merge-heads: chỉ {len(heads)} head, cần ≥ 2", file=sys.stderr)
        return 1

    if _run(["alembic", "-c", str(alembic_ini), "merge", "heads", "--rev-id", name]).returncode != 0:
        return 1
    after_heads = _alembic_heads(alembic_ini)
    if after_heads != [name]:
        print(f"merge-heads: sau merge còn {after_heads}, cần đúng [{name}]", file=sys.stderr)
        return 1
    if lint_migrations_main([str(versions_dir)]) != 0:
        print("merge-heads: lint_migrations hỏng sau khi merge", file=sys.stderr)
        return 1

    dest = _clean_dir(OUT_DIR / "merge-heads")
    new_files = [p for p in versions_dir.glob("*.py") if p not in before]
    for p in new_files:
        shutil.copy2(p, dest / p.name)
    print(f"merge-heads: {len(new_files)} file mới -> {dest}")
    return 0


def cmd_shell(_args: argparse.Namespace) -> int:
    os.execvp("bash", ["bash"])


def cmd_gc(_args: argparse.Namespace) -> int:
    """Xoá venv-*/mypy-* của worktree không còn tồn tại (run.sh truyền danh sách còn sống)."""
    valid = {n for n in os.environ.get("VERIFY_VALID_NAMES", "").split(",") if n}
    removed = []
    for d in sorted([*WORK_DIR.glob("venv-*"), *WORK_DIR.glob("mypy-*")]):
        if d.name.split("-", 1)[1] not in valid:
            shutil.rmtree(d, ignore_errors=True)
            removed.append(d.name)
    print(f"gc: xoá {len(removed)} thư mục: {removed}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tools.verify.steps")
    sub = parser.add_subparsers(dest="task", required=True)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--steps", default=None)
    p_verify.set_defaults(fn=cmd_verify)

    sub.add_parser("lock").set_defaults(fn=cmd_lock)
    sub.add_parser("openapi").set_defaults(fn=cmd_openapi)

    p_merge = sub.add_parser("merge-heads")
    p_merge.add_argument("name")
    p_merge.set_defaults(fn=cmd_merge_heads)

    sub.add_parser("shell").set_defaults(fn=cmd_shell)
    sub.add_parser("gc").set_defaults(fn=cmd_gc)

    args = parser.parse_args(argv)
    rc: int = args.fn(args)
    return rc


if __name__ == "__main__":
    sys.exit(main())
