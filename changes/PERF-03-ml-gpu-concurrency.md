# PERF-03 — fix/perf-03-ml-gpu-concurrency: số tiến trình `ml` đọc lúc chạy, `ml-train` chạy CPU

- `deploy/compose/base.yml`: lệnh `ml` bỏ `--concurrency ${ML_INFER_CONCURRENCY:-3}` (nội suy lúc compose, nên `ML_INFER_CONCURRENCY` đặt trong `environment:` của override không có tác dụng); thêm `ML_INFER_CONCURRENCY: ${ML_INFER_CONCURRENCY:-3}` vào `environment:`.
- `apps/ml/celery_main.py` + `apps/ml/runtime/settings.py`: `app.conf.worker_concurrency = ML_INFER_CONCURRENCY` (mặc định 3, 1–64). `--concurrency 1` ở lệnh `ml-train`/`ml-gpu` vẫn thắng.
- VRAM: `ml-train` đặt `ML_DEVICE=cpu` ở dev/ci/prod — suy luận GPU của `ml` đã chiếm 5,8/6,1 GB trên RTX 4050; huấn luyện GPU chỉ qua `ml-gpu`. Không giới hạn arena ORT (`gpu_mem_limit`): với 2–3 tiến trình suy luận vẫn vừa; cần thì đặt `ML_INFER_CONCURRENCY=2` trên GPU 6 GB.
- Test: `deploy/tests/test_compose.py` (ml không ghi cứng concurrency, ml-train cpu), `apps/ml/runtime/tests/test_celery_main.py` (đọc biến lúc chạy, mặc định 3).
