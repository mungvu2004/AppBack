# Review merge fix/fix-it-ml-bugs → main

- Ngày: 2026-10-24 · Reviewer: phiên /merge-review · Commit đầu nhánh: 5e8d23598890 (base `main` 2925da92)
- Nguồn luật: `RULE.md` và `RULE-CODE.md` **không có** trong repo (CLAUDE.md vẫn trỏ tới). Dùng `docs/charter/BE-00.md`, `BE-KFM.md`, `CASE.md`, `FIX.md`; mã `R-xx`/`LOG-xx`… giữ như các phán quyết trước.
- Cổng: phạm vi **đầy đủ** — lượt review đầu của nhánh (R-33b (1)). `bash tools/verify/run.sh verify` mã thoát **0** (log: `F:/App/qa-results/it-ml/verify-full.log`; 8657 passed; bước 0–8 đạt, 5b perf 3 test, case_gate đạt, migrate_check đạt, bước 7 H1 1998 mẫu @ AppFront f3781ade).
- Độ phủ (in bởi `coverage_gate`): tổng dòng 99,47% · nhánh 98,03% · tập file bị chạm 99,67% / 97,54%. `apps/ml/objects` 100,00% / 98,44%; `apps/worker/pipeline_build` 98,75% / 93,89%.

## Phạm vi và điều kiện dừng sớm

- Cây sạch. 2 commit: b711cfe5 `fix(pipeline): close corner gaps and attach openings by box` (Prompt: FIX-IT-OPENINGS), 5e8d2359 `fix(ml): drop tile-cut slivers inside larger cut boxes` (Prompt: FIX-IT-CUT-FRAGMENTS). Conventional Commits ≤ 72 ký tự; trailer `Prompt:` đọc được bằng `%(trailers:key=Prompt)`. Có `changes/FIX-IT-OPENINGS.md`, `changes/FIX-IT-CUT-FRAGMENTS.md`.
- 7 file, +274/−44, mã logic ~100 dòng → dưới ngưỡng MNT-05. Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng; không chạm `docs/charter/*`, `uv.lock`, `pyproject.toml`, `openapi.json`, `APPFRONT_SHA`.

## Bốn điểm tác giả nêu là chưa chắc

1. **Test chéo khẳng định số thực 1273 / 2545.** Giá trị là `js_round` của hình chiếu GEOS lên tim 45°: rộng 1800/√2 = 1272,79 (lề 0,29), `offset` = 3181,98 − 636,5 = 2545,48 (lề 0,02). Sai số `line_locate_point` trên đoạn (0,0)–(4000,4000) cỡ 1e-9 mm, nhỏ hơn lề hàng triệu lần → không flaky, không phải finding.
2. **Cửa bị vách ngang chia đôi có rộng 450 thay vì 900.** Tái hiện trong container (`run.sh shell`): W1a (0,1000)–(2000,1000), W1b (2000,1000)–(4000,1000), vách W2 tại x=2000, hộp cửa 1550–2450 → branch `(tường 0, offset 1550, rộng 450)`. Trên `main`, công thức cũ cho rộng 900 với `offset` kẹp về 1100, tức cửa dời 450 mm khỏi chỗ thật. Cả hai đều không đúng, nhưng bản mới giữ đúng mép thật và không đè vách ngang; luật `DOOR-WIDTH` (`apps/api/rules/catalog.py:78`, tối thiểu 600) sẽ gắn cờ cửa 450 để người dùng xem lại. Chấp nhận được, không phải finding.
3. **Kéo vách ngang tới tối đa `max(bề dày, 150)` (≤ 400 mm).** Chỉ xảy ra khi khe giữa đầu tường và chân có hộp ô mở phủ ≥ 50% (`_extend_once` gọi `boxes.covers` trước `_stretch_to`), và đầu vách được kéo **đúng tới** chỗ giao, nên không mọc mẩu thừa. Không tạo tường dài 0 (chân nằm ngoài `[0, L]`). Các test e2e của BE (`test_e2e_real`, `test_e2e_fuzz`, `test_build_dimensions`) đều xanh trong lượt đầy đủ. Bộ IT phía AppFront (golden G2–G5) chưa chạy lại: xem finding 4.
4. **Luật mảnh mỏng có xoá nhầm vật riêng lồng nhau cùng nhãn không.** Luật chỉ bỏ ứng viên **chạm mép trong** (`keep[idx] = ~(cut[idx] & cover.any(axis=1))`), không bao giờ bỏ hộp trọn. Vật riêng ≤ độ chồng lát (160 px) luôn có bản trọn ở lát bên, bản đó vẫn sống, và NMS giữ nó cạnh hộp lớn (IoU < 0,5). Rủi ro còn lại chỉ ở vật > 160 px, bị cắt, nằm ≥ 70% trong một hộp cùng nhãn lớn ≥ 2 lần và điểm không thấp hơn. Ca tủ bếp thứ hai ở G5 (IoU 0,47, lớn 2,1 lần) đúng là loại đó và nhiều khả năng là hộp trùng của cùng quầy chữ L, nhưng chưa có số đo trên tập lớn: xem finding 2.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-02 / R-19 | Trên tường chéo, rộng = hình chiếu **hộp thẳng trục** lên tim, nên cộng cả bề dày: span = L + t·\|sin 2θ\|. Tái hiện (`run.sh shell`): tường 45°, cửa thật 900 × 150 → `width_mm` **1049**. Hai cửa sổ thật 900 cách nhau 100 mm trên tường 45° → cái thứ hai bị `openingOverlap`. Không lùi so với `main` (cũ 1200 cũng chồng), nhưng BUG-IT-004 lấy G5 (bản vẽ xoay 45°) làm bằng chứng, và `changes/FIX-IT-OPENINGS.md:7-8` ghi "hết `openingOverlap` giả … cửa sổ kề nhau". Câu đó chỉ đúng với tường thẳng trục. | `apps/worker/pipeline_build/geometry.py:465` | Trừ phần bề dày: `measured = min(js_round(high - low - seg.thickness_mm * abs(2 * ux * uy)), math.floor(length))` với `(ux, uy) = _unit(seg)`. Tường thẳng trục có `ux·uy = 0` nên không đổi. Thêm test: tường 45°, hai cửa sổ 900 cách 100 → hai ô mở, mỗi cái ≈ 900, `openingOverlap == 0`. |
| 2 | P2 | TEST-06 / ML M06 | Luật `CUT_SLIVER_AREA_RATIO` mới chỉ được kiểm bằng unit test và một trang G5. Lần đổi trước của chính hàm này đo trên 400 trang test + 400 trang validation CubiCasa (`detector.py` docstring `merge_candidates`). Ở G5, luật còn xoá thêm một hộp không phải mảnh mỏng (lớn 2,1 lần, IoU 0,47). Thiếu test khẳng định hộp **trọn** nhỏ nằm trong hộp cắt lớn được giữ, tức đúng tính chất làm luật an toàn. | `apps/ml/objects/detector.py:342-343`; `apps/ml/objects/tests/test_detector_postprocess.py` | (a) Chạy cùng bộ đo 400+400 trang trên GPU, so trước/sau: số hộp bị luật mới bỏ theo nhãn, mAP50/recall theo nhãn. Nhận nếu recall không giảm quá 0,5 điểm ở nhãn nào. (b) Thêm test: hộp nhỏ **không chạm mép** nằm trọn trong hộp cùng nhãn chạm mép lớn 3 lần → cả hai còn. Không làm ngay thì ghi dòng nợ có chủ (`apps/ml/objects`) trước khi gộp. |
| 3 | P3 | R-02 / FIX luật 2 | Nhánh đổi hai quy tắc của B5-05 [6] bước 4: gắn theo **tâm** hộp và rộng theo `LABEL_TARGETS`. BUG-IT-003 ghi "cần chủ dự án quyết", nhưng không chỗ nào ghi đây là lệch khỏi prompt: docstring còn gán quy tắc mới cho B5-05. Test cũ `test_build_walls__wall_shorter_than_door_too_wide` bị viết lại thành `…short_wall_keeps_door_clamped_to_length` mà `changes/` không nói (FIX luật 2). Không có bằng chứng đỏ-trước-xanh-sau (FIX luật 1); xét theo mã thì các test mới đều đỏ trên `main`. | `apps/worker/pipeline_build/constants.py:12`; `changes/FIX-IT-OPENINGS.md` | Thêm vào `changes/FIX-IT-OPENINGS.md` mục "Lệch khỏi B5-05 [6] bước 4: tâm → hộp, rộng `LABEL_TARGETS` → hình chiếu (BUG-IT-003/004, quyết <ai/ngày>); test `wall_shorter_than_door_too_wide` thay bằng `short_wall_keeps_door_clamped_to_length` + `degenerate_projection_falls_back_too_wide` vì hợp đồng hành vi đổi". Docstring `constants.py:12`: "(lệch B5-05 [6] bước 4, BUG-IT-003)". |
| 4 | P3 | OPS / TEST-07 | Chưa có xác nhận đầu-cuối rằng lỗi gốc đã hết: G2 kỳ vọng ≥ 6/7 cửa, G3/G4/G5 số cửa, và số phòng/kích thước trong golden IT (điểm 3). | — | Sau khi gộp: dựng lại ảnh `worker` + `ml` trên f14, chạy lại các spec IT-ML-016/062 và số cửa G2–G5, rồi ghi kết quả vào `F:/App/qa-results/it-ml/BUG-LOG-IT.md`. |
| 5 | Nit | R-02 | Docstring module vẫn nhắc `query_nearest`, trong khi lời gọi duy nhất đã bị bỏ. | `apps/worker/pipeline_build/geometry.py:5` | Đổi thành "(`dwithin`, `query`)". |

Đã soát, không có finding: SEC (không có biên vào mới; dữ liệu là đầu ra của mô hình), CON (thuần hàm, `_stretch_to` sửa `_Seg` cục bộ của một lượt dựng), PERF (`_attach_walls` một truy vấn `dwithin` theo lô + `shapely.distance` vector hoá, sắp O(P log P) theo số cặp; ma trận `(m,m)` theo nhãn như cũ), RES/DB/API (không đổi dây: `widthMm` vẫn `PositiveMm`, rộng ≥ 300 hoặc mặc định nhãn; `rescale_unreviewed` co `width_mm` như trước), edge case (`rects` rỗng, `geoms` rỗng, hộp diện tích 0 cho `overlaps` = 0 nên không tự xoá; tỉ lệ > 1 nên không cặp nào xoá lẫn nhau).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3,5 | 0,525 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 3,5 | 0,245 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |

Tổng: **4,59 / 5** · P0: 0 · P1: 0 · P2: 2 · P3: 2 · Nit: 1

## PHÁN QUYẾT: APPROVE

Không có P0/P1; cổng đầy đủ thoát 0 (8657 passed); độ phủ ≥ 90/90 ở mọi gói bị chạm (`pipeline_build` 98,75/93,89; `ml/objects` 100/98,44). Ba lỗi BUG-IT-001/003/004 được sửa ở gốc trong hàm dùng chung (`_foot_on_other`, `_attach_walls`, `_candidate`), BUG-IT-002 sửa trong `_drop_cut_fragments`, đều có test âm. Điểm 4,59 ≥ 4,0 nên theo ma trận là APPROVE. Điều kiện merge:
1. Finding 1 và 2: sửa trên nhánh rồi chạy kiểm **đích** (`verify --steps 1,2,3,4` + pytest/coverage `apps/worker/pipeline_build`, `apps/ml/objects`), **hoặc** ghi dòng nợ P2 có chủ trước khi gộp. `DEBT.md` đã bị gỡ khỏi repo (TIDY-ROOT), nên ghi ở sổ nợ hiện hành hoặc mục "Nợ" của `changes/FIX-IT-*.md`.
2. Finding 3: thêm hai dòng vào `changes/FIX-IT-OPENINGS.md` (chỉ tài liệu, không cần chạy lại cổng).
3. Gộp `--no-ff` hoặc squash theo từng prompt, giữ trailer `Prompt:`. Cây sau gộp khác cây đã kiểm thì chạy verify tích hợp trên `main`. Sau đó làm finding 4.
