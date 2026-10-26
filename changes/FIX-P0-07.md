# FIX-P0-07 (B5-06b) — persist truyền bia mộ người xoá vào merge

- `apps/worker/pipeline_persist/merge.py`: `make_merge(ai, s_ai, removed=Removed())` truyền `removed` vào `merge_pipeline_result` ở cả hai nhánh (có/không co giãn).
- `service._persist`: `removed = await human_removals(db, floor_pk=ctx.floor_pk)` ngay đầu (đã dưới khoá `lock_run`, trước phiên bản "trước" và `_write_ai_layer`); `_write_ai_layer` nhận `removed`.
- Log `pipeline_suppressed_by_removal` {run_id, count} khi `MergeResult.suppressed_ids` khác rỗng: `WriteResult` không mang `MergeResult`, nên `_write_ai_layer` bọc hàm trộn (`merge_and_log`) để đọc `suppressed_ids` mà không sửa `writer.py`. Log phát lúc trộn, trước commit.
- Giao lặp (`replay`) không đổi.
- Test: `apps/worker/pipeline_persist/tests/test_persist_removals.py` (mới, 3 ca: `test_run_persist_suppresses_user_deleted_wall`, `test_run_persist_keeps_edited_unreviewed_wall`, `test_run_persist_keeps_overridden_dimension`) — tệp riêng vì `test_persist_rules.py` đã 605 dòng. `_restart` của `test_persist_rules.py` dời sang `helpers.restart_run` để dùng chung.
- e2e `tests/e2e/test_pipeline_e2e.py`: `test_rerun_after_edit_keeps_wall`, `test_rerun_after_delete_keeps_it_deleted`; tách `_put_body`/`_layer_body` dùng chung với `_review_first_wall`.
- Phụ thuộc: P0-04 (`edited`), P0-05 (`Removed`, `suppressed_ids`, merge_dimensions), P0-06 (`human_removals`, `mark_edited` trong writer).
