# Review merge fix/qa03-be-pdf-count0 → main

- Ngày: 2026-10-12 · Reviewer: phiên /merge-review · Commit đầu nhánh: 3a00289483d1 (base `main` bf83f815bf9e, `main` chưa đi tiếp)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1); `bash tools/verify/run.sh verify` mã thoát 0
  (log: `F:/App/AppBack/backend/dieu-phoi/chay/QA-03/verify-be.log`, dòng 1 trỏ log gốc
  `.cache/src-out/verify/20261011T180535Z-3a00289483d1.log` — sha trong tên trùng HEAD; bước 0–8 `đạt`, 8429 passed, `verify exit=0`)
- Độ phủ: tổng dòng 99,47% · nhánh 98,02% — `packages/vision` 99,72%/99,04%; mọi nhánh mới của `_open_document`
  (không phải PDF, mở NULL → hỏng, mở NULL → mật khẩu, 0 trang, mở được) đều có test chạy qua.

## Phạm vi

1 commit `fix(vision): classify zero-page PDF without stale PDFium error`, trailer `Prompt: QA-03`. 3 file, +41/−13:
`packages/vision/preprocess/pdf.py` (`_open_document` mở bằng `FPDF_LoadMemDocument64` thô), test hồi quy mới trong
`packages/vision/preprocess/tests/test_pdf.py`, `changes/QA-03.md`. Không route, không bảng, không migration, không đổi dây.

Điều kiện dừng sớm: cây sạch; `changes/QA-03.md` có; dòng đầu đúng Conventional Commits (62 ký tự); không file cấm; không
`pragma`/`type: ignore`/`noqa`/`skip`/`xfail` mới → không áp dụng.

## Kiểm độc lập (chạy trong container qua `run.sh shell`, bản chép, không đụng worktree)

- Gốc lỗi xác nhận trên pypdfium2 5.14.0 / PDFium 156.0.8076.0: `_open_pdf` gọi `FPDF_GetLastError()` mỗi khi
  `FPDF_GetPageCount(pdf) < 1`, kể cả khi `pdf` mở được, và ném mà không `FPDF_CloseDocument` → mã cũ + rò handle.
- Test mới **đỏ** với `pdf.py` của `main` (`assert 'FILE_CORRUPT' == 'PDF_UNREADABLE'`), **xanh** ở HEAD (23/23 `test_pdf.py`).
- Đầu dò đếm `FPDF_LoadMemDocument64` khác NULL và `FPDF_CloseDocument` qua cả 3 hàm công khai, chuỗi xen kẽ
  hỏng → 0 trang → mật khẩu người dùng → 0 trang → chỉ mật khẩu chủ → hỏng → 0 trang → 3 trang → 0 trang: mở 18, đóng 18,
  khớp từng handle (không rò, không đóng hai lần). Ánh xạ: hỏng `FILE_CORRUPT` (`__cause__` PdfiumError err 3, NO-124 còn
  log được), mật khẩu người dùng `PDF_UNREADABLE` (err 4), 0 trang `PDF_UNREADABLE` bất kể lịch sử, chỉ mật khẩu chủ đếm/khổ/dựng bình thường.
- Đời sống bộ đệm: `PdfDocument(raw)` không giữ `data` (`_data_holder` rỗng), nhưng cả 3 caller (`pdf_page_count`,
  `pdf_page_size_pt`, `render_pdf_page`) đóng tài liệu trong `finally` bên trong `with PDF_LOCK`, khi `data` vẫn là tham số
  sống; `complete.py:_check_pages(bytes(buffer), …)` giữ `bytes` suốt lời gọi. An toàn.
- Luồng/tiến trình: `GetLastError` là trạng thái toàn cục của PDFium, đọc ngay sau lần mở hỏng, trong `PDF_LOCK`; `pdf.py`
  là module duy nhất nhập pypdfium2 (`grep`), nên không ai ghi đè mã giữa hai lời gọi. Mỗi tiến trình có PDFium riêng.
- Trần số trang (`PDF_PAGE_MAX`, `apps/api/drawings/complete.py:_check_pages`) không đổi; nhận `len(pdf)` như cũ.
- R-19: cả 3 đường mở tài liệu đi qua `_open_document` → sửa một chỗ là đủ.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-05 | Lách `pdfium.PdfDocument(data)` bằng API thô có nêu **lý do** nhưng không nêu **đường nâng cấp**: khi nào bỏ cách lách (pypdfium2 sửa `_open_pdf` chỉ đọc mã lỗi khi `pdf` NULL và đóng tài liệu 0 trang). | `packages/vision/preprocess/pdf.py:40-43` | Thêm một câu: "bỏ khi pypdfium2 > 5.14 không còn đọc `FPDF_GetLastError` lúc mở thành công; test BUG-256 giữ hành vi". Không chặn. |
| 2 | Nit | RES-01 | Tài liệu trả về không ghim `data` (đường `bytes` của pypdfium2 giữ nó trong `_data_holder`); an toàn chỉ dựa vào hợp đồng docstring "đóng khi `data` còn sống". Mọi caller hiện tại đúng hợp đồng (đã kiểm). | `packages/vision/preprocess/pdf.py:44,55` | Giữ như hiện tại (hàm riêng tư, 3 caller trong cùng module); chỉ lưu ý khi thêm caller trả tài liệu ra ngoài khoá. |
| 3 | Nit | OBS-02 | `PdfiumError` tự dựng ghi mã số (`PDFium: 3`) thay vì chữ như pypdfium2 (`Data format error`), log NO-124 khó đọc hơn chút. | `packages/vision/preprocess/pdf.py:50` | Tuỳ chọn; mã số vẫn tra được. |
| 4 | Nit | MNT-03 | Comment phiên bản cũ "pypdfium2 5.13" (ngoài diff) lệch `uv.lock` 5.14.0 và docstring mới "5.14". | `packages/vision/preprocess/pdf.py:16-17`, `packages/vision/preprocess/tests/test_pdf.py:8` | Sửa chữ khi chạm file lần sau. |

Sổ nợ: tác giả không nêu nợ; `DEBT.md` không có dòng mở nào về `preprocess/pdf` hay nợ `[thứ tự chạy]` của `packages/vision`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |

Tổng: 4,97 / 5

## PHÁN QUYẾT: APPROVE
Không P0/P1/P2; điểm 4,97 ≥ 4,0. Sửa đúng gốc ở hàm mọi đường mở PDF đi qua: chỉ phân loại theo `FPDF_GetLastError`
khi mở trả NULL, tài liệu 0 trang thành `PDF_UNREADABLE` tường minh và được đóng (hết rò handle). Đã tự kiểm: test mới đỏ
trên `main`, xanh ở HEAD; số handle mở/đóng khớp qua mọi nhánh lỗi; cổng đầy đủ mã thoát 0 trên đúng HEAD 3a00289483d1.
Một P3 và ba Nit không chặn.
