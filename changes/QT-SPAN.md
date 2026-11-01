# QT-SPAN — đoạn kích thước tổng bị đo bằng đường dóng cắt xuyên

- Làm gì: `packages/vision/dimensions/chains.py` — (1) `_line_row` xét cả hàng nằm trong hộp chữ (hộp OCR dư xuống dưới chân chữ, đường chữ đứng lên bị bỏ nên lấy nhầm đường chuỗi trong ở dưới), hoà thì lấy hàng tự phủ nhiều nhất; (2) `_ticks` bỏ nét đứng đi ra cả hai phía xa >= 3 lần tầm dò (đường dóng/trục cắt xuyên), trừ khi nằm ở đầu đường.
- Vì sao: three-bedroom, chữ "10275" ra 57 px (cặp đường dóng 335,5–392,5 của chuỗi trong) thay vì cả đường trục 1–7.
- Đo three-bedroom: "10275" 57,0 → 322,5 px (31,86 mm/px); cụm tỉ lệ 27,82 (3 mẫu) → 31,19 (5 mẫu).
- Đo ch-01..14 (span_px mới/cũ, cùng text.json + page.png): đổi 80 chuỗi ở 13 ca (ch-08 không đổi); với chữ số so `mm_per_px` đáp án: 20 gần hơn, 7 xa hơn, 3 bằng.
- Cụm tỉ lệ (lệch 3 %) so đáp án: 11 ca giữ nguyên; ch-03 cùng 13,91 nhưng 5 → 17 mẫu; ch-13 29,68 (3,6 %) → 30,38 (6,0 %) — cả hai đã ngoài 3 %, ca này vẫn sai trước và sau.
- Hệ số 3 chọn theo đo: 2 lần làm hỏng nhiều hơn (23 gần/12 xa); chỉ đổi hàng (không lọc đường cắt) 17/5 nhưng "10275" vẫn 57,5.
- Giới hạn: chuỗi trong mà MỌI vạch đều là đường trục cắt xuyên (không vạch riêng) sẽ bị lấy cả đường — cục bộ không phân biệt được với đường tổng.
