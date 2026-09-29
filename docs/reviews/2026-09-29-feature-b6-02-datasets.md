# Review merge `feature/b6-02-datasets` → main

- Ngày: 2026-09-29 · Reviewer: phiên `/merge-review` (worktree riêng `b6-02-review`, không sửa mã, không merge)
- Commit đầu nhánh: `939227911c40` · cây `8d386016c650` · 9 commit không-merge, 5.802 thêm / 35 bớt, 51 file
- Nhánh gộp **ba** thay đổi → ba phán quyết riêng dưới đây (squash ba commit theo thứ tự FIX-111 → FIX-112 → B6-02).
- **Phạm vi kiểm: đầy đủ** — log cổng đầy đủ của **chính** sha này, `backend/dieu-phoi/chay/B6-02/E/gate.log`
  (`…/verify/20260929T053537Z-939227911c40.log`), **mã thoát 0**, 8/8 bước `đạt`. Cổng **không chạy lại** theo
  quyết định của người dùng (chốt ở B6-01: reviewer đọc log cổng đầy đủ của việc gộp). Đối chiếu log ↔ sha:
  tên log mang sha `939227911c40`; nội dung log phản ánh cả hai commit cuối (bước 5b in
  `apps/worker/datasets/tests/test_perf.py ..` — hệ quả của `ef09448`; case_gate in `C01` cho `ml_create_dataset` —
  hệ quả của `9392279`); 6.364 test so với 6.019 của log cổng nhánh FIX-112 một mình.
- Bảng cổng (đọc từ mã thoát thật trong log, không suy diễn):

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | ruff format --check | đạt | |
| 2 | ruff check | đạt | |
| 3 | mypy --strict | đạt | |
| 4 | lint-imports | đạt | |
| 5 | pytest -n (cov) → coverage_gate | đạt | 6.364 passed, 555,40 s |
| 5b | pytest -m perf → case_gate | đạt | 4 perf passed; case_gate 77 thao tác, thiếu 0, 3 cảnh báo BE-BIND cũ |
| 6 | lint_migrations → migrate_check | đạt | 19 revision, 10/10 kiểm |
| 7 | H1 H3 H4 H5 | đạt | 1.772 mẫu response |
| 8 | openapi | đạt | |

- Độ phủ (bước 5): **tổng dòng 99,56 % · nhánh 98,42 %**; mọi gói bị chạm ≥ 90/90 — thấp nhất `packages/db`
  97,18/95,76 và `apps/api/telemetry` 98,92/96,05; `apps/worker/datasets` 100/100,
  `apps/api/admin_ml_datasets` 99,10/100; tập file bị chạm 99,76/98,73.
- Điều kiện dừng sớm: cây sạch ✔ · `changes/B6-02.md`, `changes/FIX-112.md` có ✔ (FIX-111 thuộc `Prompt: B0-01`,
  `changes/B0-01.md` đã có trên main) · 9/9 commit đúng Conventional Commits, `Prompt:` trả ra ở cả 9, `Fix:` đúng ở
  hai commit FIX ✔ · không đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA` ✔ ·
  `uv.lock` chỉ thêm `pytest-cov 7.1.0`, `pytest-xdist 3.8.0`, `execnet 2.1.2` — đúng hệ quả của `pyproject.toml`
  cùng nhánh ✔ · không `pragma: no cover`, không `# type: ignore` trần (một `# type: ignore[attr-defined]` có mã,
  trong test), không `# noqa` trần (ba `S608` + một `S603` đều kèm lý do), không `skip`/`xfail` mới, không hạ ngưỡng ✔.

---

## 1. FIX-111 — `d8038d6` `test(tools): isolate cases.toml in the no-operations main test`

Một dòng: `test_main_đạt_khi_chưa_có_thao_tác` vá thêm `case_gate.load_cases_toml`. Tự kiểm: `main()` gọi
`load_cases_toml(...)` qua tên module ở `tools/case_gate.py:538`, nên `monkeypatch.setattr(case_gate, ...)` chặn đúng
điểm; docstring nêu lý do và trích NO-257. Đây là sửa **gốc** (R-19) của NO-257 phía cổng, không phải nới assert.

### Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 111-1 | P3 | R-34 | `DEBT.md` NO-257 vẫn `⬜ mở` dù nửa "test cổng tự cô lập" đã xong ở commit này (nửa còn lại — B5-04 khai lại `[[task]] fn="text_read"` — vẫn mở) | `DEBT.md:278` | Sau merge đổi trạng thái NO-257 thành "một phần đã sửa (FIX-111, sha …), còn lại: B5-04 khai lại `[[task]]`" |

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25 % | 5 | 1,25 |
| CON | 15 % | 5 | 0,75 |
| LOG | 15 % | 5 | 0,75 |
| PERF | 10 % | 5 | 0,50 |
| RES | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT | 3 % | 4 | 0,12 |

Tổng: **4,97 / 5**

### PHÁN QUYẾT: APPROVE

---

## 2. FIX-112 — `19a33d6` `perf(verify): run the pytest gate step in parallel`

Bước 5 đổi `coverage run -m pytest` → `pytest -n 6 --dist loadfile --cov --cov-report=`; `db_url` đổi từ
"một database mỗi test" sang "một database mỗi tiến trình, dọn bằng `DELETE` + `setval` + nạp lại seed"; 16 file,
bốn Lệch đã được điều phối duyệt. Lợi: 1.205 s → 555 s ở bước 5.

**Bốn khẳng định của tác giả, tự kiểm chứ không tin báo cáo:**

1. *Độ phủ gộp đủ từ mọi tiến trình.* Bằng chứng trong `gate.log`: `apps/worker/datasets` 100 %/100 % và
   `packages/testing` 99,54 %/98,28 % — mã chỉ chạy **trong tiến trình con** xdist vẫn được đo; tổng 99,56/98,42
   không tụt so với các lượt tuần tự trước. `coverage json` in `Combined 1 file` (pytest-cov đã gộp sẵn), nên việc
   bỏ `coverage combine` là đúng chứ không giấu dữ liệu.
2. *`case_gate` đọc junit/vết đúng.* `--junitxml=/tmp/junit.xml` do tiến trình **chủ** của xdist ghi;
   `JUNIT_PATHS` (`tools/case_gate.py:30`) vẫn là `/tmp/junit.xml` + `/tmp/junit-perf.xml`; log in
   `generated xml file: /tmp/junit.xml` rồi `case_gate: đạt`, thiếu 0 trên 77 thao tác. `CASE_TRACE_FILE` là **một**
   file cho 6 tiến trình — có test tiến trình **thật** đo đúng chỗ đó (`tools/tests/test_parallel_fixtures.py:116`,
   6 × 150 dòng, kiểm cả số dòng lẫn `json.loads` từng dòng).
3. *Số test bằng chạy tuần tự.* `--collect-only` tuần tự trước khi sửa: **6.021**; cổng nhánh FIX-112:
   **6.019 passed** ở bước 5 + **2 passed** ở bước 5b = 6.021. Không mất test nào; hai test chuyển sang 5b đúng là
   hai test bị đánh `perf`.
4. *Không né cổng (K24).* `addopts` vẫn `-m "not gpu and not perf"` (không sửa), nên đánh `perf` là **chuyển** sang
   bước 5b chứ không bỏ chạy; `perf_case_named` (`tools/verify/steps.py:185`) vẫn chặn test `perf` mang tên case;
   ngưỡng 90/90 không đổi; sau khi đánh, `apps/api/auth` 99,77/97,79 và `apps/api/telemetry` 98,92/96,05 — không
   nhờ việc đánh dấu mà qua ngưỡng. Bốn Lệch đều là file test/fixture, đúng phạm vi điều phối đã duyệt.

**Cô lập — soát riêng:** `_RESET_SQL` liệt kê bảng **lúc chạy** (`pg_tables`) nên bảng do fixture tạo giữa phiên
cũng bị xoá dòng; `SET LOCAL session_replication_role='replica'` + cả lượt trong **một** giao dịch nên thứ tự bảng
không quan trọng và lượt nạp lại seed vẫn ở trong cùng giao dịch đó; `lock_timeout` 10 s biến "một kết nối test còn
treo" thành lỗi nêu tên bảng thay vì treo cổng; lượt dọn ở finalizer của `db_url` chạy **sau** khi
`db_sessionmaker` đã `dispose`. Hai chỗ rò còn lại là P3 dưới đây.

### Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 112-1 | **P2** | TEST-04 / R-35 | Thay đổi này làm cổng bắt buộc **đỏ giả ~1/4 lượt**: `test_quality_set_corners__queue_capacity[1]` khẳng định đúng 3/5 request bị 503 với hạn chờ đồng hồ tường 0,3 s, không chịu được 6 tiến trình giành CPU (đo của chính tác giả: đỏ 1/4 lượt). Mỗi lượt đỏ giả tốn ~18 phút của mọi worker sau này. Nguyên nhân gốc đã biết và cách sửa đúng bằng cách commit này đã dùng hai lần (`@pytest.mark.perf`) | `apps/api/quality/tests/test_queue.py` (NO-264) | Sửa ngay sau merge: `Gate` tất định hoặc `@pytest.mark.perf`; đây là điều kiện theo dõi số một của nhánh |
| 112-2 | **P2** | TEST-04 / BE-00 §12 | 14 file test khác còn khẳng định trần đồng hồ / `timeout_s` mà chưa gắn `perf` theo luật mới — cùng lớp lỗi với 112-1, hôm nay chưa đỏ nhưng là mìn dưới `-n` | NO-272 (danh sách 14 file) | Rà từng chỗ: cận trên → `perf`; hạn chờ rộng → giữ |
| 112-3 | P3 | CON-06 / R-05 | Lượt dọn chạy `setval(seq, 1, false)` **trước** rồi mới `INSERT … SELECT *` nạp lại seed: bảng seed có cột `Identity()`/serial sẽ để bộ đếm ở 1 trong khi dòng seed đã chiếm 1…N → test đầu tiên chèn vào bảng đó đụng khoá chính. Hôm nay **chưa** nổ vì hai bảng seed duy nhất (`model_versions`, `model_families`) dùng khoá `Text` | `packages/testing/fixtures/db.py:106-140` (`_RESET_SQL`, `_build_reset_plan`) | Đưa lượt `setval` xuống **sau** lượt nạp lại, hoặc `setval(seq, max(col))`; thêm test bảng seed có `Identity()` |
| 112-4 | P3 | CON-06 | Lượt dọn chỉ xoá **dòng**. Bảng/kiểu/chuỗi do test tạo (`metadata.create_all` của `apps/api/core`, bảng dựng tay của `packages/db/tests/test_engine.py`) nay **sống** tới hết phiên tiến trình, trong khi bản cũ `CREATE DATABASE … TEMPLATE` mỗi test đã dọn chúng; `pg_get_serial_sequence` cũng bỏ qua chuỗi không thuộc cột nào. Chú thích trong mã mới chỉ nói tới rò **dữ liệu** | `packages/testing/fixtures/db.py:106-118` | Ghi rõ giới hạn này trong docstring (R-05), hoặc `DROP` bảng lạ ngoài danh sách của `upgrade head` |
| 112-5 | P3 | MNT-02 | Tài liệu lệch mã: `changes/FIX-112.md` vẫn viết "Postgres đã một DB mỗi test" (chính là thứ commit này thay) và không nêu `deploy/compose/verify.yml`, fixture `drawing_signer`, hai dấu `perf`; chú thích `db_sessionmaker` vẫn nói "mỗi test một database" | `changes/FIX-112.md:4`, `packages/testing/fixtures/db.py:280` | Cập nhật hai chỗ ở FIX kế tiếp chạm gói này |
| 112-6 | Nit | R-05 | Lập luận "O_APPEND không cho hai dòng xen nhau" chỉ đúng dưới `PIPE_BUF` (4 KiB); test đo bằng dòng ~120 byte | `tools/tests/test_parallel_fixtures.py:8-10` | Một dòng docstring nêu ngưỡng 4 KiB và đường nâng cấp (một file vết mỗi tiến trình) |

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25 % | 5 | 1,25 |
| CON | 15 % | 4 | 0,60 |
| LOG | 15 % | 5 | 0,75 |
| PERF | 10 % | 5 | 0,50 |
| RES | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 | 0,50 |
| TEST | 7 % | 3 | 0,21 |
| OBS, OPS | 5 % | 3 | 0,15 |
| MNT | 3 % | 4 | 0,12 |

Tổng: **4,58 / 5**

### PHÁN QUYẾT: APPROVE

Không P0/P1. Hai P2 đều đã có dòng `DEBT.md` (NO-264, NO-272) đúng R-38. Lợi đo được là thật và kiểm được từ log
(1.205 s → 555 s), cô lập được chứng minh bằng test tiến trình thật chứ không bằng lập luận. **Điều kiện theo dõi:**
112-1 phải được sửa ở FIX kế tiếp — một cổng đỏ giả 1/4 lượt là thuế lên mọi prompt sau.

---

## 3. B6-02 — phần còn lại của `git diff main...HEAD`

`apps/api/admin_ml_datasets` (N28-N31) + `apps/worker/datasets` (task `default.datasets.build_version`, hai lịch)
+ revision `r20260929_b6_02` + model, payload, factory.

**Soát trọng tâm — kết quả:**

- **K01** ✔ dây không mang `projectIds`/`requeueCount`/`createdBy`/`buildStartedAt` (`schemas.py:83-101`,
  `test_contract.py`); **K02** ✔ `manifestSha256`/`splitCounts` ⇔ `ready`, `failureCode` ⇔ `failed` giữ ở ba tầng
  (CHECK `manifest_ready`, `split_counts_ready`; `WireModel` bỏ trường `None`; `test_contract.py:112`) — xem 3-3 cho
  chỗ CHECK còn một chiều.
- **K17** ✔ `on_after_commit` ở `service.py:194` và `jobs.py:79`; `jobs._send_after_commit` là **hàm riêng** chứ
  không `lambda` trong vòng lặp (đúng bẫy closure), và `_requeue_unstarted` còn `await after_commit_idle(session)`
  để beat không trả về khi thông điệp chưa thật sự gửi.
- **K18** ✔ `datasets FOR UPDATE` → đọc `building` → `begin_nested` + bắt `IntegrityError`; unique partial
  `uq_dataset_versions_dataset_id_building` có ở cả model lẫn migration; C14 có test cho **cả hai** op
  (`test_write.py:111`, `:264`) và cho tầng hàm (`test_versions.py:94`). Giao lặp không tạo bản thứ hai:
  `_claim` trả `None` khi bản không còn `building` (`test_build_dataset_version__J06`, `__J06_late_run`,
  `__not_building`, `__second_version_keeps_first`).
- **K22/K36** ✔ mọi session đóng **trước** lượt `stat`/`open_read`/`put`/`delete_prefix`; đo bằng
  `pool.checkedout() == 0` khi một `put` đang bị chặn (`tests/test_perf.py:87,107,112`), pool chỉ 5 kết nối nên
  giữ session sẽ treo chứ không chỉ chậm. Ảnh trang chảy thẳng `open_read` → `put` qua `_chain`, không qua `bytes`.
- **K19** ✔ không chỗ nào mặc định tỉ lệ: `render.py` không có mặc định `mm_per_px`, tầng thiếu tỉ lệ bị bỏ
  (`no_scale`, `tasks.py:240`).
- **Thứ tự khoá `datasets → dataset_versions`** ✔ `start_version` khoá `datasets` trước (`versions.py:46`);
  `_claim` chỉ khoá `dataset_versions`; không đường nào khoá ngược.
- **`LockLost` trước mỗi `put` và trước `finish_version`** — trước mỗi `put` ✔ (`SampleWriter._put:95`, kể cả
  `put` của `manifest.jsonl` ở `finish:114`); trước `finish_version` ✔ (`tasks.py:495`). **Một lượt ghi kho không
  được rào** — xem finding 3-1.
- **Bản `ready` không bao giờ bị `delete_prefix`** ✔ ba đường đều đóng: `_finish` đọc **lại** trạng thái và chỉ xoá
  khi `failed` (`tasks.py:460-465`); `run_fail_dataset_version` chỉ xoá khi `fail_version` trả `True`
  (`:548`); `jobs._orphans` giữ mọi dòng `status != 'failed'`, tức cả `ready` lẫn `building` (`jobs.py:166-170`).
  Có test cho cả hai hướng (`__cleans_up_when_finish_loses`, `__keeps_objects_when_another_run_finished`).
- **Ranh giới `worker-no-web`** ✔ `lint-imports` ở bước 4, **cộng** một test chạy thật trong tiến trình con với
  `fastapi`/`starlette`/`uvicorn`/`jwt`/`argon2` đặt `None` trong `sys.modules` (`tests/test_boundary.py`) — bắt
  được cả lượt nhập trong thân hàm mà cây nhập tĩnh bỏ sót.
- **Luật vẽ tường / khe cửa / hộp** ✔ `_segment_corners_px` đúng cho đoạn xiên bất kỳ (không giả định trục), kéo
  dài nửa bề dày mỗi đầu cho thân tường và **không** kéo dài cho khe ô mở; `raster=True` lùi mép xa 1 px đúng quy
  ước nửa-mở của `PointPx`; chỉ ô mở `door` khoét mặt nạ, `window` không; hộp là hộp trục thẳng bao 4 góc, kẹp vào
  khung, hộp ngoài khung bị bỏ; `other` không có nhãn huấn luyện. Có test cho từng luật (`tests/test_render.py`).
- **Ma trận case [8]** ✔ `case_gate` xanh: bốn thao tác `ml_list_datasets`, `ml_create_dataset`,
  `ml_list_dataset_versions`, `ml_build_dataset_version` đều `đạt`, không thiếu case nào; `cases.toml` khai đúng
  phần thêm (`C14`, `C16`) và hai task (`build_dataset_version` J02/J03/J05/J08/J09,
  `sweep_dataset_version_builds` J07).
- **Mock/fake đúng tầng (K23 luật lai)** ✔ mọi test đường chính chạy Postgres thật (`db_sessionmaker`), Redis thật
  (`safe_client`, `broker`) và `LocalDiskStorage` thật; `AtPutStorage` chỉ là lớp bọc chèn điểm dừng, không thay SQL.

**Năm Lệch cần phán — tất cả CHẤP NHẬN:**

1. *`dataset_object` bị lách bằng `writer._sample_key`* (NO-263). Chấp nhận: `dataset_object` gọi `_name()` →
   `is_segment`, nên nó **không thể** nhận đường 3 đoạn mà `sample_path` trả; cách gọi prompt khối [6] mô tả luôn
   ném `ValueError`. Bản thay thế dùng đúng `check_id('dsv', …)` + `check_key` của lõi và **cùng** tiền tố
   `ml/datasets/{dsv}/` với `dataset_object` và với `version_prefix` — tôi đã đối chiếu ba chỗ, nên `delete_prefix`
   và lịch dọn vẫn phủ hết tệp mẫu. Nợ đã ghi đúng chủ (B0-04, `packages/storage`).
2. *`start_version` ném `ValueError` khi dataset không có (thay vì `None`)*. Chấp nhận và **tốt hơn** prompt: giữ
   cho `None` chỉ có một nghĩa ("đã có bản `building`" → 409). 404 đã kiểm trước ở `service._get_dataset`, nên
   `ValueError` chỉ đạt được khi người gọi tự bịa id — đúng lỗi lập trình. Có test.
3. *`DATASET_EMPTY` ném ở task*. Chấp nhận: nó là `failureCode` của một bản `failed`, không bao giờ là thân lỗi
   HTTP, nên không đăng ký `ERRORS.define` là đúng (khác `MODEL_VERSION_NOT_EVALUATED` của B6-01). Đường đi khép
   kín: `PermanentError(DATASET_EMPTY)` → `on_failed` → `fail_version` + `delete_prefix`.
4. *J09 viết trên `start_version` + `on_after_commit`, không qua route*. Chấp nhận: `service.build_dataset_version`
   là **nơi duy nhất** gửi task và `test_tasks.py:545` chạy đúng hook sau commit với broker thật; đường route được
   phủ riêng bởi `test_ml_build_dataset_version__C10_queue_once`.
5. *Hai lý do bỏ tầng thêm (`no_document`, `no_image`) và `wall_mask(..., openings=…)`*. Chấp nhận: không biết ô mở
   thì không có cách nào khoét khe cửa mà khối [6] đòi, và tham số có mặc định rỗng nên chữ ký prompt vẫn gọi được;
   hai lý do thêm đều có test (`test_read_floor_reports_a_missing_document`, `__missing_page_object`).

### Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 3-1 | **P2** | CON-05 / R-05 | `delete_prefix` dọn lượt chết giữa chừng là **lượt ghi kho duy nhất không đi qua rào khoá**, ngược với bất biến số 1 mà chính module khai (`tasks.py:5-8` "Khoá rào trước **mỗi** lượt ghi"). Kịch bản hỏng: khoá hết hạn trong lúc `_claim` chờ khoá dòng `dataset_versions`; worker B lấy được khoá, `_claim`, `delete_prefix`, bắt đầu ghi; worker A còn tới `LOCK_RENEW_MS` (20 s) trước khi vòng gia hạn huỷ nó, mà `delete_prefix` của A liệt-kê-rồi-xoá có thể vắt qua những `put` đầu của B → B chốt `ready` với manifest trỏ tới object A đã xoá | `apps/worker/datasets/tasks.py:487` | Thêm **một dòng** `await fence.check()` ngay trước `delete_prefix`; thêm test "khoá bị cướp giữa `_claim` và lượt dọn" |
| 3-2 | P3 | LOG-02 / R-16 | `walls_by_id[opening.wall_id]` ném `KeyError` với tài liệu có `wall_id` trỏ hư không → **chết cả lượt dựng** thay vì bỏ một tầng, ngược với nguyên tắc "bỏ theo lý do, không làm hỏng cả lượt" (`tasks.py:15-16`). Hôm nay không tái hiện được qua API: `apps/api/spatial_write/writer.py:285-287` chặn tài liệu có lỗi `critical` (`missingReference` của ô mở là `critical`) — nên đây là tầng phòng thủ thiếu, không phải lỗi sống | `apps/worker/datasets/render.py:118`, `:155` | `walls_by_id.get(...)` rồi bỏ qua ô mở mồ côi (hoặc trả một `SkipReason`); test tài liệu có `wall_id` mồ côi |
| 3-3 | P3 | DB-04 | CHECK `failure_code` chỉ một chiều (`failure_code IS NULL OR (status='failed' AND …)`), trong khi `manifest_ready` và `split_counts_ready` cùng bảng là `=` hai chiều. Dòng `failed` mà `failure_code IS NULL` được DB cho qua và sẽ phá luật dây `failureCode ⇔ failed` (K02); hôm nay không đường mã nào sinh ra nó (`fail_version` luôn có mã) | `packages/db/models/admin_ml_datasets.py:91-94`, migration `:105-108` | `(failure_code IS NOT NULL) = (status = 'failed')` ở revision expand kế tiếp — revision này đã hợp nhất thì không sửa (BE-00 §6.1) |
| 3-4 | P3 | MNT-01 / R-01 | 57 hàm thiếu docstring: 56 là test/helper test (`admin_ml_datasets/tests/test_write.py:50,74,124,181,219,234,245,252,279`, `tests/test_contract.py:41,48,52,85,92,97,112`, `tests/test_errors_settings.py:17,27,41`, `tests/test_versions.py:23,33,41,135,149,158,173`, `tests/test_read.py:17`, `worker/datasets/tests/test_render.py:13,36,60,80…`) và một mã thật: `_Beat.__init__` | như cột trước + `apps/worker/datasets/tasks.py:137` | Bổ sung một câu cho mỗi hàm ở FIX kế tiếp chạm module — cùng lớp với NO-262 |
| 3-5 | Nit | R-02 | `errors.py:18` nói `DATASET_BUILD_IN_PROGRESS` ⇔ "`versions.start_version` trả `None`" nhưng không nhắc đường `ValueError` thêm sau (chỉ có ở `versions.py:42-44`) — người đọc `errors.py` một mình sẽ tưởng `None` phủ cả hai ca | `apps/api/admin_ml_datasets/errors.py:18` | Thêm nửa câu trỏ sang `versions.start_version` |
| 3-6 | Nit | TEST-05 | `test_build_dataset_version__holds_no_connection_while_putting` là khẳng định **đúng đắn** K22/K36, không phải trần đồng hồ (chỉ có `wait_for(..., 30 s)` rộng rãi), nhưng ăn theo `pytestmark = pytest.mark.perf` cả file nên nó rời bước 5 (song song) sang 5b | `apps/worker/datasets/tests/test_perf.py:37,84` | Tách test này ra `test_tasks.py` hoặc bỏ `perf` riêng cho nó, để nó chạy dưới `-n` |

Không có finding SEC: bốn route đều `require_admin` khai một lần ở router; `dataset_id` sai mẫu ra **404** chứ không
rò sự tồn tại; `projectIds` kiểm cả mẫu lẫn "có thật và chưa xoá mềm" rồi ra **cùng** một 422 `field:"projectIds"`
(không máy dò); `name` qua `clean_text` (NFC + cấm `Cc`/bidi) rồi `name_key = casefold`; mọi khoá object qua
`check_id`/`check_key`; không bí mật trong log (`extra` chỉ mang id và mã).

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25 % | 5 | 1,25 |
| CON | 15 % | 3 | 0,45 |
| LOG | 15 % | 4 | 0,60 |
| PERF | 10 % | 5 | 0,50 |
| RES | 10 % | 5 | 0,50 |
| DB, API | 10 % | 4 | 0,40 |
| TEST | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT | 3 % | 4 | 0,12 |

Tổng: **4,42 / 5**

### PHÁN QUYẾT: APPROVE

Không P0/P1. Một P2 (3-1) và ba P3/Nit. Đây là mã cẩn thận: bất biến được khai rõ ở đầu module rồi giữ đúng ở hầu
hết mọi đường, session ngắn được **đo** chứ không khẳng định, ranh giới worker được kiểm bằng tiến trình thật,
và mọi Lệch khỏi prompt đều có lý do đứng được cùng nợ ghi đúng chủ.

---

## Tổng kết merge

| Thay đổi | Phán quyết | Điểm |
|---|---|---|
| FIX-111 `d8038d6` | **APPROVE** | 4,97 / 5 |
| FIX-112 `19a33d6` | **APPROVE** | 4,58 / 5 |
| B6-02 (phần còn lại) | **APPROVE** | 4,42 / 5 |

**Được merge** (squash ba commit theo thứ tự FIX-111 → FIX-112 → B6-02, giữ trailer `Prompt:`/`Fix:` của từng cái
theo R-36).

### Nợ phải ghi `DEBT.md` **trước** merge (R-38 — phiên review không sửa `DEBT.md`)

| Finding | Mức | Chủ | Tóm tắt dòng nợ |
|---|---|---|---|
| 3-1 | P2 | B6-02 (`apps/worker/datasets`) | `delete_prefix` dọn đầu lượt (`tasks.py:487`) không qua `fence.check()` — lượt mất khoá có thể xoá object của chủ khoá mới; sửa: `await fence.check()` trước lượt dọn + test cướp khoá giữa `_claim` và lượt dọn |
| 3-2 | P3 | B6-02 (`apps/worker/datasets/render.py`) | `walls_by_id[opening.wall_id]` ném `KeyError` làm chết cả lượt dựng thay vì bỏ một tầng; chặn bởi `check_integrity` ở đường ghi nên chưa tái hiện; sửa: `.get()` + bỏ qua |
| 3-3 | P3 | B6-02 (model + revision kế tiếp) | CHECK `failure_code` một chiều, cho phép `failed` không có `failureCode` (phá K02); sửa ở revision expand sau |
| 3-4 | P3 | B6-02 | 57 hàm thiếu docstring (56 test + `_Beat.__init__`) — cùng lớp NO-262 |
| 111-1 | P3 | B0-01 | NO-257 phải đổi trạng thái: nửa "test cổng tự cô lập `cases.toml`" đã xong ở FIX-111 |
| 112-5 | P3 | B0-01 | `changes/FIX-112.md` và chú thích `db_sessionmaker` còn mô tả cơ chế "một DB mỗi test" đã bị thay |
| 112-6 | Nit | B0-01 | Lập luận O_APPEND chỉ đúng dưới `PIPE_BUF` — ghi ngưỡng vào docstring |

112-1 (NO-264), 112-2 (NO-272), 112-3/112-4 (mở rộng NO-267) đã có dòng trong `DEBT.md`; 112-3 và 112-4 nên thêm
một dòng riêng vì NO-267 chỉ nói về chi phí kết nối, không nói về `setval`/rò lược đồ.
