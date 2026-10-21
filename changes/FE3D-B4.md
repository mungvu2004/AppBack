# FE3D-B4 · Tuỳ chọn tài khoản lưu ở máy chủ (FE3D-FIX-003)

- Migration `r20261021_fe3db4` (expand, sau `r20261021_fe3db3`): cột `users.preferences` JSONB NOT NULL `server_default '{}'` + CHECK `ck_users_preferences_object` (`jsonb_typeof = 'object'`); dòng cũ nhận `{}`, không backfill.
- N11/N12/N14 (`MeSchema`): `preferences` luôn có (object, có thể `{}`), hình dạng khớp FE `UserPreferencesSchema`: `appearance{themeChoice light|dark|system, viewportDark, reducedMotion, showGrid, density comfortable|compact}`, `notifications{<loại>: {inApp, email}}`, `seen{welcome, tours[]}`.
- Khoá của `notifications` = loại thông báo server gửi: `aiCompleted`, `violationFound`, `projectInvite`. Loại khác (kể cả `commentMention` của FE) → 422 `VALIDATION`.
- PATCH N12 `preferences` = bản vá gộp sâu: khoá vắng giữ nguyên; khoá có giá trị ghi; `null` ở bất kỳ khoá con nào xoá khoá đó; object gộp tiếp; `seen.tours` thay cả danh sách (≤ 64 id `^[A-Za-z0-9_.:-]{1,64}$`); một ô thông báo phải đủ `{inApp, email}` (boolean JSON thật) và thay cả ô; `preferences: null` xoá hết về `{}`. Khoá lạ ở mọi tầng → 422. Đọc-gộp-ghi dưới `SELECT … FOR UPDATE` (hai PATCH song song không mất bản vá).
- `notify` (`apps/api/notifications/service.py`): người nhận có `notifications.<kind>.inApp = false` → không ghi dòng, không phát, trả `None`. Kênh email chưa có ở BE (chỉ lưu lựa chọn).
- Quyền không đổi (chính người gọi). Không mã lỗi mới; `openapi.json` để người điều phối sinh lại.
