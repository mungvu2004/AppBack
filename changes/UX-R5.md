# UX-R5 — đợt sửa sau duyệt kịch bản r4

## be-rooms (UX-04, UX-14)

- UX-14 `apps/worker/pipeline_build/rooms.py` `relabel_by_size`: YOLO báo `bed` trong phòng `_NO_BED_USAGES` (khách, bếp, WC, hành lang, lô gia) → `other` + `variant="rug"` (FE vẽ thảm `rectangular-carpet`). Đo 14 ca với objects.json của YOLO đang chạy (`F:/runs/walls-tidy/cases`): 3 giường đổi — ch-11 thảm hoa văn phòng khách (đúng ca K-02), ch-06 món hẹp 33×186 px trong phòng khách (không phải giường), ch-14 một món trong "phòng khách"; giường trong phòng ngủ không đổi; số phòng không đổi.
- UX-04 diện tích thông thuỷ: KHÔNG sửa đợt này. FE tính diện tích hiển thị từ `outline` (`computeArea`, bước Phòng, `graphSelectors`) và `rescale` tính lại `areaM2` từ đường bao, nên đổi riêng `areaM2` ở worker không tới người dùng và lệch hợp đồng. Đo (outline trừ thân tường, 34 phòng có nhãn diện tích): sai số tuyệt đối TB 16,0 % → 10,2 %, trung vị +9,2 % → −4,2 %, nhưng ch-12 xấu đi rõ (5,0 % → 17,6 %). Muốn làm cần quyết định hợp đồng: đường bao phòng theo mặt tường trong (ảnh hưởng `wallIds`, luật FE, 3D) hoặc trường `netAreaM2` mới.
- UX-04 tách phòng theo ≥ 2 nhãn OCR: chưa làm (hết giờ), để đợt sau.
- Không đổi API, DB, migration, hợp đồng FE–BE. Test: `apps/worker/pipeline_build/tests/test_relabel.py`, `test_rooms.py` (57 đạt).
