# FE3D-B · Trường Pascal trên tài liệu không gian (FE3D-FIX-003, B1)

- `packages/domain/spatial/model.py`: `MaterialRef` (`^(library|scene):[a-z0-9_-]{1,64}$`), `RoomFinish`, `FurnitureVariant` (35, chép FE `types.ts`); Room `finish`, `floorMaterial`; Wall `paint {interior, exterior}`; Furniture `variant`, `heightMm` (≥1), `liftMm` (≥0), `model {id ≤120, src /items/<id>/model.glb}`, `slots` (≤8, khoá `^[a-z][a-z0-9_]{0,23}$`). Tất cả tuỳ chọn, vắng khoá khi không có.
- Lưu trong JSONB tài liệu tầng: không bảng, không migration. N16 PUT nhận qua `SpatialLayer`; N15/N16/#35 trả qua `apps/api/spatial_read/wire.py`.
- `diff.py` `_TRACKED_FIELDS`: thêm `paint`, `finish`, `floor_material`, `variant`, `height_mm`, `lift_mm`, `model`, `slots` (nhật ký thay đổi).
- `samples.py`: `PASCAL_FIELDS` + `with_pascal_fields` (mẫu A14 giữ nguyên vì là gương fixture FE; mẫu hợp đồng 2xx có trường mới qua `test_spatial_write_layer__C01_pascal_fields`).
- Không endpoint mới, không mã lỗi mới. `openapi.json` do người điều phối xuất lại; `APPFRONT_SHA` = f3781ade (người điều phối ghim, bước 7/8 đạt).
