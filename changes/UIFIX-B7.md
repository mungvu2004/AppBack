# UIFIX-B7 — review UI/UX, gói backend B7 (N5-08, G1-15)

- Thêm route chỉ đọc `GET /api/projects/{project_id}/pipeline-runs` (`drawings_list_pipeline_runs`, N7b) trong `apps/api/drawings/run_history.py`: liệt kê lượt chạy pipeline của dự án, mới nhất trước, `CursorPage` (`limit` 1..200, mặc định 50, + `cursor` ký HMAC). Quyền: thành viên dự án (`require_project()`), người ngoài/dự án không có → 404. Tầng đã xoá mềm bị bỏ.
- Schema `PipelineRunOut`/`PipelineRunPage` trong `apps/api/drawings/schemas.py`; router đăng ký trong `ROUTERS` của `apps/api/drawings/router.py`.
- `GET /api/notifications` (#19) nhận thêm `limit` (1..200) và `cursor` tuỳ chọn; thân vẫn là mảng trần. Còn dòng cũ hơn thì header `X-Next-Cursor`. Không truyền gì → như cũ (tối đa `NOTIFICATIONS_LIST_MAX`).
- Test: `apps/api/drawings/tests/test_routes_runs.py` (9 test), thêm 5 test vào `apps/api/notifications/tests/test_routes_list.py`.
- BE-BIND: thêm dòng N7b. Cần điều phối: xuất `openapi.json`; sửa `tools/tests/test_charter.py:32` (37 → 39 dòng N, gồm N10b của B2); FE thêm mục `drawings_list_pipeline_runs` vào `schema-map.ts` + `src/api/schemas/pipelineRuns.ts` rồi nâng `APPFRONT_SHA`, nếu không bước contract "Bản đồ đủ" đỏ.
