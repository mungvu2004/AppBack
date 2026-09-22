# Review merge fix/b0-07-contract-tool-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, dòng `DEBT.md` và báo cáo W5-CONTRACT đều tự kiểm lại) · Commit đầu nhánh: `1ca38e2717af` (gốc `afa29ed`, 3 commit, không commit gộp: `a21a0ac` B0-01 + FIX-033, `84fed27` B0-07 + FIX-034, `1ca38e2` B0-07 + FIX-035). `main` nay ở `55333dc` (sau `afa29ed` có tài liệu FIX-038/NO-058, phán quyết B5-01 và chính B5-01 `feat(ml)`); `git merge-tree --write-tree main HEAD` → sạch, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong worktree sạch của nhánh, 09:26:45 → 09:32:37; mã thoát lấy bằng `echo $?` ngay sau `run.sh` trong shell nền, shell không bị cắt nên không cần `docker wait`; lúc khởi chạy có 1 lượt verify khác, dưới trần 2; log `verify.log` trong scratchpad của phiên review `7ec5363d-…/scratchpad/`): `1649 passed, 0 failed, 10 skipped` trong 295,96 s. Cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng: chưa có route được bảo vệ nào), đúng ngoại lệ BE-00 §12. Không gặp `RequestTimeTooSkewed`, không phải chạy lại.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,21 %** · nhánh **96,82 %**
  - `packages/testing`: dòng 99,09 % · nhánh 100,00 % · `tools`: dòng 98,60 % · nhánh 95,11 %
  - tập file bị chạm: dòng 99,09 % · nhánh 97,12 %
  - ba file mã bị sửa (probe P7, test vùng): `recorder.py` 100 % · `case_gate.py` 98 % (thiếu 187, 189, 264, **348**, 566 — chỉ 348 thuộc diff, xem #1) · `check.py` 99 % (thiếu 351 = `sys.exit(main())` dưới `__main__`, có từ trước)

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (265 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (231 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf`; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5 — `case_gate` đã đổi cách tách tên vẫn cho đúng kết quả của `main`) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/<mã>.md` | đạt — nhánh FIX không mở prompt mới; `changes/B0-01.md`, `changes/B0-07.md` đã có trên `main` |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 52, 61, 60 ký tự |
| Trailer đọc được (R-36b) | đạt — `%(trailers:key=Prompt)` in `B0-01`, `B0-07`, `B0-07`; `%(trailers:key=Fix)` in `FIX-033`, `FIX-034`, `FIX-035` |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/verify/*` | không |
| `pragma` / `type: ignore` / `noqa` / `skip` / `xfail` mới / hạ ngưỡng | không (grep diff: chỉ một dòng ngữ cảnh `t.is_xfail` có từ trước) |
| Sở hữu file (R-27) | đạt — FIX-033 chỉ `tools/case_gate.py` + test (`Prompt: B0-01`); FIX-034 chỉ `recorder.py` + test + `DEBT.md`; FIX-035 chỉ `check.py` + test + `DEBT.md` — đúng [4] của từng spec trong `docs/fixes.md` |

Nhánh 122 dòng thêm / 35 dòng bớt (≈ 45 dòng logic sản phẩm), dưới trần MNT-05.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (`run.sh shell < probe.sh`, bản sao `/tmp/w`; bản `afa29ed` của ba file đặt tạm ở `.cache/review-probe/`, đã xoá):

- **P1 — FIX-033 đỏ trước / xanh sau.** `case_gate.py` + `recorder.py` của `afa29ed`, test mới → `7 failed, 51 passed`, thoát 1 (không có `split_case_test_name`); bản nhánh → `58 passed`, thoát 0. Khớp dòng `DEBT.md` "đỏ 7/7 → xanh".
- **P2 — FIX-034.** `case_gate` mới + `recorder.py` cũ (đúng trạng thái sau `a21a0ac`) → `1 failed, 94 passed` (chỉ `test_recorder_imports_no_private_name_of_case_gate`) — vậy commit FIX-033 đứng riêng vẫn xanh (bisect được); bản nhánh → `packages/testing/golden/` `37 passed`.
- **P3 — FIX-035.** `check.py` cũ → `2 failed` (hai test `without_build_dir`), `test_real_repo_check_runs_through` vẫn xanh; bản nhánh → cả `test_check.py` `42 passed`.
- **P4 — hành vi tách tên không đổi (spec [5]).** Nạp song song bản `afa29ed` và bản nhánh; tập tên = **1 655** tên test thu từ `pytest --collect-only` của `packages apps tools` + 32 tên biên (`test_common__C04`, `…[]`, `…[a][b]`, `…[a]_z`, `test__C01`, `test_a__C01__C02`, `test_x__C01x`, `C1`/`C001`, `J06`, `test_common__C01[op]`, `C04b`, Unicode `[ünï code/α]`, xuống dòng cuối, chuỗi rỗng, `TEST_…`, `test_common_x__C04[op]` …). `split_test_name` cũ ≠ mới: **0 tên**. `_found_cases_by_op` cũ == mới với vết phủ mọi op ứng viên × mọi status/mã cố định (42 case riêng, 17 case chung tìm thấy), với vết chỉ 200, với vết rỗng; `failed`/`xfail` bị bỏ qua.
- **P5 — CLI thật, không `--build-dir`** (`TMPDIR` riêng): bản cũ để lại `contract-omigvfmd` (19 MB cùng `tsx-0`); bản nhánh không để lại `contract-*` nào. Kho `node_modules` dùng chung trên volume: 4 mục trước, 4 mục sau. (`tsx-0` là cache của trình nạp `tsx` theo uid, tên cố định, dùng lại giữa các lượt — không phải của `check.py`, không tích dần.)
- **P6 — `--build-dir`.** Thư mục không rỗng → `bước 7 hỏng: … không rỗng`, thoát 1, `keep.txt` còn nguyên (ExitStack rỗng, không xoá gì); thư mục mới → bố cục đủ (`runner.ts`, `src`, symlink `node_modules`, …) được **giữ lại**, `TMPDIR` không có `contract-*`.
- **Đột biến.** M2 (xoá cả khi có `--build-dir`) → `test_real_repo_check_runs_through` đỏ: assert mới bắt được. **M1** (bỏ bộ lọc case chung ở `_found_cases_by_op`) → `58 passed`: **không test nào bắt** (xem #1); M1b cùng đột biến trên bản `afa29ed` → `51 passed`, lỗ có từ trước.
- **P7 — độ phủ ba file bị sửa** (`coverage run --branch` trên `test_case_gate.py`, `packages/testing/golden/`, `tools/contract/tests/`: `201 passed`) — số ở đầu phán quyết. Bản `afa29ed` cùng test cũ: 0 dòng thiếu nhưng thiếu 2 nhánh `326→328`, `330→319` đúng tại hai chỗ mà FIX-033 gộp lại thành dòng 348.
- **P8** — `ruff check` trên 6 file `.py` bị chạm: đạt.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-14 · TEST-02 | Dòng `continue` của bộ lọc trong `_found_cases_by_op` — viết lại trong FIX-033 — **chưa chạy lần nào** trong bộ test (P7: thiếu dòng 348). Không test nào đưa vào một tên không phải test case (`test_x_create_is_public`) hay một tên dạng chung với case không phải case chung (`test_common__C01[x_create]`). Đột biến M1 bỏ hẳn vế `parts.common and parts.case not in _CASE_CHUNG \| {"C10", "C22"}` vẫn `58 passed`: một hồi quy làm `case_gate` tính `test_common__C01[op]` là case C01 của `op` (cổng case xanh giả) sẽ lọt bước 5. Lỗ có từ trước (bản `afa29ed` thiếu hai nhánh cùng chỗ, M1b `51 passed`), nên không nâng mức; hành vi hiện tại đúng (P4) — nhưng chính khẳng định "hành vi không đổi" của tác giả dựa trên 51 test cũ vốn không chạm vế này | `tools/case_gate.py:347-348`; `tools/tests/test_case_gate.py` | Thêm một test `evaluate`: `tests = [test_common__C01[x_create], test_x_create_is_public]` (`passed`, có vết `op="x_create"`, status 200) → `"C01" not in op_results[0].found` và không case chung nào; chủ B0-01 |
| 2 | Nit | — (sổ) | Cột "Commit" của FIX-033..035 ghi tên nhánh thay vì sha như FIX-001..031 | `docs/fixes.md:42-44` | Người điều phối điền `a21a0ac`, `84fed27`, `1ca38e2` khi gộp (`--no-ff` giữ nguyên sha) |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 1**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-033 sửa gốc (R-19, R-07).** `split_case_test_name` là **một** chỗ tách duy nhất: `case_gate` dùng chính nó (`_found_cases_by_op`), bộ ghi golden gọi nó; `grep` toàn repo, `main` @ `55333dc` và mọi nhánh cục bộ: không còn ai ngoài `case_gate.py` dùng `_TEST_COMMON_RE`/`_TEST_OP_CASE_RE` (chỉ `recorder.py` từng nhập, và đã chuyển). `_TEST_TASK_RE` (case `J`) vẫn riêng — đúng, là mẫu khác, chỉ `_task_found` dùng. Không trùng logic cũ: hai đoạn `match` của `_found_cases_by_op` bị xoá, không để song song. Thứ tự "mẫu chung trước" giữ nguyên và có test (`test_common__C04_x` rơi về dạng riêng với `op="common"`, `test_common__C04[x_create]` ra dạng chung). Viết lại vòng lặp tương đương từng nhánh (đọc mã + P4): dạng chung với case lạ → `continue` không rơi xuống mẫu riêng, như cũ.
- **Hàm công khai mới có docstring đúng R-01/R-02.** `CaseTestName` (nghĩa của `tail`, rỗng ở dạng chung) và `split_case_test_name` (hai dạng CASE §2.3, `None` khi không khớp, lý do xét mẫu chung trước, là nguồn duy nhất cho ai). Cờ `common` (lệch của tác giả) **đứng được**: `_found_cases_by_op` cần phân biệt hai dạng; suy lại từ tên ở chỗ gọi là tách lần hai. `NamedTuple` nên test so với tuple thường được.
- **FIX-034.** `split_test_name` của bộ ghi chỉ còn phần riêng của nó (làm sạch hậu tố thành gốc tên file); docstring cập nhật. Test chặn tái phát duyệt AST, `assert names` làm nó fail-closed: đổi sang `import tools.case_gate` thì test đỏ chứ không xanh giả.
- **FIX-035.** `ExitStack` + `TemporaryDirectory(prefix="contract-")` chỉ khi không có `--build-dir`; `results`/`built` đọc sau khối `with` là dữ liệu trong RAM, không đọc lại thư mục đã xoá. Xoá cả ở đường hỏng sớm (AppFront thiếu F-00a), hỏng sau khi dựng (mẫu hỏng) và đường đạt; lỗi lạ vẫn nổi lên (không nuốt), lỗi dọn cũng nổi lên thành bước 7 hỏng. `shutil.rmtree` gỡ symlink `node_modules` chứ không đi theo nó (P5, test mới kiểm kho còn). `--build-dir` được giữ (P6b, assert mới, đột biến M2 bị bắt). Không ai khác phụ thuộc thư mục dựng còn lại sau bước 7: `steps.py` chỉ gọi `python -m tools.contract.check` và đọc mã thoát; `ensure_node_modules` dựng staging trong `node_dir` riêng. Fixture `scratch` đặt `tempfile.tempdir` bằng `monkeypatch` (tự trả lại).
- **Dòng `DEBT.md`** NO-049, NO-052: `✅`, ngày đóng 2026-09-22, nêu mã FIX và test đỏ → xanh — mọi con số trong đó khớp probe P1–P3; chuyển trạng thái trong chính commit sửa (FIX-034, FIX-035), đúng luật đợt giao việc.
- **Hợp nhất.** `main` @ `55333dc` (gồm B0-06, B0-07, B1-01, B3-01, B5-01): `merge-tree` sạch; không file nào của B5-01 gọi API nhánh đổi. Với `fix/b0-01-gate-debts` (FIX-032): xung đột **chỉ** ở `DEBT.md`, hai dòng kề nhau NO-048/NO-049 — nhánh vào sau giữ cả hai dòng.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | `split_case_test_name` trả `CaseTestName(op, case, tail, common)` thay vì `(op, case, end)` | **Đứng được** — spec [5] không ghim chữ ký (DEBT ghi "vd"); cờ `common` tránh tách lần hai (R-07) |
| 2 | Thêm test `…removes_built_layout` và assert `--build-dir` được giữ | **Đứng được** — đúng chỗ FIX-035 có thể làm mất dữ liệu (kho `node_modules` sau symlink, thư mục gỡ lỗi); M2 cho thấy assert có tác dụng |
| 3 | Lượt verify đầu hỏng vì hạ tầng (`RequestTimeTooSkewed` sau khi máy ngủ), chạy lại xanh | **Đứng được** — lượt độc lập của review xanh ngay lần đầu, không gặp lỗi đó; test hỏng khi ấy (`packages/storage/tests/test_s3.py`) ngoài vùng file của nhánh |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt — tác giả không nêu nợ mới; NO-049, NO-052 đã `✅` |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh để lại | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — dòng đề xuất dưới (P3, không chặn merge) |

Dòng đề xuất (người điều phối cấp id; phiên này **không** tự ghi `DEBT.md`):

- `| ⬜ | NO-<nnn> | 2026-09-22 | | Bộ lọc của `_found_cases_by_op` (`tools/case_gate.py:347-348`) không test nào chạm: không có tên không phải test case hay dạng chung với case không phải case chung (`test_common__C01[op]`); dòng `continue` 348 chưa chạy lần nào, đột biến bỏ bộ lọc case chung vẫn `58 passed` | Test cũ chỉ dựng tên khớp (bản `afa29ed` thiếu nhánh `326→328`, `330→319`); FIX-033 gộp hai nhánh thiếu thành một dòng | B0-01 (`tools/tests/test_case_gate.py`) | P3 | mở — review merge 2026-09-22 finding #1 (`docs/reviews/2026-09-22-fix-b0-07-contract-tool-debts.md`). Chữa: một test `evaluate` với `test_common__C01[x_create]` và `test_x_create_is_public` (`passed`, có vết) → không vào `found`/`common` |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #1) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 5 (Nit #2) | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,28 + 0,25 + 0,15 = **4,93 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập (`1649 passed, 10 skipped`, 10 skip hợp lệ), độ phủ đạt ở mọi gói bị chạm (`tools` 98,60 % / 95,11 %, `packages/testing` 99,09 % / 100 %), không P0/P1/P2, điểm 4,93 ≥ 4,0. Cả ba FIX sửa đúng gốc và đúng phạm vi [4]: `case_gate` có đúng một chỗ tách tên test, công khai, có docstring, dùng lại ở chính nó và ở bộ ghi golden; không còn ai nhập hằng `_TEST_*_RE` ở bất kỳ nhánh nào; `tools.contract.check` dọn thư mục tạm ở mọi đường ra mà không chạm kho `node_modules` dùng chung hay thư mục `--build-dir`. Đỏ trước / xanh sau tự tái hiện đủ ba FIX (7/7, 1/1, 2/2), hành vi tách tên được chứng minh không đổi trên 1 687 tên. Finding #1 là lỗ test có từ trước ở đúng dòng FIX-033 viết lại — không chặn merge.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): ghi `DEBT.md` dòng `⬜` P3 cho #1 (chủ B0-01), theo dòng đề xuất ở trên.
2. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-01 **và** B0-07, cùng `Fix: FIX-033/034/035`), **không** squash. `main` đã tới `55333dc`: `merge-tree` sạch; sau khi gộp chạy lại `verify` trên `main` (xuất `openapi.json` ra gốc trước bước 8 như mọi lượt trên `main`).
3. Nếu `fix/b0-01-gate-debts` vào trước hay sau: xung đột duy nhất là hai dòng kề nhau NO-048/NO-049 của `DEBT.md` — giữ cả hai.
4. Điền sha `a21a0ac`, `84fed27`, `1ca38e2` vào cột "Commit" của FIX-033..035 trong `docs/fixes.md` (Nit #2).
