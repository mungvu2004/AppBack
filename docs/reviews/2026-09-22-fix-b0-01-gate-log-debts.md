# Review merge fix/b0-01-gate-log-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo W10-GATELOG đều tự kiểm lại) · Commit đầu nhánh: `28e3ab489bec` (gốc `a74100c`, 5 commit: `fc5da84` B0-01 + FIX-052, `b8e896a` B0-01 + FIX-053, `81ac394` B0-05 + FIX-059, `2138e2d` B0-05, `28e3ab4` B0-05). Từ lúc giao việc, `main` đã đi tới `20af9de` (`fix/b0-04-key-layout-debts`, NO-083..086 của B0-08, NO-088, hai phán quyết). `git merge-tree --write-tree 20af9de HEAD` chỉ xung đột **`DEBT.md`**. 12 file `main` đổi thêm rời hẳn 6 file của nhánh.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Chạy tại chỗ trong worktree sạch của nhánh, lúc đó 0 container `verify-run` khác. Mã thoát lấy từ client (`EXIT=0`) **và** từ dòng `mã thoát: 0` ở cuối file log host mà chính FIX-053 ghi: `.cache/src-out/verify/20260922T052335Z-28e3ab489bec.log` (21 328 byte), hai nguồn trùng nhau. Bước 5: **`2052 passed, 0 failed, 10 skipped`**, 1 deselected, 259,7 s. Cả 10 skip là `apps/api/core/tests/test_common.py` có sẵn từ trước, không skip mới.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,34 %** · nhánh **97,48 %**
  - `packages/messaging`: dòng 100,00 % · nhánh 100,00 % · `packages/testing`: 99,09 % · 100,00 % · `tools`: 98,73 % · 95,76 %
  - tập file bị chạm: dòng **99,26 %** · nhánh **97,73 %**
  - Probe P11 (`coverage run --branch` riêng hai file sửa): `tools/verify/steps.py` chỉ thiếu `42`, `188->191`, `524`, cả ba là dòng cũ. Toàn bộ mã tee/`_infra_failure` mới được phủ cả dòng lẫn nhánh.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm `node_modules` | đạt |
| 1 | `ruff format --check` | đạt (326 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (281 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision, 10/10) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu và cuối phiên) |
| `changes/B0-01.md`, `changes/B0-05.md` tồn tại | đạt |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt, cả 5 commit |
| Trailer đọc được (R-36b) | đạt. Mỗi commit có `Prompt:` (`B0-01` ×2, `B0-05` ×3); ba commit sửa có thêm `Fix: FIX-052/053/059` |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py` gốc, `deploy/compose/verify.yml` | không. `tools/verify/*` là file của chủ B0-01, FIX-052/053 cho phép (spec [4]) |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không có (grep diff rỗng) |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

File ngoài cột sở hữu: không có. `tools/verify/{run.sh,steps.py}` và `tools/tests/test_steps_commands.py` thuộc B0-01 (FIX-052/053). `packages/testing/fixtures/messaging.py` và `packages/messaging/tests/test_tasks.py` thuộc B0-05 (FIX-059). Mỗi FIX nằm trong commit riêng, trailer đúng chủ. Nhánh ≈ 130 dòng logic sản phẩm và ≈ 160 dòng test, dưới trần 400 của MNT-05.

## Công cụ kiểm tại chỗ

Mọi probe chạy trong container verify (`run.sh shell < script`, bản sao `/tmp/w`, `python -m pytest -p no:cacheprovider -o addopts=`). File bản cũ đặt tạm dưới `.cache/review-probe/` rồi `cp` đè trong container, đã xoá sau phiên. Luôn đếm `verify-run` < 2 trước mỗi lượt.

- **P1 · FIX-052 đỏ → xanh.** Đặt `steps.py` @ `a74100c` → `test_verify_chép_mẫu_hỏng_vẫn_in_đủ_bảng_và_thoát_1` **1 failed**. Probe gốc NO-075 (`VERIFY_OUT_DIR=/proc/rv CONTRACT_SAMPLES_DIR=… verify --steps 1`) trên mã cũ: rc 1, **0 dòng bảng**, `FileNotFoundError: '/proc/rv'`. Trên HEAD: test **1 passed**. Cùng probe cho rc 1, có đủ bảng: dòng `1 | ruff format --check | đạt` và `— | chép mẫu golden | hỏng | lỗi hạ tầng cổng: [Errno 2] … '/proc/rv'`.
- **P2 · FIX-053 đỏ → xanh.** Đặt `steps.py` @ `fc5da84` → `-k "log or write_each or mồ_côi"` **5 failed**. Trên HEAD: 5 passed. Cả `tools/tests/` **253 passed**.
- **P3 · một bước ném ngoại lệ lạ, `VERIFY_LOG_FILE` có đặt** (driver thay `_ALL_STEPS` bằng một bước `print("trước khi nổ"); raise RuntimeError`, rồi `sys.exit(steps.main(["verify"]))`). Tiến trình rc 1, traceback đầy đủ ra stderr. **File log chỉ có `trước khi nổ`**: không traceback, không `mã thoát` (xem #1).
- **P4 · thư mục log không tạo được** (`VERIFY_LOG_FILE=/proc/rv/verify/x.log`): rc 1, 0 dòng bảng, traceback `FileNotFoundError` trước bước đầu. Đúng thiết kế đã ghi trong docstring và test (xem mục "lệch").
- **P5 · `OUT_DIR` hỏng, log bình thường:** log có dòng `chép mẫu golden hỏng: …` (stderr), bảng 2 dòng gồm dòng `—`, và `mã thoát: 1`. Trường hợp NO-075 vẫn chạy trọn và vẫn để lại log.
- **P6 · kịch bản NO-080 đầu-cuối, giết client giữa lượt.** Chạy `run.sh verify --steps 1,2,3,4` nền. Container `…-verify-run-f14fee90dab3` (AutoRemove `true`) lên sau khoảng 6 s. Khoảng 12 s sau đó, lúc còn `uv sync`, `Stop-Process -Force` giết `docker-compose.exe` và `docker.exe` của đúng project `appback-verify-appback-fix-db`; client rc 127. Container vẫn chạy tiếp rồi tự xoá, nên `docker wait` trả `No such container`. File host `20260922T053133Z-28e3ab489bec.log` vẫn có trọn output `lint-imports`, bảng 4 dòng `đạt` và **`mã thoát: 0`**. Không còn nguồn nào khác cho mã thoát: đây đúng là giá trị FIX-053 mang lại.
- **P7 · FIX-059 đỏ → xanh.** Đặt fixture @ `b8e896a` → test mới **1 failed** `(40, [StreamHandler]) == (30, [_LiveLoggingNullHandler…])`. Chạy sau `test_a_valid_task_runs_on_a_real_worker` vẫn **1 failed** (handler bắt log của pytest bị thay). Đường cũ, test thăm dò sau worker: `ROOT 40 [StreamHandler <stderr>, LogCaptureHandler ×2]`. Trên HEAD: 1 passed, và 2 passed khi chạy sau test worker khác.
- **P8 · receiver không rò.** Test thăm dò tạm thời:
  - trong worker, `setup_logging.receivers` có **1** receiver; sau worker còn `[]`;
  - `start_worker` bị vá cho ném `RuntimeError` thì receiver vẫn gỡ (`finally`);
  - sau cả `test_tasks.py`, logger gốc ở mức 30 và giữ handler của pytest.
  - Kết quả: 49 passed.
- **P9 · người gọi factory trên `main`:** `packages/messaging packages/testing apps/ml/runtime` **307 passed**. `apps/ml/runtime/tests/test_probe_task.py` dùng `celery_worker_factory` 7 lần. Ngoài factory, repo không có `start_worker`, `setup_logging` hay `worker_hijack` nào khác.
- **P10 · mã Celery 5.6.3** (`celery/app/log.py`):
  - `_configure_logger(root, …)` (đặt mức) nằm trong `if not receivers`, nhưng **ngoài** `if worker_hijack_root_logger`. Vậy `worker_hijack_root_logger=False` không đủ, đúng như docstring `_keep_root_logger` viết.
  - Ba nhóm dòng nằm **ngoài** `if not receivers`: `os.environ.update(CELERY_LOG_*)`, `warnings.filterwarnings('always', C*DeprecationWarning)`, `logging.captureWarnings(True)` (dòng 69–75), và `os.environ.update(_MP_FORK_*)` (dòng 141–145). NO-087 nói đúng sự thật; P8 đo được cả ba dấu còn lại sau worker.
- **P11 · độ phủ mã mới:** xem đầu phán quyết.
- **Rò bí mật:** grep log lượt đầy đủ (`password|secret|token=|AKIA|minioadmin|PRIVATE`) → 0 dòng. Log chép đúng stdout và stderr của lượt. Nó nằm ở `.cache/` (git-ignore) trên host, cùng mức tin với terminal. `verify.yml` không đưa bí mật thật nào vào container.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG-06 · OBS-01 | Lượt verify kết thúc bằng **ngoại lệ** thì file log host dừng ở dòng output cuối: không traceback, không dòng `mã thoát`. `_tee_output` trả fd 1/2 trong `finally`, nên traceback do interpreter in ra **sau** khi ống đã gỡ, chỉ đi ra stderr gốc. **Probe P3:** log chỉ có `trước khi nổ`. `run_steps` không bắt ngoại lệ của bước. `_run` → `subprocess.run` ném `FileNotFoundError` khi thiếu công cụ trong venv; `merged_prompts` cũng có thể ném; cả hai đều ra đường này. Đây đúng là tình huống FIX-053 sinh ra để cứu (client đã chết, người đọc chỉ còn file log), và spec [5] đòi "toàn bộ output của lượt". Hiếm gặp, không làm sai mã thoát | `tools/verify/steps.py:295-297` | Trong khối `with`: `try: rc = _run_verify(args)` / `except Exception: traceback.print_exc(); rc = 1`, rồi vẫn `print(f"mã thoát: {rc}")`. `KeyboardInterrupt` vẫn cứ nổi lên. Thêm một test: bước ném `RuntimeError` → log có `Traceback`, `RuntimeError` và `mã thoát: 1` |
| 2 | P3 | OPS-04 · R-34 | Log cổng dồn mãi, không có trần:<br>• mỗi lượt `run.sh verify` thêm một file dưới `.cache/src-out/verify/` (lượt đạt ≈ 21 KB, lượt đỏ lớn hơn nhiều); worktree này đã tích 5 file trong khoảng 25 phút (review xoá lại 1 file probe của mình);<br>• `gc` không đụng tới thư mục này, và `in_container.sh` chép cả `.cache` vào `/tmp/w` ở **mỗi** lượt;<br>• worktree bị xoá thì mất theo; checkout sống lâu (`F:/AppBack`, nơi người điều phối verify sau mỗi lần gộp) thì dồn mãi.<br>Tác giả có nêu ở "Lệch khỏi prompt" (4) nhưng không ghi dòng `DEBT.md` | `tools/verify/run.sh:93-97` | Một dòng trước khi tạo file mới: `ls -1t "$log_dir"/*.log 2>/dev/null \| tail -n +21 \| xargs -r rm --` (giữ 20 lượt gần nhất). Hoặc ghi `DEBT.md` dòng dưới |
| 3 | Nit | R-01 | Hàm cấp module mới `_no_step` không có docstring; mọi helper khác của diff (`_table_rows`, `_printing_step`, `log_file`) đều có | `tools/tests/test_steps_commands.py:614` | Một câu: "Bước giả: bị gọi là test hỏng — chứng minh log hỏng thì không bước nào chạy" |

**P0: 0 · P1: 0 · P2: 0 · P3: 2 · Nit: 1**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-052 (NO-075) sửa gốc:** mọi lỗi chép mẫu golden đi qua đúng một lời gọi `export_contract_samples()` trong `_run_verify`, và chỗ đó bọc `except OSError`. `shutil.Error` là `OSError` nên cũng được bắt. Dòng bảng `—` có trạng thái `hỏng`, thoát 1; lỗi đầy đủ ra stderr, dòng bảng giữ dòng đầu ≤ 160 ký tự. Không nuốt lỗi. Dòng lỗi hạ tầng dựng chung qua `_infra_failure`: bước 0 dùng lại, thông báo stderr y như cũ (`làm ấm node_modules hỏng: …`), đúng R-07. `_table_rows` cũng được tách ra dùng lại ở test cũ.
- **FIX-053 (NO-080), thiết kế tee:**
  - fd 1 và fd 2 mỗi fd một ống và một luồng chép. `os.dup2` để tiến trình con thừa kế đầu ghi; đầu đọc và bản `dup` fd gốc thì không thừa kế (PEP 446). Nhờ vậy output của ruff, pytest, `coverage_gate` vào log (P6: có trọn output `lint-imports`; lượt đầy đủ: có tóm tắt pytest và khối `coverage_gate`). stdout và stderr vẫn tách.
  - Mỗi khúc được `flush` ngay, nên container bị giết giữa chừng vẫn để lại phần đã chạy (log `…051401Z…` của tác giả dừng ở `$ mypy`).
  - Luồng không chết khi một đích hỏng (`_write_each` bỏ đích đó; đĩa đầy đã có test). Luồng chết thì ống đầy và cổng treo, docstring `_pump` nói đúng cạm bẫy này.
  - Đợi luồng xả tối đa `LOG_DRAIN_TIMEOUT_S` rồi mới thoát, nên dòng cuối (bảng, `mã thoát`) không mất khi PID 1 kết thúc. Một `tee` bash trong `in_container.sh` sẽ đua với lúc PID 1 thoát, nên chọn Python là có lý do (R-10).
  - Tiến trình con mồ côi không treo cổng (có test).
  - Lượt đầy đủ của review: 0 dòng "còn giữ fd" hay "bỏ một đích". Pytest 259,7 s, không chậm hơn lượt của tác giả (330 s).
- **`run.sh`, hành vi cũ giữ nguyên:**
  - Mã thoát: `run_container` vẫn là lệnh cuối của nhánh `verify` dưới `set -e` (lượt đạt: `EXIT=0`; P5: rc 1).
  - `lock`, `openapi`, `merge-heads`, `shell`, `gc` không đổi một dòng.
  - Chỉ `verify` mount thêm `-v .cache/src-out/verify:/src-out/verify` (cùng lối với `lock`/`openapi`, không đổi `verify.yml`, đúng spec [4]). Mount này không đè `VERIFY_OUT_DIR=/src-out`, và `_clean_dir` của `contract-samples` không chạm tới nó.
  - Tên log dùng giờ UTC và sha 12 ký tự. Trùng tên trong cùng một giây thì ghi nối (có test).
  - Dòng `mã thoát: N` chỉ thêm khi có `VERIFY_LOG_FILE`. Repo không có ai đọc dòng cuối stdout của cổng.
- **FIX-059 (NO-078) sửa gốc:** `celery_worker_factory` là **đường duy nhất** của repo tới `start_worker` (fixture `celery_worker` và 7 lượt của `apps/ml/runtime` cũng đi qua nó, P9).
  - Receiver nối trước `start_worker`, gỡ trong `finally` (P8, kể cả khi `start_worker` ném).
  - Receiver là hàm cấp module nên tham chiếu yếu của `Signal.connect` không làm mất nó.
  - Test mới kiểm cả **trong** lẫn **sau** worker, cộng một `WARNING` sau worker vào được `caplog` mà không cần `at_level`. Kết quả đỏ ở cả hai thứ tự chạy (P7).
- **Hợp nhất với `main`:** API nhánh đổi là `cmd_verify` (tách `_run_verify`), `_infra_failure` và hành vi `celery_worker_factory`. Mọi người gọi của chúng trên `main` @ `20af9de` đã được grep: `steps.main` chỉ có ở `tools/tests`; factory có ở `packages/messaging`, `apps/ml/runtime` (P9 xanh). `main` không đổi `tools/**`, `deploy/**` hay fixture nào kể từ `a74100c`.
- **Sổ nợ:** NO-075, NO-078, NO-080 `✅` có ngày đóng, mã FIX, test và kết quả đỏ/xanh; mọi con số trong các dòng này khớp P1, P2, P7. NO-087 `⬜` Nit, chủ B0-05, nội dung đúng (P8, P10).

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | FIX-052 chọn "một dòng bảng" thay vì "in bảng trước" | **Đứng được.** Spec [5] cho cả hai phương án; lỗi đã bắt thì chép trước hay sau bảng không quan trọng, và dòng `—` còn vào được log (P5) |
| 2 | FIX-053 ghi log ở `steps.py`, mount bằng `-v` trong `run.sh`, không đổi `verify.yml` | **Đứng được.** Đúng spec [4] |
| 2a | Output `uv sync` (trước `steps.py`) không vào log | **Đứng được.** `uv sync` hỏng thì thoát trong vài giây đầu, khi client hầu như còn sống. File log chưa tạo, nhưng mã thoát vẫn lấy được bằng `docker wait` |
| 2b | Tiến trình con thấy ống thay vì TTY, mất màu ANSI khi chạy từ terminal tương tác | **Đứng được.** Nội dung không đổi |
| 2c | stdout thêm dòng `mã thoát: N` | **Đứng được.** Không ai đọc dòng này |
| 2d | Log dồn dưới `.cache/src-out/verify/`, `gc` không dọn | Đúng sự thật, nhưng là nợ chưa ghi → **#2** |
| 2e | Không mở được file log thì `OSError` trước bước đầu | **Đứng được** (P4). Dưới `run.sh`, thư mục log là bind-mount do `mkdir -p` dựng sẵn; hỏng ở đây nghĩa là host hay mount hỏng. Dừng ngay còn hơn chạy 6 phút mà không có log. `OUT_DIR` hỏng (đúng ca NO-075) thì cổng vẫn chạy trọn (P5) |
| 3 | FIX-059 dùng receiver `setup_logging` thay vì lưu và trả mức + handler | **Đứng được.** Đây là phương án đầu của spec [5]; P10 cho thấy chỉ receiver mới chặn được việc đặt mức |
| 4 | Không gộp `main` mới; `DEBT.md` sẽ xung đột | Đúng: `merge-tree` chỉ xung đột `DEBT.md` (xem điều kiện 3) |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng có dòng `✅` đúng sự thật | đạt: NO-075, NO-078, NO-080 |
| Nợ mới tác giả nêu có dòng | đạt: NO-087 (Nit, `⬜`, id người điều phối cấp; commit `28e3ab4` đổi từ NO-083 vì B0-08 đã dùng id đó) |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh sinh | không có |
| Nợ do review này chỉ ra đã có dòng | **chưa**, xem dưới |

Dòng đề xuất (id để người điều phối cấp; phiên này **không** ghi vào `DEBT.md`):

- `| ⬜ | NO-<nnn> | 2026-09-22 | | Lượt verify kết thúc bằng ngoại lệ (bước ném lỗi lạ, vd FileNotFoundError khi thiếu công cụ trong venv) thì file log host của FIX-053 dừng ở dòng output cuối: không traceback, không dòng "mã thoát" — đúng lúc client compose đã chết người đọc không biết vì sao | _tee_output trả fd 1/2 trong finally rồi ngoại lệ mới nổi lên; interpreter in traceback ra stderr gốc, ngoài log | B0-01 (tools/verify/steps.py:295-297) | P3 | mở — review merge 2026-09-22 fix/b0-01-gate-log-debts finding #1 (probe P3: bước ném RuntimeError → log chỉ có "trước khi nổ"). Chữa: trong khối with, except Exception: traceback.print_exc(); rc = 1, vẫn in "mã thoát"; test log có Traceback và "mã thoát: 1" |`
- `| ⬜ | NO-<nnn> | 2026-09-22 | | Log cổng .cache/src-out/verify/*.log (FIX-053) không bao giờ được dọn: mỗi lượt run.sh verify thêm một file (≈ 21 KB lượt đạt), gc không đụng tới, in_container.sh chép cả .cache vào /tmp/w mỗi lượt; checkout sống lâu (F:/AppBack) dồn mãi | FIX-053 chọn một file mỗi lượt để giữ lượt trước, chưa đặt trần | B0-01 (tools/verify/run.sh:93-97) | P3 | mở — review merge 2026-09-22 fix/b0-01-gate-log-debts finding #2; tác giả đã nêu ở "Lệch khỏi prompt" (4). Chữa: run.sh verify giữ 20 file mới nhất (ls -1t "$log_dir"/*.log \| tail -n +21 \| xargs -r rm --) trước khi tạo file mới |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #1) | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 4 (P3 #2) | 0,20 |
| MNT – Bảo trì | 3 % | 5 (Nit #3) | 0,15 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,35 + 0,20 + 0,15 = **4,80 / 5**

## PHÁN QUYẾT: APPROVE

Lượt cổng do review tự chạy thoát 0: `2052 passed, 0 failed, 10 skipped`, độ phủ đạt ở mọi gói bị chạm (tập file bị chạm 99,26 % dòng · 97,73 % nhánh). Không có P0, P1 hay P2; điểm 4,80 ≥ 4,0. Ba FIX đều sửa đúng gốc, đúng phạm vi [4], và review đã tự tái hiện đỏ trước / xanh sau cho cả ba (P1, P2, P7).

- FIX-052 bắt lỗi chép mẫu ở đúng một chỗ mọi đường đi qua.
- FIX-053 được chứng minh đầu-cuối, không chỉ bằng unit test: giết client compose giữa lượt thì container chạy tiếp và tự xoá, còn file log trên host vẫn có trọn bảng và `mã thoát: 0` (P6). Mã thoát, bảng và năm việc khác của `run.sh` không đổi.
- FIX-059 đặt receiver ở đường duy nhất tới `start_worker`, gỡ sạch cả khi `start_worker` ném, và không làm hỏng người gọi nào trên `main` (P8, P9).

Hai P3 (#1: log thiếu traceback khi lượt nổ ngoại lệ; #2: log không có trần) và một Nit không chặn merge.

Điều kiện cho phiên merge:

1. **Trước hoặc cùng lúc merge** (R-34, R-38): ghi hai dòng `DEBT.md` `⬜` P3 chủ B0-01 ở trên cho #1 và #2 (hoặc giao FIX). Nit #3 để tác giả tự quyết.
2. Gộp bằng `git merge --no-ff`, **không** squash (R-36: nhánh mang trailer của B0-01 **và** B0-05, cùng `Fix: FIX-052/053/059`).
3. Giải xung đột `DEBT.md` (xung đột duy nhất). Giữ các dòng của `main`: NO-076 `✅`, NO-077 `✅`, NO-081, NO-083..NO-086, NO-088. Giữ các dòng của nhánh: NO-075 `✅`, NO-078 `✅`, NO-080 `✅`. Chèn NO-087 giữa NO-086 và NO-088. NO-079 và NO-082 hai bên giống nhau.
4. Điền sha vào cột "Commit" của `docs/fixes.md` (hiện ghi tên nhánh): FIX-052 `fc5da84`, FIX-053 `b8e896a`, FIX-059 `81ac394`. `--no-ff` giữ nguyên các sha này.
5. Sau merge: `main` cần `openapi.json` xuất ra gốc trước lượt verify tích hợp (bước 8 so `--compare`), như các lần gộp trước.
