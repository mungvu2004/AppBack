# Review merge `feature/b3-02-spatial-read` → main

- Ngày: 2026-09-26 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `d95e79c370ca`
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ, worktree review ở đúng sha `d95e79c`,
  một lượt, 8/8 bước đạt; log `b3-02-review-verify.log`, dòng `EXIT=0`)
- Test: **4588 passed, 0 failed**, 4 deselected (1049,71 s)
- Độ phủ: tổng dòng **99,50 %** · nhánh **98,40 %** · `apps/api/spatial_read` dòng **100,00 %** · nhánh **100,00 %**
  · `packages/db` 96,33 % / 95,69 % · `packages/testing` 99,48 % / 98,57 % · tập file bị chạm 100,00 % / 100,00 %

## Trạng thái cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | ranh giới `db-isolated`, `api-jobs-no-web` giữ |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4588 passed / 0 failed |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; **thiếu = 0** |
| 6 | `lint_migrations` → `migrate_check` | đạt | 11 revision, **đúng 1 head**, seed ci hai lần, downgrade -1/base, model khớp DB, tên CHECK khớp model |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | bảng con dưới |
| 8 | `openapi` | đạt | |

Bảng con bước 7: Smoke đạt (23 module schema, 83 mục) · Bản đồ đủ đạt (83/83) · Thao tác đã mount đạt (49/83)
· **H1 đạt — 1122 mẫu response** · **H1 ngữ cảnh đạt — 50 mẫu** (gồm `n15`, `n16`) · H3 đạt (10 khoá, 3 vai)
· H4 **không áp dụng** đúng luật (B3-05 chưa hợp nhất, chưa có `apps.api.rules.catalog`) · H5 đạt (4 khung SSE).

`case_gate`: `spatial_read_floor`, `spatial_read_graph`, `spatial_read_layer` — bắt buộc
`C01 C04 C05 C06 C08 C12 C13 C17 C25`, tìm thấy y hệt, thiếu 0; task `reconcile_floor_counts` J01 + J06 đủ
(không cần dòng `[[task]]`: `tools/case_gate.py:493-499` đòi J01/J06 cho **mọi** task trong sổ). Ba cảnh báo
`files_read_object`, `health_live`, `health_ready` có từ trước B3-02.

**Mọi số tác giả báo đều tự kiểm lại và khớp** (mã thoát 0 · 4588 passed · `apps/api/spatial_read` 100/100
· case_gate thiếu 0 · H1 1122 mẫu + 50 ngữ cảnh · 1 head). Không có bước nào "chưa chạy" bị báo là "đạt".

## Điều kiện dừng sớm (không vi phạm)

Cây sạch · có `changes/B3-02.md` · 7 commit đúng Conventional Commits, đủ trailer `Prompt:` (`1ada889` thêm
`Fix: FIX-108` đúng luật) · không đụng `docs/charter/*`, `tools/contract/APPFRONT_SHA`, `uv.lock`;
`docs/contracts/openapi.json` do người điều phối làm mới (`d95e79c`, tiền lệ B2-04 `6254ba9`) và **chỉ** thêm
`get` cho ba đường B3-02 — khối `ScaleMmPerPx` là nhiễu diff, nội dung y nguyên từng byte · không
`pragma: no cover`, không `skip`/`xfail` mới, không hạ ngưỡng; đúng **một** `# type: ignore[return-value]`
(`documents.py:116`) và **một** `# noqa: S603` (`test_boundary.py:40`), cả hai có mã và lý do · không
`except Exception` rộng. `main` đi trước nhánh đúng một commit tài liệu (`c4ac23c docs(fixes): open FIX-108`),
không xung đột.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-02 | N15 tra `pk_of[floor.id]` không guard: `floor_outs` và `_floor_pks` là hai câu lệnh khác snapshot (engine không đặt `isolation_level` → READ COMMITTED), nên một tầng xoá mềm chen vào giữa làm `KeyError` → 500. #33 và N16 có `_floor_out_or_404` cho **đúng** cuộc đua này, N15 không có và không có test | `apps/api/spatial_read/graph.py:81-83` | Lọc theo bảng `pk_of`: `pairs = [(f, pk_of[f.id]) for f in floors if f.id in pk_of]` rồi dựng `levels`/`docs`/`revisions` từ `pairs` (tầng vừa biến mất rơi khỏi đồ thị, song ánh `levels ↔ floorRevisions` vẫn đúng). Test: trỏ `delete_floor_mid_request` của `_read_helpers.py` vào `graph_path` — bộ nghe bắn sau câu `SELECT … FROM floors` của `floor_outs`, tức đúng khe hở |
| 2 | P2 | MNT-05 | Nhánh ~1 870 dòng sản phẩm + 2 755 dòng test (> 400) | cả nhánh | Chấp nhận theo tiền lệ NO-045/NO-216 (khối [10] là **một** đơn vị bàn giao: 14 module + 3 bảng + revision + seed + factory; tách là đưa nửa hợp đồng vào `main`) — nhưng phải có dòng `DEBT.md` |
| 3 | P2 | MNT-03 (R-34) | Ba nợ tác giả nêu trong báo cáo **không** có dòng `NO-<nnn>` nào trong `DEBT.md` (dừng ở NO-219 cả trên nhánh lẫn `main`), kể cả nợ P3 mà đính chính 1 nói "điều phối viên ghi" | `DEBT.md` (thiếu) · `bao-cao-B3-02.md` "Nợ và việc chưa làm" | Thêm: nợ P3 seed lặp hình dạng `codec.document_to_json`/`counts.layer_counts` (chủ **B3-01**, đường nâng cấp: hạ hàm thuần xuống `packages/domain/spatial`); dòng MNT-05 của finding 2; FIX-108 [7] chờ đóng sau merge |
| 4 | P3 | MNT-03 (R-07) | Factory chép `schema_version=1` thay vì `documents.DOCUMENT_SCHEMA_VERSION`, và dựng lại lớp rỗng thay vì dùng `documents.EMPTY_LAYER` công khai — nâng lược đồ theo FIX.md luật 7 sẽ để factory ghi tài liệu mà chính đường đọc từ chối | `packages/testing/factories/spatial.py:114,119` | Nhập hai hằng từ `apps.api.spatial_read.documents` (file đã nhập `codec` nên không thêm ranh giới nào) |
| 5 | P3 | MNT-04 | Chú thích nói dòng `[[task]]` của lịch "do việc J khai, trộn vào file này khi gộp" — không có dòng nào được trộn và cũng **không cần** (J01/J06 là mặc định của mọi task) | `apps/api/spatial_read/cases.toml:8` | Sửa chú thích thành "task không cần `[[task]]`: `case_gate` đòi J01/J06 cho mọi task trong sổ" |
| 6 | P3 | TEST-02 | Bất biến [6] "mọi `DocumentCorruptError` log `floor_pk`, handler cuối trả **500**" không có test nào chốt ở mức route: đổi `DocumentCorruptError` thành `AppError` (→ 4xx) sẽ không làm đỏ bước nào | `apps/api/spatial_read/tests/test_routes_layer.py` (thiếu) · `documents.py:90-97` | Một test N16 trên dòng `schema_version=2` ghi bằng SQL trần → `response.status_code == 500`, và `caplog` có `floor_pk` |
| 7 | Nit | PERF-01 | `_floor_pks` là câu thứ hai cho dữ liệu `_load_floor_outs` đã có trong tay (`row.FloorRow.pk`, `apps/api/floors/lookup.py:77`) — `FloorOut` không mang `pk` nên đây là hệ quả, không phải lỗi. Số truy vấn vẫn hằng số (8 = 8) | `apps/api/spatial_read/graph.py:57-71` | Nợ của B2-03 (trả kèm `pk`, hoặc `(FloorOut, pk)`); đừng sửa ở đây |
| 8 | Nit | MNT-03 | `router.py:82` gọi lại `effective_scale_source(document, page_key)` mà `assemble.level_out:69` vừa tính | `apps/api/spatial_read/router.py:82` | Hàm thuần, rẻ; nếu muốn gọn thì `level_out` trả kèm nguồn hiệu lực |

Đã soát và **không** ra finding: SEC (ba route `require_project()` ở `dependencies=` nên chạy trước mọi câu tìm
tầng, K08 đúng; không IDOR — `get_floor` lọc theo `project_id`; mọi câu là SQLAlchemy tham số hoá; log có
`floor_pk`, không bí mật; `hide_parameters=True`) · CON (`claim_entity_ids` khoá theo `ORDER BY entity_id` ở
cả `SELECT … FOR UPDATE`, `INSERT … SELECT` và vòng nhận lại, `ON CONFLICT DO NOTHING` trên chính PK,
`UPDATE … AND floor_pk = :chủ_cũ` chặn lượt nhận chồng — bảy tình huống đều có test **hai session thật**;
`recount_floor` khoá `floors FOR SHARE` → `floor_documents FOR SHARE` đúng thứ tự BE-00 §7, chỉ ghi qua
`set_layer_counts`, không `touch_project`; `ensure_document` song song ra một dòng) · PERF (N15 hằng số truy
vấn 8 = 8 với 1 và 8 tầng, đo bằng `count_sql` của B2-01; `load_documents`, `load_pages`, `drawing_scales.load`
mỗi thứ một truy vấn; lịch đi keyset `pk > after`, giao dịch ngắn từng tầng, có cửa sổ nhìn lại) · DB
(expand thuần ba bảng mới, không `ALTER` bảng đang có nên không khoá bảng; mọi FK CASCADE; downgrade có và
`migrate_check` chạy; `value JSONB(none_as_null=True)` đúng đính chính; 1 head) · API (chỉ **thêm** `get`,
không đổi đường hay `operationId`; dây khớp từng khoá với `spatial.ts`/`spatialGraph.ts`/`spatialLayer.ts` ở
AppFront `9cf0b0bfffbd`: 9 khoá N15, 6 khoá N16, không `scaleStatus` ở N15, không `notes` ở N16, `areaM2`/tỉ lệ
là số JSON, `roomId`/`address`/`areaM2` vắng khoá chứ không `null`; refine `scaleStatus ⇒ scaleMillimetresPerPixel`
của FE được CHECK `(scale_source='none') = (scale_mm_per_px IS NULL)` bảo đảm) · R-01 (docstring đủ mọi hàm
sản phẩm và test mới; chỗ thiếu trong `test_seeds_settings.py` là mã B0-03 có từ trước, FIX-108 không chạm) ·
FIX-108 (sửa **gốc** — chốt bất biến thật của bộ dò seed thay vì danh sách chép tay, không nới và không xoá
assert nào; chạm đúng một file của B0-03, đúng hai test vì cả hai cùng một nguyên nhân).

Bảy "Lệch khỏi prompt" của tác giả: đều có lý do đứng được và **đã kiểm lại** — (1) seed không nhập `apps.api`
đúng đính chính 1 và `.importlinter` `db-isolated`, có `test_seed_matches_codec_and_counts` +
`test_seed_layers_decode_as_wire_models` giữ hai phía; (2) mẫu commit theo CLAUDE.md; (3) `discover` trả
`apps.api.spatial_read.drawing_scales`; (4) một truy vấn `{level_id: pk}` — số truy vấn vẫn hằng số (nhưng xem
finding 1 và 7); (5) `after_cursor_execute` là cách duy nhất dựng được cuộc đua; (6) FIX-108 chạm hai test;
(7) `test_boundary.py` miễn `wire.py` theo đúng hợp đồng [2]. Không cái nào thành finding.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 1 | 0,15 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |

Tổng: **4,27 / 5** · P0: 0 · P1: 1 · P2: 2 · P3: 3 · Nit: 2

## PHÁN QUYẾT: REQUEST CHANGES

Chất lượng nhánh này cao hơn mức trung bình của bộ: cổng xanh một lượt, `apps/api/spatial_read` phủ
100 %/100 %, và những chỗ khó nhất — `claim_entity_ids` với bảy tình huống đồng thời trên hai session Postgres
thật, `recount_floor` với thứ tự khoá BE-00 §7, hợp đồng dây khớp từng khoá với zod của AppFront — đều làm
đúng và có test chứng minh. Báo cáo của tác giả kiểm lại không thấy một con số nào sai.

Chặn merge vì **đúng một** lỗi, và là lỗi cùng loại với thứ prompt đã bắt xử lý: #33 và N16 đều trả 404 khi
tầng biến mất giữa hai câu lệnh, còn N15 tra `dict` trần và trả 500. Đây là lỗi thật dưới điều kiện biên
(READ COMMITTED, hai câu lệnh, một lượt xoá mềm chen giữa) trên một route mà `SpatialJsonViewer` và
`ExplodedView` gọi thẳng, nên nó là P1 theo RULE §1 và §3 LOG-02, không phải P2.

Phải sửa để được `APPROVE`:

1. **(P1, finding 1)** Guard `pk_of` ở `graph.py:81-83` + một test dùng `delete_floor_mid_request` trên
   `graph_path` (đỏ trước, xanh sau).
2. **(P2, finding 3)** Thêm dòng `NO-<nnn>` vào `DEBT.md` cho: nợ P3 seed lặp `codec`/`counts` (chủ B3-01),
   MNT-05 của finding 2 (`➖` chấp nhận, mẫu NO-216), và FIX-108 [7] chờ đóng.
3. **(P2, finding 2)** Đã có lý do đứng được, chỉ cần dòng `DEBT.md` ở mục 2 — không phải tách nhánh.

Finding 4–6 (P3) và 7–8 (Nit) không chặn merge; nếu không sửa trong lượt này thì gộp vào một dòng `DEBT.md`
cùng mục 2. Chạy lại `verify` một lượt sau khi sửa (finding 1 chạm `graph.py`, tức bước 5 và 7 đều phải xanh
lại) rồi mở lượt review 2.
