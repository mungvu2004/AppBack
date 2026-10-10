#!/usr/bin/env bash
# Chạy TRONG container verify (ENTRYPOINT của verify.Dockerfile). Ba việc
# đúng B0-01 [6]C:
#   1. giải nén nguồn vào /tmp/w (tar của run.sh, hoặc `cp -r /src` nếu thiếu), chmod 644;
#   2. uv sync --locked --all-packages --group dev;
#   3. exec Python của venv -m tools.verify.steps "$@".
# Riêng việc `lock`: chạy `uv lock` (không --upgrade) trước bước 2 — chưa có
# uv.lock thì `--locked` không chạy được; sync ngay sau đó kiểm lock cài được.
set -euo pipefail

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
find /tmp/w -type f -exec chmod 644 {} +
cd /tmp/w

if [[ "${1:-}" == "lock" ]]; then
  uv lock
fi
# PERF-01 B-pyc: biên dịch .pyc ngay lúc cài — venv mới không có bytecode thì mỗi tiến trình pytest tự
# biên dịch lúc import (collection 211 s ở worktree mới, 25 s khi ấm); `uv sync` làm một lần cho cả venv.
export UV_COMPILE_BYTECODE=1
uv sync --locked --all-packages --group dev

# Gốc import = gốc repo ở mọi nơi chạy (BE-01 [5]); công cụ của venv trên PATH.
export PYTHONPATH=/tmp/w
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"
exec "$UV_PROJECT_ENVIRONMENT/bin/python" -m tools.verify.steps "$@"
