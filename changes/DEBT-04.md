# DEBT-04 — cụm B: test BE chập chờn dưới tải `pytest -n` (NO-403, NO-404)

- Chỉ đổi test và bản dựng test của hai chủ: `apps/ml/runtime/tests` (B5-01), `apps/worker/pipeline_steps/tests` (B5-06c).
- Không op mới, không seed mới, không revision mới (bước 6 không áp dụng), không đổi `openapi.json` (bước 8 không đổi).
- Mỗi dòng nợ: tái hiện đỏ dưới tải CPU trên base `2ee6e7e`, xanh trên nhánh; bằng chứng ở `backend/dieu-phoi/chay/DEBT-04/B/` (ngoài git).
