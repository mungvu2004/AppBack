# Review merge fix/bench3d-09-contract-area-readiness → main (lượt 2)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: 4b46caa2bafd (PR #39, `MERGEABLE`; `origin/main` hiện 63362ae3ab0c) · Lượt 1: `docs/reviews/2026-11-03-fix-bench3d-09-contract-area-readiness.md` (491d56af, REQUEST CHANGES)
- Cổng: phạm vi đích — soát vòng sửa `491d56af..4b46caa2`, không chạm hợp đồng/openapi/migration/phụ thuộc/cấu hình cổng; bằng chứng mã thoát lấy từ CI GitHub Actions chạy toàn bộ trên đầu nhánh: run 41567843888 (workflow CI, head `4b46caa2bafdf1a012d2ee10b93609536b30ecb9` = đầu nhánh) kết luận `success`, `gh run watch --exit-status` mã thoát 0. Mọi job đạt: `changes`, `lint`, `typecheck`, `unit` (+2 shard), `ml` (+3 shard), `integration` (+5 shard), `perf`, `build`, `contract`, `coverage`. CodeQL 41567843850 và Commits 41567844014 đạt. Người dùng duyệt dùng CI thay `run.sh verify` (như các review bench-3d trước); reviewer không chạy cổng/pytest tại chỗ.
- Độ phủ (job `coverage` của run 41567843888, `coverage_gate` + `case_gate` đạt): gói bị chạm vòng này `packages/domain` 99,74/98,56 · `apps/api/spatial_read` 98,95/99,18 · `apps/api/spatial_write` 99,79/97,50 · `apps/worker/pipeline_quality` 99,70/98,39. Tổng của run này 99,31/97,50 (chạy toàn bộ trên CI, không phải số chép của lượt 1). Log CI không in theo tệp; mọi gói ≥ 90/90.

## Phạm vi vòng sửa

- Một commit `4b46caa2 fix(spatial-read): robust clear area, distrust note scale, log layer`, đúng Conventional Commits, có `Prompt: BENCH3D-09`. Cây sạch, đầu nhánh local = `origin/fix/bench3d-09-contract-area-readiness`.
- 10 tệp, +170/−41. **Không** chạm `docs/contracts/*`, `tools/contract/APPFRONT_SHA`, `docs/charter/*`, `uv.lock` (`git diff --stat 491d56af..HEAD -- docs/contracts tools/contract` rỗng). Docstring `RoomOut.clear_area_m2` đổi nhưng openapi không mang mô tả trường (lượt 1 đã thấy `clearAreaM2` không có `description`), và job `contract` xanh. Không pragma/`noqa`/`type: ignore`/skip/xfail mới.

## Kiểm từng finding lượt 1

1. **P1 `clear_area_m2` ra 0 — đã sửa.** `area.py:100-188`: `_merged` gộp đỉnh lặp/thẳng hàng (|sin rẽ| ≤ 0,01) trước khi lùi; `_collapsed` tìm cạnh lùi lật chiều mà hai cạnh kề không song song, bỏ nó rồi giao lại (vòng lặp mỗi lần bớt một đường nên dừng); cạnh lật giữa hai cạnh song song (bậc tim tường) được giữ, có chú thích `ponytail:` nêu trần; không tính được (< 3 đường, `net ≤ 0` hay `net > gross`) → `None`. Đường bao diện tích 0 vẫn → 0,00, như trước.
   - `_meet` chia cho tích chéo: ở vòng đầu hai đường kề không song song nhờ `_merged` (khi còn > 3 đỉnh); sau khi xoá, `_collapsed` chỉ xoá khi hai đường kề có |sin| > 0,01. Trường hợp chỉ 3 đỉnh thẳng hàng đúng thì `gross == 0` đã trả sớm. Không thấy đường chia 0.
   - **Tự kiểm bench, không dựa vào số tác giả.** `bench.py` của tác giả in `464 0` nhưng chỉ đếm `c == 0` — `None` không bị đếm, và nó bỏ qua `ZeroDivisionError` — nên con số đó chưa chứng minh "không vắng cho phòng lớn". Đã xác nhận `clear.py` của tác giả `exec` đúng `packages/domain/spatial/area.py` của worktree (chỉ thay import `Point`/`Wall` bằng stub). Reviewer viết `r2check.py` riêng, chạy trên **mọi** `layer.json` của bench r1, r2, r3 (1 322 phòng), bắt mọi ngoại lệ: **0 phòng ra 0; 0 phòng > 2 m² vắng khoá; 6 phòng ≤ 2 m² vắng khoá; 0 ngoại lệ.** Thông thủy/tim tường cho phòng > 2 m²: p5 0,759 · p50 0,874 · p95 0,934 (n = 1 290). Tỉ lệ thấp nhất 0,39–0,41 rơi vào phòng hình học rác (vd `e-aka-3` "phòng khác": dải rộng 150 mm dài 13 m dính vào hộp 1,7 × 2 m), hợp lý. Toàn bộ 1 322 phòng tính hết ~0,3 s.
   - **Dây:** `layer_out` chỉ đặt `clearAreaM2` khi khác `None` (`wire.py:333-334`); `test_layer_out_omits_clear_area_when_not_computable` khẳng định khoá vắng. AppFront @ d5e44a95 có nhánh `clearAreaM2 === undefined` → dùng `areaM2` (`toViewModel.ts:434`, `roomLabelReviewGateway.ts:791`).
   - **Test chặn các ca đã sửa:** lô gia `ch-08` 5,65 → 4,80 (`test_area.py:205-213`), bậc tim 50 mm giữa tường 220/100 → 11,10 (reviewer tính tay: 1 950 × 2 840 + 1 950 × 2 850 = 11,0955 m² — khớp), chữ L hai chiều bao → 10,44, vát góc 100 mm lật → bỏ cạnh → 10,64, phòng hẹp/tam giác nhỏ hơn phần lùi → `None`.
2. **P2 gốc `note` — đã sửa.** `_MEASURED_BASES = {"chain", "paired"}` (`readiness.py:45-48`), docstring nêu lý do (in co trang lệch ×2); test `note-lone-ocr-still-unresolved` khẳng định `note` vẫn có `scaleUnresolved`. `changes/BENCH3D-09.md` cập nhật.
3. **P3 log — đã sửa.** `_built_or_none` log `quality_layer_unreadable` với `run_id`, `code` (`pipeline_quality/service.py:167-176`), không lộ nội dung tệp; test bắt đúng một bản ghi `(run_id, "PIPELINE_ARTIFACT_INVALID")`.
4. Nit 4 (`scaleStatus` vs `reasons`) và Nit 5 (đọc lại `layer.json`) của lượt 1: chưa đổi, không chặn.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | TEST | `float(clear_area_m2(...) or -1)`: `Decimal("0.00")` là falsy nên 0 bị đổi thành −1, còn `None` thì `room["clearAreaM2"]` đã `KeyError` trước đó. Đúng với dữ liệu mẫu hiện tại nhưng đọc dễ hiểu nhầm ý định. | `apps/api/spatial_read/tests/test_wire.py:68`; `apps/api/spatial_write/tests/test_routes.py:106` | `expected = clear_area_m2(...)`; `assert expected is not None and room["clearAreaM2"] == float(expected)`. |
| 2 | Nit | API | (giữ từ lượt 1, #4) `scaleStatus: "unresolved"` cùng lúc readiness không còn `scaleUnresolved` khi gốc `chain`/`paired`. | `apps/api/spatial_read/readiness.py:114-116` | Ghi một dòng vào docstring `FloorLayerDocumentOut.scale_status`. |
| 3 | Nit | PERF | (giữ từ lượt 1, #5) quality đọc lại cả `layer.json` chỉ lấy hai khoá. | `apps/worker/pipeline_quality/service.py:213` | Không gấp. |

Không có P0/P1/P2/P3.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 4,5 | 0,45 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,78 / 5

## PHÁN QUYẾT: APPROVE

Vòng sửa giải đúng gốc cả ba finding lượt 1. `clear_area_m2` không còn trả 0 cho phòng có diện tích: reviewer tự chạy lại trên 1 322 phòng bench r1–r3, không phòng nào ra 0 hay ném lỗi, không phòng > 2 m² nào vắng khoá. Khi không tính được thì khoá vắng trên dây và FE lùi về `areaM2`. Các ca gây lỗi (cạnh chẻ, bậc tim tường, chữ L, vát góc, phòng hẹp) đều có test với số tính tay khớp. Gốc `note` không còn được tin, và có log cho `layer.json` hỏng. Vòng này không đổi hợp đồng: `openapi.json`/`APPFRONT_SHA` giữ nguyên, job `contract` xanh. CI GitHub Actions run 41567843888 trên đúng đầu nhánh `success`, độ phủ các gói bị chạm ≥ 90/90. Ba Nit không chặn merge.
