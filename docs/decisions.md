# Sổ quyết định (QD-nnn)

Nguồn duy nhất cho quyết định khi spec, app và BE lệch nhau (skill `tl-decision`). ID tăng dần, không dùng lại, không xoá; đổi ý = bản ghi mới, bản cũ ghi "thay bởi". Agent tra sổ (`grep -n -i "<từ khoá>" F:/App/AppBack/docs/decisions.md`) trước khi hỏi lại.

### QD-001 · 2026-10-14 · phase 04 · SCR-18
- Câu hỏi: #35 (PUT lớp tầng) có được ghi `dimensions` không?
- Nguồn lệch: spec `docs/charter/HOP-DONG-MOI.md` §4 N16 "`dimensions` chỉ đọc ở v1", #35 thân strict `{layer?, scaleMillimetresPerPixel?}` | app `AppFront src/lib/autosave/spatialLayerSave.ts` gửi `dimensions` (qa/phase04-run) | BE `apps/api/spatial_write/writer.py` (fix/qa04-dimensions) | BUG-577
- Phương án: A) đổi hợp đồng, #35 nhận `dimensions?`, nhật ký theo id, 409 khi base cũ; B) giữ v1 chỉ đọc, FE thôi gửi và báo thật "chưa lưu lên máy chủ"
- Quyết định: A
- Người quyết: người dùng, 2026-10-14 (phiên qa-phase 04, trả lời câu hỏi Q1 trong `backend/dieu-phoi/chay/QA-04/questions.md`; duyệt câu chữ nguyên văn `backend/dieu-phoi/chay/QA-04/charter-ban-11.md`) · căn cứ: màn Đọc kích thước OCR phải lưu được kết quả duyệt
- Ảnh hưởng mã: app SCR-18 DimensionOcrReview + `spatialLayerSave.ts`; BE `apps/api/spatial_write` (ghi `dimensions`, nhật ký §1.3, trùng id → 422)
- Ảnh hưởng test: BE `apps/api/spatial_write/tests/test_routes_dimensions.py` (ghi/đọc lại, `[]` xoá, vắng giữ nguyên, 409 hai người); FE `src/lib/autosave/__tests__/spatialLayerSave.test.ts`; stack phase 04 dimensions
- Ảnh hưởng tài liệu: HOP-DONG-MOI Bản 11 (§4 N16, #35, §10 L4); `docs/contracts/openapi.json`; BUG-577
- Trạng thái: có hiệu lực
