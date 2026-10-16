# Review merge fix/qa09-vectorize-degenerate → main

- Ngày: 2026-10-16 · Reviewer: phiên /merge-review · Commit đầu nhánh: 9f01255c6cfc (merge-base = `origin/main` 58bb5294a09a, nhánh không chậm sau `main`, không cần rebase)
- Cổng: phạm vi đầy đủ — lượt 1 của nhánh (R-33b đk 1). Reviewer tự chạy `bash tools/verify/run.sh verify` dưới stack-lock (f14 dừng),
  **mã thoát 0** (log: `.cache/src-out/verify/20261016T100138Z-9f01255c6cfc.log`; bản ghi ngoài: `F:/worktrees/AppBack/qa09-vectorize-verify.log`).
  Bước 0–8 và 5b đều `đạt`; pytest 8506 passed; perf 3 test; H1/H3/H4/H5 đạt; openapi đạt.
- Độ phủ: tổng dòng 99,47% · nhánh 98,00% — `packages/vision` dòng 99,86% · nhánh 99,37% — tập file bị chạm dòng 99,46% · nhánh 98,15%.

## Phạm vi

1 commit `fix(vision): drop wall segments that collapse after rounding`, 2 file, +18/−6 (logic 5 dòng):
`packages/vision/walls/vectorize.py` (`_finalise`), `packages/vision/walls/tests/test_vectorize.py` (+1 test).

Điều kiện dừng sớm (§2) — **trúng hai**:
- Không có `changes/<mã prompt>.md` (BE-00 §13.2). Nhánh không thêm/sửa file nào trong `changes/`; `main` chưa có `changes/QA-09.md`.
- Thân commit không có trailer `Prompt: <mã>` (chỉ `Bug: BUG-P09-008` + `Co-Authored-By`);
  `git log -1 --format='%(trailers:key=Prompt,valueonly)' 9f01255c` in rỗng. Tiền lệ: mọi nhánh sửa bug QA trước (QA-06b, QA-07, QA-08, PERF-02) đều có cả hai.

Còn lại sạch: cây sạch; dòng đầu đúng Conventional Commits; không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`;
không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới; không hạ ngưỡng cổng.

## Kiểm tính đúng của bản sửa (để lượt 2 chỉ cần soát thủ tục)

- Gốc: `_finalise` so `start == end` trên toạ độ **chưa** làm tròn rồi mới `round(.., 2)`; hai đầu lệch < 0,005 px qua được bộ lọc rồi trùng nhau
  sau làm tròn → `to_wall_px` (`apps/ml/walls/step.py:57`) dựng `WallPx`, validator `packages/ml_contracts/artifacts.py:113-114`
  ném "đầu và cuối tường trùng nhau" → hỏng cả trang. Khớp BUG-LOG-P09 BUG-P09-008.
- Mã mới (`vectorize.py:570-575`): kẹp → làm tròn → so → đếm vào `short`. `_finalise` là nơi duy nhất sinh `WallSegment`
  (gọi từ `vectorize_with_stats:611`, mọi đường `vectorize`/`segment_page` đi qua) → sửa gốc (R-19). Đổi chiều `end < start`
  giờ so trên toạ độ đã làm tròn, nhất quán với giá trị xuất ra; vẫn tất định (J06 không ảnh hưởng).
- Test mới `test_finalise__ends_that_collapse_after_rounding_are_dropped` (`test_vectorize.py:315-322`): trên mã cũ đoạn mẫu được giữ
  (hai đầu chưa làm tròn khác nhau) → `walls == ()` đỏ; xanh ở HEAD (cổng). Đỏ-trước-sửa reviewer **không tự chạy** (máy chủ không có `cv2`);
  bằng chứng là lập luận trên + ghi chú tác giả trong BUG-LOG-P09.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Dừng sớm (§2) | BE-00 §13.2 | Thiếu `changes/<mã prompt>.md` cho bản sửa BUG-P09-008 | nhánh, thư mục `changes/` | Thêm `changes/QA-09.md` (hoặc mã prompt điều phối chọn): bug, gốc, sửa, test đỏ→xanh, hành vi đổi (`dropped.short` có thể tăng 1 trên trang có đoạn suy biến) |
| 2 | Dừng sớm (§2) | R-36b | Thiếu trailer `Prompt: <mã>`; `%(trailers:key=Prompt)` rỗng | thân commit `9f01255c` | Commit `changes/` kèm khối trailer liền `Prompt: QA-09` + `Bug: BUG-P09-008` + `Co-Authored-By`; khi gộp squash, thông điệp squash mang cùng khối trailer, kiểm bằng lệnh trên |
| 3 | Nit | R-01 | Docstring `_finalise` còn ghi thứ tự cũ "Kẹp biên, bỏ đoạn suy biến, làm tròn" — nay làm tròn trước khi bỏ | `packages/vision/walls/vectorize.py:566` | "Kẹp biên, làm tròn, bỏ đoạn suy biến (so sau làm tròn) và sắp …" |
| 4 | Nit | TEST | `assert all(w.start != w.end for w in walls)` thừa khi dòng kế khẳng định `walls == ()` | `packages/vision/walls/tests/test_vectorize.py:320` | Bỏ dòng thừa, hoặc thêm một `_Seg` hợp lệ để assert `all(...)` có nghĩa |

Không có P0/P1/P2/P3 về mã.

## Kiểm sổ nợ

Tác giả không nêu nợ mới; không có dòng `DEBT.md` cần thêm. Không nợ P0/P1 mở gắn với `packages/vision/walls` chặn merge.

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
| MNT | 3% | 4 | 0,12 |

Tổng: 4,97 / 5 (chấm mã; không thay được điều kiện dừng sớm)

## PHÁN QUYẾT: REJECT

Theo §2: thiếu `changes/<mã prompt>.md` và thiếu trailer `Prompt:` là điều kiện dừng sớm, bất kể chất lượng mã. Bản thân bản sửa đúng gốc,
5 dòng logic, có test hồi quy, cổng đầy đủ ở đúng sha `9f01255c` thoát 0 (8506 test, độ phủ 99,47/98,00).
Để được duyệt: (1) thêm `changes/QA-09.md` (finding #1); (2) commit đó mang khối trailer `Prompt: QA-09` đọc được (finding #2);
nên sửa luôn Nit #3, #4. Lượt 2 phạm vi **đích** (diff chỉ tài liệu/docstring/test, không chạm R-33b đk 2–7):
`run.sh verify --steps 1,2,3,4` + pytest `test_vectorize.py`; nếu `main` đổi trước lúc gộp thì chạy lại cổng trên cây tích hợp.
