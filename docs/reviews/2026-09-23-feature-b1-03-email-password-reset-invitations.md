# Review merge feature/b1-03-email-password-reset-invitations → main

- Ngày: 2026-09-23 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `09dc9d05c22e`
- Loại task (RULE.md §6): **Auth, phân quyền, PII** — SEC/LOG/API/OBS/TEST bắt buộc, nâng mức theo §1.
- Phạm vi: `git diff main...HEAD` — 28 file, +3715 dòng (`packages/mail/**`, `apps/api/auth_recovery/**`,
  `packages/db/models/auth_recovery.py`, `r20260923_b1_03_one_time_tokens.py`,
  `packages/messaging/payloads/auth_recovery.py`, `packages/testing/fixtures/mail.py`, `changes/B1-03.md`).
  Chỉ chấm commit cuối + diff tổng (nhánh sẽ squash).
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ trong worktree review, **mã thoát 0**.
- Cây làm việc sạch; commit cuối đúng mẫu (`feat(auth-recovery): …`, 62 ký tự, trailer `Prompt: B1-03`);
  không đụng file cấm (`docs/charter/*`, `openapi.json`, `uv.lock`, `tools/contract/APPFRONT_SHA`, `.importlinter`);
  không `pragma: no cover`, không `skip`/`xfail` mới, mọi `# noqa`/`# type: ignore` đều có mã + lý do;
  `changes/B1-03.md` có mặt.

## Bảng cổng (E.10 — mã thoát thật, tự chạy)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (6 revision, đúng 1 head, downgrade/upgrade lại đạt) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt (H4/H5 *không áp dụng* — B3-05/B4-01 chưa hợp nhất) |
| 8 | `openapi` | đạt |

- Test: **2941 qua · 0 hỏng · 7 bỏ qua · 4 deselect** (453 s).
- Độ phủ: tổng **99,08% dòng · 97,69% nhánh**; tập file bị chạm 97,96% / 97,22%;
  `apps/api/auth_recovery` **97,20 / 96,00**; `packages/mail` **100,00 / 100,00**;
  `packages/db` 94,97 / 95,45; `packages/messaging` 100 / 100; `packages/testing` 99,03 / 99,22.
  Mọi gói bị chạm ≥ 90% dòng **và** nhánh.
- `case_gate`: `auth_request_password_reset` C01 C02 C03 C11 C16 C24 **C27 C28** đạt;
  `auth_confirm_password_reset` và `auth_accept_invitation` C01 C02 C03 C11 C16 C24 **C26** đạt.
  J-case kiểm bằng tên test: `send_token_mail` J01/J02/J03/J06, `resend_unsent` J01/J06, `purge_tokens` J01/J06 — đủ.

> Số của tác giả (8 bước đạt, 2941/0/7, 97,20/96,00 và 100/100) **khớp** với lượt chạy độc lập này.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-01 / lệch prompt [6] | Một người nhận hỏng giết cả lô thư, **lặp lại mãi**. Vòng gửi ném `PermanentError` ngay ở token đầu tiên hỏng, nên các token **sau** nó trong lô không bao giờ được gửi và cũng không được đánh dấu. `run_resend_unsent` chọn lại đúng tập đó (`ORDER BY created_at LIMIT 500`) rồi chia lô 50 y hệt, nên 5 phút sau lô ấy lại chết ở đúng token đó — tới khi token hỏng hết hạn (**7 ngày** với `invite`). Prompt [6] ghi rõ `PermanentError("TOKEN_KEY_ROTATED")` là **"cho token đó"**, không phải cho cả lô. Hệ quả: thư mời của người dùng A không bao giờ tới vì địa chỉ của người dùng B bị SMTP từ chối hẳn; và địa chỉ hỏng ấy bị gửi lại 12 lần/giờ suốt 7 ngày (rủi ro bị chặn tên miền gửi). Lệch này **không** nằm trong danh sách "Lệch khỏi prompt" của tác giả. | `apps/api/auth_recovery/jobs.py:100-116` (vòng `for row in rows`, `raise` trong vòng); `apps/api/auth_recovery/jobs.py:138-146` (chọn + chia lô ổn định) | Cô lập theo token: bắt `MailRejectedError`/khoá-không-khớp **trong** vòng, đánh dấu riêng token hỏng để nó rời tập quét bù (một cột hỏng, hoặc `superseded_at=now`), `continue`, rồi ném **một** `PermanentError` gom mã sau khi hết vòng. Thêm test lô `[token hỏng, token tốt]` → token tốt vẫn tới. |
| 2 | **P2** | SEC-01 (C27) | Cân bằng chống dò của N8 **chưa từng được đo ở nhánh đáng đo**. Test `__C27` gọi một lượt "làm ấm" cho email thật *trước* vòng đo; lượt đó cấp token, nên mọi vòng đo sau đều rơi vào nhánh **cooldown noop** — tức test so PING với PING, không bao giờ chạm nhánh `issue`. Nhánh `issue` mới là nhánh khác biệt: nó chạy thêm 1 `UPDATE` + 1 `INSERT` và `send_task` thật (LPUSH qua kết nối pool của Celery), trong khi nhánh không cấp chỉ PING. Prompt [6] N8 đòi "hai nhánh cùng số truy vấn" — điều kiện này chỉ đúng cho hai lượt *đọc*, không đúng cho lượt ghi. | `apps/api/auth_recovery/tests/test_router_request_reset.py:117-140`; `apps/api/auth_recovery/router.py:216-226` | Đo đúng cặp cần đo: mỗi vòng dựng một người **mới** (hoặc đẩy `fake_clock` qua cooldown) để lượt đo rơi vào nhánh `issue`, so với email lạ. Nếu khoảng lệch không kéo dưới ngưỡng được thì ghi số đo vào `DEBT.md` và nêu rõ phần dư chấp nhận, thay vì để một test không thể đỏ. |
| 3 | **P2** | PERF-01 / RES-01 | `_ping_broker` mở **một client Redis mới mỗi request**: `broker_redis_sync()` là `redis.Redis.from_url(...)` dựng pool mới mỗi lời gọi (`packages/messaging/redis.py:123-129`), ping xong đóng ngay. Đường này chạy cho **mọi** request N8 không cấp token — đúng phần lưu lượng mà kẻ dò sinh ra — nên mỗi lượt dò là một vòng TCP connect/close tới `redis-broker`, chỉ có hạn mức 10/900 s theo IP chắn. Nó cũng làm hỏng chính mục đích cân thời gian: connect mới + PING không tương đương LPUSH qua kết nối pool. | `apps/api/auth_recovery/router.py:207-213` | Dùng một client dùng chung cả tiến trình (bọc `@cache` quanh client broker, hoặc mượn đúng kết nối mà `send_task` dùng) thay vì dựng/huỷ mỗi lượt. |
| 4 | **P2** | TEST-01 | Không có test nào cho đường hỏng-giữa-lô của finding 1: `test_send_token_mail__J06` chỉ có token bị **truy vấn lọc bỏ** (đã gửi / đã bị thay), không có token **gửi hỏng** đứng trước một token tốt. Đây là lý do finding 1 lọt qua 8 bước cổng xanh. | `apps/api/auth_recovery/tests/test_jobs.py:130-153` | Đi kèm bản vá của finding 1. |
| 5 | P3 | R-07 | `_seed_token` bị chép–dán gần nguyên văn giữa hai file test (khác nhau vài tham số và `flush` vs `commit`); `test_router_*.py` còn có thêm `_seed_reset_token`/`_seed_invite_token` cùng khuôn. CLAUDE.md quy định factory dữ liệu test nằm ở `packages/testing/factories/<module>.py`; B1-04/B1-05 sẽ cần đúng helper này. | `apps/api/auth_recovery/tests/test_tokens.py:50-75` và `apps/api/auth_recovery/tests/test_jobs.py:71-102` | Gộp vào `packages/testing/factories/auth_recovery.py`. |
| 6 | P3 | R-01 | Thiếu docstring ở một số hàm mã sản phẩm: `_b64url`, `_ttl_for` (hàm này mang luật nghiệp vụ — TTL nào theo `purpose`), `MemoryMailer.send`, `Mailer.send`, bốn `__init__`, `_check_token_id`, và `_http_get`/`_http_delete`/`run`/`_serve` của fixture. | `apps/api/auth_recovery/tokens.py:51,65`; `packages/mail/sender.py:25,31,39,69,102,106`; `packages/messaging/payloads/auth_recovery.py:18`; `packages/testing/fixtures/mail.py:58,63,143,153` | Thêm một câu mỗi hàm. (Hàm test thiếu docstring thì ngang với `apps/api/auth` đã hợp nhất — Nit, không tính.) |
| 7 | Nit | R-08 | `run_send_token_mail` dài 59 dòng kể cả docstring 8 dòng (thân ~45). Bản vá của finding 1 nên tách sẵn phần gửi-một-token ra hàm riêng. | `apps/api/auth_recovery/jobs.py:70-125` | — |
| 8 | Nit | LOG | `_reset_eligible` suy lúc phát token bằng `expires_at - ttl`; đổi `PASSWORD_RESET_TTL_MIN` sẽ dịch cooldown của những token **đã** phát (dài ra hoặc ngắn đi). Cách làm vẫn đúng hơn `created_at` (`func.now()` phía DB, không theo `Clock` tiêm được) — chỉ cần một câu trong docstring nói rõ cạm bẫy này. | `apps/api/auth_recovery/router.py:171-181` | — |
| 9 | Nit | MNT | `memory_mailer: Any` ở nhiều test thay vì `MemoryMailer` — mất kiểm kiểu ở chỗ `mypy --strict` lẽ ra bắt được. | `apps/api/auth_recovery/tests/test_jobs.py` | — |

### Các điểm "Lệch khỏi prompt" tác giả tự khai — phán quyết từng điểm

| Điểm khai | Phán quyết |
|---|---|
| `issue_token` dùng `INSERT … ON CONFLICT DO NOTHING` + làm lại một lần thay savepoint | **Chấp nhận.** Lý do đứng được và đã ghi `NO-140` (`packages/db/hooks.py` bắn `after_commit` khi savepoint đóng). Bất biến prompt đòi ("vô hiệu cũ rồi chèn mới trong một giao dịch, vi phạm partial unique → làm lại **một** lần") được giữ nguyên; `index_where` nhắm đúng `ACTIVE_UNIQUE`; có test đua thật (`test_issue_token_concurrent_same_user_keeps_one_active`). |
| Cooldown C28 tính từ `expires_at - ttl` thay `created_at` | **Chấp nhận** — xem Nit 8. |
| J02/J03 gọi thẳng lõi `run_send_token_mail` | **Chấp nhận.** Đường task mỏng vẫn được phủ bằng một test đồng bộ chạy `.apply()` thật (`test_send_token_mail_task_wiring_smoke`), nên không có dòng nào chỉ "phủ trên giấy". |
| `packages/mail` đọc `SMTP_HOST`… còn `base.yml` chỉ truyền `SMTP_URL` | **Chấp nhận có điều kiện.** Tên biến khớp đúng bảng prompt [2] và `deploy/**` ngoài sở hữu B1-03; nợ đã ghi `NO-141` (P2, chủ B0-08). Nhưng cho tới khi `NO-141` đóng thì **tính năng không chạy được trên stack compose** (nạp `MailSettings` hỏng vì thiếu `SMTP_HOST`/`MAIL_FROM`) — người điều phối nên xếp FIX cho B0-08 ngay sau lần gộp này, không để trôi. |
| Tự khai thêm: C27 — mọi nhánh không cấp token đều PING | **Chấp nhận, và là cải thiện** so với prompt (prompt chỉ đòi nhánh "không có người"). Có test cho cả `pending`/`disabled` và cả nhánh cooldown. |
| Tự khai thêm: `mailpit_inbox` `clear()` lúc teardown; e2e dùng `SystemClock()` | **Chấp nhận.** Fixture dọn cả hai đầu; bộ test chạy tuần tự (không `-n`), nên không giẫm chân `tools/tests/test_services.py`. Lý do `SystemClock()` đúng: worker thật dùng `SystemClock()`, token phát bằng đồng hồ giả 2026-01-01 sẽ bị `active_clause` của worker coi là hết hạn. |

### Những chỗ đã kiểm và **đạt** (không thành finding)

- **K11** — token bản rõ chỉ sống trong khung `_new_token_row`/`build_token_mail`; payload Celery chỉ mang `token_ids` (`SendTokenMailPayload`, 1–50, `is_id("tok", …)`); `subject` là hằng tĩnh theo `purpose`; `on_failed` chỉ log `token_ids` + mã (có test đọc `caplog`); `purge` chỉ log `removed`.
- **K17/J09** — `send_task` đi qua `on_after_commit`; rollback bỏ callback (`test_issue_token_rollback_leaves_broker_empty`); đúng **một** callback mỗi giao dịch, khoá lô theo `get_transaction()` nên giao dịch kế tiếp trên cùng session không lẫn danh sách; không `begin_nested` ở đâu cả.
- **K18/J06** — `sent_at IS NULL` nằm ngay trong câu truy vấn của lô; `UPDATE … WHERE sent_at IS NULL` khi ghi; giao lại lô không gửi trùng (test); `purge` có `PURGE_BATCH` 1000 và trần `PURGE_MAX_BATCHES` 100; `resend` có `RESEND_SELECT_LIMIT` 500.
- **N8/C27** — `SET LOCAL synchronous_commit = off` chạy **trước** mọi rẽ nhánh nên đúng ở mọi nhánh; hai lượt đọc cùng dạng (`_NOBODY_ID` giữ đúng hình truy vấn); chỉ hạn mức `recovery_ip` theo IP, **không** có hạn mức theo email; luôn 204 thân rỗng. (Phần dư xem finding 2/3.)
- **N9/N10** — `await db.rollback()` đứng trước `hash_password` ở cả hai route (K36), và `token.id`/`token.user_id` được đọc **trước** rollback; thứ tự `users` → `one_time_tokens` → `refresh_sessions`; `consume_token` là `UPDATE … RETURNING` nguyên tử; mọi đường hỏng 422 mã riêng, không 401 (K30); N9 `revoke_sessions` + `revoke_tokens` + `clear_auth_cookies`; N10 `pending → active`, đặt hai cookie, trả `None` (không trả `Response`, giữ `Set-Cookie`), người thực hiện lấy từ token chứ không từ thân.
  Hai test đua thật đáng ghi nhận: `__concurrent_same_token_one_wins` (204/422) và `__disabled_mid_hash_*` (chặn ở điểm băm, đổi `status` bằng session khác, rồi kiểm người dùng **không** đổi trạng thái — chứng minh `UPDATE users` đã được rollback).
  Về thu hồi: `revoke_sessions` đủ để giết cả access token vì `check_session` đọc ảnh chụp có cờ `revoked` và `_drop_cached_after_commit` xoá cache — không cần `bump_token_version`.
- **Token** — công thức khớp prompt từng ký tự (`base64url(HMAC-SHA256(key, f"{id}|{purpose}|" + nonce))`, 43 ký tự); DB chỉ giữ `sha256` hex + `nonce`; tra bằng khoá chỉ mục trên `token_hash` (không so chuỗi bí mật trong mã Python); xoay khoá qua `verification_keys` có test cả hai chiều (khoá cũ còn nhận, khoá lạ → `TOKEN_KEY_ROTATED`).
- **`packages/mail`** — CR/LF ở `to`/`subject` → `ValueError` (có test cả hai trường); `timeout=smtp_timeout_s` tường minh; STARTTLS dùng `ssl.create_default_context()`; ánh xạ 4xx/5xx gom vào một hàm `_map_smtp_error` có 10 test; `memory` chỉ hợp lệ khi `APP_ENV=test` (fail-closed, có test ở `dev`); chỉ stdlib (`smtplib`/`ssl`/`email`/`threading`), không thêm dòng nào vào `uv.lock`; `smtp_reject_server` chỉ xuất hiện ở J03 và 3 test của chính `packages/mail`.
- **Link/thư** — gốc link luôn từ `PUBLIC_BASE_URL`, không từ header; token nằm trong **fragment** (`#token=`) nên không vào access log của proxy; tên người nhận vào html qua `html.escape`, có test khẳng định nó **không** vào `subject`.
- **Revision** — đúng một revision, `down_revision = r20260922_b1_02` = head của `main`; `migrate_check` chạy đủ downgrade −1 / base / upgrade lại / model khớp DB / tên CHECK khớp model; partial unique `(user_id, purpose) WHERE used_at IS NULL AND superseded_at IS NULL` và index `(sent_at, created_at) WHERE sent_at IS NULL` đúng khối [5].
- **Ranh giới** — `lint-imports` đạt; `jobs.py`/`tokens.py` không nhập `fastapi`/`jwt`/`argon2` và có test tiến trình con khẳng định điều đó (`test_jobs_import_without_web_or_crypto_packages`); không file nào của prompt khác bị sửa; `packages.testing` chỉ được nhập từ test.
- **Sổ nợ** — hai nợ tác giả nêu đều có dòng trong `DEBT.md` (`NO-140`, `NO-141`), cả hai P2 **mở**, không có nợ P0/P1 mở nào của nhánh này (R-34, R-35, R-38 thoả).

## Điểm

| Miền | Trọng số | Điểm | Tích | Vì sao |
|---|---|---|---|---|
| SEC – Bảo mật | 25% | 3 | 0,75 | finding 2 (P2) |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 | không finding — đua token, đua consume, đua disabled-giữa-băm đều có test thật |
| LOG – Tính đúng đắn | 15% | 1 | 0,15 | finding 1 (P1) |
| PERF – Hiệu năng | 10% | 3 | 0,30 | finding 3 (P2) |
| RES – Chịu lỗi | 10% | 5 | 0,50 | timeout tường minh, quét bù có trần, `TransientError` lùi đúng |
| DB, API – Migration & contract | 10% | 5 | 0,50 | không finding — bước 6 và 7 xanh, một head |
| TEST – Kiểm thử | 7% | 3 | 0,21 | finding 4 (P2) |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 | log có cấu trúc, không lộ bí mật |
| MNT – Bảo trì | 3% | 4 | 0,12 | chỉ P3 (finding 5, 6) |
| **Tổng** | **100%** | | **3,53 / 5** | |

## PHÁN QUYẾT: 🔶 REQUEST CHANGES (3,53/5)

Nhánh này làm tốt gần như mọi thứ khó của một prompt auth: chống dò có test **đo thời gian thật**,
ba test đua chạy trên Postgres thật, e2e đi qua Mailpit thật và worker Celery thật, token không bao giờ
rời khung hàm đã sinh ra nó, ranh giới worker được khẳng định bằng một tiến trình con. Tám bước cổng
xanh và mọi con số tác giả báo đều đúng khi chạy lại độc lập.

Chặn merge vì **một P1**: đường gửi thư không cô lập lỗi theo từng token, nên một người nhận bị SMTP
từ chối hẳn (hoặc một token phát bằng khoá đã rơi khỏi `SECRET_KEY_PREVIOUS`) làm chết cả lô, và lượt
quét bù mỗi 5 phút dựng lại đúng lô ấy để nó chết lại ở đúng chỗ cũ — tới khi token hỏng hết hạn, tức
tới **7 ngày** với thư mời. Đây là lệch khỏi câu chữ của prompt [6] ("`PermanentError` … **cho token
đó**") và tác giả không khai nó là lệch. Tám bước cổng không bắt được vì không có test nào đặt một
token hỏng đứng trước một token tốt trong cùng một lô.

**Phải sửa để được duyệt:**

1. **(finding 1 + 4, P1)** Cô lập lỗi gửi theo từng token trong `run_send_token_mail`: bắt
   `MailRejectedError` và trường hợp khoá không khớp **bên trong** vòng, đánh dấu riêng token hỏng để
   nó rời tập của `run_resend_unsent`, `continue` với các token còn lại, rồi ném một `PermanentError`
   gom mã **sau** khi hết vòng. Kèm test lô `[token hỏng, token tốt]` khẳng định token tốt vẫn tới.
2. **(finding 2, P2)** Sửa `test_auth_request_password_reset__C27` để vòng đo thật sự rơi vào nhánh
   `issue` (người mới mỗi vòng, hoặc đẩy `fake_clock` qua cooldown), rồi so với email lạ. Nếu khoảng
   lệch không kéo xuống dưới ngưỡng được thì ghi số đo và phần dư chấp nhận vào `DEBT.md`.
3. **(finding 3, P2)** `_ping_broker` dùng client Redis dùng chung cả tiến trình thay vì dựng và huỷ
   một pool mỗi request.

Finding 5–9 (P3/Nit) không chặn merge; nếu không sửa trong vòng này thì ghi một dòng `DEBT.md` cho
finding 5 và 6. Người điều phối cần xếp FIX cho **B0-08** về `NO-141` ngay sau lần gộp: cho tới khi
`deploy/compose/*.yml` truyền tám biến `MAIL_*`/`SMTP_*`, tính năng này không chạy được ngoài môi
trường test.
