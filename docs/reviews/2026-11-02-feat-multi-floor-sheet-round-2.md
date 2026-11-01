# Review merge feat/multi-floor-sheet → main (lượt 2)

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 97deeaff1d79 (trên `origin/main` 2e999b03, sau 4 commit)
- Cổng: phạm vi **đích, dùng lại cổng đầy đủ của lượt 1**. `bash tools/verify/run.sh verify` (phiên chính chạy) mã thoát **0**, cả 8 bước + 5b đạt (log `F:/App/qa-results/multi-floor/be-verify.log`, dòng cuối `exit=0`; log cổng `.cache/src-out/verify/20261101T182057Z-5b4ddccc3022.log`, SHA khớp `5b4ddccc` của lượt 1). pytest 9456 passed trong 14 phút 29 giây; perf 5 test. Cây cuối khác cây đã qua cổng đúng ba chỗ (`git diff 5b4ddccc HEAD -- . ':!docs/reviews'`): một dòng docstring `apps/api/drawings/schemas.py:66`, câu chữ hàng #5 `docs/charter/BE-BIND.md:29`, tệp mới `changes/MULTI-FLOOR-01.md`. Không đổi mã chạy hay test, nên không cần chạy lại bước 1–7; riêng docstring `CropRect` đi vào `openapi.json` (finding 4).
- Độ phủ (từ lượt đầy đủ trên `5b4ddccc`): tổng dòng 99,41 % · nhánh 97,62 % | `apps/api/drawings` 99,74 / 98,65 · `apps/worker/pipeline_orchestrate` 98,77 / 97,30 · `packages/db` 97,53 / 95,90 · tập file bị chạm 99,48 / 97,96. `coverage_gate: đạt`.

## Soát vòng sửa

- Cây sạch. Lịch sử: `1bb6ff96 docs(charter)` (chỉ `BE-00.md`, `BE-BIND.md`, trailer `Charter-Approved: changes/MULTI-FLOOR-01.md (người dùng duyệt 2026-11-02)`) → `5e33857a feat(drawings)` (mã, test, migration, `changes/MULTI-FLOOR-01.md`) → `348c62d9 chore(contract)` (chỉ `docs/contracts/openapi.json`) → `97deeaff docs(reviews)` (phán quyết lượt 1). Cả bốn có `Prompt: MULTI-FLOOR-01`, dòng đầu đúng mẫu. Nhánh chưa lên `origin`.
- Lượt 1 A (thiếu tệp bàn giao): **đóng**, có `changes/MULTI-FLOOR-01.md`; mục Nợ ghi finding 3 lượt 1 (không `find_frame` trong vùng cắt, tỉ lệ đọc cả tờ) và rủi ro hai head.
- Lượt 1 B (charter lẫn trong commit mã): **phần tách commit đóng**. `1bb6ff96` chỉ chạm tài liệu. **Phần bản duyệt chưa đạt**: xem finding C.
- Lượt 1 finding 1 (hai head với `feat/library-file-models`): **đóng cho nhánh này**. Thứ tự đã chốt: nhánh này vào `main` trước, nhánh LIB-FILES nối lại `down_revision` của `r20261102_lib_decor_group` sang `r20261102_mf_01`. Việc đó đã ghi trong `changes/MULTI-FLOOR-01.md:11` của nhánh này. Lưu ý: phiên merge LIB-FILES phải đọc được ghi chú đó; nên ghi thêm vào tệp bàn giao của LIB-FILES khi nhánh đó lên review.
- Lượt 1 Nit 4 (`field`): **đóng**. BE-BIND và docstring giờ ghi `crop` hoặc `crop.<khoá>`, khớp test `startswith("crop")`.
- `docs/contracts/openapi.json` (`348c62d9`) mang `description` của `CropRect` với câu docstring **cũ** (`VALIDATION field=\"crop\"`) vì sinh từ cây trước khi sửa docstring. Bước 8 của cổng đã chạy trên cây cũ nên không bắt được. Xem finding 4 (P2).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| C | **§2 REJECT** | merge-review §2 / BE-00 §2 | Trailer `Charter-Approved:` phải trỏ tới bản duyệt có thật. Tệp được trỏ, `changes/MULTI-FLOOR-01.md`, **không** ghi việc người dùng duyệt (không có dòng "người dùng duyệt …", không có câu duyệt), và tệp đó chưa có ở commit `1bb6ff96` (chỉ sinh ở `5e33857a`). Câu "Duyệt, merge đi" chỉ có trong tin nhắn của điều phối; reviewer không kiểm được. Tiền lệ: `changes/LB-01.md:11` ghi rõ "Charter: người dùng duyệt 2026-11-01 câu chữ …"; `0c4839a9` trích nguyên câu duyệt ngay trong trailer | `1bb6ff96` (trailer); `changes/MULTI-FLOOR-01.md` | Chọn **một**: (a) thêm vào `changes/MULTI-FLOOR-01.md` dòng `- Charter: người dùng duyệt 2026-11-02 câu chữ BE-00 W14 (crop tuỳ chọn ở thân init) và BE-BIND #5 (crop?, field crop hoặc crop.<khoá>): "Duyệt, merge đi".` (commit `docs(changes): …` mới, không cần viết lại lịch sử); hoặc (b) sửa trailer của `1bb6ff96` thành `Charter-Approved: người dùng duyệt 2026-11-02 ("Duyệt, merge đi")` như `0c4839a9`. Chỉ đổi tài liệu: lượt 3 chỉ soát diff đó, dùng lại cổng này |
| 1 | P3 | TEST-01 | Lượt 1 finding 2, **chưa làm** (đã biết, không chặn): `start.py:102` đổi `crop_corners` thành `PageSource.crop` không có test GD1 đi qua. Mục Nợ của `changes/MULTI-FLOOR-01.md` chưa ghi việc này | `apps/worker/pipeline_orchestrate/start.py:102` | Ghi vào mục Nợ cùng lúc với C(a); làm test GD1 ở lát sau |
| 2 | Nit | MNT | Lượt 1 Nit 5, chưa làm: `crop_corners: Mapped[Any]` | `packages/db/models/drawings.py:64` | `Mapped[list[list[float]] \| None]` khi chạm lại |
| 3 | Nit | OPS | Lượt 1 Nit 6, chưa làm: tên nhánh không theo `<loại>/<mã>-<mô tả>` | tên nhánh | Không cần đổi |
| 4 | **P2** | DB/API / BE-00 §12 bước 8 | `openapi.json` (`348c62d9`) còn câu docstring cũ của `CropRect` (`VALIDATION field=\"crop\"`), trong khi mã cuối sinh ra câu mới. Bước 8 trên nhánh tích hợp so **từng byte** (`apps/api/core/openapi.py:205`, `--compare docs/contracts/openapi.json` khi `VERIFY_BRANCH=integration`, `tools/verify/steps.py:439-442`), nên sau khi merge cổng của `main`/CI sẽ đỏ ở bước 8. Cổng lượt 1 chạy trên cây cũ nên không bắt được | `docs/contracts/openapi.json` (`CropRect.description`) | Ngay trong nhánh: điều phối chạy `bash tools/verify/run.sh openapi`, chép bản xuất vào `docs/contracts/openapi.json`; commit `chore(contract): …` mới (hoặc sửa `348c62d9`). Diff phải chỉ là đúng một chuỗi `description` |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4 | 0,40 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,67 / 5

## PHÁN QUYẾT: REJECT

Chỉ còn một điều kiện dừng sớm §2 (C): `Charter-Approved:` trỏ tới `changes/MULTI-FLOOR-01.md`, nhưng tệp đó không ghi việc người dùng duyệt. Mọi thứ khác đã đủ để APPROVE: cổng đầy đủ thoát 0 cho cây chỉ khác về tài liệu, độ phủ ≥ 90/90 ở mọi gói chạm, commit charter đã tách riêng, thứ tự merge với LIB-FILES đã chốt và ghi lại, không có P0/P1. Còn một P2 (finding 4) phải làm trong nhánh vì nếu không `main` sẽ đỏ ở bước 8.

Để được duyệt ở lượt 3:
1. Làm C theo (a) hoặc (b). Với (a), ghi luôn finding 1 vào mục Nợ.
2. Làm finding 4: sinh lại `docs/contracts/openapi.json` từ cây cuối, commit `chore(contract)`.
3. Lượt 3 chỉ soát `git diff 97deeaff <mới> -- . ':!docs/reviews'` (phải chỉ là `changes/MULTI-FLOOR-01.md` và một chuỗi `description` trong `openapi.json`, hoặc trailer) và dùng lại log cổng này; nên chạy `run.sh verify --steps 8` với `VERIFY_BRANCH=integration` nếu tiện, không cần cổng đầy đủ.
4. Sau khi merge: phiên LIB-FILES nối `down_revision` sang `r20261102_mf_01` và sinh lại `openapi.json` sau khi gộp.
