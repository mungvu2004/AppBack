# Review merge fix/bench3d-07-pdf-auto-page → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 55bed5e42146 (PR #37; merge-base = `origin/main` 08947af4e21d, PR `MERGEABLE`)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41558950830) — người dùng quyết định dùng CI thay `run.sh verify` (như các review bench-3d trước). Run 41558950830 (workflow CI, head `55bed5e421463b6808dd2bfc29855af8c29b002b` = đầu nhánh): `changes`, `lint`, `typecheck`, `unit` (2 shard), `integration` (5 shard, gồm `verify --steps 6 (migrations)` đạt: `lint_migrations` đạt 41 revision, `migrate_check` đạt), `ml` (3 shard), `perf`, `contract`, `build`, `coverage` đều `success`. Run 41558951104 (CodeQL) `success`; run 41558950970 (Commits) `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41558950830, `tools.coverage_gate` đạt, case_gate đạt): tổng dòng 99,31% · nhánh 97,50% — gói bị chạm: `apps/api/drawings` 99,74% / 98,65%; `packages/vision` 99,26% / 96,85%; `packages/db` 97,59% / 95,90%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md`; trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. 2 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-07`:
  `37502451 feat(drawings): pick the plan page of a PDF when the client sends none`,
  `55bed5e4 fix(preprocess): read the segment cap at call time in _walk_objects`.
- 11 tệp, +340/−19 (mã logic ~160 dòng) — dưới 400, không cần tách.
- Có `changes/BENCH3D-07.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa`, `type: ignore` mới, skip/xfail mới, không hạ ngưỡng.

## Hai P1 của PR #33 (`2026-11-03-fix-bench3d-01-geometry-checks.md` #1, #2)

| P1 cũ | Trạng thái | Bằng chứng |
|---|---|---|
| #1 PERF/RES: `pick_plan_page` chặn vòng sự kiện dưới `PDF_LOCK` | **Đã giải** | `complete.py:239` `await asyncio.to_thread(_check_pages, bytes(buffer), facts)` — cả đếm trang lẫn dò trang ra luồng khác (cùng mẫu `thumbnails.py:48`). `_is_drawing` truyền `limit=PLAN_MIN_SEGMENTS` vào `_walk_objects` (`pdf_vector.py:212`) và không gọi `get_textpage`. Commit 55bed5e4 bỏ default `limit=_MAX_SEGMENTS` bị bind lúc import, thành keyword bắt buộc. Test `test_complete_picks_plan_page_off_the_event_loop` (spy ghi `threading.get_ident()` ≠ luồng vòng sự kiện) và `test_pick_plan_page_stops_reading_at_plan_min_segments` (đúng 100 lần `_path_segments`, `get_textpage` bị cấm). Docstring `_check_pages` đã đúng. Còn một lỗ ở đường dựng ảnh 36 dpi — xem finding #1 (khác P1 cũ: bộ nhớ, không phải vòng sự kiện). |
| #2 LOG/API: ghi đè `pageIndex` 0 tường minh, `crop` lệch trang | **Đã giải** | #5 ghi `uploads.page_auto = "page_index" not in body.model_fields_set` (`uploads.py:148-150`, `:222`); `load_upload` tính `auto_page = page_auto IS TRUE AND crop_corners IS NULL` (`uploads.py:137`), nên `pageIndex: 0` tường minh (`false`), có `crop`, và dòng cũ (`NULL`) đều giữ trang. `_check_pages` chỉ gọi `pick_plan_page` khi `auto_page` và > 1 trang (`complete.py:197`). Test: `test_full_flow_pdf_explicit_page_zero_on_cover_is_kept` (có sẵn, bìa + mặt bằng, `pageIndex: 0` → 0), `test_full_flow_pdf_explicit_page_zero_is_not_auto` (`page_auto` false), `test_full_flow_pdf_without_page_index_but_crop_keeps_page_zero`, `test_full_flow_pdf_without_page_index_skips_cover` (→ 1). FE @ `origin/master`: PDF nhiều trang chỉ tải khi đã chọn trang (`isAwaitingPage`), luồng tách căn gửi `pageIndex: 0` tường minh, nên FE không bị đổi trang; chỉ client vắng `pageIndex` (bench, API trực tiếp, FE khi không đếm được trang) mới được tự chọn. |

## Soát nội dung

- **Migration (DB, BE-00 §6.1)** `r20261103_bench3d_07_upload_page_auto.py`: tên tệp và `revision = "r20261103_bench3d_07"` (20 ký tự ≤ 32) đúng mẫu `r<yyyymmdd>_<mã>_<việc>`; một revision cho prompt; `down_revision = "r20261102_aid_01"` là head duy nhất của `origin/main` (đã quét `versions/`: sau nhánh chỉ còn 1 head `r20261103_bench3d_07`). Expand thuần: `add_column` `BOOLEAN NULL`, không default, không backfill, không index — chỉ sửa catalog, khoá `ACCESS EXCLUSIVE` tức thời. `downgrade()` thật (`drop_column`, được miễn vì nằm trong thân `downgrade`). Model `UploadRow.page_auto: Mapped[bool | None]`, `nullable=True` khớp; `migrate_check` (model khớp DB, vòng up/down) đạt trên CI. Tương thích ngược: bản API cũ bỏ qua cột; dòng cũ `NULL` → giữ trang.
- **Khử trùng init** (`uploads.py:172`): thêm `page_auto IS <bool>` để init vắng `pageIndex` và init `pageIndex: 0` không bị gộp — đúng, nhưng chưa có test (finding #3).
- **`_check_pages`** giữ thứ tự cũ (trần trang → `pageIndex` ngoài khoảng) rồi mới dò; `VisionError` của dò trang → `AppError` cùng mã (thành dòng `rejected`, test `test_check_pages__plan_page_pick_failure_is_app_error`). Trang chọn ghi `row.page_index` trong `_finish` dưới khoá dòng, trước `start_run`; mọi chỗ đọc sau đó (`quality/service.py`, `pipeline_orchestrate/start.py`, `preprocess.py`) đọc `uploads.page_index` nên nhất quán. Gọi lại #7 sau 5xx: dò lại cùng tệp → cùng kết quả (tất định).
- **Wire/hợp đồng:** không đổi thân, `openapi.json`, `APPFRONT_SHA`; job `contract` xanh. Nghĩa của "vắng `pageIndex`" đổi với PDF nhiều trang không `crop` (finding #5 về câu chữ).
- **SEC:** không đầu vào mới ngoài cờ suy từ `model_fields_set`; đường dựng ảnh mới bỏ qua trần U06 (finding #1).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | SEC / PERF | Dựng ảnh dò mực **không qua trần điểm ảnh U06**. `_is_drawing` gọi `_render_page(pdf, page_index, PLAN_PICK_DPI / POINTS_PER_INCH)` với tỉ lệ cố định, không `effective_dpi`/`cap_pixels` — trong khi mọi đường dựng khác (`render_pdf_page`, `render_pdf_thumbnails`, `pdf.py:153-176`) đều hạ DPI theo khổ trang, và `docs/security/asvs-checklist.md` B-07 ("Bom PDF: số trang và khổ trang bị chặn") dựa vào đúng bất biến đó. PDFium nhận khổ trang tuỳ ý (đã thử `pypdfium2` 5.14 trong `f14-api-1`: trang 30 000 pt → `get_size() = (30000, 30000)`). Một tệp vài KB, ≥ 2 trang, không gửi `pageIndex`, trang 0 khổ 30 000 pt có một ảnh 2×2 phủ trang (< 100 nét, ảnh ≥ 30 %) → dựng 15 000 × 15 000 px: bitmap BGRx ~900 MB + bản chép RGB ~675 MB + `.mean(axis=2)` float64 ~1,8 GB ≈ 3,4 GB trong **tiến trình API** (container `f14-api-1` không đặt `Memory`, chung trần WSL 10 GB của cả stack), lặp được tới 20 trang mỗi lượt, giữ `PDF_LOCK` suốt (ảnh nhỏ #thumbnails, xử lý chất lượng cùng tiến trình đứng chờ). Khổ nhỏ hơn (14 400 pt, giới hạn Acrobat) vẫn ~0,8 GB mỗi trang. Bất kỳ ai có `floor.upload` gọi được. | `packages/vision/preprocess/pdf_vector.py:217` | Tính tỉ lệ bằng trần: `scale = effective_dpi(width_pt, height_pt, PLAN_PICK_DPI, PLAN_PICK_MAX_PIXELS) / POINTS_PER_INCH` với `PLAN_PICK_MAX_PIXELS` cỡ 1 000 000 (A3 ở 36 dpi chỉ ~0,25 MP nên không đổi kết quả bench), qua `cap_pixels` như `render_pdf_thumbnails`; đếm mực trên một kênh hoặc `mean(axis=2, dtype=np.float32)`. Thêm test: trang 30 000 pt có ảnh phủ trang → `_render_page` nhận tỉ lệ ≤ trần (spy), `pick_plan_page` vẫn trả kết quả. |
| 2 | P3 | OBS | BE âm thầm đổi trang mà không để lại dấu: không log, không trường nào cho thấy trang đã được tự chọn (chỉ `uploads.page_index` khác 0). Khi heuristic chọn sai (trang bảng thống kê ≥ 100 nét đứng trước mặt bằng, mặt bằng vector < 100 nét) thì người vận hành không truy được vì sao lượt dựng ra trang khác. | `apps/api/drawings/complete.py:197-202` | Log có cấu trúc `upload_page_auto_picked` (`upload_id`, `pages`, `picked`) khi `pick_plan_page` trả khác `facts.page_index`. |
| 3 | P3 | TEST | Điều kiện khử trùng mới `UploadRow.page_auto.is_(_page_auto(body))` không có test: hai init giống hệt, một vắng `pageIndex` một gửi `pageIndex: 0`, phải ra hai lượt khác nhau. Bỏ dòng này thì mọi test hiện có vẫn xanh (là điều kiện SQL, độ phủ nhánh không bắt được). | `apps/api/drawings/uploads.py:172` | Thêm test cạnh `test_init_crop_retry_dedupes_only_same_crop`: init vắng `pageIndex` rồi init `pageIndex: 0` cùng tệp → hai `id` khác nhau; lặp lại init vắng → cùng `id`. |
| 4 | Nit | PERF | `_check_pages` mở tài liệu hai lần dưới hai lượt `PDF_LOCK` (`_page_count` rồi `pick_plan_page`). Rẻ so với dò trang. | `apps/api/drawings/complete.py:192-200` | Không cần đổi; nếu chạm lại thì cho `pick_plan_page` nhận số trang đã đếm trong cùng lượt mở. |
| 5 | Nit | DOC | Docstring `InitUploadBody` vẫn ghi "`pageIndex` vắng = 0 (F-03)" (và schema sinh ra vẫn khai `default: 0`), nay sai với PDF nhiều trang không `crop`. | `apps/api/drawings/schemas.py:91` | Sửa câu: "vắng = 0, trừ PDF nhiều trang không `crop`: #7 tự chọn trang bản vẽ (BENCH3D-07)". |

Một P1 chặn merge. Không có nợ tác giả nêu; P3/Nit nếu không sửa trong nhánh này thì ghi vào `changes/BENCH3D-07.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 3 | 0,75 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 3,5 | 0,35 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,09 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Hai P1 của PR #33 đã được giải đúng gốc: dò trang chạy trên `asyncio.to_thread`, dừng ở `PLAN_MIN_SEGMENTS`, không trích chữ; chỉ tự chọn khi client **vắng** `pageIndex` và không `crop` (cờ `uploads.page_auto` từ `model_fields_set`), có test cho từng ca. Migration đúng §6.1 (expand thuần, một head, `downgrade` thật, `migrate_check` đạt). CI run 41558950830 `success` trên đúng head 55bed5e42146, độ phủ tổng và gói bị chạm ≥ 90/90. Còn một P1 chưa waiver, phải sửa để được duyệt:
(1) `_is_drawing` (`pdf_vector.py:217`) dựng trang ở 36 dpi cố định, bỏ qua trần điểm ảnh U06 — PDF vài KB với trang khổ lớn làm tiến trình API cấp phát nhiều GB dưới `PDF_LOCK`. Hạ tỉ lệ bằng `effective_dpi` (+ `cap_pixels`) với trần nhỏ, kèm test trang khổ lớn.
Ba P3/Nit còn lại không chặn merge.
