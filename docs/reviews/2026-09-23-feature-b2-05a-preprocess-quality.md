# Review merge `feature/b2-05a-preprocess-quality` → main

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (worktree riêng `b2-05a-review`, tách ở sha chấm)
- Commit đầu nhánh: `a927fdd1785e` — `feat(vision): add preprocess and quality packages`
- Phạm vi: `git diff main...HEAD` = **27 file**, toàn bộ trong `packages/vision/{preprocess,quality}/`
  + `changes/B2-05a.md`; **+3.500 dòng** (≈ 1.440 dòng mã nguồn, ≈ 2.054 dòng test).
- Prompt: `backend/prompts/B2-05a.md` khối [2], [6], [7], [8], [9], [10], [12].
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ trong phiên này, **mã thoát 0**
  (container `appback-verify-b2-05a-review-verify-run-9a50e7871f86`, log giữ bằng `docker logs -f`).
- Độ phủ (số của chính lượt chạy này): tổng repo dòng **99,13 %** · nhánh **97,53 %**;
  `packages/vision` dòng **100,00 %** · nhánh **100,00 %**; tập file bị chạm **100 % / 100 %**.

## 1. Bảng cổng E.10 — lấy từ mã thoát thật của phiên review

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 3 test) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt |
| 8 | `openapi` | đạt |

Bước 5: **2787 qua · 10 bỏ qua · 4 bị loại** trong 346 s. Bước 5b: **3 test perf qua** trong 28 s.

**10 "bỏ qua" đã truy nguồn, không thuộc diff này và không vi phạm BE-00 §12:** cả 10 nằm ở
`apps/api/core/tests/test_common.py` (`ssssssssss` trong log), là các ca
`@pytest.mark.parametrize` trên `_protected()` / `_idempotent()` còn **rỗng** vì B3-05/B4-01 chưa
hợp nhất — đúng ngoại lệ "tập tham số rỗng" của BE-00 §12. `git diff --name-only main...HEAD |
grep apps/api` trả 0 file. Diff này không có một `skip`, `xfail`, `pragma: no cover` nào
(đã grep toàn bộ 27 file).

## 2. Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-04 / R-16, R-17 | `pypdfium2.PdfiumError` lọt ra khỏi gói trên PDF hỏng do kẻ xấu dựng — vi phạm hợp đồng khối [2] "lỗi là `VisionError`" và khối [8] "không ngoại lệ lạ lọt ra (U07)" | `packages/vision/preprocess/pdf.py:197` (`_page_size_pt`), `packages/vision/preprocess/pdf.py:238` (`_render_page`) | Bọc **toàn bộ** thân chạm pdfium (`pdf[page_index]`, `page.get_size()`, `page.render()`, `bitmap.to_numpy()`) bằng `except pdfium.PdfiumError` → `VisionError("FILE_CORRUPT")`, sửa ở cả hai chỗ (R-19), + test tái hiện |
| 2 | P2 | R-01 (MNT-04) | **48 hàm không có docstring**, trong khi R-01 đòi docstring cho *mỗi* hàm | `quality/tests/test_thresholds.py:49-154` (20 hàm), `quality/tests/test_metrics.py:50-172` (12 hàm), `preprocess/tests/test_raster.py:32,36,42,46,85,142`, `preprocess/types.py:37,68,100`, `quality/assess.py:63`, `quality/metrics.py:38`, `preprocess/errors.py:31` | Thêm một câu cho mỗi hàm; với `__post_init__`/`__init__` ghi bất biến nó giữ và lỗi nó ném |
| 3 | P2 | MNT-05 | Nhánh > 400 dòng logic (≈ 1.440 dòng mã nguồn) | toàn nhánh | **Không đáng tách thêm**: khối [10] của prompt định nghĩa đúng đơn vị bàn giao này, và nhánh đã được dựng từ 3 nhánh lớp 1 (`io`, `geometry`, `metrics`) nên từng mảng đã được viết và đo ở kích thước nhỏ. Ghi lại theo luật, không yêu cầu sửa |
| 4 | Nit | R-01 / MNT-04 | `# type: ignore[arg-type]`, `[operator]`, `[index]` ở 5 chỗ trong test có **mã** nhưng không có **lý do** kèm theo (khác hai dòng `pdf.py:14-15` đã ghi đủ lý do) | `preprocess/tests/test_errors.py:37`, `preprocess/tests/test_geometry.py:121`, `preprocess/tests/test_types.py:71,96`, `quality/tests/test_assess.py:236` | Thêm nửa câu lý do ("cố tình truyền sai kiểu để chốt lỗi lúc chạy") |
| 5 | Nit | MNT-02 | Test nhập hàm riêng tư của module khác (`_bbox_region`) | `quality/tests/test_assess.py:16` | Chấp nhận được (khối [6] đòi giữ nhánh này và `assess` không tới được nó); chỉ ghi để không thành tiền lệ |

### Chi tiết finding 1 (P1)

```
[P1][LOG-04] PdfiumError lọt ra khỏi packages.vision.preprocess
📍 Vị trí: packages/vision/preprocess/pdf.py:197 và :238 — dòng `page = pdf[page_index]`
🔍 Bằng chứng (tái hiện trong chính container verify của phiên này):
     PDF A4 3 trang do `synthetic.make_pdf` dựng, đổi `/Type /Page` của trang cuối
     thành `/Type/Bad ` (10 byte, giữ nguyên offset xref) →
       pdf_page_count(data)      : ok          (pdfium vẫn đếm 3 trang)
       pdf_page_size_pt(data, 2) : !!! LEAK pypdfium2._helpers.misc.PdfiumError: Failed to load page.
       render_pdf_page(data, 2)  : !!! LEAK pypdfium2._helpers.misc.PdfiumError: Failed to load page.
     Nguồn: pypdfium2 5.13 `PdfDocument.get_page` ném `PdfiumError("Failed to load page.")`
     khi `FPDF_LoadPage` trả NULL; `err_code` của ngoại lệ này là `None` (chỉ đường mở
     tài liệu mới có `err_code`). `_open_document` bắt `PdfiumError`, nhưng `_page_size_pt`
     và `_render_page` thì không — `try/finally` ở đó chỉ đóng tài nguyên, không phân loại lỗi.
     Cắt PDF 50 % (ca U07 mà test đang có) **không** chạm được đường này: pdfium sửa chữa
     được tệp cụt và hỏng ngay ở bước mở, nên `test_pdf_page_count_u07_truncated_half`
     xanh mà bất biến "không ngoại lệ lạ lọt ra" vẫn thủng.
💥 Tác động: khối [7] quy định "mọi `bytes` coi như do kẻ xấu dựng"; khối [2] quy định lỗi
     của gói là `VisionError` mang mã 422. Một PDF người dùng tải lên với đối tượng trang
     sai `/Type` làm người gọi (B2-04, B5-06a, handler W7) nhận `PdfiumError` thay vì
     `FILE_CORRUPT` → **500 thay vì 422**, FE không có mã để hiện, và lỗi dữ liệu vào bị
     đếm thành lỗi hệ thống trong quan trắc.
✅ Đề xuất: một `except pdfium.PdfiumError as exc: raise VisionError("FILE_CORRUPT") from exc`
     bao trọn phần chạm pdfium của `_page_size_pt` và `_render_page` (không chỉ
     `pdf[page_index]`: `get_size`, `render`, `to_numpy` cùng lớp rủi ro — R-19 sửa ở gốc,
     không vá riêng dòng tái hiện được). Giữ nguyên `finally` đóng trang.
🧪 Test cần thêm: ca U07 thứ hai dựng từ `synthetic.make_pdf` rồi phá `/Type /Page` của một
     trang, chạy qua **cả ba** `pdf_page_count`, `pdf_page_size_pt`, `render_pdf_page`, chốt
     `VisionError("FILE_CORRUPT")` chứ không phải "hoặc ok hoặc lỗi".
```

## 3. Những gì đã tự kiểm và **đạt**

- **K13 / U03 / U06 — trần điểm ảnh.** `_open_within_limit` (`raster.py:49-68`) đọc `w × h` từ
  `Image.open` và chặn **trước** `image.load()`; `test_load_raster_u03_bomb_checks_size_before_decode`
  monkeypatch `ImageFile.ImageFile.load` và chốt `calls == 0` — đúng là chứng minh, không phải
  khẳng định suông. Không ảnh nào của gói vượt trần: `load_raster` qua U03,
  `render_pdf_page` qua `cap_pixels`, `rectify`/`deskew` qua `_warp_matrix_to_cap`. `_fit_size`
  (`geometry.py:70-81`) tính bằng `isqrt` + chia nguyên nên `w·h ≤ max_pixels` là bất biến số
  nguyên, không phụ thuộc sai số `sqrt` — chặt hơn công thức `floor(…)` + "bớt 1 px" mà khối [6]
  viết, và cùng kết quả.
- **Homography gồm cả phép co.** `_warp_matrix_to_cap` nhân trái `diag(sx, sy, 1)` **trước**
  `warpPerspective`/`warpAffine`; `_capped_unchanged` dựng ma trận co cho nhánh ảnh thẳng.
  `test_rectify_homography_maps_source_corners_to_target_corners` chốt lệch ≤ 1 px;
  `test_deskew_caps_straight_image_above_max_pixels` chốt `matrix[0][0] == w_mới / 800`.
- **K14.** `sniff_kind` chỉ đụng `data[:1024]`, không có tham số tên tệp hay `Content-Type`;
  `test_sniff_kind_u08_ignores_name_and_declared_type` truyền tên và MIME mâu thuẫn ở 10 ca.
  `load_raster` truyền `formats=[…]` nên một tệp không bao giờ được thử bằng bộ giải khác.
- **`PDF_LOCK`.** Cả bốn hàm công khai mở khoá trước `_open_document` và chỉ nhả sau khi
  `pdf.close()` chạy trong `finally`; trang đóng trong `finally` riêng. `cap_pixels` (numpy/cv2)
  nằm ngoài khoá — đúng, không phải lời gọi pdfium. `test_render_pdf_page_concurrent_threads_agree`
  bắn 8 luồng. Phân loại theo `err_code` đúng U04/U07 và **đã đối chiếu mã nguồn gói**:
  `PdfiumError.__init__(msg, err_code=None)` của pypdfium2 5.13 thật sự phơi `err_code`, nên
  `_UNREADABLE_ERR_CODES = {SUCCESS, PASSWORD, SECURITY}` là phân loại theo mã chứ không so chuỗi.
  `err_code is None` rơi vào `FILE_CORRUPT`, hợp lý. (Lỗ hổng còn lại: finding 1.)
- **Cấm tuyệt đối khối [9].** Không một `except Exception`/`except BaseException`/`except:` nào
  trong `packages/vision`; không gán `Image.MAX_IMAGE_PIXELS` hay `ImageFile.LOAD_TRUNCATED_IMAGES`
  (còn có test chốt hai biến đó giữ nguyên giá trị mặc định); không `getenv`/`environ`/`Path(`/
  `urllib`/`requests`; không vòng lặp Python theo điểm ảnh (K28 — mọi phép đếm đi qua
  `cv2.countNonZero`, `connectedComponentsWithStats`, mặt nạ numpy; vòng `for` duy nhất chạy theo
  đường viền và theo 16 ô lưới). Không có tệp nhị phân trong diff.
- **Ngưỡng `quality/thresholds.py` khớp `F:/AppFront/src/domain/quality/thresholds.ts`** — đối
  chiếu từng dòng: 2000/1200/0.5/5/0.75/0.45/0.2/0.4 và biên `>=`, `>=`/`<=`, `<` của
  `classifySkew` (`magnitude <= 0.5` → good, `magnitude < 5` → attention) sao đúng từng toán tử;
  `worst_level([])` → `"good"` như `worstLevel`. Phân loại chạy trên **số đã làm tròn**
  (`_measure_working` làm tròn rồi `assess` mới phân loại), và `round_score`/`round_skew` dùng
  `js_round` = `floor(x + 0.5)` để khớp `Math.round` của JS. `QUALITY_CODES` đúng 5 mã, đúng thứ
  tự, `assess` sinh theo đúng thứ tự đó, mỗi mã tối đa một mục, chỉ khi mức ≠ `good`.
- **Lệch "ảnh sạch 2.400 × 2.000 thay vì 2.400 × 1.700" (REPORT §9.1.1): lập luận đúng, chấp nhận.**
  Kiểm lại với ngưỡng FE: cạnh ngắn 1.700 < `RESOLUTION_GOOD_SHORT_EDGE_PX = 2000` nên
  `classifyResolution(1700) = 'attention'`, tức ảnh 2.400 × 1.700 **không thể** cho `findings` rỗng.
  Khối [8] ("ảnh sạch → không phát hiện") và khối [6] ("đủ phân giải → `findings` rỗng") mâu thuẫn
  với chính ngưỡng mà khối [2] gọi là nguồn duy nhất. Tác giả đổi ảnh chứ không đổi ngưỡng — đúng
  thứ tự ưu tiên (hiến chương/hợp đồng FE trên prompt), và đã ghi lý do ngay trong docstring `_clean()`.
- **R-07, `sniff.py` ↔ `packages/storage/sniff.py`: trùng ý là cố ý và không sửa được.** Đã kiểm
  `.importlinter:37-52`, hợp đồng `domain-vision-isolated` liệt `packages.storage` trong
  `forbidden_modules` cho `source_modules = packages.domain, packages.vision` — không có module
  chung nào hai bên cùng nhập được. Hai bản cũng khác hành vi thật (bản vision nhận `%PDF-` lệch
  đầu tệp, không nhận `glb`/`safetensors`). Không phải finding.
- **R-08.** Quét AST toàn `packages/vision`: **0 hàm > 50 dòng**; lồng ≤ 3 cấp; nhánh nhiều nhất là
  `assess` (5 `if`) và `_quad_candidates` (3) — cyclomatic đều ≤ 10.
- **Test hiệu năng `@pytest.mark.perf` đo thật.** `test_perf.py` dựng ảnh 7.745 × 5.164 = 40,0 MP
  (sát `DEFAULT_MAX_PIXELS`) và trang A1 @ 200 DPI, có **sàn** `_SCAN_MIN_PX = 39 MP` /
  `_A1_MIN_PX = 30 MP` để phép đo không lặng lẽ co lại, chạy đủ sáu bước
  (load → find_frame → rectify → deskew → assess → encode_png) sau một lượt khởi động và assert
  tổng `< 12,0 s`. Cả 3 ca qua ở bước 5b của lượt chạy này.
- **Cây sạch** (`git status --porcelain` rỗng), **không đụng file cấm** (27 file đều trong cột "Sở
  hữu" của prompt), `changes/B2-05a.md` có mặt, dòng đầu commit đúng Conventional Commits (46 ký
  tự), khối trailer đúng R-36b (một dòng trống trước, `Prompt: B2-05a` + `Co-Authored-By:` liền nhau).

## 4. Về 23 điểm "Lệch khỏi prompt" tác giả tự khai (REPORT §9)

Đã đọc và đối chiếu từng điểm với mã trong diff. **Chấp nhận cả 23**, không điểm nào thành finding:
19 điểm là tự chỉnh ngưỡng kỹ thuật hoặc chọn cách dựng test có số đo kèm theo (§9.1.2-3, §9.1.6-10,
§9.3.1-5, §9.3.7), đúng chỗ khối [11] mục 5 yêu cầu ghi lại; 4 điểm là "prompt ↔ hợp đồng mâu
thuẫn, theo hợp đồng" (§9.1.1 đã kiểm ở trên; §9.1.5 `Level` là kiểu trả về mà chính khối [2] khai;
§9.2.1 và §9.3.6 xoá nhánh chết, phù hợp R-11/R-14). §9.2.5 (`type: ignore[import-untyped]`) và
§9.2.6 (trùng `sniff`) đã kiểm riêng ở mục 3. `find_frame_working` (§9.1.4) không xuất ở `__init__`
— đúng, khối [2] không có nó, và `__all__` của hai gói khớp khối [2] (+ `Level`).

## 5. Sổ nợ

`DEBT.md` chưa có dòng nào cho B2-05a; báo cáo tác giả khai "không có nợ mở" — nhất quán với diff
(không tìm thấy `TODO`, `FIXME`, `ponytail:`, nhánh bỏ ngỏ nào). Ba finding P1/P2 ở trên là **nợ
do review chỉ ra**, R-38 đòi ghi `DEBT.md` **trước** khi merge; người điều phối ghi trên `main`.

## 6. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 1 | 0,15 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,34 / 5** |

LOG = 1 vì có một P1. MNT = 3 vì có P2 (finding 2 và 3). Các miền còn lại không có finding.
SEC giữ 5: phép kiểm ở biên (magic bytes, trần điểm ảnh trước giải mã, `validate_quad`) đều đủ và
fail-closed; khiếm khuyết của finding 1 là **loại ngoại lệ** trả ra, không phải thiếu kiểm — dữ
liệu xấu vẫn bị từ chối.

## PHÁN QUYẾT: REQUEST CHANGES

Chất lượng nhánh cao hơn mức trung bình rõ rệt: cổng xanh thật (tự chạy, mã thoát 0), độ phủ
`packages/vision` 100 % dòng **và** 100 % nhánh, test hiệu năng đo đúng ở trần 40 MP, ngưỡng FE
sao đúng từng toán tử biên, và 23 điểm lệch prompt đều có số đo kèm theo — không điểm nào là lệch
tuỳ tiện. Điểm 4,34/5 tự nó đủ để `APPROVE`.

Chặn merge vì **một** finding P1, và `RULE.md` §5 không cho waiver ngầm: `pdf_page_size_pt` và
`render_pdf_page` để `pypdfium2.PdfiumError` lọt ra ngoài gói với một PDF hỏng mà kẻ xấu dựng được,
phá đúng bất biến mà khối [2] ("lỗi là `VisionError`"), khối [7] ("mọi bytes coi như do kẻ xấu
dựng") và khối [8] ("không ngoại lệ lạ lọt ra") cùng đặt ra. Ca U07 đang có (cắt PDF 50 %) không
chạm tới đường đó nên cổng xanh mà bất biến vẫn thủng — đây chính là trường hợp R-37 tồn tại để bắt.

**Điều kiện để được duyệt lượt sau (chủ file: prompt B2-05a):**

1. **Bắt buộc (P1):** `except pdfium.PdfiumError` → `VisionError("FILE_CORRUPT")` bao trọn phần
   chạm pdfium của `_page_size_pt` (`pdf.py:190-202`) và `_render_page` (`pdf.py:231-242`) — sửa ở
   gốc cho cả `get_size`, `render`, `to_numpy`, không chỉ dòng `pdf[page_index]` tái hiện được
   (R-19). Kèm ca U07 mới phá `/Type /Page` chạy qua cả ba hàm công khai.
2. **Bắt buộc (P2):** thêm docstring cho 48 hàm ở finding 2 (R-01), hoặc xin waiver tường minh của
   người điều phối cho riêng nhóm hàm test một dòng.
3. **Ghi `DEBT.md` trước khi merge (R-38):** một dòng cho finding 1 và một dòng cho finding 2.
   Finding 3 (MNT-05) ghi kèm ghi chú "chấp nhận — đúng đơn vị bàn giao của khối [10]".
4. Finding 4 và 5 là `Nit`, không chặn.

Sau khi sửa: chạy lại `bash tools/verify/run.sh verify` (một lượt, mã thoát thật) rồi xin
`/merge-review` lượt 2. **Không merge** khi phán quyết còn là `REQUEST CHANGES`, kể cả khi cổng xanh.
