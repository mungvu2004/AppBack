# FE3D-B5 · Tường AI cao theo chiều cao tầng (FE3D-FIX-003)

- `apps/worker/pipeline_persist/merge.py`: thêm `with_floor_height(ai, height_mm)`. Tường AI đang mang chiều cao giữ chỗ `DEFAULT_WALL_HEIGHT_MM` (3600, B5-05 dựng không có DB) lấy `floors.height_mm`; tường có chiều cao khác (lan can, tường thấp) giữ nguyên.
- `apps/worker/pipeline_persist/context.py`: `PersistContext.floor_height_mm` đọc `floors.height_mm` (NOT NULL, 2000-10000); `service._write_ai_layer` dùng bản đọc dưới khoá tầng.
- Mục người duyệt/người vẽ không đổi (chỉ lớp AI qua `with_floor_height` trước `make_merge`).
- Test: `tests/test_merge.py` (lan can giữ, tường 3600 → 2700), `tests/test_persist_rules.py` (tầng 2700 mm, persist thật trên Postgres); helpers nhận `floor_height_mm`.
- Không endpoint, không bảng, không migration, không mã lỗi mới, không đổi `openapi.json`.
