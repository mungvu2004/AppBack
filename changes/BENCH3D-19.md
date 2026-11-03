# BENCH3D-19 — chặn ảnh phối cảnh 3D theo hướng nét tường

- `apps/worker/pipeline_quality/checks.py` `axis_share` / `not_a_floor_plan`: phần tổng dài tường nằm trong ±4° của cặp họ hướng vuông góc tốt nhất (mod 90°) < `MIN_AXIS_SHARE` (0,65) → không phải mặt bằng.
- `apps/worker/pipeline_build/tasks.py` `_build_and_write`: gọi ngay sau `build_layer`, trước khi ghi `layer.json` → `PermanentError(NOT_A_FLOOR_PLAN)` (mã sẵn có, FE có câu báo), tầng giữ lớp cũ; log `axis_share`.
- Bench-3d (r4b + tập F): chặn 4/4 ảnh 3D (0,47–0,60), 0 chặn nhầm (mặt bằng A ≥ 0,985; thấp nhất hợp lệ e-sun-2 0,687).
- Không đổi hợp đồng/openapi, không migration.
