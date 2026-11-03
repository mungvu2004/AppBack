# Review merge fix/bench3d-24-silent-flags → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 300ea03da896 (PR #51; base `main`, `MERGEABLE`/`CLEAN`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41626074894) — người dùng quyết định dùng CI thay `run.sh verify`. Run 41626074894 (workflow CI, `pull_request`, head `300ea03da896a4279a950a536c346a0342f49e45` = đầu nhánh) `success`; `gh pr checks 51`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Reviewer không chạy cổng, docker hay bench tại chỗ.
- Độ phủ (job `coverage` của run 41626074894, `tools.coverage_gate` đạt): tổng dòng 99,32% · nhánh 97,55% — gói bị chạm `apps/worker/pipeline_quality` 99,76% / 98,72%, `apps/worker/pipeline_build` 98,53% / 94,53%, `apps/api/spatial_read` 98,95% / 99,18%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-24-silent-flags` (300ea03d). Nhánh cắt từ `integ/bench3d-r5` (eb510d6a, chứa PR #46–#50 — phán quyết riêng). Review này chỉ chấm `git diff integ/bench3d-r5...HEAD`: 2 commit, 9 tệp, +164/−14 (logic ~90 dòng, dưới 400).
- Commit: `6add5c41 fix(quality): flag mass doorless rooms and room area vs drawing note`, `300ea03d fix(quality): skip room-size area notes, inclusive area bounds` — dòng đầu đúng mẫu, có `Prompt: BENCH3D-24`; job `commits` xanh. Có `changes/BENCH3D-24.md`.
- Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **A — `ROOMS_WITHOUT_DOOR` critical** (`checks.py:208-229`): critical khi ≥ 2 phòng (trừ lô gia/hành lang) **và** ≥ 50 % không tường nào mang cửa đi; nhánh cũ "không ô mở nào → critical" giữ nguyên. Ca 2 phòng 1 thiếu cửa (share 0,5, 1 < 2) vẫn chỉ báo — test `test_room_without_door_on_its_walls__info_only` giữ hành vi cũ; ca dương 2/3 có test. `detail.roomIds` là tuple → `to_wire` qua `json.dumps` thành list; `GeometryCheck.detail` nới kiểu, consumer duy nhất ngoài test là `to_wire` (grep), typecheck CI xanh.
- **B — `AREA_TEXT_MISMATCH`** (`checks.py:232-255`): bỏ số khớp diện tích một phòng (tầng ≥ 2 phòng), so với dải [Σ thông thủy·0,85; Σ tim tường·1,15], biên làm tròn 0,01 m². Tầng không phòng/Σ ≤ 0 → không báo; mọi số bị lọc → không báo (lệch về phía im lặng, không báo nhầm). `math.log(gross / note)` an toàn vì `gross > 0` và `area_notes` dương (đọc `layer.json` từ chối số ≤ 0, NaN, bool). `clear_area_m2(...) or room.area_m2` dùng hàm có sẵn (`packages/domain/spatial/area.py:157`), trả `None` khi không tính được.
- **Đường dữ liệu**: `build.py:931-939 area_notes` (regex ≤ 3 chữ số nguyên, lookbehind chặn đọc đuôi số dài, ≥ 25 m², không lặp) → `BuiltLayer.area_notes` → khoá tuỳ chọn `areaNotes` (chỉ ghi khi có; `layer.json` cũ không có khoá vẫn đọc — giống `labelOrientation` BENCH3D-14) → `service.run_quality` → `build_report` → `geometry_checks`. Test khứ hồi + từ chối giá trị hỏng + test service tới `criticalChecks`.
- **API/FE**: `readiness.GEOMETRY_CHECK_ORDER` thêm mã cuối; `readiness.checks` là chuỗi tự do, job `contract` xanh, không đổi OpenAPI/DB. FE chưa có câu riêng (finding #4).
- **Codex review của làn** (`F:/runs/bench-3d/dot4/flags/codex.md`): 0 P1, 2 P2 (nhãn phòng lớn bị coi là diện tích căn; báo sai đúng biên trên do float) — cả hai đã sửa ở 300ea03d, có test `test_area_text_mismatch__room_label_is_not_a_unit_total_and_bound_is_inclusive`.
- **Replay của làn** (`BAO-CAO.md`, `critical-diff.txt`, mốc r5c chấm lại): F im lặng 8 → 3 (f-07, f-12, f-22 nhờ B; f-16, f-17 nhờ A), bench im lặng 8 → 8, ĐẠT 39/66 và 8/29 không đổi. Reviewer không chạy lại replay (ngoài phạm vi phiên); số trên là của tác giả, khớp `critical-diff.txt`.
- SEC/CON/RES: hàm thuần trên dữ liệu OCR đã có; regex không lồng lượng từ (không ReDoS); không trạng thái dùng chung, không I/O mới. PERF: một lượt regex trên chữ OCR + `clear_area_m2` mỗi phòng chỉ khi có số m²; job `perf` xanh.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | B báo nhầm mới (critical → readiness `needsReview`) trên **6 ca ĐẠT chưa có cờ**: bench cn-12 (ratio 0,851), cn-22 (0,86), e-hin-2 (0,859), nt-01 và nt-05 (0,698 — "161,5 m²" là tổng sàn nhà nhiều tầng, số còn lại 54 m² cũng không khớp), F f-08 (0,795) — 5/39 bench, 1/8 F (`critical-diff.txt`). Dải 0,85–0,87 trộn ca đúng (f-07 0,856, cn-13 0,865) với ca báo nhầm (cn-12, cn-22, e-hin-2), tức ngưỡng 15 % không tách được hai nhóm ở vùng này; nhận định "nhiều khả năng thiếu thật một phần" của báo cáo làn chưa có bằng chứng (các ca này ĐẠT theo đáp án). Lớp nt-01/05 là hệ thống: nhà phố hay ghi tổng sàn nhiều tầng. Không phải lỗi im lặng (vạch cứng của BRIEF-dot4 vẫn giữ), nhưng người dùng bị bắt duyệt lại mô hình đúng ở ~13 % ca ĐẠT bench. | `apps/worker/pipeline_quality/checks.py:75`, `:244-251` | Chủ dự án chọn (ghi vào `changes/BENCH3D-24.md`): (a) giữ như hiện tại, ghi rõ tỉ lệ báo nhầm 5/39 + 1/8 là chấp nhận; hoặc (b) critical chỉ khi lệch xa (ratio < 0,80 hoặc > 1,25) **và** không có ≥ 2 số khác nhau cùng không khớp (trường hợp mơ hồ như nt-01/05 → báo không chặn). Theo ratio trong `critical-diff.txt`, (b) giữ f-04/f-05/f-12/f-14/f-22 (nếu các tờ này không mang ≥ 2 số m² cùng lệch — reviewer chưa kiểm), mất f-07 (F im lặng 3 → 4), bỏ được cn-12/cn-22/e-hin-2/nt-01/nt-05; f-08 (0,795) vẫn báo. Chạy thật cn-12 trên f14 (đã nằm trong danh sách ca của làn) để biết Σ phòng thấp là thiếu thật hay số ghi gồm hộp kỹ thuật/tường ngoài. |
| 2 | P3 | MNT | Docstring `_rooms_without_door` còn ghi hành vi cũ: "Có phòng mà không ô mở nào → chặn; còn lại chỉ báo tỉ lệ…" — nay còn chặn khi ≥ 2 phòng và ≥ 50 % thiếu cửa (R-02). | `apps/worker/pipeline_quality/checks.py:209` | Sửa câu đầu docstring: "… không ô mở nào, hoặc ≥ `DOORLESS_CRITICAL_ROOMS` phòng và ≥ `DOORLESS_CRITICAL_SHARE` phòng thiếu cửa đi → chặn; còn lại chỉ báo". |
| 3 | P3 | OBS | Replay chung `F:/runs/bench-3d/tools/replay/_inner.py` không truyền `area_notes` vào `build_report`, nên mọi replay sau khi merge **không thấy** `AREA_TEXT_MISMATCH` (số im lặng F sẽ đọc là 8 thay vì 3). Báo cáo làn có ghi, `changes/BENCH3D-24.md` thì không. | `changes/BENCH3D-24.md:6`; công cụ ngoài repo | Thêm một dòng vào `changes/BENCH3D-24.md`; người điều phối thêm `area_notes=getattr(built, "area_notes", ())` vào `_inner.py` trước lượt replay kế tiếp. |
| 4 | P3 | DB/API | FE chưa có câu riêng cho `AREA_TEXT_MISMATCH` (mã lạ → câu chung `geometrySuspect`); `ratio` và `roomIds` chỉ ở `quality.json`, không lên dây nên FE không chỉ được phòng thiếu cửa hay "lệch X %". Đã ghi trong `changes/BENCH3D-24.md:6` (câu đề xuất cho AppFront). | `apps/api/spatial_read/readiness.py:42`; AppFront `processingGate.ts` | Việc tiếp của AppFront: thêm câu theo mã; nếu cần "lệch X %"/id phòng thì mở prompt riêng thêm trường dây (đổi schema + OpenAPI). |
| 5 | Nit | MNT | Dòng `Prompt:` tách khỏi `Co-Authored-By:` bằng dòng trống nên `git interpret-trailers` không thấy nó (CI vẫn xanh vì đọc thân). | 2 commit 6add5c41, 300ea03d | Để `Prompt:` và `Co-Authored-By:` cùng khối trailer cuối. |

Không có P0/P1.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 3 | 0,45 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,54 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,54 ≥ 4,0. Hai luật nhỏ, đúng chỗ, tương thích ngược (`layer.json` cũ, hợp đồng FE không đổi), có test dương/âm cho cả hai và cho đường dữ liệu `areaNotes`; hai P2 của Codex đã sửa có test. CI GitHub Actions trên đúng SHA đầu nhánh xanh 24/24, độ phủ gói và tổng ≥ 90/90. Theo replay của làn, F im lặng 8 → 3, không ca ĐẠT nào trượt.

Điều kiện để merge:
1. Merge sau các PR #46–#50 (nhánh này cắt từ `integ/bench3d-r5`); nếu `main` đổi so với tổ hợp đó thì cập nhật nhánh và chờ CI chạy lại xanh.
2. Chủ dự án chọn cách xử lý finding #1 (chấp nhận tỉ lệ báo nhầm 6 ca ĐẠT, hoặc hạ B thành báo-không-chặn ở vùng mơ hồ) và ghi lựa chọn cùng #3 vào `changes/BENCH3D-24.md` hoặc đợt DEBT kế tiếp; #2 sửa một câu, gom cùng đợt.
