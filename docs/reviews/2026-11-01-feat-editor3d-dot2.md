# Review merge feat/editor3d-dot2 → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, tác giả không tự chấm) · Commit đầu nhánh: d36ceb9fa340
- Cổng: phạm vi lượt 1 **đầy đủ** (R-33b điều kiện 1; diff còn chạm `docs/contracts/**`). Reviewer **chưa chạy được**
  `bash tools/verify/run.sh verify`: vòng chờ (đợi 0 container verify) chờ từ 16:04 tới 17:07. Suốt thời gian đó máy luôn có
  container verify của phiên khác (`gate-queue`, PERF-11, kèm 3 container `hold`). Lúc 17:07 phiên điều phối dừng vòng chờ khi
  nó **chưa** dựng container nào (log `F:/App/ui-review/editor3d-20261031/log/dot2-review-full.log` chỉ có dòng `start wait`).
  Bằng chứng cổng BE duy nhất là lượt `verify --steps 5,7` của người điều phối tại d36ceb9fa340 (log
  `F:/App/ui-review/editor3d-20261031/log/dot2-be-contract.log`, log cổng `.cache/src-out/verify/20261101T091644Z-d36ceb9fa340.log`):
  **mã thoát 1**, bước 5 `hỏng` (2 failed / 9347 passed, 26 phút 26 giây), bước 7 `chưa chạy`. Lượt đó chạy cùng lúc với cổng
  `gate-queue`.
- Độ phủ: **không đo** (bước 5 hỏng nên không có số độ phủ của gói).
- Phạm vi: 3 commit + 1 merge `origin/main` (xung đột `diff.py` giải đúng: giữ `curve_offset_mm` của main, thêm trường mới). ~70
  dòng logic, dưới 400. Cây sạch. Nhánh **chưa đẩy** (upstream là `origin/main`, không có `origin/feat/editor3d-dot2`); việc đẩy
  thuộc người merge. Có `changes/EDITOR3D-DOT2.md`. Không có `pragma`, `noqa` trần, `type: ignore`, skip/xfail mới, không hạ ngưỡng.
- Tệp cấm: `docs/contracts/openapi.json` và `tools/contract/APPFRONT_SHA` chỉ nằm trong commit `d36ceb9f` `chore(contract)`.
  Commit này là việc của người điều phối, đúng yêu cầu ở `changes/EDITOR3D-DOT2.md:12-13`, nên **chấp nhận** (tiền lệ
  `2026-10-27-fix-openapi-snapshot.md:26`). Reviewer so ngữ nghĩa JSON `origin/main` với HEAD: chỉ có đúng 8 khác biệt, đều
  là **thêm** thuộc tính tuỳ chọn (`Opening`/`OpeningOut`.`doorStyle`,`reversed`; `Room`/`RoomOut`.`dressingOff`,`ceilingMaterial`),
  không xoá hay đổi gì, nên tương thích ngược. `25de8d3c` có trong `AppFront origin/master` (`merge-base --is-ancestor`).
- Hợp đồng FE: `AppFront@25de8d3c src/api/schemas/spatial.ts:229-231,279-327` khớp đúng: cùng regex `DRESS-`, cùng trần
  200, cùng enum `doorStyle`. FE bỏ khoá `dressingOff` khi rỗng và bỏ `reversed` khi khác `true`.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (gỡ ở 6b2e4d52). Trọng số chấm lấy theo phán quyết trước
  (`2026-11-01-feat-walls-arc.md`).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | API / CON | BE thêm bất biến `doorStyle` chỉ hợp lệ khi `kind="door"` và `swing="sliding"`, nhưng FE @ 25de8d3c không giữ bất biến này. `OpeningSchema` không có `refine`. Hai lệnh QC sửa ô mở đều rải `...input.before`, nên vẫn giữ `doorStyle`: đổi chiều mở (`objectLayerReviewGateway.ts:1056`, `{ ...input.before, swing: input.swing }`) và đổi loại cửa đi → cửa sổ (`:992-997`). Cửa lùa âm tường/xếp tạo trong 3D, sau đó đổi sang `left` (hoặc thành cửa sổ) trên màn duyệt lớp đối tượng, sẽ làm **cả lần PUT tầng bị 422** (`doorStyle chỉ dùng cho cửa đi swing=sliding`). Người dùng không lưu được tầng cho tới khi đổi lại | `packages/domain/spatial/model.py:285-290`; AppFront `src/screens/qc/ObjectLayerReview/objectLayerReviewGateway.ts:992-997,1056` | Sửa phía AppFront (prompt FE riêng): hai lệnh trên bỏ `doorStyle` khi `swing !== 'sliding'` hoặc `kind !== 'door'`, và `OpeningSchema` thêm `refine` cùng luật để lỗi hiện ở FE. Giữ validator BE (kiểm ở biên là đúng). Ghi nợ này vào sổ đang dùng trước merge |
| 2 | P3 | LOG-01 | `changes/EDITOR3D-DOT2.md:4` ghi `dressing_off` "vắng khoá khi rỗng", nhưng mô hình nhận `[]` và lưu `()`: `exclude_none` không bỏ tuple rỗng, nên `[]` được ghi xuống và đọc ra lại. `None`→`()` cũng tạo một `FieldChange` và bật `edited`, dù không có gì đổi. FE hiện tại không gửi `[]`, nên đây chỉ là lệch giữa ghi chú và mã | `packages/domain/spatial/model.py:340` | Thêm `exclude_if=lambda v: not v` (hoặc validator đổi `()`→`None`) để đúng lời ghi chú; hoặc sửa ghi chú |
| 3 | P3 | TEST-01 | `doorStyle` chỉ được test ở tầng miền (`test_opening_door_style_only_on_sliding_door`). `PASCAL_FIELDS` không có `doorStyle`, nên không có test nào đi qua API thật cho đọc/ghi `doorStyle`, cũng không có test PUT cửa bản lề mang `doorStyle` → 422 với đúng phong bì lỗi/`field` | `packages/domain/spatial/samples.py:243`; `apps/api/spatial_write/tests/test_routes.py:99-104` | Thêm một test PUT khứ hồi cửa lùa `doorStyle: "pocket"` và một test thân sai C02 cho cửa `swing="left"` |
| 4 | P3 | R-36b | Trailer `Prompt:` của `c92b61f9` và `d36ceb9f` **không đọc được**: `git log --format='%(trailers:key=Prompt)'` in rỗng, vì một dòng trống tách `Prompt:` khỏi `Co-Authored-By:`, khiến `Prompt:` không nằm trong khối trailer cuối. Chỉ `34379822` đọc được. `git log --grep` vẫn tìm ra, nên không coi là "thiếu trailer" (tiền lệ `2026-09-20-feature-b0-04-object-storage.md:20`, P3 không chặn) | thân commit `c92b61f9`, `d36ceb9f` | Lần sau để `Prompt:` và `Co-Authored-By:` liền nhau. Nếu gộp squash/viết lại thì dùng khối trailer liền |
| 5 | Nit | LOG-01 | `dressing_off` không chặn id trùng: 200 chỗ có thể là cùng một id | `packages/domain/spatial/model.py:340` | Tuỳ chọn: kiểm duy nhất ở validator, hoặc để FE khử trùng |

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

## PHÁN QUYẾT: REQUEST CHANGES

Về mã thì không có P0/P1 và điểm 4,65 ≥ 4,0. Thay đổi nhỏ, chỉ thêm trường tuỳ chọn, tương thích ngược, khớp với schema FE
@ 25de8d3c. `diff_layers` theo dõi các trường mới, nên `mark_edited` giữ được sửa của người khi chạy lại pipeline. Không có migration.

Chặn merge chỉ vì **thiếu bằng chứng cổng**. Lượt cổng BE duy nhất tại HEAD thoát 1 (bước 5: `test_run_training_job_m04_fails_when_a_lock_is_lost[cuda-gpu-GPU_LOCK_LOST]`
và `test_quality_set_corners__queue_capacity[1]`). Cả hai test này nhạy thời gian (sleep 0,4 s, chờ hàng 0,3 s), nằm ngoài vùng
diff chạm, và lượt đó chạy chung máy với một cổng khác. Rất có thể đây là lỗi do tải chứ không phải hồi quy, nhưng chưa có bằng
chứng. Lượt cổng đầy đủ của reviewer bị dừng trước khi chạy.

Điều kiện để được APPROVE (không cần sửa mã):
1. Chạy `bash tools/verify/run.sh verify` đầy đủ tại d36ceb9fa340 (hoặc HEAD sau commit phán quyết này), lúc **không** có
   container verify nào khác, và thoát 0 với 8/8 bước đạt. Mỗi gói bị chạm (`packages/domain`, `apps/api/spatial_read`) cùng
   tổng phải ≥ 90/90. Hai test trên phải đạt; nếu vẫn đỏ khi máy rảnh thì phải truy gốc.
2. Ghi finding 1 (nợ FE: `doorStyle` mồ côi → 422) vào sổ nợ/backlog đang dùng, giao prompt AppFront sửa.

Finding 2–4 không chặn merge, nên xử lý trong lượt sửa kế tiếp. Việc merge thuộc phiên gọi review.

---

# Lượt 2 — review merge feat/editor3d-dot2 → main

- Ngày: 2026-11-01 · Reviewer: phiên /merge-review (agent độc lập, lượt 2) · Commit đầu nhánh: e5ee29e21064
- Phạm vi: 3 commit sau phán quyết lượt 1 (`5a0db696`): `5176fa5d` (sửa), merge `50fc4226` (`origin/main` = `f14f478c`,
  PERF-11), `e5ee29e2` (E501 docstring). Diff vòng sửa chỉ chạm `packages/domain/spatial/model.py` (+8/−2) và hai tệp test;
  không chạm điều kiện (2)–(7) của R-33b. Merge sạch: `git show --remerge-diff 50fc4226` rỗng, `git diff 5176fa5d 50fc4226`
  trùng đúng `git diff merge-base..f14f478c` (7 tệp PERF-11, không thêm gì lạ). Cây sạch, HEAD = `origin/feat/editor3d-dot2`.
  Trailer `Prompt: EDITOR3D-DOT2` đọc được bằng `%(trailers:key=Prompt)` ở cả ba commit mới. Không pragma/noqa/type: ignore/skip/xfail.
- Cổng: phạm vi **đích** (lượt 2, R-33b). Reviewer tự chạy tại e5ee29e21064:
  - `bash tools/verify/run.sh verify --steps 1,2,3,4` → **mã thoát 0** (log `F:/App/ui-review/editor3d-20261031/log/dot2-review2-steps1234.log`,
    log cổng `.cache/src-out/verify/20261101T105150Z-e5ee29e21064.log`).
  - `run.sh shell` + `pytest packages/domain/spatial apps/api/spatial_write apps/api/spatial_read --cov --cov-branch` →
    **642 passed, mã thoát 0** (log `F:/App/ui-review/editor3d-20261031/log/dot2-review2-pytest.log`).
  - Bằng chứng thêm (đã kiểm, không chỉ tin): cổng **đầy đủ** của tác giả tại đúng HEAD — tên log do `run.sh` đặt theo
    `git rev-parse --short=12 HEAD`: `.cache/src-out/verify/20261101T103930Z-e5ee29e21064.log`, 8/8 bước `đạt`, `mã thoát: 0`,
    bước 5: 9352 passed (hai test đỏ ở lượt 1 nay đạt), bước 7 AppFront @ 25de8d3c đạt, bước 8 openapi đạt. Đáp ứng điều kiện 1 của lượt 1.
- Độ phủ: tổng không đo (phạm vi đích) — file đổi: `packages/domain/spatial/model.py` 100%/100% (coverage bỏ qua vì phủ đủ);
  hai tệp test 100%/100%. (Lượt đầy đủ của tác giả ghi: `packages/domain` 100/100, `apps/api/spatial_write` 99,79/97,50,
  `apps/api/spatial_read` 100/100, tổng 99,41/97,58.)

## Đối chiếu finding lượt 1
| # lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|
| 1 P2 doorStyle mồ côi → 422 | **Đã sửa ở FE, chưa vào master** | AppFront `feat/editor3d-dot2` @ `66fe141a`: `withSlidingStyleChecked` (`objectLayerReviewGateway.ts:977-986`) bọc cả lệnh đổi loại (`:996-1001`) và đổi chiều mở (`:1063-1065`); `OpeningSchema.refine` cùng luật với `Opening._door_style_on_sliding_door` (`spatial.ts:285-288`). Đường sinh `doorStyle` duy nhất còn lại (`toSpatial.ts:299-303`) chỉ gắn khi `swing: 'sliding'`. `66fe141a` **chưa** là tổ tiên `origin/master` của AppFront |
| 2 P3 dressingOff `[]` | Đã sửa | `model.py:340-344` `AfterValidator(lambda ids: ids or None)` → `[]` lưu như vắng, không tạo `FieldChange`; trần 200 vẫn giữ (`test_model.py:178` 201 id bị từ chối, đạt); test `test_empty_dressing_off_is_absent` |
| 3 P3 test API doorStyle | Đã sửa (một phần) | `test_routes.py:107-123` khứ hồi `pocket` trên cửa lùa (200 + GET đọc lại) và cửa `left` → 422. Chưa khẳng định phong bì lỗi/`field` — xem finding 1 dưới |
| 4 P3 trailer | Không sửa commit cũ (chấp nhận, không viết lại lịch sử); commit mới đúng | `%(trailers:key=Prompt)` của `5176fa5d`, `50fc4226`, `e5ee29e2` |
| 5 Nit id trùng | Giữ nguyên | — |

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-01 | Ca 422 chỉ khẳng định `status_code`, không khẳng định phong bì lỗi (mã/`field` trỏ `doorStyle`) — một 422 vì lý do khác của thân cũng làm test xanh | `apps/api/spatial_write/tests/test_routes.py:118` | Khi 422 thì assert thêm mã lỗi và trường trong phong bì như các test thân sai C02 khác |
| 2 | P3 | API / R-27 | Sửa của finding 1 lượt 1 nằm ở AppFront `66fe141a`, chưa merge. Merge BE trước FE vẫn an toàn (chỉ thêm trường tuỳ chọn), nhưng đường QC đổi chiều mở/đổi loại trên cửa lùa âm tường/xếp vẫn 422 cho tới khi FE vào master | AppFront `feat/editor3d-dot2` | Phiên merge gộp FE `feat/editor3d-dot2` ngay sau BE; sau đó nâng `tools/contract/APPFRONT_SHA` lên SHA master có `66fe141a` (commit `chore(contract)` của người điều phối) để bước 7 kiểm H1 bằng schema đã có `refine` |
| 3 | Nit | LOG-01 | (giữ từ lượt 1) `dressing_off` không chặn id trùng | `packages/domain/spatial/model.py:340` | Tuỳ chọn |

APPFRONT_SHA: giữ `25de8d3c` cho merge này là **đúng**. Vòng sửa không đổi hình dạng hợp đồng: bước 8 openapi đạt (đổi
kiểu `dressing_off` không đổi JSON schema xuất ra), FE chỉ thêm `refine` (không đổi khoá/kiểu), mẫu `samples.py` không có
`doorStyle` nên `refine` không làm H1 đổi kết quả. Nâng pin sau khi FE merge là việc nên làm (finding 2), không chặn.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4 | 0,40 |
| TEST | 7% | 4 | 0,28 |
| OBS/OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |
Tổng: 4,83 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1/P2, điểm 4,83 ≥ 4,0. Lý do chặn của lượt 1 (thiếu bằng chứng cổng) đã hết: cổng đầy đủ tại đúng e5ee29e21064
thoát 0 với 8/8 bước, reviewer chạy lại phạm vi đích cũng thoát 0. Finding 2–3 lượt 1 đã sửa; finding 1 lượt 1 đã sửa phía
AppFront. Việc còn lại (không chặn): merge AppFront `feat/editor3d-dot2` ngay sau, rồi nâng `APPFRONT_SHA`; assert phong bì
lỗi ở test 422 trong lượt chạm tệp kế tiếp. Việc merge thuộc phiên gọi review.
