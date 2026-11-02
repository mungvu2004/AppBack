# QT-SWING — chiều mở cửa đọc từ nét vẽ

- Mới `apps/worker/pipeline_build/swing.py`: cửa một cánh trên tường thẳng thử 4 giả thuyết (bản lề đầu a/b × cánh
  hai phía), lấy mẫu nét cánh + cung 1/4 trên ảnh mực (trang trừ mặt nạ tường); không chắc → giữ giá trị cũ.
- Đổi sang ngữ nghĩa FE: `swing` left/right = bản lề phía `centreline.start`/`end` (Pascal `hingesSide`);
  `reversed` = phía cánh đọc được khác luật `swingDirectionOf` (port `rule_side`, tính sau luật hậu xử lý).
- `build_walls(page=...)`; build.py: `_Attempt.page`, truyền trang vào `build_walls`, giữ `leaves` qua `join_arcs`,
  `settle_reversed` sau `apply_post_rules`.
- Đo 81 cửa một cánh (lan3/swing/KET-QUA.md): đúng cả bản lề + phía 34,6 % → 58,0 %; bản lề 54,3 → 67,9 %;
  phía mở 65,4 → 82,7 %.
