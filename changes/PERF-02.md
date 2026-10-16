# PERF-02 — `vectorize_with_stats` treo vô hạn trên trang CubiCasa thật

- Triệu chứng (bao-cao A1f): 5/20 trang test chạm trần 60 s, mặt nạ classic trang 1191 > 30 phút; trang xong thì ≤ 0,19 s.
- Gốc: không phải vòng siêu tuyến tính mà là vòng **vô hạn** ở `_resolve`. Nhánh xương đi từ một cụm giao về chính
  cụm đó (sót lại sau khi bỏ râu) cho đoạn dài 0 có `a_key == b_key`; `_drop_short` ghi `alias[k] = k`, đoạn giữ lại
  dùng khoá `k` thì `_resolve` quay mãi. Vài đoạn ngắn khép vòng cũng cho chu trình như thế.
- Sửa `packages/vision/walls/vectorize.py` `_drop_short`: nối theo gốc nhóm (union-find), bỏ qua khi hai khoá đã chung nhóm.
  Đổi kèm theo: chuỗi đoạn vát góc dùng chung khoá trước đây bị ghi đè `alias[b]` (mất một lần nhập), nay nhập trọn
  cả nhóm — đúng ý "nhập hai khoá làm một", đầu ra có thể đổi trên trang có chuỗi vát góc như thế.
- Test mới `test_vectorize__branch_back_to_its_own_junction_terminates` (mặt nạ SegFormer 16 x 14 cắt từ trang 7809,
  hạn 10 s trong luồng nền): đỏ trước sửa (hết hạn), xanh sau; `packages/vision/walls` + `apps/ml/walls` 211 xanh.
- Không endpoint, không bảng, không migration, không đổi dây: bước 6, 7, 8 không có gì mới để kiểm.
- Lỗi khác tìm thấy lúc dò: mặt nạ toàn `True` làm `approxPolyDP` ném lỗi (NO-427, `DEBT.md`); lỗi treo là NO-426 (đóng).
