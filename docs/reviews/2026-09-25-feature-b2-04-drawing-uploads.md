# Review merge `feature/b2-04-drawing-uploads` → main

- Ngày: 2026-09-25 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `23b014875661`
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ trong worktree review ở đúng sha,
  8/8 bước đạt)
- Độ phủ: tổng dòng **99,48 %** · nhánh **98,36 %** · `apps/api/drawings` dòng **99,71 %** · nhánh **98,56 %**
  · tập file bị chạm dòng 99,66 % · nhánh 98,13 %
- Test: **4395 passed, 0 failed**, 4 deselected (969,36 s)

## Trạng thái cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | 714 file |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4395 passed / 0 failed |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm |
| 6 | `lint_migrations` → `migrate_check` | đạt | 1 head; upgrade/downgrade/upgrade lại |
| 7 | `tools.contract.check` (H1 H3 H4 H5) | đạt | H1 1081 mẫu · H1 ngữ cảnh 42 mẫu · H3 10 khoá/3 vai · H5 4 khung · **H4 không áp dụng** (B3-05 chưa hợp nhất — đúng BE-00 §12) |
| 8 | `openapi` | đạt | 100 321 byte |

Điều kiện dừng sớm: cây sạch; `changes/B2-04.md` có; 10 commit đều đúng mẫu Conventional Commits
kèm trailer `Prompt:` (`e9ef485` thêm `Fix: FIX-107` đúng luật); không đụng `docs/charter/*`,
`tools/contract/APPFRONT_SHA`, `uv.lock`; `docs/contracts/openapi.json` chỉ **thêm** 530 dòng
(5 đường + 6 schema của B2-04, `git show 6254ba9` không có dòng `-` nào); không `pragma: no cover`,
không `type: ignore`, không `skip`/`xfail` mới, không `except Exception`; đúng **một** `# noqa: S603`
có mã và lý do (`tests/test_boundary.py:27`).

FIX-107 (`e9ef485`, chỉ `apps/api/streams/tests/test_registry.py`): dựng sổ từ `extensions.override`
**rỗng** thay vì lượt dò repo thật; giữ nguyên cả hai assert (`DenyUploads`, `snapshot is policy`),
không nới, và chạy được cả trong repo không có `apps/api/drawings`. Đúng phương án đã duyệt.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-34 / MNT-02 | Bốn nợ tác giả tự nêu trong `bao-cao-B2-04.md` mục "Nợ và việc chưa làm" **không** có dòng `DEBT.md`: (a) `/src` mount read-only của `run.sh` (báo cáo tự viết "Nên ghi vào ENV.md/DEBT.md"); (b) `new_ulid()` cho B0-02 — NO-168 vẫn ghi "bản thứ hai" trong khi đây là bản thứ ba; (c) chủ đúng của `chunk_key` là `packages/storage/keys.py` — NO-079 chưa ghi; (d) `_BIDI` bản sao **thứ tư** — NO-169 vẫn ghi "bản thứ ba" | `DEBT.md` (nhánh không đụng) ↔ `apps/api/drawings/drawings.py:43`, `apps/api/drawings/uploads.py:92`, `apps/api/drawings/schemas.py:33-38` | Điều phối viên (chủ `DEBT.md`) thêm/nới 4 dòng trên `main` cùng lượt gộp |
| 2 | P2 | MNT-05 | Nhánh ~2 760 dòng logic (20 file mã nguồn, chưa kể 4 568 dòng test) > trần 400 | `git diff --stat main...HEAD` | **Chấp nhận, không tách**: khối [10] của B2-04 là một đơn vị bàn giao (4 bảng + 5 route + 3 lịch + 2 cổng), tách phá thứ tự phụ thuộc B2-04 → B2-05b/B5-06a — cùng lý do đã chấp nhận ở NO-123. Cần một dòng `DEBT.md` `chấp nhận` kèm lý do |
| 3 | P3 | API-02 | Ảnh trang được ký `attachment` + `application/octet-stream` chứ không `inline` + `image/png` như mọi ảnh do server đặt tên khác. Nguyên nhân gốc: `new_page_key` dựng `pages/{i}-{ULID}.png` (theo đính chính §13) mà `keys.server_chosen_kind` chỉ nhận `pages/{i}.png`, nên `kind` không truyền được | `apps/api/drawings/drawings.py:44,47-49`; bằng chứng: `packages/storage/keys.py:103-107`, `packages/storage/port.py:187-189`, tiền lệ `apps/api/me/avatar.py:246` | `Drawing.url` (N1) và `sourceImageUrl` (N7) là **cùng một ảnh** FE hiển thị (HOP-DONG-MOI:335). Nợ cho B0-04: dạy `upload_page`/`server_chosen_kind` bố cục có ULID, rồi ký `inline` + `kind="png"` |
| 4 | P3 | PERF-01 | Ký URL gọi `presigned_get_object` — hàm **đồng bộ** — thẳng trên vòng sự kiện, một lượt mỗi mục trong vòng lặp; N7 cho `limit` tới 200 và `view_parts.load` chạy cho **mọi** tầng của **mọi** dự án trong N1 | `apps/api/drawings/latest.py:99-107`, `apps/api/drawings/view_parts.py:42-54`; bằng chứng `packages/storage/s3.py:236`, `apps/api/drawings/latest.py:33` | NO-207 đã ghi đúng lỗi này nhưng chỉ nêu `apps/api/me/avatar.py` — nới NO-207 thêm hai chỗ gọi mới; nâng cấp: ký lô trong `asyncio.to_thread` |
| 5 | P3 | R-01 | Ba hàm thiếu docstring | `apps/api/drawings/runs.py:83` (`_snapshot`), `apps/api/drawings/tests/test_jobs.py:45,48` (`_FailingStorage.delete`, `.delete_prefix`) | Thêm một dòng cho mỗi hàm |
| 6 | P3 | MNT-02 / TEST-04 | Fixture `latest_client` nạp `latest_router` **lần thứ hai**: `router.py:30` đã khai `ROUTERS = (router, latest_router)` và `apps/api/core/app.py:89-96` trải mọi phần tử, nên `api_app` đã có N7. Docstring còn viết "`apps/api/drawings/router.py` chưa có trên nhánh này" — đúng lúc việc B viết, sai sau khi G trộn fragment (`b049638`) | `apps/api/drawings/tests/test_routes_latest.py:50-56` | Bỏ fixture, dùng `api_client` như các file test route khác |
| 7 | Nit | R-07 | `_EXT_KIND` là bản sao từng byte của `uploads.EXT_KIND`, trong khi file **đã** nhập từ chính module ấy (dòng 20) | `packages/testing/factories/drawings.py:34` ↔ `apps/api/drawings/uploads.py:53` | `from apps.api.drawings.uploads import EXT_KIND` |
| 8 | Nit | R-02 | Chuỗi tài liệu của `chunk_key` nằm cách lệnh nhập nó 18 dòng, không gắn vào ký hiệu nào | `packages/testing/factories/drawings.py:38` | Dời lên ngay dưới dòng 20 hoặc bỏ |
| 9 | Nit | R-10 | Nhánh `else b""` không tới được: `keep = len(marker) - 1` là 3 cho `png`, 1 cho `jpeg`; `pdf` đi nhánh `_tail_only` | `apps/api/drawings/complete.py:104` | `self._buf = data[-keep:]` |
| 10 | Nit | R-02 | `Create Date: 2026-09-25` cắt ngắn so với `script.py.mako` (`${create_date}` dạng đầy đủ ở mọi revision khác, vd `r20260925_b2_02_project_settings.py:5`) — hệ quả của việc viết tay revision (lệch #4 của D) | `packages/db/migrations/versions/r20260925_b2_04_drawings.py:5` | Chép đúng dạng công cụ sinh |

Không có P0, không có P1.

## Đã tự kiểm, không thành finding

- **`Progress`** (`progress.py:52-69`): bảng nguồn trạng thái BE-BIND §4 nằm ở **một** hàm thuần;
  `endedAt` chỉ khi `completed` (K33); `error` luôn là mã UPPER_SNAKE; trường vắng thì vắng hẳn (W2);
  `progressPercent` lấy `max` ở `_apply` nên không lùi, trọng số suy từ `PIPELINE_STEPS` (tổng 100).
  Bốn nhánh H1 có mẫu 2xx (bước 7 `đạt`).
- **`record_step`** (`runs.py:394-423`): bước lùi / giao lặp J06 / lượt đã kết thúc / bị thay đều trả
  `None` và **không ghi gì**; xoá mềm trong cửa sổ `FLOOR_RESTORE_WINDOW_S` ghi như tầng sống, quá cửa
  sổ hoặc dự án xoá mềm → `FLOOR_DELETED` không `ended_at`; `_floor_was_recreated` loại chính `floor.pk`
  nên dòng đếm của tầng tạo lại không bị đè (lệch #2 của D — có lý do đứng được, `uq_floors_level`
  bảo đảm hàng trả về luôn là tầng thay thế). `fail_run` (lệch #3 của D) là cách duy nhất giữ luật dòng
  đếm ở **một** bản khi lõi quét bù cần đánh hỏng lượt — chấp nhận.
- **K36**: `uploads.py:298` và `complete.py:306` `await db.rollback()` **trước** giải mã/băm/`put` và
  trước sniff/nối/đếm trang; `UploadFacts` là bản chụp đông cứng nên không giữ đối tượng ORM qua ranh
  giới. `test_chunk_upload_does_not_hold_the_pool__K36` đo thật trên app `DB_POOL_SIZE=1`,
  `DB_MAX_OVERFLOW=0`: `pool.checkedout() == 0` và #8 trả trong 0,006 s.
- **#7 bảy bước** (`complete.py`): đúng thứ tự; tệp hỏng **trả** `Response` W7 422 chứ không ném
  (`routing.py:16` xác nhận response 4xx *trả về* vẫn commit) nên dòng `rejected` sống; `original.*`
  bị xoá ở `_reject`; C14 khoá tầng (`get_floor for_update`) rồi khoá upload; 409
  `UPLOAD_CHUNKS_CHANGED` khi danh sách khoá đổi; NO-124 log `exc.__cause__` mức warning
  (`_page_count`); U07 dò dấu kết thúc **trên luồng** nối, không nạp cả tệp (trừ PDF, có lý do).
- **J09/K17/K18**: `send_task` và `publish` chỉ qua `on_after_commit` với callback **đồng bộ**
  (đính chính §2); `publish_progress_after_commit` chụp `Progress` trong giao dịch rồi mới hẹn.
  Không module nào khai `pipeline.orchestrate.start` — chỉ gửi ([12]). C10 có hai test riêng đếm
  thông điệp `pipeline.cpu` trên Redis thật.
- **#5**: tên/đuôi/MIME/kích thước/`pageIndex` đúng mã và `field`; khử trùng chạy dưới khoá tầng nên
  đúng cả tuần tự lẫn song song (`test_init_twice_in_parallel_reuses_one_upload`); hạn mức
  `on_error="open"`, `store="cache"`.
- **Quyền [7]**: `floor.upload` cho #5–#7, thành viên cho #8/N7/S1; `load_upload` lọc `project_id` và
  tầng chưa xoá nên upload dự án khác → 404; C06 kiểm người ngoài mang vai `admin` vẫn 404.
- **N7**: **một** câu, `DISTINCT ON (floors.pk)` + `LATERAL` lượt chạy mới nhất, `nulls_last` đưa ứng
  viên có lượt chạy lên trước, tầng chưa có lượt rơi về upload mới nhất khác `rejected`; cursor
  `(floor_order, floor_pk)`; `sourceImageUrl` chỉ khi `DrawingRow.upload_id == UploadRow.id`.
  `attach_floor_order` (`_drawing_helpers.py:31-38`) gọi `attach_context` **không điều kiện** — nhánh
  bỏ qua mà việc B mô tả đã bị gỡ; `23b0148` gắn cho **mọi** mẫu 2xx, kể cả trang rỗng và trang hai.
- **Bản vẽ**: `upsert_drawing` mở bằng `lock_run`; `new_page_key` sinh ULID mới mỗi lượt (W23);
  `ValueError` cho kích thước ≤ 0, upload chưa `complete`, upload khác tầng, khoá trang sai chỗ
  (kiểm bằng `upload_prefix_of` của lõi, không regex); cổng `drawing_scales` + W24 `max(1, round(...))`;
  `drawing_pages`/`view_parts` mỗi bên một truy vấn, có test số câu SQL không đổi giữa 1 và 20 tầng.
- **Việc nền**: `_found` lọc bằng `upload_prefix_of` (NO-079), không regex tự viết; lô tra DB 500;
  cửa sổ lùi `AFTER × 2^requeue_count`, trần `REQUEUE_MAX = 6` rồi `PIPELINE_STALLED` qua `runs.fail_run`;
  `jobs.py` chỉ UPDATE `requeue_count`/`updated_at` — đúng [9]; mọi lượt gọi kho nằm ngoài giao dịch;
  J01/J06 đủ cho ba lịch; `test_boundary.py` kiểm 5 module nhập được khi chặn `fastapi/starlette/jwt/argon2`
  bằng **tiến trình Python mới**.
- **Migration** (DB-01..05): expand thuần, hằng chép tay không nhập model; CHECK đủ; FK tới
  `projects.id`/`floors.pk`/`uploads.id` đều `ON DELETE CASCADE`; `superseded_by` cố ý không FK (có lý do);
  `uq_drawings_floor_pk`; hai index của `pipeline_runs` phục vụ đúng `start_run`/N7 và lịch quét bù;
  index một phần của `uploads` phục vụ khử trùng; `downgrade` đảo thứ tự; bước 6 xác nhận 1 head.
- **TEST**: không mock Postgres/Redis/MinIO/Mailpit (chỉ `GatedStorage`/`_FailingStorage` bọc kho đĩa
  **thật** để chèn lỗi, và một `monkeypatch` hằng `LOOKUP_BATCH`); không tải mạng; PDF mẫu mượn
  `packages.vision.preprocess.tests.synthetic` thay vì bản sao thứ hai (R-07).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 4 | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 | 0,40 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,67 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1; cổng đầy đủ xanh 8/8 với mã thoát thật 0, độ phủ vượt ngưỡng ở mọi gói bị chạm.
Mọi trọng tâm soát của prompt đều tự kiểm được bằng mã trong diff: luật `Progress` sống ở **một** hàm
thuần, `record_step` không tin worker và không ghi gì cho mọi lượt giao muộn, K36 có phép đo thật trên
pool một kết nối, #7 giữ được dòng `rejected` vì **trả** chứ không ném, tác dụng ngoài chỉ chạy sau
commit bằng callback đồng bộ, N7 gọn trong một câu `DISTINCT ON`, lịch nền lọc khoá bằng hàm của lõi
và chỉ đụng `requeue_count`. Hai P2 đều thuộc miền bảo trì và **không** nằm trong mã: chúng là sổ nợ.

**Điều kiện kèm theo (không chặn merge, làm cùng lượt gộp):** điều phối viên — chủ `DEBT.md` — ghi
sáu dòng trước hoặc trong commit gộp: bốn nợ của finding #1, một dòng `chấp nhận` cho finding #2 (mẫu
NO-123), một dòng mới cho finding #3, và nới NO-207 theo finding #4. Finding #5–#10 để prompt sau hoặc
một FIX gom.
