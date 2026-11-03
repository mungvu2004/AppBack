# BENCH3D-16 — phòng hở mặt ngoài không còn mất (đường bao căn trước `polygonize`)

- `apps/worker/pipeline_build/rooms.py` `_envelope_outlines`: đường bao căn = đóng hình thái tim tường + đoạn khép (nới 2 m, lấp lỗ, co lại); `polygonize` lại cùng đường khép. Ô ngoài phòng có sẵn (trừ phòng đã có, giữ mảnh lớn nhất) thành phòng khi ≥ 2 cạnh hộp bao sát đường khép và chứa nhãn chữ hay ≥ 4 m², và bao lồi của ô không ôm quanh phòng có sẵn (≤ 0,5 diện tích ô: vành giữa căn và khung ảnh).
- Cờ lô gia cho ô không nhãn 1,5–15 m², sâu ≤ 2 m, cạnh dài ≤ 4 m hay ≤ hai lần biên hở; xếp sau tên suy từ đồ đạc. Hành lang dài hở một đầu không còn thành lô gia.
- Thứ tự trong `build_rooms`: khép kín → hạt nhãn → đường bao → lô gia rìa (chữ ký không đổi). `_walled_sides`/`_near_walls` tách từ `_rim_outlines`.
- Khe góc/chữ T vượt ngưỡng ở mặt ngoài giờ vẫn ra phòng (test cũ chuyển sang kiểm `_gap_closers`/`_door_closers`). Lô gia rìa không nhãn sát đầu tường bên (4,5 thay 4,95 m²).
- Vòng review: ô đường bao còn lỗ (phòng kín giữa ô) chia bằng `_simple_parts` thành mảnh không lỗ, outline đã làm tròn chồng phòng có sẵn thì bỏ — không phủ lại phòng kín. Biên hở trên đường bao của phòng (trừ lô gia) xuất qua `closers_out` (`_open_edge_closers`, không nhãn, đầu chuỗi ở đầu tường) để `close_envelope_gaps` (BENCH3D-15, đã gộp) dựng tường vỏ.
- Không migration, không đổi hợp đồng/openapi.
