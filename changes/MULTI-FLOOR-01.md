# MULTI-FLOOR-01 · Một tờ nhiều mặt bằng: mỗi tầng một vùng cắt

- `apps/api/drawings/schemas.py`: `CropRect` (`xRatio, yRatio, widthRatio, heightRatio`, khoá lạ bị chặn); `InitUploadBody.crop` tuỳ chọn. Mỗi tỉ lệ trong [0,1], vùng nằm trong trang (dư 1e-6), diện tích ≥ 0,01; sai → 422 `VALIDATION`, `field` là `crop` hoặc `crop.<khoá>`. Không dùng ngưỡng 5 % của #31.
- `packages/db/models/drawings.py` + migration `r20261102_mf_01` (chỉ thêm cột, trên `r20261102_lb_01`): `uploads.crop_corners` JSONB null, 4 góc TL,TR,BR,BL như `quality_assessments.corners`.
- `apps/api/drawings/uploads.py`: lưu crop thành 4 góc; khử trùng lượt #5 tính cả `crop_corners`.
- `apps/worker/pipeline_orchestrate/start.py`, `preprocess.py`: `PageSource.crop`; `choose_path` thay đường `auto` bằng đường `user` với góc crop. Góc dùng lại và góc #31 của chính lượt tải vẫn thắng. Góc crop được lưu vào đánh giá nên #31 sau đó cắt tiếp từ trang gốc.
- Ảnh raster đã xoay theo EXIF (`raster.py:118`), khớp ảnh trình duyệt hiển thị.
- Wire: chỉ thêm một trường tuỳ chọn ở thân #5; phản hồi không đổi. `docs/contracts/openapi.json` sinh lại.
- Test: `apps/api/drawings/tests/test_routes_init.py` (lưu góc, khử trùng theo crop, 7 crop sai → 422, biên 1e-6), `apps/worker/pipeline_orchestrate/tests/test_preprocess.py` (chọn đường, cắt 800×600 → 400×300).
- Thử thật trên f14: tờ CubiCasa 3 mặt bằng → 3 tầng, ảnh mỗi tầng đúng kích thước vùng (592×485, 592×659, 617×609); crop vượt trang → 422.
- Nợ: worker không chạy `find_frame` trong vùng cắt (khung tên nằm trong vùng vẫn giữ); PDF vector đọc ghi chú tỉ lệ của cả tờ. Hai head alembic nếu `feat/library-file-models` vào main trước: nối lại `down_revision`.
