# Review merge fix/debt-01-deploy → main (lượt 2)

- Ngày: 2026-09-24 · Reviewer: phiên /merge-review độc lập · Commit đầu nhánh: `c2f3c72` (detached trong worktree `review-debt-01-deploy`, `git status --porcelain` rỗng trước và sau)
- Lượt 1: `docs/reviews/2026-09-24-fix-debt-01-deploy.md` (APPROVE WITH COMMENTS 4,45/5 trên `66ce4d7` = `3f2e14d` sau rebase). Phạm vi lượt này: `git diff 3f2e14d..c2f3c72` — 6 commit, 15 tệp, +278/−86 (logic < 400 dòng, không MNT-05).
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (log: `backend/dieu-phoi/chay/DEBT-01/r2r2-verify.log`, dòng `EXIT=0`); 3840 passed, 4 deselected.
- Độ phủ: tổng dòng 99,44 % · nhánh 98,34 % — `apps/ml/runtime` 99,65 % / 98,61 % · `packages/storage` 99,64 % / 98,31 % · tập tệp bị chạm 99,38 % / 96,88 %.

## Bảng cổng (E.10, từ mã thoát thật)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict | đạt |
| 4 | lint-imports | đạt |
| 5 | coverage run -m pytest → coverage_gate | đạt |
| 5b | pytest -m perf → case_gate | đạt (perf: 0 đơn vị bị chạm) |
| 6 | lint_migrations → migrate_check | đạt |
| 7 | H1 H3 H4 H5 | đạt (H4 "không áp dụng": B3-05 chưa hợp nhất — đúng BE-00 §12) |
| 8 | openapi | đạt |

## Kiểm độc lập

**Commit, chủ, trailer.** 6 commit đều `<type>(<scope>): …`, có `Prompt:` + `Fix:`, mỗi commit chỉ chạm tệp của một chủ:
`0e1e709`, `777f895`, `b77af7c` B0-08 (`deploy/compose/*`, `deploy/tests/*`) · `f672677` B0-10 (`deploy/scripts/README.md`) ·
`2739918` B0-04 (`packages/storage/*`, FIX-105 đã được đặt trước trên `main` `6219e31`) · `c2f3c72` B5-01 (`apps/ml/runtime/*`).
Không đụng tệp cấm, không `pragma`/`noqa` trần/`skip` mới (`noqa: S603` có mã và lý do). `changes/DEBT-01.md` có.

**(1) Luật khác origin BE-00 §8/K15 không yếu đi cho API.** `grep create_storage` ngoài test cho đúng 5 nơi gọi:
`apps/api/core/app.py:152` (`app.state.settings` = `CoreSettings` đã resolve ở `create_app`, dòng 204),
`apps/api/floors/jobs.py:186`, `apps/api/me/jobs.py:97`, `apps/api/projects/jobs.py:135` (cả ba `get_core_settings()`),
`apps/ml/runtime/tasks_util.py:77` (`None`). `LocalDiskStorage(`/`S3Storage(` chỉ được dựng trong `packages/storage/factory.py`;
`s3_public_endpoint` không được đọc ở nơi nào khác. Mọi đường API vẫn chạy `_check_public_origin` trước khi dựng kho, lifespan API
vẫn hỏng lúc khởi động (fail-fast như cũ). Test mới `test_create_storage_rejects_s3_on_the_app_origin[staging|production]`,
`…_accepts_s3_on_another_origin_in_production`, `…_lets_dev_share_the_origin` giữ đủ ba nhánh của luật cũ.
Còn một cửa hở về kiểu (finding #1).

**(2) `ml` không cần `SECRET_KEY`/`PUBLIC_BASE_URL`/`REDIS_CACHE_URL` ở mọi đường.** Grep `apps/ml/**` (ngoài test): không còn
`get_core_settings`/`CoreSettings`; `APP_ENV` qua `MlEnvSettings`. Gói `ml` nhập: `packages.core.{clock,errors,error_codes,ids}`
(không đọc cấu hình), `packages.messaging.*` (`MessagingSettings.redis_cache_url` tuỳ chọn; `ml` chỉ dùng `broker_redis_sync`,
`safe_redis` → `redis_broker_url`, không gọi `cache_redis*`), `packages.observability` (chỉ `METRICS_*`), `packages.storage`
(`packages/core/keys.py` chỉ bị gọi trong `LocalDiskStorage.signed_url`/`verify_token`, `ml` không gọi — và `ml` luôn `s3`).
`packages/mail/settings.py` (đọc `get_core_settings`) không nằm trong đồ thị nhập của `ml`. Đo trong container, môi trường
production không có `SECRET_KEY`, `SECRET_KEY_PREVIOUS`, `PUBLIC_BASE_URL`, `REDIS_CACHE_URL`, `DATABASE_URL`:
`import apps.ml.celery_main` (kéo theo `discover_submodules("apps.ml","tasks")`) + `MlEnvSettings()` → thoát 0.

**(3) `env_file` vs `environment:` ở `prod.yml`.** Biến `ml` đọc: `APP_ENV`, `REDIS_BROKER_URL`, `CELERY_VISIBILITY_TIMEOUT_S`,
`TASK_*`, `STREAM_MAXLEN`, `STORAGE_BACKEND`, `S3_*`, `ML_DEVICE` — đều ở `environment:` của `base.yml:196-210/223-234`
(nội suy từ `--env-file appback.env`, đè `env_file`); `ML_BACKEND`, `ML_MODELS_DIR`, `ML_ORT_THREADS`, `METRICS_*` — trong
`ml.env.example`, không trùng (`test_ml_env_example_holds_only_ml_knobs` chặn trùng và chặn biến cấm). Thiếu `ml.env`
(`required: false`) thì `ml` chạy mặc định an toàn (`onnx`, 4 luồng, exporter 9464). Test `test_compose_prod_image_naming_…`
nay khẳng định **đúng** `[appback.env]` cho dịch vụ ngoài ml (chặt hơn bản `any(...)` cũ), `test_compose_prod_ml_env_file_is_not_appback_env`
khẳng định đúng `[ml.env]` cho `ml`/`ml-gpu`.

**(4) Test đỏ → xanh** (`apps/ml/runtime/tests/test_tasks_util.py -k without_the_api_secrets`, log
`backend/dieu-phoi/chay/DEBT-01/r2r2-redgreen.log`):

| Mã | Kết quả |
|---|---|
| `c2f3c72` nguyên vẹn | 1 passed (RC 0) |
| `tasks_util.py` @ `3f2e14d`, storage mới | 1 failed — `ValidationError … CoreSettings` (RC 1) |
| `tasks_util.py` mới, `packages/storage/{factory,local,settings}.py` @ `3f2e14d` | 1 failed — `ValidationError … StorageSettings` (RC 1) |
| cả hai @ `3f2e14d` | 1 failed — `ValidationError … StorageSettings` (RC 1) |

Cả FIX-105 lẫn FIX-091 đều cần thiết; test bắt được mỗi nửa riêng. FIX-104: regex mới khớp `uv:0.9.30-python3.12-…`, ngưỡng 7 tầng giữ, bước 5 đạt.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | SEC-xx / R-17 | `create_storage(settings, core_settings: CoreSettings \| None, …)` cho phép **bỏ qua im lặng** luật khác origin BE-00 §8/K15 bằng cách truyền `None`. Hôm nay đúng (4 nơi gọi của API đều truyền `CoreSettings`, xem (1)), nhưng không có gì ngăn một job API mới truyền `None` — mypy không bắt, test hiện có không bắt, và với `s3` thì kho dựng xong ký URL bình thường (chỉ `local` từ chối `signed_url`). Trước FIX-105 luật nằm trong `StorageSettings` nên không có đường vòng. | `packages/storage/factory.py:50,57` | Hoặc tách hàm riêng cho tiến trình không ký URL (vd `create_unsigned_storage(settings, clock)` mà `S3Storage` cũng từ chối `signed_url`), để `create_storage` bắt buộc `CoreSettings`; hoặc tối thiểu thêm test tĩnh: mọi `create_storage(…, None, …)` chỉ được nằm dưới `apps/ml/`. |
| 2 | Nit | TEST-xx | `test_production_s3_loads_without_the_api_secrets` đặt `APP_ENV=production` và gỡ `SECRET_KEY` nhưng không còn `reset_settings_cache()`: nếu ai đó thêm lại `get_core_settings()` vào `StorageSettings`, test vẫn có thể xanh khi cache `CoreSettings` đã ấm từ test trước. Rủi ro thấp vì test tiến trình riêng `test_infer_context_builds_without_the_api_secrets` đã chặn đúng hồi quy này (đo ở bảng trên). | `packages/storage/tests/test_settings.py:71` | Gọi `reset_settings_cache()` trong test (hoặc chấp nhận, vì test subprocess đã phủ). |
| 3 | Nit | OPS-xx | Lệnh kiểm `ml.env` trong runbook chỉ grep `SECRET_KEY|DATABASE_URL|SMTP_|MAIL_|REDIS_CACHE_URL|PUBLIC_BASE_URL`, hẹp hơn danh sách cấm của chính mẫu (`POSTGRES_*`, `MINIO_ROOT_*`, `S3_ACCESS_KEY`/`S3_SECRET_KEY` chung). | `deploy/scripts/README.md:54` | Kiểm theo danh sách cho phép thay vì danh sách cấm: `grep -vE '^(#|$|ML_|METRICS_)' /etc/appback/ml.env` phải rỗng — khớp đúng luật của `test_ml_env_example_holds_only_ml_knobs`. |

Không có P0/P1/P2. Các finding lượt 1 đã thành NO-196…NO-201, không xét lại.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 (P3 #1) | 1,00 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #2) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (Nit #3) | 0,25 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |
| **Tổng** | **100 %** | | **4,75 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0/P1/P2, điểm 4,75 ≥ 4,0, cổng đầy đủ thoát 0, độ phủ mọi gói bị chạm ≥ 90 % cả dòng lẫn nhánh, test hồi quy đỏ trên
`3f2e14d` (cả hai nửa) và xanh trên `c2f3c72`. Luật khác origin vẫn chạy ở mọi đường API; `ml` không còn cần và không còn nhận
`SECRET_KEY`/`PUBLIC_BASE_URL`/`REDIS_CACHE_URL` — cả qua `environment:` (dev/ci/prod) lẫn qua `env_file` ở prod.

**NO-085 đóng được khi nhánh này vào `main`**: phần mã (FIX-089 `19648c3`, FIX-091 `f7abc9f` + `c2f3c72`, FIX-105 `2739918`) và
phần compose (FIX-086 `0e1e709`, `b77af7c`; runbook FIX-087 `f672677`) đều có, test chặn tái phát ở cả ba môi trường compose và
một test tiến trình riêng với môi trường `ml` production.

Nợ mới đề xuất người điều phối ghi vào `DEBT.md` (P3, không chặn): finding #1 (chủ B0-04, `packages/storage/factory.py`). Nit #2, #3 tuỳ chủ.
