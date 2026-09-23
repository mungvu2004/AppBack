#!/usr/bin/env bash
# Đưa api/worker/beat về tag trước, không gián đoạn như deploy.sh. KHÔNG migrate,
# không alembic downgrade (expand/contract bảo đảm bản cũ chạy trên lược đồ mới —
# BE-00 §6.1). Cách gọi: rollback.sh [<tag>] — thiếu thì đọc $APPBACK_DIR/previous_tag.
# Thứ tự: pull → đổi api → đổi worker/beat → smoke → ghi current_tag.
# Mã thoát: 0 đạt; 1 hỏng; 2 thiếu tag hoặc tag sai mẫu.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
# shellcheck source=deploy/scripts/lib.sh
source "$SCRIPT_DIR/lib.sh"

tag="${1:-}"
if [[ -z "$tag" ]]; then
  tag="$(read_state previous_tag)"
fi
if [[ -z "$tag" ]]; then
  echo "không có tag để rollback (thiếu đối số và previous_tag)" >&2
  exit 2
fi
if ! validate_tag "$tag"; then
  echo "tag không hợp lệ: $tag" >&2
  exit 2
fi

export IMAGE_TAG="$tag"
# --policy missing: tag bất biến, bỏ qua nếu ảnh đã có cục bộ (deploy.sh cùng lý do).
docker compose pull --policy missing

if ! swap_api "$tag"; then
  echo "hỏng rollback — container api mới không healthy tới timeout" >&2
  exit 1
fi
swap_workers "$tag"

if ! run_smoke; then
  echo "hỏng smoke sau rollback" >&2
  exit 1
fi

write_state current_tag "$tag"
exit 0
