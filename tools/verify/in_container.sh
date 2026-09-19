#!/usr/bin/env bash
# Chạy TRONG container verify (ENTRYPOINT của verify.Dockerfile). Ba việc
# đúng B0-01 [6]C:
#   1. chép /src vào /tmp/w, chmod 644 (mount Windows để mode 777 giả);
#   2. uv sync --locked --all-packages --group dev;
#   3. exec Python của venv -m tools.verify.steps "$@".
# Riêng việc `lock`: chạy `uv lock` (không --upgrade) trước bước 2 — chưa có
# uv.lock thì `--locked` không chạy được; sync ngay sau đó kiểm lock cài được.
set -euo pipefail

# /tmp/w đã có sẵn (working_dir) → chép NỘI DUNG /src, không tạo /tmp/w/src
mkdir -p /tmp/w
cp -r /src/. /tmp/w/
find /tmp/w -type f -exec chmod 644 {} +
cd /tmp/w

if [[ "${1:-}" == "lock" ]]; then
  uv lock
fi
uv sync --locked --all-packages --group dev

# Gốc import = gốc repo ở mọi nơi chạy (BE-01 [5]); công cụ của venv trên PATH.
export PYTHONPATH=/tmp/w
export PATH="$UV_PROJECT_ENVIRONMENT/bin:$PATH"
exec "$UV_PROJECT_ENVIRONMENT/bin/python" -m tools.verify.steps "$@"
