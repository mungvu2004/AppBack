# FIX-P0-12 (B2-04): lượt chạy hỏng báo người tải lên

- `apps/api/drawings/runs.py`: `_settle` nhận thêm `clock` (hai người gọi `record_step` và `_abandon` đều có sẵn).
  Lượt `failed` với mã ngoài {`PIPELINE_SUPERSEDED`, `FLOOR_DELETED`} → `_notify_failed`: một câu đọc
  `uploads.created_by`, `projects.name`, `floors.name`; còn là thành viên (`is_member`) thì
  `notify(kind="aiFailed", place="floors", floor_level_id=…, object_label=<tên tầng>, dedupe_key="aiFailed:<run>:<uploader>")`.
- Lượt bị thay đi qua `_supersede_live_runs` (UPDATE thẳng, không qua `_settle`) nên vốn không báo; tập loại trừ vẫn giữ mã đó.
- `fail_run(PIPELINE_STALLED)` của lõi quét bù giờ cũng sinh thông báo; test ngoài `test_runs.py` đếm thông báo/câu truy vấn
  sau quét bù có thể cần xem lại khi chạy gate.
- Test (`apps/api/drawings/tests/test_runs.py`): `test_record_step_failed_notifies_uploader`,
  `test_fail_run_stalled_notifies_uploader`, `test_failed_twice_notifies_once`, `test_superseded_does_not_notify`,
  `test_floor_deleted_does_not_notify`, `test_uploader_left_project_not_notified`.
- Phụ thuộc FIX-P0-11 (CHECK `kind`).
