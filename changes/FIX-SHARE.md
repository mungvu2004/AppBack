# FIX-SHARE — quyền xuất mô hình + liên kết chia sẻ kiểm ở máy chủ

- Module mới `apps/api/share_links` (router tự dò qua `ROUTERS`).
- `POST /api/projects/{project_id}/exports` — `require_project("model.export")` (admin, engineer); trả `SpatialGraphDocumentOut` (N15).
- `GET|POST /api/projects/{project_id}/share-links`, `DELETE .../share-links/{link_id}` (BE-BIND #47-#49) — `require_project("share.create")`; 404 người ngoài trước 403 viewer.
- `GET /api/share/{token}` công khai, chỉ đọc; token lạ/hết hạn/thu hồi → 404 `resource:"share_link"`.
- Bảng mới `share_links` (migration expand thuần `r20261025_share_links`, không `# contract:`); `IdPrefix` thêm `shl`.
- Test: `apps/api/share_links/tests/test_routes.py` (3 test). CHƯA CHẠY: Docker tắt lúc làm.
- Cần điều phối: xuất `openapi.json`; BE-BIND #47-49 đổi chủ từ v2; FE thêm schema-map + bật `SHARE_LINKS_SUPPORTED`.
