# Review merge fix/bench3d-01-geometry-checks → main (lượt 2)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 86ecf4c1b3b4 (= `origin/fix/bench3d-01-geometry-checks`; vòng sửa `0f193bd8..86ecf4c1`, một commit)
- Cổng: phạm vi đích — lượt 2 chỉ soát diff vòng sửa. Diff này không chạm điều kiện "đầy đủ" nào của R-33b: không migration, không hợp đồng, không khoá/giao dịch; nó chỉ gỡ mã đã thêm ở lượt 1. Bằng chứng vẫn là cổng đầy đủ: CI GitHub Actions run 41492549287 `success` trên head SHA 86ecf4c1b3b4 = đầu nhánh, mọi job `success` (changes, lint, typecheck, build, perf, unit-shards 1-2 + unit, integration-shards 1-5 + integration, ml-shards 1-3 + ml, contract, coverage). CodeQL run 41492549476 `success`; Commits run 41492549438 `success`. Người dùng quyết định dùng CI thay `run.sh verify` cục bộ.
- Độ phủ (job coverage 125442543756): tổng dòng 99,31% · nhánh 97,48%. File đổi theo gói: `apps/api/drawings` 99,74/98,65 · `apps/worker/pipeline_build` 98,11/92,69 · `apps/worker/pipeline_quality` 99,69/98,33 · `packages/vision` 99,25/96,82. Đều ≥ 90/90.

## Phạm vi vòng sửa

- Commit `86ecf4c1 fix(drawings): keep the client page, fix inversion and quality counts`: dòng đầu đúng mẫu, có `Prompt: BENCH3D-01`. Cây sạch.
- 14 tệp, +104/−199. Không pragma, `noqa`, `type: ignore`, skip/xfail mới. Không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`.
- `apps/api/drawings/complete.py`, `packages/vision/preprocess/pdf_vector.py`, `apps/api/drawings/tests/test_routes_complete.py`, `packages/vision/preprocess/tests/test_pdf.py` **trùng byte với merge-base e86e0b41** (`git diff --quiet e86e0b41 HEAD -- …` thoát 0). Cả nhánh giờ không còn đổi gì ở hai tệp nguồn này.

## Soát finding lượt 1

| # lượt 1 | Mức | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 PERF/RES: `pick_plan_page` chặn vòng sự kiện | P1 | **Đã giải** (gỡ) | `pick_plan_page`, `_is_drawing`, `_read_page` và các hằng `PLAN_*` đã bị xoá; `complete.py`/`pdf_vector.py` trùng merge-base nên đường #7 trở lại như `main`. `git grep pick_plan_page` chỉ còn khớp ở change note và phán quyết lượt 1. |
| 2 LOG/API: ghi đè `pageIndex` 0 tường minh, lệch `crop` | P1 | **Đã giải** (gỡ) | `uploads.page_index` lại là đúng trang client gửi. Test mới `test_full_flow_pdf_explicit_page_zero_on_cover_is_kept` (`apps/api/drawings/tests/test_upload_flow.py:117-132`): PDF bìa chữ + trang mặt bằng, `page_index=0` → dòng lưu 0. Test này sẽ đỏ nếu logic tự chọn quay lại. |
| 3 LOG: đảo nhầm ảnh chụp thiếu sáng | P2 | **Đã giải** | `raster.py:113-121`: ngoài trung vị < 128 còn yêu cầu số điểm ảnh sáng hơn nền rõ (> 32 mức) **nhiều hơn** số điểm ảnh tối hơn nền rõ, tức nét sáng trên nền tối. Test `test_load_raster_dim_photo_of_white_paper_is_kept` (nền 110, nét 20 → giữ nguyên); hai test cực trị cũ vẫn giữ. Change note đã ghi `load_raster` của ML cũng đảo. |
| 4 OBS: `criticalCount` 0 khi `hasCritical` true | P3 | **Đã giải** | `service.py:138-142` `_critical_count` cộng lỗi toàn vẹn `critical` với kiểm hình học `critical`; dùng cho cả tóm tắt lẫn log (`service.py:216`), log có thêm `checks`. Hai test service đã cập nhật khẳng định đếm theo `artifact["checks"]`. |
| 5 LOG: `ROOMS_WITHOUT_DOOR` critical khi chỉ có phòng miễn | P3 | **Đã giải** | `checks.py:152` lọc `DOORLESS_USAGES_EXEMPT` trước cả nhánh "không ô mở". Test `test_only_exempt_rooms_without_any_opening__no_check`. |
| 6 Nit R-01: thiếu docstring | Nit | **Đã giải** | Đủ docstring cho `box_union`, `box_area`, `to_wire`, `_line`, `_inside_point`, `_parallel`, `_room_usage_unknown`. |
| 7 Nit MNT: đường `F:/runs/...` trong docstring | Nit | **Đã giải** | `checks.py:4` chỉ còn nêu W1/W4 và ngưỡng. |

## Gỡ bỏ có để lại mã chết hay đổi hợp đồng?

- **Mã chết:** không còn. Lượt 1 thêm import `POINTS_PER_INCH`/`_render_page` và mục `__all__` `pick_plan_page` vào `pdf_vector.py`; nay tệp đã trùng merge-base nên chúng không còn. Ở `synthetic.py` đã xoá `SCAN_OPS`/`BLANK_SCAN_OPS`. Phần còn lại (`COVER_OPS`, `PLAN_OPS`, `join_pdfs`) vẫn được test mới ở `test_upload_flow.py` dùng (`git grep`). Lint (ruff) và typecheck xanh trên CI.
- **Hợp đồng:** không đổi. #5/#7 trùng `main`, `openapi.json` không chạm, job `contract` `success`. Thay đổi duy nhất mà bên ngoài nhìn thấy vẫn là khoá `checks` mới trong `quality.json`/`quality_summary` (đã xét ở lượt 1, không có người đọc lược đồ chặt) và việc `criticalCount` nay đếm cả kiểm hình học. Cột này không được API trả ra; readiness chỉ đọc `hasCritical` (`apps/api/spatial_read/readiness.py:64`).

## Finding mới
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | PERF | `_light_paper` nay tính `pixels.max(axis=2)` trên **toàn ảnh** trước khi xét trung vị. Mọi `load_raster` (preprocess worker, vòng nạp dữ liệu huấn luyện/đánh giá ML) vì thế tốn thêm một mảng H×W và một lượt quét đủ ảnh, kể cả với giấy sáng là ca phổ biến. Ở trần 40 MP (`DEFAULT_MAX_PIXELS`), đó là ~40 MB tạm. Trước vòng sửa chỉ quét 1/16 lưới. | `packages/vision/preprocess/raster.py:113-114` | Tính trung vị trên `pixels[::4, ::4].max(axis=2)` trước; chỉ khi trung vị < 128 mới tính `brightness` toàn ảnh để đếm hai tỉ lệ. |
| 2 | Nit | OPS | Gỡ `pick_plan_page` nghĩa là ca bench two-page-ch04 (PDF bìa chữ, gửi không kèm `pageIndex`) vẫn ra `NOT_A_FLOOR_PLAN`. Change note có ghi, nhưng chưa có việc tiếp nào được đặt (ví dụ trang gợi ý ở endpoint ảnh nhỏ cho FE chọn sẵn). | `changes/BENCH3D-01.md:12-16` | Điều phối ghi một dòng việc tiếp khi lập đợt sau; không chặn merge. |
| 3 | Nit | MNT | Docstring `_check_pages` nói `pdf_page_count` chạy trên `asyncio.to_thread` ở người gọi, trong khi `_build_original` gọi đồng bộ. Lỗi có sẵn trên `main`, không thuộc nhánh này. | `apps/api/drawings/complete.py:182` (không thuộc diff) | Sửa câu chữ khi chạm lại tệp. |

Không có P0/P1/P2 còn mở. Không có nợ mới cần dòng nợ.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,83 / 5

## PHÁN QUYẾT: APPROVE

Hai P1 lượt 1 được giải bằng cách gỡ hẳn tính năng tự chọn trang. Đường #7 trở lại đúng `main` (trùng byte với merge-base), có test chốt việc giữ `pageIndex` 0 tường minh. P2 đảo ảnh đã thêm điều kiện cực tính kèm test ảnh thiếu sáng. P3 và Nit lượt 1 đều đã sửa. Việc gỡ không để lại mã chết và không đổi hợp đồng. CI run 41492549287 `success` trên đúng head 86ecf4c1b3b4, độ phủ tổng và các gói bị chạm ≥ 90/90. Còn một P3 hiệu năng nhỏ ở `_light_paper` và hai Nit, không chặn merge.
