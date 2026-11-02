# BENCH3D-05 — nhận phòng: phòng khách không gian mở, lô gia ở tầng không ghi tên phòng

- `apps/worker/pipeline_build/rooms.py` `_open_space_labels`: tầng chưa có phòng khách thì "bếp"/"hành lang" rộng hơn 18 m² (`_OPEN_SPACE_M2`) → `livingRoom` "phòng khách"; không có thì phòng không tên lớn nhất (> 18 m²) của tầng đã có ít nhất một phòng có tên → phòng khách. Bench-3d r2: 17/17 "bếp" 24–52 m² là khách + bếp + ăn; "hành lang" 27 m² (ch-11), "phòng khác" 29–44 m² (cn-14, ch-10) là phòng khách.
- Lô gia mặt ngoài: luật cũ (tầng có nhãn chữ, ≥ 3 m trên biên bao lồi) giữ nguyên. Thêm nhánh cho tầng chỉ có tên suy từ đồ đạc (bản vẽ VN không ghi tên phòng): phòng không tên 2–15 m², hẹp (cạnh ngắn hộp bao xoay ≤ 2 m, `_LOGGIA_DEPTH_MM`), ≥ 3 m mặt ngoài tính bằng phần lớn hơn của cạnh trên biên bao lồi hay cạnh không giáp phòng nào (`_exposed_lengths`, bắt lô gia lõm vào mặt nhà).
- Mô phỏng trên layer r2 (không chạy lại bench): P4 tăng ở ch-08, ch-10, ch-11, cn-06, cn-07, cn-09, cn-14, cn-16, cn-17, cn-20, cn-21, cn-22; không ca có đáp án nào giảm. Rủi ro: cn-19 kho 3,8 m² mặt ngoài thành lô gia (P4 ca này không đổi).
- Test cũ `test_short_cabinet_with_dining_set_names_kitchen_not_bedroom`: khu khách-bếp 32 m² nay là phòng khách (vẫn không phải phòng ngủ).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test apps/worker/pipeline_build, packages/vision/dimensions. Migration/hợp đồng: không áp dụng.
