# QT-SCALE — tỉ lệ 2 mẫu đồng thuận, bắt bậc bề dày khi đổi tỉ lệ, `scaleBasis`

- B1: `infer_scale` nhận đúng 2 mẫu khi hai số mm khác nhau, mỗi số ≥ 1000 mm và tỉ số lệch ≤ 1 % (`paired=True`);
  hằng riêng trong `infer.py`, không đổi `thresholds.py` (gương FE). Ca ch-09 (12130/491,5 + 11310/458) ra ~24,69 mm/px.
- B3: `rescale._wall` bắt bậc lại bề dày từ số đo đã đổi tỉ lệ (tường AI chưa sửa), giữ bề dày người gõ; đổi `k` rồi
  `1/k` trả bậc cũ. Bảng 6 bậc + `snap_thickness` chuyển về `packages/domain/spatial/thickness.py`, `geometry.py` dùng lại.
- `layer.json` thêm khoá tuỳ chọn `scaleBasis` (chain | paired | note | door | wallThickness | default); file cũ thiếu
  khoá vẫn đọc được. API/openapi không đổi.
- Test cũ sửa theo hành vi mới: hai mẫu 4800/2400 khớp nhau giờ là `paired` (đổi sang 900 mm); bề dày AI nhân thẳng
  (440, 3, 1 → 0) giờ bắt bậc (400, 100, 100).
