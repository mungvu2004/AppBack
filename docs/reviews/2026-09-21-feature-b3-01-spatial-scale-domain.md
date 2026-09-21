# Review merge feature/b3-01-spatial-scale-domain → main

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, không có ngữ cảnh của phiên đó; mọi khẳng định trong commit, `changes/B3-01.md` và báo cáo "lệch khỏi prompt" đều tự kiểm lại) · Commit đầu nhánh: `c0c70419cdd3` (gốc `3bbfe19`, 1 commit `c0c7041` B3-01). `main` đi thêm `f5f8d2a` (chỉ file phán quyết B0-07); `git merge-tree` sạch, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trong worktree sạch của nhánh; log `verify-b3-01.log` trong scratchpad của phiên): `1360 passed, 10 skipped` trong 247,6 s. Cả 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng, có từ B0-06, nhánh không chạm), đúng ngoại lệ BE-00 §12.
- Độ phủ (in từ `tools.coverage_gate`, không phải từ báo cáo tác giả):
  - tổng: dòng **99,31 %** · nhánh **96,93 %**
  - `packages/domain` (đơn vị bị chạm, gồm `spatial` và `scale`): dòng **100,00 %** · nhánh **100,00 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (210 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (184 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | không áp dụng — **hợp lệ**: nhánh không có `changes/B0-07.md` (B0-07 mới được duyệt, chưa hợp nhất) |
| 8 | openapi | đạt |

Bước 6 và 8 chạy thật và đạt (có `changes/B0-03.md`, `changes/B0-06.md` trên nhánh); prompt dự kiến "không áp dụng" là lỗi thời, tác giả làm đúng BE-00 §12.

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B3-01.md` tồn tại, 3–10 dòng | đạt (8 dòng) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — `feat(domain): add spatial model, integrity, area, diff and scale` (64 ký tự) |
| Trailer đọc được (R-36b) | đạt — `%(trailers:key=Prompt,valueonly)` → `B3-01`; `Prompt:` và `Co-Authored-By:` liền nhau, có dòng trống trước |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**`, `packages/core/**`, `packages/domain/{__init__.py,pyproject.toml}` | không — diff chỉ có `changes/B3-01.md`, `packages/domain/spatial/**`, `packages/domain/scale/**`, đúng cột `so_huu` |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — `noqa` mới duy nhất là `S603` có mã và lý do (`test_boundary.py:35`); hai `noqa: E402` nằm **trong chuỗi** mã của tiến trình con, không phải chú thích Python |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (Python 3.12, bản sao `/tmp/w`, không vào repo) và bằng Node 24 trên máy chỉ để tính số tham chiếu của FE:

- **G1 — đối chiếu số với FE (mục tiêu chính của prompt).** Chép nguyên văn (bỏ kiểu) `roundArea`/`doubleSignedAreaMm2`/`signedAreaMm2`/`computeArea`/`totalArea` (`area.ts:130-207`), `median`/`splitOutliers` (`outliers.ts:39-113`), `computeConfidence`/`inferScale`/`compareScaleToAiEstimate` (`scale.ts:90-237,348-360`) của AppFront @ `9cf0b0b`, sinh vector tất định bằng PRNG có hạt, rồi chạy **cùng** vector qua gói BE: 7 023 giá trị `Math.round` (gồm nửa, sát nửa, ±2^52±1, 2^53−1), 3 400 đường bao (so cả m² lẫn mm² có dấu), 300 tổng nhiều phòng, 1 500 bộ mẫu `inferScale` (mẫu 0 px/0 mm, mẫu lạc ×0,1/×3/×10, 0–14 mẫu), 2 007 phép so với AI, 3 000 phép `Math.round(v × new/old)` của đổi tỉ lệ → **0 lệch** ở cả sáu nhóm. Mười mẫu của `scale.test.ts`: FE ra `mm = 12.004999999999999`, `confidence = 0.982415`, `rejectedIds = [M-009, M-010]` — đúng con số BE chốt ở `test_infer.py:65`.
- **G2 — bộ mẫu A14.** Đối từng dòng `samples.py` với `sampleBuilding.ts:34-239`: id (`L-LEVEL<6>` không `0` cuối, các loại khác `<6>0`), toạ độ, cờ `APPROVED`/`DETECTED`, `openingIds` gắn theo thứ tự ô mở, `roomId = i % 4`, `referenceIds`, `grossFloorAreaM2 = 248.6`, phòng cuối `27.6` — khớp. Chỉ `createdAt` đổi sang `2026-08-13T02:00:00.000Z` như HOP-DONG-MOI §4.1 cho phép.
- **G3 — độ phức tạp của `check_integrity`** trên lớp do client gửi (một tường liệt kê M id ô mở không có, N ô mở trỏ về tường đó mà tường không liệt kê): 0,70 MiB → 0,34 s; 1,41 MiB → 1,22 s; 2,82 MiB → 6,23 s; **7,80 MiB (dưới trần 8 MiB của #35) → 41,84 s**, trong khi `SpatialLayer.model_validate_json` cùng thân chỉ 0,47 s. Bản dùng `set` cho cùng kết quả trong 0,015 s. Xem #1.
- **G4 — AST** trên 25 file `.py` của diff: không hàm nào > 50 dòng; một hàm thiếu docstring (`RescaleError.__init__`, xem #4; hai `@overload` của `change_entity_type` là stub, không tính). Dòng logic (bỏ trống, comment, docstring): **833** sản phẩm (≈ 190 là dữ liệu của `samples.py`) + **772** test.
- **G5 — biên mô hình ngoài ma trận [8]:** `confidence: true` → hỏng (`float_type`); `rotationDeg: 90`, `scaleMillimetresPerPixel: 12` (số nguyên JSON) → đạt; `order: true` → hỏng; toạ độ `1.0` → hỏng (`int_type`); `model_validate_json` khứ hồi đạt; `Note.body` có `\n` → hỏng (xem #6).
- **G6 — tuyên bố số học của tác giả:** `sum([1e16, 1.0, -1e16])` = `1.0` trên 3.12 (cộng bù), vòng lặp và `reduce` của FE = `0.0`; `math.floor(x + 0.5)` lệch `Math.round` ở `0.49999999999999994`, `±(2^52+1)`, `2^53−1` (vector G1). FE làm tròn tích chéo đơn lẻ > 2^53: đường bao 4000 × 4250 đặt ở toạ độ 10^9 mm ra `2A = 33 999 872` thay vì `34 000 000` (BE ra đúng số sau); dưới ~10^8 mm không có lệch nào trong G1.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | PERF-05 · R-25 | **`check_integrity` bậc hai theo dữ liệu client.** Luật "ô mở trỏ về tường mà tường không liệt kê" duyệt mọi ô mở trỏ về một tường và với mỗi ô mở quét tuyến tính `tuple` `wall.opening_ids` (`ref not in wall.opening_ids`) → O(N × M), cả N lẫn M do thân #35 quyết định. Đo (G3): một thân 7,80 MiB, hợp lệ mô hình, **dưới trần 8 MiB**, giữ CPU **41,8 s** (gấp ~90 lần giải mã cả thân). B3-03 gọi hàm này trên lớp người dùng gửi ở mỗi PUT #35 (prompt [1], [2]; HOP-DONG-MOI #35 `LAYER_INTEGRITY_BROKEN`), nên một tài khoản có quyền sửa gửi vài request là chiếm hết worker (chặn cả vòng sự kiện nếu B3-03 gọi đồng bộ trong route async). `RULE-CODE.md` R-25 cấm đúng mẫu này | `packages/domain/spatial/integrity.py:51` | Dựng `listed = set(wall.opening_ids)` một lần cho mỗi tường rồi kiểm `ref not in listed` — kết quả và thứ tự không đổi (vẫn duyệt theo `hosted`), đo 0,015 s trên cùng thân. Thêm một test chặn tái phát (vd lớp N = 2 000, M = 20 000 chạy dưới trần thời gian, gắn `perf` theo BE-00 §12, hoặc đếm phép so qua một `Sequence` giả có `__contains__` đếm lượt) |
| 2 | P2 | MNT-05 | Nhánh thêm ≈ 833 dòng logic sản phẩm (≈ 190 dòng là dữ liệu A14) và 772 dòng test, vượt 400. **Không đáng tách:** một prompt; `scale` nhập `spatial.area.js_round` và `spatial.model`, tách ra là đưa vào `main` một nửa hợp đồng [2] | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` chấp nhận như `NO-039` |
| 3 | P3 | LOG-02 · R-17 | `_factor` kiểm `old`, `new` hữu hạn và > 0 nhưng **không** kiểm `k = new / old`. Hai tỉ lệ hợp lệ mà tỉ số tràn (`old=1e-300, new=1e300` → `k = inf`) hay chìm về 0 thì lỗi nổ ra ở thực thể chưa duyệt **đầu tiên**: `RescaleError("W-WALL0000000")` với nguyên nhân `"không làm tròn được số không hữu hạn: nan"` (G5) — B3-03 sẽ báo sai thực thể cho một lỗi của **tham số**. Không mất dữ liệu (vẫn 422, lớp không đổi) | `packages/domain/scale/rescale.py:25-29` | Trong `_factor`: `k = new / old`; `if not (math.isfinite(k) and k > 0): raise ValueError(...)`; thêm hai ca vào `test_scales_must_be_positive_and_finite` |
| 4 | P3 | R-01 · MNT-04 | `RescaleError.__init__` không có docstring (R-01: mỗi hàm 1–12 dòng); lớp có docstring nhưng không nói `entity_id` là thuộc tính người gọi đọc để dựng mã lỗi | `packages/domain/scale/rescale.py:20` | Một câu: "`entity_id` là id thực thể hỏng, B3-03/B3-04 đọc để trả lỗi" |
| 5 | Nit | MNT-04 · TEST-02 | Hai docstring test nói sai điều chúng kiểm: `test_half_rounds_up` ghi "0,0125 m², **đúng nửa**" nhưng 0,0125 × 100 = 1,25, không phải nửa (tên test FE cũng nhầm y hệt); `test_js_round_matches_math_round` ghi "**hai ca cuối** là chỗ `floor(x + 0.5)` sai" nhưng ca cuối là `123.0` — ca công thức prompt sai thật là `0.49999999999999994` và `±(2^52+1)` | `packages/domain/spatial/tests/test_area.py:33`, `:133` | Sửa chữ: "1,25 → 1 (không phải nửa)"; "ba ca `0.49999999999999994`, `±(2^52+1)` là chỗ `floor(x + 0.5)` sai" |
| 6 | Nit | LOG-02 | `HumanText` cấm mọi ký tự `Cc`, nên `Note.body` có xuống dòng (`\n`) bị từ chối (G5), trong khi ghi chú là văn bản nhiều dòng tự nhiên. **Đúng chữ prompt** [6] và v1 `notes` luôn rỗng trên dây (HOP-DONG-MOI N15), nên hôm nay không ảnh hưởng | `packages/domain/spatial/model.py:62-69`, `:247` | Không sửa ở B3-01. Khi ghi chú có đường ghi: cho `body` một kiểu riêng nhận `\n`/`\t`, vẫn cấm ký tự đảo chiều |

**P0: 0 · P1: 1 · P2: 1 · P3: 2 · Nit: 2**

## Những chỗ đã soi kỹ và **đạt**

- **Cùng con số với FE (LOG, mục tiêu của prompt):** G1 — 0 lệch trên 17 230 vector qua sáu nhóm phép tính. Thứ tự phép tính khớp từng bước: `abs(signed) / 1_000_000 * 100` rồi `Math.round` rồi `/ 100` như `roundArea`; tổng dây giày cộng dồn, kiểm trần **sau mỗi bước**; `total_area_m2` cộng `abs` chưa làm tròn rồi làm tròn một lần; `spread / centre / limit`; `(lower + upper) / 2`; `reduce` tuần tự cho trung bình độ lệch. Đổi sang `Decimal` chỉ **sau** khi đã làm tròn bằng số nguyên (`Decimal(int) / 100`), nên không bao giờ `Decimal(float)`; không có `round()` dựng sẵn ở đâu; không bao giờ `-0.00` (test kiểm cả `is_signed()`).
- **`js_round`:** `floor` rồi so phần lẻ `x − floor(x) ≥ 0,5`. Phép trừ này **chính xác** trên mọi số thực hữu hạn (Sterbenz khi `|x| ≥ 1`; với `x ∈ (−1, 0)` chỉ có thể làm tròn lên phía ≥ 0,5, cho đúng `0` như `Math.round`), nên hàm bằng `Math.round` trên toàn miền hữu hạn — G1 xác nhận thêm bằng thực nghiệm.
- **Mô hình ↔ FE (K01, K02, W1–W4):** mỗi lớp có đúng các trường của `types.ts:95-255`, không thêm trường nào; `extra="forbid"`; xuất bằng `exclude_none=True` (không `exclude_unset`), test khứ hồi cả A14 và đếm 0 `null`. `areaM2`, `grossFloorAreaM2` là `float` → số JSON (có test chuỗi `"areaM2": 17.0`). `Mm` = `StrictInt` trong ±(2^53−1); `StrictFloat` nhận số nguyên JSON nhưng chặn `bool`; góc `[0, 360)`; tin cậy `[0, 1]` cấm NaN. Id W4 dùng lại `is_spatial_id` của B0-02 (không regex mới), đúng loại cho id và tham chiếu có loại, loại bất kỳ cho `referenceIds`, `Note.entityId`. `createdAt` kiểm bằng `parse_wire`, giữ nguyên chuỗi. A5 **không** nằm trong validator (để B3-03 trả `REVIEW_BY_AI_FORBIDDEN`).
- **Toàn vẹn:** năm luật đúng mức của `integrity.ts` (critical/warning), thứ tự luật cố định, trong luật theo `walls → openings → rooms → furniture`; `level_id` truyền vào thắng thực thể đầu tiên; lớp rỗng không lỗi; bốn lớp A14 sạch. Chỉ đọc, không sửa dữ liệu.
- **Diff (HOP-DONG-MOI §1.3):** tên trường snake_case đúng bảng và đúng `FIELD_DESCRIPTORS` của `semantic.ts`; đỉnh `V-<wallId>-start|end` với `x`, `y` ngay sau tường; tạo = một mục mỗi trường có giá trị (không có mục cho trường vắng); xoá = `__deleted__` + `MISSING` (hợp với `RemoteFieldChange.__post_init__` cấm `None`); `door ↔ window` = xoá dưới loại cũ + tạo dưới loại mới; so bằng `model_dump(mode="json")`; O(n) qua `dict`. `has_untracked_changes` bắt đúng ca chỉ đổi `reviewed` (và cả ca chỉ đổi thứ tự — đã ghi trong docstring).
- **Suy tỉ lệ (K19):** không bao giờ trả tỉ lệ mặc định; `mm_per_px` chỉ khi ≥ 3 mẫu **và** tin cậy ≥ 0,6; `code` = `PipelineCode.SCALE_UNRESOLVED` khi không suy được; `rejected_ids` = mẫu không dùng được (thứ tự đầu vào) rồi mẫu lạc. "Lệch 15 %" đúng chỗ (`compare_scale_to_ai_estimate`), có ca biên 15,00 % / 15,01 %.
- **Đổi tỉ lệ (K21):** chỉ `reviewed=False`; mục đã duyệt trả **đúng đối tượng cũ** (test so `==`); không chỗ nào đặt `reviewed=True`; chiều cao, cao bậu, góc, tin cậy giữ; `areaM2` của phòng chưa duyệt tính lại; mọi kết quả đi qua `model_validate` đầy đủ nên vi phạm (tường dài 0, bề dày 0, vượt 2^53) thành `RescaleError(entity_id)`, không kẹp.
- **Ranh giới (R-28, BE-00 §2.1):** `lint-imports` đạt; gói chỉ nhập `pydantic` và `packages.core`; test tiến trình con chặn `sqlalchemy`/`fastapi`/`celery`/`numpy`/`torch` rồi nhập cả hai gói và dựng A14 — đạt.
- **Ma trận case [8]:** đủ từng dòng (mô hình 23 ca biên đạt + 60 ca hỏng, A5, bảng `entityType` tách cửa đi/cửa sổ, mọi luật và mức toàn vẹn, mọi ca diện tích đối chiếu `area.test.ts`, mọi ca diff, các ca suy tỉ lệ chép `scale.test.ts:79-159`, năm ca thống kê, biên và AI, mọi ca đổi tỉ lệ, ranh giới nhập). Test không phụ thuộc đồng hồ, mạng hay thứ tự chạy.
- **SEC / CON / RES / OBS:** gói thuần — không I/O, không bí mật, không trạng thái dùng chung khả biến (`sample_building` nhớ một bản **bất biến**), không lời gọi ra ngoài. `subprocess.run` trong test dùng đối số cố định.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | `js_round` không dùng `math.floor(x + 0.5)` | **Đứng được.** G1: công thức prompt lệch `Math.round` ở 4/7 023 vector (`0.49999999999999994`, `±(2^52+1)`, `2^53−1`); bản của tác giả 0 lệch và chứng minh được là chính xác (xem mục "đạt") |
| 2 | `infer_scale` coi tỉ số tràn vô cực/về 0 là mẫu không dùng được | **Đứng được.** An toàn hơn và ít phạm vi hơn (BE-00 §13.2): FE để lọt thì ra tỉ lệ vô cực hay trung vị 0, vi phạm `Level.scaleMillimetresPerPixel` hữu hạn > 0 và K19. Chỉ khác FE khi độ dài ~10^±300; G1 (1 500 bộ mẫu thật) 0 lệch |
| 3 | `signed_area_mm2` nhân bằng `int` chính xác | **Đứng được.** Chính prompt [6] đòi "tổng chéo tính bằng `int`". G6: chỉ khác FE khi toạ độ cỡ ≥ 10^8–10^9 mm (100–1 000 km), BE ra số **đúng** còn FE ra số đã làm tròn; docstring ghi rõ |
| 4 | Cộng bằng vòng lặp thay `sum()` | **Đứng được.** G6: `sum()` 3.12 cộng bù Neumaier (`1.0`), `reduce` của FE và vòng lặp (`0.0`) |
| 5 | `ref_id` của `levelMembership` = tầng lạ; của `levelElevationOrder` = tầng ngay dưới | **Đứng được.** Prompt chỉ định `ref_id` cho `missingReference`; hai lựa chọn này là id "so với" hữu ích nhất cho B3-03, có test |
| 6 | `sample_layer(i)` ngoài 0..3 → `ValueError` | **Đứng được.** Fail-closed, đúng quy ước lỗi của gói ([2]) |
| 7 | Thêm tên công khai `SpatialLayer.entities()`, `BUILDING_ID`, `Reviewed`, `DELETED`, `SAMPLE_TOTAL_AREA_M2` | **Đứng được.** Không cái nào là trường dây (K01 không áp dụng); mỗi cái có nơi dùng thật (`entities()` ở toàn vẹn và diff, `BUILDING_ID` là id giả prompt [6] đặt, `DELETED` là hằng `__deleted__`); `SAMPLE_TOTAL_AREA_M2` chính prompt [6] khai. Không cái nào là abstraction thừa (R-10) |
| 8 | Bước 6, 8 chạy thật; commit viết lại theo §13.2; nhánh bỏ tiền tố người dùng | **Đứng được.** Tự chạy: bước 6 và 8 `đạt`; bước 7 `không áp dụng` hợp lệ; commit và tên nhánh đúng mẫu |
| 9 | Không có nợ mới | **Đứng được về khai báo** (không `TODO`/`ponytail:`, không giới hạn nào bị giấu), **nhưng** review này tìm ra #1 (P1, phải sửa) và #2–#4 cần sửa hoặc ghi sổ — xem dưới |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt — tác giả không nêu nợ nào; diff không chạm `DEBT.md` |
| Nợ P0/P1 còn `⬜`/`🔧` | không có trên sổ; #1 là P1 **mới** do review chỉ ra → phải **sửa** trước merge, không ghi nợ thay cho sửa (R-38) |
| Nợ do review này chỉ ra đã có dòng | **chưa** |

Dòng đề xuất (lấy id `NO-<nnn>` kế tiếp còn trống lúc ghi; phiên này **không** tự ghi vào `DEBT.md`):

- `| ➖ | NO-<nnn> | 2026-09-21 | 2026-09-21 | Nhánh feature/b3-01-spatial-scale-domain vượt trần 400 dòng logic của MNT-05 (≈ 833 dòng sản phẩm, ≈ 190 là dữ liệu A14; 772 dòng test) | Một prompt giao hai gói móc vào nhau: scale nhập spatial.area.js_round và spatial.model | B3-01 | P2 | Chấp nhận như NO-039: tách là đưa vào main một nửa hợp đồng [2]. Review merge 2026-09-21 finding #2 |`
- Nếu #3, #4 không sửa trong lượt sửa #1: `| ⬜ | NO-<nnn> | 2026-09-21 | | _factor không kiểm k = new/old; tỉ số tràn/chìm báo RescaleError cho thực thể chưa duyệt đầu tiên thay vì lỗi tham số | Chỉ kiểm hai tỉ lệ, không kiểm thương | B3-01 (packages/domain/scale/rescale.py:25) | P3 | mở — review merge 2026-09-21 finding #3 |` và `| ⬜ | NO-<nnn> | 2026-09-21 | | RescaleError.__init__ thiếu docstring (R-01) | — | B3-01 (packages/domain/scale/rescale.py:20) | P3 | mở — review merge 2026-09-21 finding #4 |`

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 #3; Nit #6) | 0,60 |
| PERF – Hiệu năng | 10 % | 1 (P1 #1) | 0,10 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #5) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #2; P3 #4) | 0,09 |

Tổng: 1,25 + 0,75 + 0,60 + 0,10 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,39 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Phần khó nhất của prompt làm rất tốt: cổng thoát 0 trên lượt chạy độc lập, độ phủ 100 % / 100 % cho cả hai gói, và mục tiêu "cùng con số với FE" được chứng minh chứ không chỉ khẳng định — 17 230 vector chạy song song qua chính mã FE và gói BE, 0 lệch; bộ mẫu A14 chép đúng; cả 9 điểm "lệch khỏi prompt" của tác giả đều đứng được. Điểm 4,39 đủ ngưỡng `APPROVE`, **nhưng** ma trận của `RULE.md` §5 là tuyệt đối: có P1 chưa waiver thì `REQUEST CHANGES`. #1 là lỗ DoS thật trên đường ghi #35 mà B3-03 sẽ nối vào: một thân hợp lệ 7,8 MiB giữ CPU 42 s. Sửa chỉ một dòng trong file của chính B3-01, nên không có lý do waiver.

**Phải làm để được duyệt:**

1. Sửa #1 ở `packages/domain/spatial/integrity.py:51` (dùng `set(wall.opening_ids)`), kèm test chặn tái phát đỏ trên mã hiện tại và xanh sau khi sửa; `bash tools/verify/run.sh verify` thoát 0.
2. Sửa luôn #3, #4 trong cùng lượt (mỗi cái 1–3 dòng), hoặc ghi hai dòng P3 đề xuất ở trên vào `DEBT.md`.
3. Ghi dòng `➖` cho #2 (MNT-05) vào `DEBT.md` trước khi merge (R-38).
4. Nit #5, #6 do tác giả tự quyết.
5. Xin `/merge-review` lại ở **phiên mới** (R-37). Khi được duyệt: gộp bằng **squash** (nhánh chỉ mang trailer của một prompt, `Prompt: B3-01`).
