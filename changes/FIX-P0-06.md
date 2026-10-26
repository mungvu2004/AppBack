# FIX-P0-06 (a, b, c) — writer suy cờ `edited`, co giãn hết khi tỉ lệ cũ là tạm, trộn kích thước

- (a) `apps/api/spatial_write/writer.py`: người ghi ≠ `SYSTEM_PIPELINE` → `mark_edited(current.layer, body.layer)` trong `_next_layer` và `mark_edited_dimensions(current.dimensions, body.dimensions)` trong `_next_dimensions`, **trước** co giãn (so ở tỉ lệ cũ, co giãn không tính là sửa). H1 §2.3.
- (b) `_Scale.include_reviewed = scale_status(current.scale_source) == "unresolved"` (`pipeline`, `project_default`); truyền vào mọi lần `rescale_unreviewed`/`rescale_dimensions` (nền, lớp gửi, kích thước gửi). Tỉ lệ cũ `human`/`none` giữ luật cũ. H4.
- (c) Nhánh `merge`: `merge_dimensions(nền đã co giãn, kích thước AI đã đưa về tỉ lệ đích, id_map)` rồi `_drop_missing_refs`; bỏ `_remap_refs` (merge_dimensions tự ánh xạ). Nhánh người ghi giữ nguyên. Chữ ký callback merge không đổi. H3.
- Lệch hành vi đáng chú ý: tường AI **mới** do người gửi lên (id chưa có) được đánh `edited` ngay lượt ghi đầu (luật `prev is None` của H1).
- Test: `test_writer.py` (3 ca H1), `test_writer_scale.py` (3 ca H4 + 2 ca H3), `test_routes.py::test_spatial_write_layer__C01_edited`. `test_scale_rescales_only_unreviewed_entities` giữ nguyên.
- Phụ thuộc: FIX-P0-04 (`mark_edited*`, `include_reviewed`), FIX-P0-05b (`merge_dimensions` xuất qua `packages.domain.rules_ai`).
