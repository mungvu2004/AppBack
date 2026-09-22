"""tools/verify/steps.py — 8 bước và các việc lock/openapi/merge-heads/gc/shell.

Lệnh con (ruff, mypy, pytest…) được thay bằng bộ ghi khi chỉ kiểm logic điều
phối; openapi (module giả) và merge-heads (alembic thật trên thư mục tạm) chạy
tiến trình thật.
"""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import pytest

from tools.contract import runner_client
from tools.contract.runner_client import RunnerError
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
    # Lượt cổng thật (bước 5) đặt biến này: test không được ghi vào log thật của lượt đang chạy nó
    monkeypatch.delenv("VERIFY_LOG_FILE", raising=False)
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


def test_lock_thư_mục_ra_là_mount_point_không_gỡ_được(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-001: `run.sh` mount host vào đúng `/src-out/lock`.

    `rmtree` xoá nội dung nhưng để lại chính mount point (EBUSY bị nuốt) — dựng
    lại đúng hành vi đó để chắc `_clean_dir` không ném `FileExistsError`.
    """

    def rmtree_giữ_gốc(path: Path | str, **_kw: Any) -> None:
        for child in Path(path).iterdir():
            child.unlink()

    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    out = steps.OUT_DIR / "lock"
    out.mkdir(parents=True)
    (out / "cũ.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(shutil, "rmtree", rmtree_giữ_gốc)

    assert steps.main(["lock"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["uv.lock"]


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


# --- FIX-006, FIX-008 ----------------------------------------------------------------


def test_clean_dir_không_nuốt_lỗi_xoá_mục_con(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-008: mục con không xoá được thì `_clean_dir` ném, không để file cũ sót lại im lặng.

    Sót lại là `merge-heads` chép nhầm revision cũ ra ngoài. Container chạy bằng root nên
    quyền tệp không chặn được xoá; dựng lỗi bằng cách cho `os.unlink` từ chối đúng một file.
    """
    out = steps.OUT_DIR / "merge-heads"
    out.mkdir(parents=True)
    (out / "cũ.py").write_text("x", encoding="utf-8")
    real_unlink = os.unlink

    def unlink_bị_khoá(path: Any, *args: Any, **kwargs: Any) -> None:
        """`os.unlink` từ chối riêng `cũ.py`, như file đang bị giữ."""
        if Path(path).name == "cũ.py":
            raise PermissionError(13, "bị khoá", str(path))
        real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", unlink_bị_khoá)
    with pytest.raises(PermissionError, match="bị khoá"):
        steps._clean_dir(out)


def test_clean_dir_xoá_cả_thư_mục_con_giữ_gốc(repo: Path) -> None:
    """Thư mục con cũng bị xoá; chính thư mục ra (có thể là mount point, NO-001) được giữ."""
    out = steps.OUT_DIR / "lock"
    (out / "con" / "cháu").mkdir(parents=True)
    (out / "con" / "cháu" / "a.txt").write_text("x", encoding="utf-8")
    (out / "b.txt").write_text("x", encoding="utf-8")
    assert steps._clean_dir(out) == out
    assert out.is_dir()
    assert list(out.iterdir()) == []


def _fail_one_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """Một bước hỏng: việc chép mẫu vẫn phải chạy (người điều phối cần mẫu nhất khi đỏ)."""
    monkeypatch.setattr(steps, "_ALL_STEPS", [("7", lambda: steps.StepOutcome("7", "h", steps.STATUS_FAIL))])


def test_verify_chép_mẫu_golden_ra_thư_mục_ra(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NO-043, ENV §2: cuối lượt, `CONTRACT_SAMPLES_DIR` chép ra `/src-out/contract-samples`, mẫu cũ bị thay."""
    samples = tmp_path / "contract-samples"
    (samples / "op").mkdir(parents=True)
    (samples / "op" / "C01-1.json").write_text("{}", encoding="utf-8")
    out = steps.OUT_DIR / "contract-samples"
    out.mkdir(parents=True)
    (out / "cũ.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CONTRACT_SAMPLES_DIR", str(samples))
    _fail_one_step(monkeypatch)
    assert steps.main(["verify"]) == 1
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["op/C01-1.json"]


def test_verify_không_có_mẫu_thì_thư_mục_ra_rỗng(repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lượt không test nào ghi mẫu (thư mục chưa tạo) → thư mục ra rỗng, không còn mẫu của lượt trước."""
    out = steps.OUT_DIR / "contract-samples"
    out.mkdir(parents=True)
    (out / "cũ.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CONTRACT_SAMPLES_DIR", str(tmp_path / "chua-co"))
    _fail_one_step(monkeypatch)
    assert steps.main(["verify"]) == 1
    assert list(out.iterdir()) == []


def _table_rows(out: str) -> dict[str, str]:
    """Dòng bảng cổng theo cột `#` (một dòng mỗi bước)."""
    return {line.split("|")[0].strip(): line for line in out.splitlines() if " | " in line}


def test_verify_chép_mẫu_hỏng_vẫn_in_đủ_bảng_và_thoát_1(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """NO-075: thư mục ra không ghi được → bảng vẫn in đủ, thêm một dòng lỗi chép mẫu, thoát 1 — không traceback.

    Container chạy bằng root nên quyền tệp không chặn được ghi; dựng lỗi bằng thư mục ra nằm dưới một file
    (`NotADirectoryError`), cùng họ `OSError` với probe `VERIFY_OUT_DIR=/proc/rv` của review.
    """
    blocker = tmp_path / "là-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(steps, "OUT_DIR", blocker / "out")
    monkeypatch.setenv("CONTRACT_SAMPLES_DIR", str(tmp_path / "contract-samples"))
    monkeypatch.setattr(steps, "_ALL_STEPS", [("1", lambda: steps.StepOutcome("1", "a", steps.STATUS_OK))])
    assert steps.main(["verify"]) == 1
    captured = capsys.readouterr()
    rows = _table_rows(captured.out)
    assert steps.STATUS_OK in rows["1"]
    assert "chép mẫu golden" in rows["—"]
    assert steps.STATUS_FAIL in rows["—"]
    assert "Not a directory" in rows["—"]
    assert "chép mẫu golden hỏng" in captured.err


def test_verify_ngoài_container_không_chép(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Không đặt `CONTRACT_SAMPLES_DIR` (chạy ngoài cổng) → không tạo gì dưới thư mục ra."""
    monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)
    _fail_one_step(monkeypatch)
    assert steps.main(["verify"]) == 1
    assert not (steps.OUT_DIR / "contract-samples").exists()


# --- log cổng ra thư mục host (NO-080) ---------------------------------------------


def _printing_step(number: str, status: str) -> tuple[str, Callable[[], steps.StepOutcome]]:
    """Bước giả in qua một tiến trình con thật (`steps._run`, như pytest hay `coverage_gate`): ghi thẳng fd 1, 2."""

    def fn() -> steps.StepOutcome:
        code = f"import sys; print('tóm tắt pytest {number}'); print('cảnh báo {number}', file=sys.stderr)"
        assert steps._run([sys.executable, "-c", code]).returncode == 0
        return steps.StepOutcome(number, f"bước {number}", status)

    return number, fn


@pytest.fixture
def log_file(repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`VERIFY_LOG_FILE` như `run.sh` đặt: một file dưới thư mục ra, thư mục cha chưa có."""
    path = steps.OUT_DIR / "verify" / "20260922T000000Z-lượt.log"
    monkeypatch.setenv("VERIFY_LOG_FILE", str(path))
    monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)
    return path


def test_verify_ghi_cả_output_của_lượt_ra_file_log(
    log_file: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """NO-080: file log có output của tiến trình con, bảng cổng và mã thoát; stdout/stderr vẫn như cũ, vẫn tách."""
    monkeypatch.setattr(
        steps, "_ALL_STEPS", [_printing_step("1", steps.STATUS_OK), _printing_step("2", steps.STATUS_FAIL)]
    )
    assert steps.main(["verify"]) == 1
    captured = capfd.readouterr()
    text = log_file.read_text(encoding="utf-8")
    for needle in ("tóm tắt pytest 1", "cảnh báo 2", "Trạng thái", "mã thoát: 1"):
        assert needle in text
    rows = _table_rows(text)
    assert rows == _table_rows(captured.out)
    assert (steps.STATUS_OK in rows["1"], steps.STATUS_FAIL in rows["2"]) == (True, True)
    assert "tóm tắt pytest 2" in captured.out.splitlines()
    assert "cảnh báo 2" in captured.err.splitlines()
    assert "cảnh báo 2" not in captured.out.splitlines()


def test_verify_log_nối_thêm_không_đè_lượt_trước(log_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cùng tên file (hai lượt trong một giây) → nối tiếp, lượt trước không mất."""
    monkeypatch.setattr(steps, "_ALL_STEPS", [_printing_step("1", steps.STATUS_OK)])
    assert steps.main(["verify"]) == 0
    assert steps.main(["verify"]) == 0
    assert log_file.read_text(encoding="utf-8").count("mã thoát: 0") == 2


def _no_step() -> steps.StepOutcome:
    raise AssertionError("không được chạy bước nào khi chưa mở được log")


def test_verify_log_không_mở_được_thì_hỏng_trước_bước_đầu(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thư mục log không tạo được (thiếu mount, đường nằm dưới một file) → `OSError` trước khi chạy bước nào."""
    blocker = tmp_path / "là-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("VERIFY_LOG_FILE", str(blocker / "verify" / "lượt.log"))
    monkeypatch.setattr(steps, "_ALL_STEPS", [("1", _no_step)])
    with pytest.raises(NotADirectoryError):
        steps.main(["verify"])


def test_verify_tiến_trình_con_mồ_côi_không_treo_cổng(
    log_file: Path, monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    """Tiến trình con còn giữ fd 1 sau lượt → bỏ đợi sau `LOG_DRAIN_TIMEOUT_S`, báo stderr; log đủ, mã thoát giữ."""
    orphans: list[subprocess.Popen[bytes]] = []

    def step() -> steps.StepOutcome:
        orphans.append(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]))
        return steps.StepOutcome("1", "a", steps.STATUS_OK)

    monkeypatch.setattr(steps, "LOG_DRAIN_TIMEOUT_S", 0.2)
    monkeypatch.setattr(steps, "_ALL_STEPS", [("1", step)])
    try:
        assert steps.main(["verify"]) == 0
    finally:
        for orphan in orphans:
            orphan.kill()
            orphan.wait()
    assert "mã thoát: 0" in log_file.read_text(encoding="utf-8")
    assert "tiến trình con còn giữ fd 1" in capfd.readouterr().err


def test_write_each_bỏ_đích_hỏng_giữ_đích_còn_lại() -> None:
    """Đĩa log đầy giữa lượt → bỏ riêng đích đó, stdout vẫn nhận đủ; luồng chép không chết (ống đầy là cổng treo)."""

    class DiskFull(io.BytesIO):
        """Đích ghi luôn báo đĩa đầy."""

        def write(self, _b: Any) -> int:
            raise OSError(28, "No space left on device")

    full, good = DiskFull(), io.BytesIO()
    sinks: list[BinaryIO] = [full, good]
    problems: list[str] = []
    steps._write_each(sinks, b"a", problems)
    steps._write_each(sinks, b"b", problems)
    assert (good.getvalue(), sinks) == (b"ab", [good])
    assert len(problems) == 1
    assert "No space left" in problems[0]


# --- làm ấm runner Node (NO-048) ----------------------------------------------------


def _warm(fake: FakeRun, error: Exception | None = None) -> Callable[[Path], Path]:
    """Thay `ensure_node_modules`: ghi lượt gọi vào cùng sổ lệnh của `fake` để so thứ tự với bước 5.

    Chỉ nhận đúng một đối số vị trí: gọi kèm `cache_dir`/`package_dir` (lệch kho npm hay băm lock
    của fixture `contract_build`) thì `TypeError`.
    """

    def ensure(node_dir: Path) -> Path:
        fake.calls.append(["ensure_node_modules", str(node_dir)])
        if error is not None:
            raise error
        return node_dir / "băm-lock"

    return ensure


@pytest.mark.parametrize("argv", [[], ["--steps", "5"], ["--steps", "7"], ["--steps", "1,5b,7"]])
def test_verify_làm_ấm_node_modules_trước_bước_5(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    """NO-048: `npm ci` lạnh chạy ở pha chuẩn bị, trên đúng thư mục của `contract_build`, trước mọi lệnh bước 5."""
    node_dir = tmp_path / "contract-node"
    monkeypatch.setenv("CONTRACT_NODE_DIR", str(node_dir))
    monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)
    fake = _fake(monkeypatch)
    monkeypatch.setattr(runner_client, "ensure_node_modules", _warm(fake))
    assert steps.main(["verify", *argv]) == 0
    assert fake.calls[0] == ["ensure_node_modules", str(runner_client.node_dir_from_env())]
    assert [c for c in fake.calls if c[0] == "ensure_node_modules"] == [fake.calls[0]]


@pytest.mark.parametrize("argv", [["--steps", "1,2,4"], ["--steps", "5b,6,8"]])
def test_verify_không_bước_cần_runner_thì_không_làm_ấm(
    repo: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    """`--steps` không gồm 5 hay 7 → không đụng `npm`, không đổi volume."""
    monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)
    fake = _fake(monkeypatch)
    monkeypatch.setattr(runner_client, "ensure_node_modules", _warm(fake))
    assert steps.main(["verify", *argv]) == 0
    assert not fake.ran("ensure_node_modules")


@pytest.mark.parametrize(
    "error",
    [
        RunnerError("npm thoát 1: getaddrinfo ENOTFOUND registry.npmjs.org\nnpm ERR! chi tiết"),
        PermissionError(13, "cấm"),
    ],
)
def test_verify_làm_ấm_hỏng_là_lỗi_hạ_tầng_của_cổng(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    """npm hay đĩa hỏng lúc làm ấm → cổng hỏng, bảng nêu lỗi; bước 5 không chạy (không để pytest tải mạng)."""
    monkeypatch.delenv("CONTRACT_SAMPLES_DIR", raising=False)
    fake = _fake(monkeypatch)
    monkeypatch.setattr(runner_client, "ensure_node_modules", _warm(fake, error))
    assert steps.main(["verify"]) == 1
    assert not fake.ran("coverage run")
    rows = _table_rows(capsys.readouterr().out)
    assert steps.STATUS_FAIL in rows["0"]
    assert str(error).splitlines()[0] in rows["0"]
    assert steps.STATUS_SKIP in rows["5"]
