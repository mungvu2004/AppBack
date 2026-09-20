# Review merge feature/b0-05-redis-celery-event-bus → main

- Ngày: 2026-09-20 · Reviewer: phiên `/merge-review` (độc lập, không phải tác giả) · Commit đầu nhánh: `9e7d5b8fe6fc` (gốc `7d2b01e`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong phiên này, 860 test xanh, 70,5 s cho bước 5)
- Độ phủ (in từ `tools.coverage_gate`, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,03 %** · nhánh **95,77 %**
  - `packages/messaging`: dòng **100,00 %** · nhánh **100,00 %**
  - `apps/worker`: dòng 100,00 % · nhánh 100,00 % · `packages/testing`: 98,53 % / 100,00 %
  - tập file bị chạm: dòng 99,39 % · nhánh 100,00 %
- Bảng cổng thật: 1 `ruff format` đạt · 2 `ruff check` đạt · 3 `mypy --strict` đạt · 4 `lint-imports` đạt · 5 `pytest → coverage_gate` đạt · 5b `perf → case_gate` đạt (0 đơn vị perf bị chạm) · 6 `lint_migrations → migrate_check` đạt · 7 `tools.contract.check` **không áp dụng** · 8 `openapi` **không áp dụng**.
  Hai bước "không áp dụng" đúng luật BE-00 §12 (chưa có `changes/B0-06.md`, `changes/B0-07.md`), **không** phải "hỏng".

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B0-05.md` tồn tại, 3–10 dòng | đạt (6 dòng nội dung) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt (69 ký tự, 1 commit) |
| Trailer `Prompt:` đọc được | đạt — `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `B0-05` (R-36b giữ được) |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `tools/**`, `conftest.py`, `.importlinter`, `pyproject.toml` gốc | **không** — `git diff --stat main...HEAD --` trên các đường này rỗng |
| `uv.lock` sửa tay | không — không đổi (không thêm thư viện ngoài) |
| `pragma: no cover` / `no branch` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | không có. Năm `# noqa` đều **có mã và có lý do** (`N818` ×2, `BLE001` ×2, `S603` ×1) — hợp lệ theo K24 |

Không có điều kiện dừng sớm nào kích hoạt.

## Ba điểm người gọi yêu cầu tự kiểm bằng mã

**1. `registered_tasks() -> list[str]` thay vì `list[TaskInfo]` — tác giả ĐÚNG.**
Kiểm bằng mã, không bằng lời: `tools/case_gate.py:513-515` `_real_task_names()` trả `list[str]`;
`evaluate(..., task_names: list[str])` làm `names = set(task_names)` (`case_gate.py:465`) rồi so **trực tiếp** với
`TaskRequirement.fn` của `cases.toml` (`:466-468`) và với khoá của `_task_found()`, vốn lấy từ nhóm `fn` của
`_TEST_TASK_RE = ^test_(?P<fn>.+)__(?P<case>J\d{2})$` (`:296`). CASE §2.3 viết nguyên văn "`fn` là tên hàm như
`registered_tasks()` trả". Trả dataclass thì mọi task đều báo thiếu J01/J06. Hiến chương thắng prompt (CLAUDE.md),
và `NO-020` ghi đúng, đúng mức, đúng chủ. Thêm một điểm đúng mà tác giả không nêu: `registered_tasks()` trả **list**
chứ không phải set, nên luật "hai task trùng tên hàm → hỏng" của CASE §2.3 (`case_gate.py:470-474`) vẫn bắt được.

**2. Sửa `packages/messaging/__init__.py` ngoài cột `so_huu` — KHÔNG phải vi phạm K27/R-27.**
`tools/case_gate.py:514` gọi `_optional_attr("packages.messaging", "registered_tasks")`, tức đọc **thuộc tính của gói**;
CASE §2.3 liệt kê "sổ task (`packages.messaging.registered_tasks()`)" là đầu vào. Không có `__init__.py` thì cổng case
im lặng bỏ qua sổ task mãi mãi. Ngoài ra BE-00 §2 ("mỗi prompt sở hữu **thư mục một cấp** của riêng nó") và §2.2
(dòng `define_task … registered_tasks … | packages/messaging | B0-05`) giao cả thư mục cho B0-05; file trên `main`
chỉ là một dòng docstring, không thuộc prompt nào khác. Hiến chương thắng cột `so_huu` của prompt. Lệch đã ghi
trong thân commit. Không tính finding (xem Nit #8 cho phần dư).

**3. `SafeLock.hold` báo mất khoá bằng `cancel()` — cơ chế đúng, nhưng có MỘT lỗ thật.**
Đã soi và **chạy thử trong container**:
- Đường huỷ/`uncancel` **đúng**: giả thuyết "keeper `cancel()` đúng lúc thân vừa xong nên `CancelledError` bị
  `suppress` ở `await keeper` nuốt mất" — tôi đã dựng kịch bản ép (thân kết thúc bằng `time.sleep` đồng bộ) và
  **không tái hiện được**: `__aexit__` của `asynccontextmanager` tự nó là điểm treo nên huỷ luôn tới `yield` trước
  `finally`; kết quả `hold() bao LockLost (dung)`, `task.cancelling() == 0`. **Không ghi thành finding** (không bằng
  chứng thì không phải finding).
- Rò khoá trong `finally` **không có**: `state.lost` → bỏ `release`, đúng; `release` lại so token bằng Lua nên không
  đụng khoá của chủ mới.
- **Lỗ thật:** `_Renewal.run` không bắt ngoại lệ, nên một lỗi Redis **tạm thời** ở `renew()` giết luôn vòng gia hạn
  mà `lost` vẫn `False` → xem finding **#2** (đã tái hiện, có số liệu).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | RES-04 / LOG-04 / C13 | `translate_redis_error` chỉ bắt `ConnectionError` và `TimeoutError`. **Đã đo trong container** (`redis-py` của lock hiện tại): `OutOfMemoryError` và `ReadOnlyError` kế thừa `ResponseError`, **không** kế thừa `ConnectionError`, nên `translate_redis_error(...)` trả `None`. Mà instance broker theo hiến chương **bắt buộc** `noeviction` (BE-00 §1) — `OutOfMemoryError` chính là chế độ hỏng *thiết kế sẵn* của nó, và `ReadOnlyError` là chế độ hỏng của một lượt failover. Hai hệ quả đã chạy thử: (a) `EventBus.publish` ném `OutOfMemoryError` **thô** → API trả 500 `INTERNAL` thay vì 503 `DEPENDENCY_UNAVAILABLE` + `retry_after` (C13); (b) nặng hơn: `_deliveries()` chạy `INCR` ở **mọi** lượt task, nên khi broker đầy, `_handle` rơi vào nhánh `except Exception` → `on_failed(payload, "INTERNAL")` **và ack**. Chạy thật: `oom_probe.apply(...)` → `state = SUCCESS`, `on_failed = [('oom-1','INTERNAL')]`, thân task **chưa từng chạy**, thông điệp đã biến khỏi hàng. Nghĩa là một lượt broker chạm `maxmemory` biến **toàn bộ** việc đang bay thành hỏng vĩnh viễn thay vì thử lại — trái `BE-00 §7` ("`DEPENDENCY_UNAVAILABLE` trong task là lỗi tạm") và R-16 | `packages/messaging/redis.py:156-164`; lan sang `packages/messaging/celery_app.py:37-41` (`BROKER_CONNECTION_ERRORS`), `tasks.py:207-211`, `tasks.py:263-265` | Thêm `redis.exceptions.OutOfMemoryError`, `ReadOnlyError`, `ClusterDownError` vào `translate_redis_error` (và vào `BROKER_CONNECTION_ERRORS`), giữ `ResponseError` còn lại (`WRONGTYPE`, script hỏng) nổi lên nguyên trạng. Test được bằng dịch vụ **thật**, không cần mock: `ephemeral_redis("noeviction")` + `CONFIG SET maxmemory 1` → mọi lệnh ghi trả OOM (tôi đã dùng đúng cách này) |
| 2 | **P1** | CON-05 / RES-01 | `_Renewal.run` gọi `await self._lock.renew(...)` **không bọc try**. `renew` đi qua `redis_errors()` nên một lỗi kết nối Redis **tạm thời** biến thành `AppError` và thoát khỏi `run()`: task gia hạn chết, `state.lost` **vẫn là `False`**, không ai huỷ thân, không ai ném `LockLost`. Thân tiếp tục chạy trong khi khoá hết hạn và người khác lấy được. Lỗi chỉ lộ ra **sau khi thân đã xong**, ném từ `finally` (`await keeper`), nên còn che luôn ngoại lệ thật của thân. **Đã tái hiện trong container**: keeper gia hạn đúng **1** lần rồi chết, thân chạy hết 1,2 s (= 3 lần TTL), `EXISTS lock:probe:lock == 0` (khoá đã mất), `hold()` **không** báo `LockLost`, chỉ ném lỗi Redis lúc thoát. Trái chính hợp đồng của `hold` ("mất khoá → `LockLost`", prompt B0-05 [2]) và trái RULE.md CON-05 ("xử lý lock hết hạn khi tác vụ chưa xong"). Tác động: BE-00 §7 dùng khoá này cho `training:slot` và `gpu:0` — hai tiến trình huấn luyện cùng chiếm một GPU. `NO-025` **không** phủ ca này (nó nói về thân tự nuốt `CancelledError`) | `packages/messaging/locks.py:136-143`, hệ quả ở `locks.py:118-123` | Trong `run()`, bọc `renew` bằng `try/except Exception`: lỗi Redis = **không chứng minh được còn giữ khoá** → fail-closed, đặt `self.lost = True` và huỷ thân (hoặc thử lại tối đa một lần trong phần TTL còn dư rồi mới bỏ cuộc). Đừng để ngoại lệ thoát khỏi `run()`. Test: `SafeLock` trên `ephemeral_redis`, `container.stop()` giữa thân → phải ra `LockLost`, không phải lỗi Redis từ `finally` |
| 3 | P2 | TEST-03 / R-14 | Hai test **bắt buộc theo prompt [8]** không có: (a) "J02 … `countdown` đúng `10, 60, 300` khi dùng cấu hình mặc định (kiểm qua `request`/`retry` của task đã bind)" — cả bộ test chỉ có `backoff_step(retries, (10, 60, 300))` với tuple **viết tay** (`test_tasks.py:203-206`) và `conf.task_retry_backoff_s == (10,60,300)` ở `test_settings.py:30`; không test nào chứng minh đường dây `settings → _retry_or_exhaust → task.retry(countdown=…)` truyền đúng giá trị, vì fixture `messaging_env` ép `TASK_RETRY_BACKOFF_S=0,0,0` cho **mọi** test task. (b) "Dò task … gói mẫu nối vào `apps.ml.__path__` → `registered_tasks()` có task của nó" — không có; khẳng định duy nhất về sổ là `registered_tasks() == []` (`test_tasks.py:193`). Hệ quả: nhánh `discover_submodules("apps.ml"/"apps.worker", "tasks")` trong `registered_tasks()` chưa bao giờ được chứng minh là **tìm thấy** thứ gì, và nửa "task" của `case_gate` (J01/J06) chưa từng chạy trên một sổ khác rỗng. Độ phủ 100 % **không** thay được hai khẳng định này | `packages/messaging/tests/test_tasks.py:191-206`; prompt B0-05 [8] | (a) một test gọi `run_always_transient.apply(...)` với `TASK_RETRY_BACKOFF_S` mặc định và bắt `countdown` (monkeypatch `Task.retry` hoặc đọc `Retry.when`); (b) một test dựng gói mẫu ở `tmp_path`, nối vào `apps.worker.__path__`/`apps.ml.__path__`, khẳng định tên hàm của nó **có** trong `registered_tasks()` rồi dọn `sys.modules` (khuôn `probe_package` của `test_schedules.py:34-48` đã sẵn) |
| 4 | P2 | OBS-01 / OBS-03 | Không log nào của đường hỏng mang `task_id`. `poison_message` ghi `{"task": <tên task>, "reason": …}` và cố ý **không** in thân (đúng); `task_failed` và `on_failed_error` cũng chỉ có tên task. Khi một thông điệp độc bị loại và **ack**, vận hành không còn cách nào truy ra *thông điệp nào* đã mất — tên task là hằng số, không phân biệt được lượt. `_handle` đang cầm sẵn `task` (có `task.request.id`) nên thông tin này có sẵn, chỉ là không truyền xuống | `packages/messaging/tasks.py:181`, `:219`, `:257`, `:264` | Truyền `task.request.id` (và `task.request.retries`) vào `extra` của cả bốn dòng log; `_parse` nhận thêm tham số `task_id`. Giữ nguyên luật không in thân |
| 5 | P2 | TEST-02 | Test khoá chốt hành vi bằng đồng hồ thật với biên rất hẹp: `TTL_MS = 300`, `RENEW_MS = 80`, và các thân chạy 1,05 s / 1,2 s. Cổng chạy trong container Linux, ENV cho phép **≤ 4 lượt verify song song**, và `NO-007` ghi chính chặng mạng tới Redis thỉnh thoảng kẹt. Một lần vòng sự kiện trễ > 300 ms là `test_hold_keeps_the_lock_alive_past_three_ttls` đỏ giả (khoá hết hạn) hoặc `test_hold_interrupts_the_body_when_the_lock_is_taken_away` đỏ giả. Cùng hạng lỗi với `NO-016` (P3 của B0-04) nhưng biên ở đây nhỏ hơn hai bậc độ lớn, và **chưa có dòng nợ nào** | `packages/messaging/tests/test_locks.py:12-13`, `:71-77`, `:89-102` | Nới `TTL_MS` lên cỡ 2 000 ms và `RENEW_MS` cỡ 300 ms (thời gian chạy thêm không đáng kể vì chỉ 3 test), hoặc khẳng định theo quan hệ (`await lock.renew(token) is True` sau khi vượt TTL) thay vì theo `EXISTS` đúng thời điểm |
| 6 | P3 | LOG-04 / R-16 | `hold()` gọi `await self.release(token)` **bên trong `finally`**. `release` đi qua `redis_errors()`, nên Redis trục trặc đúng lúc thoát sẽ ném `AppError` từ `finally` và **thay thế** ngoại lệ thật của thân (`ZeroDivisionError` của người gọi biến mất). Cùng đoạn `finally` cũng có thể ném lại lỗi mà keeper đã chết mang theo (xem #2) | `packages/messaging/locks.py:118-123` | Bọc `release` trong `finally` bằng `with suppress(AppError):` + một dòng log `lock_release_failed` — khoá sẽ tự hết hạn theo TTL, mất `release` không phải lỗi đáng che ngoại lệ của thân |
| 7 | P3 | R-05 / PERF-06 | Khoá rào `lock:{name}:fence` **không TTL** là ngoại lệ prompt [5] cho phép, và lý do (giữ tính đơn điệu của token) đứng được — nhưng comment chỉ nêu *lý do*, không nêu **ngưỡng** và **đường nâng cấp** như R-05 đòi. Hệ quả vận hành thật: một khoá vĩnh viễn cho **mỗi tên khoá từng dùng**, trên đúng instance bắt buộc `noeviction`. Khoá đăng nhập của B1-01 mang HMAC của email → một khoá rào mãi mãi cho **mỗi địa chỉ email từng thử đăng nhập. Không ai dọn, và `noeviction` nghĩa là chạm `maxmemory` thì **mọi** lệnh ghi hỏng (đúng ca của finding #1). Không có dòng `DEBT.md` | `packages/messaging/locks.py:19-21`, `:76-79` | Ghi vào comment ngưỡng (số khoá rào ước tính, mức `maxmemory` phải đặt) và đường nâng cấp; đường nâng cấp gọn nhất là **một** bộ đếm dùng chung `lock:fence` cho mọi khoá (vẫn đơn điệu toàn cục, O(1) khoá) thay vì một bộ đếm mỗi tên. Tối thiểu: thêm dòng `DEBT.md` giao B0-08 đặt `maxmemory` và cảnh báo |
| 8 | P3 | R-10 / MNT-02 | `__init__.py` tái xuất **38** tên, trong khi thứ `case_gate` cần là **một** (`registered_tasks`). Mặt công khai rộng làm mọi `import packages.messaging` kéo theo `celery_app`, `locks`, `redis`, `schedules`, `streams`, `tasks`; và nó **thiếu** đúng thứ `NO-026` bảo B0-06 gọi — `broker_redis_sync` không nằm trong danh sách, nên B0-06 buộc phải nhập từ `packages.messaging.redis` chứ không từ gói (dòng nợ nói khác) | `packages/messaging/__init__.py:8-73` (đối chiếu `DEBT.md` NO-026) | Hoặc thu gọn còn những tên BE-00 §2.2 liệt kê + `registered_tasks`, hoặc thêm `broker_redis_sync` và sửa câu chữ của `NO-026` cho khớp |
| 9 | P3 | TEST-02 | `_delivery_client` (`ProcessLocal[SyncRedis]`) không có đường `reset`, khác với `reset_producer_app()` và `reset_messaging_settings_cache()`. `test_streams.py:257-283` **đổi** `REDIS_BROKER_URL` sang một container tạm rồi dừng container đó; bất kỳ test task nào chạy sau mà `_delivery_client` đã được dựng sẽ dùng client trỏ vào container đã chết. Hôm nay chưa nổ vì thứ tự file may mắn. `NO-024` chỉ ghi `_runner`, không ghi cái này | `packages/messaging/tasks.py:44` | Thêm `reset_delivery_client()` cạnh `reset_producer_app()` và gọi trong fixture `producer_reset` (hoặc gộp thành một `reset_messaging_process_state()`) |
| 10 | Nit | SEC-13 | `_fail` ghi `"error": repr(exc)` của ngoại lệ do **mã module khác** ném. `on_failed` của B1-*/B5-* rất có thể nhét id, email hay đường dẫn vào thông điệp lỗi; `repr` đưa nguyên xi vào log | `packages/messaging/tasks.py:219` | Ghi `type(exc).__name__` thay cho `repr(exc)`; stack trace của `_log.exception` vẫn đủ để gỡ lỗi |
| 11 | Nit | TEST-02 | `test_after_commit_flag_does_not_leak_between_tests` và `test_the_inline_flag_does_not_survive_the_worker_fixtures` **phụ thuộc thứ tự chạy** (docstring của chính chúng nói "Test ngay sau…"); chạy lẻ thì chúng khẳng định đúng nhưng vô nghĩa. Prompt [8] đòi đúng khuôn này nên **không tính lỗi** — chỉ ghi lại để phiên sau biết | `packages/messaging/tests/test_celery_app.py:267-269`, `tests/test_tasks.py:429-431` | Giữ nguyên; nếu muốn chắc thì thêm một test tự gọi `create_celery` trong `subprocess` rồi kiểm env của tiến trình cha |
| 12 | Nit | MNT-04 | `beat_schedule()` duyệt `_SCHEDULES.values()` theo thứ tự chèn, trong khi `schedule_entries()` sắp theo tên và `discover_*` cố ý nhập **theo thứ tự tên**. Lịch của beat vì thế phụ thuộc thứ tự nhập module | `packages/messaging/schedules.py:60-69` | `for entry in sorted(_SCHEDULES.values(), key=…)`, hoặc dùng lại `schedule_entries()` |

**P0: 0 · P1: 2 · P2: 3 · P3: 4 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **K34 (chord/group/chain, `result_backend`):** không chỉ đúng mà còn **tự canh cho prompt sau** — `test_canvas_scan.py` quét AST **mọi** `.py` dưới `packages/` và `apps/`, bắt cả `from celery import chord` lẫn `from celery.canvas import group, chain`, cộng `.delay(`/`.apply_async(` trong `apps/api/**`; có test âm bằng cây giả ở `tmp_path` chứng minh bộ quét thật sự bắt được. `test_no_result_backend_is_configured` chốt `result_backend` rỗng.
- **K32 / J10 (`publish_once` nguyên tử):** script Lua `_PUBLISH_ONCE` chạy `GET` → (nếu chưa có) `XADD` → `SET … EX` trong **một** lượt Redis, trả id cũ ở lượt lặp; `KEYS`/`ARGV` dùng đúng, không nối chuỗi vào script (không có đường tiêm). `_Bus._once_call` là **một** nguồn tham số cho cả bản async và sync (đúng R-07, không chép–dán). Có test cùng khoá → cùng id + stream đúng một mục, khoá khác → hai mục, và hết TTL → mục mới.
- **RES-01 / R-24 (trần tường minh cho mọi lời gọi Redis):** bốn client async đặt `socket_connect_timeout=2` và `socket_timeout` theo vai; client Streams để `socket_timeout=30` **lớn hơn** `MAX_BLOCK_MS=25 000` và `_check_block_ms` từ chối `block_ms` vượt trần — đúng chỗ mà `XREAD BLOCK` hay làm treo. Bản đồng bộ 0,5 s vì nằm trên đường trả response. `producer_app` đặt `socket_timeout`/`socket_connect_timeout` = 1 s, `broker_connection_retry=False`, `max_retries=0`. Mỗi con số đều có test đọc lại từ `connection_pool.connection_kwargs`.
- **C13 chứng minh bằng dịch vụ thật (K23):** 503 + `retry_after=5` được chứng minh bằng cách **dừng container Redis thật** và bằng cổng bị từ chối, cho cả `EventBus.publish` lẫn `send_task` — không mock, không `fakeredis`. `translate_redis_error(ResponseError)` có test khẳng định **không** hoá 503 (đúng R-16) — chỉ tiếc là tập "lỗi phụ thuộc" thiếu hai lớp, xem finding #1.
- **Bộ đếm `WORKER_LOST` có trừ `retries`:** `_deliveries` trả `count - task.request.retries`, và có **hai** test đối xứng chốt cả hai chiều: đặt sẵn bộ đếm = 3 không kèm retry → `WORKER_LOST`; đặt sẵn = 3 kèm `retries=3` → **không** `WORKER_LOST`, task chạy bình thường. Đây đúng là cái bẫy mà một cài đặt cẩu thả sẽ rơi vào. Khoá đếm có TTL 24 giờ như prompt [6] đòi.
- **Phân loại lỗi trong `define_task` (J02/J03/J05/J08):** thứ tự bắt đúng — `TransientError` và `AppError(DEPENDENCY_UNAVAILABLE)` → lùi theo bậc rồi `RETRY_EXHAUSTED`; `PermanentError(code)` → đúng mã; `SoftTimeLimitExceeded` → `TASK_TIMEOUT`; còn lại → log kèm stack + `INTERNAL`. `AppError` mã **khác** `DEPENDENCY_UNAVAILABLE` đi đường `INTERNAL` chứ không thử lại, có test riêng. Thông điệp độc (không phải dict / sai schema / `schema_version` lệch) bị ack, **không** gọi `on_failed`, và có test chứng minh log **không** in thân (`"khong-duoc-in" not in caplog.text`). `on_failed` tự ném → log `on_failed_error`, worker sống.
- **`visibility_timeout` một giá trị:** cả `create_celery` và `_build_producer` đều lấy từ **cùng** trường `celery_visibility_timeout_s`, không có bảng theo hàng; `test_visibility_timeout_is_set_in_exactly_one_place` còn khẳng định `task_queues` rỗng (không có đường đặt theo hàng nào khác).
- **Ranh giới import (R-28):** `lint-imports` đạt; hợp đồng `messaging-isolated` giữ nguyên. Cách tránh vòng nhập của `registered_tasks` (nhập `schedules` **tại chỗ** trong thân hàm, kèm comment nói rõ tại sao) là đúng, không phải mẹo. `test_worker_main.py` chạy trong **tiến trình Python mới** và chứng minh `apps.ml`, `fastapi`, `starlette`, `uvicorn`, `jwt`, `argon2` **không** vào `sys.modules` của worker — đúng BE-00 §2.1 và §12.
- **Test task đúng khuôn BE-00 §7:** `celery_worker_factory(queues)` chỉ nghe hàng được nêu và **từ chối hàng lạ**; test đếm thông điệp tự `DEL` các hàng ở đầu và cuối; payload đọc qua `queued_payloads` (bóc vỏ base64 của kombu) chứ không so chuỗi thô — đúng cảnh báo của hiến chương. Không có `task_always_eager` ở đâu.
- **Cờ `DB_AFTER_COMMIT_INLINE` không rò:** `producer_reset` autouse dùng `monkeypatch.delenv` nên giá trị cũ tự được trả lại; có test chốt cờ vắng mặt sau `create_celery` và sau các fixture worker, và test chốt `producer_app()` **không** đặt cờ.
- **Sổ task và sổ lịch:** trùng tên task → `ValueError` **lúc nhập module** (cả `define_task` lẫn `periodic` dùng chung `register_task`, nên một task và một lịch cũng không thể trùng tên); `every < 60 s` → `ValueError`; `discover_submodules` **ném** khi module có thật mà nhập lỗi (có test), chỉ im lặng khi module không tồn tại — đúng nguyên tắc "im lặng ở đây là một task biến mất khỏi sổ".
- **Cấu hình fail-closed (OPS-02):** `MessagingSettings` không có mặc định cho hai URL Redis → thiếu biến là hỏng **lúc nạp**, không phải lúc gửi task đầu tiên; URL phải là `redis(s)://` có host; `TASK_SOFT_TIME_LIMIT_S` phải nhỏ hơn `TASK_TIME_LIMIT_S`; backoff phải 1–10 bậc và không âm. `assert_broker_policy` chạy ở `worker_init` và **dừng worker** nếu broker là `allkeys-lru`, có test cả hai chiều trên hai Redis thật khác chính sách.
- **R-23 (không chặn vòng sự kiện):** client đồng bộ chỉ xuất hiện ở đường **không** có vòng sự kiện (`_deliveries` trong thân task Celery, `SyncEventBus` cho `on_after_commit`, `assert_broker_policy` trong tín hiệu `worker_init`). Một `asyncio.Runner` mỗi tiến trình, dựng ở `worker_process_init`, có test chứng minh hai task `async` liên tiếp dùng lại **một** client `redis.asyncio` mà không lỗi "attached to a different loop".
- **S05 (client rớt không rò kết nối):** đếm `CLIENT LIST` trước/sau, huỷ `read_after(block_ms)` giữa chừng, `aclose()`, rồi khẳng định số kết nối trở lại như cũ.
- **Docstring (R-01, R-02):** mọi module, lớp và hàm công khai đều có docstring nói **tại sao** chứ không kể lại thân hàm — `sync_result` giải thích vì sao `redis-py` khai `Awaitable | Any`, `ProcessLocal` giải thích vì sao phải dựng lại sau `fork`, `_deliveries` giải thích vì sao phải trừ `retries`. Đây là phần làm tốt hơn mặt bằng chung của repo.

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-38 | Kết quả |
|---|---|
| `NO-019` … `NO-026` đúng nội dung, đúng chủ | **đạt, đã kiểm từng dòng.** NO-019: `tools/tests/test_case_gate.py:478` đúng là khẳng định `_real_task_names() == []`, chủ B0-01 đúng (`tools/**` ngoài quyền B0-05 theo [12]), và tái hiện được như tác giả mô tả. NO-020: đã kiểm bằng mã (xem mục "Ba điểm"). NO-021: đúng, cùng gốc với NO-006, chủ B0-08 đúng. NO-022: đúng — `start_worker` chạy `pool="solo"` trong luồng của tiến trình test. NO-023: đúng, `_deliveries` có hai lượt `INCR` + `EXPIRE`. NO-024: đúng, `_runner` không bao giờ đóng. NO-025: đúng nhưng **hẹp hơn thực tế** (xem finding #2). NO-026: đúng, nhưng câu "B0-06 gọi `broker_redis_sync()`" lệch với mặt công khai của gói (Nit #8) |
| Id tăng dần, không xoá dòng | đạt |
| Nợ P0/P1 còn `⬜`/`🔧` | đạt **ở thời điểm tác giả nộp** (không có P0/P1 mở). **Không còn đạt sau phiên này**: finding #1 và #2 là P1 → R-38 chặn merge cho tới khi **sửa**, không phải chỉ ghi nợ |
| Nợ tác giả **quên** ghi | **có 5**: (a) `translate_redis_error` bỏ sót lớp lỗi phụ thuộc (#1); (b) vòng gia hạn chết im lặng (#2); (c) hai test bắt buộc của prompt [8] không có (#3); (d) test khoá phụ thuộc đồng hồ thật biên 300 ms (#5); (e) khoá rào không TTL thiếu ngưỡng + đường nâng cấp và không ai dọn (#7). Thêm #4, #6, #9 cũng chưa có dòng nào |

## Điểm

| Miền | Trọng số | Điểm | Tích | Lý do |
|---|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 | Không finding mức P. Lua dùng `KEYS`/`ARGV` không nối chuỗi; payload `extra="forbid"`; `PermanentError.code` theo mẫu; log độc **không** in thân, có test. Chỉ một Nit (`repr(exc)`) |
| CON – Concurrency & dữ liệu | 15 % | 1 | 0,15 | P1 #2 (vòng gia hạn chết → thân chạy tiếp dưới khoá đã mất, đã tái hiện). Bù lại: token rào, Lua CAS cho `renew`/`release`, `publish_once` nguyên tử đều đúng |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 | Chỉ P3 #6 (`finally` che ngoại lệ của thân). Phân loại lỗi task, case biên (rỗng, 0, âm, trần, sai mẫu, Unicode id) phủ rất dày |
| PERF – Hiệu năng | 10 % | 4 | 0,40 | Chỉ P3 #7; N+1 duy nhất (`INCR`+`EXPIRE`) đã tự nhận ở NO-023 kèm đường nâng cấp |
| RES – Chịu lỗi | 10 % | 1 | 0,10 | P1 #1 (broker chạm `maxmemory` → mọi task hỏng vĩnh viễn + ack, đã chạy thử). Bù lại: trần kết nối/đọc tường minh ở **mọi** client, backoff có trần, 503 chứng minh bằng container thật |
| DB, API – Migration & contract | 10 % | 5 | 0,50 | Không migration, không endpoint, không đổi hợp đồng FE. Bước 6 xanh, bước 7/8 "không áp dụng" đúng luật |
| TEST – Kiểm thử | 7 % | 3 | 0,21 | P2 #3 (hai test bắt buộc của prompt thiếu), P2 #5 (biên thời gian thật 300 ms), P3 #9. Bù lại: dịch vụ thật, worker Celery thật, negative case dày, quét AST tự canh prompt sau |
| OBS, OPS – Vận hành | 5 % | 3 | 0,15 | P2 #4 (không log nào mang `task_id`); NO-021 (P2, chưa nơi khai biến môi trường) đã có dòng nợ đúng chủ B0-08 |
| MNT – Bảo trì | 3 % | 4 | 0,12 | Chỉ P3 #8 và hai Nit. Nhánh một prompt, một commit, trailer đọc được — không lặp lại lỗi gộp nhiều prompt của lần trước |
| **Tổng** | **100 %** | | **3,48** | |

## PHÁN QUYẾT: REQUEST CHANGES

Đây là một nhánh viết tốt: cổng thoát 0 thật, `packages/messaging` phủ **100 % dòng và 100 % nhánh**, và ba chỗ
người gọi yêu cầu soi kỹ nhất thì **hai chỗ tác giả đúng và tôi xác nhận bằng mã** (kiểu trả của `registered_tasks`,
quyền sửa `__init__.py`), còn cơ chế `cancel()`/`uncancel` của `hold` thì tôi đã cố ép vỡ và **không ép vỡ được**.
`publish_once` nguyên tử, bộ đếm `WORKER_LOST` có trừ `retries` với test hai chiều, trần Redis tường minh ở mọi
client, bộ quét AST tự canh cho prompt sau — đều là mã đúng chuẩn production.

Nhưng có **hai finding P1**, cả hai đều được tôi **tái hiện bằng lệnh chạy thật trong container verify**, chứ không
phải suy đoán từ đọc mã:

- **#1** — instance broker theo hiến chương **bắt buộc** `noeviction`, nghĩa là `OutOfMemoryError` là chế độ hỏng
  *được thiết kế sẵn* của nó. `translate_redis_error` không nhận ra lớp lỗi đó, nên khi broker chạm `maxmemory`,
  `_deliveries()` (chạy ở **mọi** lượt task) rơi vào `except Exception` và **mọi** việc đang bay bị đánh hỏng vĩnh
  viễn rồi **ack** — `state = SUCCESS`, `on_failed = INTERNAL`, thân task chưa từng chạy, thông điệp biến mất khỏi
  hàng. Trái thẳng BE-00 §7 ("`DEPENDENCY_UNAVAILABLE` trong task là lỗi tạm"). Đây là mất việc dưới điều kiện biên,
  đúng định nghĩa P1 của `RULE.md` §1.
- **#2** — `_Renewal.run` không bọc try, nên **một** lỗi Redis tạm thời giết vòng gia hạn mà `lost` vẫn `False`:
  đo được keeper gia hạn đúng 1 lần rồi chết, thân chạy hết 1,2 s (3 lần TTL) trong khi `EXISTS lock:… == 0`, và
  `hold()` **không** ném `LockLost`. Hợp đồng của chính `hold` ("mất khoá → `LockLost`") bị phá trong đúng tình
  huống mà khoá phân tán tồn tại để xử lý. BE-00 §7 dùng khoá này cho `training:slot` và `gpu:0`.

Theo ma trận `RULE.md` §5, có P1 chưa waiver → `REQUEST CHANGES`; `RULE-CODE.md` R-38 cũng chặn merge khi có nợ
P0/P1 mở. Điểm 3,48 chỉ là số phụ — kể cả không có P1 thì nó cũng chỉ tới `APPROVE WITH COMMENTS`.

**Điều kiện cụ thể để được duyệt (xin review lại sau khi làm đủ):**

1. **Sửa #1 (P1, bắt buộc, phải có mã).** Thêm `OutOfMemoryError`, `ReadOnlyError`, `ClusterDownError` vào
   `translate_redis_error` (`redis.py:156-164`) **và** vào `BROKER_CONNECTION_ERRORS` (`celery_app.py:37-41`);
   giữ các `ResponseError` còn lại nổi lên nguyên trạng để không nuốt `WRONGTYPE`/lỗi script.
   Kèm **hai** test trên dịch vụ thật (không mock): `ephemeral_redis("noeviction")` + `CONFIG SET maxmemory 1` →
   (a) `EventBus.publish` ném `AppError` mã `DEPENDENCY_UNAVAILABLE` với `retry_after=5`; (b) một task qua
   `define_task` được **thử lại** (không phải `on_failed(..., "INTERNAL")`).
2. **Sửa #2 (P1, bắt buộc, phải có mã).** `_Renewal.run` (`locks.py:136-143`) phải fail-closed: bọc `renew` bằng
   `try/except Exception` → đặt `self.lost = True` và huỷ thân (hoặc thử lại một lần trong phần TTL còn dư rồi mới
   bỏ cuộc); không để ngoại lệ nào thoát khỏi `run()`. Kèm test: `container.stop()` giữa thân `hold` → phải ra
   `LockLost`, không phải lỗi Redis ném từ `finally`.
3. **Bổ sung hai test bắt buộc của prompt [8] (#3, P2).** (a) `countdown` đúng `10, 60, 300` qua đường `task.retry`
   với cấu hình **mặc định**; (b) `registered_tasks()` tìm thấy task của một gói mẫu nối vào
   `apps.worker.__path__`/`apps.ml.__path__`. Nếu quyết không làm (b) trong phiên này thì phải có dòng `DEBT.md`
   nói rõ, gắn vào `NO-019`.
4. **Ghi `DEBT.md` cho mọi finding còn lại trước khi merge (R-38):** #4 (P2, chủ B0-05), #5 (P2, chủ B0-05),
   #6, #7, #8, #9 (P3, chủ B0-05), #10, #12 (Nit, chủ B0-05). Mỗi dòng đủ: nợ là gì, nguyên nhân gốc, chủ, mức,
   trạng thái. Riêng **#7** ghi kèm điều kiện nâng lên P2 thực sự khi B1-01 bắt đầu tạo khoá rào theo email.
   Đồng thời **mở rộng `NO-025`** để nó không còn ngụ ý rằng "mất khoá luôn dẫn tới `LockLost`", và **sửa câu chữ
   của `NO-026`** cho khớp mặt công khai thật của gói (`broker_redis_sync` không nằm trong `packages.messaging`).
5. **Chạy lại `bash tools/verify/run.sh verify` và dán mã thoát thật** sau khi sửa (K25).

**Không** cần đụng tới: kiểu trả của `registered_tasks()` (giữ `list[str]`, hiến chương thắng prompt), việc sửa
`packages/messaging/__init__.py` (hợp lệ), cơ chế `cancel()`/`uncancel()` của `hold` (đã kiểm, không vỡ), hay
`_declared_in_tests` (quyết định đúng: sổ task là đầu vào của cổng thì chỉ được phụ thuộc mã sản phẩm).

---

# Review lại — lượt 2 (sau `1de8525`)

- Ngày: 2026-09-20 · Reviewer: cùng phiên `/merge-review` độc lập · Commit đầu nhánh: `1de8525` (`fix(messaging): treat server-side redis failures as retryable`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** — tôi tự chạy lại, không lấy số của người điều phối. **872** test xanh (lượt 1: 860), bước 5 hết 71,2 s.
- Độ phủ (in từ `tools.coverage_gate`): tổng dòng **99,04 %** · nhánh **95,77 %** · `packages/messaging` **100,00 % / 100,00 %** · `apps/worker` 100 / 100 · `packages/testing` 98,64 / 100 · tập file bị chạm 99,42 / 100.
- Bảng cổng: 1–6 **đạt**, 5b đạt (0 đơn vị perf bị chạm), 7 và 8 **không áp dụng** (vẫn đúng BE-00 §12).
- Cây sạch, hai commit, **cả hai** trailer `Prompt: B0-05` đọc được bằng `%(trailers:key=Prompt,valueonly)` (R-36b giữ). Không đụng file cấm. `1de8525` là `fix(...)` mà không có trailer `Fix: FIX-<nnn>` — **kiểm và chấp nhận**: `FIX-<nnn>` trong repo này dành cho việc người điều phối giao sửa file của prompt **khác** (FIX-001 → `tools/**`, FIX-002 → `packages/db/**`); đây là B0-05 tự sửa mã của chính mình theo finding, `Prompt: B0-05` là đủ.

## Hai P1 — kiểm lại từng cái, không tin lời

**P1 #1 — ĐÃ SỬA, sửa ở gốc (R-19).** `DEPENDENCY_ERRORS` (`packages/messaging/redis.py:52-60`) là **một** danh sách
dùng chung cho `translate_redis_error` (`redis.py:176`) **và** `BROKER_CONNECTION_ERRORS` (`celery_app.py:37`), nên
hai đường không thể lệch nhau nữa — đúng R-07, và rộng hơn thứ tôi đề xuất (tôi chỉ bảo thêm vào hai chỗ).
Tôi dò lại **mọi** lối ra Redis của gói: `EventBus`/`SyncEventBus` (mọi phương thức) và
`SafeLock.acquire`/`renew`/`release` đều đã qua `redis_errors()`; lỗ duy nhất còn lại là `_deliveries` thì commit này
đã bọc (`tasks.py:221`) — và đó là lỗ **tác giả tự tìm ra**, tôi chỉ chỉ gián tiếp. `assert_broker_policy` cố ý
không bọc (hỏng lúc khởi động worker là đúng ý "thà không chạy còn hơn mất việc"). Test chứng minh trên Redis
**thật**: `test_streams.py:301` (broker đầy → 503 `retry_after=5`) và `test_tasks.py:512` (task →
`RETRY_EXHAUSTED`, **không** `INTERNAL`) — đúng hai khẳng định tôi đòi ở điều kiện 1, và cả hai đều đỏ trước bản vá.

**P1 #2 — ĐÃ SỬA, fail-closed đúng hướng.** `_Renewal._renewed` (`locks.py:148-160`) bắt `Exception`, ghi
`lock_renew_failed`, trả `False` → `lost = True` → huỷ thân → `LockLost`. `CancelledError` là `BaseException` nên
không bị nuốt — tôi đã đối chiếu, nhận xét này của tác giả đúng. `finally` khi `lost` thì **không** `release`, tức
không đụng khoá của chủ mới: fail-closed cả hai đầu. Test `test_locks.py:144` là test hồi quy thật: trước bản vá nó
đỏ hai lần (sai loại ngoại lệ **và** `reached != []`).
**Cách dựng lỗi của tác giả tốt hơn đề xuất của tôi** và tôi xác nhận lý do họ đưa: `maxmemory` không chặn `PEXPIRE`
(lệnh không cấp phát, không mang cờ `denyoom`), nên chỉ `SHUTDOWN NOSAVE` / cắt kết nối mới dựng được cảnh "gia hạn
không xong". Lý do đó được ghi ngay trong thân test — đúng R-03.

## Hai chỗ tác giả làm khác ý tôi — phán quyết

**1. `ClusterDownError` test bằng membership thay vì dựng thể hiện — CHẤP NHẬN, lý do đã kiểm chứng.**
Tôi không tin lời mà chạy thử trong container: `redis-py` khai `def __init__(self, resp):` **không kiểu**, và
`mypy --strict` trên một đoạn dựng thể hiện trả đúng
`error: Call to untyped function "ClusterDownError" in typed context [no-untyped-call]`.
Dựng được thì phải thêm `type: ignore[no-untyped-call]` cho một lớp **không thể xảy ra** với client Redis đơn lẻ
(BE-00 §1) — đổi một `type: ignore` lấy một khẳng định không mạnh hơn là lỗ vốn.
`test_cluster_down_stays_in_the_dependency_list` (`test_redis.py:148`) vẫn chặn được đúng thứ cần chặn: ai dọn danh
sách mà bỏ lớp này ra thì test đỏ. Hành vi của nó giống hệt hai lớp kia vì cùng đi qua **một**
`isinstance(exc, DEPENDENCY_ERRORS)`. Không phải né cổng.

**2. `#6` không sửa bằng mã, viện R-14 "nhánh không test được" — LÝ DO KHÔNG ĐỨNG ĐƯỢC, nhưng không chặn merge.**
Tác giả mời phản đối, nên tôi phản đối **bằng bằng chứng chứ không bằng ý kiến**: nhánh đó **dựng được**, bằng đúng
kỹ thuật tác giả vừa tự phát minh cho P1 #2. Công thức: TTL dài và `renew_every_ms` dài hơn cả thân (ví dụ
`SafeLock(client, "gpu:0", 5000).hold(4000)`) → keeper **không bao giờ** kịp chạy → `lost` giữ `False` → `finally`
chắc chắn đi vào `release`; trong thân gọi `admin.shutdown(nosave=True)` rồi `raise ZeroDivisionError`.
Tôi đã chạy đúng kịch bản này trong container verify, kết quả in ra:
`KET QUA: nguoi goi thay AppError DEPENDENCY_UNAVAILABLE - ngoai le that cua than DA BI CHE`.
Tức là nhánh chạy qua được, và finding #6 tái hiện được. R-14 vì vậy **không** miễn cho ca này.
Mức vẫn là **P3** (che ngoại lệ, không mất dữ liệu) nên **không chặn merge** — nhưng dòng `NO-028` đang mang một
nguyên nhân gốc **sai**, mà `DEBT.md` là thứ phiên sau đọc để tin. Phải sửa câu chữ (finding L2-1).

## Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| L2-1 | P3 | R-34 | `NO-028` ghi nguyên nhân "nhánh `except` đó **chưa test được** … (R-14 cấm viết nhánh không chạy qua được)". **Sai, đã tái hiện**: TTL 5 000 ms + `renew_every_ms` 4 000 ms làm keeper không bao giờ chạy → `lost` = `False` → `finally` chắc chắn vào `release`; `admin.shutdown(nosave=True)` trong thân rồi `raise ZeroDivisionError` → người gọi nhận `AppError DEPENDENCY_UNAVAILABLE`, ngoại lệ thật của thân biến mất. Sổ nợ mang lý do sai thì phiên sau không thử lại | `DEBT.md` dòng `NO-028`; mã ở `packages/messaging/locks.py:121-126` | Sửa nguyên nhân gốc của `NO-028` thành "chưa làm, không phải không làm được", kèm công thức trên. Tốt hơn: sửa luôn (≈ 6 dòng: `try/except AppError` quanh `release`, log `lock_release_failed`) cộng một test dùng `ephemeral_broker` theo đúng công thức |
| L2-2 | Nit | R-34 / R-05 | `NO-029` kết luận bộ đếm rào "vài chục tên khoá cố định → vài KB, không phải nguồn tăng trưởng", và xếp khoá theo id vào thì tương lai ("nếu sau này có khoá theo `job_id`"). Nhưng BE-00 §7 **đã** đặt tên `training:claim:{job}` — một tên khoá cho **mỗi** lượt huấn luyện. Nếu B6-03a dựng nó bằng `SafeLock` thì bộ đếm rào tăng theo số job, vô hạn, trên instance `noeviction` | `DEBT.md` dòng `NO-029` | Đổi "nếu sau này" thành trích dẫn `training:claim:{job}` của BE-00 §7, và nêu rõ ràng buộc bàn giao cho B6-03a: hoặc không dùng `SafeLock` cho khoá theo job, hoặc đổi bộ đếm sang `HINCRBY` một hash có TTL trước khi B6-03a hợp nhất |
| L2-3 | Nit | TEST-03 | `test_the_retry_countdown_walks_the_charter_ladder` (`test_tasks.py:497`) chạy trên `run_ladder`, vốn khai `backoff=(10, 60, 300)` **tường minh** (`test_tasks.py:102`), nên nhánh `spec.backoff is None` → đọc `TASK_RETRY_BACKOFF_S` không được đi qua với giá trị thật; prompt [8] nói "khi dùng **cấu hình mặc định**". Trên thực tế **không phải lỗ**: `test_defaults_match_the_charter` chốt mặc định = `(10, 60, 300)`, nhánh `spec.backoff is None` có test khác đi qua, và `backoff_step` không phân biệt nguồn — hai nửa ghép lại là đủ | `packages/messaging/tests/test_tasks.py:97-102`, `:497` | Nếu muốn đúng câu chữ prompt: bỏ tham số `backoff` của `run_ladder` và cho test tự `monkeypatch.setenv("TASK_RETRY_BACKOFF_S", "10,60,300")` thay vì khai cứng |
| L2-4 | Nit | MNT-04 | `test_every_failure_log_carries_the_task_id` (`test_tasks.py:528`) chỉ khẳng định cho `poison_message`; hai điểm log còn lại (`task_failed`, `on_failed_error`) có `task_id` trong mã nhưng không có khẳng định nào. Tên test hứa nhiều hơn nó kiểm | `packages/messaging/tests/test_tasks.py:528-536` | Tham số hoá ba ca (độc / `PermanentError` / `on_failed` ném) và so `task_id` của cả ba, hoặc đổi tên test cho đúng phạm vi |
| L2-5 | Nit | TEST-02 | Test mới `test_hold_treats_a_broken_redis_as_a_lost_lock` dùng lại đúng biên hẹp `TTL_MS = 300` / `RENEW_MS = 80` mà `NO-027` (P2, đang mở) vừa ghi là mỏng — nhánh này vì thế đóng lại với **ba** test khoá phụ thuộc đồng hồ thật thay vì hai | `packages/messaging/tests/test_locks.py:144-168` | Khi làm `NO-027` thì nới cả ba cùng lượt; riêng test này không cần biên hẹp (nó chờ `SHUTDOWN`, không chờ hết hạn) |
| L2-6 | Nit | LOG-02 | `_deliveries` (`tasks.py:210-223`) chạy `INCR` rồi `EXPIRE` trong **hai** lượt. Nay đã bọc `redis_errors()`, nhưng nếu `INCR` thành công mà `EXPIRE` hỏng (kết nối rụng giữa hai lệnh) thì bộ đếm đã tăng trong khi lượt chạy bị thử lại → `count` chạy nhanh hơn `retries` và có thể chạm `WORKER_LOST` sớm. Rất hẹp, và `NO-023` đã đề xuất đúng cách chữa | `packages/messaging/tasks.py:210-223`; `DEBT.md` `NO-023` | Ghi thêm một câu vào `NO-023`: gộp `INCR` + `EXPIRE` thành một script Lua vừa bớt một lượt đi-về vừa bỏ được độ lệch này |

**Lượt 2 — P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 5**

## Trạng thái năm điều kiện của lượt 1

| Điều kiện | Kết quả |
|---|---|
| 1. Sửa #1 bằng mã + hai test trên Redis thật | **đạt**, và sửa rộng hơn yêu cầu (`DEPENDENCY_ERRORS` dùng chung, cộng lỗ `_deliveries` tác giả tự tìm) |
| 2. Sửa #2 bằng mã + test cắt Redis giữa thân | **đạt**; cách dựng lỗi (`SHUTDOWN NOSAVE`) đúng hơn đề xuất của tôi, lý do đã kiểm chứng |
| 3. Hai test bắt buộc của prompt [8] | **đạt** — `test_tasks.py:491` (task dưới `apps.ml`, có khôi phục sổ `_TASKS` khi teardown) và `:497` (bậc lùi qua `self.retry` thật, bắt `Retry.when`, không ngủ). Còn một chỗ lệch câu chữ, xem L2-3 |
| 4. Ghi `DEBT.md` cho #4…#10, #12 | **đạt và vượt**: #4, #8, #9, #12 **sửa luôn bằng mã** thay vì ghi nợ; #5, #6, #7, #10 thành `NO-027`…`NO-030`, đủ nợ/nguyên nhân/chủ/mức. `NO-025` đã mở rộng đúng ý (thêm ca thân đồng bộ dài) và nâng Nit → P3; `NO-026` đã nói rõ là ràng buộc bàn giao và khớp với việc tái xuất `broker_redis_sync`. Trừ điểm duy nhất: nguyên nhân của `NO-028` sai (L2-1) |
| 5. Chạy lại verify, mã thoát thật | **đạt** — tôi tự chạy, exit 0, số liệu ở đầu mục này |

## Điểm (lượt 2)

| Miền | Trọng số | Điểm | Tích | Lý do |
|---|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 | Không finding. `NO-030` (Nit, `repr(exc)`) đã có dòng nợ; log hỏng vẫn không in thân thông điệp |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 | P1 #2 **đã sửa** fail-closed, có test hồi quy trên Redis thật. Còn P3 `NO-025`, `NO-028` (cộng L2-1) |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 | Chỉ P3 `NO-028` (che ngoại lệ trong `finally`) cộng Nit L2-6 |
| PERF – Hiệu năng | 10 % | 4 | 0,40 | Chỉ P3 `NO-023`, `NO-029`, đều có đường nâng cấp cụ thể |
| RES – Chịu lỗi | 10 % | 4 | 0,40 | P1 #1 **đã sửa ở gốc**, một danh sách dùng chung cho cả hai đường, test bằng Redis thật chạm `maxmemory`. Còn Nit L2-6 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 | Không migration, không endpoint, không đổi hợp đồng FE |
| TEST – Kiểm thử | 7 % | 3 | 0,21 | `NO-027` (P2, mở) vẫn là test khoá phụ thuộc đồng hồ thật, nay thành ba test (L2-5); cộng Nit L2-3, L2-4. Bù lại: 12 test mới, dịch vụ thật, hai test hồi quy P1 đều đỏ-trước-xanh-sau |
| OBS, OPS – Vận hành | 5 % | 3 | 0,15 | #4 đã sửa (`task_id` ở cả ba điểm log, qua `task_id_of`). `NO-021` (P2, chủ B0-08, biến môi trường) vẫn mở — đúng chủ, không phải việc của B0-05 |
| MNT – Bảo trì | 3 % | 4 | 0,12 | Chỉ Nit. Một prompt, hai commit, cả hai trailer đọc được; tách `fix` khỏi `feat` là đúng khuôn |
| **Tổng** | **100 %** | | **4,23** | |

## PHÁN QUYẾT LƯỢT 2: APPROVE

Cả hai P1 đều được sửa **ở gốc**, không phải vá triệu chứng (R-19): #1 gom thành **một** `DEPENDENCY_ERRORS` để
đường gửi task và đường đọc/ghi Redis không bao giờ lệch nhau nữa — rộng hơn thứ tôi yêu cầu — và tác giả còn tự
tìm thêm lỗ `_deliveries` cùng hạng; #2 fail-closed đúng hướng, `CancelledError` không bị nuốt, khoá của chủ mới
không bị đụng. Hai test hồi quy dựng lỗi trên **Redis thật** (`maxmemory` và `SHUTDOWN NOSAVE`), đều đỏ trước bản
vá. Hai test bắt buộc của prompt [8] đã có. Bốn finding P2/P3 khác được **sửa luôn bằng mã** thay vì đẩy vào sổ nợ,
và bốn cái còn lại có dòng `NO-027`…`NO-030` đủ nợ, nguyên nhân, chủ, mức. Cổng exit 0 do chính tôi chạy;
`packages/messaging` giữ 100 % dòng và 100 % nhánh sau khi thêm 12 test.

Không còn P0, không còn P1; mọi P2 đang mở (`NO-021`, `NO-027`) đều đã có dòng sổ nợ đúng chủ — R-38 thoả. Điểm
**4,23 ≥ 4,0** → theo ma trận `RULE.md` §5 là **APPROVE**. Nhánh được phép vào `main`.

**Hai việc nên làm cùng lượt gộp — chỉ sửa chữ trong `DEBT.md`, KHÔNG chặn merge:**

1. **`NO-028`** (L2-1): đổi nguyên nhân gốc từ "nhánh `except` chưa test được" thành "chưa làm, không phải không
   làm được", kèm công thức tôi đã chạy qua (`hold(4000)` trên TTL 5 000 ms để keeper không kịp chạy, cộng
   `admin.shutdown(nosave=True)` trong thân). Không để sổ nợ mang một lý do mà phiên sau sẽ tin là bất khả.
2. **`NO-029`** (L2-2): thay "nếu sau này có khoá theo `job_id`" bằng trích dẫn `training:claim:{job}` của BE-00 §7,
   và ghi thành ràng buộc bàn giao cho **B6-03a** (không dùng `SafeLock` cho khoá theo job, hoặc đổi bộ đếm rào
   sang hash có TTL trước khi B6-03a hợp nhất).

Bốn Nit còn lại (L2-3…L2-6) tác giả tự quyết, không cần làm gì trước khi gộp.

**Gộp:** một prompt, hai commit (`feat` cộng `fix`), cả hai mang `Prompt: B0-05` — **squash một lần** là đúng
(`CLAUDE.md`, BE-00 §13.2), không lặp lại vấn đề gộp nhiều prompt của nhánh B0-04.
