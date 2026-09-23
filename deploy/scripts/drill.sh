#!/usr/bin/env bash
# deploy/scripts/drill.sh — diễn tập sao lưu/khôi phục trên compose (B0-10 [6], hop-dong.md §2).
#
# Dựng compose (mặc định deploy/compose/ci.yml), chụp ảnh CSDL + object, sao lưu
# (deploy/backup/backup.sh), rồi khôi phục hai lần: Pha A đè lên CSDL đang sống,
# Pha B từ trắng (down -v && up) — cả hai phải khớp ảnh chụp gốc.
#
# Biến môi trường:
#   DRILL_COMPOSE_FILE   file compose dùng cho diễn tập (mặc định deploy/compose/ci.yml)
#   IMAGE_TAG             tag ảnh (mặc định ci)
#   WEB_HTTP_PORT, API_HOST_PORT, POSTGRES_HOST_PORT  cổng host (hop-dong.md §6)
#   BACKUP_AGE_RECIPIENT/BACKUP_AGE_IDENTITY  do script tự đặt nếu máy có age/age-keygen
#
# Mã thoát: 0 hai pha khớp; 1 lệch hoặc một bước hỏng; 2 tham số dòng lệnh sai
# (hop-dong.md §2). Gọi không tham số để chạy diễn tập đầy đủ; `--compare <gốc>
# <sau>` chỉ so sánh hai thư mục ảnh chụp đã có (không đụng Docker — dùng để kiểm).
set -euo pipefail

export MSYS_NO_PATHCONV=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

export COMPOSE_FILE="${DRILL_COMPOSE_FILE:-deploy/compose/ci.yml}"
export COMPOSE_ENV_FILES="deploy/compose/env.example"
export COMPOSE_PROJECT_NAME="appback-drill"
export IMAGE_TAG="${IMAGE_TAG:-ci}"
export IMAGE_REGISTRY=""
export WEB_HTTP_PORT="${WEB_HTTP_PORT:-18080}"
export API_HOST_PORT="${API_HOST_PORT:-18000}"
export POSTGRES_HOST_PORT="${POSTGRES_HOST_PORT:-15432}"
export PUBLIC_BASE_URL="http://127.0.0.1:${WEB_HTTP_PORT}"
export APPBACK_BASE_URL="http://127.0.0.1:${WEB_HTTP_PORT}"
export APPBACK_STORAGE="s3"

DRILL_ID="drill$(date -u +%Y%m%d%H%M%S)"
SCRATCH=""
AGE_DIR=""
# BACKUP_TARGET là tên biến README §9 bảo người vận hành đặt trong appback.env (đường sao
# lưu thật) — drill.sh xuất khẩu biến cùng tên cho backup.sh dùng, nên PHẢI khởi tạo rỗng ở
# đây (lối thoát sớm trước main(), vd đối số sai, mới đọc "" thay vì giá trị thừa kế từ môi
# trường) và cleanup() chỉ được xoá khi CHÍNH drill đã tạo (cờ riêng, không chỉ dựa vào biến
# rỗng hay không — review round 1 P1: LOG-01).
BACKUP_TARGET=""
DRILL_OWNS_BACKUP_TARGET=0

cleanup() {
  # Dọn compose (kể cả volume) và thư mục tạm dù kết thúc thế nào; giữ nguyên mã thoát gốc
  # (lệnh cuối trong một EXIT trap tự thành mã thoát của tiến trình nếu không chốt lại).
  local status=$?
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
  [ -n "$SCRATCH" ] && rm -rf "$SCRATCH"
  [ -n "$AGE_DIR" ] && rm -rf "$AGE_DIR"
  [ "$DRILL_OWNS_BACKUP_TARGET" = "1" ] && [ -n "$BACKUP_TARGET" ] && rm -rf "$BACKUP_TARGET"
  exit "$status"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Trợ giúp chung
# ---------------------------------------------------------------------------

_random_password() {
  # Sinh 24 ký tự ngẫu nhiên [A-Za-z0-9] bằng $RANDOM — không qua ống, an toàn dưới pipefail.
  local chars="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
  local out="" i
  for ((i = 0; i < 24; i++)); do
    out+="${chars:RANDOM % ${#chars}:1}"
  done
  printf '%s' "$out"
}

_mc() {
  # Chạy một lệnh mc trong container minio-init tạm; "$@" = tham số mc.
  # $S3_* và "$@" trong chuỗi lệnh phải nở BÊN TRONG container, không ở host.
  # shellcheck disable=SC2016
  docker compose run --rm --no-deps -T --entrypoint sh minio-init -c \
    'mc alias set local "$S3_ENDPOINT" "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null && exec mc "$@"' sh "$@"
}

mc_put() {
  # Đẩy nội dung đọc từ stdin thành object tại khoá "$1" (dưới bucket của app).
  _mc pipe "local/${S3_BUCKET_NAME}/$1"
}

mc_cat_sha256() {
  # SHA-256 nội dung object tại khoá "$1".
  _mc cat "local/${S3_BUCKET_NAME}/$1" | sha256sum | cut -d' ' -f1
}

mc_find_objects() {
  # Liệt kê mọi object dưới tiền tố "$1" (đường đầy đủ có "local/<bucket>/…" mỗi dòng).
  _mc find "local/${S3_BUCKET_NAME}/$1" --type f 2>/dev/null || true
}

create_admin() {
  # Tạo một admin qua CLI (nếu có) với mật khẩu ngẫu nhiên qua stdin — không in mật khẩu.
  local email="$1"
  if [ ! -f "$REPO_ROOT/apps/api/auth/cli.py" ]; then
    echo "bỏ qua create-admin — không có apps/api/auth/cli.py" >&2
    return 0
  fi
  local pw
  pw="$(_random_password)"
  printf '%s\n' "$pw" | docker compose run --rm -T api \
    python -m apps.api.auth.cli create-admin --email "$email" --name "Drill Admin" --password-stdin >/dev/null
}

read_tsv() {
  # Nạp file TSV "khoá<TAB>giá trị" ("$1") vào mảng kết hợp tên "$2".
  local -n _arr="$2"
  local k v
  while IFS=$'\t' read -r k v; do
    [ -n "$k" ] && _arr["$k"]="$v"
  done < "$1"
}

compare_snapshots() {
  # In bảng so sánh gốc/sau (tables.tsv + objects.tsv) của hai thư mục ảnh chụp; trả 1 nếu lệch.
  local goc="$1" sau="$2"
  local -A bt ot bo oo
  read_tsv "$goc/tables.tsv" bt
  read_tsv "$sau/tables.tsv" ot
  read_tsv "$goc/objects.tsv" bo
  read_tsv "$sau/objects.tsv" oo
  local mismatch=0 key match
  printf '%-40s | %-12s | %-12s | %s\n' "bảng/đối tượng" "gốc" "sau" "khớp"
  for key in $(printf '%s\n' "${!bt[@]}" "${!ot[@]}" | sort -u); do
    match="có"
    [ "${bt[$key]:-}" = "${ot[$key]:-}" ] || { match="KHÔNG"; mismatch=1; }
    printf '%-40s | %-12s | %-12s | %s\n' "$key" "${bt[$key]:-thiếu}" "${ot[$key]:-thiếu}" "$match"
  done
  for key in $(printf '%s\n' "${!bo[@]}" "${!oo[@]}" | sort -u); do
    match="có"
    [ "${bo[$key]:-}" = "${oo[$key]:-}" ] || { match="KHÔNG"; mismatch=1; }
    printf '%-40s | %-12.12s | %-12.12s | %s\n' "$key" "${bo[$key]:-thiếu}" "${oo[$key]:-thiếu}" "$match"
  done
  return "$mismatch"
}

report_three() {
  # In bảng so sánh gốc | pha A | pha B | khớp (tables.tsv + objects.tsv); trả 1 nếu lệch.
  local goc="$1" pa="$2" pb="$3"
  local -A gt at bt go ao bo
  read_tsv "$goc/tables.tsv" gt
  read_tsv "$pa/tables.tsv" at
  read_tsv "$pb/tables.tsv" bt
  read_tsv "$goc/objects.tsv" go
  read_tsv "$pa/objects.tsv" ao
  read_tsv "$pb/objects.tsv" bo
  local mismatch=0 key match
  printf '%-40s | %10s | %10s | %10s | %s\n' "bảng/đối tượng" "gốc" "pha A" "pha B" "khớp"
  for key in $(printf '%s\n' "${!gt[@]}" "${!at[@]}" "${!bt[@]}" | sort -u); do
    match="có"
    if [ "${gt[$key]:-}" != "${at[$key]:-}" ] || [ "${gt[$key]:-}" != "${bt[$key]:-}" ]; then
      match="KHÔNG"; mismatch=1
    fi
    printf '%-40s | %10s | %10s | %10s | %s\n' "$key" "${gt[$key]:-thiếu}" "${at[$key]:-thiếu}" "${bt[$key]:-thiếu}" "$match"
  done
  for key in $(printf '%s\n' "${!go[@]}" "${!ao[@]}" "${!bo[@]}" | sort -u); do
    match="có"
    if [ "${go[$key]:-}" != "${ao[$key]:-}" ] || [ "${go[$key]:-}" != "${bo[$key]:-}" ]; then
      match="KHÔNG"; mismatch=1
    fi
    printf '%-40s | %10.10s | %10.10s | %10.10s | %s\n' "$key" "${go[$key]:-thiếu}" "${ao[$key]:-thiếu}" "${bo[$key]:-thiếu}" "$match"
  done
  return "$mismatch"
}

snapshot() {
  # Chụp ảnh CSDL (mọi bảng public) + object dưới projects/ vào thư mục "$1".
  local dir="$1"
  mkdir -p "$dir"
  local tables
  tables="$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -Atc \
    "select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by table_name")"
  : > "$dir/tables.tsv"
  local t cnt
  while IFS= read -r t; do
    [ -z "$t" ] && continue
    cnt="$(docker compose exec -T postgres psql -U "$PG_USER" -d "$PG_DB" -Atc "select count(*) from \"$t\"")"
    printf '%s\t%s\n' "$t" "$cnt" >> "$dir/tables.tsv"
  done <<< "$tables"
  : > "$dir/objects.tsv"
  local full key hash
  while IFS= read -r full; do
    [ -z "$full" ] && continue
    key="${full#local/"${S3_BUCKET_NAME}"/}"
    hash="$(mc_cat_sha256 "$key")"
    printf '%s\t%s\n' "$key" "$hash" >> "$dir/objects.tsv"
  done <<< "$(mc_find_objects projects)"
}

do_restore() {
  # Gọi restore.sh với thư mục bản sao lưu "$1"; in thời gian; thoát khác 0 khi restore.sh hỏng.
  local backup_dir="$1" label="$2" start end
  start="$(date +%s)"
  if ! bash "$REPO_ROOT/deploy/backup/restore.sh" "$backup_dir"; then
    echo "restore.sh hỏng ở $label" >&2
    return 1
  fi
  end="$(date +%s)"
  echo "khôi phục $label: $((end - start))s"
}

# ---------------------------------------------------------------------------
# Diễn tập đầy đủ
# ---------------------------------------------------------------------------

main() {
  SCRATCH="$(mktemp -d)"
  AGE_DIR="$(mktemp -d)"
  BACKUP_TARGET="$(mktemp -d)"
  export BACKUP_TARGET
  DRILL_OWNS_BACKUP_TARGET=1

  if command -v age >/dev/null 2>&1 && command -v age-keygen >/dev/null 2>&1; then
    age-keygen -o "$AGE_DIR/key.txt" 2>/dev/null
    BACKUP_AGE_RECIPIENT="$(grep '^# public key:' "$AGE_DIR/key.txt" | cut -d: -f2 | tr -d ' ')"
    BACKUP_AGE_IDENTITY="$AGE_DIR/key.txt"
    export BACKUP_AGE_RECIPIENT BACKUP_AGE_IDENTITY
  else
    echo "mã hoá: chưa chạy — thiếu age"
  fi

  # Bước 1: dựng compose, seed, admin, 3 object gốc.
  docker compose up -d --wait
  docker compose run --rm migrate python -m packages.db.seeds
  PG_USER="$(docker compose exec -T postgres sh -c 'printf "%s" "$POSTGRES_USER"')"
  PG_DB="$(docker compose exec -T postgres sh -c 'printf "%s" "$POSTGRES_DB"')"
  S3_BUCKET_NAME="$(docker compose run --rm --no-deps -T --entrypoint sh minio-init -c 'printf "%s" "$S3_BUCKET"')"
  create_admin "drill-${DRILL_ID}@example.com"
  local i
  for i in 1 2 3; do
    printf 'drill object %s %s' "$i" "$DRILL_ID" | mc_put "projects/${DRILL_ID}/obj-${i}.bin"
  done

  # Bước 2: ảnh chụp gốc.
  snapshot "$SCRATCH/goc"

  # Bước 3: sao lưu.
  local backup_start backup_end backup_out backup_dir
  backup_start="$(date +%s)"
  if ! backup_out="$(bash "$REPO_ROOT/deploy/backup/backup.sh")"; then
    echo "backup.sh hỏng" >&2
    exit 1
  fi
  backup_end="$(date +%s)"
  backup_dir="$(printf '%s\n' "$backup_out" | tail -n 1)"
  echo "sao lưu: $((backup_end - backup_start))s, $(du -sh "$backup_dir" | cut -f1)"

  # Bước 4, Pha A: thêm dữ liệu rồi khôi phục đè lên CSDL đang sống.
  create_admin "drill-extra-${DRILL_ID}@example.com"
  printf 'drill extra object %s' "$DRILL_ID" | mc_put "projects/${DRILL_ID}/extra.bin"
  do_restore "$backup_dir" "Pha A"
  snapshot "$SCRATCH/pha-a"

  # Bước 5, Pha B: khôi phục từ trắng.
  docker compose down -v
  docker compose up -d --wait
  do_restore "$backup_dir" "Pha B"
  snapshot "$SCRATCH/pha-b"

  # Bước 6: bảng so sánh; lệch → thoát 1.
  if ! report_three "$SCRATCH/goc" "$SCRATCH/pha-a" "$SCRATCH/pha-b"; then
    echo "diễn tập lệch — xem bảng ở trên" >&2
    exit 1
  fi
  echo "diễn tập khớp cả hai pha"
}

usage() {
  echo "cách dùng: drill.sh | drill.sh --compare <gốc> <sau>" >&2
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  case "${1:-}" in
    --compare)
      [ $# -eq 3 ] || { usage; exit 2; }
      compare_snapshots "$2" "$3"
      exit $?
      ;;
    "")
      main
      ;;
    *)
      usage
      exit 2
      ;;
  esac
fi
