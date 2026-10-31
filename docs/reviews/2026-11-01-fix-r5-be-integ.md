# Review merge fix/r5-be-integ → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, tác giả không tự chấm) · Commit đầu nhánh: 27a60f19ac2f
- Cổng: phạm vi lượt 1 **đầy đủ** — `bash tools/verify/run.sh verify` mã thoát 0, 8/8 bước đạt (log
  `F:/runs/r5-integ/be-full4.log`, log cổng `.cache/src-out/verify/20261031T194246Z-27a60f19ac2f.log`: SHA khớp HEAD;
  pytest 9290 đạt; 5b perf 1 test đạt; bước 7 hợp đồng AppFront @ a4bbd512 đạt). Reviewer không chạy lại cổng (một container
  verify của phiên khác đang chạy); `origin/main` 55072c51 là tổ tiên của HEAD, không có gì mới sau lượt cổng.
- Độ phủ: tổng dòng 99,42 % · nhánh 97,60 % | `apps/worker/pipeline_build` 98,36 % / 92,60 % | tập file bị chạm 97,99 % / 91,91 %.
- Phạm vi: 7 commit không merge + 2 merge `origin/main`; 235 dòng thêm trong `apps/` (dưới 400, không cần tách).
  Cây sạch; commit đúng mẫu, đủ `Prompt: UX-R5`; có `changes/UX-R5.md`; không chạm tệp cấm; không `pragma`, `noqa` trần,
  `type: ignore`, skip/xfail mới. Không đổi API, DB, migration; `Dimension.referenceIds` rỗng đã hợp lệ trong mô hình
  (`packages/domain/spatial/model.py` `Dimension`), `variant="rug"` có trong `FurnitureVariant` và FE `src/domain/spatial/types.ts`.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md`; trọng số chấm lấy theo phán quyết trước
  (`2026-11-01-fix-walls-curve-shaft.md`).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | PERF-05 / R-07 | `_drop_hugging_stubs` quét **mọi** `segs` cho mỗi mẩu ≤ 600 mm (`next(... for wall in segs)`), rồi dựng `others` cả mảng và `_dangling` tạo `LineString` cho từng tường: O(mẩu × tường). Ở trần 20 000 tường (K18) với vài nghìn mẩu ngắn là ~10⁸ lần gọi `_hugs`, quá trần 30 s; `test_perf.py` (bản sao `render_plan(100)`) không có mẩu ôm tường nên không bắt. `_reach_dangling` cạnh đó đã dùng `neighbours` (dwithin 2400 mm ≫ 150 mm + ½ bề dày) | `apps/worker/pipeline_build/geometry.py:676`, `:679` | Truyền `neighbours` vào hàm như `_reach_dangling` (`geometry.py:570`): tìm host trong `neighbours[i]`, `others = [segs[k] for k in neighbours[i] if segs[k] is not host]` |
| 2 | P3 | LOG-02 / OBS | Chữ có mẫu ghép tường nhưng không dựng được bị đếm `dimensionUnpaired` (dòng 419, 430) và không vào `done`, nên `_chain_dimensions` vẫn có thể dựng `Dimension` cho chính chữ đó: số liệu bỏ và số dựng chồng nhau | `apps/worker/pipeline_build/build.py:419`, `:430`, `:438` | Chỉ tăng `dimensionUnpaired` khi chữ cũng không ra `Dimension` chuỗi, hoặc dựng chuỗi trước rồi đếm phần còn lại |
| 3 | P3 | LOG-01 | Docstring `_split_by_labels` và `changes/UX-R5.md` nói "cắt dọc **tường cụt**", nhưng `_best_cut` thử mọi tường chạm vùng nới `ROOM_SNAP_MM`, kể cả tường ngoài vùng gặp biên chữ T (phần kéo dài ≤ 2,5 m có thể chia phòng hẹp theo đường không có vách) | `apps/worker/pipeline_build/rooms.py:277`, `:300-302` | Lọc chỉ tường có ≥ 1 đầu nằm trong `polygon` (đầu cụt), hoặc sửa docstring cho đúng hành vi |
| 4 | P3 | TEST-01 | Thiếu ca âm: mẩu ôm tường dày mà **cả hai** đầu chạm tường thứ ba → phải giữ; host mỏng hơn/bằng → giữ. Tách phòng chỉ đo trên 14 ca bench (ngưỡng 2,5 m chọn trên chính tập đó), chưa có tập giữ riêng | `apps/worker/pipeline_build/tests/test_geometry_openings.py:589`; `changes/UX-R5.md` | Thêm 1 test tham số cho hai ca giữ; ghi tập giữ riêng vào kế hoạch đợt sau |
| 5 | P3 | R-34 | Phần chưa làm (UX-38, diện tích thông thuỷ cần quyết định hợp đồng, chữ số ~3 px không đọc được, `span_px=None` ở `vector-apt.pdf`) chỉ nằm trong `changes/UX-R5.md`; repo không có `DEBT.md` | `changes/UX-R5.md` | Ghi các mục này vào sổ nợ/backlog đang dùng của dự án |
| 6 | Nit | R-01 | Docstring bước 2 còn ghi "bước 7 chỉ dựng `Dimension` từ mẫu ghép tường, mẫu chuỗi bị `_SAMPLE_ID` bỏ qua" — sai sau UX-02 | `apps/worker/pipeline_build/build.py:228-229` | Sửa: bước 7 dựng thêm `Dimension` không gắn thực thể từ mẫu chuỗi (`_chain_dimensions`) |
| 7 | Nit | LOG-02 | Chỉ kẹp đầu `start` về 0 (`max(x - half, 0.0)`), đầu kia không kẹp: khi kẹp, `line` ngắn hơn `valueMm` | `apps/worker/pipeline_build/build.py:458`, `:460` | Dịch cả đoạn (`x0 = max(x - half, 0); x1 = x0 + 2·half`) thay vì cắt một đầu |
| 8 | Nit | PERF | `_split_by_labels` dựng `LineString` cho mọi tường trước khi xét `len(labels) < 2`; `line.buffer(ROOM_SNAP_MM)` tính lại cho mỗi mảnh cắt; ngăn xếp `pop()` đảo thứ tự vành không bị cắt (chỉ ảnh hưởng hoà khoá sắp `(min y, min x)`) | `apps/worker/pipeline_build/rooms.py:282-287`, `:298`, `:330` | Trả sớm trước khi dựng `lines`; buffer một lần mỗi `line`; duyệt FIFO (`deque.popleft`) để giữ thứ tự |
| 9 | Nit | MNT-04 | `changes/UX-R5.md` dòng 37 còn "ruff/mypy, cổng đầy đủ: chưa chạy" trong khi cổng đầy đủ đã đạt tại 27a60f19 | `changes/UX-R5.md:37` | Cập nhật dòng trạng thái cổng |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 3 | 0,30 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,50 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1; cổng đầy đủ mã thoát 0 tại đúng HEAD, độ phủ ≥ 90/90 mọi phạm vi; điểm 4,50 ≥ 4,0. Ba thay đổi (Dimension từ
mẫu chuỗi, tách phòng theo ≥ 2 nhãn, bỏ mẩu ôm tường dày) đều có test đường chính và số đo bench 14 ca không ca nào xấu đi.
Khuyến nghị mạnh sửa finding 1 (P2, dùng chỉ mục `neighbours` có sẵn) ở nhánh kế tiếp trước khi có bản vẽ lớn nhiều mẩu ngắn;
các P3/Nit không chặn merge.
