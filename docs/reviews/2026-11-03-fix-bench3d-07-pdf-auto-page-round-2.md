# Review merge fix/bench3d-07-pdf-auto-page → main (lượt 2)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 30fb517e8c64 (PR #37; vòng sửa `335ca70e..30fb517e`, một commit)
- Cổng: phạm vi đích — lượt 2 chỉ soát vòng sửa (R-33b); vòng sửa không chạm migration, phụ thuộc hay tệp cấm. Bằng chứng: CI GitHub Actions run 41563519880 (workflow CI, head `30fb517e8c64611f3a8436f71f6a870f27d9f4f9` = đầu nhánh) kết luận **`failure`**: job `typecheck` hỏng ở bước 8 `openapi` ("`docs/contracts/openapi.json` lệch với bản vừa xuất"); mypy --strict đạt. Mọi job khác (`changes`, `lint`, `unit`, `integration`, `ml`, `perf`, `contract`, `build`, `coverage`) `success`. CodeQL 41563519832 `success`, Commits 41563519878 `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41563519880, `coverage_gate` đạt; CI đo cả repo): tổng dòng 99,31% · nhánh 97,50% — `apps/api/drawings` 99,74% / 98,21%; `packages/vision` 99,27% / 96,85%; `packages/db` 97,59% / 95,90%. Tất cả ≥ 90/90.
- `main` đã đi tiếp (PR #35, #36, #38: 13 commit từ 08947af4). PR vẫn `MERGEABLE` (`mergeStateStatus` `BLOCKED` chỉ vì check đỏ/chờ duyệt); `git merge-tree` sạch; không tệp nào trùng giữa nhánh và phần `main` mới; `main` không thêm migration nên sau gộp vẫn một head `r20261103_bench3d_07`.

## Phạm vi vòng sửa

- Cây sạch. Commit `30fb517e fix(preprocess): cap the ink probe render of the PDF page pick`, đúng Conventional Commits, có `Prompt: BENCH3D-07`. 8 tệp, +71/−5.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, migration. Không pragma, `noqa`, `type: ignore` mới, skip/xfail mới.

## Finding lượt 1

| # lượt 1 | Mức | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 SEC/PERF: ảnh dò mực không qua trần U06 | P1 | **Đã giải** | `pdf_vector.py:221-223`: `scale = effective_dpi(width_pt, height_pt, PLAN_PICK_DPI, PLAN_PICK_MAX_PIXELS) / POINTS_PER_INCH`, rồi `cap_pixels(..., PLAN_PICK_MAX_PIXELS)` (1 MP), đếm mực `mean(axis=2, dtype=np.float32)` — cùng mẫu `render_pdf_thumbnails`. Trang 30 000 pt → 2,4 dpi → ~1000 × 1000 px (~4 MB thay vì ~3,4 GB). Test `test_pick_plan_page_huge_scanned_page_stays_under_pixel_cap` (`test_pdf.py:304-322`) dựng **thật** PDF bìa quét trắng + trang quét 30 000 × 30 000 pt (`synthetic.scan_ops`), spy bọc `_render_page` thật và đo `shape` ảnh pdfium trả: `h·w ≤ PLAN_PICK_MAX_PIXELS · 1,01`, và vẫn chọn đúng trang 1 (trang quét có mực dưới DPI thấp). Bỏ `effective_dpi` thì test cấp phát 15 000² px và đỏ ở assert. A3/A4 ở 36 dpi < 1 MP nên kết quả bench không đổi. |
| 2 OBS: đổi trang không để lại dấu | P3 | **Đã giải** | `complete.py:203-204`: `_log.info("upload_page_auto_picked", extra={"upload_id", "pages", "picked"})` khi trang chọn khác `facts.page_index`; không khoá nào trùng thuộc tính `LogRecord`, không dữ liệu nhạy cảm. Test `test_full_flow_pdf_without_page_index_skips_cover` khẳng định đúng một bản ghi `(upload_id, 2, 1)`. |
| 3 TEST: khử trùng `page_auto` chưa có test | P3 | **Đã giải** | `test_init_retry_dedupes_omitted_and_explicit_page_index_apart` (`test_routes_init.py:322-336`): vắng `pageIndex` rồi `pageIndex: 0` → hai `id`; gửi lại vắng → cùng `id` đầu. Bỏ điều kiện `page_auto.is_(…)` ở `uploads.py:172` thì assert đầu đỏ. |
| 4 Nit PERF: mở tài liệu hai lần | Nit | Chấp nhận | Ghi vào `changes/BENCH3D-07.md` ("rẻ, để nguyên"). |
| 5 Nit DOC: docstring `InitUploadBody` | Nit | **Sửa nhưng làm đỏ cổng** | Xem finding #1 dưới. Đề xuất ở lượt 1 bỏ sót việc docstring này là `description` của schema trong OpenAPI — lỗi của đề xuất review, không phải của tác giả. |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | API / cổng bước 8 | Đổi docstring `InitUploadBody` đổi luôn `components.schemas.InitUploadBody.description` của OpenAPI xuất ra, nên bản xuất lệch bản tham chiếu `docs/contracts/openapi.json:3304` (vẫn câu cũ "`pageIndex` vắng = 0 (F-03), `mimeType` rỗng…"). CI run 41563519880 job `typecheck`: `verify --steps 3,8` → bước 8 `openapi` **hỏng**, run kết luận `failure`. Theo BE-00 §2 dòng 82, `docs/contracts/openapi.json` chỉ người điều phối sửa, nên tác giả không được tự chép bản mới vào. | `apps/api/drawings/schemas.py:91-93` | Cách gọn nhất: trả docstring lớp về đúng câu cũ (byte-for-byte), đưa ghi chú BENCH3D-07 ra comment `#` ngay trên `page_index` (comment không vào OpenAPI); docstring `_page_auto` (`uploads.py:148-150`) đã nói đủ ý. Cách kia: người điều phối chạy `run.sh openapi` rồi chép vào `docs/contracts/openapi.json` trong cùng lần gộp (BE-00 bước 8). Đổi xong thì CI phải xanh trên head mới. |

Không còn finding nào khác. Không P0, không P2.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 3,5 | 0,35 |
| TEST | 7% | 5 | 0,35 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,74 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Hai P3 và P1 lượt 1 đã được giải đúng gốc. Ảnh dò mực giờ đi qua `effective_dpi` và `cap_pixels` ở trần 1 MP; test dựng thật trang 30 000 pt và đo số điểm ảnh pdfium trả. Đã có log `upload_page_auto_picked` và test khử trùng vắng `pageIndex` khác `pageIndex: 0`. Nhưng cổng CI đỏ: run 41563519880 `failure` ở bước 8 `openapi`, vì docstring `InitUploadBody` mới đổi `description` của schema (và docstring này sửa theo Nit #5 do chính review lượt 1 đề xuất). Để được duyệt:
(1) trả docstring `InitUploadBody` (`schemas.py:91-93`) về đúng câu cũ và chuyển ghi chú BENCH3D-07 sang comment `#`, **hoặc** người điều phối cập nhật `docs/contracts/openapi.json` trong lần gộp;
(2) CI xanh trên head mới. Lượt 3 chỉ cần soát diff đó và run CI mới.
