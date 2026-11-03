# Review merge fix/bench3d-20-geometry → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 49897fd229dc (PR #47, `MERGEABLE`; merge-base = `origin/main` 3bf5f3ec; HEAD = `origin/fix/bench3d-20-geometry`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41618897942) — người dùng quyết định dùng CI thay `run.sh verify`. Run 41618897942 (workflow CI, `pull_request`, head `49897fd229dc47672bdd39a5c8f20e78a78189dd` = đầu nhánh) `success`; run Commits 41622648942 `success`; `gh pr checks 47`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Reviewer chạy lại riêng job `perf` (lượt 2) để có mẫu đo thứ hai, `success`. Không chạy cổng/docker tại chỗ.
- Độ phủ (job `coverage`, `tools.coverage_gate` đạt): tổng dòng 99,32% · nhánh 97,53% — gói bị chạm `apps/worker/pipeline_build` 98,48% / 94,30%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. `origin/main..HEAD` 4 commit: `e496021d fix(worker): bỏ vùng phụ xiên trục, không nối khe giữa hai vùng`, `f80b4247 fix(worker): không dựng tường vỏ qua khe giữa hai vùng`, `0ebb2d29 perf(worker): region_labels theo chuỗi grow_region, tra bằng STRtree`, `49897fd2 chore(changes): ghi chú BENCH3D-20` — dòng đầu đúng mẫu, đều có `Prompt: BENCH3D-20`. Job `commits` xanh.
- `git diff --stat origin/main...HEAD`: 5 tệp, +220/−3 — `clusters.py` +57, `geometry.py` +67/−3, hai tệp test +93, `changes/BENCH3D-20.md` +6. Logic ~120 dòng, dưới 400.
- Có `changes/BENCH3D-20.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **`region_labels`** (`clusters.py:85-114`): gán vùng theo đúng chuỗi của `_multiple_plans` (`checks.py:168-173`): seed = cụm dài nhất còn lại, hoà lấy chỉ số nhỏ (khớp `max(range, key=...)` ở `_drop_far_clusters` và thứ tự `set` int của `_multiple_plans`). Gộp theo lô (`dwithin` trên `STRtree` các hộp, khoảng cách hình chữ nhật Euclid = `box_gap`) hội tụ về cùng điểm cố định với `grow_region` nuốt từng hộp, vì vùng chỉ lớn lên (đơn điệu). Bộ nhớ O(n) mỗi truy vấn — P1 n² của Codex lượt 2 đã sửa. Test `region_labels__same_chain_as_multiple_plans` khoá đúng ca P2 Codex lượt 2 (vùng sau lớn tới gần vùng trước không bị gộp).
- **`axis_share`** (`clusters.py:123-138`): cửa sổ 2×4° trên vòng góc mod 90 (sắp + nối bản +90°, `searchsorted` + tổng tích luỹ) — đúng cực đại theo vị trí cửa sổ đặt tại từng góc; O(n log n). Test vòng qua 0 (89°/2°), bản xoay 30°, hai họ 0,5, phối cảnh 0,2.
- **B3** (`geometry.py:439-443`): chỉ vùng ≠ vùng chứa cụm dài nhất; tường đã bị luật cũ bỏ không tính vào phép đo (P2 Codex lượt 1 đã sửa). Test: phối cảnh bỏ, căn xoay 30° và căn thứ hai thẳng trục giữ.
- **B4** (`geometry.py:829-852`, `:1482-1534`): `_join_gaps` lọc `near` theo vùng (khe ≤ `FAR_CLUSTER_GAP_MM` 1,5 m luôn cùng vùng, nên chỉ cặp 1,5–2,4 m (`OPENING_GAP_MAX_MM`) lòi khỏi hộp vùng bị chặn); `close_envelope_gaps` bỏ đoạn khép hai đầu khác vùng (`_point_regions`, tường gần nhất). Test khe 2 m không nối / 1,2 m vẫn nối; test tích hợp `build_rooms` có closer qua khe nhưng không thành tường.
- **Hành vi thật**: replay (`dot4/geometry/diff-score.txt`) bench 35→36 (nt-02), F 5→6 (f-26), f-12/f-22/f-23 S4 T→Đ, không ca nào tụt. Chạy thật f14 r5/f3 (`KET-QUA-r5.md`, mã tích hợp gồm `geometry.py`/`clusters.py` của làn này): nt-02, f-26 lên ĐẠT, tụt 0. f-12/f-22 mất `MULTIPLE_PLANS` (vốn báo nhầm) thành im lặng ở r5, hết im lặng nhờ BENCH3D-24 (PR #51, vòng 2).
- **PERF** (`test_build_layer__perf_under_30_seconds`, thời gian testcase trong `junit-perf.xml` của CI): lượt 1 run 41618897942 **30,37 s**, lượt 2 (reviewer chạy lại) **18,12 s**; `main` 3bf5f3ec 18,79 s, e4ac7525 28,24 s; PR anh em #46 18,81 s, #49 17,79 s. Chênh 12 s giữa hai lượt trên cùng SHA → nhiễu runner, không phải hồi quy; khớp số đo cục bộ +~1 s của tác giả. Biên của test này trên CI mỏng sẵn từ `main` (ngoài phạm vi PR).
- SEC/CON/RES: hàm thuần, không đầu vào người dùng mới, không trạng thái dùng chung, không I/O. DB/API: không migration, không đổi `layer.json`/`DROPPED_KEYS`/hợp đồng; job `contract` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | B3 bỏ **cả vùng phụ lớn** chỉ dựa trên `axis_share < 0,6`, không xét bằng chứng mặt bằng (phòng/ô mở/chữ). Biên mỏng hai phía theo chính báo cáo làn: vùng cần bỏ cao nhất f-12 0,57; vùng cần giữ e-sun-2 mẩu 0,60. Một căn thứ hai thật có ~½ chiều dài tường xiên 45° (họ 0/90 + 45/135 → `axis_share` ≈ 0,5, đúng ca test `(0, 90, 30, 120)` = 0,5) bị xoá hết, chỉ cộng vào bộ đếm chung `isolatedBlock` — không cảnh báo nào cho người dùng biết mất một mặt bằng. | `apps/worker/pipeline_build/geometry.py:389`, `:439-443` | Thêm điều kiện vùng phụ không có chữ phòng/hộp cửa trong hộp vùng (hoặc dưới tỉ lệ chiều dài nào đó so với vùng chính) trước khi bỏ; hoặc (làn quality) phát cảnh báo khi bước dựng bỏ vùng phụ xiên (cần khoá `dropped` riêng — đổi hợp đồng, làm sau). Ghi nợ vào `changes/BENCH3D-20.md`. |
| 2 | P2 | MNT | `changes/BENCH3D-20.md` không ghi giới hạn đã biết mà báo cáo làn nêu: biên ngưỡng 0,57↔0,60, f-12/f-22 thành im lặng ở r5 (do mất `MULTIPLE_PLANS` báo nhầm, xử lý ở BENCH3D-24), `_point_regions` chọn tuỳ ý khi đầu đoạn cách đều hai vùng. Nợ chỉ nằm ngoài repo (`F:/runs/bench-3d/dot4/geometry/BAO-CAO.md`). | `changes/BENCH3D-20.md:3-6` | Thêm mục "Giới hạn / nợ" liệt kê ba điểm trên, dẫn BENCH3D-24 cho f-12/f-22. |
| 3 | P3 | LOG | `region_labels` trong `_drop_far_clusters` tính trên **mọi** cụm, kể cả cụm vừa bị đưa vào `drop` (`far_small`/`stray_out`). Một mẩu lạc đã bỏ nằm giữa có thể nối vùng xiên vào vùng chính → B3 bỏ sót (giữ nhầm, an toàn), và lệch với `_multiple_plans` (chạy trên tường còn lại). | `apps/worker/pipeline_build/geometry.py:439` | Tính `region_labels` trên các cụm không thuộc `drop` (lọc `boxes`/`lengths` theo chỉ số), hoặc ghi rõ giới hạn trong docstring. |
| 4 | P3 | PERF | Mỗi bước lớn của một vùng truy vấn lại cả hộp vùng và nhận lại mọi hộp đã gán (`hits` rồi lọc `labels < 0`): vùng dạng chuỗi dài (mỗi bước nuốt một hộp) là O(n²) thời gian (bộ nhớ vẫn O(n)). Cùng lớp với `grow_region` cũ, perf test 5 000 cụm đạt. | `apps/worker/pipeline_build/clusters.py:104-111` | Để nguyên nếu perf ổn; khi cần, chỉ truy vấn phần hộp mới mở rộng (hiệu hộp cũ/mới) hoặc gom theo `neighbours` một lượt rồi duyệt đồ thị. |
| 5 | Nit | MNT | Commit `49897fd2` có dòng trống giữa `Prompt:` và `Co-Authored-By:` nên `git interpret-trailers` không thấy `Prompt:` (CI vẫn xanh vì đọc thân). | commit 49897fd2 | Để hai trailer cùng khối cuối ở các commit sau. |

Không có P0/P1. Hai lượt Codex (P1 ma trận n×n, P1 mảng cặp n², P2 tường đã bỏ kéo `axis_share`, P2 lệch chuỗi vùng) đã sửa, có test.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,61 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,61 ≥ 4,0. Phân vùng mới khớp đúng chuỗi `_multiple_plans` và có test khoá ca lệch; B3/B4 có test âm (căn xoay, căn thứ hai thẳng trục, khe ô cửa 1,2 m vẫn nối). CI trên đúng SHA đầu nhánh xanh 24/24, độ phủ ≥ 90/90; lượt perf chạy lại 18,1 s cho thấy 30,4 s lượt 1 là nhiễu runner. Replay và chạy thật f14 (r5/f3) xác nhận nt-02, f-26 lên ĐẠT, không ca nào tụt. Nên làm trong lượt sau (không chặn merge): ghi nợ #1–#2 vào `changes/BENCH3D-20.md`, và thêm điều kiện bằng chứng mặt bằng cho B3 trước khi gặp ca căn xiên 45° thật.
