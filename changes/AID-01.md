# AID-01 — AI chọn phong cách và đồ nội thất (Gemini qua Vertex)

- Sau khi pipeline nhận diện một tầng xong (`pipeline_quality` bước cuối), `enqueue_auto` xếp một lượt "AI tự chọn kiểu"
  cho **dự án** (một phong cách cho cả căn). Task `design.director.run` (hàng `default`): chọn kiểu → chọn sơn, sàn, mẫu đồ
  theo vai trò từ bảng ảnh đánh số (Gemini không thấy tên/id mẫu) → kiểm luật (ΔL sàn–tường ≥ 8, sàn khô không hoa văn)
  → bổ sung đồ (Gemini nói món + cạnh tường, mã đặt bằng shapely). Kết quả là bản JSON trong bảng mới `design_concepts`,
  **không ghi vào tài liệu tầng**; FE dựng phong cách từ nó.
- N47 `GET`/N48 `POST /api/projects/{project_id}/design-concept`: trạng thái + chọn 1 trong 12 kiểu (cùng đầu vào thì dùng lại).
- Gói mới `packages/genai` (cổng `GenAI`, `VertexGemini`, google-auth), `packages/domain/design_director` (12 kiểu, dữ liệu
  vật liệu tĩnh + bảng ảnh, xếp hạng ứng viên, prompt, kiểm), `apps/api/design_director`, `apps/worker/design_director`.
- DB: bảng `design_concepts` (migration `r20261102_aid_01`, chỉ mở rộng). W4 `dcn_`. Lịch `sweep_design_concepts`.
- Công tắc quản trị `DESIGN_DIRECTOR_ENABLED` mặc định **tắt**; khoá `DESIGN_DIRECTOR_VERTEX_SA_JSON` chỉ qua env. Hạn mức
  `DESIGN_DIRECTOR_DAILY_QUOTA` lượt/chủ dự án/ngày. Hồ sơ mẫu thư viện: `DESIGN_DIRECTOR_PROFILES_PATH`.
- Charter: BE-00 (W4 `dcn_`, việc nền), BE-BIND (N47, N48; 49 + 2 + 50), HOP-DONG-MOI §12 — người dùng duyệt 2026-11-02 ("oke").
- Lượt 2 (sau REQUEST CHANGES `docs/reviews/2026-11-02-feature-aid-01-design-director.md`): `openapi.json` có N47/N48 (P1 #1);
  `APPFRONT_SHA` ghim commit FE đã vào `master` (P1 #2); Vertex `TIMEOUT_S` 60 s, `MAX_ATTEMPTS` 3 → xấu nhất ~12,4 phút
  một lượt, dưới trần quét `running` 15 phút (P2 RES).

## Nợ (P3 lượt 1, chưa làm)

- NO-AID-1 (CON): hạn mức ngày đếm rồi chèn không nguyên tử (`apps/api/design_director/service.py`), hai lượt song song có
  thể vượt 1; dự án nhiều tầng xếp một lượt mỗi tầng xong (`pipeline_quality`), lượt sau dùng lại khoá đầu vào khi tầng
  không đổi nhưng vẫn tốn hạn mức. Hướng: `SELECT … FOR UPDATE` trên dòng dự án khi đếm; gộp kích hoạt theo dự án.
- NO-AID-2 (PERF): worker tải ảnh xem trước của **mọi** mẫu có hồ sơ (`apps/worker/design_director/tasks.py`) dù chỉ
  ứng viên top-N được vẽ lên bảng. Hướng: xếp hạng trước, tải ảnh sau.
- NO-AID-3 (OPS): chưa có `packages/domain/library/profiles.jsonl` trong repo — thiếu thì AI chỉ chọn sơn/sàn và đồ bổ sung
  không có mẫu riêng. Hồ sơ 883 mẫu ở `F:/runs/library-profiles/profiles.jsonl` (phiên thư viện); đưa vào cùng lượt nhập
  thư viện, hoặc đặt `DESIGN_DIRECTOR_PROFILES_PATH`.
- NO-AID-4 (MNT): `_versions` trong `apps/api/design_director/state.py` còn nhánh dự phòng "0" cho hằng vắng — nay
  `PROMPT_VERSION` và `MATERIALS_VERSION` luôn có; bỏ nhánh, nhập thẳng.
- NO-AID-5 (OPS): ảnh worker không có phông DejaVu → sơ đồ R*/E* gửi Gemini dùng phông mặc định nhỏ của Pillow. Hướng:
  thêm `fonts-dejavu-core` khi dựng lại ảnh worker.
- NO-AID-8 (TEST): cổng đầy đủ 8 lượt không lượt nào xanh hết; lỗi luôn ở test ngoài phần sửa, chạy riêng thì qua:
  Redis hết giờ (`admin_ml_datasets` C07, `ml/walls` J01), `pipeline_steps`
  `test_sweep_resends_remaining_families_when_walls_used`, `admin_ml_registry`
  `test_requeue_pending_model_evaluations_smoke`; `pipeline_build` `test_build_layer__perf_under_30_seconds` đỏ cả trên
  `main`. Người dùng cho merge không cần cổng xanh ("Merge luôn", 2026-11-02), dựa trên verdict lượt 2 (không chặn nào
  trong mã nhánh). Hướng: lô DEBT riêng sửa các test chập chờn.
- NO-AID-7 (DOC): BE-00 §13.1 chưa liệt kê `packages/genai` và `google-auth`; R-27: phiên sửa `.importlinter` và
  `apps/worker/pipeline_quality` (ngoài thư mục của mình) — chủ các tệp đó soát lại.
