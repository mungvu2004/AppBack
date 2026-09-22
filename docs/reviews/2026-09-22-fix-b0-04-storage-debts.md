# Review merge fix/b0-04-storage-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md`, `docs/fixes.md` và báo cáo `W1-STORAGE.report.md` đều tự kiểm lại) · Commit đầu nhánh: `ffbfcf4dbf49` = 9 commit FIX-011..019 của B0-04 (`f070775` … `5e0a831`, đúng sha ghi ở bảng `docs/fixes.md`) + commit gộp `main` `ffbfcf4` (cha `5e0a831`, `25dad10`). Merge-base với `main` = `25dad10`; phạm vi = `git diff main...HEAD` (10 file: `DEBT.md` + `packages/storage/**`).
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, lấy từ `RUN_SH_EXIT` của chính shell bọc (không bị cắt; lượt chạy 09:26:46–09:36:43 trên `ffbfcf4dbf49`, trước đó `docker ps -q --filter name=verify-run | wc -l` = 1). Log: `verify.log` trong scratchpad của phiên review. Bước 5: **1656 passed, 0 failed, 10 skipped**, 529,3 s; cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng — chưa có route được bảo vệ nào), đúng ngoại lệ BE-00 §12, file y hệt `main`.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,20 %** · nhánh **96,66 %**
  - `packages/storage` (gói duy nhất bị chạm): dòng **99,65 %** · nhánh **98,46 %**
  - tập file bị chạm: dòng **99,59 %** · nhánh **98,08 %**
  - Chạy riêng `packages/storage` + `apps/api/files` dưới coverage (probe P2): `keys.py`, `port.py`, `s3.py` **100 %** dòng và nhánh; `local.py` chỉ thiếu `188`, `279` (nhánh lỗi của `verify_token`/`_text`, nhánh không đụng tới, bộ đầy đủ đi qua). Mọi dòng nhánh sửa đều có test chạy qua; không dòng nào rơi vào sai số NO-035 (gói không dùng SQLAlchemy).

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (267 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (232 file) |
| 4 | `lint-imports` | đạt (mọi hợp đồng KEPT) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5; ba cảnh báo route hạ tầng sẵn có) |
| 6 | `lint_migrations` → `migrate_check` | đạt (3 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu phiên và cuối phiên) |
| `changes/B0-04.md` tồn tại | đạt (có từ B0-04; FIX không bắt buộc sửa mảnh) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 10 commit, dài nhất 70 ký tự |
| Trailer đọc được (R-36b) | đạt — `git log --format='%(trailers:key=Prompt,valueonly)'` ra `B0-04` ở cả 10 commit; 9 commit FIX ra đúng `Fix: FIX-011` … `FIX-019`; commit gộp không `Fix:` |
| Dòng `DEBT.md` đổi trong **chính** commit sửa | đạt — mỗi commit FIX sửa đúng một dòng (NO-009 … NO-017, `⬜` → `✅`) |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không (grep trên diff: 0) |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |
| File ngoài `packages/storage/**` (phạm vi [4] chung của FIX-011..019) | chỉ `DEBT.md` (luật của đoạn giao việc: dòng nợ đổi trong commit sửa) |

Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (`run.sh shell < probe.sh`, bản sao `/tmp/w`, file của commit cũ nhúng trong script dạng base64 nên không có gì ghi vào worktree):

- **P1 — đỏ trước / xanh sau từng FIX.** Mỗi FIX: test của chính commit FIX chạy trên mã của commit **cha** ("trước") rồi trên mã của commit FIX ("sau").

  | FIX | Test chặn tái phát | Trước (mã cha) | Sau (mã FIX) | Test đỏ ở lượt "trước" | Khớp dòng `DEBT.md`? |
  |---|---|---|---|---|---|
  | 011 | `test_server_error_with_xml_body_returns_503[500-InternalError, 503-SlowDown]` | 2 failed | 2 passed | cả hai tham số | ✓ — đúng hai test ghi ở NO-009 |
  | 012 | `test_delete_prefix_deletes_in_batches`, `…_reports_objects_it_could_not_delete` | 2 failed | 2 passed | cả hai | ✓ — NO-010 |
  | 013 | `test_signed_url_with_kind_does_not_stat[*]`, `…_rejects_kind_outside_server_named_keys[*]`, `test_server_chosen_kind_…[*]` | 15 failed, 2 passed | 17 passed | 9 tham số `test_server_chosen_kind_…` (hàm chưa có), 4 `rejects_kind_…` (thông điệp cũ "khoá ảnh đại diện"), 2 `with_kind_does_not_stat[local/s3-page_key]`; 2 lượt qua là `[local/s3-avatar_key]` — số đếm 9 + 4 + 2 = 15 chỉ khớp khi hai ca `page_key` đỏ | ✓ — NO-011 |
  | 014 | `test_delete_prefix_raises_instead_of_reporting_success`, `…_of_a_missing_prefix_is_silent` | 1 failed, 1 passed | 2 passed | `…_raises_instead_of_reporting_success` (ca "tiền tố chưa có" vốn đã im lặng) | ✓ — NO-012 |
  | 015 | `test_list_prefix_streams_the_tree_in_batches`, `test_list_prefix_orders_by_full_key[local, s3]` | 1 failed, 2 passed | 3 passed | `…_streams_the_tree_in_batches`; test thứ tự đã xanh trên mã cũ (bản cũ cũng sắp theo khoá đầy đủ) — đúng "giữ thứ tự hợp đồng hiện có" | ✓ — NO-013 |
  | 016 | `test_put_on_a_full_spool_disk_returns_503` | 1 failed | 1 passed | chính nó | ✓ — NO-014 |
  | 017 | `test_ensure_bucket_raises_when_cors_is_refused` (+ test MinIO `NotImplemented` cũ) | 1 failed, 1 passed | 2 passed | `…_raises_when_cors_is_refused`; test MinIO cũ xanh cả hai lượt | ✓ — NO-015 |
  | 018 | `test_stat_uses_filesystem_time`, `test_list_prefix_older_than[local, s3]` | 3 passed | 3 passed | — (không có đỏ tất định; lỗi cũ là chập chờn) | ✓ — hai test không còn `datetime.now`, mốc lấy từ `os.utime`/`stat()` của chính kho |
  | 019 | — (chỉ docstring, chú thích, lời test) | — | — | — | ✓ |

  Tập test đỏ/xanh khớp từng dòng nợ. **Thông điệp đỏ nguyên văn** mà các dòng nợ trích (vd NO-010 `['GET','DELETE','DELETE','DELETE']`, NO-012 "DID NOT RAISE") **chưa thu được**: lượt probe thứ hai dùng để in chúng bị Claude Code dừng vì máy thiếu RAM **khi còn đang chờ slot** (container chưa khởi động; log chỉ có dòng chờ), và theo luật của phiên thì không tự chạy lại. Lượt đầu đã in tên test đỏ và mã thoát, đủ cho luật 1 của FIX.md.

- **P2 — độ phủ riêng gói:** `packages/storage` + `apps/api/files` dưới coverage → `181 passed`; số liệu ở đầu file.
- **P3 — xoá nhiều lô trên MinIO thật (1001 object):** **chưa đo** — test có trong lượt probe thứ hai (bị dừng vì thiếu RAM, xem trên). Không finding nào dựa vào nó: #1 đứng trên mã test và chữ spec.
- **P4 — 5xx không phải lỗi tạm:** proxy trả `501 NotImplemented` (thân XML) cho `GET` → `open_read` ném `AppError DEPENDENCY_UNAVAILABLE`, `retry_after=5`, `__cause__` là `S3Error` (xem #3).
- **P5 — tiền tố trùng một tệp/object:** local (mã nhánh): `list_prefix` → `NotADirectoryError`, `delete_prefix` → `NotADirectoryError`; local (mã cũ `f72590b`): `[]` và im lặng; S3 (mã nhánh): `delete_prefix("projects/prj_…/")` im lặng và object `projects/prj_…` **vẫn còn** (`stat` khác `None`). `_delete_under` xoá mọi thứ mà `list_objects(prefix=…, recursive=True)` trả, và `list_prefix` gọi đúng lệnh đó, nên object còn sống nghĩa là lệnh liệt kê không trả nó: S3 coi tiền tố là rỗng. Dòng in riêng của `list_prefix` S3 nằm trong lượt probe thứ hai, lượt đó không chạy (xem #4).
- **P6 — AST các file `.py` của diff:** không hàm nào > 50 dòng (chỉ hai **lớp** bộ điều hợp dài, có từ trước). Hàm/lớp **mới** thiếu docstring: 5 (xem #6). Có từ trước nhánh, ngoài phạm vi FIX: 41 hàm test/hàm phụ, và 5 lớp/hàm sản phẩm (`LocalDiskStorage`, `ObjectInfo`, `SignedUrl`, `S3Storage`, `S3Storage.__init__`).
- **P7 — `minio` 7.2.20 trên Python 3.12.12:** `Minio._list_objects` và `Minio.remove_objects` là generator (gọi hàm không ra mạng; `list_prefix` dựng bộ duyệt ngoài `_s3_errors` là đúng); `remove_objects` lấy tối đa 1000 khoá mỗi lượt (nguồn thư viện: `zip(range(1000), delete_object_list)`, chú thích "get 1000 entries or whatever available").
- **P8 — hợp nhất với `main` hiện tại:** xem mục riêng dưới.

## Kiểm hợp nhất với `main`

- **`main` không còn là "chỉ thêm tài liệu".** Lúc review, `main` ở `55333dc feat(ml): add ml contracts, synthetic fakes and onnx loader` (B5-01, 48 file mã sau `25dad10`), không phải `1021267` như đoạn giao việc ghi. `git merge-tree --write-tree main HEAD` → cây `c25fa69`, **không xung đột**. B5-01 dùng `packages.storage` ở `apps/ml/runtime/{loader,tasks_util}.py` và `tests/helpers.py` (`ObjectStorage`, `LocalDiskStorage`, `CHUNK_SIZE`, `ObjectInfo`, `create_storage`, `get_storage_settings`) — mọi tên còn nguyên, `Protocol` `ObjectStorage` không đổi. Probe P8: phủ `apps/ml` + `packages/ml_contracts` của cây gộp lên mã nhánh, chạy `test_loader`, `test_tasks_util`, `test_probe_task`, `test_payloads` (so luật khoá với `check_key`), `packages/storage`, `apps/api/files` → **315 passed**. `uv.lock`/`pyproject.toml` không đổi giữa hai bên.
- **Người gọi của mọi tên nhánh đổi** (`git grep` trên `HEAD` và `main`): `keys.avatar_kind` → `server_chosen_kind`, `local._disk_errors`/`_UNAVAILABLE_ERRNOS` → `port.disk_errors`/`UNAVAILABLE_ERRNOS`, `S3Storage._list_under` (xoá), `LocalDiskStorage._keys_under` (đổi chữ ký) — **không ai ngoài gói gọi**. `apps/api/files/tests/test_files.py:47,64` ký `signed_url(AVATAR_KEY, disposition="inline", kind="png")`: `AVATAR_KEY` khớp nhánh ảnh đại diện của `server_chosen_kind`, test xanh trong cổng. `ensure_bucket` chưa có người gọi trong app (sẽ là B0-08), nên đổi sang fail-closed của FIX-017 không làm đổi hành vi khởi động hôm nay.
- **NO-017 phần B0-06 — khẳng định của tác giả đúng.** `apps/api/files/router.py:37-49` gọi `storage.stat(grant.key)` **lúc phục vụ**; `_disposition` (`:52-54`) chỉ trả `inline` khi token ghi `inline` **và** `info.kind ∈ IMAGE_KINDS`; `_content_type` lấy loại theo magic bytes cho bản `inline`. `test_inline_token_on_non_image_falls_back_to_attachment` (PDF ghi vào khoá ảnh đại diện, ký `inline, kind="png"`) chứng minh. B0-06 không cần sửa gì.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-01 · LOG-06 | Spec FIX-012 [6] (`docs/fixes.md:211`): "Test: xoá **> 1 lô** trên MinIO thật, đếm lượt gọi". `test_delete_prefix_deletes_in_batches` chỉ ghi **3** object (`range(3)`), nên chỉ chứng minh "1 `POST ?delete` thay cho 3 `DELETE`" — không chạm biên 1000 khoá/lượt, không chạm chỗ danh sách lười của `list_objects` nối sang lô thứ hai. Câu "(≤ 1000 khoá/lượt `DeleteObjects`)" của dòng NO-010 là hành vi của thư viện, không phải của test. Lệch spec không được ghi ở dòng nợ. Mã sản phẩm không sai (P7: `remove_objects` tự chia lô 1000 khoá), nhưng không test nào chốt được nó — chẳng hạn ai đó đổi sang gọi thẳng `_delete_objects` với cả danh sách thì 3 object vẫn xanh | `packages/storage/tests/test_s3.py:186-199` | Ghi 1001 object (song song bằng `asyncio.gather` có semaphore), khẳng định đúng **2** `POST ?delete`, 0 `DELETE`, tiền tố rỗng |
| 2 | P3 | MNT-03 · R-07 | `_SERVER_NAMED_RE` chép tay luật id tầng `L-[0-9A-Z]{10,64}` của `packages/core/ids.py:61` (`is_spatial_id`) — bản thứ ba của luật này trong repo (FE `ids.ts`, `core/ids.py`, nay `keys.py`). Hàm dựng khoá (`upload_page` → `_level_id` → `is_spatial_id`) và hàm nhận khoá (`server_chosen_kind`) đọc luật từ hai nguồn: `core` nới mẫu id tầng thì `upload_page` vẫn dựng được khoá mà `server_chosen_kind` không nhận ra → `signed_url(kind="png")` cho ảnh trang ném `ValueError` (500 ở danh sách thumbnail). Fail-closed, không lỗ bảo mật, nhưng trôi im lặng: test chỉ dùng id tầng 10 ký tự (`L-ABCDEFGHIJ`). Cùng họ với `NO-060` (luật khoá chép sang `ml_contracts`) | `packages/storage/keys.py:30-34`, `:62-67` | Kiểm từng đoạn bằng hàm công khai sẵn có: tách khoá theo `/`, `is_id("prj", …)`, `is_spatial_id("level", …)`, `is_id("upl", …)`, `pages/<số>.png` — đúng lối của hàm dựng khoá; hoặc tối thiểu thêm test `server_chosen_kind(upload_page(...))` với id tầng dài 10 và 64 để hai nguồn không trôi |
| 3 | Nit | LOG-04 · RES-02 | `_s3_errors` đổi **mọi** `S3Error` có `status >= 500` thành 503 + `Retry-After: 5`, kể cả `501 NotImplemented` — lỗi **vĩnh viễn** (kho S3-tương thích không hỗ trợ API đó), thử lại không bao giờ khỏi. Probe P4 xác nhận. Đúng chữ spec FIX-011 ("`response.status >= 500`"), nên chỉ là Nit | `packages/storage/s3.py:87-90` | `if exc.response.status >= SERVER_ERROR_STATUS and exc.code != "NotImplemented"` (dùng lại hằng `CORS_UNSUPPORTED`, đổi tên thành `NOT_IMPLEMENTED`); 501 để nổi lên như 4xx |
| 4 | Nit | LOG-02 | FIX-015 làm hai bộ điều hợp lệch nhau ở ca biên "đường dẫn của tiền tố là một **tệp**": `_keys_under` chỉ bắt `FileNotFoundError`, nên local `list_prefix` nay ném `NotADirectoryError` (500) trong khi mã cũ trả `[]` và S3 coi tiền tố là rỗng (probe P5). Không hàm dựng khoá nào sinh được khoá trùng đường dẫn tiền tố, nên ca này chỉ tới được bằng `put` khoá tay. `delete_prefix` cũng ném ở ca này — nhưng đó là **chủ ý** của FIX-014 (chính test NO-012 dùng ca này làm lỗi xoá tất định, vì container chạy root nên không dựng được lỗi quyền) | `packages/storage/local.py:238-242` | `except (FileNotFoundError, NotADirectoryError): return` trong `_keys_under` (tiền tố không phải thư mục = không có object nào dưới nó, như S3); thêm tham số hoá `object_storage` cho ca này vào `test_contract.py` |
| 5 | Nit | PERF-06 · R-22 · LOG-04 | `_delete_under` làm `errors = list(remove_objects(...))`: giữ **mọi** `DeleteError` trong RAM và gửi tiếp mọi lô dù lô nào cũng hỏng (khoá thiếu quyền `s3:DeleteObject` trên 1 triệu object = 1 triệu `DeleteError` + 1000 lượt `DeleteObjects` vô ích), trong khi chỉ in 5. Lỗi từng object `SlowDown`/`InternalError` (tạm) cũng thành `RuntimeError` như `AccessDenied` (vĩnh viễn) — chấp nhận được vì chỉ lịch dọn rác gọi và lượt sau chạy lại | `packages/storage/s3.py:276-279` | Duyệt lười: đếm tổng, giữ ≤ `DELETE_ERRORS_SHOWN` mẫu; hoặc dừng ở lô đầu có lỗi và ném ngay (lịch dọn chạy lại) |
| 6 | Nit | R-01 | Năm hàm/phương thức mới không docstring (probe P6): `FaultProxy.__init__`, `original_key`, `_FullDiskSpool.__enter__`, `.write`, `.seek`. Cùng lối với 41 hàm test/hàm phụ có từ trước trong các file này, nên không nâng mức (5 lớp sản phẩm thiếu docstring có từ B0-04, ngoài phạm vi FIX — FIX.md luật 3) | `packages/storage/tests/fault_proxy.py:55`; `tests/test_contract.py:221`; `tests/test_s3.py:218,224,227` | Một câu mỗi hàm (vd `write`: "Ghi nào cũng gặp `ENOSPC` — dựng đúng cảnh bộ đệm tràn xuống đĩa đầy") |
| 7 | Nit | SEC-07 (gia cố) | FIX-013 mở rộng lòng tin "đuôi do server chọn **sau khi đã kiểm magic bytes**" từ ảnh đại diện sang `…/pages/{i}.png`, nhưng điều kiện đó chỉ là quy ước cho người ghi (pipeline B2-xx), gói không ép: `put` nhận byte bất kỳ ở khoá trang/ảnh đại diện. Chính `apps/api/files/tests/test_files.py:63-64` ghi **PDF** vào khoá ảnh đại diện rồi ký `inline, kind="png"` thành công. Bản local an toàn vì route đọc lại `kind` lúc phục vụ; bản S3 thì URL ký cố định `response-content-type: image/png` + `inline` không có `HEAD`, nên phục vụ byte không phải PNG với nhãn `image/png`. Không khai thác được (origin S3 khác `PUBLIC_BASE_URL` theo BE-00 §8, trình duyệt không chạy `image/png` như HTML) — chỉ là gia cố | `packages/storage/keys.py:62-67`; `local.py:73`, `s3.py:115-161` (`put`) | Trong `put` của hai bộ điều hợp: `expected = server_chosen_kind(key)`; `expected is not None and sniff(head) != expected` → `ValueError` (không ghi). Bất biến của `server_chosen_kind` khi đó do gói giữ, không do người gọi nhớ |

**P0: 0 · P1: 0 · P2: 0 · P3: 2 · Nit: 5**

## Những chỗ đã soi kỹ và **đạt**

- **FIX-011 (NO-009) — sửa gốc (R-19).** `_s3_errors` là context manager duy nhất bọc mọi lời gọi mạng của `S3Storage` (`ensure_bucket`, `put`, `stat`, `open_read`, `delete`, `delete_prefix`, từng lô của `list_prefix`), nên nhánh `S3Error ≥ 500` áp cho mọi đường, không riêng `GET` mà test tiêm lỗi. Thứ tự `except` đúng: `stat`/`open_read` bọc `try: with _s3_errors(): … except S3Error` — 5xx đã thành `AppError` trước khi tới nhánh `_MISSING_CODES`; 4xx (`AccessDenied`) nổi lên nguyên vẹn (chạy qua bởi test CORS 403). Không thêm `status_forcelist` là đúng phạm vi (thử lại 5xx cho `PUT` không idempotent theo phía client là đổi hành vi). Proxy tiêm lỗi đứng trước MinIO **thật**, chuyển nguyên `Host` nên SigV4 vẫn khớp — không mock MinIO (K23).
- **FIX-012 (NO-010).** `remove_objects` + generator lười của `list_objects`, không `list(...)` danh sách khoá; lỗi từng object trong thân 200 không bị nuốt (R-16), thông điệp có tổng số và ≤ 5 khoá, không lộ bí mật. Đếm request qua proxy: 0 `DELETE`, đúng 1 `POST ?delete`.
- **FIX-013 (NO-011).** `fullmatch` trên cả phép hoặc (khoá thừa đoạn `pages/sub/0.png`, đuôi `.jpg` ở trang, `original.png`, ảnh đại diện `.pdf` → `None`, có test từng ca); `kind` truyền sẵn sai đuôi vẫn `ValueError`; `kind=None` + `inline` vẫn đọc metadata và 404 khi thiếu. Ký `inline` ảnh trang không tốn `HEAD` trên cả hai bộ điều hợp (test đếm lượt `stat`).
- **FIX-014 (NO-012).** `rmtree(onexc=_ignore_missing)`: chỉ `FileNotFoundError` được bỏ qua (tiền tố chưa có, mục bị xoá đồng thời), lỗi khác qua `disk_errors` (ENOSPC/EROFS/EDQUOT → 503) hoặc nổi lên; `_disk_errors` không còn là mã chết. `onexc` cần Python ≥ 3.12 — container 3.12.12.
- **FIX-015 (NO-013).** `next_batch` kéo ≤ `LIST_BATCH` mục mỗi lượt trong luồng riêng (không chặn vòng sự kiện, R-23), đọc `LIST_BATCH` lúc gọi; S3 kéo đúng trang `ListObjectsV2` cần tới; local `os.scandir` lười từng thư mục, danh mục được vật hoá rồi đóng **trước** khi `yield` (bỏ dở vòng lặp không rò fd). Thứ tự "thư mục `a` xếp như `a/`" đúng bằng thứ tự byte của khoá đầy đủ (so sánh chuỗi Python theo code point = thứ tự byte UTF-8, khoá lại chỉ ASCII qua `check_key`), có test `a.b < a/b < a0` cho cả hai bộ điều hợp. Bộ duyệt đồng bộ được tiến tuần tự từ nhiều luồng, không bao giờ đồng thời (async generator không cho `anext` chồng).
- **FIX-016 (NO-014).** `disk_errors`/`UNAVAILABLE_ERRNOS` lên `port.py`, `local.py` dùng lại (R-07, bản cũ xoá hẳn); `S3Storage.put` bọc cả vòng đệm; `PAYLOAD_TOO_LARGE` không phải `OSError` nên vẫn là 413; không để lại object khi hỏng. Tiêm lỗi bằng thay `SpooledTemporaryFile` (đĩa cục bộ, không phải dịch vụ đang kiểm — K23 không áp).
- **FIX-017 (NO-015).** Chỉ `NotImplemented` (đúng mã MinIO đã đo, test MinIO thật vẫn xanh) được ghi `INFO`; mã khác ném lại, 5xx của `PutBucketCors` đi tiếp qua `_s3_errors` → 503 — fail-closed (R-17), đúng một trong hai hướng spec cho phép.
- **FIX-018 (NO-016).** Hai test không còn đồng hồ thật: `os.utime` ghim `st_mtime` rồi so **bằng**; `older_than` lấy từ `stat()` của chính kho (`+1 s` → có, `=` → không, đúng phép `<` chặt) — tất định cả trên MinIO (Last-Modified tròn giây, hai vế cùng từ `HEAD`).
- **FIX-019 (NO-017).** `FileGrant` ghi rõ token không mang `kind` và nơi phục vụ phải tự đọc; `signed_url` nói vì sao bỏ giá trị `resolve_kind`; `_message` nói đúng bốn trường `k|e|d|n` và vì sao `n` chặt hơn BE-00 §8; lời test nói đúng "không chứa khoá **dạng thô**". Khớp `apps/api/files/router.py` (docstring module cũng ghi MAC trên bốn trường).
- **Kích thước (MNT-05):** ≈ 137 dòng sản phẩm thêm (`keys` 11, `local` 38, `port` 39, `s3` 49, không kể dòng trống/chú thích) + ≈ 325 dòng test (gồm `fault_proxy.py` 139) — dưới trần 400 dòng logic, không cần tách.
- **Ranh giới (R-27, R-28):** chỉ `packages/storage/**` + `DEBT.md`; `fault_proxy.py` nằm dưới `tests/`, không bị mã sản phẩm nhập; `port.py` chỉ thêm nhập thư viện chuẩn; `lint-imports` KEPT.

## Tuyên bố của tác giả (báo cáo `W1-STORAGE.report.md`)

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | Cổng thoát 0, 1656 passed / 0 failed / 10 skipped | **Đúng** — lượt độc lập của review ra cùng số (529 s thay vì 377 s do chạy song song với lượt khác) |
| 2 | Độ phủ tổng 99,20 % · 96,66 %; `packages/storage` 99,65 % · 98,46 % | **Đúng** — trùng từng chữ số |
| 3 | Gộp `main` sạch, `DEBT.md` chỉ khác 9 dòng NO-009..017 | **Đúng** — `git diff main...HEAD -- DEBT.md` đúng 9 dòng |
| 4 | Không ai ngoài gói gọi tên bị đổi | **Đúng** — kể cả với `main` mới hơn (`55333dc`, B5-01) |
| 5 | NO-017 phần B0-06 không cần sửa | **Đúng** — xem mục hợp nhất |
| 6 | Đỏ → xanh của FIX-011..018 nằm ở báo cáo từng FIX | **Đúng** — review tự tái hiện được cả bảy FIX có đỏ (P1), tập test đỏ khớp dòng `DEBT.md`; thông điệp đỏ nguyên văn chưa đối chiếu (probe thứ hai không chạy) |
| 7 | "`main` chỉ thêm tài liệu sau `25dad10`" (đoạn giao việc) | **Không còn đúng** lúc review: `main` đã có B5-01 (`55333dc`). Gộp vẫn sạch và test phụ thuộc chéo xanh (P8) — không chặn |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng có dòng và nói đúng sự thật | đạt — NO-009..NO-017 `✅` kèm ngày 2026-09-21 và mã FIX; tên test, tập test đỏ/xanh, lựa chọn phạm vi ("không `status_forcelist`", "không `limit`/`continuation_token`") khớp mã và probe (thông điệp đỏ nguyên văn chưa đối chiếu, xem P1); riêng NO-010 nói "(≤ 1000 khoá/lượt)" mà test không chứng minh (#1) |
| Nợ mới tác giả nêu | không có — báo cáo "Nợ và việc chưa làm: không", khớp diff (không `TODO`/`ponytail:` mới) |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh để lại | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — dòng đề xuất dưới (id do người điều phối cấp; phiên này không ghi `DEBT.md`) |

Dòng đề xuất (chỉ cần nếu tác giả không sửa trên nhánh trước khi merge):

```text
| ⬜ | NO-<nnn> | 2026-09-22 | | `test_delete_prefix_deletes_in_batches` chỉ ghi 3 object nên không chạm biên 1000 khoá/lượt `DeleteObjects` mà FIX-012 [6] yêu cầu ("xoá > 1 lô") | Chọn cỡ nhỏ cho test nhanh; "≤ 1000 khoá/lượt" là hành vi của `minio.remove_objects`, chưa test nào chứng minh | B0-04 (`packages/storage/tests/test_s3.py:186`) | P3 | mở — review merge 2026-09-22 finding #1 (`docs/reviews/2026-09-22-fix-b0-04-storage-debts.md`). Chữa: 1001 object ghi song song, khẳng định đúng 2 `POST ?delete`, 0 `DELETE`, tiền tố rỗng |
| ⬜ | NO-<nnn> | 2026-09-22 | | `keys._SERVER_NAMED_RE` chép tay luật id tầng `L-[0-9A-Z]{10,64}` của `packages/core/ids.py:61` — hàm dựng khoá và `server_chosen_kind` đọc luật từ hai nguồn (R-07) | Một regex cho gọn thay vì kiểm từng đoạn bằng `is_id`/`is_spatial_id` như hàm dựng khoá | B0-04 (`packages/storage/keys.py:30-34`) | P3 | mở — review merge 2026-09-22 finding #2; cùng họ NO-060. Chữa: tách khoá theo `/` và kiểm từng đoạn bằng `is_id`/`is_spatial_id`; hoặc test khoá trang với id tầng dài 10 và 64 |
```

Nit #3–#7 do tác giả tự quyết, không cần dòng nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (Nit #7) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (Nit #3, #4) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (Nit #5) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #1) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #2; Nit #6) | 0,12 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,28 + 0,25 + 0,12 = **4,90 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 ở lượt chạy độc lập, không P0/P1/P2, điểm 4,90 ≥ 4,0. Cả chín FIX sửa ở **gốc**, qua chỗ mọi đường gọi đi qua (R-19): 5xx có thân XML ở `_s3_errors` dùng chung, lỗi đĩa ở `port.disk_errors` cho cả hai bộ điều hợp, luật `kind` ở `server_chosen_kind` mà `resolve_kind` của cả hai bộ điều hợp gọi. Mỗi FIX đúng phạm vi [4] (`packages/storage/**` + dòng `DEBT.md` của chính nó). Bảy FIX có đỏ đều được review tự tái hiện đỏ trên mã cha, xanh trên mã FIX, và tập test đỏ khớp dòng nợ. Khẳng định "NO-017 phần B0-06 đã tuân" đúng ở `apps/api/files/router.py`. Nhánh gộp sạch với cả `main` mới hơn đoạn giao việc (B5-01 `55333dc`), và test phụ thuộc chéo đều xanh. Hai P3 (#1 test FIX-012 chưa chạm biên lô như spec, #2 luật id tầng chép tay) không chặn merge.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): hoặc tác giả sửa #1, #2 trên nhánh (hai commit `fix(storage)`/`test(storage)` `Prompt: B0-04`, chạy lại cổng), hoặc người điều phối ghi hai dòng `⬜` P3 ở trên vào `DEBT.md`. Nit #3–#7 không chặn.
2. Gộp bằng `git merge --no-ff` (R-36; `docs/fixes.md:160`, `:280`): **không** squash, để giữ nguyên sha `f070775` … `5e0a831` mà bảng `docs/fixes.md` và `DEBT.md` đang trỏ tới, cùng chín trailer `Fix: FIX-011` … `FIX-019`.
3. `main` đã đi tới `55333dc` (B5-01, không chỉ tài liệu): gộp không xung đột (`git merge-tree` → `c25fa69`). Sau khi gộp, chạy `bash tools/verify/run.sh verify` trên `main` (nhánh `integration`; xuất `openapi.json` ra gốc trước cho bước 8 như mọi lần gộp).
