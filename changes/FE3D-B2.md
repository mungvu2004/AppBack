# FE3D-B2 · Phong cách cảnh 3D theo dự án (FE3D-FIX-003)

- Migration `r20261020_fe3db2` (expand, sau `r20261004_b1_03_fix325`): cột `project_settings.scene_style` TEXT NULL + CHECK `ck_project_settings_scene_style_values` (5 id `am-ap`, `hien-dai-sang`, `go-am`, `toi-gian`, `sang-trong-toi`, chép từ AppFront `sceneStyles.ts`).
- N5/N6 (`apps/api/project_settings`): trường tuỳ chọn `sceneStyle`; GET trả khi có, NULL → vắng (như `notes`).
- PUT N6: vắng `sceneStyle` = **giữ** giá trị đang lưu (client cũ không xoá phong cách người khác chọn); `null` = xoá; id lạ → 422 `body.sceneStyle`. Băm C09b của thân không có khoá này không đổi.
- Quyền không đổi (`project.settings.edit`). Không mã lỗi mới; `openapi.json` để người điều phối sinh lại.
- Hợp đồng: AppFront `ProjectSettingsSchema` đang strict, chưa có `sceneStyle` → FE đã đọc khoan dung khi ghim `APPFRONT_SHA` f3781ade, bước 7 đạt (mẫu golden `settings_replace_settings/C01_scene_style-*` mang khoá này).
