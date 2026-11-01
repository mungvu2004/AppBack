# LIB-FILES — mẫu nội thất từ tệp GLB thật trong thư viện

- Danh mục thứ hai bên cạnh `CATALOGUE` dựng bằng mã: `packages/domain/library/files.json` (63 mẫu CC0/MIT/CC-BY 4.0: id, tên, nhóm, giấy phép, tác giả, nguồn, `sha256`), nạp và kiểm lúc nhập module (`files.py`). Tệp nhị phân ở ngoài git.
- Nhóm mới `decor` (cây, thảm, rèm, đèn bàn, đồ trang trí): CHECK `ck_library_items_item_group` dựng lại bằng migration `r20261102_lib_decor_group` (sau `r20261102_mf_01`), ghi ở `docs/contracts.toml`.
- `measure_glb` (Python thuần): hộp bao thế giới + số tam giác từ chính tệp GLB; khớp `build_glb` cho cả 16 mục dựng bằng mã.
- Seed giữ mẫu từ tệp (không rút); lịch phát hành vẫn bỏ qua chúng. CLI mới `python -m apps.api.library.cli import-files <dir>`: so `sha256`, đo, đẩy `model.glb` (+ `preview.png` nếu có), ghi dòng đã phát hành.
- API: `LibraryItemOut.attribution` tuỳ chọn ("<tác giả> · <giấy phép>", CC-BY bắt buộc ghi công); openapi sinh lại; hợp đồng FE ghim AppFront `607c71db` (nhận `decor` + `attribution`).
- Cổng đầy đủ 02/11: hỏng 1/9487 ở `test_sweep_resends_quality_check` (nợ NO-430 đã có, chạy riêng 17/17 đạt); chạy lại bước 3, 5, 5b, 6, 7, 8 đều đạt.
- Nợ (mở, từ merge-review lượt 1, P3): `_file_plan` đo tệp trước khi so `sha256` — tệp hỏng có thể ném lỗi ngoài nhóm bắt và dừng cả lệnh, tệp có một chiều 0 mm được `put` rồi mới vi phạm CHECK `published`; sửa: so sha trước, chiều ≤ 0 → `failed`. Thiếu test nhánh tệp không đọc được, hai nhánh lỗi của `measure_glb` và log lỗi. Gói 63 tệp nhị phân chỉ có trên máy F:/runs/can-mau/library-import/out — cần một nơi lưu dùng chung.
