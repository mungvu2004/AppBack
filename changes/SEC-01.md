# SEC-01 — `qc.approve` kiểm ở máy chủ (NFR-02)

- Trước: duyệt QC (cấp `reviewed=True`) đi qua #35 ghi lớp và N19 phục hồi, cả hai chỉ đòi `layer.edit`;
  khoá `qc.approve` của ma trận chỉ được giao diện kiểm.
- Sửa `apps/api/spatial_write/writer.py`: `write_layer(may_approve=...)` (mặc định `False`, đóng). Dưới khoá tầng,
  so tài liệu hiện tại với lớp + kích thước sắp ghi; có mục **mới** mang `reviewed=True` mà thiếu quyền → 403 `FORBIDDEN`.
  #35 (`spatial_write/router.py`) và N19 (`versions/service.py`) truyền `can(role, "qc.approve")`; pipeline không truyền.
  Thứ tự lỗi: 404 (người ngoài) → 403 `layer.edit` (viewer) → 422/409 của thân → 403 `qc.approve` (cần tài liệu đã khoá).
  Bỏ duyệt hay giữ dấu duyệt cũ không cần `qc.approve`.
- Test mới: `apps/api/spatial_write/tests/test_routes_approve.py`, `apps/api/versions/tests/test_routes_restore_approve.py`;
  fixture `packages/testing/fixtures/permissions.py` (`engineer_without_qc_approve`) vì ma trận thật cho `qc.approve`
  và `layer.edit` cùng giá trị ở mọi vai.
- `model.export`, `share.create`: không có tuyến máy chủ nào (xuất dựng ở trình duyệt từ dữ liệu thành viên được đọc;
  share-links #47–49 là v2 theo BE-BIND) — không có gì để gác ở BE.
- Không endpoint mới, không bảng, không migration, không đổi dây (403 thân W7 đã có): bước 6, 7, 8 không có gì mới.
