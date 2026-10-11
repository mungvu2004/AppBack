# QA-02b — câu thông báo viết hoa chữ đầu (nợ ND-C5)

- `apps/api/notifications/messages.py`: ba câu cố định viết hoa chữ đầu theo luật chữ A6 của FE
  ("Bạn vừa được thêm vào dự án", "Hệ thống AI đã xử lý xong bản vẽ", "Phát hiện N vi phạm luật ở");
  câu mở bằng tên người ("{tên} đã thêm bạn vào dự án") giữ nguyên.
- Test và factory (`packages/testing/factories/notifications.py`) đổi theo câu mới; thêm một test chặn câu cố định viết thường.
- Không endpoint, không bảng, không migration, không đổi hình dạng dây: bước 6, 7, 8 không có gì mới để kiểm.
- Dòng thông báo đã lưu trước đây giữ câu cũ (không migration dữ liệu).
- Lệch khỏi prompt B4-02 [6] "Câu" (bảng câu viết thường, `backend/prompts/B4-02.md:138-140`): câu cố định nay viết hoa chữ đầu theo luật A6 của FE (nợ ND-C5, QA-02b); `test_messages.py` khẳng định câu mới.
