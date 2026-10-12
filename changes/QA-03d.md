# QA-03d — pytest cho năm hàng danh mục không kiểm an toàn qua HTTP (P13)

- Chỉ thêm test, không đổi mã sản phẩm: BE1-G-009 (`core/tests/test_idempotency.py`), BE1-G-042
  (`projects/tests/test_service.py`, #26 trọn qua HTTP), BE1-G-099 (`project_members/tests/test_add_member.py`),
  BE2-G-083 (`drawings/tests/test_routes_complete.py`), BE2-G-234 (`drawings/tests/test_routes_progress.py`).
- BE2-G-083 là ứng viên bug (NO-417, đổi NO-419 ở QA-03e vì trùng id nhánh khác): kho chập chờn ở #7 bước 2 thành dòng `rejected` vĩnh viễn; test viết theo
  hành vi đúng và đánh `xfail(strict=True)` — `case_gate` (BE-00 §12) cấm xfail, nên bước 5b hỏng tới khi sửa xong
  (sửa xong thì test XPASS → gỡ dấu xfail trong chính commit sửa).
- Không endpoint, không bảng, không migration, không đổi hình dạng dây: bước 6, 7, 8 không có gì mới để kiểm.
- QA-03e (FIX-2330, BUG-568): `apps/api/drawings/complete.py` `complete_upload` ném tiếp `AppError` 5xx khi dựng
  `original.*` (kho 503) thay vì `_reject` → dòng giữ `receiving`, #7 gửi lại được; 4xx của tệp vẫn `rejected`.
  Gỡ xfail của `test_complete__storage_error_503_keeps_upload_receiving`; NO-419 đóng. Không đổi hình dạng dây.
- QA-03e (FIX-2331, BUG-513, người dùng duyệt 2026-10-12 theo khuyến nghị; sửa hiến chương ở commit docs riêng có Charter-Approved): #27 `DELETE /api/projects/{project_id}`
  đòi thành viên **và** vai hệ thống `admin` (`require_project("admin")`, `apps/api/projects/access.py`) thay vì
  `project.settings.edit` — khớp FE chỉ mở vùng nguy hiểm cho admin; engineer/viewer thành viên → 403 `FORBIDDEN`,
  người ngoài vẫn 404 trước (K08). Không thêm vai theo dự án, không đổi ma trận gương FE (H3). "Xoá mọi tầng" của FE
  là chuỗi `DELETE /floors/{id}` (FloorManager cũng dùng cho engineer) nên không đổi. BE-BIND #27 cột Khoá → `admin`.
  Không đổi hình dạng dây, openapi không đổi.
