# FIX-P0-04 (B3-01) — cờ `edited` và co giãn gồm mục đã duyệt

- `Reviewed.edited: StrictBool = False` (mọi thực thể, kể cả `Dimension`). `False` thì vắng khoá khi dump (`exclude_if`, như `roofs` rỗng): jsonb và dây của tài liệu cũ không đổi; không nâng `DOCUMENT_SCHEMA_VERSION`.
- Mới `packages/domain/spatial/provenance.py`: `mark_edited(current, sent)`, `mark_edited_dimensions(current, sent)`, xuất qua `packages.domain.spatial`. Mục `ai` trong `sent`: `edited = sent.edited or prev is None or prev.edited or prev.source == "human" or id đổi trường theo dõi` (`diff_layers`, mục `vertex` quy về tường chủ qua `vertex_id`; kích thước so `value_mm`, `reference_ids`, `override_value_mm`). Mục `human` giữ nguyên.
- `rescale_unreviewed` / `rescale_dimensions` thêm keyword `include_reviewed: bool = False`; mặc định giữ luật K21 cũ.
- Test: `packages/domain/spatial/tests/test_provenance.py` (8 ca), `packages/domain/scale/tests/test_rescale.py` thêm `test_reviewed_entities_scale_when_include_reviewed`, `test_dimensions_include_reviewed_scale_line`.
- Lệch: tập trường kích thước chép lại từ `apps/api/spatial_write/writer.py` `_dimension_values` (miền không nhập được `apps`); `line` không tính là sửa.
- Chưa làm (người điều phối): `check-documents` trên seed + test giải mọi `versions.snapshot` (FIX.md luật 6); thêm `edited` vào HOP-DONG-MOI.
