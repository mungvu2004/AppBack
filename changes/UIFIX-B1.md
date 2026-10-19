# UIFIX-B1 — review UI/UX, gói backend B1 (thư và thông báo)

- Thư mời và thư đặt lại mật khẩu (`apps/api/auth_recovery/messages.py`): tên sản phẩm "AppFront"; hạn dùng theo `Asia/Ho_Chi_Minh` ghi "(giờ Việt Nam)"; câu viết hoa đầu câu; thư đặt lại thêm câu "nếu bạn không yêu cầu thì bỏ qua"; thư mời thêm câu "liên kết trong thư cũ không còn dùng được". (G1-07, G2-11)
- Thư mời nêu người mời và vai (`apps/api/auth_recovery/jobs.py`): đọc tên người mời từ nhật ký `user.invite`/`user.invite_resend` mới nhất và vai từ `users.role`, trong cùng câu truy vấn của lô. (G2-11)
- `POST /users/invitations` (#44): email của người `pending` đang chờ → 409 `USER_INVITE_PENDING` `field:"emails"`, cả lô không tạo gì, không gửi thư. Trước đây mời lại sẽ thay token và gửi thêm thư. `active`/`disabled` vẫn trả 422 `USER_EMAIL_TAKEN` và được xét trước. Muốn gửi lại thì dùng #45. (G2-8)
- Thông báo `aiCompleted`: câu thành `Dự án <tên>: Hệ thống AI đã xử lý xong bản vẽ` (FE nối tên tầng phía sau); tên rỗng sau làm sạch thì giữ câu cũ. Thông báo đã có trong DB không đổi. (G1-13)
- Test: `auth_recovery/tests/test_messages.py`, `test_jobs.py`, `notifications/tests/test_messages.py`, `users/tests/test_invite.py`, `users/tests/test_service.py`.
