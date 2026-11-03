# BENCH3D-15 — vỏ tường: đoạn khép phòng ở mặt ngoài thành tường (bench-3d đợt 3, làn L4)

- `apps/worker/pipeline_build/rooms.py` `build_rooms`: tham số tuỳ chọn `closers_out` nhận các đoạn khép phòng không có tường (`_door_closers` kèm nhãn hộp, rồi `_gap_closers`) dạng `geometry.RoomCloser`; phòng dựng ra không đổi.
- `apps/worker/pipeline_build/geometry.py` `close_envelope_gaps(closers=...)`: đoạn khép nằm ở mặt ngoài (đúng một bên là phòng) → khe < 600 mm kéo tường chủ thẳng hàng, dài hơn thành tường mới: mang ô mở của hộp cửa đi/cửa sổ sinh đoạn (bỏ nếu hộp đã thành ô mở cùng loại trên tường song song/thẳng hàng có khoảng chiếu giao khe, `_opening_near` — không xét theo khoảng cách tâm), hoặc cửa sổ tin 0,3 khi trang có ≥ 2 nét kính dọc khe (`_glazed`), còn lại tường đặc. Khe trong nhà, khe không bên nào là phòng (sân trong) giữ hở; đoạn chồng/cắt tường đang có bỏ qua (W4).
- R2': khe đoạn nối 3b trên tường ngoài của phòng `loggia`/`utility`/`other` → tường đặc, không đoán cửa đi.
- `build.py` `_assembled`: nối closers từ `build_rooms` sang `close_envelope_gaps`.
- Test: `tests/test_envelope_closers.py`; `test_e2e_real` seed cửa chính vào phòng utility/lô gia giờ khép bằng tường đặc.
- Không đổi hợp đồng/openapi, không migration.
