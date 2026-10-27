#!/usr/bin/env bash
# Chạy TRONG container verify (ENTRYPOINT của verify.Dockerfile). Ba việc
# đúng B0-01 [6]C:
#   1. giải nén nguồn vào /tmp/w (tar của run.sh, hoặc `cp -r /src` nếu thiếu), chmod 644;
#   2. uv sync --locked --all-packages --group dev;
#   3. exec Python của venv -m tools.verify.steps "$@".
# Riêng việc `lock`: chạy `uv lock` (không --upgrade) trước bước 2 — chưa có
# uv.lock thì `--locked` không chạy được; sync ngay sau đó kiểm lock cài được.
set -euo pipefail
mark() { echo "[mốc] $(date +%s.%N) $*" >&2; }  # PERF-03: đo khởi động (cặp với run.sh)
mark "container bắt đầu"

# /tmp/w đã có sẵn (working_dir) → giải nén NỘI DUNG repo vào đó, không tạo /tmp/w/src
mkdir -p /tmp/w
# Nguồn tới bằng tar `run.sh` dựng trên host từ `git ls-files -co --exclude-standard` (PERF-01 BE-7):
# một lần đọc tuần tự 13 MB thay ~3.300 lần open qua mount Windows→WSL2 (`cp -r` đo 169 s nguội).
# Không có tar (ai gọi compose tay, không qua `run.sh`) → về `cp -r` của mount /src như trước.
if [[ -f /src-tar/src.tar ]]; then
  tar -xf /src-tar/src.tar -C /tmp/w
else
  cp -r /src/. /tmp/w/
fi
mark "giải nén xong"
find /tmp/w -type f -exec chmod 644 {} +
mark "chmod xong"
cd /tmp/w

if [[ "${1:-}" == "lock" ]]; then
  uv lock
fi
# PERF-01 B-pyc: biên dịch .pyc ngay lúc cài — venv mới không có bytecode thì mỗi tiến trình pytest tự
# biên dịch lúc import (collection 211 s ở worktree mới, 25 s khi ấm); `uv sync` làm một lần cho cả venv.
export UV_COMPILE_BYTECODE=1
# PERF-03: venv dùng chung theo băm `uv.lock` + phiên bản uv, không theo tên worktree — worktree mới
# không còn cài lại cả venv (473 s đo 2026-10-27). Gói workspace cài editable trỏ `/tmp/w`, cùng đường ở mọi
# container. `flock`: hai lượt cùng băm (khác worktree) không `uv sync` chồng lên nhau; `touch` cho `gc`
# giữ các venv dùng gần nhất (`VENV_PREFIX` trong steps.py).
venv_key="$({ cat uv.lock; uv --version; } | sha256sum | cut -c1-16)"
export UV_PROJECT_ENVIRONMENT="/work/venv-lock-$venv_key"
# `uv sync` ấm vẫn ~35 s (biên dịch lại .pyc của 16.444 tệp). Đầu vào của sync là uv.lock + mọi
# pyproject.toml + phiên bản uv: trùng đúng lượt sync đạt gần nhất (dấu `.verify-synced`, ghi SAU khi
# sync đạt) thì kết quả `--locked` cũng y hệt — bỏ qua. Kiểm và sync cùng trong khoá.
sync_key="$({ cat uv.lock; uv --version; find . -name pyproject.toml -not -path '*/node_modules/*' -print0 | sort -z | xargs -0 sha256sum; } | sha256sum | cut -c1-16)"
exec 9> "/work/flock-venv-lock-$venv_key"
flock 9
if [[ "$(cat "$UV_PROJECT_ENVIRONMENT/.verify-synced" 2> /dev/null || true)" != "$sync_key" ]]; then
  uv sync --locked --all-packages --group dev
  echo "$sync_key" > "$UV_PROJECT_ENVIRONMENT/.verify-synced"
fi
# `shell` có thể `uv pip install` vào venv CHUNG: xoá dấu để lượt kế sync lại và gỡ gói lạ (review PERF-03 #1).
if [[ "${1:-}" == "shell" ]]; then
  rm -f "$UV_PROJECT_ENVIRONMENT/.verify-synced"
fi
flock -u 9
exec 9>&-
touch "$UV_PROJECT_ENVIRONMENT"
mark "uv sync xong"

# Gốc import = gốc repo ở mọi nơi chạy (BE-01 [5]); công cụ của venv trên PATH.
export PYTHONPATH=/tmp/w
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"

# Một cổng ĐẦY ĐỦ một lúc trên cả máy (ENV §4, GATE-LOCK): mỗi lượt ~8,4 GiB trong VM 12 GB, hai lượt chồng
# nhau từng làm OOM và treo Docker Desktop (2026-10-27). Khoá nằm trên volume `/work` mọi worktree dùng chung;
# fd 8 đi theo `exec` sang python và các worker pytest, nên khoá nhả khi lượt kết thúc — kể cả bị giết, không
# có khoá treo. `--fast` và `shell` nhẹ hơn nhiều, không xếp hàng.
if [[ "${1:-}" == "verify" && " $* " != *" --fast "* ]]; then
  exec 8> /work/gate-full.lock
  if ! flock -n 8; then
    echo "cổng đầy đủ: đang chờ lượt khác xong — $(cat /work/gate-full.owner 2> /dev/null || echo 'không rõ chủ')" >&2
    flock 8
  fi
  echo "${VERIFY_NAME:-?} từ $(date -u +%H:%M:%SZ)" > /work/gate-full.owner
  mark "giữ khoá cổng đầy đủ"
fi
exec "$UV_PROJECT_ENVIRONMENT/bin/python" -m tools.verify.steps "$@"
