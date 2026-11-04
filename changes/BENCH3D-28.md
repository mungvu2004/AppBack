# BENCH3D-28 — gộp tường không phủ sai bề dày; bỏ đồ AI ngoài khối nhà

- Tường, gốc do WALL-RUN (#52): cả nhóm thẳng hàng lấy một trung vị, nên f-22 mép trên 400 | 220/150/220 | 400 ra một tường
  400 phủ 3,9 m tường mỏng. `wall_runs._thickness_runs` cắt nhóm dọc đường: gộp đến khi bậc cao / bậc thấp (`snap_thickness`)
  vượt `_TIER_RATIO` 1,5 (150-220, 200-300 gộp; 100-200, 220-400 không). Khúc ≤ `_SLIVER_MM` 600 là vụn đo ở chữ T, theo dãy
  đang gộp, không cắt dãy. Trung vị và bắt bậc một lần giữ nguyên, nay tính trên từng dãy.
- Đồ: `furniture_dedup.find_outside`, chạy đầu `dedupe_furniture`. AI chưa duyệt, tâm cách bao lồi (đầu mút tường + góc phòng)
  quá `BUILDING_MARGIN_MM` 1000 → bỏ hẳn, đếm ở log `pipeline_build_furniture_outside_dropped`. Đồ người đặt, đã duyệt không bị
  đụng. Đo bằng bao tường nên bàn ăn ở phòng khách hở tường (không ra phòng nào) vẫn còn, `rooms.build_furniture` vẫn chỉ gắn
  `suggested` cho món đó.
- Đo tường (phát lại `merge_wall_runs` trên `F:/runs/bench-3d/dot5/base`, 96 tầng, so `dot5/v3` là #52; `dot7-leftovers/`):
  số tường chưa gộp 2738 → #52 2079 → nay 2267; cặp khúc chạm nhau 717 → 97 → 274, trong đó 246 cặp khác bậc thật. Chiều dài khúc
  bị phủ bề dày lệch quá 1,5 lần: #52 300 m ở 71 tầng → nay 16 m ở 24 tầng, toàn khúc ≤ 600 mm. f-22: 30 → 19 → 21 tường, mép
  trên thành 400 | 220 | 400.
- Đo đồ (phát lại trên `runs/r5`, `tap-f/runs/f3`, `bench-can-ho/art5`; danh sách `dot7-leftovers/do-bi-bo.csv`): bench 60 tầng
  bỏ 126/2098 ở 23 tầng; F 27 tầng bỏ 16/693 ở 4 tầng; căn hộ 14 tầng bỏ 0/275. Mọi món bị bỏ đều đã mang `suggested`; F1-F4 không đổi ở tầng nào, đương nhiên,
  vì công thức F trong phát lại không tính đồ gợi ý, nên F không chứng minh được gì ở đây. f-22 mới: bỏ đúng 2 món `other` .62, `chair` .27.
- Soi mắt `dot7-leftovers/soi-do-bi-bo.png`: gần hết là sơ đồ tầng, key plan, ảnh phối cảnh. Có món thật bị mất: ghế tắm nắng
  nhãn `bed` trên sân vườn cong syn-penthouse (ngoài bao, không có tường), và giường ở các căn khác của mặt bằng cả tầng e-sun-1,
  e-sun-2 (không dò ra tường ở các căn đó).
- Giới hạn đã chấp nhận: tường lạc ở vùng ngoài (e-sun-1 có tường ở x ≈ 85 m) nới bao lồi, đồ trong vùng đó vẫn còn. Đồ gợi ý
  trong bao nhưng ngoài phòng vẫn còn cờ `suggested`.
- Không đổi API/DB/OpenAPI/hợp đồng. Lớp đã lưu không tự đổi, phải chạy lại pipeline.
