# BENCH3D-06 — tường: khép khe tường ngoài không dựng tường chồng lên tường đã có (W4)

- Gốc hồi quy W4 (cn-03, cn-08, cn-21, ch-11 r2): `_bridge_segments` sinh một đoạn nối cho **mỗi** cặp thẳng hàng,
  nên tường đứt nhiều mảnh cho ra các đoạn nối xoè từ một đầu tới từng mảnh. Trước đợt 1 chúng chỉ khép phòng; từ C5
  (`close_envelope_gaps`) mỗi đoạn trên mặt ngoài thành tường mang cửa → tường mới chạy dọc mảnh tường thật.
- `close_envelope_gaps` bỏ đoạn nối mà tường qua khe sẽ chồng song song lên tường đang có (kể cả tường qua khe vừa dựng)
  theo `_clash` — cùng luật WALL-OVERLAP của FE đã chặn lượt kéo tường ở 3b. Áp cho cả khe hẹp (kéo tường chủ).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test `apps/worker/pipeline_build`.
- Lượt 2: 3b (f) `_drop_dangling_nibs` bỏ thêm mẩu < 200 mm không chạm hộp ô mở mà **cả hai đầu** nằm trong thân cùng
  một tường khác (≤ ½ dày tường đó + 10 mm, `_buried`) — mẩu thò 11–62 mm ở chữ T/góc trước đây lọt vì đầu nào cũng
  "chạm" tường. Mẩu nối hai tường (má cửa, đoạn nối hai tường song song) vẫn giữ.
- Lượt 2: `close_envelope_gaps` tìm tường chủ trên danh sách đang sửa, không trên `wall_set.walls` gốc: tường chủ đã kéo
  qua một khe không bị kéo lùi khi khe thứ hai chung đầu mút.
