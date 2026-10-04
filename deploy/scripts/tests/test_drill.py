"""Test `deploy/scripts/drill.sh` — không xoá `BACKUP_TARGET` thừa kế khi thoát sớm."""

from __future__ import annotations

from pathlib import Path

from deploy.scripts.tests.support import REPO_ROOT, fake_bin, read_log, run_script

SCRIPT = REPO_ROOT / "deploy" / "scripts" / "drill.sh"

# `docker` giả — hai test dưới thoát trước khi gọi `main()`, nhưng `trap cleanup EXIT` vẫn
# chạy `docker compose down -v --remove-orphans`; không stub thì đây là `docker` THẬT trên
# PATH và xoá volume của một lượt `drill.sh`/compose khác đang chạy song song trên máy dev
# (review round 2 N2/TEST-02) — mọi test khác của nhánh đã stub `docker`, chỗ này lệch chuẩn.
_FAKE_DOCKER_BODY = "exit 0\n"


def _bin_dir(tmp_path: Path) -> Path:
    """Thư mục chứa `docker` giả, đặt đầu `PATH`."""
    return fake_bin(tmp_path / "bin", {"docker": _FAKE_DOCKER_BODY})


def _assert_cleanup_used_fake_docker(log: Path) -> None:
    """Khẳng định DƯƠNG rằng `cleanup()` đã gọi `docker` GIẢ (review lượt 3 R3).

    Thân chuẩn của `fake_bin` mở đầu bằng `printf … >> "$FAKE_LOG"`; hai test này
    trước đây không đặt `FAKE_LOG` nên stub in `bash: : No such file or directory`
    rồi mất dòng log — `docker` thật bị chặn nhưng không có gì chứng minh, ai lỡ bỏ
    `bin_dir` sau này thì test vẫn xanh và `compose down -v` THẬT lại chạy.
    """
    lines = list(read_log(log))
    assert any("compose down -v" in line for line in lines), f"cleanup() không gọi docker giả — dòng đã ghi: {lines}"


def test_drill_bad_args_khong_xoa_backup_target_thua_ke(tmp_path: Path) -> None:
    """Review round 1 P1 (LOG-01): đối số sai → thoát 2 trước khi `main()` tự tạo thư mục
    tạm riêng; `cleanup()` (chạy qua `trap … EXIT`) không được đụng `BACKUP_TARGET` thừa kế
    từ môi trường (README §9: người vận hành đặt biến này trỏ tới bản sao lưu thật)."""
    inherited = tmp_path / "bao-sao-luu-that"
    inherited.mkdir()
    marker = inherited / "bao-cap-nhat-nhat.tar"
    marker.write_text("du lieu that", encoding="utf-8")

    log = tmp_path / "docker.log"
    result = run_script(
        SCRIPT,
        ["--bogus-arg"],
        env={"BACKUP_TARGET": str(inherited), "FAKE_LOG": str(log)},
        bin_dir=_bin_dir(tmp_path),
    )

    assert result.returncode == 2, result.stderr
    assert inherited.is_dir()
    assert marker.read_text(encoding="utf-8") == "du lieu that"
    _assert_cleanup_used_fake_docker(log)


def test_drill_compare_sai_so_doi_so_khong_xoa_backup_target_thua_ke(tmp_path: Path) -> None:
    """Cùng lỗ hổng ở nhánh `--compare` thiếu đối số (thoát 2 trước `main()`)."""
    inherited = tmp_path / "bao-sao-luu-that"
    inherited.mkdir()
    marker = inherited / "bao.tar"
    marker.write_text("du lieu that", encoding="utf-8")

    log = tmp_path / "docker.log"
    result = run_script(
        SCRIPT,
        ["--compare", "chi-mot-doi-so"],
        env={"BACKUP_TARGET": str(inherited), "FAKE_LOG": str(log)},
        bin_dir=_bin_dir(tmp_path),
    )

    assert result.returncode == 2, result.stderr
    assert inherited.is_dir()
    assert marker.exists()
    _assert_cleanup_used_fake_docker(log)


def test_drill_storage_is_parameter_not_hardcoded__no_c16b(tmp_path: Path) -> None:
    """Diễn tập phải chạy được cả kho `local` (FIX-215 lọt hồi quy umask vì drill ép `s3`):
    `DRILL_STORAGE` quyết định `APPBACK_STORAGE`, giá trị lạ → thoát 2 trước mọi lệnh docker."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'APPBACK_STORAGE="s3"' not in text, "drill.sh còn ép APPBACK_STORAGE=s3"
    log = tmp_path / "log"
    result = run_script(SCRIPT, [], bin_dir=_bin_dir(tmp_path), env={"FAKE_LOG": str(log), "DRILL_STORAGE": "bogus"})
    assert result.returncode == 2, result.stderr
    assert "DRILL_STORAGE" in result.stderr


# `docker` giả đọc cạn stdin như `docker compose exec -T` thật (W10/C47: lệnh docker trong vòng
# `while read … <<< …` nuốt phần còn lại của danh sách, ảnh chụp chỉ còn dòng đầu).
_FAKE_DOCKER_SNAPSHOT = r"""
cat >/dev/null
case "$*" in
  *information_schema*) printf 'alpha\nbeta\ngamma\n' ;;
  *"count(*)"*) printf '7\n' ;;
  *find*) printf 'local/local/projects/p/a.bin\nlocal/local/projects/p/b.bin\nlocal/local/projects/p/c.bin\n' ;;
  *sha256sum*) printf 'abc123  -\n' ;;
esac
"""


def test_drill_snapshot_lists_every_table_and_object__w10(tmp_path: Path) -> None:
    """`snapshot` chụp ĐỦ mọi bảng và object kể cả khi `docker` đọc stdin — không thì diễn tập
    so sánh một bảng một object rồi báo "khớp" giả (FIX-341)."""
    bin_dir = fake_bin(tmp_path / "bin", {"docker": _FAKE_DOCKER_SNAPSHOT})
    out = tmp_path / "snap"
    wrapper = tmp_path / "w.sh"
    wrapper.write_text(
        f'source "{SCRIPT.as_posix()}"\ntrap - EXIT\n'
        f'PG_USER=u PG_DB=d S3_BUCKET_NAME=local APPBACK_STORAGE=local snapshot "{out.as_posix()}"\n',
        encoding="utf-8",
    )
    result = run_script(wrapper, bin_dir=bin_dir, env={"FAKE_LOG": str(tmp_path / "log")})
    assert result.returncode == 0, result.stderr
    tables = (out / "tables.tsv").read_text(encoding="utf-8").splitlines()
    objects = (out / "objects.tsv").read_text(encoding="utf-8").splitlines()
    assert tables == ["alpha\t7", "beta\t7", "gamma\t7"]
    assert objects == [f"projects/p/{n}.bin\tabc123" for n in "abc"]
