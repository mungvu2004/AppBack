# Review merge fix/door-scale → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (tác giả không tự chấm) · Commit đầu nhánh: 90e6fc6e (trên `origin/main` 4198ab06)
- Cổng: phạm vi lượt 1 **đầy đủ** (R-33b điều kiện 1) — `bash tools/verify/run.sh verify` mã thoát **0**, cả 10 bước đạt (pytest 9438 passed trong 10 phút 7 giây, perf 2 test, migrate_check, hợp đồng,
  openapi). Cổng chép nguồn lúc 21:49:01, trước sửa đổi chưa commit của tác giả vào `test_build_scale.py` (21:50:28),
  nên kết quả là của đúng 90e6fc6e
  (log: `F:/runs/merge-review-open-attach/verify-door-scale.log`). f14-ml-1 dừng trong lúc chạy cổng.
- Độ phủ: tổng dòng 99,41% · nhánh 97,62% | `apps/worker/pipeline_build` dòng 98,47% · nhánh 93,63% | tập file bị chạm
  dòng 97,08% · nhánh 90,00% (`coverage_gate` đạt, nhánh của tập file chạm vừa chạm ngưỡng)
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước.
- Bench, reviewer tự chạy lại: mã nhúng trong `F:/runs/bench-can-ho/now/now.py` khớp `main` 4198ab06 ở cả 5 module;
  `now2.py` khớp nhánh (chỉ khác cách xuống dòng một lời gọi `np.array`). Chạy lại cả hai vào thư mục mới
  (`/tmp/rv/a`, `/tmp/rv/b` trong f14-worker-1), chấm bằng `score.py`: ra đúng số của tác giả — ch phòng đúng
  87 → 83, thừa 13 → 16, gộp 13 → 15, sót 9 → 11; cn phòng đúng 121 → 121, thừa 26 → 30, đúng loại 102 → 103;
  cửa không đổi (92 đi, 37 sổ, 13 sai); tỉ lệ ch-01 −4,9 → +8,0 %, ch-04 +28,8 → +0,9 %, ch-09 −41,9 → +9,7 %,
  các bản có tỉ lệ OCR không đổi. Đầu ra và script: `F:/runs/merge-review-open-attach/ds/`.

## Đánh đổi ch-09 / bộ cn — có chấp nhận được không

Chấp nhận được. Lý do:

1. Tỉ lệ sai làm sai **mọi** kích thước của mô hình 3D (ch-09 lệch −42 % dài = diện tích còn ~⅓), còn phòng thì
   người dùng sửa được trong trình sửa; phòng "đúng" cũ của ch-09 là đúng nhờ tỉ lệ sai làm khe 3,2–4,1 m co dưới
   `OPENING_GAP_MAX_MM` (2400). Đo theo diện tích phòng có đáp án của ch-09: lệch dài −39 % → +17 %.
2. Bộ cn không có đáp án tỉ lệ nên tác giả không đo được tỉ lệ ở đó. Reviewer đo thay bằng tổng diện tích phòng dựng
   được so với tổng diện tích ghi trong đáp án (7 bản cn có số; tổng phòng dựng được là xấp xỉ vì có thể thiếu phòng):
   cn-05 85,4 m²: 107 → 74; cn-06 65,1: 38 → 57; cn-15 48: 59 → 45; cn-22 101,9: 71 → 101 (gần đúng hơn ở 4 bản);
   cn-08 112,9: 130 → 152 (kém hơn); cn-14 81: 96 → 69 và cn-21 66: 65 → 63 (ngang); cn-04 theo diện tích từng phòng
   −6 % → +6 % dài (ngang). Tức là trên dữ liệu độc lập, tỉ lệ từ cửa nhìn chung tốt hơn ước lượng bề dày tường.
3. Phòng đúng trên cn giữ nguyên 121; thừa +4 là cái giá có thật và có đường sửa đã đo (nâng `OPENING_GAP_MAX_MM`).

Điều kiện: đánh đổi và việc tiếp theo phải là nợ ghi lại được tìm thấy (finding 1).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-34 | Nợ phát sinh (ch-09 mất phòng ở tỉ lệ đúng, cn thừa 26 → 30, hướng sửa `OPENING_GAP_MAX_MM`) chỉ nằm trong một gạch đầu dòng của `changes/DOOR-SCALE.md`, không có mã nợ/việc tiếp theo; repo không còn `DEBT.md` | `changes/DOOR-SCALE.md:6` | Ghi thành mục nợ có mã (vd. `NO-<nnn>` hoặc backlog đang dùng) kèm số đo hiện tại và tiêu chí đóng (ch-09 khép phòng ở tỉ lệ đúng mà cn thừa không tăng) |
| 2 | P3 | TEST-01 | Test cửa đôi không khoá bộ lọc `_DOUBLE_DOOR_RATIO`: cạnh dài `[50, 50, 50, 50, 120]` cho trung vị 50 cả khi có lẫn không có lọc (745/50 = 14,9 cả hai) → gỡ dòng lọc test vẫn đạt. Thêm nữa, bộ lọc chỉ có tác dụng khi cửa đôi là thiểu số (lúc đó trung vị vốn đã bền): `[50, 50, 120, 120]` → 8,76 cả hai cách; `[50, 52, 54, 120, 130]` → 14,33 so với 13,80 | `build.py:315`, `test_build_scale.py:92-98` | Đổi dữ liệu test sang ca mà lọc đổi kết quả (vd. `[50, 52, 54, 120, 130]` → 745/52 = 14,326923); ghi trong docstring rằng lọc chỉ chống thiểu số cửa đôi, đa số cửa lùa/cửa đôi vẫn kéo tỉ lệ lệch |
| 3 | P3 | LOG-01 | 3/6 bản ch đi nhánh ước lượng không có đáp án tỉ lệ và đổi mạnh: ch-02 19,0 → 13,4 mm/px (tổng phòng 136 → 68 m², hợp lý hơn), ch-08 17,5 → 23,2 (86 → 155 m², nghi lớn quá), ch-05 11,0 → 13,2. ch-08 chưa ai soát | `build.py:641` | Soát ch-08 (đếm hộp `door` và cạnh dài; nhiều cửa lùa/cửa nhỏ?) trước khi coi 745 mm là ổn; ghi kết quả vào `changes/DOOR-SCALE.md` |
| 4 | Nit | R-01 | `_DOOR_MIN_COUNT`, `_DOUBLE_DOOR_RATIO` không có docstring (hằng bên cạnh đều có) | `build.py:83-84` | Thêm một dòng mỗi hằng |
| 5 | Nit | MNT-04 | Chú thích bước 7 vẫn nói "tỉ lệ ước từ tường chỉ đúng tầm ±30 %", nay tỉ lệ ước có thể từ cửa | `build.py:647` | "Tỉ lệ ước (cửa đi hoặc bề dày tường)…" |

Soát thêm, không thành finding: `_door_scale(...) or _build_scale(...)` chỉ rơi về tường khi `None` (tỉ lệ cửa kẹp
≥ 1,0 nên không bao giờ là 0); `BoxPx` buộc `min < max` nên cạnh dài > 0, không chia cho 0; `single` luôn chứa ít nhất
nửa số hộp nên không rỗng; nguồn vẫn `pipeline` + `estimated` nên không dựng `Dimension` từ mẫu khớp, `trusted` vẫn
sai như cũ. Hai ca test thêm cho nhánh cũ (`TL 1/5000` ngoài dải, chữ chuỗi 9000 ngoài dải, ghi chú không tường) đều
khẳng định hành vi, không chỉ để chạy dòng. Không `pragma`, `noqa` trần, `type: ignore` không mã, skip/xfail mới; cây
sạch, một commit đúng mẫu có `Prompt: DOOR-SCALE`, có `changes/DOOR-SCALE.md`; không chạm tệp cấm, API, DB, hợp đồng FE–BE.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,75 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, cổng đầy đủ mã thoát 0, độ phủ đạt, điểm 4,75 ≥ 4,0. Bench chạy lại khớp số của tác giả; đánh đổi phòng
ch-09 / cn thừa +4 chấp nhận được vì tỉ lệ (mọi kích thước 3D) đúng hơn rõ trên bench có đáp án và nhìn chung đúng hơn
trên bộ cn độc lập (đo theo tổng diện tích). Nên làm cùng lượt trước khi merge, đều rẻ: finding 1 (ghi nợ có mã và tiêu
chí đóng), finding 2 (dữ liệu test khiến bộ lọc cửa đôi đổi kết quả). Finding 3 (soát ch-08) và hai Nit không chặn.
Phán quyết này cho 90e6fc6e; commit sửa thêm sau đó cần một lượt đích (`verify --fast`).
