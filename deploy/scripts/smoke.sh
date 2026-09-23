#!/usr/bin/env bash
# 5 kiểm smoke sau deploy/rollback (B0-10 [2]): /api/health, /api/ready 200;
# / 200 có header Content-Security-Policy; /draco/draco_decoder.wasm 200;
# /api/nope 404 thân JSON có khoá "code". Cách gọi: smoke.sh <base_url>.
# Tổng thời gian ≤ SMOKE_DEADLINE_S (mặc định 60, hợp đồng §2) — mỗi curl dùng
# --max-time bằng phần ngân sách còn lại (tối đa 10s/lần), không phải 10s cố định
# (review round 1 P3 RES-02: 10s cố định mỗi lần có thể đẩy tổng lên ~70s).
# In một dòng mỗi kiểm (đạt/hỏng). Mã thoát: 0 đạt hết; 1 có kiểm hỏng; 2 thiếu đối số.
set -euo pipefail

# Bỏ MSYS_NO_PATHCONV kế thừa từ script gọi (drill.sh/deploy.sh cần nó cho `docker
# run -v`): trên Git Bash, biến này khiến curl.exe (không phải chương trình MSYS)
# nhận thẳng đường POSIX của `-o`/`-D` mà không dịch, ghi hỏng (exit 23) dù server
# trả 200 thật — smoke.sh không gọi docker nên không cần biến này.
unset MSYS_NO_PATHCONV

base_url="${1:-}"
if [[ -z "$base_url" ]]; then
  echo "cách dùng: smoke.sh <base_url>" >&2
  exit 2
fi

SMOKE_DEADLINE_S="${SMOKE_DEADLINE_S:-60}"
deadline=$(( $(date +%s) + SMOKE_DEADLINE_S ))
failed=0
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

# Còn hạn tổng $SMOKE_DEADLINE_S không — hết thì in hỏng cho kiểm $1 và trả 1.
within_deadline() {
  if (( $(date +%s) >= deadline )); then
    echo "hỏng $1 (hết hạn ${SMOKE_DEADLINE_S}s)"
    return 1
  fi
  return 0
}

# Phần ngân sách còn lại cho MỘT lần curl: tối đa 10s, tối thiểu 1s (curl từ chối 0).
_max_time() {
  local remaining=$(( deadline - $(date +%s) ))
  (( remaining < 1 )) && remaining=1
  (( remaining > 10 )) && remaining=10
  printf '%s' "$remaining"
}

# Kiểm mã trạng thái HTTP của một đường dẫn khớp $2.
check_status() {
  local path="$1" want="$2" code
  within_deadline "$path" || { failed=1; return; }
  code="$(curl -sS --max-time "$(_max_time)" -o "$tmp_dir/body" -w '%{http_code}' "$base_url$path" || echo "000")"
  if [[ "$code" == "$want" ]]; then
    echo "đạt $path"
  else
    echo "hỏng $path (mã $code)"
    failed=1
  fi
}

check_status "/api/health" 200
check_status "/api/ready" 200

# / : 200 và có header Content-Security-Policy.
if within_deadline "/"; then
  code="$(curl -sS --max-time "$(_max_time)" -D "$tmp_dir/headers" -o "$tmp_dir/body" -w '%{http_code}' "$base_url/" || echo "000")"
  if [[ "$code" == "200" ]] && grep -qi '^content-security-policy:' "$tmp_dir/headers"; then
    echo "đạt /"
  else
    echo "hỏng / (mã $code hoặc thiếu Content-Security-Policy)"
    failed=1
  fi
else
  failed=1
fi

check_status "/draco/draco_decoder.wasm" 200

# /api/nope : 404, thân JSON có khoá "code".
if within_deadline "/api/nope"; then
  code="$(curl -sS --max-time "$(_max_time)" -o "$tmp_dir/body" -w '%{http_code}' "$base_url/api/nope" || echo "000")"
  if [[ "$code" == "404" ]] \
    && python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if "code" in d else 1)' "$tmp_dir/body" 2>/dev/null; then
    echo "đạt /api/nope"
  else
    echo "hỏng /api/nope (mã $code hoặc thân thiếu code)"
    failed=1
  fi
else
  failed=1
fi

exit "$failed"
