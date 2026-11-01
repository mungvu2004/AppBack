# Review merge fix/open-attach → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (tác giả không tự chấm) · Commit đầu nhánh: c2142f27ad4e (trên `origin/main` ccea7c8e)
- Cổng: phạm vi lượt 1 **đầy đủ** (R-33b điều kiện 1) — `bash tools/verify/run.sh verify` mã thoát **0**, cả 10 bước đạt (pytest 9432 passed trong 10 phút 29 giây, perf 2 test, migrate_check, hợp đồng
  AppFront @ 45b6874c, openapi)
  (log: `F:/runs/merge-review-open-attach/verify.log`). f14-ml-1 dừng trong lúc chạy cổng.
- Độ phủ: tổng dòng 99,41% · nhánh 97,59% | `apps/worker/pipeline_build` dòng 98,46% · nhánh 93,20% | tập file bị chạm
  dòng 98,34% · nhánh 92,86% (`coverage_gate` đạt)
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước
  (`2026-11-01-feat-walls-arc.md`).
- Bench ngoài cổng, reviewer tự chạy lại: mã nhúng trong `F:/runs/bench-can-ho/inv-openings/fix/run_new.py` khớp
  `geometry.py`/`build.py` của c2142f27 (chỉ khác một cặp ngoặc thừa và một chữ trong chú thích). Chạy bằng mã nhánh
  trên artifact f14 của 14 bản: tổng tường 508 (khớp báo cáo 475 → 508), 33 tường qua khe, **cả 33 đều mang ô mở**;
  `compare.py` trên đầu ra của tác giả: cửa đi đúng 70 → 82, cửa sổ 29 → 32, sai 7 → 7, `openingTooWide` 9 → 0,
  `openingOverlap` 10 → 4, phòng giống hệt cả 14 bản. Thăm dò thêm tường cong (`_room_with_bay` của `test_arcs.py`,
  4 hộp ở đỉnh và gần hai đầu cung): `main` và nhánh cho cùng kết quả (ô mở trên tường cong, cùng rộng).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-01 | Tường qua khe dựng **trước** khi biết ô mở có sống không; ô mở trên nó rơi về sau thì tường đặc ở lại, bịt khe cửa. Tái hiện (1 mm/px): tường 0–800 ở y=1000, `double_door` hộp x 700–1250, y 950–1050 → nhánh ra 2 tường `(0–800, 0 ô mở)`, `(800–1250, 0 ô mở)`, `openingUnattached` 1; `main` ra 1 tường, cũng `openingUnattached` 1. Nguyên nhân: `_gap_walls` không xét nhãn, khe tự do 450 ≥ 300 nhưng `_candidate` bỏ cửa đôi < 600 mm. Bench 0/33 nên hiếm, nhưng đây là lỗi nhìn thấy trong 3D/trình sửa (vách đặc giữa lối đi) mà trước đây không có | `geometry.py:749-792` (`_gap_walls`), `geometry.py:855-857` (`_candidate`), `geometry.py:1004-1009` (`build_walls`) | Sau `_resolve_overlaps`, bỏ tường không có đầu vào (`inputs == ()`) mà không ô mở nào chọn rồi đánh lại chỉ số trước `_assemble`; hoặc tối thiểu trong `_gap_walls` đòi khe tự do ≥ `_MIN_DOUBLE_DOOR_MM` khi nhãn là `double_door`. Thêm test đúng ca trên |
| 2 | P3 | TEST-01 | Lọc `room_walls` trong `build.py` (bỏ tường qua khe khi dựng phòng) không có test khẳng định: mọi test OPEN-ATTACH gọi `build_walls`, không test nào qua `build_layer` có tường qua khe rồi so phòng. Bỏ lọc đi thì chỉ bench bắt được | `build.py:513-515` | Một test `build_layer`: phòng có cửa trong khe giữa hai má vuông góc → phòng (số, diện tích, `wallIds`) như khi không có hộp cửa |
| 3 | Nit | PERF-05 | `_attach_walls` (STRtree + khoảng cách) chạy hai lần trên gần như cùng đầu vào: bước 3c và bước 4. Chi phí không đáng kể ở cỡ bản vẽ căn hộ | `geometry.py` `_gap_walls`, `_opening_candidates` | Giữ nguyên; chỉ gộp khi bản vẽ lớn làm chậm đo được |

Test đổi có chủ đích (4 hàm, 6 ca chạy): `degenerate_projection_clamped_to_short_wall` (3 ca), `wall_under_min_width_too_wide`,
`clamped_openings_on_short_wall_overlap`, `orthogonal_three_degrees_not_joined`. Đã soát từng ca: hộp chỉ dời về phần lố
đầu tường < 300 mm nên luật gốc (BUG-IT-009 kẹp về L, `openingTooWide`, chồng khoảng trên tường ngắn, 3° không gộp) vẫn
được kiểm với cùng khẳng định, có ca còn thêm khẳng định (`len(result.walls) == 1`, đầu tường giữ 1550). Hình học cũ
(lố ≥ 300 mm, khe giữa hai tường thẳng hàng) chuyển sang test mới khẳng định hành vi mới
(`box_past_wall_end_gets_gap_wall`, `door_between_perpendicular_walls_gets_gap_wall`, `overlapping_gap_boxes_share_one_wall`,
`door_skips_jamb_stub_nearer_centre`, `short_box_off_axis_falls_back_to_nearest`). Không làm yếu test.

Không có `pragma`, `noqa` trần, `type: ignore` không mã, skip/xfail mới, không hạ ngưỡng; cây sạch, một commit đúng mẫu
có `Prompt: OPEN-ATTACH`, có `changes/OPEN-ATTACH.md`; không chạm tệp cấm, API, DB, migration, hợp đồng FE–BE.
Docstring đủ cho `_runs_along`, `_gap_walls`, `_longest_free`, `_placement`; `_placement` gom lại phép chiếu dây/cung
trước đây nằm trong `_opening_candidates` (không trùng lặp).

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

Không P0/P1, cổng đầy đủ mã thoát 0, độ phủ đạt 90/90, điểm 4,75 ≥ 4,0. Bench do reviewer chạy lại bằng mã nhánh xác nhận
số của tác giả (cửa đi đúng +12, cửa sổ +3, ô mở sai không tăng, phòng không đổi) và 33/33 tường qua khe đều mang ô mở.
Finding 1 (P2) và 2 (P3) không chặn merge nhưng nên sửa cùng lượt: phiên tác giả báo đang sửa cả hai trên nhánh này;
vòng sửa đó cần một lượt review 2 (phạm vi đích: `verify --fast` + `pytest apps/worker/pipeline_build`, trừ khi diff chạm
điều kiện đầy đủ của R-33b). Nếu merge c2142f27 trước khi có vòng sửa, ghi finding 1 và 2 vào `changes/OPEN-ATTACH.md`
làm nợ (repo không còn `DEBT.md`).
