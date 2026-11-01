# QT-ORIENT — luật 4: hướng đồ AI

- `packages/domain/rules_ai/orient.py`, gọi cuối `apply_post_rules`: gương `orientDetected.ts` của FE. Ghế (trừ sofa) quay vào bàn/quầy ≤ 900 mm, không có thì lưng tựa tường; đồ tựa tường (giường, tủ áo, tủ bếp, thiết bị vệ sinh, máy giặt, sofa, kệ TV, tủ lạnh, kệ, tủ, `other` chưa có variant) quay lưng về tường thẳng trục gần nhất ≤ 600 mm, không có thì giữ 0°.
- Thêm so với FE: góc hai tường thì giường/bồn cầu tựa cạnh ngắn, dãy tủ/tủ áo/kệ TV/lavabo/sofa tựa cạnh dài; `other` chưa có variant cũng tựa tường.
- Quay 90°/270° hoán hai cạnh hộp (K1); luật 1 đo theo hộp thế giới nên vẫn idempotent. Bàn làm việc chưa xoay (không có variant `desk`).
- Đo 14 ca bench (dựng lại lớp, ghép facing-consensus IoU ≥ 0,3 một–một, F:/runs/chan-doan-quy-trinh/lan3/orient/score.py): ghép 202/338, đúng 171/202 = 84,7 % (mốc 0° cùng tập 19,8 %; chưa có luật `other` 77,7 %).
- Theo loại: giường 85,7 %, sofa 85,7 %, bồn cầu 95,8 %, tủ áo 82,4 %, quầy 92,3 %, lavabo 100 %, ghế ăn 93,8 %, bếp 87,5 %, tủ lạnh 80 %; ghế văn phòng 28,6 % (chưa có bàn làm việc để quay vào).
