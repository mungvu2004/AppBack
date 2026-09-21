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

---

## Lượt review lại (độc lập)

- Ngày: 2026-09-21 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả, không phải phiên review lượt đầu; mọi khẳng định trong commit `5498df8`, `DEBT.md` và lượt đầu đều tự kiểm lại) · Commit đầu nhánh: `5498df8e9fac` (gốc `3bbfe19`, 2 commit: `c0c7041` mã B3-01, `5498df8` sửa theo review). `main` nay ở `78da4ab`: sau `3fab67b` (NO-045) đã hợp nhất B0-07 (`fc01234..78da4ab`, có `changes/B0-07.md`). Nhánh chưa rebase; `git merge-tree --write-tree` với cả `3fab67b` lẫn `78da4ab` thoát 0, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ, log `verify-b3-01-r2b.log` trong scratchpad của phiên): `1363 passed, 10 skipped` trong 112,4 s; 10 skip là `apps/api/core/tests/test_common.py` (tập tham số rỗng, có từ B0-06), đúng ngoại lệ BE-00 §12. Lượt gọi **đầu tiên** (`verify-b3-01-r2.log`) thoát **1** ở bước 5 (`1 failed, 1362 passed`; bước 5b–8 `chưa chạy`): `tools/tests/test_services.py::test_postgres_16_lên_thật` `TimeoutError` ở `test_services.py:42` (`asyncpg.connect` không trần tường minh → mặc định 60 s của thư viện, qua `host.docker.internal:61006`). Đó là lớp `NO-007`, file của B0-01, nhánh không chạm, mọi test `packages/domain` đạt trong lượt đó; lượt chạy lại trên cùng mã thoát 0. Xem "Kiểm sổ nợ".
- Độ phủ (in từ `tools.coverage_gate`): tổng dòng **99,31 %** · nhánh **96,93 %** · `packages/domain` **100,00 %** / **100,00 %** · tập file bị chạm **100,00 %** / **100,00 %**.

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (210 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (184 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị `perf` bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 | không áp dụng — hợp lệ **cho cây của nhánh** (không có `changes/B0-07.md`, BE-00 §12). B0-07 nay đã ở `main`, nên sau rebase bước này phải chạy thật |
| 8 | openapi | đạt |

**Điều kiện dừng sớm** (tự kiểm lại): cây sạch; `changes/B3-01.md` có, 8 dòng; hai commit đúng mẫu, `5498df8` là `fix(domain): make integrity linear and reject overflowing scale ratios` (70 ký tự); `%(trailers:key=Prompt,valueonly)` → `B3-01` cho cả hai, `Co-Authored-By` cùng khối; diff `main...HEAD` vẫn chỉ gồm `changes/B3-01.md`, `packages/domain/spatial/**`, `packages/domain/scale/**`, và `5498df8` chỉ chạm 5 file trong đó; không `pragma`, `type: ignore`, `noqa` trần, `skip`, `xfail` mới (ba `noqa` của diff là ba cái lượt đầu đã xét). Không điều kiện nào kích hoạt.

**Công cụ kiểm tại chỗ** (container verify, Python 3.12; mã cũ lấy bằng `git show c0c7041:<file>` rồi chép đè **trong** bản sao `/tmp/w`, không chạm worktree):

- **R2-A — đỏ trước, xanh sau.** `integrity.py` của `c0c7041` + test của đầu nhánh: `test_hosted_openings_do_not_rescan_the_wall_list` **FAILED** `assert 201 <= 2` (`listed.scans` = 1 lượt lặp + 200 lượt `in`), 18 test còn lại đạt; trả `integrity.py` của đầu nhánh → 19/19 đạt. `rescale.py` của `c0c7041` + test của đầu nhánh: **2 FAILED** đúng hai ca mới `test_scales_must_be_positive_and_finite[1e-300-1e+300]` và `[1e+300-1e-300]`, 16 đạt; đầu nhánh 18/18.
- **R2-G3 — G3 của lượt đầu, cùng thân** (7,80 MiB; một tường liệt kê 250 000 id lạ, 20 000 ô mở trỏ về nó mà tường không liệt kê): `c0c7041` **49,36 s**; đầu nhánh **0,31 s** và **0,32 s** (hai lượt), trong khi `model_validate_json` cùng thân mất 0,41 s. Cả hai bản cùng ra 270 000 lỗi.
- **R2-G7 — tường trùng id** (xem N1): W tường cùng id `W-WALL0000000`, `openingIds` rỗng, N ô mở trỏ về id đó; JSON gọn 227 byte/tường, 187 byte/ô mở. Đầu nhánh: W = N = 1 000 (0,40 MiB) → 0,97 s, 1 000 001 lỗi, RSS 115 MiB; 2 000 (0,79 MiB) → 3,92 s, 4 000 001 lỗi, 367 MiB; 3 000 (1,19 MiB) → **8,62 s, 9 000 001 lỗi, 786 MiB**; 8 000 (3,16 MiB) dưới `ulimit -v` 4 GiB → **`MemoryError` sau 56,8 s**. Cùng mã nhưng đổi `hosted.get` thành `hosted.pop`: 3 000 × 3 000 → 0,00 s, 3 001 lỗi, 54 MiB, và 19/19 test của `test_integrity.py` vẫn đạt.
- **R2-R — số học.** Chín ca của `test_js_round_matches_math_round`: `floor(x + 0.5)` lệch `js_round` đúng ba ca `0.49999999999999994`, `±(2^52+1)`, khớp docstring mới. `_factor`: `(1e-300, 1e300)`, `(1e300, 1e-300)`, `(5e-324, 1.0)` → `ValueError` "tỉ số tỉ lệ …"; `(1.0, 1e300)` → `k = 1e300`; `(1.0, 5e-324)` → `k = 5e-324` (hữu hạn, > 0, đi tiếp và làm thực thể về 0 → `RescaleError` của thực thể, cùng lớp với `test_one_millimetre_wall_collapsing_names_the_wall`: hợp lệ, không phải finding).
- **AST** trên 24 file `.py` của diff: 0 hàm/lớp thiếu docstring (không tính hai stub `@overload`), không hàm nào > 50 dòng.

### Trạng thái finding của lượt đầu

| # cũ | Mức | Trạng thái | Bằng chứng tự kiểm |
|---|---|---|---|
| 1 | P1 | **đã sửa đúng chỗ lượt đầu chỉ; gốc chưa hết** | `integrity.py:52-53` dựng `listed = set(wall.opening_ids)` một lần cho mỗi tường; kết quả và thứ tự không đổi (vẫn duyệt theo `hosted`). Test chặn tái phát `test_integrity.py:135-160` đếm lượt quét qua một lớp con `tuple` (không đo giờ, tất định): R2-A đỏ trên `c0c7041`, xanh trên đầu nhánh; R2-G3 từ 49,36 s xuống 0,31 s. **Nhưng** cùng luật vẫn bậc hai theo thân client qua đường tường trùng id: N1 dưới. Tiêu đề commit "make integrity linear" vì thế chưa đúng |
| 2 | P2 | chấp nhận | `NO-045` ➖ trên `main` (`3fab67b`, `DEBT.md:67`): đủ chín cột, cùng khuôn `NO-039`, lý do đứng được (tách là đưa vào `main` một nửa hợp đồng [2]; `scale` nhập `spatial`), trỏ file phán quyết. Vẫn tính điểm MNT |
| 3 | P3 | **đã sửa** | `rescale.py:34-37` kiểm `k = new / old` hữu hạn và > 0 → `ValueError` thuần. `test_rescale.py:80-92` thêm hai ca tràn/chìm, khẳng định **không** phải `RescaleError`, cho cả `rescale_unreviewed` lẫn `rescale_dimensions`: R2-A đỏ → xanh; hai nhánh của `if` mới đều phủ (gói 100 % nhánh). Ca cũ `test_overflowing_factor_is_refused` (nay là lỗi tham số) được thay bằng `test_length_beyond_safe_integer_names_the_entity` (`:73`, `k = 1e300` hữu hạn), nên đường "thực thể vượt 2^53 → `RescaleError` đúng id" vẫn có test. `RescaleError` là lớp con của `ValueError`, nên người gọi bắt `ValueError` không đổi hành vi |
| 4 | P3 | **đã sửa** | `rescale.py:21` có docstring, nêu `entity_id` là thứ B3-03, B3-04 đọc; AST không còn hàm thiếu |
| 5 | Nit | **đã sửa** | `test_area.py:33` "x 100 = 1,25 (không phải nửa) → 0,01" đúng; `:133` nêu đúng ba ca (R2-R). Tên hàm `test_half_rounds_up` vẫn nói điều ngược lại: N2 |
| 6 | Nit | giữ nguyên | Không đổi, đúng chữ prompt [6]; tác giả tự quyết như lượt đầu cho phép |

`5498df8` không chạm `area.py`, `infer.py`, `outliers.py`, `model.py`, `samples.py`, `diff.py`, `kinds.py`. Thay đổi ở `_factor` chỉ từ chối `k` không hữu hạn hoặc bằng 0, nơi FE cũng không cho được con số hợp lệ. Vì vậy G1 (17 230 vector, 0 lệch) và G2 (A14) của lượt đầu vẫn đứng, không cần chạy lại.

### Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | **P1** | PERF-05 · R-25 · R-19 | **`check_integrity` vẫn bậc hai theo thân client, qua tường trùng id.** `hosted` gom ô mở theo `wall_id` (`:43-45`); vòng tường (`:48-53`) lấy `hosted.get(wall.id, ())` cho **mỗi** tường, nên W tường cùng một id đọc lại cùng một danh sách N ô mở và sinh **W × N** cảnh báo. Mô hình không cấm id trùng (đó chính là việc của luật `duplicateId`; `SpatialLayer` không có validator), và `diff.py:7` ghi rõ B3-03 kiểm toàn vẹn **trước** khi diff, nên thân #35 nào cũng đi tới đây. R2-G7: 1,19 MiB → 8,6 s và 786 MiB; 3,16 MiB → `MemoryError` ở trần 4 GiB sau 56,8 s. Với trần 8 MiB của #35 (`HOP-DONG-MOI.md:382`), chia đều thành ≈ 18 477 tường và ≈ 22 429 ô mở thì ra ≈ 4,1 × 10^8 cảnh báo; ngoại suy từ ≈ 85 byte/lỗi đo được là **≈ 35 GB**. Một request của tài khoản có quyền sửa là đủ làm tiến trình API bị OOM-kill, nặng hơn #1 cũ (CPU 42 s). Lỗi có từ `c0c7041`, lượt đầu bỏ sót. Bản sửa #1 chỉ vá phép quét `tuple` mà lượt đầu nêu, chưa chạm gốc "việc của mỗi tường tỉ lệ với số ô mở của id đó" (R-19). Xếp P1 như #1 cũ và như mức mặc định của PERF-05; chưa lên P0 chỉ vì chưa route nào gọi hàm này | `packages/domain/spatial/integrity.py:53` (cùng `:43-45`) | Sửa một từ: `hosted.pop(wall.id, ())` thay cho `hosted.get(...)`. Tường đầu tiên mang id nhận phần kiểm; các bản trùng (đã bị `duplicateId` critical) không lặp lại. Với lớp không trùng id, kết quả và thứ tự y nguyên. R2-G7 đã thử: 3 000 × 3 000 → 3 001 lỗi, 0,00 s, 19/19 test cũ đạt. Test chặn tái phát: ba tường cùng id không liệt kê gì, hai ô mở trỏ về id đó → đúng 2 cảnh báo `warning` (mã hiện tại ra 6) |
| N2 | Nit | MNT-04 · TEST-02 | Tên `test_half_rounds_up` nói "nửa làm tròn lên", trong khi docstring vừa sửa nói đúng là 1,25 "không phải nửa" và kết quả làm tròn **xuống** (0,01). Tên này chép lại tên sai của FE (`area.test.ts:199` "rounds a half away from zero") | `packages/domain/spatial/tests/test_area.py:32` | Đổi tên, vd `test_sliver_quarter_rounds_down`; giữ trỏ `area.test.ts:199-201` trong docstring |

Đã kiểm và **không** thấy finding thêm: các luật khác của `check_integrity` đều tuyến tính kể cả khi id trùng (`Counter` cho `duplicateId`; `wall.opening_ids`, `room.wall_ids` là danh sách của chính thực thể nên tổng bị chặn bởi thân; tra cứu qua `set`); `diff_layers` O(n) qua `dict` (id trùng thì bản sau thắng, không nhân lên); `rescale_*` tuyến tính. `ScanCounter` (`test_integrity.py:135`) sống sót qua `model_copy` (không kiểm lại mô hình) và đếm cả `set(...)` lẫn `in`; R2-A cho thấy nó bắt đúng mã cũ. Ngưỡng `≤ 2` là hằng, không phụ thuộc giờ máy hay thứ tự chạy.

### Kiểm sổ nợ

- `NO-045` ➖ (P2, B3-01) có trên `main`, đúng định dạng: điều kiện #3 của lượt đầu đạt.
- Không có nợ P0/P1 nào còn `⬜`/`🔧` trên sổ. N1 là P1 **mới** do review chỉ ra → phải **sửa** trước merge, không ghi nợ thay cho sửa (R-38). N2 là Nit, không bắt buộc ghi sổ.
- Ngoài nhánh: lượt cổng đầu đỏ giả ở `tools/tests/test_services.py:42` (`test_postgres_16_lên_thật`, `asyncpg.connect` không có `timeout=` → mặc định 60 s qua `host.docker.internal`). `NO-042`/FIX-007 chỉ nêu `:32-33` (`_select_one`, trần 5 s); gốc chung là `NO-007` (FIX-009). Đề xuất người điều phối nối vào ghi chú `NO-042`: "cả `:42` `test_postgres_16_lên_thật` dùng trần mặc định 60 s của asyncpg (R-24); đỏ giả 2026-09-21 khi verify `5498df8`", và đưa `:42` vào phạm vi FIX-007. Không chặn B3-01 (K27: file của B0-01).

### Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (#3 đã sửa; Nit #6 giữ) | 0,75 |
| PERF – Hiệu năng | 10 % | 1 (P1 N1) | 0,10 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit N2) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 MNT-05 chấp nhận ở `NO-045`) | 0,09 |

Tổng: 1,25 + 0,75 + 0,75 + 0,10 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,54 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Lượt sửa làm đúng và đủ những gì lượt đầu yêu cầu, và mỗi mục đã được tự kiểm bằng chạy thật: #1 dùng `set`, test chặn tái phát đỏ trên `c0c7041` (`201 <= 2`) và xanh trên đầu nhánh, G3 7,80 MiB từ 49,4 s xuống 0,31 s; #3 và #4 sửa kèm test đỏ → xanh; Nit #5 đúng chữ; `NO-045` có trên `main`. Cổng thoát 0 ở lượt chạy lại (lượt đầu đỏ giả do `NO-007`, ngoài nhánh), độ phủ `packages/domain` 100 % / 100 %. Điểm 4,54 đủ ngưỡng `APPROVE`, **nhưng** review này tìm ra N1: cùng luật "ô mở trỏ về tường mà tường không liệt kê" vẫn sinh W × N lỗi khi tường trùng id, và một thân 3,16 MiB (dưới trần 8 MiB của #35) đã làm cạn 4 GiB. Đó là P1 chưa waiver → `REQUEST CHANGES` theo ma trận `RULE.md` §5. Sửa chỉ một từ trong file của chính B3-01, nên không có lý do waiver.

**Phải làm để được duyệt:**

1. Sửa N1 ở `packages/domain/spatial/integrity.py:53` (`hosted.pop(wall.id, ())`, hoặc cách khác sao cho mỗi ô mở chỉ được xét một lần dù có bao nhiêu tường trùng id), kèm test chặn tái phát đỏ trên `5498df8` và xanh sau khi sửa (vd ba tường cùng id + hai ô mở → đúng 2 cảnh báo).
2. Rebase nhánh lên `main` hiện tại (`78da4ab`, đã có B0-07) để bước 7 chạy thật thay vì "không áp dụng"; `bash tools/verify/run.sh verify` thoát 0.
3. N2 do tác giả tự quyết (nên đổi tên test trong cùng lượt).
4. Xin `/merge-review` lại ở **phiên mới** (R-37). Khi được duyệt: gộp bằng **squash** (nhánh chỉ mang trailer `Prompt: B3-01`).
5. Không chặn B3-01: người điều phối bổ sung `:42` vào `NO-042`/FIX-007 như mục "Kiểm sổ nợ".
