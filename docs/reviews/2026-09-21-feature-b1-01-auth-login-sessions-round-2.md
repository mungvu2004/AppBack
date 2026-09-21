# Review merge feature/b1-01-auth-login-sessions → main — lượt 2

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập**, khác phiên tác giả và khác reviewer lượt 1. Lượt 1 (`APPROVE 4,49/5` tại `04a1c3a42433`) ở `docs/reviews/2026-09-21-feature-b1-01-auth-login-sessions.md`, commit `ef69c60` trên `main`. Mọi khẳng định trong hai commit mới đều kiểm lại bằng diff, probe và cổng; lời commit không được tính là bằng chứng · Commit đầu nhánh: `b877f464a019` (gốc `5bb39de`, 8 commit). Hai commit mới so với lượt 1: `b6e85b9` `fix(auth): address b1-01 merge review findings` và `b877f46` `docs(repo): log NO-056 and record FIX-029..031 commits`. Cả hai mang `Prompt: B1-01`, đọc được bằng `%(trailers:key=Prompt,valueonly)`, dòng đầu dài 47 và 55 ký tự. Tác giả cố ý không rebase (rebase sẽ đổi các sha FIX mà `docs/fixes.md` ghi). Từ gốc tới giờ `main` chỉ thêm file phán quyết lượt 1; `git merge-tree --write-tree main HEAD` không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** ở lượt chạy đầu tiên và duy nhất (chạy tại chỗ trong worktree sạch, log `review2/verify.log` trong scratchpad của phiên): `1638 passed, 10 skipped` trong 213,1 s. Lượt 1 có 1631, nay thêm đúng 7 test mới. 10 skip vẫn là `apps/api/core/tests/test_common.py` với tập tham số rỗng, đúng ngoại lệ BE-00 §12.
- Độ phủ (lấy từ `tools.coverage_gate`):
  - tổng: dòng **99,22 %** · nhánh **96,75 %**
  - `apps/api/auth`: dòng **98,61 %** · nhánh **92,65 %** (lượt 1: 98,44 / 91,13)
  - `apps/api/core`: 99,47 / 98,06 · `packages/db`: 98,77 / 97,32 · `packages/testing`: 99,09 / 100,00
  - tập file bị chạm: dòng 98,64 % · nhánh 93,90 %
  - `coverage` riêng cho `apps/api/auth` báo thiếu `router.py:151,173,248,277` và `sessions.py:369,452,455,458,460,463` (kể cả dòng log mới `:458`). Tất cả là dòng nằm ngay sau một `await` đi qua greenlet của SQLAlchemy, tức sai số đo đã chấp nhận ở `NO-035`. Chúng không phải thiếu test: chẳng hạn `test_reuse_is_logged_without_the_token` chỉ đạt khi `:458` thật sự chạy.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (261 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (231 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng KEPT, 0 BROKEN) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf`; `auth_login` 7/7, `auth_refresh` 5/5, `auth_logout` 2/2) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9, gồm "model khớp DB") |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. H1 có 186 mẫu. H3/H4/H5 `không áp dụng` là **hợp lệ** vì B1-02, B3-05, B4-01 chưa hợp nhất |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng (trước và sau probe) | đạt |
| `changes/B1-01.md` | đạt (không đổi, 10 dòng) |
| Dòng đầu Conventional Commits, trailer đọc được (R-36b) | đạt với cả 8 commit |
| Diff `04a1c3a..HEAD` đụng file cấm | không. Diff chỉ chạm `apps/api/auth/{login_guard,router,sessions}.py`, ba file test của `apps/api/auth`, `packages/db/models/auth.py`, revision `r20260921_b1_01_auth.py` của chính B1-01, `DEBT.md` và `docs/fixes.md` (chỉ cột "Commit") |
| `pragma` / `type: ignore` / `noqa` / `skip` / `xfail` mới, hạ ngưỡng | không |

## Probe chạy lại

Probe chạy trong container verify, trên bản sao `/tmp/w`, không vào repo. Các file cũ đặt tạm trong `.cache/` rồi xoá, nên worktree vẫn sạch.

- **R2-P1: đỏ trước, xanh sau.** Chép `router.py`, `sessions.py`, `login_guard.py`, `models/auth.py` và revision của `04a1c3a` đè lên bản sao, giữ nguyên test của nhánh. Kết quả: **6 failed, 2 passed**. Sáu test hỏng là `test_auth_refresh__C11_parallel`, `test_old_token_across_a_key_rotation_revokes_the_session`, `test_second_read_refuses_to_rotate`, `test_reuse_is_logged_without_the_token`, `test_lock_is_logged_once_without_the_email`, `test_revocation_always_carries_a_reason`. Hai test đạt là test canh `test_junk_token_with_a_previous_key_never_revokes` (đúng cả trước lẫn sau) và test pool K36. Mã của nhánh: **8/8 passed**. Khớp lời commit "6 of 6".
- **R2-P2: tầng thất bại của refresh (#2).**
  - 80 lượt **song song** cùng một cookie `<sid>.<rác>` → **401 × 20, 429 × 60**, mọi 429 có `Retry-After: 10`. Lượt 1 đo 40 lượt được 401 × 40, 429 × 0. Sau trận dội, cookie đúng của chủ phiên vẫn refresh được 200.
  - 25 lượt song song của **chủ phiên** cùng cookie T0 → **200 × 25**, đúng một `Set-Cookie`.
- **R2-P3: chuỗi HMAC qua mốc xoay khoá (#3).** Gọi thẳng `_chain_reaches` với `verification_keys = (K_mới, K_cũ)`. Chuỗi gồm `a` bước K_cũ rồi `b` bước K_mới:
  - `(0,1) (1,0) (1,1) (5,27) (31,1) (1,31) (32,0) (0,32)` → `True`;
  - `(16,17) (1,32) (32,1) (0,33)` → `False`.
  - Biên `a + b ≤ 32` đúng tới từng bước. Hai trường hợp đã ghi là không dò (R-05) cho đúng `False`: hai lần xoay khoá, và thứ tự khoá ngược.
  - Chi phí mỗi token rác: **0,074 ms** khi chỉ có một khoá, **1,38 ms** khi có một khoá cũ, **4,42 ms** khi có ba khoá cũ (xem Nit N3).
- **R2-P4: khoá dòng `users` (Nit #7).** SQL sinh ra kết thúc bằng `FOR NO KEY UPDATE SKIP LOCKED`. Cho giao dịch A gọi `touch_last_active` rồi chưa commit; giao dịch B đặt `lock_timeout = 1s` rồi `start_session` cho cùng người dùng. Mã nhánh: `INSERT refresh_sessions` **đi qua**. Mã `04a1c3a`: INSERT **hỏng** vì hết `lock_timeout` (`DBAPIError`).
- **R2-P5: `CHECK` ghép cặp (Nit #8).** Đặt `revoked_reason` mà không đặt `revoked_at` → `IntegrityError` (chiều ngược lại đã có test của tác giả). `pg_get_constraintdef` = `CHECK (((revoked_at IS NULL) = (revoked_reason IS NULL)))`. Tên ràng buộc trong DB là `ck_refresh_sessions_ck_refresh_sessions_revoked_pair` (xem N2).
- **R2-P6: log thật qua `JsonFormatter` (#5).**
  - `{"sid": "…", "userId": "usr_…", "level": "WARNING", "logger": "apps.api.auth.sessions", "msg": "refresh_reuse_revoked", …}`
  - `{"emailKey": "a7cc…", "reason": "email_ip_locked", "logger": "apps.api.auth.login_guard", "msg": "login_throttled", …}`
  - Cả hai dòng không chứa token hay email thô.
- **R2-P7: đột biến kiểm test log (N1).** Thêm `"presented": token` vào `extra` của `refresh_reuse_revoked` (`sessions.py:458`). `test_reuse_is_logged_without_the_token` vẫn **1 passed**.
- **R2-P8: AST 8 file `.py` của delta.** 0 hàm/lớp thiếu docstring, không hàm nào dài quá 50 dòng.

## Trạng thái finding của lượt 1

| # | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | P2 | chấp nhận | `NO-056` ➖ (MNT-05), đúng dòng lượt 1 đề xuất, cùng lối với `NO-039`/`NO-047`. Vẫn tính vào điểm MNT |
| 2 | P3 | **đã sửa** | `router.py:211-233`. Cửa trước `_check_failures` chỉ đọc. Cửa sau `_denied` chạy `INCR` nguyên khối (kèm TTL, cùng `MULTI`) **sau** khi bị từ chối, rồi `> REFRESH_FAIL_LIMIT` → 429. Kiểm bằng R2-P1, R2-P2. Tác giả không làm theo đề xuất "tăng trước rồi `DECR` khi thành công", và **lý do đứng được**. Theo cách "tăng trước", một loạt 25 thẻ của chủ phiên sẽ đẩy bộ đếm lên 1..25 trước mọi lượt `DECR`, nên thẻ thứ 21 trở đi nhận 429. FE đang ghim (BE-00 §11, `7dccb44`) đăng xuất **mọi thẻ** khi gặp bất kỳ lỗi refresh nào. Chính BE-00 §11 cũng khai tầng tổng "đủ cho nhiều thẻ khôi phục cùng lúc". Cách của tác giả không bao giờ đếm lượt thành công, nên cũng khớp chữ của prompt [6] ("chỉ đếm lượt trả 401"). Lượt vượt trần vẫn được đếm dù trả 429, nhưng vô hại: TTL chỉ đặt ở lượt đầu (`NX`). Việc DB của một loạt song song vẫn do tầng tổng chặn trần (`INCR` nguyên khối, 300/phút theo `sid`), như ở lượt 1 |
| 3 | P3 | **đã sửa** | `sessions.py:381-411`. `_walk` dò chuỗi một khoá; với mỗi khoá cũ thì dò thêm chuỗi đổi khoá **một** lần. Kiểm bằng R2-P3 (12/12 biên) và R2-P1. Hai lần xoay khoá trong 32 bước không dò, đã ghi ngưỡng và đường nâng cấp đúng R-05. Xem Nit N3 về con số chi phí |
| 4 | P3 | **đã sửa** | `sessions.py:438-468`, `:516`. Lượt đọc lại gọi `_decide(may_rotate=False)`; nếu token vẫn là `current` thì `RuntimeError` thay vì lặng lẽ trả thành công. Nhánh này thật sự không với tới: dưới READ COMMITTED, `UPDATE` 0 dòng nghĩa là bản đã commit của dòng khác `current_token_hash`, hoặc đã có `revoked_at`, hoặc dòng đã bị xoá, và lệnh `SELECT` sau thấy đúng bản đó (`read_state` đọc cột, không đọc thực thể ORM, nên không vướng identity map). `test_losing_the_rotation_race…` vẫn xanh, và test mới đỏ trên `04a1c3a` |
| 5 | P3 | **đã sửa** | `sessions.py:457-458` và `login_guard.py:112-119` (mã Lua `3` = vừa khoá; lượt đập vào khoá đang có không log). Kiểm bằng R2-P6. Log không có token hay email. Test đi kèm có một chỗ yếu: N1 |
| 6 | Nit | **đã sửa** | `router.py:60-62`: docstring nằm ngay dưới `FAIL_BUCKET_HEX`. `_cookie_sid` ghi rõ `UNKNOWN_SID` chỉ là chỗ đỡ theo hợp đồng `KeyFn` (lượt 1 chấp nhận một trong hai cách này) |
| 7 | Nit | **đã sửa** | `sessions.py:353-354`, kiểm bằng R2-P4 (đỏ trước, xanh sau) |
| 8 | Nit | **đã sửa** | `models/auth.py:95-96` và revision `:88`, kiểm bằng R2-P5 và bước 6 (9/9). Sửa **thẳng** revision `r20260921_b1_01` là **hợp lệ**: BE-00 §6.1 quy định "mỗi prompt tối đa **một** revision", nên thêm revision thứ hai của B1-01 mới là trái luật. Revision chưa từng lên `main` (`git branch -a --contains 4320e0e` chỉ ra nhánh này; lịch sử `--all` của file chỉ có `4320e0e`, `b6e85b9`). DB của cổng dựng mới mỗi lượt (testcontainers), nên không môi trường chung nào có thể đã chạy bản cũ. Bảng được tạo cùng revision nên không có khoá bảng hay `NOT VALID`. Mọi lệnh ghi `revoked_at` (`sessions.py:255,276,366`) đều ghi kèm lý do |
| 9 | Nit | **đã sửa** | `test_login.py:319` nâng `HASH_WAIT_S` lên 30 s trong test. `passwords.py:86` đọc biến module lúc gọi nên bản vá có tác dụng. Vi phạm K36 vẫn đỏ ở `wait_until(idle.check, 1,5 s)` và không treo, vì thoát `AsyncExitStack` là trả hết chỗ băm |
| 10 | Nit | chấp nhận | Không đổi. Lượt 1 đã coi là chấp nhận được, và `NO-056` ghi lại quyết định đó |
| 11 | Nit | **đã sửa** | `models/auth.py:32-36`: `RevokeReason` là `Literal`, `REVOKE_REASONS = get_args(RevokeReason)`. `sessions.py:56` nhập từ model. `grep` cả repo không còn nguồn thứ hai |
| 12 | Nit | **đã sửa** | `docs/fixes.md:38-40` ghi `1e2d146`, `971a1a1`, `9f80576`. Tự kiểm: ba sha này đúng là commit mang `Fix: FIX-029/030/031` + `Prompt: B0-06` |

## Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | P3 | TEST-02 · R-30 | Hai test "log không lộ bí mật" không thể đỏ. `caplog.text` dựng bằng định dạng mặc định của pytest (`%(levelname)s %(name)s:… %(message)s`; `pyproject.toml` không đặt `log_format`), nên **không chứa `extra=`**. Mà `extra=` chính là chỗ một lần sửa sau dễ làm lộ token nhất. R2-P7: thêm `"presented": token` vào `extra` thì `test_reuse_is_logged_without_the_token` vẫn đạt. Mã sản phẩm hôm nay đúng (R2-P6); chỉ phép kiểm "không mang token" trong docstring test là rỗng. `test_login.py:449` cùng lối, nhưng ít rủi ro hơn vì `admit` không nhận email thô | `apps/api/auth/tests/test_refresh.py:521`; `apps/api/auth/tests/test_login.py:449` | Khẳng định trên đúng thứ ra log: `line = JsonFormatter().format(records[0])`; `assert token not in line` (với test đăng nhập là `user.email not in line`), hoặc duyệt `records[0].__dict__.values()` |
| N2 | P3 | MNT-04 · DB-05 | **Tên `CHECK` trong DB bị lặp tiền tố, lệch với model.** Revision truyền `name=f"ck_{SESSIONS}_revoked_pair"`, nhưng `op.create_table` lại áp quy ước `"ck": "ck_%(table_name)s_%(constraint_name)s"` (`packages/db/base.py:17`) lên tên đã đủ tiền tố. R2-P5 và `pg_constraint` cho thấy DB có `ck_refresh_sessions_ck_refresh_sessions_revoked_pair`, `ck_users_ck_users_role`, … (**cả 7** `CHECK` của revision), trong khi model sinh `ck_refresh_sessions_revoked_pair`, `ck_users_role`. `migrate_check` không bắt được vì so model với DB không so `CHECK`. Tác động: mọi SQL hay revision contract gọi theo tên của model (ví dụ đổi `CHECK` lý do thu hồi khi thêm một lý do, đúng việc Nit #11 nhắm tới) sẽ không tìm thấy ràng buộc; thông điệp `IntegrityError` mang tên lạ. Không sai dữ liệu. Mẫu này có từ trước, trên `main`: revision B0-06 cũng sinh `ck_idempotency_records_ck_idempotency_records_{state,key_format}`. Lượt 1 bỏ sót. Chưa nâng mức vì không có đường runtime nào đọc tên `CHECK` (`unique_violation` chỉ đọc tên `uq_`) | `packages/db/migrations/versions/r20260921_b1_01_auth.py:55-59`, `:83-88` | Revision **chưa hợp nhất**, nên sửa tại chỗ là rẻ nhất, cùng đường với Nit #8: `name=op.f("ck_users_role")` (hoặc chỉ `name="role"`) cho cả 7 `CHECK`. Sau khi lên `main`, đổi tên cần `RENAME CONSTRAINT`, mà lint expand cấm, nên phải thành một revision contract. Không sửa trong nhánh thì ghi `DEBT.md`. Phần của B0-06 và việc thêm kiểm tên `CHECK` vào `migrate_check` (chủ B0-03) ghi một dòng `DEBT.md` riêng |
| N3 | Nit | R-05 · MNT-04 | Docstring `_chain_reaches` ghi "≈ `lookback²/2` HMAC mỗi khoá cũ, **dưới 1 ms**". R2-P3 đo được **1,38 ms** mỗi token rác với một khoá cũ, **4,42 ms** với ba khoá cũ, tăng tuyến tính theo số phần tử `SECRET_KEY_PREVIOUS`. Việc này chạy đồng bộ trên vòng sự kiện, chỉ ở đường token lạ và chỉ trong cửa sổ còn khoá cũ. Tầng tổng chặn trần 300 lượt/phút theo `sid`, nên không thành đòn khuếch đại đáng kể | `apps/api/auth/sessions.py:396` | Sửa con số ("≈ 1,4 ms mỗi khoá cũ, tuyến tính theo số khoá cũ") để ngưỡng R-05 đúng thực đo |

**Lượt 2: P0: 0 · P1: 0 · P2: 0 mới (P2 #1 của lượt 1 chấp nhận ở `NO-056`) · P3: 2 mới · Nit: 1 mới**

## Những chỗ đã soi kỹ và **đạt**

- **Tầng thất bại của refresh.**
  - Chạy tuần tự: 20 lượt đầu 401, lượt 21 bị cửa trước chặn 429 (`test_auth_refresh__C11` vẫn xanh).
  - Chạy song song: đúng 20 lượt 401 nhờ `INCR` nguyên khối, không phụ thuộc thứ tự lượt.
  - Redis cache hỏng: `soft_redis` trả `None` → vẫn 401 (fail-open đúng BE-00 §11).
  - Từ chối vẫn được **trả** chứ không ném, kể cả khi đổi thành 429, nên lệnh thu hồi `reuse` của lượt đó vẫn commit.
  - `bump` đọc TTL trong cùng `MULTI`, không tốn thêm vòng mạng; `record_failure` bỏ qua giá trị trả. Đường đăng nhập vẫn cùng số lệnh Redis cho email lạ và email có thật (C27 xanh).
- **Lý do khoá đăng nhập.** Mã Lua `3` chỉ tách "vừa đặt khoá" khỏi "đang khoá" để log một lần; hành vi 429 không đổi (probe P4 của lượt 1 vẫn đúng: khoá nằm trọn trong Lua).
- **Chuỗi đổi khoá.** Đúng giả thiết "xoay luôn ký bằng `current_key`" (`_rotate`, `sessions.py:474`). Nhánh ân hạn `_successor` vẫn thử từng khoá. Token rác khi có khoá cũ vẫn không ghi DB (test canh mới, R2-P1).
- **Bất biến lượt đọc lại.** Như ở dòng #4. `cast` ở `:516` có comment, và `RuntimeError` ở `:467` giữ bất biến lúc chạy.
- **Nguồn lý do thu hồi và hạn mức.** Một nguồn duy nhất. `LOCK_REASONS` chỉ có hai mã mà Lua trả cho nhánh log (`2`, `3`); mã `1` bị lọc trước.

## Kiểm sổ nợ

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Điều kiện 1 của lượt 1 (`NO-056` ➖ trước khi merge) | đạt. Dòng đủ cột, đúng lối `NO-039`/`NO-047`, và trích file phán quyết lượt 1 |
| P3 #2–#5 của lượt 1 | đã sửa trên nhánh, nên không cần dòng `⬜` |
| Id | `NO-053..056` không trùng nhánh nào. `main` dừng ở `NO-052`, `feature/b5-01-ml-contracts-fakes-loader` dùng `NO-060..063`, các nhánh `fix/*` không dùng id ≥ 053 |
| Nợ P0/P1 còn `⬜`/`🔧` | không |
| Nợ do lượt này chỉ ra | **chưa có dòng**. Xem dưới |

Dòng đề xuất nếu tác giả không sửa trong nhánh. Id kế tiếp còn trống là `NO-057`, `NO-058`; người điều phối kiểm lại vì `feature/b5-01` đã giữ `NO-060..063`. Phiên này **không** tự ghi vào `DEBT.md`.

- `| ⬜ | NO-057 | 2026-09-21 | — | Hai test "log không lộ token/email" (apps/api/auth/tests/test_refresh.py:521, test_login.py:449) kiểm caplog.text, không chứa extra= — thêm token vào extra vẫn xanh | caplog.text dùng định dạng mặc định của pytest, không in extra | B1-01 | P3 | Khẳng định trên JsonFormatter().format(record). Review merge lượt 2 finding N1 |`
- `| ⬜ | NO-058 | 2026-09-21 | — | Tên CHECK trong DB lặp tiền tố (ck_users_ck_users_role, ck_idempotency_records_ck_idempotency_records_state, …) lệch tên model | Revision truyền tên đủ tiền tố, op.create_table áp lại quy ước "ck" của packages/db/base.py; migrate_check không so CHECK | B0-03 (quy ước, migrate_check) · B0-06, B1-01 (revision) | P3 | Revision chưa hợp nhất: op.f(...); đã hợp nhất: revision contract. Review merge lượt 2 finding N2 |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (#2 đã sửa) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 (Nit #7 đã sửa) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (#3, #4 đã sửa) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (chỉ Nit N3) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 (P3 N2) | 0,40 |
| TEST – Kiểm thử | 7 % | 4 (P3 N1) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 (#5 đã sửa) | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #1 chấp nhận ở `NO-056`) | 0,09 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,40 + 0,28 + 0,25 + 0,09 = **4,77 / 5**

## PHÁN QUYẾT (lượt 2): APPROVE

Lý do:

- Cổng thoát 0 ngay lượt đầu trên `b877f46`, độ phủ đạt ở mọi gói bị chạm (`apps/api/auth` 98,61 % / 92,65 %), không có P0/P1, điểm 4,77 ≥ 4,0.
- Bốn P3 và năm Nit của lượt 1 đã sửa. Mỗi bản sửa đều có test **đỏ trên `04a1c3a`, xanh ở đầu nhánh** (6/6, tự tái hiện ở R2-P1) và probe chạy thật:
  - 80 lượt rác song song ra đúng 20 × 401;
  - 25 thẻ của chủ phiên song song đều 200;
  - chuỗi đổi khoá đúng biên `a + b ≤ 32`;
  - `INSERT` phiên mới không còn chờ khoá `last_active_at`;
  - `CHECK` ghép cặp chặn cả hai chiều.
- Hai điểm tác giả làm khác đề xuất của lượt 1 đều đứng được. Tầng thất bại tăng **sau** khi bị từ chối, vì cách "tăng trước" sẽ trả 429 cho chính các thẻ của chủ phiên, và FE đang ghim sẽ đăng xuất mọi thẻ. Revision được sửa thẳng, vì BE-00 §6.1 chỉ cho mỗi prompt **một** revision, và revision này chưa từng rời nhánh.
- Hai P3 mới (N1 test log rỗng, N2 tên `CHECK` lặp tiền tố, có từ trước trên `main`) không chặn merge.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38), chọn một trong hai:
   - tác giả sửa N1 và N2 trên nhánh (N2 bằng `op.f(...)` ngay trong revision chưa hợp nhất, cùng đường với Nit #8), chạy lại cổng, rồi xin lượt review ngắn cho delta;
   - hoặc ghi hai dòng `NO-057`, `NO-058` như trên. Đây là nhật ký quản trị, được commit thẳng lên `main` theo ngoại lệ R-36.

   Nit N3 do tác giả tự quyết.
2. Gộp bằng `git merge --no-ff`, **không** squash và **không** rebase. Lý do: R-36 vì nhánh mang trailer của B1-01 **và** B0-06 + `Fix: FIX-029/030/031`; và các sha `1e2d146`, `971a1a1`, `9f80576` đã ghi ở `docs/fixes.md` phải còn đúng sau khi gộp. `merge-tree` với `main` sạch.
3. Như lượt 1: người điều phối ghi nhận ngoại lệ K27 của FIX-029..031 (đã cấp phép trong phiên tác giả).
