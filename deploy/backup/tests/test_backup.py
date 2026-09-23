"""Test `deploy/backup/backup.sh` (B0-10 [3], [8]) — pytest bước 5.

`docker` và `age` là lệnh giả (`fake_bin`) chỉ để kiểm thứ tự; thân của chúng ghi tệp
thật (giả lập `pg_dump`/`mc mirror`/`age`) để `manifest.json` băm được đúng nội dung
trên đĩa. Không có Docker/age thật trong lượt test này (support.py).
"""

from __future__ import annotations

import hashlib
import json
import re
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from deploy.scripts.tests.support import fake_bin, read_log, run_script

BACKUP_SH = Path(__file__).resolve().parents[1] / "backup.sh"

# Thân lệnh `docker` giả: nhận biết pg_dump/psql/mc mirror/tar qua nội dung "$*" rồi
# ghi tệp thật vào thư mục gắn qua "-v host:container" để manifest.json băm được.
_FAKE_DOCKER_BODY = r"""
args="$*"
host_mount=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-v" ]; then
    host_mount="${a%%:*}"
  fi
  prev="$a"
done

case "$args" in
  *pg_dump*)
    printf 'FAKE-PG-DUMP-BYTES\n'
    exit 0
    ;;
  *"select version_num"*)
    printf 'fakerev0001\n'
    exit 0
    ;;
  *"mc mirror --remove"*)
    exit 0
    ;;
  *"mc mirror"*)
    mkdir -p "$host_mount/projects/proj1"
    printf 'object-a' > "$host_mount/projects/proj1/a.bin"
    printf 'object-b' > "$host_mount/projects/proj1/b.bin"
    printf 'object-c' > "$host_mount/c.bin"
    exit 0
    ;;
  *"entrypoint tar"*|*" tar "*)
    if [ -n "$host_mount" ]; then
      src="$(mktemp -d)"
      printf 'vol-object-1' > "$src/x.bin"
      printf 'vol-object-2' > "$src/y.bin"
      tar -cf "$host_mount/objects.tar" -C "$src" .
      rm -rf "$src"
    fi
    exit 0
    ;;
  *"DROP DATABASE"*|*"CREATE DATABASE"*|*pg_restore*)
    cat >/dev/null
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
"""

_FAKE_AGE_BODY = r"""
out=""
prev=""
for a in "$@"; do
  if [ "$prev" = "-o" ]; then
    out="$a"
  fi
  prev="$a"
done
src="${@: -1}"
if [ "$1" = "-d" ]; then
  cp "$src" "$out"
else
  printf 'AGE-ENCRYPTED:' > "$out"
  cat "$src" >> "$out"
fi
"""


def _bin_dir(tmp_path: Path, *, fail_pg_dump: bool = False) -> Path:
    """Đặt lệnh giả `docker`/`age` vào `tmp_path/bin`; `fail_pg_dump` mô phỏng pg_dump hỏng."""
    docker_body = _FAKE_DOCKER_BODY
    if fail_pg_dump:
        docker_body = 'case "$*" in *pg_dump*) exit 1 ;; esac\n' + docker_body
    return fake_bin(tmp_path / "bin", {"docker": docker_body, "age": _FAKE_AGE_BODY})


def _run_backup(tmp_path: Path, env: dict[str, str]) -> tuple[int, str, Path]:
    """Chạy `backup.sh` với `env`, trả (mã thoát, log lệnh, BACKUP_TARGET)."""
    target = tmp_path / "target"
    log = tmp_path / "log"
    env = dict(env)
    fail_pg_dump = env.pop("_FAIL", "") == "1"
    full_env = {"FAKE_LOG": str(log), "BACKUP_TARGET": str(target), **env}
    result = run_script(BACKUP_SH, env=full_env, bin_dir=_bin_dir(tmp_path, fail_pg_dump=fail_pg_dump))
    return result.returncode, "\n".join(read_log(log)), target


def _sha256(path: Path) -> str:
    """SHA-256 hex của một tệp thật trên đĩa."""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_backup__manifest_has_required_fields_and_correct_hashes(tmp_path: Path) -> None:
    """s3 không mã hoá: manifest đủ trường §3, files khớp SHA-256 thật, object_count đúng."""
    code, log, target = _run_backup(tmp_path, {"APPBACK_STORAGE": "s3"})
    assert code == 0, log

    dirs = [p for p in target.iterdir() if p.is_dir()]
    assert len(dirs) == 1
    stage = dirs[0]
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))

    for key in ("created_at", "alembic_head", "storage", "encrypted", "object_count", "files"):
        assert key in manifest

    assert manifest["storage"] == "s3"
    assert manifest["encrypted"] is False
    assert manifest["alembic_head"] == "fakerev0001"
    assert manifest["object_count"] == 3
    assert len(manifest["files"]) == 4  # db.dump + 3 object

    for rel, expected in manifest["files"].items():
        assert _sha256(stage / rel) == expected


def test_backup__pg_dump_runs_before_mirror_and_mirror_has_no_remove(tmp_path: Path) -> None:
    """Log lệnh: pg_dump đứng trước mc mirror; không lệnh mirror nào dùng --remove."""
    code, log, _ = _run_backup(tmp_path, {"APPBACK_STORAGE": "s3"})
    assert code == 0, log

    lines = log.splitlines()
    pg_dump_idx = next(i for i, line in enumerate(lines) if "pg_dump" in line)
    mirror_idx = next(i for i, line in enumerate(lines) if "mc mirror" in line)
    assert pg_dump_idx < mirror_idx

    for line in lines:
        if "mirror" in line:
            assert "--remove" not in line


def test_backup__local_storage_produces_tar_and_skips_mirror(tmp_path: Path) -> None:
    """APPBACK_STORAGE=local → objects.tar, không lệnh mc mirror nào chạy."""
    code, log, target = _run_backup(tmp_path, {"APPBACK_STORAGE": "local"})
    assert code == 0, log
    assert "mirror" not in log

    stage = next(p for p in target.iterdir() if p.is_dir())
    assert (stage / "objects.tar").is_file()
    assert not (stage / "objects").exists()

    with tarfile.open(stage / "objects.tar") as tar:
        member_files = [m for m in tar.getmembers() if m.isfile()]
    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["storage"] == "local"
    assert manifest["object_count"] == len(member_files) == 2
    assert set(manifest["files"]) == {"db.dump", "objects.tar"}


def test_backup__age_recipient_encrypts_and_leaves_only_age_files(tmp_path: Path) -> None:
    """Có BACKUP_AGE_RECIPIENT → chỉ còn .age + manifest.json, encrypted: true."""
    code, log, target = _run_backup(tmp_path, {"APPBACK_STORAGE": "s3", "BACKUP_AGE_RECIPIENT": "age1testrecipient"})
    assert code == 0, log

    stage = next(p for p in target.iterdir() if p.is_dir())
    names = {p.name for p in stage.iterdir()}
    assert names == {"db.dump.age", "objects.tar.age", "manifest.json"}

    manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["encrypted"] is True
    assert set(manifest["files"]) == {"db.dump.age", "objects.tar.age"}
    for rel, expected in manifest["files"].items():
        assert _sha256(stage / rel) == expected


def test_backup__pg_dump_failure_exits_1_and_removes_stage_dir(tmp_path: Path) -> None:
    """pg_dump hỏng → thoát 1, không để lại thư mục dở dang."""
    code, log, target = _run_backup(tmp_path, {"APPBACK_STORAGE": "s3", "_FAIL": "1"})
    assert code == 1, log
    if target.exists():
        assert not any(target.iterdir())


def _make_day_dirs(target: Path, days_ago: list[int]) -> list[Path]:
    """Dựng thư mục giả `yyyymmddT000000Z` cho mỗi ngày trong `days_ago` (0 = hôm nay)."""
    target.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    made = []
    for delta in days_ago:
        ts = (now - timedelta(days=delta)).strftime("%Y%m%dT000000Z")
        d = target / ts
        d.mkdir(exist_ok=True)
        made.append(d)
    return made


def test_backup__rotate_only_keeps_seven_days_and_weekly_and_untouched_stray(tmp_path: Path) -> None:
    """Xoay vòng giữ 7 bản mới nhất + bản mới nhất mỗi tuần của 4 tuần; thư mục lạ không bị xoá."""
    target = tmp_path / "target"
    _make_day_dirs(target, list(range(40)))
    stray = target / "not-a-backup"
    stray.mkdir()

    env = {"FAKE_LOG": str(tmp_path / "log"), "BACKUP_TARGET": str(target)}
    result = run_script(BACKUP_SH, args=["--rotate-only"], env=env, bin_dir=_bin_dir(tmp_path))
    assert result.returncode == 0, result.stderr

    remaining = sorted(p.name for p in target.iterdir())
    assert stray.name in remaining

    pattern = re.compile(r"^\d{8}T\d{6}Z$")
    dated = [name for name in remaining if pattern.fullmatch(name)]

    now = datetime.now(UTC)
    expected = {(now - timedelta(days=d)).strftime("%Y%m%dT000000Z") for d in range(7)}
    for i in range(4):
        week_key = (now - timedelta(weeks=i)).isocalendar()[:2]
        same_week = [d for d in range(40) if (now - timedelta(days=d)).isocalendar()[:2] == week_key]
        if same_week:
            latest = min(same_week)
            expected.add((now - timedelta(days=latest)).strftime("%Y%m%dT000000Z"))

    assert set(dated) == expected
