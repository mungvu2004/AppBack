# Review merge feature/b6-03b-training-runner → main

- Ngày: 2026-10-02 (UTC; tên tệp giữ ngày mở lượt review theo yêu cầu điều phối) · Reviewer: phiên /merge-review (lượt 1)
- Commit đầu nhánh: `93eab65d` (giao ở `3a303c8`; `3a303c8..93eab65` = hai test sửa + `DEBT.md` trả về `main`)
- Phạm vi diff: `apps/ml/training_runner/**` (22 tệp) + `changes/B6-03b.md`; 3548 dòng thêm, 0 dòng ngoài cột "Sở hữu"
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1 — review lượt 1 của nhánh); `bash tools/verify/run.sh verify`
  **mã thoát 0** trên `93eab65` (log: `backend/dieu-phoi/chay/B6-03b/M/gate-2.log`). Lượt cổng 1 trên `3a303c8`
  **đỏ bước 5** (`gate-1.log`, 1/7555 — `test_main_trainers_honours_app_env`), đã sửa ở `4a226b0`.
- Độ phủ: `apps/ml/training_runner` dòng **98,74 %** · nhánh **94,59 %** (gộp cả tiến trình con) — `gate-2.log:351`,
  `coverage_gate: đạt`. 7555 test đạt trong 523,98 s.
- Tái hiện của reviewer (1 container `run.sh shell`, log `backend/dieu-phoi/chay/B6-03b/R/repro-1.log`):
  `pytest -q -p no:randomly …::test_run_training_job_m04 …::test_start_training_runner__J01` → **1 failed, 1 passed**.

## Bảng cổng (E.10, từ mã thoát thật của `gate-2.log`)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt |
| 8 | `openapi` | đạt |

`case_gate: đạt`. Dòng `case_gate` của `start_training_runner` **không ra số** — sổ case chưa biết task của
`apps/ml`; đúng điều [11].2 của prompt (`[[task]]` giữ nguyên), đã ghi nợ `NO-309`.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | TEST-02 / [9] "test chạy được song song" | `run()` của M04 gọi `reset_ml_settings_cache()` sau `monkeypatch.setenv("ML_DEVICE", …)` nhưng **không bao giờ** trả cache về: `get_ml_settings` là `lru_cache`, nên sau M04 mọi test **sau đó trong cùng tiến trình** thấy `ml_device="cuda"`. `_hold_locks` gọi `resolve_device(get_ml_settings().ml_device)` → lượt hỏng trước `heartbeat(0)`. **Đã tái hiện xác định** (không cần xdist): chạy M04 rồi `__J01` trong một tiến trình → `__J01` đỏ, `kinds == ['log','finished']`, đúng ba lỗi của `M/pre-4.log` (`claim_renew_refused`, `watchdog_timeout`, `__J01`). Nối tiếp thì không lộ (M04 nằm gần cuối tệp), chỉ lộ khi xdist chia lại thứ tự — đúng điều cấm tuyệt đối | `apps/ml/training_runner/tests/test_runtime.py:300` (dùng ở `:269-368`) | Fixture khôi phục trong `test_runtime.py`: `@pytest.fixture(autouse=True)` `yield` rồi `reset_ml_settings_cache()`; test khác sẽ không còn thừa hưởng `ML_DEVICE` của M04 |
| 2 | P2 | TEST-02 | `_tmp_dirs()` quét **toàn bộ** thư mục tạm của container; dưới xdist `-n 6` (6 tiến trình chung `/tmp`, không có `TMPDIR` riêng) một lượt `run_training_job` của tiến trình khác đang sống làm `assert set(_tmp_dirs()) <= before` đỏ ngẫu nhiên. Chưa tái hiện, nhưng cơ chế có thật | `apps/ml/training_runner/tests/test_runner.py:202`, dùng ở `:218` (`__J04`), `:232` (`__J05`), `:298` (`_watchdog`) | Chốt riêng thư mục của lượt, ví dụ `monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))` trong fixture `harness` — đúng cách `test_purge_stale_tmp_removes_old_dirs:532` đã làm |
| 3 | P2 | MNT-01 / R-08 | Hai hàm test vượt trần 50 dòng: `test_run_training_job_cancel_while_waiting` ~91 dòng, `test_run_training_job_m04` ~100 dòng | `apps/ml/training_runner/tests/test_runtime.py:177`, `:269` | Đưa script tiến trình con ra hằng module; tách M04 thành bốn test (cpu-chờ-slot, cpu-không-gpu, cuda-giữ-hai-khoá, mất-khoá) dùng chung helper `run` |
| 4 | P3 | R-07 | `max_len = 500` chép lại `MAX_METRIC_POINTS` (`packages/ml_contracts/payloads.py:36`); thêm nữa `_FLUSH_EVERY_POINTS = 100` chặn bộ đệm ở 100 nên nhánh chia lô **không bao giờ** sinh quá một lô (linh hoạt chết). B5-01 hạ trần → payload vỡ bằng `ValidationError`, mà `_send_or_log` chỉ bắt `AppError` | `apps/ml/training_runner/reporter.py:165` | Nhập `MAX_METRIC_POINTS`, hay bỏ hẳn việc chia lô |
| 5 | P3 | RES | `cancel()` của luồng nhịp tim `join()` **không** trần thời gian, khác `slot.JOIN_TIMEOUT_S`/`watchdog.JOIN_TIMEOUT_S` (5 s); `send` kẹt trong luồng daemon treo luôn lượt gỡ `ExitStack` | `apps/ml/training_runner/reporter.py:138` | `thread.join(JOIN_TIMEOUT_S)` cùng hằng với hai module kia |
| 6 | P3 | LOG / [2] | Trainer "không tin" ném `PermanentError("TRAINING_CANCELLED")` khi runner chưa chốt lý do dừng → `_failed(exc.code)` gửi `finished(failed, TRAINING_CANCELLED)`, mà [2] ghi mã này **không bao giờ** lên dây | `apps/ml/training_runner/runner.py:403-405` | Trong `except PermanentError`, ánh xạ riêng `TRAINING_CANCELLED` sang đường huỷ (hay `INTERNAL`) |
| 7 | P3 | TEST-02 | `assert code in {0, 1}` không phân biệt được "override bị bỏ qua" với "override được nạp" — test không thể đỏ dù hồi quy | `apps/ml/training_runner/tests/test_runner.py:632-642` | So mã lỗi `finished` (`TRAINING_TRAINER_MISSING`) hay dòng log `training_trainer_override_ignored` |
| 8 | P3 | OBS | Docstring module còn tả trạng thái nhánh trước khi gộp ("Việc D chỉ viết test… tới lúc đó file không `import` được") — sai với cây hiện tại | `apps/ml/training_runner/tests/test_runtime.py:1-7` | Viết lại theo nội dung test |
| 9 | Nit | R-01 | `_wait(predicate: object)` rồi `# type: ignore[operator]`; kiểu thật là `Callable[[], bool]` | `apps/ml/training_runner/tests/test_tasks.py:86,92` | Khai đúng kiểu, bỏ `type: ignore` |
| 10 | Nit | PERF | `_validated_weights` đọc trọn tệp trọng số vào RAM (trần 512 MiB) trước khi băm/`put` — cùng idiom `apps/ml/runtime/loader.py`, chấp nhận trong tiến trình con riêng | `apps/ml/training_runner/runner.py:120` | Không cần sửa; ghi nhận |

## Đã đối chiếu, **không** thành finding

- **Năm lệch/quyết định biết trước đều đứng được:** `safe_redis_sync()` (đồng bộ, DB an toàn, cùng DB B6-03a đặt
  `cancel_key`) · `training_slot` tự viết trong `slot.py` vì `gpu.py` cứng khoá `gpu:0` và [12] cấm sửa (nợ `NO-308`) ·
  `keys.sample_key` dựng khoá ba đoạn bằng `check_id`+`check_key` (NO-263, cùng cách `apps/worker/datasets/writer.py`) ·
  manifest không giải được → `DATASET_MANIFEST_MISMATCH` · `keys.py` khai lại mẫu của B6-03a (`NO-305`).
- **Lệch thêm do tác giả khai, đều có lý do:** `onnx.load_model_from_string` thay `onnx.load(load_external_data=False)`
  — tương đương (không nạp dữ liệu ngoài) và dùng lại byte đã đọc để băm; `_cancel_requested` bắt `(RedisError, AppError)`
  chứ không `Exception`; `Watchdog(monotonic=…)` tiêm được; `_pipeline` bắt `OSError` **chỉ khi** `watchdog.expired`;
  `redis_errors()` quanh lệnh Redis của task để Redis hỏng thành J02 chứ không `INTERNAL`; `proc.kill()` trước khi xoá
  claim khi `OSError` xảy ra sau `Popen`.
- **Thứ tự [6] 1-9 đúng:** `claim_lease` vào `ExitStack` trước `purge_stale_tmp` và trước mọi thứ nặng (`torch`,
  `discover_trainers` chỉ chạm ở bước 3/5); manifest, split, trần đọc xong **trước** vòng chờ khoá (`_prepare` ⟶
  `_hold_locks`); `resolve_device`/`trainers()` chỉ sau `training:slot`; `cpu` không gọi `gpu_slot` (M04 ghim
  `gpu_calls == []`); `check_disk` đo **sau** khi giữ khoá (`test_run_training_job_disk_full` ghim `seen == [True]`);
  băm khi đọc từng khúc (`dataset._download_one`).
- **Lý do dừng quyết kết quả:** `StopState` "lý do đầu thắng", `_stopped` phân nhánh huỷ/quá giờ/mất slot/mất gpu/mất
  claim; claim mất → `_claim_lost` (không `put`, không `finished`, `delete_if_owner` không xoá claim người khác —
  `test_run_training_job_claim_lost` ghim token người khác còn nguyên). Luồng canh dọn `tmp`, gửi `finished` theo lý do,
  `exit(1)` tiêm được, `_expired()` chặn gửi lần hai ở **mọi** lối (`_stopped`, `_failed`, `_send_finished`).
- **ONNX không tin:** đường phải nằm dưới `out_dir`, cỡ ≤ 512 MiB, byte đầu `0x08`, `DecodeError` → mã, `has_external_data`
  → mã; không `pickle`/`torch.load` ở đâu trong mã sản phẩm (M03 còn vá `pickle.load`/`loads` để nổ nếu runner thử).
  Số đo phải đúng một khoá `FAMILY_METRIC[family]`; `put(weights_key(job, token))` chỉ sau khi `renew_if_owner` còn khớp.
- **Reporter:** gom theo thứ tự gọi, xả ở 100 điểm / 10 s và **trước** `finished`; `line` tăng từ 1; `finish` gửi lại 6 lần
  lùi 2-4-8-16-32-60 s rồi log `training_finished_unsent`, trả `False` → thoát 1, object **còn**;
  `training_send_failed`/`training_finished_unsent` là sự kiện `logging` máy chủ, không vào log job.
- **Ma trận [8] đủ:** J01, J01_smoke, J03-J06, J08, M02-M04, `cancel_while_waiting` (ghim `torch not in sys.modules`
  trong tiến trình Python mới), `claim_lost`, `watchdog`, `disk_full`, `seed`, `split_empty`, reporter gửi lại,
  `test_training_keys_literal`, ranh giới chặn `sqlalchemy`/`torch`. Dịch vụ **thật** khắp nơi (Redis Testcontainers
  theo từng worker xdist, kho đĩa thật, `celery_worker_factory` + tiến trình con thật ở J01_smoke); không `fakeredis`,
  không `task_always_eager`, không `os._exit` thật trong test. `cases.toml` chỉ khai mã J (NO-294).
- **K24 sạch:** không `pragma: no cover`, không `skip`/`xfail`, không hạ ngưỡng; mọi `# noqa`/`# type: ignore` đều có mã
  **và** lý do. `except Exception` đúng **một** chỗ — `__main__.main()` (`# noqa: BLE001` kèm lý do), đúng [9].
- **R-01:** mọi hàm, kể cả hàm lồng và hàm test, đều có docstring (năm hàm không có nằm **trong chuỗi script** của tiến
  trình con, không phải mã). Không nhập `packages.db`, `apps.api`, `apps.worker`, `packages.messaging.payloads.training`;
  không `packages.testing` trong mã không phải test; không `shell=True`.
- **Sổ nợ:** `NO-305`, `NO-308`, `NO-309`, `NO-310` đều có dòng trong `DEBT.md` (`:326`, `:329-331`) — đã được trả về
  `main` ở `a635f32`/`93eab65`, nhánh không còn chạm `DEBT.md`. Không nợ `P0`/`P1` mở.
- **Git:** cây sạch; mọi commit không phải merge đúng mẫu `<type>(<scope>): …` ≤ 72 ký tự và có trailer `Prompt: B6-03b`;
  commit merge được `.githooks/commit-msg` miễn trừ tường minh. `changes/B6-03b.md` có, 7 dòng.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 1 | 0,07 |
| OBS, OPS – Vận hành | 5 % | 4 | 0,20 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,36 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Mã sản phẩm của nhánh này tốt hơn mức trung bình của bộ: thứ tự chín bước đúng hợp đồng BE-00 §7, mọi lối dừng và mọi
lối mất khoá đều có test dịch vụ thật, trainer bị coi là không tin ở cả ONNX lẫn số đo, độ phủ 98,74 % dòng / 94,59 %
nhánh, cổng đầy đủ xanh. Không có P0, không có lỗi bảo mật hay đồng thời. Chặn merge **chỉ** vì finding 1: bộ test tự
làm bẩn trạng thái toàn cục (`get_ml_settings` là `lru_cache`, M04 xoá cache với `ML_DEVICE` đã vá mà không trả lại),
nên mọi test chạy sau M04 trong cùng tiến trình đều có thể đỏ — tôi tái hiện xác định trong một tiến trình, không cần
xdist, và nó giải thích đúng ba test đỏ của `M/pre-4.log`. Đây là điều **cấm tuyệt đối** của prompt ([9] "test chạy được
song song") và nếu vào `main` thì nó sẽ làm đỏ cổng của những prompt sau mà họ không có cách truy ra.

Điều kiện để `APPROVE` ở lượt 2:

1. **Bắt buộc (P1)** — thêm fixture khôi phục cache trong `apps/ml/training_runner/tests/test_runtime.py`
   (`autouse`, `yield` rồi `reset_ml_settings_cache()`), rồi chứng minh bằng một lượt
   `pytest -q -p no:randomly …::test_run_training_job_m04 …::test_start_training_runner__J01` xanh **và** một lượt
   `pytest -n 6 -m "not perf" apps/ml` xanh.
2. **Bắt buộc (P2)** — sửa finding 2 và 3, **hoặc** ghi mỗi cái một dòng `NO-<nnn>` trong `DEBT.md` kèm chủ và mức.
3. Finding 4-8 và hai Nit: sửa nếu còn thời gian, không chặn merge.
