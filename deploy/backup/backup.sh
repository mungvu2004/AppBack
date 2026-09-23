#!/usr/bin/env bash
# Sao lưu Postgres + kho object của AppBack (B0-10 [2], hợp đồng §3).
#
# Gọi: backup.sh            — tạo bản sao lưu mới rồi xoay vòng.
#      backup.sh --rotate-only — chỉ chạy xoay vòng trên BACKUP_TARGET hiện có (để kiểm độc lập).
#
# Biến môi trường (đều có mặc định, hợp đồng B0-10 §1, §3):
#   APPBACK_DIR             /opt/appback           — chứa prod.yml khi COMPOSE_FILE chưa đặt.
#   COMPOSE_FILE             $APPBACK_DIR/prod.yml  — tôn trọng biến gốc compose, không tự thêm -f.
#   COMPOSE_PROJECT_NAME     appback
#   BACKUP_TARGET            /var/backups/appback   — thư mục gốc chứa các bản sao lưu theo ngày giờ.
#   APPBACK_STORAGE          s3                     — "s3" mirror bucket MinIO; "local" tar volume.
#   BACKUP_AGE_RECIPIENT     (rỗng)                 — có thì mã hoá db.dump/objects.tar bằng age -r.
#
# Mã thoát: 0 đạt; 1 hỏng (thư mục dở bị xoá trước khi thoát).
set -euo pipefail

: "${APPBACK_DIR:=/opt/appback}"
: "${COMPOSE_FILE:=$APPBACK_DIR/prod.yml}"
: "${COMPOSE_PROJECT_NAME:=appback}"
export COMPOSE_FILE COMPOSE_PROJECT_NAME

: "${BACKUP_TARGET:=/var/backups/appback}"
: "${BACKUP_AGE_RECIPIENT:=}"
: "${APPBACK_STORAGE:=s3}"

case "$APPBACK_STORAGE" in
  s3 | local) ;;
  *)
    echo "loi: APPBACK_STORAGE phai la s3 hoac local, dang la: $APPBACK_STORAGE" >&2
    exit 1
    ;;
esac

# Giữ 7 bản mới nhất + bản mới nhất của mỗi tuần ISO trong 4 tuần gần nhất (hợp đồng §3);
# chỉ xoá thư mục khớp mẫu tên yyyymmddThhmmssZ, thư mục lạ giữ nguyên.
rotate_backups() {
  local target="$1"
  mkdir -p "$target"
  python3 - "$target" <<'PY'
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

target = Path(sys.argv[1])
pattern = re.compile(r"^\d{8}T\d{6}Z$")

entries = []
for child in target.iterdir():
    if child.is_dir() and pattern.fullmatch(child.name):
        ts = datetime.strptime(child.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        entries.append((ts, child))

if not entries:
    sys.exit(0)

entries.sort(key=lambda e: e[0], reverse=True)
keep = {path for _, path in entries[:7]}

now = datetime.now(timezone.utc)
for i in range(4):
    week_key = (now - timedelta(weeks=i)).isocalendar()[:2]
    same_week = [e for e in entries if e[0].isocalendar()[:2] == week_key]
    if same_week:
        same_week.sort(key=lambda e: e[0], reverse=True)
        keep.add(same_week[0][1])

for _, path in entries:
    if path not in keep:
        shutil.rmtree(path)
PY
}

if [[ "${1:-}" == "--rotate-only" ]]; then
  rotate_backups "$BACKUP_TARGET"
  exit 0
fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
stage_dir="$BACKUP_TARGET/$timestamp"

if [[ -e "$stage_dir" ]]; then
  echo "loi: thu muc da ton tai: $stage_dir" >&2
  exit 1
fi
mkdir -p "$stage_dir"

# Xoá thư mục dở khi có lỗi giữa chừng (B0-10 [2]), giữ nguyên mã thoát gốc.
cleanup() {
  local ec=$?
  trap - EXIT
  if [[ "$ec" -ne 0 && -d "$stage_dir" ]]; then
    rm -rf "$stage_dir"
  fi
  exit "$ec"
}
trap cleanup EXIT

# 1) pg_dump trước mọi thao tác object (B0-10 [2]).
# shellcheck disable=SC2016 # biến $POSTGRES_USER/$POSTGRES_DB phải giãn TRONG container postgres.
docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$stage_dir/db.dump"

# 2) đồng bộ object: s3 -> mc mirror (không --remove); local -> tar volume local-storage.
object_count=0
objects_dir=""
case "$APPBACK_STORAGE" in
  s3)
    objects_dir="$stage_dir/objects"
    mkdir -p "$objects_dir"
    # shellcheck disable=SC2016 # $S3_ENDPOINT/$S3_BUCKET/... phải giãn TRONG container minio-init.
    docker compose run --rm --no-deps --entrypoint sh -v "$objects_dir:/backup-objects" minio-init -c \
      'mc alias set local "$S3_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc mirror local/"$S3_BUCKET" /backup-objects'
    object_count="$(find "$objects_dir" -type f | wc -l | tr -d ' ')"
    ;;
  local)
    docker compose run --rm --no-deps --entrypoint tar -v "$stage_dir:/backup-dest" api \
      cf /backup-dest/objects.tar -C /var/lib/appback/storage .
    object_count="$(
      python3 -c 'import sys, tarfile; t = tarfile.open(sys.argv[1]); print(sum(1 for m in t.getmembers() if m.isfile()))' \
        "$stage_dir/objects.tar"
    )"
    ;;
esac

# 3) alembic head — revision đang áp dụng cho CSDL vừa dump (để khôi phục biết nâng lên head nào).
# shellcheck disable=SC2016 # $POSTGRES_USER/$POSTGRES_DB phải giãn TRONG container postgres.
alembic_head="$(docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select version_num from alembic_version"')"
alembic_head="$(printf '%s' "$alembic_head" | tr -d '[:space:]')"

# 4) mã hoá nếu có BACKUP_AGE_RECIPIENT: tar hoá objects/ (nếu là s3), age -r từng tệp dữ liệu, xoá bản rõ.
encrypted=false
if [[ -n "$BACKUP_AGE_RECIPIENT" ]]; then
  encrypted=true
  if [[ "$APPBACK_STORAGE" == "s3" ]]; then
    tar -cf "$stage_dir/objects.tar" -C "$objects_dir" .
    rm -rf "$objects_dir"
  fi
  age -r "$BACKUP_AGE_RECIPIENT" -o "$stage_dir/db.dump.age" "$stage_dir/db.dump"
  rm -f "$stage_dir/db.dump"
  age -r "$BACKUP_AGE_RECIPIENT" -o "$stage_dir/objects.tar.age" "$stage_dir/objects.tar"
  rm -f "$stage_dir/objects.tar"
fi

# 5) manifest.json — dựng bằng python3 (json.dumps), băm đúng tệp còn lại trên đĩa.
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
STAGE_DIR="$stage_dir" CREATED_AT="$created_at" ALEMBIC_HEAD="$alembic_head" \
  STORAGE="$APPBACK_STORAGE" ENCRYPTED="$encrypted" OBJECT_COUNT="$object_count" \
  python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

stage = Path(os.environ["STAGE_DIR"])
files = {}
for path in sorted(stage.rglob("*")):
    if path.is_file():
        rel = path.relative_to(stage).as_posix()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        files[rel] = digest.hexdigest()

manifest = {
    "created_at": os.environ["CREATED_AT"],
    "alembic_head": os.environ["ALEMBIC_HEAD"],
    "storage": os.environ["STORAGE"],
    "encrypted": os.environ["ENCRYPTED"] == "true",
    "object_count": int(os.environ["OBJECT_COUNT"]),
    "files": files,
}
(stage / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

# 6) xoay vòng bản cũ trong cùng BACKUP_TARGET.
rotate_backups "$BACKUP_TARGET"

# Đường dẫn bản sao lưu vừa tạo phải là dòng stdout cuối (hợp đồng B0-10 §2).
echo "$stage_dir"
