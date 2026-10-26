# FIX-P0-05b — trộn kích thước thay vì thay cả danh sách (B3-06, H3 Phase 0; phần (c) của FIX-P0-05)

- Mới `packages/domain/rules_ai/dimensions.py`: `merge_dimensions(current, ai, id_map) -> tuple[Dimension, ...]`, hàm thuần (K18).
- Giữ mục `reviewed or source=="human" or edited or override_value_mm is not None`; bỏ mục AI cũ còn lại.
- Mục AI mới: `reference_ids` ánh xạ qua `id_map`; bỏ nếu cùng tập `reference_ids` khác rỗng với mục giữ, hoặc hai đầu `line` trong `MATCH_TOLERANCE_MM` (`_near` của `merge.py`, xét cả hai chiều).
- Thứ tự: mục giữ (thứ tự cũ) rồi mục AI mới (thứ tự `ai`). `ponytail:` so `line` O(n·m), dựng lưới ô nếu chậm.
- Dòng xuất `merge_dimensions` trong `packages/domain/rules_ai/__init__.py` do FIX-P0-05 (agent B) thêm.
- Test: `packages/domain/rules_ai/tests/test_dimensions.py` (8 ca: override, người vẽ, `edited`, thay AI thường, trùng tham chiếu, trùng đường ±50 mm, `id_map`, thứ tự).
