# Review merge feature/b0-04-object-storage → main

- Ngày: 2026-09-20 · Reviewer: phiên /merge-review (độc lập, không phải tác giả) · Commit đầu nhánh: `68cdebea9885` (gốc `def60baa4b72`)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ, 2026-09-20; log phiên, 692 test xanh, 114,6 s)
- Độ phủ (in từ `tools.coverage_gate`, không phải từ báo cáo tác giả):
  - tổng: dòng **98,94 %** · nhánh **95,30 %**
  - `packages/storage`: dòng **99,62 %** · nhánh **98,21 %**
  - `packages/db`: dòng 98,57 % · nhánh 97,32 % · `packages/testing`: 100 % / 100 % · `tools`: 98,24 % / 93,17 %
  - tập file bị chạm: dòng 99,23 % · nhánh 97,52 %
- Bảng cổng thật: 1 `ruff format` đạt · 2 `ruff check` đạt · 3 `mypy --strict` đạt · 4 `lint-imports` đạt · 5 `pytest → coverage_gate` đạt · 5b `perf → case_gate` đạt · 6 `lint_migrations → migrate_check` đạt · 7 `tools.contract.check` không áp dụng · 8 `openapi` không áp dụng.
  Hai bước "không áp dụng" đúng luật BE-00 §12 (B0-06 chưa hợp nhất nên chưa có `apps/api`), **không** phải "hỏng".

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B0-04.md` tồn tại, 3–10 dòng | đạt (7 dòng) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt (5/5 commit) |
| Trailer `Prompt:` | 3/5 có (`1b97b24` B0-04, `c5bf22e` B0-01+FIX-001, `68cdebe` B0-03+FIX-002); hai commit docs thiếu → finding #9, không chặn |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA` | không |
| `uv.lock` sửa tay | không — diff đúng 2 dòng, là hệ quả của `urllib3` thêm vào `packages/storage/pyproject.toml` cùng nhánh, đúng khuôn `uv lock` sinh ra |
| `pragma: no cover` / `no branch` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | không có. Chỉ 2 `# noqa: S105` **có mã và có lý do** (khoá giả trong fixture/test) — hợp lệ theo K24 |

Không có điều kiện dừng sớm nào kích hoạt.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | RES-01 / R-16 | `_s3_errors` chỉ bắt `urllib3.exceptions.HTTPError` và `ServerError`. Đã **kiểm chứng trong container** (`minio 7.2.20`, `Minio._url_open`): `response_error = S3Error.fromxml(response) if response.data else None` — 5xx **có thân XML** (`SlowDown` 503, `InternalError` 500, `ServiceUnavailable`) sinh `S3Error`, không phải `ServerError`. Ngoài ra `urllib3.Retry(total=2)` có `status_forcelist` **rỗng** (đã in ra), nên 5xx cũng không được thử lại. Hệ quả: S3/MinIO tiết lưu hoặc lỗi máy chủ → `S3Error` thô lọt ra ngoài → API trả 500 `INTERNAL` thay vì 503 + `Retry-After`, trái với khẳng định của `changes/B0-04.md` ("lỗi phụ thuộc của **cả hai** bộ điều hợp → 503") | `packages/storage/s3.py:67-73` | Trong `_s3_errors`, bắt thêm `S3Error` có `exc.code` thuộc tập thử-lại-được (`SlowDown`, `InternalError`, `ServiceUnavailable`, `RequestTimeout`, `503 SlowDown`) hoặc `exc.response.status >= 500` → `DEPENDENCY_UNAVAILABLE`; giữ nguyên đường `AccessDenied`/`NoSuchBucket` nổi lên (test hiện có đã chốt đúng hành vi đó). Thêm test negative cho một `S3Error` 5xx |
| 2 | P2 | PERF-01 / R-20 | `_delete_under` xoá **từng** object bằng `remove_object` trong vòng lặp, trong khi `Minio.remove_objects` có sẵn (đã xác nhận `hasattr(Minio, "remove_objects") == True` ở minio 7.2.20) và gom 1000 khoá mỗi request `DeleteObjects`. Dọn rác một dự án 10 k object = 10 k lượt đi-về, giữ một luồng executor rất lâu. Đây là N+1 **không** nằm trong `DEBT.md` (NO-004 chỉ nói về `list_prefix`) | `packages/storage/s3.py:244-247` | Đổi sang `remove_objects(bucket, (DeleteObject(o.object_name) for o in ...))` và duyệt kết quả lỗi trả về (API này trả lỗi theo từng khoá, không ném) |
| 3 | P2 | PERF-01 | `resolve_kind` với `disposition="inline"` luôn gọi `storage.stat(key)` → **một `HEAD` S3 cho mỗi URL ký**. Lối tắt `kind` truyền sẵn chỉ mở cho khoá ảnh đại diện, trong khi khoá `…/pages/{i}.png` **cũng** do server sinh sau khi đã kiểm magic bytes (cùng lý lẽ K15). Một endpoint trả 50 thumbnail `inline` = 50 lượt `HEAD` trước khi trả lời | `packages/storage/port.py:140-146`, `packages/storage/keys.py:27-30` | Mở rộng `avatar_kind` thành `server_chosen_kind(key)` phủ cả `…/pages/{i}.png` (và artifact `runs/**` có đuôi do server chọn), giữ nguyên luật cấm cho `original.<đuôi>` của người dùng. **Nâng lên P1 nếu B0-06 ký URL `inline` theo danh sách** |
| 4 | P3 | LOG-04 / R-16 | `delete_prefix` của `LocalDiskStorage` dùng `shutil.rmtree(..., ignore_errors=True)`: xoá hỏng bị nuốt im lặng, hàm vẫn "thành công" trong khi object còn nguyên. Cùng hạng lỗi với NO-008 đang mở cho `tools/verify`, nhưng ở đây chưa có dòng nợ. `_disk_errors()` bọc quanh nó là mã chết vì `rmtree(ignore_errors=True)` không bao giờ ném | `packages/storage/local.py:156-160` | Bỏ `ignore_errors`, để `OSError` đi qua `_disk_errors` (ENOSPC/EROFS → 503, còn lại nổi lên); `FileNotFoundError` thì bỏ qua tường minh |
| 5 | P3 | PERF-06 / R-22 | `_list_under` ép `list_objects` (vốn là generator phân trang) thành `list` đầy đủ trong RAM trước khi `list_prefix` yield từng cái; `_keys_under` của bản local cũng `sorted(rglob("*"))` toàn cây. Tiền tố lớn nạp hết vào RAM, trái R-22. NO-004 chỉ ghi phần N+1, không ghi phần này | `packages/storage/s3.py:240-242`, `packages/storage/local.py:243-247` | Bơm theo lô qua `asyncio.Queue`, hoặc nhận `limit`/`continuation_token` và phân trang như W22 |
| 6 | P3 | RES-01 | Hai bộ điều hợp xử lý đĩa đầy khác nhau: `LocalDiskStorage` map `ENOSPC/EROFS/EDQUOT` → 503 qua `_disk_errors`, còn `S3Storage.put` cũng ghi đĩa (`SpooledTemporaryFile` tràn khỏi 16 MiB xuống `TMPDIR`) nhưng `OSError` ở `buffer.write` không được bọc → 500 | `packages/storage/s3.py:110-117` | Bọc vòng đệm bằng cùng một context manager lỗi đĩa (tách `_disk_errors` lên `port.py` để hai bộ điều hợp dùng chung — đúng R-07) |
| 7 | P3 | OBS-01 / LOG-04 | `ensure_bucket` bắt **mọi** `S3Error` của `PutBucketCors` rồi ghi `INFO "cors_managed_by_server"`. `AccessDenied` (khoá thiếu quyền `s3:PutBucketCORS`) hay `NoSuchBucket` do đó biến mất thành một dòng INFO, bucket production chạy tiếp với CORS sai | `packages/storage/s3.py:88-93` | Chỉ nuốt `exc.code == "NotImplemented"` (đúng hành vi MinIO đã đo); mã khác ghi `WARNING` kèm `code` hoặc ném lên |
| 8 | P3 | TEST-02 | `test_stat_uses_filesystem_time` so `datetime.now(UTC)` thật với cửa sổ 60 s (phụ thuộc đồng hồ thật, trôi nếu máy CI treo); `test_list_prefix_older_than` cũng trộn `datetime.now(UTC)` thật với `fake_clock` của `put`. Chạy được nhưng không tất định | `packages/storage/tests/test_local.py:171-177`, `packages/storage/tests/test_contract.py:136-141` | Lấy mốc từ `stat()` vừa đọc thay vì `now()`, hoặc chỉ khẳng định quan hệ thứ tự |
| 9 | P3 | MNT-05 / R-36 | Nhánh gộp việc của **ba** prompt: B0-04 (`1b97b24`), FIX-001 của B0-01 (`c5bf22e`), FIX-002 của B0-03 (`68cdebe`), cộng hai commit docs (`3cafe63`, `1478543`) **không có trailer `Prompt:`**. ~1 030 dòng mã nghiệp vụ + ~1 000 dòng test, vượt ngưỡng 400 dòng logic. `CLAUDE.md` nói người điều phối gộp bằng **squash** → một squash sẽ làm mất hai trong ba trailer `Prompt:` | toàn nhánh; `git log main..HEAD` | Gộp bằng **ba squash riêng** (một cho B0-04, một cho mỗi FIX) hoặc `merge --no-ff` để giữ trailer; hai commit docs nhận trailer `Prompt: điều-phối` khi viết lại |
| 10 | Nit | TEST-02 | `assert KEY not in signed.url` gợi ý token là mờ, nhưng thân token là base64url **không mã hoá** của `{"k":…}` — khoá giải ra được bằng một lệnh. (Bản thân thiết kế đúng BE-00 §8: token là bearer, chỉ cấm vào log.) | `packages/storage/tests/test_local.py:73` | Đổi thành khẳng định đúng ý: URL không chứa đường dẫn hệ thống tệp và không chứa khoá **dạng thô** |
| 11 | Nit | R-09 | `LocalDiskStorage.signed_url` gọi `resolve_kind(...)` rồi **vứt** giá trị trả về (chỉ dùng tác dụng phụ ném lỗi), trong khi docstring của `resolve_kind` nói "trả `kind` dùng cho `response-content-type`". Hệ quả thật: token local không mang `kind`, nên luật `inline` chỉ được kiểm **lúc ký**, B0-06 phải kiểm lại lúc phục vụ | `packages/storage/local.py:180` | Hoặc nhét `kind` đã giải vào thân token (và vào `FileGrant`), hoặc ghi rõ trong docstring `FileGrant` rằng B0-06 **phải** tự `stat` lại |
| 12 | Nit | MNT-04 | `_message` ghi chú "(BE-00 §8)" nhưng bản tin có **4** trường `k|e|d|n`, còn hiến chương ghi `object_key \| exp \| disposition`. Thực thi **chặt hơn** hiến chương (buộc cả tên tệp), đây là điểm cộng — chỉ chú thích lệch | `packages/storage/local.py:260-265` | Ghi rõ "§8 cộng trường `n`, buộc luôn tên tệp" |

**P0: 0 · P1: 0 · P2: 3 · P3: 6 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **Path traversal (SEC-07, K13):** `check_key` chặn rỗng, `.`/`..`, đoạn rỗng (`a//b`), đường tuyệt đối (`/a`), `\`, NUL, `\x7f`, > 1024 byte, và đuôi `.meta.json`; `check_prefix` buộc `/` cuối nên `projects/prj_A/` không chạm `projects/prj_AB/`. `test_every_entry_point_checks_the_key` chứng minh **cả bảy** điểm vào (`put`, `stat`, `open_read`, `delete`, `delete_prefix`, `list_prefix`, `signed_url`) đều kiểm — không có cửa sau. Hàm dựng khoá kiểm id theo `packages.core.ids`, không nối chuỗi người dùng.
- **Magic bytes (SEC-07, K14):** `kind` **luôn** tính từ 64 byte đầu, không bao giờ từ đuôi hay `Content-Type` khai; `test_put_ignores_declared_content_type` ghi PDF vào khoá `.png` và vẫn ra `kind="pdf"`. `as_kind` fail-closed về `unknown` cho metadata lạ → `inline` bị từ chối.
- **Luật URL ký (W23, K15, K16):** TTL 2 giờ tính từ `floor_to_hour` → đời thật 60–120 phút, test tham số hoá phút 0/5/59; URL ổn định trong cùng giờ và đổi sang giờ sau (test so cả `url` lẫn `expires_at`). `inline` chỉ cho PNG/JPEG đã kiểm magic bytes; `kind` truyền sẵn chỉ hợp lệ cho khoá ảnh đại diện đúng đuôi, có test cả hai chiều từ chối. URL local luôn đi `/api/files/{token}`, không bao giờ lộ đường dẫn tệp.
- **Token HMAC (SEC-10, SEC-15):** khoá con HKDF `file`, so bằng `hmac.compare_digest`, hỗ trợ `SECRET_KEY_PREVIOUS` và **từ chối** khoá đã thôi dùng (hai test đối xứng). Token giả, cắt cụt, sai base64, sai kiểu `e` (float/bool), `d` ngoài tập, hết hạn — tất cả ra 404 không lộ lý do. Bản tin `k|e|d|n` không mơ hồ vì ba trường đầu không chứa `|`.
- **Đồng thời (CON):** ghi qua file tạm tên ngẫu nhiên rồi `os.replace` — `test_concurrent_writes_never_produce_a_torn_object` chạy cho **cả hai** bộ điều hợp. Giới hạn đan metadata của bản local đã ghi NO-003 và ghi trong docstring module.
- **Chặn vòng sự kiện (R-23):** mọi thao tác đĩa và mọi lời gọi `minio` đồng bộ đều qua `asyncio.to_thread`. `presigned_get_object` gọi thẳng là **đúng**: đã xác minh `region` luôn được ghim (`s3_region` mặc định `us-east-1`) nên `Minio._get_region` không phát `GetBucketLocation` — test `test_signed_url_uses_the_public_endpoint_without_network` chốt điều này.
- **Timeout (RES-01, R-24):** `http_client()` đặt connect 3 s / read 15 s tường minh (thay mặc định 300 s của minio), `Retry(total=2, backoff_factor=0.2)`, `maxsize=10`; `allowed_methods` mặc định của urllib3 (đã in ra) đúng là tập idempotent nên chú thích trong mã chính xác.
- **413 không để lại rác (C12):** cả hai bộ điều hợp kiểm `max_bytes` **trước** khi chạm kho (local: file tạm bị xoá trong `finally`; S3: chưa gửi lượt nào), có test chung.
- **Không mock (K23):** `s3_storage` chạy trên MinIO thật; 503 được chứng minh bằng cách **dừng container thật** (`ephemeral_minio`) và bằng cổng bị từ chối, không bằng mock. `AccessDenied` và `NoSuchBucket` có test riêng để chắc chúng **không** bị biến thành 404/`None`.
- **Cấu hình fail-closed (OPS-02):** thiếu trường S3 → hỏng lúc nạp, không phải lúc ghi object đầu tiên; luật khác origin của BE-00 §8 được ép ở `staging`/`production`, có test cả hai chiều. `s3_secret_key` là `SecretStr`, không rò ra log.
- **Ranh giới import (R-28):** `lint-imports` đạt; `packages/storage` chỉ phụ thuộc `packages.core` + `minio`/`urllib3`, đúng dòng `| packages/storage | minio | core |` của BE-00 §2. Không có mã nghiệp vụ nào nhập `packages.testing`.
- **FIX-001 (`tools/verify/steps.py`)** sửa **gốc** đúng R-19: nguyên nhân là `rmtree` không gỡ được chính mount point, không phải "thư mục bẩn"; `exist_ok=True` là bản vá nhỏ nhất đúng chỗ, có test tái hiện hành vi mount point, và phần dư (`ignore_errors` nuốt lỗi) được tách ra thành NO-008 thay vì sửa mò.
- **FIX-002 (`packages/db/**`)** cũng đúng R-19: nguyên nhân đo được (chặng `host.docker.internal` kẹt 67,9 s **rồi thành công**, Postgres rảnh 6/100 kết nối) chứ không đoán; vá ở **mọi** đường đi (`engine.py`, `migrate_check.py`, `migrations/env.py`, `fixtures/db.py`) chứ không riêng test đỏ; tách hai trần (request 10 s hỏng nhanh, cổng 180 s chịu đựng) là lựa chọn đúng; phần dư ghi NO-007. `db_connect_timeout_s` có mặc định an toàn nên không phải breaking change.

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt — NO-001…NO-008, id tăng dần, không xoá dòng nào |
| Nợ P0/P1 không còn `⬜`/`🔧` | đạt — không có P0; P1 duy nhất (NO-002) đã `✅` kèm FIX-002 và bằng chứng 10/10 lượt xanh |
| Dòng `➖` có lý do đứng được | đạt cả ba, và **đã kiểm chứng**: NO-003 (giới hạn chỉ ảnh hưởng kho dev, đã ghi trong docstring `local.py`); NO-004 (N+1 chỉ lịch dọn rác gọi, có đường nâng cấp + số dòng); NO-005 (**xác nhận trong container**: `hasattr(Minio, "set_bucket_cors") == False` ở minio 7.2.20 — lý do dùng `_execute` là thật, không phải cớ) |
| Nợ do review này chỉ ra đã có dòng | **chưa** — finding #1…#8 chưa có `NO-<nnn>` nào. R-38 buộc ghi **trước** khi merge |

## Điểm

| Miền | Trọng số | Điểm | Tích | Lý do |
|---|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 | Không finding. Traversal, magic bytes, HMAC constant-time, xoay khoá, fail-closed, khác origin — đều có mã và test |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 | Chỉ P3 (giới hạn metadata local, đã nhận NO-003); có test ghi song song cho cả hai bộ điều hợp |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 | Chỉ P3 (#4, #7 nuốt lỗi); case biên phủ rất kỹ (rỗng, cụt, Unicode NFD, trần, âm) |
| PERF – Hiệu năng | 10 % | 3 | 0,30 | P2 #2, #3 (+ P3 #5, + NO-004 đã nhận) |
| RES – Chịu lỗi | 10 % | 3 | 0,30 | P2 #1 (5xx có thân → 500 thay vì 503), P3 #6; bù lại timeout tường minh đầy đủ |
| DB, API – Migration & contract | 10 % | 5 | 0,50 | Không migration, không đổi hợp đồng FE; `db_connect_timeout_s` có mặc định an toàn, tương thích ngược |
| TEST – Kiểm thử | 7 % | 4 | 0,28 | Chỉ P3/Nit (#8, #10). Dịch vụ thật, negative case dày, test đồng thời, test xoay khoá, tham số hoá hai bộ điều hợp |
| OBS, OPS – Vận hành | 5 % | 3 | 0,15 | P2 NO-006 (chưa nơi nào khai `STORAGE_*`/`S3_*`) — đã có dòng nợ và giao đúng chủ B0-08 |
| MNT – Bảo trì | 3 % | 3 | 0,09 | P2 #9 (nhánh gộp ba prompt, > 400 dòng logic) |
| **Tổng** | **100 %** | | **4,07** | |

## PHÁN QUYẾT: APPROVE WITH COMMENTS

Mã nghiệp vụ đạt chuẩn: cổng thoát 0 thật, độ phủ vượt xa sàn (99,62 % dòng / 98,21 % nhánh cho `packages/storage`), và **ba** điểm khó nhất của prompt này — chống path traversal ở mọi điểm vào, nhận loại tệp bằng magic bytes thay vì đuôi, và luật URL ký làm tròn đầu giờ với `inline` chỉ cho ảnh đã kiểm — đều có mã đúng **và** test chứng minh, chạy trên MinIO thật chứ không mock. Không có P0, không có P1, nên không có gì **chặn** merge. Điểm 4,07 nằm ngay mép `APPROVE`, nhưng ba finding P2 mới do phiên này phát hiện (#1, #2, #3) chưa có dòng nào trong `DEBT.md`, mà `RULE-CODE.md` R-38 buộc nợ do review chỉ ra phải được ghi **trước** khi merge — vì vậy là `APPROVE WITH COMMENTS` chứ không phải `APPROVE` trơn.

**Điều kiện để được merge (chỉ sửa tài liệu, không cần đụng mã):**

1. Thêm dòng `DEBT.md` cho finding #1 (P2, chủ B0-04), #2 (P2, chủ B0-04), #3 (P2, chủ B0-04) và #4…#8 (P3, chủ B0-04), mỗi dòng đủ: nợ là gì, nguyên nhân gốc, chủ, mức, trạng thái `⬜`. Finding #3 ghi kèm điều kiện nâng cấp thành P1 (khi B0-06 ký URL `inline` theo danh sách).
2. Gộp vào `main` theo cách **giữ được cả ba trailer `Prompt:`** — ba lần squash riêng (B0-04, FIX-001, FIX-002) hoặc `merge --no-ff`. Một squash chung sẽ xoá dấu vết chủ sở hữu của hai FIX.

**Ranh giới sở hữu (BE-00 §2, K27) — ghi nhận và đánh giá:** nhánh chạm ba vùng ngoài quyền của B0-04:
`tools/verify/steps.py` + `tools/tests/test_steps_commands.py` (chủ B0-01, mà `CLAUDE.md` còn ghi rõ "không prompt nào khác B0-01 sửa"),
`packages/db/**` + `packages/testing/fixtures/db.py` (chủ B0-03),
và `CLAUDE.md`, `RULE-CODE.md`, `DEBT.md`, `.claude/skills/merge-review/` (người điều phối).
Người điều phối đã cho phép trong phiên này, nên **chấp nhận được** — và chấp nhận được vì cách làm đúng: mỗi FIX đi trong commit riêng, mang trailer `Prompt:` của **đúng prompt chủ** (không phải B0-04) cộng `Fix: FIX-00n`, sửa tối thiểu đúng nguyên nhân gốc, có test chặn tái phát, và phần dư chưa xử được ghi thành nợ mở đúng chủ (NO-007, NO-008). Đây là khuôn mẫu đúng cho FIX liên prompt. Điều **không** chấp nhận được nếu lặp lại: gói chúng vào cùng một nhánh tính năng rồi squash một lần (finding #9) — lần sau tách nhánh `fix/b0-01-…`, `fix/b0-03-…` riêng.
