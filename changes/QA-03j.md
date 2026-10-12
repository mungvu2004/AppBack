# QA-03j — FIX-2434 BUG-576 (#31 hình thoi bắt đầu ở đỉnh trên)

- `packages/vision/preprocess/geometry.py` `validate_quad`: bỏ luật "điểm đầu = `order_corners`" (so `x + y` pixel trên
  trang chưa nắn — sai hệ toạ độ so với luật TL của #31 trên tỉ lệ trang đang hiển thị, NO-227), thay bằng lồi + **chiều
  kim đồng hồ** (4 tích có hướng > 0). Điểm đầu người gọi chọn vẫn là TL của ảnh nắn; góc tự tìm (`find_frame`) đi qua
  `order_corners` nên không đổi.
- Test: `packages/vision/preprocess/tests/test_geometry.py` (hình thoi hai điểm đầu), `apps/api/quality/tests/test_routes_corners.py`
  (#31 → 200 cho cả hai điểm đầu trên ảnh 600x420).
- Không đổi route, schema, migration, openapi.
