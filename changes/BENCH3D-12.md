# BENCH3D-12 — luật 2: cửa kính lùa ra lô gia thành cửa đi

- `packages/domain/rules_ai/post_rules.py` `_fix_windows`: trước nhánh cũ, cửa sổ AI chưa duyệt rộng ≥ `SLIDING_DOOR_MIN_WIDTH_MM` (1400) trên tường thẳng mà tại tâm ô mở hai bên đều là phòng, một bên là `loggia` **chưa có cửa đi nào nối sang phòng khác** → `kind="door"`, `swing="sliding"`, cao `SLIDING_DOOR_HEIGHT_MM` (2200), bệ 0, tin cậy ≤ 0,5.
- Tín hiệu "lô gia chưa có lối vào" (thay vì nâng ngưỡng): lô gia đã có cửa đi thì ô kính rộng là cửa sổ thật (bench ch-12 1786 mm, syn-can-ho-4pn 1797 mm giữ cửa sổ). Cửa ra ngoài (một bên không phải phòng) không tính lối vào.
- Bench r3 mô phỏng (47 ca A/B/C): O1c Đ23 C9 T4 → Đ28 C6 T2; O1b Đ32 C13 T2 → Đ35 C11 T1; O1 không đổi.
- `_RoomIndex.at` trả vị trí phòng chứa điểm (`contains` dùng lại). Hằng mới trong `constants.py`. Bản tham chiếu test thêm luật.
- Không migration, không đổi hợp đồng/openapi.
