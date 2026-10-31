# UX-R5 — đợt sửa UX vòng 5 (AppBack/AI)

## be-ocr — UX-02: kích thước đọc được thành `Dimension`

- Nguyên nhân gốc (đo trên 14 ca bench, mã `main` 89064a64): OCR trên f14 chạy model thật (`rapidocrRec`,
  `ML_BACKEND=onnx`) và đọc được số; ch-03 có 10 mẫu chuỗi, suy đúng 13,915 mm/px (đáp án 13,918). Nhưng bước 7
  của `build_layer` chỉ dựng `Dimension` từ mẫu ghép tường (`t…-w…`), bỏ qua mẫu chuỗi — mà mẫu chuỗi mới là thứ
  quyết tỉ lệ. Kết quả 11/14 ca có 0 `Dimension` → FE (`dimensionCount === 0`) báo "Không đọc được số kích thước nào".
- `apps/worker/pipeline_build/build.py` `_chain_dimensions`: chữ chỉ có mẫu chuỗi, trong ngưỡng 2 % của `s`, chưa có
  `Dimension` ghép tường → một `Dimension` `linear`, `referenceIds` rỗng, đoạn dài `span_px` giữa hộp chữ theo chiều dài
  hộp. Tỉ lệ, tường, phòng không đổi (bảng `F:/runs/r5-be-ocr/KET-QUA.txt`): ca có `Dimension` 3/14 → 8/14.
- Chưa sửa: ch-04/ch-05/ch-08 chữ số cao ~3 px trên ảnh 1290 px (phóng 2-4× vẫn 0 số dò được), không đọc nổi bằng OCR;
  ghi chú "TL: 1/100" đọc được nhưng ảnh raster không biết khổ giấy (ch-04: 1/100 + A3 cho 32,6 mm/px, đáp án 14,6).
