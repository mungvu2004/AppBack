# FE3D-ROOF · Lưu mái Pascal (roof-contract.md)

- `packages/domain/spatial/model.py`: `Roof` (id `RF-`, `levelId`, `nodes` 1..33 object JSON, JSON cả mái ≤ 64 KB, không `NaN`); `SpatialLayer.roofs` và `SpatialGraph.roofs` mặc định `()`, rỗng thì vắng khoá khi dump (jsonb tài liệu cũ không đổi).
- Diff: một mái là một thực thể, trường theo dõi duy nhất `nodes` → thêm/sửa/xoá = đúng một mục `entityType: "roof"`. Toàn vẹn: `duplicateId`, `levelMembership` tính cả mái.
- Lõi: `SpatialKind` thêm `roof` (`RF`), `VersionEntityType`/`CHANGE_ENTITY_TYPES` thêm `roof`.
- Migration `r20261024_fe3d_roof` (contract): thay CHECK `ck_floor_change_log_entity_type` để nhận `'roof'`. Cần người điều phối đăng ký ở `docs/contracts.toml`.
- Dây: `RoofOut`, `roofs` tuỳ chọn ở `SpatialLayerOut`/`SpatialGraphOut` → `openapi.json` đổi (người điều phối xuất lại).
- Đổi tỉ lệ, luật hậu kỳ AI, gộp pipeline giữ nguyên mái hiện có.
- Không endpoint mới, không mã lỗi mới, không nâng `schema_version`.
