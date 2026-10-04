"""NO-269: job `unit`/`integration`/`ml` chạy pytest song song (xdist) dưới `pytest-cov` như bước 5.

Chạy THẬT `job_test_group` của `tools/ci/job.sh` với `pytest` giả trên PATH (ghi lại đối số và
biến môi trường) — không chạy bộ test thật, không mạng.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
JOB_SH = REPO_ROOT / "tools" / "ci" / "job.sh"


def _run_group(tmp_path: Path, group: str, extra_env: dict[str, str] | None = None) -> tuple[int, list[str], str]:
    """Nguồn job.sh, gọi `job_test_group <group>` với `pytest`/`python` giả; trả (mã thoát, đối số
    của lần gọi `pytest`, biến `COVERAGE_FILE` thấy được). Xoá vết `trace-<group>.jsonl` mà job.sh
    tạo ở gốc repo (nó `cd "$REPO_ROOT"` khi được nguồn — NO-191)."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    out = tmp_path / "pytest-call"
    for name, body in {
        "pytest": f'printf "%s\n" "$@" > "{out}"\necho "COVERAGE_FILE=${{COVERAGE_FILE:-}}" >> "{out}"',
        "python": "exit 0",
    }.items():
        cmd = bin_dir / name
        cmd.write_text(f"#!/usr/bin/env bash\n{body}\n", encoding="utf-8")
        cmd.chmod(0o755)
    script = tmp_path / "run.sh"
    script.write_text(f'source "{JOB_SH}"\njob_test_group {group}\nexit "$FAILED"\n', encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env.pop("CI_PYTEST_WORKERS", None)
    env.update(extra_env or {})
    trace = REPO_ROOT / f"trace-{group}.jsonl"
    try:
        result = subprocess.run(  # noqa: S603 — script cục bộ dựng trong tmp_path
            ["bash", str(script)],  # noqa: S607 — `bash` có sẵn trên PATH của runner
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        trace.unlink(missing_ok=True)
    lines = out.read_text(encoding="utf-8").splitlines() if out.exists() else []
    return result.returncode, lines[:-1], lines[-1] if lines else ""


@pytest.mark.parametrize("group", ["unit", "integration", "ml"])
def test_job_test_group__runs_pytest_with_xdist_and_cov(tmp_path: Path, group: str) -> None:
    """Mỗi nhóm: `pytest -n <N> --dist loadfile --cov --cov-report= --ci-split=<nhóm>` (đúng như bước
    5), không `coverage run`; `COVERAGE_FILE=.coverage.<nhóm>` để pytest-cov gộp vào đúng file mà
    ci.yml tải lên (`.coverage.*`) và `coverage combine artifacts/*/` đọc."""
    code, args, cov_env = _run_group(tmp_path, group)
    assert code == 0
    assert args[0] == "-n"
    assert args[1].isdigit()
    assert int(args[1]) >= 2
    assert args[2:6] == ["--dist", "loadfile", "--cov", "--cov-report="]
    assert f"--ci-split={group}" in args
    assert f"--junitxml=junit-{group}.xml" in args
    assert cov_env == f"COVERAGE_FILE=.coverage.{group}"


def test_job_test_group__workers_env_overrides_and_bad_value_falls_back(tmp_path: Path) -> None:
    """`CI_PYTEST_WORKERS` đổi số tiến trình; giá trị rỗng/lạ → mặc định (không truyền cho xdist)."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, args, _ = _run_group(tmp_path / "a", "unit", {"CI_PYTEST_WORKERS": "4"})
    assert args[1] == "4"
    _, args, _ = _run_group(tmp_path / "b", "unit", {"CI_PYTEST_WORKERS": "abc"})
    assert args[1].isdigit()
    assert int(args[1]) >= 2


def test_job_test_group__ml_uses_fewer_workers_than_unit(tmp_path: Path) -> None:
    """Nhóm `ml` nặng RAM (torch) → ít tiến trình hơn nhóm khác trên runner 4 vCPU / 16 GB."""
    (tmp_path / "u").mkdir()
    (tmp_path / "m").mkdir()
    _, unit_args, _ = _run_group(tmp_path / "u", "unit")
    _, ml_args, _ = _run_group(tmp_path / "m", "ml")
    assert int(ml_args[1]) < int(unit_args[1])
