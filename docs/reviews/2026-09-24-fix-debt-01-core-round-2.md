# Review merge `fix/debt-01-core` → main — lượt 2

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` độc lập (worktree `review-debt-01-core`, detached) · Commit đầu nhánh: `b25530b450c8`
- Lượt 1: `docs/reviews/2026-09-24-fix-debt-01-core.md` — REQUEST CHANGES (finding 1, 2 là P1; 3, 4 là P2).
- Phạm vi lượt này: `git diff 99bc366..b25530b` — 2 commit, 5 file, +164/−23.
  - `917ce5a` fix(messaging) — B0-05 FIX-089: `messaging_env` đặt `METRICS_PORT=0`, receiver `worker_process_shutdown`, `metrics_port_for_process`.
  - `b25530b` fix(core) — B0-06 FIX-090: assert RED theo đúng chuỗi nhãn, kẹp nhãn `method`.
- Cổng: `bash tools/verify/run.sh verify` (một lượt, đầy đủ, reviewer tự chạy trên `b25530b`) — **mã thoát 0**
  (log: `backend/dieu-phoi/chay/DEBT-01/r3r2-verify-bg.log`; log cổng trong worktree
  `.cache/src-out/verify/20260924T133104Z-b25530b450c8.log`)
- Độ phủ (từ `coverage_gate` của cổng): **tổng dòng 99,07 % · nhánh 97,72 %**; tập file bị chạm dòng 99,38 % · nhánh 97,48 %.
  Khớp số tác giả báo (3792 passed, 99,07 % / 97,72 %), nhưng số trên là do reviewer đo lại.

## Bảng E.10 — từ mã thoát thật

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | 486 file |
| 4 | `lint-imports` | đạt | 9 kept, 0 broken |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 3792 passed, 4 deselected, 0 failed, 0 error, 773 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf 1 test; 25 thao tác, 3 cảnh báo BE-BIND có sẵn (`files_read_object`, `health_live`, `health_ready`) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, 1 head, 10/10 mục |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H4 "không áp dụng" đúng luật: B3-05 chưa hợp nhất |
| 8 | `openapi` | đạt | |

Mã thoát cổng: **0**.

### Độ phủ từng gói bị chạm (dòng / nhánh, cả hai ≥ 90 %)

| Gói | Dòng | Nhánh |
|---|---:|---:|
| `apps/api/auth` | 98,49 % | 91,91 % |
| `apps/api/core` | 99,47 % | 98,06 % |
| `apps/api/streams` | 100,00 % | 100,00 % |
| `apps/ml` | 100,00 % | 100,00 % |
| `apps/ml/runtime` | 99,65 % | 98,61 % |
| `packages/db` | 95,36 % | 95,54 % |
| `packages/messaging` | 100,00 % | 100,00 % |
| `packages/ml_contracts` | 99,91 % | 99,56 % |
| `packages/testing` | 99,18 % | 97,37 % |
| **Tổng** | **99,07 %** | **97,72 %** |

## Kiểm độc lập — từng finding lượt 1

Chạy trong container cổng (`run.sh shell`) trên bản chép `/tmp/w` của mã nhánh, hoàn nguyên **chỉ** file sản phẩm về `99bc366`
(worktree không bị sửa; `git status --porcelain` rỗng trước và sau).

| Lượt 1 | Kiểm | Đỏ trên `99bc366` | Xanh trên `b25530b` | Kết luận |
|---|---|---|---|---|
| **#1 P1** exporter rò vào pytest | `pytest packages/messaging/tests/test_tasks.py packages/messaging/tests/test_celery_app.py packages/observability/tests/test_exporter.py` với `packages/testing/fixtures/messaging.py` của `99bc366` | mã thoát **1**, 4 failed — gồm test mới `test_a_test_worker_leaves_no_metrics_exporter_in_the_pytest_process` và 3 test exporter nối sau nó | mã thoát 0, 85 passed; cổng đầy đủ không còn lỗi teardown nào ở `packages/observability/tests` | **đã giải**. Chặn ở hai đường: `METRICS_PORT=0` + xoá cache `ObservabilitySettings` hai đầu trong `messaging_env` (mà `celery_worker_factory` phụ thuộc qua `celery_test_app` — cả 3 nơi dùng factory đều đi qua), và receiver `worker_process_shutdown` cho con prefork thật. Đo trong venv: `solo.TaskPool.__init__` bắn `worker_process_init`, module `solo` không bắn `worker_process_shutdown` — docstring đúng. |
| **#2 P1** test RED phụ thuộc thứ tự | Cổng đầy đủ (thứ tự thật đã làm đỏ lượt 1) | lượt 1: 1 failed trong cổng đầy đủ | 0 failed trong cổng đầy đủ | **đã giải**. `_red_count` khẳng định đúng một dòng khớp **trọn** chuỗi nhãn `{route,method,status}`, nên chuỗi `POST 404 … 0.0` do module khác để lại không còn trùng; test 2 còn chặt thêm (`endswith(" 1.0")`). Không dựng lại cảnh đỏ riêng — cổng lượt 1 đã là cảnh đỏ. |
| **#3 P2** hai con prefork tranh một cổng | Mã + venv | — | 4 case tham số hoá xanh | **đã giải** theo đề xuất lượt 1 (cổng riêng từng con). Đo trong venv: `billiard.pool.Pool._create_worker_process` gán `w.index = i`; `celery.utils.log.current_process_index(base=0)` trả `None` ở tiến trình chính → cổng gốc. Phần scrape còn lại: finding R2-1. |
| **#4 P2** nhãn `method` không kẹp | Test mới `test_red_metric_folds_an_unknown_method_into_the_dash_label` với `apps/api/core/middleware.py` của `99bc366` | mã thoát **1**, `ValueError: giá trị nhãn sai (chuỗi ≤ 64 ký tự): 'XXXX…'` từ `_label_key` | xanh trong cổng | **đã giải**. Tập đóng 9 method RFC 9110 §9, còn lại về `-` — chặn luôn trục nở chuỗi nhãn, tốt hơn cắt bớt. |

- **K24**: `# type: ignore[attr-defined]` ở `packages/messaging/celery_app.py:19` có mã và lý do (celery-types thiếu `current_process_index`);
  mypy `--strict` của cổng xanh nên dòng ignore không thừa. Không `pragma`, `noqa` trần, `skip`/`xfail`, hạ ngưỡng.
- Không đụng file cấm (`docs/charter/*`, `openapi.json`, `uv.lock`, `pyproject.toml`, `DEBT.md`, `changes/*`). Không `conftest.py` lồng.
- Commit: dòng đầu đúng Conventional Commits (59 và 63 ký tự), đủ trailer `Prompt: B0-05`/`B0-06` + `Fix: FIX-089`/`FIX-090`.
  Chủ đúng: `packages/messaging/**`, `packages/testing/fixtures/messaging.py` → B0-05; `apps/api/core/**` → B0-06 (K27 ok).
- R-01/R-02: mọi hàm và hằng mới có docstring nêu lý do; test mới đặt tên theo hành vi.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| R2-1 | P3 | OBS-02 | Worker giờ phơi `/metrics` trên **dải** `METRICS_PORT … METRICS_PORT + WORKER_CONCURRENCY − 1` (mặc định 9464–9465), nhưng dòng NO-162 trong `DEBT.md` (chủ B0-08) chỉ ghi "trỏ `api:9464` (và worker/ml khi NO-161 xong)" — không nêu dải, mà `WORKER_CONCURRENCY` lại chỉnh được qua biến môi trường. Scrape tĩnh theo đúng chữ dòng nợ sẽ chỉ thu con số 0, tức lặp lại chính triệu chứng của finding 3 lượt 1 ở tầng thu thập. Docstring `metrics_port_for_process` có nói điều này, nhưng người làm NO-162 đọc dòng nợ chứ không đọc docstring. | `packages/messaging/celery_app.py:108-121` ↔ `deploy/compose/base.yml:155` ↔ `DEBT.md` NO-162 | Người điều phối sửa ô "Chữa" của NO-162: khai target `worker:9464 … 9464+WORKER_CONCURRENCY−1` (hoặc dò theo DNS/`file_sd`), kèm test compose buộc dải target khớp `--concurrency`. Không chặn merge. |
| R2-2 | Nit | CON-04 | `start_metrics_exporter` ghi đè `_exporter` mà không trả tham chiếu cũ: hai lượt `worker_process_init` trong **một** tiến trình với `METRICS_PORT > 0` tăng đếm lên 2, `stop_metrics_exporter` chỉ trả 1, server còn mở. Không tới được ở môi trường thật (prefork bắn một lần mỗi con; `ml` chạy prefork `--concurrency 1`), chỉ ở test — và `_stop_exporters` của test đã vòng `while` để dọn. | `packages/messaging/celery_app.py:140` | Tuỳ chọn: `if _exporter is not None: return` ở đầu receiver. Không cần dòng nợ. |

Finding 5–8 của lượt 1 vẫn đúng như đã ghi; ba cái cần nợ đã có dòng: NO-186 (finding 5), NO-187 (finding 6), NO-188 (finding 7).
Finding 8 (Nit, test chọc `_instance`) giữ nguyên, không cần nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---:|---:|---:|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 4 | 0,60 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 4 | 0,20 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,77 / 5** |

CON 4 vì NO-186/NO-187 (có từ lượt 1, đã có dòng nợ). OBS 4 vì R2-1. TEST từ 1 lên 5: hai test mới đỏ thật trên mã cũ, cổng đầy đủ không còn phụ thuộc thứ tự.

## Từng dòng nợ trong phạm vi — có đóng được khi merge không

| NO | Đóng được? | Lý do |
|---|---|---|
| NO-085 (phần mã) | **có** (phần mã) | Tiến trình `ml` chạy không cần `SECRET_KEY`/`PUBLIC_BASE_URL`/`REDIS_CACHE_URL` — lượt 1 đã dựng đỏ→xanh, lượt 2 không đụng. Cả dòng chỉ đóng khi `fix/debt-01-deploy` (gỡ ba biến khỏi `deploy/compose/base.yml` cho `ml`/`ml-gpu`) cũng đã vào `main`. |
| NO-097 | **có** | `apps/api/core/auth.py` hết khai riêng `Role`/`ROLES`. Gương thứ ba ở `packages/db` là NO-188 (Nit). |
| NO-104 | **có** | Thử lại có backoff, có trần, giữ `.part` + `os.replace`; 4 test không tải mạng. |
| NO-137 | **có** | `_grant_everything` trả `ProjectAccess` đúng kiểu. |
| NO-140 | **có** | Sửa gốc ở `_on_commit`; đỏ→xanh trên Postgres thật (lượt 1). |
| NO-151 | **có** | `legacy_responses=True` ghim tường minh; test khẳng định cả cờ lẫn `protocol == 3`. |
| NO-152 | **có** (mã) | Ngân sách thử lại theo vai + test đếm lượt trên Redis thật. Điều kiện khi đóng: sửa ô "Nguyên nhân gốc" (redis-py 8.1 trên đường `from_url` mặc định **0** lượt, không phải 10 — lượt 1 §Kiểm độc lập). |
| NO-156 | **có** | `StreamRoute` + `release_held`; đỏ→xanh (lượt 1). Phần `AsyncSession` là NO-186. |
| NO-157 | **có** | `event_id_key` công khai, bản chép ở `sse.py` đã xoá. |
| NO-159 | **có** | `api_env` **và** giờ cả `messaging_env` đặt `METRICS_PORT=0`, có test. |
| NO-160 | **có** | Metric RED theo route template; test hết phụ thuộc thứ tự, cổng đầy đủ xanh; nhãn `method` kẹp. |
| NO-161 | **có** | Exporter mở ở mỗi tiến trình con Celery, tắt ở `worker_process_shutdown`, không rò vào pytest, mỗi con một cổng. Việc scrape dải cổng thuộc NO-162 (xem R2-1). |

## PHÁN QUYẾT: APPROVE

Cả bốn finding chặn/nên sửa của lượt 1 đã được giải ở gốc và reviewer tự kiểm được: finding 1 và 4 dựng lại đỏ thật trên mã
`99bc366` (4 failed; `ValueError` từ `_label_key`) rồi xanh trên `b25530b`; finding 2 hết đỏ trong chính cổng đầy đủ đã làm nó đỏ
ở lượt 1; finding 3 sửa đúng hướng lượt 1 đề xuất, cơ chế chỉ số con của billiard đo trong venv. Cổng đầy đủ do reviewer chạy
**thoát 0**, độ phủ tổng 99,07 % / 97,72 % và mọi gói bị chạm ≥ 90 % cả dòng lẫn nhánh. Không P0/P1/P2, điểm 4,77.

Việc cho người điều phối (không chặn merge): sửa ô "Chữa" của NO-162 theo R2-1; sửa ô "Nguyên nhân gốc" của NO-152 khi đóng;
NO-085 chỉ đóng trọn sau khi nhánh deploy cũng đã merge.

Ghi chú vận hành: pane RUNNER của skill `runner-terminal` lưu handle theo `ORCA_TERMINAL_HANDLE`, nên hai reviewer con cùng
phiên điều phối **dùng chung một pane** — lệnh của reviewer này bị gõ vào stdin lượt verify của reviewer kia. Reviewer đã vô
hiệu hoá dòng lệnh xếp hàng (`r3r2-verify.log.cmd.sh` chỉ còn `echo`) và chạy cổng ở nền, log riêng `r3r2-verify-bg.log`.
