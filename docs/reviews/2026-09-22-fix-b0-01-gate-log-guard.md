# Review merge fix/b0-01-gate-log-guard → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, không phải phiên tác giả. Mọi khẳng định trong commit, `DEBT.md` và báo cáo W14-GATEGUARD đều được kiểm lại. Commit đầu nhánh: `47efe53e59f6`, gốc `24b0027` (= `main`), 2 commit:
  - `2debb52`: B0-01 + FIX-068
  - `47efe53`: B0-05 + FIX-069
- `main` @ `24b0027` là tổ tiên của HEAD (`git merge-base --is-ancestor` đúng). `git merge-tree --write-tree main HEAD` rc 0, không xung đột. Không cần gộp `main` thêm.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Chạy tại chỗ trong worktree sạch của nhánh; trước lượt, `docker ps -q --filter name=verify-run | wc -l` = 1 (< 2). Mã thoát có từ hai nguồn trùng nhau:
  - client: `EXIT=0` từ `$?` của `run.sh` trong shell nền. Shell không bị cắt, nên không cần `docker wait`;
  - dòng `mã thoát: 0` ở cuối log host của chính lượt này, `.cache/src-out/verify/20260922T064048Z-47efe53e59f6.log`.
- Bước 5: **`2142 passed, 0 failed, 10 skipped`**, 1 deselected, 105 warnings, 323,12 s. Cả 10 skip là tập tham số rỗng có sẵn của `apps/api/core/tests/test_common.py`. Deselected là test `perf` của B5-01. Số test và số warnings bằng đúng lượt của tác giả (`20260922T063321Z-47efe53e59f6.log`).
- Độ phủ, in từ `tools.coverage_gate` của lượt trên (không lấy từ báo cáo tác giả):
  - tổng: dòng **99,35 %** · nhánh **97,54 %**
  - `packages/messaging`: dòng 100,00 % · nhánh 100,00 %
  - `tools`: dòng 98,74 % · nhánh 95,76 %
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**
  - `run.sh` là shell, ngoài coverage Python. Mọi dòng mới của nó chạy trong `tools/tests/test_run_sh.py` (5 test) và trong probe P1, P2. Không dòng nào dính NO-035.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm `node_modules` | đạt |
| 1 | `ruff format --check` | đạt (332 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (282 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision, 1 head) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu và cuối phiên) |
| `changes/B0-01.md`, `changes/B0-05.md` tồn tại | đạt |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt, cả 2 commit (69 và 66 ký tự) |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt,valueonly)` in `B0-01` (`2debb52`) và `B0-05` (`47efe53`); `Fix:` in `FIX-068`, `FIX-069` |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py` gốc | không. `tools/verify/run.sh` là file của chủ B0-01, được FIX-068 cho phép (spec [4]) |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không có. `noqa: S603` duy nhất trong diff là dòng ngữ cảnh cũ, có mã và lý do |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

File ngoài cột sở hữu: không có. `tools/verify/run.sh` và `tools/tests/test_run_sh.py` thuộc B0-01 (FIX-068, đúng spec [4]). `packages/messaging/tests/test_tasks.py` thuộc B0-05 (FIX-069, đúng spec [4]); fixture `packages/testing/fixtures/messaging.py` **không** đổi. Mỗi FIX nằm trong commit riêng, trailer đúng chủ. Nhánh +60/−18 dòng, trong đó 3 dòng logic sản phẩm (`run.sh:103-105`), dưới xa trần 400 của MNT-05.

## Công cụ kiểm tại chỗ

Probe container chạy bằng `run.sh shell < probe.sh`, trên bản sao `/tmp/w`, lệnh `python -m pytest -p no:cacheprovider -o addopts=""`. Bản cũ @ `main` (`run.sh`, `test_run_sh.py`, `test_tasks.py`) đặt tạm ở `.cache/review-probe/` rồi `cp` đè trong container; bản đột biến fixture dựng bằng `sed` ngay trong `/tmp/w`. Thư mục `.cache/review-probe/` đã xoá. Probe host chạy trong scratchpad của phiên, cũng đã xoá. Trước lượt container, `verify-run` đếm được 0.

- **P1 · FIX-068 trên host (Git Bash), lỗi giả.** `run.sh` cũ và mới chép vào repo git tạm, 20 log sẵn (mtime tăng dần), `docker` giả trên `PATH` ghi lại lần gọi và thoát `$DOCKER_RC`. Lệnh giả hỏng (`rm`, `find` hay `xargs`) in một dòng stderr rồi thoát 1.

  | Bản | Lệnh hỏng | `docker` thoát | rc `run.sh` | `docker` được gọi | log còn | stderr |
  |---|---|---|---|---|---|---|
  | cũ | `rm` | 0 | **123** | **không** | 20 | `rm: …` |
  | cũ | `find` | 0 | **1** | **không** | 20 | `find: …` |
  | mới | `rm` | 0 | 0 | có | 20 | `rm: …` + `dọn log cổng cũ hỏng — bỏ qua, cổng vẫn chạy` |
  | mới | `rm` | 3 | **3** | có | 20 | như trên |
  | mới | `find` | 0 | 0 | có | 20 | `find: …` + cảnh báo |
  | mới | `xargs` | 0 | 0 | có | 20 | `xargs: …` + cảnh báo |
  | mới | không | 0 / 3 | 0 / 3 | có | 19 | rỗng |
  | cũ | không | 0 | 0 | có | 19 | rỗng |

  Mã thoát của `run.sh` luôn là mã của `docker`, kể cả khi dọn hỏng. stderr của lệnh hỏng vẫn in, không bị nuốt. Khi không có lỗi, trần 19 + 1 vẫn áp như trước và không in cảnh báo.
- **P2 · FIX-068 với file bị giữ thật trên Windows** (không lệnh giả nào). PowerShell giữ log cũ nhất bằng `[IO.File]::Open(p, Open, ReadWrite, FileShare None)` suốt lượt `run.sh`, và `/usr/bin/rm` thật của Git Bash chạy:
  - `run.sh` cũ: rc **123**, `docker` không được gọi, `rm: cannot remove '…/202609010000.log': Device or resource busy`;
  - `run.sh` mới: rc **0**, `docker` được gọi, cùng dòng `Device or resource busy` rồi dòng cảnh báo; 20 log còn (file bị giữ ở lại, lượt sau dọn tiếp).
- **P3 · FIX-068, đỏ → xanh (container).**
  - `run.sh` @ `main` + test mới → **1 failed** (`test_verify_vẫn_chạy_cổng_khi_dọn_log_cũ_hỏng`), 4 passed, rc 1.
  - `run.sh` @ `main` + test @ `main` → 4 passed (test cũ không có ca này).
  - HEAD → **5 passed**; cả `tools/tests/` → **259 passed**.
  - `shellcheck tools/verify/run.sh` rc 0; `bash -n` rc 0.
- **P4 · FIX-069, đột biến fixture `_restoring_process_logging` (container).** Test đích: `test_the_worker_factory_leaves_no_process_logging_state[clean|preset]`.

  | Fixture | Test @ `main` | Test của nhánh |
  |---|---|---|
  | M1: dòng 209 `logging.captureWarnings(False)` → `pass` | 2 passed (sống) | **1 failed** `[clean]` |
  | M2: dòng 208 điều kiện → `if True:` | 2 passed (sống) | **1 failed** `[preset]` |
  | M3 (thêm của review): điều kiện đảo `is showwarning` | 2 passed (sống) | **2 failed** |
  | HEAD, không đột biến | — | **2 passed** |

  Cả `test_tasks.py` trên HEAD → **47 passed**. Probe thứ tự: một test tạm đặt **trước** trên dòng lệnh gọi `captureWarnings(True)` rồi không trả (`logging` nhớ hàm cũ, đúng dấu mà một worker lỗi để lại) → test đích vẫn 3 passed. `captureWarnings(False)` mới ở đầu test làm hàm gốc đúng cả khi test trước đã rò.
- **P5 · ruff** trên hai file test bị chạm: `ruff check` và `ruff format --check` đạt.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| — | — | — | Không có finding. | — | — |

**P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 0**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-068 (NO-092) sửa gốc, không che lỗi thật của cổng.**
  - Chặn ở đúng chỗ duy nhất có đường hỏng: đường ống dọn log (`run.sh:103-105`). Không có bước nào khác của nhánh `verify` được bọc thêm.
  - Cú pháp đúng dưới `set -euo pipefail` (`run.sh:6`). Nhóm `{ …; }` có `;` trước `}`, dòng nối bằng `\`. Nhóm là vế trái của `||`, nên bash bỏ `errexit` **trong** nhóm. `pipefail` cho mọi khâu hỏng (`find`, `sort`, `tail`, `cut`, `xargs`/`rm`) làm cả nhóm khác 0, và thế là cảnh báo chạy (P1: `rm`, `find`, `xargs` đều ra cảnh báo). Cảnh báo ra stderr, đúng spec [5]. stderr của lệnh hỏng vẫn in (P1, P2), nên người đọc biết file nào bị giữ.
  - Mã thoát: `run_container` vẫn là lệnh cuối của nhánh `verify` và không bị bọc, nên mã thoát của `run.sh` là mã của cổng. P1 cho thấy `docker` thoát 3 thì `run.sh` thoát 3, cả khi dọn hỏng lẫn khi không. Cảnh báo in **trước** khi cổng chạy, nên không lẫn vào bảng bước hay dòng `mã thoát:` của log host. Lỗi thật của cổng vẫn đỏ như cũ.
  - Không đổi hành vi khác: `diff` `run.sh` @ `main`/HEAD chỉ đổi dòng 101-105 trong nhánh `verify` (2 dòng comment + 3 dòng bọc). `lock`, `openapi`, `merge-heads`, `shell`, `gc`, việc lạ, mount và biến môi trường không đổi một ký tự. Không có lỗi thì trần log áp y như FIX-066 (P1: 19 log còn, stderr rỗng).
  - Comment `run.sh:101-102` nói **tại sao** (file bị giữ trên Windows; file biến mất giữa lúc `find` đọc), đúng R-05.
  - File bị giữ thì ở lại tới lượt sau, và thư mục có thể tạm quá 20 file. Điều này đúng ý spec [5] ("dọn là việc phụ") và không tích luỹ, vì lượt nào cũng dọn lại.
- **FIX-069 (NO-093) đúng spec [5], [6].** Chỉ đổi test, fixture giữ nguyên. Test kiểm bằng hành vi qua API công khai (`logging.captureWarnings`, `warnings.showwarning`), không đọc `logging._warnings_showwarning`.
  - Ca `clean`: bật capture sau worker phải đổi `showwarning`, tức `logging` không còn tưởng mình đang bắt. Ca `preset`: tắt phải trả đúng hàm gốc đã lưu.
  - Bắt đủ M1, M2 của review trước, và cả M3 (điều kiện đảo) mà test cũ để sống (P4).
  - `finally: logging.captureWarnings(False)` trả capture về tắt ở mọi đường, nên test không để dấu cho test sau. Với fixture lỗi M1, chính `finally` này còn dọn luôn hàm cũ mà `logging` nhớ.
  - Docstring nói lý do bằng một câu (`catch_warnings` không trả hàm gốc `logging` tự nhớ), có dẫn NO-093.
- **Hợp nhất với `main` @ `24b0027`.** `main` = merge-base, không có gì mới để gộp.
  - Người gọi `run.sh verify`: `justfile`, `deploy/compose/verify.yml` (tài liệu), `tools/verify/steps.py` (tài liệu) và mọi worktree. Hợp đồng gọi, đối số và mã thoát không đổi (P1).
  - Hàm test đổi chữ ký `_run_verify` (nay trả `(args, stderr)`) chỉ được gọi trong `tools/tests/test_run_sh.py`. Trùng tên với `tools/verify/steps.py::_run_verify` nhưng khác module, cả hai đều riêng tư.
  - Repo không có `captureWarnings`, `catch_warnings` hay `showwarning` nào khác ngoài fixture và test này (grep `packages apps tools conftest.py`).
  - Lượt cổng đầy đủ của review xanh.
- **R-01/R-02, R-07.** Hàm mới `_fake_command`, `_old_logs`, test mới và docstring module đều nói lý do, không kể lại mã. `_run_verify` có docstring mới cho giá trị trả. `_old_logs` được tách ra để hai test dùng chung, thay vì chép khối dựng log.
- **Nit #3 của review trước** (tên log tăng cùng chiều mtime) vẫn còn: `_old_logs` giữ nguyên thứ tự đó, và docstring của nó nói thật điều này. Phán quyết trước để tác giả tự quyết, nên đây không phải finding mới.
- **Sổ nợ.** NO-092, NO-093 có `✅`, ngày đóng 2026-09-22, mã FIX, tên test. Các số đỏ/xanh ghi trong dòng đều khớp probe của review:
  - NO-092: 1 failed, rc 123 → 5 passed, 259 passed; `docker` thoát 3 → `run.sh` thoát 3 (P1, P3).
  - NO-093: M1 → `[clean]` đỏ, M2 → `[preset]` đỏ, test cũ 2 passed dưới cả hai; 2 passed, 47 passed (P4).

## Tuyên bố "lệch khỏi prompt" của tác giả

Tác giả ghi "không". Review khớp: FIX-068 dùng đúng hướng chữa mà review `fix/b0-01-gate-log-followups` đề xuất (`{ …; } || echo … >&2`, chỉ thêm "cổng vẫn chạy" vào câu cảnh báo). FIX-069 kiểm đúng hai điều spec [5] nêu. Dòng `captureWarnings(False)` thêm ở đầu test nằm trong phạm vi [4] (chỉ `test_tasks.py`) và có lý do (P4, probe thứ tự).

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng có dòng `✅` đúng sự thật | đạt: NO-092, NO-093 |
| Nợ mới tác giả nêu | không có. Báo cáo ghi "không có nợ mới", và review không thấy nợ nào tác giả biết mà bỏ sót |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh sinh | không có |
| Nợ do review này chỉ ra | không có (0 finding), nên không có dòng `DEBT.md` đề xuất |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,15 = **5,00 / 5**

## PHÁN QUYẾT: APPROVE

Lượt cổng do review tự chạy thoát 0: `2142 passed, 0 failed, 10 skipped`. Độ phủ đạt ở mọi gói bị chạm (tập file bị chạm 100,00 % dòng · 100,00 % nhánh; tổng 99,35 % · 97,54 %). Không có finding nào; điểm 5,00 ≥ 4,0. Cả hai FIX sửa đúng gốc, đúng phạm vi [4], và review đã tự tái hiện đỏ trước / xanh sau cho cả hai (P1–P4).

- **FIX-068**: dọn log hỏng (lỗi giả của `rm`, `find`, `xargs`, và một file bị Windows giữ thật) chỉ để lại cảnh báo trên stderr. Cổng vẫn chạy, mã thoát vẫn là của cổng (3 → 3), và mọi việc khác của `run.sh` không đổi.
- **FIX-069**: test nay bắt M1, M2 và cả M3. Nó dùng API công khai và vẫn xanh khi test trước đã để capture bật.

Điều kiện cho phiên merge:

1. Gộp bằng `git merge --no-ff fix/b0-01-gate-log-guard`, **không** squash (R-36: nhánh mang trailer của B0-01 **và** B0-05, cùng `Fix: FIX-068/069`). `main` là tổ tiên của nhánh, nên không có xung đột.
2. Điền sha vào cột "Commit" của `docs/fixes.md:77-78`, hiện ghi tên nhánh: FIX-068 `2debb52`, FIX-069 `47efe53`. `--no-ff` giữ nguyên các sha này.
3. `DEBT.md` không cần dòng mới.
4. Sau merge: xuất `openapi.json` ra gốc `main` trước lượt verify tích hợp, vì bước 8 chạy `--compare`, như các lần gộp trước.
