# PERF-03 — perf/ml-workers (P2, P3, P20, P19)

- P2: dịch vụ `ml` chỉ nghe `ml.infer`, `--concurrency ${ML_INFER_CONCURRENCY:-3}` (3 tiến trình × `ML_ORT_THREADS=4` ≈ 12 nhân); dịch vụ mới `ml-train` (anchor của `ml` trong `base.yml`, khai ở dev/ci/prod, profile `ml`) nghe `ml.training`, concurrency 1, `ML_WARMUP=0`. Trước đây tường/YOLO/OCR một lần chạy xếp hàng nối tiếp và job huấn luyện (≤ 3600 s) chặn mọi upload. `ml-gpu` giữ cả hai hàng, concurrency 1 (một GPU 6 GB).
- P3: `apps/ml/warmup.py` — ở `worker_process_init` nạp mọi bản ghim có ONNX trong `ML_MODELS_DIR` qua `load_onnx` (cùng checksum → lượt thật trúng cache), chạy một lượt giả, dựng + chạy bộ dò OCR. Lỗi chỉ cảnh báo. `ML_WARMUP=0` tắt (fixture test đặt mặc định 0). `worker_proc_alive_timeout=300` để Celery không giết con đang làm ấm. Bản storage đang kích hoạt (ml không đọc DB) vẫn nạp ở lượt đầu.
- P20: healthcheck worker 30 s (ảnh 15 → 30 s; compose 10 → 30 s, `start_interval: 5s` trong `start_period: 60s`).
- P19: OCR bỏ lượt xoay 180° khi lượt thẳng tin cậy ≥ `UPRIGHT_SURE_CONFIDENCE` (0,9); dưới ngưỡng vẫn đọc cả hai, lấy lượt tốt hơn. Cần bench độ chính xác (như P18) để xác nhận ngưỡng.
- Test: `apps/ml/runtime/tests/test_warmup.py` (4), `test_best_skips_flip_when_upright_is_sure` trong `apps/ml/text/tests/test_reader.py`.
