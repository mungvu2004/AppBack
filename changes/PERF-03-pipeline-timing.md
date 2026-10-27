# PERF-03 — đo thời gian từng bước pipeline (P26) + cache trang ML (P21)

- P26: mỗi bước xong ghi một dòng log có cấu trúc `pipeline_step_timing` (`run_id`, `step`, `status`, `duration_ms`):
  ba bước ML ở `apps/ml/runtime/tasks_util.run_step`, `step_done` (mọi kết quả tới, gồm `spatialDataBuild`),
  task `pipeline.persist.run` (`step="persist"`) và `pipeline.quality.run` (`qualityCheck`). Không khoá kho, không bí mật.
- Không lưu duration vào DB: `pipeline_runs`/`run_pins` không có cột JSON tự do (`used`, `quality_summary` có hợp đồng riêng),
  thêm cột cần migration — chưa làm; log JSON đủ để đo (`grep pipeline_step_timing`).
- P21: `run_step` giữ LRU `PAGE_CACHE_SIZE=2` trang đã giải theo (kho, `page_key`, khổ) trong tiến trình; mảng cache chỉ-đọc,
  mỗi task nhận bản sao. Trước: 3 lần tải MinIO + `cv2.imdecode` mỗi lượt; sau: 1 lần khi ba task rơi cùng tiến trình.
- Fixture autouse `packages/testing/fixtures/ml_page_cache.py` xoá cache giữa các test.
- Không endpoint, không bảng, không migration mới.
