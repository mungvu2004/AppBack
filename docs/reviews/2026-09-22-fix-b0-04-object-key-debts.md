# Review merge fix/b0-04-object-key-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo `W7-KEYS.report.md` đều tự kiểm lại) · Commit đầu nhánh: `9b35caeb51e6`. Nhánh có 7 commit: `f6fb907` FIX-043 (B0-02), `59e9e32` FIX-044 (B0-04), `4aad113` FIX-045 (B5-01), `09e4b21` FIX-046 (B0-04), `1bd891b` FIX-047 (B0-04), commit gộp `main` `c10bad0` (cha `1bd891b`, `5f39fb2`) và `9b35cae` ghi NO-076/NO-077. Merge-base = `5f39fb2`; phạm vi = `git diff main...HEAD` (8 file: `DEBT.md`, `packages/core/{object_keys.py, tests/test_object_keys.py}`, `packages/storage/{keys.py, tests/test_keys.py, tests/test_s3.py}`, `packages/ml_contracts/{payloads.py, tests/test_payloads.py}`; +242/−145 dòng). **`main` đã đi thêm** tới `f5cc758` (gộp `fix/b0-05-quiet-release-case-filter`) sau khi tác giả gộp — xem điều kiện merge 2.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, lấy từ `RUN_SH_EXIT` của chính shell bọc (không bị cắt; lượt chạy 11:06:45–11:13:47 trên `9b35caeb51e6`; ngay trước đó `docker ps -q --filter name=verify-run | wc -l` = 1). Log: `verify.log` trong scratchpad của phiên review. Bước 5: **2033 passed, 0 failed, 10 skipped**, 1 deselected, 346,5 s; cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng — chưa có route được bảo vệ nào), đúng ngoại lệ BE-00 §12, file y hệt `main`.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,31 %** · nhánh **97,25 %**
  - `packages/core`: dòng **100,00 %** · nhánh **100,00 %** · `packages/ml_contracts`: **99,90 %** · **99,57 %** · `packages/storage`: **99,64 %** · **98,33 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**
  - Probe P2 (chạy riêng ba module bị sửa): `object_keys.py` 28 lệnh/14 nhánh, `keys.py` 74/24, `payloads.py` 204/62 — **100 %** dòng và nhánh. Không dòng nào rơi vào sai số NO-035 (ba module không đi qua SQLAlchemy).

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (322 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (281 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken — gồm `packages.core không nhập gói nội bộ khác…` KEPT) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf 1 passed; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5; ba cảnh báo route hạ tầng sẵn có) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu phiên và cuối phiên) |
| `changes/B0-02.md`, `changes/B0-04.md`, `changes/B5-01.md` tồn tại | đạt (có từ các prompt gốc; FIX không bắt buộc sửa mảnh) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 7 commit, dài nhất 69 ký tự (`refactor`/`fix`/`test`/`chore`/`docs` đúng loại theo đoạn giao việc đợt 2) |
| Trailer đọc được (R-36b) | đạt — `%(trailers:key=Prompt,valueonly)` ra `B0-02`, `B0-04`, `B5-01`, `B0-04`, `B0-04`, `B0-04`, `B0-04`; năm commit FIX ra đúng `Fix: FIX-043` … `FIX-047`; commit gộp và commit sổ không `Fix:` |
| Dòng `DEBT.md` đổi trong **chính** commit sửa | đạt — NO-060 `✅` trong `4aad113` (FIX cuối của bộ ba 043..045), NO-073 trong `09e4b21`, NO-072 trong `1bd891b` |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không |
| `pragma` / `type: ignore` / `noqa` / `skip` / `xfail` mới / hạ ngưỡng | không (grep trên diff: 0) |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không (`packages/core/object_keys.py` chỉ nhập `re`, `typing`; BE-00 §13.1 giữ nguyên) |
| File ngoài phạm vi [4] của FIX-043..047 | chỉ `DEBT.md` (luật của đoạn giao việc: dòng nợ đổi trong commit sửa; NO-076/077 do người điều phối cấp id) |
| Nhánh > 400 dòng logic (MNT-05) | không — +242/−145 gồm test và `DEBT.md` |

Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (`run.sh shell < probe.sh`, bản sao `/tmp/w`; file của commit cũ nhúng trong script dạng base64 nên **không có gì ghi vào worktree**, kể cả `.cache/`). Hai lượt probe, mỗi lượt đều đếm `verify-run` < 2 trước khi chạy.

- **P1 — đỏ trước / xanh sau từng FIX** (test của commit FIX chạy trên mã của commit cha, rồi trên mã của nhánh):

  | FIX | Test chặn tái phát | Trước | Sau | Khớp dòng `DEBT.md`? |
  |---|---|---|---|---|
  | 043 | `packages/core/tests/test_object_keys.py` (36 ca) | module chưa có → `ModuleNotFoundError: No module named 'packages.core.object_keys'`, exit ≠ 0 | 36 passed | ✓ — "đỏ: module chưa có → xanh 36 passed". (Probe của tôi xoá module trên cây HEAD nên lỗi nổ ở plugin `packages.testing.fixtures.api` — nó nhập `storage.keys` đã trỏ về lõi — exit 1; trên cây cha thật chỉ file test hỏng khi thu thập. Đỏ tất yếu của module mới; bằng chứng có nghĩa là FIX-044/045.) |
  | 044 | `test_key_rules_come_from_core` (`test_keys.py` @ `59e9e32` trên `keys.py` @ `main`) | **1 failed, 27 passed** — `assert <function check_key …> is <function check_key …>` | 28 passed | ✓ — "đỏ trên FIX-043: 1 failed → xanh" |
  | 045 | `test_object_key_rules_come_from_core` (`test_payloads.py` @ HEAD trên `payloads.py` @ `main`) | **1 failed, 88 passed** — validator của `ObjectKey` là `check_object_key`, không phải `check_key` | 89 passed | ✓ |
  | 046 | `test_server_chosen_kind_only_for_keys_the_server_names[…/pages/007.png]`, `test_server_chosen_kind_reads_id_rules_of_core[is_spatial_id, is_id]` (`test_keys.py` @ HEAD trên `keys.py` @ `59e9e32`) | **3 failed, 37 passed** — `'png' == None`, `'png' is None` ×2 | 40 passed | ✓ — "đỏ 3 failed → xanh 40 passed" |
  | 047 | `test_delete_prefix_deletes_in_batches` (`s3.py` HEAD với `_delete_under` thay bằng vòng `remove_object` của bản trước FIX-012) | **1 failed** — `assert 1001 == 0` (1001 `DELETE`) | 1 passed ×2 lượt (14,8 s · 12,9 s) trên MinIO thật | ✓ — nguyên văn `assert 1001 == 0` |

  Sau mỗi lượt, cây `/tmp/w` được `cmp` lại với bản HEAD (4/4 khớp) trước khi chạy probe Python.
- **P2 — độ phủ riêng ba module:** số liệu ở đầu file.
- **P3 — hệ quả của `…/pages/007.png` với `signed_url(inline)`:** `port.resolve_kind(_, k007, "inline", "png")` — HEAD: `ValueError: kind='png' chỉ hợp lệ cho khoá do server đặt tên, đúng đuôi: …/pages/007.png`; trước FIX-046: `'png'`. Không truyền `kind` → vẫn đi nhánh `stat` (một lượt đọc metadata / `HEAD`). `upload_page(…, 0|7|10)` sinh `0.png`, `7.png`, `10.png`.
- **P4 — `server_chosen_kind` cũ (regex) và mới (hàm dựng) trên 206 492 khoá** (bảng tổ hợp id đúng/sai/biên × tên trang/ảnh đại diện, cộng 300 000 đột biến 1–3 ký tự của hai khoá chuẩn, seed cố định): 6 213 khoá cả hai cùng nhận; lệch **đúng hai nhóm**: 12 khoá tên trang có số 0 đứng đầu (`007.png`, `00.png`) và 15 khoá dài hơn 1024 byte (chỉ số trang rất dài) — cũ nhận `png`, mới `None`. **Không có lệch nào khác.** Khoá trang đã nắn của B2-04 `pages/{i}-{ULID}.png`: cũ `None`, mới `None`.
- **P5 — chi phí mỗi lượt `server_chosen_kind`:** khoá trang 0,75 → **12,0 µs**, ảnh đại diện 0,69 → 2,78 µs, khoá khác 0,23 → 0,15 µs (xem Nit #3).
- **P6 — tương đương luật khoá trên 154 142 mẫu** (chuỗi ngẫu nhiên từ `a Z 0 . - _ / \ ␠ \x00 \x7f é o+◌́ ó .. \n`, trần 1023/1024/1025 byte ASCII và 511/512/513 `é`, đuôi `.meta.json`): `core.check_key` so với `check_key` cũ của `storage` — lệch đạt/không **0**, lệch thông báo **0**; so với `check_object_key` cũ của `ml_contracts` — lệch đạt/không **0**; `check_prefix` so với bản cũ của `storage` (cả thông báo) và `_prefix_key` cũ — **0**; `is_segment` so với `_name` cũ — **0**.
- **P7 — mẫu biên cũ có mặt ở `packages/core/tests`:** 12 bad + 3 good + 3 tiền tố của `storage/tests/test_keys.py` @ `main` và 12 `KEY_SAMPLES` của `ml_contracts` @ `main` — **thiếu 0**, phân loại đạt/không trùng. Core có 19 bad, 5 good, 4 tiền tố, 1 tiền tố đúng, 7 `is_segment` = 36 ca. Mẫu `khóa`: test core có cả NFD (`kho\xcc\x81a`) lẫn NFC (`kh\xc3\xb3a`); mẫu cũ của `ml_contracts` là **NFC** — tác giả nói đúng.
- **P8 — AST 7 file `.py` của diff:** không hàm nào > 50 dòng; hàm **mới** thiếu docstring duy nhất là `test_check_prefix_accepts_valid_prefix` (Nit #2); các hàm thiếu docstring khác trong `test_payloads.py`, `test_keys.py`, `test_s3.py` có từ trước, diff không chạm.
- **P9 — hợp nhất với `main` hiện tại:** `git merge-tree --write-tree f5cc758 HEAD` → **xung đột duy nhất ở `DEBT.md`** (dòng kề nhau: nhánh sửa NO-073, `main` sửa NO-074; `main` còn sửa NO-067). File mã của `5f39fb2..f5cc758` (`apps/ml/runtime/gpu.py`, `packages/messaging/locks.py`, test của chúng, `tools/tests/test_case_gate.py`) rời hẳn file mã của nhánh.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-06 · API-04 | FIX-043 lập một **thành phần dùng chung mới** ở lõi (`check_key`, `check_prefix`, `is_segment`, `MAX_KEY_BYTES`, `META_SUFFIX` — gọi từ `storage` và `ml_contracts`), nhưng bảng "Thành phần dùng chung → chủ" của hiến chương không có dòng nào cho nó (`grep object_keys\|check_key docs/charter/BE-00.md` rỗng). R-06 bảo prompt sau tìm hàm dùng chung theo đúng bảng này; prompt chưa chạy vẫn tự chép luật: `B2-04.md:128` (lịch `purge_upload_orphans`) viết tay regex `^projects/prj_[0-9A-HJKMNP-TV-Z]{26}/floors/L-[0-9A-Z]{10,64}/uploads/upl_…/` — bản chép thứ ba của đúng luật id tầng mà NO-073 vừa gỡ. Nhánh không được sửa hiến chương/prompt (chủ: người điều phối), nên đây là nợ, không chặn | `docs/charter/BE-00.md:100-125` (§2.2); `F:/AppBack/backend/prompts/B2-04.md:128` | Thêm dòng §2.2: "Luật khoá object (`check_key`, `check_prefix`, `is_segment`, `MAX_KEY_BYTES`, `META_SUFFIX`) \| `packages/core/object_keys.py` \| B0-02 · gọi: B0-04, B5-01". Sửa B2-04 [6] cho lịch dọn lọc khoá bằng một hàm của `packages.storage.keys` (tách đoạn rồi hỏi `is_id`/`is_spatial_id` như `server_chosen_kind`) thay cho regex. Ghi `DEBT.md` (dòng đề xuất ở dưới) |
| 2 | Nit | R-01 | Hàm test mới duy nhất không có docstring (P8) | `packages/core/tests/test_object_keys.py:64` | Một dòng, vd "Tiền tố hợp lệ trả lại chính nó." |
| 3 | Nit | PERF-05 | `server_chosen_kind` giờ dựng lại khoá qua `upload_prefix` → `project_prefix` → `check_prefix`/`check_key` ba lần cộng regex id: **16×** chậm hơn với khoá trang (0,75 → 12,0 µs, P5), 4× với ảnh đại diện. Tuyệt đối vẫn nhỏ (1 000 thumbnail ≈ 12 ms CPU trên vòng sự kiện, rẻ hơn nhiều một `HEAD` mà `kind` giúp tránh) và **chưa có người gọi sản phẩm nào truyền `kind`** (`grep "signed_url(" apps packages`: chỉ test) | `packages/storage/keys.py:124-137` | Chấp nhận. Khi một endpoint ký hàng trăm ảnh trang kèm `kind`, ghi ngưỡng theo R-05 trong docstring hoặc so tiền tố `upload_prefix(…)` một lần rồi chỉ kiểm tên trang |
| 4 | Nit | TEST-02 | `test_delete_prefix_deletes_in_batches` mất **12,9–14,8 s** mỗi lượt khi máy tải cao (tác giả đo 6,3–12,4 s) vì cả 1001 lượt `PUT` gieo dữ liệu đều đi qua proxy Python (`ThreadingHTTPServer` chuyển tiếp từng request), trong khi test chỉ cần đếm request của **lượt xoá** | `packages/storage/tests/test_s3.py:191-205` | Gieo 1001 object bằng client thẳng tới MinIO (`client_for(endpoint, …)` của fixture `minio_endpoint`, cùng bucket), chỉ `delete_prefix` đi qua `proxied`; mọi assert giữ nguyên |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **Một nguồn cho luật khoá (NO-060, R-07):** `packages/core/object_keys.py` giữ đúng luật cũ của `storage` (rỗng → trần byte UTF-8 → đuôi `.meta.json` → từng đoạn: đoạn chấm trước, ký tự sau), thông báo y hệt bản `storage` (P6: 0 lệch trên 154 142 mẫu); `ml_contracts` nhập thẳng, xoá `check_object_key`, `_prefix_key`, `MAX_KEY_BYTES`, `_META_SUFFIX`, `_SEGMENT_RE`; `storage.keys` xoá bản riêng. `is_segment` công khai là cần: `_name` của `storage` và vòng đoạn của `check_key` dùng chung một luật, không sinh bản chép thứ ba. `from … import X as X` là cách xuất lại tường minh mà `mypy --strict` (`no_implicit_reexport`) đòi.
- **Ranh giới import:** `object_keys.py` chỉ nhập `re`, `typing`; hợp đồng `core-isolated` KEPT; `ml_contracts` vẫn không nhập `packages.storage` (test cũ `from packages.storage.keys import check_key` trong `test_payloads.py` cũng đã gỡ).
- **Người gọi API bị đổi (grep sau khi gộp `main`, cả `apps/**` của B0-06, B0-07, B1-01, B3-01, B5-01):** `storage.keys` vẫn xuất `check_key`, `check_prefix`, `META_SUFFIX`, `server_chosen_kind` cho `local.py:33`, `s3.py:30`, `port.py:21`, `apps/api/health/tests/test_health.py:115`; `MAX_KEY_BYTES` (thôi xuất ở `storage.keys`, `payloads`) và `check_object_key` không còn ai nhập — kể cả trong `backend/prompts/*.md`. Thông báo `ValueError` mới của `ml_contracts`: không test nào khớp chuỗi cũ (`main:test_payloads.py` không có `match=` cho khoá; `grep "sai luật\|khoá object rỗng"` trên `main` chỉ ra chính `payloads.py`), còn `define_task` coi mọi `ValidationError` là thông điệp độc (J08) bất kể nội dung.
- **FIX-046 (NO-073):** `server_chosen_kind` tách khoá theo `/` bằng `match` và hỏi chính `avatar`/`upload_page`; nhánh ảnh đại diện không so lại khoá nhưng dựng lại từng byte vì `name.partition(".")` rồi ghép lại đúng `{ulid}.{ext}` (P4 xác nhận), nhánh trang so khoá dựng lại với khoá vào (chặn `007`, chữ số Unicode, `0` không đuôi). `except ValueError → None` chỉ nuốt tín hiệu "hàm dựng từ chối" (cả `int()` của chuỗi > 4 300 chữ số), đã ghi trong docstring — không phải R-16. Test đột biến (`monkeypatch keys.is_spatial_id/is_id → False`) đỏ trên bản regex, xanh trên bản mới (P1), đúng lối "đột biến luật" spec [6] cho phép khi hai luật trùng khít; test biên id tầng dài 10/64 đạt, 9/65 không, có thêm 6 khoá âm (không đuôi, `.png.png`, `prj_lowercase`, `library/…`).
- **FIX-047 (NO-072):** 1001 ảnh trang, `Semaphore(8)` dưới `maxsize=10` của pool (`s3.py:71`), `TaskGroup` nên lỗi ghi nào cũng nổi lên; khẳng định 0 `DELETE`, **đúng 2** `POST ?delete`, 2 `POST` tổng, tiền tố rỗng — bản xoá từng object đỏ `1001 == 0` (P1); vì khẳng định **đúng** 2 lượt nên cỡ lô khác 1000 (một lô cho cả 1001 khoá, hay lô nhỏ hơn) cũng làm test đỏ. `FaultProxy` là `ThreadingHTTPServer`, ghi `requests` trong khoá (`fault_proxy.py:67-71`).
- **Test:** dịch vụ thật (MinIO qua proxy tiêm lỗi), không mock; không phụ thuộc thời gian thật; seed đột biến và mẫu biên đều tất định.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | FIX-046 hỏi thẳng hàm dựng thay vì tự kiểm từng đoạn bằng `is_id`/`is_spatial_id`; hệ quả hẹp hơn: `…/pages/007.png` không còn là khoá do server đặt | **Đứng được.** (i) **Không người ghi nào sinh số trang có số 0 đầu:** hàm dựng duy nhất là `upload_page` (`f"{index}.png"`, P3); `grep "pages/"` trong `apps/`, `packages/` (trừ test) chỉ ra `keys.py:78`; spec B2-04 buộc `pages/{i}.png` đi qua `keys.upload_page` (`B2-04.md:75`), và K13 cấm nối khoá thẳng. Trang đã nắn `pages/{i}-{ULID}.png` của B2-04 không phải khoá server đặt ở **cả** bản cũ lẫn bản mới (P4) và B2-04 ký nó `attachment` không `kind` (`B2-04.md:120`), nên không đổi gì. (ii) **Hệ quả cho `signed_url(inline)`:** truyền `kind` với khoá `007` → **bị từ chối** (`ValueError` của `resolve_kind`, lỗi lập trình, không phải 4xx), không chỉ tốn thêm `HEAD`; không truyền `kind` → một lượt `stat`/`HEAD` như mọi khoá khác. Hôm nay không người gọi sản phẩm nào truyền `kind`. (iii) Ngoài `007`, bản mới còn chặt hơn ở khoá > 1024 byte (P4) — khoá không bao giờ ghi được (`put` chạy `check_key`) |
| 2 | FIX-044 dồn ca luật khoá của `storage` về `packages/core/tests`, thêm `is_segment` công khai, thôi xuất `MAX_KEY_BYTES` ở `storage.keys`/`payloads` | **Đứng được.** P7: 18 ca của `storage` + 12 mẫu của `ml_contracts` có đủ, không mất ca biên nào; P6: hành vi và thông báo không đổi; `object_keys.py` 100 % dòng/nhánh (P2). Không ai nhập `MAX_KEY_BYTES` từ hai chỗ cũ |
| 3 | Dòng NO-060 ghi mẫu `khóa` là NFD, thực ra NFC; test lõi có cả hai | **Đúng** (P7, byte `c3 b3`); dòng `✅` của NO-060 ghi rõ điều này |
| 4 | Đếm-rồi-chạy của trần 2 container có khe tranh chấp | **Đúng** — phiên này thấy 3 `verify-run` cùng lúc lúc 11:07 (lượt của tôi khởi động khi đếm = 1, một worker khác khởi động cùng lúc). Việc của người điều phối (khoá chung quanh `run.sh`), không phải của nhánh |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng nói đúng sự thật | đạt — NO-060, NO-072, NO-073 `✅` kèm ngày đóng và mã FIX; mọi số đỏ/xanh trong ba dòng khớp P1 (1 failed/27 · 1 failed/88 · 3 failed/37 → 40 passed · `assert 1001 == 0`), số ca 36 khớp P7 |
| Mọi nợ tác giả nêu đều có dòng | đạt — NO-076 (`keys.py:26` `_ULID_RE` chép `ids.py:35` `_ULID_BODY`) và NO-077 (`payloads.py:115` `_upload_prefix` dựng lại `keys.py:64` `upload_prefix`) `⬜` P3, cả bốn vị trí đã kiểm đúng dòng |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh sinh | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — xem dưới |

Dòng đề xuất (người điều phối cấp id; phiên này **không** tự ghi vào `DEBT.md`):

- `| ⬜ | NO-<nnn> | 2026-09-22 | | BE-00 §2.2 "Thành phần dùng chung → chủ" chưa có dòng cho luật khoá object ở `packages/core/object_keys.py` (`check_key`, `check_prefix`, `is_segment`, `MAX_KEY_BYTES`, `META_SUFFIX`) mà FIX-043 dời xuống lõi; `prompts/B2-04.md:128` (lịch `purge_upload_orphans`) còn tự viết regex bố cục + id của khoá lượt tải lên | Hiến chương và prompt viết trước FIX-043 | người điều phối (`docs/charter/BE-00.md`, `prompts/B2-04.md`) | P3 | mở — review merge 2026-09-22 `fix/b0-04-object-key-debts` finding #1; cùng họ NO-073, NO-076, NO-077. Chữa: thêm dòng §2.2 "Luật khoá object … \| packages/core/object_keys.py \| B0-02 · gọi: B0-04, B5-01"; B2-04 [6] lọc khoá bằng hàm của `packages.storage.keys` thay regex |`
- Nit #2–#4: tác giả tự quyết, không cần dòng nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 (Nit #3) | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #2, #4) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #1) | 0,12 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,12 = **4,97 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập (2033 passed, 0 failed), độ phủ 100 % dòng và nhánh ở tập file bị chạm và ở cả ba module sửa, không P0/P1/P2, điểm 4,97 ≥ 4,0. Năm FIX sửa đúng gốc chứ không vá triệu chứng: luật khoá có **một** nguồn ở lõi và cả hai gói cùng gọi (tương đương từng thông báo với bản cũ trên 154 142 mẫu, đủ 30 mẫu biên cũ), `server_chosen_kind` đọc luật id và bố cục từ chính hàm dựng (lệch với regex cũ chỉ ở hai nhóm khoá không người ghi nào sinh ra, trên 206 492 mẫu), test xoá lô chạm thật biên 1000 khoá. Mỗi FIX đỏ trước/xanh sau đã tự tái hiện đúng con số ghi trong `DEBT.md`. Hai lệch tác giả tự nêu đứng được: `pages/007.png` không có người ghi (với `kind` thì bị từ chối bằng `ValueError`, không chỉ tốn thêm `HEAD` — không người gọi sản phẩm nào truyền `kind`), và test dồn về lõi không mất ca nào.

Điều kiện cho phiên merge:

1. **Trước khi merge** (R-38): ghi dòng `NO-<nnn>` ở trên cho finding #1 (P3, chủ người điều phối). Nit #2–#4 không chặn.
2. `main` đã ở `f5cc758`: `git merge --no-ff fix/b0-04-object-key-debts` sẽ **xung đột ở `DEBT.md`** (P9 — dòng NO-073 của nhánh kề NO-074 của `main`). Giải bằng tay, giữ cả hai phía: của nhánh NO-060/NO-072/NO-073 `✅` + NO-076/NO-077 `⬜`; của `main` NO-067/NO-074 `✅`. Không file mã nào chồng nhau; chạy verify tích hợp trên `main` sau khi gộp như thường lệ.
3. Gộp bằng `--no-ff` (R-36: trailer của **ba** prompt B0-02, B0-04, B5-01 + `Fix: FIX-043…047`), **không** squash.
4. Điền sha vào cột "Commit" của `docs/fixes.md`: FIX-043 `f6fb907`, FIX-044 `59e9e32`, FIX-045 `4aad113`, FIX-046 `09e4b21`, FIX-047 `1bd891b` (`--no-ff` giữ nguyên các sha này).
