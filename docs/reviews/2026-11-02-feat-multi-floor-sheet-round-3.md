# Review merge feat/multi-floor-sheet → main (lượt 3)

- Ngày: 2026-11-02 · Reviewer: phiên /merge-review (agent độc lập, lượt 3) · Commit đầu nhánh: 8b02d50ea96f (trên `origin/main` 2e999b03)
- Cổng: phạm vi **đích, dùng lại cổng đầy đủ của lượt 1**. `bash tools/verify/run.sh verify` mã thoát **0**, cả 8 bước + 5b đạt (log `F:/App/qa-results/multi-floor/be-verify.log`; log cổng `.cache/src-out/verify/20261101T182057Z-5b4ddccc3022.log`, SHA `5b4ddccc`). Vòng sửa lượt 3 (`git diff 97deeaff HEAD -- . ':!docs/reviews'`) chỉ chạm `changes/MULTI-FLOOR-01.md` (+2 dòng) và `docs/contracts/openapi.json` (1 chuỗi `description`). Cộng với vòng sửa lượt 2, cây cuối khác cây đã qua cổng ở một dòng docstring, câu chữ BE-BIND #5, tệp changes và chuỗi `description` khớp docstring đó. Không có mã chạy hay test nào đổi, nên không cần chạy lại cổng (R-33b: không chạm điều kiện "đầy đủ").
- Độ phủ (lượt đầy đủ trên `5b4ddccc`): tổng dòng 99,41 % · nhánh 97,62 % | `apps/api/drawings` 99,74 / 98,65 · `apps/worker/pipeline_orchestrate` 98,77 / 97,30 · `packages/db` 97,53 / 95,90 · tập file bị chạm 99,48 / 97,96.

## Soát vòng sửa

- Cây sạch. Hai commit mới: `de3ccdf5 docs(changes): …` và `8b02d50e chore(contract): …`. Cả hai có `Prompt: MULTI-FLOOR-01`, dòng đầu đúng mẫu, chỉ chạm tài liệu hoặc tệp sinh ra. Nhánh chưa lên `origin`.
- Lượt 2 C (bản duyệt charter): **đóng**. `changes/MULTI-FLOOR-01.md:13` ghi "Charter: người dùng duyệt 2026-11-02 câu chữ BE-00 W14 và BE-BIND #5: \"Duyệt, merge đi\"". Trailer `Charter-Approved: changes/MULTI-FLOOR-01.md (người dùng duyệt 2026-11-02)` của `1bb6ff96` giờ trỏ tới một bản duyệt có ghi lại, cùng dạng với `changes/LB-01.md:11`. Câu duyệt do điều phối chuyển lại; reviewer không thấy trực tiếp cuộc trò chuyện, chỉ kiểm được bản ghi.
- Lượt 2 finding 4 (`openapi.json` lệch): **đóng**. Diff đúng một dòng: `CropRect.description` đổi sang câu docstring mới, khớp từng chữ với `apps/api/drawings/schemas.py:66` ("Sai luật → 422 `VALIDATION`, `field` là `crop` hoặc `crop.<khoá>`."). Bước 8 so từng byte trên nhánh tích hợp sẽ không còn lệch vì chỗ này.
- Lượt 2 finding 1 (test GD1): giờ là nợ có ghi lại ở `changes/MULTI-FLOOR-01.md:12`.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-01 | Đoạn nối `uploads.crop_corners` → `PageSource.crop` chưa có test GD1; đã ghi nợ | `apps/worker/pipeline_orchestrate/start.py:102`; `changes/MULTI-FLOOR-01.md:12` | Lát sau |
| 2 | P3 | LOG | Không `find_frame` trong vùng cắt; PDF vector đọc tỉ lệ của cả tờ; đã ghi nợ | `apps/worker/pipeline_orchestrate/preprocess.py:150-152`; `changes/MULTI-FLOOR-01.md:11` | Lát sau |
| 3 | Nit | MNT | `crop_corners: Mapped[Any]` | `packages/db/models/drawings.py:64` | `Mapped[list[list[float]] \| None]` khi chạm lại |
| 4 | Nit | OPS | Tên nhánh không theo `<loại>/<mã>-<mô tả>` | tên nhánh | Không cần đổi |

Lưu ý khi merge (không phải finding của nhánh này): `feat/library-file-models` (`f7585326`) có `r20261102_lib_decor_group` với `down_revision = "r20261102_lb_01"`. Nhánh này vào trước, nên phiên merge LIB-FILES phải đổi `down_revision` đó sang `r20261102_mf_01`, chạy lại bước 6, và sinh lại `docs/contracts/openapi.json` sau khi gộp. Việc này đã ghi ở `changes/MULTI-FLOOR-01.md:11`; nên nhắc thêm trong tệp bàn giao của LIB-FILES. Merge bằng squash (BE-00 §13.2) thì commit gộp vẫn chạm `docs/charter/*` cùng mã: theo cách đã làm với LB-01, giữ trailer `Charter-Approved:` trong thông điệp commit gộp.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,72 / 5

## PHÁN QUYẾT: APPROVE

Không còn điều kiện dừng sớm §2: có tệp bàn giao, commit charter chỉ chạm tài liệu và trỏ tới bản duyệt có ghi lại, không chạm tệp cấm ngoài phần của điều phối (`openapi.json` tách thành commit `chore(contract)`). Cổng đầy đủ thoát 0, độ phủ ≥ 90/90 ở mọi gói bị chạm, và cây cuối chỉ khác cây đã qua cổng ở tài liệu và một chuỗi mô tả trong tệp sinh ra. Không có P0/P1/P2; hai P3 đã ghi nợ trong `changes/MULTI-FLOOR-01.md`. Merge thuộc phiên gọi; nhớ lưu ý về `down_revision` của LIB-FILES ở trên.
