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

source "$(dirname "${BASH_SOURCE[0]}")/../../tools/verify/appfront_repo.sh"
repo="${APPFRONT_REPO:-$(appfront_repo_default "$(dirname "${BASH_SOURCE[0]}")")}"
dest_parent="$(dirname "$dest")"
mkdir -p "$dest_parent"

tmp="$(mktemp -d "$dest_parent/.web-context-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

git -c core.autocrlf=false -c core.eol=lf -C "$repo" archive "$sha" | tar -x -C "$tmp"

# Git LFS (AppFront từ 2026-10-24: khung hình /welcome ở public/landing-lab): `git archive` chỉ
# xuất con trỏ 3 dòng, không xuất nội dung. Lấy đối tượng còn thiếu rồi chép từ kho LFS cục bộ
# đè lên con trỏ; thiếu đối tượng thì hỏng ngay, đừng để ảnh web mang con trỏ thay hình.
if git -C "$repo" lfs version >/dev/null 2>&1; then
  lfs_list="$(git -C "$repo" lfs ls-files --long "$sha")"
  if [ -n "$lfs_list" ]; then
    git -C "$repo" lfs fetch origin "$sha" >/dev/null 2>&1 || true
    lfs_objects="$(git -C "$repo" rev-parse --path-format=absolute --git-common-dir)/lfs/objects"
    while read -r oid _ path; do
      obj="$lfs_objects/${oid:0:2}/${oid:2:2}/$oid"
      [ -f "$obj" ] || { echo "web-context.sh: thiếu đối tượng LFS $oid ($path)" >&2; exit 1; }
      cp "$obj" "$tmp/$path"
    done <<<"$lfs_list"
  fi
elif grep -q 'filter=lfs' "$tmp/.gitattributes" 2>/dev/null; then
  echo "web-context.sh: AppFront dùng Git LFS nhưng máy này chưa có git-lfs" >&2
  exit 1
fi

mv "$tmp" "$dest"
trap - EXIT
