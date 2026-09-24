# Review merge `feature/b2-03-floors` → main — **lượt 2** (vòng sửa 1)

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `aeb2292e456b`
- Lượt 1: `docs/reviews/2026-09-24-feature-b2-03-floors.md` — APPROVE 4,42/5, 8 finding (2 P2 · 4 P3 · 2 Nit)
- Phạm vi lượt này: **chỉ diff vòng sửa** `git diff 0ec2393..aeb2292` — 15 file, 178 dòng thêm / 22 xoá, hai
  commit: `2d42377` (FIX-082 vòng 2, `Prompt: B2-01` + `Fix: FIX-082`) và `aeb2292` (`Prompt: B2-03`).
  Miền lượt 1 đã cho 5/5 mà diff không chạm (SEC, CON, RES, OBS) **không** chấm lại.
- Worktree review: `b2-03-review` `git checkout --detach aeb2292`, cây sạch (`git status --porcelain` rỗng),
  không sửa một dòng mã nào của nhánh.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát thật 0**, chạy lại một lần tại chỗ trong worktree review
  (log `.cache/src-out/verify/20260924T031138Z-aeb2292e456b.log`)
- Độ phủ: tổng dòng **99,12%** · nhánh **97,65%**; `apps/api/floors` dòng **99,60%** · nhánh **100,00%**
- File cấm: diff **không** chạm `docs/charter/*`, `docs/contracts.toml`, `uv.lock`, `openapi.json`,
  `APPFRONT_SHA`, `pyproject.toml` gốc, `.importlinter`, `conftest.py` gốc, `tools/verify/*`, `DEBT.md`
- Không dòng nào thêm `# pragma: no cover`, `pragma: no branch`, `type: ignore`, `noqa` trần, `skip`/`xfail`,
  không hạ ngưỡng nào (grep toàn diff vòng sửa)

## 1. Bảng cổng (E.10, mã thoát thật của phiên review lượt 2)

| # | Bước | Trạng thái | Ghi chú |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | 588 file |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | 472 file nguồn |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | **3649 passed · 0 failed · 0 skipped · 4 deselected** (653,78 s) |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; `case_gate` 21 thao tác, 0 "HỎNG" |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, **đúng 1 head**; up/down/up, **model khớp DB**, tên CHECK khớp |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H1 628 mẫu; H4 `không áp dụng` (B3-05 chưa hợp nhất — đúng BE-00 §12) |
| 8 | `openapi` | đạt | `/tmp/openapi.json` **50703 byte** (lượt 1: 49219 — `requestBody` #13 đã có mặt) |

Độ phủ từng gói bị chạm (`tools.coverage_gate` thật, đều ≥ 90/90): `apps/api/floors` 99,60% / 100,00% ·
`apps/api/projects` 98,42% / 96,43% · `packages/db` 95,35% / 95,45% · `packages/testing` 99,18% / 97,37% ·
tập file bị chạm 99,62% / 100,00%.

**Con số tác giả khớp lần chạy độc lập này**, trừ một sai lệch vô hại: tổng nhánh 97,65% (tác giả ghi 97,62%).
3649 passed, `apps/api/floors` 99,60% / 100,00%, openapi 50703 byte — khớp từng số.

## 2. Tám finding lượt 1 → đã đóng thật chưa

| # | Mức · ID lượt 1 | Trạng thái | Bằng chứng tự kiểm (không tin báo cáo) |
|---|---|---|---|
| 1 | P2 API-04 · R-11 | **đóng** | `router.py:52-63` nhận `body: FloorReorderIn` thật và dùng `body.floor_ids` (bỏ `await request.json()`); `test_schemas.py:215` đọc `real_app().openapi()` rồi assert `paths["/api/floors/reorder"]["patch"]["requestBody"]` trỏ `$ref` `FloorReorderIn` có `floorIds` — test **chặn** (đỏ trên `0ec2393`). Bước 8 độc lập: 49219 → 50703 byte. Lớp không còn dead code |
| 2 | P2 MNT-03 · R-34 | **đóng** | `DEBT.md` trên `main` (`35c3020`) dòng 188 `NO-168` và 189 `NO-169` **đều đã có** đoạn của B2-03 (2026-09-24, trích chính review lượt 1); `lookup.py:113-115` và `schemas.py:27-31` trỏ đúng hai mã đó thay vì "ghi nợ" trần. Nhánh **không** sửa `DEBT.md` — đúng quyền sở hữu |
| 3 | P3 PERF-03 | **đóng** | Index thứ 4 `ix_floors_project_id_level_id` (đầy đủ, không `WHERE`) có ở **cả hai** nơi: `packages/db/models/floors.py:60` và `r20260923_b2_03_floors.py:77`; `migrate_check` "model khớp DB" đạt. `downgrade` là `op.drop_table(FLOORS)` nên index đi theo (docstring nói rõ). Đúng câu cần phục vụ: `jobs.py:56-65` `_sibling_flag` và `:103-108` `_has_sibling` đều lọc `(project_id, level_id)` **không** lọc `deleted_at`. `test_models.py:134` kiểm `pg_indexes` + `EXPLAIN` — test chặn (đỏ khi chưa có index) |
| 4 | P3 LOG-02 | **đóng** | `service.py:54-62` `_restorable` lấy `max(deleted_at)` thay vì `next()`; `_locked_rows` thêm `ORDER BY FloorRow.pk` nên **thứ tự khoá vẫn theo `pk`** (BE-00 §7), không đổi sang `deleted_at`. `test_service.py:47` chèn thẳng **hai dòng xoá mềm cùng `(project_id, level_id)`** (dòng cũ hơn ở `pk` nhỏ hơn) rồi assert `restored.pk == newer.pk` — đỏ trên mã cũ vì `next()` theo `ORDER BY pk` trả dòng cũ. Đây đúng là test lượt 1 nói "chưa dựng được" |
| 5 | P3 MNT-04 | **đóng một phần** → finding mới #9 | `changes/B2-03.md:6-8` và `_bodies.py:3-7` đã viết lại đúng, nhưng **5 file test khác vẫn giữ nguyên câu sai** (xem #9) |
| 6 | P3 TEST-02 · R-01 | **đóng** | Tự soát độc lập bằng bộ dò `def` → docstring trên **toàn** `apps/api/floors/**`: `0ec2393` thiếu **đúng 7** hàm (khớp danh sách lượt 1), `aeb2292` thiếu **0**. Bảy docstring thêm vào đều nói thực chất, không phải câu bù |
| 7 | Nit TEST-02 (FIX-082) | **đóng** | `test_parts.py:86-99` **chỉ thêm** assert, không nới, không xoá: `_app_with(ViewPart(PROJECT_FLOORS, _load))` tường minh + `resolve(None) != resolve(overridden)` + `view_part(PROJECT_FLOORS) is not None` và `.kind == PROJECT_FLOORS`. Nhánh "không ai cài" vẫn được kiểm riêng ở `test_routes_write.py`. Commit **riêng** `2d42377`, trailer đủ `Prompt: B2-01` + `Fix: FIX-082` |
| 8 | Nit TEST-02 (C14) | **đóng** | `test_routes_create.py:146-147` assert `(code, field) == ("FLOOR_ID_TAKEN", "id")` cho đúng bên 409 |

**7/8 đóng hẳn, 1 đóng một phần.** Không finding nào được "đóng bằng lời": mỗi cái có mã đổi thật, và 5/8 có
test chặn mới hoặc chặt hơn. Không finding lượt 1 nào bị nới, không assert nào bị xoá trong toàn diff.

## 3. Soát riêng theo yêu cầu

**#13 nhận `body: FloorReorderIn` — lỗi resolver có còn thắng?** Đạt ở mọi case hợp đồng, kiểm cả cơ chế lẫn
test. FastAPI ràng buộc `body` **sau** khi `solve_dependencies` chạy các sub-dependency, nên `ListAccess` →
`require_project(resolver=project_of_floor_list)` → `_read_floor_ids` vẫn raise trước. Test chạy thật và xanh:
`__non_json_content_type_is_validation` (`Content-Type: text/plain`, thân `x` → 422 `field:"floorIds"`),
`__empty_array_is_validation`, `__duplicate_id_is_validation`, `__top_level_array_body_is_validation`, `__C02`
(`floorIds` sai kiểu), `__C03` (khoá lạ) → đều 422 `VALIDATION` `field:"floorIds"`; `__unknown_id_is_mismatch`,
`__missing_floor_is_mismatch`, `__mixed_projects_is_mismatch` → `FLOOR_REORDER_MISMATCH`; `__C06` (admin hệ
thống ngoài dự án) → 404 `resource:"floor"`. Không case nào đổi mã lỗi. Một ngoại lệ nằm ngoài hợp đồng: thân
JSON **hỏng** với `Content-Type: application/json` — xem finding #10.

**Một nguồn luật hình dạng?** Đạt. Luật thật (object, khoá lạ, `1..FLOORS_MAX`, phần tử là chuỗi, không trùng)
chỉ sống ở `resolvers._parsed_floor_ids:63-81`. `FloorReorderIn` khai **đúng một dòng** `floor_ids: list[str]`,
không validator, không `Field(...)` biên — không chép luật nào (R-07). `body.floor_ids` và `floor_ids` của
resolver đọc cùng thân đã cache của Starlette nên không thể lệch nhau.

**Case loại G\*:** đạt, và là hệ quả tốt ngoài dự kiến. Vì `has_body` giờ là `True` (`openapi.py:136` đọc
`route.dependant.body_params`), `case_gate` **tự** đòi thêm C02 + C03 (`case_gate.py:172-175`). Log lượt này:
`floors_reorder_floors | bắt buộc [… 'C02','C03' …] | tìm thấy [… 'C02','C03' …] | đạt` — phân loại và thực tế
không còn lệch. `C21` không bị đòi thêm vì `/floors/reorder` không có tham số đường (`body_mirrors_path` =
False). `C16` vẫn miễn đúng `cases.toml`.

**Index thứ 4 — chấp nhận, không phải finding.** [5] của prompt chốt đúng 3 index một phần; thêm index đầy đủ
là **lệch khỏi prompt có lý do đứng được** và tác giả đã ghi mục "Lệch khỏi prompt (vòng sửa 1)" đúng R-21:
ba index kia đều `postgresql_where` nên planner không dùng được cho câu không lọc `deleted_at` của lịch dọn.
Không xoá index nào đã chốt, chỉ thêm. Model ↔ revision khớp, `migrate_check` xác nhận. Sửa **tại chỗ** trong
revision là đúng BE-00 §6.1: `r20260923_b2_03_floors.py` chưa có trên `main` (`git cat-file -e main:…` báo
không tồn tại), nên không phải chuyện expand/contract.

**`_restorable` + thứ tự khoá:** đạt (xem #4). Thứ tự khoá vẫn `pk` ở cả `_locked_rows` và `_active_rows_locked`,
nên hai đường vẫn khoá cùng chiều sau cùng một khoá tư vấn — không sinh deadlock mới. Chọn dòng mới nhất làm
trong Python; `deleted_at` bằng nhau → dòng `pk` nhỏ hơn, tất định. Cách viết 4 dòng thay vì `max(...,
default=None)` một dòng là bắt buộc để `mypy --strict` thu hẹp được `datetime | None` — không phải rườm rà.

**FIX-082 vòng 2:** đạt (xem #7). Chỉ thêm assert, commit riêng, hai trailer đủ, phạm vi vẫn trong
`apps/api/projects/tests/` mà `docs/fixes.md` FIX-082 uỷ quyền.

**Comment `NO-168`/`NO-169`:** đạt (xem #2), hai mã đều tồn tại thật trên `main`.

**Docstring mọi hàm:** đạt (xem #6), 0 thiếu trên toàn `apps/api/floors/**`.

## 4. Finding lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 9 | P3 | MNT-04 · R-19 | Finding #5 lượt 1 chỉ được vá **đúng hai chỗ review nêu tên** (`changes/B2-03.md`, `_bodies.py`); **5 file cùng một lỗi** vẫn viết route "chưa hợp nhất trên nhánh này" — vá triệu chứng chứ chưa sửa gốc (R-19): lượt 1 nêu 2 vị trí làm ví dụ, gốc là "docstring test viết theo thời viết mù, chưa cập nhật sau khi gộp". Không ảnh hưởng cổng (`tools/charter.py:merged_prompts` chỉ đọc tên file), nhưng người đọc tiếp theo vẫn bị dẫn sai | `test_routes_create.py:3-5`, `test_routes_delete.py:3`, `test_routes_list.py:3`, `test_routes_patch.py:3`, `test_routes_reorder.py:3` | Viết lại cả 5 câu như đã làm với `_bodies.py` (một dòng mỗi file), hoặc bỏ câu đó và để `_bodies.py` giữ phần bối cảnh |
| 10 | P3 | MNT-03 | Docstring `FloorReorderIn` khẳng định "resolver đọc thân thô **trước** khi FastAPI ràng buộc `body` này, nên **lỗi resolver luôn thắng**". Chữ "luôn" sai: FastAPI **giải JSON** trước mọi dependency (chính repo ghi vậy ở `apps/api/core/routing.py:100-105` và `:111`), chỉ việc *ràng buộc* Pydantic mới chạy sau. Nên với `Content-Type: application/json` + thân JSON hỏng, `aeb2292` trả **400 `MALFORMED_JSON`** (`errors.py:126-128`, lỗi `json_invalid`) chứ không phải 422 `field:"floorIds"` như `0ec2393`. Hành vi mới là hành vi **chuẩn hiến chương** W8 (`core/tests/test_routing.py:160` kiểm tập trung cho mọi route có thân) và BE-BIND dòng 13 không đòi mã nào cho JSON hỏng → **không phải lỗi hợp đồng**; nhưng câu docstring thì sai, và đây là thay đổi hành vi không được ghi ở "Lệch khỏi prompt" | `apps/api/floors/schemas.py:122-124` | Sửa câu: "lỗi resolver thắng với mọi thân **giải được**; thân JSON hỏng thì FastAPI trả 400 `MALFORMED_JSON` trước dependency, đúng W8". Không cần test riêng — `test_routing.py` đã phủ luật chung, thêm ở đây là chép (R-07) |

Không finding **P0**, **P1** hay **P2** nào. Không finding mới nào do vòng sửa **gây ra**: #9 là phần còn lại
của một finding cũ, #10 là một câu docstring (hành vi kèm theo đúng hiến chương). Không phát hiện hồi quy: 3649
test xanh, 0 hỏng, không mã lỗi nào đổi ngoài đường JSON hỏng đã phân tích ở #10.

## 5. Điểm

Thang RULE.md §5 mỗi miền: 5 không finding · 4 chỉ P3 · 3 có P2 · 1 có P1 · 0 có P0.

| Miền | Trọng số | Điểm | Tích | Căn cứ |
|---|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 | diff không chạm; `__C06` 404-trước-403 và "không lộ tồn tại" vẫn xanh sau khi thêm `body` |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 | `_locked_rows` thêm `ORDER BY pk` → thứ tự khoá BE-00 §7 **chặt hơn** lượt 1; `__concurrent_with_delete_does_not_500`, `__C14` vẫn xanh |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 | #4 đóng, có test hai dòng xoá mềm chặn |
| PERF – Hiệu năng | 10% | 5 | 0,50 | #3 đóng, index ở cả model và revision, test `pg_indexes` + `EXPLAIN` |
| RES – Chịu lỗi | 10% | 5 | 0,50 | diff không chạm lịch dọn / `except AppError` |
| DB, API – Migration & contract | 10% | 5 | 0,50 | #1 đóng: `requestBody` #13 có trong `openapi.json` (50703 byte), test chặn; revision sửa tại chỗ đúng luật, 1 head, model khớp DB |
| TEST – Kiểm thử | 7% | 5 | 0,35 | #6 đóng (0 hàm thiếu docstring, tự dò lại); #7 #8 chặt hơn; 3 test mới đều chặn thật |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 | diff không chạm log / nhật ký |
| MNT – Bảo trì | 3% | 4 | 0,12 | #2 đóng, nhưng còn hai P3: #9 (5 file docstring sai trạng thái) và #10 (câu docstring sai về thứ tự FastAPI) |
| **Tổng** | **100%** | | **4,97 / 5** | |

Lượt 1 4,42 → lượt 2 **4,97**: sáu miền lên 5/5 nhờ #1 #3 #4 #6 đóng hẳn; MNT còn 4 vì #5 chỉ đóng một phần.

## PHÁN QUYẾT: APPROVE

Không P0, không P1, không P2; điểm **4,97 ≥ 4,9** — đạt mức người dùng đặt để được gộp. Cổng đầy đủ 8/8 với mã
thoát thật **0** chạy lại độc lập trên chính sha `aeb2292`, 3649 test xanh 0 hỏng, độ phủ mọi gói bị chạm và
tổng đều vượt xa sàn 90/90. Bảy trong tám finding lượt 1 đóng hẳn, mỗi cái bằng mã đổi thật chứ không bằng lời,
và năm cái có test chặn mới hoặc chặt hơn — kể cả test lượt 1 nói "chưa dựng được" (hai dòng xoá mềm cùng id).
Vòng sửa còn làm chặt thêm hai thứ review lượt 1 không đòi: `ORDER BY pk` cho `_locked_rows` đưa thứ tự khoá về
đúng BE-00 §7 tường minh, và `body: FloorReorderIn` khiến `case_gate` tự xếp #13 vào loại G\* nên C02/C03 thành
**bắt buộc** thay vì chỉ tình cờ có. Không một hồi quy nào: không assert bị nới, không `pragma`/`skip`/
`type: ignore` mới, không file cấm bị chạm, không `DEBT.md` bị sửa từ nhánh.

Hai P3 còn lại đều là câu chữ trong docstring, không chạm hành vi và không chặn merge.

**Điều kiện kèm theo (không chặn merge):**

1. Vào `main` bằng `git merge --no-ff` để giữ trailer của **cả hai** prompt (`Prompt: B2-03` ở `aeb2292` và
   `Prompt: B2-01` + `Fix: FIX-082` ở `2d42377`), đúng `docs/fixes.md` mục FIX-082 — như lượt 1 đã chốt.
2. Ghi `DEBT.md` hai dòng `NO-<nnn>` cho finding #9 và #10 (chủ B2-03), hoặc giao một FIX sửa cả 5+1 câu
   docstring — cả hai đều P3, R-35 không chặn.
3. Sau merge, xuất `openapi.json` ra gốc repo trước khi chạy bước 8 của `main`.
