# Review merge `feature/b1-05-user-admin` → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worktree `b1-05-review`, HEAD tách) · Commit đầu nhánh: `7587f462fd5a`
- Phạm vi: `git diff main...HEAD` — 1 commit, 16 file, +2295/−0. Nằm **trọn** whitelist của spec
  (`apps/api/users/{__init__,router,schemas,errors,service}.py`, `apps/api/users/cases.toml`,
  `apps/api/users/tests/**`, `changes/B1-05.md`). `git status --porcelain` rỗng.
- Cổng: `bash tools/verify/run.sh verify` chạy **một** lượt tại chỗ trong worktree này: **mã thoát 0**
  (log `C:/Users/mxuan/AppData/Local/Temp/claude/b1-05rev/verify.log`, dòng `EXIT=0`). Không dựa vào
  `gate1.log` của tác giả.
- Độ phủ (`coverage_gate`): tổng dòng **99,45 %** · nhánh **98,36 %**; `apps/api/users` **100 % / 100 %**;
  tập file bị chạm **100 % / 100 %**. Pytest: **4008 passed, 0 failed, 4 deselected**, 937 s.

## Bảng E.10 — lấy từ mã thoát thật của lượt chạy này

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 9 hợp đồng giữ, 0 gãy |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4008 passed / 0 failed / 4 deselected |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf 0 đơn vị bị chạm; 34 thao tác đã mount, 3 cảnh báo cũ (`files_read_object`, `health_live`, `health_ready`) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, 10/10 mục; nhánh không thêm revision |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H1 871 mẫu · H1 ngữ cảnh 10 · H3 10 khoá/3 vai · H5 3 khung · **H4 "không áp dụng"** (B3-05 chưa hợp nhất — đúng BE-00 §12) |
| 8 | `openapi` | đạt | ghi `/tmp/openapi.json`, 76 802 byte — bước này **không** cần `openapi.json` hợp nhất ở gốc, nên không có mục "không áp dụng" nào |

`case_gate` 9 op của B1-05: `users_list_users`, `users_list_memberships`, `users_list_activity`,
`users_change_role`, `users_disable_user`, `users_enable_user`, `users_invite_users`,
`users_resend_invitation`, `users_delete_user` — **tất cả `đạt`, thiếu = 0**.

## Kiểm độc lập báo cáo tác giả

| Khẳng định của tác giả | Kết quả reviewer tự kiểm |
|---|---|
| cổng thoát 0, bước 1–8 đạt | **đúng** — lượt chạy riêng của reviewer, `EXIT=0`, bảng trên |
| độ phủ tổng 99,45/98,36; `apps/api/users` 100/100 | **đúng**, trùng từng chữ số |
| `case_gate` 9 op, thiếu = 0 | **đúng** |
| H1 871 mẫu, H3 10 khoá/3 vai | **đúng** |
| diff nằm trọn whitelist, `status` rỗng, trailer `Prompt: B1-05` | **đúng**; dòng đầu commit 47 ký tự, đúng Conventional Commits, khối trailer là đoạn cuối, không `--no-verify` |
| C14 hai client thật song song | **đúng** — `test_concurrency.py:39-56` dùng `auth_app` + `signed_in(…, client=other)` + `asyncio.gather`, khẳng định `sorted(status)[0] == 200`, bên kia ∈ {401,403,422}, `admin active còn lại == 1` |
| #38 3 người = 30 người = 4 câu SQL | **đúng** — `test_read.py:114-127` dùng `count_sql` thật và `assert small.count == large.count` (không phải số cứng) |
| không có nợ mới | **một phần** — xem finding 1 (cần một dòng `DEBT.md`) |

Đã soát riêng hai điểm người điều phối chỉ định:

- **Lệch (3) — `USER_LAST_ADMIN` không tới được qua HTTP.** Lập luận của tác giả **đúng về logic**:
  `lock_admin_set` (`service.py:166-171`) đòi người thực hiện nằm trong tập admin `active`, nên
  `len(admins) == 1` ⇒ `admins == (actor,)` ⇒ `target.id in admins` ⇒ `target == actor` ⇒ `forbid_self()`
  đã ném trước ở cả #41 (`:294`), #42 (`:308`) và #46 (`:454`). Bất biến "luôn còn ≥ 1 admin `active`"
  **vẫn giữ**, chỉ là do `USER_SELF_MODIFICATION` chứ không phải `USER_LAST_ADMIN`; prompt [6] cho phép
  bên thua là "403 **hoặc** 422". Không phải lỗi. Hệ quả còn lại là test/độ phủ — finding 3.
- **Lệch (6) — bỏ trùng trước khi kiểm trần.** 51 email **khác nhau** vẫn ra 422 đúng
  (`test_invite.py:152-159`, reviewer đọc lại đường mã: `_validate_emails` giữ 51 khoá ⇒
  `_require_batch_size` ném). Chỗ thật sự lệch là lô **có trùng** — finding 2.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | SEC-03 / K37 | `confirmEmail` là trường email trên dây **duy nhất** của repo không đi qua `validate_wire_email`. `SignInBody.email` (`apps/api/auth/router.py:76-79`) và `PasswordResetRequestBody.email` (`apps/api/auth_recovery/router.py:84-87`) đều qua, dù cũng chỉ **so** chứ không lưu. `_require_confirm` chỉ gọi `normalize_email` = `NFC + strip + casefold`, mà reviewer đã đo: `normalize_email('\u212A@example.com') == 'k@example.com'` và `normalize_email('\u017F@example.com') == 's@example.com'`. Người xác nhận xoá vì vậy khớp được bằng một chuỗi chủ tài khoản **không thể gõ ra**. Khai thác leo thang: **không** (người gọi đã là admin có `user.manage`); hại thật: rào chắn chống xoá nhầm yếu đi. Gốc P3, **nâng một bậc** theo `RULE.md` §1 (luồng auth/PII **và** thao tác không hoàn tác được) | `apps/api/users/schemas.py:72-76` (`DeleteUserBody.confirm_email`); so với `apps/api/users/service.py:111-114` | Thêm `@field_validator("confirm_email")` gọi `validate_wire_email` (đúng 4 dòng, khuôn `SignInBody._wire_email`), giữ nguyên `_require_confirm`. FE gửi `confirmEmail` qua `emailSchema` (`src/api/schemas/users.ts:292-297`) nên không gãy hợp đồng: email sai dạng → 422 `VALIDATION` `field:"confirmEmail"`, email đúng dạng nhưng sai người → vẫn `USER_CONFIRM_EMAIL_MISMATCH`. Không sửa trước merge thì **bắt buộc** một dòng `DEBT.md` (§1 P2) |
| 2 | P3 | LOG-01 | Bỏ trùng chạy trong validator của schema, `_require_batch_size` chạy **sau** nó, nên một lô 60 phần tử mà bỏ trùng còn ≤ 50 được nhận **201** thay vì 422 `field:"emails"`. Prompt [6] #44 nêu thứ tự ngược ("`emails` > `INVITE_BATCH_MAX` → 422. Mỗi email qua `validate_wire_email` … Bỏ trùng…"). **Không** phải vector DoS mới: `validate_wire_email` vẫn chạy trên **mọi** phần tử trước khi vào service dù đổi thứ tự (chỉ `Field(max_length=…)` mới chặn sớm được, mà trần lại là cấu hình động), và thân bị `DEFAULT_BODY_LIMIT` chặn ở 1 MiB (`apps/api/core/routing.py:44`) | `apps/api/users/schemas.py:85-93` + `apps/api/users/service.py:117-120`, gọi ở `:412` | Muốn đúng chữ prompt thì kiểm `len(values)` ngay đầu `_validate_emails` **trước** vòng bỏ trùng. Tác giả đã ghi ở "Lệch khỏi prompt (6)" và hành vi hiện tại khoan dung hơn với người dùng → chấp nhận được, chỉ cần một dòng `DEBT.md` nếu giữ |
| 3 | P3 | TEST-04 / MNT-05 | Nhánh `raise` của `forbid_last_admin` là mã **không tới được qua HTTP** (xem mục "Kiểm độc lập"). Nó chỉ được phủ bằng `test_forbid_last_admin_blocks_the_only_admin`, test này dựng một `WriteScope` ở trạng thái **không thể tồn tại** (`actor_id="usr_a"` mà `admins=("usr_b",)` — `lock_admin_set` đã loại trường hợp đó). Hệ quả: con số "`apps/api/users` nhánh 100 %" không phản ánh đường thật, và không có test HTTP nào chốt bất biến "≥ 1 admin `active`" bằng chính mã lỗi `USER_LAST_ADMIN`. Không đề nghị **xoá** lớp chốt: prompt [6] "Khoá tập admin" điểm 3 đòi có nó, và tác giả đã ghi rõ ở docstring `service.py:154-157` + "Lệch khỏi prompt (3)" | `apps/api/users/service.py:153-160`; `apps/api/users/tests/test_service.py:22-27` | Giữ nguyên mã. Ghi một dòng `DEBT.md` nói rõ `USER_LAST_ADMIN` hiện **không phát được** qua API, để prompt sau (và FE) không trông chờ nó. Reviewer đã kiểm: AppFront không tham chiếu mã lỗi này ở đâu (`grep` toàn `src/` = 0 kết quả), màn dùng câu chung `describeError` đúng như prompt [2] nói — nên **không** có nguy cơ gãy FE |
| 4 | Nit | PERF-02 | `admin_views` `await avatar_url(...)` cho **từng** người. Đúng yêu cầu "không N+1" (hàm này không chạm DB — đã kiểm `resolve_kind` thoát ngay khi `kind` được truyền, `packages/storage/port.py:173-176`), nhưng `presigned_get_object` của minio là lời gọi **đồng bộ** chạy thẳng trên vòng sự kiện, nên #38 với `USERS_LIST_MAX = 1000` người đều có ảnh sẽ ký 1000 URL trong một request. Ngoài whitelist B1-05 (chủ là B1-04 / B0-04) → **không** tính vào điểm nhánh này, R-27 | gọi ở `apps/api/users/service.py:231`; mã thật `apps/api/me/avatar.py:237-247`, `packages/storage/s3.py:224-246` | Người điều phối cân nhắc một dòng `DEBT.md` cho chủ B1-04: ký lô trong `asyncio.to_thread`, hoặc chỉ ký khi FE thật sự cần |

Không có finding P0/P1. Không có điều kiện dừng sớm nào của `/merge-review` §2: cây sạch, có
`changes/B1-05.md`, commit đúng mẫu + trailer, không đụng file cấm, không `pragma: no cover`,
không `skip`/`xfail` mới, hai `# type: ignore[attr-defined]` (`tests/test_delete.py:185-186`) và hai
`# noqa` (`tests/test_e2e.py:14,26`) đều có mã **và** lý do.

## Những điểm đã kiểm và **đạt** (không thành finding)

- **Khoá tập admin** (`service.py:166-189`) là câu SQL **đầu tiên** của cả sáu route ghi, qua **một** hàm
  dùng chung (`open_scope` cho #41–#43, #45, #46; `lock_admin_set` cho #44), `ORDER BY id FOR UPDATE`,
  trong cùng giao dịch ghi; không có chỗ nào kiểm vai hay "admin cuối" ngoài giao dịch. `lock_timeout`
  5 000 ms toàn cục (`packages/db/settings.py:26`) nên hàng đợi khoá không treo vô hạn.
- **Tự sửa mình** → `USER_SELF_MODIFICATION` ở #41/#42/#46; **không đổi gì** → 200, không nhật ký, không
  `bump_token_version` — có test riêng cho cả ba route (`test_state.py:132-139`, `:257-266`, `:360-368`).
- **#42** `revoke_sessions("disabled")` + `bump_token_version` + `revoke_tokens`, có test phiên thật chết
  (`test_state.py:269-290`). **#43** `active` nếu có `password_hash`, không thì `pending` (`:296-309`).
- **#46** dựng `AdminUser` **trước** khi xoá (`service.py:456` trước `:457`), `deleted_at` + `disabled`,
  revoke + bump + `revoke_tokens`, `remove_user_from_all_projects`, log `project_orphaned` **sau commit**
  qua `on_after_commit`, `USER_CONFIRM_EMAIL_MISMATCH` so qua `normalize_email`, `PATH_BODY_MISMATCH` do
  guard chung `routing.py:136-149` (có test C21).
- **#44** hạn mức `users_invite` dùng **chung** với #45 (một `Depends` duy nhất, `router.py:35-46`;
  30/3600 s, `key_user`, `store="safe"`, `on_error="closed"`), có test xô đếm chung
  (`test_invite.py:309-318`); mọi email qua `validate_wire_email` ở mức cả danh sách để lỗi mang
  `field:"emails"` (K37); bỏ trùng theo `normalize_email` giữ thứ tự đầu; xử lý theo `email_normalized ASC`
  nhưng **trả theo thứ tự đầu vào**; tất-cả-hoặc-không với `USER_EMAIL_TAKEN`; người `pending` có sẵn đổi
  vai + bump + token mới; `name = nfc(local)[:120]`; đua email mới xử lý bằng
  `INSERT … ON CONFLICT DO NOTHING` + đọc lại `FOR UPDATE` (đính chính 5 của spec — reviewer chỉ chấm
  cách hiện thực: nhắm đúng partial unique `index_where=deleted_at IS NULL`, không savepoint, không 500,
  không 422 giả, có test cả hai nhánh `pending`/`active`); thư chỉ đi sau commit và C10 không gửi lần hai.
- **#38** `total` bỏ người xoá mềm; `lastActiveAt` luôn có khoá (`KeepNull`); `invitedAt`/`inviteExpiresAt`
  chỉ khi `pending` **và** có lời mời chưa dùng/chưa bị thay, **kể cả hết hạn** (`latest_invitations`
  `tokens.py:167-183` lọc `used_at IS NULL AND superseded_at IS NULL`, **không** đọc `sent_at` — NO-150
  được tôn trọng); `avatarUrl` vắng khoá khi không có ảnh.
- **#39/#40** 404 cho người không có/đã xoá mềm, thứ tự và trần đúng khối [6], `id` hoạt động là chuỗi
  thập phân (`str(row.id)`), FE giải bằng `idSchema = z.string().min(1)` nên khớp.
- **K01/K02**: `set(body) == KEYS` được khẳng định ở cả 5 file test; `AdminUserSchema` của FE là `.strict()`
  và trùng từng trường. **K05/K09/K34**: người thực hiện luôn từ `Principal`, `userId` thân chỉ để guard W21.
- **R-01** docstring đủ mọi hàm (kể cả hàm riêng và validator); **R-08** hàm dài nhất 26 dòng, không hàm nào
  vượt độ phức tạp; **R-07** không chép khoá/kiểm sáu lần; **K23** không mock Postgres/Redis/MinIO/Mailpit —
  có e2e Mailpit + worker Celery thật (`test_e2e.py`). `cases.toml` `extra` đúng khối [8] của prompt.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 3 (finding 1, P2) | 0,75 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (finding 2, P3) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 (finding 4 là Nit, chủ khác) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (finding 3, P3) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (finding 3, P3) | 0,12 |
| **Tổng** | **100 %** | | **4,25 / 5** |

Loại task theo `RULE.md` §6: **Auth, phân quyền, PII** — SEC/LOG/API/OBS/TEST bắt buộc, đã soát hết;
quy tắc nâng mức của §1 đã áp cho finding 1.

## PHÁN QUYẾT: APPROVE (4,25/5)

Không có P0/P1, điểm ≥ 4,0 → theo ma trận `RULE.md` §5 là **APPROVE**. Nhánh làm đúng phần khó nhất của
prompt: khoá tập admin là câu đầu của mọi route ghi qua một hàm dùng chung, C14 có test hai client đăng
nhập thật, #38 không N+1 có bộ đếm SQL thật, thư chỉ đi sau commit, và cổng đầy đủ do chính reviewer chạy
lại thoát 0 với `apps/api/users` phủ 100 % dòng **và** 100 % nhánh. Báo cáo của tác giả kiểm lại đúng ở
mọi con số.

**Điều kiện kèm theo merge (không chặn, nhưng bắt buộc làm):** người điều phối ghi `DEBT.md`
— finding 1 (P2, `RULE.md` §1 đòi "sửa trước merge **hoặc** ticket có lý do"), finding 2 và finding 3
(P3, để prompt sau biết `USER_LAST_ADMIN` hiện không phát được qua API), và cân nhắc finding 4 cho chủ
B1-04. Reviewer **không** sửa `DEBT.md` theo spec.
