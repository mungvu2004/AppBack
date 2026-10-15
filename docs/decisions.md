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

### QD-002 · 2026-10-15 · phase 04 · SCR-17
- Câu hỏi: lớp AI `table` vào chip 'Bàn ăn' hay 'Nội thất khác'?
- Nguồn lệch: test `qa/tests/phase04_objects_edge.spec.ts` FL-17-06 bước 17-C-022 bấm chip 'Bàn ăn' | app `src/screens/qc/ObjectLayerReview/objectLayerReviewGateway.ts:372-387` ánh xạ `table` → 'Nội thất khác', chip tắt khi không có dữ liệu (`ObjectLayerLeftPanel.tsx:244-259`, BUG-590) | catalog QA-04c `catalog-C2.md:168/297` ⚑
- Phương án: A) đổi ánh xạ sang diningTable; B) giữ ánh xạ, test kiểm bàn trong 'Nội thất khác' và chip 'Bàn ăn' tắt
- Quyết định: B
- Người quyết: người dùng, 2026-10-15 (phiên qa-phase 04, Q2 `backend/dieu-phoi/chay/QA-04/questions.md`) · căn cứ: ánh xạ cố ý, bàn làm việc/bàn trà không phải bàn ăn
- Ảnh hưởng mã: không đổi mã app
- Ảnh hưởng test: `phase04_objects_edge.spec.ts` FL-17-06 bước 17-C-022
- Ảnh hưởng tài liệu: catalog QA-04c 17-C-022 bỏ ⚑
- Trạng thái: có hiệu lực

### QD-003 · 2026-10-15 · phase 04 · SCR-22
- Câu hỏi: tầng đang chọn chưa có bản quét có hiện thông báo 'quét một phần' không?
- Nguồn lệch: test `qa/tests/phase04_journeys_edge.spec.ts` FL-X-04 bước 22-B-011/012 chọn 'Tầng 2' (chưa quét) | app `src/screens/viewer/OverlayComparison/useOverlayComparison.ts:690-696` coi là 'empty', hiện thông báo chưa có bản vẽ
- Phương án: A) giữ app, test kiểm thông báo quét một phần trên 'Tầng 1'; B) app hiện thông báo quét một phần cả khi tầng chưa quét
- Quyết định: A
- Người quyết: người dùng, 2026-10-15 (phiên qa-phase 04, Q3 `backend/dieu-phoi/chay/QA-04/questions.md`) · căn cứ: tầng chưa quét không có gì để báo "một phần"
- Ảnh hưởng mã: không đổi mã app
- Ảnh hưởng test: `phase04_journeys_edge.spec.ts` FL-X-04 bước 22-B-011/012 chuyển sang 'Tầng 1'
- Ảnh hưởng tài liệu: không
- Trạng thái: có hiệu lực

### QD-004 · 2026-10-15 · phase 04 · SCR-14
- Câu hỏi: đang kéo đoạn tham chiếu, tiêu điểm ở ô "Chiều dài thật", Esc có huỷ kéo không?
- Nguồn lệch: catalog QA-04c 14-E-004 + BUG-597 (Esc vẫn tới binding toàn cục từ ô nhập) | luật bộ phím tắt phase 05 "một phím, một hành động" (AppFront 8e4d2db3, 0192e455; QA-05c E1-B12/B13, 23-E-008): phím ô nhập đã xử lý thì không chuyển tiếp
- Phương án: A) giữ luật phase 05, Esc trong ô chỉ hoàn tác ô, đổi 14-E-004; B) đang kéo thì Esc luôn huỷ kéo, SCR-14 tự xử lý, giữ luật bộ phím tắt
- Quyết định: B
- Người quyết: người dùng, 2026-10-15 (phiên qa-phase 04, Q4 `backend/dieu-phoi/chay/QA-04/questions.md`)
- Ảnh hưởng mã: AppFront `useScaleCalibration.ts` nghe Esc ở pha capture chỉ trong lúc kéo (d77e4650); `shortcutRegistry.ts` không đổi
- Ảnh hưởng test: vitest `ScaleCalibration.test.tsx` '… Esc vẫn huỷ đoạn (14-E-004, QD-004)'; stack `phase04_scale_edge.spec.ts` FL-14-04 không đổi kỳ vọng
- Ảnh hưởng tài liệu: catalog QA-04c 14-E-004 nguồn trỏ QD-004
- Trạng thái: có hiệu lực
