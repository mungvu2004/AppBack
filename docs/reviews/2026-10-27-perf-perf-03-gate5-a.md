# Review merge perf/perf-03-gate5-a → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 6a1c3e5520d5 (base `main` b8feb82cbe58, trùng `origin/main`)
- Cổng: phạm vi **đầy đủ**: lượt review 1 của nhánh (R-33b điều kiện 1), diff chạm `tools/**`, `deploy/**`, `packages/testing/**`. Reviewer tự chạy `VERIFY_NAME=gate5-a bash tools/verify/run.sh verify` tại 6a1c3e55, **mã thoát 0**, 10/10 bước đạt, 07:31:12Z → 07:42:13Z (11 phút 1 giây). Log: `.cache/src-out/verify/20261027T073114Z-6a1c3e5520d5.log`. Bước 5: 8945 passed trong 531 s. Khởi động đo được 5 s, từ `run.sh bắt đầu` tới `uv sync xong`: bỏ được `compose build` và `uv sync`, venv `venv-lock-04e6a93ee2e403f8`.
- Độ phủ: tổng dòng 99,48% · nhánh 98,00%. Đơn vị bị chạm: `tools` 98,78/96,57 · `packages/testing` 99,56/98,52 · `apps/ml/runtime` 100/100 · `apps/ml/training_runner` 98,80/94,70 · `apps/ml/training_segformer` 100/100.

## Điều kiện dừng sớm

- Cây sạch (`git status --porcelain` rỗng), nhánh đứng trên đầu `main`.
- Có `changes/PERF-03.md`.
- 12 commit không phải merge đều có dòng đầu Conventional Commits. 11 commit đọc được `Prompt: PERF-03` bằng `%(trailers)`; `b7daeedb` thì không (Nit #8).
- Diff không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`. Người dùng đã giao PERF-03, nên các tệp cổng (`tools/verify/*`, `deploy/compose/verify.yml`) được phép sửa.
- Không có `pragma`, `skip`/`xfail` mới, không hạ ngưỡng. `-n 6 --dist loadfile` giữ nguyên. Các `# type: ignore[...]` và `# noqa: S108` mới đều có mã và lý do.

## Đã soát, không có finding

- **Venv dùng chung theo băm `uv.lock`.** Mọi thành viên workspace trong `uv.lock` đều là `source = { virtual = ... }` (`package = false`). Venv chỉ chứa thư viện ngoài; mã repo đi qua `PYTHONPATH=/tmp/w`. Vì thế venv dùng chung không chở mã của worktree khác. Hai lượt cùng băm: `flock` trên volume chung xếp hàng `uv sync`, lượt sau thấy dấu khớp thì bỏ qua. Lock đổi thì băm mới, sinh venv mới, venv cũ không bị đụng. Dấu `.verify-synced` chỉ ghi sau khi sync đạt (`set -e`): sync hỏng giữa chừng thì lượt sau sync lại. Bỏ `uv sync --locked` khi đầu vào (lock, mọi `pyproject.toml`, phiên bản uv) trùng lượt đạt trước không đổi kết luận "lock khớp pyproject".
- **Bỏ `compose build`.** `verify.Dockerfile` chỉ `COPY --from=node` (stage ghim digest), không chép gì từ context. Nhãn = băm Dockerfile là đủ.
- **`verify --fast`.** Trạng thái lấy từ mã thoát thật. Bước chưa chạy in "chưa chạy" kèm tên của cổng nhanh. Đổi chỉ tài liệu thì bước 5 ghi "không áp dụng". Đổi `conftest.py`, `pyproject.toml`, `uv.lock` hay `packages/testing/fixtures/` thì chạy cả bộ. Bảng không in 5b/7/8, cuối bảng có dòng "Cổng NHANH". Mypy nền dùng cache ấm riêng (`mypy-fast-<tên>`), không ghi vào cache theo băm cây của cổng đầy đủ. Ngoại lệ là mã 5 (finding #2).
- **`worker_rss`.** Mỗi test chỉ tốn một syscall, kết quả test không đổi. Ghi vào `/tmp` của container. Đã có trong bảng lượt này (đỉnh 1,2–2,3 GiB mỗi worker).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-04 / R-19 | **Venv dùng chung không còn tự lành.** `run.sh shell` (cmd_shell) đưa `$UV_PROJECT_ENVIRONMENT/bin` lên PATH, trỏ vào venv **chung của mọi worktree**. Trong shell, `uv pip install x` hay sửa `site-packages` sẽ làm bẩn venv đó. Trước PERF-03 mỗi lượt đều chạy `uv sync --locked`, mà sync mặc định xoá gói thừa, nên venv tự về đúng lock. Giờ dấu `.verify-synced` vẫn khớp nên sync bị bỏ: gói lạ ở lại cho **mọi** worktree tới khi `uv.lock` đổi. Hệ quả là cổng có thể xanh giả: mã nhập một gói không có trong lock vẫn qua bước 5. | `tools/verify/in_container.sh:46-48` | Việc `shell` xoá dấu trước khi vào bash, ví dụ `[[ "${1:-}" == shell ]] && rm -f "$UV_PROJECT_ENVIRONMENT/.verify-synced"`, để lượt sau sync lại đúng một lần (~35 s). Hoặc thêm `uv sync --locked --check` rẻ vào nhánh bỏ qua. Thêm một dòng README. |
| 2 | P3 | K25 / LOG-02 | `verify --fast`: pytest trả mã 5 (đơn vị bị chạm không có test nào) bị in "**đạt**" dù không test nào chạy. Detail chỉ ghi tên thư mục. | `tools/verify/steps.py:569` | Mã 5 → `STATUS_NA`, detail "không thu được test". Sửa tham số `(5, STATUS_OK)` trong test tương ứng. |
| 3 | P3 | PERF / R-19 | Việc dời `import torch` (5 tệp test ML) và `rapidocr` (`ml_ocr`) vào hàm **không giảm** RSS của worker. Mỗi worker xdist collect cả bộ test, mà `apps/ml/training_segformer/tests/test_trainer.py:20` và `test_export.py:12` vẫn `import torch` ở đầu module. `apps/ml/text/tests/test_reader.py` và `apps/ml/objects/tests/*` vẫn nhập onnxruntime/rapidocr ở đầu module (35 tệp nhập cv2/onnxruntime). Bảng RSS của chính lượt này còn ghi `test_trainer.py +888,6`, `test_reader.py +593,8`. Plugin nhóm `loadgroup` từng là lý do cho việc dời import, nhưng đã bị bỏ ở 6a1c3e55. | 5 tệp test ML, `packages/testing/fixtures/ml_ocr.py` | Hoặc dời hết (đo lại RSS sau collect), hoặc bỏ dòng "import nặng … dời vào hàm" khỏi `changes/PERF-03.md` cho khỏi gây hiểu nhầm. Không cần revert. |
| 4 | P3 | OPS-04 | `gc` xử lý sai hai loại thư mục mới. (a) Lấy `"fast-<tên>"` từ `mypy-fast-<tên>` làm tên worktree, không khớp ⇒ **xoá cache ấm của cổng nhanh** ở mỗi lần `gc`. (b) `venv-<worktree>` kiểu cũ không còn ai dùng sau PERF-03, nhưng `gc` vẫn giữ khi worktree còn sống. Volume `/work` hiện có 26 thư mục như vậy (vd `venv-appback` 2,2 GB). | `tools/verify/steps.py:858-861` | Cắt tiền tố `mypy-fast-` trước khi so `valid`. Coi `venv-*` không phải `venv-lock-*` là rác và xoá. Thêm 2 ca vào `test_gc_*`. |
| 5 | P3 | OBS-01 | Log của `verify --fast` mang cùng mẫu tên `<giờ>-<sha>.log`, cùng thư mục và cùng trần 20 log với cổng đầy đủ. Chạy nhanh "mỗi lần sửa" sẽ đẩy log đầy đủ ra khỏi trần, và log nhanh dễ bị lấy nhầm làm bằng chứng cổng: review đọc "log mới nhất". | `tools/verify/run.sh:148` | Lượt `--fast` dùng tên `*.fast.log` (hoặc thư mục con `fast/`), tính trần riêng. |
| 6 | P3 | TEST-02 / R-14 | Nhánh bỏ `compose build` khi nhãn khớp không có test. `test_run_sh` chỉ kiểm có gọi `image inspect`; docker giả trả nhãn rỗng nên luôn build. | `tools/tests/test_run_sh.py:197` | Thêm ca docker giả trả đúng `VERIFY_IMAGE_KEY`: không có dòng `compose … build`. |
| 7 | Nit | MNT-04 | Hai dòng nối bị dồn thành nhiều dấu cách, có lẽ do mất `\`: `2> /dev/null)"     !=` và `-print0   \| sort`. Chạy đúng nhưng khó đọc. Chú thích đầu `run.sh` chưa ghi `--fast`. `--fast --steps …` lặng lẽ bỏ `--steps`. | `tools/verify/run.sh:5,124`, `in_container.sh:43`, `steps.py:605` | Tách dòng lại; báo lỗi khi dùng chung hai cờ. |
| 8 | Nit | R-36b | `b7daeedb` có dòng trống giữa `Prompt:` và `Co-Authored-By:` nên `%(trailers)` rỗng. `95a329eb` là commit merge, không có trailer. | lịch sử nhánh | Không cần viết lại: nhánh một prompt, gộp **squash** (R-36) với khối trailer đúng. |
| 9 | Nit | R-01 | Lớp giả `_Node`, `_Session` và các method của `_Reporter` trong test không có docstring. | `packages/testing/tests/test_worker_rss.py:37-75` | Thêm một câu cho mỗi cái. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,45 / 5** · P0: 0 · P1: 0 · P2: 1 · P3: 5 · Nit: 3

## PHÁN QUYẾT: APPROVE

Cổng đầy đủ do reviewer tự chạy thoát 0 ở 10/10 bước, độ phủ tổng 99,48/98,00, mọi đơn vị bị chạm ≥ 94,7% nhánh. Khởi động cổng đo được 5 s, khớp báo cáo. Venv dùng chung an toàn với hai lượt song song và khi lock đổi, vì mọi thành viên workspace là `virtual` và sync được khoá bằng `flock`. `--fast` lấy trạng thái từ mã thoát thật. Không có P0/P1, điểm 4,45 ≥ 4,0. Vẫn nên sửa P2 #1 trước khi gộp: một dòng trong `in_container.sh`, chặn kẽ hở xanh giả mà PERF-03 mở ra. Nếu không sửa, #1 và các P3 vào đợt nợ kế, chủ là PERF-03 / người điều phối. Gộp bằng **squash**, thân có `Prompt: PERF-03` đúng khối trailer.
