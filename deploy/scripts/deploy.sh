#!/usr/bin/env bash
# CD api/worker/beat lên $APPBACK_DIR (mặc định /opt/appback) bằng tag ảnh mới.
# Cách gọi: deploy.sh <tag> [--dry-run]. Thứ tự cố định (B0-10 [6]): pull → ghi
# previous_tag → migrate (ảnh mới) → đổi api không gián đoạn → đổi worker/beat →
# smoke → ghi current_tag; hỏng ở migrate thì dừng ngay, không đổi container;
# hỏng ở đổi api/smoke thì rollback về previous_tag. --dry-run chỉ in kế hoạch,
# không gọi docker, không ghi file trạng thái. Biến môi trường: hợp đồng B0-10 §1.
# Mã thoát: 0 đạt; 1 hỏng; 2 đối số sai.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=deploy/scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

tag="${1:-}"
[[ "${2:-}" == "--dry-run" ]] && DRY_RUN=1

if [[ -z "$tag" ]]; then
  echo "cách dùng: deploy.sh <tag> [--dry-run]" >&2
  exit 2
fi
if ! validate_tag "$tag"; then
  echo "tag không hợp lệ: $tag" >&2
  exit 2
fi

previous_tag=""
if [[ "$DRY_RUN" != "1" ]]; then
  previous_tag="$(read_state current_tag)"
fi

export IMAGE_TAG="$tag"
# --policy missing: tag bất biến (sha-.../v...) nên bỏ qua nếu đã có cục bộ — đúng cho ảnh
# đã build tại chỗ lúc kiểm không gián đoạn (vd IMAGE_TAG=ci2), không kéo lại từ registry.
run docker compose pull --policy missing
if [[ "$DRY_RUN" != "1" && -n "$previous_tag" ]]; then
  write_state previous_tag "$previous_tag"
fi

if ! run docker compose run --rm migrate; then
  echo "hỏng migrate — không đổi container" >&2
  exit 1
fi

if ! swap_api "$tag"; then
  echo "hỏng đổi api — container mới không healthy tới timeout" >&2
  if [[ -n "$previous_tag" ]]; then
    # bash <script>, không exec đường dẫn trực tiếp: container verify chmod 644 mọi
    # file khi chép từ mount Windows (ENV.md §2) — bit thực thi không đáng tin cậy.
    bash "$SCRIPT_DIR/rollback.sh" "$previous_tag" || true
  else
    echo "không có previous_tag — không tự rollback được" >&2
  fi
  exit 1
fi
swap_workers "$tag"

if ! run_smoke; then
  echo "hỏng smoke — rollback về previous_tag" >&2
  if [[ -n "$previous_tag" ]]; then
    bash "$SCRIPT_DIR/rollback.sh" "$previous_tag"
  else
    echo "không có previous_tag — không tự rollback được" >&2
  fi
  exit 1
fi

if [[ "$DRY_RUN" != "1" ]]; then
  write_state current_tag "$tag"
fi
exit 0
