# QA-09b — gắn mã catalog B09-* vào docstring test pytest

- Chỉ sửa docstring của 80 test (38 file test): thêm dòng `Catalog: B09-<màn>-<nnn>.` để cổng phủ phase 09 (`qa/tools/coverage-gate.mjs`) ánh xạ được hàng catalog BE tới test.
- Test đã có `Catalog:` từ phase 08 giữ nguyên id cũ, id B09 nối thêm sau dấu phẩy.
- Không đổi mã nguồn, thân test, endpoint, bảng, migration, dây: bước 6, 7, 8 không có gì mới để kiểm.
