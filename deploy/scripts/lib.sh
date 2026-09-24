#!/usr/bin/env bash
# Thư viện dùng chung cho deploy.sh và rollback.sh (R-07) — CHỈ được `source`,
# không tự chạy. Mặc định biến môi trường, kiểm tag, đổi api/worker/beat,
# gọi smoke, đọc/ghi current_tag & previous_tag, và hai hàm run()/plan() cho
# chế độ --dry-run của deploy.sh (in lệnh thay vì chạy — hợp đồng B0-10 §1,§2).
set -euo pipefail

: "${APPBACK_DIR:=/opt/appback}"
# Không dùng ":=" — drill.sh cố ý đặt IMAGE_REGISTRY="" (ảnh cục bộ, không registry);
# ":=" coi rỗng như chưa đặt và sẽ ghi đè lại registry mặc định.
: "${IMAGE_REGISTRY=ghcr.io/mungvu2004}"
: "${APPBACK_BASE_URL:=http://127.0.0.1}"
: "${APPBACK_HEALTH_TIMEOUT_S:=180}"
: "${APPBACK_HEALTH_POLL_S:=2}"
# Chờ nginx tự dịch lại "api" trước khi xoá container cũ. Khai ĐÚNG MỘT LẦN ở đây
# (NO-120: trước đây hằng 11 có ba bản — dòng kế hoạch dry-run, lệnh sleep thật và
# README — nên hạ mặc định của sleep mà test vẫn xanh).
#
# RÀNG BUỘC (R-05): 11 = TTL cache DNS của nginx (10s, `resolver 127.0.0.11
# valid=10s` ở deploy/nginx/templates/{dev,prod}/app.conf.template) + 1s biên an
# toàn; test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl chốt quan hệ đó.
# Dùng `=` chứ không `:=` (bài học NO-114): test và người vận hành đặt
# APPBACK_API_SWAP_SETTLE_S=0 để tắt hẳn lúc kiểm, `:=` coi 0 là hợp lệ nhưng coi
# chuỗi rỗng như chưa đặt và sẽ ghi đè lại.
: "${APPBACK_API_SWAP_SETTLE_S=11}"
export APPBACK_DIR IMAGE_REGISTRY APPBACK_BASE_URL APPBACK_HEALTH_TIMEOUT_S APPBACK_API_SWAP_SETTLE_S
export COMPOSE_FILE="${COMPOSE_FILE:-$APPBACK_DIR/prod.yml}"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-appback}"
export COMPOSE_ENV_FILES="${COMPOSE_ENV_FILES:-}"

LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
APPBACK_TAG_RE='^(v[0-9]+\.[0-9]+\.[0-9]+|sha-[0-9a-f]{12}|[a-z0-9][a-z0-9._-]{0,63})$'

DRY_RUN="${DRY_RUN:-0}"
STEP_NO=0

# Đúng mẫu tag hợp đồng §2 (release, sha-<12>, hoặc nhánh tự do cho diễn tập).
validate_tag() {
  [[ "$1" =~ $APPBACK_TAG_RE ]]
}

# Chạy lệnh thật; ở chế độ dry-run chỉ in bước đánh số kèm lệnh, không chạy.
run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    STEP_NO=$((STEP_NO + 1))
    printf '%d. %s\n' "$STEP_NO" "$*"
    return 0
  fi
  "$@"
}

# In một dòng kế hoạch không gắn với lệnh docker cụ thể (vd "chờ healthy").
plan() {
  if [[ "$DRY_RUN" == "1" ]]; then
    STEP_NO=$((STEP_NO + 1))
    printf '%d. %s\n' "$STEP_NO" "$*"
  fi
}

# Chờ một container cụ thể (id "$1") thành "healthy" tới APPBACK_HEALTH_TIMEOUT_S
# (docker inspect, mỗi APPBACK_HEALTH_POLL_S giây). Dùng chung cho swap_api (chờ
# container mới của một service đang chạy 2 bản) và wait_healthy (chờ container
# duy nhất của một service, sau restore.sh) — R-07, trước đây restore.sh tự chép
# vòng lặp này.
wait_container_healthy() {
  local cid="$1" elapsed=0 status
  while :; do
    status="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && return 0
    if (( elapsed >= APPBACK_HEALTH_TIMEOUT_S )); then
      return 1
    fi
    sleep "$APPBACK_HEALTH_POLL_S"
    elapsed=$((elapsed + APPBACK_HEALTH_POLL_S))
  done
}

# Chờ container hiện tại (đúng một bản) của dịch vụ compose "$1" thành healthy.
wait_healthy() {
  local service="$1" cid
  cid="$(docker compose ps -q "$service")"
  if ! wait_container_healthy "$cid"; then
    echo "loi: $service khong healthy sau ${APPBACK_HEALTH_TIMEOUT_S}s" >&2
    return 1
  fi
}

# Đổi container api không gián đoạn: scale 2 → chờ mới healthy → xoá cũ → scale 1
# (thiết kế 6 bước đã chốt, hop-dong.md §2). Thoát khác 0 nếu không healthy tới
# timeout; khi đó KHÔNG dừng container cũ, container mới bị xoá.
swap_api() {
  local tag="$1"
  export IMAGE_TAG="$tag"
  if [[ "$DRY_RUN" == "1" ]]; then
    run docker compose up -d --no-deps --no-recreate --scale api=2 api
    plan "chờ container api mới healthy (timeout ${APPBACK_HEALTH_TIMEOUT_S}s)"
    plan "chờ nginx tự dịch lại DNS (${APPBACK_API_SWAP_SETTLE_S}s)"
    plan "xoá container api cũ, trả về scale api=1"
    return 0
  fi
  local old_ids new_ids new_id id
  old_ids="$(docker compose ps -q api)"
  docker compose up -d --no-deps --no-recreate --scale api=2 api
  new_ids="$(docker compose ps -q api)"
  new_id=""
  for id in $new_ids; do
    case " $old_ids " in
      *" $id "*) ;;
      *) new_id="$id" ;;
    esac
  done
  if [[ -z "$new_id" ]]; then
    # `--no-recreate --scale api=2` không tạo container mới nào (vd đã có 2 bản từ trước) —
    # không có gì để chờ healthy; hỏng ngay thay vì quay đủ APPBACK_HEALTH_TIMEOUT_S rồi mới
    # báo (review round 1 P3 RES-01).
    echo "loi: swap_api không tạo được container api mới (--scale api=2 không thêm bản nào)" >&2
    return 1
  fi
  if ! wait_container_healthy "$new_id"; then
    docker rm -f "$new_id" >/dev/null 2>&1 || true
    return 1
  fi
  # Chờ nginx tự dịch lại "api" trước khi xoá container cũ — không chờ thì nginx còn giữ
  # cache DNS trỏ container cũ, dừng nó gây 502/refused thật cho request đang tới dù thiết
  # kế 6 bước (hop-dong.md §2) đã đúng thứ tự. Mặc định và ràng buộc: xem khai báo đầu file.
  sleep "$APPBACK_API_SWAP_SETTLE_S"
  for id in $old_ids; do
    docker stop -t 30 "$id"
    docker rm "$id"
  done
  docker compose up -d --no-deps --no-recreate --scale api=1 api
}

# Đổi worker/beat thường (acks_late giao lại task đang chạy — không cần đổi kiểu blue/green).
swap_workers() {
  local tag="$1"
  export IMAGE_TAG="$tag"
  run docker compose up -d --no-deps worker beat
}

# Gọi smoke.sh cạnh script này với $APPBACK_BASE_URL; chỉ in kế hoạch ở dry-run.
run_smoke() {
  if [[ "$DRY_RUN" == "1" ]]; then
    plan "smoke: smoke.sh $APPBACK_BASE_URL"
    return 0
  fi
  bash "$LIB_DIR/smoke.sh" "$APPBACK_BASE_URL"
}

# Đọc $APPBACK_DIR/<tên tệp trạng thái>; rỗng nếu chưa có. Luôn thoát 0 (an
# toàn dưới set -e khi gọi trong $(...)).
read_state() {
  local f="$APPBACK_DIR/$1"
  [[ -f "$f" ]] && cat "$f"
  return 0
}

# Ghi giá trị vào $APPBACK_DIR/<tên tệp trạng thái>.
write_state() {
  printf '%s' "$2" > "$APPBACK_DIR/$1"
}
