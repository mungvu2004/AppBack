# Review merge feature/b6-02b-cubicasa-import → main

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (lượt 1, R-37) · Commit đầu nhánh: `4ce1f41b51ef`
- Cổng: phạm vi đầy đủ (lớp gộp, xdist chạy một mình); `bash tools/verify/run.sh verify` mã thoát **1**
  (log: `backend/dieu-phoi/chay/B6-02b/M/gate-1.log`, sha trong `M/gate.sha` = `4ce1f41`; tiền kiểm
  `M/pre-3.log` → `PREFLIGHT OK 4ce1f41`)
- Độ phủ: **không đo ở lớp gộp** — bước 6 `chưa chạy` (sau bước 5 hỏng). Số của các lượt đích của
  tác giả: `archive.py` 98 % dòng / 96 % nhánh · `svg.py` 100 % / 96,6 % · `importer.py` 97,5 % /
  96,3 % · `cli.py` 98,4 % / 92,9 % · `convert.py` **không có số** (không có báo cáo lượt C)
- Phạm vi diff đúng sở hữu: `apps/worker/datasets_cubicasa/**` (16 tệp) + `changes/B6-02b.md`, không
  tệp nào khác; 4 447 dòng thêm, 0 xoá; không dữ liệu CubiCasa / ảnh nhị phân trong commit.

## Bảng E.10 (lấy từ mã thoát thật trong `M/gate-1.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | Contracts: 10 kept, 0 broken |
| 5 | `pytest -n 6 --cov` | **hỏng** | 1 failed, 7 861 passed, 625,89 s |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy | |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | chưa chạy | |
| 8 | `openapi` | chưa chạy | |

Mã thoát: **1**.

Test hỏng duy nhất: `apps/api/quality/tests/test_processing.py::test_process_corners__U03_huge_declared_size`
— **ngoài phạm vi nhánh này** (xem F-02; nguyên nhân gốc nằm ở `packages/vision/preprocess` +
`apps/ml/training_yolo`, không ở `apps/worker/datasets_cubicasa`). 153 test mới của module đều qua.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F-01 | **P1** | PERF-05 | **ReDoS**: `_NUM_RE`/`_LENGTH_RE` quay lui bậc hai trên token số dài, độ dài do kẻ xấu đặt tới trần SVG 16 MiB. Đo lại trên `parse_model_svg` thật: token 4 000 chữ số + `x` → 0,311 s · 8 000 → 1,263 s · 16 000 → 5,367 s · 32 000 → **22,659 s** (≈ N²). Ở trần `cubicasa_svg_max_bytes` một `points` duy nhất ≈ 1,67e7 chữ số → ≈ 7,1e6 s (**≈ 71 ngày**) cho MỘT mẫu; biến thể nhẹ hơn 512 đa giác × 32 KB = 16 MiB → ≈ 3,2 giờ. Vì cả `_convert_sample` chạy trong `asyncio.to_thread`, `touch_version` không nhịp được: lịch B6-02 chốt bản `DATASET_BUILD_TIMEOUT` sau 1 giờ còn lệnh vẫn đốt một lõi CPU vô hạn. Trái [7] ("mọi byte nguồn coi như do kẻ xấu dựng") và cùng lớp với phòng vệ bom zip / billion laughs mà prompt đã đòi | `apps/worker/datasets_cubicasa/svg.py:76` (và `:85`) | Một dòng, đã đo: `:76` → `if any(len(t) > 32 or _NUM_RE.fullmatch(t) is None for t in tokens):`; `_length` (`:85`) thêm `if len(value) > 64: return None` trước `fullmatch`. Đo lại cùng kịch bản: **22,659 s → 0,001 s**, kết quả không đổi (`polygon_invalid`) |
| F-02 | **P1** (ngoài phạm vi, chủ khác) | TEST / RES | Bước 5 đỏ vì ô nhiễm trạng thái toàn cục giữa test: `ultralytics.utils.patches` thay **toàn cục** `PIL.Image.open`; `packages/vision/preprocess/raster.py:58` gọi `Image.open` và trông vào phòng vệ của chính nó, nên `PIL.Image.DecompressionBombError` lọt ra thay vì `VisionError("IMAGE_TOO_LARGE")` → `process_corners` không ném `AppError`. Chính docstring `raster.py:5` nói rõ không được chạm biến toàn cục `Image.MAX_IMAGE_PIXELS` — ultralytics vi phạm đúng điều đó. `apps/ml/training_yolo/tests/test_offline.py` nhập `ultralytics` ở tầng module (vào `main` hôm nay qua B6-04b, `6b65d76`). B6-02b thêm 7 tệp test → `--dist loadfile` xếp lại → ML và `apps/api/quality` rơi cùng worker `gw3` và lỗi tiềm ẩn lộ ra. **Không phải lỗi mã B6-02b**, nhưng cổng đỏ thì không merge | `apps/api/quality/tests/test_processing.py:154`; gốc: `packages/vision/preprocess/raster.py:58`, `apps/ml/training_yolo/tests/test_offline.py` | Giao FIX cho chủ `packages/vision/preprocess` (K27): `_open_within_limit` tự kiểm khổ **trước** `Image.open` và/hoặc gọi hàm `PIL.Image.open` gốc đã lưu, không qua bản bị vá; hoặc `apps/ml/training_yolo/tests/test_offline.py` nhập `ultralytics` trong hàm. Ghi một dòng `DEBT.md` rồi chạy lại cổng |
| F-03 | **P2** | TEST | Ca M06 của [8] đòi "nhập hai lần → **cùng `manifest_sha256`**". Test chỉ so tập `path` + `split_counts` của hai manifest, rồi so object của bản **đầu với chính nó**; không so byte/sha giữa hai bản. Một nguồn phi tất định trong `encode_png`/`encode_mask` sẽ lọt qua đúng bất biến mà ca này sinh ra để giữ | `apps/worker/datasets_cubicasa/tests/test_runtime.py:115-182` | So trực tiếp: `assert {(e.path, e.sha256) for e in first_manifest} == {(e.path, e.sha256) for e in second_manifest}`, hoặc đọc `DatasetVersionRow.manifest_sha256` của hai bản và `assert` bằng nhau |
| F-04 | P3 | MNT (dead code) | `choose_image` chỉ trả `None` khi `IMAGE_NAME` vắng trong `sizes`, mà `_read_image` vừa tự dựng dict đúng khoá đó ⇒ nhánh `if choice is None` **không thể rẽ** (đúng khớp nhánh thiếu mà `bao-cao-D.md` ghi ở dòng 275). `bao-cao-D.md` mục 3 giải thích nhánh này là "khổ SVG vô lý" — `choose_image` không kiểm khổ SVG, nên lời giải thích đó **sai** | `apps/worker/datasets_cubicasa/importer.py:275-277`; `convert.py:54-62` | Bỏ nhánh (và để `choose_image` trả `ImageChoice` thẳng), hoặc cho `choose_image` thực kiểm khổ SVG nếu muốn giữ `image_invalid` |
| F-05 | P3 | [8] / `chung.md` | 21/21 test của `test_convert.py` mang `__` trong tên (`test_choose_image__picks_f1_scaled`, …) trong khi [8] và `chung.md` cấm rõ (`__` dành cho `test_<operationId>__<case>` và `__J0x`). Không làm đỏ `case_gate` (phần sau `__` không khớp `[A-Z]\d{2}[a-z]?`, `tools/case_gate.py:294`), nên không chặn cổng | `apps/worker/datasets_cubicasa/tests/test_convert.py:31-…` (21 hàm) | Đổi sang `test_choose_image_picks_f1_scaled` … (một lượt `sed`) |
| F-06 | P3 | R-08 | Hai hàm vượt trần 50 dòng: `import_cubicasa` 52 dòng, `test_import_cubicasa_holds_no_connection_while_putting` 54 dòng | `importer.py:538`, `tests/test_runtime.py:61` | Tách phần "chọn gốc nguồn" (zip / thư mục) của `import_cubicasa` thành hàm riêng |
| F-07 | Nit | TEST | `original_put` gán **sau** `await new_dataset(maker)` trong cùng `try`; `new_dataset` ném thì `finally` đọc biến chưa gán → `UnboundLocalError` che lỗi thật | `tests/test_runtime.py:78-113` | Gán `original_put` trước `try` |
| F-08 | Nit | LOG | `safe_extract` kiểm `ratio`/`max_file_bytes` từng mục (trong `_check_members`) **trước** khi so tổng `too_large`, còn [6] liệt kê `too_large` trước `ratio`; zip phạm cả hai sẽ báo `ratio`. Không ca [8] nào phụ thuộc | `archive.py:100-112`, `:146-148` | So `total > max_total_bytes` ngay trong vòng cộng dồn, hoặc ghi rõ thứ tự đã chọn trong docstring |

## Những gì đã kiểm và đạt

- **`safe_extract` (K13, BE-00 §11):** kiểm **cả danh mục** trước byte ghi đầu tiên; đủ **8** `reason`
  (`path`, `symlink`, `encrypted`, `too_many_files`, `too_large`, `ratio`, `corrupt`, `disk`), mỗi
  `reason` có test riêng; `(dest/tên).resolve()` phải `is_relative_to(dest.resolve())`;
  `open(…, "xb")`; **đếm byte thật** và chặn khi vượt `file_size` khai (`archive.py:129`) nên trần
  thật ≤ trần khai; không `extractall`/`extract`/`unpack_archive`; lỗi giữa chừng `_clear_dir(dest)`;
  zip nhận theo magic `PK\x03\x04`, không theo đuôi (K14) — có cả ca `.dat` là zip và thư mục tên `.zip`.
- **Đường nguồn:** `discover_samples` không đi vào symlink nào (đếm `unsafe_path`), ngăn xếp tường
  minh sâu ≤ 3; `read_regular` = `os.lstat` + `S_ISREG` → `os.open(O_RDONLY|O_NOFOLLOW|O_NONBLOCK)`
  (FIFO không treo, có test) → `fstat` lại → trần byte **trước** khi đọc hết (đọc tối đa
  `max_bytes + 1`); `ELOOP` → `UnsafePathError`, `OSError` khác nổi lên nguyên dạng.
- **SVG:** NUL / `<!DOCTYPE` / `<!ENTITY` (không phân biệt hoa thường) và trần byte chặn **trước**
  `ET.fromstring`, `# noqa: S314` có lý do đúng; không `xlink:href`, không `<use>`, không DTD, không
  `lxml`/`defusedxml`/`minidom`; tên thẻ cục bộ (`rpartition("}")`); ghép CTM đúng thứ tự SVG
  (`matrix`/`translate`/`scale`/`rotate` có tâm; `_mat_mult(cha, riêng)`), transform trên **lá** cũng
  áp dụng; `skewX` → `None` → bỏ cả cây con; đa giác < 3 điểm, lẻ số, không hữu hạn bị bỏ; trần
  20 000 tường / 5 000 hộp **dừng sớm** trong vòng; `defs` không duyệt; không đệ quy (có ca nhóm lồng sâu).
- **Chuyển:** `cv2.fillPoly` **từng** đa giác (đúng phép đo của điều phối: một lời gọi nhiều đường
  viền tô chẵn-lẻ làm góc tường thành lỗ), khe cửa khoét về `False` — có test pixel ở giữa tường, giữa
  khe cửa, giữa phòng; hộp kẹp vào khổ ảnh, hộp suy biến sau kẹp bị bỏ; `FIXTURE_LABELS` đúng 5 tên,
  tên khác chỉ đếm; `ink_ratio` đúng định nghĩa `(mask & gray<128).sum() / mask.sum()`, mask rỗng → `None`.
- **Lệnh:** đúng thứ tự bước 1–7 của [6] (dataset → họ → nguồn → `start_version` → ghi → chốt); mọi
  đường `refused` **không** tạo bản (có `_version_count(...) == 0`); mọi `failed` gọi `fail_version`
  rồi `delete_prefix`, và cả hai bước dọn hỏng vẫn trả `failed` (log `error`, không ném);
  K22/K36 — không session nào bị giữ khi đọc tệp hay gọi kho, chứng minh bằng engine riêng
  `db_pool_size=1` + `pool.checkedout() == 0` trong lúc `put` bị chặn; việc CPU trên `to_thread`;
  một mẫu trong RAM mỗi lúc; `DATASET_TOO_LARGE` cả từ trần `cubicasa_max_samples` và từ writer;
  nhịp `touch_version` 50 mẫu / 60 s trong session ngắn riêng; **không** `except Exception` (BLE)
  ở đâu, `_failure_code` trả `None` để lỗi lạ **nổi lên** thay vì thành bản `failed` âm thầm;
  `OSError` của kho không bị nuốt; `cli` chỉ chạy trong `main()` (chứng minh bằng tiến trình con có
  `DATABASE_URL` hỏng vẫn thoát 0), in bằng `sys.stdout/stderr.write`; `dataset_versions` chỉ ghi
  qua bốn hàm của B6-02.
- **Quyết định biết trước của điều phối:** cả 7 mục đều thực hiện đúng và ghi rõ trong docstring kèm
  số đo (luật toạ độ phương án 1 → `ImageBranch` chỉ còn `"identity"`, `F1_original.png` không đọc,
  thiếu `F1_scaled.png` → `no_image`, `fit_x`/`fit_y` chỉ báo cáo; `discover_samples`/`read_regular`
  ở `archive.py`; dùng lại hàm/hằng công khai của `apps.worker.datasets.tasks`; `ink_ratio` đo cho cả
  hai họ; `_Beat` khác ngữ nghĩa và nói rõ vì sao; `fillPoly` từng đa giác).
- **Test:** 153 test, Postgres testcontainers + `LocalDiskStorage` thật (K23 đúng tầng — chỉ bọc
  `put`/`delete_prefix`/`finish_version` để tiêm lỗi, không thay dịch vụ); mọi dòng ma trận [8] có
  test nhận ra được; đúng **một** test `perf` và nó log bằng `logging`; không `pragma: no cover`,
  không `skip`/`xfail`, không `type: ignore` thiếu mã và lý do; `audit.py` (docstring R-01 mọi hàm kể
  cả test và hàm lồng, suppression, dòng > 120, whitelist) → **đạt**.
- **Sổ nợ:** ba báo cáo tác giả đều ghi "không có nợ mới"; `DEBT.md` không có dòng B6-02b nào → nhất
  quán, không thiếu dòng theo R-34.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 1 | 0,10 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,28 / 5** |

Tổng: 4,28 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Module viết tốt hơn mức trung bình của bộ: ba cửa kiểm của luồng đúng thứ tự, tám `reason` của
`safe_extract` đủ và mỗi cái có test, `O_NOFOLLOW` + `lstat`/`fstat` + trần byte trước khi đọc hết,
DTD/thực thể chặn trước `ET`, K36 chứng minh bằng `checkedout() == 0` chứ không bằng lời, 153 test
chạy trên Postgres và kho thật với đáp án pixel tính được. Điểm miền 4,28. Nhưng ma trận §5 chặn ở
P1, và ở đây có hai P1 chưa waiver, cộng một cổng đỏ.

**Phải sửa để được duyệt:**

1. **F-01 (P1, trong phạm vi):** chặn ReDoS ở `svg.py:76` và `:85` bằng trần độ dài token (bản sửa
   một dòng đã đo: 22,659 s → 0,001 s, không đổi kết quả). Prompt đã đòi phòng vệ cùng lớp cho bom
   zip và billion laughs; để ngỏ một regex quay lui bậc hai trên **cùng** những byte đó là lỗ hổng
   tài nguyên, không phải chuyện style.
2. **F-02 (P1, ngoài phạm vi):** cổng đỏ ở `test_process_corners__U03_huge_declared_size`. Không
   phải lỗi mã B6-02b — gốc là `ultralytics` vá toàn cục `PIL.Image.open` và
   `packages/vision/preprocess/raster.py:58` tin vào `Image.open` đã bị vá. Giao FIX cho chủ
   `packages/vision/preprocess` (K27), ghi một dòng `DEBT.md`, rồi chạy lại cổng đầy đủ: bước 5b,
   6, 7, 8 và **số độ phủ của lớp gộp** hiện vẫn `chưa chạy`, chưa ai đo.
3. **F-03 (P2):** thêm `assert` so `manifest_sha256` (hay `(path, sha256)`) giữa hai lần nhập, đúng
   bất biến M06 mà ca [8] sinh ra để giữ.

F-04 … F-08 là P3/Nit, tác giả tự quyết, không chặn merge — nhưng F-04 nên sửa cùng lượt vì
`bao-cao-D.md` mục 3 đang giải thích sai một nhánh không thể rẽ, và F-05 là quy ước đã ghi hai nơi.

Lượt 2 chỉ cần soát lại: bản sửa `svg.py`, cổng đầy đủ xanh kèm số độ phủ dòng/nhánh của cả 5 tệp
nguồn, và `assert` M06.
