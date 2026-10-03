# Review merge docs/b7-02-security-audit → main (lượt 2)

- Ngày: 2026-10-03 · Reviewer: phiên /merge-review (cùng phiên lượt 1) · Commit đầu nhánh: `b0cf95dcd2ac`
- Lượt 1: `docs/reviews/2026-10-02-docs-b7-02-security-audit.md` — REQUEST CHANGES (4,23/5), 1 P1 · 2 P2 · 2 P3 · Nit.
- Phạm vi lượt 2: `git diff 3e431edada86..b0cf95dcd2ac` — 1 commit `b0cf95d docs(security): address B7-02 review round 1` (trailer `Prompt: B7-02`), 4 tệp (`README.md`, `asvs-checklist.md`, `fixes/SEC-043.md`, `fixes/SEC-061.md`), +14 −9, chỉ trong `docs/security/**`. Cây sạch.
- Cổng: phạm vi **đầy đủ** — cổng 2 trên sha lượt 1 không hoàn tất (hạ tầng), nên cần một cổng đầy đủ trên sha vòng sửa; không chạy lại, đọc log điều phối:
  - cổng 3, sha `b0cf95dcd2ac` (`M/gate.sha`): `M/gate-3.log` — dòng 1 log cổng `…/20261003T063247Z-b0cf95dcd2ac.log` (đúng sha); bảng E.10 (:512-521) bước 0, 1, 2, 3, 4, 5, 5b, 6, 7, 8 đều `đạt`; `7868 passed` (:383); `coverage_gate: đạt` (:390); `case_gate: đạt` (:479); `mã thoát: 0` (:523), `mã thoát (run.sh): 0` (:524).
- Độ phủ (cổng 3): tổng dòng 99,45 % · nhánh 97,87 % (:388); nhánh chỉ đổi tài liệu.

## Trạng thái finding lượt 1

| # | Mức | Finding lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| 1 | P1 | Bảng `chưa kiểm` gộp hai nhóm [6]; dòng đầu README không là `kiểm toán chưa đủ` | **đã sửa** | `README.md:1` = `kiểm toán chưa đủ — nhóm Giấy phép (V14) 100 % chưa kiểm`; bảng `:37-48` đúng 10 nhóm của [6], quy tắc chia dòng V14 ghi ở `:35`. Tự đếm lại từ `asvs-checklist.md` (awk theo `#`/chương): Xác thực 18/0, Quyền 7/0, Đầu vào 19/0, Lỗi-log 11/3, Dữ liệu 12/3, Giao tiếp 11/4, Giới hạn 26/2, Chuỗi cung ứng 11/2, ML 9/2, Giấy phép 2/2 — tổng 126, `chưa kiểm` 18, khớp từng dòng; chỉ Giấy phép > 50 % |
| 2 | P2 | Test của `SEC-061` đặt ở tệp B0-09 | **đã sửa** | `fixes/SEC-061.md:16,22`: [4] = `notify.yml` + `deploy/scripts/tests/test_workflow_notify.py` (cả hai `7f36f79`, `Prompt: B0-10`), cấm `tools/ci/tests/test_workflows.py` (B0-09); [6] trỏ đúng tệp B0-10 |
| 3 | P2 | Mã ASVS `12.1.1` sai nghĩa ở B-27, B-28 | **đã sửa** | `asvs-checklist.md:110-111` cột `mã ASVS` = `—` (luật [2]: không chắc → `—`); kết quả/bằng chứng không đổi |
| 4 | P3 | C-22, D-13 xếp sai nhóm [6] | **đã sửa** | `README.md:35` gán C-22 → Dữ liệu, D-13 → Chuỗi cung ứng; số đếm đã phản ánh (Dữ liệu 12, Giới hạn 26, Chuỗi cung ứng 11). Chương của C-22 vẫn ghi V11 trong checklist — chấp nhận được vì phép đếm theo nhóm đã ghi rõ |
| 5 | P3 | `SEC-043` [5] đề xuất sửa test của prompt khác | **đã sửa** | `fixes/SEC-043.md:24`: chỉ sửa `.gitleaks.toml` (tệp duy nhất của [4]), bỏ phương án `# gitleaks:allow` |

Diff không thêm lỗi mới: bảng tổng đầu README (đạt 100 · lỗ 8 · chưa kiểm 18 · tổng 126) không đổi và vẫn khớp checklist; B-27/B-28 vẫn `đạt`; SEC ↔ `lỗ` vẫn 8 ↔ 8.

## Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | — | Nit lượt 1 chưa sửa: (a) lý do mức `trung bình` của SEC-041; (b) [4] SEC-060 thiếu `deploy/tests/test_nginx.py` (cùng chủ B0-08); (c) B-22 `7.1.1` chỉ phủ một phần câu kiểm; (d) B-08 dẫn test tham số không kèm id | `fixes/SEC-041.md:2`, `fixes/SEC-060.md:16-17`, `asvs-checklist.md:50`, `:104` | **Không chặn**: chỉ tài liệu, không đổi kết luận nào; sửa sẽ đổi cây khỏi cây cổng 3 → thêm một lượt verify tích hợp. Điều phối ghi nợ; người giao FIX cho SEC-041/SEC-060 bổ sung khi điền khối |
| 2 | Nit | — | Tỉ lệ Giới hạn 2/26 = 7,7 % ghi `7 %` (cắt cụt; các dòng khác cắt hay làm tròn đều ra cùng số) | `README.md:45` | Không chặn; ghi `8 %` hoặc nói rõ "cắt cụt" khi có lượt sửa tài liệu sau |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |

Tổng: **4,82 / 5**

## Nợ nên ghi (`DEBT.md`, người điều phối)

- Như lượt 1: tám `SEC-*` theo chủ (B6-03b 020; B0-10 040, 061; B0-02 041, 042; B0-09 043; B0-08 060; B6-04a 062), nợ hiến chương A1/B/C1–C8/D, 18 mục `chưa kiểm — thiếu ảnh` cần kiểm bù qua nginx/`prod.yml`.
- Bốn Nit tài liệu của lượt 1 (finding lượt 2 #1) + tỉ lệ `7 %` (#2).
- Kiểm toán ở trạng thái `kiểm toán chưa đủ` (Giấy phép 100 % `chưa kiểm`) — [11].2 đòi báo người điều phối.

## PHÁN QUYẾT: APPROVE

Cả năm finding lượt 1 (1 P1, 2 P2, 2 P3) đã sửa đúng và tự kiểm lại được; vòng sửa không thêm lỗi mới. Bảng `chưa kiểm` khớp checklist từng nhóm, và dòng đầu README báo đúng `kiểm toán chưa đủ`. Cổng 3 đầy đủ trên `b0cf95dcd2ac` thoát 0. Không còn P0/P1/P2; điểm 4,82 ≥ 4,0. Hai Nit còn lại (bốn Nit tài liệu của lượt 1, tỉ lệ `7 %`) không chặn merge và do điều phối ghi nợ. Merge thuộc phiên điều phối. Khi merge, theo [11].2, phải báo trạng thái `kiểm toán chưa đủ` (nhóm Giấy phép) cho người điều phối/người dùng.
