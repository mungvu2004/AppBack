# BENCH3D-26 — đồ trùng: một vật nhận hai lần, hai hộp khác loại đè nhau

- Mới `pipeline_build/furniture_dedup.py` `dedupe_furniture`, gọi trong `build._attempt` ngay sau `apply_post_rules` (hộp đã
  bắt tường, đã quay, so bằng `world_box`); mọi đường dựng đều qua `_attempt`. Chỉ xét đồ AI chưa duyệt (K21).
- Luật (hằng số trong tệp): cùng loại IoU ≥ 0,5, hoặc lồng IoM ≥ 0,8 (trừ `other`, `chair`); khác loại IoU ≥ 0,6; khác loại
  lồng IoM ≥ 0,8 khi cả hai là đồ cố định trên sàn (`_FLOOR_FIXED`), trừ `wardrobe`/`washingMachine` trong `kitchenCabinet`.
  Bỏ: gợi ý trước đồ thật; cùng chỗ → đúng công năng phòng rồi độ tin; lồng nhau → hộp nhỏ, trừ khi chỉ hộp nhỏ đúng công
  năng phòng. Hoà hẳn phá theo hộp rồi loại, không theo vị trí danh sách.
- Chậu bếp: `sanitaryFixture` lồng trong `kitchenCabinet` (IoU < 0,6), không dính phòng tắm → không bỏ, thành chậu mỏng
  `variant="sink"`, `heightMm` 20 (dạng `SINK` của `sceneFurnish.ts`); `toPascal.sinkFolderOf` dựng tủ chứa nó thành mẫu có
  chậu. AppFront không tự bày lại chậu khi phòng đã có tủ (`needsKitchenRun`). Chậu mỏng miễn `_duplicate`: chạy lại y nguyên.
- Đồ nhỏ trên đồ lớn (`other`/`chair`/`table`) không bị coi là trùng: IoM một mình không đủ, ghi ở đầu tệp.
- Đồ ngoài khối nhà: không thêm luật, `rooms.build_furniture` đã gắn `suggested`.
- Đếm ở log `pipeline_build_furniture_deduped` (`dropped`, `sinks`), không thêm vào `BuiltLayer.dropped` vì bộ 12 khoá được
  kiểm khi đọc lại layer.json đã lưu. Hiệu năng: 5 000 hộp 8 ms (thưa) / 66 ms (dày).
- Không đổi API/DB/OpenAPI/hợp đồng. Lớp đã lưu không tự đổi, phải chạy lại pipeline.
- Đo (phát lại trên layer.json đã lưu r5/f3/art5, `F:/runs/bench-3d/dot6-dedup/`; F tính trên đồ ở layer vì lượt lưu không có
  probe): bench 60 tầng 2098 → 1975 món, 65 chậu; F 27 tầng 693 → 650, 31 chậu; căn hộ 14 tầng 275 → 250, 26 chậu. Không ca nào
  giảm F; F4 T: bench 37 → 0, F 15 → 0. Idempotent trên mọi tầng; xáo 30 lần không đổi nội dung ở tầng nào.
- Nợ phía AppFront (không sửa ở đây): `MISPLACED_FURNITURE` xét theo `kind` nên chậu mỏng ở bếp/phòng khách/phòng ngủ vẫn bị cảnh
  báo `ROOM-FURNITURE-MISMATCH`, như trước nhánh này.
- Nợ chấp nhận: ghế thật lồng trong hộp ghế dài/hộp bao độ tin thấp được giữ cả hai (ch-10, cn-17, f-28), nên hộp thừa còn chồng.
