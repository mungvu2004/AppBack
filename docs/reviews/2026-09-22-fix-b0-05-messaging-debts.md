# Review merge fix/b0-05-messaging-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, dòng `DEBT.md`, `docs/fixes.md` và báo cáo `W2-MESSAGING.report.md` đều tự kiểm lại) · Commit đầu nhánh: `83d533559a1b`. Gốc so sánh `55333dc` (= merge-base; tác giả đã gộp `main` hai lần: `f4223f2` @ `25dad10`, `c03b8c1` @ `55333dc`). 12 commit: 8 FIX (`b6c54ea` FIX-020 … `aa60797` FIX-027), 2 commit gộp, 2 commit sổ nợ (`22dee96` NO-065, `83d5335` NO-066).
- `main` hiện @ `7ba37ae` (sau gốc: gộp `fix/b0-07-contract-tool-debts` — chỉ `tools/case_gate.py`, `tools/contract/check.py`, `packages/testing/golden/recorder.py` + test, `DEBT.md`, một file review). `git merge-tree --write-tree main HEAD`: **một** xung đột, `DEBT.md` (NO-067 của `main` và NO-065/NO-066 của nhánh cùng nối vào cuối bảng); không file mã nào chồng nhau.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** — chạy tại chỗ trong worktree sạch của nhánh, 02:48:56Z → 02:55:23Z; mã thoát lấy từ `$?` của chính `run.sh` (shell bọc không bị cắt, không cần `docker wait`); trước lượt chạy đếm `docker ps -q --filter name=verify-run` = 1. Log: `C:/Users/mxuan/AppData/Local/Temp/claude/C--Users-mxuan-orca-workspaces-appback-fix-messaging/8ca4ccb2-6a8b-4fd7-bd79-8bf0258c7d18/scratchpad/verify.log`. **1962 passed, 0 failed, 10 skipped, 1 deselected** trong 323,2 s.
  - 10 skipped: tập tham số rỗng của `apps/api/core/tests/test_common.py` (có sẵn từ B0-06) — `coverage_gate` hỏng với mọi skip khác, nên bước 5 đạt là bằng chứng.
  - **1 deselected không phải test `gpu`** như đề bài giả định: trong cả repo chỉ có đúng một test mang marker `gpu|perf` — `packages/ml_contracts/tests/test_synthetic.py:225` `test_render_plan_performance`, `@pytest.mark.perf` (B5-01). Bước 5 chạy `-m "not gpu and not perf"` nên bỏ nó; bước 5b chỉ chạy `perf` khi đơn vị có test `perf` bị chạm hoặc nhánh `integration` (BE-00 §12) — nhánh chỉ chạm `packages/messaging` nên bước 5b in "perf: 0 đơn vị bị chạm". Hợp lệ, không phải test bị bỏ. (Probe H liệt kê tập `-m "gpu or perf"`.)
- Độ phủ (in từ `tools.coverage_gate`, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,32 %** · nhánh **97,17 %**
  - `packages/messaging`: dòng **100,00 %** · nhánh **100,00 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**
  - Tác giả báo 99,33 % / 97,22 % tổng; chênh 0,01–0,05 điểm là do `coverage` đo cả tiến trình con (`patch = ["subprocess"]`): số tiến trình con của worker bị `SIGKILL` (không ghi dữ liệu) khác nhau giữa các lượt.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (313 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (277 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa có `changes/*.md`) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B0-05.md` tồn tại, 3–10 dòng | đạt (10 dòng; nhánh không đổi phạm vi của prompt nên không phải sửa) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — cả 12 commit (dài nhất 70 ký tự, `aa60797`) |
| Trailer đọc được (R-36b) | đạt — `git log --format='%(trailers:key=Prompt,valueonly)'` in `B0-05` cho cả 12 commit; 8 commit FIX in thêm `Fix: FIX-020` … `FIX-027` |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không — diff chỉ có `DEBT.md` và `packages/messaging/**` (đúng [4] chung của FIX-020..027) |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — một `noqa` mới có mã và lý do (`S603`, `test_worker_lost.py:65`) |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

Không có điều kiện dừng sớm nào kích hoạt. Cỡ nhánh: ≈ 72 dòng logic sản phẩm (`locks.py` 37, `tasks.py` 28, `redis.py` 7) + ≈ 305 dòng test/probe — dưới trần 400 của MNT-05.

## Công cụ kiểm tại chỗ

Mọi probe chạy trong container verify (`bash tools/verify/run.sh shell < probe.sh`, bản sao `/tmp/w`, `python -m pytest -p no:cacheprovider -o addopts=""`). Bản file của `main` đặt tạm dưới `.cache/probe/` (git-ignore), chép đè trong container rồi chép lại bản nhánh từ `/src`; cuối probe `cmp` bảy file với `/src` — không lệch. Log: `C:/Users/mxuan/AppData/Local/Temp/claude/C--Users-mxuan-orca-workspaces-appback-fix-messaging/8ca4ccb2-6a8b-4fd7-bd79-8bf0258c7d18/scratchpad/probe.log`.

- **P-A — FIX-021, FIX-022, FIX-027 (`tasks.py` của `main` + `test_tasks.py` của nhánh):** `3 failed, 41 deselected`. `test_the_delivery_count_and_its_ttl_are_one_atomic_command` → `AssertionError: assert ['INCRBY', 'EXPIRE'] == ['EVAL']`; `test_an_on_failed_error_is_logged_briefly` → `error` là `RuntimeError('xxx…du-lieu-nguoi-dung-o-cuoi')` (repr đầy đủ, có đuôi dữ liệu) và log in cả stack; `test_the_worker_process_closes_its_event_loop_on_shutdown` đỏ (không có handler `worker_process_shutdown`). Bản nhánh: `3 passed`.
- **P-B — FIX-022 (`redis.py` của `main`):** `test_process_local_reset_forgets_the_value` đỏ (`reset()` trả `None`) → `1 failed, 1 passed` (test "không trả tài nguyên của tiến trình cha" xanh cả trên mã cũ, đúng vì mã cũ luôn trả `None` — nó chốt biên, không chốt lỗi). Bản nhánh: `2 passed`.
- **P-C — FIX-023, FIX-025 (`locks.py` của `main` + `test_locks.py` của nhánh):** `4 failed` — hai lần `Failed: DID NOT RAISE LockLost` (thân nuốt huỷ; thân chặn đồng bộ), `assert current.cancelling() == 0` → `1 == 0` (thân đổi lượt huỷ thành lỗi riêng: mã cũ không `uncancel`), và `AppError: DEPENDENCY_UNAVAILABLE` che `ZeroDivisionError` của thân (đúng công thức NO-028). Bản nhánh: `4 passed`.
- **P-D — FIX-024 (test cũ ↔ test mới, cùng mã nhánh, chèn trễ bằng plugin pytest để giả lập máy tải):**
  - trễ 120 ms sau mỗi `acquire`: `test_an_expired_owner_cannot_renew_or_release_the_new_owner` **cũ** đỏ `assert 0 == 1` (khoá TTL 100 ms của chủ mới hết hạn trước lượt `EXISTS`); bản **mới** cùng trễ `2 passed` (kèm `test_the_second_holder_gets_a_larger_fence_token`).
  - trễ 250 ms trước mỗi lần gia hạn: `test_hold_keeps_the_lock_alive_past_three_ttls` **cũ** đỏ `LockLost: gpu:0` (TTL 300 ms < 80 + 250 ms); bốn test `hold` **mới** (đẩy hạn, ngắt thân, nuốt huỷ, đổi lỗi) cùng trễ `4 passed`. Tức là test mới chịu được độ trễ gấp hai–ba lần biên cũ, không chỉ "xanh khi máy rảnh".
- **P-E — thêm cho `hold()` (test tạm, đã xoá):** `4 passed` — (1) khoá bị **người khác lấy** trong lúc thân chặn đồng bộ 300 ms → `LockLost`, khoá của chủ mới còn nguyên và chủ mới `release` được (`True`); (2) huỷ từ ngoài → task kết thúc `cancelled()`, khoá được trả; (3) `asyncio.timeout(0.3)` bọc ngoài → `TimeoutError` (không bị đổi thành `LockLost`), khoá được trả, `cancelling() == 0`; (4) mất khoá dưới `asyncio.timeout(10)` chưa hết giờ → `LockLost`, `cancelling() == 0` (timeout ngoài không đọc nhầm lượt huỷ).
- **P-F — `test_locks.py` bản nhánh ×3:** `22 passed` cả ba (5,1 / 5,0 / 6,0 s).
- **P-G — FIX-020, `test_worker_lost.py` ×3:** `1 passed` cả ba; pha `call` **3,57 / 3,55 / 2,95 s** (cả phiên 7,4 / 7,0 / 5,4 s), khớp số đo 3,2–8,3 s của tác giả.
- **P-G2 — đột biến `task_reject_on_worker_lost=False` (`celery_app.py:66`):** `1 failed` sau 65 s — `AssertionError: quá 60.0 s mà chưa: lượt giao 2 vào thân` (thông điệp bị ack khi tiến trình con chết, không quay lại hàng). Test chặn đúng cơ chế giao lại.
- **P-G3 — đột biến trần `_deliveries(task) > MAX_DELIVERIES + 1` (`tasks.py:295`):** `1 failed` sau 69 s ở `wait_for(... "on_failed nhận mã hỏng")` — lượt 4 lại vào thân thay vì báo `WORKER_LOST`. Test chặn đúng trần.
- **P-H — tập bị bỏ ở bước 5:** `pytest --collect-only -m "gpu or perf"` → `1/1973 tests collected`; `grep` marker `gpu|perf|pytestmark|marks=` trên `apps packages tests deploy` chỉ ra `packages/ml_contracts/tests/test_synthetic.py:225` `@pytest.mark.perf`. Đó là test "deselected" của bước 5.
- Ghi chú quy trình: probe ngắn thứ hai (in dòng tổng của P-A: `3 failed, 41 deselected` — đúng ba test `…logged_briefly`, `…one_atomic_command`, `…closes_its_event_loop_on_shutdown`) khởi động khi đếm `verify-run` = 2, **trái** trần < 2 của người điều phối; lượt đó chạy ~30 s rồi thoát. Cổng và probe chính đều khởi động khi đếm = 1.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-07 · MNT-03 | Sau lần gộp `c03b8c1`, logic "trả khoá; Redis hỏng (`DEPENDENCY_UNAVAILABLE`) thì ghi `WARNING` rồi bỏ qua, TTL dọn hộ, không che lỗi của thân" có **hai** bản: `SafeLock._release_quietly` (FIX-025, riêng tư) và `_Keeper._release` của `apps/ml/runtime/gpu.py` (B5-01, vào `main` ở `55333dc`). Hai nhánh viết song song nên không ai thấy lần thứ hai; lúc gộp, tác giả `grep` người gọi trên `f4223f2` (trước B5-01) và không `grep` lại sau `c03b8c1` — báo cáo vẫn ghi "không ai ngoài gói dùng `SafeLock`/`release`", sai với `gpu.py:23,74,101,116,132`. Hành vi hiện **tương thích** (gpu bỏ qua giá trị `bool` mới của `release`; bài `apps/ml/runtime/tests/test_device_gpu.py` xanh trong cổng), chỉ là trùng lặp | `packages/messaging/locks.py:103-112`; `apps/ml/runtime/gpu.py:129-136` | B0-05 đổi `_release_quietly` thành công khai (`release_quietly(token) -> bool \| None`, trả `None` khi đã nuốt lỗi phụ thuộc), B5-01 thay thân `_Keeper._release` bằng `runner.run(lock.release_quietly(token))` (K27: FIX cho B5-01). Không chặn merge; ghi `DEBT.md` (dòng đề xuất dưới) |
| 2 | Nit | R-02 · R-05 | Docstring `reset_runner` viết "`Runner.close()` … để engine async đóng đàng hoàng": `Runner.close()` (CPython 3.12 `asyncio/runners.py`) chỉ huỷ task còn treo, `shutdown_asyncgens`, `shutdown_default_executor(THREAD_JOIN_TIMEOUT)` rồi đóng vòng — **không** `dispose()` engine SQLAlchemy nào (sessionmaker của worker gắn theo vòng ở `packages/db/engine.py:70-79`). Nó cũng thêm một trần chờ ngầm: `shutdown_default_executor` đợi luồng của executor mặc định tới 300 s, nên một `asyncio.to_thread` kẹt làm tiến trình con tắt chậm tới 5 phút (trước FIX-022 tiến trình thoát ngay) | `packages/messaging/tasks.py:122-130` | Sửa câu thành "huỷ task treo, đóng async generator và executor mặc định (chờ luồng tối đa 300 s — trần của asyncio), rồi đóng vòng" để người đọc không tưởng engine đã được `dispose` |
| 3 | Nit | R-19 · SEC-13 | Lý do của FIX-027 ("stack in lại nguyên thông điệp, mà thông điệp của lỗi module khác có thể chứa dữ liệu người dùng") áp y hệt cho `task_failed` của nhánh "lỗi lạ của thân task" — thân task cũng là mã module khác, và dòng đó vẫn `_log.exception` (stack kèm thông điệp). Chọn giữ stack ở đó là đứng được (với lỗi lạ của thân, stack là thông tin gỡ lỗi duy nhất), nhưng hai chỗ cạnh nhau đang theo hai chính sách mà không chỗ nào nói vì sao | `packages/messaging/tasks.py:311-312` (đối chiếu `:252-266`) | Một câu trong comment `noqa: BLE001` ở `:311`: "giữ stack có chủ ý — lỗi lạ của thân là bug của module chủ, bộ che của `packages/core/logging.py` cắt bí mật" |
| 4 | Nit | R-06 · R-07 | `wait_for[T]` của `test_worker_lost.py` là bản thứ hai (trong cùng gói) của vòng hỏi có trần `wait_until` ở `test_tasks.py:85-92`; toàn repo có sáu bản (`apps/api/auth/tests/support.py:69`, `apps/api/core/tests/sample.py:406`, `apps/ml/runtime/tests/test_device_gpu.py:51`, `apps/ml/runtime/tests/test_probe_task.py:87`) | `packages/messaging/tests/test_worker_lost.py:36-45` | Không bắt sửa trong nhánh FIX; nếu gom: một `poll_until` đồng bộ + bản async ở `packages/testing/` (B0-01), `wait_for` giữ phần in đuôi log worker qua tham số `on_timeout` |
| 5 | Nit | R-05 | Đường nâng cấp ghi cạnh `FENCE_SUFFIX` (`HINCRBY` một hash có TTL dài hơn đời job) phức tạp hơn cần: **một** bộ đếm rào dùng chung `lock:fence` cho mọi tên khoá vẫn đơn điệu (đơn điệu toàn cục ⇒ đơn điệu theo từng tên), O(1) khoá, không TTL, không phải đoán "đời job" — đúng gợi ý của review merge 2026-09-20 finding #7. Lựa chọn của tác giả vẫn đúng, chỉ dài hơn | `packages/messaging/locks.py:25-30` | Nêu thêm phương án bộ đếm chung (lưu ý lúc chuyển: khởi tạo `lock:fence` bằng `max` các bộ đếm cũ để token không lùi) |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 4**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-020 (NO-022) — worker thật chết giữa task.** Worker `celery -A packages.messaging.tests.worker_probe worker -P prefork -c 1 -Q default --without-heartbeat --without-mingle --without-gossip` trong **nhóm tiến trình riêng** (`start_new_session=True`); dọn bằng `killpg(SIGTERM)`, quá 20 s thì `SIGKILL` cả nhóm — test hỏng giữa chừng không để lại tiến trình mồ côi. Test chỉ `SIGKILL` **tiến trình con** đang chạy task (PID do chính thân task ghi vào Redis an toàn), đúng cảnh "worker chết" của production; tiến trình cha thấy `WorkerLostError`, `task_reject_on_worker_lost=True` trả thông điệp về hàng. Ba lần giết → lượt 4 báo `WORKER_LOST` cho `on_failed` rồi ack, thân không chạy (đúng 3 PID, cả 3 khác nhau). **Không phụ thuộc giờ thật hay thứ tự:** mọi lượt chờ đọc **trạng thái** trong Redis (`LRANGE` PID, `GET` mã hỏng) với trần 60 s chỉ để không treo; `run_id` là UUID riêng; hàng `default` bị `DEL` đầu và cuối test (BE-00 §7 "Test task"); khoá Redis của probe có TTL 300 s và được xoá trong `finally`. `worker_probe.py` không bao giờ được nhập trong tiến trình test (lý do ghi ở docstring: `create_celery` đặt `DB_AFTER_COMMIT_INLINE` và app hiện hành cho cả tiến trình), tên `test_…` không khớp nên pytest không thu thập; task `tests.crash.hang` khai trong module `.tests.` nên `registered_tasks()` loại nó khỏi sổ của `case_gate`. Nhanh: 2,95–3,57 s pha `call` (P-G). Đột biến chứng minh test chặn đúng hai cơ chế nó nhắm (P-G2, P-G3).
- **FIX-021 (NO-023) — một `EVAL`.** `INCR` + `EXPIRE` trong một script Lua (`_COUNT_DELIVERY`), gọi `eval` (không `register_script`) để luôn đúng một vòng mạng kể cả lần đầu; không còn khe "đếm xong mà mất TTL". Chỉ `_deliveries` dùng bộ đếm này (`grep incr|expire` trong gói: còn lại là bộ đếm rào — cố ý không TTL, NO-029 — và `EXPIRE` stream 24 h, không phải cặp đếm). Test quan sát lệnh qua client **thật** (Redis vẫn chạy lệnh; K23 không bị vi phạm), khẳng định thêm `0 < TTL ≤ 86 400` và giá trị 1. Đỏ trước/xanh sau: P-A.
- **FIX-022 (NO-024) — đóng `Runner`.** `reset_runner()` gắn `worker_process_shutdown` — tín hiệu Celery phát **trong tiến trình con** của pool, đúng tiến trình đã mở vòng ở `worker_process_init`. `ProcessLocal.reset()` trả tài nguyên vừa quên **chỉ khi** nó thuộc PID hiện tại: không bao giờ đóng vòng/socket dựng trước `fork` của tiến trình cha (test bằng `os.getpid` giả — thay OS, không thay dịch vụ). Người gọi `reset()` khác (`celery_app.py:130`, `tasks.py:232`, `apps/ml/runtime/tasks_util.py:88`) bỏ qua giá trị trả về, tương thích. Chỉ handler của gói nghe `worker_process_shutdown` trong cả repo, nên test phát tín hiệu thật trong tiến trình test không kéo theo tác dụng phụ nào khác. Đỏ trước/xanh sau: P-A, P-B.
- **FIX-023 (NO-025) — `hold` không để thân "thoát êm" sau khi mất khoá.** Soi từng đường của `locks.py:137-156`: thân ném khi chưa mất khoá → trả khoá êm rồi ném lại nguyên trạng (kể cả `CancelledError` từ ngoài — P-E2, `asyncio.timeout` — P-E3); mất khoá + `CancelledError` → `uncancel()` rồi `LockLost` (không để lượt huỷ của vòng gia hạn rò ra `asyncio.timeout` bên ngoài — P-E4, test `cancelling() == 0`); mất khoá + thân đổi lượt huỷ thành lỗi riêng → `uncancel()` rồi để lỗi đó đi qua; thân nuốt huỷ và thoát bình thường → `LockLost`; thân chặn đồng bộ (vòng gia hạn không chen được) → `release` (nay trả `bool` từ script so đuôi token) thấy khoá không còn là của mình → `LockLost`, và **không đụng** khoá của chủ mới (P-E1). `lost` được đặt và `holder.cancel()` được gọi liền nhau không qua `await` nào, nên hai cờ luôn khớp. Giới hạn còn lại (không ngắt được thân **giữa chừng**) là của asyncio và đã ghi ở docstring kèm câu "việc rất dài tự gọi `renew()`… phía ghi dùng token rào" mà spec [5] đòi. Làm nhiều hơn spec tối thiểu (spec cho phép chuyển `➖` chỉ với docstring) nhưng vẫn trong [4], cùng một nợ, không đổi tên/hàng/payload — đứng được. Người gọi `SafeLock` ngoài gói duy nhất (`apps/ml/runtime/gpu.py`) không dùng `hold`, nên đổi hành vi lúc thoát không chạm ai. Đỏ trước/xanh sau: P-C.
- **FIX-024 (NO-027) — test khoá theo trạng thái.** "Hết hạn" dựng bằng `DEL`; "gia hạn kịp" khẳng định bằng quan hệ (`PTTL` bị đẩy lên lại ≥ 3 lần, hỏi mỗi 10 ms, trần 30 s); thân dài chờ một `Event` không bao giờ bật (trần 30 s) thay vì `sleep(TTL×4)`; TTL 5 000 ms = 50 × chu kỳ gia hạn 100 ms. Không còn `sleep` đoán giờ nào trong file (`grep sleep|monotonic` chỉ còn vòng hỏi `PTTL`). P-D chứng minh bằng trễ chèn có chủ ý: test cũ đỏ, test mới xanh dưới cùng độ trễ.
- **FIX-025 (NO-028) — lỗi trả khoá không che lỗi thân.** `_release_quietly` chỉ nuốt `AppError` — và `redis_errors()` chỉ sinh đúng `DEPENDENCY_UNAVAILABLE` (`redis.py:176-196`), nên "chỉ nuốt lỗi phụ thuộc" trong docstring là chính xác; lỗi lạ vẫn nổi lên. Đường thân xong bình thường giữ nguyên: `release` hỏng vẫn ném 503 (người gọi cần biết). Log `lock_release_failed` mang tên khoá và mã lỗi, không token. Test theo đúng công thức NO-028; chu kỳ gia hạn `TTL - 1` và thân không có `await` nào trước khi ném, nên vòng gia hạn không bao giờ kịp chạy — tất định, không phụ thuộc tải. Đỏ trước/xanh sau: P-C.
- **FIX-026 (NO-029, `➖`) — chấp nhận đứng được (R-05).** Comment cạnh `FENCE_SUFFIX` có **ngưỡng** (~70 byte mỗi tên khoá, tên cố định → vài KB, không bao giờ thu hồi trên `noeviction`), **đường nâng cấp** (bộ đếm theo job có TTL — xem Nit #5), và **ràng buộc bàn giao** cho B6-03a. Đã kiểm điều kiện của chấp nhận: người dùng `SafeLock` duy nhất trong repo là `gpu.py` với tên cố định `gpu:0` (B1-01 **không** dùng `SafeLock` cho khoá đăng nhập — mối lo "một bộ đếm mỗi email" của review 2026-09-20 finding #7 không thành hiện thực); claim huấn luyện của BE-00 §7 dùng token 32 hex so bằng Lua riêng, không dùng token rào của gói này. Dòng `DEBT.md` ghi rõ điều kiện đổi ý ("khi có tên khoá theo id không giới hạn").
- **FIX-027 (NO-030).** `_fail` ghi `ERROR` với `error = "<Lớp>: <200 ký tự đầu>"`, không stack (stack in lại nguyên thông điệp); test khẳng định giá trị chính xác, `exc_info is None`, và đuôi dữ liệu không có trong `caplog.text`. Đỏ trước/xanh sau: P-A. (Chính sách khác ở `task_failed` — Nit #3.)
- **Hợp nhất với `main`.** Người gọi các API nhánh đổi (`grep` trên HEAD, sau cả hai lần gộp): `SafeLock.release` → `apps/ml/runtime/gpu.py:132` (bỏ qua giá trị, tương thích); `ProcessLocal.reset` → `celery_app.py:130`, `tasks.py:232`, `apps/ml/runtime/tasks_util.py:88` (bỏ qua giá trị); `hold`, `LockLost`, `reset_runner`, `_deliveries`, `_fail`, `worker_process_shutdown` → không ai ngoài gói. `mypy --strict` 277 file đạt, toàn bộ test của B0-06, B0-07, B1-01, B3-01, B5-01 xanh trên mã nhánh. `main` đi thêm từ gốc (`7ba37ae`) không chạm `packages/messaging/**`.

## Tuyên bố của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Cổng lượt 3 trên `83d5335` mã thoát 0; `1962 passed, 10 skipped` | **Đúng** — lượt độc lập của review ra cùng số |
| 2 | Độ phủ `packages/messaging` 100 % / 100 %; tổng 99,33 % / 97,22 % | **Đúng** (lượt review 99,32 % / 97,17 % tổng — chênh do đo tiến trình con) |
| 3 | "Không ai ngoài gói dùng `SafeLock`/`hold`/`release`/`LockLost`, `ProcessLocal`…" | **Sai một phần**: đúng trên `f4223f2` lúc tác giả `grep`, sai sau lần gộp `c03b8c1` — `apps/ml/runtime/gpu.py` dùng `SafeLock.acquire/renew/release`, `apps/ml/runtime/tasks_util.py` dùng `ProcessLocal.reset`. Không gây lỗi (xem mục hợp nhất), nhưng dẫn tới finding #1 |
| 4 | `test_worker_lost.py` 3,2–8,3 s | **Đúng** — P-G 2,95–3,57 s |
| 5 | Đột biến `task_reject_on_worker_lost=False` → đỏ ("lượt giao 2 không bao giờ tới") | **Đúng** — P-G2, cùng thông báo; review thêm đột biến trần (P-G3), cũng đỏ |
| 6 | Đỏ trước/xanh sau của FIX-021..025, FIX-027 như ghi ở `DEBT.md` | **Đúng**, từng thông báo lỗi khớp (P-A, P-B, P-C); FIX-023 còn thêm một test đỏ-trước tác giả không kể (`…raised_after_losing_the_lock_through`, `cancelling() 1 == 0`) |
| 7 | Gộp `main` hai lần, không rebase (giữ sha FIX-020..027 ở `docs/fixes.md`) | **Đúng** — sha trong bảng `docs/fixes.md:29-36` đều là tổ tiên của HEAD; `DEBT.md` sau gộp không mất dòng, không trùng id |
| 8 | NO-065 tái hiện được, gốc đã rõ | **Đúng** — `test_new_revision.py:14` tính `TODAY` một lần lúc nhập, `new_revision.py:66` đọc `datetime.now(UTC)` lúc gọi; hai test dùng `TODAY` (`:60-69`, `:80-83`) là đúng hai test tác giả nêu |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| NO-022..NO-025, NO-027, NO-028, NO-030 chuyển `✅` kèm ngày đóng, mã FIX, test đỏ-trước và thông báo đỏ | đạt — mỗi thông báo đỏ ghi trong dòng khớp đúng probe P-A…P-C; FIX-024 ghi số lượt đỏ dưới tải (1/12, 2/16) và 16/16 xanh sau |
| NO-029 `➖` có lý do đứng được, ngưỡng, đường nâng cấp (R-05) | đạt — xem FIX-026 ở trên; "đổi ý khi có tên khoá theo id không giới hạn" là điều kiện kiểm được |
| **NO-065** (B0-03, P3) đúng sự thật, đúng chủ, đúng mức | đạt — cơ chế đã kiểm ở mã (tuyên bố #8); chủ đúng (`packages/db/**` là B0-03); P3 khớp tiền lệ cùng lớp NO-016 (test trộn giờ thật, B0-04, P3). Hướng sửa (tiêm `Clock` vào `new_revision`, R-18) đúng gốc, không nới assert |
| **NO-066** (B1-01, P2) đúng sự thật, đúng chủ, đúng mức | đạt — `_denied` tăng bằng `bump` (`MULTI` nguyên khối, `login_guard.py:76-88`), nên thừa 401 chỉ có thể do `soft_redis(bump…)` trả `None` (`services.py:49-62`); `CONNECT_TIMEOUT_S = 2.0` (`redis.py:36`) đúng như dòng nợ; cửa sổ 60 s (`settings.py:44`) quá dài để hết hạn giữa test, nên giả thuyết "kết nối mới quá trần" là giả thuyết hợp lý còn lại. "Chưa xác định" + 14 lượt xanh + giả thuyết đã loại, không retry/không nới assert — đúng R-35. P2 khớp TEST-02 và tiền lệ NO-027 (test chập chờn chặn cổng). Chủ đúng (test và `router.py` của B1-01) |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh này | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — dòng đề xuất dưới |

Dòng đề xuất (id do người điều phối cấp; phiên này **không** ghi vào `DEBT.md`):

- `| ⬜ | NO-<nnn> | 2026-09-22 | | Logic "trả khoá; Redis hỏng thì WARNING rồi bỏ qua (TTL dọn hộ), không che lỗi của thân" có hai bản: SafeLock._release_quietly (FIX-025) và _Keeper._release của apps/ml/runtime/gpu.py (B5-01) | Hai nhánh viết song song (fix/b0-05-messaging-debts và feature/b5-01), gặp nhau ở lần gộp c03b8c1; bản của B0-05 là riêng tư nên B5-01 không gọi được | B0-05 (packages/messaging/locks.py:103-112) · B5-01 (apps/ml/runtime/gpu.py:129-136) | P3 | mở — review merge 2026-09-22 finding #1 (docs/reviews/2026-09-22-fix-b0-05-messaging-debts.md), trái R-07. Chữa: B0-05 công khai release_quietly(token); B5-01 gọi runner.run(lock.release_quietly(token)) (FIX cho B5-01, K27) |`
- Nit #2–#5: tác giả tự quyết, không cần dòng nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (Nit #3) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #4) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (Nit #2) | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #1; Nit #5) | 0,12 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,12 = **4,97 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập (1962 passed, 0 failed; 10 skip là tập tham số rỗng hợp lệ; 1 deselected là test `perf` của B5-01, không phải test bị bỏ), `packages/messaging` và tập file bị chạm phủ 100 % dòng và nhánh, không có P0/P1/P2, điểm 4,97 ≥ 4,0. Cả tám FIX sửa đúng gốc trong đúng [4] (`packages/messaging/**`), và đỏ trước/xanh sau đã **tự tái hiện** chứ không lấy từ báo cáo: FIX-021/022/027 đỏ trên `tasks.py`/`redis.py` của `main`, FIX-023/025 đỏ 4/4 trên `locks.py` của `main`, FIX-024 được chứng minh bằng độ trễ chèn có chủ ý (test cũ đỏ, test mới xanh cùng độ trễ), FIX-020 là worker prefork thật bị `SIGKILL` — không phụ thuộc giờ thật hay thứ tự, 3–3,6 s, và đột biến hai cơ chế nó nhắm đều làm nó đỏ. Phần rủi ro nhất — đường thoát mới của `SafeLock.hold` — đúng ở mọi nhánh đã soi, kể cả tương tác với `asyncio.timeout` bên ngoài và khoá đã sang tay chủ mới. NO-029 chấp nhận có ngưỡng và đường nâng cấp; hai dòng nợ mới NO-065/NO-066 đúng sự thật, đúng chủ, đúng mức. Hợp nhất với `main` sạch về mã; người gọi duy nhất ngoài gói mà báo cáo tác giả bỏ sót (`gpu.py`) vẫn tương thích.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): ghi dòng `DEBT.md` đề xuất ở trên cho finding #1 (P3, `⬜`, chủ B0-05 + B5-01). Nit #2–#5 do tác giả tự quyết, không chặn merge.
2. Gộp `main` @ `7ba37ae` (hoặc mới hơn) vào nhánh — hay giải ngay lúc merge — xung đột **chỉ** ở `DEBT.md`: giữ **cả** NO-065, NO-066 của nhánh **và** NO-067 của `main`, xếp theo id; không dòng nào khác đổi. Nếu gộp lại trên nhánh thì chạy lại cổng một lượt (mã `main` mới chỉ ở `tools/case_gate.py`, `tools/contract/check.py`, `packages/testing/golden/recorder.py`, không giao với nhánh).
3. Cách gộp khuyến nghị: `git merge --no-ff fix/b0-05-messaging-debts` — **không** squash: giữ tám commit FIX với sha đã ghi ở `docs/fixes.md:29-36` (FIX-020..027) cùng trailer `Prompt: B0-05` + `Fix: FIX-0nn` (R-36; tiền lệ `fix/b0-07-contract-tool-debts` @ `7ba37ae`).
