# MULTI-FLOOR-02 · Dựng song song nhiều tầng một dự án không còn deadlock

- Hiện tượng (thử thật trên f14, 02/11): tải một tờ 3 mặt bằng cho 3 tầng (MULTI-FLOOR-01), ba lượt dựng chạy song song; một tầng hỏng ở `spatialDataBuild` với `INTERNAL`, log worker `DeadlockDetectedError` trong `touch_project` (`apps/api/projects/summaries.py`).
- Gốc: lượt ghi chèn dòng con trỏ `projects.id` (phiên bản…) → khoá ngoại để `KEY SHARE` trên dòng dự án; rồi `touch_projects` xin `SELECT … FOR UPDATE`, khoá này xung đột với `KEY SHARE` của lượt kia → hai lượt chờ nhau.
- Sửa: `touch_projects` khoá bằng `FOR NO KEY UPDATE` (`with_for_update(key_share=True)`) — đúng khoá mà `UPDATE updated_at` tự xin; vẫn tuần tự hoá các lượt chạm, giữ thứ tự id (NO-142), nhưng không chờ khoá ngoại.
- Test: `apps/api/projects/tests/test_summaries.py::test_touch_project_does_not_wait_for_foreign_key_share_lock` (một phiên giữ `FOR KEY SHARE`, `touch_project` phải xong trong 5 s); thử đột biến trả về `FOR UPDATE` → test hỏng. Test hình dạng SQL đổi sang `FOR NO KEY UPDATE`.
- Thử lại trên f14 (vá nóng): cùng kịch bản 3 tầng qua giao diện → 3/3 tầng `completed`, 0 deadlock trong log.
