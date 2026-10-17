# QA-11b — gắn mã catalog B11-* vào docstring test pytest

- Chỉ sửa docstring của test trong 16 file test: thêm dòng `Catalog: B11-<màn>-<nnn>.` để cổng phủ phase 11 (`qa/tools/coverage-gate.mjs`) ánh xạ được hàng catalog BE tới test.
- Test đã có `Catalog:` từ phase trước giữ nguyên id cũ, id B11 nối thêm sau dấu phẩy.
- Không đổi mã nguồn, thân test, endpoint, bảng, migration, dây: bước 6, 7, 8 không có gì mới để kiểm.
