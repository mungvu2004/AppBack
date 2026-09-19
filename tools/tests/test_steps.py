"""tools/verify/steps.py — [8]: gating theo file điều kiện, "chưa chạy" sau bước hỏng, VERIFY_NAME."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tools.lint_migrations import MERGE_REVISION_RE
from tools.verify.steps import (
    STATUS_FAIL,
    STATUS_NA,
    STATUS_OK,
    STATUS_SKIP,
    StepOutcome,
    _gate_status,
    normalize_verify_name,
    perf_case_named,
    run_steps,
)


def test_verify_name_chuẩn_hoá() -> None:
    assert normalize_verify_name("Orca Worker #7") == "orca-worker--7"
    assert normalize_verify_name("B0-01_worktree") == "b0-01_worktree"


def test_gate_status_thiếu_file_chưa_hợp_nhất_là_không_áp_dụng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tools.verify.steps as steps_mod

    monkeypatch.setattr(steps_mod, "REPO_ROOT", tmp_path)
    status = _gate_status(tmp_path / "khong-co.py", "B0-03")
    assert status == STATUS_NA


def test_gate_status_thiếu_file_đã_hợp_nhất_là_hỏng(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "changes").mkdir()
    (tmp_path / "changes" / "B0-03.md").write_text("x", encoding="utf-8")
    import tools.verify.steps as steps_mod

    monkeypatch.setattr(steps_mod, "REPO_ROOT", tmp_path)
    status = _gate_status(tmp_path / "khong-co.py", "B0-03")
    assert status == STATUS_FAIL


def test_gate_status_có_file_chạy_thật(tmp_path: Path) -> None:
    f = tmp_path / "co.py"
    f.write_text("", encoding="utf-8")
    assert _gate_status(f, "B0-03") is None


def test_merge_name_pattern() -> None:
    assert MERGE_REVISION_RE.match("r20260918_merge_w08_1")
    assert MERGE_REVISION_RE.match("r20260918_merge_w08_2")
    assert not MERGE_REVISION_RE.match("r20260918_merge_w08")
    assert not MERGE_REVISION_RE.match("r20260918_merge_w08_0")


def test_chưa_chạy_sau_bước_hỏng() -> None:
    steps = [
        ("1", lambda: StepOutcome("1", "a", STATUS_OK)),
        ("2", lambda: StepOutcome("2", "b", STATUS_FAIL)),
        ("3", lambda: StepOutcome("3", "c", STATUS_OK)),
    ]
    outcomes = run_steps(steps, wanted=None)
    assert [o.status for o in outcomes] == [STATUS_OK, STATUS_FAIL, STATUS_SKIP]


def test_không_áp_dụng_không_chặn_bước_sau() -> None:
    steps = [
        ("6", lambda: StepOutcome("6", "a", STATUS_NA)),
        ("7", lambda: StepOutcome("7", "b", STATUS_OK)),
    ]
    outcomes = run_steps(steps, wanted=None)
    assert [o.status for o in outcomes] == [STATUS_NA, STATUS_OK]


def test_steps_lọc_theo_wanted() -> None:
    calls: list[str] = []

    def make(n: str) -> Callable[[], StepOutcome]:
        def _fn() -> StepOutcome:
            calls.append(n)
            return StepOutcome(n, n, STATUS_OK)

        return _fn

    steps = [(n, make(n)) for n in ("1", "2", "4")]
    run_steps(steps, wanted={"1", "4"})
    assert calls == ["1", "4"]


def test_perf_mang_tên_case_hỏng() -> None:
    ids = [
        "packages/vision/tests/test_speed.py::test_resize_speed",
        "apps/api/x/tests/test_y.py::test_x_create__C04",
        "apps/api/x/tests/test_y.py::test_x_create__C09b[a]",
    ]
    assert perf_case_named(ids) == ids[1:]


def test_perf_tên_thường_đạt() -> None:
    assert perf_case_named(["packages/vision/tests/test_speed.py::test_resize__under_2s"]) == []
