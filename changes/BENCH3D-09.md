# BENCH3D-09 — hợp đồng FE–BE: thông thủy, geometrySuspect, readiness.checks, scaleBasis

- `packages/domain/spatial/area.py` `clear_area_m2`: đường bao tim tường lùi vào nửa bề dày tường nằm trên từng cạnh (song song ≤ ~5°, cách ≤ một bề dày, chồng dài nhất); cạnh không có tường → nửa bề dày trung vị của tầng. Làm tròn như `areaM2`.
- Sửa sau review (P1): gộp đỉnh thẳng hàng trước khi lùi; cạnh lùi lật chiều mà hai cạnh kề không song song thì bỏ và giao lại hai cạnh kề; bậc tim tường (cạnh kề song song) giữ. Không tính được → `None`, dây vắng khoá (FE dùng `areaM2`), không bao giờ 0 cho phòng có diện tích. Bench r3: phòng > 2 m² ra 0 từ 64/452 → 0/464; 2 phòng < 2 m² vắng khoá.
- `rooms[].clearAreaM2` chỉ ở phía đọc: `layer_out` tính cho N15, N16, phản hồi PUT #35, phiên bản; miền `Room` không có trường (thân PUT mang nó → 422, FE bỏ trước khi gửi).
- `pipeline_quality` ghi thêm vào `quality_summary`: `criticalChecks` (mã kiểm hình học critical) và `scaleBasis` + `scaleChecks` (khoá nghi vấn) đọc từ `layer.json` của lượt; tệp hỏng/vắng → bỏ hai khoá tỉ lệ + log `quality_layer_unreadable` (`run_id`, `code`), lượt vẫn xong.
- Readiness: kiểm hình học critical → lý do mới `geometrySuspect` + `readiness.checks` (thứ tự cố định, mã lạ đứng sau); `criticalIssues` chỉ còn cho lỗi toàn vẹn (lượt cũ chưa có `criticalChecks` giữ luật cũ).
- N16 thêm `scaleBasis` (`human` khi tỉ lệ người đặt còn hiệu lực, còn lại lấy gốc của lượt mới nhất); tỉ lệ `chain`/`paired` không nghi vấn `scaleChecks` → bỏ `scaleUnresolved` (`note` — một chữ OCR `TL 1:N` — vẫn báo, sửa sau review P2) (`scaleStatus` giữ nguyên).
- `pipeline_persist.service._read_built` → `read_built` (quality dùng lại).
- Hợp đồng/openapi: người điều phối cập nhật `openapi.json`, `docs/contracts/*`, `APPFRONT_SHA` khi gộp (FE nhận trước). Không migration.
