# BENCH3D-23 — phòng ngủ suy lớn hẳn thành khách; cửa lùa cần lô gia sâu

- `apps/worker/pipeline_build/rooms.py` `_open_space_labels`: tầng chưa có phòng khách, ≥ 2 phòng ngủ, phòng ngủ lớn nhất suy từ đồ (không phải nhãn chữ) > 18 m² và ≥ 1,3× phòng thứ hai → phòng khách (tin cậy suy đoán).
- `packages/domain/rules_ai/post_rules.py` `_sliding_door`: cửa sổ chỉ thành cửa lùa khi lô gia còn ở điểm cách tim tường `SLIDING_LOGGIA_MIN_DEPTH_MM` (800) trước tâm ô kính (dải 500 mm sinh từ nét khung không còn đổi cửa sổ phòng ngủ).
- Replay: F P2 +3 (f-02, f-08, f-11), f-06 O1 T→Đ; bench không ca nào xấu. Không đổi hợp đồng/openapi.
