# Review merge fix/bench3d-19-quality → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 95b93ae8719d (PR #46; merge-base 3bf5f3ecfdf5 = `origin/main` hiện tại; PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41618884972) — người dùng quyết định dùng CI thay `run.sh verify`. Run 41618884972 (head `95b93ae8719d57233fb60e4256eab0190225664f` = đầu nhánh) `success`; `gh pr checks 46`: 24/24 pass (changes, commits, lint, typecheck, unit/integration/ml shards, build, contract, coverage, perf, CodeQL). Job `perf`: 41 passed trong 117 s. Reviewer không chạy cổng hay probe tại chỗ.
- Độ phủ (job `coverage` của run 41618884972): tổng dòng 99,32% · nhánh 97,55% — gói bị chạm `apps/worker/pipeline_build` 98,52% / 94,40%, `apps/worker/pipeline_quality` 99,75% / 98,61%. ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước, nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch, HEAD = `origin/fix/bench3d-19-quality`. 2 commit: `34767caa fix(pipeline-build): chặn ảnh phối cảnh 3D theo hướng nét tường`, `95b93ae8 chore(changes): ghi chú BENCH3D-19` — dòng đầu đúng mẫu, có `Prompt: BENCH3D-19`; job `commits` xanh.
- 6 file, +130/−2; logic ~60 dòng. Có `changes/BENCH3D-19.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail, không hạ ngưỡng.

## Soát nội dung

- **`axis_share`** (`checks.py:238-268`): hướng tường gom ô 0,1° mod 90°, `hist` theo chiều dài, tổng tiền tố trên `hist` nhân đôi để lấy cung vòng. Cửa sổ ±4° = 81 ô. Cặp (i, i+gap) với gap 0…819: phần chồng `[i+gap−40, i+40]` dài 81−gap đúng khi gap ≤ 80; gap ≤ 819 thì cửa sổ thứ hai không vòng chạm cửa sổ thứ nhất (cần gap ≥ 820), và gap ≥ 820 đối xứng với 900−gap đã xét. `% _AXIS_BINS` sau `floor` chặn trường hợp float làm tròn lên 90,0°. Chỉ số lớn nhất 899+81 < 1801 = độ dài `prefix`. Không tường / tổng dài 0 → 1,0. Tự kiểm lại thay cho lượt Codex 2 chưa chạy.
- **Chỗ gọi** (`tasks.py:165-169`): sau `build_layer`, trước `storage.put` → lượt hỏng `PermanentError(NOT_A_FLOOR_PLAN)`, không ghi `layer.json`, tầng giữ lớp cũ. Lý do đặt ở bước dựng (quality chạy sau persist) đứng được. Mã lỗi dùng lại chuỗi có sẵn của bước tách tường (`apps/ml/runtime/error_codes.py:30`); FE có câu báo (`AppFront/src/screens/pipeline/pipelineErrorText.ts`) → không đổi hợp đồng, job `contract` xanh.
- **Bằng chứng hành vi**: mô phỏng 95 `layer.json` (`F:/runs/bench-3d/dot4/quality/sim_axis.log`): chặn 4/4 ảnh 3D (0,47–0,60), 0 chặn nhầm. Chạy thật đối chiếu: `runs/r5` + `tap-f/runs/f3` — e-imp-1, e-imp-2, e-isg-1, f-30 hỏng ở `spatialDataBuild` với `NOT_A_FLOOR_PLAN`; ba ca hỏng khác (nt-07-render3d, e-aka-2, f-29) hỏng ở `wallSegmentation` như r4b/f2 trước nhánh; e-sun-2 (biên 0,69) `completed`. Không có mặt bằng hợp lệ nào bị chặn thêm.
- **PERF**: 820 lượt × phép vector 900 phần tử, độc lập số tường; lane đo 0,02 s cho 20 000 tường. CI `perf` xanh.
- SEC/CON/RES: hàm thuần trên lớp vừa dựng, không đầu vào người dùng mới, không trạng thái dùng chung, không I/O mới. Log `pipeline_build_not_a_floor_plan` chỉ có `run_id` + tỉ lệ.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG | Chặn cứng, không có đường lui, biên mỏng: mặt bằng hợp lệ thấp nhất đo được e-sun-2 0,687 so với ngưỡng 0,65. Tường cong bị dựng thành dây cung trải đều mọi hướng mod 90°, chỉ ~18 % chiều dài rơi vào 2 cửa sổ ±4° → mặt bằng có tường cong chiếm > ~43 % tổng dài (hoặc ba hướng chính, họ thứ ba > 35 %) bị báo "Ảnh tải lên không giống bản vẽ mặt bằng" và người dùng không dựng được gì. Bộ đo 95 ca chưa có ca nào như vậy nên chưa phải lỗi đã thấy, nhưng `changes/BENCH3D-19.md` không ghi rủi ro này. | `apps/worker/pipeline_quality/checks.py:62`, `:271-277`; `apps/worker/pipeline_build/tasks.py:165-169` | Ghi rủi ro + biên đo được vào `changes/BENCH3D-19.md`. Lượt sau: theo dõi log `axis_share` trên dữ liệu thật; nếu có chặn nhầm thì bỏ đoạn ngắn hơn ngưỡng (dây cung) khỏi histogram hoặc hạ chặn cứng thành cờ `geometrySuspect` cho dải 0,55–0,65. |
| 2 | P3 | MNT | `pipeline_build.tasks` nhập `pipeline_quality.checks`, trong khi `checks.py:17-18` đã nhập `pipeline_build.clusters`/`constants` → hai gói phụ thuộc vòng lẫn nhau (lint-imports chưa cấm, không vòng lúc nạp vì `pipeline_build/__init__` không nạp `tasks`). `axis_share`/`not_a_floor_plan` không được bước quality dùng. | `apps/worker/pipeline_build/tasks.py:24`; `apps/worker/pipeline_quality/checks.py:238-277` | Chuyển hai hàm + hằng sang `pipeline_build` (vd `pipeline_build/plan_shape.py`) để chiều phụ thuộc giữ một hướng quality → build. |
| 3 | P3 | LOG | Không có cỡ mẫu tối thiểu: lớp chỉ 3–4 tường theo 3 hướng (ảnh mờ, dựng ra ít tường) cũng bị gán `NOT_A_FLOOR_PLAN`, thông báo lệch nguyên nhân. | `apps/worker/pipeline_quality/checks.py:271-277` | Chỉ kết luận khi tổng dài tường / số tường vượt một ngưỡng nhỏ; dưới đó trả `None` để cổng khác báo. |
| 4 | P3 | TEST | Đường chặn ở `_build_and_write` chỉ được test bằng `monkeypatch` `not_a_floor_plan` → 0,5; chưa có test đi qua `build_layer` thật với tường xiên tới `failed NOT_A_FLOOR_PLAN`. Ca âm thật được phủ gián tiếp qua các test J01… | `apps/worker/pipeline_build/tests/test_tasks.py:277-288` | Thêm một test dùng đầu vào tường 4 họ hướng (như `test_checks.py` `four`) đi qua `_apply` mà không patch. |
| 5 | Nit | MNT | Chuỗi `NOT_A_FLOOR_PLAN` khai lại ở worker thay vì một nguồn chung (`packages.core.error_codes`); cùng mẫu với `PIPELINE_ARTIFACT_MISSING` có sẵn. | `apps/worker/pipeline_build/errors.py:17` | Khi gom mã lỗi, đưa về `packages.core.error_codes`. |
| 6 | Nit | MNT | Dòng `Prompt:` tách khỏi `Co-Authored-By:` bằng dòng trống nên `git interpret-trailers` không thấy nó (CI vẫn xanh). | commit 34767caa, 95b93ae8 | Để hai trailer cùng khối cuối. |

Không có P0/P1. Hai P2 của Codex lượt 1 (lưới thô, chọn tham lam) đã sửa và có test (`test_axis_share__best_pair_not_grid_or_greedy`).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,68 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,68 ≥ 4,0. Thuật toán `axis_share` đúng (đã soát chỉ số chồng cửa sổ và vòng mod 90°), chặn trước khi ghi `layer.json` nên tầng không bị ghi đè bằng mô hình rác, dùng lại mã lỗi FE đã hiểu, không đổi hợp đồng. Chạy thật r5/f3 khớp mô phỏng: 4/4 ảnh 3D bị chặn ở `spatialDataBuild`, ca biên e-sun-2 vẫn dựng. CI trên đúng SHA đầu nhánh xanh 24/24, độ phủ ≥ 90/90. Khuyến nghị (không chặn merge): ghi rủi ro chặn nhầm tường cong/ba hướng (finding 1) vào `changes/BENCH3D-19.md` và theo dõi log `axis_share`.
