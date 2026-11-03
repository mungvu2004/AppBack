# BENCH3D-08 — cảnh báo tờ nhiều căn liền nhau

- `apps/worker/pipeline_quality/checks.py` `_multiple_plans`: ngoài luật cũ (≥ 2 vùng tường tách xa), `MULTIPLE_PLANS` (critical) còn bật khi hộp bao mọi tường dài quá `PLAN_MAX_SPAN_MM` = 35 m — tờ mặt bằng cả tầng toà nhà mà các căn dính liền thành một cụm tường. `detail` thêm `spanMm`.
- Đo trên bench-3d r2: bật mới ở e-sun-1, e-sun-2 (54–75 m); không ca nhóm A nào bật (dài nhất 18 m).
- `ROTATED_PLAN` chưa làm: chữ trong `text.json` và lớp không phân biệt được bản vẽ xoay 90°; cần đọc ảnh trang ở bước kiểm chất lượng (ghi trong báo cáo làn L4).
- Test `test_service`: lớp mẫu 48 tường nối đuôi dài 48 m nay có thêm `MULTIPLE_PLANS`.
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test apps/worker/pipeline_quality.
- Nợ mở (review 2026-11-03, P2): luật span 35 m dùng tỉ lệ có thể chỉ là ước lượng (cửa/bề dày tường) → hạ thành chỉ báo khi `scaleBasis` không phải chuỗi kích thước hoặc có `estimateSpread`.
- Nợ mở (review 2026-11-03, P2): span lấy hộp bao mọi tường, kể cả tường rào/ranh lô → nhà đất lô lớn có thể báo nhầm; đo trên hộp bao phòng hoặc đòi tín hiệu thứ hai, thêm test ranh lô 40 m.
