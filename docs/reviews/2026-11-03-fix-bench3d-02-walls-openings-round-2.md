# Review merge fix/bench3d-02-walls-openings → main (lượt 2)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 2be05fc0dd5f (trên phán quyết lượt 1 `827809c1`)
- Cổng: phạm vi đích — lượt 2 chỉ soát vòng sửa `827809c1..2be05fc0` (R-33b), diff chỉ chạm `geometry._bridge_hosts`, một test và `changes/BENCH3D-02.md`, không chạm điều kiện (2)–(7). Bằng chứng: phạm vi đầy đủ (CI GitHub Actions run 41491482207), head `2be05fc0dd5fdbc1fb5737184e2331d51275e573` = đầu nhánh, kết luận `success`: changes, lint, typecheck, build, perf, unit-shards 1–2, integration-shards 1–5, ml-shards 1–3, unit, integration, ml, contract, coverage đều `success`. Kèm run 41491482198 (Commits, `success`) và 41491482187 (CodeQL, `success`). Không chạy cổng tại chỗ (người dùng quyết định, máy bận).
- Độ phủ: CI vẫn đo đầy đủ — tổng dòng 99,31% · nhánh 97,48% (`coverage_gate: đạt`); `apps/worker/pipeline_build` 98,18% / 93,11%; `packages/vision` 99,25% / 96,81%. Log CI không in số theo từng tệp, nên không có số riêng cho `geometry.py`.

## Phạm vi vòng sửa

- Một commit `2be05fc0 fix(walls): only collinear walls host a narrow envelope-gap closure`, dòng đầu đúng mẫu, có `Prompt: BENCH3D-02`. Cây sạch.
- `apps/worker/pipeline_build/geometry.py:1163-1180`: `_bridge_hosts` giờ chỉ giữ tường có đầu mút trùng đầu khe **và** `|cos(tường, khe)| ≥ _HUG_COS_MIN` (10°). Không pragma, `type: ignore`, `noqa`, skip mới.
- Sửa ở hàm dùng chung nên cả hai nhánh của `close_envelope_gaps` đều được hưởng: khe < 600 mm (`_extend_host` không còn chọn được vách vuông góc) và khe ≥ 600 mm (`max` bề dày / `min` tin cậy chỉ lấy từ tường thẳng hàng). Đúng gốc (R-19).

## Test mới có thật sự chặn lỗi không (soát bằng đọc mã)

`test_close_envelope_gaps__narrow_gap_skips_perpendicular_partition` (`test_geometry_openings.py:908`): đầu vào là vách `(2000,4000)→(2000,0)` cùng hộp có khe trên `[2000, 2500]`, qua `build_walls`, rồi gọi `_bridge_hosts` với khe `(2000,0)–(2500,0)`.
- Đầu trên của vách không bị dịch: đầu `(2000,0)` chạm đầu tường `A` (khoảng cách 0) nên không lơ lửng — `_extend_all` và `_reach_dangling` không kéo. Không có hộp ô mở nên `_merge_aligned` không gộp `A` với `B` qua khe (luật chỉ gộp "khe mang hộp"; test lượt 1 `narrow_exterior_gap_extends_a_host` cùng hình học cũng cho thấy khe còn). `Scaling(1, 1)` giữ nguyên toạ độ.
- Vì vậy với `geometry.py` trước sửa, vách có đầu mút `(2000,0)` trùng đầu khe nên lọt vào `hosts`, `start.y == 4000` → `assert all(... y == 0)` hỏng. Bất kể thứ tự tường. Sau sửa, vách bị lọc (cos = 0), còn `A` và `B` → `assert hosts` và `all(...)` đạt. Test chặn đúng lỗi ở tầng chọn tường chủ.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | TEST | Test gọi thẳng hàm riêng `_bridge_hosts`, không khẳng định kết quả cuối qua `close_envelope_gaps` (vách giữ nguyên hai đầu, `A` được kéo tới 2500). Đủ chặn lỗi đã báo, nhưng không chặn nếu sau này có chỗ khác chọn tường chủ. | `apps/worker/pipeline_build/tests/test_geometry_openings.py:908-920` | Khi chạm lại, dùng `_closed(...)` và khẳng định đầu mút của vách và của `A` sau khi khép. |
| 2 | Nit | TEST | Nhánh suy biến `gap == 0` / `length == 0` (giữ tường, không lọc theo góc) chưa có test. Thực tế không xảy ra, vì `_near_ends` chỉ trả khe `> 0` và tường dựng có độ dài dương. | `apps/worker/pipeline_build/geometry.py:1177` | Để nguyên. |

Finding P2 lượt 1: **đã đóng**. Ba P3 và ba Nit của lượt 1 (docstring trôi `:59-71`, chép luật C3 trong `_gap_door`, C4 lệch C3 ở `_merge_split`, các Nit) nằm ngoài vòng sửa này; vẫn sửa khi chạm lại tệp như lượt 1 đã ghi, không chặn merge.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,81 / 5

## PHÁN QUYẾT: APPROVE

Sửa đúng gốc ở hàm dùng chung; test mới, đọc theo mã, hỏng trên bản trước sửa và đạt trên bản sửa. CI đầy đủ xanh trên đúng head `2be05fc0` (run 41491482207 `success`, độ phủ tổng 99,31/97,48). Không có P0, P1 hay P2. Có thể merge.
