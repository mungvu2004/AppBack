# DEBT-02 — Trả hết nợ kỹ thuật (mọi dòng mở của DEBT.md), theo đợt

- Không op mới, không seed mới; revision mới chỉ khi một dòng nợ đòi (bước 6 khi đó áp dụng).
- Mỗi đợt một nhánh gộp `fix/debt-02-w<n>`; nhánh cụm `fix/debt-02-w<n>-<cụm>`, mỗi chủ file một commit `fix(<scope>): …` + trailer `Prompt:`/`Fix:` (FIX-117 trở đi, `docs/fixes.md`).
- Mỗi dòng nợ: test chặn tái phát đỏ trên `main`, xanh trên nhánh; bằng chứng ở `backend/dieu-phoi/chay/DEBT-02/` (ngoài git).
- Đợt 1: `tools/verify`, `tools/ci`, `.github`, `tools/case_gate.py`, `deploy/compose/{verify,ci}.yml` — cổng và công cụ; test tĩnh quét YAML/script thay cho chạy workflow thật.
- Hợp đồng FE–BE không đổi (bước 8 chỉ chạy lại); `docs/contracts.toml` chỉ người điều phối sửa (sổ case, NO-309).
