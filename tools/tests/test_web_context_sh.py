"""`deploy/docker/web-context.sh` và `run.sh`: đường mặc định của repo AppFront (NO-325).

Chạy bản chép của script thật trong một repo git tạm, `git archive` giả ghi lại đường `-C`.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash") or "bash"
GIT = shutil.which("git") or "git"
TAR = shutil.which("tar") or "tar"
SHA = "0" * 40


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """Repo git tạm `tmp_path/AppBack` (cha có dấu cách) chứa bản chép `run.sh`, `web-context.sh`, `APPFRONT_SHA`."""
    root = tmp_path / "gốc có cách" / "AppBack"
    for rel in ("tools/verify/run.sh", "tools/verify/appfront_repo.sh", "deploy/docker/web-context.sh"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, root / rel)
    (root / "tools" / "contract").mkdir(parents=True)
    (root / "tools" / "contract" / "APPFRONT_SHA").write_text(SHA + "\n", encoding="utf-8")
    subprocess.run([GIT, "init", "-q", str(root)], check=True)  # noqa: S603 — lệnh cố định trên thư mục tạm
    subprocess.run(  # noqa: S603 — như trên
        [
            GIT,
            "-C",
            str(root),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
        check=True,
    )
    return root


def _git_shim(bin_dir: Path) -> Path:
    """`git` giả: `archive` ghi đối số và in một tar rỗng; mọi lệnh khác chuyển cho git thật. Trả file ghi đối số."""
    bin_dir.mkdir()
    seen = bin_dir / "archive-args"
    shim = bin_dir / "git"
    shim.write_text(
        f'#!/bin/sh\ncase " $* " in *" archive "*) printf "%s\n" "$@" > "{seen}"; '
        f'exec "{TAR}" -cf - -T /dev/null ;; esac\nexec "{GIT}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    docker = bin_dir / "docker"  # run.sh gọi docker thật nếu không có shim
    docker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    docker.chmod(0o755)
    return seen


def _archive_repo(seen: Path) -> str:
    """Đối số ngay sau `-C` trong lệnh `git archive` đã ghi."""
    args = seen.read_text(encoding="utf-8").splitlines()
    return args[args.index("-C") + 1]


def _run(cmd: list[str], bin_dir: Path, cwd: Path) -> None:
    """Chạy `cmd` với shim đứng đầu `PATH`, không đặt `APPFRONT_REPO`; phải thoát 0."""
    env = {k: v for k, v in os.environ.items() if k != "APPFRONT_REPO"}
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    result = subprocess.run(  # noqa: S603 — bash + script repo tạm
        cmd, env=env, cwd=cwd, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_run_sh__appfront_mặc_định_là_anh_em_của_checkout_chính(checkout: Path, tmp_path: Path) -> None:
    """NO-325: không `APPFRONT_REPO` → `<cha của checkout chính>/AppFront`, không phải `F:/AppFront` cứng."""
    seen = _git_shim(tmp_path / "bin")
    _run([BASH, str(checkout / "tools/verify/run.sh"), "verify"], tmp_path / "bin", checkout)
    assert Path(_archive_repo(seen)) == checkout.parent / "AppFront"


def test_run_sh__appfront_mặc_định_đúng_từ_worktree_phụ(checkout: Path, tmp_path: Path) -> None:
    """Worktree phụ nằm ngoài thư mục cha của checkout chính (Orca) vẫn tìm ra repo AppFront cạnh checkout chính."""
    extra = tmp_path / "nơi khác" / "wt"
    add = [GIT, "-C", str(checkout), "worktree", "add", "-q", "--detach", str(extra)]
    subprocess.run(add, check=True)  # noqa: S603 — repo tạm
    shutil.copytree(checkout / "tools", extra / "tools", dirs_exist_ok=True)
    seen = _git_shim(tmp_path / "bin")
    _run([BASH, str(extra / "tools/verify/run.sh"), "verify"], tmp_path / "bin", extra)
    assert Path(_archive_repo(seen)) == checkout.parent / "AppFront"


def test_web_context_sh__appfront_mặc_định_là_anh_em_của_checkout_chính(checkout: Path, tmp_path: Path) -> None:
    """NO-325: `web-context.sh` không `APPFRONT_REPO` dùng cùng đường mặc định như `run.sh`."""
    seen = _git_shim(tmp_path / "bin")
    _run([BASH, str(checkout / "deploy/docker/web-context.sh"), SHA, str(tmp_path / "ra")], tmp_path / "bin", checkout)
    assert Path(_archive_repo(seen)) == checkout.parent / "AppFront"
