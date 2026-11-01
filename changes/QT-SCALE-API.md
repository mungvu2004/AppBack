# QT-SCALE-API — hai route đọc gợi ý cho màn tỉ lệ

- `GET /projects/{pid}/floors/{fid}/dimension-strings` (N45): chữ toàn số (bỏ `.` `,` khoảng trắng) 300–30 000 mm trong `dimensionReading/text.json` của lượt `completed` mới nhất, kèm hộp px và hướng theo tỉ lệ cạnh hộp; không trả `span_px`.
- `GET /projects/{pid}/floors/{fid}/detected-geometry` (N46): điểm bắt (đầu đoạn + giao điểm, gộp < 3 px), bề dày tường median/p90, cửa `door`/`double_door`, phòng lớn nhất của lớp đã lưu (mm ÷ tỉ lệ tầng), hộp bao tường — đều theo px trang.
- Vì sao: D1 (lan2/giai-phap-phan4.md) — FE đặt tỉ lệ bằng một cú bấm trên dữ liệu đã dò thay vì kéo tay.
- Chưa có lượt, artifact vắng/hỏng → danh sách rỗng, trường `null` có khoá (không lỗi). Quyền: thành viên (như N16), `ETag` qua `cached_json`.
- Hợp đồng: BE-BIND N45/N46 + openapi; `APPFRONT_SHA` không đổi (FE chưa dùng). Không migration.
- Test: `apps/api/spatial_read/tests/test_routes_detected.py` C01/C06/C08/C17 cho cả hai op + 401.
