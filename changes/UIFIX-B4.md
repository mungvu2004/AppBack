# UIFIX-B4 · G4b-17 lưu lưới trục và gốc toạ độ

- #35 `PUT /api/projects/{p}/floors/{f}/spatial/layer` nhận thêm `body.axes` (thay nguyên danh sách, như `dimensions`) và `body.origin` `{x, y}` mm nguyên.
- Kiểm trục giống kích thước: `id` trùng → `VALIDATION`, `source:"ai"`+`reviewed:true` → `REVIEW_BY_AI_FORBIDDEN`, `levelId` khác tầng → `LAYER_LEVEL_MISMATCH`; duyệt trục mới cần `qc.approve`.
- `document_to_json` ghi trục thật và khoá `origin` (vắng khi chưa đặt); jsonb `floor_documents.document` chứa luôn, không migration.
- N16 trả `axes` + `origin`; N15 trả `graph.axes` gộp mọi tầng.
- Chưa làm: đổi tỉ lệ không tính lại trục; nhật ký `floor_change_log` không có dòng cho trục/gốc; snapshot phiên bản chưa chụp trục/gốc.
- Test: `apps/api/spatial_write/tests/test_routes_axes.py`, `apps/api/spatial_read/tests/test_codec.py::test_document_axes_and_origin_round_trip`.
