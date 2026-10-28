# B3-SUGGEST — gợi ý của máy và món người thêm trên S-13

- `Furniture.suggested` (miền `packages/domain/spatial/model.py`, dây `FurnitureOut`): tuỳ chọn, mặc định `False`, vắng khoá khi `False` — tài liệu cũ và FE cũ không đổi.
- Nhật ký `floor_change_log` theo dõi thêm trường `suggested` của đồ đạc (`diff.py`): máy gợi ý (tạo với `true`), người nhận (gỡ cờ) hay bỏ (`__deleted__`) đều có dòng — nhãn miễn phí về sau. Gỡ cờ không đánh `edited` (`provenance.py`).
- `apps/worker/datasets/render.py`: bỏ hộp `suggested` và hộp người vẽ còn đúng 600 × 600 mm (bấm, chưa kéo/đổi cỡ) khỏi nhãn YOLO.
- Không migration, không route mới. `APPFRONT_SHA` nâng tới commit FE có `suggested` trong `FurnitureSchema`.
