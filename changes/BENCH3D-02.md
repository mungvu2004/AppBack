# BENCH3D-02 — tường: bề dày qua chữ T, bỏ nét mảnh và mẩu vụn; cửa rộng, cửa sổ bị cắt đôi, vỏ hở chỗ sót cửa

- C1: `vectorize._groups` chỉ gộp hai nhánh thẳng hàng qua nút khi bề dày lớn/nhỏ ≤ `_PIECE_THICKNESS_RATIO` (1,25):
  tường ngoài 220 và vách 110 cùng trục không còn bị trung bình thành 200.
- C2 (`apps/worker/pipeline_build/geometry.py`): tường đo < 40 mm là nét mảnh → bỏ (trừ khi cả bản đều mảnh — tỉ lệ sai);
  tường song song nằm trong thân tường đo dày hơn (nét kính cửa lùa) → bỏ, ô mở về tường chủ; mẩu < 200 mm có đầu lơ
  lửng, không chạm hộp ô mở → bỏ. Mọi lượt bỏ đếm vào `isolatedBlock` (không thêm khoá `dropped`).
- C3: cửa đi không đọc được cung mở mà rộng ≥ 1,5 m → `sliding` (kể cả khi không có trang); đọc được cung mà rộng
  > 1,2 m → `double`. `doorStyle` không đặt nên luật miền (chỉ cửa lùa) vẫn giữ.
- C4: ô mở cùng loại cùng tường cách ≤ 60 mm (cửa sổ bị bộ dò cắt 1400 + 600) gộp thành một khoảng, lấy thuộc tính
  mảnh `confidence` cao hơn; mảnh bị nhập đếm `openingOverlap`.
- C5 (`geometry.close_envelope_gaps`, gọi trong `build._assembled` sau khi có phòng): đoạn nối khe thẳng hàng trên mặt
  ngoài phòng, khe 600–2400 mm → tường qua khe (không đầu vào) mang cửa đi đoán (đọc cánh; ≥ 1,5 m → lùa; còn lại
  tin 0,3); khe < 600 mm → kéo một tường chủ khép khe. Khe trong nhà giữ hở như cũ.
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test `packages/vision/walls`, `apps/worker/pipeline_build`.
- Vòng sửa review: tường chủ khép khe hẹp phải thẳng hàng với khe (vách chữ T không bị kéo xiên).
