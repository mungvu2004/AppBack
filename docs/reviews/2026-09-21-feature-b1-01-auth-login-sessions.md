# Review merge feature/b1-01-auth-login-sessions → main

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `changes/B1-01.md` và báo cáo tác giả đều tự kiểm lại) · Commit đầu nhánh: `04a1c3a42433` (gốc `5bb39de` = `main` hiện tại, 6 commit: `4320e0e` B1-01, `1e2d146` B0-06 + FIX-029, `de7f9ea` B1-01, `971a1a1` B0-06 + FIX-030, `9f80576` B0-06 + FIX-031, `04a1c3a` B1-01). `main` không đi thêm commit nào, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong worktree sạch của nhánh; log `b1-01-verify.log` trong scratchpad của phiên): `1631 passed, 10 skipped` trong 318,1 s. Cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng: chưa có route **được bảo vệ** nào; ba route của nhánh là công khai), đúng ngoại lệ BE-00 §12.
- Độ phủ (in từ `tools.coverage_gate`, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,20 %** · nhánh **96,66 %**
  - `apps/api/auth`: dòng **98,44 %** · nhánh **91,13 %**
  - `apps/api/core`: dòng 99,47 % · nhánh 98,06 % · `packages/db`: 98,77 % · 97,32 % · `packages/testing`: 99,09 % · 100,00 %
  - tập file bị chạm: dòng **98,52 %** · nhánh **92,76 %**
  - Các dòng `coverage` báo thiếu trong `apps/api/auth` (vd `router.py:169`, chạy ở **mọi** lượt đăng nhập) đều là dòng ngay sau một `await` đi qua greenlet của SQLAlchemy — đúng sai số đo đã chấp nhận ở `NO-035`, không phải thiếu test.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (261 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (231 file) |
| 4 | `lint-imports` | đạt (mọi hợp đồng KEPT, gồm `apps.api.*.jobs` không nhập `fastapi/starlette/uvicorn/jwt/argon2`) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf`; `auth_login` 7/7, `auth_refresh` 5/5, `auth_logout` 2/2 case bắt buộc) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9, gồm "model khớp DB") |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 146 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B1-01.md` tồn tại, 3–10 dòng | đạt (10 dòng) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — cả 6 commit (dài nhất 67 ký tự) |
| Trailer đọc được (R-36b) | đạt — mỗi commit có `Prompt:`; ba commit FIX có thêm `Fix: FIX-029/030/031`; khối trailer liền nhau, có dòng trống trước |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — mọi `noqa` mới có mã và lý do (`S105`, `S106`, `S101`, `S603`); một `type: ignore[arg-type]` có mã và lý do trong test (`test_units.py:171`), cùng lối với tiền lệ ở `apps/api/core/tests/` |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

File ngoài cột `so_huu` của prompt: `apps/api/core/{ratelimit.py, tests/test_app.py, tests/test_openapi.py, tests/test_ratelimit.py, tests/test_fixtures.py}`, `packages/testing/fixtures/api.py` (FIX-029..031, commit riêng `Prompt: B0-06`), `DEBT.md`, `docs/fixes.md`. Theo báo cáo tác giả, người điều phối cấp phép "FIX here" ngày 2026-09-21 (ngoại lệ K27, cùng tiền lệ FIX-003..005 ghi ở `docs/fixes.md`). Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (bản sao `/tmp/w`, không vào repo):

- **P1 — đỏ trước / xanh sau của ba FIX.** Đặt lại file của `main` vào bản sao: `ratelimit.py` cũ + hai test mới → `2 failed` (`TypeError: '<' not supported between instances of 'function' and 'int'`); `fixtures/api.py` cũ + test mới → `1 failed`; `test_app.py`/`test_openapi.py` cũ trên mã nhánh → đúng **5 failed** như NO-053. Bản của nhánh: `67 passed` cho bốn file test lõi. Hành vi của hạn mức số nguyên không đổi (vẫn kiểm lúc khai, `test_rate_limit_rejects_bad_quota` xanh).
- **P2 — thuật toán refresh gọi thẳng `refresh_session` trên Postgres thật, `fake_clock`:**
  - biên ân hạn: xoay T0→T1; đúng +30 s gửi T0 → `Refreshed` cùng T1; +30 s +1 µs → `SESSION_REVOKED` (dùng lại);
  - 5 lượt song song trên **5 session DB riêng** cùng T0 → cả 5 `Refreshed`, **1** token duy nhất (so-và-đặt + đọc lại một lần hoạt động);
  - chuỗi qua một lần xoay `SECRET_KEY`: T0 –K_old→ T1, xoay khoá (khoá cũ sang `SECRET_KEY_PREVIOUS`), +31 s T1 –K_new→ T2, +31 s gửi lại T0 → `UNAUTHENTICATED`, `revoked_reason = None` (xem #3).
- **P3 — tầng thất bại của refresh:** 40 lượt **song song** cùng một cookie `<sid>.<rác>` → `401 × 40`, `429 × 0` (trần 20) (xem #2).
- **P4 — khoá đăng nhập:** 12 lượt sai **song song** cùng (email, IP) → `401 × 5`, `429 × 7`: kịch bản Lua nguyên khối đúng như docstring.
- **P5 — chống dò (C27), đếm lệnh ở DB an toàn bằng `INFO commandstats`:** email có thật sai mật khẩu và email lạ cùng 3 vòng mạng (`EVALSHA × 2` — hạn mức IP của B0-06 và `admit` — cộng một `MULTI/EXEC`), cùng tập lệnh; chênh duy nhất là một `EXPIRE` của nhánh `fails == 1` trong Lua, phụ thuộc "lượt đầu của cặp (email, IP)" chứ không phụ thuộc email có tồn tại.
- **P6 — AST 37 file `.py` của diff:** không hàm nào > 50 dòng, không hàm/lớp nào thiếu docstring. Dòng logic (bỏ trống, comment, docstring): **≈ 1 270** sản phẩm của B1-01 (gồm migration 84, model 70) + 85 của `ratelimit.py`; **≈ 1 500** test của `apps/api/auth` + fixture/factory.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | MNT-05 | Nhánh ≈ 1 270 dòng logic sản phẩm B1-01 + ≈ 1 500 dòng test, vượt 400. **Không đáng tách:** một prompt; đăng nhập → `start_session` → refresh → verifier → `check_session` móc vào nhau, tách ra là đưa vào `main` một nửa thuật toán BE-00 §5. Ba FIX của B0-06 đã tách commit riêng | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` như `NO-039`, `NO-045`, `NO-047` |
| 2 | P3 | SEC-14 · CON-01 | Tầng thất bại của refresh là **đọc-rồi-mới-tăng** không nguyên khối: `_check_failures` `peek` (GET+TTL), handler chạy, rồi mới `bump` khi bị từ chối. Mọi lượt song song cùng đọc số cũ nên cùng lọt. **Probe P3:** 40 lượt song song cùng cookie rác → 40 × 401, 0 × 429 (trần 20). Không nâng mức theo luật "auth": tầng này không phải ranh giới bảo mật — kẻ tấn công vốn đổi token (mỗi token một bucket, đúng thiết kế BE-00 §11), còn tầng tổng theo `sid` (INCR nguyên khối) vẫn giữ trần 300/phút; tác động chỉ là trần 20/phút "mềm" dưới tải song song | `apps/api/auth/router.py:207-211`, `:223`, `:228` | Tăng **trước** rồi bù: `count = bump(bucket)`; `count > REFRESH_FAIL_LIMIT` → 429; lượt thành công `DECR` (chủ phiên vẫn không tự khoá mình). Hoặc giữ nguyên và ghi ngưỡng theo R-05 ("vượt trần tối đa bằng số lượt đang song song") trong docstring `_check_failures` |
| 3 | P3 | LOG-02 · SEC-03 | Dò chuỗi HMAC đi **từng khoá riêng** (`for key: step = next(step, key)` 32 lần), nên chuỗi xoay **băng qua một lần xoay `SECRET_KEY`** (đoạn đầu ký K_old, đoạn sau K_new) không bao giờ chạm `current`. **Probe P2:** T0 –K_old→ T1, xoay khoá, T1 –K_new→ T2, gửi lại T0 → 401 `UNAUTHENTICATED`, phiên **không** bị thu hồi. Đúng chữ BE-00 §5 bước 7 ("với từng khoá kiểm"), không cho ai vào được; mất đúng tính năng "phát hiện token bị đánh cắp" trong cửa sổ xoay khoá (token cũ ≥ 2 bước, đi qua mốc xoay) | `apps/api/auth/sessions.py:381-389` | Chuỗi chỉ đổi khoá tối đa một lần (luôn ký bằng `current_key`), nên thử thêm "a bước K_cũ rồi tới 32−a bước K_mới" (≈ 560 HMAC mỗi token lạ khi có hai khoá, dưới 1 ms); hoặc ghi giới hạn theo R-05 trong docstring `_chain_reaches` kèm một test chốt hành vi |
| 4 | P3 | R-14 · MNT-03 | Nhánh dự phòng không với tới được: sau `UPDATE` 0 dòng, `_decide` lần hai **không thể** trả `_Rotate` (lệnh `UPDATE` hỏng nghĩa là `current_token_hash` đã đổi hoặc `revoked_at` đã đặt và đã commit; không đường nào đổi ngược lại — chính docstring nói vậy). Nhánh vẫn viết, lại **trả thành công** với token trình lên, và nằm trong biểu thức điều kiện một dòng nên độ phủ nhánh không nhìn thấy | `apps/api/auth/sessions.py:484-485` | Làm bất biến tường minh: cho `_decide` tham số `allow_rotate=False` ở lượt hai (trả `Refreshed \| RefreshDenied`), hoặc `raise RuntimeError(...)` khi gặp `_Rotate` — trạng thái "không thể" phải nổ to, không lặng lẽ cho qua |
| 5 | P3 | OBS-01 · SEC-14 | Không có dòng log nào khi thu hồi phiên vì **dùng lại** (dấu hiệu token bị đánh cắp) hay khi khoá đăng nhập bị đặt; ở access log hai việc này chỉ là 401/429 lẫn trong token rác và gõ sai. Nhật ký hoạt động thuộc B1-02, nhưng một dòng log vận hành thì không | `apps/api/auth/sessions.py:429-431`; `apps/api/auth/login_guard.py:103-104` | `_log.warning("refresh_reuse_revoked", extra={"sid": str(sid)})` (không token, không email); `login_locked` với `email_key` và mã kết quả của `admit` |
| 6 | Nit | R-01 · MNT-04 | Docstring thuộc tính đặt sau `UNKNOWN_SID` nhưng mô tả `FAIL_BUCKET_HEX` ("sid + 16 ký tự đầu SHA-256…"); nhánh `UNKNOWN_SID` của `_cookie_sid` cũng không với tới được (handler đã kiểm mẫu cookie trước khi gọi limiter) | `apps/api/auth/router.py:60-62`, `:109-112` | Chuyển docstring lên ngay dưới `FAIL_BUCKET_HEX`; `_cookie_sid` nhận thẳng `sid` đã giải (hoặc ghi rõ nhánh dự phòng là cho khoá gọi ngoài handler) |
| 7 | Nit | CON-07 | `touch_last_active` khoá `FOR UPDATE SKIP LOCKED`; khoá này xung đột với `FOR KEY SHARE` mà `INSERT refresh_sessions` (FK) cần, nên một lượt đăng nhập của cùng người phải **chờ** giao dịch refresh đang giữ dòng `users` (ngắn, không deadlock). `FOR NO KEY UPDATE` đủ cho việc chỉ ghi `last_active_at` | `apps/api/auth/sessions.py:354` | `.with_for_update(skip_locked=True, key_share=True)` (PostgreSQL: `FOR NO KEY UPDATE SKIP LOCKED`) |
| 8 | Nit | DB-05 | Không có `CHECK` ghép cặp `revoked_at`/`revoked_reason`; một module khác (B1-03, B1-05) ghi thiếu một trong hai vẫn lọt, trái tinh thần docstring model ("luật giá trị giữ bằng `CHECK`") | `packages/db/models/auth.py:98-99` | `CHECK ((revoked_at IS NULL) = (revoked_reason IS NULL))` ở revision kế tiếp của B1-01 (hay ngay revision này trước khi hợp nhất) |
| 9 | Nit | TEST-02 | Test pool K36 giữ mọi chỗ băm trong khi chờ tối đa 1,5 s + 1,5 s + lượt probe, còn 40 lượt đăng nhập bỏ cuộc sau `HASH_WAIT_S = 2 s`. Máy chậm thì khẳng định cuối `[401] * 40` thành 503 — đỏ giả (không xanh giả). Đo thật: pool rảnh sau ≈ 50 ms nên hôm nay không chập chờn | `apps/api/auth/tests/test_login.py:320-341` | Khẳng định tổng thời gian giữ chỗ < `HASH_WAIT_S`, hoặc nâng trần chờ trong test bằng `monkeypatch` |
| 10 | Nit | TEST-02 | Test chặn tái phát của FIX-031 chỉ kiểm **đồ thị fixture** (`safe_client ∈ request.fixturenames`), không kiểm DB an toàn thật sự rỗng sau khi dọn | `apps/api/core/tests/test_fixtures.py:89-92` | Chấp nhận được (kiểm hành vi giữa hai test là phụ thuộc thứ tự chạy); nếu muốn: một test tự `SET` vào DB an toàn rồi gọi teardown của `api_env` bằng `request.getfixturevalue` trong một phạm vi con |
| 11 | Nit | R-07 | Tập lý do thu hồi khai hai nơi: `RevokeReason` (`Literal`) và `REVOKE_REASONS` (tuple của `CHECK`); thêm một lý do phải sửa cả hai (cộng migration) | `apps/api/auth/sessions.py:70-72`; `packages/db/models/auth.py:32-41` | Khai `Literal` ở model, dựng tuple bằng `typing.get_args` |
| 12 | Nit | — (sổ) | Cột "Commit" của FIX-029..031 ghi tên nhánh thay vì sha như FIX-001..028 | `docs/fixes.md:38-40` | Người điều phối điền `1e2d146`, `971a1a1`, `9f80576` khi gộp (`--no-ff` giữ nguyên các sha này) |

**P0: 0 · P1: 0 · P2: 1 · P3: 4 · Nit: 7**

## Những chỗ đã soi kỹ và **đạt**

- **Thuật toán refresh (BE-00 §5, K10, K35), từng bước:** cookie thiếu/sai mẫu (`<uuid chữ thường>.<43 ký tự base64url>`) → 401 `UNAUTHENTICATED` trước mọi thứ; hai tầng hạn mức (`store="cache"`, `on_error="open"`, qua `soft_redis`) trước khi đọc phiên; không có phiên → `UNAUTHENTICATED`; **thu hồi/hết idle/hết tuyệt đối kiểm trước mọi nhánh** → `SESSION_REVOKED` (test "logout rồi gửi `previous` trong ân hạn"). `current` trong ân hạn → trả lại chính cookie, không xoay lần hai; ngoài ân hạn → `UPDATE … WHERE id AND current_token_hash AND revoked_at IS NULL RETURNING`; 0 dòng → đọc lại **một** lần: dưới READ COMMITTED lượt thua chỉ có thể thấy mình là `previous` trong ân hạn hoặc phiên đã thu hồi (probe P2 + `test_losing_the_rotation_race…` dựng đúng thế chờ khoá dòng qua `pg_stat_activity`). `previous` trong ân hạn → token kế tiếp **tính lại** và kiểm `sha256(next) = current` với từng khoá của `verification_keys`, không ghi DB; ngoài ân hạn → thu hồi `reuse`. Token lạ → chuỗi ≤ 32 bước; chạm `current` → `reuse`, không chạm → `UNAUTHENTICATED` **không ghi DB** (30 token rác, phiên vẫn sống). Người không `active`/đã xoá → thu hồi `disabled`/`deleted`. Mọi so sánh băm dùng `hmac.compare_digest`; DB chỉ giữ SHA-256.
- **Từ chối được *trả* chứ không ném:** `refresh_session` trả `RefreshDenied`, handler trả `error_response(...)`; `AppRoute` chỉ rollback khi có ngoại lệ (`routing.py:16-17`, `_finish` commit cả response 4xx), nên lệnh thu hồi `reuse` được commit — test C20 đọc lại `revoked_reason == "reuse"` trên session mới.
- **Hạn phiên:** ghi nhớ 7/30 ngày, không ghi nhớ 12/24 giờ; xoay kéo idle tới `min(now + idle, absolute)` (test 4 lượt × 6 ngày chạm đúng ngày 30); `last_active_at` bằng `UPDATE … WHERE id IN (SELECT … FOR UPDATE SKIP LOCKED)` khi cũ hơn 5 phút (test dòng đang bị khoá → refresh vẫn 200 dưới 3 s). Xoá ảnh chụp cache sau commit khi xoay (lệch #7 của tác giả) có lý do đứng được: ảnh chụp mang hạn idle cũ.
- **Đăng nhập (B1-01 [6], C27, K36):** đúng thứ tự 1–9; `require_origin` rồi hạn mức IP `store="safe"`, `on_error="closed"` (chạy trước khi Pydantic kiểm thân); khoá/`INCR fail`/hạn mức mềm email nằm trong **một** kịch bản Lua (probe P4); email lạ, người `pending` và sai mật khẩu đi cùng một đường (băm giả dựng lười, cùng hồ sơ), cùng thân 401 (probe P5, test C27 40/40 + 429 ở cùng lượt thứ 6); `ACCOUNT_DISABLED` chỉ sau mật khẩu đúng; `await db.rollback()` **trước** khi băm và trước khi băm lại (`_rehash` so-và-đặt trên băm cũ); test pool 1 kết nối khẳng định `checkedout() == 0` trong lúc 40 lượt kẹt chờ băm, route bảo vệ đọc DB xong < 1 s. Trả 204 bằng `None` để FastAPI giữ `Set-Cookie`.
- **Băm (BE-00 §5, §7):** argon2id `RFC_9106_LOW_MEMORY`; hồ sơ `test` bị từ chối ngoài `APP_ENV=test`; `nfc()` trước khi băm và kiểm; executor riêng `PASSWORD_HASH_CONCURRENCY` luồng; semaphore theo vòng sự kiện (`WeakKeyDictionary`, dựng lười); `wait_for(sem.acquire(), 2 s)` rồi mới `run_in_executor` → 503 `DEPENDENCY_UNAVAILABLE` + `Retry-After` (không `wait_for` quanh executor). Băm hỏng trong DB → 401 có log, không 500.
- **Verifier (K04, K20, K30, K34):** `jwt.decode(algorithms=["HS256"], audience=…)`, tắt ba kiểm thời gian của PyJWT, `require` đủ năm claim; tự so `exp > now`, `iat ≤ now + 30 s` với `Clock` tiêm; kiểm kiểu từng claim (chặn `bool`, `ver < 0`, `sub` sai mẫu `usr_`, `sid` không phải UUID chuẩn); chỉ lỗi chữ ký mới thử khoá kế tiếp. `alg: none`, khoá lạ, `aud="stream"`, thiếu `sid`, hết hạn theo `fake_clock`, `iat` tương lai → 401 `UNAUTHENTICATED`; `fake_clock` +1 năm vẫn qua. `check_session`: ảnh chụp cache ≤ 5 s (trần trong `AuthSettings`), hỏng/sai kiểu/vai lạ → đọc Postgres bằng session ngắn riêng (không 503, không 401); Postgres hỏng → 503 (không đăng xuất người dùng); vai luôn từ DB. Thu hồi, vô hiệu, `bump_token_version` → 401 ngay sau commit; xoá cache hỏng → hết sau TTL.
- **Cookie:** hai cookie `HttpOnly; Secure; SameSite=Strict`, `Path=/api/auth` và `/api/streams`; `Max-Age` tới hạn idle chỉ khi ghi nhớ; cookie luồng `Max-Age=600`; xoá = cùng tên, cùng `Path`, `Max-Age=0`. Logout: `Origin` lệch/thiếu → 403 **kèm** lệnh xoá hai cookie, không thu hồi; không cookie/cookie rác/lặp → 204.
- **Email (K37):** regex `.email()` của zod 3.23.8 chép đúng, `re.IGNORECASE | re.ASCII`, `isascii()`, trim, ≤ 254 trước khi khớp (không ReDoS); `ſ`, `K`, `İ`, `ı`, `admin@localhost`, Unicode → 422 `field:"email"`. `email_key` là HMAC khoá `lookup` (32 hex), khoá Redis không bao giờ chứa email thô.
- **Dữ liệu (BE-00 §6, §6.1):** một revision `r20260921_b1_01` (15 ký tự) chỉ tạo hai bảng mới + index cùng revision (expand, không cần `CONCURRENTLY`), `downgrade()` thật, `migrate_check` 9/9 gồm "model khớp DB". Truy vấn mới đều có index: đăng nhập dùng unique partial `uq_users_email`; `read_state` theo PK; thu hồi hàng loạt/`bump_token_version` dùng `ix_refresh_sessions_user_id_live`; lịch dọn dùng hai index bổ sung (lệch #4 của tác giả, đứng được theo R-21). `CHECK` vai/trạng thái/ngôn ngữ/lý do/độ dài tên ở DB.
- **Lịch dọn, CLI, ranh giới:** `@periodic("default.auth.purge_sessions", every=1 giờ)` gọi lõi `run_purge_sessions(worker_sessionmaker(), SystemClock())`, xoá theo lô có trần vòng lặp; J01, J06, test lô nhỏ và test khói gọi chính hàm lịch. Test tiến trình con chặn đủ bốn gói `fastapi/starlette/jwt/argon2` rồi nhập `jobs`; nhập `cli` không đọc stdin; nhập mọi module không đọc cấu hình, không dựng executor. CLI: mật khẩu chỉ từ stdin/`getpass`, in bằng `sys.stdout.write`, thoát 0/2/3, mật khẩu không có trong stdout/stderr/log.
- **Hợp đồng FE:** `SignInSchema` strict (`rememberMe` `strict=True`, khoá lạ → 422, mật khẩu ≥ 8 như `PasswordSchema` của FE `src/api/schemas/index.ts:56,69`); W16 `{accessToken, expiresAt .000Z, roles: [đúng 1 vai], user}` qua schema strict riêng (H1 đạt); `register` không mount (404).
- **Test:** dịch vụ thật (Postgres, hai Redis, container Redis tạm dừng được cho ca `redis-cache`/DB an toàn chết), không mock; thời gian qua `fake_clock`, chỉ chờ TTL Redis nhỏ (≤ 4 s) bằng `wait_until` có trần; test đồng thời thật (C19 `gather`, cuộc đua khoá dòng dựng bằng `pg_stat_activity`). Mọi dòng của ma trận [8] có test; `case_gate` đủ case của ba thao tác.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Khoá theo BE-00 §11 ("bộ đếm sai sống 900 s, mỗi lượt sau lần sai thứ 5 lại khoá"), thêm `LOGIN_FAILURE_WINDOW_S` | **Đứng được.** Chính thuật toán bước 3 của prompt [6] (`INCR fail` TTL 900 s, `> LIMIT` → khoá) cho ra hành vi này; câu test "qua `LOGIN_LOCK_S` → được" mâu thuẫn với nó và với hiến chương → theo hiến chương (CLAUDE.md). Trần khoá có hạn: TTL bộ đếm chỉ đặt ở lượt đầu, nên tối đa 900 s + `LOGIN_LOCK_S` |
| 2 | Test pool theo K36 (`DB_POOL_SIZE=1`, `MAX_OVERFLOW=0`, `POOL_TIMEOUT_S=1`, `checkedout() == 0`) | **Đứng được.** K36 ghi đúng cấu hình này, chặt hơn `DB_POOL_SIZE=2` |
| 3 | Test ranh giới `jobs` chặn bốn gói | **Đứng được.** BE-00 §7 "Hàm worker nhập" |
| 4 | Thêm hai index cho lịch dọn | **Đứng được.** R-21 |
| 5 | Hạn mức tách cặp `*_LIMIT` + `*_WINDOW_S` | **Đứng được.** Giá trị mặc định đúng [5] |
| 6 | `UPDATE` xoay thêm `revoked_at IS NULL`; 0 dòng → đọc lại một lần | **Đứng được** về thuật toán (probe P2, test đua); nhánh dự phòng của lượt đọc lại là #4 |
| 7 | Xoay xong xoá ảnh chụp cache sau commit | **Đứng được.** Tránh 401 oan sát hạn idle |
| 8 | Body đăng nhập đòi `password` ≥ 8 → 422 `field:"password"` | **Đứng được.** Đúng `PasswordSchema` của FE; 422 không lộ gì về tài khoản |
| 9 | Commit theo Conventional Commits | **Đứng được.** BE-00 §13.2 |
| 10 | Sửa file ngoài "Sở hữu" (FIX-029..031, `docs/fixes.md`, `DEBT.md`) | **Đứng được** với cấp phép của người điều phối ghi trong báo cáo tác giả (ngoại lệ K27, tiền lệ FIX-003..005). Mỗi FIX sửa đúng gốc (test chốt trạng thái repo; `rate_limit` nhận hạn mức gọi được; `api_env` dọn cả DB an toàn), giữ hành vi của người gọi cũ, đỏ trước/xanh sau đã tự tái hiện (probe P1) |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt — `NO-053` (P1), `NO-054` (Nit), `NO-055` (P3), cả ba `✅` kèm ngày đóng và mã FIX; đúng lối ghi "mở — … · FIX-…" của các dòng đã đóng trước đó |
| Nợ P0/P1 còn `⬜`/`🔧` | không — `NO-053` (P1) đã đóng bằng FIX-029, đã tự kiểm |
| Nợ do review này chỉ ra đã có dòng | **chưa** — xem dưới |

Dòng đề xuất (id kế tiếp còn trống sau nhánh là `NO-056`; phiên này **không** tự ghi vào `DEBT.md`):

- `| ➖ | NO-056 | 2026-09-21 | 2026-09-21 | Nhánh feature/b1-01-auth-login-sessions vượt trần 400 dòng logic của MNT-05 (≈ 1 270 dòng sản phẩm, ≈ 1 500 dòng test) | Một prompt; đăng nhập, phiên, refresh và verifier móc vào nhau (BE-00 §5) | B1-01 | P2 | Chấp nhận như NO-039/NO-045/NO-047: tách là đưa vào main một nửa thuật toán. Review merge 2026-09-21 finding #1 |`
- Nếu không sửa trong nhánh: `⬜` P3 chủ B1-01 cho #2 (`router.py:207`, tầng thất bại đọc-rồi-tăng), #3 (`sessions.py:381`, chuỗi qua mốc xoay khoá), #4 (`sessions.py:485`, nhánh dự phòng không với tới), #5 (`sessions.py:429`, `login_guard.py:103`, thiếu log sự kiện bảo mật) — mỗi dòng trích "review merge 2026-09-21 finding #n".

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 (P3 #2) | 1,00 |
| CON – Concurrency & dữ liệu | 15 % | 5 (Nit #7) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #3, #4) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (Nit #8) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #9, #10) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 4 (P3 #5) | 0,20 |
| MNT – Bảo trì | 3 % | 3 (P2 #1; Nit #6, #11, #12) | 0,09 |

Tổng: 1,00 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,35 + 0,20 + 0,09 = **4,49 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập, độ phủ đạt ở mọi gói bị chạm (`apps/api/auth` 98,44 % / 91,13 %), không có P0/P1, điểm 4,49 ≥ 4,0. Phần rủi ro nhất của prompt — thuật toán refresh BE-00 §5 — được cài đúng từng bước và được chứng minh bằng chạy thật chứ không chỉ khẳng định: thu hồi kiểm trước ân hạn, không xoay lần hai trong 30 s, so-và-đặt với một lượt đọc lại (5 session DB song song ra đúng một cookie), biên ân hạn chính xác tới micro giây, token rác không ghi DB, lệnh thu hồi vì dùng lại được commit vì từ chối được *trả* chứ không ném. Đăng nhập chống dò đúng (cùng đường, cùng số vòng Redis, khoá nguyên khối trong Lua), K36 có test pool 1 kết nối, verifier không bao giờ so giờ thật và không tin vai trong token. Cả 10 điểm "lệch khỏi prompt" đứng được; ba FIX của B0-06 sửa đúng gốc và đỏ trước/xanh sau đã tự tái hiện.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): ghi `DEBT.md` dòng `NO-056` dạng `➖` cho #1 (MNT-05, chấp nhận). Nên ghi `⬜` P3 cho #2–#5 nếu tác giả không sửa trong nhánh; Nit #6–#12 do tác giả tự quyết, không chặn merge.
2. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B1-01 **và** của B0-06 + `Fix: FIX-029/030/031`), **không** squash.
3. Người điều phối ghi nhận ngoại lệ K27 của FIX-029..031 (đã cấp phép trong phiên tác giả) và điền sha `1e2d146`, `971a1a1`, `9f80576` vào cột "Commit" của `docs/fixes.md` (Nit #12).
