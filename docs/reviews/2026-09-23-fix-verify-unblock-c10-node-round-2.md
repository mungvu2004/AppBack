# Review merge `fix/verify-unblock-c10-node` → main — lượt 2

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (worktree `review-fix-r2`, tách rời, không sửa mã)
- Commit đầu nhánh: `950a791acc65` · 9 commit trên `main` (`031befff9f94`), `git diff --stat main...HEAD`:
  7 file, +208 −47
- Phạm vi lượt này: `git diff 165d9fc..HEAD` — 4 commit vòng sửa (`45f7747`, `e2b791d`, `e44e791`, `950a791`),
  4 file, +136 −25. Lượt 1: `docs/reviews/2026-09-23-fix-verify-unblock-c10-node.md` (REQUEST CHANGES, 4,69/5).
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ **một lượt, foreground/attached**, **mã thoát 0** —
  log `C:/Users/mxuan/orca/workspaces/AppBack/review-fix-r2/.cache/src-out/verify/20260923T105254Z-950a791acc65.log`
- Test: **2796 passed, 7 skipped, 4 deselected, 0 failed** (457,19 s) — trong đó
  `tools/ci/tests/test_h2.py::test_main_real_app_passes` **chạy thật** (8,4 s, Testcontainers thật, K23).
- Độ phủ: tổng **dòng 99,15% · nhánh 97,71%** · **tập file bị chạm dòng 99,68% · nhánh 98,21%** ·
  `apps/api/core` 99,47/98,06 · `packages/db` 94,77/95,45 · `tools` 98,89/96,42 — mọi số ≥ 90%.

## Bảng cổng (mã thoát thật)

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | 441 file |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | **đạt** | 2796 passed / 0 failed; tập file bị chạm 99,68% dòng · 98,21% nhánh |
| 5b | `pytest -m perf` → `case_gate` | **đạt** | 3 thao tác mount, `auth_login` `auth_logout` `auth_refresh` đều `đạt`; 3 cảnh báo (`files_read_object`, `health_live`, `health_ready` — miễn H1, không có dòng BE-BIND) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 5 revision; 10/10 kiểm của `migrate_check` đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | Smoke, Bản đồ đủ (83/83), Thao tác đã mount (6/83), **H1 đạt — 186 mẫu response**, H1 ngữ cảnh, H3 đạt; H4 `không áp dụng` (B3-05 chưa hợp nhất), H5 `không áp dụng` (B4-01 chưa hợp nhất) — đúng BE-00 §12 |
| 8 | `openapi` | đạt | `/tmp/openapi.json`, 8174 byte |

**mã thoát: 0 — 8/8 đạt.** Hai ô `không áp dụng` ở bước 7 là H4/H5, hợp lệ theo BE-00 §12 (`not_yet()`,
`tools/contract/check.py:119-123`): chủ `B3-05`/`B4-01` chưa có trong `changes/`.

## Ba việc lượt 1 đòi — đã làm đủ

1. **Finding 1 (P1, cổng đỏ)** — `45f7747` thêm đúng 5 test cho 5 chỗ trống: dòng `40` (`_is_separator_line`
   trả `False`), `57` (`_find_col` thiếu cột), `66` (`_parse_method_path` method lạ), nhánh `46->48` và
   `48->50` (`_split_cells`). `tools/charter.py` **100% dòng / 100% nhánh**; bước 5 xanh.
2. **Finding 2 (P3)** — `test_khoá_bỏ_backtick` (`tools/tests/test_charter.py:49`) dựng bảng bằng
   `_write_table` thay vì ghim hàng 25 của BE-BIND thật: hồi quy NO-128 nay độc lập với hiến chương.
   Header 8 cột / hàng 8 ô, khớp; `assert rows[0].lock == "project.create"` chỉ xanh khi backtick bị bóc.
3. **Finding 3 (P3)** — `_seed(..., state: Literal["in_progress", "completed"])`
   (`apps/api/core/tests/test_common.py:248-256`): state lạ bị `mypy --strict` chặn lúc dịch (bước 3 đạt),
   không còn âm thầm mồi dòng `completed` thiếu `status_code`/`response_body`.

Nit 4 của lượt 1 (thân commit `77acfb8` nói hẹp hơn 25 hàng) là việc lúc squash, không chấm lại ở đây.

## Ba kiểm riêng mà lượt này phải trả lời

- **`950a791` có làm mất vết case C10 cho `case_gate` không → KHÔNG.** Vết case đi qua biến môi trường
  **khác hẳn**: `trace_case` đọc `CASE_TRACE_FILE` (`packages/testing/fixtures/api.py:42,90-92`), còn
  `monkeypatch.delenv` chỉ gỡ `CONTRACT_SAMPLES_DIR` (`packages/testing/golden/recorder.py:34`).
  `deploy/compose/verify.yml:27` đặt `CASE_TRACE_FILE=/tmp/case-trace.jsonl` cho cả container, nên C10
  vẫn ghi vết. Bằng chứng chạy: bước 5b `case_gate: đạt`, cả ba op đều `tìm thấy` đủ bộ case bắt buộc —
  **NO-129 nay đã được chứng minh**, thứ lượt 1 chưa chạy tới.
- **Cơ chế tắt ghi golden có rò sang test khác không → KHÔNG.** `monkeypatch` là fixture phạm vi hàm,
  tự hoàn nguyên `os.environ` lúc teardown; C10 tham số hoá theo op nên mỗi item có `monkeypatch` riêng.
  `record_response` gọi `samples_root()` **mỗi lần ghi** (không chụp lúc setup fixture), nên gỡ biến giữa
  test có hiệu lực ngay và chỉ trong test đó; `attach_context` cũng đi qua `samples_root()` nên không ném
  `ValueError` khi bộ ghi tắt. Không có luồng/tiến trình nào chạy song song trong cùng test.
  Kiểm thêm **không mất bằng chứng nào**: H1 chỉ đòi (a) mẫu giải đạt, (b) ngày giờ W3, (c) **một mẫu 2xx
  cho mỗi op đã mount** — nguồn là C01, không phải C10 (`_missing_success`, `tools/contract/check.py:176-188`,
  thông điệp ghi thẳng "test C01 ghi golden") — và (d) nhánh `Progress`. Trong bảy case chung
  (C04, C05, C12, C13, C22, C25, C10) **chỉ C10 mồi thân giả**; sáu case còn lại trả response thật của app,
  nên tắt bộ ghi đúng một case là đủ hẹp, không phải vá rộng. Bước 7 xanh với 186 mẫu xác nhận.
- **`e44e791` có để lại dữ liệu ảnh hưởng thao tác H2 khác không → KHÔNG.** Chỉ chèn **một** dòng `users`
  (`tools/ci/h2.py:310-326`): `role="admin"`, `status="active"`, `password_hash=None`, email
  `h2-admin-<ULID>@example.com` — hợp mọi `CHECK` của `packages/db/models/auth.py:67-74`, không đụng
  `unique_active("uq_users_email")` vì id là ULID mới mỗi tiến trình. Vai của người gọi lấy từ **token**
  (`FakeTokenVerifier.verify`, `apps/api/core/auth.py:67-75`), không tra DB, nên dòng này không đổi kết quả
  phân quyền của bất kỳ op nào — nó chỉ tồn tại để FK tới `users` có đích. `packages/db/seeds/` hiện **không
  có file seed nào**, nên `apply_seeds` không tạo email nào để đụng. Không idempotent, nhưng chỉ chạy một lần
  mỗi tiến trình H2 (`main()` → `_migrate_and_seed`), và **không** phải seed module nên vòng "seed ci hai lần"
  của `migrate_check` không chạm tới — bước 6 xanh xác nhận.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | MNT-02 / R-02 | Docstring nêu ví dụ FK là `project_memberships.user_id`, nhưng bảng đó **không tồn tại** trên nhánh này hay trên `main` — `packages/db/models/` chỉ có `auth`, `access`, `idempotency`, và FK duy nhất tới `users` là `refresh_sessions.user_id`. Nó tới cùng B2-01 (chưa hợp nhất). Người đọc `main` tra tên bảng sẽ không thấy gì. Sửa **đúng gốc**, chỉ là ví dụ trỏ tới tương lai mà không nói vậy. | `tools/ci/h2.py:314` | Ghi rõ nguồn: "route ghi có FK tới `users` (đầu tiên: `project_memberships.user_id` của B2-01)". |
| 2 | Nit | MNT-01 / R-10 | `_split_cells` chỉ được gọi từ `_parse_table`, mà `_parse_table` chỉ nhận dòng đã qua `_is_table_line` (`line.strip().startswith("\|")`) — nên nhánh "ô không mở bằng `\|`" **không thể với tới** qua API công khai. Test mới mua độ phủ nhánh bằng cách nhập và gọi thẳng hàm private thay vì xoá guard chết. (Nhánh "không đóng bằng `\|`" thì **có** thật: markdown cho phép `\| a \| b`.) | `tools/charter.py:46` · test `tools/tests/test_charter.py:136` | Việc của B0-01 về sau: bỏ `if body.startswith("\|")` (luôn đúng) cùng test của nó, giữ lại test "không đóng". Xoá mã sản phẩm trong vòng sửa cổng là rủi ro thừa — không chặn merge. |

Không có P0, P1, P2, P3.

## Kiểm đã làm, không thành finding

- **Điều kiện dừng sớm**: cây sạch (`git status --porcelain` rỗng ở cả worktree review lẫn `F:/AppBack`);
  4 dòng đầu đúng Conventional Commits (61/50/43/47 ký tự, đều ≤ 72), mỗi commit đủ trailer `Prompt:` + `Fix:`;
  diff **không** đụng `docs/charter/*`, `docs/contracts.toml`, `openapi.json`, `tools/contract/APPFRONT_SHA`,
  `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py` gốc, `tools/verify/*`; không `pragma: no cover`,
  `pragma: no branch`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng nào (grep trên `+` của diff).
- **Sở hữu file (R-27)**: `tools/tests/test_charter.py` → `Prompt: B0-01` ✔ · `apps/api/core/tests/test_common.py`
  → `Prompt: B0-06` ✔ (×2) · `tools/ci/h2.py` + `tools/ci/tests/test_h2.py` → `Prompt: B0-09` ✔.
  Mỗi prompt chủ đều có `changes/<mã>.md` trên `main`.
- **Sửa gốc, không vá triệu chứng (R-19)**: `e44e791` sinh `admin_id` **một lần** trong `main()` rồi luồn qua
  `_migrate_and_seed` → `_seed` → `_seed_admin_user`, và `_admin_header(admin_id)` dùng lại đúng id đó — chứ
  không vá riêng một route. `test_main_returns_1_when_report_fails` cập nhật `lambda admin_id: None` nên chữ ký
  giả không lệch chữ ký thật.
- **TEST / K23**: `test_seed_admin_user_inserts_a_real_row` (`tools/ci/tests/test_h2.py:195`) dùng fixture
  `db_session` — Postgres thật, mỗi test một database (`packages/testing/fixtures/db.py:107-123`), nên
  `await db_session.commit()` không rò sang test khác. Không mock dịch vụ nào.
- **Bằng chứng tác giả — đã tự kiểm lại, khớp**: `log-fix-round2-h2-before.log:96,114` cho thấy nguyên nhân thật
  (`ForeignKeyViolationError` trên `fk_project_memberships_user_id_users` → 500 ở `POST /api/projects`), và
  `log-fix-round2-h2-after.log` kết thúc `1 passed … PYTEST_EXIT:0`. Ghi chú: hai log đó chạy trong worktree
  **B2-01** (nơi `project_memberships` có thật); trên nhánh này `test_main_real_app_passes` vẫn chạy và xanh
  (8,4 s) — nghĩa là bản sửa đúng ở cả hai cây. Log độ phủ của tác giả (`charter.py` 100%) khớp cổng đầy đủ.
- **SEC**: không bí mật trong log/URL; `password_hash=None` nên admin giả không đăng nhập được bằng mật khẩu;
  `h2.py` chỉ chạy trong hạ tầng `_provision()` (Testcontainers), `FakeTokenVerifier` chỉ vào app khi
  `APP_ENV=test` (BE-00 §2.2). **CON / PERF / RES / DB-API**: diff không đụng luồng đồng thời, truy vấn,
  timeout, migration hay hợp đồng FE — bước 6, 7, 8 xanh xác nhận không có breaking change.
- **Sổ nợ (R-34)**: `DEBT.md` trên `main` có đủ **NO-132** (dòng 152), **NO-133** (153), **NO-134** (154), cả ba
  P1, đúng chủ, đang ở trạng thái `đang sửa`. Nhánh không sinh nợ P0/P1 mới. Hai Nit ở trên không cần dòng nợ
  (RULE.md: chỉ P2 trở lên mới bắt buộc).
- **MNT-05**: +208 dòng cả nhánh, trong đó vòng sửa +136 — dưới trần 400, không cần tách.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,97 / 5** |

TEST lên 1 → 5: cổng 8/8 xanh, `tools/charter.py` 100% dòng và nhánh, tập file bị chạm 99,68/98,21, và
`case_gate` — thứ lượt 1 chưa chạy tới — nay `đạt`. MNT giữ 4 vì hai Nit ở trên.

## PHÁN QUYẾT: APPROVE

Vòng sửa làm đủ ba việc lượt 1 đòi, và làm đúng chỗ: finding 1 phủ bằng 5 test qua API công khai chứ không hạ
ngưỡng, finding 3 chuyển kiểm tra sang lúc dịch (`Literal` + `mypy --strict`) thay vì lúc chạy. Hai bản sửa
phát sinh cũng đúng gốc: `e44e791` luồn một `admin_id` duy nhất từ `main()` xuống cả seed lẫn header thay vì
vá từng route, `950a791` khoanh việc tắt bộ ghi golden vào đúng case duy nhất mồi thân giả. Ba kiểm riêng đều
âm tính: không mất vết case C10, không rò phạm vi `monkeypatch`, không để lại dữ liệu seed ảnh hưởng H2.

Cổng đầy đủ chạy một lượt foreground, **mã thoát 0, 8/8 đạt** — kể cả bước 5b `case_gate` (NO-129 nay có bằng
chứng) và bước 7 H1 với 186 mẫu (bỏ mẫu giả C10 không làm hụt mẫu 2xx của op nào). Không P0/P1/P2/P3; điểm
4,97/5 ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

Việc của phiên gọi review khi merge (không phải điều kiện để `APPROVE`):

1. Squash rồi viết lại thân theo Nit 4 của lượt 1 — nêu đủ **25 hàng** cột Khoá có backtick, không chỉ
   `project.create`.
2. Đóng **NO-126, NO-127, NO-128, NO-129, NO-131, NO-132, NO-133, NO-134** trong `DEBT.md` (đang là `đang sửa`).
3. Hai Nit ở trên: ghi thành việc nhỏ cho B0-09 và B0-01, hoặc bỏ qua — không chặn.
