# FIX-P0-05 (a, b) — merge giữ mục người đã sửa, không hồi sinh mục người đã xoá (B3-06)

- `packages/domain/rules_ai/merge.py`: `_keep_ids` giữ thêm mục `edited` (cùng phần ghim); `_check_preconditions` từ chối lớp AI có mục `edited=True` (`ValueError`, như `reviewed`).
- Thêm `Removed` (bia mộ tường `(id, đường tâm)` và phòng `(id, đường bao)`); `merge_pipeline_result(current, ai, removed=Removed())`. Bia mộ có id còn trong `current` bị bỏ qua.
- `_screen`: tường AI không trùng `K` mà trùng bia mộ theo `_same_run` (dùng lại `_WallMatcher` dựng trên đoạn bia mộ, lưới ô) → chặn; phòng AI trùng bia mộ theo luật `_RoomMatcher` → chặn. Mục bị chặn không có ánh xạ id. `_WallMatcher`/`_RoomMatcher` nay nhận cặp `(id, hình học)` và trả id.
- Nối lại: gỡ id tường bị chặn khỏi `wallIds` của phòng AI còn lại; bỏ ô mở AI trên tường bị chặn (gỡ khỏi `openingIds`); đồ AI trỏ phòng bị chặn → `roomId = None` (tránh tham chiếu treo).
- `MergeResult.suppressed_ids` (thứ tự `ai`, cũng nằm trong `dropped_ai_ids`). `ponytail:` ghi giới hạn: bia mộ không hết hạn khi đổi bản vẽ, toạ độ ở tỷ lệ lúc xoá.
- `__init__.py` xuất `Removed` và `merge_dimensions` (FIX-P0-05b).
- Test: 8 ca mới trong `tests/test_merge.py`; `tests/reference.py` (so mọi cặp) và `tests/test_random.py` nhận bia mộ, bản lưới phải bằng bản tham chiếu kể cả `suppressed_ids`; `builders.review` thêm `edited`.
