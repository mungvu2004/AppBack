# Review merge fix/walls-curve-shaft → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (đọc diff bởi agent độc lập, tác giả không tự chấm) · Commit đầu nhánh: e6bd144262c3
- Cổng: phạm vi lượt 1 **đầy đủ** trên 05ba5916 — `bash tools/verify/run.sh verify` mã thoát 1: bước 5 hỏng đúng 1/9277 test
  (`apps/worker/pipeline_steps/tests/test_sweep_rules.py::test_sweep_fails_build_step_without_matching_drawing`,
  `redis.exceptions.TimeoutError` trên Redis dùng chung của f14, không chạm mã tường); chạy lại riêng test đó: đạt.
  Bước 3, 6, 8 chưa chạy trong lượt đó → `verify --fast` (mypy đạt, 1221 tệp) và `verify --steps 6,8` mã thoát 0.
  Lượt 2 (vòng sửa e6bd1442, chỉ `packages/vision/walls`): **đích** — `verify --fast` mã thoát 0, 779 test đạt
  (33 tệp bị ảnh hưởng, gồm `apps/ml/walls`, `apps/worker/pipeline_build/tests/test_e2e_real.py`).
  Log: `F:/App/.scratch-curve/{full,fast9,steps68}.log`.
- Độ phủ: lượt đầy đủ dừng ở bước 5 nên tổng **không đo**; đơn vị bị chạm `packages/vision` đạt ngưỡng 90/90 của cổng nhanh.
- Bench ngoài cổng (14 bản vẽ căn hộ, mặt nạ model thật, `vectorize_with_stats` + `build_layer`): ch-13 tường xiên 2 → 0,
  phòng/cửa/đầu lơ lửng giữ nguyên; 13 ca còn lại y hệt `main`.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất / trạng thái |
|---|---|---|---|---|---|
| 1 | P2 | PERF-05 | `_enclosing_cell` quét mọi tường cho từng đoạn chéo (O(chéo × tường)) | vectorize.py `_enclosing_cell` | **Đã sửa** e6bd1442: chỉ mục tim + `bisect`, dò gần ra xa, cửa sổ `_BOX_MAX_RATIO × bề dày lớn nhất` |
| 2 | P2 | TEST-01 | Ngưỡng cung (bán kính < 4t, quét < 30°, cung ngắn) và chặn ô lớn không có test | test_vectorize.py | **Đã sửa**: `test_arc_chords__thresholds` (4 ca), `test_vectorize__room_wide_diagonal_is_not_a_box_mark` |
| 3 | P3 | MNT-01 | Lồng 4 cấp trong `_enclosing_cell` | vectorize.py | **Đã sửa**: tách `_nearest_across` |
| 4 | P3 | LOG-02 | Mẩu vụn góc hộp bị bỏ dù không dính nét chéo | vectorize.py `_drop_box_marks` | **Đã sửa**: chỉ bỏ khi chung khoá với nét vừa bỏ |
| 5 | P3 | PERF-05 | `_smooth_arcs` khớp lại đường tròn mỗi bước nới chuỗi, O(k²·n) mỗi nhánh | vectorize.py `_smooth_arcs` | Chấp nhận: k là số đoạn DP một nhánh (vài chục), bench 14 ca không chậm hơn đo được |
| 6 | Nit | LOG-02 | `count` tính trước chặn ngưỡng; `ceil(90/10)` ra 10 do sai số | `_arc_chords` | **Đã sửa**: chặn `not (≥)` trước (an toàn với `nan`), trừ 1e-6 trong `ceil` |
| 7 | Nit | R-01/R-05 | `_ARC_TOL_MIN_PX` thiếu docstring; `ponytail:` thiếu đường nâng cấp | vectorize.py | **Đã sửa** |
| 8 | Nit | MNT-04 | `changes/WALLS-CURVE.md` dẫn đường bench ngoài repo | changes | **Đã sửa**: ghi số trực tiếp |

Không có `pragma`, `noqa` trần, `type: ignore` không mã, skip/xfail mới; commit đúng mẫu, có `Prompt: WALLS-CURVE`;
không chạm tệp cấm, API, DB, hợp đồng FE–BE.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 4 | 0,40 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,65 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1; hai P2 của lượt 1 đã sửa trong e6bd1442 và cổng đích của vòng sửa xanh; điểm 4,65 ≥ 4,0.
Còn hở (đã ghi trong `changes/WALLS-CURVE.md`, không chặn merge): tường cong vẫn là chuỗi dây thẳng vì hợp đồng tường
chưa có độ cong (đang làm ở phiên riêng); hộp gen bị mặt nạ tô đặc thành một khối tường đặc chứ chưa ra bốn vách.
