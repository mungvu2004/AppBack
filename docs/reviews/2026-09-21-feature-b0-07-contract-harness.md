# Review merge feature/b0-07-contract-harness → main

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, chưa từng thấy mã trước lượt này; mọi khẳng định trong commit, `changes/B0-07.md`, `DEBT.md`, `docs/fixes.md` đều tự kiểm lại) · Commit đầu nhánh: `d3b25b03a1f8` (gốc `267e8f7`, 2 commit: `fc01234` B0-07, `d3b25b0` FIX-028 cho B0-06). `main` đi thêm một commit `3bbfe19` (chỉ `docs/fixes.md`); `git merge-tree` sạch, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong worktree sạch của nhánh, log `verify.log` trong scratchpad của phiên): `1279 passed, 10 skipped`. Cả 10 skip đều là `apps/api/core/tests/test_common.py` (tập tham số rỗng, có từ B0-06, nhánh không chạm), đúng ngoại lệ BE-00 §12 cho phép.
- Độ phủ: tổng dòng **99,30 %** · nhánh **96,99 %** · `packages/testing` 99,65 % / 100 % · `tools` 98,65 % / 94,91 % · tập file bị chạm 99,85 % / 99,32 %. Mọi gói bị chạm và tổng đều ≥ 90 % ở cả hai số.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (205 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (179 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; 3 cảnh báo cho ba route miễn) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | **đạt** — lần đầu áp dụng thật (có `changes/B0-07.md`) |
| 8 | openapi | đạt |

Bảng con của bước 7 (AppFront @ `9cf0b0bfffbd166395155abfa127099921db5a32`, 4,0 s, dựng runner 3,1 s — lượt ấm):

| Kiểm | Trạng thái | Chi tiết |
|---|---|---|
| Smoke | đạt | 23 module schema, 83 mục bản đồ |
| Bản đồ đủ | đạt | 83 mục / 83 dòng BE-BIND không v2 |
| Thao tác đã mount | đạt | 3 / 83 (ba route miễn) |
| H1 | đạt | 0 mẫu response (chưa route nghiệp vụ nào) |
| H1 ngữ cảnh | đạt | 0 mẫu |
| H3 | không áp dụng | B1-02 chưa hợp nhất — hợp lệ BE-00 §12 |
| H4 | không áp dụng | FE đúng 25 mã; B3-05 chưa hợp nhất — hợp lệ |
| H5 | không áp dụng | S1/S2 chưa mount, B4-01 chưa hợp nhất — hợp lệ |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B0-07.md` tồn tại | đạt — 8 dòng (BE-00 §13.2: 3–10) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — `feat(contract): …` 57 ký tự, `fix(api): …` 67 ký tự |
| Trailer đọc được bằng `%(trailers:key=Prompt)` | đạt — `fc01234` → `B0-07`; `d3b25b0` → `B0-06` + `Fix: FIX-028`; khối trailer liền nhau, có dòng trống trước (R-36b) |
| Đụng `docs/charter/*`, `openapi.json`, `uv.lock`, `pyproject.toml` gốc, `.importlinter`, `conftest.py`, `tools/verify/*`, `tools/charter.py`, `tools/case_gate.py`, `deploy/**`, `apps/**` | không |
| `tools/contract/APPFRONT_SHA` | **có tạo mới — không phải vi phạm**: đây là deliverable của B0-07 ([2] "Bạn ghi lần đầu, sau đó chỉ người điều phối nâng", [10]). Tự kiểm: giá trị = `git -C F:/AppFront rev-parse master` (`9cf0b0b`, "Merge: F-00c"); `git branch -r --contains` → `origin/master` (CI checkout được); F-00a/b/c có đủ — smoke nhập được cả 23 module và 83 mục |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — hai `noqa` mới đều có mã và lý do (`S105` ở `recorder.py:36`, `S603` ở `runner_client.py:94`) |
| `conftest.py` lồng, file cấu hình công cụ riêng | không |
| `contract-samples/` bị commit | không (`.gitignore:21`) |

**Phạm vi sở hữu.** Commit `fc01234` chỉ chạm đúng cột `so_huu` của prompt (`tools/contract/**`, `packages/testing/golden/**`, `packages/testing/fixtures/golden.py`, `changes/B0-07.md`); không đụng mục nào ở [12]. Commit `d3b25b0` (FIX-028, cấp phép ở `docs/fixes.md:146-161`, spec `:223-228`) chạm `packages/testing/fixtures/api.py` (đúng [4]), `DEBT.md` (đổi `NO-044` → ✅ trong chính commit sửa, đúng luật chung FIX) và `packages/testing/golden/tests/test_recorder.py` (xem Nit #11).

**Công cụ kiểm tại chỗ** (container verify, Python 3.12, Node 20; file probe chỉ nằm trong bản sao `/tmp/w`, không vào repo):

- **P1** — khung SSE của S1 có `startedAt = "2026-01-01T07:00:00.000000+07:00"`: runner giải `ok`, **H5 `đạt`**. Cùng thân đó đi qua HTTP (`drawings_read_progress`) → H1 `hỏng` "không kết thúc .sssZ (W3)". Xem #3.
- **P2** — `build_layout(…, build_dir=<thư mục có sẵn chứa giu.txt>)` → `giu.txt` **mất**. Xem #4.
- **P3** — giả lập prompt W05 đầu tiên: `auth_refresh` mount đúng đường BE-BIND, chạy `check.main` đúng như `test_real_repo_check_passes` (thư mục mẫu rỗng của riêng test) → H1 `hỏng` "auth_refresh: đã mount mà không có mẫu 2xx nào", **`main()` trả 1**. Xem #1.
- **P4 — đỏ trước khi sửa của FIX-028:** đặt lại `packages/testing/fixtures/api.py` bản `main` (còn `_op_matchers`), chạy hai test mới của FIX-028 → **`5 passed`**. Xem #6.
- **AST** trên 18 file `.py` của diff: 0 hàm/lớp/module thiếu docstring; không hàm nào > 50 dòng; lồng thật ≤ 3 cấp. Dòng logic (bỏ trống, comment, docstring): **660** Python sản phẩm + **350** TypeScript, **914** test.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | TEST-02 · R-19 | **Test khói chốt trạng thái repo hôm nay thành bất biến — cùng lớp lỗi FIX-003.** `test_real_repo_check_passes` chạy `check.main` trên app thật với `CONTRACT_SAMPLES_DIR` là thư mục **rỗng của riêng test**, rồi đòi mọi kiểm `đạt`/`không áp dụng`. Hôm nay qua được chỉ vì app chưa có route nào có thân. Prompt W05 đầu tiên mount một route có thân (vd `auth_refresh` của B1-01) thì H1 hỏng "đã mount mà không có mẫu 2xx nào", **dù golden C01 của chính route đó đã ghi đúng vào `/tmp/contract-samples` thật** — probe P3: `main()` trả 1. Hệ quả: bước 5 của nhánh B1-01 (và mọi nhánh W05 sau) đỏ vì một file của B0-07, mà worker đó không được sửa (K27) → người điều phối lại phải mở FIX như FIX-003 (`docs/fixes.md:59-63`: "`operations()` … khác rỗng ngay khi có prompt đầu tiên mount route"). Tác giả làm đúng chữ prompt [8] ("trên `main` hiện tại → mọi kiểm `đạt` hoặc `không áp dụng`"), nhưng chữ đó trái bài học CASE §2.3 mà hiến chương đã chốt | `tools/contract/tests/test_check.py:450-461` | Giữ phần ổn định theo thời gian: `main` chạy trọn (thoát 0 hoặc 1, không ném), in đủ 8 dòng, trạng thái ∈ {`đạt`, `hỏng`, `không áp dụng`}; ba kiểm cấu trúc không phụ thuộc mẫu (`Smoke`, `Bản đồ đủ`, `Thao tác đã mount`) phải `đạt`. H1–H5 trên dữ liệu thật đã do chính bước 7 đòi. Ghi một dòng "Lệch khỏi prompt" cho [8] |
| 2 | P2 | MNT-05 | Nhánh thêm ≈ 1 010 dòng logic sản phẩm (660 Python + 350 TS) và 914 dòng test, vượt 400. **Không đáng tách:** một prompt; runner Node, bản đồ, bộ ghi, `check.py` và test của chúng móc vào nhau (test nào cũng cần runner thật) | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` chấp nhận như `NO-039` |
| 3 | P3 | LOG-06 · W3 | Luật ngày giờ W3 chỉ chạy trên mẫu HTTP (`check_h1`), **không** chạy trên khung SSE (`check_h5`). `ProgressSchema` dùng `isoDateTimeSchema` cũ, nhận cả 6 chữ số và `+07:00` (chính lý do `bad_datetimes` tồn tại, `samples.py:83-88`), nên zod không bắt thay. Probe P1: khung S1 lệch W3 → H5 `đạt`, cùng thân qua HTTP → H1 `hỏng`. Không nâng P2 vì S1 dùng cùng `progress_wire` với #8 mà H1 đòi đủ 4 nhánh, nên lỗi của bộ tuần tự hoá chung vẫn bị bắt ở HTTP; còn hở khi luồng dựng thân riêng | `tools/contract/check.py:252-265` (so với `:208`) | Trong `check_h5`: `problems += [f"{e.file}: {bad}" for e in inputs.events for bad in bad_datetimes(e.body, "event")]`; thêm một test H5 với `+07:00` |
| 4 | P3 | LOG-04 · R-16 | `build_layout` mở đầu bằng `shutil.rmtree(build_dir, ignore_errors=True)`: (a) xoá **bất kỳ** thư mục nào `--build-dir` trỏ tới mà không hỏi — probe P2; gõ nhầm `--build-dir tools/contract` là mất nguồn harness; (b) nuốt lỗi xoá, nên file cũ sót lại có thể lọt vào bố cục mới (schema FE đã bị xoá ở SHA mới vẫn nhập được → smoke `đạt` giả). Cùng lớp `NO-008`, `NO-012`. Trong cổng thì `/tmp` mới mỗi container nên chưa gây hại | `tools/contract/runner_client.py:169` (cạnh `:144`) | Dựng vào `tempfile.mkdtemp()` mới mỗi lượt (bỏ `--build-dir`, hoặc chỉ nhận thư mục **chưa có**/rỗng); `rmtree` không `ignore_errors` để lỗi nổi lên. `:144` giữ được nhưng nên đổi thành `if staging.exists(): shutil.rmtree(staging)` |
| 5 | P3 | TEST-02 · LOG-06 | Hợp đồng [2]: "Mọi test cần Node hoặc AppFront xin fixture `appfront_dir`; B0-09 xếp chúng vào nhóm CI có AppFront". Hai test cần Node/npm mà không xin nó: `test_process_errors_become_runner_errors` gọi `executable("node")` ngoài `pytest.raises` → hỏng ở nhóm CI không có Node; `test_failed_install_leaves_no_target` khớp `match="npm"`, mà thiếu `npm` thì `executable("npm")` cũng ném `RunnerError` chứa "npm" → test **qua rỗng**, không hề chạy `npm ci` | `tools/contract/tests/test_runner_client.py:46-58`, `:72-78` | Hai test xin `appfront_dir` (hay `contract_build`); `match` đòi đúng lỗi của `npm ci` (vd `r"npm thoát \d+"`) |
| 6 | P3 | TEST-02 · R-35 | Test của FIX-028 **không đỏ trên mã trước khi sửa** (probe P4: `5 passed` với `api.py` của `main`), trái luật chung FIX (`docs/fixes.md:156`). `test_case_trace_and_golden_resolve_the_same_operation` chỉ khẳng định hai bộ khớp **đồng ý** trên route hôm nay, không khẳng định chỉ còn **một** bộ khớp; ai thêm lại một bảng khớp riêng vào `api.py` thì test vẫn xanh — đúng hồi quy R-07 mà NO-044 đóng. `DEBT.md` (dòng NO-044) đã tự nhận "không có hành vi đỏ để tái hiện" | `packages/testing/golden/tests/test_recorder.py:266-275` | Thêm test uỷ quyền: `monkeypatch.setattr(recorder, "_real_resolver", lambda: lambda m, p: recorder.OperationMatch("x", p, {}))` → `api_fixtures.operation_of("GET", "/bat-ky") == "x"`. Test này đỏ trên `api.py` cũ và xanh trên mã hiện tại |
| 7 | P3 | R-29 · TEST-02 | Lượt lạnh (volume chưa có `CONTRACT_NODE_DIR/<băm lock>`): `npm ci` **tải mạng** từ `registry.npmjs.org` ngay trong bước 5, qua fixture phiên `contract_build`, vì bước 5 chạy trước bước 7. CLAUDE.md "không tải mạng trong test". Prompt [8] buộc test dùng runner thật nên tác giả không tránh được trong phạm vi file của mình; chỉ xảy ra một lần cho mỗi băm lock | `packages/testing/fixtures/golden.py:45-49` → `tools/contract/runner_client.py:123-145` | Ghi `DEBT.md` cho B0-01: làm ấm `node_modules` theo băm lock **trước** bước 5 (bước chuẩn bị của `in_container.sh`, hay tầng ảnh verify), để pytest không bao giờ là nơi tải mạng lần đầu |
| 8 | P3 | R-27 · MNT-02 | Bộ ghi nhập **tên riêng** của file B0-01: `from tools.case_gate import _TEST_COMMON_RE, _TEST_OP_CASE_RE`. Dùng chung là đúng R-07 (một nguồn tách tên test), nhưng CLAUDE.md "file của prompt khác: gọi qua hàm công khai". B0-01 đổi tên hai hằng này thì mọi phiên test hỏng lúc nhập (`api.py` nay nhập `recorder`) | `packages/testing/golden/recorder.py:32` | Ghi `DEBT.md` cho B0-01: xuất một hàm công khai (vd `case_gate.split_case_test_name(name) -> (op, case, end) \| None`); bộ ghi gọi hàm đó |
| 9 | Nit | R-10 | `Inputs.permissions_module`, `Inputs.rules_module` không bao giờ nhận giá trị khác mặc định (test gọi thẳng `check_h3`/`check_h4` với tên module) — tham số cấu hình cho giá trị không đổi | `tools/contract/check.py:87-88`, `:303-304` | Bỏ hai trường, `run_checks` truyền thẳng `PERMISSIONS_MODULE`, `RULES_MODULE` |
| 10 | Nit | LOG-02 | H4 so `fe_spec[name] != be_value` trực tiếp. Nếu B3-05 giữ `min`/`max` bằng `Decimal` (R-18) thì `0.1 != Decimal("0.1")` là `True` → hỏng giả (fail-closed, không lọt lỗi) | `tools/contract/h4.py:48` | So qua `Decimal(str(fe_value)) == Decimal(str(be_value))`, hoặc ghi rõ trong docstring kiểu mà B3-05 phải dùng |
| 11 | Nit | R-27 | Commit FIX-028 sửa cả `test_recorder.py`, ngoài [4] của FIX-028 ("Sửa: `packages/testing/fixtures/api.py`"). Chấp nhận được: đó là file của chính B0-07 trên nhánh B0-07, và [6] của FIX đòi thêm test | commit `d3b25b0` | Người điều phối ghi thêm file test vào [4] của FIX-028 ở `docs/fixes.md` cho khớp sổ |

Đã kiểm và **không** thấy finding:

- **Hợp đồng [2]/[6] của prompt:** `schema-map.ts` có đúng 83 mục (45 HTTP + 2 SSE của §1, 36 của §2; bỏ #2, #47–#49, N2), đối từng dòng với cột "Schema FE" của BE-BIND §1 và cột Response của HOP-DONG-MOI §2–§8 — khớp cả 83 (kể cả `empty` cho #1, #4, #18, #20, #21, #37, N8–N10, N13). `auth_login` = `empty`, lý do trích `session.ts` ghi ở chú thích; `auth_refresh` → `strict/refresh.ts`: `.strict()` hai tầng, `roles` là tuple đúng một vai lấy từ `AUTH_ROLES` của FE, `expiresAt` dùng `isoInstantSchema` của FE, không `.passthrough()`. Miễn H1 đúng ba route ([2], K06). Chọn schema lỗi theo `code` (`VERSION_CONFLICT` → `VersionConflictBodySchema`), 204 có thân hỏng, 3xx hỏng.
- **H1 ngữ cảnh** đủ 7 luật của [6].5 (N16, N15, N17, N1, N7, N23, `Progress`/K33), chạy sau khi giải đạt, trên đầu ra của schema; mỗi luật có một mẫu đạt và một mẫu hỏng trong `test_decode.py`.
- **Ma trận case [8]:** đủ mọi dòng (K01, K02, enum, `resource` lạ, 409 có/thiếu `currentVersion`, 204 có thân, thao tác ngoài bản đồ, năm mẫu refresh hỏng + một mẫu đạt; bản đồ thiếu/thừa, mount lạ, `CONTRACT_REQUIRE_ALL`, chủ đã hợp nhất mà chưa mount, W3 ở mọi độ sâu, thiếu nhánh `Progress`, S1 thiếu mẫu luồng; smoke export thiếu; H3 lệch một ô / không module / không module mà `changes/B1-02.md` có; H4 24 mã, khoá và `min`/`max` lệch; bộ ghi qua `make_api_client` thật; `parse_sse` nhiều `data:`, CRLF, `: ping`, `event:`; stash cả hai thứ tự nạp; hai `npm ci` song song). Mọi test giải bằng runner Node thật và zod thật ở `/appfront` (K23), không mock.
- **Cấm [9]:** không chép schema FE; không `pnpm install` AppFront; `package.json` chỉ ghim `zod@3.23.8`, `tsx@4.23.15` (lock có `integrity` cho 30 gói, `npm ci --ignore-scripts`); không literal JWT (`wire.fake_jwt()` dựng lúc chạy; chuỗi `eyJ` duy nhất trong diff là một câu docstring).
- **SEC-07:** `record_stream_event` kiểm `op`/`case` bằng `[A-Za-z0-9_]+`; `record_response` chỉ ghi khi `op` của tên test **bằng** một `operationId` thật (nên `test_common__C04[../x]` không thoát khỏi thư mục mẫu); gốc tên file lọc bằng `_UNSAFE_CHARS_RE`. **SEC-09/SEC-13:** header không ghi; `accessToken` thay bằng `A` cùng số đoạn và độ dài, mẫu vẫn qua `refresh.ts` (test `test_golden_issue_token__C01`). `subprocess.run` nhận danh sách lệnh cố định, không shell.
- **CON:** ghi mẫu bằng `mkstemp` + `os.link` (không bao giờ đè, số kế tiếp khi trùng); cài `node_modules` vào thư mục tạm cùng volume rồi `rename` nguyên tử, bên thua dùng bản của bên thắng — có test hai luồng qua `Barrier`.
- **RES-01/R-24:** `npm ci` trần 600 s, mỗi lệnh runner trần 120 s; lỗi tiến trình, quá trần, stdout không phải JSON đều thành `RunnerError` → bước 7 hỏng kèm stderr (fail-closed). `AppFront` thiếu `common.ts` → hỏng, không bỏ qua; `SampleError` cho mẫu hỏng.
- **PERF:** mọi mẫu giải trong **một** lượt runner; chép `src` 16 luồng có trần, lý do và ngưỡng ghi ở docstring (R-05).
- **FIX-028:** `operation_of` nay trả `.op` của `resolve_operation`, `_op_matchers` đã xoá (không còn chỗ gọi nào); `api.py` gắn tên lúc nhập nên bảng của app thử trong test bộ ghi không lọt vào vết case (`test_probe_table_does_not_leak_into_case_trace`); `apps/api/core/tests/test_fixtures.py` (9 test, gồm các test `trace_case` mà FIX-028 [6] đòi giữ nguyên) xanh trong cổng. `_path_pattern` dùng `route.path_format` nên tên nhóm luôn là định danh hợp lệ.

## Kiểm sổ nợ

- Không nợ P0/P1 nào còn `⬜`/`🔧` (24 dòng mở: 9 P2, 11 P3, 4 Nit).
- `NO-044` ✅ (FIX-028): đúng mã, đúng commit `d3b25b0` (khớp `docs/fixes.md:37`), đúng ngày; tự nhận không có test đỏ — xem #6.
- `NO-043` ⬜ (P3, B0-01): nợ B0-07 phát hiện, đã ghi trên `main` (`154213f`) và đã có FIX-008 mở — đúng R-34.
- Finding #1, #2 (P2) của lượt này **chưa** có dòng `DEBT.md` → phải sửa hoặc ghi trước khi merge (R-38). Các P3 chạm file của prompt khác (#7, #8) nên ghi `DEBT.md` để người điều phối giao cho B0-01.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #3, #4; Nit #10) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 (P2 #1; P3 #5, #6, #7) | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #2; P3 #8; Nit #9, #11) | 0,09 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,21 + 0,25 + 0,09 = **4,65 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập, bước 7 lần đầu chạy thật và đạt, độ phủ đạt ở mọi gói, không có P0/P1, điểm 4,65 ≥ 4,0. Harness làm đúng việc prompt giao: giải bằng chính zod của AppFront ở SHA ghim, bản đồ đủ 83 mục khớp hiến chương, miễn H1 đóng, và mọi dòng của ma trận case [8] có test trên runner Node thật. FIX-028 gộp hai bộ khớp làm một, đúng phạm vi cấp phép.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): sửa #1 (khuyến nghị mạnh: vài dòng trong file của chính B0-07; không sửa thì nhánh B1-01 và mọi nhánh W05 có route có thân sẽ đỏ ở bước 5 mà không tự sửa được), hoặc ghi `DEBT.md` một dòng P2 chủ B0-07, nêu rõ phải sửa **trước khi** prompt đầu tiên mount route có thân hợp nhất. Ghi #2 dạng `➖` (MNT-05, chấp nhận).
2. Nên ghi `DEBT.md` cho #7 và #8 (việc của B0-01); các P3 còn lại (#3–#6) và Nit (#9–#11) do tác giả tự quyết, không chặn merge.
3. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-07 và của B0-06 + `Fix: FIX-028`), **không** squash.
4. Người điều phối ghi nhận `tools/contract/APPFRONT_SHA` là lần ghi đầu thuộc deliverable của B0-07 (không phải sửa file cấm); từ sau lượt này chỉ người điều phối được nâng.

---

## Lượt 2

- Ngày: 2026-09-21 · Reviewer: cùng phiên `/merge-review` độc lập của lượt 1 (không phải phiên tác giả). Mọi khẳng định trong hai commit mới tự kiểm lại bằng diff, probe và cổng; không lấy lời commit làm bằng chứng · Commit đầu nhánh: `9319d3cf2f14` (gốc `267e8f7`, 4 commit; mới so với lượt 1: `a4b0e89` `fix(contract): …`, `9319d3c` `docs(repo): …`, cả hai `Prompt: B0-07`, khối trailer liền nhau, đọc được bằng `%(trailers:key=Prompt)`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** ở **lượt chạy đầu tiên và duy nhất** của lượt review này (chạy tại chỗ, log `verify2.log` trong scratchpad của phiên): `1282 passed, 10 skipped` (lượt 1: 1279; thêm 3 test mới). 10 skip vẫn là `test_common.py` với tập tham số rỗng. Flake `NO-042` **không** xảy ra (`tools/tests/test_services.py` 9/9 đạt). Bước 1–8 đều `đạt`; bảng con bước 7 giống lượt 1 (Smoke, bản đồ 83/83, đã mount 3/83, H1, H1 ngữ cảnh `đạt`; H3, H4, H5 `không áp dụng` hợp lệ; 3,9 s, dựng runner 2,9 s).
- Độ phủ: tổng dòng **99,30 %** · nhánh **96,99 %** · `packages/testing` 99,65 % / 100 % · `tools` 98,66 % / 94,93 % · tập file bị chạm 99,85 % / 99,33 %. Mọi gói bị chạm và tổng đều ≥ 90 % ở cả hai số.
- Điều kiện dừng sớm: cây sạch; `changes/B0-07.md` không đổi (8 dòng); diff `d3b25b0..HEAD` chỉ chạm `tools/contract/**`, `packages/testing/golden/tests/`, `DEBT.md`, `docs/fixes.md` (dòng [4] của FIX-028, người điều phối giao trong lời gọi lượt này); không `pragma`, `noqa`, `type: ignore`, `skip`, `xfail` mới; không đụng file cấm. Không điều kiện nào kích hoạt.

**Probe chạy lại** (container verify, bản sao `/tmp/w`, không vào repo):

- **P1** — khung S1 có `startedAt = "…T07:00:00.000000+07:00"`: runner giải `ok`, nay **H5 `hỏng`** "`event.startedAt` … không kết thúc .sssZ (W3)" (lượt 1: `đạt`).
- **P2** — `build_layout` vào thư mục có sẵn chứa `giu.txt` → `RunnerError` "không rỗng", `giu.txt` **còn** (lượt 1: mất). Thư mục chưa có → dựng bình thường.
- **P3** — giả lập B1-01 mount `auth_refresh` đúng đường BE-BIND: test mới `test_real_repo_check_runs_through` **đạt**; test cũ của `d3b25b0` trên đúng trạng thái đó **hỏng** `assert 1 == 0`.
- **P4** — đặt lại `api.py` bản `main` (còn `_op_matchers`): test mới `test_case_trace_asks_the_golden_resolver` **hỏng**, 5 test FIX-028 cũ vẫn đạt; `api.py` của nhánh → 6/6 đạt. Đỏ trước, xanh sau đúng như `NO-044` nay ghi.
- **AST** trên 6 file `.py` đổi: 0 hàm thiếu docstring, không hàm nào > 50 dòng.

### Trạng thái finding của lượt 1

| # | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | P2 | **đã sửa** | `test_check.py:458` `test_real_repo_check_runs_through`: `main` thoát 0 hoặc 1, đủ 8 dòng, trạng thái ∈ {đạt, hỏng, không áp dụng}, ba kiểm cấu trúc (`Smoke`, `Bản đồ đủ`, `Thao tác đã mount`) phải `đạt`. Lệch khỏi [8] ghi ngay trong docstring, kèm lý do. P3: test mới xanh, test cũ đỏ khi route có thân được mount |
| 2 | P2 | chấp nhận | `NO-047` ➖ (MNT-05), lý do đứng được, giống `NO-039`. Vẫn tính điểm MNT |
| 3 | P3 | **đã sửa** | `check.py:260` H5 chạy `bad_datetimes` trên mọi khung; test `test_h5_rejects_non_w3_datetimes` (`test_check.py:409`); P1 |
| 4 | P3 | **đã sửa** | `runner_client.py:165-175` không còn `rmtree(build_dir, ignore_errors=True)`; thư mục có nội dung → `RunnerError`; `check.py:329` mặc định `mkdtemp` mới. Test `test_layout_refuses_a_non_empty_directory` (`test_runner_client.py:113`); P2. `:144` (thư mục tạm của `npm ci`) giữ nguyên — lượt 1 đã chấp nhận. Xem Nit mới #1 |
| 5 | P3 | **đã sửa** | `test_runner_client.py:46`, `:73` `@pytest.mark.usefixtures("appfront_dir")`; `:57` `match=r"npm thoát \d+"` khớp đúng thông điệp của `run_process` khi `npm ci` thoát khác 0, không còn qua rỗng khi thiếu `npm` |
| 6 | P3 | **đã sửa** | `test_recorder.py:272` thay `recorder._real_resolver` → `operation_of("GET", "/bat-ky") == "golden_x"`; P4 đỏ trước, xanh sau. `NO-044` cập nhật đúng |
| 7 | P3 | **ghi sổ** | `NO-048` ⬜ P3, chủ B0-01, đủ cột (nguyên nhân, cách chữa: gọi `ensure_node_modules` ở bước chuẩn bị trước bước 5). Vẫn tính điểm TEST |
| 8 | P3 | **ghi sổ** | `NO-049` ⬜ P3, chủ B0-01, đủ cột (xuất hàm công khai trong `case_gate`). Vẫn tính điểm MNT |
| 9 | Nit | **đã sửa** | Hai trường `Inputs.permissions_module`, `Inputs.rules_module` đã xoá; `check.py:302-303` truyền thẳng hằng; không còn chỗ tham chiếu |
| 10 | Nit | chấp nhận | `h4.py` docstring nêu gương B3-05 phải giữ `min`/`max` bằng `int`/`float` và vì sao — một trong hai đường lượt 1 đề xuất |
| 11 | Nit | **đã sửa** | `docs/fixes.md:226` [4] của FIX-028 nay ghi thêm `test_recorder.py` |

### Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-11 · OPS-04 | Hệ quả của bản sửa #4: `python -m tools.contract.check` không có `--build-dir` dựng vào `mkdtemp(prefix="contract-")` và **không** dọn — probe P2c: sau một lượt còn lại `/tmp/contract-…` chứa bản chép `src` của AppFront (~16 MB, 1 355 file theo số đo trong docstring `copy_tree`). Trong cổng `/tmp` mới mỗi container nên vô hại; chạy tay nhiều lần ngoài container thì dồn lại | `tools/contract/check.py:329` | Khi không có `--build-dir`, dựng trong `with tempfile.TemporaryDirectory(prefix="contract-") as tmp:`; có `--build-dir` thì giữ lại để gỡ lỗi như hiện tại |
| 2 | Nit | R-36 · R-34 | `git merge-tree main HEAD` báo **xung đột** ở `DEBT.md`: `main` đã có `3fab67b` thêm `NO-045` (B3-01) vào cuối bảng, nhánh thêm `NO-047..049` cùng chỗ. `docs/fixes.md` tự gộp được. Không phải lỗi mã; nhánh bỏ qua đúng hai id `NO-045`, `NO-046` đã dành cho `fix/b0-01-gate-debts` | `DEBT.md:66-69` (nhánh) ↔ `DEBT.md` của `main` | Phiên merge giữ cả hai phía, xếp theo id (`NO-044`, `NO-045`, `NO-047`, `NO-048`, `NO-049`), không xoá dòng nào; hoặc tác giả rebase nhánh lên `main` trước khi merge |

Ngoài phạm vi nhánh, ghi để người điều phối biết: `NO-045` đang bị **dùng hai lần** — trên `main` (`3fab67b`, B3-01 ➖ MNT-05) và trên `fix/b0-01-gate-debts` (`TESTCONTAINERS_CONNECTION_MODE`, FIX-009). Trái luật "Id … không dùng lại" ở đầu `DEBT.md`; nên đổi id một bên trước khi gộp nhánh fix đó.

Đã kiểm và **không** thấy finding thêm: `check_h5` thêm luật W3 sau kiểm "không phải luồng Loại S" nên thứ tự `problems` của `test_h5_decodes_received_frames` giữ nguyên (xanh trong cổng); `build_layout` kiểm thư mục rỗng **trước** `ensure_node_modules` nên từ chối không tốn `npm ci`; `RunnerError` từ đó rơi đúng nhánh `except` của `main` → "bước 7 hỏng: …", thoát 1 (fail-closed); fixture `contract_build` luôn dựng vào `mktemp(...) / "build"` chưa có nên không vướng luật mới; `test_smoke_reports_missing_export_and_bad_entries` chép bằng `copytree`, không qua `build_layout`.

### Kiểm sổ nợ

- Không nợ P0/P1 nào còn `⬜`/`🔧`. Nợ mở do nhánh thêm: `NO-048`, `NO-049` (P3, B0-01). `NO-047` ➖ có lý do đứng được. `NO-044` ✅ nay có test đỏ trước, xanh sau (P4).
- Mọi P2/P3 của lượt 1 đã sửa hoặc có dòng `DEBT.md` (R-38 đạt). Hai Nit mới không bắt buộc ghi sổ.

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (#3, #4 đã sửa; chỉ Nit #10 chấp nhận) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #7 còn mở ở `NO-048`) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 (chỉ Nit mới #1) | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #2 chấp nhận ở `NO-047`; P3 #8 ở `NO-049`; Nit mới #2) | 0,09 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,28 + 0,25 + 0,09 = **4,87 / 5**

## PHÁN QUYẾT (lượt 2): APPROVE

Cổng thoát 0 ngay lượt đầu trên `9319d3c`, độ phủ đạt ở mọi gói, không có P0/P1, điểm 4,87 ≥ 4,0. Bảy finding của lượt 1 đã sửa, và mỗi bản sửa đều được kiểm bằng probe chạy thật: P1 (W3 trên SSE), P2 (không xoá thư mục có sẵn), P3 (test khói không còn đỏ khi route có thân được mount), P4 (test FIX-028 đỏ trước, xanh sau). Bốn mục còn lại được ghi sổ (`NO-047` ➖, `NO-048`, `NO-049`) hoặc chấp nhận có lý do (#10).

Điều kiện cho phiên merge:

1. Giải xung đột `DEBT.md` với `main` (Nit mới #2): giữ cả `NO-045` của `main` lẫn `NO-047..049` của nhánh, xếp theo id, không xoá dòng nào.
2. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-07 và B0-06 + `Fix: FIX-028`), **không** squash.
3. Người điều phối ghi nhận `tools/contract/APPFRONT_SHA` là lần ghi đầu thuộc deliverable của B0-07 (như lượt 1).
4. Không chặn merge: đổi id `NO-045` trùng trên `fix/b0-01-gate-debts` trước khi gộp nhánh đó; giao `NO-048`, `NO-049` cho B0-01.

Nit mới #1 do tác giả tự quyết.
