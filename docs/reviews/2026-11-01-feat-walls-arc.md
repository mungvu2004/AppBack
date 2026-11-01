# Review merge feat/walls-arc → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, tác giả không tự chấm) · Commit đầu nhánh: d763b2bc4814
- Cổng: phạm vi lượt 1 **đầy đủ** (R-33b điều kiện 1) — `bash tools/verify/run.sh verify` mã thoát 0, 8/8 bước đạt (log
  `F:/runs/walls-arc/review-full.log`, log cổng `.cache/src-out/verify/20261031T214130Z-d763b2bc4814.log`: SHA khớp HEAD;
  pytest 9320 đạt trong 8 phút 22 giây; 5b perf 12 test đạt; bước 6 migrate_check đạt; bước 7 hợp đồng AppFront @ a4bbd512
  đạt; bước 8 openapi đạt). Trước khi chạy không có container verify nào, C: còn 112 GB, `f14-ml-1` để tắt.
- Độ phủ: tổng dòng 99,41 % · nhánh 97,55 % | `apps/worker/pipeline_build` 98,39 % / 92,86 % · `packages/vision` 99,24 % / 96,78 %
  · `apps/ml/walls` 99,51 % / 96,88 % · `packages/ml_contracts` 99,91 % / 99,57 % · `packages/domain`, `apps/worker/datasets`,
  `apps/api/spatial_read` 100 % / 100 % | tập file bị chạm 98,68 % / 94,23 %.
- Phạm vi: 5 commit không merge + 2 merge `origin/main`; ~395 dòng thêm ngoài test (dưới 400, không cần tách). Cây sạch, HEAD
  đã đẩy (`origin/feat/walls-arc` = HEAD). Commit đúng mẫu, đủ `Prompt: WALLS-ARC` (hai commit merge là merge của git, như các
  nhánh trước). Có `changes/WALLS-ARC.md`. Diff **không** chạm `openapi.json`, `tools/contract/APPFRONT_SHA`, `docs/charter/*`,
  `uv.lock`. Không `pragma`, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
- Hợp đồng: `curveOffsetMm` vắng khoá khi 0 ở cả `Wall` (jsonb) và `WallOut` (dây), nên tài liệu cũ và FE `.strict()` cũ không
  đổi; AppFront `origin/master` đã có `curveOffsetMm` tuỳ chọn (`src/api/schemas/spatial.ts:242`). Pascal đặt ô mở theo chiều
  dài cung (`door-math.ts` `localX / getWallCurveLength`), khớp với `offsetMm` cộng dồn chiều dài dây ở `arcs._shifted`.
  Không migration (tầng là JSONB); đường ghi dùng chính `SpatialLayer` nên nhận `curveOffsetMm` và kiểm |giá trị| ≤ L/2 + 1.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (gỡ ở 6b2e4d52); trọng số chấm lấy theo phán quyết trước
  (`2026-11-01-fix-walls-curve-shaft.md`); nợ của nhánh nằm trong `changes/WALLS-ARC.md` (NO-431..434).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-03 / CON | Nhánh mở đường ghi `curveOffsetMm`, nhưng `diff_layers` không theo dõi trường này (`Wall: ("thickness_mm", "height_mm", "kind", "paint")`), nên `mark_edited` không bật `edited` khi người **chỉ** uốn/duỗi một tường AI chưa duyệt. Lượt chạy lại pipeline giữ mục `reviewed`/`human`/`edited` (`merge.py:107`), còn tường đó bị thay bằng tường máy dựng: sửa của người mất mà không báo. FE không tự gửi `edited` cho tường (`spatial.ts` chỉ gửi cho đồ đạc, kích thước). NO-431 mới ghi phần nhật ký, chưa ghi hậu quả này | `packages/domain/spatial/diff.py:21`, `packages/domain/spatial/provenance.py:39-49`, `packages/domain/rules_ai/merge.py:107` | Thêm `curve_offset_mm` vào trường theo dõi của `Wall` (đổi bảng HOP-DONG-MOI §1.3 nên người điều phối làm), hoặc trước đó cho `mark_edited` so riêng `curve_offset_mm` như `_DIMENSION_FIELDS`. Ít nhất ghi hậu quả này vào NO-431 trước merge |
| 2 | P3 | LOG-02 | `object_boxes` (nhãn YOLO cửa/cửa sổ) đặt ô mở trên tường cong theo **dây** `start→end`, nên hộp lệch khỏi tường tới cỡ sagitta. NO-433 chỉ ghi khe cửa trong mặt nạ (dòng 149), còn chỗ này cũng hỏng như vậy mà chưa ghi | `apps/worker/datasets/render.py:188`, `:106-115` | Đặt đoạn `[offset, offset + width]` theo `arc_points` của tường (đi theo chiều dài cung), dùng cho cả hai chỗ gọi; hoặc tạm bỏ ô mở trên tường cong khỏi nhãn; ghi thêm vào NO-433 |
| 3 | P3 | TEST-01 | Không có test tầng API cho `WallOut.curve_offset_mm`: đọc (khoá vắng khi 0, có khi khác 0) và ghi `PUT` giữ được `curveOffsetMm`/từ chối khi > L/2. Độ phủ 100 % chỉ vì giá trị mặc định đã chạy qua | `apps/api/spatial_read/wire.py:99`; `apps/api/spatial_read/tests`, `apps/api/spatial_write/tests` | Thêm một test đọc và một test ghi đi qua dịch vụ thật |
| 4 | P3 | LOG-02 | `_off_node` chỉ bỏ điểm xương quanh đầu **b** của đoạn được nới thêm. Đoạn đầu chuỗi (`inners[start]`) không bao giờ được cắt, kể cả khi đầu **a** của nó là nút giao. Lưỡi mặt nạ hụt nằm ở đầu a (đảo chiều xương so với test) vẫn làm cung đứt như lỗi be6e3c9c đã sửa cho đầu b | `packages/vision/walls/vectorize.py:502`, `:526-528` | Cắt cả đầu a của `segs[start]` khi `a_key[0] == 0`; thêm biến thể đảo chiều cho test lưỡi mặt nạ |
| 5 | P3 | R-34 | Repo không còn `DEBT.md`; NO-431..434 chỉ nằm trong `changes/WALLS-ARC.md` | `changes/WALLS-ARC.md:17-23` | Ghi các nợ này (và phần thêm của finding 1, 2) vào sổ nợ/backlog mà dự án đang dùng |
| 6 | Nit | LOG-01 | `explode_arcs` chỉ kẹp toạ độ ≥ 0, không kẹp mép phải/dưới, và điểm bị kẹp không còn nằm trên cung. Ở góc (0, 0), hai đỉnh liền nhau có thể trùng, khi đó `WallPx` ném lỗi. `_finalise` cũng kẹp đầu mút **sau** khi đã tính sagitta, nên về lý thuyết \|s\| có thể vượt L/2 và trượt bộ kiểm của `WallPx`. Cả hai rất khó gặp vì cung lấy từ xương nằm trong ảnh và đã tách ở 170° | `apps/worker/pipeline_build/arcs.py:42-43`; `packages/vision/walls/vectorize.py:1451`, `:1458` | Bỏ dây suy biến thay vì để `WallPx` ném lỗi; kẹp lại sagitta về nửa dây sau `_clamp` |
| 7 | Nit | R-07 | Ba bản `_straight`/lambda cùng một ý (`model.py:142`, `artifacts.py:103`, `wire.py:99`); công thức bán kính `L²/8s + s/2` chép lại ở `explode_arcs` thay vì lấy từ `domain/spatial/arc.py` | như cột trái; `apps/worker/pipeline_build/arcs.py:35` | Gom về một hàm thuần trong `arc.py` (vd. `arc_radius`) |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4 | 0,60 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4 | 0,40 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 4 | 0,12 |
Tổng: 4,65 / 5

## PHÁN QUYẾT: APPROVE

Không có P0/P1, cổng đầy đủ mã thoát 0, độ phủ tổng 99,41/97,55 và mọi gói bị chạm ≥ 90/90; điểm 4,65 ≥ 4,0.
Không có tệp cấm trong diff: sau merge, người điều phối tự cập nhật `openapi.json` và nâng `tools/contract/APPFRONT_SHA` bằng
commit riêng, như `changes/WALLS-ARC.md` đã ghi. Không chặn merge nhưng phải xử lý: finding 1 (ghi vào NO-431 hoặc vá
`mark_edited` trước khi người dùng uốn tường trên f14) và finding 2 (ghi thêm vào NO-433).
