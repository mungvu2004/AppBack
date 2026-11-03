# Review merge fix/bench3d-06-wall-overlaps → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 3381dc63b8dc (PR #36, `MERGEABLE`; merge-base = `origin/main` 08947af4e21d, nhánh không lệch main)
- Cổng: phạm vi đầy đủ (CI GitHub Actions run 41558937398) — người dùng duyệt dùng CI thay `run.sh verify` vì máy đang bận chạy chụp 3D (như các review bench-3d trước). Run 41558937398 (workflow CI, head `3381dc63b8dcc179c407e8e61f2f4756c1296958` = đầu nhánh): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `perf`, `build`, `contract`, `coverage` đều `success`; `gh run watch --exit-status` mã thoát 0. Run 41558937376 (CodeQL) và 41558937462 (Commits) cùng SHA: `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41558937398, `tools.coverage_gate` đạt, `case_gate` đạt): tổng dòng 99,31% · nhánh 97,50% — gói bị chạm: `apps/worker/pipeline_build` 98,25% / 93,30%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch (`.bench3d/` nằm trong `.git/info/exclude`). 2 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-06`:
  `1197ac24 fix(walls): skip envelope-gap bridges that run along existing walls`,
  `3381dc63 fix(walls): drop nibs buried in one wall, read live gap hosts`.
- 4 tệp, +120/−5 (mã logic ~30 dòng ở `geometry.py`, còn lại test và `changes/BENCH3D-06.md`) — dưới 400.
- Có `changes/BENCH3D-06.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.

## Soát nội dung

- **Bỏ đoạn nối chạy dọc tường** (`geometry.py:1222-1226`): đoạn nối dựng thành `_Seg` với bề dày tường chủ rồi thử `_clash` với mọi tường đang có (cả tường qua khe vừa thêm trong vòng). Đã kiểm `_clash` không tự bắt tường chủ: tường chủ thẳng hàng chạm đầu mút cho độ chồng = 0 (song song) hoặc giao tại đầu mút ≤ `_JOINT_MM` (lệch 5–10°); vách vuông góc ở mép khe cũng giao tại đầu mút. Đoạn nối xoè (A→B, A→B' với B' xa hơn) chạy dọc mảnh B–B' nên bị bắt — đúng gốc W4 nêu trong commit. Kiểm đặt trước nhánh khe rộng/hẹp nên áp cho cả hai.
- **Tường chủ đọc từ danh sách đang sửa** (`geometry.py:1217`): mã cũ lấy `hosts` từ `wall_set.walls` gốc, còn `_extend_host` đọc đường tim sống theo `id` → với khe thứ hai chung đầu mút, `tip` là đầu đã kéo nên `target` thành đầu cũ, tường bị kéo lùi và khe đầu mở lại. Đã lần theo mã: lỗi có thật, test `test_close_envelope_gaps__extended_host_not_reread_from_input` khẳng định tường trái giữ đầu (2400, 0).
- **`_buried`** (`geometry.py:692-703`, gọi ở `:716`): chỉ áp cho mẩu < 200 mm không chạm hộp ô mở (lọc có sẵn ở `:713`), đòi **cả hai** đầu trong thân **cùng một** tường sống khác. Mẩu nối hai tường song song (đầu xa nằm ngoài thân tường kia) được giữ — có test `150-connector-kept`. Hai mẩu chồng nhau không cùng bị bỏ vì tường đã bỏ có `alive = False`.
- SEC/CON/RES/DB/API: không đầu vào người dùng mới, không I/O, không trạng thái dùng chung, không đổi API/DB/hợp đồng FE; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | Test khe thứ hai khẳng định kết quả là tường xiên bắt đầu ở (2000, 0) — **giữa** thân tường chủ đã kéo tới (2400, 0) — rồi chạy lệch ~8° dọc nó ~400 mm. `_clash` không bắt vì góc > `_PARALLEL_SIN` (5°) và giao điểm trùng đầu mút (≤ `_JOINT_MM`), nên FE cũng không báo, nhưng hai thân tường chồng nhau đúng kiểu W4 đang sửa. Test chốt luôn hình học này làm hành vi mong đợi. | `apps/worker/pipeline_build/tests/test_geometry_openings.py:1010`; `apps/worker/pipeline_build/geometry.py:1225` | Bỏ assert ở dòng 1010 (giữ assert tường chủ không bị kéo lùi), hoặc ghi rõ trong `changes/BENCH3D-06.md` rằng ca xoè lệch 5–10° chưa được chặn. |
| 2 | P3 | TEST | Commit nói luật bỏ đoạn nối xoè áp cho cả nhánh khe hẹp (`_extend_host`), nhưng test mới chỉ có ca khe rộng (tường mang cửa). Dòng `continue` được phủ, còn hành vi "khe < 600 mm xoè không kéo tường chủ dọc mảnh tường" chưa có test riêng. | `apps/worker/pipeline_build/geometry.py:1225-1226`, `:1242` | Thêm một ca tham số của `test_close_envelope_gaps__fanned_bridge_along_wall_skipped` với khe < `_ENVELOPE_DOOR_MIN_MM`, khẳng định số tường và đường tim tường chủ không đổi. |
| 3 | P3 | TEST | Số bench (r3: W4 nhóm A 6→0; cn-03, cn-08, cn-21, ch-11) chỉ có trong mô tả PR và commit, không tái hiện được từ repo/CI; `changes/BENCH3D-06.md` không ghi kết quả r3 và ca nào còn lỗi. | `changes/BENCH3D-06.md:1-14` | Thêm một dòng kết quả bench r3 (đường `F:/runs/bench-3d/runs/r3`) và ca còn trượt (nếu có) vào `changes/BENCH3D-06.md`. |
| 4 | Nit | PERF | `_wall_seg(other)` dựng lại cho mọi tường ở mỗi đoạn nối, cộng hai `LineString` mỗi lần gọi `_clash` — O(đoạn nối × tường). Số đoạn nối nhỏ nên chi phí không đáng kể. | `apps/worker/pipeline_build/geometry.py:1225` | Không cần đổi. |

Không có P0/P1/P2. Tác giả không nêu nợ mới.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,85 / 5

## PHÁN QUYẾT: APPROVE

Sửa gọn đúng gốc hồi quy W4 của BENCH3D-02: đoạn nối xoè bị chặn bằng chính luật `_clash` (WALL-OVERLAP của FE) thay vì luật mới, tường chủ đọc từ danh sách đang sửa chữa một lỗi kéo lùi có thật, `_buried` chỉ bỏ mẩu < 200 mm có cả hai đầu trong thân cùng một tường và giữ mẩu nối hai tường. Mỗi thay đổi có test. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Ba P3 và một Nit có thể làm ở lượt sau (ưu tiên #1: đừng chốt tường xiên chồng thân tường chủ làm hành vi mong đợi).
