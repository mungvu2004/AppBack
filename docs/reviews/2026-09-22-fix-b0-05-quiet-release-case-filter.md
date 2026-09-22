# Review merge fix/b0-05-quiet-release-case-filter → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, dòng `DEBT.md` và báo cáo tác giả `W9-SMALL.report.md` tôi đều tự kiểm lại) · Commit đầu nhánh: `ac76b813936a`. Gốc `5f39fb2` = `main` hiện tại (tác giả đã gộp `main` vào nhánh). 4 commit: `3cb7abf` B0-01 + FIX-049, `7e56b05` B0-05 + FIX-050, `f6ee1dc` B5-01 + FIX-051, `ac76b81` gộp `main` @ `5f39fb2` (`Prompt: B0-05`). Đóng NO-067, NO-074.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Chạy tại chỗ trong worktree sạch, 03:58:17Z → 04:05:01Z. Mã thoát là `$?` của `run.sh`, ghi ở dòng `run.sh exit=0` cuối log. Shell bọc không bị cắt nên không cần `docker wait`. Trước lượt chạy tôi đếm `docker ps -q --filter name=verify-run | wc -l` bằng một vòng chờ 60 s (03:47Z → 03:58Z, lúc đó có 2–3 container của worktree khác); lượt chạy bắt đầu khi đếm được 1. Log nằm ở scratchpad của phiên review (`…/4161165a-…/scratchpad/verify.log`). pytest: **2016 passed, 0 failed, 10 skipped**, 1 deselected, 328,05 s. Cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng có sẵn của B0-06, đúng ngoại lệ BE-00 §12). Test deselected là test `perf` của B5-01.
- Độ phủ (lấy từ `tools.coverage_gate` của lượt tôi chạy):
  - tổng: dòng **99,35 %** · nhánh **97,41 %**
  - `packages/messaging`: dòng **100,00 %** · nhánh **100,00 %**
  - `apps/ml/runtime`: dòng **99,65 %** · nhánh **98,61 %**
  - `tools`: dòng **98,69 %** · nhánh **95,37 %**
  - tập file bị chạm: dòng **99,51 %** · nhánh **97,50 %**
  - Báo cáo tác giả ghi tổng 99,34 % · 97,36 %, lệch dưới 0,1 điểm. Các gói bị chạm trùng số từng chữ.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (320 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (279 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision, 1 head, 10/10 bước con) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. H1 186 mẫu. H3/H4/H5 `không áp dụng` là **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt, lúc đầu và lúc cuối phiên |
| `changes/B0-01.md`, `changes/B0-05.md`, `changes/B5-01.md` tồn tại | đạt. Nhánh FIX không sửa mảnh changelog, cùng lối đợt 1 |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt. Cả 4 commit dài 57–67 ký tự. Loại `test`/`refactor` đúng việc (FIX-049 chỉ thêm test; FIX-050/051 đổi cấu trúc, không đổi hành vi ngoài tên sự kiện log) |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt)` in ra `B0-01`, `B0-05`, `B5-01`, `B0-05`. `%(trailers:key=Fix)` in ra `FIX-049`, `FIX-050`, `FIX-051` |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/verify/*` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không |
| Phạm vi [4] của spec | đạt. FIX-049 chỉ đổi `tools/tests/test_case_gate.py` (`tools/case_gate.py` không đổi). FIX-050 đổi `packages/messaging/locks.py` và test của gói. FIX-051 đổi `apps/ml/runtime/gpu.py` và test của app. Ngoài ra chỉ có `DEBT.md`, lật `✅` ngay trong commit sửa (NO-067 ở `3cb7abf`, NO-074 ở `f6ee1dc`) |
| Commit gộp `ac76b81` | sạch. Cha là `f6ee1dc` và `5f39fb2`. `git diff main HEAD` = `git diff main...HEAD` = 6 file, 87+/22−. Cách giải xung đột `DEBT.md` giữ NO-074 `✅` của nhánh và NO-075 `⬜` của `main` |

Kích thước: 49 dòng thêm, 20 dòng bớt ở mã sản phẩm và test (không tính `DEBT.md`), xa dưới trần 400 của MNT-05. Không điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify bằng `bash tools/verify/run.sh shell < probe.sh`, trên bản chép `/tmp/w` (`PYTHONPATH=/tmp/w`, `python -m pytest -p no:cacheprovider -o addopts=""`). Bản cũ và bản đột biến đặt tạm ở `.cache/rv-w9/` dưới đuôi `.txt` (git-ignore, không công cụ nào quét), đã xoá sau phiên. Lúc bắt đầu probe có 1 container `verify-run`, dưới trần 2.

- **P1 — FIX-049, lỗ có từ trước.** Test của `main` chạy trên `case_gate.py` đột biến M1 (vế lọc `parts is None or (parts.common and parts.case not in …)` rút còn `parts is None`) cho **58 passed**: đúng lỗ mà review `fix/b0-07-contract-tool-debts` finding #1 chỉ ra.
- **P2 — FIX-049, đỏ trước.** Test của nhánh chạy trên M1 cho **1 failed, 58 passed**: `test_dạng_chung_với_case_riêng_và_tên_lạ_không_được_tính` hỏng với `AssertionError: assert {'C01'} == set()`.
- **P3 — FIX-049, xanh sau.** Test của nhánh chạy trên `case_gate.py` hiện tại cho **59 passed**. Chạy `coverage --branch` riêng bộ này: dòng 337–352 (`_found_cases_by_op`) không thiếu dòng nào, không thiếu nhánh nào. Dòng `continue` 348 trước đây chưa chạy lần nào, nay đã chạy.
- **P4 — FIX-050, đỏ trước.** `locks.py` của `3cb7abf` (hàm còn riêng tư `_release_quietly`) chạy với test của nhánh cho **1 failed, 22 passed**. Test hỏng là `test_release_quietly_turns_a_dead_redis_into_one_warning`.
- **P5 — FIX-050, ba đột biến trên bản nhánh:**
  - L1: `release_quietly` bỏ `try/except`, thành `await self.release(token)` trần → **2 failed**. Hỏng cả test mới lẫn `test_a_failed_release_never_hides_the_body_error`.
  - L2: nhánh lỗi của `hold` gọi `release` thay cho `release_quietly` → **1 failed**, đúng test `test_a_failed_release_never_hides_the_body_error`. Nghĩa là `hold` vẫn được canh để không che lỗi của thân.
  - L3: `release_quietly` nuốt lỗi mà không ghi log → **2 failed** (`assert [] == [('packages.messaging.locks', 'lock_release_failed')]`).
  - Bản nhánh: **23 passed**.
- **P6 — FIX-051, đỏ trước.** `gpu.py` của `7e56b05` chạy với test của nhánh cho **2 failed, 10 passed**. Lý do: nguồn cảnh báo là `('apps.ml.runtime.gpu', 'gpu_lock_release_failed')` thay cho `('packages.messaging.locks', …)`, và AST thấy `{'release'}`.
- **P7 — FIX-051, hai đột biến:**
  - G1: `runner.run(lock.release(token))`, không bắt lỗi nào → **2 failed**. Test đời sống hỏng ở khẳng định cảnh báo (`test_device_gpu.py:154`, `assert [] == […]`), **không** hỏng ở `pytest.raises(ZeroDivisionError)`. pytest báo `PytestUnhandledThreadExceptionWarning: Exception in thread gpu-slot` (xem #1).
  - G2: bọc `release_quietly` bằng `try/except` tự ghi `gpu_lock_release_failed` → **1 failed**, đúng test AST.
  - Bản nhánh: **12 passed**.
- **P8 — thời gian trả khoá khi Redis đã chết, so với `JOIN_TIMEOUT_S` = 5 s.** Test mới chỉ thấy cảnh báo nếu luồng giữ khoá trả xong trước khi `join` hết giờ. Đo 4 lượt `gpu_slot` (tắt Redis, thân ném): `join` mất **0,002–0,003 s**, mỗi lượt đúng một cảnh báo với `extra` `lock='gpu:0'`, `error='DEPENDENCY_UNAVAILABLE'`. Đo 3 lượt `release_quietly` gọi thẳng: **0,001 s**. redis-py 6.4.0 có `Retry(3, ExponentialWithJitterBackoff)`, nhưng kết nối bị từ chối là hỏng ngay. Biên an toàn gấp hơn 1 000 lần: test không phụ thuộc thời gian thật.
- **P9 — AST 5 file `.py` của diff.** Không hàm nào mới dài quá 50 dòng. Hàm mới thiếu docstring: `failing_body` (`test_device_gpu.py:138`) và `releases` (`:160`), xem #2. Hàm test có từ trước mà không docstring: khoảng 70, trong ba file test này.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | R-02 · MNT-04 | Docstring mới nói `release_quietly` giữ cho lỗi của thân khối GPU không bị che: "Redis hỏng lúc trả chỉ ghi `WARNING`, **không che lỗi của thân khối**". Docstring `release_quietly` cũng đưa `gpu.py` ra làm ví dụ cho "ném ở đây sẽ che lỗi thật". Ở `gpu.py` điều đó không thể xảy ra: lệnh trả khoá chạy trong luồng `gpu-slot`, còn `gpu_slot` chỉ `join` (`gpu.py:158-159`), nên ngoại lệ của luồng không bao giờ thay được lỗi của thân. **Probe P7/G1:** bỏ hẳn phần bắt lỗi thì `pytest.raises(ZeroDivisionError)` vẫn qua. Thứ đổi thật chỉ là luồng chết với traceback thô qua `threading.excepthook` (`Exception in thread gpu-slot`, ra stderr, không JSON, không `requestId`) thay cho một `WARNING` có cấu trúc. Hành vi mã đúng, test vẫn bắt được hồi quy (qua khẳng định cảnh báo và AST); chỉ lý do ghi sai | `apps/ml/runtime/gpu.py:113-114`; `packages/messaging/locks.py:106-107`; `apps/ml/runtime/tests/test_device_gpu.py:132` | Viết lại cho `gpu.py`: "Redis hỏng lúc trả thì luồng `gpu-slot` ghi một `WARNING` có cấu trúc thay vì chết với traceback thô; lỗi của thân không đi qua luồng này". Ở `locks.py` tách hai ý: `hold` dùng `release_quietly` để khỏi che lỗi thân; người giữ khoá ngoài `hold` (vd luồng dọn dẹp) dùng nó để lỗi trả khoá không làm chết đường dọn dẹp |
| 2 | Nit | R-01 | Hai hàm lồng mới không có docstring: `failing_body` và `releases` (probe P9). Cùng lối với khoảng 70 hàm test có sẵn trong các file này và với `failing_body` của `test_locks.py:239` trên `main` | `apps/ml/runtime/tests/test_device_gpu.py:138`, `:160` | Một câu cho `releases` ("tên mọi lời gọi thuộc tính `release*` trong cây"). `failing_body` tự giải thích được. Không chặn merge |
| 3 | Nit | — (sổ) | Cột "Commit" của FIX-049..051 ghi tên nhánh thay vì sha như FIX-001..038 | `docs/fixes.md:58-60` | Người điều phối điền `3cb7abf`, `7e56b05`, `f6ee1dc` khi gộp (`--no-ff` giữ nguyên các sha này) |

**P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-049 (NO-067) sửa đúng gốc.** Gốc của nợ là không test nào đưa vào tên ngoài mẫu case hay tên dạng chung với case không phải case chung. Test mới đưa vào đúng hai tên spec [5] nêu, với `passed` và vết `op="x_create"`, 200. Vì vậy phép so vết `_case_matches_trace` **có** khớp, và chỉ bộ lọc mới giữ được `found` rỗng: test đo đúng bộ lọc chứ không đo đường thiếu vết. Test hỏng trên M1, xanh trên mã hiện tại, lỗ có thật trên `main` (P1–P3). Với route không `+ngoài`, `found` của `op_results` là hợp của case riêng và case chung (`case_gate.py:458`), nên `found == set()` phủ cả hai vế "không vào `found`" và "không vào case chung" của spec.
- **FIX-050 (NO-074 phía B0-05).** `_release_quietly` đổi thành `release_quietly(token) -> None` công khai. Thân hàm giữ nguyên từng dòng; `hold` gọi tên mới ở `locks.py:148` và đó là lời gọi duy nhất của `hold`. Docstring (7 dòng, R-01) nói khi nào dùng hàm này thay `release` và khi nào bắt buộc dùng `release` ("cần biết khoá còn là của mình khi trả"). Không trả `bool | None` như review trước gợi ý: người gọi duy nhất không dùng giá trị trả, nên đúng R-10. "Chỉ nuốt lỗi phụ thuộc" đúng: `release` chỉ sinh `AppError` qua `redis_errors()`, và `translate_redis_error` chỉ trả `DEPENDENCY_UNAVAILABLE` (`redis.py:176-196`); lỗi lệnh vẫn nổi lên. Đường thân xong bình thường giữ `release` (hỏng thì ném 503, `False` thì `LockLost`). **`hold` vẫn không che lỗi thân:** đột biến L2 bị `test_a_failed_release_never_hides_the_body_error` bắt (P5).
- **FIX-051 (NO-074 phía B5-01) sửa đúng gốc.** `_Keeper._release` bị xoá; `_renew_until_stopped` gọi `runner.run(lock.release_quietly(token))`. Chỉ còn một nguồn cho logic "trả khoá lặng lẽ" (R-07). Phạm vi nuốt lỗi tương đương bản cũ: bản cũ lọc `_dependency_error`, nhưng như trên, `release` không sinh `AppError` nào khác. `_dependency_error` và import `AppError` vẫn cần cho vòng gia hạn (`gpu.py:121-122`), không có mã chết. Test AST chặn cả hai kiểu quay lại, gọi `release` trần (G1) và tự bọc `try` (G2) (P7). Test đời sống mạnh hơn bản cũ: thêm lỗi của thân và khẳng định đúng một cảnh báo từ đúng một logger. Khẳng định cũ (`lost` không bật) giữ nguyên, không nới assert nào.
- **Đổi tên sự kiện log `gpu_lock_release_failed` → `lock_release_failed`, như phán quyết của người điều phối yêu cầu kiểm:**
  - *Không ai phụ thuộc tên cũ.* `git grep` trên cả repo ở `main`: tên cũ chỉ có ở `apps/ml/runtime/gpu.py:136`; trên nhánh chỉ còn trong ghi chú đóng NO-074. Không test nào ghim nó. `grep` toàn bộ `F:/AppBack/backend/prompts` (mọi prompt B*/F* và `_charter`) không có `gpu_lock_release_failed` hay `lock_release_failed`. `deploy/` chỉ có `compose/verify.yml`, `docker/verify.Dockerfile` và `.gitkeep` (không dashboard, không luật cảnh báo). Cảnh báo sắp có của B0-10 chỉ là "health và đĩa" (`B0-10.md:22`), không lọc theo sự kiện log.
  - *Hiến chương.* BE-00 §11 chỉ đòi log JSON kèm `requestId` và che khoá nhạy cảm. Tên sự kiện cố định mà hiến chương liệt kê chỉ có mẫu log huấn luyện `training_*` (BE-00 §9), không có sự kiện nào của khoá GPU.
  - *Không mất thông tin.* Bản cũ gửi `token`, mà `token` nằm trong `_MASKED_KEYS` (`packages/core/logging.py:27-32`, `:71`), nên JSON log luôn in `***`. Bản mới gửi `lock='gpu:0'` và `error='DEPENDENCY_UNAVAILABLE'` (P8). Thứ đổi cho người đọc log: `msg`, `logger` (`apps.ml.runtime.gpu` → `packages.messaging.locks`) và trường `token` (vốn vô nghĩa) thay bằng `error`.
  - *Được ghi rõ ở ba nơi,* đúng spec [5] "hoặc ghi rõ đổi": thân commit `f6ee1dc`, ghi chú đóng NO-074, và mục "Lệch" của báo cáo tác giả (kèm cách lọc thay thế: `lock_release_failed` + `lock=gpu:0`). Thêm tham số tên sự kiện cho đúng một người gọi là trái R-10, nên chọn đổi tên là cách ít đổi hợp đồng nhất.
- **Hợp nhất với `main`.** `git grep` sau khi gộp: `SafeLock` chỉ được dùng ở `apps/ml/runtime/gpu.py` và trong gói `messaging` (tái xuất ở `packages/messaging/__init__.py`). Không module nào của B0-06, B0-07, B1-01, B3-01 dùng `SafeLock`, `release` hay `_release_quietly`. Không mã nào còn gọi tên riêng cũ; chỉ còn nhắc trong lịch sử `DEBT.md`, `docs/fixes.md`, `docs/reviews/`. Ranh giới import không đổi (`gpu.py` vốn đã nhập `packages.messaging.locks`); bước 4 đạt.
- **Sổ nợ khớp sự thật.** Ghi chú đóng của NO-067 và NO-074 nêu lệnh, số đỏ/xanh và thông điệp hỏng; tôi tái hiện được đúng các số đó (`1 failed, 58 passed` → `59 passed`; `1 failed, 22 passed`; `2 failed, 10 passed`). Ghi chú cũng nói rõ việc đổi tên sự kiện và lý do.
- **Quan sát ngoài diff, không phải finding:** `gpu_lock_lost` (`gpu.py:129`, có từ B5-01) cũng gửi `token`, nên luôn in `***`. Nếu B5-01 muốn log mang giá trị rào thì đổi tên trường (vd `fence`); không thuộc phạm vi FIX-051.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Đổi tên sự kiện log GPU; không test/tài liệu nào ghim tên cũ | **Đứng được.** Đã kiểm ở mục trên: repo, prompt, `deploy/`, BE-00 §9/§11 sạch; trường `token` cũ vốn bị che |
| 2 | Phạm vi nuốt lỗi: bản cũ lọc `DEPENDENCY_UNAVAILABLE`, bản mới nuốt mọi `AppError`, và hai bản tương đương | **Đứng được.** `redis.py:176-196` chỉ sinh đúng một mã; đột biến L1/L3 bị bắt |
| 3 | `test_gpu_slot_release_survives_a_dead_redis` được viết lại, không nới; lọc cảnh báo theo logger `apps.*`/`packages.*` | **Đứng được.** Khẳng định cũ giữ nguyên, có thêm hai khẳng định mới. Bộ lọc logger chỉ bỏ cảnh báo của thư viện, còn cảnh báo lạ nào của mã dự án thì vẫn làm test hỏng |
| 4 | Gộp `main` @ `5f39fb2`, xung đột chỉ ở cuối bảng `DEBT.md` | **Đứng được.** `diff main:DEBT.md DEBT.md` chỉ khác hai dòng NO-067, NO-074 |
| 5 | Chờ trần 2 container trước lượt chạy | Ghi nhận; lượt chạy của tôi cũng chờ đúng trần này |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt. Tác giả báo không có nợ mới; NO-067 và NO-074 `✅` kèm ngày đóng và mã FIX, đúng lối ghi "mở — … · FIX-…" của các dòng đã đóng trước đó |
| Nợ P0/P1 còn `⬜`/`🔧` | không có (bảng `DEBT.md` sau gộp không có dòng P0/P1 nào mở) |
| Nợ do review này chỉ ra | không cần dòng mới: cả ba finding là Nit, tác giả hay người điều phối tự quyết. Nếu muốn theo dõi #1: `\| ⬜ \| NO-<nnn> \| 2026-09-22 \| \| Docstring apps/ml/runtime/gpu.py:113-114 và packages/messaging/locks.py:106-107 nói release_quietly giữ không che lỗi thân khối GPU, trong khi lệnh trả chạy ở luồng gpu-slot nên không thể che; lý do thật là tránh luồng chết với traceback thô \| Chép lý do của hold sang người gọi chạy ở luồng khác \| B5-01 · B0-05 \| Nit \| mở — review merge 2026-09-22 fix/b0-05-quiet-release-case-filter finding #1 (probe G1: bỏ bắt lỗi thì pytest.raises(ZeroDivisionError) vẫn qua, chỉ còn PytestUnhandledThreadExceptionWarning) \|` |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (log mới chỉ thêm mã lỗi, không token, không bí mật) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 (`hold` và vòng gia hạn của luồng GPU không đổi đường nào) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (phạm vi nuốt lỗi tương đương, có chứng minh) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 (TTL dọn hộ như cũ; trả khoá khi Redis chết mất 1–3 ms, P8) | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (không migration, không hợp đồng HTTP; hợp đồng log đổi có ghi rõ) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #2; 3 FIX đỏ trước/xanh sau, 5/5 đột biến bị bắt) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (đổi tên sự kiện không ai phụ thuộc, có ghi rõ) | 0,25 |
| MNT – Bảo trì | 3 % | 5 (Nit #1, #3; một nguồn thay cho hai) | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,15 = **5,00 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt tôi tự chạy (2016 passed, 0 failed, 10 skipped hợp lệ). Độ phủ đạt ở mọi gói bị chạm: `packages/messaging` 100 % / 100 %, `apps/ml/runtime` 99,65 % / 98,61 %, `tools` 98,69 % / 95,37 %. Không có finding P0/P1/P2/P3, điểm 5,00.

Cả ba FIX sửa đúng gốc và đúng phạm vi [4]; đỏ trước/xanh sau tôi tự tái hiện trong container:
- FIX-049 chốt bộ lọc `_found_cases_by_op`: đột biến M1 của review `b0-07` trước lọt với 58 passed, nay bị bắt.
- FIX-050 và FIX-051 gom logic "trả khoá lặng lẽ" về một nguồn: `SafeLock.release_quietly`. Docstring nói khi nào dùng nó thay `release`, và `hold` vẫn không che lỗi của thân (đột biến L2 bị bắt).
- Việc đổi tên cảnh báo GPU sang `lock_release_failed` kèm `lock=gpu:0` không làm vỡ gì: không test, prompt, tài liệu vận hành hay luật cảnh báo nào dựa vào tên cũ. Trường `token` cũ vốn luôn bị che thành `***`.

Ba Nit không chặn merge.

Điều kiện cho phiên merge:

1. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer `Prompt:` của B0-01, B0-05 **và** B5-01, kèm `Fix: FIX-049/050/051`), **không** squash.
2. Người điều phối điền sha `3cb7abf`, `7e56b05`, `f6ee1dc` vào cột "Commit" của `docs/fixes.md:58-60` (Nit #3).
3. Nếu `main` tiến thêm trước khi gộp (các nhánh đợt 2 khác): nhiều khả năng xung đột chỉ ở những dòng kề nhau của `DEBT.md` (NO-065..NO-073). Giải bằng cách giữ cả hai phía, rồi chạy lại cổng trên kết quả gộp. Theo `grep` của tôi, không nhánh đợt 2 nào khác đụng `locks.py`, `gpu.py` hay `test_case_gate.py`.
4. Nit #1, #2: tác giả tự quyết (sửa docstring ở một FIX sau, hoặc ghi dòng `DEBT.md` đề xuất ở trên).
