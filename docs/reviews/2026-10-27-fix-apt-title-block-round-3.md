# Review merge fix/apt-title-block → main, lượt 3 (+ AppFront fix/error-resource-sharelink)

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review · Commit đầu nhánh: 1d777fdb (base `main` 95d3c78a); AppFront 44db79f3 (trên `origin/master` b41fa8f5)
- Cổng: phạm vi **đích**. Lượt 3 chỉ soát vòng sửa; diff `5be55028..1d777fdb` gồm `sheet.py` (+13 dòng logic), một test, `changes/*.md` và file review, không chạm điều kiện "đầy đủ". `bash tools/verify/run.sh verify --steps 1,2,3,4` tại 1d777fdb mã thoát **0** (log `F:/worktrees/AppBack/apt-sheet-r3-steps.log`). Bước 5–8 dùng lại lượt đầy đủ tại 5be55028, mã thoát 0, cả 10 bước (`F:/worktrees/AppBack/apt-sheet-verify-r2.log`). Reviewer đã tự kiểm `git diff backup/apt-title-block-r2 5a9f2b9b` rỗng: viết lại lịch sử không đổi cây.
- Độ phủ: không đo (phạm vi đích). File đổi: `packages/vision/preprocess/sheet.py` 98% dòng (95 câu, trượt 1; 16 nhánh, trượt 1, dòng chặn dải rỗng đã có ở 5be55028), `geometry.py` 99%, `pipeline_orchestrate/preprocess.py` 100%. `pytest --cov --cov-branch` trên `packages/vision/preprocess` + `apps/worker/pipeline_orchestrate`: 225 passed.
- AppFront: `pnpm exec vitest run src/api/__tests__/contracts/errors.test.ts` 50/50 passed; `eslint --max-warnings 0` trên 2 file đổi: sạch. Bước 7 của lượt đầy đủ đã chạy với AppFront @ d75d1d56, H1 đạt 2134 mẫu. 44db79f3 chỉ thêm test.

## Điều kiện dừng sớm (đã đóng)

- **A đóng.** `f8e73e84` tách thành `ebe87576` `fix(contract): …` (`schema-map.ts` + 3 file test) và `0c4839a9` `docs(charter): BE-BIND #47-49 …`. Commit sau **chỉ** chạm `docs/charter/BE-BIND.md`, trailer `Charter-Approved: người dùng duyệt 2026-10-26 ("tôi đồng ý thêm dòng BE-BIND")`. Lời duyệt tìm thấy trong bản ghi phiên điều phối "Thiết kế một tầng căn hộ" (local_9f86c8d5…): "…merge nhánh tỷ lệ (tôi đồng ý thêm dòng BE-BIND)…". Không còn commit nào khác chạm `docs/charter/*`.
- **B đóng.** Có `changes/FIX-2450.md` (5 route, 3 lỗi C16/C11/C24 đỏ trước xanh sau, hạn mức fail-open) và `changes/FIX-2452.md` (ghim d75d1d56, thứ tự push AppFront trước).
- `APPFRONT_SHA` = d75d1d56, tổ tiên của 44db79f3 trên `fix/error-resource-sharelink`. Gộp AppFront trước thì SHA tới được từ `origin/master`.

## Finding lượt 2

| # | Trạng thái |
|---|---|
| 1 P2 tường dày bị coi là nét khung | **đóng một phần.** `_full_lines` chỉ giữ nhóm cột rộng ≤ max(3 px, 0,4 % cạnh); ca tái hiện thành test `thick_walls_are_never_frame_lines`. Còn sót, xem finding 1 dưới |
| 2 P3 thiếu ca âm | đóng (test trên) |
| 3 P3 `changes/FIX-2451.md` | đóng: có số `run2` → `run5`, ghi `run4` cắt mép 5 ảnh không phải CAD, có việc kế |
| 4 P3 test AppFront | đóng: 44db79f3 thêm test nhận `shareLink`, đổi "mười sáu" |
| 5 P3 thứ tự push | đóng: ghi trong `changes/FIX-2452.md`; reviewer gộp theo thứ tự đó |
| 6 Nit `_longest_runs` cả ảnh | đóng: cắt `ink[:, low:high]` trước |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-01 | Luật "nét mảnh" bắt được tường đặc, nhưng **không** bắt được tường CAD vẽ hai nét mảnh (kiểu vẽ phổ biến khi không tô đặc). Ca thử của reviewer: mặt bằng 1000×800 cắt sát, không khung, không khung tên, tường hai nét 1 px cách 8 px, vách dọc chạy suốt ở x = 760, cột phòng phải có 3 tường ngang. `drawing_box` → `(31, 31, 757, 767)`: vẫn cắt mất cột phòng phải, và bỏ **cả hai** nét tường bao ở mép trái/trên (nét ở 20 và 28, cắt ở 31). Chỉ xảy ra ở đường auto, khi `find_frame` không thấy khung và ảnh cắt sát mặt bằng; 14 ảnh bench không có ca này (`run5` không mất phòng nào do cắt). | `packages/vision/preprocess/sheet.py:61-77` (`_full_lines`), `:90-115` (`_title_divider`, `_border_inset`) | Hai chốt rẻ: (a) nét viền chỉ nhận khi giữa nó và mép trang **không có mực** và phía trong có một dải trắng ≥ vài px (viền giấy luôn có lề trắng bên trong; tường bao thì không); (b) vạch ngăn khung tên chỉ nhận khi ngay bên trái nó, trong khoảng ≤ 12 px, **không** có nét song song chạy suốt (tường hai nét luôn có nét đôi). Thêm test từ ca trên. Theo luật nợ giữa đợt (sổ DEBT kế), việc này vào đợt sửa kế, có chủ là phiên điều phối. |
| 2 | Nit | MNT | `_THIN_PX`, `_THIN_RATIO` dùng chung một docstring cho hai hằng (như các hằng khác trong file; đúng kiểu của file) | `sheet.py:25-27` | Không cần sửa. |

Đã soát, không có finding: viết lại lịch sử (cây không đổi, mọi commit giữ trailer `Prompt:`/`Fix:`), `changes/FIX-2450.md`, `FIX-2452.md` khớp mã, `_full_lines` sau khi cắt `[low, high)` giữ đúng toạ độ (`low + x`), ngưỡng mảnh tính theo `ink.shape[1]` là cạnh đang quét (đúng cả khi gọi với ảnh chuyển vị).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS, OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |

Tổng: **4,65 / 5** · P0: 0 · P1: 0 · P2: 1 · P3: 0 · Nit: 1

## PHÁN QUYẾT: APPROVE

Hai điều kiện dừng sớm của lượt 2 đã đóng: charter nằm trong commit chỉ tài liệu, trailer dẫn lời duyệt có thật; đủ `changes/`. Cổng: lượt đầy đủ tại 5be55028 thoát 0 ở 10/10 bước, cây chỉ khác ở `sheet.py` + test + tài liệu, và lượt đích 1–4 tại 1d777fdb thoát 0; độ phủ file đổi ≥ 98 %. Không P0/P1, điểm 4,65 ≥ 4,0. Còn một P2 (finding 1): ca hẹp hơn lượt 2, không xảy ra trên bench. Nó vào đợt sửa kế, không chặn merge. Thứ tự gộp: AppFront `fix/error-resource-sharelink` → `master`, push; rồi `fix/apt-title-block` → `main`, push.
