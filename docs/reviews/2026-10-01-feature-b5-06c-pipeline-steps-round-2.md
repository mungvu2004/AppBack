# Review merge feature/b5-06c-pipeline-steps → main — lượt 2

- Ngày: 2026-10-01 · Reviewer: phiên /merge-review (lượt 2, R-37 phiên độc lập) · Commit đầu nhánh:
  `b8db169` (worktree review `git switch --detach b8db169`, không đụng nhánh trong `F:/AppBack`)
- **Phạm vi lượt 2:** chỉ `git diff 1d7e55b..b8db169` — vòng sửa F1–F4 của phán quyết lượt 1
  (`docs/reviews/2026-10-01-feature-b5-06c-pipeline-steps.md`, dòng 59–62). Phần còn lại của nhánh
  đã duyệt ở lượt 1 (APPROVE WITH COMMENTS, 4,45/5) và không được soát lại ở đây.
- **Phạm vi kiểm: đích** (R-33b, lượt ≥ 2 chỉ soát diff vòng sửa). Diff không chạm điều kiện (2)–(7)
  của R-33b: không migration, không hợp đồng, không phụ thuộc mới, không tệp cấu hình cổng, không
  mã dùng chung ngoài module. Phiên này **không chạy container nào** (cổng đầy đủ xdist đang chạy
  một mình trên cùng sha); chứng cứ là mã thoát thật của tiền kiểm và của cổng đầy đủ.
- Diff: 5 tệp, tất cả `⊆ apps/worker/pipeline_steps/**` (1 tệp lõi + 4 tệp test), +143 / −39.
  Không chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `DEBT.md`, `changes/B5-06c.md`, hay thư
  mục của prompt khác (R-27 đạt). Cây sạch.
- Commit `b8db169`: dòng đầu `fix(pipeline-steps): count last_used_at in the sweep idle mark`
  (58 ký tự, Conventional Commits), thân nêu F1–F4, trailer `Prompt: B5-06c` — đạt BE-00 §13.2.
- Không `# pragma: no cover` / `pragma: no branch` / `# noqa` trần / `# type: ignore` / `skip` /
  `xfail` mới trong diff (grep trên chính diff). Không hạ ngưỡng cổng nào.
- R-01: mọi thứ mới có docstring — `_requeue_body`, docstring mới cho `_IDLE_MARK`, docstring mở
  rộng cho `_CANDIDATES`, và cả ba test mới nêu **lý do** test tồn tại.

## Bảng cổng (E.10, từ mã thoát thật)

Hai nguồn, cả hai trên đúng sha `b8db169` (`M/gate.sha` = `b8db169`).

**A. Tiền kiểm đích `M/pre-8.log` — chạy xong, thoát 0** (`set -euo pipefail`; dòng cuối in
`PREFLIGHT OK b8db169` nên mọi lệnh trước đó đã thoát 0):

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 1 | `ruff format --check .` | đạt | 1174 tệp đã định dạng |
| 2 | `ruff check .` | đạt | All checks passed |
| 3 | `mypy` (strict) | đạt | 982 tệp nguồn, 0 lỗi |
| 4 | `lint-imports` | đạt | 10 kept / 0 broken |
| 5 (đích) | `coverage run --branch -m pytest -m "not perf" apps/worker/pipeline_steps` | đạt | **61 passed**, 33,87 s (lượt 1: 58 → đúng 3 test mới) |
| 5b (đích) | `preflight.py` (case/perf của module) | đạt | `PREFLIGHT OK b8db169`, không phát hiện |

**B. Cổng đầy đủ `M/gate-2.log` — chạy xong, `mã thoát: 0`** (bảng cuối log, mọi dòng dưới đây đọc
từ chính bảng đó, không từ báo cáo của ai):

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | 1174 tệp đã định dạng |
| 2 | `ruff check` | đạt | All checks passed |
| 3 | `mypy --strict` | đạt | 982 tệp nguồn, 0 lỗi |
| 4 | `lint-imports` | đạt | 10 kept / 0 broken |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | **7236 passed**, 453,94 s (lượt 1: 7233 → đúng 3 test mới); `coverage_gate: đạt` |
| 5b | `pytest -m perf` → `case_gate` | đạt | `perf: 0 đơn vị bị chạm`; `case_gate: đạt` (77 thao tác, 3 cảnh báo cũ `files_read_object`/`health_*`) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 20 revision; 10/10 kiểm `migrate_check` đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | AppFront `9cf0b0bfffbd`, 83/83 dòng BE-BIND, 80 đã mount |
| 8 | `openapi` | đạt | ghi 236 965 byte |

**mã thoát: 0.** Không bước nào "không áp dụng" và không bước nào bị bỏ. Hai số của `coverage_gate`
trên cây đầy đủ: **tổng dòng 99,48 % · nhánh 98,09 %**; **tập tệp bị chạm
(`apps/worker/pipeline_steps`) dòng 99,10 % · nhánh 96,77 %** — cả hai cặp ≥ 90/90, và khớp đúng
con số tiền kiểm đích ở trên (99,1 / 96,8), nên hai nguồn xác nhận lẫn nhau.

### Độ phủ từng tệp (tiền kiểm đích)

Từ `M/pre-8.log`, `coverage report --branch --include='apps/worker/pipeline_steps/*'`:

| Tệp | Stmts | Miss | Branch | BrPart | Dòng | Nhánh | Thiếu |
|---|---|---|---|---|---|---|---|
| `step_done.py` | 153 | 1 | 40 | 1 | **99,3 %** | **97,5 %** | 181 |
| `sweep.py` | 90 | 2 | 20 | 1 | **97,8 %** | **95,0 %** | 168–169 |
| `purge.py`, `jobs.py`, `tasks.py`, `settings.py`, `errors.py` | — | 0 | — | 0 | 100 % | 100 % | — |
| **Tổng module** | 333 | 3 | 62 | 2 | **99,1 %** | **96,8 %** | |

Mọi tệp đổi ≥ 90 % dòng **và** ≥ 90 % nhánh. So với lượt 1 (`M/pre-7.log`: `step_done.py` 97 %,
thiếu `87-90, 181`): **`87-90` đã được phủ** — đúng chỗ F4 chỉ ra. `sweep.py` thiếu `168-169` là
**đúng hai dòng đã thiếu từ lượt 1** (khi đó đánh số `148-149`), không phải thiếu mới của vòng sửa.

## Soát từng mục yêu cầu của lượt 2

| F | Yêu cầu | Phán | Bằng chứng |
|---|---|---|---|
| **F1** | `greatest(r.updated_at, m.updated_at, m.last_used_at)` ở **cả** `_CANDIDATES` và `_IDLE_MARK` | **đạt** | `sweep.py:58` (WHERE), `:63` (ORDER BY), `:72` (`_IDLE_MARK`) — cả ba vế đều có `m.last_used_at`. Cột là `Mapped[datetime \| None] = mapped_column(default=None)` (`packages/db/models/pipeline_orchestrate.py:33`) và `GREATEST` của Postgres bỏ qua `NULL`, nên lượt chưa có họ ML nào xong vẫn tính đúng — không cần `coalesce`, đúng đề xuất lượt 1. |
| **F1-test** | test đi qua `record_used` thật, không đặt tay `last_used_at` | **đạt, phân biệt được** | `test_sweep_rules.py:326-345` `test_sweep_keeps_run_whose_family_just_finished`: `set_idle(seconds=IDLE_S)` rồi gọi thẳng `pins.record_used(...)` + `commit`, rồi `sweep(...)`. Không một `update(...).values(last_used_at=...)` nào trong thân test. `record_used` ghi bằng `text()` thuần (`pins.py:53-58`: `SET used = …, last_used_at = now()`) nên chỉ cột đó nhảy — bỏ `m.last_used_at` khỏi `_CANDIDATES` là lượt lại vào lô và `llen(ML_QUEUE)` thành 3, test đổ. |
| **F2** | mọi nhánh `_requeue_one` qua `after_commit_idle` | **đạt** | Thân chuyển sang `_requeue_body` (`sweep.py:155-186`); `_requeue_one` còn đúng `async with session_scope(...): await _requeue_body(...)` rồi `await after_commit_idle(db)` không điều kiện (`:150-153`). Cả bốn `return` sớm (lượt mất, ghim mất, tươi, hết trần) giờ chỉ thoát hàm con. |
| **F2-test** | `__J07` khẳng định sự kiện `failed` không `endedAt` | **đạt, phân biệt được** | `test_sweep_cases.py:140-145`: `events[-1] == ("failed", "wallSegmentation", 5)` và `(last["error"], last.get("endedAt")) == (PIPELINE_STEP_TIMEOUT, None)`. Khẳng định **đo đúng thứ F2 nói**: fixture autouse `producer_reset` (`packages/testing/fixtures/messaging.py:63-68`) `delenv(DB_AFTER_COMMIT_INLINE)` quanh **mọi** test, nên test chạy ở chế độ executor — không có `after_commit_idle` thì `Progress failed` chưa kịp phát và `events[-1]` còn là `("running", …)`. |
| **F3** | `ORDER BY …, r.id` | **đạt** | `sweep.py:63`: `ORDER BY greatest(r.updated_at, m.updated_at, m.last_used_at), r.id LIMIT :batch`. `pipeline_run_models` một dòng một lượt (`pins.py` `on_conflict_do_nothing(index_elements=[run_id])`) nên `r.id` là khoá phá hoà toàn phần, khớp khuôn `purge._select_due`. Docstring mới nêu đúng lý do. |
| **F4** | test nhánh hỏng `queue_build` | **đạt, hai đường** | `test_step_done_rules.py:383-410` đi đường `step_done` (bản vẽ đổi `upload_id` giữa hai kết quả ML → `queue_build` → `load_run_context` `None`); `test_sweep_rules.py:348-366` đi đường quét bù (`_resend` → `current_step == BUILD_STEP` → `queue_build`, `with_drawing=False`). Hai test phủ đúng hai vế của `drawing is None or drawing.upload_id != run.upload_id` (`step_done.py:70`), và `step_done.py:87-90` hết thiếu phủ. |
| **helpers** | `set_idle` lùi cả `last_used_at` | **đạt, bắt buộc** | `helpers.py:286-291`. Không lùi cột này thì mọi test quét bù dựng một lượt **không** im và đổ hàng loạt — docstring nói đúng điều đó. Sửa nằm trong tệp test của chính module (R-27 đạt). |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| G1 | **P3** | TEST-11 | Nửa `_IDLE_MARK` của F1 **không có test phân biệt được**, và nhánh "tươi lại dưới khoá" tiêu thụ nó cũng không có test — đó đúng là hai dòng duy nhất không phủ của `sweep.py` (`168-169`: `sweep_run_fresh` + `return`). Bằng chứng: test F1 mới chặn lượt ngay ở `_CANDIDATES` nên `_requeue_one` **không bao giờ được gọi**; mọi test còn lại đi qua `set_idle`, mà `set_idle` đặt `updated_at` và `last_used_at` về **cùng** một mốc nên `greatest` ra cùng giá trị dù có `m.last_used_at` hay không; `__J10` (`test_step_done_cases.py:261`) đọc `_IDLE_MARK` nhưng đặt đồng hồ **tương đối** với chính giá trị đọc được nên cũng không phân biệt. Hệ quả: xoá `m.last_used_at` khỏi `_IDLE_MARK` thì **không test nào đổ**, và đúng cuộc đua mà `[6]` dựng `_IDLE_MARK` để chặn (`record_used` rơi vào **giữa** truy vấn chọn lô và `lock_run`) vẫn là mã không có lưới. | `apps/worker/pipeline_steps/sweep.py:72` (`_IDLE_MARK`) và `:167-169` (`sweep_run_fresh`) | Một test gọi thẳng `_requeue_one`, theo đúng khuôn `test_requeue_one_skips_run_that_changed_after_selection`: `set_idle(IDLE_S)`, rồi `record_used(...)` + `commit` **trước** khi gọi `_requeue_one` → không gửi gì, `step_requeue_count` giữ nguyên, log `sweep_run_fresh`. Một test đóng cả hai lỗ. |
| G2 | Nit | MNT-07 | Hai dòng cuối `__J07` đọc luồng sự kiện hai lần: `steps_seen(...)` đã gọi `event_bus.read_after(upload_stream(...), "0-0")` bên trong (`helpers.py:169`), rồi test gọi lại đúng lệnh đó để lấy `data` thô. | `apps/worker/pipeline_steps/tests/test_sweep_cases.py:142-145` | Một `read_after` rồi rút cả ba trường từ `events[-1].data`. Không chặn merge. |
| G3 | Nit | — | Trailer ghi `Co-Authored-By: Claude <noreply@anthropic.com>`, khác chuỗi `Claude Opus 5 <noreply@anthropic.com>` các commit khác của đợt dùng. BE-00 §13.2 chỉ bắt buộc `Prompt: <mã>` nên không phải vi phạm luật, chỉ lệch nhất quán. | thân commit `b8db169` | Không sửa (rewrite history đắt hơn giá trị). |

Đã soát và **không** có finding ở: `_requeue_body` không phải abstraction thừa (R-10 — một hàm con
để `after_commit_idle` ra khỏi `async with`, rẻ hơn `try/finally` quanh cả thân và không che lỗi);
`after_commit_idle(db)` gọi **sau** khi `session_scope` đóng session vẫn chạy được (chứng cứ đo:
`__J07` mới khẳng định sự kiện và 61/61 test qua, không phải suy luận); `_requeue_body` ném lỗi →
`session_scope` rollback → callback bị bỏ, đúng ngữ nghĩa, không mất sự kiện nào đã commit;
`greatest(…, m.last_used_at)` không đổi kế hoạch truy vấn theo hướng xấu (vẫn là biểu thức trên hai
bảng đã join, `LIMIT` vẫn chặn ở đầu); `r.id` phá hoà không phá `LIMIT` vì `pipeline_run_models`
một dòng một lượt; `last_used_at` `NULL` an toàn nhờ `GREATEST` bỏ `NULL`; không test mới nào mang
mã case trong tên và không test nào gắn `perf` (`preflight.py` xác nhận trên đúng sha); cả ba test
mới dùng dịch vụ thật (Postgres + Redis + `local_storage`, K23) và không đặt tay cột nào mà lõi
phải tự ghi; ba test mới chạy song song được (mỗi worker một DB, hàng `DEL` trước và sau qua
`clean_queues`); diff không thêm phụ thuộc, không chạm `uv.lock`/`pyproject.toml`; không tệp của
prompt khác bị sửa.

## Nợ

Phiên này không sửa `DEBT.md` (thuộc người điều phối). Trạng thái sau vòng sửa:

- **F1 (P2) → đóng được.** Sửa ở cả hai truy vấn, có test đi đường thật.
- **F2, F3, F4 (dòng P3 "vòng mài `pipeline_steps`") → đóng được.**
- **G1 (P3) mới** → một dòng `NO-<nnn>` P3: "`_IDLE_MARK` + nhánh `sweep_run_fresh` chưa có test
  phân biệt được", chủ B5-06c. Không chặn merge (R-35 chỉ chặn với P0/P1 mở).
- Lệch C của lượt 1 (tách `PIPELINE_PURGE_BATCH`) vẫn là P3 tuỳ chọn, không đổi.

## Điểm (phạm vi lượt 2)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 5 | 0,15 |
| **Tổng** | **100%** | | **4,93 / 5** |

CON lên 5 (lượt 1: 3): F1 là lỗi CON duy nhất của lượt 1 và đã sửa đúng gốc — ở **cả hai** truy
vấn, không chỉ chỗ triệu chứng (R-19). LOG lên 5 (lượt 1: 4) nhờ F2. TEST giữ 4 vì G1.

## PHÁN QUYẾT: APPROVE (4,93/5)

Vòng sửa làm đúng cả bốn việc được yêu cầu, không nhiều hơn: diff gọn trong
`apps/worker/pipeline_steps/**`, một tệp lõi và bốn tệp test, không tệp nào của prompt khác, không
một dòng nới lỏng cổng. Hai sửa đáng tiền nhất đều đi tới gốc chứ không vá triệu chứng — F1 vào
**cả** `_CANDIDATES` và `_IDLE_MARK` (một công thức, R-02), F2 đưa `after_commit_idle` ra khỏi mọi
nhánh thoát sớm thay vì dán thêm một lời gọi vào riêng nhánh hết trần — và hai test của chúng
**phân biệt được**: bỏ sửa đi thì test đổ, điều phiên này kiểm bằng cách đọc chính fixture
(`producer_reset` tắt `DB_AFTER_COMMIT_INLINE`) và chính `pins.record_used` (ghi `text()` thuần),
không tin lời báo cáo. Thiếu phủ duy nhất còn lại của module là hai dòng `sweep_run_fresh` đã thiếu
từ lượt 1, trùng với G1 — một dòng nợ P3, không chặn merge.

Cổng đầy đủ `gate-2` trên đúng sha `b8db169` **thoát 0**, cả chín bước `đạt`, `coverage_gate` 99,48 /
98,09 tổng và 99,10 / 96,77 cho tập tệp bị chạm — không điều kiện nào còn treo. Nhánh được merge vào
`main`; **việc merge thuộc phiên gọi**, phiên này không merge (R-37).
