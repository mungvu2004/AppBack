# Review merge fix/b0-01-gate-log-followups → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**. Không phải phiên tác giả. Mọi khẳng định trong commit, `DEBT.md` và báo cáo W13-GATEFOLLOW đều được kiểm lại. Commit đầu nhánh: `54e2e918865d`, gốc `5892c71`, 4 commit:
  - `aa18bd7`: B0-01 + FIX-065
  - `8a1cf3d`: B0-01 + FIX-065
  - `1b6bc06`: B0-01 + FIX-066
  - `54e2e91`: B0-05 + FIX-067
- `main` đã tiến tới `6eddd9e` (`fix/b0-04-layout-and-c11-debts`, FIX-060..064). `git merge-tree --write-tree main HEAD` chỉ xung đột **`DEBT.md`**. 10 file `main` đổi thêm không trùng file nào trong 7 file của nhánh.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Chạy tại chỗ trong worktree sạch của nhánh; trước lượt, `docker ps -q --filter name=verify-run | wc -l` = 1 (< 2). Mã thoát có từ hai nguồn trùng nhau:
  - client: `EXIT=0` từ `$?` của `run.sh` trong shell nền. Shell không bị cắt, nên không cần `docker wait`;
  - dòng `mã thoát: 0` ở cuối log host của chính lượt này, `.cache/src-out/verify/20260922T061028Z-54e2e918865d.log`.
- Bước 5: **`2104 passed, 0 failed, 10 skipped`**, 1 deselected, 257,23 s, 105 warnings. Cả 10 skip là tập tham số rỗng có sẵn của `apps/api/core/tests/test_common.py`. Deselected là test `perf` của B5-01. Số warnings bằng mọi lượt trước trên `main`, nên `catch_warnings` mới không làm mất cảnh báo nào.
- Độ phủ, in từ `tools.coverage_gate` của lượt trên (không lấy từ báo cáo tác giả):
  - tổng: dòng **99,35 %** · nhánh **97,54 %**
  - `packages/messaging`: dòng 100,00 % · nhánh 100,00 %
  - `packages/testing`: dòng 99,12 % · nhánh 100,00 %
  - `tools`: dòng 98,74 % · nhánh 95,76 %
  - tập file bị chạm: dòng **99,30 %** · nhánh **97,83 %**
  - Probe P5 (`coverage run --branch` riêng ba file test bị chạm): mã mới của `steps.py` và `fixtures/messaging.py` được phủ đủ, 0 nhánh thiếu. Dòng thiếu còn lại đều là dòng cũ. Ở `steps.py` đó là `43`, `189->192`, `532`, khớp `42`, `188->191`, `524` của phán quyết trước sau khi dòng dời. Ở `fixtures/messaging.py` đó là các fixture Redis mà bộ test con này không dùng, và `celery_worker` `218-219`, vốn không ai gọi từ trước nhánh. Không dòng nào dính NO-035.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm `node_modules` | đạt |
| 1 | `ruff format --check` | đạt (330 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (282 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu và cuối phiên) |
| `changes/B0-01.md`, `changes/B0-05.md` tồn tại | đạt |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt, cả 4 commit (dài nhất 66 ký tự) |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt)` in `B0-01` ×3, `B0-05` ×1; `Fix:` in `FIX-065` ×2, `FIX-066`, `FIX-067`. Khối trailer liền nhau, có dòng trống trước |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py` gốc, `deploy/**` | không. `tools/verify/{run.sh,steps.py}` là file của chủ B0-01, được FIX-065/066 cho phép (spec [4]) |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không có. Bốn `noqa` mới đều có mã và lý do: `S603` ×3 ở `test_run_sh.py`, `BLE001` ở `steps.py:302` |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

File ngoài cột sở hữu: không có. `tools/verify/*` và `tools/tests/*` thuộc B0-01 (FIX-065/066). `packages/testing/fixtures/messaging.py` và `packages/messaging/tests/test_tasks.py` thuộc B0-05 (FIX-067, đúng spec [4]). Mỗi FIX nằm trong commit riêng có trailer đúng chủ. Nhánh có 191 dòng thêm, trong đó ≈ 45 dòng logic sản phẩm, dưới xa trần 400 của MNT-05.

## Công cụ kiểm tại chỗ

Probe container chạy bằng `run.sh shell < probe.sh`, trên bản sao `/tmp/w`, lệnh `python -m pytest -p no:cacheprovider -o addopts=`. Bản cũ @ `5892c71` đặt tạm ở `.cache/review-probe/` rồi `cp` đè trong container; thư mục này đã xoá. Probe host chạy trong scratchpad của phiên, cũng đã xoá. Mỗi lượt container đều đếm `verify-run` < 2 trước khi chạy.

- **P1 · FIX-065, đỏ → xanh.**
  - `steps.py` @ `5892c71` + test mới → **1 failed**. HEAD → **1 passed**.
  - Driver qua **tiến trình thật** (thay `_ALL_STEPS` bằng một bước in `trước khi nổ` rồi nổ; `VERIFY_LOG_FILE` có đặt):

    | Bản | Lỗi | rc | log: Traceback / `mã thoát` | stderr: Traceback |
    |---|---|---|---|---|
    | cũ | `RuntimeError` | 1 | 0 / không | 1 |
    | cũ | `FileNotFoundError` (qua `steps._run` của công cụ không có) | 1 | 0 / không | 1 |
    | mới | `RuntimeError` | 1 | 1 / `mã thoát: 1` | 1 |
    | mới | `FileNotFoundError` | 1 | 1 / `mã thoát: 1` | 1 |
    | cũ và mới | `KeyboardInterrupt` | 130 | 0 / không | 1 |

    Mã thoát **không đổi** (1 như lúc interpreter tự thoát vì ngoại lệ). Traceback có ở **cả** log lẫn stderr, và stdout cũng có `mã thoát: 1`. `KeyboardInterrupt` vẫn nổi lên, không bị nuốt.
  - Không đặt `VERIFY_LOG_FILE`: rc 1, traceback ra stderr, giống hệt bản cũ.
- **P2 · FIX-066, đỏ → xanh.**
  - `run.sh` @ `5892c71` + test mới → **2 failed** (`[20]`, `[23]`), 2 passed (`[0]`, `[19]`). HEAD → **4 passed**. `shellcheck tools/verify/run.sh` rc 0.
  - `diff` `run.sh` cũ/mới: chỉ **thêm** hằng `VERIFY_LOG_KEEP` (dòng 57-59) và hai dòng dọn trong nhánh `verify` (101-102). `lock`, `openapi`, `merge-heads`, `shell`, `gc`, việc lạ, mount và biến môi trường không đổi một ký tự.
- **P2h · FIX-066 trên host thật (Git Bash, `/usr/bin/find` GNU findutils 4.10.0).** Chạy `run.sh` thật trong repo git tạm tên `cây làm việc`, có `docker` giả trên `PATH`.
  - Thư mục log có 23 file `lượt NN.log` (tên có dấu cách, tên **ngược** thứ tự mtime), một **thư mục** `thư mục.log`, `sub.d/old.log` và `ghi chú.txt` → rc 0, còn đúng **19** log **mới nhất theo mtime**. Thư mục `*.log`, file ở thư mục con và file khác đều còn. `docker` nhận `VERIFY_LOG_FILE=/src-out/verify/<tên mới>`.
  - Thư mục log chưa tồn tại → rc 0.
  - Lượt cổng thật của review: 6 log sẵn → không xoá gì, thành 7.
- **P2x · khi bước dọn hỏng** (xem #1).
  - `rm` giả hỏng trên `PATH` → `run.sh verify` **rc 123**, không in `log cổng:`, **`docker` không được gọi**.
  - Tình huống thật trên Windows: .NET `File.Open(p, Open, Read, ReadWrite)` giữ một file (đúng cách `Get-Content -Wait` mở) thì `/usr/bin/rm` của Git Bash báo `Device or resource busy`, rc 1.
- **P3 · FIX-067, đỏ → xanh.**
  - Fixture @ `5892c71` (thêm đúng hằng `CELERY_PROCESS_ENV` để import được) → **2 failed**. HEAD → **2 passed**.
  - Test probe tạm của review, 4 passed trên HEAD:
    - Sau worker, ca `clean`: `logging._warnings_showwarning is None`, và `captureWarnings(True)` bật lại được.
    - Ca `preset`: capture bật từ trước vẫn được `logging` nhớ.
    - `start_worker` giả gọi đúng `setup_app_for_worker(app, "error", None)` rồi ném `RuntimeError`. Trong lúc đó 5 khoá đã bị đặt (`CELERY_LOG_LEVEL='40'`, `_MP_FORK_LOGFORMAT_='[%(asctime)s: …'`) và capture đã bật. Sau đó `os.environ`, `showwarning`, bộ lọc trước = sau và `_warnings_showwarning is None`.
    - Thân `with` ném lỗi → trạng thái cũng được trả đủ.
  - Trên fixture cũ, hai ca "ném lỗi" đỏ.
- **P3m · đột biến fixture FIX-067** (xem #2):

  | Đột biến | Test của nhánh | Probe review |
  |---|---|---|
  | M1 bỏ `logging.captureWarnings(False)` | **2 passed** (sống) | 3 failed |
  | M2 luôn gọi `captureWarnings(False)` (bỏ điều kiện) | **2 passed** (sống) | 1 failed (`preset`) |
  | M3 bỏ `catch_warnings` | 2 failed | 2 failed |
  | M4 bỏ phần trả `os.environ` | 2 failed | 1 failed |

- **P4 · mã Celery 5.6.3.**
  - `celery/app/log.py:69-75` (`CELERY_LOG_*`, hai `filterwarnings('always', …)`, `captureWarnings(True)`) và `:143` (`_MP_FORK_*`) nằm ngoài `if not receivers` (`:103`).
  - `celery/contrib/testing/worker.py:154` gọi `setup_app_for_worker` (`:219-225` → `app.log.setup`) trong **luồng chính**, trước khi dựng luồng worker. Vậy `catch_warnings` ở luồng chính lưu và trả đúng trạng thái. Lúc `_restoring_process_logging` thoát, `start_worker` đã thoát trước (thứ tự LIFO của `with (…, …)`), nên luồng worker đã dừng.
  - `:82` (`CELERY_LOG_REDIRECT*`) chỉ chạy khi `redirect_stdouts=True`, mà `start_worker` không bật. Test của nhánh so **toàn bộ** `os.environ`, nên khoá nào khác rò cũng sẽ đỏ.
- **P5 · độ phủ mã mới:** xem đầu phán quyết.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | RES-04 · LOG-04 | Việc phụ "dọn log cũ" nay có thể **chặn cả lượt cổng**. Đường ống `find … \| sort \| tail \| cut \| xargs rm` chạy dưới `set -euo pipefail` (`run.sh:6`), nên chỉ cần `rm` hay `find` hỏng là `run.sh verify` thoát trước `run_container`. **Probe P2x:** `rm` hỏng → rc **123**, không `log cổng:`, `docker` không được gọi. Trên Windows điều này xảy ra thật: một log cũ đang bị giữ không kèm quyền xoá (`Get-Content -Wait`, trình xem giữ handle) làm `rm` báo `Device or resource busy`. `find` cũng thoát 1 nếu một file biến mất giữa `readdir` và `stat`. Trước nhánh, `verify` không có đường hỏng này. Xác suất thấp (chỉ file ngoài 19 log mới nhất bị xoá) và thông báo lỗi rõ ràng. Nhưng đây là cổng dùng chung của mọi worktree: dọn dẹp không nên quyết định lượt verify có chạy hay không | `tools/verify/run.sh:101-102` | Cho việc dọn hỏng thì chỉ cảnh báo: `{ find … \| xargs -r -d '\n' rm --; } \|\| echo "dọn log cổng cũ hỏng — bỏ qua, cổng vẫn chạy" >&2`. Thêm một ca vào `test_run_sh.py` với `rm` giả hỏng trên `PATH` (đã có sẵn `docker` giả): `docker` vẫn được gọi và rc 0 |
| 2 | P3 | TEST-02 · R-14 | Test của FIX-067 không chốt nửa `captureWarnings` của bản sửa. `after == before` so `warnings.showwarning`, nhưng chính `catch_warnings` đã trả `showwarning` rồi, nên trạng thái `logging` tự nhớ (`_warnings_showwarning`) không được kiểm. **Probe P3m:** bỏ hẳn `logging.captureWarnings(False)` (M1), hay bỏ điều kiện `showwarning đã đổi` (M2), test vẫn **2 passed**. Với M1, sau worker `logging` tin capture đang bật, nên `captureWarnings(True)` của test sau thành no-op. Với M2, capture bật từ trước bị `logging` quên. Cả hai đúng là dấu NO-087 và spec [6] ("trước = sau cho … `captureWarnings`") muốn chặn. Bản sửa **đúng** (P3: probe hành vi 4 passed); chỉ test chưa đủ chặt | `packages/messaging/tests/test_tasks.py:539-561` (chốt cho `packages/testing/fixtures/messaging.py:208-209`) | Kiểm bằng hành vi, dùng API công khai, sau worker. Ca `clean`: `logging.captureWarnings(True)` phải làm `warnings.showwarning` đổi. Ca `preset`: `logging.captureWarnings(False)` phải trả `warnings.showwarning` về hàm gốc lưu trước `captureWarnings(preset)`. Probe của review đỏ đúng với M1 và M2 |
| 3 | Nit | TEST-02 | Test FIX-066 đặt tên log **tăng** cùng chiều mtime, nên cách cài sắp theo tên cũng xanh. Docstring và comment `run.sh` lại nói rõ "theo mtime". Probe P2h (tên ngược mtime) cho thấy mã đúng, nhưng test chưa chốt điều đó | `tools/tests/test_run_sh.py:57-60` | Đặt mtime ngược thứ tự tên (vd `1_700_000_000 - i`), rồi tính `kept` theo mtime |

**P0: 0 · P1: 0 · P2: 0 · P3: 2 · Nit: 1**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-065 (NO-089) sửa gốc.** Mọi đường tới lượt có log đều đi qua đúng một khối `with _tee_output` trong `cmd_verify`. `try/except Exception` nằm **bên trong** khối đó, nên `traceback.print_exc()` in qua `sys.stderr` (lúc này là `err` trên fd 2 đã nối ống). Traceback vào **cả** log lẫn stderr gốc, `finally` của `_tee_output` flush rồi mới trả fd.
  - Không nuốt lỗi: rc 1, bằng rc interpreter tự trả trước đây (P1).
  - `BaseException` (`KeyboardInterrupt`, `SystemExit`) vẫn nổi lên.
  - Đường không có `VERIFY_LOG_FILE` không đổi.
  - Bảng không in khi một bước nổ. Spec [5] không đòi bảng, và log có output của từng bước tới lúc nổ.
  - Commit `8a1cf3d` bỏ assert thứ tự stdout/stderr của chính test mới. Đứng được: hai ống, hai luồng chép (thiết kế FIX-053) thì không có thứ tự; spec [6] chỉ đòi có mặt. Đây không phải "sửa test cho khớp lỗi" (FIX luật 2), vì assert bỏ đi là ràng buộc thừa của test mới viết.
- **FIX-066 (NO-090), đúng spec [5].**
  - Chỉ xoá `*.log` là **file thường** ở **đúng cấp một** của `.cache/src-out/verify` (`-maxdepth 1 -type f -name '*.log'`). Symlink, thư mục, file thư mục con và file khác không bị đụng (P2h).
  - Đường có dấu cách, có tab hay Unicode vẫn đúng (`%p` sau tab + `cut -f2-`, `xargs -d '\n'`, `rm --`). Thư mục rỗng hay chưa có vẫn rc 0.
  - Hằng `VERIFY_LOG_KEEP=20` có tên, có lý do (≈ 0,5 MB lượt đạt, đủ so lượt đỏ với vài lượt trước) và có đường nâng cấp (chép log ra ngoài).
  - Log của lượt đang chạy luôn mới nhất, nên không bao giờ bị lượt sau xoá. Container của một shell đã bị cắt vẫn ghi an toàn.
  - `in_container.sh` không cần đổi: bản chép `.cache` nay có trần.
- **FIX-067 (NO-087) sửa gốc.** `celery_worker_factory` là đường duy nhất của repo tới `start_worker`. Grep sau khi gộp `main`: `packages/messaging/tests/test_tasks.py` ×9 và `apps/ml/runtime/tests/test_probe_task.py` ×7 đều gọi trong thân test, phạm vi function. Fixture `celery_worker` không ai gọi. Repo không có `captureWarnings`, `filterwarnings`, `catch_warnings` hay `CELERY_LOG_*` nào khác, nên việc trả bộ lọc khi worker dừng không làm mất cài đặt của ai.
  - `_restoring_process_logging` vào **trước** `start_worker`, nên thoát **sau** khi worker đã dừng. Nó trả trạng thái cả khi `start_worker` ném và khi thân `with` ném (P3).
  - Giá trị môi trường có sẵn được giữ nguyên, khoá vắng thì xoá. Capture bật từ trước vẫn còn (ca `preset`).
  - Receiver FIX-059 vẫn gỡ trong `finally` ngoài cùng.
  - Chỉ dùng API công khai. Dòng "chỉ gọi `captureWarnings(False)` khi `showwarning` đã đổi" có lý do ghi trong docstring (R-05).
- **Hợp nhất với `main` @ `6eddd9e`.** API nhánh đổi là `cmd_verify` (người gọi duy nhất: `steps.main`, và chỉ `tools/tests` gọi nó), nhánh `verify` của `run.sh`, và `celery_worker_factory` cùng hằng công khai mới `CELERY_PROCESS_ENV`. `main` từ gốc tới nay không đổi `tools/**`, `deploy/**`, `packages/testing/**` hay `packages/messaging/**`. Lượt cổng đầy đủ của review xanh cho mọi người gọi.
- **R-01/R-02.** Mọi hàm, fixture và hằng mới đều có docstring nói lý do và cạm bẫy, không kể lại mã: `_restoring_process_logging`, `CELERY_PROCESS_ENV`, `_process_logging_state`, `_exploding_step`, `worktree`, `_run_verify` (test), module `test_run_sh.py`.
- **Sổ nợ.** NO-087, NO-089, NO-090 có `✅`, ngày đóng và mã FIX. Tên test và số đỏ/xanh ghi trong dòng khớp P1, P2, P3: 1 failed, 2 failed `[20]`/`[23]`, 2 failed → xanh. Khẳng định "đúng 5 khoá" khớp P3 và P4.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Bỏ assert "`mã thoát: 1` là dòng cuối" trong commit riêng `8a1cf3d` | **Đứng được** (xem mục "đạt") |
| 2 | Dùng `find -printf … \| sort -rn \| tail \| cut \| xargs -d '\n' rm --` thay cho `ls -1t "$log_dir"/*.log \| tail -n +21 \| xargs -r rm --` mà phán quyết trước gợi ý | **Đứng được, và cần thiết.** Probe host: dưới `set -euo pipefail`, gợi ý `ls` với thư mục không có log làm lệnh thoát **2**, vì glob không khớp làm `ls` hỏng. Như vậy lượt đầu của mọi worktree mới đã chết. Bản `find` thoát 0. Trần tính cả log của lượt (19 + 1 = 20) cũng khớp chữ "giữ N file" |
| 3 | FIX-067 chọn sửa thay vì `➖` | **Đứng được.** Phương án đầu của spec [5]; chỉ dùng API công khai (còn khoảng trống test, xem #2) |
| 4 | Một lượt `run.sh shell` khởi động khi đã có 2 container `verify-run` | Tác giả ghi nhận đúng sự thật; các lượt sau đều có chặn. Đây là lệch quy trình, không phải finding mã. Nó không ảnh hưởng kết quả, vì cổng review tự chạy lại |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng có dòng `✅` đúng sự thật | đạt: NO-087, NO-089, NO-090 |
| Nợ mới tác giả nêu | không có. Báo cáo ghi "không có nợ mới", và review không thấy nợ nào tác giả biết mà bỏ sót |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh sinh | không có |
| Nợ do review này chỉ ra đã có dòng | **chưa**, xem dưới |

Dòng đề xuất: id để người điều phối cấp, và phiên này **không** ghi vào `DEBT.md`.

- `| ⬜ | NO-<nnn> | 2026-09-22 | | run.sh verify thoát trước khi chạy cổng nếu bước dọn log cũ (FIX-066) hỏng: find/rm dưới set -euo pipefail, rm gặp log cũ đang bị giữ (Windows "Device or resource busy") → rc 123, docker không được gọi | Việc phụ dọn dẹp nằm trong đường chính của nhánh verify, không có \|\| cảnh báo | B0-01 (tools/verify/run.sh:101-102) | P3 | mở — review merge 2026-09-22 fix/b0-01-gate-log-followups finding #1 (probe P2x: rm giả hỏng → rc 123; .NET File.Open ReadWrite giữ file → rm Git Bash "Device or resource busy"). Chữa: { find … \| xargs -r -d '\n' rm --; } \|\| echo "dọn log cổng cũ hỏng — bỏ qua" >&2; test rm giả hỏng → docker vẫn được gọi, rc 0 |`
- `| ⬜ | NO-<nnn> | 2026-09-22 | | Test FIX-067 test_the_worker_factory_leaves_no_process_logging_state không chốt phần captureWarnings của _restoring_process_logging: bỏ captureWarnings(False) hay bỏ điều kiện "showwarning đã đổi" test vẫn xanh (catch_warnings đã trả showwarning; trạng thái logging tự nhớ không được kiểm) | Test so showwarning/bộ lọc — cả hai do catch_warnings trả — thay vì hành vi của captureWarnings sau worker | B0-05 (packages/messaging/tests/test_tasks.py:539-561) | P3 | mở — review merge 2026-09-22 fix/b0-01-gate-log-followups finding #2 (probe P3m: đột biến M1, M2 sống, 2 passed). Chữa: sau worker, ca clean — captureWarnings(True) phải đổi warnings.showwarning; ca preset — captureWarnings(False) phải trả hàm gốc lưu trước khi bật |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (P3 #1) | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #2; Nit #3) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,40 + 0,50 + 0,28 + 0,25 + 0,15 = **4,83 / 5**

## PHÁN QUYẾT: APPROVE

Lượt cổng do review tự chạy thoát 0: `2104 passed, 0 failed, 10 skipped`. Độ phủ đạt ở mọi gói bị chạm (tập file bị chạm 99,30 % dòng · 97,83 % nhánh). Không có P0, P1 hay P2; điểm 4,83 ≥ 4,0. Ba FIX đều sửa đúng gốc, đúng phạm vi [4]. Review đã tự tái hiện đỏ trước / xanh sau cho cả ba (P1, P2, P3).

- **FIX-065** không nuốt lỗi. Qua tiến trình thật, mã thoát vẫn 1, traceback có ở cả log lẫn stderr, và log có `mã thoát: 1`. `KeyboardInterrupt` vẫn nổi lên.
- **FIX-066** chỉ xoá `*.log` thường ở cấp một, theo mtime, an toàn với thư mục rỗng hay chưa có và với tên có dấu cách. Điều này đúng cả trong container lẫn Git Bash thật. Mọi việc khác của `run.sh` không đổi một ký tự.
- **FIX-067** trả đủ môi trường, bộ lọc `warnings` và capture của `logging`, kể cả khi `start_worker` ném. Người gọi trên `main` đều xanh.

Hai P3 và một Nit không chặn merge:

- #1: bước dọn hỏng thì chặn cổng.
- #2: test FIX-067 không chốt được `captureWarnings`.
- Nit #3: test FIX-066 không phân biệt mtime với tên.

Điều kiện cho phiên merge:

1. **Trước hoặc cùng lúc merge** (R-34, R-38): ghi hai dòng `DEBT.md` `⬜` P3 ở trên, #1 cho chủ B0-01 và #2 cho chủ B0-05 (hoặc giao FIX). Nit #3 để tác giả tự quyết.
2. Gộp bằng `git merge --no-ff`, **không** squash (R-36: nhánh mang trailer của B0-01 **và** B0-05, cùng `Fix: FIX-065/066/067`).
3. Giải xung đột `DEBT.md`, xung đột duy nhất:
   - lấy của `main`: NO-079, NO-081 `✅`, NO-082 `✅`, NO-088 `✅`;
   - lấy của nhánh: NO-087 `✅`, NO-089 `✅`, NO-090 `✅`;
   - thứ tự dòng giữ NO-086 → NO-087 → NO-088 → NO-089 → NO-090.
4. Điền sha vào cột "Commit" của `docs/fixes.md:74-76`, hiện đang ghi tên nhánh: FIX-065 `aa18bd7` (+ `8a1cf3d`), FIX-066 `1b6bc06`, FIX-067 `54e2e91`. `--no-ff` giữ nguyên các sha này.
5. Sau merge: xuất `openapi.json` ra gốc `main` trước lượt verify tích hợp, vì bước 8 chạy `--compare`, như các lần gộp trước. Lượt đó cũng tự áp trần log mới lên `F:/AppBack/.cache/src-out/verify`: log trên 19 lượt cũ nhất sẽ bị xoá. Log nào cần giữ thì chép ra ngoài trước.
