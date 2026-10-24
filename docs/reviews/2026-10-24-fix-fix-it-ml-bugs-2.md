# Review merge fix/fix-it-ml-bugs-2 → main

- Ngày: 2026-10-24 · Reviewer: phiên /merge-review · Commit đầu nhánh: 1e6319e40ceb (base `main` 6fb48ec8)
- Nguồn luật: `RULE.md`, `RULE-CODE.md`, `DEBT.md` **không có** trong repo. Dùng `docs/charter/BE-00.md`, `BE-KFM.md`, `CASE.md`, `FIX.md`; mã `R-xx`/`LOG-xx`… giữ như các phán quyết trước.
- Cổng: phạm vi **đầy đủ**, vì đây là lượt review đầu của nhánh (R-33b (1)). `bash tools/verify/run.sh verify` chạy ba lần:
  - lượt 1 mã thoát 1 (`F:/App/qa-results/it-ml/verify-full-2.log`): 1 failed `packages/messaging/tests/test_redis.py::test_a_dead_redis_costs_exactly_the_configured_number_of_retries` (TimeoutError thay vì ConnectionError, socket 0,5 s);
  - lượt 2 mã thoát 1 (`verify-full-2b.log`): 1 failed `apps/api/spatial_write/tests/test_large.py::test_merge_on_a_large_floor_holds_the_document_lock_briefly` (503);
  - lượt 3 mã thoát **0** (`verify-full-2c.log`): 8674 passed; bước 0–8 đạt, 5b perf (`test_perf.py`, 20k tường) đạt, case_gate đạt, migrate_check đạt, H1 1998 mẫu.
  Hai test hỏng nằm ở gói nhánh không chạm, và mỗi test qua 3/3 lần khi chạy riêng trong `run.sh shell`. Đây là test chập chờn do tải máy, không phải lỗi của diff. Ghi lại để người điều phối biết.
- Độ phủ (in bởi `coverage_gate`, lượt 3): tổng dòng 99,48% · nhánh 98,05% · tập file bị chạm 99,61% / 98,36%. `apps/worker/pipeline_build` 98,85% / 94,74%.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 3 commit: 5ddd12f8 `fix(pipeline): join diagonal door gaps and clamp short-wall openings` (Prompt: FIX-IT-DIAGONAL-OPENINGS), 9f4b79d0 `fix(pipeline): close corner gaps when building rooms` và 1e6319e4 `fix(pipeline): type room gap closers for mypy strict` (cả hai Prompt: FIX-IT-ROOM-GAPS). Dòng đầu ≤ 72 ký tự, trailer `Prompt:` đọc được. Có `changes/FIX-IT-DIAGONAL-OPENINGS.md`, `changes/FIX-IT-ROOM-GAPS.md`.
- 7 file, +312/−23, mã logic ~130 dòng, dưới ngưỡng MNT-05. Không có `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng. Không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`, `openapi.json`, `APPFRONT_SHA`.

## Reviewer tự kiểm

1. **Đỏ trước, xanh sau (FIX luật 1).** Trong `run.sh shell`, thay `geometry.py` và `rooms.py` bằng bản `main` (md5 khớp `git show main:`), giữ `constants.py` của nhánh vì test cần import hằng mới, rồi chạy hai file test của nhánh: **10 failed, 51 passed**. Các test đỏ là ba `degenerate_projection_clamped_to_short_wall[800/500/300]`, `clamped_openings_on_short_wall_overlap`, ba `diagonal_noisy_gap_joined[…]`, `diagonal_endpoint_pulled_to_near_perpendicular`, `corner_gap_400_closes`, `t_junction_gap_closes`. Các test chặn (`orthogonal_three_degrees_not_joined`, `diagonal_side_shifted_gap_not_joined`, `diagonal_touching_walls_no_bridge`, `wall_under_min_width_too_wide`, `corner_gap_over_limit_gives_no_room`, `closer_crossing_other_wall_not_added`, `sideways_stub_does_not_split_room`) xanh trên `main`, đúng vai trò của chúng. Trên nhánh: 61 passed.
2. **Phát lại trên artifact f14 đã lưu (G2..G5)** trong `f14-worker-1`. Mã của container trùng md5 với `main` cho `constants/geometry/rooms/build.py`. Chạy 4 biến thể: `main`, chỉ 007/009, chỉ 008, cả hai. Số của `main` và số từng phần **khớp đúng** số tác giả báo. Script: `<scratchpad>/rv2/combo.py`, `guard.py`, `over.py`, `open_edge.py`, `perf.py`.

| Bản vẽ | Phòng khớp/giả `main` | chỉ 008 | **cả hai** | Cửa đi giữ (khớp GT ≤ 300 mm) `main` → cả hai | Cửa kẹp kín tường (khớp) |
|---|---|---|---|---|---|
| G2 | 4/1 | 5/2 | **5/2** | 5 (4) → 5 (4) | 0 |
| G3 | 8/3 | 12/4 | **12/4** | 12 (10) → 13 (11) | 1 (1) |
| G4 | 12/2 | 17/6 | **17/6** | 20 (19) → 21 (20) | 0 |
| G5 | 4/0 | 13/0 | **13/1** | 15 (12) → 23 (19) | 8 (6) + 1 cửa sổ (1) |
| Σ | 28/6 (GT 100) | 47/12 | **47/13** | 52 (45) → 62 (54) | 9 (7) + 1 (1) |

   Tác động gộp chưa được tác giả đo, nay đã đo: chỉ khác ở G5, thêm **1 phòng giả 28,5 m²**. Phòng này không do closer: nó đã có ở biến thể "chỉ 007", do số `bridges` tăng 13 → 23. Precision phòng 82% → 78%, recall 28% → 47%.
3. **Sự đánh đổi phòng giả.** Đã thử bốn chốt chặn trên bản "cả hai", không chốt nào trội hơn cấu hình đang ship:

| Chốt chặn | khớp | giả |
|---|---|---|
| như ship (1000 mm, cos ≥ 0,5) | 47 | 13 |
| closer ≤ 800 mm | 45 | 11 |
| closer ≤ 600 mm | 39 | 11 |
| bỏ phòng < 3 m² có cạnh là closer | 43 | 10 |
| bỏ phòng < 6 m² có cạnh là closer | 37 | 6 |

   Mỗi phòng giả bỏ được làm mất từ 1 phòng khớp trở lên. GT có 17 không gian < 3 m² ở G4/G5, nên lọc theo diện tích làm hại phòng thật. Lọc mảnh mỏng không có tác dụng: không phòng giả nào có độ đặc 4πA/P² < 0,2. Chốt "không gộp phòng qua cửa" không áp dụng được: closer chỉ **thêm** đường vào `polygonize`, nên chỉ có thể tách hoặc khép mặt, không bao giờ gộp hai mặt. Mặt 85 m² ở G4 là vùng trước đây hở, nay khép lại mà bên trong thiếu tường do mô hình bỏ sót, không phải hai phòng bị gộp. **Kết luận: +19 khớp / +7 giả là chấp nhận được** (F1 0,42 → 0,59), không đòi chốt chặn trước khi gộp.
4. **Bản vẽ thẳng trục không đổi.** `_diagonal` đòi **cả hai** tường lệch trục > 5°, nên cặp thẳng trục vẫn qua nhánh 2° cũ (`geometry.py:280-283`, giống hệt `main`). Phát lại "chỉ 007": G2/G3/G4 giữ nguyên số tường và `bridges` (59/13, 120/22, 80/16). Có test `orthogonal_three_degrees_not_joined`.
5. **Ngữ nghĩa kẹp (009).** Kẹp chỉ xảy ra khi hình chiếu hộp < 300 mm, tức rộng đã về mặc định, và tường ≥ 300 mm. Ô mở khi đó phủ kín cả mẩu tường (`offset 0`, `width ⌊L⌋`). Trên 10 ô mở bị kẹp khi phát lại, 8 nằm ≤ 300 mm cạnh cửa/cửa sổ GT, nên phần lớn là ô mở thật. Cửa 300–599 mm sẽ bị luật `DOOR-WIDTH` (min 600) gắn cờ cho người dùng xem lại. Chấp nhận, trừ lỗi làm tròn ở finding 1.
6. **Hiệu năng ở trần B5-01.** `_gap_closers` trên 20 000 tường ngẫu nhiên: 0,68 s (16 743 closer, đầu tự do thưa) và 0,49 s (dày). Hàm gồm 3 truy vấn `STRtree` theo lô, `shortest_line`/`einsum`/`lexsort` vector hoá, không có vòng Python trên cặp. `test_perf.py` (20k tường/5k hộp/5k chữ, `build_layer` < 30 s) đạt ở bước 5b.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-02 / R-19 | Trần của `offset` là `js_round(length - width)`, có thể làm tròn **lên**, nên `offset + width > L`. Kẹp mới `width = ⌊L⌋` biến trường hợp này từ hiếm thành thường gặp: trên tường chéo (L không nguyên), phần lẻ ≥ 0,5 cho `offset = 1`. Phát lại G4 (cả hai): tường L = 476,93, ô mở `offset 1 + width 476 = 477`. Luật FE `OPENING-IN-WALL` mức **critical** (`AppFront/src/domain/rules/registry.ts:527`, `endMm <= wallLengthMm`, không dung sai) sẽ gắn cờ ô mở AI vừa dựng. Trên `main` phát lại: 0 ca. | `apps/worker/pipeline_build/geometry.py:507` (cùng gốc `:505`) | `offset = min(max(js_round((low + high) / 2 - width / 2), 0), math.floor(length - width))`. `width ≤ ⌊L⌋` nên vế phải ≥ 0. Thêm test: tường chéo (0,0)–(337,337) (L ≈ 476,6), hộp suy biến ở đầu xa, khẳng định `offset_mm + width_mm <= L`. Cách khác: ghi dòng nợ P2 có chủ trước khi gộp. |
| 2 | P3 | OPS / TEST-07 | Phòng khép bằng closer (và bằng `bridges`, đã có từ `main`) có cạnh không có tường. Luật FE `ROOM-NOT-CLOSED` mức critical (`geometry/index.ts:1099-1103`, `MAX_UNCOVERED_EDGE_MM = 50`) sẽ gắn cờ những phòng này. Phát lại "cả hai": 38/60 phòng có cạnh > 100 mm chạy dọc closer. Cờ đó **đúng sự thật** (tường thiếu thật), nhưng phần lớn phòng mới sẽ hiện với lỗi critical. Chưa có xác nhận đầu-cuối nào về điều này. | `apps/worker/pipeline_build/rooms.py:113` | Sau khi gộp, gộp việc này với finding 4 của review trước: dựng lại `worker` trên f14, chạy IT G2..G5, ghi số phòng khớp/giả và số cờ `ROOM-NOT-CLOSED` vào `BUG-LOG-IT.md`. Nếu chủ dự án không muốn cờ này trên phòng AI, mở việc riêng: kéo dài tường thật ở khe góc thay cho closer ảo. |
| 3 | P3 | R-02 / FIX luật 2 | Closer là phần lệch khỏi B5-05 [6] bước 5 (phòng = tường kéo `ROOM_SNAP_MM` + `bridges`), nhưng không chỗ nào ghi là lệch. Docstring `build_rooms` vẫn ghi "tường + `bridges` (B5-05 [6] bước 5)". `changes/FIX-IT-ROOM-GAPS.md` báo số phát lại 008 riêng lẻ, không có số gộp với 007. `changes/` cũng không ghi bằng chứng đỏ-trước (FIX luật 1); reviewer đã tự kiểm, xem mục "tự kiểm" 1. | `apps/worker/pipeline_build/rooms.py:178`; `changes/FIX-IT-ROOM-GAPS.md` | Docstring: "Phòng từ khép kín của tường + `bridges` + `_gap_closers` (lệch B5-05 [6] bước 5, BUG-IT-008)…". `changes/FIX-IT-ROOM-GAPS.md` thêm: "Lệch B5-05 [6] bước 5. Phát lại gộp 007+008: 5/2, 12/4, 17/6, 13/1 (Σ 47/13, `main` 28/6). Đỏ trên `main`: 10 test (danh sách)". Chỉ là tài liệu, không cần chạy lại cổng. |
| 4 | Nit | MNT | 9f4b79d0 không qua `mypy --strict` khi đứng một mình (1e6319e4 vá lại), nên lịch sử không bisect được. 1e6319e4 chỉ sửa kiểu mà mang `fix:`. | lịch sử nhánh | Gộp squash theo prompt (một commit FIX-IT-DIAGONAL-OPENINGS, một commit FIX-IT-ROOM-GAPS), giữ trailer `Prompt:`. |
| 5 | Nit | PERF / R-07 | `_gap_closers` dựng thêm `STRtree(centrelines)` dù `obstacle_tree` đã chứa đúng các tim đó ở chỉ số `< len(walls)`. Dòng cuối bọc lại `LineString(line)` cho từng phần tử của một mảng vốn đã là `LineString`. | `apps/worker/pipeline_build/rooms.py:69`, `:94` | Dùng lại `obstacle_tree`, lọc `target < len(walls)`; trả `closers.tolist()`. Không bắt buộc. |

Đã soát, không có finding: SEC (không có biên vào mới; đầu vào là artifact ML đã qua kiểm hợp đồng B5-01), CON (thuần hàm, không trạng thái chung), RES/DB/API (không đổi dây: `widthMm` vẫn `PositiveMm` ≥ 300, không có migration, không đổi OpenAPI; `Opening` không có ràng buộc độ dài tường ở BE nên finding 1 không làm `rescale_unreviewed` ném), edge case `_gap_closers` (< 2 tường; không đầu tự do; mọi ứng viên bị chặn → mảng rỗng, có test `closer_crossing_other_wall_not_added`; độ dài closer > `ROOM_SNAP_MM` > 0 nên không chia cho 0; cos ≥ 0,5 bảo đảm đoạn đã cắt 1 mm không chạm tường của chính nó), `_aligned` chéo (khe 0 hoặc > 2400 → `False`, giống điều kiện `_near_ends` mà cả `_mergeable` lẫn `_bridge_segments` vốn đã đòi).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,63 / 5** · P0: 0 · P1: 0 · P2: 1 · P3: 2 · Nit: 2

## PHÁN QUYẾT: APPROVE

Không có P0/P1. Cổng đầy đủ thoát 0 ở lượt 3 (8674 passed). Hai lượt đỏ trước đó là test chập chờn ở gói nhánh không chạm, mỗi test qua 3/3 lần khi chạy riêng. Độ phủ ≥ 90/90 (`pipeline_build` 98,85/94,74; tập chạm 99,61/98,36). Test của nhánh thật sự đỏ trên `main` (10 test). Đánh đổi phòng đã được đo cả khi gộp hai sửa: +19 khớp / +7 giả, và không chốt chặn đơn giản nào tốt hơn. Bản vẽ thẳng trục giữ nguyên 2°. `_gap_closers` chạy dưới 1 s ở trần 20k tường. Điểm 4,63 ≥ 4,0 nên theo ma trận là APPROVE. Điều kiện merge:
1. Finding 1: sửa một dòng trên nhánh + thêm test, rồi chạy kiểm **đích** (`verify --steps 1,2,3,4` + pytest/coverage `apps/worker/pipeline_build`). Nếu không sửa thì ghi dòng nợ P2 có chủ trước khi gộp, ở sổ nợ hiện hành hoặc mục "Nợ" của `changes/FIX-IT-DIAGONAL-OPENINGS.md`.
2. Finding 3: thêm docstring và các dòng vào `changes/FIX-IT-ROOM-GAPS.md` (chỉ tài liệu).
3. Gộp squash theo prompt (Nit 4), giữ trailer `Prompt:`. Nếu cây sau gộp khác cây đã kiểm thì chạy verify tích hợp trên `main`. Sau đó làm finding 2 cùng finding 4 của review trước.
