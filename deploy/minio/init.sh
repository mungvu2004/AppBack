#!/bin/sh
# Khởi tạo MinIO cho dev/ci/prod: bucket, người dùng và chính sách riêng của app
# (api/worker/beat/migrate — "khoá chung", không phải root) và ml.
# Idempotent — chạy lại nhiều lần không lỗi (kiểm chạy thật B0-08 #3).
# Ảnh minio/mc: sh = bash 5.1.8, không sed/grep/awk (đo thật 2026-09-22) — dùng
# ${var//…} của bash để thay giữ chỗ bucket trong *-policy.json.
set -eu

alias_name="local"

# Thay __BUCKET__ trong một mẫu chính sách (app-policy.json/ml-policy.json —
# hai mẫu đều là giữ chỗ, không phải chính sách MinIO đọc trực tiếp, review
# 2026-09-22 #9) bằng bucket thật, ghi ra /tmp. Dùng chung cho cả hai chính
# sách — không chép tay mã sinh hai lần (F3).
render_policy() {
  template="$1"
  dest="$2"
  content="$(cat "${template}")"
  printf '%s' "${content//__BUCKET__/${S3_BUCKET}}" >"${dest}"
}

# Gắn một chính sách vào user nếu chưa gắn (mc admin policy attach lỗi nếu gọi
# lại khi chính sách đã gắn — idempotent).
attach_policy_if_missing() {
  policy_name="$1"
  user="$2"
  attached="$(mc admin policy entities "${alias_name}" --user "${user}" 2>/dev/null || true)"
  case "${attached}" in
    *"${policy_name}"*) ;;
    *) mc admin policy attach "${alias_name}" "${policy_name}" --user "${user}" ;;
  esac
}

# In từng dòng một access key đang được gắn chính sách "$1".
#
# Ảnh minio/mc không có grep/sed/awk (đo thật 2026-09-22) nên phải tự đọc theo
# trạng thái. Định dạng đo thật của `mc admin policy entities --policy <p>`
# (mc RELEASE.2025-08-13, 2026-09-24) — không có mã màu, thụt bằng dấu cách:
#   Query time: 2026-09-24T04:15:19Z
#   Policy -> Entity Mappings:
#     Policy: app-policy
#       User Mappings:
#         newkeybbb
#         oldkeyaaa
# Chính sách chưa gắn ai thì lệnh chỉ in dòng "Query time:" và vẫn thoát 0.
users_with_policy() {
  mc admin policy entities "${alias_name}" --policy "$1" 2>/dev/null | {
    in_users=0
    while IFS= read -r line; do
      trimmed="${line#"${line%%[![:space:]]*}"}"
      case "${trimmed}" in
        "User Mappings:") in_users=1 ;;
        "" | "Query time:"* | "Policy:"* | *"Mappings:") in_users=0 ;;
        *) if [ "${in_users}" = 1 ]; then printf '%s\n' "${trimmed}"; fi ;;
      esac
    done
  }
}

# Gỡ mọi user còn giữ chính sách "$1" mà không phải access key hiện tại "$2".
#
# Xoay khoá (đổi S3_ACCESS_KEY / S3_ML_ACCESS_KEY) chỉ TẠO danh tính mới; danh
# tính cũ vẫn giữ nguyên chính sách và secret cũ vẫn đọc/ghi được bucket, tức là
# đổi khoá không thu hồi được gì (NO-096). `mc admin user remove` xoá cả danh
# tính lẫn mọi gắn kết chính sách của nó. Root (MINIO_ROOT_USER) không phải user
# IAM nên không bao giờ xuất hiện trong danh sách này.
revoke_stale_users() {
  policy_name="$1"
  keep="$2"
  for user in $(users_with_policy "${policy_name}"); do
    if [ "${user}" != "${keep}" ]; then
      mc admin user remove "${alias_name}" "${user}"
    fi
  done
}

mc alias set "${alias_name}" "${S3_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

mc mb --ignore-existing "${alias_name}/${S3_BUCKET}"

# MinIO ghi đè secret của user đã có (đo thật): gọi vô điều kiện để xoay khoá
# luôn có hiệu lực — nhánh kiểm-tồn-tại-rồi-bỏ-qua khiến đổi secret không bao
# giờ áp dụng (review 2026-09-22 #8; áp dụng như nhau cho khoá app, F3).
mc admin user add "${alias_name}" "${S3_ACCESS_KEY}" "${S3_SECRET_KEY}"
mc admin user add "${alias_name}" "${S3_ML_ACCESS_KEY}" "${S3_ML_SECRET_KEY}"

render_policy "/deploy/minio/app-policy.json" "/tmp/app-policy.json"
mc admin policy create "${alias_name}" app-policy "/tmp/app-policy.json"
attach_policy_if_missing app-policy "${S3_ACCESS_KEY}"
revoke_stale_users app-policy "${S3_ACCESS_KEY}"

render_policy "/deploy/minio/ml-policy.json" "/tmp/ml-policy.json"
mc admin policy create "${alias_name}" ml-policy "/tmp/ml-policy.json"
attach_policy_if_missing ml-policy "${S3_ML_ACCESS_KEY}"
revoke_stale_users ml-policy "${S3_ML_ACCESS_KEY}"

echo "minio-init: xong (bucket=${S3_BUCKET}, user_app=${S3_ACCESS_KEY}, user_ml=${S3_ML_ACCESS_KEY})"
