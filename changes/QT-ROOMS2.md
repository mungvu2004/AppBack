# QT-ROOMS2 — khép khe dài khi thẳng hàng (B9) + tin cậy phòng theo nhân tố (B12)

- Điều tra ch-09 (dựng lại từ artifact, ép tỉ lệ): ở 14,32 mm/px `_gap_closers` khép 4 khe 1081–1192 mm → 10 phòng (phòng ngủ chỉ 4–5 m², sai); ở 24,66 / 27,04 các khe thành 1,9–2,2 m > `ROOM_GAP_CLOSE_MM` → 4 phòng kín + 3 phòng mọc từ nhãn = 7. Nguyên nhân: ngưỡng mm khép khe QUÁ NHỎ ở tỉ lệ đúng (không phải quá lớn); cùng gốc với NO-435 (thêm 3 khe 3,2–4,1 m).
- B9: khe > 1200 mm tới `ROOM_GAP_EVIDENCE_MM` (2400) chỉ khép khi hai tường thẳng hàng (song song, lệch ngang ≤ 150 mm, chân ở đầu tường đích) và đoạn nối không sát tường khác quá nửa; khe có hộp ô mở vẫn do `_door_closers`. Khe ch-09 là vách so le nên không đủ bằng chứng → ch-09 vẫn 7 (đáp án 11).
- Bench 14 ca: số phòng không đổi ca nào, tổng |sai| 20 → 20 (ch-08 khép thêm 2 khe 2046 mm, số phòng giữ 8).
- B12: tin cậy = nguồn tên (chữ 1,0 / đồ hoặc lô gia rìa 0,6 / không tên 0,4) × max(0,5; 1 − phần chu vi không sát tường) × (0,7 nếu tỉ lệ không tin). Bench: phòng tin 1,0 từ 103/114 xuống 26/114.
- `build_rooms(scale_trusted=None)` suy từ `scaling.build == scaling.final`; build.py (ngoài gói) nên truyền `trusted` để tỉ lệ ước từ cửa cũng nhận 0,7.
