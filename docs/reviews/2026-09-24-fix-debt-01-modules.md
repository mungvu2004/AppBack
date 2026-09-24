# Review merge `fix/debt-01-modules` → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worktree `review-debt-01-modules`) · Commit đầu nhánh: `6caadb852c11`
- Phạm vi: `git diff 361db93...6caadb8`: 4 commit, 14 file, +362/−38. Mỗi commit một chủ (K27 đạt):
  FIX-093 B1-03 (`19fbed6`) · FIX-094 B2-01 (`672b44b`) · FIX-095 B2-05a (`c3e32b7`) · FIX-096 B4-01 (`6caadb8`).
- Cổng: `bash tools/verify/run.sh verify` (một lượt, đầy đủ): **mã thoát 0**
  (log: `backend/dieu-phoi/chay/DEBT-01/r4-verify.log`, bản trong container `.cache/src-out/verify/20260924T132606Z-6caadb852c11.log`)
- Độ phủ (`coverage_gate`): tổng dòng **99,08 %** · nhánh **97,85 %**.
  Từng gói bị chạm: `apps/api/auth_recovery` 97,34 / 94,64 · `apps/api/projects` 98,45 / 97,67 ·
  `apps/api/streams` 100 / 100 · `packages/vision` 100 / 100 · tập file bị chạm 98,17 / 94,59.

## Bảng E.10: lấy từ mã thoát thật

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 3764 passed, 4 deselected, 0 failed, 834 s (một tiến trình) |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf 3 test; 25 thao tác đã mount, 3 cảnh báo |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H4 "không áp dụng" (B3-05 chưa hợp nhất, đúng BE-00 §12) |
| 8 | `openapi` | đạt | |

Mã thoát cổng: **0**. `git status --porcelain` rỗng trước và sau.

## Kiểm độc lập (không dựa vào báo cáo tác giả)

Chạy trong container cổng (`run.sh shell`, bản chép `/tmp/w`, không động tới worktree). Chỉ hoàn nguyên
**file sản phẩm** về `361db93`, giữ test mới, chạy đúng test đó; sau đó chép lại bản nhánh rồi chạy lại
(log `backend/dieu-phoi/chay/DEBT-01/r4-redgreen.log`).

| Nợ | Test | Đỏ trên `361db93` | Xanh trên nhánh |
|---|---|---|---|
| NO-149 | `test_jobs.py -k "logs_isolated_failure_before_later_transient or J03"` | mã thoát **1**, 2 failed | mã thoát 0, 2 passed |
| NO-142 | `test_summaries.py -k touch_projects` | mã thoát **1**, 1 failed (`…locks_then_updates_ids_in_sorted_order`) | mã thoát 0, 2 passed |
| NO-135 | `test_wire.py` (hoàn nguyên `wire.py` + `service.py`) | mã thoát **1**, 4 failed (đổi chữ ký `user_out`) | mã thoát 0, 10 passed |
| NO-158 (Nit 2) | `test_registry.py -k default_providers_without_policy` | mã thoát **1**, 1 failed (`DID NOT RAISE`) | mã thoát 0 |
| NO-136 | `test_service.py` | test chỉ phủ nhánh, không có lượt đỏ (đúng như báo cáo) | mã thoát 0 |

Thêm: đo phủ `packages/testing/fixtures/streams.py` qua **toàn bộ** `apps/api/streams/tests` (118 passed;
đây là thư mục test duy nhất dùng `sse_open`): **Miss = dòng 156**, 1 nhánh thiếu. Dòng 174, 187, 211 đã phủ
(log `r4-cov156.log`). Xem finding 1.

- **K23**: không mock Postgres/Redis/Mailpit. Test NO-136/142/149 chạy Postgres thật, NO-158 chạy Redis
  thật (`streams_client` có `_flushed`, 40 khoá đệm không rò sang test khác).
- **NO-155**: không sửa `packages/testing/fixtures/streams.py`. Tác giả hạ `_OPEN_TIMEOUT_S` bằng
  monkeypatch (theo khuôn `test_disconnect_times_out_when_the_app_never_exits` có sẵn) và dùng predicate
  luôn sai. Cách này tất định: lối ra duy nhất của vòng là `raise TimeoutError`. Nó cũng đúng ý dòng nợ
  ("ép hạn hết giữa hai lượt kéo"): `timeout_s = _POLL_TICK_S = 0,2`, lượt kéo đầu hết hạn rồi vòng quay
  lại với `remaining ≤ 0`. Không cần tiêm đồng hồ vào fixture. Nhưng dòng 156 chưa được phủ (finding 1).
- **NO-142, thứ tự khoá**: `SELECT … ORDER BY id FOR UPDATE` của Postgres khoá dòng **sau** nút Sort
  (LockRows nằm trên Sort), nên các dòng bị khoá theo đúng `id` tăng dần. `UPDATE` theo sau chỉ lấy lại
  khoá đang giữ. Sửa đúng gốc.
- **NO-135**: `apps/api/me/**` không bị sửa, chỉ nhập `apps.api.me.avatar.avatar_url` (hàm công khai,
  truyền `kind`, không `stat`). `lint-imports` đạt.
- **K27**: đã tra `tao_so_tra.py --chu` cho file của từng commit, mỗi commit chỉ chạm file của đúng một chủ.
  Dòng đầu các commit đúng Conventional Commits, trailer `Prompt:`/`Fix:`/`Co-Authored-By:` liền nhau.
  `changes/DEBT-01.md` có.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-01 / R-19 | NO-155 mới đóng **3/4** nhánh. Dòng nợ ghi rõ bốn dòng 156, 174, 187, 211. Ba test mới phủ 174, 187 (`_await_start`) và 211 (`raw_until`). Dòng **156** (`_pull`: app ASGI thoát mà không gửi thêm message → `RuntimeError`) vẫn chưa có test: đo trên toàn `apps/api/streams/tests` thì `Miss 156`. Báo cáo tác giả §1 và §6 ghi "bốn nhánh… đã đóng", điều này sai. | `packages/testing/fixtures/streams.py:156` ↔ `apps/api/streams/tests/test_fixture_streams.py:222-384` | Thêm một ca: app gửi `http.response.start` kiểu `text/event-stream` rồi `return` (không gửi thân). `next_frames(1)` phải ném `RuntimeError("…kết thúc mà không gửi thêm…")`. Nếu không thêm thì thu hẹp NO-155 về dòng 156, không đánh dấu `✅`. |
| 2 | P3 | TEST-01 / R-17 | NO-135 chỉ được chứng minh ở mức đơn vị, với kho giả. Dây thật `request.app` → `_storage_of(app)` → `app.state.storage` không có test route nào có `avatar_key` và mong `avatarUrl` xuất hiện. `_storage_of` dùng `getattr(…, None)` hai tầng: app thật mà thiếu hay đổi tên `state.storage` thì hàm lặng lẽ trả `None`, ảnh đại diện biến mất khỏi dây trong khi mọi test vẫn xanh. Docstring `test_routes_build.py:91` ("không `avatarUrl` (B1-04 chưa cắm)") nay đã sai. Test đó vẫn đạt chỉ vì factory không đặt `avatar_key`. | `apps/api/projects/service.py:100-108`; `apps/api/projects/tests/test_routes_build.py:91,104` | Thêm test route (`api_client` + kho local của app): đặt `avatar_key` cho một thành viên, `GET /api/projects` phải trả `avatarUrl`. Khi `app is not None` thì đọc `app.state.storage` thẳng như `deps.storage` (hỏng thì ném ngay). Sửa docstring ở `:91`. |
| 3 | P3 | CON-01 / TEST-06 | Test NO-142 chỉ kiểm **hình dạng SQL**: có 2 câu, câu đầu chứa `FOR UPDATE` và `ORDER BY`. Không có test hai giao dịch chứng minh hết khoá chéo. Ngoài ra "guard lô rỗng" mà prompt [6] giao (Nit 2 của NO-142, `count_projects_of_users`) **chưa làm**, vì `memberships.py` nằm ngoài whitelist của spec. Guard trong `touch_projects` là guard có sẵn từ trước, test mới cho nó đạt cả trên `main`. | `apps/api/projects/tests/test_summaries.py:239-268`; `apps/api/projects/memberships.py:115-126` | Nợ mức Nit nên không chặn merge. Giữ NO-142 mở cho phần `memberships.py` (hoặc tách dòng mới, chủ B2-01), kèm đề nghị một test hai session gọi `touch_projects` với thứ tự id ngược nhau. |
| 4 | Nit | OBS-01 | Một token hỏng giờ sinh **hai** bản ghi `token_mail_failed` cùng tên nhưng khác dạng: `token_id` + `smtp_code` lúc cô lập, và `token_ids` của cả lô ở `on_failed` khi `PermanentError` nổi lên. Luật cảnh báo đếm theo tên sự kiện sẽ đếm đôi. | `apps/api/auth_recovery/jobs.py:65-78,131-134` | Đặt tên riêng cho log cô lập (vd `token_mail_isolated`), hoặc ghi rõ trong docstring rằng `on_failed` là bản tóm tắt của lô. |
| 5 | Nit | TEST-08 / R-07 | Test NO-149b khai fixture `memory_mailer` nhưng ngay sau đó đè `create_mailer` bằng `_TransientMailer`, nên fixture thừa. J02 cùng file đã có đường lỗi tạm thời **thật** (`refused_url("smtp")`) mà test mới dùng lại được. Tương tự, `_FakeAvatarStorage` tự viết trong `test_wire.py`, trong khi đã có fixture `local_storage` (`LocalDiskStorage` thật) mà test của B1-04 dùng (`apps/api/me/tests/test_avatar_unit.py:259`). | `apps/api/auth_recovery/tests/test_jobs.py:223,248-252`; `apps/api/projects/tests/test_wire.py:27-40` | Bỏ `memory_mailer` và dùng SMTP bị từ chối như J02. Dùng `local_storage` thay kho giả. |
| 6 | Nit | R-01 (CASE tên) | Luật chung của spec yêu cầu tên `test_<hàm>__<điều kiện>`. Test mới dùng một gạch dưới: `test_write_changes_raises_not_found_when_…`, `test_touch_projects_…`, `test_user_out_…`, `test_raw_until_times_out_…`, `test_await_start_times_out_…`, `test_default_providers_without_policy_…`, `test_render_pdf_page_wraps_…`. Theo đúng lối cũ của từng file, `case_gate` không bắt. | các file test trong diff | Đổi tên khi chạm lại file. |

Không tìm thấy các vi phạm sau: file cấm bị đụng (`docs/charter/*`, `openapi.json`, `uv.lock`, `pyproject.toml`,
`DEBT.md`, `apps/api/me/**`, `apps/api/floors/**`), `conftest.py` lồng, `# pragma: no cover`,
`type: ignore` trần (các `type: ignore` mới đều có mã: `[attr-defined]`, `[import-untyped]`, `[operator]`),
`skip`/`xfail`, hạ ngưỡng. Nhánh 362 dòng thêm, phần lớn là test, dưới ngưỡng MNT-05.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---:|---:|---:|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 4 | 0,60 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 5 | 0,15 |
| **Tổng** | **100%** | | **4,78 / 5** |

## Từng NO đóng được khi merge không

| NO | FIX | Đóng khi merge? | Bằng chứng / lý do |
|---|---|---|---|
| NO-125 | FIX-095 | ✅ có | Test `test_render_pdf_page_wraps_pdfium_error_raised_inside_open_page` (monkeypatch `PdfPage.render`), dòng dài ở `test_geometry.py:121` đã bọc lại. Chỉ phủ nhánh nên không có lượt đỏ. `packages/vision` 100/100. |
| NO-135 | FIX-094 | ✅ có (kèm nợ mới 2) | `user_out` ký qua `apps.api.me.avatar.avatar_url`. Đỏ 4 failed → xanh 10 passed. Đỏ do đổi chữ ký, không do assert. Dây route chưa có test (finding 2). |
| NO-136 | FIX-094 | ✅ có | Test hai session xen kẽ `test_write_changes_raises_not_found_when_deleted_between_gate_and_update` qua Postgres thật. Chỉ phủ nhánh. Riêng đường #27 (`delete_project`, `service.py:325`) không có test đua tương tự; dòng nợ không đòi. |
| NO-142 | FIX-094 | ⚠️ một phần | Phần `touch_projects` đạt: đỏ → xanh, thứ tự khoá đúng. Nit 2 (guard lô rỗng `count_projects_of_users`, `memberships.py`) chưa làm → giữ dòng mở hoặc tách dòng (finding 3). |
| NO-149 | FIX-093 | ✅ có | (a) `smtp_code` 550 có trong log J03. (b) log lúc cô lập, không bị `TransientError` sau nuốt mất. Nit: `Mailer`, `ORDER BY created_at`. Đỏ 2 failed → xanh 2 passed. |
| NO-155 | FIX-096 | ⚠️ một phần | Dòng 174, 187, 211 đã phủ, tất định. Dòng **156** vẫn `Miss` trên toàn `apps/api/streams/tests` (finding 1). Chưa được đánh dấu `✅`. |
| NO-158 | FIX-096 | ✅ có | `default_providers()` qua `_check`: đỏ `DID NOT RAISE` → xanh. Seed 43 khoá với `BATCH=3` ép `SCAN` quay nhiều lượt; `apps/api/streams` 100/100 nhánh trong cổng. |

## Nợ

Nợ mới cần dòng trong `DEBT.md` (người điều phối mở, chủ ghi trong ngoặc):

1. **P3**: NO-155 còn dòng `packages/testing/fixtures/streams.py:156` chưa test (B4-01). Thu hẹp NO-155 hoặc mở dòng mới.
2. **P3**: dây `avatarUrl` qua `app.state.storage` không có test route, `_storage_of` lặng lẽ trả `None`, docstring `test_routes_build.py:91` sai (B2-01) (finding 2).
3. **Nit**: phần còn lại của NO-142: guard lô rỗng `count_projects_of_users` và test hai giao dịch (B2-01) (finding 3).
4. **Nit**: log `token_mail_failed` trùng tên hai dạng (B1-03) (finding 4); fixture thừa, kho giả tự viết (B1-03, B2-01) (finding 5).

## PHÁN QUYẾT: APPROVE

Cổng đầy đủ thoát 0 trong một tiến trình, không có test phụ thuộc thứ tự lộ ra. Độ phủ tổng và từng gói bị chạm
đều ≥ 90 % cả dòng lẫn nhánh. Mọi sửa hành vi đều có test đỏ trên `361db93` → xanh trên nhánh, reviewer đã
chạy lại. Không có P0/P1/P2, điểm 4,78/5. Nhánh được merge. Khi cập nhật `DEBT.md`, người điều phối
**không** được đánh dấu `✅` cho NO-155 và NO-142 (xem bảng trên) và cần mở các dòng ở mục Nợ.
