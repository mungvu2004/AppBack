# FIX-P0-11 (B4-02): loại thông báo `aiFailed`

- `packages/db/models/notifications.py`: `NotificationKind` thêm `"aiFailed"` (cuối tuple, CHECK dựng theo thứ tự này).
- Revision contract mới `packages/db/migrations/versions/r20261026_b4_02_p0_11_ai_failed_kind.py`
  (`r20261026_b4_02_p0_11`, down `r20261026_b5_06a_p0_08`): drop + create `ck_notifications_kind` có `'aiFailed'`;
  downgrade xoá dòng `kind='aiFailed'` rồi dựng lại CHECK ba loại.
- **Người điều phối phải đăng ký `r20261026_b4_02_p0_11` vào `docs/contracts.toml`**, nếu không `lint_migrations` báo
  "# contract: chưa đăng ký" và chặn `drop_constraint`.
- `apps/api/notifications/messages.py`: `ai_failed(project_name)` → "Dự án X: AI chưa xử lý được bản vẽ". Lệch hợp đồng
  (hợp đồng ghi `ai_failed(project_name, floor_name)`): FE nối `objectLabel` (tên tầng) ngay sau câu, giống `ai_completed`,
  nên câu không nêu tầng; hiển thị vẫn là "… bản vẽ <tầng>". Người gọi duy nhất là `runs.py` (cùng agent).
- Test: `test_messages__ai_failed`, câu `ai_failed` thêm vào `test_messages__no_sentence_ends_with_a_label`;
  `test_notify__ai_failed_kind_is_stored` (đỏ trước revision vì CHECK).
- `apps/api/me/schemas.py` dùng `NotificationKind` nên tự nhận `aiFailed` (OpenAPI đổi enum → kiểm hợp đồng FE bước 7,
  cần FIX-P0-03 + APPFRONT_SHA). Docstring ở `me/schemas.py:55` còn liệt kê ba loại (không phải tệp của G).
