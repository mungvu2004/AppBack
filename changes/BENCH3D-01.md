# BENCH3D-01 — kiểm hình học sau dựng bật cờ chất lượng nghiêm trọng

- Mới `apps/worker/pipeline_quality/checks.py`: `geometry_checks(layer)` thuần, năm mã `OPEN_ENVELOPE`, `WALL_FRAGMENTS`,
  `MULTIPLE_PLANS`, `ROOMS_WITHOUT_DOOR`, `ROOM_USAGE_UNKNOWN`; ngưỡng theo bộ chấm bench-3d (W1, W4), là hằng có tên.
- `quality.json` thêm khoá `checks`; tóm tắt `quality_summary` thêm `checks` (mã); mã `critical` bật `hasCritical` → lý do
  readiness `criticalIssues` sẵn có hiện ra. Không đổi hợp đồng API, DB, migration.
- Không đụng `check_integrity` (còn chặn lượt lưu của người dùng). `OPEN_ENVELOPE` chỉ chặn khi ≥ 2 phòng rò hoặc
  phòng rò ≥ 6 m² (hộp kỹ thuật nhỏ lòi ra ngoài chỉ báo).
- Đầu vào lạ: `load_raster` đảo ảnh nền tối nét sáng (trung vị độ sáng < 128 **và** điểm ảnh sáng hơn nền rõ nhiều
  hơn điểm ảnh tối hơn nền rõ); ảnh chụp giấy trắng thiếu sáng (nền xám, nét đen) giữ nguyên. `load_raster` dùng chung
  nên nạp dữ liệu huấn luyện/đánh giá ML (`training_segformer`, `training_yolo`, `ml_eval`, `datasets_cubicasa`) cũng đảo.
- Review lượt 1 (2026-11-03): bỏ tự chọn trang PDF ở #7 (`pick_plan_page`). #7 không biết `pageIndex` 0 là người dùng
  chọn hay mặc định (thông tin chỉ có ở #5, giữ nó cần cột mới + migration), mà FE luôn bắt chọn trang cho PDF nhiều
  trang → ghi đè làm sai trang và lệch `crop`. Trang trong `uploads.page_index` luôn là trang client gửi; bench
  two-page-ch04 không gửi `pageIndex` vẫn dựng trang 0. `criticalCount` đếm cả kiểm hình học `critical`;
  `ROOMS_WITHOUT_DOOR` lọc phòng miễn trước khi xét "không ô mở".
- `_clusters`/`_box_gap`/vùng U57 chuyển sang `apps/worker/pipeline_build/clusters.py`, bước dựng và bước kiểm dùng chung.
- Cổng áp dụng: lint/type, test `apps/worker/pipeline_quality`, `apps/worker/pipeline_build`,
  `packages/vision/preprocess`, `apps/api/drawings`. Migration/hợp đồng: không áp dụng.
