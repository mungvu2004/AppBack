# BENCH3D-26 — đồ trùng: một vật nhận hai lần, hai hộp khác loại đè nhau

- Mới `pipeline_build/furniture_dedup.py` `dedupe_furniture`, gọi trong `build._attempt` ngay sau `apply_post_rules` (hộp đã
  bắt tường, đã quay, so bằng `world_box`); mọi đường dựng đều qua `_attempt`. Chỉ xét đồ AI chưa duyệt (K21).
- Luật (hằng số trong tệp): cùng loại IoU ≥ 0,5 hoặc lồng IoM ≥ 0,8 (trừ `other`); khác loại IoU ≥ 0,6; khác loại lồng
  IoM ≥ 0,8 khi cả hai là đồ cố định trên sàn (`_FLOOR_FIXED`), trừ `wardrobe` trong `kitchenCabinet`. Bỏ: gợi ý trước đồ
  thật; cùng chỗ → đúng công năng phòng rồi độ tin; lồng nhau → hộp nhỏ, trừ khi chỉ hộp nhỏ đúng công năng phòng.
- Đồ nhỏ trên đồ lớn (`other`/`chair`/`table`) không bị coi là trùng: IoM một mình không đủ, ghi ở đầu tệp.
- Đồ ngoài khối nhà: không thêm luật, `rooms.build_furniture` đã gắn `suggested`. Dò f-22: 6 món ngoài đều đã có cờ.
- Không đổi API/DB/OpenAPI/hợp đồng. Lớp đã lưu không tự đổi, phải chạy lại pipeline.
- Đo (phát lại trên layer.json đã lưu r5/f3/art5, `F:/runs/bench-3d/dot6-dedup/`; F tính trên đồ ở layer vì lượt lưu không có
  probe): bench 60 tầng 2098 → 1903 món, F tập 27 tầng 693 → 617, căn hộ 14 tầng 275 → 224; F4 (trùng chỗ) lên ở 88 tiêu chí-ca,
  không ca nào giảm F. f-22 lớp sống: bỏ 5 món (vòi trong bồn tắm, 2 tủ lavabo, 2 gối thành thiết bị vệ sinh), F4 T → Đ.
