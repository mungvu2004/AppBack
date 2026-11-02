# BENCH3D-06 — tường: khép khe tường ngoài không dựng tường chồng lên tường đã có (W4)

- Gốc hồi quy W4 (cn-03, cn-08, cn-21, ch-11 r2): `_bridge_segments` sinh một đoạn nối cho **mỗi** cặp thẳng hàng,
  nên tường đứt nhiều mảnh cho ra các đoạn nối xoè từ một đầu tới từng mảnh. Trước đợt 1 chúng chỉ khép phòng; từ C5
  (`close_envelope_gaps`) mỗi đoạn trên mặt ngoài thành tường mang cửa → tường mới chạy dọc mảnh tường thật.
- `close_envelope_gaps` bỏ đoạn nối mà tường qua khe sẽ chồng song song lên tường đang có (kể cả tường qua khe vừa dựng)
  theo `_clash` — cùng luật WALL-OVERLAP của FE đã chặn lượt kéo tường ở 3b. Áp cho cả khe hẹp (kéo tường chủ).
- Không đổi API, DB, migration, hợp đồng FE–BE.
- Cổng áp dụng: lint/type, test `apps/worker/pipeline_build`.
