# PERF-03 — spatial-etag (P13, P14, P27)

- N15 `GET /api/projects/{id}/spatial`, N16 `.../floors/{f}/spatial/layer`, N18 `.../versions/{v}/snapshot`
  trả `Response` đã serialize một lần (`spatial_read/http_cache.cached_json`): bỏ bước FastAPI validate
  + serialize lại kiểu trả về. `response_model` khai ở decorator nên openapi không đổi.
- `ETag` yếu = blake2b của thân (không từ `revision`: thân N16/N15 còn mang tên tầng, bản vẽ ký,
  readiness — đổi mà `revision` không tăng). `If-None-Match` khớp → 304 không thân.
  `Cache-Control: private, no-cache`; trình duyệt tự gửi `If-None-Match` với `fetch` mặc định.
- nginx: location regex riêng nén `application/json` cho đúng ba route trên (lý do BREACH ghi
  trong `app_locations.conf`); `/api/projects` và auth vẫn không nén.
- Không làm: gộp đọc trùng `floors` ở N16 (đổi ngữ nghĩa test xoá-giữa-request), `model_construct`,
  `max-age=60` cho `/api/feature-flags` và `/api/library` (cache trình duyệt không khoá theo
  header `Authorization` → đổi người dùng cùng trình duyệt thấy dữ liệu cũ; cờ admin trễ 60 s).
