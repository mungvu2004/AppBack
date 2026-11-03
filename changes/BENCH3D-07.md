# BENCH3D-07 — tự chọn trang bản vẽ của PDF khi client không chọn trang

- Migration `r20261103_bench3d_07` (chỉ mở rộng, trên `r20261102_aid_01`): cột `uploads.page_auto` BOOLEAN NULL, không
  default, không backfill. #5 ghi `true` khi thân **vắng** `pageIndex` (`model_fields_set`); `pageIndex: 0` tường minh → `false`.
- #7 chỉ tự chọn trang khi `page_auto` đúng **và** `crop_corners` NULL: `pick_plan_page` (`pdf_vector.py`) lấy trang đầu
  tiên có ≥ 100 nét vector, hoặc ảnh nhúng ≥ 30 % trang mà lõi trang ≥ 2 % mực ở 36 dpi; không trang nào → 0. Trang
  chọn được ghi vào `uploads.page_index` trước khi mở lượt chạy. Trang client gửi (kể cả 0) và lượt cũ (NULL) giữ nguyên.
- Dò trang chạy trên `asyncio.to_thread` (cùng đếm trang), dừng duyệt khi đủ `PLAN_MIN_SEGMENTS`, không trích chữ.
- Không đổi wire, `openapi.json`, hợp đồng. Bench two-page-ch04 (bìa quét, không gửi `pageIndex`): trang 1 thay vì bìa.
- Cổng áp dụng: lint/type, migration lint, test `packages/vision/preprocess`, `apps/api/drawings`.
