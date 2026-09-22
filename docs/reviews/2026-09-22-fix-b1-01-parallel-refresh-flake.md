# Review merge fix/b1-01-parallel-refresh-flake → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, dòng `DEBT.md` và báo cáo tác giả `W8-REFRESH.report.md` tôi đều tự kiểm lại) · Commit đầu nhánh: `b15a622d3b00`. Gốc `5f39fb2` (tác giả đã gộp `main` @ `5f39fb2` vào nhánh). 2 commit: `cf98f29` gộp `main` (`Prompt: B1-01`, `Fix: FIX-048`; cha `a091633` và `5f39fb2`, không mang thay đổi riêng) và `b15a622` `test(auth)` B1-01 + FIX-048. Đóng NO-066, ghi NO-078.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**. Chạy tại chỗ trong worktree sạch, 04:37:38Z → 04:43:17Z. Mã thoát là `$?` của `run.sh`, ghi ở dòng `run.sh exit=0` cuối log; shell bọc không bị cắt nên không cần `docker wait` (tôi vẫn bám `docker logs -f` song song làm dự phòng). Trước lượt chạy tôi đếm `docker ps -q --filter name=verify-run | wc -l` mỗi 60 s (04:32Z → 04:37Z đếm được 2, container của worktree khác); lượt chạy bắt đầu khi đếm được 1. Log ở scratchpad của phiên review (`…/4e7aa349-…/scratchpad/verify.log`). pytest: **2014 passed, 0 failed, 10 skipped**, 1 deselected, 285,41 s. Cả 10 skip là `apps/api/core/tests/test_common.py` (`got empty parameter set for (operation)`, tự kiểm bằng `-rs`; ngoại lệ BE-00 §12 có sẵn của B0-06). Test deselected là test `perf` của B5-01. `apps/api/auth/tests/test_refresh.py` 35/35 xanh trong lượt cổng.
- Độ phủ (lấy từ `tools.coverage_gate` của lượt tôi chạy):
  - tổng: dòng **99,31 %** · nhánh **97,26 %**
  - `apps/api/auth`: dòng **98,49 %** · nhánh **91,91 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %** (file duy nhất đổi là test; `coverage` bỏ `*/tests/*`)
  - Báo cáo tác giả ghi tổng 99,32 % · 97,31 % và `apps/api/auth` 98,61 % · 92,65 %. Mã sản phẩm của `apps/api/auth` không đổi, nên chênh dưới 1 điểm giữa hai lượt là sai số đo sau `await` qua greenlet (NO-035), không phải thiếu test.

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
| `changes/B1-01.md` tồn tại | đạt (10 dòng). Nhánh FIX không sửa mảnh changelog, cùng lối đợt 1 |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt. `b15a622` 63 ký tự, loại `test` đúng việc (chỉ đổi test); `cf98f29` 61 ký tự `chore(repo)` |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt)` in `B1-01` cho cả hai commit; `%(trailers:key=Fix)` in `FIX-048`. Khối trailer liền nhau, có dòng trống trước |
| Đụng `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/verify/*` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` / retry mới / hạ ngưỡng | không. `noqa` duy nhất trong diff là dòng ngữ cảnh có sẵn (`S105` có lý do) |
| Phạm vi [4] của spec | đạt. Chỉ `apps/api/auth/tests/test_refresh.py` (+87/−6) và `DEBT.md`; `router.py` không đổi (spec cho phép đổi "chỉ khi gốc nằm ở đó", mà gốc nằm ở hạ tầng); không chạm `packages/**`. NO-066 lật `✅` ngay trong commit sửa `b15a622` |
| Commit gộp `cf98f29` | sạch. Cha `a091633` là tổ tiên của `5f39fb2`, và `git diff 5f39fb2 cf98f29` rỗng: commit gộp không mang thay đổi riêng. `git diff main...HEAD` chỉ có 2 file trên |

Kích thước: 87 dòng thêm, 6 dòng bớt ở test (không tính `DEBT.md`), xa dưới trần 400 của MNT-05. Không điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify bằng `bash tools/verify/run.sh shell < probe.sh`, trên bản chép `/tmp/w` (`PYTHONPATH=/tmp/w`, `python -m pytest -p no:cacheprovider -o addopts=""`), `TESTCONTAINERS_CONNECTION_MODE=bridge_ip` (đường của cổng hiện nay). Bản `test_refresh.py` của `main` (`git show main:…`, trùng `5f39fb2`) đặt tạm ở `.cache/rv-w8/` dưới đuôi `.txt`, chép vào `/tmp/w` thành `test_refresh_main_rv.py` để chạy **cùng lượt** với bản nhánh; đã xoá sau phiên. Hai lượt container: lượt probe chính (04:43:40Z → 04:49:05Z, lúc bắt đầu có 1 container `verify-run` khác) và lượt P9 (04:52:12Z, lúc bắt đầu có 0), đều dưới trần 2. Cả hai `rc=0`.

Để dựng lại **đúng điều kiện gốc** mà không mock dịch vụ nào, tôi tiêm một chỗ kẹt vào bản chép `router.py`: lượt thứ 5 qua cửa trước (`_check_failures`) của mỗi bucket `await asyncio.sleep(PROBE_STALL_S)` ngay trước `refresh_session`, tức đúng chỗ mà lượt đỏ gốc kẹt ở bắt tay Postgres (sau khi `peek` đã cho qua, trước `bump`). Không đặt `PROBE_STALL_S` thì mã y hệt nhánh.

- **P1 — xanh sau, cả file.** `test_refresh.py` của nhánh: **35 passed** (19,2 s).
- **P2 — đỏ trước / xanh sau ở đúng cỡ thật (kẹt 69 s).** `PROBE_STALL_S=69`, cùng một lượt pytest:
  - bản `main` (cửa sổ mặc định 60 s): **FAILED** `At index 20 diff: 401 != 429` — đúng chữ ký đỏ của NO-066 (call 69,26 s);
  - bản nhánh (`BURST_WINDOW_S` = 360 s): **PASSED** (call 69,35 s).
  - Đối chứng không kẹt: cả hai bản PASSED.
- **P3 — hết hạn TTL thật chứ không `DEL` (cửa sổ 2 s, kẹt 3 s).** 40 lượt → `Counter({401: 21, 429: 19})`, bộ đếm cuối `(1, 2)`; bộ kiểm mới báo "bộ đếm mở cửa sổ thứ hai giữa loạt …". Tức `DEL` trong test tất định cho đúng trạng thái Redis mà một lần hết hạn thật để lại (giá trị 1, TTL = cả cửa sổ mới).
- **P4 — lặp dưới `coverage run`.** `test_auth_refresh__C11_parallel` × 20 và `test_a_denial_after_the_fail_window_counts_from_one` × 20: **40 passed**, loạt chậm nhất 1,22 s (≪ 360 s).
- **P5 — cửa sổ dài không che ca nào C11 phải bắt (ba đột biến mã sản phẩm, cả hai bản test cùng lượt):**
  - M1 `bump` đọc-rồi-ghi (`GET` rồi `SET`, không nguyên khối): **cả hai FAILED**; `Counter({401: 40})`, bộ đếm cuối `(7, 360)` — mất cập nhật. Xem #1 về thông điệp;
  - M2 lệch một ở `_denied` (`>` thành `>=`): **cả hai FAILED**; bản nhánh báo `Counter({429: 21, 401: 19})`;
  - M3 cửa sau không bao giờ trả 429: **cả hai FAILED**; bản nhánh báo `Counter({401: 40})`.
  - Assert đếm chính xác `[401] * 20 + [429] * 20` giữ nguyên từng ký tự (`test_refresh.py:516`); chỉ thêm hai kiểm **trước** nó. Không có đột biến nào lọt bản nhánh mà bản `main` bắt được.
- **P6 — kiểm (1) "Redis mở" có hiệu lực trong thứ tự cổng.** Đột biến M4: `bump` ném `redis.exceptions.ConnectionError` 1/7 lượt (→ `soft_redis` mở). Chạy theo thứ tự cổng: `test_a_valid_task_runs_on_a_real_worker` (worker Celery thật) → test in logger gốc → hai bản C11_parallel. Logger gốc lúc đó: `level=40`, `[StreamHandler <stderr>, LogCaptureHandler × 2]`, `apps.api.auth.services` **không** bật `WARNING`; vậy mà bản nhánh vẫn **FAILED** đúng tên `redis-cache hỏng giữa loạt → tầng thất bại mở (on_error=open), không phải đếm sai: ['apps.api.auth.services: ConnectionError' × 5]` nhờ `caplog.at_level(WARNING)`. Bản `main` chỉ báo số.
- **P7 — anh em cùng gốc (R-19).** Đếm sự kiện `connect` của pool SQLAlchemy (bắt tay Postgres mới) **trong** cửa sổ: C11 tuần tự (21 lượt) **0** kết nối mới (pool dùng lại kết nối mở lúc đăng nhập, trước cửa sổ); C11 song song (40 lượt) **14** kết nối mới (pool 10 + overflow 5). Vậy chỉ loạt song song mới có bắt tay nằm giữa cửa sổ; `test_auth_refresh__C11` và `test_auth_refresh__C11_total` (tuần tự) không phơi ra gốc này. `grep asyncio.gather` trong test của `apps/**`: các loạt song song khác (`test_login.py:345`, `test_refresh.py:136`, `test_routing.py:260`) không so đếm chính xác theo cửa sổ cố định, nên cửa sổ mở lại không làm chúng đỏ.
- **P8 — NO-078.** `celery.contrib.testing.worker.start_worker(…, loglevel='error', …)` và `_start_worker_thread` gọi `setup_app_for_worker(app, loglevel, logfile)`. Sau một test có worker thật: logger gốc `level=40` với `StreamHandler <stderr>` (handler của pytest `_LiveLoggingNullHandler`, `_FileHandler` bị gỡ). Đối chứng không chạy worker trước: `level=30`, `apps.api.auth.services` bật `WARNING`. Đúng như dòng NO-078 mô tả.
- **P9 — hướng chữa thứ hai của NO-078.** Dòng NO-078 đưa hai hướng: "fixture lưu mức + handler của logger gốc và trả lại sau `start_worker`" **hoặc** "`worker_hijack_root_logger=False` cho app thử". Probe thứ hai (Celery **5.6.3** trong container, `app.log.setup(loglevel='error')` trên logger gốc mức 30):
  - mặc định → `(40, [StreamHandler <stderr>])`;
  - `worker_hijack_root_logger=False` → **vẫn** `(40, [StreamHandler <stderr>])`;
  - một receiver nối vào `celery.signals.setup_logging` → `(30, [])`, không đổi.
  - Nguồn: `Logging.setup_logging_subsystem` chỉ bỏ qua việc cấu hình khi `setup_logging` có receiver. Cờ hijack chỉ quyết định có xoá handler cũ hay không; `_configure_logger` vẫn luôn `logger.setLevel(loglevel)`. Vậy hướng thứ hai không chữa được đúng triệu chứng của NO-078 (mức ERROR). Xem #2.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-02 · R-02 | Bộ kiểm mới gọi **sai tên** đúng loại hồi quy mà C11_parallel sinh ra để bắt. Kiểm (2) suy "bộ đếm cuối < trần ⇒ cửa sổ thứ hai, **không phải đếm sai**" từ tiền đề "`INCR` nguyên khối" (docstring dòng 506–509), mà tính nguyên khối chính là thứ test đang kiểm. **Probe P5/M1** (`bump` đọc-rồi-ghi, loạt 1 s nên không cửa sổ nào kịp hết): bản nhánh hỏng với `AssertionError: bộ đếm mở cửa sổ thứ hai giữa loạt (cuối loạt (giá trị, TTL) = (7, 360)), không phải đếm sai: Counter({401: 40})`. Test vẫn đỏ (không có xanh giả), nhưng thông điệp khẳng định ngược sự thật và đẩy người đọc về phía hạ tầng/NO-066, trong khi bản `main` chỉ in số trung tính. Spec [5] đòi "báo đúng tên nguyên nhân"; chiều ngược lại (đếm sai thật không được đổ cho hạ tầng) cũng thuộc yêu cầu đó | `apps/api/auth/tests/test_refresh.py:506-515` | Với `INCR` nguyên khối, mỗi lượt muộn vừa thêm một 401 vừa thêm một đơn vị vào cửa sổ mới, nên cửa sổ thứ hai kéo theo `statuses.count(401) - limit == counter[0]` (P3: 21−20 = 1; test `DEL`: 1; số đo NO-066: 22 → 2, 26 → 6). M1 cho 40−20 = 20 ≠ 7. Chỉ báo "cửa sổ thứ hai" khi `counter[0] < limit and statuses.count(401) - limit == counter[0]`; ngược lại rơi xuống assert đếm (thông điệp `Counter`, không kèm "không phải đếm sai"). Thêm một ca thuần: `_assert_exact_fail_limit([401] * 40, [], (7, 360), 20)` không được khớp "cửa sổ thứ hai". Cách tối thiểu: bỏ vế "không phải đếm sai" khỏi thông điệp kiểm (2) và sửa câu docstring 506 thành "nếu `INCR` còn nguyên khối" |
| 2 | Nit | — (sổ) | Hướng chữa thứ hai trong dòng NO-078 ("hoặc `worker_hijack_root_logger=False` cho app thử") không chữa được nợ. **Probe P9** (Celery 5.6.3): tắt cờ này thì logger gốc vẫn bị đặt mức 40 (ERROR) và thêm `StreamHandler`. Chỉ khi nối một receiver vào `celery.signals.setup_logging` thì logger gốc mới giữ nguyên. Hiện tượng, gốc và mức của NO-078 đều đúng, chỉ câu hướng chữa sai. Ai làm theo câu đó sẽ bị chính test chốt "mức gốc không đổi sau worker" (mà dòng này đòi) bắt lại, nên chỉ là Nit | `DEBT.md`, dòng NO-078, cột trạng thái/hướng chữa | Người điều phối sửa câu khi gộp: "… (hoặc nối một receiver rỗng vào `celery.signals.setup_logging` cho worker thử; `worker_hijack_root_logger=False` **không** đủ vì Celery vẫn `setLevel(ERROR)` logger gốc) …" |
| 3 | Nit | — (sổ) | Cột "Commit" của FIX-048 ghi tên nhánh thay vì sha như FIX-001..038 | `docs/fixes.md:57` | Người điều phối điền `b15a622` khi gộp (`--no-ff` giữ nguyên sha này) |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 2**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-048 sửa đúng gốc (R-19), và gốc là hạ tầng chứ không phải mã.** Mọi lượt 401 của tầng thất bại đi qua `_denied` → `bump` (`MULTI`: `INCR`, `EXPIRE … NX`, `TTL`; `login_guard.py:76-88`), nên thừa 401 chỉ có thể do cửa sổ mở lại hoặc `soft_redis` mở. P2 dựng lại đúng cơ chế ở cỡ thật: một lượt đã qua cửa trước kẹt 69 s, `bump` của nó rơi vào cửa sổ thứ hai, bản `main` đỏ với đúng chữ ký gốc, bản nhánh xanh. `router.py` đúng thiết kế cửa sổ cố định (BE-00 §11), không có gì để sửa ở đó; spec [4] cho phép để nguyên. FIX-009 (đường bridge IP, đã ở `main`) chữa đường hạ tầng; FIX-048 làm test không phụ thuộc vào đường đó.
- **`BURST_WINDOW_S` = 2 × `GATE_CONNECT_TIMEOUT_S` không phải nới assert.** (a) Assert đếm chính xác giữ nguyên, ba đột biến sản phẩm đều bị bắt như bản cũ (P5). (b) Cửa sổ chỉ đổi *khoảng thời gian* mà mọi `bump` của **một** loạt phải rơi vào; loạt đo được ≤ 1,22 s (P4), còn một lượt kẹt quá `GATE_CONNECT_TIMEOUT_S` = 180 s thì hỏng kết nối (app thử đặt `DB_CONNECT_TIMEOUT_S` = 180, `packages/testing/fixtures/api.py:151`), thành 5xx và làm test đỏ theo đường khác. 360 s vì thế chỉ nuốt đúng khoảng kẹt mà cổng cố ý chịu (NO-002, NO-007). (c) Hành vi với cấu hình mặc định (cửa sổ 60 s; lượt thứ 21 nhận 429 + `Retry-After`) vẫn do `test_auth_refresh__C11` (tuần tự) kiểm. Theo FIX.md luật 2, đổi test chỉ hợp lệ khi test sai so với hiến chương: test cũ ngầm giả định loạt xong trong 60 s, trái với mức kẹt bắt tay mà `GATE_CONNECT_TIMEOUT_S` ghi rõ; docstring `BURST_WINDOW_S` và báo cáo đều nói ra điều đó.
- **Không phụ thuộc thứ tự chạy, không rò cấu hình.** `monkeypatch.setenv("REFRESH_FAIL_WINDOW_S", …)` + `reset_auth_settings_cache()`; teardown của `auth_env` (`packages/testing/fixtures/auth.py:74-80`) xoá cache trước khi `monkeypatch` trả biến môi trường, nên test sau đọc lại 60 s. Handler đọc `get_auth_settings()` mỗi request (`router.py:243`), nên đặt biến sau khi app đã khởi động vẫn có hiệu lực. Khoá bucket chứa `sid` riêng của mỗi test.
- **Test tất định mới đúng TEST-02.** `DEL` thật trên `redis-cache` thật thay cho chờ TTL giờ thật (người điều phối duyệt); P3 cho thấy hết hạn TTL thật để lại đúng trạng thái đó (giá trị 1, TTL cả cửa sổ). Test khẳng định cả hành vi sản phẩm (lượt bị từ chối sau khi cửa sổ hết đếm lại từ 1 → 401) lẫn thông điệp của bộ kiểm. `_bucket_of` gọi lại `router._fail_bucket` (cùng app B1-01) thay vì chép định dạng khoá (R-07).
- **Kiểm (1) "Redis mở" hoạt động kể cả khi logger gốc đang ở ERROR** do worker Celery để lại (P6): chính là lý do lượt đỏ gốc không cho thấy `rate_limit_open`, nay test tự bật mức `WARNING` trong loạt.
- **R-01/R-08:** mọi hàm mới có docstring; hàm dài nhất là `test_a_denial_after_the_fail_window_counts_from_one`, 21 dòng kể cả docstring. `BURST_WINDOW_S` có docstring thuộc tính giải thích *tại sao*.
- **Hợp nhất với `main` (@ `311b8c3`).** `git merge-tree --write-tree main HEAD`: xung đột **duy nhất** ở `DEBT.md` (dòng NO-078 của nhánh và NO-076, NO-077, NO-079 của `main` cùng chèn sau NO-075). Từ `5f39fb2` tới `311b8c3`, `main` không đổi file nào dưới `apps/api/**`, `packages/db/**`, `packages/testing/**`, `packages/messaging/redis.py`, `conftest.py`, `pyproject.toml`. Nhánh không đổi API nào (chỉ test), nên không có người gọi nào để `grep`; các API mà test mới **dùng** (`login_guard.peek`, `router._fail_bucket`, `packages.db.engine.GATE_CONNECT_TIMEOUT_S`, fixture `cache_client`) giữ nguyên trên `main`.
- **Sổ nợ khớp sự thật.** Ghi chú đóng NO-066 nêu gốc, cách đo, số đỏ/xanh và thông điệp; phần tôi tái hiện được đều khớp: chữ ký đỏ, bộ đếm cuối dưới trần ở cửa sổ thứ hai, kẹt ~69 s mà vẫn xanh sau sửa. Các số 3/300 đường cũ và 0/300 đường bridge IP tôi không đo lại (đòi hàng trăm lượt trên đường `host.docker.internal` đã bỏ); cơ chế thì P2 dựng lại tất định. Tuyên bố cũ của NO-066 ("`configure_logging` thay handler gốc") được sửa đúng thành Celery ở NO-078 — `configure_logging` không được gọi ở mã sản phẩm nào hiện nay.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Gộp `main` (có FIX-009) trước khi tái hiện; đo đường cũ bằng `env -u TESTCONTAINERS_CONNECTION_MODE` | **Đứng được.** Commit gộp sạch (chỉ mang file của `main`), có trailer của nhánh |
| 2 | Hết cửa sổ bằng `DEL` thay vì chờ TTL (điều chỉnh của người điều phối, TEST-02) | **Đứng được.** P3: hết hạn thật cho cùng trạng thái |
| 3 | Không viết test tất định riêng cho nhánh "Redis hỏng → mở" | **Đứng được.** Dựng Redis hỏng giữa loạt cần container tạm dừng + thử lại của redis-py (1–17 s/lượt); P6 chứng minh kiểm (1) có hiệu lực trong thứ tự cổng |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt. NO-066 `✅` kèm ngày đóng và mã FIX; NO-078 `⬜` mới, chủ B0-05 |
| NO-078 đúng sự thật | đạt về hiện tượng và gốc (P8): `start_worker` mặc định `loglevel='error'`, logger gốc ở mức 40 với `StreamHandler` của Celery sau worker, `WARNING` của test sau bị bỏ. Vị trí `packages/testing/fixtures/messaging.py:149` (`with start_worker(`) đúng. Riêng câu hướng chữa thứ hai thì sai (#2, probe P9) |
| NO-078 đúng mức | đạt. P2 theo RULE.md §1 ("thiếu log"): không ảnh hưởng sản phẩm, nhưng làm mất log `WARNING` trong báo cáo đỏ của mọi test `apps/**`, `tools/**` chạy sau `packages/messaging` trong cổng, và đã thực sự che chẩn đoán NO-066. Không thuộc diện nâng bậc (không phải hot path/auth trong sản phẩm) |
| Nợ P0/P1 còn `⬜`/`🔧` | không có |
| Nợ do review này chỉ ra | #1 là P3: tác giả tự quyết. Nếu không sửa ngay, dòng đề xuất dưới đây |

Dòng đề xuất (id do người điều phối cấp; phiên này **không** tự ghi vào `DEBT.md`):

`| ⬜ | NO-<nnn> | 2026-09-22 | | Bộ kiểm _assert_exact_fail_limit của C11_parallel gọi một lỗi đếm thật là "cửa sổ thứ hai …, không phải đếm sai": bump đọc-rồi-ghi (không nguyên khối) → AssertionError "bộ đếm mở cửa sổ thứ hai giữa loạt ((7, 360)), không phải đếm sai: Counter({401: 40})" | Kiểm (2) suy "bộ đếm cuối < trần ⇒ cửa sổ mở lại" từ tiền đề INCR nguyên khối — chính tính chất test đang kiểm | B1-01 (apps/api/auth/tests/test_refresh.py:506-515) | P3 | mở — review merge 2026-09-22 fix/b1-01-parallel-refresh-flake finding #1. Chữa: chỉ báo cửa sổ thứ hai khi counter[0] < trần và statuses.count(401) − trần == counter[0]; thêm ca thuần ([401]×40, [], (7, 360), 20) không khớp "cửa sổ thứ hai"; hoặc bỏ vế "không phải đếm sai" |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (không đổi mã sản phẩm; hạn mức refresh giữ nguyên) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 (C11_parallel vẫn bắt đếm không nguyên khối, P5/M1) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (gốc xác định và dựng lại tất định, P2/P3) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (loạt ≤ 1,22 s) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 (nhánh `on_error=open` được gọi tên, P6) | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (không migration, không hợp đồng HTTP) | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #1) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 (NO-078 ghi đúng; log test được bắt lại trong loạt) | 0,25 |
| MNT – Bảo trì | 3 % | 5 (Nit #2, #3) | 0,15 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,28 + 0,25 + 0,15 = **4,93 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt tôi tự chạy (2014 passed, 0 failed, 10 skipped hợp lệ); `apps/api/auth` 98,49 % dòng · 91,91 % nhánh, tổng 99,31 % · 97,26 %. Không P0/P1/P2; một P3, hai Nit; điểm 4,93.

FIX-048 sửa đúng gốc và đúng phạm vi [4]. Gốc NO-066 là hạ tầng: một lượt kẹt ở bắt tay Postgres làm `bump` rơi sang cửa sổ cố định thứ hai. `router.py` đúng và không bị đụng. Đỏ trước/xanh sau tôi tự dựng lại ở đúng cỡ thật trong container: kẹt 69 s làm bản `main` đỏ với `At index 20 diff: 401 != 429`, còn bản nhánh xanh. Cửa sổ 360 s không phải nới assert: assert đếm chính xác giữ nguyên, và ba đột biến sản phẩm (đếm không nguyên khối, lệch một, bỏ 429) vẫn làm bản nhánh đỏ như bản cũ. Kiểm "Redis mở" gọi đúng tên ngay cả khi logger gốc đang bị Celery để ở ERROR. NO-078 đúng hiện tượng, đúng gốc, đúng mức P2.

Finding #1 không chặn merge: test vẫn đỏ với mọi đột biến. Chỉ thông điệp của kiểm (2) sai khi lỗi nằm ở chính tính nguyên khối.

Điều kiện cho phiên merge:

1. Gộp bằng `git merge --no-ff` (R-36: giữ sha `b15a622` mang `Fix: FIX-048`), **không** squash.
2. Xung đột duy nhất ở `DEBT.md`: giữ cả hai phía, xếp theo id (NO-075, NO-076, NO-077, **NO-078**, NO-079). Sau gộp chạy lại cổng trên kết quả (xuất `openapi.json` ra gốc trước bước 8 như mọi lần gộp).
3. Người điều phối điền sha `b15a622` vào cột "Commit" của `docs/fixes.md:57` (Nit #3).
4. Khi ghi NO-078 lúc gộp, sửa câu hướng chữa thứ hai theo #2 (receiver `setup_logging`, không phải `worker_hijack_root_logger=False`).
5. #1: tác giả/người điều phối tự quyết — sửa trong một FIX sau, hoặc ghi dòng `DEBT.md` đề xuất ở trên.
