"""Test `deploy/scripts/drill.sh` — không xoá `BACKUP_TARGET` thừa kế khi thoát sớm."""

from __future__ import annotations

from pathlib import Path

from deploy.scripts.tests.support import REPO_ROOT, fake_bin, run_script

SCRIPT = REPO_ROOT / "deploy" / "scripts" / "drill.sh"

# `docker` giả — hai test dưới thoát trước khi gọi `main()`, nhưng `trap cleanup EXIT` vẫn
# chạy `docker compose down -v --remove-orphans`; không stub thì đây là `docker` THẬT trên
# PATH và xoá volume của một lượt `drill.sh`/compose khác đang chạy song song trên máy dev
# (review round 2 N2/TEST-02) — mọi test khác của nhánh đã stub `docker`, chỗ này lệch chuẩn.
_FAKE_DOCKER_BODY = "exit 0\n"


def _bin_dir(tmp_path: Path) -> Path:
    return fake_bin(tmp_path / "bin", {"docker": _FAKE_DOCKER_BODY})


def test_drill_bad_args_khong_xoa_backup_target_thua_ke(tmp_path: Path) -> None:
    """Review round 1 P1 (LOG-01): đối số sai → thoát 2 trước khi `main()` tự tạo thư mục
    tạm riêng; `cleanup()` (chạy qua `trap … EXIT`) không được đụng `BACKUP_TARGET` thừa kế
    từ môi trường (README §9: người vận hành đặt biến này trỏ tới bản sao lưu thật)."""
    inherited = tmp_path / "bao-sao-luu-that"
    inherited.mkdir()
    marker = inherited / "bao-cap-nhat-nhat.tar"
    marker.write_text("du lieu that", encoding="utf-8")

    result = run_script(
        SCRIPT,
        ["--bogus-arg"],
        env={"BACKUP_TARGET": str(inherited)},
        bin_dir=_bin_dir(tmp_path),
    )

    assert result.returncode == 2, result.stderr
    assert inherited.is_dir()
    assert marker.read_text(encoding="utf-8") == "du lieu that"


def test_drill_compare_sai_so_doi_so_khong_xoa_backup_target_thua_ke(tmp_path: Path) -> None:
    """Cùng lỗ hổng ở nhánh `--compare` thiếu đối số (thoát 2 trước `main()`)."""
    inherited = tmp_path / "bao-sao-luu-that"
    inherited.mkdir()
    marker = inherited / "bao.tar"
    marker.write_text("du lieu that", encoding="utf-8")

    result = run_script(
        SCRIPT,
        ["--compare", "chi-mot-doi-so"],
        env={"BACKUP_TARGET": str(inherited)},
        bin_dir=_bin_dir(tmp_path),
    )

    assert result.returncode == 2, result.stderr
    assert inherited.is_dir()
    assert marker.exists()
