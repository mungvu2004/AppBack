# Review merge fix/b6-04b-ultralytics-pil-open → main (FIX-116)

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `1861e9198b26`
- Nợ đóng: **NO-322** (`DEBT.md`) — chủ B6-04b + B5-01
- Cổng: phạm vi **đầy đủ**, chạy một mình; `bash tools/verify/run.sh verify` **mã thoát 0**
  (log `backend/dieu-phoi/chay/FIX-116/gate-1.log`; `FIX-116/gate.sha` = `1861e9198b26220c372af724b69fc688fc35af9d`,
  trùng sha nhánh đi review). `7690 passed`, 613,62 s. Bảng E.10 lấy từ mã thoát thật trong log:

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 10 kept / 0 broken |
| 5 | `pytest -n (cov)` → `coverage_gate` | đạt | 7 690 qua / 0 hỏng |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm |
| 6 | `lint_migrations` → `migrate_check` | đạt | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | 64 mẫu ngữ cảnh · 10 khoá/3 vai · 25 mã/26 khoá ngưỡng · 6 khung SSE |
| 8 | `openapi` | đạt | 255 271 byte |

  **mã thoát: 0** — không bước nào `hỏng` hay `chưa chạy`. Tiền kiểm: `FIX-116/pre5.log` xanh
  (`119 passed, 1 deselected`); `pre.log`→`pre4.log` là các lượt đỏ trung gian của vòng viết (xem
  mục "Lịch sử kiểm"). Đối chiếu số test: cổng B6-02b trên `4ce1f41` chạy 7 862 ca (7 861 qua + 1 hỏng)
  với 177 ca riêng của B6-02b ⇒ nền `main` ≈ 7 685; FIX-116 = nền + 4 ca mới ⇒ 7 690 **khớp**, tức bốn
  test hồi quy mới thật sự có chạy trong cổng (log chỉ in dấu chấm, không in tên ca)
- Phạm vi diff `main...1861e91`: 7 tệp, +249/−2 — `apps/ml/runtime/ultralytics_import.py` (mới),
  `apps/ml/runtime/tests/test_ultralytics_import.py` (mới), `apps/ml/runtime/export_yolo.py`,
  `apps/ml/runtime/tests/test_imports.py`, `apps/ml/training_yolo/trainer.py`,
  `apps/ml/training_yolo/tests/test_trainer.py`, `changes/FIX-116.md` (mới). **Không** chạm
  `packages/vision/**`, `apps/api/**`, `DEBT.md` — đúng giới hạn spec. Tất cả trong whitelist
  (`test_imports.py` chỉ đổi `ULTRALYTICS_ALLOWED` + một dòng docstring = "chỉ đường nhập ultralytics").
- Độ phủ tệp sản phẩm đã sửa (`FIX-116/pre5.log`): `export_yolo.py` **100 %** · `ultralytics_import.py`
  **100 %** · `trainer.py` **97 %** (5 miss, 1 BrPart; thiếu 200-202, 241, 244-245) — mỗi tệp ≥ 90/90.
- Lệnh tái hiện NO-322 (`pytest -p no:randomly … ml_eval/test_metrics.py apps/api/quality/test_processing.py`):
  **xanh** — `pre2.log:142` `30 passed, 1 deselected`. Trên `main` sạch cùng lệnh là `1 failed`
  (`B6-02b/M/repro-main.log`). Đây là bằng chứng trực tiếp nhất rằng gốc đã bị xử.

## Sửa có đúng gốc và đúng một chỗ không (R-19)

**Có.** Gốc là `ultralytics` gán đè `PIL.Image.open` **lúc nhập package**, và bản bọc
`patches.image_open` bắt `except Exception` rồi nhập `pi_heif` (không có trong `uv.lock`) nên mọi lỗi
thật biến thành `ModuleNotFoundError`. FIX không vá `raster.py` (nơi *lộ* triệu chứng) mà chặn tại
biên nhập ultralytics, nên **mọi** người dùng `PIL.Image.open` trong tiến trình được bảo vệ, không
riêng `load_raster`.

Hàm gọn và đúng: lưu `PIL.Image.open` → `import ultralytics` → đặt lại trong `finally` (nên lượt nhập
hỏng cũng không để lại bản vá); nhánh "đã bị vá sẵn" nhận ra bằng `saved.__module__ != "PIL.Image"`
rồi lấy lại bản gốc mà ultralytics giữ ở `patches._image_open`. Idempotent.

**Tôi tự `grep` toàn repo (`import ultralytics` / `from ultralytics`) và dò từng chỗ**, không tin bảng
của tác giả — 8 vị trí thật, **tất cả** đi qua chokepoint:

| Vị trí | Loại | Chokepoint trước dòng nhập |
|---|---|---|
| `apps/ml/runtime/ultralytics_import.py:48` | sản phẩm | **chính nó** |
| `apps/ml/runtime/ultralytics_import.py:31` | sản phẩm | trong `_pillow_image_open`, chỉ đọc `sys.modules` |
| `apps/ml/runtime/export_yolo.py:64` | sản phẩm | `import_ultralytics()` ở `:63` (sau so SHA, sau cờ ngoại tuyến) |
| `apps/ml/training_yolo/trainer.py:67-69` | sản phẩm | `import_ultralytics()` ở `:64` (sau `_OFFLINE_ENV` + `YOLO_CONFIG_DIR`) |
| `apps/ml/training_yolo/trainer.py:346` | sản phẩm | đi qua `prepare_ultralytics()` của cùng lượt chạy |
| `apps/ml/training_yolo/tests/test_trainer.py:45, 67, 154, 164-165, 256, 295` | test | `prepare_ultralytics()` ở `:44, 66, 153, 163, 255, 294` — **6/6** |
| `apps/ml/ml_eval/tests/test_sandbox.py:141, 159` | test | `prepare_ultralytics()` ở `:139` (`:159` nằm trong hàm do chính test đó gọi sau) |
| `apps/ml/ml_eval/tests/test_metrics.py:110` | test | `prepare_ultralytics()` ở `:108` |
| `apps/ml/training_yolo/tests/test_offline.py:18` | **không phải import thật** | nằm **trong chuỗi `_PROBE`** chạy ở tiến trình con, và chuỗi đó tự gọi `prepare_ultralytics()` trước |
| `apps/ml/runtime/tests/test_imports.py:55` | **không phải import thật** | chuỗi dữ liệu của ca kiểm bộ quét |

Hai dòng cuối đáng nói: spec FIX-116 khẳng định `test_offline.py:18` là "nhập ở **mức module**" và
phải sửa. Khẳng định đó **sai** (`grep` bắt chuỗi `_PROBE`), và người làm đã **đúng** khi không sửa gì
ở đó. `apps/ml/ml_eval/tests/` nằm trong whitelist nhưng không cần đổi dòng nào — tôi đã kiểm, không
phải bỏ sót. Vậy diff hẹp hơn whitelist là đúng, không phải thiếu.

**Khai "`torch.save` không đụng đường nào của ta" (docstring `:16-17`): đúng** — `grep -rn "torch\.save"`
toàn repo chỉ ra chính hai dòng docstring đó, không có lời gọi nào.

## Bất biến có test khoá không

| Yêu cầu | Test | Nhận xét |
|---|---|---|
| "sau hàm, `PIL.Image.open` là của Pillow" ở tiến trình **sạch** | `test_import_keeps_pillow_open_in_a_clean_process` | Không chỉ `assert is saved` mà còn chạy `load_raster` thật **qua `packages.vision`** trên PNG bom 50 000² và PNG cụt → `IMAGE_TOO_LARGE`, `FILE_CORRUPT`. Tức là tái hiện NO-322 end-to-end rồi chứng minh đã khỏi, không phải chỉ kiểm con trỏ hàm |
| nhánh "đã bị vá sẵn" | `test_import_repairs_an_already_patched_process` | Tiến trình con nhập `ultralytics` **trần** trước; khẳng định `__module__` đi từ `ultralytics.utils.patches` → `PIL.Image`, kèm bom → `IMAGE_TOO_LARGE` |
| tên riêng `_image_open` | `test_import_restores_from_the_ultralytics_copy` | `assert PIL.Image.open is patches._image_open` — ultralytics đổi tên thì `_pillow_image_open()` ném `AttributeError` và test đỏ ngay; thêm `assert __module__ == "PIL.Image"` nên bản `_image_open` thôi là hàm gốc cũng bị bắt. Kèm `ponytail:` ở docstring `:28-29` nêu đúng trần (ghim 8.4.155) và dấu hiệu phải nâng |
| idempotent | `test_import_ultralytics_is_idempotent` | nhánh "chưa bị vá", tại chỗ (tiến trình con không vào độ phủ) |

Hai test tại chỗ đều gọi `prepare_ultralytics()` trước và `test_import_restores_from_the_ultralytics_copy`
dùng `MonkeyPatch.context()`, nên không rò `PIL.Image.open` sang test sau — tôi đã lần thứ tự:
`prepare_ultralytics()` chạy **trước** `setattr`, nên giá trị monkeypatch hoàn lại là bản Pillow thật.

**Ghi chú đọc số:** `pre5.log` in `ultralytics_import.py 11 stmts / 0 branch / 100 %`. Con số "100 %
nhánh" ở đây **rỗng nghĩa** — `saved if … else …` là biểu thức điều kiện, `coverage --branch` không
tính là nhánh. Bằng chứng thật cho hai phía là hai test tại chỗ ở trên, không phải con số. Ghi ra để
người sau không trích 100 % làm bảo đảm.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| H-01 | **P2** | TEST | Bất biến của FIX là "mọi đường nhập `ultralytics` đi qua chokepoint", nhưng **không có cổng nào gác tệp test** — `scan()` bỏ qua đúng những tệp đó (`if "/tests/" not in rel`), nên `ULTRALYTICS_ALLOWED` chỉ ràng buộc mã **sản phẩm**. Hôm nay bất biến vẫn đúng (tôi kiểm 8/8 chỗ), nhưng chỉ nhờ **trùng hợp có lợi**: mọi test đã phải gọi `prepare_ultralytics()` vì lý do khác (cờ `YOLO_*`, R-02). Ngày mai ai thêm một `import ultralytics` trần trong một tệp test thì không gì đỏ, và NO-322 quay lại đúng dạng cũ — hỏng từ xa, chỉ lộ ra tuỳ cách `--dist loadfile` xếp worker. Mà NO-322 **vốn sinh ra từ mã test**, nên cổng bỏ trống đúng vùng đã gây sự cố | `apps/ml/runtime/tests/test_imports.py:38-45` | (a) cho `scan()` xét cả tệp test, chỉ cho `ultralytics` ở tệp có tham chiếu `prepare_ultralytics`/`import_ultralytics`; **hoặc** (b) rẻ hơn và bắt được mọi đường rò bất kể chỗ nhập: fixture `autouse`, phạm vi module, dưới `apps/ml` khẳng định `PIL.Image.open.__module__ == "PIL.Image"` lúc teardown — cổng này sẽ bắt được **chính** NO-322 lúc nó mới sinh. P2 ⇒ nếu không làm trong FIX này thì ghi một dòng `DEBT.md` |
| H-02 | Nit | R-01 | `scan()` thiếu docstring ⇒ `audit.py` báo `HỎNG thiếu docstring: apps/ml/runtime/tests/test_imports.py:38 scan`. **Có trước FIX** (tôi `git show main:` kiểm: trên `main` cũng thiếu), không do FIX gây ra | `apps/ml/runtime/tests/test_imports.py:38` | Thêm một dòng docstring ngay trong FIX này: tệp đang mở, sửa một dòng, và `audit.py` thôi báo động giả cho mọi phiên sau |
| H-03 | Nit | TEST | Module mới không được thêm vào danh sách của `test_runtime_imports_without_torch_or_forbidden_packages`, nên không có khẳng định nào rằng `apps.ml.runtime.ultralytics_import` nhập được khi `ultralytics`/`torch` bị chặn (thực tế **có** an toàn: cả hai lệnh nhập đều nằm trong hàm) | `apps/ml/runtime/tests/test_imports.py:84` | Thêm `"ultralytics_import"` vào tuple module của test đó |

Không có P0, P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,83 / 5** |

Tổng: 4,83 / 5

## PHÁN QUYẾT: APPROVE

Sửa đúng gốc, đúng một chỗ, và chứng minh bằng đúng loại bằng chứng mà lỗi này đòi. Ba điểm làm tôi
duyệt: (1) FIX chặn ở biên nhập `ultralytics` chứ không vá `raster.py` nơi triệu chứng lộ ra, nên
mọi người dùng `PIL.Image.open` trong tiến trình được bảo vệ, không riêng `load_raster` (R-19);
(2) bất biến được khoá trong **tiến trình con sạch** và khoá bằng hành vi thật — `load_raster` trên
PNG bom và PNG cụt phải ra `IMAGE_TOO_LARGE`/`FILE_CORRUPT` — chứ không chỉ so con trỏ hàm, và lệnh
tái hiện NO-322 đã xanh (`pre2.log:142`) trong khi trên `main` sạch nó đỏ; (3) chỗ duy nhất phải bám
tên riêng (`patches._image_open`) được đánh dấu `ponytail:` **và** có test khẳng định đúng tên đó, nên
nâng bản ultralytics sẽ làm test đỏ thay vì âm thầm trôi.

Tôi cũng tự kiểm hai khai dễ tin bừa: `grep` cả repo xác nhận 8/8 chỗ nhập `ultralytics` đều đứng sau
chokepoint, và không có lời gọi `torch.save` nào để bản vá thứ hai của ultralytics gây hại. Lịch sử
`pre2…pre5` cho thấy người làm gỡ đúng nguyên nhân khi hai test subprocess đỏ (Pillow chỉ kiểm bom
sau khi đọc tới `IDAT`) thay vì nới khẳng định — đúng tinh thần R-19.

Còn **H-01 (P2)**: cổng gác bất biến bỏ trống đúng vùng đã sinh ra NO-322 (tệp test). Không chặn
merge theo ma trận §5, nhưng P2 phải có vé: làm luôn trong FIX (một fixture `autouse` là đủ) hoặc ghi
một dòng `DEBT.md` trước khi gộp. H-02, H-03 là Nit; H-02 có trước FIX nhưng nên sửa kèm vì chỉ một
dòng và đang làm `audit.py` báo động giả.

Không tự merge: việc merge thuộc phiên gọi review này.

## Lịch sử kiểm (đọc `pre*.log`, soát cách gỡ lỗi)

| Log | Kết quả | Việc đã xảy ra |
|---|---|---|
| `pre.log` | 2 lỗi ruff | định dạng, đã sửa |
| `pre2.log` | `2 failed, 1022 passed` | **hai test subprocess mới** đỏ (không phải test cũ nào) |
| `pre3.log` | `2 failed, 4 passed` | vẫn hai test đó |
| `pre4.log` | `1 failed, 118 passed` | `test_cpu_run_stays_offline` — chính ca FIX thêm `prepare_ultralytics()` vào |
| `pre5.log` | `119 passed, 1 deselected` | xanh; độ phủ ba tệp sản phẩm 100 / 100 / 97 % |

Hai lượt đỏ đầu không bị "chữa" bằng cách nới khẳng định: docstring `_png_declaring` (`:56-57`) ghi lại
đúng nguyên nhân tìm được — `Image.open` chỉ chạy `_decompression_bomb_check` **sau** khi plugin đọc tới
`IDAT`, nên PNG chỉ có IHDR hỏng sẽ ra `FILE_CORRUPT` chứ không ra bom — rồi dựng PNG đủ chunk. Đó là
sửa gốc của chính ca kiểm, đúng tinh thần R-19. Tôi kiểm riêng: trong `pre2.log` không có ca cũ nào đỏ
(dòng 382 nhắc `test_race.py` là ở khối cảnh báo, không phải khối `FAILED`).
