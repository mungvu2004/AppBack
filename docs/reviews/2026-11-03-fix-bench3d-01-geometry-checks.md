# Review merge fix/bench3d-01-geometry-checks → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 63c67a9e5204 (merge-base e86e0b41c3de; `origin/main` hiện 167ab02a6be8, gộp thử sạch, không tệp chung)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41481834926) — người dùng quyết định dùng CI thay `run.sh verify` (máy bận chụp 3D). Run 41481834926 "CI" `success` trên head SHA 63c67a9e5204 = đầu nhánh (`origin/fix/bench3d-01-geometry-checks`): changes, lint, typecheck, unit, integration, ml, contract, build, coverage đều `success`. Run 41481834686 "CodeQL" `success`. "Commits": run 41481834696 `failure` (tiêu đề PR cũ sai mẫu), run 41483919473 `success` sau khi đổi tiêu đề, cùng SHA. CI chạy trên merge ref với base b0067e57; main sau đó chỉ thêm PR #34 (chỉ `ci`/công cụ cổng, không chạm tệp của nhánh).
- Độ phủ (job coverage 125407556581): tổng dòng 99,31% · nhánh 97,48% — gói bị chạm: `apps/api/drawings` 99,74/98,65 · `apps/worker/pipeline_build` 98,06/92,48 · `apps/worker/pipeline_quality` 99,69/98,33 · `packages/vision` 99,26/96,84. Đều ≥ 90/90.

## Phạm vi

- Cây sạch. 3 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-01`: `82595a2c feat(pipeline_quality)…`, `c8f7f779 fix(pipeline_quality)…`, `63c67a9e feat(drawings)…`. Có `changes/BENCH3D-01.md`.
- 16 tệp, +748/−101 (≈ 390 dòng logic, phần còn lại là test; 85 dòng của `geometry.py` là chuyển sang `clusters.py`). Dưới trần MNT-05.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa`, skip/xfail mới; `type: ignore[import-untyped]` mới ở `synthetic.py` có mã và lý do, giống dòng sẵn có ở `pdf_vector.py`.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | PERF / RES | `pick_plan_page` chạy **đồng bộ trên vòng sự kiện** của API: `_build_original` (async) gọi thẳng `_check_pages` → `pick_plan_page`, không `asyncio.to_thread`. Hàm giữ `PDF_LOCK` (`threading.Lock`), với mỗi trang đến trang bản vẽ đầu tiên gọi `_read_page` — đi **hết** đối tượng trang (tới `_MAX_SEGMENTS` = 200 000 đoạn qua ctypes) và trích cả chữ (`get_text_range`, không dùng tới) — rồi có thể dựng ảnh 36 dpi. Mọi PDF nhiều trang với `pageIndex` 0 đều trả giá này, kể cả khi trang 0 đã là bản vẽ (đi hết trang 0 rồi mới trả 0). Trong lúc đó mọi request khác của tiến trình API đứng; nếu luồng khác (ảnh nhỏ, xử lý chất lượng) đang giữ `PDF_LOCK` thì vòng sự kiện chờ khoá luôn. Không trần thời gian. (Docstring `_check_pages` nói `pdf_page_count` chạy trên `to_thread` ở người gọi — không đúng từ trước, nhưng đếm trang thì rẻ; dựng/duyệt trang thì không.) | `apps/api/drawings/complete.py:238` (gọi), `complete.py:196-201`, `packages/vision/preprocess/pdf_vector.py:196-209` | `page_index = … await asyncio.to_thread(_check_pages, bytes(buffer), facts)`; trong `_is_drawing` dừng đi đối tượng ngay khi đủ `PLAN_MIN_SEGMENTS` (truyền trần vào `_walk_objects`) và bỏ trích chữ; sửa docstring cho đúng. Thêm test khẳng định lời gọi chạy ngoài luồng vòng sự kiện (ví dụ `pick_plan_page` giả ghi `threading.get_ident()`). |
| 2 | P1 | LOG / API | Tự đổi trang **ghi đè lựa chọn tường minh** `pageIndex` 0. Nhánh coi 0 là "không chọn", nhưng FE chặn tải PDF nhiều trang cho tới khi người dùng chọn trang (`isAwaitingPage`, `AppFront/src/screens/upload/FloorUploadScreen/useFloorUploadScreen.ts:299-305`; `apps/api/drawings/thumbnails.py:3`), và luồng tách căn gửi `pageIndex: 0` kèm ghi chú "lấy trang 1" cho người dùng (`useApartmentSplit.ts:150-156`). Vậy mọi `pageIndex` 0 của PDF nhiều trang từ FE đều là lựa chọn của người dùng; khi trang đó trượt heuristic (trang brochure có ảnh mặt bằng < 30 % trang, mặt bằng vector < 100 đoạn thẳng) BE âm thầm dựng trang khác. Có `crop` (MULTI-FLOOR-01, tỉ lệ của trang đã chọn) thì vùng cắt còn áp lên trang khác. Test `test_full_flow_pdf_explicit_page_index_is_kept` chỉ phủ trang ≠ 0. | `apps/api/drawings/complete.py:196-201`, `complete.py:296` | Chỉ tự chọn khi client **vắng** `pageIndex`: ở #5 ghi `"page_index" in body.model_fields_set` vào dòng `uploads` (cột cờ mới, migration) và `_check_pages` chỉ gọi `pick_plan_page` khi cờ đó báo vắng **và** `crop_corners is None`. Cách không đụng DB: bỏ ghi đè ở #7, chuyển heuristic sang endpoint ảnh nhỏ thành "trang gợi ý" để FE chọn sẵn. Thêm test: `pageIndex: 0` tường minh (có và không `crop`) với trang 0 là bìa → giữ 0. |
| 3 | P2 | LOG | Đảo nền tối chỉ dựa vào trung vị độ sáng tuyệt đối < 128: ảnh chụp điện thoại giấy trắng thiếu sáng (nền xám ~100–120, nét đen) cũng có trung vị < 128 nên bị đảo thành nét sáng trên nền tối — đúng loại đầu vào xấu mà bước này định sửa. `load_raster` dùng chung nên hệ quả lan cả sang nạp dữ liệu huấn luyện/đánh giá (`apps/ml/training_segformer/data.py:43`, `apps/ml/training_yolo/dataset.py:56`, `apps/ml/ml_eval/evaluate.py:33`, `apps/worker/datasets_cubicasa/importer.py:288`); `changes/BENCH3D-01.md` không nhắc. Test chỉ có hai ảnh tổng hợp cực trị (nền 10 và 240). | `packages/vision/preprocess/raster.py:108` | Thêm điều kiện cực tính: chỉ đảo khi nét (phần thiểu số) **sáng hơn** nền, ví dụ `p95 - median > median - p5` trên lưới thưa đã lấy; thêm test ảnh nền xám 110 nét đen 20 → không đảo. Ghi vào change note việc `load_raster` của ML cũng đảo. |
| 4 | P3 | OBS | Tóm tắt và log lệch nhau khi cờ nghiêm trọng đến từ kiểm hình học: `hasCritical: true` nhưng `criticalCount: 0` (test `test_run_quality_records_summary_clean` khẳng định đúng trạng thái đó), log `quality_critical_issues` ghi `issue_count = len(report.issues)` = 0. | `apps/worker/pipeline_quality/service.py:142`, `service.py:201-202` | Cộng số kiểm `critical` vào `criticalCount` (hoặc thêm `criticalChecks`) và đưa `checks` vào `extra` của log. |
| 5 | P3 | LOG | `ROOMS_WITHOUT_DOOR` bật `critical` khi tầng không có ô mở nào, kể cả khi mọi phòng là loại miễn (`loggia`, `corridor`); nhánh có ô mở thì đã lọc miễn. | `apps/worker/pipeline_quality/checks.py:147-148` | Lọc `DOORLESS_USAGES_EXEMPT` trước, rồi mới xét "không ô mở"; không còn phòng → `None`. |
| 6 | Nit | R-01 | Hàm mới thiếu docstring: `box_union`, `box_area` (nay là API công khai của `clusters.py`), `GeometryCheck.to_wire`, `_line`, `_inside_point`, `_parallel`, `_room_usage_unknown`. | `apps/worker/pipeline_build/clusters.py:57,61`; `apps/worker/pipeline_quality/checks.py:54,58,63,90,159` | Thêm một dòng docstring mỗi hàm khi chạm lại. |
| 7 | Nit | MNT | Docstring trỏ đường ngoài repo `F:/runs/bench-3d/tools/score.py` — người đọc repo không mở được. | `apps/worker/pipeline_quality/checks.py:4` | Nêu tên luật (W1, W4) và ngưỡng, bỏ đường máy cục bộ. |

Không có nợ tác giả nêu; không cần dòng nợ mới cho P1 (phải sửa trước merge). P2 #3 nếu không sửa trong nhánh này thì phải có dòng nợ.

## Ghi nhận tốt

- `geometry_checks` thuần, ngưỡng là hằng có tên kèm lý do; tách khỏi `check_integrity` nên không chặn lượt lưu của người dùng. Hệ quả của `hasCritical` chỉ là lý do readiness `criticalIssues` trước khi tầng được duyệt (`apps/api/spatial_read/readiness.py:63-65`), không chặn ghi.
- Chuyển `_clusters`/`_box_gap`/vùng U57 sang `clusters.py` giữ nguyên hành vi bước dựng (cùng thuật toán, cùng hằng), bước kiểm dùng lại thay vì chép (R-07).
- `quality.json` thêm khoá `checks`: không người đọc nào trong `apps/`/`packages/` phân tích tệp này với lược đồ chặt; job `contract` xanh.
- Test kiểm hình học có cả ca âm (dưới ngưỡng, cụm xa nhỏ, phòng nhỏ lòi ra chỉ báo); `pick_plan_page` có test bìa chữ, bìa quét trắng, trang quét, rơi về 0, trần `max_pages`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 3 | 0,30 |
| RES | 10% | 4 | 0,40 |
| DB/API | 10% | 4 | 0,40 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,17 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Cổng CI xanh và độ phủ đạt, phần kiểm hình học đúng hướng, nhưng còn hai P1 chưa waiver ở đường tải PDF:
(1) `pick_plan_page` chạy đồng bộ trên vòng sự kiện API và dưới `threading.Lock` — phải đưa `_check_pages` ra `asyncio.to_thread` và cho `_is_drawing` dừng sớm ở `PLAN_MIN_SEGMENTS`, bỏ trích chữ;
(2) tự đổi trang ghi đè `pageIndex` 0 mà FE gửi như lựa chọn tường minh (và có thể làm `crop` lệch trang) — chỉ tự chọn khi client vắng `pageIndex` và không có `crop`, hoặc chuyển thành gợi ý trang cho FE; kèm test `pageIndex: 0` tường minh giữ nguyên.
P2 #3 (đảo nhầm ảnh chụp thiếu sáng) sửa trong nhánh hoặc ghi nợ. Sau khi sửa, review lượt 2 phạm vi đích trên diff vòng sửa + CI mới cùng SHA.
