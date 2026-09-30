# Review merge feature/b5-06b-pipeline-persist → main

- Ngày: 2026-09-30 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `a2c462eae9a4`
- Cây: `git status --porcelain` rỗng · 7 commit (`0f32052`…`a2c462e`), mọi dòng đầu đúng Conventional Commits, mọi thân có trailer `Prompt: B5-06b`
- Phạm vi diff: `apps/worker/pipeline_persist/**` (17 tệp) + `changes/B5-06b.md` — **không** tệp nào ngoài cột "Sở hữu" của prompt, không chạm tệp cấm của [12]
- Cỡ nhánh: 2.202 dòng thêm; **284 dòng logic sản phẩm** (docstring 122 dòng) + ~1.717 dòng test → dưới trần 400 của MNT-05, không đáng tách
- Cổng: phạm vi **đầy đủ — log cổng lượt 3 của lớp gộp** (spec review cấm mở lại cổng đầy đủ); `bash tools/verify/run.sh verify` trên `a2c462e` (`M/gate.sha`), log `backend/dieu-phoi/chay/B5-06b/M/gate.log`, cây `1e9d7e319ba4` = `git rev-parse a2c462e^{tree}`
- Độ phủ: tổng dòng **99,48%** · nhánh **98,08%** — `apps/worker/pipeline_persist` dòng **97,10%** · nhánh **92,11%** (tập file bị chạm cùng số) → cả hai ngưỡng 90/90 đều đạt, không `pragma`, không hạ ngưỡng

## Bảng E.10 (mã thoát thật, lấy từ `M/gate.log`)

`bash tools/verify/run.sh verify` — **mã thoát 0** (log dòng 527), cổng lượt 3 xong ~2026-09-30T08:28Z, header log `20260930T081542Z-a2c462eae9a4.log`.

|   # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | 7175 passed, 606,24 s; `coverage_gate: đạt` |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 2 test; `case_gate: đạt` |
| 6 | `lint_migrations` → `migrate_check` | đạt | 20 revision |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | 1772 mẫu response, 25 mã, 6 khung SSE |
| 8 | `openapi` | đạt | 236.965 byte |

Không bước nào "không áp dụng"; không bước nào "chưa chạy".

`case_gate` cho task `persist_pipeline_result`: `đạt`, không dòng "thiếu" nào (J01, J03, J06, J09, J10 đủ; `cases.toml` khai `J03 J09 J10`, `case_gate` tự đòi J01 + J06). Ba `CẢNH BÁO` của `case_gate` (`files_read_object`, `health_live`, `health_ready` mount mà không có dòng BE-BIND) là có từ trước, ngoài diff.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | PERF-04 | Lõi giữ khoá `floors … FOR UPDATE` **21,08 s** trên lớp 20.000 tường (toà mẫu 0,106 s) — quá trần 5 s mà khối [8] đặt. `merge_pipeline_result` + `write_layer` chạy trọn trong giao dịch giữ khoá, nên một lượt pipeline của toà lớn làm mọi người ghi cùng tầng vượt `DB_LOCK_TIMEOUT_MS` = 5 s (họ nhận lỗi, không chỉ chờ). Không tự đo lại được ở lượt này (cổng xdist của lớp gộp phải chạy một mình); số lấy từ `bao-cao-B.md` và có test in ra (`test_persist_lock_hold_20k_walls`, chỉ log, không khẳng định — đúng như [8] yêu cầu) | `apps/worker/pipeline_persist/service.py:187-208` (`_persist`, dưới khoá của `_run_transaction:213`) | Không sửa trong nhánh này — trộn **phải** ở dưới khoá để chặn đua #35. Nợ `NO-296` cho B3-06 (tối ưu `merge_pipeline_result`) hoặc B3-03 (tách phần tính ra ngoài khoá kèm kiểm revision). Dòng nợ phải vào `DEBT.md` cùng lần merge |
| 2 | P3 | R-34 | Bốn dòng nợ của prompt (`NO-296`–`NO-299`) chỉ có trong `backend/dieu-phoi/chay/B5-06b/debt-draft.md`, chưa có dòng nào trong `DEBT.md` (tệp kết ở `NO-295`). `DEBT.md` không thuộc `so_huu` của B5-06b nên tác giả không được sửa — đúng luật, nhưng nợ chưa ghi vẫn là nợ có thể mất | `DEBT.md:315` (dòng cuối) vs `debt-draft.md:1-4` | Người điều phối commit 4 dòng lên `main` trước hoặc cùng lần merge (đúng khuôn `NO-295` của B5-06a) — **điều kiện merge** |
| 3 | P3 | R-07 | Trùng lặp helper giữa 4 tệp test dù `tests/helpers.py` là tệp của chính prompt: `_arrange` bốn bản (`cases:78`, `rules:80`, `runtime:129`, `lock:97`), `_persist_once`/`_persist` hai bản thân giống nhau (`cases:71`, `rules:95`), `CPU_QUEUE` hai bản (`cases:37`, `runtime:55`), `type Maker` ba bản (`runtime:53`, `lock:39`, `k36:29`), và phép dựng "lớp AI vỡ tham chiếu" hai bản (`runtime:126` `_broken_layer` vs `rules:569` nội tuyến) | `apps/worker/pipeline_persist/tests/test_persist_runtime.py:126`, `tests/test_persist_rules.py:569` (+ các vị trí trên) | Dồn `_arrange(maker, storage, clock, *, layer=None, make_built=None)`, `broken_layer(level_id)`, `Maker`, `CPU_QUEUE` vào `tests/helpers.py`; gộp vào vòng dọn của `NO-297` |
| 4 | P3 | R-02 | `service._read_built` lặp khuôn gom-tới-trần của `pipeline_build/tasks.py:82` `_read_artifact`; `service._floor_state` lặp luật cửa sổ khôi phục của `apps/api/drawings/runs.py:319` `_out_of_window`. Cả hai gốc là hàm riêng tư của prompt khác ([12] cấm sửa) và cả hai bản lặp đã ghi docstring nói rõ vì sao viết lại | `apps/worker/pipeline_persist/service.py:74-95`, `:98-110` | Đúng như `NO-297` đã soạn: B5-05 công khai `read_artifact(storage, key, max_bytes)`, B2-04 công khai luật cửa sổ, rồi B5-06b dùng lại |
| 5 | Nit | MNT-02 | `bao-cao-A.md` "Lệch khỏi prompt" mục 5 (`_settle` phát `Progress` cả ở nhánh ghi) và `bao-cao-B.md` mục "Lỗi ở A" + hai dòng nợ `ai_built` đã **cũ** so với sha review: `363ca00` đổi `_settle` chỉ phát ở nhánh phát lại và gỡ `ai_built` sang `helpers.sample_built`/`ai_layer`. Báo cáo gộp `bao-cao-B5-06b.md` thì đúng | `bao-cao-A.md`, `bao-cao-B.md` | Không chặn merge; báo cáo gộp là bản có hiệu lực |
| 6 | Nit | RES-03 | `fail_step` không `await after_commit_idle(db)` sau commit, còn `run_persist` thì có. Trong tiến trình worker `create_celery` đặt `DB_AFTER_COMMIT_INLINE=1` nên khung `Progress` `failed` vẫn phát tại chỗ; ở một tiến trình không đặt cờ đó, callback bị lên lịch rồi vòng nghỉ → mất khung | `apps/worker/pipeline_persist/service.py:275-276` | Thêm một dòng `await after_commit_idle(db)` cho đối xứng (prompt [6] không đòi, nên chỉ là Nit) |
| 7 | Nit | LOG-07 | Thông điệp `RuntimeError` nói `persisted_revision … đã có`, nhưng `mark_persisted` cũng trả `False` khi **không có dòng** `pipeline_run_models` nào cho lượt (`pins.py:68-74` là `UPDATE … WHERE`); hai nguyên nhân khác nhau dùng chung một câu | `apps/worker/pipeline_persist/service.py:207` | Nói cả hai khả năng, hoặc đọc `load_pins` để phân biệt khi dựng thông điệp |

Không có finding P0 hay P1.

## Đã tự kiểm, không thành finding

- **K36** (`service.py:248-254`): session bước 1 đóng ở `async with` trước `_read_built`; giao dịch chính mở sau khi đã có `BuiltLayer`. Test `test_persist_holds_no_session_while_reading_storage` chứng minh bằng pool **một** kết nối (`db_pool_size=1`, `db_max_overflow=0`, `db_pool_timeout_s=1`) và `engine.pool.checkedout() == 0` trong lúc `open_read` bị chặn — lớp bọc kế thừa `LocalDiskStorage` thật, không mock (K23).
- **Thứ tự [6] bước 3.1→3.10**: `_run_transaction:213` `lock_run` → `load_context` → `_floor_state` → `load_pins` → `_persist` (`create_version` có `note` → `write_layer` → `create_version` `note=None` → `mark_persisted` → `record_step`) → `_settle` (`is_member`/`notify` → `_queue_quality`). Khớp từng bước.
- **Tầng xoá**: trong cửa sổ → `"deferred"` → `run_persist:256` rollback, không ghi gì, lượt vẫn đứng `spatialDataBuild` (test `…defers_while_floor_is_restorable` khẳng định cả `current_step` lẫn `error_code`, rồi khôi phục và giao lại → `persisted`); ngoài cửa sổ hoặc dự án xoá → `record_step(failed, FLOOR_DELETED)` rồi commit (hai test riêng). `_floor_state` cho dự án xoá là `gone` ngay, không cửa sổ — cùng luật với `runs._out_of_window:325`.
- **Progress phát đúng một lần** (lệch biết trước số 4 của spec): `_settle:182` chỉ gọi `publish_progress_after_commit` khi `replay`; nhánh ghi để `record_step` → `runs._settle:365` tự hẹn phát. `__J01` khẳng định `len(progress) - before == 1`. Soát cả gói: không còn lời gọi `publish_progress_after_commit` nào khác.
- **Nhánh phát lại**: không `create_version`, không `write_layer`, không `record_step`; `notify` cùng `dedupe_key=f"aiCompleted:{run_id}:{uploader_id}"`; `send_task` **chỉ** qua `on_after_commit` (`_queue_quality:146-154`; K17, J09); `after_commit_idle` gọi sau khi giao dịch đóng — `hooks.py:110` khai rõ "gọi được sau khi session đã đóng".
- **Ánh xạ lỗi** (`_write_ai_layer:136-143`): chỉ bọc quanh `write_layer` (và `make_merge` chạy bên trong nó); ba mã layer → `PermanentError(cùng mã)`; `VALIDATION` và `ValueError` → `PIPELINE_RESULT_INVALID`; `DEPENDENCY_UNAVAILABLE`, `NOT_FOUND` của `write_layer` lan nguyên; `ValueError` của `notify`/`record_step`/`mark_persisted`/`create_version` nằm ngoài `try` nên lan. Không `except Exception`/`except BaseException` ở đâu trong gói (đã grep cả gói).
- **K19**: `scale_source=built.scale_source`, mà `BuiltLayer.scale_source` khai `Literal["pipeline", "project_default"]` (`pipeline_build/build.py:90`) — `human` không biểu diễn được. Ba test tỉ lệ phủ cả ba hạng (`human` cùng trang, `human` trang khác, `project_default`).
- **K21**: `body=LayerWrite(None, …)` — không `body.layer`; `make_merge` đúng hai nhánh, hàm lồng `merge` có tên (không lambda); `test_persist_keeps_reviewed_entities` so từng trường của tường đã duyệt và kiểm `reference_ids` của kích thước.
- **Ma trận [8]**: `__J01`, `__J01_smoke`, `__J06`, `__J06_concurrent`, `__J03` (ba ca trong một hàm — đúng, vì `_TEST_TASK_RE` của `case_gate.py:296` không nhận hậu tố `[…]` của `parametrize`), `__J09`, `__J10`, + 19 test theo việc. `cases.toml` khai đúng và **chỉ** case J (`J03 J09 J10`, tránh bẫy NO-294). Hai test `perf` (`test_persist_lock_hold_*`) không mang mã case; `__J01_smoke` in thời gian bằng `logging` thay vì assert perf. Hàng đọc bằng `LRANGE` (`queued_payloads`). Dịch vụ thật: Postgres, Redis, kho đĩa; hai lớp bọc (`BrokenStorage`, `_GatedRead`) kế thừa `LocalDiskStorage` thật; `monkeypatch` chỉ chạm `service.mark_persisted`, `service.load_context`, `service.get_pipeline_build_settings`, `service.create_version`, `service.lock_run` và `tasks._STORAGE._factory` — không mock session, `write_layer`, `create_version`, `notify` hay Redis (K23; `_STORAGE._factory` đúng khuôn B5-06a đã hợp nhất, `test_start_cases.py:168`).
- **R-01**: đọc hết 17 tệp — mọi hàm, hàm lồng, lớp và test đều có docstring; không dòng nào > 120 ký tự; không hàm nào > 50 dòng.
- **K24**: không `pragma: no cover`/`no branch`, không `skip`/`xfail`, không hạ ngưỡng. Hai chú thích dập cảnh báo đều có mã + lý do: `# noqa: S603` (`test_boundary.py:33`), `# type: ignore[arg-type]` (`test_persist_lock.py:171`).
- **[12] không chạm**: `git diff --name-only main...HEAD` chỉ ra `apps/worker/pipeline_persist/**` và `changes/B5-06b.md`.
- **Lệch biết trước 1, 2, 3, 5 của spec**: đều đúng — `get_pipeline_build_settings().PIPELINE_ARTIFACT_MAX_BYTES`, `SYSTEM_PIPELINE` từ `packages.core.errors:144` (không phải bản trùng ở `apps/api/access/activity.py:19`), hợp đồng nội bộ do điều phối định (`reset_persist_storage`, `_STORAGE` `ProcessLocal`, `tests/helpers.py`), và ba phần thêm của `helpers` (`open_run_at_build(…, *, storage=None)`, `ai_layer`, `DONE_STEPS`) đều có lý do ghi trong docstring. Thêm một lệch đúng nữa: `get_floors_settings().floor_restore_window_s` (chữ thường) thay cho `FloorsSettings.FLOOR_RESTORE_WINDOW_S` của [3].
- **Migration/hợp đồng**: không bảng, không revision alembic, không endpoint → `openapi.json` không đổi; đúng như `changes/B5-06b.md` khai.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 3 | 0,30 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,70 / 5** |

## PHÁN QUYẾT: APPROVE

Cổng lượt 3 trên đúng sha review (`a2c462e`, cây `1e9d7e3`) thoát **0** với 8/8 bước `đạt`, 7175 test qua, độ phủ gói bị chạm 97,10% dòng / 92,11% nhánh; không có finding P0 hay P1 và tổng điểm 4,70 ≥ 4,0.

Lõi làm đúng ba pha mà K36 đòi và đúng thứ tự mười bước của khối [6]; nhánh phát lại thật sự chỉ làm những tác dụng chịu được giao lặp — J06 tuần tự, J06 song song và J10 đều khẳng định "đúng một" cho phiên bản, thông báo, mục `user_stream` và thông điệp `pipeline.quality.run`. Khung `Progress` phát đúng một lần ở nhánh ghi (`363ca00` đã gỡ lời gọi thứ hai; `__J01` khẳng định `len(progress) - before == 1`). Ánh xạ lỗi hẹp đúng chỗ — chỉ quanh `write_layer` — không `except Exception` ở đâu trong gói, và `ValueError` của các hàm ghi khác vẫn lan ra thành `INTERNAL` kèm stack. Bảy finding còn lại là một P2 hiệu năng đã có địa chỉ ngoài nhánh này (`NO-296` → B3-06), ba P3 dọn dẹp/sổ nợ và ba Nit.

**Điều kiện khi merge (không phải điều kiện để duyệt):**
1. Người điều phối commit 4 dòng `NO-296`–`NO-299` từ `debt-draft.md` vào `DEBT.md` cùng lần merge (finding 2).
2. Squash nhánh gộp luôn commit merge `7b3312c` của `feature/b5-06b-runtime`.
