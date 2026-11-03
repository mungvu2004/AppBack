# Review merge fix/bench3d-08-sheet-checks → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: a1ddaf1dff58 (PR #38; merge-base = `origin/main` 08947af4e21d, PR `MERGEABLE`)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41558958644). Người dùng duyệt dùng CI thay `run.sh verify`, như các review bench-3d trước. Run 41558958644 (workflow CI, head `a1ddaf1dff58977f8289b19ee02cceff38fc66da` = đầu nhánh) kết luận `success`: `changes`, `lint`, `typecheck`, `unit` (+2 shard), `ml` (+3 shard), `integration` (+5 shard), `perf`, `build`, `contract`, `coverage` đều đạt. Run 41558958647 (CodeQL) đạt, run 41558958658 (Commits) đạt. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41558958644, `tools.coverage_gate` đạt, case gate đạt): tổng dòng 99,31% · nhánh 97,50%. Gói bị chạm: `apps/worker/pipeline_quality` 99,69% / 98,33%. Đều ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52), nên trọng số chấm lấy theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. Một commit `a1ddaf1d fix(pipeline-quality): flag sheets whose walls span a whole tower`, đúng Conventional Commits, có trailer `Prompt: BENCH3D-08`.
- 4 tệp, +33/−4 (mã logic ~10 dòng). Có `changes/BENCH3D-08.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, không `noqa` trần, không `type: ignore`, không skip/xfail, không hạ ngưỡng.

## Soát nội dung

- `_multiple_plans` (`apps/worker/pipeline_quality/checks.py:132-151`): luật cũ (≥ 2 vùng tường tách xa, mỗi vùng ≥ 15 % tổng dài) giữ nguyên. Luật mới: hộp bao đường tim của **mọi** tường có cạnh dài > `PLAN_MAX_SPAN_MM` = 35 000 mm thì cũng bật `MULTIPLE_PLANS` (critical). `detail` thêm `spanMm`. Tường < 2 vẫn trả `None`. Biên `span == 35 000` không bật, khớp chữ "dài quá".
- Hệ quả khi bật: `hasCritical` → readiness `needsReview` với lý do `criticalIssues` (`apps/api/spatial_read/readiness.py:62-64`) cho tới khi tầng được duyệt hết. Cờ không chặn chỉnh sửa hay lưu, chỉ báo người dùng phải xem lại. FE @ origin/master không đọc mã kiểm hay `spanMm` (chỉ thấy `spanMm` cục bộ của histogram/overlay, không liên quan), nên không đổi hợp đồng. Job `contract` xanh.
- Test: `test_joined_units_spanning_whole_tower__multiple_plans` (40 m, một cụm, khẳng định đúng `detail`) và `test_large_single_house__single_plan` (30 × 12 m không bật). `test_service` cập nhật vì lớp mẫu 48 tường nối đuôi dài 48 m nay vượt ngưỡng.
- SEC/CON/RES/PERF: hàm thuần, không đầu vào mới, không I/O. Thêm một `MultiLineString(...).bounds` O(n), không đáng kể.
- `ROTATED_PLAN` không làm, lý do ghi trong commit và `changes/BENCH3D-08.md` (cần ảnh trang). Chấp nhận.

### Ngưỡng 35 m xét theo giá trị

1. **Nhà đơn lớn (dương tính giả).** Ngưỡng tuyệt đối đo trên hộp bao **mọi** tường dựng được, kể cả tường rào, tường sân, tường ranh lô nếu bước dựng giữ chúng. Ranh lô bao quanh nhà nên hộp của nó chồng lên vùng chính, và U57 không bao giờ bỏ nó (`apps/worker/pipeline_build/geometry.py:330-346` chỉ bỏ cụm *tách xa* và nhỏ). Vậy với bản vẽ có ranh lô, luật đo chiều dài lô chứ không đo chiều dài nhà. Nhà ống sâu (phố cổ 40–60 m), biệt thự lô lớn, nhà vườn hay shophouse liền kề vẽ cả dãy đều vượt 35 m mà vẫn là một mặt bằng. Bench nhóm A (căn hộ, dài nhất 18 m) không có loại nào như vậy, nên con số "0 dương tính giả" chỉ đúng cho căn hộ. Phạm vi sản phẩm hiện là căn hộ nhiều tầng/nhiều tờ, nên rủi ro này có thật nhưng còn hẹp.
2. **Phụ thuộc tỉ lệ ước lượng.** `span` tính bằng mm theo tỉ lệ của pipeline, mà tỉ lệ này có thể là ước từ bề dày tường hay cửa. Chính `build.py:80-85` ghi bề dày dò được ở tỉ lệ đúng nằm trong 95–273 mm quanh đích 150 mm, và `build.py:87-89` ghi ước theo tường lệch tới 42 %. Tỉ lệ phóng 1,58× (tường mảnh 95 mm bị ép lên 150) sẽ đẩy một căn 23 m lên 36 m (tính tay, chưa gặp trên bench). Ca dài nhất bench A (18 m) chỉ chịu được sai số ≤ 1,94×. Đây là kiểm đầu tiên trong `checks.py` dùng ngưỡng mm tuyệt đối. Các kiểm khác (vỏ hở, mảnh vụn, tỉ lệ phòng không cửa) không đổi khi tỉ lệ đổi, hoặc dùng sai số nhỏ cỡ 30–200 mm. Bước quality không đọc `scaleBasis`/`scaleChecks` của `layer.json`, nên không biết tỉ lệ đang tạm hay hai ước đang vênh. Lúc tỉ lệ còn tạm thì readiness đã có `scaleUnresolved` nên thiệt hại thêm nhỏ. Nhưng sau khi người dùng chốt tỉ lệ, `criticalIssues` tính theo tỉ lệ sai vẫn còn trong `quality_summary` của lượt cho tới khi duyệt hết hoặc chạy lại.
3. **Đánh giá chung.** Là heuristic rẻ, bắt đúng hai ca bench e-sun-1/e-sun-2 (54–75 m), cách xa vùng căn hộ (≤ 18 m) khoảng 2×. Hậu quả của dương tính giả là một lý do "cần xem lại" sai, không mất dữ liệu, không chặn thao tác. Đủ để merge, nhưng cần ghi nợ và nên siết lại (xem finding 1–2).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | Ngưỡng 35 m là mm tuyệt đối trên tỉ lệ có thể chỉ là ước lượng. Sai số tỉ lệ mà repo tự ghi (bề dày 95–273 mm, ước tường lệch tới 42 %) đủ đẩy một căn 23–25 m qua ngưỡng. Bước quality không biết tỉ lệ đang tạm hay vênh, và cờ `critical` tính theo tỉ lệ sai vẫn nằm lại trong `quality_summary` sau khi người dùng chốt tỉ lệ. | `apps/worker/pipeline_quality/checks.py:40-42`, `:147-151`; `apps/worker/pipeline_build/build.py:80-89`; `apps/api/spatial_read/readiness.py:62-64` | Đưa `scaleBasis`/`scaleChecks` vào `geometry_checks`. Khi tỉ lệ không từ chuỗi kích thước (ước cửa/tường) hoặc có `scaleChecks.estimateSpread`, hạ luật span xuống `critical=False` (chỉ báo), hoặc dùng thước tương đối không phụ thuộc tỉ lệ (vd span / trung vị bề dày tường > ~200, hay số cụm phòng có bếp/cửa chính ≥ 2). Thêm test cho nhánh tỉ lệ ước. Ghi nợ vào `changes/BENCH3D-08.md` nếu để sau. |
| 2 | P2 | LOG | Luật span đo hộp bao của mọi tường, không qua lọc 15 % tổng dài như luật cụm. Tường rào/ranh lô/tường sân bao quanh nhà luôn nằm trong vùng chính (U57 không bỏ) nên span thành chiều dài lô. Nhà ống sâu, biệt thự lô lớn, dãy shophouse liền kề vượt 35 m dù chỉ một mặt bằng. Bench chỉ có căn hộ (≤ 18 m) nên "0 dương tính giả" chưa phủ loại nhà này. Test "nhà lớn" chỉ thử hộp 30 × 12 m không rào. | `apps/worker/pipeline_quality/checks.py:147-149`; `apps/worker/pipeline_quality/tests/test_checks.py:125-127`; `apps/worker/pipeline_build/geometry.py:330-346` | Ghi giới hạn "luật span dành cho căn hộ; nhà đất có ranh lô có thể bật nhầm" vào `changes/BENCH3D-08.md`. Khi có ca nhà đất, đo span trên hộp bao **phòng** (`layer.rooms`) thay vì tường, hoặc đòi thêm tín hiệu thứ hai (≥ 2 bếp, hay ≥ 2 cụm phòng nối nhau chỉ qua hành lang) trước khi bật `critical`. Thêm một test nhà 12 × 20 m nằm trong ranh lô 40 m giữ một mặt bằng. |
| 3 | P3 | TEST | Không có test đúng biên (35 000 không bật, 35 001 bật). Ca tổng hợp cách ngưỡng 5 m mỗi phía (30 m / 40 m), nên lỡ đổi `<=` thành `<` không test nào bắt. `test_small_far_cluster__single_plan` (span 30,8 m) nay cũng chỉ còn đúng nhờ ngưỡng chứ không còn nhờ lọc 15 %. | `apps/worker/pipeline_quality/tests/test_checks.py:117-131` | Thêm một test tham số hoá 35 000 / 35 001 mm. |
| 4 | P3 | TEST | Số đo bench (e-sun-1/2 bật ở 54–75 m, nhóm A dài nhất 18 m) chỉ có trong commit/`changes`, không tái hiện được từ repo. `KET-QUA-r2` nêu hai ca nhiều căn là e-aka-2 và e-sun-2, nhưng `changes/BENCH3D-08.md` không nói e-aka-2 có bật hay không. | `changes/BENCH3D-08.md:4` | Thêm một dòng kết quả e-aka-2, kèm span của ca dài nhất mỗi nhóm B/C/D để thấy khoảng cách tới ngưỡng. |
| 5 | Nit | API | Khi chỉ luật span bật, `detail` là `{"plans": 1, "spanMm": …}`: `MULTIPLE_PLANS` mà `plans: 1` dễ đọc nhầm trong `quality.json`. | `apps/worker/pipeline_quality/checks.py:151` | Thêm khoá lý do (vd `"bySpan": 1`) hoặc để `plans` vắng khi luật cụm không bật. Không gấp, FE không đọc. |
| 6 | Nit | MNT | Docstring hằng nói "hiếm khi dài quá 30 m" nhưng ngưỡng là 35 m và dữ kiện đo là 18 m. Ba con số khác nhau, không ghi nguồn số 30. | `apps/worker/pipeline_quality/checks.py:41-42` | Ghi thẳng "bench nhóm A ≤ 18 m, e-sun ≥ 54 m; 35 m ≈ 2× biên tỉ lệ". |

Không có P0/P1. Hai P2 chưa có dòng nợ trong `changes/BENCH3D-08.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,62 / 5

## PHÁN QUYẾT: APPROVE WITH COMMENTS

Thay đổi nhỏ, khoanh gọn trong một hàm thuần của bước quality. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90, không đổi API/DB/hợp đồng FE. Luật span bắt đúng loại tờ cả tầng mà luật cụm bỏ sót, và với phạm vi hiện tại (căn hộ) còn biên ~2× trước ngưỡng. Điểm 4,62 đủ mức APPROVE theo ma trận, nhưng còn hai P2 chưa ghi nợ: ngưỡng mm tuyệt đối dựa trên tỉ lệ có thể chỉ là ước lượng (#1), và hộp bao mọi tường làm nhà đất có ranh lô hoặc nhà ống sâu bật nhầm (#2). Merge được. Điều kiện là ghi hai P2 vào `changes/BENCH3D-08.md` (hoặc lô DEBT kế tiếp) như nợ `mở`. Ưu tiên #1: hạ luật span xuống chỉ báo khi tỉ lệ là ước lượng.
