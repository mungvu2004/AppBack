# FE3D-B3 · Ẩn tầng trong cảnh 3D (FE3D-FIX-003)

- Migration `r20261021_fe3db3` (expand, sau `r20261020_fe3db2`): cột `floors.hidden_in_3d` BOOLEAN NOT NULL `server_default false`; dòng cũ nhận `false`, không backfill.
- `FloorOut` (`apps/api/projects/wire.py`, dùng chung #10 #11 #12 #13 #33 #34 và `project.floors`): trường `hiddenIn3d` luôn có (alias tay — `to_camel` ra `hiddenIn3D`).
- PATCH #34 (`FloorPatchIn`): `hiddenIn3d` tuỳ chọn, chỉ nhận boolean JSON (chuỗi/số/`null` → 422 `VALIDATION`); cùng giá trị = không ghi, không nhật ký (như khoá khác).
- POST #10 không nhận khoá này (tầng mới luôn hiện); khôi phục tầng xoá mềm đặt lại `false`.
- Quyền không đổi (`layer.edit`). Không mã lỗi mới; `openapi.json` để người điều phối sinh lại.
- Hợp đồng: AppFront `FloorSchema` đã đọc khoan dung `hiddenIn3d` (thẻ R1); ghim `APPFRONT_SHA` f3781ade, bước 7 đạt.
