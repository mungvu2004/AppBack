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
- Nợ NO-431 (mở): `rules_ai` (bám đồ vào mặt tường, phân mặt trong/ngoài) và `spatial/diff.py` (lịch sử không ghi trường
  `curveOffsetMm`) coi tường cong là dây.
- Nợ NO-432 (mở): kích thước ghi trên tường cong (bước 7) đo theo dây; ô mở trên cung bị kẹp trong một dây ≤ 10° như trước.
- Nợ NO-433 (mở): khe cửa trong mặt nạ huấn luyện (`render.py`) cắt theo dây, chưa theo cung.
- Nợ NO-434 (mở): bước 5b (WALLS-CURVE) báo nhầm cung trên bản vẽ CVC: góc vát 45° tường dày (`Ib_RI0501`, R/t 3,9) và
  tường chéo có gãy (`IIa_GL0401`); 5 cung tìm được trên 39 trang CVC đều dài 6-12 lần bề dày. Cần phép thử phân biệt
  vát góc với cung trước khi bật trên bản vẽ ngoài bộ bench.
