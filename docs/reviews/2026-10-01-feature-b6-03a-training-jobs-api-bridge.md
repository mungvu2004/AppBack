# Review merge feature/b6-03a-training-jobs-api-bridge → main

- Ngày: 2026-10-01 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `c8b69e67a331`
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1 — lượt 1 của nhánh đi review); không chạy lại, dùng
  log cổng đầy đủ của lớp gộp trên **đúng** sha `c8b69e67a331`:
  `backend/dieu-phoi/chay/B6-03a/M/gate-1.log` (log trong container:
  `/work/.cache/src-out/verify/20261001T135142Z-c8b69e67a331.log`), lệnh
  `bash tools/verify/run.sh verify`, **mã thoát 1** — hỏng ở bước 1, bước 2–8 `chưa chạy`.
- Độ phủ: **không đo** — bước 5 (`pytest -n` + `coverage_gate`) chưa chạy ở sha này. Không số nào
  được chép lại từ lượt khác (K25).

## Bảng cổng (E.10 — lấy từ mã thoát thật trong `M/gate-1.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | **hỏng** | 2 file cần format lại, 1221 file đã đúng |
| 2 | `ruff check` | chưa chạy | |
| 3 | `mypy --strict` | chưa chạy | |
| 4 | `lint-imports` | chưa chạy | |
| 5 | `pytest -n (cov)` → `coverage_gate` | chưa chạy | |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy | |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | chưa chạy | |
| 8 | `openapi` | chưa chạy | |

Mã thoát: **1**.

Lớp gộp đã chạy thêm một lượt ở sha sau (`M/gate-2.log`, sha khác — ngoài phạm vi phán quyết này):
bước 1 `đạt`, **bước 2 `ruff check` hỏng với 10 lỗi**. Cả 10 lỗi ấy có mặt nguyên vẹn ở
`c8b69e67a331` (đã đối chiếu từng `file:dòng` trong cây của sha này), nên chúng được tính vào lượt
review này.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | G-01, R-33 | Cổng đỏ ngay bước 1: `ruff format --check` đòi format lại 2 file. Bước 2–8 **chưa chạy**, nên ở sha này **không có bằng chứng** nào cho mypy, ranh giới nhập, test, độ phủ, `case_gate`, `migrate_check`, H1 golden, openapi. Thêm vào đó bước 2 có 10 lỗi `ruff check` (xem #2, #3). | `apps/worker/training_bridge/tasks.py:132,181,228`; `apps/worker/training_bridge/tests/test_jobs.py:136` (và các lời gọi `make_training_job` cùng khuôn ở 147/166/207/…) | `ruff format .` rồi chạy lại cổng **đầy đủ**; chỉ báo xong khi mã thoát 0 và bảng E.10 có cả 8 bước `đạt`. |
| 2 | **P1** | LOG-04, R-16 (BLE001) | `except Exception` nuốt **mọi** ngoại lệ, không phân biệt lỗi thử lại được với lỗi lập trình. Nặng nhất là `_claims_present`: bất cứ lỗi nào (thiếu `REDIS_BROKER_URL` ở tiến trình beat, `MessagingSettings` không dựng được, bug trong `zip(strict=True)`…) cũng thành `None` ⇒ **cả ba lịch** im lặng trả 0 mãi mãi, chỉ log `training_sweep_skipped` — job mất nhịp tim không bao giờ được chốt, artifact không bao giờ được dọn, mà log lại quy sai nguyên nhân cho Redis. Ngoại lệ gốc bị bỏ hẳn, không trường nào mang nó. Hai chỗ còn lại rollback đúng một job nhưng cũng mất nguyên nhân. `test_sweep_lost_training_jobs_rolls_back_one_job_when_arm_cancel_key_fails` ném `RuntimeError` và **khẳng định** nó bị nuốt — hành vi này là có chủ ý. | `apps/worker/training_bridge/jobs.py:79`, `:116`, `:203` | Bắt đúng tập lỗi phụ thuộc đã có trong repo: `except DEPENDENCY_ERRORS` (`packages/messaging/redis.py:69`) hoặc `redis.exceptions.RedisError`; lỗi khác để nổi lên (lịch hỏng to còn hơn hỏng im). Thêm `error=type(exc).__name__` vào `training_sweep_skipped` và hai log rollback. BLE001 khi đó tự hết, không cần `# noqa`. |
| 3 | P2 | MNT-01, K24 | Bảy lỗi `ruff check` còn lại: `RUF002` (dấu `×` nhập nhằng trong docstring); `I001` khối import chưa sắp; `RUF100` ba `# noqa` chỉ mã **không được bật** (`ANN401`, `SLF001` ×2) — ba chú thích ức chế vô nghĩa; `F401` import thừa. | `jobs.py:12`; `tests/test_finish.py:7`, `tests/test_jobs.py:8`; `tests/test_finish.py:57`, `tests/test_jobs.py:251`, `:378`; `tests/test_tasks.py:35` (`TrainingJobRow` nhập mà không dùng) | `ruff check --fix` lo 6/10; `RUF002` đổi `×` thành `x`; `BLE001` sửa theo #2. |
| 4 | P2 | R-34 | Nợ tác giả nêu trong báo cáo ("B6-03b khai lại `trained_version_id`, `cancel_key`, `claim_key`, `WEIGHTS_NAME_RE`") **không có dòng `NO-<nnn>` trong `DEBT.md`**. | `backend/dieu-phoi/chay/B6-03a/bao-cao-B6-03a.md:75-77` ⇄ `DEBT.md` (không dòng nào cho B6-03a/B6-03b) | Thêm một dòng `NO-<nnn>` (chủ: B6-03b, mức P3, trạng thái mở) trước khi gộp. Chủ `DEBT.md` ghi, không phải phiên review. |
| 5 | P2 | R-07, MNT-04 | Hai `open_storage` **khác nhau** trong cùng cặp module: `tasks.py:368` tự khai bản truyền `None` cho `CoreSettings` (bản chép từ `apps/worker/datasets/tasks.py:558`), còn `jobs.py:36` nhập bản của `apps.api.library.assets` (bản đọc `get_core_settings()`). Lịch `purge_training_job_artifacts` do đó kéo một phụ thuộc vào `apps.api.library` mà nó không cần, và hai đường chạm kho của chính module này cấu hình khác nhau — một bên đổi cài đặt là lệch âm thầm. | `apps/worker/training_bridge/jobs.py:36` vs `apps/worker/training_bridge/tasks.py:368` | `jobs.py` nhập `open_storage` từ `apps.worker.training_bridge.tasks` (nó đã nhập `arm_cancel_key` từ đó) và bỏ `from apps.api.library.assets import open_storage`. Bản chép thứ ba so với `datasets` là nợ của người khác → ghi `DEBT.md`. |
| 6 | P3 | R-24 | `arm_cancel_key` và `_claims_present` dựng client `safe_redis()` mỗi lượt gọi mà **không** `aclose()`; `service._arm_cancel_key` của cùng prompt thì đóng trong `finally`. Mỗi task/mỗi beat bỏ lại một pool. Khuôn cũ `apps/worker/datasets/tasks.py:522` cũng vậy → nợ sẵn có, nhưng nhánh này nhân nó lên tám điểm gọi. | `apps/worker/training_bridge/tasks.py:56`, `jobs.py:78` (so với `apps/api/admin_ml_jobs/service.py:204-208`) | Đóng client trong `finally` như bản API, hoặc ghi một dòng `DEBT.md` về vòng đời client `safe_redis()` của worker và chỉ rõ chủ. |
| 7 | P3 | LOG-02 | Trần điểm số đo chỉ kiểm **một lần trước** vòng lặp, nên một lô (tới 500 điểm, `MAX_METRIC_POINTS`) vẫn vượt `training_max_metric_points` rồi mới bị chặn ở lô sau. [6] nói "vượt trần điểm → bỏ, log". | `apps/worker/training_bridge/tasks.py:168` | So `(total or 0) + len(payload.points) > trần` thay vì `>= trần`, hoặc cắt lô tại trần. |
| 8 | Nit | R-02 | `_LOG_PARAM_MAX_CHARS` đặt tên như trần của **một tham số** nhưng dùng để cắt **cả câu** đã dựng. | `packages/messaging/payloads/training.py:89,155` | Đổi tên thành `_LOG_TEXT_MAX_CHARS`. |
| 9 | Nit | BE-00 §13.2 | Hai commit gộp nhánh con (`aca53fa`, `cb2351a`) có dòng đầu không theo Conventional Commits và không trailer `Prompt:`. Lần squash vào `main` xoá chúng, nên không chặn. | `aca53fa`, `cb2351a` | Không cần sửa; gộp vào `main` bằng squash như BE-00 §13.2. |

### Đã soát và **đạt** (không finding)

- **Hợp đồng dây ⇔ model ⇔ revision.** CHECK của `training_jobs` gương đủ mọi refine
  `TrainingJobSchema` (HOP-DONG-MOI §8 dòng 548): `result_succeeded`, `failure_code_failed`,
  `ended_finished`, `queued_not_started`, `started_present`, `ended_after_started`,
  `epochs_range`, `current_epoch_range`. Revision `r20261001_b6_03a` chép tay từng hằng, expand
  thuần, `down_revision = r20260930_b5_06a` (một head), thứ tự FK đúng, `downgrade` ngược lại.
  `training_jobs` khai trước `training_metrics`/`training_logs` và trước mọi bảng `model_*`
  (BE-00 §9); `_lock_job` luôn khoá job trước khi chạm bảng con hay registry.
- **N33** đúng thứ tự `422 (schema) → 422 TRAINING_BASE_MODEL_MISMATCH → 404 →
  DATASET_VERSION_NOT_READY → DATASET_FAMILY_MISMATCH`; `creator_id` từ `Principal` (K05);
  `send_task` qua `on_after_commit` (K17) — `test_ml_create_job__J09_rollback_leaves_no_message`
  đọc hàng Redis thật bằng `llen`.
- **N35** `FOR UPDATE`, `cancel_key` **trước** commit, Redis lỗi → 503 + rollback
  (`__C13_redis_down` dừng một container Redis riêng, job vẫn `running`), `cancelling|cancelled` →
  200 không tác dụng và **không** đặt lại TTL (`__C10_once` đo TTL trước/sau), `succeeded|failed`
  → 409 `TRAINING_JOB_NOT_CANCELLABLE`, `__C14_concurrent` đúng một dòng nhật ký.
- **N36/N37** đọc `status` job trước hàng; `_whole_steps` không cắt giữa một bước; `_held_step`
  giữ bước cuối khi job chưa kết thúc, hay đã kết thúc trong cửa sổ mà bước cuối thiếu `split`;
  `nextCursor` **vắng chỉ khi** quá cửa sổ muộn **và** hết hàng — bốn ca ở
  `test_progress.py:172-240` phủ đúng bốn nhánh của [8].
- **Cầu nối**: mỗi task một giao dịch + `FOR UPDATE`; `cancel_key` đặt trước mọi commit sang
  `failed|cancelled` và trên mọi thông điệp của job đã kết thúc (`_accept_progress` + bốn điểm gọi
  `arm_cancel_key`); M05 `recorded_at = min(gửi, now)`; J06 bằng `ON CONFLICT DO NOTHING` trên PK
  `(job_id, split, step)` và unique `(job_id, dedupe_sha)`; `stat` chạy **ngoài** giao dịch và
  `test_finish_does_not_hold_a_db_connection_while_statting_weights` đo `pool.checkedout() == 0`
  (K36 thật, không mock); `register_trained_version` → `request_evaluation` cùng giao dịch, không
  task nào tự `send_task`; `on_failed` chỉ log, không văn bản ngoại lệ thô, không thân payload.
- **`render_log`**: che `KHOÁ=giá trị` **trước** URL (nên cả cụm thành một `[biến môi trường]`),
  rồi `$VAR`/`%VAR%`, URL, đường Windows, POSIX, `~`; `code` không UPPER_SNAKE → `[mã]`; số thực
  dấu phẩy; cắt ≤ 2000; khoá lạ, khoá dạng chấm, thiếu/thừa tham số (trừ `line`) → `None`. Mười
  khoá và tập tham số khớp bảng BE-00 §9, câu viết thường (BE-00 §10), mỗi điểm có test khẳng định.
- **Lịch**: đọc `claim_key` bằng một `MGET` **trước** khi đổi job nào, lỗi → bỏ cả lượt; claim còn
  → `training_heartbeat_late`, không đổi; backoff `training_requeue_after_s × 2^requeue_count`
  (`updated_at` tự lên nhờ `onupdate` của `TimestampMixin`), trần 6 lượt gửi rồi
  `TRAINING_DISPATCH_STALLED`; purge chỉ `failed|cancelled`, **không** đụng `succeeded`,
  `delete_prefix` ngoài giao dịch, `UPDATE … WHERE artifacts_purged_at IS NULL` tự idempotent.
  NO-029 được tôn trọng: không dùng `SafeLock` cho claim theo job.
- **Ma trận [8] đủ.** Sáu `op` có đúng bộ case của Loại A (`ml_read_job` có cả sáu hậu tố trạng
  thái của C01), hai C10 riêng, năm task và ba lịch đều có `__J01` + `__J06`, ba lịch có test khói,
  `cases.toml` chỉ khai case J (`finish_training_job` J03/J09, `sweep_lost_training_jobs` J07 —
  NO-294). Dịch vụ thật khắp nơi: không `fakeredis`, không `task_always_eager`, không SQLite;
  `test_finish_training_job__J01_smoke` chạy `celery_worker_factory(["default"])` thật qua bốn
  payload B5-01; `_BlockingStatStorage` chỉ **bọc** `local_storage` thật (K23).
- **Một nguồn cài đặt** `TRAINING_*` ở `apps/api/admin_ml_jobs/settings.py`, worker chỉ xuất lại
  (`training_bridge/settings.py`) — đúng quyết định của điều phối. `MODEL_CHECKSUM_MISMATCH` lấy
  `.code` của registry. `arm_cancel_key` của cầu nối và `_arm_cancel_key` của API là hai lời gọi
  `safe_redis().set` riêng; API không nhập `apps.worker`, không ai nhập `apps.ml`.
- **[12] không bị chạm**: diff đúng 33 file trong `so_huu` (+ revision), không `conftest.py` lồng,
  không file cấu hình công cụ riêng, không `pragma: no cover`, không skip/xfail, mọi `# noqa` và
  `# type: ignore` đều có mã kèm lý do (K24) — ba cái bị `RUF100` là mã **không bật**, không trần.
- **Bảy mục "Lệch khỏi prompt"** của báo cáo đều **chấp nhận**, đã đối chiếu từng mục với mã: tên
  `CursorPage[…]`; `since`/`limit` khai tại chỗ; `CancelTrainingJobIn`; `safe_redis()` tại chỗ;
  `metrics == {}` thay bằng khoá họ khác (payload B5-01 `check_metrics` đòi đúng một khoá — đã đọc
  `packages/ml_contracts/payloads.py:281-304`, xác nhận không dựng được `{}`); hằng mã lỗi qua
  `errors.py`; không lệch tên.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 1 (P1 #2) | 0,15 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 4 (P3 #6) | 0,40 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 (P3: import thừa trong test; thiết kế test không finding) | 0,28 |
| OBS, OPS – Vận hành | 5% | 3 (P2: log bỏ nguyên nhân, xem #2) | 0,15 |
| MNT – Bảo trì | 3% | 3 (P2 #3, #4, #5) | 0,09 |
| **Tổng** | **100%** | | **4,07 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Phần nghiệp vụ của nhánh này rất chắc: mọi bất biến khó của [6] — thứ tự lỗi N33, `cancel_key`
trước commit ở N35 và ở bốn điểm của cầu nối, luật giữ bước cuối và cửa sổ muộn của N36/N37, K36
quanh `stat`, J06 bằng constraint thật, `render_log` che đủ bốn lớp dữ liệu — đều có mã đúng và có
test dịch vụ thật khẳng định. Nhưng nhánh **không vào `main` ở sha này** vì hai lý do P1: (a) cổng
đầy đủ thoát 1 ngay **bước 1**, nên bảy bước sau chưa chạy và ở sha này không tồn tại bằng chứng
nào về mypy, ranh giới nhập, test, độ phủ, `case_gate`, `migrate_check`, H1 hay openapi —
`RULE.md` §2 G-01/G-02 "fail thì không review"; (b) ba `except Exception` của `jobs.py` nuốt cả lỗi
lập trình, biến mọi sự cố không-Redis của beat thành ba lịch im lặng vô hiệu kèm một log quy sai
nguyên nhân (LOG-04, R-16) — và chính `ruff` cũng từ chối chúng.

Để được `APPROVE` ở lượt 2:

1. `ruff format .` (sửa `tasks.py:132,181,228` và khuôn `make_training_job` nhiều dòng ở
   `test_jobs.py`).
2. Thay ba `except Exception` của `jobs.py:79,116,203` bằng `DEPENDENCY_ERRORS` (hay `RedisError`),
   để lỗi lạ nổi lên, và thêm nguyên nhân (`error=type(exc).__name__`) vào `training_sweep_skipped`
   cùng hai log rollback.
3. Dọn bảy lỗi `ruff check` còn lại: `RUF002` `×` ở `jobs.py:12`; `I001` ở `test_finish.py:7` và
   `test_jobs.py:8`; ba `RUF100` (`ANN401`, `SLF001` ×2) — bỏ `# noqa` của mã không bật; `F401`
   `TrainingJobRow` ở `test_tasks.py:35`.
4. `jobs.py` dùng `open_storage` của `apps.worker.training_bridge.tasks`, bỏ phụ thuộc vào
   `apps.api.library.assets` (#5).
5. Một dòng `NO-<nnn>` trong `DEBT.md` cho nợ hợp đồng chung B6-03b (#4), và một dòng cho vòng đời
   client `safe_redis()` của worker nếu chọn không sửa #6 trong lượt này.
6. Chạy lại cổng **đầy đủ** (R-33b điều kiện 1 + 3: nhánh đổi file ngoài thư mục module —
   `packages/db/models/`, migration, `packages/messaging/payloads/`, `packages/testing/factories/` —
   và thêm nhiều file `.py` mới), dán nguyên bảng E.10 tám bước `đạt`, kèm độ phủ dòng **và** nhánh
   ≥ 90% cho `admin_ml_jobs`, `training_bridge`, `payloads/training.py` và tổng, cùng bảng
   `case_gate` 6 `op` / 5 task / 3 lịch.

#7 (trần điểm theo lô), #8 và #9 tác giả tự quyết, không chặn merge.
