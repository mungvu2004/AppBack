# WALLS-ARC — tường cong một mảnh từ vector hoá tới dây FE

- Quy ước một trường, mặc định thẳng: sagitta có dấu, pháp tuyến dây `n = (-dy, dx)/L`, điểm giữa cung = trung điểm
  dây − sagitta · n, |sagitta| ≤ L/2 (đúng `curveOffset` của Pascal). Hàm thuần `packages/domain/spatial/arc.py`.
- `vision/walls/vectorize.py` bước 10f `_join_arcs`: chuỗi dây cung của 5b (nối bằng khoá giữa cung) → một
  `WallSegment.sagitta_px`; cung > 170° tách đôi. `ml_contracts` `WallPx.sagitta_px` (vắng khoá khi 0 → `walls.json` cũ
  y nguyên byte), `apps/ml/walls/step.py` chuyển tiếp.
- `pipeline_build/arcs.py`: `build_layer` nổ tường cong thành dây đều trước bước 3 (bước 3-7 chạy y như khi vector hoá
  còn trả dây), sau `build_rooms` gộp dây của một cung thành một `Wall.curve_offset_mm`; ô mở cộng dồn offset, `wallIds`
  của phòng và `input_to_wall` đánh lại. Chuỗi không còn nguyên (gộp, mất, đứt, số dây lẻ) giữ các dây.
- `domain/spatial/model.py` `Wall.curve_offset_mm` (vắng khoá khi 0; |giá trị| ≤ L/2 + 1 mm), `scale/rescale.py` nhân hệ
  số rồi kẹp nửa dây, `spatial_read/wire.py` `WallOut.curve_offset_mm` (vắng khi 0: `WallSchema` FE là `.strict()`),
  `worker/datasets/render.py` mặt nạ huấn luyện tô theo cung. Không migration (tài liệu tầng là JSONB).
- Bench 14 ca (`F:/runs/walls-arc/ab.sh`, gốc `origin/fix/walls-curve-shaft`): 14/14 giống từng byte (không ca nào có cung).
- **Cần người điều phối**: hợp đồng FE–BE thêm `curveOffsetMm` (tuỳ chọn) vào `WallSchema` đọc/ghi, xuất lại
  `openapi.json`, nâng `tools/contract/APPFRONT_SHA` lên AppFront `feat/walls-arc`.
- NO-431 (đóng): `rules_ai` đo khe đồ tới chính cung (`arc.foot_on_arc`), dò trong/ngoài ở đỉnh cung, lưới tường nở thêm
  |sagitta|; `spatial/diff.py` theo dõi `curve_offset_mm` (bảng HOP-DONG-MOI §1.3 thêm cả `paint` vốn đã theo dõi), nên
  `provenance.mark_edited` bỏ nhánh vá riêng.
- NO-432 (đóng): ô mở gắn vào dây của một cung chiếu lên cả cung (`geometry._arc_chains`, cùng điều kiện gộp của
  `join_arcs`), đặt trên dây đầu với `offsetMm` tính từ đầu cung — cửa rộng hơn một dây 10° không còn bị kẹp/rơi. Chữ kích
  thước ghép với cả tường cong (dây lớn) chứ không với dây 10° (`_Attempt.whole_px`, bước 2 và 7).
- NO-433 (đóng): khe cửa trong mặt nạ huấn luyện và hộp nhãn ô mở lấy các tứ giác dọc cung (`arc.span_points`).
- NO-434 (đóng): 5b chỉ nhận cung khi lệch RMS tới đường tròn ≤ 0,6 lần lệch tới chính các đoạn DP (`_ARC_FIT_GAIN`): 5 cung
  giả trên 40 trang CVC (tỉ lệ ≥ 0,76) bị loại, ban công vẽ tay (0,12) và qua mặt nạ ML (0,47) giữ.
