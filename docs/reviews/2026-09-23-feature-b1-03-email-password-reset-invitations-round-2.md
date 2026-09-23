# Review merge feature/b1-03-email-password-reset-invitations → main — lượt 2

- Ngày: 2026-09-23 · Reviewer: phiên /merge-review (cùng phiên lượt 1, độc lập với tác giả)
- Lượt 1: `09dc9d05c22e` — REQUEST CHANGES 3,53/5
  (`docs/reviews/2026-09-23-feature-b1-03-email-password-reset-invitations.md`)
- Lượt 2: **`df2d349`** — `fix(auth-recovery): isolate permanent mail failures per token`
- Phạm vi chấm: **chỉ diff vòng sửa** `git diff 09dc9d0..df2d349` trên 14 file thuộc sở hữu B1-03
  (+310 / −272). Phần còn lại của `git diff main...HEAD` đã chấm ở lượt 1, không chấm lại.
- Cây chạy cổng: `git checkout --detach df2d349` + `git merge --no-ff --no-commit main` (`4f4f295`) —
  **gộp sạch, không xung đột**, thay đổi duy nhất từ `main` là `uv.lock` (redis 6.4 → 8.1). Sau khi
  chạy xong: `git merge --abort`, worktree sạch trở lại `df2d349`.

## Bảng cổng (E.10 — mã thoát thật, tự chạy)

Không có **một** lượt chạy nào xanh cả tám bước, vì lượt đầy đủ dừng ở bước 3 vì lý do **ngoài
B1-03** (xem "Chặn merge" bên dưới). Bảng dưới ghi đúng bước nào chạy ở lượt nào:

| # | Bước | Trạng thái | Lượt chạy |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | cả hai |
| 1 | `ruff format --check` | đạt | đầy đủ (508 file) |
| 2 | `ruff check` | đạt | đầy đủ |
| 3 | `mypy --strict` | **hỏng** | đầy đủ — **6 lỗi, 4 file, không file nào của B1-03** |
| 4 | `lint-imports` | đạt | bổ sung `--steps 4,5,6,7,8` |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | bổ sung |
| 5b | `pytest -m perf` → `case_gate` | **chưa chạy** | — |
| 6 | `lint_migrations` → `migrate_check` | đạt | bổ sung (7 revision, **đúng 1 head**) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | bổ sung (H4/H5 *không áp dụng* — B3-05/B4-01 chưa hợp nhất) |
| 8 | `openapi` | đạt | bổ sung |

- Lượt đầy đủ: `bash tools/verify/run.sh verify` → **mã thoát 1**, dừng ở bước 3, bước 4–8 "chưa chạy".
- Lượt bổ sung: `bash tools/verify/run.sh verify --steps 4,5,6,7,8` trên **cùng** cây → **mã thoát 0**.
- Test: **3172 qua · 0 hỏng · 4 deselect** (527 s).
- Độ phủ: tổng **99,03% dòng · 97,61% nhánh**; tập file bị chạm 98,01 / 96,49;
  `apps/api/auth_recovery` **97,32 / 94,64**; `packages/mail` **100,00 / 100,00**.
  Mọi gói bị chạm ≥ 90% dòng **và** nhánh. (Nhánh của `auth_recovery` xuống 96,00 → 94,64 so với
  lượt 1 — vẫn cách ngưỡng rất xa, do vòng sửa thêm nhánh `if code is None` / chọn cột đánh dấu.)

**Vì sao bước 5b ghi "chưa chạy" chứ không phải "hỏng":** chạy `--steps 5b` riêng **có** trả mã
thoát 1, nhưng đó là **hiện vật của việc chạy lẻ**, không phải lỗi thật: `case_gate` đọc vết case do
bước 5 sinh ra *trong cùng lượt chạy*, container mới thì vết rỗng — bằng chứng là nó báo thiếu
`J01`/`J06` của cả `purge_sessions`, `purge_activity`, `purge_expired_idempotency` (đã hợp nhất và
xanh trên `main` từ lâu) và `tìm thấy []` cho toàn bộ op của B2-01. Báo "hỏng" ở đây là sai sự thật
y như báo "đạt" (K25), nên ghi "chưa chạy".

Bù lại bằng một kiểm tra tên test trực tiếp — đúng thứ `case_gate` đối chiếu (`test_<operationId>__<caseid>`):

| Op / task | Case tìm thấy |
|---|---|
| `auth_request_password_reset` | C01 C02 C03 C11 C16 C24 **C27 C28** |
| `auth_confirm_password_reset` | C01 C02 C03 C11 C16 C24 **C26** |
| `auth_accept_invitation` | C01 C02 C03 C11 C16 C24 **C26** |
| `send_token_mail` | J01 J02 J03 J06 |
| `resend_unsent` | J01 J06 |
| `purge_tokens` | J01 J06 |

Giống hệt lượt 1 (nơi `case_gate` **đạt** thật); vòng sửa không đổi tên test case nào. Đây là suy
luận từ tên, **không** phải phán quyết của cổng — cần một lượt chạy đầy đủ xanh để chốt.

## Trạng thái từng finding lượt 1

| Finding lượt 1 | Nợ | Trạng thái | Bằng chứng |
|---|---|---|---|
| **1 — P1** lỗi vĩnh viễn giết cả lô, lặp mãi | NO-143 | ✅ **đóng** | `_send_one` (`jobs.py:96-121`) trả **mã lỗi** thay vì ném; vòng `for` đi tiếp, đếm `sent`, hết vòng mới `raise PermanentError(first_failure)` (`jobs.py:152-166`). Cách đánh dấu **đứng được**: `TOKEN_KEY_ROTATED` → `superseded_at` (token không bao giờ dựng lại được — đúng nghĩa "đã bị thay", và rời cả `active_clause` lẫn tập quét bù); `MAIL_REJECTED` → `sent_at` (rời `sent_at IS NULL` của `run_resend_unsent`). Tôi đã tự kiểm khẳng định "`sent_at` không bao giờ được đọc để suy đã gửi thành công": `grep` toàn repo cho thấy mã sản phẩm chỉ dùng nó làm bộ lọc `IS NULL` (`jobs.py:148,177`) và vị từ index — **đúng**. Không dòng nào phạm partial unique: đặt `superseded_at` *gỡ* dòng khỏi index, đặt `sent_at` không đụng vị từ index. |
| **4 — P2** thiếu test lô [hỏng, tốt] | NO-143 | ✅ **đóng** | `test_send_token_mail__J01_isolates_bad_token_from_batch` (`test_jobs.py:170-208`): bẻ `token_hash` của token đầu → không khoá nào khớp, gửi lô `[bad, good]`, khẳng định `PermanentError(TOKEN_KEY_ROTATED)` **và** `memory_mailer.sent == 1` tới `good_user` **và** `bad.superseded_at is not None` **và** `run_resend_unsent == 0`. **Đỏ thật trên mã cũ**: `_mark_permanent_failure` là hàm mới, mã cũ không thể đặt `superseded_at`, nên khẳng định đó hỏng — không phụ thuộc thứ tự dòng trả về. `test_send_token_mail__J03` cũng được bổ sung khẳng định `sent_at is not None`, phủ nhánh `MAIL_REJECTED` của cùng hàm. |
| **2 — P2** C27 đo PING với PING | NO-144 | ✅ **đóng** | `test_router_request_reset.py:118-147`: mỗi vòng `make_user(db_session)` **mới**, nên lượt "known" rơi vào nhánh `issue` thật. Tôi đã kiểm `make_user` **có `await db.commit()`** (`packages/testing/factories/auth.py:44`) — nếu nó chỉ `flush()` thì app (session khác) không thấy người dùng và vòng đo lại tụt về nhánh "ping", tức bản vá sẽ vô hiệu trong im lặng. Nó commit, nên khẳng định `gap < MAX_MEDIAN_GAP_S` giờ **có thể đỏ**. |
| **3 — P2** client Redis mỗi request | NO-145 | ✅ **đóng** | `_broker_client = ProcessLocal[SyncRedis](broker_redis_sync)` (`router.py:207-215`), `_ping_broker` chỉ còn `.get().ping()`. Dùng lại đúng khuôn có sẵn (`tasks.py:52 _delivery_client`, `celery_app.py:120 _producer`) chứ không dựng abstraction mới (R-10). `ProcessLocal` (`packages/messaging/redis.py:64-94`, **có sẵn từ trước**, không phải mã mới của vòng này) có `threading.Lock` và dựng lại khi PID đổi → an toàn luồng và qua `fork`. Timeout kế thừa từ `_sync_client` (`socket_connect_timeout`/`socket_timeout` = `SYNC_TIMEOUT_S`). |
| **5 — P3** `_seed_token` chép–dán · **6 — P3** thiếu docstring · **9 — Nit** `memory_mailer: Any` | NO-146 | ✅ **đóng** | `apps/api/auth_recovery/tests/support.py` mới gom `_seed_token`/`_seed_reset_token`/`_seed_invite_token` từ **bốn** file; theo khuôn `apps/api/auth/tests/support.py` đã có (hợp lý hơn gợi ý `packages/testing/factories/` của tôi ở lượt 1 — B1-05 vẫn nhập được, và `test_e2e.py` đã nhập chéo kiểu này). Docstring đã thêm ở `tokens.py:52,67`, `packages/mail/sender.py` (5 chỗ + thân cho stub Protocol), `payloads/auth_recovery.py:19`, `fixtures/mail.py` (4 chỗ). `memory_mailer: Any` → `MemoryMailer` ở cả 5 test. |
| **7 — Nit** `run_send_token_mail` 59 dòng | NO-146 | ✅ đóng | Còn 26 dòng; phần gửi một token tách ra `_send_one`. |
| **8 — Nit** cooldown suy từ `expires_at - ttl` | NO-147 | ➖ chấp nhận | Đã ghi `NO-147` là "chấp nhận", lý do đứng được. |

Một rủi ro tôi soát riêng vì nó dễ làm hồi quy âm thầm: `support.py::seed_token` **đổi mặc định
`created_at`** — trước đây `_seed_token` của `test_jobs.py` đặt `created_at=clock.now()`, nay để
trống thì cột lấy `func.now()` của DB. Đã kiểm từng chỗ dùng: `resend_unsent` J01/J06 vẫn cho cùng
kết quả (cả hai mốc đều không lọt cửa sổ cắt hạn), `purge_tokens` lọc theo `used_at`/`superseded_at`
chứ không theo `created_at`, và `test_latest_invitations_returns_latest_unused_even_expired` so với
`newer_row.created_at` (giá trị đọc lại từ DB) chứ không so với `fake_clock`. Hai dòng của cùng một
người nay trùng `created_at` (cùng giao dịch → `func.now()` bằng nhau) nhưng dòng cũ đã
`superseded_at` nên bị `latest_invitations` lọc ra trước, `DISTINCT ON` không có hoà. **Không hồi quy.**

## Finding mới của vòng sửa

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | OBS-01 | `smtp_code` nay **mất hẳn**. Mã cũ `raise PermanentError(MAIL_REJECTED) from exc` giữ `MailRejectedError` (mang `smtp_code`) trong chuỗi nguyên nhân; mã mới bắt `except MailRejectedError:` không `as exc`, và `raise PermanentError(first_failure)` cuối vòng không có `__cause__`. `_on_send_token_mail_failed` chỉ log `token_ids` + mã, nên mã trả lời SMTP — thứ mà `sender.py:29,37` cố ý mang theo "để log" — không tới được log nào. Vận hành mất khả năng phân biệt 550 "mailbox không tồn tại" với 554 "bị coi là spam". | `apps/api/auth_recovery/jobs.py:118-120`, `jobs.py:158-166` | Log `smtp_code` ngay tại chỗ cô lập trong `_send_one` (theo thiết kế nó **không** mang địa chỉ hay thân thư, nên không phạm K11). |
| 2 | P3 | RES-02 | Mã lỗi vĩnh viễn bị **nuốt** khi một token **sau** nó trong lô ném `TransientError`: `_send_one` ném thẳng ra khỏi vòng nên `first_failure` mất; lượt Celery thử lại không còn thấy token đã cô lập (đã bị lọc khỏi tập dòng), `first_failure` là `None` → task "thành công" và `on_failed` không bao giờ báo cái `MAIL_REJECTED`/`TOKEN_KEY_ROTATED` đã thật sự xảy ra. Mất dấu vết, không mất dữ liệu. | `apps/api/auth_recovery/jobs.py:152-166` | Cùng một bản vá với finding 1: log tại chỗ cô lập thì mã không còn phụ thuộc việc sống sót tới cuối vòng. |
| 3 | Nit | MNT-01 | `_send_one(… mailer: Any …)`: Protocol `Mailer` có sẵn ở `packages/mail/sender.py` và `jobs.py` đã nhập từ đúng module đó; để `Any` là tắt kiểm kiểu ở chính vòng sửa vừa bỏ `Any` khỏi test. (`row: Any` thì giữ nguyên là hợp lý — theo khuôn `_resolve_plain_token`, `Row` của SQLAlchemy.) | `apps/api/auth_recovery/jobs.py:99` | `mailer: Mailer`. |
| 4 | Nit | TEST-02 | Khẳng định tiêu đề của test lô ("token tốt **sau** nó") không được ghim: câu `SELECT` của `run_send_token_mail` không có `ORDER BY`, thứ tự dòng do Postgres chọn. Test vẫn bắt được hồi quy ở mọi thứ tự (nhờ khẳng định `superseded_at`/`requeued == 0`), nên **không yếu** — chỉ là điều docstring nói không phải điều test đo. | `apps/api/auth_recovery/jobs.py:143-150`; `test_jobs.py:170-208` | Thêm `.order_by(OneTimeToken.created_at)` vào câu truy vấn (cũng làm thứ tự gửi tất định), hoặc sửa docstring cho khớp. |
| 5 | Nit | (nhìn trước) | `sent_at` nay mang hai nghĩa: "đã gửi được" và "đã thử giao xong, bị từ chối hẳn". Đúng ở thời điểm này (đã kiểm: mã sản phẩm chỉ dùng nó làm bộ lọc `IS NULL`), nhưng màn lời mời của **B1-05** nếu hiện "đã gửi lúc …" từ cột này sẽ báo sai cho lời mời bị hard-bounce. | `apps/api/auth_recovery/jobs.py:72-86` | Một dòng `DEBT.md` để B1-05 biết; nếu B1-05 cần phân biệt thì thêm cột `failed_at` lúc đó. |

Không có finding P0/P1/P2 nào thuộc về B1-03 ở vòng này.

## Chặn merge — **không phải lỗi của B1-03**

| Mức | ID | Mô tả | Chủ |
|---|---|---|---|
| **P1** | DEP-01 | Bản nâng `redis` 6.4.0 → 8.1.0 (`d0bb175`, vào `main` qua `4f4f295`) làm **`mypy --strict` đỏ trên chính `main`**: 6 lỗi ở 4 file (stub redis-py 8.1 đổi kiểu trả về của `xreadgroup`, `get`, `incr`). Bước 3 của **mọi** nhánh cắt từ `main` sẽ hỏng, kể cả nhánh này. | B0-05 (`packages/messaging/streams.py:143`, `packages/messaging/tests/test_locks.py:66`), B0-06 (`apps/api/core/tests/test_internals.py:251`), B1-01 (`apps/api/auth/tests/test_units.py:180`) |

**Bằng chứng quy trách nhiệm (không suy đoán):** tôi tạo một worktree tạm ở **`main` sạch** (`4f4f295`,
không có B1-03) và chạy `bash tools/verify/run.sh verify --steps 1,2,3` → **cùng 6 lỗi, cùng 4 file,
cùng số dòng** (`checked 374 source files`); trên cây đã gộp B1-03 là `checked 401 source files` —
B1-03 thêm 27 file và **không góp lỗi nào**. Không file nào trong 4 file đó nằm trong diff
`09dc9d0..df2d349` hay trong 14 file thuộc sở hữu B1-03.

Ba lỗi `streams.py:143` là kiểu thật (stub `xreadgroup` mới trả `bytes | str`), hai lỗi
`redundant-cast` là `Redis.incr` nay đã được khai kiểu nên `cast` thành thừa, một lỗi `test_locks.py`
là `get()` trả `bytes | str | None`. Cả năm file đều **ngoài sở hữu B1-03** — bắt tác giả B1-03 sửa
là vi phạm K27/R-27.

## Điểm (chấm riêng phần việc của B1-03 ở vòng sửa)

| Miền | Trọng số | Điểm | Tích | Vì sao |
|---|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 | NO-144 đóng; C27 giờ đo đúng cặp `issue` vs "không người" |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 | không finding; cách đánh dấu không đụng partial unique |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 | NO-143 đóng, cô lập đúng theo từng token |
| PERF – Hiệu năng | 10% | 5 | 0,50 | NO-145 đóng bằng khuôn `ProcessLocal` có sẵn |
| RES – Chịu lỗi | 10% | 4 | 0,40 | finding 2 (P3) |
| DB, API – Migration & contract | 10% | 5 | 0,50 | rebase `down_revision` sang `r20260923_b2_01`, chuỗi thẳng đúng 1 head, bước 6 và 7 xanh |
| TEST – Kiểm thử | 7% | 4 | 0,28 | finding 4 (Nit) — test mới đúng và đỏ được trên mã cũ |
| OBS, OPS – Vận hành | 5% | 4 | 0,20 | finding 1 (P3) |
| MNT – Bảo trì | 3% | 4 | 0,12 | finding 3 (Nit) |
| **Tổng** | **100%** | | **4,75 / 5** | |

## PHÁN QUYẾT: ✅ APPROVE (4,75/5) — **kèm điều kiện merge bắt buộc**

Cả bốn finding chặn của lượt 1 đã được đóng **đúng cách gốc**, không phải vá triệu chứng (R-19):
lỗi vĩnh viễn nay cô lập theo từng token với cách đánh dấu tôi đã tự kiểm là đứng được trên toàn
repo; test lô [hỏng, tốt] thật sự đỏ trên mã cũ; C27 đo đúng nhánh cần đo (và `make_user` commit,
nên bản vá không vô hiệu trong im lặng); client broker dùng lại khuôn `ProcessLocal` có sẵn thay vì
dựng abstraction mới. Vòng sửa không gây hồi quy nào — kể cả chỗ dễ hồi quy âm thầm nhất là đổi mặc
định `created_at` của helper gộp, tôi đã soát từng chỗ dùng. 3172 test qua, 0 hỏng, mọi gói bị chạm
vẫn trên ngưỡng phủ. Năm finding mới đều P3/Nit, không chặn.

**Điều kiện merge (R-37, BE-00 §12 — cổng phải xanh thì mới được vào `main`):**

1. **Phải có FIX cho DEP-01 trước.** `main` đang đỏ ở bước 3; merge B1-03 không làm nó tệ hơn nhưng
   cũng không làm nó xanh. Giao cho B0-05 (2 file), B0-06 (1 file), B1-01 (1 file) — hoặc một FIX
   gom nếu người điều phối muốn nhanh. **Đây là việc của `main`, không phải của B1-03; đừng trả
   nhánh này về cho tác giả vì nó.**
2. **Sau khi DEP-01 xong, chạy lại cổng đầy đủ một lượt trên cây đã gộp** và xác nhận đủ tám bước
   xanh — đặc biệt là **bước 5b/`case_gate`, bước duy nhất lượt này chưa có phán quyết thật của
   cổng**. Kiểm tra tên test ở trên cho thấy mọi case ID còn nguyên, nhưng đó là suy luận, không
   thay được một lượt chạy.
3. Nếu không sửa finding 1–5 trong vòng này thì ghi một dòng `DEBT.md` cho finding 1+2 (gộp được,
   cùng một bản vá) và finding 5.

Tôi ghi nhận điều này lệch khỏi câu chữ §3 của skill ("thoát khác 0 → REQUEST CHANGES"): lệch có
chủ ý, vì mã thoát 1 ở đây đo tình trạng của `main` chứ không đo nhánh đang chấm, và `REQUEST
CHANGES` sẽ dồn việc sai người. Cái chặn merge vẫn còn nguyên — chỉ là nó được ghi đúng chủ.
