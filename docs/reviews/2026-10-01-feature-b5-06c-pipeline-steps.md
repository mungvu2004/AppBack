# Review merge feature/b5-06c-pipeline-steps → main

- Ngày: 2026-10-01 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `1d7e55b4b119`
  (cây `43637af005cd`)
- Phạm vi kiểm: **đầy đủ** (R-33b điều kiện 1 — review lượt 1 của nhánh). Cổng do lớp gộp chạy
  trên worktree `b5-06c-step-done`; phiên này không chạy lại cổng, chỉ đọc log.
- Tái hiện F1 bằng lệnh đích: **đã dựng test nhưng không chạy được**. Worktree review chưa có
  venv (`/work/venv-b5-06c-review` chưa tồn tại) nên `run.sh shell` phải `uv sync` — khoảng 30
  phút tải gói ML, vượt trần thời gian của phiên. Container đã dừng, không để lại rác. Test đã
  soạn sẵn ở `backend/dieu-phoi/chay/B5-06c/R/f1.sh` (sửa đường `python` thành
  `/work/venv-<worktree>/bin/python` trước khi chạy); chứng cứ F1 trong phán quyết này là **đọc
  mã**, không phải đo — xem cột "Mô tả" của F1 để biết chính xác suy luận và chỗ kiểm lại.
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** — log
  `F:/AppBack/backend/dieu-phoi/chay/B5-06c/M/gate-1.log`, `M/gate.sha` = `1d7e55b`
  (log tự khai `20261001T044040Z-1d7e55b4b119`).
- Độ phủ `apps/worker/pipeline_steps`: dòng **98,48 %** · nhánh **95,16 %** (tập file bị chạm: 98,48 / 95,16; tổng repo 99,47 / 98,06) — cả hai ≥ 90 %. Phần thiếu phủ đáng kể duy nhất: `step_done.py:87-90` (F4).
- Phạm vi diff: `apps/worker/pipeline_steps/**` (18 tệp) + `changes/B5-06c.md`; không tệp nào khác,
  `[12]` không bị chạm, cây sạch, 10/12 commit đúng Conventional Commits + trailer `Prompt: B5-06c`
  (hai commit `Merge branch…` được `.githooks/commit-msg:14` miễn theo mẫu).

## Bảng cổng (E.10, từ mã thoát thật của `M/gate-1.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | 1174 tệp đã định dạng |
| 2 | `ruff check` | đạt | All checks passed |
| 3 | `mypy --strict` | đạt | 982 tệp nguồn, 0 lỗi |
| 4 | `lint-imports` | đạt | 10 kept / 0 broken |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | 7233 passed, 465,75 s; `coverage_gate: đạt` |
| 5b | `pytest -m perf` → `case_gate` | đạt | `perf: 0 đơn vị bị chạm`; `case_gate: đạt` |
| 6 | `lint_migrations` → `migrate_check` | đạt | 20 revision; 10/10 kiểm `migrate_check` đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | AppFront `9cf0b0bfffbd`, 83/83 dòng BE-BIND |
| 8 | `openapi` | đạt | ghi 236 965 byte |

**mã thoát: 0.** Không bước nào "không áp dụng": `changes/B5-06c.md` khai `migrate_check`/openapi
"không áp dụng" cho prompt, nhưng lớp gộp chạy trên cây đầy đủ nên cả hai bước vẫn chạy thật và
`đạt` — không có bước nào bị bỏ. `case_gate` chỉ in bảng cho `operationId` (77 thao tác đã mount),
không in dòng cho task/lịch; `cases.toml` khai đúng `J08/J09/J10` cho
`orchestrate_pipeline_step_done` và `J07` cho `sweep_stuck_pipeline_runs`, và cả ba đơn vị đều có
test `__J01`/`__J06` nên `case_gate: đạt` là phán quyết đủ cho `[8]`.

## Lệch khỏi prompt — phán quyết

| # | Lệch | Phán |
|---|---|---|
| 1 | `queue_build(db, run, *, clock)` không nhận `pins` | **chấp nhận** — `BuildStepPayload` chỉ cần bản vẽ + `read_settings`; `pins` sẽ là tham số chết (R-10). Tách `load_run_context` làm hàm chung của `step_done`/`sweep` đúng R-07, và nó kiểm đúng điều `[6]` đòi: `d = current_drawing(floor_pk)` phải thuộc `run.upload_id`. |
| 2 | Quét bù dùng lại `runs.send_start_after_commit` cho `preprocess` | **chấp nhận** — một nguồn dựng `PipelineStartPayload`, và `[12]` cấm tự khai `pipeline.orchestrate.start`. Docstring của hàm đó đã nói chính lõi quét bù là người gọi thứ hai. |
| 3 | `error_code` sai mẫu bị `StepResultPayload` chặn trước lõi | **chấp nhận** — `packages/ml_contracts/payloads.py:147` đã có pattern `ErrorCode`, nên mã xấu chỉ tới từ người gọi trong tiến trình; `_record_failed` giữ kiểm phòng thủ là đúng, và `_CODE_RE` khớp **đúng** `_UPPER_SNAKE` của `runs.py:57` nên không bao giờ biến thành `ValueError` của `record_step`. Test dựng payload bằng `model_construct` — hợp pháp. |
| 4 | Hằng `BUILD_TASK`/`PERSIST_TASK`/`QUALITY_TASK` tự khai trong `step_done.py` | **chấp nhận** — `[1]` cấm nhập module B5-06b/B5-07. Khoá hàng vẫn suy từ `queue_for(BUILD_TASK)` nên không chép chuỗi tên hàng (R-07). |
| 5 | `record_step` tự phát `Progress` | **chấp nhận, đã soát không phát đôi** — `runs._settle` gọi `publish_progress_after_commit`; `_requeue_one` chỉ gọi `publish_progress_after_commit` khi `_resend` trả `True` (tức không có `record_step` nào), còn nhánh hết trần và nhánh bản vẽ lệch để `record_step` phát. |
| 6–12 (báo cáo lớp gộp) | sha tiền kiểm tính trên host; `__J01_smoke` đồng bộ; `asyncio.to_thread` cho hàm `@periodic`; `drop_after_commit` bọc cả bản dựng; fixture gán lại tránh `F811`; ghim lại `dimensionReading` về cổ điển; `on_failed` test bằng lượt không tồn tại | **chấp nhận** — mỗi lệch có lý do kỹ thuật kiểm được và không lệch nào nới lỏng một khẳng định. |
| C | `PIPELINE_SWEEP_BATCH` dùng chung cho cả `purge` | **chấp nhận** — `[5]` không khai hằng batch riêng cho purge nên đây là lựa chọn duy nhất đúng spec; tách `PIPELINE_PURGE_BATCH` là việc tuỳ chọn → nợ P3. |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F1 | **P2** | CON-04 | Mốc im của quét bù bỏ sót hoạt động của `record_used`. `greatest(r.updated_at, m.updated_at)` không nhúc nhích khi một họ ML vừa xong, vì `pins.record_used` ghi bằng `text()` thuần (`SET used = …, last_used_at = now()`) nên `TimestampMixin.onupdate` (`packages/db/base.py:30`) không chạy — `onupdate` chỉ áp cho `update()` của Core, tức `set_step_requeue`/`mark_persisted`. Hệ quả: lượt nào có một bước ML chạy > `PIPELINE_STEP_REQUEUE_AFTER_S` (600 s) trong khi họ khác đã về sẽ bị coi là kẹt → quét bù **gửi lại chính suy luận đang chạy** (lãng phí GPU) và đốt một lượt `step_requeue_count`, tức rút ngắn trần trước `PIPELINE_STEP_TIMEOUT`. Test không bắt được vì `helpers.set_idle` đặt thẳng cả hai `updated_at` bằng `update().values(...)`, che đúng đường thật. | `apps/worker/pipeline_steps/sweep.py:55` (`_CANDIDATES`) và `:64` (`_IDLE_MARK`); nguồn: `apps/worker/pipeline_orchestrate/pins.py:56-59` | Thêm `m.last_used_at` vào cả hai `greatest(...)`: `GREATEST` của Postgres bỏ qua `NULL` nên không cần `coalesce`, và cột đó do chính `record_used` ghi. Sửa nằm **trong** tệp của B5-06c, không phải chạm B5-06a. Kèm một test: `record_used` một họ rồi quét ngay → lượt không được chọn. |
| F2 | P3 | LOG-07 | Nhánh hết trần (và hai nhánh bỏ sớm) của `_requeue_one` `return` **trong** `async with`, nên bỏ qua `await after_commit_idle(db)` ở dòng 168 dù `record_step(…, PIPELINE_STEP_TIMEOUT)` vừa hẹn một callback phát `Progress`. Trong worker thật `DB_AFTER_COMMIT_INLINE=1` nên callback chạy tại chỗ → không mất sự kiện; nhưng khi không có cờ đó (khuôn executor của `packages/db/hooks.py`) hàm lịch trả về trước khi `Progress failed` kịp phát, trái chữ `[6]` "commit xong `await after_commit_idle(db)`". `__J07` không bắt vì nhánh hết trần chỉ khẳng định dòng DB, không khẳng định sự kiện. | `apps/worker/pipeline_steps/sweep.py:150-160` so với `:168` | Đưa `after_commit_idle` vào `finally`, hoặc đổi ba `return` sớm thành một biến thoát rồi rơi xuống dòng 168. Kèm khẳng định sự kiện `failed` vào `__J07`. |
| F3 | P3 | PERF-09 | `_CANDIDATES` `ORDER BY greatest(r.updated_at, m.updated_at)` không có khoá phá hoà. Với `LIMIT :batch` và nhiều lượt cùng mốc im (thường gặp: vài lượt ghi trong cùng một giao dịch hay cùng một nhịp `now()`), Postgres chọn tập con tuỳ ý nên một lượt có thể bị bỏ qua nhiều lượt quét liền. `_select_due` của `purge.py:51` đã làm đúng (`ORDER BY updated_at, run_id`). | `apps/worker/pipeline_steps/sweep.py:59` | Thêm `, r.id` vào `ORDER BY` cho khớp khuôn `purge.py`. |
| F4 | P3 | TEST-11 | Nhánh hỏng của `queue_build` (bản vẽ không thuộc `run.upload_id` đúng lúc xếp `spatialDataBuild`) không có test — đây là phần thiếu phủ đáng kể duy nhất (`step_done.py:87-90` trong báo cáo `--cov`). `test_sweep_fails_run_without_matching_drawing` có, nhưng nó đi qua nhánh ML của `_resend` (`sweep.py:111-121`), không qua `queue_build`. | `apps/worker/pipeline_steps/step_done.py:85-90` | Một test: đổi `current_drawing` của tầng sang lượt tải khác **sau** khi hai họ đã xong, rồi giao kết quả họ thứ ba → `failed` `PIPELINE_RESULT_INVALID` và không `pipeline.build.run`. |
| F5 | P3 | MNT-05 | Nhánh > 400 dòng mã nghiệp vụ (632 dòng không-test trên 8 tệp). | toàn `apps/worker/pipeline_steps/` | **Không đáng tách**: `[10]` của prompt ấn định đúng tám tệp này, và nhánh đã chia sẵn thành ba nhánh con (`step-done`, `sweep`, `purge`) đọc riêng được. Mặc định của skill là P2; hạ xuống P3 có chủ ý, ghi ra đây để truy được. |

Đã soát và **không** có finding ở: `step_done` chỉ một giao dịch (`run_pipeline_step_done` mở đúng
một `session_scope`); luật bỏ "họ đã có trong `used`" dùng chung cho cả `fail_pipeline_step_done_core`
(qua `_live`); `MODEL_PIN_MISMATCH` và kiểm khoá artifact đều chạy **sau** `lock_run` +
`load_pins(for_update=True)`; `_advance` đẩy theo thứ tự `PIPELINE_STEPS` chứ không theo
`MODEL_FAMILIES` (có docstring nói rõ) và `set_step_requeue(0)` chỉ khi thật có bước được đẩy;
`reached_build` chỉ `True` khi **lần lặp này** chạm bước ML cuối, nên J06 không gửi
`pipeline.build.run` lần hai và J10 để quét bù lo; `spatialDataBuild completed` chỉ gửi
`persist.run` khi `persisted_revision is None`; mọi việc gửi đi qua `on_after_commit` (J09);
`StepResultPayload.status` là `Literal["completed","failed"]` nên hai nhánh của `_build_result` phủ
hết; LLEN hai hàng chạy song song bằng `asyncio.gather`, mỗi lệnh `wait_for` 1 s,
`TimeoutError`/`RedisError` → "còn việc", và **trước** mọi session (K36 — có test đo
`pool.checkedout() == 0` với pool một kết nối); lượt chờ hàng bị loại trong `WHERE` chứ không chặn
đầu lô; lùi `× 2^count` và trần `PIPELINE_RUN_MAX_S` tính từ `started_at`; đọc lại mốc im dưới khoá
(`_idle_seconds`); `PIPELINE_STEP_TIMEOUT` không đặt `ended_at` (`runs._apply` chỉ đặt `ended_at` ở
bước cuối); `purge` đóng session trước `delete_prefix` rồi một giao dịch ngắn
`mark_artifacts_purged`, chỉ xoá `run_prefix` = `…/runs/{run}/` nên `pages/`, `original.*` an toàn,
và lỗi kho cố ý không bị bắt (đánh dấu sai sự thật tệ hơn chậm một ngày); ghi `pipeline_run_models`
chỉ qua `pins`, `pipeline_runs` chỉ qua `record_step`; không đọc nội dung artifact ML (chỉ so khoá);
không `except Exception`, không `pragma: no cover`/`skip`/`xfail`/`# noqa` trần/`# type: ignore`;
`lint-imports` 10/10 KEPT (không `apps.ml`, `torch`, `onnxruntime`, `fastapi`) và `test_boundary.py`
còn soát lại bằng AST; K34 không chord/group/chain; mọi SQL thô dùng `bindparams`, không f-string;
ma trận `[8]` phủ đủ (58 test, dịch vụ thật, đọc hàng bằng `LLEN`/`LRANGE` khi không worker nào
nghe); R-01 docstring **mọi** hàm kể cả hàm lồng và test (soát bằng script, 0 thiếu); không hàm nào
> 50 dòng ngoài `__J01` (51 dòng tính cả docstring — thân 44 dòng, đạt); `cases.toml` chỉ khai case
`J` (NO-294) và không tên test nào chứa `perf`.

## Nợ nên ghi (DEBT.md thuộc người điều phối; phiên này không sửa)

- **F1** → một dòng P2 mở, chủ B5-06c: mốc im bỏ sót `record_used`, sửa bằng `m.last_used_at`.
- F2, F3, F4 → gộp được một dòng P3 "vòng mài `pipeline_steps`".
- F5 / lệch C → P3 tuỳ chọn: tách `PIPELINE_PURGE_BATCH` khỏi `PIPELINE_SWEEP_BATCH`.
- **Đóng được nhờ nhánh này:** `NO-292` (đã khai `pipeline.orchestrate.step_done`) và `NO-290`
  (quét bù đánh `PIPELINE_STEP_TIMEOUT` khi `build.run` thành thông điệp độc — đúng cách giải nợ
  mà chính dòng `NO-290` ghi).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 3 | 0,45 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,45 / 5** |

PERF giữ 5 dù có F3: F3 là công bằng hàng đợi, không phải chi phí truy vấn — đã tính một lần ở
CON, không chấm đôi.

## PHÁN QUYẾT: APPROVE WITH COMMENTS

Nhánh làm đúng `[6]` ở mọi bất biến đắt giá và cổng đầy đủ của lớp gộp xanh thật (mã thoát 0,
8/8 bước `đạt`, 7233 test, độ phủ 98,48/95,16 cho `apps/worker/pipeline_steps`). Không có P0, không
có P1: tám tệp nguồn đọc như một mô-đun chín — một giao dịch cho `step_done`, Redis đứng ngoài mọi
session với trần 1 s và luật fail-closed, mọi việc gửi đi qua `on_after_commit`, `purge` đóng session
trước `delete_prefix`, SQL thô đều `bindparams`, docstring đủ mọi hàm, và mười hai chỗ lệch khỏi
prompt đều có lý do kiểm được. Tổng điểm 4,45/5 vượt ngưỡng `APPROVE`; tôi vẫn chọn **APPROVE WITH
COMMENTS** vì F1 là một P2 **mở** về hành vi (không chỉ là mỹ quan): mốc im của quét bù bỏ sót
`record_used`, nên một lượt có bước ML chạy quá 10 phút sẽ bị gửi lại chính suy luận đang chạy và
mất một lượt trong trần `PIPELINE_STEP_REQUEUE_MAX`. Theo ma trận §6 của skill, P2 phải có một dòng
`DEBT.md` trước khi merge.

**Được merge khi** người điều phối ghi dòng `DEBT.md` cho F1 (P2, mở, chủ B5-06c) — và nên ghi luôn
một dòng P3 gộp F2–F4. Sửa mã **không** phải điều kiện: F1 nằm trong tệp của B5-06c và là một lần
thêm `m.last_used_at` vào hai câu `greatest(...)`, làm được trong vòng mài tiếp theo hoặc trong lượt
2 nếu người điều phối muốn vào `main` sạch. Không có gì khác chặn merge: `[12]` không bị chạm, cây
sạch, mọi commit không-merge đúng mẫu + trailer `Prompt: B5-06c`, và nhánh này đóng được `NO-290`,
`NO-292`.
