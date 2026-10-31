# WALLS-CURVE — tường cong và ký hiệu hộp kỹ thuật (vector hoá tường)

- `packages/vision/walls/vectorize.py` bước 5b `_smooth_arcs`: chuỗi ≥ 3 đoạn DP liền nhau có điểm xương nằm trên một
  đường tròn (lệch ≤ max(1,5 px; 0,2 × bề dày)), quét ≥ 30°, bán kính ≥ 4 và dài ≥ 5 lần bề dày → chia lại thành dây
  đều nhau nằm đúng trên cung (≤ 10°/dây, dây ≥ 1,5 × bề dày). Dây cung (`_Seg.arc`) không bị ép trục, hút góc hay góp
  vào hướng chủ đạo. Ngưỡng bán kính thêm sau khi bench thấy góc có cột bo xương tròn (ch-12, ch-13 ra tường xiên).
- Bước 10c0 `_drop_box_marks`: bản vẽ vuông góc, nét chéo có hai đầu ở góc/tâm của ô kín bốn tường (≤ 20 × bề dày mỏng
  nhất) là ký hiệu hộp gen/hộp kỹ thuật gạch X → bỏ, kèm mẩu vụn ở góc ô; bốn vách hộp giữ.
- Bước 10b `_clash` chỉ so hai phía của đoạn chéo: hộp gen bị mặt nạ tô đặc có hai cạnh dọc đã chung nút, luật cũ chặn
  hút hai nhánh chéo xuống góc đáy nên ra tường xiên chữ V (ch-13, giữa WC1/WC2).
- Bench 14 ca căn hộ (mặt nạ model thật, chạy `vectorize_with_stats` + `build_layer`, so với `main`): ch-13 xiên 2 → 0,
  tường 27 → 23, phòng 5, cửa 9, đầu lơ lửng 4 giữ nguyên; 13 ca còn lại y hệt `main` (số tường, phòng, cửa, xiên,
  bề dày không chuẩn).
- Review lượt 1: `_enclosing_cell` dò theo chỉ mục tim + `bisect` (không quét mọi tường cho từng đoạn chéo); mẩu vụn
  góc hộp chỉ bỏ khi chung đầu mút với nét chéo vừa bỏ; test ngưỡng cung (`_arc_chords`) và đường chéo cả phòng.
- Còn hở: tường cong vẫn là nhiều đoạn thẳng (hợp đồng `WallPx`/`WallOut` chưa có độ cong; Pascal có `curveOffset`);
  hộp gen tô đặc thành một khối tường đặc hẹp hơn hộp, chưa ra bốn vách (đo mực không tách được hộp với cột gạch chéo).
- Không đổi API, DB, migration, hợp đồng FE–BE.
