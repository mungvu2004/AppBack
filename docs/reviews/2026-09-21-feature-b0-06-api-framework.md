# Review merge feature/b0-06-api-framework → main

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` · Commit đầu nhánh: `0fc49ee5a085` (gốc `3b7ebf4`)
- **Không độc lập theo R-37.** Lệnh được gọi trong chính phiên đã viết B0-06 (chưa `/clear`). Người điều phối gọi lệnh sau khi đã được báo điều này. Để bù, mọi khẳng định dưới đây đều tự kiểm lại bằng lệnh chạy trong phiên này; không khẳng định nào lấy từ báo cáo của tác giả. Người điều phối nên chạy lại `/merge-review` ở phiên mới trước khi merge.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 1** (chạy tại chỗ, log `scratchpad/review-verify.log`): `1119 passed, 10 skipped, 1 error`. Lượt đầu tiên của phiên còn không chạy được vì Docker Desktop tắt (máy khởi động lại) — tính là "chưa chạy", không tính là đạt.
- Đối chiếu: lượt verify trước trên **cùng** commit `0fc49ee` thoát 0 (`1120 passed`, log `…/tasks/bi9deifhi.output`, 2026-09-20 22:01). Lỗi của lượt này là hạ tầng (xem finding #2), nhưng luật của skill là chấm theo mã thoát thật.
- Độ phủ: **không có số của lượt này** (bước 5 hỏng trước `coverage_gate`). Số của lượt xanh trên cùng commit: tổng dòng 99,18 % · nhánh 96,53 % · `apps/api/core` 99,54 % / 97,97 % · `apps/api/files`, `apps/api/health` 100 % / 100 %.

Bảng cổng thật của lượt này:

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | **hỏng** — `ERROR at setup of test_request_id_is_echoed`: `asyncpg.connect(host='host.docker.internal', timeout=10)` → `TimeoutError` |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy |
| 7 | H1 H3 H4 H5 | chưa chạy |
| 8 | openapi | chưa chạy |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B0-06.md` tồn tại | đạt |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 5 commit, dài nhất 70 ký tự |
| Trailer `Prompt:` đọc được | đạt — `B0-06`, `B0-01`+`FIX-003`, `B0-03`+`FIX-004`, `B0-05`+`FIX-005`, `B0-06` |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py`, `tools/verify/*` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới | không — mọi `type: ignore` có mã và lý do; mọi `noqa` có mã |

Không có điều kiện dừng sớm nào kích hoạt. Ba commit FIX đụng file ngoài cột "Sở hữu" của B0-06 (`tools/tests/`, `packages/db/tests/`, `packages/messaging/tests/`) **có** cấp phép của người điều phối trong phiên, spec đủ khuôn ở `docs/fixes.md`, trailer đúng chủ — không phải vi phạm K27.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | SEC-03 · OPS-02 · R-17 | `create_app(settings=None)` dùng `schema_settings()`, mà hàm này **nuốt** `ValidationError` và trả `SCHEMA_SETTINGS` (`app_env="ci"`, `public_base_url="http://localhost:8000"`). Cấu hình dự phòng chỉ dành cho việc đọc schema nay nằm trên đường khởi động thật. **Tái hiện trong phiên:** `APP_ENV=production`, thiếu `SECRET_KEY` → `create_app()` **không ném**; app chạy với `app_env=ci`, `openapi_url=/api/openapi.json`, `DenyAllTokenVerifier`, `public_base_url=http://localhost:8000`. Gõ nhầm `APPENVIRONMENT=production` → cũng lên ở `ci`. Trong khi đó, đủ biến mà `APP_ENV=production` thì `create_app()` ném đúng như hợp đồng [2]. Nghĩa là chốt "staging/production chưa có verifier thì không khởi động" bị **lách** đúng lúc cấu hình sai. Nâng P2→P1 vì nằm trên đường xác thực (RULE.md §1) | `apps/api/core/app.py:160` (`resolved = settings if settings is not None else schema_settings()`), `:59` | `create_app(settings=None)` gọi thẳng `get_core_settings()` (fail-fast). Chỉ `openapi.real_app()` (`apps/api/core/openapi.py:149`) truyền `schema_settings()` tường minh. Thêm test: env sai → `create_app()` ném `ValidationError`; `APP_ENV=production` không có module auth → vẫn `RuntimeError` |
| 2 | P2 | TEST-02 · RES-01 | `api_env` không đặt trần bắt tay cho engine của app thử, nên mọi app test dùng trần 10 s của đường **phục vụ request**. FIX-002 (NO-002) đã lập trần 180 s cho đường cổng/test chính vì chặng `host.docker.internal` hay kẹt (NO-007). B0-06 thêm khoảng 250 test, mỗi test mở một engine mới qua chặng đó, nên cổng đỏ giả nhiều hơn. **Đã xảy ra trong review này:** bước 5 hỏng ở setup, `timeout = 10` | `packages/testing/fixtures/api.py:141` (`api_env`, cạnh `:153`) | `monkeypatch.setenv("DB_CONNECT_TIMEOUT_S", str(int(GATE_CONNECT_TIMEOUT_S)))` trong `api_env`. `db_sessionmaker` của B0-03 (`packages/testing/fixtures/db.py:109`) cũng dùng 10 s — ghi `DEBT.md` cho B0-03, không sửa ở nhánh này |
| 3 | P2 | TEST-02 | Test của FIX-005 là **mệnh đề hằng đúng** với đúng lỗi mà nó tuyên bố bắt. `beat_ledger = list(beat_schedule())` được đọc **sau** khi nhập `celery_main`, mà `beat_schedule()` chỉ đọc `_SCHEDULES` chứ không dò module. **Tái hiện trong phiên:** giả lập `celery_main` quên `discover_jobs()` → `beat = [] \| beat_ledger = []` → assert qua. `docs/fixes.md:103` lại khẳng định trường hợp này "→ đỏ", tức sổ FIX ghi sai | `packages/messaging/tests/test_worker_main.py:28,62`; `docs/fixes.md:103` | Trong PROBE, gọi `discover_jobs()` (idempotent) **trước** khi tính `beat_ledger`, để vế phải là sổ đầy đủ độc lập với việc `celery_main` có dò hay không. Sửa lại câu [6] của FIX-005 cho đúng |
| 4 | P2 | TEST-02 | Ba test đồng thời xếp thứ tự hai request bằng `asyncio.sleep(SETTLE_S)` với `SETTLE_S = 0.05`, tức dựa vào **thời gian thật**. Nếu lượt đầu chưa kịp `INSERT` nhận việc trong 50 ms (chặng DB kẹt, NO-007), thứ tự đảo: lượt thứ hai nhận việc rồi chờ cổng chỉ được mở **sau** khi chính nó trả về → hết `GATE_TIMEOUT_S = 5` → 500 → test đỏ giả | `apps/api/core/tests/test_idempotency.py:38,163,185,188` | Chờ **trạng thái** thay vì chờ thời gian: poll tới khi có dòng `in_progress` trong `idempotency_records`. Helper `wait_until` đã có sẵn trong `sample.py` nhưng chưa ai dùng (xem #8) |
| 5 | P2 | MNT-01 · R-08 | `idempotency.begin` dài 64 dòng, vượt trần 50 (độ phức tạp chỉ 2, phần lớn là dict và danh sách cột) | `apps/api/core/idempotency.py:123` | Tách `_claim_statement(...)` và `_read_blocker(session, ...)` |
| 6 | P2 | MNT-05 | Nhánh có 1 590 dòng logic sản phẩm và 2 110 dòng logic test, vượt 400. **Không đáng tách:** đây là một prompt, và các phần móc vào nhau (`AppRoute` ↔ idempotency ↔ middleware ↔ thân lỗi) | toàn nhánh | Chỉ ghi nhận, không cần làm gì |
| 7 | P3 | R-01 · MNT-04 | 44 hàm/lớp sản phẩm thiếu docstring. Đáng kể nhất là `AppRoute.get_route_handler` — chính đường đi của mọi request — cùng `deps.event_bus/storage/clock/core_settings`, `origin._settings/_matches`, `ratelimit._script`, `openapi.build_parser`, ba handler lỗi | `apps/api/core/routing.py:197`, `deps.py:31-45`, `origin.py:30,36`, `ratelimit.py:57`, `openapi.py:164`, `errors.py:159-169` | Thêm docstring một câu. Các `__init__`/`__call__` của middleware có docstring lớp rồi, bỏ qua được |
| 8 | P3 | MNT-03 · R-11 | Code chết trong app thử: `wait_until`, `sample_principal` — 0 chỗ gọi | `apps/api/core/tests/sample.py:391,396` | Dùng `wait_until` cho #4, xoá `sample_principal` |
| 9 | P3 | MNT-03 · R-07 | `_b64`/`_unb64` chép lại y nguyên từ `packages/storage/local.py:275,280` | `apps/api/core/pagination.py:65,70` | Chấp nhận được (hàm riêng của gói khác), nhưng phải có một dòng comment nêu lý do không dùng chung |
| 10 | P3 | PERF-05 | `route_of(scope)` quét tuyến tính mọi route **hai lần** mỗi request (`BodyLimit` trước routing, `AccessLog` sau), trong khi sau routing FastAPI đã đặt `scope["route"]` | `apps/api/core/middleware.py:114,171` | `AccessLogMiddleware` đọc `scope.get("route")`; chỉ `BodyLimit` cần tự khớp |
| 11 | Nit | LOG-02 | `_KEY_RE = re.compile(KEY_PATTERN.strip("^$"))`: `strip` theo tập ký tự, dễ vỡ nếu mẫu đổi | `apps/api/core/idempotency.py:57` | `re.compile(KEY_PATTERN)` + `fullmatch` là đủ |
| 12 | Nit | TEST-02 | `test_real_operations_đọc_được_sổ_thật` dùng `all(...)` nên qua cả khi sổ **rỗng** | `tools/tests/test_case_gate.py:481` | Chấp nhận — docstring đã nói test cố ý không khẳng định số lượng |

Đã kiểm và **không** thấy finding: SEC-01 (mọi SQL qua SQLAlchemy/bind param), SEC-02 (khoá idempotency có `user_id`), SEC-07/K15 (`/api/files`: một 404 duy nhất, `inline` chỉ khi magic bytes là PNG/JPEG), SEC-12 (500 không lộ stack, `test_unknown_exception_is_500_without_stack`), SEC-13/K11 (log truy cập không có đường thật, có test), SEC-14 (rate limit Lua nguyên tử, `Retry-After` kẹp 10 s). CON-01/CON-02: nhận việc bằng **một** `INSERT … ON CONFLICT DO UPDATE … WHERE`, hoàn tất trong cùng giao dịch nghiệp vụ, chiếm lại khi hết hạn thuê — có test Postgres thật cho song song và chiếm lại. DB-01/DB-04: migration chỉ expand, có `downgrade()`, `migrate_check` 9/9 ở lượt xanh. API-02: thân W7 thống nhất, 405 → 404.

## Kiểm sổ nợ

- NO-031, NO-032, NO-033 (P1): ✅, có mã FIX và spec — không còn P0/P1 mở (`DEBT.md`, 35 dòng).
- NO-034, NO-035 (➖): lý do đứng được, có ngưỡng và đường nâng cấp.
- Finding #1–#5 của review này **chưa** có dòng `DEBT.md`.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #1) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (chỉ Nit) | 0,75 |
| PERF – Hiệu năng | 10 % | 4 (P3 #10) | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 (P2 #2, #3, #4) | 0,21 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #5, #6) | 0,09 |

Tổng: **3,70 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Có một P1 chưa waiver (#1), và cổng thoát 1 ở lượt review. Mỗi lý do một mình đã đủ để không duyệt. Phần lõi — thứ tự của `AppRoute`, idempotency, thân lỗi, middleware — đúng hiến chương và có test dịch vụ thật tốt, nên sau khi sửa dưới đây, nhánh nhiều khả năng đạt `APPROVE`.

Phải làm để được duyệt:

1. **#1 (P1):** `create_app(settings=None)` fail-fast qua `get_core_settings()`; chỉ `openapi.real_app()` dùng `schema_settings()`; kèm test env sai → `create_app()` ném.
2. **Cổng xanh trên một lượt mới:** sửa #2 (`api_env` đặt `DB_CONNECT_TIMEOUT_S` = `GATE_CONNECT_TIMEOUT_S`) để lỗi hạ tầng NO-007 không làm đỏ cổng; ghi `DEBT.md` cho `db_sessionmaker` của B0-03.
3. **P2 #3, #4, #5:** sửa (khuyến nghị — cả ba đều nhỏ), hoặc ghi mỗi cái một dòng `DEBT.md` kèm chủ và mức. #3 đụng test của B0-05, nên đi dưới FIX-005 (sửa cả `docs/fixes.md:103`). #6 chỉ ghi nhận.
4. **Chạy lại `/merge-review` ở một phiên mới** (sau `/clear` hoặc từ terminal khác) — lần này là phiên độc lập theo đúng R-37.

P3 và Nit (#7–#12) do tác giả tự quyết, không chặn merge.

---

## Lượt review lại (độc lập)

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, chưa từng thấy mã trước lượt này) · Commit đầu nhánh: `6d42121fa2aa` (gốc `3b7ebf4`, 8 commit)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ, log ở scratchpad của phiên): `1134 passed, 10 skipped`. 10 skip đều là `test_common.py` với tập tham số rỗng (chưa có route được bảo vệ), đúng ngoại lệ duy nhất BE-00 §12 cho phép; `case_gate` đạt.
- Độ phủ: tổng dòng 99,23 % · nhánh 96,71 % · `apps/api/core` 99,45 % / 97,97 % · `apps/api/files`, `apps/api/health`, `packages/messaging` 100 % / 100 % · `packages/db` 98,65 % / 97,32 % · `packages/testing` 99,51 % / 100 % · `tools` 98,24 % / 94,05 % · tập file bị chạm 99,55 % / 98,16 %.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (9/9) |
| 7 | H1 H3 H4 H5 | không áp dụng — hợp lệ: chưa có `changes/B0-07.md` |
| 8 | openapi | đạt |

**Điều kiện dừng sớm** (tự kiểm lại, không dùng bảng của lượt trước): cây sạch; có `changes/B0-06.md`; 8 commit đúng mẫu, dòng đầu dài nhất 71 ký tự, trailer đọc được bằng `%(trailers:key=Prompt)` (`B0-06`×5, `B0-01`+`FIX-003`, `B0-03`+`FIX-004`, `B0-05`+`FIX-005`×2); không đụng file cấm; mọi `noqa`/`type: ignore` mới đều có mã và lý do; không `pragma`, `skip`, `xfail` mới. Không điều kiện nào kích hoạt.

**Công cụ kiểm tại chỗ** (trong container verify, Python 3.12): AST đếm docstring và độ dài hàm trên mọi file `.py` của diff; bốn probe chạy thật (B: `create_app` với env sai; C: route nhiều method; D: `Origin` sai dạng; E: giả lập `celery_main` quên `discover_jobs()`; F: va chạm `request_digest`).

### Trạng thái finding của lượt trước

| # cũ | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | P1 | **đã sửa** | `app.py:172` đọc thẳng `get_core_settings()`; `schema_settings()` chỉ còn ở `openapi.py:297`. Probe B: `APP_ENV=production` thiếu `SECRET_KEY` → `ValidationError`; gõ nhầm `APPENVIRONMENT` → `ValidationError` (`app_env` bắt buộc, không mặc định); đủ biến mà chưa có auth → `RuntimeError`. Test `test_app.py:209-231` |
| 2 | P2 | **đã sửa phía B0-06** | `fixtures/api.py:159` đặt `DB_CONNECT_TIMEOUT_S` = `GATE_CONNECT_TIMEOUT_S`, test `test_app.py:247`. Phía B0-03 là NO-036 (P2, mở, đủ cột) |
| 3 | P2 | **đã sửa** | `test_worker_main.py:31-34` gọi `discover_jobs()` trước khi tính vế phải. Probe E: `beat = []` · `beat_ledger = ['default.idempotency.purge_expired']` → assert đỏ như `docs/fixes.md` nay ghi |
| 4 | P2 | **đã sửa** | `test_idempotency.py:184,205,210` chờ trạng thái DB bằng `wait_until` (`sample.py:393`), không còn `sleep` xếp thứ tự |
| 5 | P2 | **đã sửa** | `begin` còn 20 dòng (`idempotency.py:193-212`); AST: không hàm nào của diff > 50 dòng |
| 6 | P2 | còn (bản chất) | xem #3 dưới |
| 7 | P3 | **đã sửa cho mã sản phẩm** | AST: 0 hàm/lớp sản phẩm thiếu docstring (trừ `upgrade`/`downgrade` của revision, theo khuôn `script.py.mako` của B0-03). Phần test: xem #6 dưới |
| 8 | P3 | **đã sửa** | `sample_principal` đã xoá; `wait_until` có 11 chỗ dùng |
| 9 | P3 | **đã sửa** | comment lý do ở `pagination.py:66-68` |
| 10 | P3 | **đã sửa** | `BodyLimit` khớp một lần, để ở `scope["appback.route"]` (`middleware.py:185-188`), `AccessLog` đọc lại (`:122`) |
| 11 | Nit | **đã sửa** | `idempotency.py:58` `re.compile(KEY_PATTERN)` + `fullmatch` |
| 12 | Nit | chấp nhận | không đổi, lý do đứng được |

### Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | SEC-05 · LOG-04 · R-17 | `Origin` sai dạng làm nổ `ValueError` thay vì 403. `_origin_of` đưa header thô vào `urlsplit`, mà `urlsplit` ném `ValueError: Invalid IPv6 URL` với `http://[` hay `http://[::1`. **Probe D:** cả `require_origin` lẫn `reject_foreign_origin` ném đúng lỗi đó (không phải `AppError`) → `FinalErrorMiddleware` → `translate_unknown` ghi `unhandled_exception` **kèm stack** → 500 `INTERNAL`. Tác động: hợp đồng là 403 `ORIGIN_MISMATCH` (BE-00 §5, C24); bất kỳ ai chưa đăng nhập cũng tạo được một 500 cộng một stack trace mỗi request trên mọi route dùng hai hàm này (login/refresh/logout của B1-01, luồng của B4-01), làm bẩn cảnh báo 5xx. **Không nâng P1** vì chưa route nào trong nhánh dùng hai hàm này và kết cục vẫn là từ chối (fail-closed). Nếu còn nguyên khi B1-01 mount login thì luật nâng mức "luồng auth" biến nó thành P1 | `apps/api/core/origin.py:24-27`, đi qua `:40`, `:51` | Trong `_matches` bắt `ValueError` của `_origin_of(origin)` và coi là lệch (403). Thêm test `Origin: http://[` cho cả hai hàm |
| 2 | **P2** | CON-02 | Dòng idempotency `completed` của một lượt **đã commit** có thể bị xoá. `_finish` đặt `after_commit_idle` trong cùng `try` mà `except BaseException` gọi `_abort` → `discard`. `complete` không đổi `claim_token`, còn `discard` xoá theo `id` + `claim_token`, nên `WHERE` vẫn khớp dòng vừa chuyển `completed`. Sau commit, `after_commit_idle` chỉ còn lọt ra `BaseException`: lỗi callback bị nuốt ở `packages/db/hooks.py:147-150`, nên thực tế là `CancelledError`. Kịch bản: rolling deploy, uvicorn `--timeout-graceful-shutdown` huỷ task request → FE thấy lỗi mạng → thử lại cùng `Idempotency-Key` (W9) → handler chạy **lần hai**, ghi trùng. Xác suất thấp vì cửa sổ chỉ bằng thời gian callback, nhưng nó phá đúng bất biến mà idempotency tồn tại để giữ. Phân tích mã, chưa dựng test | `apps/api/core/routing.py:296-304`; `apps/api/core/idempotency.py:240-248`, `:255-264` | Sửa gốc ở một chỗ mọi đường đi qua: `discard` thêm `IdempotencyRecord.state == STATE_IN_PROGRESS` vào `WHERE`. Nên thêm: đưa `after_commit_idle` ra khỏi `try` rollback. Test: huỷ task sau commit → dòng vẫn `completed` |
| 3 | P2 | MNT-05 | Nhánh thêm ≈ 2 730 dòng mã sản phẩm (kể cả docstring) và ≈ 3 300 dòng test trong 52 file, vượt xa 400. **Không đáng tách:** một prompt, các phần móc vào nhau (`AppRoute` ↔ idempotency ↔ middleware ↔ thân lỗi) | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` chấp nhận |
| 4 | P3 | LOG-02 · API-02 | Route khai nhiều method mất idempotency mà không ai biết. `wire_method` lấy method đầu tiên theo thứ tự chữ. **Probe C:** `api_route("/multi", methods=["GET","POST"])` → `wire_method GET`, `uses_idempotency False`, `Operation(method="GET", idempotency="off")`. Hệ quả: POST không nhận việc idempotency; `case_gate` không đòi C10/C22; `test_method_and_path_are_unique` chỉ thấy GET. Hôm nay chưa route nào như vậy | `apps/api/core/routing.py:179-185`, `:326-333` | `check_routers` từ chối route có hơn một method (trừ `HEAD`), kèm test |
| 5 | P3 | PERF-04 · R-23 | Mỗi guard giải JSON lại từ đầu: `_json_body` gọi `json.loads(await request.body())`, trong khi FastAPI đã gọi `request.json()` và Starlette đã cache kết quả. Route `versioned` có tham số đường (vd #35, trần 8 MiB) vì thế giải thân ba lần trên vòng sự kiện | `apps/api/core/routing.py:98-106` (gọi ở `:123`, `:139`) | Dùng `await request.json()`, bọc `try/except ValueError` như hiện tại |
| 6 | P3 | R-01 · MNT-04 | 98 hàm/lớp trong các file test mới của B0-06 thiếu docstring (AST), vd `test_common.py:63,67,83,108`, `test_errors.py:55,60`, `test_wire.py:41-67`, `test_internals.py:80-117`. Mã sản phẩm đã đủ | `apps/api/core/tests/*`, `apps/api/*/tests/*` | Thêm một câu cho helper và lớp giả; test có tên tự nói thì một dòng là đủ |
| 7 | P3 | MNT-04 | `changes/B0-06.md` dài 13 dòng; BE-00 §13.2 quy định 3–10 dòng | `changes/B0-06.md` | Rút gọn còn ≤ 10 dòng |
| 8 | P3 | R-27 · FIX.md luật 5 | FIX tự cấp cho file của prompt khác. `docs/fixes.md` **không có trên `main`**: nhánh tự tạo nó (`0fc49ee`, trailer `Prompt: B0-06`) và tự viết spec FIX-003..005, trong khi FIX.md luật 5 nói người điều phối giữ sổ này. Các commit FIX sửa `tools/tests/test_case_gate.py`, `packages/db/tests/test_new_revision.py`, `packages/messaging/tests/*`: ngoài `so_huu` của B0-06 và nằm trong danh sách "không được sửa" ở khối [12] của prompt. Cấp phép của người điều phối **chỉ có trong lời tác giả** (mục review trên), repo không có bằng chứng. Nội dung sửa thì đúng: trailer đúng chủ, probe E xác nhận FIX-005, cổng xanh | `docs/fixes.md`; commit `cdee48c`, `960dced`, `c952c40`, `d032787` | Phiên merge xác nhận cấp phép. Gộp bằng `--no-ff` (R-36) để giữ trailer của cả B0-01, B0-03, B0-05, B0-06 |
| 9 | Nit | LOG-02 | `request_digest` nối các phần bằng `\|` mà không thoát ký tự. **Probe F:** đường `/api/items/a\|b` không query và đường `/api/items/a` với query `b\|` cho **cùng** hash. Chỉ tác động khi cùng người dùng, cùng khoá, cùng khuôn route, nên không ảnh hưởng người khác | `apps/api/core/idempotency.py:85-96` | Băm từng phần kèm tiền tố độ dài |
| 10 | Nit | CON-01 | `DELETE … WHERE id IN (SELECT … WHERE expires_at <= now LIMIT n)`: vế ngoài không kiểm lại `expires_at`. Dòng vừa bị `begin` chiếm lại đúng lúc dọn có thể bị xoá, làm `complete` của lượt đó 0 dòng → 503 giả. Lượt đó thử lại được, không ghi trùng. Phân tích, chưa tái hiện | `apps/api/core/jobs.py:43-47` | Thêm `IdempotencyRecord.expires_at <= now` vào `DELETE` |
| 11 | Nit | R-34 | NO-035 còn trỏ dòng 165–169 và số 97,56 % của `begin` **trước** khi tách; nay `begin` ở `idempotency.py:193-212`, cổng báo 97,97 % | `DEBT.md` (NO-035) | Cập nhật dòng và số |

Đã kiểm và **không** thấy finding thêm: SEC-01 (mọi SQL qua SQLAlchemy/bind param, `jobs.py` và `idempotency.py`); SEC-02 (khoá idempotency có `user_id` từ `Principal`, không từ thân); SEC-03/W10 (401 trước khi đọc thân, test 64 MiB); SEC-07/K15 (`/api/files`: một 404, `inline` chỉ khi token ghi `inline` **và** magic bytes PNG/JPEG); SEC-12 (500 không lộ stack); SEC-13/K11 (log truy cập chỉ `routeTemplate`); SEC-14/W9 (Lua nguyên tử, `Retry-After` kẹp 10 s); SEC-15 (cursor so bằng `hmac.compare_digest` với mọi khoá kiểm). CON-01 của `begin`: một `INSERT … ON CONFLICT DO UPDATE … WHERE` nhận việc hoặc chiếm lại, có test Postgres thật cho song song và hết hạn thuê. RES-01 (`/api/ready` trần tổng 2 s, lệnh chặn qua `to_thread`). DB-01/DB-04 (chỉ expand, `downgrade()` thật, `migrate_check` 9/9). API-02 (405 → 404, thân W7 thống nhất). Ba route công khai nằm trong tập [7]; route-scan và mã lỗi duy nhất có test. `{link_id}` có trong BE-BIND nhưng thiếu trong `PATH_VALUES` là **đúng**, vì #49 thuộc v2.

### Kiểm sổ nợ

- Không có nợ P0/P1 nào còn `mở`. NO-031..NO-033 ✅, NO-034/NO-035 ➖ có lý do, NO-036 (P2, B0-03) ⬜ đủ cột.
- Finding #1, #2, #3 (P2) của lượt này **chưa** có dòng `DEBT.md` → phải ghi trước khi merge (R-38, ma trận §5).

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 3 (P2 #1) | 0,75 |
| CON – Concurrency & dữ liệu | 15 % | 3 (P2 #2) | 0,45 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #4) | 0,60 |
| PERF – Hiệu năng | 10 % | 4 (P3 #5) | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #3) | 0,09 |

Tổng: **3,89 / 5**

## PHÁN QUYẾT: APPROVE WITH COMMENTS

Cổng thoát 0 trên lượt chạy độc lập, không có P0/P1, điểm 3,89. Mọi P1 và P2 của lượt trước đều đã sửa, và mỗi cái đã được kiểm lại bằng mã, test hoặc probe chạy thật. Lõi của khung (thứ tự `AppRoute`, nhận việc idempotency bằng một lệnh, thân W7, bốn lớp middleware) đúng hiến chương và có test trên dịch vụ thật.

Điều kiện để merge:

1. Ghi `DEBT.md` **trước khi merge** (R-38) cho ba P2: #1 (`origin.py`, B0-06, P2 — nêu rõ thành P1 nếu còn khi B1-01 mount login), #2 (`routing.py`/`idempotency.py`, B0-06, P2), #3 (`➖` chấp nhận). Khuyến nghị sửa luôn #1 và #2 trong một FIX: mỗi cái vài dòng, kèm test.
2. Người điều phối xác nhận đã cấp phép FIX-003..005 và sổ `docs/fixes.md` (#8).
3. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của bốn prompt), **không** squash.

P3 và Nit (#4–#11) do tác giả tự quyết, không chặn merge.

---

## Lượt review lại (độc lập) — lần 3

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, không phải hai phiên review trước; mọi khẳng định trong commit, `DEBT.md`, `docs/fixes.md` và hai lượt trên đều tự kiểm lại) · Commit đầu nhánh: `01a5ff16328f` (gốc `3b7ebf4`, 12 commit; mới so với lượt 2: `014ca6d`, `ced9995`, `839cab9`, `01a5ff1`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ, log `verify3.log` trong scratchpad của phiên): `1141 passed, 10 skipped`. Cả 10 skip đều là `got empty parameter set for (operation)` ở `apps/api/core/tests/test_common.py:119, 128 (×4), 137, 151, 165, 177, 192` (tự kiểm bằng `pytest -rs`), đúng ngoại lệ duy nhất BE-00 §12 cho phép. `case_gate` đạt: 0 thao tác có dòng BE-BIND, 3 cảnh báo cho ba route công khai của [7].
- Độ phủ: tổng dòng **99,23 %** · nhánh **96,73 %** · `apps/api/core` 99,46 % / 98,03 % · `apps/api/files`, `apps/api/health`, `packages/messaging` 100 % / 100 % · `packages/db` 98,65 % / 97,32 % · `packages/testing` 99,51 % / 100 % · `tools` 98,24 % / 94,05 % · tập file bị chạm 99,55 % / 98,21 %. Mọi gói và tổng đều ≥ 90 % ở cả hai số.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (184 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (160 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 | không áp dụng — hợp lệ: `changes/` chưa có `B0-07.md` |
| 8 | openapi | đạt |

**Điều kiện dừng sớm** (tự kiểm lại): cây sạch; `changes/B0-06.md` có, 9 dòng; 12 commit đúng mẫu Conventional Commits, dòng đầu dài nhất 70 ký tự (`960dced`); trailer đọc được bằng `%(trailers:key=Prompt)` cho cả 12 (`B0-06`×6, `B0-01`+`FIX-003`×2, `B0-03`+`FIX-004`×2, `B0-05`+`FIX-005`×2); không đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py`, `tools/verify/*`, `tools/charter.py`; không `conftest.py` lồng hay file cấu hình công cụ; mọi `noqa`/`type: ignore` mới đều có mã; không `pragma`, `skip`, `xfail` mới. Không điều kiện nào kích hoạt.

**Công cụ kiểm tại chỗ** (container verify, Python 3.12; file probe chỉ nằm trong bản sao `/tmp/w`, không vào repo):

- **G1** đếm `json.loads` trên đúng thân của `PUT /api/sample/versions/{project_id}` (route `versioned` có tham số đường, tức hai guard): FastAPI 0.141.1 giải thân bằng `request.json()`, và cả request chỉ **1** lần giải (của FastAPI).
- **G2** thay `after_commit_idle` bằng hàm ném `BaseException` **sau** commit (giả lập huỷ task lúc deploy): dòng idempotency vẫn `completed`; lượt lặp cùng khoá trả `200` đúng thân cũ, không chạy lại handler.
- **G3** pool `DB_POOL_SIZE=2`, `DB_MAX_OVERFLOW=0`, `DB_POOL_TIMEOUT_S=2`; route bảo vệ có dependency đọc DB qua session của request; bắn 2 POST song song: **không** `Idempotency-Key` → `[200, 200]` trong 0,08 s; **có** `Idempotency-Key` → `[503, 503]` `DEPENDENCY_UNAVAILABLE` sau 2,09 s (xem finding #1).
- **AST** trên 49 file `.py` của diff: file của B0-06 thiếu docstring **0**; 82 hàm thiếu docstring đều là hàm **không bị nhánh chạm** trong ba file test của B0-01/B0-03/B0-05 (có từ `main`); không hàm nào > 50 dòng, không lồng > 3 cấp. Dòng logic (bỏ trống, comment, docstring): 1 554 mã sản phẩm, 3 268 test và fixture.

### Trạng thái finding của lượt 2

| # lượt 2 | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | P2 | **đã sửa** | `origin.py:24-34` bắt `ValueError` của `urlsplit` → `None`; `:44-50` coi `None` là lệch. Test `test_permissions.py::test_malformed_origin_is_403_not_500` (3 mẫu `http://[`, `http://[::1`, `://`; cả `require_origin` lẫn `reject_foreign_origin` → 403 `ORIGIN_MISMATCH`), đạt trong cổng. `NO-037` ✅ |
| 2 | P2 | **đã sửa** | `idempotency.py:259-274`: `discard` thêm `state == 'in_progress'` vào `WHERE`, sửa ở chỗ mọi đường đi qua. Test đơn vị `test_discard_never_deletes_a_completed_record`; **probe G2** xác nhận cả đường thật (huỷ sau commit → dòng còn `completed`, lượt lặp replay). Gợi ý phụ (đưa `after_commit_idle` ra khỏi `try`) không làm — chấp nhận, gốc đã sửa. `NO-038` ✅ |
| 3 | P2 | chấp nhận | `NO-039` ➖: lý do đứng được (tách ra là đưa nửa khung vào `main`). Vẫn tính điểm MNT |
| 4 | P3 | **đã sửa** | `routing.py:114-124` `_single_method` từ chối route nhiều method lúc khai; `:198-200` từ chối `versioned=True` trên method đọc. Test `test_routing.py::test_multi_method_route_is_rejected_at_declaration`, `::test_versioned_read_route_is_rejected_at_declaration` |
| 5 | P3 | **đã sửa** | `routing.py:99-111` dùng `request.json()` (Starlette nhớ kết quả). **Probe G1**: 1 lần giải cho cả request |
| 6 | P3 | **đã sửa** | AST: 0 hàm/lớp thiếu docstring trong file của B0-06; các hàm test mà FIX-003/004 chạm cũng đã có (`ced9995`, `839cab9`) |
| 7 | P3 | **đã sửa** | `changes/B0-06.md` còn 9 dòng |
| 8 | P3 | **đã ghi sổ, chờ xác nhận** | `docs/fixes.md` nay ghi lời giao việc FIX-003..005 (2026-09-20, xác nhận lại 2026-09-21) và commit của từng FIX. Dòng đó vẫn do tác giả viết; repo không có bằng chứng độc lập → phiên merge xác nhận |
| 9 | Nit | **đã sửa** | `request_digest` dùng tiền tố độ dài 8 byte (`idempotency.py:95-100`), test `test_request_digest_fields_cannot_bleed_into_each_other` (xem Nit #3 dưới) |
| 10 | Nit | **đã sửa** | `jobs.py:49-53` kiểm lại `expires_at <= now` trong chính `DELETE`. Không có test chặn tái phát (race khó dựng) — chấp nhận |
| 11 | Nit | **đã sửa** | `NO-035` nay trỏ `194`, `211`/`213`, `255–256` — khớp `idempotency.py` hiện tại; số 99,46 % / 98,03 % khớp cổng lượt này |

### Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | PERF-08 · CON-07 · RES-03 | **Một lượt ghi có `Idempotency-Key` giữ hai kết nối của cùng một pool (hold-and-wait).** `AppRoute` mở session của request (`routing.py:232-234`); dependency của router/route (quyền, nạp tài nguyên) chạy **trước** guard (`:207-210`, đúng BE-00 §7) và nếu đọc DB qua `DbSession` thì session đó giữ một kết nối tới lúc commit. Guard gọi `idempotency.begin(request.app.state.sessionmaker, …)` (`:175-183`), mà `begin` mở session **thứ hai trên cùng engine** (`idempotency.py:209`). Pool thật là 10 + 5, chờ 5 s (`packages/db/settings.py:19-21`): từ 15 lượt ghi đồng thời trên một tiến trình, mọi lượt giữ một kết nối và chờ kết nối thứ hai, không ai nhả → cả loạt 503 sau 5 s; dưới ngưỡng đó thì sức chứa ghi còn một nửa. FE thử lại 503 có khoá (W9) nên tải không giảm. **Probe G3:** pool 2, hai POST song song → không khoá `[200, 200]` 0,08 s, có khoá `[503, 503]` sau 2,09 s. **Không nâng P1** vì hôm nay chưa có route bảo vệ nào (tập tham số của `test_common` rỗng), nên đường này chưa với tới được. Route đầu tiên có dependency đọc DB trước guard (`require_project` của B2-01, nạp tài nguyên kiểu `Depends(get_x_or_404)`) hợp nhất mà chưa sửa thì đây là **P1** (lỗi dưới tải; PERF-08/CON-07 mặc định P1) | `apps/api/core/routing.py:175-183`, `:232-234`; `apps/api/core/idempotency.py:209`, `:266` | Tách pool (bulkhead): `lifespan` dựng một engine nhỏ riêng cho idempotency (vd `pool_size=5`, `max_overflow=0`, cùng `connect_args`), đặt `app.state.idempotency_sessionmaker`; `begin` và `discard` dùng nó. Lệnh nhận việc chỉ là một câu lệnh + commit nên pool nhỏ là đủ, và vì nó không bao giờ chờ pool của request nên hết vòng chờ. Test: dựng lại G3 (pool request 2, hai POST song song có khoá, dependency đọc DB) → `[200, 200]`. Chưa sửa thì ghi `DEBT.md` **trước khi merge** (R-38), cột mức ghi rõ "thành P1 khi B2-01 hợp nhất" |
| 2 | P3 | R-34 | Sổ nợ không phản ánh việc nhánh đã làm. `NO-019` (P2, B0-01) mô tả đúng hai test `test_real_task_names` và `test_main_đạt_khi_chưa_có_thao_tác` mà FIX-003 đã sửa (`tools/tests/test_case_gate.py:486-501` dựng sổ bằng `monkeypatch`) nhưng vẫn `⬜`. `NO-026` (ràng buộc cho B0-06) đã được tuân ở `app.py:147` (`await asyncio.to_thread(assert_broker_policy, …)`), `NO-017` (phần "B0-06 phải tuân") đã được tuân ở `files/router.py:51-53` (đọc `info.kind` lúc phục vụ); cả hai vẫn `⬜` | `DEBT.md:39`, `:41`, `:48` | `NO-019` → ✅ trỏ FIX-003 / `cdee48c`; `NO-026` → ✅ trỏ `app.py:147`; `NO-017` ghi phần B0-06 đã tuân, phần còn lại (#10, #12 của review B0-04) để mở |
| 3 | Nit | LOG-06 | `request_digest` không còn đúng chữ công thức BE-00 §7 (`method \| đường thật \| query đã sắp \| thân thô`, `BE-00.md:340`): nay mỗi phần mang tiền tố độ dài. Lý do đúng (hai request khác nhau trùng hash), nhưng đây là lệch hiến chương chưa được ghi ở đâu; dòng đầu docstring (`idempotency.py:87`) vẫn nêu công thức cũ | `apps/api/core/idempotency.py:86-100` | Ghi một dòng "Lệch khỏi hiến chương" trong `changes/B0-06.md`; người điều phối cập nhật câu của BE-00 §7 |
| 4 | Nit | R-02 | Docstring `_reset_settings` nói "Bốn cache cấu hình" nhưng thân chỉ xoá ba | `packages/testing/fixtures/api.py:169-172` | Sửa thành "Ba cache" |

Đã kiểm và **không** thấy finding thêm, ngoài những gì hai lượt trên đã kiểm: `_single_method` chạy trong `AppRoute.__init__` nên route sai hỏng ngay lúc nạp `router.py` (fail-closed); `request.json()` ném `ValueError` (kể cả `UnicodeDecodeError`) cho thân hỏng, giữ đúng hành vi cũ; `discard` sau khi lượt khác chiếm lại vẫn không xoá dòng của họ (`claim_token` khác); chiếm lại dòng hết hạn thuê mà khác hash thì lượt cũ hoàn tất 0 dòng và rollback, không ghi trùng; `jobs.py` vẫn có trần `BATCH × MAX_BATCHES`; merge-base là `3b7ebf4`, `main` chỉ đi thêm hai commit `docs/reviews/*` nên không có xung đột mã.

### Kiểm sổ nợ

- Không nợ P0/P1 nào còn `⬜`/`🔧` (25 dòng mở, mức cao nhất P2). `NO-031..033` ✅ có mã FIX và spec; `NO-037`, `NO-038` ✅ có commit `014ca6d` và test; `NO-034`, `NO-035`, `NO-039` ➖ có lý do đứng được; `NO-036` (P2, B0-03) ⬜ đủ cột.
- Finding #1 (P2) của lượt này **chưa** có dòng `DEBT.md` → phải ghi trước khi merge (R-38) nếu không sửa ngay.

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 3 (P2 #1) | 0,45 |
| LOG – Tính đúng đắn | 15 % | 5 (chỉ Nit #3) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (#1 tính một lần ở CON) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 MNT-05 chấp nhận ở `NO-039`; P3 #2) | 0,09 |

Tổng: 1,25 + 0,45 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,64 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập, độ phủ đạt ở mọi gói, không có P0/P1, điểm 4,64 ≥ 4,0. Mọi P2 và P3 của lượt 2 đã sửa, trừ MNT-05 được chấp nhận có lý do; hai P2 quan trọng (origin sai dạng, `discard` xoá dòng `completed`) được kiểm lại bằng test trong cổng và bằng probe chạy thật (G2).

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): sửa finding #1 (khuyến nghị: engine idempotency riêng, vài dòng trong `lifespan` cộng test G3), hoặc ghi `DEBT.md` một dòng P2 chủ B0-06, nêu rõ phải sửa trước khi B2-01 (hay bất kỳ route nào có dependency đọc DB trước guard) hợp nhất, vì khi đó nó thành P1.
2. Người điều phối xác nhận lời giao việc FIX-003..005 đã ghi ở `docs/fixes.md` (#8 của lượt 2).
3. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-01, B0-03, B0-05, B0-06), **không** squash.

P3 và Nit (#2–#4) do tác giả tự quyết, không chặn merge.

---

## Lượt review lại (độc lập) — lần 4

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, không phải ba phiên review trước; mọi khẳng định trong commit, `DEBT.md`, `docs/fixes.md` và ba lượt trên đều tự kiểm lại) · Commit đầu nhánh: `88d6c0b25285` (gốc `3b7ebf4`, 15 commit; mới so với lượt 3: `d82745d`, `45a73ad`, `88d6c0b`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ, log `verify2.log` trong scratchpad của phiên): `1142 passed, 10 skipped`. Cả 10 skip đều là `got empty parameter set for (operation)` ở `apps/api/core/tests/test_common.py:119, 128 (×4), 137, 151, 165, 177, 192` (tự kiểm bằng `pytest -rs`), đúng ngoại lệ duy nhất BE-00 §12 cho phép. Lượt gọi **đầu tiên** của phiên thoát 1 ngay ở `docker build` (`node:20-bookworm-slim`: `TLS handshake timeout` tới `registry-1.docker.io`), trước khi bước 1 chạy: tính là **chưa chạy**, không tính đạt; lượt chạy lại build bằng cache và chạy trọn 8 bước.
- Độ phủ: tổng dòng **99,23 %** · nhánh **96,73 %** · `apps/api/core` 99,46 % / 98,03 % · `apps/api/files`, `apps/api/health`, `packages/messaging` 100 % / 100 % · `packages/db` 98,65 % / 97,32 % · `packages/testing` 99,51 % / 100 % · `tools` 98,24 % / 94,05 % · tập file bị chạm 99,55 % / 98,21 %. Mọi gói và tổng đều ≥ 90 % ở cả hai số.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (184 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (160 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; 0 thao tác có dòng BE-BIND, 3 cảnh báo cho ba route công khai của [7]) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 | không áp dụng — hợp lệ: `changes/` chưa có `B0-07.md` |
| 8 | openapi | đạt |

**Điều kiện dừng sớm** (tự kiểm lại): cây sạch; `changes/B0-06.md` có, 9 dòng; 15 commit đúng mẫu Conventional Commits, dòng đầu dài nhất 70 ký tự (`960dced`); trailer đọc được bằng `%(trailers:key=Prompt)` cho cả 15 (`B0-06`×9, `B0-01`+`FIX-003`×2, `B0-03`+`FIX-004`×2, `B0-05`+`FIX-005`×2); diff không đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py`, `tools/verify/*`, `tools/charter.py`, không có file cấu hình công cụ; mọi `noqa`/`type: ignore` mới đều có mã; không `pragma`, `skip`, `xfail` mới. Không điều kiện nào kích hoạt.

**Công cụ kiểm tại chỗ** (container verify, Python 3.12; file probe chỉ nằm trong bản sao `/tmp/w`, xoá sau khi chạy, không vào repo):

- **R4-B — đỏ trước, xanh sau** của test mới: đổi `routing.py:176` về `request.app.state.sessionmaker` (đúng mã trước `d82745d`) → `test_claim_never_waits_on_the_request_pool` hỏng `assert 503 == 200` (`test_idempotency.py:363`) sau khi hết `pool_timeout`; trả lại dòng đó → đạt. Khớp lời ghi ở `NO-040`.
- **R4-C — dựng lại G3 của lượt 3 trên mã hiện tại** (pool request 2, `DB_MAX_OVERFLOW=0`, `DB_POOL_TIMEOUT_S=2`, route `/api/sample/db-first` có dependency đọc DB **trước** guard): 2 POST song song không khoá → `{200: 2}` 0,08 s; **có khoá → `{200: 2}` 0,12 s** (lượt 3: `[503, 503]` sau 2,09 s); 30 POST có khoá khác nhau → `{200: 30}` 0,44 s; 10 POST **cùng** khoá → `{200: 9, 503 IDEMPOTENCY_IN_PROGRESS: 1}` (một lượt chạy, tám lượt trả lại, không có 500). Pool nhận việc đọc từ app: `size=5`, `max_overflow=0`, `timeout` thừa hưởng `DB_POOL_TIMEOUT_S`.
- **AST** trên 49 file `.py` của diff: file của B0-06 thiếu docstring **0**; không hàm nào > 50 dòng.
- **Vòng chờ giữa hai pool** (đọc mã): pool nhận việc không bao giờ chờ pool request — `begin`/`discard` chỉ chạy một câu lệnh rồi commit; `_abort` và `_finish` đóng session request **trước** khi `discard` (`routing.py:299-305`, `:321-324`), nên không lượt nào giữ kết nối nhận việc trong lúc chờ kết nối request. Lệnh nhận việc chỉ có thể chờ khoá dòng do `complete` của lượt khác giữ, mà khoá đó nhả ở `commit` ngay sau, không cần pool nhận việc; chờ quá `lock_timeout` là `55P03` → 503 (`packages/db/errors.py`). Không có chu trình.

### Trạng thái finding cũ

| # | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| lượt 3 #1 | P2 | **đã sửa** | `d82745d`: `lifespan` dựng engine thứ hai `claims` (`app.py:143-147`; `CLAIM_POOL_SIZE = 5`, `db_max_overflow = 0`, `app.py:60-63`), đóng ở `app.py:167`; guard nhận việc và hai lời `discard` dùng `app.state.claim_sessionmaker` (`routing.py:176`, `:305`, `:324`) — sửa ở mọi đường gọi `begin`/`discard`. Test `test_claim_never_waits_on_the_request_pool` (`test_idempotency.py:348-364`) ghim pool request 1 kết nối, tất định (một request, không `sleep`). R4-B đỏ → xanh; R4-C: G3 nay `[200, 200]`. `NO-040` ✅ |
| lượt 3 #2 | P3 | **đã sửa** | `45a73ad`: `NO-019` ✅ trỏ FIX-003 / `cdee48c`; `NO-026` ✅ trỏ `eb40a3c` (`app.py:158` gọi `asyncio.to_thread(assert_broker_policy, …)`, client đóng ở `:164`); `NO-017` ghi phần B0-06 đã tuân (`files/router.py:51-53`), phần B0-04 còn mở. Chữ của hai dòng ✅: xem Nit #1 dưới |
| lượt 3 #3 | Nit | chấp nhận | Lệch chữ BE-00 §7 ghi thành `NO-041` (➖, lý do đứng được, có đường quay lại) và nêu ngay trong docstring `idempotency.py:92-94`, thay cho dòng trong `changes/B0-06.md` mà lượt 3 gợi ý — cùng mục đích: người điều phối thấy và sửa chữ hiến chương |
| lượt 3 #4 | Nit | **đã sửa** | `fixtures/api.py:169` "Ba cache cấu hình (core, db, storage)" |
| lượt 2 #3 | P2 | chấp nhận | `NO-039` ➖ (MNT-05). Vẫn tính điểm MNT |
| lượt 2 #8 | P3 | **chờ phiên merge xác nhận** | `docs/fixes.md` vẫn chỉ có lời giao việc FIX-003..005 do tác giả chép lại; repo không có bằng chứng độc lập |

Các mục đã sửa của lượt 1–2 vẫn còn nguyên trên mã hiện tại: `create_app` fail-fast (`app.py:184`), `Origin` sai dạng → `None` (`origin.py:185-188`, `:204-205`), `discard` chỉ xoá dòng `in_progress` (`idempotency.py:277`), `_single_method` và cấm `versioned` trên method đọc (`routing.py:114-124`, `:198-200`), `request.json()` (`routing.py:99-111`), `DELETE` dọn rác kiểm lại hạn (`jobs.py:51`).

### Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-34 | `NO-019` và `NO-026` đã đổi ô trạng thái sang ✅ nhưng cột "Ghi chú đóng" vẫn mở đầu bằng "mở — …" (chữ của lúc còn mở); ghi chú đóng chỉ được nối sau dấu "·". Ô ✔ là nguồn sự thật theo đầu sổ nên không sai nghĩa, nhưng người đọc lướt thấy hai chữ trái nhau trên cùng một dòng | `DEBT.md:41`, `:48` | Đổi tiền tố "mở —" thành "lúc mở:" (giữ lịch sử, không xoá chữ) và đưa ghi chú đóng lên đầu ô như các dòng ✅ khác |
| 2 | Nit | R-05 · OPS-04 | `CLAIM_POOL_SIZE = 5` là giới hạn cố định, không overflow; docstring nêu "5 kết nối phục vụ hàng nghìn lượt nhận việc mỗi giây" mà không có số đo, và chưa có đường nâng cấp (dấu hiệu nào thì nâng, nâng bằng cách nào). Hệ quả vận hành đi kèm: mỗi tiến trình API nay giữ tới 10 + 5 + 5 = 20 kết nối Postgres, chưa được ghi thành ngân sách cho người dựng compose (B0-08, cùng lớp `NO-006`) | `apps/api/core/app.py:60-63` | Thêm một câu nêu ngưỡng quan sát (vd 503 do `pool_timeout` ở guard nhận việc) và đường nâng cấp (nâng hằng, hoặc đưa ra biến môi trường khi có số đo); ghi ngân sách kết nối mỗi tiến trình vào phần bàn giao cho B0-08 |

Đã kiểm và **không** thấy finding thêm trong ba commit mới: `database.model_copy(update=…)` giữ nguyên DSN, trần bắt tay, `statement_timeout`/`lock_timeout` của engine request (R4-C đọc lại pool thật); `api_env` dọn cache cấu hình khi kết thúc (`fixtures/api.py:165`) nên `DB_POOL_SIZE=1` của test mới không rò sang test sau; `claim_sessionmaker` chỉ đặt trong `lifespan`, và mọi app thử đi qua `make_api_client` (có chạy `lifespan`); `openapi.real_app()` không chạy `lifespan` nên bước 8 không mở pool nào; `/api/ready` chỉ thử engine request — chấp nhận, hai engine cùng DSN. Merge-base vẫn là `3b7ebf4`; `main` chỉ đi thêm ba commit `docs/reviews/*`, không xung đột mã.

### Kiểm sổ nợ

- Không nợ P0/P1 nào còn `⬜`/`🔧` (24 dòng mở, mức cao nhất P2: `NO-006`, `-007`, `-009`, `-010`, `-011`, `-021`, `-027`, `-036`, `-042`).
- `NO-040` ✅ đã kiểm lại bằng R4-B và R4-C. `NO-041` ➖ lý do đứng được. `NO-019`, `NO-026` ✅ khớp mã (xem Nit #1 về chữ).
- `NO-042` ⬜ (P2, B0-01): nguyên nhân gốc tự kiểm trong mã — `tools/tests/test_services.py:33` gọi `asyncpg.connect(…, timeout=5)` cho cả bản Postgres **dùng chung** qua chặng `host.docker.internal`; cùng lớp `NO-007`/`NO-036`. Lượt cổng của phiên này không gặp nó. File ngoài quyền B0-06 (K27), đúng là việc của FIX cho B0-01; không chặn merge.
- Hai Nit của lượt này không bắt buộc ghi `DEBT.md`.

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 (lượt 3 #1 đã sửa, R4-C) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 (chỉ Nit #2) | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 MNT-05 chấp nhận ở `NO-039`; Nit #1) | 0,09 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,94 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập, độ phủ đạt ở mọi gói, không có P0/P1, điểm 4,94 ≥ 4,0. P2 duy nhất của lượt 3 (một lượt ghi có khoá giữ hai kết nối của cùng một pool) đã được sửa ở gốc bằng pool nhận việc riêng, và được kiểm bằng cả test đỏ → xanh (R4-B) lẫn dựng lại đúng kịch bản G3 (R4-C). P3 và Nit của lượt 3 đã sửa, hoặc được chấp nhận có lý do.

Điều kiện cho phiên merge:

1. Người điều phối xác nhận lời giao việc FIX-003..005 ghi ở `docs/fixes.md` (#8 của lượt 2; repo vẫn chỉ có lời của tác giả).
2. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-01, B0-03, B0-05, B0-06), **không** squash.
3. Không chặn merge, nên làm sớm: giao FIX cho B0-01 (`NO-042`) và B0-03 (`NO-036`), hai nguồn cổng đỏ giả còn lại quanh chặng `host.docker.internal` (`NO-007`); sửa chữ BE-00 §7 theo `NO-041`.

Nit #1–#2 do tác giả tự quyết.
