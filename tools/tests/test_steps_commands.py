"""tools/verify/steps.py — 8 bước và các việc lock/openapi/merge-heads/gc/shell.

Lệnh con (ruff, mypy, pytest…) được thay bằng bộ ghi khi chỉ kiểm logic điều
phối; openapi (module giả) và merge-heads (alembic thật trên thư mục tạm) chạy
tiến trình thật.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from tools.verify import steps


@dataclass
class FakeRun:
    """Thay `steps._run`: ghi lệnh, trả mã thoát theo `rules` (khớp chuỗi con đầu tiên)."""

    rules: dict[str, tuple[int, str]] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    def __call__(self, cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append(cmd)
        joined = " ".join(cmd)
        for needle, (rc, stdout) in self.rules.items():
            if needle in joined:
                return subprocess.CompletedProcess(cmd, rc, stdout=stdout, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def ran(self, needle: str) -> bool:
        return any(needle in " ".join(c) for c in self.calls)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(steps, "REPO_ROOT", root)
    monkeypatch.setattr(steps, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(steps, "WORK_DIR", tmp_path / "work")
    monkeypatch.delenv("VERIFY_BRANCH", raising=False)
    monkeypatch.delenv("VERIFY_CHANGED", raising=False)
    # coverage `patch = subprocess` đo mọi tiến trình con qua biến này; tiến trình
    # con ở đây chạy trong repo giả (module openapi giả…) — không được lẫn vào số đo
    monkeypatch.delenv("COVERAGE_PROCESS_CONFIG", raising=False)
    return root


def _fake(monkeypatch: pytest.MonkeyPatch, **rules: tuple[int, str]) -> FakeRun:
    fake = FakeRun(rules={k.replace("__", " "): v for k, v in rules.items()})
    monkeypatch.setattr(steps, "_run", fake)
    return fake


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


# --- bước 1-4 -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fn", "number"),
    [
        (steps.step_ruff_format, "1"),
        (steps.step_ruff_check, "2"),
        (steps.step_mypy, "3"),
        (steps.step_lint_imports, "4"),
    ],
)
@pytest.mark.parametrize(("rc", "status"), [(0, steps.STATUS_OK), (1, steps.STATUS_FAIL)])
def test_bước_1_đến_4_theo_mã_thoát(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    fn: Callable[[], steps.StepOutcome],
    number: str,
    rc: int,
    status: str,
) -> None:
    monkeypatch.setattr(steps, "_run", FakeRun(rules={"": (rc, "")}))
    outcome = fn()
    assert (outcome.number, outcome.status) == (number, status)


# --- bước 5 -------------------------------------------------------------------------


def test_bước_5_đạt_gọi_đủ_chuỗi(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake(monkeypatch)
    assert steps.step_coverage().status == steps.STATUS_OK
    assert [c[:2] for c in fake.calls][:3] == [["coverage", "run"], ["coverage", "combine"], ["coverage", "json"]]
    assert fake.ran("tools.coverage_gate")


def test_bước_5_pytest_hỏng_không_gọi_gate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake(monkeypatch, coverage__run=(1, ""))
    assert steps.step_coverage().status == steps.STATUS_FAIL
    assert not fake.ran("tools.coverage_gate")


def test_bước_5_combine_hỏng_không_bị_nuốt(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # vd cấu hình [paths] sai: combine hỏng thì bước 5 hỏng, không lặng lẽ đi tiếp
    fake = _fake(monkeypatch, coverage__combine=(1, ""))
    assert steps.step_coverage().status == steps.STATUS_FAIL
    assert not fake.ran("coverage json")


def test_bước_5_gate_hỏng(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, **{"tools.coverage_gate": (1, "")})
    assert steps.step_coverage().status == steps.STATUS_FAIL


# --- bước 5b ------------------------------------------------------------------------


def test_5b_không_đơn_vị_bị_chạm_bỏ_pytest_perf(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake(monkeypatch)
    outcome = steps.step_perf()
    assert (outcome.status, outcome.detail) == (steps.STATUS_OK, "perf: 0 đơn vị bị chạm")
    assert not fake.ran("--collect-only")
    assert fake.ran("tools.case_gate")


def test_5b_đơn_vị_bị_chạm_có_perf_thì_chạy(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "packages" / "vision").mkdir(parents=True)
    monkeypatch.setenv("VERIFY_CHANGED", "packages/vision/x.py\ndocs/a.md")
    fake = _fake(monkeypatch, **{"--collect-only": (0, "packages/vision/tests/test_p.py::test_speed\n\n1 test\n")})
    outcome = steps.step_perf()
    assert (outcome.status, outcome.detail) == (steps.STATUS_OK, "perf: 1 test")
    perf_run = [c for c in fake.calls if "--junitxml=/tmp/junit-perf.xml" in c]
    assert perf_run == [["pytest", "-m", "perf and not gpu", "--junitxml=/tmp/junit-perf.xml", "packages/vision"]]


def test_5b_đơn_vị_bị_chạm_không_có_perf_thì_bỏ(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / "packages" / "vision").mkdir(parents=True)
    monkeypatch.setenv("VERIFY_CHANGED", "packages/vision/x.py")
    fake = _fake(monkeypatch, **{"--collect-only": (5, "no tests collected\n")})
    assert steps.step_perf().detail == "perf: 0 đơn vị bị chạm"
    assert not fake.ran("junit-perf")


def test_5b_integration_chạy_mọi_perf(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_BRANCH", "integration")
    fake = _fake(monkeypatch, **{"--collect-only": (0, "a/tests/test_p.py::test_speed\n")})
    assert steps.step_perf().status == steps.STATUS_OK
    collect = next(c for c in fake.calls if "--collect-only" in c)
    assert collect[-1] == "--junitxml=/tmp/junit-collect.xml"  # không giới hạn đường


def test_5b_perf_mang_tên_case_hỏng_trước_khi_chạy(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_BRANCH", "integration")
    fake = _fake(monkeypatch, **{"--collect-only": (0, "a/tests/test_p.py::test_x_create__C04\n")})
    outcome = steps.step_perf()
    assert outcome.status == steps.STATUS_FAIL
    assert "test_x_create__C04" in outcome.detail
    assert not fake.ran("tools.case_gate")


def test_5b_perf_hỏng(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_BRANCH", "integration")
    _fake(monkeypatch, **{"--collect-only": (0, "a/tests/test_p.py::test_speed\n"), "junit-perf": (1, "")})
    assert steps.step_perf().status == steps.STATUS_FAIL


def test_5b_case_gate_hỏng(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, **{"tools.case_gate": (1, "")})
    assert steps.step_perf().status == steps.STATUS_FAIL


# --- bước 6-8: file điều kiện -------------------------------------------------------


@pytest.mark.parametrize(
    ("fn", "cond", "owner"),
    [
        (steps.step_migrations, "packages/db/migrate_check.py", "B0-03"),
        (steps.step_contract, "tools/contract/check.py", "B0-07"),
        (steps.step_openapi, "apps/api/core/openapi.py", "B0-06"),
    ],
)
def test_bước_6_8_không_áp_dụng_rồi_hỏng_rồi_chạy(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    fn: Callable[[], steps.StepOutcome],
    cond: str,
    owner: str,
) -> None:
    fake = _fake(monkeypatch)
    assert fn().status == steps.STATUS_NA
    _touch(repo, f"changes/{owner}.md")
    assert fn().status == steps.STATUS_FAIL
    assert fake.calls == []
    _touch(repo, cond)
    assert fn().status == steps.STATUS_OK
    assert fake.calls


def test_bước_6_lint_hỏng_không_gọi_migrate_check(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(repo, "packages/db/migrate_check.py")
    fake = _fake(monkeypatch, **{"tools.lint_migrations": (1, "")})
    assert steps.step_migrations().status == steps.STATUS_FAIL
    assert not fake.ran("packages.db.migrate_check")


def test_bước_6_migrate_check_hỏng(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(repo, "packages/db/migrate_check.py")
    _fake(monkeypatch, **{"packages.db.migrate_check": (1, "")})
    assert steps.step_migrations().status == steps.STATUS_FAIL


def test_bước_7_hỏng_theo_mã_thoát(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(repo, "tools/contract/check.py")
    _fake(monkeypatch, **{"tools.contract.check": (1, "")})
    assert steps.step_contract().status == steps.STATUS_FAIL


def test_bước_8_integration_so_với_bản_commit(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(repo, "apps/api/core/openapi.py")
    monkeypatch.setenv("VERIFY_BRANCH", "integration")
    fake = _fake(monkeypatch)
    steps.step_openapi()
    assert fake.calls[0][-2:] == ["--compare", "openapi.json"]


def test_bước_8_worker_không_so(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _touch(repo, "apps/api/core/openapi.py")
    fake = _fake(monkeypatch, **{"apps.api.core.openapi": (1, "")})
    assert steps.step_openapi().status == steps.STATUS_FAIL
    assert "--compare" not in fake.calls[0]


# --- verify / main ------------------------------------------------------------------


def test_main_verify_in_bảng_và_mã_thoát(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        steps,
        "_ALL_STEPS",
        [
            ("1", lambda: steps.StepOutcome("1", "a", steps.STATUS_OK)),
            ("2", lambda: steps.StepOutcome("2", "b", steps.STATUS_FAIL)),
            ("3", lambda: steps.StepOutcome("3", "c", steps.STATUS_OK)),
        ],
    )
    assert steps.main(["verify"]) == 1
    out = capsys.readouterr().out
    assert "chưa chạy" in out
    assert steps.main(["verify", "--steps", "1"]) == 0


# --- lock / openapi -----------------------------------------------------------------


def test_lock_chép_uv_lock_xoá_file_cũ(repo: Path) -> None:
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    old = steps.OUT_DIR / "lock" / "cũ.txt"
    old.parent.mkdir(parents=True)
    old.write_text("x", encoding="utf-8")
    assert steps.main(["lock"]) == 0
    assert sorted(p.name for p in (steps.OUT_DIR / "lock").iterdir()) == ["uv.lock"]


def test_openapi_thiếu_module_nêu_b0_06(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert steps.main(["openapi"]) == 1
    assert "B0-06" in capsys.readouterr().err


def test_openapi_module_giả_ghi_đúng_file_xoá_file_cũ(repo: Path) -> None:
    for pkg in ("apps", "apps/api", "apps/api/core"):
        _touch(repo, f"{pkg}/__init__.py")
    (repo / "apps" / "api" / "core" / "openapi.py").write_text(
        "import sys\nfrom pathlib import Path\n"
        "Path(sys.argv[sys.argv.index('--out') + 1]).write_text('{\"openapi\": \"3.1.0\"}')\n",
        encoding="utf-8",
    )
    stale = steps.OUT_DIR / "openapi" / "cũ.json"
    stale.parent.mkdir(parents=True)
    stale.write_text("{}", encoding="utf-8")
    assert steps.main(["openapi"]) == 0
    out_dir = steps.OUT_DIR / "openapi"
    assert sorted(p.name for p in out_dir.iterdir()) == ["openapi.json"]
    assert (out_dir / "openapi.json").read_text(encoding="utf-8") == '{"openapi": "3.1.0"}'


# --- merge-heads --------------------------------------------------------------------

_ALEMBIC_INI = "[alembic]\nscript_location = %(here)s/migrations\n"
_MAKO = (
    '"""${message}"""\n'
    "revision = ${repr(up_revision)}\n"
    "down_revision = ${repr(down_revision)}\n"
    "branch_labels = None\n"
    "depends_on = None\n\n\n"
    "def upgrade() -> None:\n    pass\n\n\n"
    "def downgrade() -> None:\n    pass\n"
)


def _alembic_repo(root: Path, *revisions: tuple[str, str | None]) -> Path:
    db = root / "packages" / "db"
    versions = db / "migrations" / "versions"
    versions.mkdir(parents=True)
    (db / "alembic.ini").write_text(_ALEMBIC_INI, encoding="utf-8")
    (db / "migrations" / "script.py.mako").write_text(_MAKO, encoding="utf-8")
    for rev, down in revisions:
        (versions / f"{rev}_viec.py").write_text(
            f'revision = "{rev}"\ndown_revision = {down!r}\n\n\n'
            "def upgrade() -> None:\n    pass\n\n\n"
            "def downgrade() -> None:\n    pass\n",
            encoding="utf-8",
        )
    return versions


def _no_subprocess(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
    raise AssertionError(f"không được gọi {cmd} trước khi kiểm xong tên")


def test_merge_heads_sai_mẫu_hỏng_trước_alembic(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(steps, "_run", _no_subprocess)
    _alembic_repo(repo)
    assert steps.main(["merge-heads", "r20260919_merge_w00"]) == 1
    assert "sai mẫu" in capsys.readouterr().err


def test_merge_heads_thiếu_alembic_ini_nêu_b0_03(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert "B0-03" in capsys.readouterr().err


def test_merge_heads_trùng_revision_có_sẵn_hỏng_trước_alembic(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _alembic_repo(repo, ("r20260919_merge_w00_1", None))
    monkeypatch.setattr(steps, "_run", _no_subprocess)
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert "đã là revision" in capsys.readouterr().err


def test_merge_heads_một_head_hỏng(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _alembic_repo(repo, ("r20260919_b0_03", None))
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert "chỉ 1 head" in capsys.readouterr().err


def test_merge_heads_hai_head_ra_đúng_một_file(repo: Path) -> None:
    versions = _alembic_repo(repo, ("r20260919_b0_03", None), ("r20260919_b0_04", None))
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 0
    out = sorted((steps.OUT_DIR / "merge-heads").iterdir())
    assert len(out) == 1
    assert "r20260919_merge_w00_1" in out[0].read_text(encoding="utf-8")
    assert steps._alembic_heads(repo / "packages" / "db" / "alembic.ini") == ["r20260919_merge_w00_1"]
    assert (versions / out[0].name).is_file()


_TWO_HEADS = (0, "a (head)\nb (head)\n")


def test_merge_heads_alembic_merge_hỏng(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _alembic_repo(repo)
    fake = _fake(monkeypatch, **{"alembic.ini merge": (1, ""), "alembic.ini heads": _TWO_HEADS})
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert fake.calls[-1][-4:-2] == ["merge", "heads"]  # dừng ngay sau merge


def test_merge_heads_sau_merge_còn_hai_head_hỏng(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _alembic_repo(repo)
    _fake(monkeypatch, **{"alembic.ini heads": _TWO_HEADS})
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert "sau merge còn ['a', 'b']" in capsys.readouterr().err


def test_merge_heads_lint_hỏng_không_chép(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    versions = _alembic_repo(repo)
    heads = iter(["a (head)\nb (head)\n", "r20260919_merge_w00_1 (head)\n"])

    def run(cmd: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-1] == "heads":
            return subprocess.CompletedProcess(cmd, 0, stdout=next(heads), stderr="")
        (versions / "bad.py").write_text('revision = "r20260919_merge_w00_0"\n', encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(steps, "_run", run)
    assert steps.main(["merge-heads", "r20260919_merge_w00_1"]) == 1
    assert not (steps.OUT_DIR / "merge-heads").exists()


# --- gc / shell / _touched_units ----------------------------------------------------


def test_gc_xoá_thư_mục_của_worktree_đã_mất(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("venv-a", "venv-b", "mypy-a", "mypy-c", "uv-cache"):
        (steps.WORK_DIR / name).mkdir(parents=True)
    monkeypatch.setenv("VERIFY_VALID_NAMES", "a")
    assert steps.main(["gc"]) == 0
    assert sorted(p.name for p in steps.WORK_DIR.iterdir()) == ["mypy-a", "uv-cache", "venv-a"]


def test_shell_exec_bash(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(os, "execvp", lambda file, args: calls.append((file, args)))
    steps.cmd_shell(argparse.Namespace())
    assert calls == [("bash", ["bash"])]


def test_touched_units_từ_verify_changed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VERIFY_CHANGED", "packages/core/a.py\napps/api/auth/r.py\ndocs/x.md\n")
    assert steps._touched_units() == {"packages/core", "apps/api/auth"}


def test_run_thật_in_lệnh(capsys: pytest.CaptureFixture[str]) -> None:
    r = steps._run([sys.executable, "-c", "print('ok')"], capture_output=True)
    assert (r.returncode, r.stdout.strip()) == (0, "ok")
    assert capsys.readouterr().out.startswith("$ ")
