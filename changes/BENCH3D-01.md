# BENCH3D-01 — kiểm hình học sau dựng bật cờ chất lượng nghiêm trọng

- Mới `apps/worker/pipeline_quality/checks.py`: `geometry_checks(layer)` thuần, năm mã `OPEN_ENVELOPE`, `WALL_FRAGMENTS`,
  `MULTIPLE_PLANS`, `ROOMS_WITHOUT_DOOR`, `ROOM_USAGE_UNKNOWN`; ngưỡng theo bộ chấm bench-3d (W1, W4), là hằng có tên.
- `quality.json` thêm khoá `checks`; tóm tắt `quality_summary` thêm `checks` (mã); mã `critical` bật `hasCritical` → lý do
  readiness `criticalIssues` sẵn có hiện ra. Không đổi hợp đồng API, DB, migration.
- Không đụng `check_integrity` (còn chặn lượt lưu của người dùng).
- `_clusters`/`_box_gap`/vùng U57 chuyển sang `apps/worker/pipeline_build/clusters.py`, bước dựng và bước kiểm dùng chung.
- Cổng áp dụng: lint/type, test `apps/worker/pipeline_quality`, `apps/worker/pipeline_build`. Migration/hợp đồng: không áp dụng.
