# Review merge feature/b1-04-profile-password-avatar → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `b875db45fdd2`
- Base: `main` `e59f44f` · một commit · 15 file / 1783 dòng thêm, trọn trong whitelist B1-04
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong worktree review, không dùng lại log tác giả)
- Độ phủ (`tools/coverage_gate` thật): tổng dòng 99,03% · nhánh 97,63%; `apps/api/me` dòng 97,15% · nhánh 100,00%
- Loại task (RULE.md §6): **Auth, phân quyền, PII** — đổi mật khẩu, thu hồi phiên, ảnh có EXIF/GPS

## 1. Bảng cổng (E.10, mã thoát thật của phiên review)

| # | Bước | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 3512 passed · 0 failed · 0 skipped · 4 deselected (606 s) |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; `case_gate` 20 thao tác đã mount |
| 6 | `lint_migrations` → `migrate_check` | đạt | 7 revision, không revision mới |
| 7 | H1 H3 H4 H5 | đạt | H1 596 mẫu response; H4 `không áp dụng` (B3-05 chưa hợp nhất — đúng luật BE-00 §12, không liên quan B1-04) |
| 8 | `openapi` | đạt | ghi `/tmp/openapi.json`, 47567 byte |

`case_gate` bốn op mới đều `đạt` (`me_read_profile`, `me_update_profile`, `me_change_password`, `me_replace_avatar`),
`test_purge_avatars__J01`/`__J06` có mặt. **Mọi con số tác giả báo đều khớp với lần chạy độc lập này** (sai lệch duy
nhất là tổng độ phủ 99,02% ↔ 99,03%, mức làm tròn).

Điều kiện dừng sớm của skill: cây sạch ✓ · `changes/B1-04.md` có ✓ · dòng đầu commit đúng Conventional Commits và có
trailer `Prompt: B1-04` ✓ · không đụng file cấm ✓ · không `pragma: no cover`, không `type: ignore` trần, không
`skip`/`xfail` mới, không hạ ngưỡng ✓. Không có điều kiện REJECT sớm nào.

## 2. Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-02 | `language: null` tường minh → 500 `INTERNAL` | `apps/api/me/schemas.py:47`, `apps/api/me/router.py:115-122` | Từ chối `null` bằng `field_validator` như đã làm cho `fullName` → 422 `field:"language"` |
| 2 | **P2** | LOG-06 | PNG mã hoá lại **vẫn mang ICC profile** của ảnh gốc, trái đặc tả bước 5 và trái docstring của chính module | `apps/api/me/avatar.py:198-204` | `final.info.pop("icc_profile", None)` (và `"exif"`) trước `save`, hoặc truyền `icc_profile=None, exif=None` |
| 3 | **P2** | TEST-03 | Thiếu 4 test nghiệm thu mà khối [8] của prompt liệt kê tên | `apps/api/me/tests/` | Bổ sung: storage dừng → 503 + `avatar_key` không đổi; `Idempotency-Key` lặp → một object; PNG 4096×4096 16-bit; N13 DB dừng → 503 |
| 4 | P3 | MNT-03 / R-07 | Bản sao nguyên văn của `_BIDI_OVERRIDE` + kiểm Cc/bidi | `apps/api/me/schemas.py:22,25-27` ↔ `apps/api/auth_recovery/router.py:64-73` | Nợ cho **B0-02**: đưa hàm chung vào `packages/core/text.py` (đã là nhà của `nfc`) |
| 5 | P3 | R-06 | `_new_ulid` gọi `new_id("tpl", clock)` rồi cắt tiền tố vì không có hàm sinh ULID trần công khai | `apps/api/me/router.py:252-258` | Nợ cho **B0-02**: thêm `ids.new_ulid(clock) -> str`, `new_id` gọi lại nó |
| 6 | Nit | CON-06 | Ghi biến toàn cục tiến trình `ImageFile.LOAD_TRUNCATED_IMAGES` từ luồng phụ mỗi request | `apps/api/me/avatar.py:189` | Đổi thành `assert`/kiểm lúc nhập module |
| 7 | Nit | MNT-04 | `# type: ignore[misc]` / `[index]` có mã nhưng không có lý do (CLAUDE.md đòi cả hai) | `apps/api/me/router.py:74,165` | Thêm nửa câu lý do |
| — | (ghi nhận, bỏ qua) | MNT-05 | 726 dòng logic (> 400) | `apps/api/me/*.py` | **Không đáng tách**: 4 route + 1 lịch của đúng một module, prompt định nghĩa đây là một đơn vị bàn giao |

### [P1][LOG-02] `PATCH /api/me` với `language: null` → 500

📍 `apps/api/me/schemas.py:47` (`language: Literal["vi", "en"] | None = None`) → `apps/api/me/router.py:115-122`
(`_profile_values`).

🔍 **Bằng chứng** (tự chạy, không suy diễn):
- `UpdateMeBody.model_validate({"language": None})` hợp lệ — không `field_validator` nào chặn `None`;
  `model_fields_set = {'language'}` nên qua được `_at_least_one_key`; `_profile_values` trả
  `{'language': None}` → `UPDATE users SET language = NULL`.
- `users.language` là `nullable=False` (`packages/db/migrations/versions/r20260921_b1_01_auth.py:55`;
  `packages/db/models/auth.py:63` `Mapped[str]`).
- SQLSTATE `23502` không nằm trong danh sách nào của `translate_db_error`
  (`packages/db/errors.py:59-70`) → trả `None` → bộ xử lý chung trả 500 `INTERNAL`.
- **Chạy thật** (probe tạm, đã xoá): `PATCH /api/me {"language": null}` →
  `500 {"code": "INTERNAL", "requestId": "…"}`.

💥 **Tác động:** bất kỳ người dùng đã đăng nhập nào cũng ép được 500 trên một endpoint PII bằng một thân hợp lệ về
cú pháp. Trái BE-00 §5 (input của client không bao giờ ra 500), đốt ngân sách lỗi và làm nhiễu alert. Giao dịch
bị cuốn ngược nên **không** mất/hỏng dữ liệu — đây là lý do finding dừng ở P1 chứ không nâng lên P0 theo luật
nâng bậc "luồng auth/PII" của RULE.md §1: hậu quả thực tế không khớp định nghĩa P0 (khai thác bảo mật, mất dữ
liệu, sập hệ thống).

✅ **Đề xuất:** đúng cách tác giả đã xử lý cho `fullName` — một `field_validator("language")` ném khi `value is None`.
Đây là cùng một lỗi gốc (R-19): tác giả đã nhận ra lớp lỗi "`null` tường minh trên cột `NOT NULL`", ghi vào "Lệch
khỏi prompt" mục 2, nhưng chỉ áp cho `fullName` và bỏ sót `language` — cột `NOT NULL` còn lại trong `_COLUMN_OF`.

🧪 **Test cần thêm:** `{"language": None}` → 422 `field:"language"`; nên thêm một test tham số hoá quét **mọi** khoá
của `_COLUMN_OF` với `null` tường minh để lớp lỗi này không tái diễn khi thêm cột.

### [P2][LOG-06] PNG mã hoá lại vẫn mang ICC profile

📍 `apps/api/me/avatar.py:198-204`.

🔍 **Bằng chứng** (chạy thật trong container cổng, Pillow 12.3.0): PNG nguồn gắn ICC sRGB 588 byte → sau
`process_avatar`, ảnh ra **vẫn có** `icc_profile` 588 byte (`ICC_SRC_present True 588` → `ICC_OUT_present True 588`).
Nguyên nhân: `Image.convert`/`thumbnail` chép `self.info` sang ảnh mới, và bộ ghi PNG của Pillow lấy
`im.encoderinfo.get("icc_profile", im.info.get("icc_profile"))` — không truyền gì thì nó **rơi về** `info` của ảnh
nguồn. Nhánh JPEG sạch (đã kiểm: EXIF ra rỗng, không ICC), nên K13/"không giữ EXIF" **không** bị vi phạm cho GPS.

💥 **Tác động:** trái bước 5 của prompt ("không mang EXIF/ICC/metadata") và trái chính docstring `avatar.py:16-17`.
Metadata của thiết bị nguồn đi ra ngoài qua object công khai và làm object phình thêm; ICC không chứa toạ độ nên
mức độ dừng ở P2, không phải lỗ hổng riêng tư.

✅ **Đề xuất:** `final.info.pop("icc_profile", None)` (kèm `"exif"`) trước `save`, hoặc `save(..., icc_profile=None,
exif=None)`. 🧪 Test: PNG có ICC + eXIf vào → ảnh ra không còn khoá nào trong `info`.

### [P2][TEST-03] Thiếu bốn test nghiệm thu khối [8] đã gọi tên

`case_gate` không bắt được vì bốn case này không nằm trong ma trận bắt buộc:

1. **N14 storage dừng → 503, `avatar_key` không đổi** (`ephemeral_minio` backend S3) — nhánh RES-04 của module
   hoàn toàn chưa được chứng minh. Cơ chế dịch lỗi kho → 503 là của B0-04 và đã chạy ở module khác, nên đây là
   lỗ hổng bằng chứng chứ không phải lỗi đã biết.
2. **N14 lặp cùng `Idempotency-Key` → cùng response, chỉ một object mới** — route dựa vào mặc định
   `idempotency="auto"` (`apps/api/core/routing.py:63`, đúng luật, không cần `route_options`), nhưng không có
   test nào chứng minh nó thật sự áp cho `PUT /api/me/avatar`. Đây là CON-02 trên đường ghi object.
3. **N14 PNG 4096×4096 16-bit → lưu ≤ 512×512 8-bit** — tôi đã tự kiểm và **mã chạy đúng** (`I;16` 600×400 →
   `RGB` 512×341), nên đây thuần tuý là thiếu test, không phải lỗi.
4. **N13 "DB an toàn dừng → 503"**.

## 3. Những gì đã tự kiểm và **đạt**

- **SEC:** không IDOR (mọi truy vấn khoá theo `principal.user_id`, không id trên đường/thân); mass assignment chặn
  bằng allowlist `_COLUMN_OF` + `extra="forbid"` (test `email` trong thân → 422, email không đổi); magic bytes
  quyết định loại, không tin `mimeType`/đuôi (K14); khoá object qua `keys.avatar` có kiểm ULID, không path
  traversal; không log mật khẩu/`contentBase64`/thân (K11 — cả module chỉ có một dòng log, trong `jobs.py`);
  EXIF (kể cả GPS) của JPEG bị xoá — đã kiểm bằng ảnh thật.
- **N13 đúng từng bước:** rate limit `me_password` 5/900 `store="safe"` `on_error="closed"`
  (`router.py:146-153`); `await db.rollback()` **trước** `verify_password`/`hash_password` (`router.py:232`, K36);
  sai mật khẩu → 422 `CURRENT_PASSWORD_INCORRECT` `field:"currentPassword"`, **không bao giờ 401** (K30, có test
  riêng); một giao dịch, đúng thứ tự khoá `users → one_time_tokens → refresh_sessions`
  (`_finish_change_password:212-217`); `UPDATE … WHERE password_hash=:old AND deleted_at IS NULL RETURNING`,
  0 dòng → 422; `revoke_tokens(purpose="password_reset")`; `SELECT … FOR SHARE` phiên hiện tại, không có →
  401 `SESSION_REVOKED`; `revoke_sessions(except_sid=…)`. **Cả hai test đua đều có thật và đúng ý:**
  N9 đổi hash giữa lúc băm (`test_change_password.py:141`, chặn `hash_password` bằng `Event`) và phiên bị thu hồi
  trong DB mà cache còn (`:118`) — cả hai còn assert mật khẩu **không** bị đè.
- **N14 đúng thứ tự 0–8:** rate limit trước mọi DB; `b64decode(validate=True)`; kiểm > 512 KiB **trước** sniff;
  `w × h` kiểm tường minh **trước** `load()` và **không** gán `Image.MAX_IMAGE_PIXELS` (K13 — test đếm
  `ImageFile.load` và khẳng định 0 lời gọi, tôi đã đọc và tin cách đếm); `DecompressionBombError` →
  `IMAGE_TOO_LARGE`; danh sách ngoại lệ tường minh, không `except Exception`; semaphore theo vòng sự kiện
  (`WeakKeyDictionary`), chờ > 2 s → 503 `DEPENDENCY_UNAVAILABLE`; toàn bộ việc CPU trong **một**
  `asyncio.to_thread`; khoá object mới mỗi lần (có test); `put` trước giao dịch, `max_bytes` 2 MiB.
- **N11/N12:** `MeSchema` đúng trường, không `null` (K01/K02 — test khẳng định `set(body)` chính xác);
  `jobTitle`/`phone` rỗng/toàn khoảng trắng/`null` → `NULL` → vắng trường; Cc và bidi → 422 đúng `field`;
  NFC (C16); đọc lại sau ghi (K22); thân có `email` → 422; người đã xoá mềm → 401, không 500 (cả bốn route).
- **`avatar_url`:** không `stat` (test đếm lời gọi = 0), `kind` qua `keys.server_chosen_kind`, `None` khi rỗng.
- **`jobs.py`:** không nhập `fastapi`/`jwt`/`argon2`/`apps.api.core` (có test chạy tiến trình con với
  `sys.modules` bị chặn); regex khoá đúng nguyên văn khối [6]; đọc DB **theo lô** bằng `IN (...)`, một truy vấn
  mỗi lô (R-20, không N+1); không xoá ảnh hiện tại hay khoá lạ (J01 khẳng định cả hai); `@periodic` trả task
  Celery đồng bộ nên `test_purge_avatars_smoke` chạy thật chứ không tạo coroutine treo.
- **K20:** không `datetime.now()` trong mã nguồn (chỉ trong test, kèm lý do đúng: `last_modified` là giờ thật
  của hệ tệp). **R-01:** mọi hàm, kể cả hàm private và helper test, đều có docstring. **R-08:** hàm dài nhất
  ~20 dòng, không hàm nào vượt 50 dòng hay cyclomatic 10. Test dùng Postgres/Redis/MinIO thật, không mock (K23).
- **Bốn điểm "Lệch khỏi prompt" của tác giả:** (1) bảng chữ ký GIF/WebP/BMP/TIFF — đúng đính chính người điều
  phối, có test cho cả ba nhánh; (2) `fullName: null` → 422 — hợp lý và an toàn hơn, **nhưng** chính là lỗ hổng
  của finding #1 vì áp thiếu cột; (3) `_new_ulid` — **đã tự kiểm `packages/core/ids.py`: đúng là không có hàm
  sinh ULID trần công khai** (chỉ có `is_ulid` để kiểm), nên cách làm là lựa chọn duy nhất trong whitelist →
  finding #5 là nợ cho B0-02, không phải lỗi của B1-04; (4) bản sao kiểm ký tự cấm — xác nhận trùng nguyên văn
  `auth_recovery/router.py:64-73`, chủ đúng là `packages/core/text.py` (B0-02) → finding #4.
- **NO-130 có thật** (`DEBT.md:150`, P2, chủ B0-01): quy 10 dòng thiếu của `router.py` cho nó là đáng tin, và
  dù sao `apps/api/me` vẫn 97,15% dòng / 100,00% nhánh, vượt xa ngưỡng 90/90.

## 4. Sổ nợ

Tác giả báo "không có nợ". Với finding #4 và #5 thì **có** hai dòng nợ phải ghi (chủ là B0-02, không phải B1-04),
cộng nợ của finding #3 nếu không sửa trước merge. Người điều phối ghi `DEBT.md` (worker không được sửa file đó):

| Nợ | Mô tả | Chủ | Mức |
|---|---|---|---|
| mới | `packages/core/ids.py` không phơi hàm sinh ULID trần; `keys.avatar` đòi ULID trần nên người gọi phải dựng id giả `tpl_…` rồi cắt tiền tố | B0-02 (`packages/core/ids.py`) | P3 |
| mới | Kiểm ký tự Cc/bidi của tên người dùng bị chép ở hai nơi (`auth_recovery/router.py`, `apps/api/me/schemas.py`); nhà đúng là `packages/core/text.py` | B0-02 (`packages/core/text.py`) | P3 |

Ghi chú (không chấm điểm, không phải mã): báo cáo nghiệm thu `bao-cao-B1-04.md` ([11].6) chưa được viết.

## 5. Điểm

| Miền | Trọng số | Điểm | Tích | Lý do |
|---|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 | Không finding; magic bytes, allowlist cột, EXIF/GPS sạch, K30/K11 đạt |
| CON – Concurrency & dữ liệu | 15% | 4 | 0,60 | Chỉ Nit #6; thứ tự khoá và hai test đua của N13 đều đúng |
| LOG – Tính đúng đắn | 15% | 1 | 0,15 | Finding #1 (P1) và #2 (P2) |
| PERF – Hiệu năng | 10% | 5 | 0,50 | Việc CPU trong luồng riêng, đọc DB theo lô, trần 512 KiB |
| RES – Chịu lỗi | 10% | 4 | 0,40 | Semaphore → 503 có test; nhánh storage dừng chưa được chứng minh |
| DB, API – Migration & contract | 10% | 5 | 0,50 | Không migration; H1 596 mẫu đạt; `MeSchema` đúng hợp đồng |
| TEST – Kiểm thử | 7% | 3 | 0,21 | Finding #3 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 | Không lộ bí mật trong log; cấu hình fail-closed |
| MNT – Bảo trì | 3% | 4 | 0,12 | Finding #4, #5, #7; MNT-05 ghi nhận và bỏ qua có lý do |
| **Tổng** | **100%** | | **3,98 / 5** | |

## PHÁN QUYẾT: REQUEST CHANGES

Đây là một nhánh chất lượng cao: cổng đầy đủ xanh thật, mọi con số tác giả báo đều đúng khi chạy lại độc lập, các
điểm khó nhất của prompt (thứ tự khoá và hai đường đua của N13, kiểm kích thước trước `load()` với phép đếm bộ giải
mã, semaphore theo vòng sự kiện, ranh giới nhập của `jobs.py`, đọc DB theo lô) đều được làm đúng và có test chứng
minh. Nhưng RULE.md §5 rất rõ: **một P1 chưa waiver là chặn merge**, và ở đây P1 là một 500 mà bất kỳ người dùng đã
đăng nhập nào cũng ép được trên một endpoint PII — đúng lớp lỗi mà chính tác giả đã nhận ra và chặn cho `fullName`,
chỉ là bỏ sót `language`.

**Để được APPROVE, phải sửa:**

1. **(bắt buộc)** Finding #1 — `language: null` tường minh phải ra 422 `field:"language"`, kèm test; nên là test
   tham số hoá quét mọi khoá `NOT NULL` của `_COLUMN_OF` để lớp lỗi này không tái diễn.
2. **(bắt buộc)** Finding #2 — bỏ `icc_profile`/`exif` khỏi `info` trước khi `save` PNG, kèm test khẳng định ảnh ra
   không còn metadata nào.
3. **(bắt buộc, hoặc waiver có ticket + chủ + deadline)** Finding #3 — ít nhất hai test `Idempotency-Key` lặp và
   storage dừng → 503, vì đó là hai bất biến an toàn của N14 mà hiện chưa có gì chứng minh.
4. Finding #4, #5: **không** sửa trong nhánh này (ngoài whitelist) — người điều phối ghi hai dòng `DEBT.md` cho B0-02.
5. Finding #6, #7 là Nit, tác giả tự quyết.

Sau khi sửa: chạy lại cổng đầy đủ một lần và xin review lượt 2.
