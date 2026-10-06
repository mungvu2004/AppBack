PHÁN QUYẾT: APPROVE

# Review merge fix/fix-378-pascal-flag-compose → main — lượt 3 (xác nhận tách hiến chương)

- Ngày: 2026-10-06 · Reviewer: phiên /merge-review (lượt 3) · Commit đầu nhánh: `b1704f7de3cb` (3 commit: `ee08803`, `0e7edc4`, `b1704f7`) · `main` = `bba4b04`
- Lưu ở: `docs/reviews/2026-10-06-fix-fix-378-pascal-flag-compose-round-3.md` (điều phối commit)
- Cổng: phạm vi **dùng lại cổng đầy đủ của `0e7edc4`** — `gate-X1.log` sha `0e7edc4`, **mã thoát 0**, bước 0–8 + 5b đạt (chi tiết ở lượt 2). Lý do dùng lại được: xem §Cổng.
- Độ phủ (từ cổng đó, cùng cây): tổng dòng 99,48 % · nhánh 98,03 %; `apps/api/telemetry` 98,92 % / 96,05 %; `tools` 98,90 % / 96,46 %; tập file bị chạm 100 % / 100 %.
- Ảnh web: `web-build-8c28.log` — `docker build` `web.Dockerfile` mới (không `pnpm draco`) với AppFront `8c28ef961eee…` (dòng 51), **`ma thoat: 0`**; bước `RUN … pnpm build && test -f dist/draco/draco_decoder.wasm && test -f dist/assets/pascal/pascal-mount.js` `DONE 83.4s`; dòng 194 "Đã chép 3 file bộ giải mã Draco vào public/draco/", dòng 645 xuất `public/assets/pascal/pascal-mount.js`.

## Soát vòng sửa (`git diff 0e7edc4..b1704f7`)
- Đúng 1 tệp `docs/charter/HOP-DONG-MOI.md` (+2/−3), đưa về bản merge-base: `git diff main...b1704f7 -- docs/charter` rỗng. Cây sạch; commit `chore(charter): drop charter edit from code branch` đúng mẫu, trailer `Prompt: FIX-378`.
- Hiến chương đã vào `main` riêng: `bba4b04` `docs(charter): list scene.pascal-viewer as sixth feature flag`, chỉ chạm `docs/charter/HOP-DONG-MOI.md`, trailer `Charter-Approved: backend/dieu-phoi/chay/F-14/duyet-nguoi-dung-2026-10-06.md` — tệp duyệt có thật, ghi đúng câu chữ (5→6 khoá, `scene.pascal-viewer`, `:86-92`→`:86-93`). `git diff 0e7edc4 bba4b04 -- docs/charter` rỗng → nội dung hiến chương trên `main` trùng bản đã soát ở lượt 2.
- `b1704f7` chạm `docs/charter/*` không có `Charter-Approved`, nhưng chỉ hoàn nguyên về merge-base (tác động ròng của nhánh lên hiến chương = 0) và biến mất khi squash → không vi phạm §2. Finding A lượt 2 **đóng**.

## Cổng — dùng lại được
- `git merge-tree --write-tree main b1704f7` = `c3a3b7945e95cf4f811e7216cc1a18a244f45095` = `git rev-parse 0e7edc4^{tree}`: cây sau squash **trùng từng byte** với cây cổng `gate-X1.log` đã chạy. Không còn gì để kiểm lại.
- Phụ chứng: không mã/test nào đọc `HOP-DONG-MOI.md` — `git grep HOP-DONG-MOI -- '*.py'` chỉ khớp chú thích/docstring trích dẫn; các tệp hiến chương mà test/công cụ thật sự mở là `BE-BIND.md` (`tools/contract/check.py:42`, `tools/case_gate.py:546`, `apps/api/core/tests/test_routes.py:22`, …) và `CASE.md` (`tools/tests/test_case_gate.py:64`).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| — | — | — | Không còn finding mở. A (lượt 2, §2) đóng như trên; B (P3, chưa dựng ảnh web) đóng bằng `web-build-8c28.log` mã thoát 0. | — | — |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: **5,0 / 5**

## PHÁN QUYẾT: APPROVE
Mọi finding của lượt 1–2 đã đóng: hiến chương tách thành commit tài liệu riêng có `Charter-Approved` và bản duyệt thật; nhánh không còn tác động ròng lên `docs/charter/*`; cây squash trùng tuyệt đối cây đã qua cổng đầy đủ (mã thoát 0, độ phủ ≥ 90/90 mọi gói chạm, hợp đồng FE @ 8c28ef96 xanh); ảnh web dựng được ở sha ghim mới với Dockerfile mới. Được squash vào `main` (việc của điều phối). Sau merge: commit phán quyết này vào `docs/reviews/`; route không đổi nên `docs/contracts/openapi.json` đã nằm trong nhánh.
