# Review merge fix/wall-runs-lcorner → main

- Ngày: 2026-11-04 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 14c00a7d2c02 (PR #52; base `main` d347afb91d1f = merge-base, `MERGEABLE`/`UNSTABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41687780365, attempt 1) — người dùng quyết định dùng CI thay `run.sh verify`; reviewer không chạy cổng, docker hay bench tại chỗ. Run 41687780365 (head `14c00a7d` = đầu nhánh) **`failure`**: job `perf` đỏ — `apps/worker/pipeline_build/tests/test_perf.py:124` `test_build_layer__perf_under_30_seconds`: "build_layer mất 30.24s, trần 30s" (`1 failed, 40 passed`). 22 job còn lại xanh (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, CodeQL). Lúc kết thúc review (`gh pr checks 52`) `perf` vẫn `fail`, chưa có lượt chạy lại.
- Độ phủ: **không đo** — job `coverage` `skipping` vì `perf` đỏ; không có số của CI để kiểm ≥ 90/90 (không chép số lượt trước, K25).
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md`; trọng số chấm theo phán quyết trước (`2026-11-03-fix-bench3d-24-silent-flags.md`), nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/wall-runs-lcorner`. `git diff origin/main...HEAD`: 1 commit, 10 tệp, +548/−38 (logic ~300 dòng: `wall_runs.py` 187, `rooms.py` +80, `checks.py` +27 — dưới 400).
- Commit `14c00a7d fix(pipeline-build): merge touching wall runs, close open L corners`: đúng mẫu, có `Prompt: BENCH3D-25`; job `commits` xanh. Có `changes/BENCH3D-25.md`.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **WALL-RUN** (`wall_runs.py`, gọi ở `build.py:764` sau `apply_post_rules`, trước `settle_reversed`): chỉ tường `source="ai"`, chưa duyệt, thẳng, dài > 0 (`_mergeable`), cùng `kind`, lệch ≤ 2°, hai đầu khúc kia cách tim ≤ ½ bề dày lớn hơn, khe chiếu ≤ 10 mm. Union-find qua `STRtree` đầu mút. Tường gộp giữ id/tim/`kind` của khúc dài nhất, đặt ở vị trí khúc đầu nhóm (tất định, K18).
  - Toán `offsetMm` khúc ngược chiều: ô mở chiếm `[o, o+w]` trên khúc, khúc chạy ngược từ `shift` → trên tim mới chiếm `[shift−o−w, shift−o]`; mã `shift − (o + w)` đúng (tự kiểm lại test `test_reversed_piece_moves_its_opening_and_flips_the_swing`: 10000−500−900 = 8600).
  - Đổi `left`↔`right`: `swing.py:11-12` định nghĩa `left` ⇔ bản lề ở mép phía `centreline.start`; khúc ngược chiều thì mép đó thành phía `end` của tường gộp → đổi là đúng. `double/sliding/fixed` giữ nguyên. `reversed` chỉ do `settle_reversed` đặt (grep: không chỗ nào khác), chạy **sau** gộp, `leaves` khoá theo id ô mở + vector tuyệt đối → tính lại đúng trên tim mới.
  - Tham chiếu id: `opening.wallId`, `wall.openingIds`, `room.wallIds`, `dimension.referenceIds` đổi theo; `input_to_wall`/`leaves` chỉ dùng trước bước gộp (`build.py:611, 717`) hoặc khoá theo id ô mở. `check_integrity` (`integrity.py:38-63`) chỉ soát id trùng/thiếu — không còn tham chiếu treo. FE hàn tường cũng ánh xạ `referenceIds` sang tường gộp (`AppFront wallCommands.ts:1120`) → cùng ngữ nghĩa.
  - Integrity không soát `offset+width ≤ dài` hay ô mở chồng nhau, nên ca biên ở finding #4 không làm build `ValueError`, nhưng cũng không bị chặn.
- **Góc L hở** (`rooms._corner_closers`): chỉ cho đầu tự do chưa được `_gap_closers` khép; vuông góc theo `_T_JUNCTION_COS`; cả hai phía hụt ≤ 1,5 × bề dày lớn hơn; giao điểm giữa thân B (chữ T) bị loại; đoạn cắt tim tường/`bridges` khác bị loại. Khe cửa đi sát góc: hụt tính tới tim nên khe 600 mm giữa mặt tường ứng với hụt ≥ 600 + ½ bề dày > 1,5 × bề dày với tường ≤ 400 → không bịt (test `l_corner_beyond_reach_stays_open`). Đoạn trùng (cả hai đầu cùng tự do sinh cặp đoạn giống nhau) đi vào `closers_out` hai lần, nhưng `close_envelope_gaps` lọc chồng (`_uncovered`, `_clash` gồm cả tường vừa thêm, `geometry.py:1527-1546`) và chỉ dựng khi đúng một bên là phòng → không thấy đường sinh tường vỏ đôi hay phòng giả mới.
- **`ROOMS_WITHOUT_DOOR`** (`checks.py:208-246`): cửa tính cho phòng khi tường trong `wallIds` **và** tâm cửa cách biên phòng ≤ bề dày tường. Luật chặt hơn chỉ làm *tăng* phòng thiếu cửa; ngưỡng critical giữ nguyên (≥ N phòng và ≥ 50 %). Bench: không ca ĐẠT nào đổi kết luận vì cờ (xem dưới). Ca biên tường cong ở finding #5.
- **Tên phòng** `phòng chưa rõ tên`, `_NOT_LABELS` giữ cả tên cũ; AppFront `origin/master` chưa có chuỗi này (tác giả dẫn nhánh `feat/wall-review-ux`) — chuỗi tự do, không đổi hợp đồng.
- **Bench** (tự chạy `diffscore.py` thuần Python trên tệp điểm của tác giả, không replay): bench 66 — ch-10 ĐẠT → TRƯỢT (P5), syn-can-ho-150 TRƯỢT → ĐẠT (W6, bỏ lỗi im lặng), ch-13/cn-08/cn-19 tiêu chí lên → ĐẠT 39 → 39, im lặng 8 → 7. Tập F — f-22 lên 6 tiêu chí, f-02/f-11/f-13 lên, f-06 P6 Đ → C, **f-17 thành lỗi im lặng** (đã ghi trong `changes/BENCH3D-25.md:15-17`). Khớp khẳng định của tác giả.
- **PERF** (bằng chứng từ junit artifact `perf` của các run CI, thời gian gồm lượt khởi động ~0,6 s):

  | Run | Nhánh | `build_layer` perf | Test đối chứng `full_chain_noisier` |
  |---|---|---|---|
  | 41630312495 | main d347afb9 (đầu `main`) | 29,67 s | 13,72 s |
  | 41629267816 | bench3d-24 a6e418ed | 22,23 s | 13,51 s |
  | 41627984926 | main f0521651 | 28,53 s | 13,73 s |
  | 41627477651 / 41627380553 / 41626619158 / 41626550551 | các nhánh BENCH3D | 29,53 / 28,25 / 29,08 / 28,25 s | 13,78 / 14,89 / 13,83 / 13,72 s |
  | 41604532723 / 41629041341 | main | 18,79 / 19,08 s | 12,14 / 12,18 s |
  | **41687780365** | **PR #52** | **30,89 s** | 13,80 s |

  Trên runner cùng tốc độ (đối chứng 13,7-13,8 s), `main` đo 28,3-29,7 s, PR 30,9 s: thêm ~1,2-2,4 s (~4-8 %). Trần đã sát ở `main` (đầu `main` còn ~1 s), nên chạy lại có thể xanh nhờ may mắn nhưng không đủ làm bằng chứng. Đường mới: `merge_wall_runs` một `STRtree` + union-find, O(N + cặp); `_corner_closers` dựng lại `STRtree(centrelines)` (đã có ở `rooms.py:230`) và gọi `obstacle_tree.query` **mỗi cặp ứng viên** trong vòng Python (`rooms.py:294-307`); `_has_door` dựng một `Polygon` mỗi phòng.
- SEC/RES: hàm thuần trên dữ liệu đã có, không I/O, không đầu vào người dùng mới.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | PERF / R-33 (cổng) | CI đầu nhánh đỏ: `test_build_layer__perf_under_30_seconds` 30,24 s > trần 30 s; `coverage` bị bỏ nên không có bằng chứng độ phủ. So junit cùng tốc độ runner: PR thêm ~1,2-2,4 s trên đầu vào 20k tường so với `main` (28,3-29,7 s). | `apps/worker/pipeline_build/build.py:764`; `apps/worker/pipeline_build/rooms.py:294-307` | Cắt chi phí đường mới thay vì nới trần (K24): trong `_corner_closers` dùng lại cây `STRtree(centrelines)` của `_gap_closers` (truyền vào) và gom `trimmed` của mọi cặp thành **một** `obstacle_tree.query(..., "intersects")` rồi lọc theo chỉ số; đo `merge_wall_runs` + `_corner_closers` trên đầu vào perf (log thời gian như `apply_post_rules_total`). Đẩy lại, chờ `perf` xanh **và** `coverage` chạy, ghi số độ phủ gói `pipeline_build`/`pipeline_quality` ≥ 90/90. |
| 2 | P2 | CON / LOG | Chạy lại pipeline trên lớp đã có: `merge_pipeline_result` chỉ khớp tường theo hai đầu mút (`merge.py:131 _same_run`). Tường gộp không khớp khúc người đã duyệt (tạo trước nhánh này) → thêm một tường AI dài chồng lên tường đã duyệt; bia mộ của một khúc đã xoá không chặn tường gộp phủ qua nó → tường xoá "sống lại" trong tường gộp (trái ý H2). Không test, không ghi trong `changes/BENCH3D-25.md`. | `apps/worker/pipeline_build/wall_runs.py:160-187`; `packages/domain/rules_ai/merge.py:131,278-285` | Hoặc trong `_screen` coi tường AI là trùng khi nó thẳng hàng và **phủ** một tường giữ/bia mộ (tách phần phủ, giữ phần dư), có test; hoặc ghi rõ nợ chuyển tiếp vào `changes/BENCH3D-25.md` (lớp tạo trước BENCH3D-25 có khúc đã duyệt/xoá → chạy lại sinh tường chồng) và đưa vào đợt DEBT kế. |
| 3 | P3 | LOG | Nhóm theo union-find bắc cầu: mỗi cặp ≤ 2° và ≤ ½ bề dày, nhưng không soát lại cả nhóm với tim khúc dẫn. Cạnh hơi gãy (0° → 1,9° → 3,8°) gộp thành một đường thẳng, đầu khúc xa lệch quá ½ bề dày khỏi vị trí cũ trong khi `room.outline` vẫn theo khúc cũ. | `apps/worker/pipeline_build/wall_runs.py:96-99, 120-127` | Sau khi nhóm, bỏ khỏi nhóm khúc nào có `_joins(lead, member)` sai (hoặc đầu mút cách tim dẫn > ½ bề dày), thêm một test cạnh gãy. |
| 4 | P3 | LOG | Khúc chồng nhau (`_joins` cho khe âm) mà cả hai mang ô mở ở vùng chồng → hai ô mở chồng trên tường gộp; không chặn trên `offset + width ≤ dài tường` (chỉ `max(0, …)`); `integrity.py` không soát hai điều này nên lớp vẫn qua. | `apps/worker/pipeline_build/wall_runs.py:131-142` | Kẹp `offset ≤ dài − width`; ô mở cùng `kind` chồng > 50 % thì giữ cái tin cao hơn; thêm test khúc chồng có cửa. |
| 5 | P3 | LOG | `_door_centres` lấy tâm cửa bằng `LineString.interpolate` trên dây cung, kể cả tường cong (`curve_offset_mm ≠ 0`): tâm lệch khỏi cung một đoạn cỡ mũi tên cung → phòng có thể bị tính "thiếu cửa", góp vào ngưỡng critical. | `apps/worker/pipeline_quality/checks.py:208-218` | Tường cong: lấy điểm trên cung (đã có toán cung ở `packages/domain/rules_ai/geometry.py:153`) hoặc bỏ phép thử khoảng cách, giữ luật `wallIds` cũ; thêm test cửa trên tường cong. |
| 6 | P3 | DB/API | Sau gộp, nhiều kích thước AI của các khúc cùng trỏ `referenceIds = (tường gộp,)`; `merge_dimensions` coi trùng khi cùng tập `referenceIds` (`dimensions.py:41-43`) → chạy lại mà người đã giữ một kích thước của tường đó thì mọi kích thước AI khác dọc tường (chuỗi kích thước từng đoạn) bị bỏ. | `apps/worker/pipeline_build/wall_runs.py:186`; `packages/domain/rules_ai/dimensions.py:41-43` | Ghi nợ; khi sửa, coi trùng khi cùng `referenceIds` **và** `line` khớp (`_same_line`). |
| 7 | P3 | PERF / TEST | Nợ có sẵn: `test_build_layer__perf_under_30_seconds` dao động 18,8-29,7 s trên `main`, đầu `main` chỉ còn ~1 s dư — cổng chập chờn với mọi nhánh chạm `build_layer`. | `apps/worker/pipeline_build/tests/test_perf.py:124` | Đưa vào đợt DEBT kế (không nới trần trong nhánh này): đo `process_time` thay `perf_counter`, hoặc tối ưu đường nóng của `build_layer` để có dư ≥ 20 %. |

Không P0. Một P1 (cổng đỏ).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4,5 | 0,675 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 2,5 | 0,25 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,27 / 5

## PHÁN QUYẾT: REQUEST CHANGES

Thiết kế đúng chỗ và toán chính đúng: toạ độ ô mở của khúc ngược chiều, đổi `left/right` khớp định nghĩa `swing.py`, `reversed` tính lại sau gộp, mọi tham chiếu id đổi theo và qua `check_integrity`; bench 39 → 39 ĐẠT, f-22 có lại phòng khách, đánh đổi (ch-10, f-17) đã ghi rõ. Nhưng cổng CI trên đúng SHA đầu nhánh đỏ (`perf` 30,24 s > 30 s, ~+4-8 % so với `main` cùng runner) và vì thế không có số độ phủ — theo ma trận, P1 chưa waiver → REQUEST CHANGES.

Để được duyệt:
1. Sửa finding #1: giảm chi phí `_corner_closers` (dùng lại cây, một truy vấn gom) và/hoặc `merge_wall_runs`, không nới trần; đẩy một lần, CI xanh 24/24 **gồm `perf` và `coverage`**, độ phủ gói chạm ≥ 90/90. Nếu chủ dự án chấp nhận perf là nhiễu runner thì phải là waiver ghi tên người duyệt trong `changes/BENCH3D-25.md`, kèm một lượt chạy lại `perf` xanh và `coverage` chạy.
2. Finding #2: sửa ở `_screen` có test, hoặc ghi nợ chuyển tiếp vào `changes/BENCH3D-25.md`.
3. #3-#7 (P3): ghi một dòng mỗi mục vào `changes/BENCH3D-25.md` hoặc đợt DEBT kế; không chặn merge.

---

# Lượt 2 — vòng sửa 142d8234..19e68ffa

- Ngày: 2026-11-04 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 19e68ffa949a (trên phán quyết lượt 1 142d8234)
- Cổng: Phạm vi kiểm: đích — vòng sửa chỉ chạm `apps/worker/pipeline_build/wall_runs.py`, test của nó và `changes/BENCH3D-25.md` (không DB, API, hợp đồng, phụ thuộc, cấu hình cổng). CI vẫn chạy đủ trên đầu nhánh: run 41693040360 (CI), 41693040362 (commits), 41693040356 (CodeQL) **đang chạy** lúc kết thúc review — `perf`, `coverage` chưa có kết quả, chỉ `changes` xanh. Reviewer không chờ, không chạy cổng/docker/bench tại chỗ; `verify --fast` exit 0 là lời tác giả, không tự kiểm.
- Độ phủ: chưa có (job `coverage` của run 41693040360 chưa chạy).

## Soát vòng sửa

- `git diff 142d8234..19e68ffa`: 1 commit `fix(pipeline-build): batch wall-run pair filter, guard bent runs`, đúng mẫu, có `Prompt: BENCH3D-25`; 3 tệp, +72/−16. Không tệp cấm, không pragma/`noqa`/`type: ignore`/skip, không đổi ngưỡng.
- **#1 (P1 perf) — `_groups`** (`wall_runs.py:76-116`): thay `dwithin` quanh đầu mút bằng truy vấn hộp bao cạnh `2·reach` rồi lọc numpy (khác tường, cùng `kind`, `|cross| ≤ sin 2°`) trước vòng Python. Hộp chứa đĩa bán kính `reach` nên tập ứng viên là **tập cha** của tập cũ; bộ lọc chỉ lặp lại đúng hai điều kiện đầu của `_joins`, và `_joins` vẫn soát lại từng cặp → kết quả nhóm như cũ. `parent` chỉ chứa tường đã thành cặp, duyệt `sorted(parent)` nên `members[0]` vẫn là chỉ số nhỏ nhất (tất định). Chia cho độ dài an toàn vì `_mergeable` đã loại tường dài 0. Tác giả đo `merge_wall_runs` 0,26 → 0,10 s CPU trên ca perf; reviewer không đo lại. Khoản tiết kiệm (~0,16 s) nhỏ hơn biên dao động giữa các run `main` cùng tốc độ runner (28,3-29,7 s, lượt 1), nên **chỉ CI `perf` xanh trên 19e68ffa mới đóng được #1**; `_corner_closers` giữ truy vấn từng cặp (ca perf không có góc hở) — chấp nhận được khi CI xanh.
- **#3, #4 (P3) — `_merged`** (`wall_runs.py:130-166`): trả `None` (giữ nguyên các khúc) khi một đầu mút của nhóm cách tim khúc dài nhất > ½ bề dày lớn nhất của nhóm, hoặc ô mở đặt lại chồng nhau hay vượt chiều dài tường gộp. Soát cặp kề sau khi sắp theo `offset` là đủ (ô mở chồng ô không kề thì cũng chồng ô kề giữa chúng; ô vượt cuối mà không phải ô cuối thì đã chồng ô cuối). Hướng an toàn: từ chối cả nhóm, giữ hành vi trước nhánh. Test mới `test_bent_chain_and_clashing_openings_stay_apart` phủ cả hai nhánh `None` (chuỗi lệch 80 mm/khúc, khúc cuối 160 > 100; hai cửa cùng `[1000, 1900]`). Ô mở sát đầu tường có thể bị từ chối vì làm tròn ≤ 1 mm — chỉ làm mất một lần gộp, không sinh dữ liệu hỏng.
- **Bench**: `cmp v2-bench.txt v3-bench.txt` giống hệt; `diffscore.py v2-F.txt v3-F.txt` không in ca nào đổi (cùng 42 dòng) → điểm không đổi so với lượt 1, khớp lời tác giả.
- **Nợ chấp nhận** (`changes/BENCH3D-25.md:24-33`):
  - #2 (P2): lý do đứng được — `merge.py` theo docstring "không sinh id mới" (K18), sửa đúng cần cắt tường AI quanh khúc giữ/bia mộ với id tất định, là prompt riêng; ảnh hưởng chỉ ở tầng dựng **trước** nhánh này có khúc đã duyệt/xoá, tầng dựng sau khớp nguyên khối. Đã ghi rõ hệ quả (tường chồng, khúc xoá hiện lại). Chấp nhận.
  - #5, #6 (P3): đã ghi. Chấp nhận.
  - #7 (P3, test perf chập chờn trên `main`) **chưa có dòng** trong `changes/BENCH3D-25.md` — xem finding R2-1.

## Finding (lượt 2)
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 (lượt 1) | P1 → **chờ CI** | PERF / R-33 | Mã đã giảm chi phí `_groups`; chưa có bằng chứng cổng: `perf` và `coverage` của run 41693040360 đang chạy. | `apps/worker/pipeline_build/wall_runs.py:76-116` | Đóng khi run 41693040360 (hoặc lượt chạy lại trên 19e68ffa) xanh 24/24 gồm `perf` và `coverage`, độ phủ gói `pipeline_build`/`pipeline_quality` và tổng ≥ 90/90. Không nới trần. |
| R2-1 | P3 | OBS | Nợ #7 lượt 1 (test `build_layer` perf dao động 18,8-29,7 s trên `main`, dư ~1 s) không được ghi trong `changes/BENCH3D-25.md`. | `changes/BENCH3D-25.md:28-33` | Thêm một dòng nợ (đợt DEBT kế: đo `process_time` hoặc tối ưu `build_layer` để dư ≥ 20 %), gom vào lần đẩy sau nếu có. |

#2 (P2) và #5, #6 (P3) chuyển thành nợ chấp nhận có lý do; #3, #4 đã sửa có test. Không P0.

## Điểm (lượt 2)
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 4,5 | 0,675 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 3,5 | 0,35 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,48 / 5

## PHÁN QUYẾT (lượt 2): REQUEST CHANGES — chỉ còn chờ bằng chứng cổng

Về mã, vòng sửa đã xử lý đủ: bộ lọc theo lô giữ nguyên ngữ nghĩa nhóm, hai lá chắn mới đi theo hướng an toàn và có test, nợ P2/P3 có lý do đứng được, điểm bench không đổi. Không còn finding mã nào chặn merge (điểm 4,48 ≥ 4,0). Phán quyết chưa thành APPROVE chỉ vì CI trên 19e68ffa chưa xong lúc review: P1 (#1) là cổng, phải có mã thoát thật.

Điều kiện để thành **APPROVE** (không cần review lại mã):
1. Run CI trên 19e68ffa xanh 24/24, **gồm `perf` và `coverage`**, độ phủ gói chạm và tổng ≥ 90/90. Phiên gọi ghi run id + số độ phủ vào một dòng cuối file này.
2. Nếu `perf` lại đỏ: không nới trần; tối ưu tiếp (`_corner_closers`: dùng lại cây `STRtree(centrelines)` và gom truy vấn `intersects`), rồi review lượt 3.
3. R2-1 (P3): thêm dòng nợ perf vào `changes/BENCH3D-25.md` — không chặn merge.
