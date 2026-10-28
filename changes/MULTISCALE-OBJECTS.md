# MULTISCALE-OBJECTS — lượt phóng thêm cho bộ dò đồ đạc (B1 vật sót)

- `YoloOnnxDetector(multiscale=True)` (bước pipeline bật; đánh giá model giữ một lượt): thêm lượt phóng theo cỡ cửa của lượt gốc,
  ứng viên mọi cỡ đi chung `merge_candidates`, chỉ cộng hộp mới (lọc trùng IoU ≥ 0,3, lọc chứa ≥ 60%), hộp gốc giữ nguyên.
- Sửa phép "mép trang" của `_cut_edge_touches` chịu sai số làm tròn (lát của lượt phóng là số thực).
- Không đổi API, DB, migration, hợp đồng FE–BE, payload.
- Cổng áp dụng: lint/type, test apps/ml/objects. Migration/hợp đồng: không áp dụng.
- Ngưỡng B2 (`LABEL_CONFIDENCE_MIN`, hiệu chỉnh trên CubiCasa val thu nhỏ/JPEG/phủ màu) và tắt `stair` ở bước pipeline (`labels.pipeline_labels`).
