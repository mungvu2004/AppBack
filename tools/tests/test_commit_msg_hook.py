"""Hook `.githooks/commit-msg`: dòng đầu theo Conventional Commits (BE-00 §13.2)."""

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / ".githooks" / "commit-msg"
BASH = shutil.which("bash") or "bash"


def _run(tmp_path: Path, message: str) -> subprocess.CompletedProcess[str]:
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(message, encoding="utf-8")
    return subprocess.run(  # noqa: S603 — lệnh cố định: bash + hook trong repo + file tạm
        [BASH, str(HOOK), str(msg_file)], capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    "message",
    [
        "feat(core): add error registry and masked logging\n\nPrompt: B0-02\n",
        "chore(repo): bootstrap uv monorepo\n",
        "fix(api): handle null pointer in payment gateway",
        "feat!: drop python 3.11",
        "ci(github/actions): pin checkout",
        "docs: update readme",
        "# Please enter the commit message\n\nrefactor(db): split engine module\n",
        "Merge branch 'feature/b0-02-core-errors-logging-ids'",
        'Revert "feat(core): add ids"',
        "fixup! feat(core): add ids",
        "feat(core): " + "x" * 60,  # đúng 72 ký tự
    ],
)
def test_hook_accepts(tmp_path: Path, message: str) -> None:
    result = _run(tmp_path, message)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "message",
    [
        "B0-02: lõi",
        "B0-02 FIX FIX-001: sửa",
        "feature(core): add ids",
        "Feat(core): add ids",
        "feat(Core): add ids",
        "feat(core):add ids",
        "feat(core):  ",
        "feat(): add ids",
        "feat(core) add ids",
        "update stuff",
        "feat(core): " + "x" * 61,  # 73 ký tự
        "",
        "# chỉ có chú thích\n",
    ],
)
def test_hook_rejects(tmp_path: Path, message: str) -> None:
    result = _run(tmp_path, message)
    assert result.returncode == 1
    assert "BE-00 §13.2" in result.stderr
