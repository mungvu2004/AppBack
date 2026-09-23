"""Quét shellcheck trên script shell của B0-10 và kiểm cấu trúc `drill.sh` (B0-10 [8])."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from deploy.scripts.tests.support import REPO_ROOT, run_script

DRILL_SH = REPO_ROOT / "deploy" / "scripts" / "drill.sh"

# Glob lúc chạy (không liệt kê tay): file của B0-10 việc khác (deploy.sh, backup.sh, …) tự
# được quét sau khi các nhánh song song gộp lại, không cần sửa test này lần nữa.
_SHELL_SCRIPTS = sorted(
    {*Path(REPO_ROOT, "deploy", "scripts").rglob("*.sh"), *Path(REPO_ROOT, "deploy", "backup").rglob("*.sh")}
)


def test_shellcheck_binary_present() -> None:
    """Ảnh verify phải có `shellcheck` sẵn — thiếu là hỏng, không phải bỏ qua (K25)."""
    assert shutil.which("shellcheck") is not None, "thiếu shellcheck trong PATH — cổng phải hỏng, không skip"


@pytest.mark.parametrize("script", _SHELL_SCRIPTS, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_shellcheck_clean(script: Path) -> None:
    """`shellcheck` không cảnh báo trên từng script `.sh` của `deploy/scripts` và `deploy/backup`."""
    assert shutil.which("shellcheck") is not None, "thiếu shellcheck trong PATH — cổng phải hỏng, không skip"
    # -x: theo `source "$DIR/lib.sh"` động qua chú thích `# shellcheck source=…` (deploy.sh,
    # rollback.sh, restore.sh) — đường trong chú thích đó tính từ REPO_ROOT (cwd ở đây), nên
    # truyền đường script tương đối, không phải tuyệt đối.
    result = subprocess.run(  # noqa: S603 — shellcheck có sẵn trên PATH, đường script cố định
        ["shellcheck", "-x", str(script.relative_to(REPO_ROOT))],  # noqa: S607 — tên lệnh cố định
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"shellcheck cảnh báo ở {script}:\n{result.stdout}{result.stderr}"


def test_drill_sh_stops_and_recreates_between_phases() -> None:
    """Giữa Pha A (đè lên) và Pha B (từ trắng) phải có `docker compose down -v` (B0-10 [6])."""
    text = DRILL_SH.read_text(encoding="utf-8")
    phase_a = text.index("Pha A")
    after_phase_a = text[phase_a:]
    between = after_phase_a[: after_phase_a.index("Bước 6")]
    assert "down -v" in between, "thiếu `docker compose down -v` giữa Pha A và Pha B"


def test_drill_sh_calls_backup_before_restore() -> None:
    """`backup.sh` phải được gọi trước lần gọi `restore.sh` đầu tiên."""
    text = DRILL_SH.read_text(encoding="utf-8")
    backup_idx = text.index("backup.sh")
    restore_idx = text.index("restore.sh")
    assert backup_idx < restore_idx, "backup.sh phải đứng trước restore.sh trong drill.sh"


def test_drill_sh_has_cleanup_trap() -> None:
    """`drill.sh` phải dọn compose + thư mục tạm bằng `trap ... EXIT`."""
    text = DRILL_SH.read_text(encoding="utf-8")
    assert "trap cleanup EXIT" in text
    assert "down -v --remove-orphans" in text


def test_drill_sh_compare_matches_identical_snapshots() -> None:
    """`drill.sh --compare <gốc> <sau>` thoát 0 khi hai ảnh chụp khớp nhau."""
    with tempfile.TemporaryDirectory() as tmp:
        goc = Path(tmp, "goc")
        sau = Path(tmp, "sau")
        for d in (goc, sau):
            d.mkdir()
            (d / "tables.tsv").write_text("users\t3\nprojects\t1\n", encoding="utf-8")
            (d / "objects.tsv").write_text("projects/a/obj-1.bin\tdeadbeef\n", encoding="utf-8")
        result = run_script(DRILL_SH, ["--compare", str(goc), str(sau)])
        assert result.returncode == 0, result.stdout + result.stderr
        assert "khớp" in result.stdout


def test_drill_sh_compare_flags_mismatch() -> None:
    """`drill.sh --compare <gốc> <sau>` thoát khác 0 khi số dòng hoặc SHA-256 lệch nhau."""
    with tempfile.TemporaryDirectory() as tmp:
        goc = Path(tmp, "goc")
        sau = Path(tmp, "sau")
        goc.mkdir()
        sau.mkdir()
        (goc / "tables.tsv").write_text("users\t3\n", encoding="utf-8")
        (sau / "tables.tsv").write_text("users\t4\n", encoding="utf-8")
        (goc / "objects.tsv").write_text("projects/a/obj-1.bin\tdeadbeef\n", encoding="utf-8")
        (sau / "objects.tsv").write_text("projects/a/obj-1.bin\tdeadbeef\n", encoding="utf-8")
        result = run_script(DRILL_SH, ["--compare", str(goc), str(sau)])
        assert result.returncode != 0
        assert "KHÔNG" in result.stdout


def test_drill_sh_compare_requires_two_directories() -> None:
    """Thiếu tham số cho `--compare` thoát mã 2 (đối số sai, hop-dong.md §2)."""
    with tempfile.TemporaryDirectory() as tmp:
        result = run_script(DRILL_SH, ["--compare", str(Path(tmp, "only-one"))])
        assert result.returncode == 2
