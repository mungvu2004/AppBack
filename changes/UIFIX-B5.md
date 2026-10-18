# UIFIX-B5 · G3-13: hạ vai / vô hiệu không được bỏ dự án không còn người sửa

- `apps/api/project_members/service.py`: thêm hàm công khai `require_editors_left(db, user_id)`. Với mỗi dự án còn sống mà người này là thành viên (`project_id ASC`), hàm khoá tập người sửa bằng `lock_editor_ids` (cùng khoá với N4) rồi dùng lại `_require_not_last_editor`. Nếu người này là người sửa cuối, trả 422 `MEMBER_LAST_EDITOR`.
- `apps/api/users/service.py`: `change_role` (#41) gọi hàm này khi vai mới không thuộc `EDITOR_ROLES`. `disable_user` (#42) gọi khi người đó chưa `disabled`. Hàm chạy sau `forbid_self`, trước mọi lệnh ghi.
- Thứ tự khoá: tập admin, rồi người mục tiêu (`users`), rồi membership. Đây cũng là thứ tự `delete_user` đang dùng.
- Test: `apps/api/users/tests/test_last_editor.py`, gồm 4 test (2 case bị từ chối, 2 case được phép).
- Không có mã lỗi mới, không có migration, không đổi `openapi.json`.
