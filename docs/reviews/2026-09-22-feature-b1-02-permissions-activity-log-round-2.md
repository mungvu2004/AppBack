# Review merge feature/b1-02-permissions-activity-log → main (lượt 2)

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, lượt 2. Phiên này không viết mã và không làm merge: mã do W1, D, E, F viết, M gộp và tự review lượt 1. Mọi khẳng định trong `bao-cao-B1-02.md` và `DEBT.md` đều được kiểm lại bằng diff và bằng cổng tự chạy · Commit đầu nhánh: `abfc0ad2a7c2` (cha `88e36b3`, tức commit lượt 1 duyệt; fast-forward từ `feature/b1-02-project-id-check`) · merge-base với `main` = `4d3df23`. `main` đã đi thêm tới `07ab214` (`bf50968` B0-08 `deploy/`, `.dockerignore`, `changes/B0-08.md`, cùng các commit sổ nợ và review). `git merge-tree --write-tree main abfc0ad` sạch, và hai bên không chạm chung đường nào.
- Phạm vi soát kỹ lượt này: `git diff 88e36b3..abfc0ad`, gồm 2 tệp, +38/−3: `apps/api/access/activity.py`, `apps/api/access/tests/test_activity.py` (sửa NO-100). Điều kiện dừng sớm, cổng và phần kiểm xem kết luận lượt 1 còn đứng không thì chạy trên toàn `main...abfc0ad` (19 tệp mới, +1 474).
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, chạy tại chỗ trên `abfc0ad` (worktree `b1-02-m-merge` sạch trước và sau, lúc khởi động có 0 container `verify-run`). Log host là `.cache/src-out/verify/20260922T091843Z-abfc0ad2a7c2.log`, có bản sao `docker logs -f` của `appback-verify-b1-02-m-merge-verify-run-c3fd8cbc38fd` ở scratchpad của phiên. Kết quả `2210 passed, 10 skipped, 1 deselected` (278 s): `test_activity.py` 23 qua, `test_deps.py` 19, `test_matrix.py` 14, `test_jobs.py` 4, `test_kinds.py` 6, `test_boundary.py` 2. Số liệu khớp `verify-dieu-phoi-2.log` của người điều phối (`EXIT=0`, 2210 qua).
- Độ phủ: tổng dòng **99,36 %** · nhánh **97,52 %**; `apps/api/access` 100 · 100; `packages/domain` 100 · 100; `packages/testing` 99,16 · 100; `packages/db` 98,84 · 97,22; tập file bị chạm 100 · 100.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (353 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (300 file) |
| 4 | `lint-imports` | đạt (9 giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm; `auth_*` đủ case) |
| 6 | `lint_migrations` → `migrate_check` | đạt (5 revision; 10/10, có "model khớp DB" và "tên CHECK khớp model") |
| 7 | H1 H3 H4 H5 | đạt: **H3 đạt, 10 khoá × 3 vai**; H4/H5 `không áp dụng` hợp lệ vì B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill, toàn nhánh)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (trước và sau verify) |
| `changes/B1-02.md` | có, 9 dòng |
| Dòng đầu Conventional Commits ≤ 72 | đạt: 6 commit, dài nhất 65 ký tự (`fd8880b`) |
| Trailer `Prompt:` | 6/6 đọc được `B1-02` qua `%(trailers:key=Prompt,valueonly)`, kể cả `abfc0ad` và merge `88e36b3` |
| Đụng file cấm ([12] prompt, B0-01 [7]) | không: 19 tệp đều `A`, đều thuộc `so_huu` + revision của khối [10]. Chênh lượt 2 chỉ gồm 2 tệp của `apps/api/access` |
| `pragma` / `type: ignore` không mã / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | không: 4 `type: ignore[...]` đều có mã, 1 `noqa: S603` có mã và lý do. Chênh lượt 2 không thêm cái nào |
| `conftest.py` lồng, file cấu hình công cụ riêng | không |

## Kiểm phần chênh `88e36b3..abfc0ad` (NO-100)

| Khẳng định (commit `abfc0ad`, `DEBT.md` NO-100) | Kết quả | Bằng chứng |
|---|---|---|
| `record_activity` từ chối `project_id` sai mẫu **trước** `db.add` | **đúng** | `activity.py:34-37` `_check_project_id`: `None` hoặc `is_id("prj", …)` (W4, BE-00 §3); gọi ở `:61`, trước `_normalized` và `db.add` (`:64`). `is_id` dùng `fullmatch` trên thân ULID HOA 26 ký tự (`packages/core/ids.py:55-68`), nên `\n` cuối chuỗi, chữ thường và tiền tố khác đều bị chặn |
| Sửa ở gốc, không vá theo từng đường (R-19) | **đúng** | Mọi chủ route ghi nhật ký đều đi qua `record_activity`. Hiện chưa có caller nào ngoài test (`grep record_activity` trên `apps`, `packages`), nên không có caller nào vỡ |
| Test âm đủ 4 dạng, và đỏ trước khi sửa | **đúng** | `test_activity.py:128-152`: rác, rỗng, `prj_123`, `usr_<ULID>`. Bản trước sửa không kiểm, và DB không có CHECK cho `project_id`, nên cả 4 `pytest.raises` đều phải hỏng. Con số "4 failed / 19 passed → 23 passed" khớp số test của tệp (23 qua trong lượt verify này) |
| Test đường thường không còn dùng id rác | **đúng** | `:32`, `:40`, `:47`: `new_id("prj", fake_clock)` thay `"prj_test"` và khẳng định giá trị đọc lại. Nhánh `None` vẫn được `test_record_activity_project_id_defaults_to_none` phủ |
| Giữ bất biến của lượt 1 | **đúng** | Vẫn không `commit` (test rollback xanh). Không nhập thêm module nào (`packages.core.ids` đã nhập từ trước), nên `test_boundary.py` 2/2 xanh khi chặn `fastapi`/`starlette`/`jwt`/`argon2`. Không đụng model, migration, `deps`, `jobs`. `apps/api/access` vẫn 100 · 100 |

**Kết luận lượt 1 vẫn đứng.** Phần chênh chỉ thêm một phép kiểm thuần, chạy trước lần ghi duy nhất. SEC (vai chỉ từ `CurrentPrincipal`), CON (không commit, purge theo lô, chạy lặp vô hại), PERF, DB (expand thuần, có down, `migrate_check` 10/10) và TEST (dịch vụ thật, `FakeClock`, J01/J06) không đổi. Chỉ LOG khác đi: finding #3 lượt 1 đã đóng.

## Đánh giá bốn chỗ lệch khỏi prompt tác giả tự khai

| Lệch | Đứng được? | Lý do |
|---|---|---|
| (1) `require_role(...)` khác admin mang khoá `role:<…>`; lỗi bị `test_routes.py:73-80` bắt ở bước 5, không phải `ValueError` lúc khai | **có** | Lúc gọi `require_role`, dependency chưa biết route nào sẽ dùng nó. Muốn ném lúc khai thì phải móc vào khung route của B0-06, và khối [12] cấm sửa `apps/api/core/**`. Bước 5 chặn trước mọi merge. `test_role_key_on_bind_route_fails_the_route_scan` chốt hành vi. NO-098 `➖` có đường nâng cấp |
| (2) `PERMISSION_KEYS` theo object literal `permissionMatrix` của FE, không theo thứ tự bảng [2] | **có** | Chính khối [2] ghi "`PERMISSION_KEYS` … (thứ tự của FE)". Đã mở `F:/AppFront` @ `9cf0b0b` (= `APPFRONT_SHA`): `permissions.ts:90+` xếp theo bảng chữ cái, khớp `matrix.py:31-42`. 30 ô trùng bảng [2]. H3 đạt trong lượt verify này |
| (3) `Role`/`PermissionKey` khai lại ở domain | **có** | [2] đòi `ROLES: tuple[Role, ...]` ở domain; [9] cấm domain nhập gì ngoài `packages.core`, mà `Role` gốc nằm ở `apps/api/core/auth.py`. NO-097 giữ việc gom về một chỗ (hướng `apps → domain` hợp lệ). Finding #2 lượt 1 vẫn còn |
| (4) `record_activity` kiểm thêm `project_id` | **có** | W4 (BE-00 §3) chốt `prj_<ULID>`, và hiến chương đứng trên prompt. Phép kiểm này cùng khuôn với `actor_id` ở khối [6] và fail-closed (R-17) |

## Kiểm sổ nợ

| Nợ | Kết quả |
|---|---|
| NO-097 (Nit, `⬜`, B0-06) | có trên `main`, đủ cột; ứng với #2 lượt 1 |
| NO-098 (P3, `➖`) | lý do đứng được (xem lệch 1) |
| NO-099 (P3, `⬜`, AppFront) | có; prompt cấm sửa FE ở đây |
| NO-100 (P3, `✅`) | **phần sửa là thật** (bảng trên), nhưng ghi chép còn sót, xem #8 |
| P0/P1 mở | không có |

## Finding

Finding lượt 1: #1 đã rút lại; **#3 đã đóng** nhờ `abfc0ad`; #2 (P3), #4, #5, #6 (Nit) vẫn còn hiệu lực. Vị trí của #4 dời sang `apps/api/access/tests/test_activity.py:164`, vị trí của #6 sang `packages/testing/fixtures/access.py:50`. Dưới đây là finding mới, đánh số tiếp từ #7. #9 và #10 nằm ngoài phần chênh: lượt 1 bỏ sót, phiên này thấy khi đọc lại toàn diff.

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 7 | Nit | R-06 · MNT-03 | `_check_project_id` viết lại gần như nguyên `check_id` của lõi (`packages/core/ids.py:71-79`: `is_id` sai thì ném `ValueError`), chỉ thêm nhánh `None`. Cách này vẫn nhất quán với `_check_actor_id` bên cạnh và giữ tên trường trong thông báo lỗi (test khớp `"project_id"`) | `apps/api/access/activity.py:34-37` | Giữ nguyên cũng được. Nếu muốn dùng lại lõi: `if project_id is not None: check_id("prj", project_id)`, và đổi `match=` của test |
| 8 | Nit | R-34 | Dòng NO-100 trên `main` đã tích `✅` trước khi bản sửa vào `main`. Ô ghi chú vẫn mở đầu bằng "đang sửa — …", và commit sửa được ghi là sha nhánh `abfc0ad` "(trước squash)". Sau squash sha này không có trên `main`, nên mất đường tra | `DEBT.md:120` (`main`) | Ngay sau squash: người điều phối thay `abfc0ad` bằng sha squash trên `main`, và viết lại ô ghi chú theo khuôn `mở — … · **đóng** — <sha>: …` như NO-006 |
| 9 | P3 | LOG-06 | `assert_one_activity` nhận `async_sessionmaker` làm tham số đầu, trong khi khối [6] khai `assert_one_activity(db, *, actor_id, kind, object_code)`. Lý do có trong docstring của module: dòng do app commit phải đọc trên session mới. Chỗ lệch này **không** có trong "Lệch khỏi prompt" (`bao-cao-B1-02.md:108-118`), dù helper này là hợp đồng mà 9 prompt sau nhập (B1-05, B2-01..04, B3-04, B3-05, B6-01..03a, khối [3]). `mypy --strict` bắt được nếu ai truyền `AsyncSession`, nên tác động thấp | `packages/testing/fixtures/access.py:61-63` | Không cần sửa mã. Thêm một dòng "Lệch khỏi prompt" vào báo cáo B1-02 (chữ ký nhận `db_sessionmaker`, kèm lý do), để chủ route đọc báo cáo biết mà truyền đúng fixture |
| 10 | Nit | MNT-04 | Docstring ghi "đúng thứ tự `permissions.ts:19-29`", nhưng dòng 19-29 là union `PermissionKey`, thứ tự khác (`project.create` đứng đầu). Nguồn thứ tự thật là object literal `:90-141`, đúng như docstring của module và của `matrix.py` | `packages/domain/permissions/tests/test_matrix.py:50` | Sửa thành `permissions.ts:90-141` |

Không có nợ mới từ P2 trở lên. #9 là P3, nên chỉ cần ghi vào báo cáo, không bắt buộc có dòng `DEBT.md`.

## Điểm

Nit không trừ điểm.

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #9; #3 lượt 1 đã đóng) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #5 lượt 1) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #2 lượt 1 = NO-097; Nit #4, #6, #7, #10) | 0,12 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,12 = **4,82 / 5**

## PHÁN QUYẾT: APPROVE

Phần gộp thêm mà lượt 1 đặt làm điều kiện (NO-100, `abfc0ad`) là sửa thật và sửa ở gốc. `project_id` sai mẫu bị chặn bằng `ValueError` trước `db.add`, có 4 test âm, và bất biến nào của lượt 1 cũng không bị phá. Cổng do phiên này tự chạy trên đúng `abfc0ad` thoát 0: 8/8 bước đạt, 2210 qua, H3 đạt, 99,36 % / 97,52 %, `apps/api/access` và `packages/domain` 100 · 100. Không có P0/P1 và điểm ≥ 4,0, nên theo `RULE.md` §5 phán quyết là APPROVE. Cả bốn chỗ lệch tác giả tự khai đều đứng được.

Không có điều kiện nào chặn merge. Khi merge:
1. Gộp **squash** vì nhánh chỉ có một prompt (R-36). Thân commit có `Prompt: B1-02` trong khối trailer đúng R-36b.
2. Sau squash, người điều phối cập nhật sha của NO-100 trong `DEBT.md` (#8).
3. Chạy verify tích hợp trên `main` sau khi gộp: `main` đã có `bf50968` mà lượt verify này không chứa. Trước đó xuất `openapi.json` ra gốc, vì bước 8 trên `main` có so.
4. Các P3/Nit #7, #9, #10 do tác giả hoặc người điều phối quyết; #9 chỉ cần thêm một dòng vào báo cáo.
