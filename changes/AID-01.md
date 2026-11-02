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
