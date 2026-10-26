# FIX-P0-06b — đọc "bia mộ" từ nhật ký thay đổi (B3-03, H2 Phase 0; phần (d) của FIX-P0-06)

- `apps/api/spatial_write/changes.py` thêm `human_removals(db, *, floor_pk) -> Removed`; nhập được từ worker (không fastapi).
- Truy vấn 1: `DISTINCT ON (entity_id)` dòng mới nhất mỗi id tường/phòng, giữ id mà dòng đó là `__deleted__` với `changed_by <> 'system:pipeline'` (xoá rồi ghi lại cùng id → không còn).
- Truy vấn 2: `DISTINCT ON (entity_id, field)` giá trị mới nhất `x`/`y` của `vertex_id(id, "start"|"end")` và `outline` của phòng (index `(floor_pk, entity_id, field, revision)`). Thiếu hình học → bỏ mục. Không lọc id còn sống (merge lọc).
- Lịch gộp chỉ xoá dòng bị dòng mới hơn cùng `(entity_id, field)` che, nên bia mộ sống qua gộp.
- Test (Postgres thật): `apps/api/spatial_write/tests/test_changes.py` — `test_human_removals_lists_user_deleted_wall`, `_ignores_pipeline_deletions`, `_ignores_restored_id`, `_survives_compaction`.
- `Removed` lấy từ `packages.domain.rules_ai` (FIX-P0-05, agent B).
