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
