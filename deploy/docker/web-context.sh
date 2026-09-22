#!/usr/bin/env bash
# Xuất AppFront tại <sha> ra thư mục build-context "appfront" cho web.Dockerfile
# (docker build --build-context appfront=<thu-muc-dich>).
# Giải vào thư mục tạm rồi mv nguyên khối, tránh để lại bản dở nếu bị ngắt giữa chừng.
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: web-context.sh <sha> <thu-muc-dich>" >&2
  exit 1
fi

sha="$1"
dest="$2"

if [ -e "$dest" ]; then
  echo "web-context.sh: thư mục đích đã tồn tại: $dest" >&2
  exit 1
fi

repo="${APPFRONT_REPO:-F:/AppFront}"
dest_parent="$(dirname "$dest")"
mkdir -p "$dest_parent"

tmp="$(mktemp -d "$dest_parent/.web-context-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

git -c core.autocrlf=false -c core.eol=lf -C "$repo" archive "$sha" | tar -x -C "$tmp"

mv "$tmp" "$dest"
trap - EXIT
