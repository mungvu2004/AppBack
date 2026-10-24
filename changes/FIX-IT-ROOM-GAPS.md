# FIX-IT-ROOM-GAPS — khép phòng ở khe góc/chữ T không có hộp ô mở (BUG-IT-008)

- `apps/worker/pipeline_build/rooms.py` `_gap_closers`: đầu tường tự do (không chạm tường/`bridges` trong `ROOM_SNAP_MM`)
  nối thẳng tới điểm gần nhất trên tim tường khác ≤ `ROOM_GAP_CLOSE_MM=1000`, lệch hướng ra của đầu tường ≤ 60°
  (`ROOM_GAP_CLOSE_MIN_COS=0.5`), không cắt tim tường/`bridges` khác; mỗi đầu giữ đoạn ngắn nhất. Chỉ thêm vào
  `_room_outlines` trước `polygonize`, tường/`bridges`/`wallIds` không đổi; `STRtree` theo lô (trần B5-01).
- Replay G2..G5 (khớp GT IoU ≥ 0,5 / phòng giả): G2 4/1 → 5/2, G3 8/3 → 12/4, G4 12/2 → 17/6, G5 4/0 → 13/0.
- Test: `apps/worker/pipeline_build/tests/test_rooms.py`; `test_corner_gap_400_gives_no_room` đổi thành
  `test_build_rooms__corner_gap_400_closes` (khe 400 mm nay khép, đúng BUG-IT-008). Không đổi API, migration, hợp đồng FE.
