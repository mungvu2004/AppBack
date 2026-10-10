# Review merge perf/test-speed-be → main

- Ngày: 2026-10-11 · Reviewer: phiên /merge-review (độc lập, không phải tác giả) · Commit đầu nhánh: 981e0e9506bd
- Prompt: PERF-01 (`backend/prompts/PERF-01.md`), `changes/PERF-01.md` có. Người dùng đã duyệt cho PERF-01 sửa `tools/verify/*`, `pyproject`, `conftest.py` gốc, cache mypy theo băm cây.
- Cổng: Phạm vi kiểm: đầy đủ — đọc log cổng của việc gộp (B6-01: reviewer không chạy lại cổng). `bash tools/verify/run.sh verify` mã thoát 0
  (log: `backend/dieu-phoi/chay/PERF-01/do-cuoi/be-cuoi2.log` = `<wt>/.cache/src-out/verify/20261010T191738Z-981e0e9506bd.log`).
  Khớp cây: `git -C <wt> rev-parse HEAD` = 981e0e95…, `git status --porcelain` rỗng; container `appback-verify-perf-be-…`, venv `/work/venv-perf-be` (VERIFY_NAME=perf-be).
  Bảng 10/10 bước đạt (0, 1, 2, 3, 4, 5, 5b, 6, 7, 8); `8426 passed` (log cổng main @ 7ee351ab: 8411 → tăng ròng 15; main sau đó chỉ đổi `APPFRONT_SHA`).
- Độ phủ: tổng dòng 99,47% · nhánh 98,02%; mọi gói bị chạm ≥ 90/90 (thấp nhất `apps/worker/pipeline_persist` 98,48/90,62); tập file bị chạm 99,30/98,44.
- Tái hiện của reviewer (lệnh đích, `run.sh shell`): (a) `start_mypy`+`join_mypy` riêng → in `Success: no issues found in 1156 source files`;
  (b) ghi mốc 9 byte vào `/tmp/mypy.log`, `pytest -n 2 tools/ci/tests tools/tests` → còn 0 byte; chạy từng test của `test_steps_commands.py` → 3 test làm rỗng (F1);
  (c) GNU tar 1.35 trên host: tệp đã theo dõi bị `rm` chưa stage → `Cannot stat`, pipeline rc=2 (F2); (d) nạp `ml_ocr.py` thêm 0,23 s/tiến trình — không phải finding.

Soát bất biến: không xoá/skip/xfail test nào ngoài 2 hàm test của hành vi "mypy nguội" đã được thay có duyệt (`test_verify__full_gate_runs_mypy_cold`, `test_cold_mypy_cache__unset_variable_stays_unset`; thay bằng 12 test mới); không nới/bớt `assert`
(9 dòng `-assert` đều có bản thay tương đương hoặc thuộc hành vi đã thay); ngưỡng độ phủ, `testpaths`, số bước cổng giữ nguyên; không chạm `docs/charter/*`,
`openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`; `# noqa: S603`, `# type: ignore[import-untyped]` (chuyển chỗ), `# type: ignore[arg-type]` đều có mã.
Đã soát và không có finding: `db.py` `_RESEQUENCE_SQL` (`pg_depend` `deptype IN ('a','i')` + `relkind='S'` = đúng tập `pg_get_serial_sequence` trả; chuỗi
không thuộc cột nào vẫn không đặt lại như trước); `ordering.py` (`list.sort` tại chỗ, ổn định, không mất/trùng, không phụ thuộc xdist, `trylast` sau lọc `-m`/`ci_split`);
`api_env` `ARGON2_PROFILE=test` (mọi test đổi `APP_ENV=dev` đều `match=` lỗi riêng, test rehash tự dựng băm; không test nào cần hồ sơ sản phẩm);
mypy nền (bước 3 lấy `proc.wait()` thật; dừng sớm giết tiến trình, bước 3 "chưa chạy"; băm phủ `.py/.pyi` dưới `files`, `pyproject.toml`, `uv.lock`, phiên bản mypy;
không gì trong `packages|apps|tools` nhập module ngoài gốc); cache ảnh quality (trả `.copy()`, bytes bất biến); `SyntheticPlan` mảng `setflags(write=False)`;
`RapidOcrReader` dùng chung (`pinned_name` không ảnh hưởng, `reader.py:309-320`); `model.py` nạp `transformers` trong hàm — hành vi sản phẩm giữ nguyên.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F1 | P2 | TEST-02 (tác động OBS) | Test ghi đè log mypy THẬT của lượt cổng: fixture `repo` vá `_popen` nhưng không vá `MYPY_LOG`; `test_verify_làm_ấm_node_modules_trước_bước_5[argv0]`, `test_verify_làm_ấm_hỏng_là_lỗi_hạ_tầng_của_cổng[error0,error1]` gọi `steps.main(["verify"])` với `_ALL_STEPS` thật → `background_mypy()` → `start_mypy()` → `MYPY_LOG.open("wb")` cắt `/tmp/mypy.log` trong lúc bước 5 chạy song song mypy nền. Bằng chứng: log cổng dòng 460 `--- mypy (nền) ---` rỗng (cả log 7b705f9c), trong khi chạy riêng in `Success: …`; tái hiện (b). Trạng thái bước 3 vẫn từ mã thoát thật nên kết quả cổng này hợp lệ, nhưng khi mypy đỏ ở cổng đầy đủ thì lỗi của nó mất khỏi log. | `tools/tests/test_steps_commands.py:84-102` (fixture `repo`), `:1021`, `:1054`; `tools/verify/steps.py:151,246` | Trong `repo`: `monkeypatch.setattr(steps, "MYPY_LOG", tmp_path / "mypy.log")`; nên thêm: đặt `MYPY_LOG` riêng theo lượt (cạnh `VERIFY_LOG_FILE`/`mkstemp`) để không tiến trình nào khác đè được. Ghi `DEBT.md` trước khi gộp (R-38). |
| F2 | P3 | OPS / R-19 | `run.sh` dựng tar từ `git ls-files -co`: tệp đã theo dõi bị xoá nhưng chưa stage vẫn được liệt kê → `tar` "Cannot stat", rc=2, `set -euo pipefail` dừng cả `run.sh` (mọi việc: verify/shell/lock). `cp -r` cũ không vướng. Đóng an toàn (không gửi nguồn sai) nhưng chặn worker đang xoá tệp. Tái hiện (c). | `tools/verify/run.sh:66` | Thêm `--ignore-failed-read` cho `tar`, hoặc trừ `git ls-files -d` khỏi danh sách. |
| F3 | P3 | CON-06 | Tên tạm cố định `src.tar.tmp` và mount cả thư mục `src-tar`: hai lượt cùng worktree (ENV §4 cho 2 lượt song song) ghi chung một `.tmp`; và container của lượt A giải nén sau `docker build`, lúc đó `src.tar` có thể đã là của lượt B → log mang sha A nhưng kiểm cây B. Chú thích "lượt song song không đọc tar nửa vời" không đúng hết. | `tools/verify/run.sh:64-68,111` | `mktemp` một tên tar riêng mỗi lượt, mount đúng tệp đó (`-v <tar>:/src-tar/src.tar:ro`), xoá sau lượt. |
| F4 | P3 | TEST-02 | `test_canvas_scan` nhớ kết quả quét vào `.pytest_cache` theo `(đường, mtime_ns, size)`, không theo nội dung — cùng họ "phát lại kết quả cũ" của NO-306 (công cụ giữ mtime + cùng cỡ → đạt giả). Ở cổng `/tmp/w` mới mỗi lượt và tar không mang `.pytest_cache` nên không bao giờ trúng: không mua được gì ở cổng. | `packages/messaging/tests/test_canvas_scan.py:56-79` | Bỏ cache (quay lại `assert scan(REPO_ROOT) == []`) hoặc khoá theo băm nội dung. |
| F5 | P3 | PERF-06 | `_cached_render_plan` `lru_cache(maxsize=None)` giữ 40 `SyntheticPlan` 1600x1200 (pixels 5,76 MB + mask 1,92 MB + PNG) ≈ 300 MB trong một worker suốt tệp, trên máy mà RAM là trần (CLAUDE.md của chính PERF-01 nói vậy). Đúng đắn: mảng chỉ đọc, không rò. | `apps/ml/ml_eval/tests/test_tasks.py:54-68` | Ghi số đo RSS vào docstring, hoặc chỉ nhớ `image_png`/đáp án thay vì cả `pixels`. |
| F6 | Nit | TEST-02 | Biên thời gian thu hẹp: watchdog stall 0,3 s x 3 epoch so grace 0,2 s + poll 0,05 s → còn ~0,65 s (trước ~8 s); `BLOCKED_PROBE_S` 0,5 → 0,15 s làm khẳng định "người ghi chưa xong" kém nhạy, câu "đủ dài để một lượt `create_version` tự do xong" không có số đo trong diff. Đều đóng an toàn (đỏ chứ không xanh giả) trừ độ nhạy probe. | `apps/ml/training_runner/tests/test_runner.py:322-323,678-679`; `apps/worker/pipeline_persist/tests/test_persist_lock.py:40-43` | Khẳng định thêm `blocked_s >= RELEASE_AFTER_S - BLOCKED_PROBE_S` (chứng minh dương là đã bị chặn) thay vì chỉ log. |
| F7 | Nit | R-36b | 5 commit có dòng trống giữa `Prompt:` và `Co-Authored-By:` → `%(trailers:key=Prompt)` rỗng: 25bc0c2e, 52f4f278, ca93578b, 03029e70, 7eebbee5. Squash thay thông điệp nên không chặn. | lịch sử nhánh | Thông điệp squash: khối trailer liền nhau; kiểm `git log -1 --format='%(trailers:key=Prompt,valueonly)'` in `PERF-01`. |

Không ghi MNT-05: phần logic ngoài test/JSON/chú thích < 400 dòng (phần lớn +784 là test, docstring và `test_durations.json`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4 (F3) | 0,60 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 4 (F5) | 0,40 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 3 (F1, F4) | 0,21 |
| OBS, OPS | 5% | 4 (F2) | 0,20 |
| MNT | 3% | 5 | 0,15 |

Tổng: 4,56 / 5

## PHÁN QUYẾT: APPROVE
Không P0/P1, điểm 4,56 ≥ 4,0. Cổng đầy đủ trên đúng 981e0e95 thoát 0, 8.426 test, độ phủ giữ ngưỡng; các bất biến của PERF-01 (không bớt test/assert/bước/ngưỡng,
không đổi mã sản phẩm ngoài `training_segformer/model.py`) đứng. Điều kiện gộp (R-38): người điều phối ghi `DEBT.md` cho F1 (P2) và F2–F5 (P3) trước khi squash;
thông điệp squash theo R-36b (F7). F1 nên sửa sớm: cho tới khi sửa, lượt cổng đầy đủ nào mypy đỏ sẽ không có thông báo lỗi trong log (trạng thái vẫn đúng).
