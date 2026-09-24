# Review merge feature/b1-04-profile-password-avatar → main — lượt 2

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (cùng reviewer lượt 1, R-37) · Commit đầu nhánh: `9365372d6e21`
- Phạm vi lượt này: **chỉ** `git diff b875db4..9365372` — 8 file, +231/−15. Phần đã chấm ở lượt 1 không chấm lại.
- Vòng sửa đáp phán quyết `docs/reviews/2026-09-24-feature-b1-04-profile-password-avatar.md` (REQUEST CHANGES, 3,98/5)
- Cổng: **không** chạy lại cổng đầy đủ (reviewer một lần mỗi nhánh). Đọc `gate2.log` của tác giả + tự chạy hai phép
  kiểm độc lập (mục 2).

## 1. Từng finding lượt 1 → đã đóng chưa

| Finding lượt 1 | Nợ | Trạng thái | Sửa ở đâu | Tự kiểm |
|---|---|---|---|---|
| #1 P1 LOG-02 `language: null` → 500 | NO-165 | **ĐÓNG, sửa đúng gốc** | `apps/api/me/schemas.py:87-93` (`_validate_language`) | `test_update_profile.py:165-177` quét cả `_COLUMN_OF` |
| #2 P2 LOG-06 PNG còn ICC profile | NO-166 | **ĐÓNG, sửa đúng gốc** | `apps/api/me/avatar.py:205-209` (`final.info.clear()`) | `test_avatar_unit.py:95-114`, cả PNG và JPEG |
| #3 P2 TEST-03 thiếu 4 test khối [8] | NO-167 | **ĐÓNG, đủ cả bốn** | 4 test mới (chi tiết dưới) | đọc từng test + chạy lại module |
| #7 Nit MNT-04 `type: ignore` thiếu lý do | — | **ĐÓNG** | `apps/api/me/router.py:74,165` | đọc diff |
| #4 P3 trùng lặp kiểm Cc/bidi | NO-168 | không sửa — **đúng** | ngoài whitelist, chủ B0-02 | — |
| #5 P3 `_new_ulid` | NO-169 | không sửa — **đúng** | ngoài whitelist, chủ B0-02 | — |
| #6 Nit CON-06 `LOAD_TRUNCATED_IMAGES` | — | không sửa | `avatar.py:189` | xem mục 4 |

### NO-165 — sửa đúng gốc, không vá triệu chứng (R-19)

`_validate_language` (`schemas.py:87-93`) từ chối `null` tường minh đúng như `_validate_full_name` đã làm. Điều làm
nó thành **sửa gốc** chứ không phải vá một cột: test `test_me_update_profile_not_nullable_field_explicit_null_is_422`
(`test_update_profile.py:165-177`) tham số hoá trên `NOT_NULLABLE_FIELDS = sorted(_COLUMN_OF.keys() -
_NULLABLE_ON_EMPTY)` — tức **suy ra từ chính bảng cột của router**, không phải danh sách chép tay. Thêm một cột
`NOT NULL` vào `_COLUMN_OF` mà quên chặn `null` thì test đỏ ngay. Test còn đọc lại `GET /api/me` và assert 200, tức
chứng minh cột không bị `NULL` hoá chứ không chỉ chứng minh mã trả về. Đúng thứ tôi yêu cầu ở lượt 1.

Cặp đôi `test_me_update_profile_language_valid_value_is_saved` phủ nhánh thành công của validator mới.

### NO-166 — sửa đúng gốc, và đúng *lý do* gốc

`final.info.clear()` trước `save` (`avatar.py:205-209`), kèm docstring module (`avatar.py:16-20`) viết lại đúng cơ
chế: Pillow **rơi về `im.info`** khi `save()` không được truyền `exif=`/`icc_profile=`, nên "không truyền gì" là
chưa đủ. Sửa nằm trong `_decode_and_reencode` nên phủ cả PNG lẫn JPEG bằng một đường.

Hai test mới đều có **chốt chống test giả**: `assert "icc_profile" in src.info` trên ảnh *vào* trước khi xử lý, nên
test không thể xanh nhờ ảnh mẫu vốn đã không có ICC. Thứ tự `convert` → `thumbnail` → `clear()` → `save` cũng đúng:
`convert("RGBA")` đọc `info["transparency"]` của ảnh palette **trước** khi `info` bị xoá, nên không mất kênh trong
suốt.

### NO-167 — bốn test đều thật, không có test bù nhìn

1. `test_me_replace_avatar_storage_down_is_503_avatar_key_unchanged` — dựng `ephemeral_minio` thật rồi **dừng nó**,
   dựng app riêng trỏ backend `s3` vào endpoint đã chết → 503 `DEPENDENCY_UNAVAILABLE`, `avatar_key` không được ghi.
   Không mock (K23). `reset_storage_settings_cache()` gọi trong `finally` **trước** khi `monkeypatch` trả lại biến
   môi trường — đúng thứ tự, không rò cấu hình sang test sau.
2. `test_me_replace_avatar_idempotency_key_repeat_creates_one_object` — gửi hai lượt cùng `Idempotency-Key`, assert
   `first.json() == second.json()` **và** `len(objects) == 1` dưới `users/{u}/avatar/`. Đây đúng là bằng chứng
   CON-02 mà lượt 1 nói là đang thiếu: nó chứng minh tầng idempotency mặc định (`idempotency="auto"`) thật sự áp cho
   `PUT /api/me/avatar`, chứ không chỉ "đúng luật trên giấy".
3. `test_me_replace_avatar_png_4096_16bit_downsizes_to_8bit` — đọc **object đã lưu thật** qua
   `storage.open_read(row.avatar_key)` rồi assert ≤ 512×512 và mode `RGB`/`RGBA`. Ảnh mẫu 4096×4096 một màu nên nén
   còn vài KB, qua lọt trần 512 KiB và trần 40 Mpx đúng như thiết kế.
4. `test_me_change_password_safe_redis_down_is_503` — **đúng ý khối [8]**, đã tra tận gốc chứ không suy đoán:
   BE-00 §11 (dòng 434) gọi đúng kho `store="safe"` là "**DB an toàn**" ("Khoá đăng nhập đặt ở DB an toàn
   (`store=safe`)"), nên câu "DB an toàn dừng → 503" của prompt chính là kho `safe` chết → rate limit `on_error=
   "closed"` → 503. Test dùng `refused_url("redis")` + client Redis thật, theo đúng khuôn
   `apps/api/core/tests/test_ratelimit.py`, và giữ `cache` là client thật để không phá hạn mức khác. Không mock.

### Nit MNT-04 → đóng

`router.py:74,165`: `# type: ignore[misc]  # Row đúng cột SELECT` / `[index]`. Có mã **và** lý do.

## 2. Bằng chứng cổng lượt 2

**Của tác giả** (`backend/dieu-phoi/chay/B1-04/gate2.log`, đã tự đọc chứ không tin tóm tắt): 9/9 bước `đạt`;
`3520 passed, 0 failed, 0 skipped, 4 deselected` (592,7 s); `coverage_gate` tổng dòng 99,02% · nhánh 97,59%,
`apps/api/me` dòng 97,20% · nhánh 100,00%; `case_gate: đạt` với cả bốn op `me_*`.

**Tự chạy độc lập trong worktree review:**

| Phép kiểm | Kết quả |
|---|---|
| `verify --steps 1,2,3,4` | **mã thoát 0** — ruff format, ruff check, `mypy --strict` (457 file), lint-imports đều `đạt` |
| `coverage run --branch -m pytest apps/api/me -q` | **78 passed, 0 failed** (31,5 s) |
| `coverage report --include='apps/api/me/*'` | `avatar.py` 99% (146 stmt, thiếu 1) · `jobs.py` 100% · `router.py` 92% (thiếu 10) · `schemas.py` 100% · `__init__.py` 100% · **TOTAL 98%**, nhánh 0 phần khuyết |

**Không có số nào lệch gate2.log.** Từng con số per-file trùng khít báo cáo tác giả. Mười dòng thiếu của `router.py`
vẫn là NO-130 (`DEBT.md:150`, chủ B0-01) như lượt 1 đã xác nhận; một dòng thiếu của `avatar.py` là nhánh
`DecompressionBombError` phòng hờ đã ghi nhận từ lượt 1. Không cần chạy lại cổng đầy đủ.

## 3. Sửa ngoài finding: `convert` trước `thumbnail` — kiểm hệ quả

Tác giả tự khai một sửa không nằm trong finding nào (`avatar.py:196-205`): đổi thứ tự thành `convert` 8-bit **trước**
`thumbnail`. Tôi đã kiểm ba mặt, chạy thật trong container cổng (Pillow 12.3.0):

**Lỗi gốc là thật, và lượt 1 của tôi đã bỏ sót nó.** Đo trực tiếp:

```
THUMB_I16 (600, 400)   OK -> (512, 341)
THUMB_I16 (4096, 4096) RAISED ValueError image has wrong mode
```

`Image.thumbnail` dùng đường `reduce` nhanh khi tỉ lệ thu lớn, và đường đó không hỗ trợ mode `I;16`. Ở lượt 1 tôi
viết "PNG 16-bit: mã chạy đúng" — câu đó chỉ đúng cho ảnh 600×400 mà tôi thật sự chạy (tỉ lệ 1,17, không chạm đường
`reduce`). Đúng kích thước khối [8] gọi tên (4096×4096) thì mã **vỡ** với `ValueError` → người dùng nhận 422
`FILE_CORRUPT` cho một ảnh hợp lệ. Test NO-167 của tác giả bắt được lỗi này; probe nhỏ của tôi thì không. Ghi lại
cho rõ: đây là lỗi thật tác giả tìm ra, không phải sửa thừa.

**Hệ quả tài nguyên — có thật nhưng có trần.** Đổi thứ tự thêm một bản sao **nguyên cỡ** (`Image.convert` cùng mode
vẫn trả bản sao) trước khi thu nhỏ: ~50 MB cho 4096×4096 RGB, ~67 MB cho RGBA, chồng lên bộ đệm nguyên cỡ đã giải mã.
Đo thật: xử lý một PNG 4096×4096 đẩy RSS tiến trình từ ~27 MB lên ~227 MB (RGB) / ~293 MB (RGBA) — đây là mốc
**cao nhất** của cả tiến trình test nên là cận trên, không phải chi phí ròng mỗi request. CPU: 0,19 s cho PNG RGB
4096, 0,13 s cho `I;16` 4096. Dưới semaphore 2 thì trần là hai lượt như vậy cùng lúc.

**JPEG không bị ảnh hưởng:** `opened.draft("RGB", (512, 512))` vẫn chạy **trước** `load()`, nên JPEG 4096×4096 giải
mã thẳng ở ~1/8 cỡ — đo được 0,01 s, rẻ hơn hai bậc so với PNG. **Ảnh thường không đổi hành vi:** bộ test module
78/78 xanh, nhánh `avatar.py` phủ 100% nên cả hai phía của `_has_alpha` đều chạy; với PNG palette thứ tự mới còn cho
chất lượng **tốt hơn** (resample sau khi đã convert, thay vì resample trên bảng màu).

→ Ghi một **P3 PERF-06** (mục 4). Không chặn merge: đúng đắn thắng tiết kiệm bộ nhớ, trần đã bị `MAX_DIMENSION`
4096 + `MAX_PIXELS` 40 Mpx + semaphore 2 chặn, và phương án né bản sao (chỉ `convert` khi mode không phải
`RGB`/`RGBA` 8-bit) làm mã rắc rối hơn hẳn phần thắng được.

## 4. Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | PERF-06 | `convert` nguyên cỡ trước `thumbnail` thêm một bản sao ~50–67 MB cho ảnh 4096×4096, kể cả khi ảnh đã là `RGB`/`RGBA` 8-bit (trường hợp phổ biến nhất) | `apps/api/me/avatar.py:196-203` | Tuỳ chọn: chỉ `convert` trước khi thu nhỏ khi `transposed.mode not in ("RGB", "RGBA")`, còn lại giữ thứ tự cũ. Không bắt buộc — xem lý do mục 3 |
| 2 | P3 | CON-06 | (**mang từ lượt 1, lượt đó tôi chấm nhẹ tay**) gán `ImageFile.LOAD_TRUNCATED_IMAGES` mỗi request từ luồng phụ | `apps/api/me/avatar.py:189` | Xem ghi chú bên dưới — cần người điều phối phân xử, **không** sửa trong nhánh này |
| 3 | Nit | TEST-02 | Test storage dừng assert `avatar_key is None` trên người dùng **mới**, nên chứng minh "không ghi khoá mới" chứ chưa chứng minh "khoá **cũ** không đổi" | `test_replace_avatar_route.py:227` | Đặt sẵn một avatar thành công rồi mới giết storage, assert khoá vẫn là khoá cũ |
| 4 | Nit | MNT-04 | `NOT_NULLABLE_FIELDS` suy "cột `NOT NULL`" từ `_NULLABLE_ON_EMPTY` (vốn là khái niệm "rỗng → xoá"), hai khái niệm chỉ *tình cờ* trùng nhau hôm nay | `test_update_profile.py:19` | Nếu sau này có cột nullable không nằm trong `_NULLABLE_ON_EMPTY`, sweep sẽ đòi 422 sai. Lệch về phía an toàn nên không hại |

### Ghi chú finding #2 (minh bạch về lượt 1)

Lượt 1 tôi chấm đây là `Nit` với lý do "prompt bắt buộc giá trị này". Lượt này, khi tra BE-00 §11 cho một việc khác,
tôi thấy dòng 446 của hiến chương viết: "**không** gán `Image.MAX_IMAGE_PIXELS` hay `ImageFile.LOAD_TRUNCATED_IMAGES`
(biến toàn cục của cả tiến trình API, không an toàn luồng)". Tức hiến chương cấm gán, còn prompt [6] bước 4 lại bảo
gán `= False` — **mâu thuẫn prompt ↔ hiến chương**, mà CLAUDE.md quy định hiến chương thắng. Đáng lẽ lượt 1 tôi phải
trích dòng này thay vì chấm Nit.

Dù vậy **không chặn merge lượt này**, vì ba lý do: (a) dòng mã đó **không** nằm trong diff lượt 2, ngoài phạm vi được
giao; (b) giá trị gán bằng đúng mặc định của Pillow, và `packages/vision/preprocess/tests/test_raster.py:184` assert
đúng giá trị đó — không có xung đột hành vi nào hôm nay; (c) tác giả làm đúng chữ của prompt, lỗi thuộc về chỗ prompt
lệch hiến chương. Đề nghị người điều phối ghi một dòng `DEBT.md` P3 và quyết định sửa prompt hay sửa mã ở một FIX
riêng.

## 5. Điểm (chấm lại trạng thái nhánh sau vòng sửa)

| Miền | Trọng số | Điểm | Tích | Đổi so với lượt 1 |
|---|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 | giữ nguyên |
| CON – Concurrency & dữ liệu | 15% | 4 | 0,60 | giữ 4 — idempotency nay đã có bằng chứng, còn P3 #2 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 | **1 → 5**: P1 NO-165 và P2 NO-166 đều đóng đúng gốc |
| PERF – Hiệu năng | 10% | 4 | 0,40 | **5 → 4**: P3 #1 (đánh đổi có chủ ý, chấp nhận được) |
| RES – Chịu lỗi | 10% | 5 | 0,50 | **4 → 5**: nhánh storage dừng → 503 nay có test thật |
| DB, API – Migration & contract | 10% | 5 | 0,50 | giữ nguyên |
| TEST – Kiểm thử | 7% | 5 | 0,35 | **3 → 5**: đủ bốn test, đều thật, có chốt chống test giả |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 | giữ nguyên |
| MNT – Bảo trì | 3% | 4 | 0,12 | giữ 4 — Nit MNT-04 đóng, còn hai P3 là nợ của B0-02 |
| **Tổng** | **100%** | | **4,72 / 5** | 3,98 → 4,72 |

Ma trận RULE.md §5: không P0, không P1, điểm ≥ 4,0 → **APPROVE**.

## PHÁN QUYẾT: APPROVE

Cả ba finding bắt buộc đều được đóng **ở gốc chứ không vá triệu chứng**, và hai trong ba được đóng kèm một cơ chế
chống tái phát chứ không chỉ một test cho đúng ca lỗi: sweep test của NO-165 suy danh sách cột từ chính
`_COLUMN_OF`, và hai test của NO-166 tự chứng minh ảnh vào thật sự có ICC trước khi khẳng định ảnh ra không còn.
Bốn test của NO-167 đều chạy dịch vụ thật, trong đó test idempotency là đúng bằng chứng CON-02 mà lượt 1 nói là
đang thiếu. Số của tôi tự chạy (steps 1–4 mã thoát 0; 78/78 test module; độ phủ per-file) trùng khít `gate2.log`,
nên không cần chạy lại cổng đầy đủ.

Vòng sửa còn tìm thêm một lỗi thật mà lượt 1 của tôi bỏ sót — `thumbnail` vỡ trên mode `I;16` ở tỉ lệ thu lớn, đúng
kích thước 4096×4096 mà khối [8] gọi tên — và sửa nó ở gốc. Tôi đã dựng lại lỗi đó để xác nhận. Đánh đổi bộ nhớ đi
kèm là có thật nhưng có trần rõ ràng và đã đo, nên chỉ là P3.

**Được merge.** Bốn mục còn lại (2 P3 + 2 Nit) không chặn; người điều phối ghi `DEBT.md`:

- NO-168, NO-169 (đã có từ lượt 1, chủ B0-02): trùng lặp kiểm Cc/bidi, và thiếu hàm sinh ULID trần công khai.
- Mới, P3, chủ B0-01/người điều phối: prompt B1-04 [6] bước 4 bảo gán `ImageFile.LOAD_TRUNCATED_IMAGES = False`
  trong khi BE-00 §11 cấm gán — cần thống nhất một chỗ (xem mục 4, finding #2).
- Mới, P3, chủ B1-04: `avatar.py:196-203` sao chép nguyên cỡ trước khi thu nhỏ (finding #1) — chỉ sửa nếu hồ sơ bộ
  nhớ của API trở thành vấn đề thật.

Việc merge thuộc phiên gọi tôi; phiên này không merge.
