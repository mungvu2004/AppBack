"""Test cho `tools/ci/commits.py` (job `commits`, B0-09): repo git tạm, commit thật."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tools.ci import commits

_GIT_TIMEOUT = 30
_ZERO_SHA = "0" * 40


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Chạy `git` trong `repo`, thoát khác 0 thì ném lỗi ngay (test không nuốt lỗi thiết lập)."""
    return subprocess.run(  # noqa: S603 — "git" cố định, test tự dựng repo tạm
        ["git", "-C", str(repo), *args],  # noqa: S607 — thực thi "git" qua PATH, không phải input người dùng
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=True,
    )


def _commit(repo: Path, message: str, *, filename: str = "f.txt") -> str:
    """Sửa một file rồi tạo commit thật với `message`; trả SHA đầy đủ."""
    path = repo / filename
    path.write_text(f"{message}\n{path.read_text() if path.exists() else ''}", encoding="utf-8")
    _git(repo, "add", filename)
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "commit",
        "--no-verify",
        "-m",
        message,
    )
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Repo git tạm, không hook (`core.hooksPath` trỏ thư mục rỗng) để tạo được commit sai mẫu."""
    empty_hooks = tmp_path / "empty-hooks"
    empty_hooks.mkdir()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _git(repo_dir, "init", "-q", "-b", "main")
    _git(repo_dir, "config", "core.hooksPath", str(empty_hooks))
    return repo_dir


def _run_main(monkeypatch: pytest.MonkeyPatch, repo_dir: Path, **env: str) -> int:
    """Gọi `commits.main()` với cwd và biến môi trường của một ca, biến khác bị dọn sạch (fail-closed thật)."""
    for key in ("EVENT", "PR_TITLE", "HEAD_REF", "BASE_SHA", "HEAD_SHA"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(repo_dir)
    return commits.main()


def test_pull_request_all_valid_passes(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Case thường: tiêu đề PR, mọi commit, nhánh và trailer đều đúng mẫu → đạt."""
    base = _commit(repo, "chore(repo): init")
    _commit(repo, "feat(core): add ids\n\nPrompt: B0-02")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): add ids",
        HEAD_REF="feature/b0-02-core-ids",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 0


def test_pull_request_bad_title_fails(
    monkeypatch: pytest.MonkeyPatch, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tiêu đề PR sai Conventional Commits → hỏng."""
    base = _commit(repo, "chore(repo): init")
    head = _commit(repo, "feat(core): add ids\n\nPrompt: B0-02")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="B0-02: lõi",
        HEAD_REF="feature/b0-02-core-ids",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 1
    assert "B0-02: lõi" in capsys.readouterr().err


def test_bad_commit_between_good_ones_reported_alone(
    monkeypatch: pytest.MonkeyPatch, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Một commit sai giữa hai commit đúng → hỏng, in đúng dòng đó và chỉ dòng đó."""
    base = _commit(repo, "chore(repo): init")
    _commit(repo, "feat(core): step one\n\nPrompt: B0-02")
    _commit(repo, "update stuff")
    head = _commit(repo, "feat(core): step two\n\nPrompt: B0-02")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): finish",
        HEAD_REF="feature/b0-02-core-ids",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 1
    err = capsys.readouterr().err
    assert "update stuff" in err
    assert "step one" not in err
    assert "step two" not in err


def test_merge_commit_is_skipped(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Commit merge (nhiều cha) với thông điệp sai mẫu vẫn đạt vì bị bỏ qua khi kiểm dòng đầu."""
    base = _commit(repo, "chore(repo): init")
    _git(repo, "checkout", "-q", "-b", "feature/b0-02-core-ids")
    _commit(repo, "feat(core): add ids\n\nPrompt: B0-02")
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "chore(repo): main moves on", filename="g.txt")
    _git(repo, "checkout", "-q", "feature/b0-02-core-ids")
    _git(
        repo,
        "-c",
        "user.name=Test",
        "-c",
        "user.email=test@example.com",
        "merge",
        "--no-ff",
        "--no-verify",
        "-m",
        "bad merge message not conventional",
        "main",
    )
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): add ids",
        HEAD_REF="feature/b0-02-core-ids",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 0


@pytest.mark.parametrize(
    ("head_ref", "expect_pass"),
    [
        ("b0-02", False),
        ("mungvu2004/x", False),
        ("feature/b0-02-core-ids", True),
        ("dependabot/uv/x", True),
    ],
)
def test_branch_name_patterns(monkeypatch: pytest.MonkeyPatch, repo: Path, head_ref: str, expect_pass: bool) -> None:
    """Tên nhánh: kiểu hợp lệ đạt, tuỳ ý không đạt; `dependabot/**` luôn đạt (miễn cả trailer)."""
    base = _commit(repo, "chore(repo): init")
    head = _commit(repo, "feat(core): add ids\n\nPrompt: B0-02")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): add ids",
        HEAD_REF=head_ref,
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert (code == 0) is expect_pass


@pytest.mark.parametrize("trailer_line", [None, "Prompt: B0-03"])
def test_missing_or_wrong_trailer_fails(monkeypatch: pytest.MonkeyPatch, repo: Path, trailer_line: str | None) -> None:
    """Nhánh `feature/b0-02-…` thiếu trailer `Prompt: B0-02`, hoặc mang mã khác → hỏng."""
    base = _commit(repo, "chore(repo): init")
    message = "feat(core): add ids" if trailer_line is None else f"feat(core): add ids\n\n{trailer_line}"
    head = _commit(repo, message)
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): add ids",
        HEAD_REF="feature/b0-02-core-ids",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 1


def test_push_with_zero_base_checks_only_head(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`push` với `BASE_SHA` toàn số 0 (nhánh mới) → chỉ kiểm `HEAD_SHA`, commit cũ sai mẫu không làm hỏng."""
    _commit(repo, "update stuff")
    head = _commit(repo, "feat(core): add ids")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="push",
        HEAD_REF="main",
        BASE_SHA=_ZERO_SHA,
        HEAD_SHA=head,
    )
    assert code == 0


def test_push_checks_every_header_in_range_no_branch_or_trailer(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`push`: kiểm dòng đầu của các commit trong khoảng, không đòi tên nhánh/trailer."""
    base = _commit(repo, "chore(repo): init")
    head = _commit(repo, "feat(core): add ids")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="push",
        HEAD_REF="mungvu2004/whatever-not-a-prompt-branch",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 0


def test_unknown_event_fails_closed(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`EVENT` lạ → thoát 1 trước khi chạm git."""
    code = _run_main(monkeypatch, repo, EVENT="release", BASE_SHA="a" * 40, HEAD_SHA="b" * 40)
    assert code == 1


def test_workflow_dispatch_with_empty_base_checks_only_head(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`workflow_dispatch` (lượt chạy tay) với `BASE_SHA` rỗng → chỉ kiểm `HEAD_SHA`, đạt nếu đúng mẫu
    (/merge-review lượt 1 #2: trước đó mọi lượt chạy tay đỏ vì EVENT bị từ chối thẳng)."""
    _commit(repo, "update stuff")
    head = _commit(repo, "feat(core): add ids")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="workflow_dispatch",
        HEAD_REF="main",
        BASE_SHA="",
        HEAD_SHA=head,
    )
    assert code == 0


def test_workflow_dispatch_bad_head_header_fails(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`workflow_dispatch` vẫn kiểm dòng đầu `HEAD_SHA` — sai mẫu thì hỏng, không phải "miễn hết"."""
    head = _commit(repo, "not conventional commits")
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="workflow_dispatch",
        HEAD_REF="main",
        BASE_SHA="",
        HEAD_SHA=head,
    )
    assert code == 1


def test_dependabot_branch_skips_per_commit_header_but_checks_pr_title(
    monkeypatch: pytest.MonkeyPatch, repo: Path
) -> None:
    """`dependabot/docker/...` với commit dài (dòng đầu > 72, hậu tố Dependabot thêm " in /thư-mục")
    vẫn đạt vì per-commit không còn kiểm trên nhánh này — tiêu đề PR ngắn, đúng mẫu, vẫn được kiểm
    (/merge-review lượt 1 #4)."""
    base = _commit(repo, "chore(repo): init")
    long_header = "build(deps): bump nginxinc/nginx-unprivileged from 1.28.0-alpine to 1.29.1-alpine in /deploy/docker"
    assert len(long_header) > 72
    head = _commit(repo, long_header)
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="build(deps): bump nginx-unprivileged in /deploy/docker",
        HEAD_REF="dependabot/docker/nginx-unprivileged-1.29.1-alpine",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 0


def test_dependabot_branch_long_pr_title_still_fails(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """`dependabot/**` miễn dòng đầu từng commit, KHÔNG miễn tiêu đề PR — tiêu đề PR dài (chưa được
    người điều phối rút gọn trước khi squash, README §3) vẫn hỏng (/merge-review lượt 1 #4)."""
    base = _commit(repo, "chore(repo): init")
    head = _commit(repo, "build(deps): bump nginx from 1.0.0 to 1.0.1")
    long_pr_title = (
        "build(deps): bump nginxinc/nginx-unprivileged from 1.28.0-alpine to 1.29.1-alpine in /deploy/docker"
    )
    assert len(long_pr_title) > 72
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE=long_pr_title,
        HEAD_REF="dependabot/docker/nginx-unprivileged-1.29.1-alpine",
        BASE_SHA=base,
        HEAD_SHA=head,
    )
    assert code == 1


def test_missing_required_env_fails_closed(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """Thiếu biến bắt buộc của `pull_request` (`HEAD_REF`) → thoát 1."""
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="pull_request",
        PR_TITLE="feat(core): add ids",
        BASE_SHA="a" * 40,
        HEAD_SHA="b" * 40,
    )
    assert code == 1


def test_nonexistent_sha_fails_closed(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    """SHA đúng dạng hex 40 nhưng không tồn tại trong repo → git lỗi, thoát 1 kèm stderr (không nuốt)."""
    _commit(repo, "chore(repo): init")
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    code = _run_main(
        monkeypatch,
        repo,
        EVENT="push",
        HEAD_REF="main",
        BASE_SHA="a" * 40,
        HEAD_SHA=head,
    )
    assert code == 1


def test_module_entrypoint_runs_as_subprocess(repo: Path) -> None:
    """`python -m tools.ci.commits` chạy được như module, phủ lối vào `if __name__ == \"__main__\"`."""
    base = _commit(repo, "chore(repo): init")
    head = _commit(repo, "feat(core): add ids")
    env = dict(os.environ)
    env.update(
        {
            "EVENT": "push",
            "HEAD_REF": "main",
            "BASE_SHA": base,
            "HEAD_SHA": head,
            "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "tools.ci.commits"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    assert result.returncode == 0, result.stderr
