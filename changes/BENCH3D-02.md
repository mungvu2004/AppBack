# BENCH3D-02 — tường: bề dày qua chữ T, bỏ nét mảnh và mẩu vụn

- C1: `vectorize._groups` chỉ gộp hai nhánh thẳng hàng qua nút khi bề dày lớn/nhỏ ≤ `_PIECE_THICKNESS_RATIO` (1,25):
  tường ngoài 220 và vách 110 cùng trục không còn bị trung bình thành 200.
- C2 (`apps/worker/pipeline_build/geometry.py`): tường đo < 40 mm là nét mảnh → bỏ (trừ khi cả bản đều mảnh — tỉ lệ sai);
  tường song song nằm trong thân tường đo dày hơn (nét kính cửa lùa) → bỏ, ô mở về tường chủ; mẩu < 200 mm có đầu lơ
  lửng, không chạm hộp ô mở → bỏ. Mọi lượt bỏ đếm vào `isolatedBlock` (không thêm khoá `dropped`).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test `packages/vision/walls`, `apps/worker/pipeline_build`.
