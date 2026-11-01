# QT-ORIENT — luật 4: hướng đồ AI

- Thêm `packages/domain/rules_ai/orient.py`, gọi trong `apply_post_rules` sau luật 1-3: gương `orientDetected.ts` của FE.
- Ghế (trừ sofa) quay vào bàn/quầy gần nhất ≤ 900 mm, không có thì lưng tựa tường; đồ tựa tường (giường, tủ áo, tủ bếp,
  thiết bị vệ sinh, máy giặt, sofa, kệ TV, tủ lạnh, kệ, tủ) quay lưng về tường thẳng trục gần nhất ≤ 600 mm.
- Cải tiến so với FE: khi hai trục đều có tường, giường/bồn cầu tựa cạnh ngắn; dãy tủ/tủ áo/kệ TV/lavabo/sofa tựa cạnh dài.
- Quay 90°/270° hoán hai cạnh hộp (khung riêng K1); luật 1 đo theo hộp thế giới nên lượt hai không đổi gì (idempotent).
- Chỉ đồ AI chưa duyệt còn 0°; không có tường gần thì giữ 0°. Bàn làm việc chưa xoay (không có variant `desk`).
- Đo trên 14 ca bench: xem mục "Số đo" (thêm sau khi đo).
