# DOOR-SCALE — tỉ lệ tạm từ cửa đi thay cho bề dày tường

- `apps/worker/pipeline_build/build.py` `_door_scale`: dự án chưa đặt tỉ lệ và OCR không ra tỉ lệ (U01) → tỉ lệ tạm = 745 mm / cạnh dài trung vị của hộp `door` (≥ 3 cửa, bỏ hộp dài hơn 1,6 lần trung vị: cửa đôi, cửa lùa); thiếu cửa thì vẫn bề dày trung vị = 150 mm như cũ. Nguồn vẫn `pipeline`, vẫn `unresolved`, không dựng `Dimension` từ mẫu khớp (giữ `estimated`).
- 745 mm: hộp YOLO hẹp hơn cánh cửa thật (~850 mm); đo trên 11 bản bench căn hộ có đáp án, leave-one-out lệch trung vị ~8–10 %, tối đa ~17 % (`F:/runs/bench-can-ho/inv-doorscale`).
- Bench 35 bản (lượt f14 31/10, dựng lại bằng mã main, `F:/runs/bench-can-ho/now`): 3 bản có đáp án dùng nhánh ước lượng: ch-04 +28,8 % → +0,9 %, ch-09 −41,9 % → +9,7 %, ch-01 −4,9 % → +8,0 %. Bản có tỉ lệ OCR không đổi.
- Đánh đổi đã biết: phòng `ch` 87 → 83 dựng riêng đúng (ch-09: ở tỉ lệ thật ba khe tường 3,2–4,1 m — tường kính, tường ngoài nhạt model bỏ sót, bếp mở — vượt `OPENING_GAP_MAX_MM` nên mặt phòng hở; tỉ lệ sai cũ làm chúng < 2,4 m và được nối; ch-05 không có đáp án tỉ lệ). Bộ độc lập `cn` (21 bản): phòng đúng 121 → 121, thừa 26 → 30. Nâng `OPENING_GAP_MAX_MM` lên 4200 bù được (cn đúng 127, sót 8) nhưng thừa 35 → không làm ở đây.
- Không đổi API, DB, migration, hợp đồng FE–BE. Cổng áp dụng: lint/type, test `apps/worker/pipeline_build`.
