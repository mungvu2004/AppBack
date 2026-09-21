# Review merge feature/b1-01-auth-login-sessions → main — lượt 3 (delta)

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập**, không phải tác giả. Lượt 1: `APPROVE 4,49/5` tại `04a1c3a` (`docs/reviews/2026-09-21-feature-b1-01-auth-login-sessions.md`). Lượt 2: `APPROVE 4,77/5` tại `b877f46` (`…-round-2.md`), kèm điều kiện sửa N1/N2 trên nhánh rồi xin review ngắn cho delta. Lượt này **chỉ soi sâu delta** `b877f46..ff8372e`; phần còn lại giữ nguyên kết luận của lượt 1 và 2.
- Commit đầu nhánh: `ff8372e8be45` (gốc `5bb39de`, 10 commit). Hai commit mới, cả hai mang `Prompt: B1-01` (đọc được bằng `%(trailers:key=Prompt,valueonly)`):
  - `f8985cb` `fix(auth): address b1-01 round-two review findings` (50 ký tự)
  - `ff8372e` `docs(repo): log NO-057 found in the b1-01 round-two review` (58 ký tự)
- Delta chạm 6 file: revision `r20260921_b1_01_auth.py` của chính B1-01, `apps/api/auth/sessions.py` (chỉ docstring), ba file test của `apps/api/auth`, `DEBT.md` (+1 dòng). Không file cấm, không `pragma`/`noqa`/`type: ignore`/`skip`/`xfail` mới. `git status --porcelain` rỗng trước và sau probe. `git merge-tree --write-tree main HEAD` sạch (với `main` = `4c8cc3d`).
- Cổng: `bash tools/verify/run.sh verify`, chạy tại chỗ trong worktree sạch (log `review3/verify.log`, `review3/verify2.log` trong scratchpad của phiên):
  - lượt 1: **mã thoát 1**. Hỏng đúng một test, `tools/tests/test_services.py::test_ephemeral_postgres_dừng_xong_bản_dùng_chung_vẫn_chạy` (`asyncpg.connect(timeout=5)` hết giờ qua `host.docker.internal`). Đây là đỏ giả đã biết `NO-042` (⬜, B0-01); file không đổi từ `d3c4fd8`, không thuộc delta;
  - lượt 2 (chạy lại một lần): **mã thoát 0**, `1639 passed, 10 skipped` (lượt 2 có 1638, thêm đúng 1 test mới).
- Độ phủ (`tools.coverage_gate`, lượt thoát 0): tổng dòng **99,21 %** · nhánh **96,68 %**; `apps/api/auth` **98,49 % / 91,91 %**; `apps/api/core` 99,47 / 98,06; `packages/db` 98,77 / 97,32; `packages/testing` 99,09 / 100,00; tập file bị chạm 98,56 / 93,29. Số của `apps/api/auth` dao động nhẹ giữa các lượt vì sai số đo sau `await` qua greenlet (`NO-035`).

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (231 file) |
| 4 | `lint-imports` | đạt (9 KEPT, 0 BROKEN) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (`auth_login` 7/7, `auth_refresh` 5/5, `auth_logout` 2/2) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9: up, seed ×2, down −1, up, down base, chỉ còn `alembic_version`, up lại, model khớp DB) |
| 7 | H1 H3 H4 H5 | đạt. H1 186 mẫu; H3/H4/H5 `không áp dụng` hợp lệ (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Probe (container verify, bản sao `/tmp/w`; file tạm trong `.cache/` đã xoá)

- **R3-P1 — tên ràng buộc ở đầu nhánh.** `alembic upgrade head` rồi đọc `pg_constraint`: `users` có đúng `ck_users_{role,status,language,name_length,token_version}`, `refresh_sessions` có đúng `ck_refresh_sessions_{revoked_reason,revoked_pair}`. Cả 7 tên trùng từng chữ với `Base.metadata`. `pk_`/`fk_` của hai bảng cũng trùng.
- **R3-P2 — test mới đỏ trên revision cũ.** Chép revision của `b877f46` đè lên: `test_check_constraint_names_match_the_model` **hỏng**, `Extra items in the left set: 'ck_users_ck_users_status', 'ck_users_ck_users_role', 'ck_refresh_sessions_ck_refresh_sessions_revoked_pair', …`. Ở đầu nhánh: đạt. Test đọc DB dựng bằng Alembic thật (`db_template` → `command.upgrade`), không phải `create_all`, nên không rỗng.
- **R3-P3 — đột biến test log.**
  - `"presented": token` vào `extra` của `refresh_reuse_revoked`: test mới **hỏng**; test cũ của `b877f46` cùng đột biến vẫn **đạt** (tái hiện đúng N1).
  - Token vào một dòng WARNING của logger khác: **hỏng** (vòng `all(...)` duyệt mọi bản ghi).
  - Token dưới khoá `refreshToken`: **đạt**, đúng, vì `JsonFormatter` che khoá đó, nên thứ thật sự ra log không mang token.
  - Email thô (`body.email` của lời gọi) vào `extra` của `login_throttled`: `test_lock_is_logged_once_without_the_email` **hỏng**.
- **R3-P4 — NO-057.** Cùng lượt đọc `pg_constraint` cho thấy `ck_idempotency_records_ck_idempotency_records_{state,key_format}`, trong khi model sinh `ck_idempotency_records_{state,key_format}`. Nguyên nhân khớp mã: `r20260920_b0_06_idempotency.py:44-45` truyền `name=f"ck_{TABLE}_…"` không bọc `op.f`. `migrate_check.py:75-77` dùng `compare_metadata` của Alembic, mà hàm này không so `CHECK`. Dòng nợ mô tả đúng.

## Trạng thái finding của lượt 2

| # | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| N1 | P3 | **đã sửa** | `test_refresh.py:521-523`, `test_login.py:448-451`: khẳng định trên `JsonFormatter().format(record)`, gồm cả `extra`. R3-P3: đỏ với mọi đột biến lộ bí mật, xanh khi bí mật nằm dưới khoá bị che |
| N2 | P3 | **đã sửa** (phần B1-01) · phần B0-06 ghi `NO-057` | `r20260921_b1_01_auth.py:57-61, 88, 90`: cả 7 `CHECK` bọc `op.f(...)`; không còn `CHECK` nào thiếu. Revision chưa từng lên `main`, sửa tại chỗ hợp lệ như Nit #8 của lượt 2. Test mới `test_units.py:199-214` (R3-P1, R3-P2). `downgrade` chỉ `drop_table`, không phụ thuộc tên; bước 6 đạt 9/9 |
| N3 | Nit | **đã sửa** | `sessions.py:396-397`: con số đổi thành "1,4 ms với một khoá cũ, 4,4 ms với ba", đúng thực đo của lượt 2 |

## Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N4 | Nit | R-34 · MNT-04 | `NO-057` chỉ giao phần B0-06 (đổi tên hai `CHECK` đã hợp nhất). Lỗ hổng gốc là `migrate_check` không so tên `CHECK`: dòng nợ **có nêu** ở cột nguyên nhân nhưng **không** có chủ (B0-03) hay việc chữa. Lượt 2 đã đề nghị ghi phần này. Test mới của B1-01 chỉ canh hai bảng của nó, nên revision sau (của prompt khác) vẫn có thể lặp đúng lỗi mà cổng không đỏ | `DEBT.md:76` (cột chủ: chỉ "B0-06") | Người điều phối thêm "B0-03 (`packages/db/migrate_check.py`): so tên `CHECK` của DB với `Base.metadata`" vào cột chủ/cách chữa của `NO-057`, hoặc mở một dòng riêng. Đây là nhật ký quản trị, commit thẳng lên `main` theo ngoại lệ R-36. Không chặn merge |

**Lượt 3: P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 1 mới (N4)**

## Kiểm sổ nợ

| Kiểm | Kết quả |
|---|---|
| Điều kiện 1 của lượt 2 | đạt theo nhánh "sửa trên nhánh + review delta": N1, N2 đã sửa; phần N2 nằm ngoài nhánh ghi `NO-057` ⬜ P3, chủ B0-06. Không cần dòng `NO-058` |
| Id `NO-057` | không trùng: `main` dừng ở `NO-052`, nhánh này dùng `NO-053..057`, `feature/b5-01-…` dùng `NO-060..064` |
| Định dạng dòng | đúng lối các dòng ⬜ khác (ngày đóng để trống) |
| Nợ P0/P1 còn ⬜/🔧 | không |

## Điểm (mang từ lượt 2, chỉ đổi miền mà delta chạm)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (N3 đã sửa) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (N2 đã sửa; phần B0-06 có từ trước trên `main`, ghi `NO-057`) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (N1 đã sửa, đột biến kiểm được) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #1 lượt 1 chấp nhận ở `NO-056`; Nit N4) | 0,09 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,94 / 5**

## PHÁN QUYẾT (lượt 3): APPROVE

Lý do: delta nhỏ (45 dòng thêm) và đúng việc lượt 2 yêu cầu. Cả ba điểm N1, N2, N3 đã sửa, và mỗi bản sửa đều có bằng chứng tự kiểm: test tên `CHECK` đỏ trên revision cũ, xanh ở đầu nhánh; test log đỏ với mọi đột biến lộ token hoặc email. Cổng thoát 0 ở lượt chạy lại. Lượt đỏ đầu là `NO-042`, ngoài nhánh. Độ phủ `apps/api/auth` 98,49 / 91,91. Không có P0 đến P3; điểm 4,94 ≥ 4,0.

Điều kiện cho phiên merge (không có điều kiện chặn mới):

1. Gộp bằng `git merge --no-ff`, **không** squash, **không** rebase, như lượt 2. Lý do: nhánh mang trailer của B1-01 và B0-06 cùng `Fix: FIX-029/030/031`, và các sha `1e2d146`, `971a1a1`, `9f80576` ghi ở `docs/fixes.md` phải còn đúng.
2. Như lượt 1 và 2: người điều phối ghi nhận ngoại lệ K27 của FIX-029..031.
3. Nên làm, không chặn: bổ sung chủ B0-03 vào `NO-057` (N4). `NO-042` tiếp tục làm đỏ giả cổng; nên ưu tiên đóng.
