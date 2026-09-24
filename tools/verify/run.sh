#!/usr/bin/env bash
# Lệnh cổng thật trên máy Windows (Git Bash). "just verify" trong mọi tài
# liệu nghĩa là `bash tools/verify/run.sh verify`. BE-01 [6]A.
#
# Việc: verify [--steps 1,2,4] | lock | openapi | merge-heads <tên> | shell | gc
set -euo pipefail
export MSYS_NO_PATHCONV=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

win_path() {
  if [[ "$(uname -s)" == MINGW* ]]; then
    (cd "$1" && pwd -W)
  else
    (cd "$1" && pwd)
  fi
}

VERIFY_TASK="${1:-verify}"
shift || true

# ---------------------------------------------------------------------------
# Chuẩn bị chung (verify, openapi, merge-heads, shell dùng chung — [2])
# ---------------------------------------------------------------------------

: "${VERIFY_NAME:=$(basename "$REPO_ROOT")}"
VERIFY_NAME="$(printf '%s' "$VERIFY_NAME" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_-' '-')"
export VERIFY_NAME

if [[ -n "${VERIFY_BRANCH:-}" ]]; then
  case "$VERIFY_BRANCH" in
    integration|worker) ;;
    *) echo "VERIFY_BRANCH='$VERIFY_BRANCH' không hợp lệ (integration|worker)" >&2; exit 1 ;;
  esac
else
  current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
  if [[ "$current_branch" == "main" ]]; then
    VERIFY_BRANCH="integration"
  else
    VERIFY_BRANCH="worker"
  fi
fi
export VERIFY_BRANCH

merge_base="$(git merge-base HEAD main 2>/dev/null || git rev-parse HEAD)"
VERIFY_CHANGED="$(
  { git diff --name-only "$merge_base" 2>/dev/null; git ls-files --others --exclude-standard; } \
    | sort -u
)"
export VERIFY_CHANGED

CACHE_DIR="$REPO_ROOT/.cache"
mkdir -p "$CACHE_DIR"

# Số log cổng tối đa trong .cache/src-out/verify sau một lượt, tính cả log của lượt đó: 20 lượt ≈ 0,5 MB lượt
# đạt, đủ so lượt đỏ với vài lượt trước nó; log cần giữ lâu hơn thì chép ra ngoài (NO-090).
VERIFY_LOG_KEEP=20

# AppFront @ APPFRONT_SHA — ENV §2 bước 3. Chưa có file SHA → thư mục rỗng.
APPFRONT_SHA_FILE="$REPO_ROOT/tools/contract/APPFRONT_SHA"
if [[ -f "$APPFRONT_SHA_FILE" ]]; then
  sha="$(tr -d '[:space:]' < "$APPFRONT_SHA_FILE")"
  appfront_cache="$CACHE_DIR/appfront/$sha"
  if [[ ! -d "$appfront_cache" ]]; then
    tmp_dir="$(mktemp -d)"
    git -c core.autocrlf=false -c core.eol=lf -C "${APPFRONT_REPO:-F:/AppFront}" archive "$sha" src package.json \
      | tar -x -C "$tmp_dir"
    mkdir -p "$(dirname "$appfront_cache")"
    mv "$tmp_dir" "$appfront_cache"
  fi
  VERIFY_APPFRONT_DIR="$(win_path "$appfront_cache")"
else
  empty_dir="$CACHE_DIR/appfront-empty"
  mkdir -p "$empty_dir"
  VERIFY_APPFRONT_DIR="$(win_path "$empty_dir")"
fi
export VERIFY_APPFRONT_DIR

mkdir -p "$REPO_ROOT/contract-samples"
VERIFY_SRC_DIR="$(win_path "$REPO_ROOT")"
VERIFY_CONTRACT_SAMPLES_DIR="$(win_path "$REPO_ROOT/contract-samples")"
export VERIFY_SRC_DIR VERIFY_CONTRACT_SAMPLES_DIR

COMPOSE=(docker compose -p "appback-verify-$VERIFY_NAME" -f "$VERIFY_SRC_DIR/deploy/compose/verify.yml")

run_container() {
  "${COMPOSE[@]}" run --rm --build "$@"
}

# ---------------------------------------------------------------------------
case "$VERIFY_TASK" in
  verify)
    # Log cổng ra host (NO-080): container tự xoá khi thoát, output chỉ đi qua client compose — shell
    # bọc bị cắt là mất bảng, file này thì còn. steps.py ghi song song stdout, không thay stdout.
    log_dir="$CACHE_DIR/src-out/verify"
    mkdir -p "$log_dir"
    # Trần log (NO-090): mỗi lượt một file, không dọn thì checkout sống lâu dồn mãi (in_container.sh còn chép
    # cả .cache mỗi lượt). Giữ VERIFY_LOG_KEEP - 1 log mới nhất (mtime) trước khi lượt này tạo log của nó.
    # Dọn là việc phụ (NO-092): log cũ đang bị giữ trên Windows ("Device or resource busy") làm `rm` hỏng,
    # file biến mất giữa lúc `find` đọc thư mục làm `find` hỏng — cảnh báo rồi vẫn chạy cổng.
    { find "$log_dir" -maxdepth 1 -type f -name '*.log' -printf '%T@\t%p\n' \
        | sort -rn | tail -n +"$VERIFY_LOG_KEEP" | cut -f2- | xargs -r -d '\n' rm --; } \
      || echo "dọn log cổng cũ hỏng — bỏ qua, cổng vẫn chạy" >&2
    log_name="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short=12 HEAD).log"
    echo "log cổng: $(win_path "$log_dir")/$log_name"
    run_container -v "$(win_path "$log_dir"):/src-out/verify" -e "VERIFY_LOG_FILE=/src-out/verify/$log_name" \
      verify verify "$@"
    ;;

  lock)
    out_dir="$CACHE_DIR/src-out/lock"
    mkdir -p "$out_dir"
    run_container -v "$(win_path "$out_dir"):/src-out/lock" verify lock "$@"
    cp "$out_dir/uv.lock" "$REPO_ROOT/uv.lock"
    echo "đã chép $out_dir/uv.lock -> $REPO_ROOT/uv.lock"
    ;;

  openapi)
    out_dir="$CACHE_DIR/src-out/openapi"
    mkdir -p "$out_dir"
    run_container -v "$(win_path "$out_dir"):/src-out/openapi" verify openapi "$@"
    echo "Xong. Chép kết quả:  cp $out_dir/openapi.json $REPO_ROOT/openapi.json"
    ;;

  merge-heads)
    name="${1:-}"
    if [[ -z "$name" ]]; then
      echo "merge-heads cần <tên> (r<yyyymmdd>_merge_w<nn>_<k>)" >&2
      exit 1
    fi
    out_dir="$CACHE_DIR/src-out/merge-heads"
    mkdir -p "$out_dir"
    run_container -v "$(win_path "$out_dir"):/src-out/merge-heads" verify merge-heads "$name"
    echo "Xong. Chép revision mới:  cp $out_dir/*.py $REPO_ROOT/packages/db/migrations/versions/"
    ;;

  shell)
    # có TTY → bash tương tác; không có (vd `run.sh shell <<< 'lệnh'`) → đọc lệnh từ stdin
    if [[ -t 0 ]]; then tty_flag=-it; else tty_flag=-T; fi
    run_container "$tty_flag" verify shell
    ;;

  gc)
    valid_names="$(
      git -C "$REPO_ROOT" worktree list --porcelain 2>/dev/null \
        | awk '/^worktree /{print $2}' \
        | xargs -n1 -r basename \
        | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9_\n-' '-' \
        | paste -sd, -
    )"
    VERIFY_VALID_NAMES="$valid_names" "${COMPOSE[@]}" run --rm --build \
      -e VERIFY_VALID_NAMES="$valid_names" verify gc
    ;;

  *)
    echo "việc lạ: $VERIFY_TASK (verify|lock|openapi|merge-heads|shell|gc)" >&2
    exit 1
    ;;
esac
