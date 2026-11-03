# Review merge fix/bench3d-14-sheet-gates → main

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 1) · Commit đầu nhánh: 1519fbaa962e (PR #42; merge-base 297f2067ea93 = `origin/main` hiện tại, nhánh không chậm hơn main; PR `MERGEABLE`)
- Cổng: Phạm vi kiểm: đầy đủ (CI GitHub Actions run 41589644719) — quy ước hiện hành dùng CI thay `run.sh verify` trên máy. Run 41589644719 (workflow CI, sự kiện `pull_request`, head `1519fbaa962eb0caa150863c7c03fef9f55fde0e` = đầu nhánh, kết luận `success`): `changes`, `lint`, `typecheck`, `unit` (2 shard), `ml` (3 shard), `integration` (5 shard), `build`, `contract`, `coverage`, `perf` đều `success`. Run 41589644794 (CodeQL, actions + python): `success`. Run 41589644743 (Commits): `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41589644719, `coverage_gate: đạt`, `case_gate` đạt, 0 cảnh báo): tổng dòng 99,31% · nhánh 97,50% — gói bị chạm: `apps/ml/walls` 99,54% / 97,22%; `apps/worker/pipeline_build` 98,29% / 93,47%; `apps/worker/pipeline_quality` 99,73% / 98,53%. Tất cả ≥ 90/90.
- Ghi chú: checkout không có `RULE.md`, `RULE-CODE.md`, `DEBT.md` (đã gỡ ở 6b2e4d52); trọng số chấm theo các phán quyết trước. Nợ ghi vào `changes/<mã>.md`.

## Phạm vi

- Cây sạch. 2 commit, dòng đầu đúng Conventional Commits, mỗi commit có `Prompt: BENCH3D-14`:
  `0b65ad01 fix(quality): scale-free multiple-plan check, compact-drawing gate`,
  `1519fbaa feat(quality): report rotated plans from vertical room labels`.
- 12 tệp, +343/−31 (mã logic ~150 dòng, còn lại là test và `changes/BENCH3D-14.md`) — dưới 400, không cần tách.
- Có `changes/BENCH3D-14.md`. Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa` trần, `type: ignore` mới, skip/xfail mới, không hạ ngưỡng.

## Soát nội dung

- **Ranh giới tệp (R-27, `BRIEF-dot3.md` làn L3):** `checks.py`, `step.py` (cổng `NOT_A_FLOOR_PLAN`), `rooms.py` (`_roomy` + `_open_space_labels`, dòng 615-645, cộng docstring hằng `_CORRIDOR_DEPTH_MM` dòng 135-137 của cùng luật) đúng bảng làn. `build.py` chạm ngoài các dải ghi trong bảng (`_OPTIONAL_KEYS` :128, `BuiltLayer` :152-212, `label_orientation` cuối module, một đối số ở :798) — đây là đường "OCR → quality cho `ROTATED_PLAN`" mà làn được giao; điều tra `no.md` S4 đã chỉ rõ phải mang số đếm qua `BuiltLayer` vì bước quality chỉ đọc `layer.json`. Không đổi tên/chữ ký hàm dùng chung (`build_report`, `geometry_checks` chỉ thêm tham số khoá có mặc định). Gộp thử `git merge-tree` với các làn cùng đợt `fix/bench3d-12`, `-13`, `-15`, `-16`: sạch, không xung đột.
- **Hợp đồng FE (`readiness.checks`):** nhánh không chạm `apps/api`. `GEOMETRY_CHECK_ORDER` của `main` (`apps/api/spatial_read/readiness.py:35-42`) đã có `ROTATED_PLAN` từ BENCH3D-09. `readiness.checks` chỉ lấy `criticalChecks` (`readiness.py:79`), mà `ROTATED_PLAN` luôn `critical=False` → mã này **không bao giờ lên dây**; chỉ nằm trong `quality.json` và `quality_summary.checks` (JSONB). Dù có lên, AppFront @ `APPFRONT_SHA` d5e44a95 nhận mã lạ: `src/api/schemas/spatialLayer.ts:94` `checks: z.array(z.string().min(1)).optional()`. Job `contract` xanh. Không đổi API/DB/migration.
- **MULTIPLE_PLANS** (`checks.py:146-185`): chỉ báo không phụ thuộc tỉ lệ đúng đề xuất S1 (tử, mẫu cùng nhân tỉ lệ); `_scale_free_spans` trả `None` khi không phòng nào có diện tích > 0 (ca rỗng có xử lý). Luật span 35 m theo dải sai số `SCALE_ERROR` thận trọng hơn đề xuất S1 (S1 bỏ hẳn luật span cho nguồn ước lượng; nhánh giữ nó, `door` vẫn chặn khi span > 42,2 m). Đối chiếu mô phỏng r3 (`no.md`): e-sun-1 (75 m), e-sun-2 (54 m), nt-03 (46 m) đều `door` → vẫn critical; e-aka-3 thêm critical; nhóm A không báo nhầm. Bench thật r4b (`KET-QUA-r4.md`, mã gồm PR #40-#44): D 7/7, không ca nào tụt hạng. Mỗi nhánh (block/warn/absent theo 4 nguồn tỉ lệ, ranh lô rộng, 6 căn tỉ lệ sai ×0,4) có test.
- **NOT_A_FLOOR_PLAN** (`step.py:190`, `219-235`): dưới sàn 0,3 vẫn luôn từ chối — 11 ảnh không phải bản vẽ của bộ hiệu chỉnh cao nhất 0,23 nên bộ hiệu chỉnh không đổi kết quả. Dải [0,3; 1,0) nhận khi tổng tường ≥ 2 lần cạnh dài hộp bao tường; `walls` rỗng → tổng 0 → từ chối (không chia 0). Test 4 ca (căn nhỏ giữa trang, nét rải, dưới sàn, lấp trang) + log khi từ chối. Bench thật r4b: e-mpp-1 lên ĐẠT, nt-07 vẫn bị chặn.
- **Hành lang chữ L** (`rooms.py:615-645`): `_roomy` = `buffer(-1250)` không rỗng, áp cho cả "hành lang" lẫn phòng không tên lớn nhất, đúng S5 (mô phỏng 0 ca đổi trên 56 phòng khách). Test hành lang L có chữ/không chữ và phòng khách L rộng 3 m.
- **ROTATED_PLAN** (`build.py:802-821`, `checks.py:218-226`): đếm nhãn ≥ 3 chữ cái, `span_px is None`; hộp gần vuông không tính; ≥ 3 nhãn và ≥ 60 % dọc → chỉ báo. `labelOrientation` là khoá gốc tuỳ chọn, chỉ ghi khi có nhãn, `from_json` từ chối bộ khoá lạ/không phải object (test). `service.py` đọc `layer.json` trước `build_report` (trước đây đọc ngay sau, cùng một lần đọc — không thêm I/O).
- SEC/CON/RES: không đầu vào người dùng mới, không trạng thái dùng chung, không I/O mới; log `walls_not_a_floor_plan` chỉ có `run_id` và hai tỉ số.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | LOG | Chỉ báo không phụ thuộc tỉ lệ dùng **cạnh dài** hộp bao chia √(trung vị diện tích phòng). Nhà phố dài một căn (lô 4 × 25 m) có nhiều phòng nhỏ (3 WC, kho, giếng trời, hộp kỹ thuật, lô gia) cho trung vị ~6 m² → 25 / 2,45 = 10,2 tường và ~10 phòng → `MULTIPLE_PLANS` critical (báo nhầm `geometrySuspect`). Biên từ căn đơn lớn nhất của bench (8,1, cn-19) tới ngưỡng 10 chỉ 1,2×, bench chưa có nhà phố dài (`no.md` §4 tự ghi). | `apps/worker/pipeline_quality/checks.py:48-51`, `146-153`, `181` | Thêm một test nhà phố 4 × 25 m nhiều phòng nhỏ; nếu bật thì bỏ phòng < 4 m² khỏi trung vị hoặc chuẩn hoá theo √(diện tích hộp bao) thay cạnh dài. Ghi giới hạn này vào `changes/BENCH3D-14.md`. |
| 2 | P3 | OBS | Docstring hứa "log ghi cả hai tỉ số để hiệu chỉnh lại", nhưng chỉ log khi **từ chối**. Trang được **nhận nhờ dải** [0,3; 1,0) không để dấu vết, nên không phát hiện được nhận nhầm (phối cảnh 3D có khung thành tường kiểu f-22/f-23/f-30 của tập F). Ngưỡng `DRAWING_WALL_LENGTH_RATIO = 2.0` chưa chạy lại trên SegFormer thật với ảnh không phải bản vẽ (tác giả tự ghi). | `apps/ml/walls/step.py:72-78`, `219-235` | Log `walls_low_evidence_accepted` (cùng `page_ratio`, `drawing_ratio`) khi nhận qua dải; đợt sau chạy lại 11 ảnh không phải bản vẽ + f-22/f-23/f-30 để hiệu chỉnh. |
| 3 | P3 | DB/API | Kiểm không critical không có người dùng: `readiness.checks` chỉ lấy `criticalChecks`, nên `ROTATED_PLAN` và `MULTIPLE_PLANS` mức báo (span 35-60 m với tỉ lệ `wallThickness`/`default`, trước nhánh này là critical) chỉ còn trong `quality.json`/`quality_summary`, người dùng không thấy. Không vỡ hợp đồng (FE nhận chuỗi tự do) và không ca bench nào bị hạ (r4b D 7/7), nhưng phần "chỉ báo" hiện chưa tới tay ai. | `apps/api/spatial_read/readiness.py:79-87`; `apps/worker/pipeline_quality/checks.py:182-185`, `218-226` | Ghi vào `changes/BENCH3D-14.md` (hoặc nợ đợt sau): cần trường dây cho kiểm mức báo (ví dụ `readiness.warnings`) nếu muốn `ROTATED_PLAN` hiện cho người dùng. |
| 4 | P3 | R-07 | `_TEXT_ASPECT = 1.5` chép lại `apps.ml.text.reader.ROTATE_RATIO` (`reader.py:71`), docstring tự nói "cùng ngưỡng". Hai nguồn sự thật: đổi ngưỡng xoay vùng OCR ở một chỗ thì đếm hướng nhãn lệch. | `apps/worker/pipeline_build/build.py:803`; `apps/ml/text/reader.py:71` | Đặt hằng chung cạnh `TextPx` trong `packages/ml_contracts/artifacts.py` và import ở cả hai nơi. |
| 5 | P3 | DB/API | `from_json` của bản cũ từ chối khoá gốc `labelOrientation`; rollback worker giữa `pipeline_build` và `pipeline_persist` làm job đang chạy hỏng ở persist. `schemaVersion` không đổi. Cùng tiền lệ `scaleBasis`/`scaleChecks` (review BENCH3D-03 #4), rủi ro thấp. | `apps/worker/pipeline_build/build.py:128`, `200-202` | Ghi một dòng rollback vào `changes/BENCH3D-14.md`; chấp nhận. |
| 6 | Nit | LOG | `labelOrientation` chỉ kiểm bộ khoá, không kiểm kiểu giá trị: `{"vertical": null, "horizontal": 0}` → `int(None)` ném `TypeError`, lọt qua `except ValueError` của `read_built` (`pipeline_persist/service.py:94`). Tệp nội bộ do chính worker ghi; cùng mẫu có sẵn ở `scaleChecks` (`float(v)`). | `apps/worker/pipeline_build/build.py:201-212` | Khi chạm lại: kiểm `isinstance(value, int) and value >= 0` trong `from_json`. |
| 7 | Nit | MNT | `_ORIENTATION_KEYS` khai báo cuối module nhưng dùng ở `BuiltLayer.from_json` phía trên (chạy được vì tra lúc gọi), khó đọc. | `apps/worker/pipeline_build/build.py:202`, `802` | Chuyển lên cạnh `_OPTIONAL_KEYS` (:128). |

Không có P0/P1/P2. Nợ tác giả nêu (ngưỡng `DRAWING_WALL_LENGTH_RATIO` chưa hiệu chỉnh trên SegFormer thật) có trong docstring `step.py` và `changes/BENCH3D-14.md`; giới hạn còn lại (e-aka-1, f-26 hai căn cạnh nhau chưa bắt) ghi ở `KET-QUA-r4.md` §6.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 4,5 | 0,45 |
| TEST | 7% | 4,5 | 0,315 |
| OBS/OPS | 5% | 4 | 0,20 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,78 / 5

## PHÁN QUYẾT: APPROVE

Ba sửa của làn L3 làm đúng các đề xuất S1/S3/S4/S5 của điều tra `no.md`, có điều kiện chặt và test cho từng nhánh: `MULTIPLE_PLANS` thêm chỉ báo không phụ thuộc tỉ lệ và đặt luật span theo dải sai số của nguồn tỉ lệ (không ca bench nào mất cảnh báo, e-aka-3 thêm critical); cổng `NOT_A_FLOOR_PLAN` giữ sàn 0,3 nên bộ hiệu chỉnh cũ không đổi, e-mpp-1 lên ĐẠT trên bench thật; hành lang chữ L đo bằng bề rộng thật; `ROTATED_PLAN` chỉ báo, mang qua khoá tuỳ chọn của `layer.json`. Không đổi API/DB/hợp đồng FE (mã mới không lên `readiness.checks`, và FE nhận chuỗi tự do). Gộp thử với các làn 12/13/15/16 sạch. CI GitHub Actions trên đúng SHA đầu nhánh xanh toàn bộ, độ phủ gói bị chạm và tổng ≥ 90/90. Không P0/P1/P2; năm P3 và hai Nit làm ở lượt sau (ưu tiên #1: test nhà phố dài cho chỉ báo không phụ thuộc tỉ lệ, và #2: log trang nhận qua dải để hiệu chỉnh).
