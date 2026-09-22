"""`tools/verify/run.sh verify`: trần số log cổng giữ trên host (NO-090), dọn hỏng không chặn cổng (NO-092).

Chạy bản chép của `run.sh` thật trong một repo git tạm, `docker` giả trên `PATH` ghi lại đối số:
kiểm đúng đoạn shell mà lượt cổng chạy, không dựng container.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RUN_SH = Path(__file__).resolve().parents[2] / "tools" / "verify" / "run.sh"
BASH = shutil.which("bash") or "bash"
GIT = shutil.which("git") or "git"
LOG_KEEP = 20
"""Trần `VERIFY_LOG_KEEP` của `run.sh`: số log tối đa trong thư mục sau một lượt, tính cả log của lượt đó."""


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    """Repo git tạm (tên có dấu cách) chứa `tools/verify/run.sh` thật và một commit — `run.sh` đọc HEAD."""
    root = tmp_path / "cây làm việc"
    (root / "tools" / "verify").mkdir(parents=True)
    shutil.copy2(RUN_SH, root / "tools" / "verify" / "run.sh")
    git = [GIT, "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run([GIT, "init", "-q", str(root)], check=True)  # noqa: S603 — lệnh cố định trên thư mục tạm
    subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], check=True)  # noqa: S603 — như trên
    return root


def _fake_command(bin_dir: Path, name: str, body: str) -> None:
    """Lệnh `sh` giả `name` trong `bin_dir` — `_run_verify` đặt `bin_dir` trước `PATH` thật."""
    bin_dir.mkdir(exist_ok=True)
    command = bin_dir / name
    command.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    command.chmod(0o755)


def _run_verify(root: Path, bin_dir: Path) -> tuple[list[str], str]:
    """`bash run.sh verify` với `docker` giả (cùng lệnh giả khác đã đặt trong `bin_dir`); lượt phải thoát 0.

    Trả đối số `docker` nhận được (mỗi dòng một đối số) và stderr của `run.sh`.
    """
    calls = bin_dir / "docker-args"
    _fake_command(bin_dir, "docker", f'printf "%s\\n" "$@" > "{calls}"')
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(  # noqa: S603 — bash + run.sh của repo tạm
        [BASH, str(root / "tools" / "verify" / "run.sh"), "verify"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return calls.read_text(encoding="utf-8").splitlines(), result.stderr


def _old_logs(log_dir: Path, count: int) -> list[str]:
    """`count` log cổng cũ trong `log_dir`, mtime tăng dần theo thứ tự tên trả về."""
    log_dir.mkdir(parents=True)
    names = [f"20260901T0000{i:02d}Z-{i:012x}.log" for i in range(count)]
    for i, name in enumerate(names):
        (log_dir / name).write_text("lượt cũ\n", encoding="utf-8")
        os.utime(log_dir / name, (1_700_000_000 + i, 1_700_000_000 + i))
    return names


@pytest.mark.parametrize("existing", [0, LOG_KEEP - 1, LOG_KEEP, LOG_KEEP + 3])
def test_verify_giữ_log_mới_nhất_dưới_trần(worktree: Path, tmp_path: Path, existing: int) -> None:
    """NO-090: trước lượt còn đúng `LOG_KEEP - 1` log mới nhất (theo mtime); file khác trong thư mục để nguyên."""
    log_dir = worktree / ".cache" / "src-out" / "verify"
    names = _old_logs(log_dir, existing)
    (log_dir / "ghi-chú.txt").write_text("không phải log\n", encoding="utf-8")

    args, _ = _run_verify(worktree, tmp_path / "bin")

    kept = names[max(0, existing - (LOG_KEEP - 1)) :]
    assert sorted(p.name for p in log_dir.iterdir()) == sorted([*kept, "ghi-chú.txt"])
    assert any(a.startswith("VERIFY_LOG_FILE=/src-out/verify/") for a in args)


def test_verify_vẫn_chạy_cổng_khi_dọn_log_cũ_hỏng(worktree: Path, tmp_path: Path) -> None:
    """NO-092: `rm` hỏng (log cũ bị giữ trên Windows: "Device or resource busy") chỉ để lại một dòng cảnh báo.

    Dọn log là việc phụ: `docker` vẫn được gọi, mã thoát là của cổng (0), log cũ còn nguyên.
    """
    log_dir = worktree / ".cache" / "src-out" / "verify"
    names = _old_logs(log_dir, LOG_KEEP)
    bin_dir = tmp_path / "bin"
    _fake_command(bin_dir, "rm", 'echo "rm: cannot remove $2: Device or resource busy" >&2; exit 1')

    args, stderr = _run_verify(worktree, bin_dir)

    assert any(a.startswith("VERIFY_LOG_FILE=/src-out/verify/") for a in args)
    assert "Device or resource busy" in stderr
    assert "dọn log cổng cũ hỏng" in stderr
    assert sorted(p.name for p in log_dir.iterdir()) == sorted(names)
