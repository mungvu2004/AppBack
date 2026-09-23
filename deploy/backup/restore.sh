#!/usr/bin/env bash
# Khôi phục AppBack từ một bản sao lưu của backup.sh (B0-10 [2]).
#
# Gọi: restore.sh <thư mục bản sao lưu>
#
# Thứ tự bắt buộc: (1) kiểm SHA-256 mọi tệp trong manifest TRƯỚC khi dừng gì; (2) giải mã
# .age nếu có; (3) dừng api/worker/beat; (4) DROP DATABASE … WITH (FORCE) rồi CREATE DATABASE;
# (5) pg_restore; (6) khôi phục object (bucket/volume bị xoá sạch trước khi đổ lại); (7) migrate;
# (8) bật lại api/worker/beat, chờ healthy; (9) smoke.sh.
#
# APPBACK_DIR/COMPOSE_FILE/COMPOSE_PROJECT_NAME/APPBACK_BASE_URL/APPBACK_HEALTH_TIMEOUT_S
# và wait_healthy đến từ `../scripts/lib.sh` (source ở dưới, R-07 — dùng chung với
# deploy.sh/rollback.sh). Biến riêng của script này:
#   BACKUP_AGE_IDENTITY       (rỗng) — bắt buộc khi bản sao lưu có .age.
#   APPBACK_SCRIPTS_DIR       thư mục "../scripts" cạnh script này — chứa lib.sh, smoke.sh.
#
# Mã thoát: 0 đạt; 1 hỏng; 2 đối số/môi trường sai (kể cả thiếu BACKUP_AGE_IDENTITY); 3 SHA-256 lệch.
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "dung: restore.sh <thu muc ban sao luu>" >&2
  exit 2
fi

backup_dir="$1"
if [[ ! -d "$backup_dir" ]]; then
  echo "loi: khong tim thay thu muc: $backup_dir" >&2
  exit 2
fi
# Chuẩn hoá thành đường tuyệt đối ngay — đường tương đối làm nguồn bind `-v` của Docker sai
# (Docker không tự giải theo cwd của script), lỗi chỉ nổ SAU khi đã DROP DATABASE (review
# round 1 P3 SEC-03).
backup_dir="$(cd "$backup_dir" && pwd)"

manifest="$backup_dir/manifest.json"
if [[ ! -f "$manifest" ]]; then
  echo "loi: thieu manifest.json trong $backup_dir" >&2
  exit 2
fi

: "${BACKUP_AGE_IDENTITY:=}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
: "${APPBACK_SCRIPTS_DIR:=$script_dir/../scripts}"
# lib.sh đặt mặc định APPBACK_DIR/COMPOSE_FILE/COMPOSE_PROJECT_NAME/APPBACK_BASE_URL/
# APPBACK_HEALTH_TIMEOUT_S và wait_container_healthy/wait_healthy (R-07 — trước đây
# restore.sh tự chép các mặc định và vòng lặp chờ healthy riêng).
# shellcheck source=deploy/scripts/lib.sh
source "$APPBACK_SCRIPTS_DIR/lib.sh"

# 1) SHA-256 mọi tệp trong manifest.files TRƯỚC khi dừng bất cứ gì (B0-10 [2]).
if ! python3 - "$backup_dir" "$manifest" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

backup_dir = Path(sys.argv[1])
manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for rel, expected in manifest["files"].items():
    path = backup_dir / rel
    if not path.is_file():
        print(f"thieu tep trong manifest: {rel}", file=sys.stderr)
        sys.exit(1)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        print(f"sha256 lech: {rel}", file=sys.stderr)
        sys.exit(1)
PY
then
  echo "loi: kiem SHA-256 that bai" >&2
  exit 3
fi

storage="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["storage"])' "$manifest")"
encrypted="$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1]))["encrypted"]).lower())' "$manifest")"

# Kiểm `storage` hợp lệ NGAY sau khi đọc, TRƯỚC mọi lệnh giải mã/dừng dịch vụ/DROP DATABASE
# (review round 1 P2 SEC-01/LOG-02: trước đây chỉ kiểm ở bước 6, sau khi đã drop DB — biên
# lệch chuẩn của chính backup.sh, vốn kiểm giá trị này ngay đầu ở :27-33).
case "$storage" in
  s3 | local) ;;
  *)
    echo "loi: storage la khong hop le trong manifest: $storage" >&2
    exit 1
    ;;
esac

# 2) giải mã .age nếu có (thiếu BACKUP_AGE_IDENTITY -> thoát 2, trước mọi lệnh dừng).
work_dir=""
cleanup_work_dir() {
  if [[ -n "$work_dir" && -d "$work_dir" ]]; then
    rm -rf "$work_dir"
  fi
}
trap cleanup_work_dir EXIT

db_dump_path="$backup_dir/db.dump"
objects_dir_path="$backup_dir/objects"
objects_tar_path="$backup_dir/objects.tar"

if [[ "$encrypted" == "true" ]]; then
  if [[ -z "$BACKUP_AGE_IDENTITY" ]]; then
    echo "loi: ban sao luu da ma hoa nhung thieu BACKUP_AGE_IDENTITY" >&2
    exit 2
  fi
  work_dir="$(mktemp -d)"
  age -d -i "$BACKUP_AGE_IDENTITY" -o "$work_dir/db.dump" "$backup_dir/db.dump.age"
  age -d -i "$BACKUP_AGE_IDENTITY" -o "$work_dir/objects.tar" "$backup_dir/objects.tar.age"
  db_dump_path="$work_dir/db.dump"
  objects_tar_path="$work_dir/objects.tar"
  if [[ "$storage" == "s3" ]]; then
    mkdir -p "$work_dir/objects"
    tar -xf "$objects_tar_path" -C "$work_dir/objects"
    objects_dir_path="$work_dir/objects"
  fi
fi

# 3) dừng dịch vụ trước khi chạm CSDL/kho object.
docker compose stop api worker beat

# 4) DROP DATABASE … WITH (FORCE) rồi CREATE DATABASE — nối vào DB "postgres", không phải DB đích.
# shellcheck disable=SC2016 # $POSTGRES_USER/$POSTGRES_DB phải giãn TRONG container postgres.
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$POSTGRES_DB\" WITH (FORCE)"'
# shellcheck disable=SC2016 # $POSTGRES_USER/$POSTGRES_DB phải giãn TRONG container postgres.
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$POSTGRES_DB\""'

# 5) pg_restore từ tệp đã kiểm/giải mã (đọc qua stdin, không cần seek).
# shellcheck disable=SC2016 # $POSTGRES_USER/$POSTGRES_DB phải giãn TRONG container postgres.
docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < "$db_dump_path"

# 6) khôi phục object — bucket/volume bị xoá sạch trước khi đổ lại (object phát sinh sau bản sao lưu biến mất).
case "$storage" in
  s3)
    # shellcheck disable=SC2016 # $S3_ENDPOINT/$S3_BUCKET/... phải giãn TRONG container minio-init.
    docker compose run --rm --no-deps --entrypoint sh -v "$objects_dir_path:/restore-objects:ro" minio-init -c \
      'mc alias set local "$S3_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null && mc mirror --remove /restore-objects local/"$S3_BUCKET"'
    ;;
  local)
    docker compose run --rm --no-deps --entrypoint sh -v "$objects_tar_path:/restore/objects.tar:ro" api -c \
      'find /var/lib/appback/storage -mindepth 1 -delete && tar -xf /restore/objects.tar -C /var/lib/appback/storage'
    ;;
  *)
    # Không thể tới — đã kiểm "s3|local" ở :83, trước mọi lệnh dừng/DROP DATABASE (review
    # round 2 N7). Giữ lại làm phòng thủ, không phải đường vào còn sống.
    echo "loi: storage la khong hop le trong manifest: $storage" >&2
    exit 1
    ;;
esac

# 7) migrate — alembic upgrade head bằng ảnh hiện hành, KHÔNG downgrade (B0-10 [9]).
docker compose run --rm migrate

# 8) bật lại dịch vụ, chờ api healthy trước khi smoke.
docker compose up -d api worker beat
wait_healthy api

# 9) smoke test.
bash "$APPBACK_SCRIPTS_DIR/smoke.sh" "$APPBACK_BASE_URL"
