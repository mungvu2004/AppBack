# BENCH3D-22 — OCR: số dọc đọc ngược, đọc lại trang nhỏ chưa ra tỉ lệ

- `apps/ml/text/reader.py` `_best`: lượt đọc thẳng ra số nguyên ≥ 3 chữ số có 0 đứng đầu (`0009`) → luôn đọc thêm lượt 180°, nhận khi ra số không 0 đầu, cùng độ dài, tin cậy ≥ 0,5 (f-19 → tỉ lệ đúng).
- `apps/ml/text/tasks.py` `read_page`: trang cạnh dài < 2000 px chưa ra tỉ lệ chuỗi → đọc lại trên ảnh ×2 + giãn mức xám, chỉ nhận khi lượt lại ra tỉ lệ; bỏ khi chữ ngang và dọc đều đã ra tỉ lệ riêng (ch-01 +8 % → +0,1 %).
- Chi phí: thêm một lượt OCR CPU cho trang không có chuỗi. Không đổi schema `text.json`/hợp đồng.
