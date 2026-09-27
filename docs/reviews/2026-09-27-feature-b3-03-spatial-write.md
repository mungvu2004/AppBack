# Review merge `feature/b3-03-spatial-write` → main

- Ngày: 2026-09-27 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `6fdbe1cf15c0`
- Cổng: phạm vi **đầy đủ** — lượt review 1 của nhánh (R-33b điều kiện 1). `bash tools/verify/run.sh verify`
  mã thoát **0** (một lượt, worktree review ở đúng sha `6fdbe1c`, chạy trong pane RUNNER;
  log `…/scratchpad/verify-full.log`, dòng `EXIT=0`; log cổng trong container
  `.cache/src-out/verify/20260927T162042Z-6fdbe1cf15c0.log`) — 8/8 bước `đạt`
- Test: **4864 passed, 0 failed**, 7 deselected (1327,78 s = 22:07)
- Độ phủ: tổng dòng **99,53 %** · nhánh **98,48 %** · `apps/api/spatial_write` dòng **100,00 %** ·
  nhánh **100,00 %** · tập file bị chạm dòng **100,00 %** · nhánh **100,00 %**

## Trạng thái cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | ranh giới `db-isolated`, `api-jobs-no-web` giữ |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4864 passed / 0 failed; `coverage combine` 62 file |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; **thiếu = 0** |
| 6 | `lint_migrations` → `migrate_check` | đạt | 12 revision, **đúng 1 head**, 10/10 mục của `migrate_check` |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | bảng con dưới |
| 8 | `openapi` | đạt | 155 769 byte, không lệch |

Bảng con bước 7 (AppFront `9cf0b0bfffbd`): Smoke đạt (23 module schema, 83 mục) · Bản đồ đủ đạt (83/83)
· Thao tác đã mount đạt (**53**/83, B3-02 là 49) · **H1 đạt — 1232 mẫu response** (B3-02 là 1122, tức #35
góp ~110 mẫu mới) · **H1 ngữ cảnh đạt — 50 mẫu** · H3 đạt (10 khoá, 3 vai) · H4 **không áp dụng** đúng luật
BE-00 §12 (B3-05 chưa hợp nhất, chưa có `apps.api.rules.catalog`) · H5 đạt (4 khung SSE).

`case_gate`: `spatial_write_layer` — bắt buộc `C01 C02 C03 C04 C05 C06 C07 C08 C09 C09b C12 C13 C14 C16 C17
C25` (16 case), **tìm thấy y hệt 16, thiếu 0**. Lịch `compact_change_log`: `case_gate` chỉ in dòng task khi
**thiếu** (`tools/case_gate.py:493-500` → `result.task_missing`), và `case_gate: đạt` với 0 dòng task nghĩa là
mọi task trong sổ có đủ J01 + J06; đã tự kiểm hai test tồn tại thật:
`test_compact_change_log__J01` (`tests/test_jobs.py:94`) và `__J06` (`:121`). Ba cảnh báo
`files_read_object`, `health_live`, `health_ready` có từ trước B3-02.

**Mọi số tác giả báo đều tự kiểm lại và khớp**: mã thoát 0 · 8 bước đạt · 4864 passed / 7 deselected ·
tổng 99,53 % / 98,48 % · `spatial_write` 100/100 · `case_gate` `spatial_write_layer` 16/16 thiếu 0. Khác biệt
duy nhất là thời gian (tác giả 24:15, lượt này 22:07 — cùng máy, khác tải). Không có bước nào "chưa chạy" bị
báo là "đạt" (K25).

## Điều kiện dừng sớm (không vi phạm)

Cây sạch (`git status --porcelain` rỗng) · có `changes/B3-03.md` (10 dòng, ghi rõ "Không có migration") ·
6 commit đúng Conventional Commits ≤ 72 ký tự, **tất cả** đủ trailer `Prompt: B3-03` (`30015ff` là commit gộp
hai nhánh lớp 1 của DAG, dòng đầu vẫn đúng mẫu) · nhánh dựng đúng trên `main`
(`git merge-base main HEAD` = `9e37313` = `main` hiện tại, không cần rebase, không xung đột) · không đụng
`docs/charter/*`, `docs/contracts.toml`, `uv.lock`, `tools/**`, `conftest.py`, `pyproject.toml`,
`.importlinter`, `tools/contract/APPFRONT_SHA`, `apps/api/{core,auth,access,projects,floors,drawings,spatial_read}/**`,
`packages/**`; `docs/contracts/openapi.json` do người điều phối làm mới (`6fdbe1c`, tiền lệ B3-02 `d95e79c`) ·
không tạo `cases.toml`, không `conftest.py` lồng, không file cấu hình công cụ riêng · không `pragma: no cover`,
không `pragma: no branch`, không `skip`/`xfail` mới, không hạ ngưỡng; đúng **một** `# noqa: S603` có mã và lý do
(`tests/test_boundary.py:33`), **không một** `# type: ignore` nào · không `except Exception` rộng.

**Diff `openapi.json` đã tự kiểm theo cấu trúc** (so JSON đã giải, không đọc diff dòng): 571 dòng **chỉ thêm**,
0 dòng xoá. Đường thêm: 0. Đường **đổi: đúng một** —
`/api/projects/{project_id}/floors/{floor_id}/spatial/layer`, và trong đó `get` giống **từng byte**, chỉ `put`
là mới. Schema thêm: 12 (`FloorLayerWriteSchema`, `FloorLayerWriteBodySchema`, `FloorLayerWriteResultSchema`,
`LayerScaleMmPerPx`, `SpatialLayer`, `Wall`, `Opening`, `Room`, `Furniture`, `Segment`, `Point`, `BoundingBox`).
Schema xoá: 0. Schema **đổi: 0** — `ScaleMmPerPx` của `project_settings` còn nguyên, tức `131580e`
(`ScaleMmPerPx` → `LayerScaleMmPerPx`) thật sự đã chặn cuộc đụng tên K01/K02 mà nó nói. Không khoá nào khác
của tài liệu đổi.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-02 | `_scale` gọi `Decimal(str(value)).quantize(1E-6)` **trước** khi kiểm dải. Với mọi số JSON hữu hạn có ≥ 23 chữ số phần nguyên (≥ `1e22`), kết quả cần > 28 chữ số nên `decimal` ném `InvalidOperation` — là `ArithmeticError`, **không** phải `ValueError`. `BeforeValidator` của Pydantic chỉ đổi `ValueError`/`AssertionError` thành 422, nên ngoại lệ lọt qua Pydantic, **không** thành `RequestValidationError`, rơi xuống chặng cuối `apps/api/core/middleware.py:276` → `translate_unknown` (`errors.py:149-156`) → **500 `INTERNAL`** + log `unhandled_exception` có stack, thay vì 422 `VALIDATION` + `field` mà [2] hứa. Đã dựng lại với đúng pydantic `2.13.5` của `uv.lock:1347`: `1000001` → `ValidationError`, `1e22` → `InvalidOperation` không ai bắt. **Tới được qua UI thật**: zod của FE là `z.number().positive().finite()` (`F:/AppFront/src/api/schemas/spatialLayer.ts:59`) — **không có trần** — nên trình duyệt gửi `1e22` đi bình thường | `apps/api/spatial_write/schemas.py:41` | Bọc phép quantize: `except InvalidOperation as error: raise ValueError("tỉ lệ ngoài dải") from error` — giữ nguyên mọi hành vi đang có, kể cả luật "0 sau làm tròn → 422". Kèm finding 3 |
| 2 | P2 | PERF-02 | `remote_changes_since` nạp **mọi** dòng `DISTINCT ON (entity_id, field)` có `revision > base` dưới dạng thực thể ORM đầy đủ (gồm `value` JSONB) rồi mới cắt trong Python bằng `deque(maxlen=limit)`. `SPATIAL_CONFLICT_CHANGES_MAX = 5000` vì thế chỉ chặn **thân trả về**, không chặn việc phải làm. Chính số đo của tác giả: lượt ghi đầu trên tầng 3.000 tường sinh ~28.000 dòng nhật ký (`bao-cao-r.md`), nên một 409 ở `baseVersion 0` trên tầng ấy nạp ~28.000 đối tượng để trả 5.000 | `apps/api/spatial_write/changes.py:30-50` | Đẩy phép cắt vào SQL: giữ `DISTINCT ON` làm subquery rồi `select(sub).order_by(sub.c.revision.desc(), sub.c.id.desc()).limit(limit)`, đảo lại trong Python (vẫn "mục **mới nhất**", vẫn một truy vấn); chọn 7 cột thay vì thực thể ORM |
| 3 | P2 | TEST-02 | `test_scale_rejects_everything_outside_the_contract` dừng ở `SCALE_MAX + 1`, và C02 chỉ có `zero_scale`. Không test nào chạm biên **độ lớn** nơi chính `decimal` vỡ — đó là lý do finding 1 đi qua được 8 bước cổng và 4864 test xanh | `apps/api/spatial_write/tests/test_schemas.py:32` · `tests/test_routes.py:48-58` (`_bad_bodies`) | Thêm `1e22` và một số nguyên JSON lớn (`10**30`) vào tham số test mức hàm, và một dòng `huge_scale` vào `_bad_bodies` của C02 (đỏ trước, xanh sau) |
| 4 | P2 | MNT-05 | Nhánh ~924 dòng sản phẩm + ~3.380 dòng test (> 400) | cả nhánh | Chấp nhận theo tiền lệ NO-216/NO-221: khối [10] của B3-03 là **một** đơn vị bàn giao (8 module; B3-04 và B5-06b cùng chờ `write_layer` **và** `remote_changes_since`), tách là đưa nửa hợp đồng vào `main`. Đường nâng cấp: chia ngay ở bản prompt (lõi ghi ↔ route + lịch). Phải có dòng `DEBT.md` |
| 5 | P3 | CON-04 | Lệch #1 của W (`load_document` trước `ensure_document`) có một lỗ mà báo cáo không thấy: khi tầng **chưa có dòng** `floor_documents`, nhánh `or` đọc lại qua `ensure_document`, vốn `SELECT` **không** `FOR UPDATE` (`spatial_read/documents.py:155`). Đường `merge` vì thế chạy **không khoá** ở lượt ghi đầu tiên của một tầng, ngược với `bao-cao-w.md` ("Đường merge … khoá `floor_documents FOR UPDATE`, nên nó không bao giờ … thử lại"). Không hỏng dữ liệu — `UPDATE … WHERE revision = :eb` vẫn chặn và lượt ấy thử lại — nhưng một lượt `merge` có thể thua đua mà nó được thiết kế để không bao giờ thua, và thua `SPATIAL_WRITE_ATTEMPTS` lần thì ra 503 | `apps/api/spatial_write/writer.py:280-282` | Giữ đúng thứ tự prompt bước 3 (`ensure_document` rồi `load_document(for_update=…)`) — sửa trong file của B3-03, không chạm B3-02. Cách thứ hai (truyền `for_update` xuống câu đọc lại của `ensure_document`) chạm file của B3-02 → nợ + FIX cho đúng chủ (K27) |
| 6 | P3 | MNT-03 (R-07) | Hai chỗ lặp do ranh giới worker W/R của DAG, **không** do luật sở hữu (cả hai file đều thuộc B3-03): `layer_of(level_id, walls, rooms, furniture)` bao trọn `simple_layer(level_id, walls, rooms)` và cả hai đang được dùng; `slipping_load` (bên đua chen vào giữa bước 3 và 11) gần như giống từng dòng ở hai file test | `tests/_route_helpers.py:87` ↔ `tests/_helpers.py:168` · `tests/test_routes_errors.py:210-228` ↔ `tests/test_writer_conflict.py:222-249` | Thêm `furniture: Sequence[Furniture] = ()` vào `simple_layer` rồi xoá `layer_of`; hạ `slipping_load` xuống `_helpers.py` thành một helper nhận `floor`/`actor`/`clock` — việc này đồng thời đóng finding 7 |
| 7 | P3 | MNT-03 (R-08) | Hai hàm test > 50 dòng | `tests/test_routes_errors.py:188` (51) · `tests/test_writer_conflict.py:211` (54) | Tách `slipping_load` theo finding 6; cả hai xuống dưới 40 dòng |
| 8 | P3 | MNT-03 (R-01) | Hai helper lồng thiếu docstring — chỗ **duy nhất** trong cả nhánh (đã quét 21 file: mọi module, lớp, hàm khác đều có) | `tests/test_jobs.py:191` (`_seed`) · `:197` (`_count`) | Một câu mỗi hàm |
| 9 | P3 | API-05 | `put` của #35 khai `parameters` chỉ có `floor_id`; `get` **cùng đường** và `patch /api/projects/{project_id}/floors/{floor_id}/spatial` khai cả hai. Handler chỉ lấy `project_id` qua `require_project` nên FastAPI không sinh ra nó, mà OpenAPI 3.1 đòi khai mọi biến của path template. Tiền lệ **đã có trên `main`**: `put /api/projects/{project_id}/settings` cũng thiếu, nên cổng hợp đồng xanh và đây không phải lỗi mới về bản chất | `docs/contracts/openapi.json` (`put` của #35) | Nếu dọn thì dọn cùng route `settings`: khai `project_id: str` trong chữ ký như `patch` láng giềng. Không đáng sửa riêng cho nhánh này |
| 10 | Nit | OBS-02 | Đường 503 (thua đua `SPATIAL_WRITE_ATTEMPTS` lần) không để lại dòng log nào của chính nó; người vận hành thấy 503 mà không biết tầng nào | `apps/api/spatial_write/writer.py:208` | Một `_log.warning` kèm `floor_pk` trước khi ném |
| 11 | Nit | MNT-03 | Docstring `body_sha256` giải thích vì sao dùng `str(Decimal)` thay `float`, nhưng `Decimal("10")` và `Decimal("10.000000")` vẫn ra hai vân tay khác nhau. Vô hại cho #35 (Pydantic luôn quantize 6 chữ số); người gọi Python (B5-06b) truyền `Decimal` chưa quantize thì chỉ **trượt** C09b rồi rơi vào phép kiểm xung đột — hướng an toàn | `apps/api/spatial_write/writer.py:151-157` | Một mệnh đề: "người gọi Python phải tự quantize nếu muốn C09b khớp" |

## Đã soát và không ra finding

**SEC** — `require_project("layer.edit")` là **tham số** `Depends` nên chạy trước guard 428, trước Pydantic và
trước mọi câu tìm tầng: K08 đúng, người ngoài dự án (kể cả admin hệ thống) ra 404 `resource:"project"`
(`__C06`), viewer ra 403 (`__C07`). Không IDOR: `get_floor(project_id=access.project_id, level_id=floor_id)`
lọc theo dự án, và `write_layer` lấy `project_id`/`level_id` từ **dòng `floors` đã khoá**
(`writer.py:201-202`) chứ không từ request, nên `claim_entity_ids` không thể bị đẩy sang dự án khác. Không mass
assignment: `extra="forbid"` ở cả ba lớp (đã kiểm `additionalProperties: false` trong openapi) và `LayerWrite`
dựng tường minh từ đúng hai trường — `dimensions` cố ý **không** có trên dây, nên dây không thể đặt kích thước.
Mọi câu là SQLAlchemy tham số hoá. `changed_by_name` đọc từ `users` **trong cùng giao dịch**
(`router.py:36-42`), không lấy từ token (K05/W18) — có test `logs_the_token_subject` (đổi tên sau đó không đổi
dòng cũ). Log không có bí mật.

**CON** — Thứ tự khoá đúng BE-00 §7 từng bước: `floors FOR SHARE` (`_locked_floor`) → `floor_documents`
(`_bump`, `FOR UPDATE` chỉ ở đường `merge`) → `floor_entity_ids` (`_claim`) → `project_floor_summaries`
(`set_layer_counts`) → `projects` (`touch_project`), và `_commit:464-480` gọi đúng dãy ấy, đúng thứ tự bước
11 → 12 → 13 → 14 của [6]. SAVEPOINT bọc bước 11–15 (prompt đòi 11–14; bọc thêm `touch_project` là phía an
toàn) và **được test bằng đúng cảnh prompt tả**: bắt `LAYER_INTEGRITY_BROKEN` rồi `commit`, `revision` và
`floor_entity_ids` không đổi (`tests/test_writer.py:493`). Vòng thử lại dùng `base_revision` **gốc**
(`_Request` là `frozen`, `_attempt` không đổi nó) và quá trần ra 503 + `Retry-After: 1` (`writer.py:208`, hai
test: mức hàm và mức route). Vòng thử lại **thật sự thấy dữ liệu mới** — điểm tôi nghi nhất vì SQLAlchemy không
làm mới thực thể đã có trong identity map khi không `populate_existing()`: C14 hai request HTTP song song (hai
giao dịch Postgres thật, `asyncio.gather`) cho đúng `[200, 409]` với `currentVersion 1` và `remoteChanges ≥ 1`;
nếu lượt thử thứ hai đọc lại bản cũ thì bên thua phải ra **503** chứ không ra 409, nên test này chốt đúng chỗ
ấy. C09b so đủ **ba** trường (`last_writer_id`, `last_body_sha256`, `last_base_revision`) và `_bump` giữ
`last_base_revision` = bản **gốc** người dùng cầm ở đường thường, `eb` ở đường `merge` — đúng [6] bước 11.
"Diff rỗng thì nhận ghi" (`test_empty_remote_diff_accepts_the_write`), khác thân → 409, người khác cùng thân →
409. Tranh id giữa hai tầng cùng dự án: `race()` hai session thật, đúng một bên thắng.

**LOG** (ngoài finding 1) — Bước 2 dừng ở lỗi **đầu tiên** đúng thứ tự A5 → `levelId` → toàn vẹn, `field` dựng
theo thứ tự `walls, openings, rooms, furniture` rồi chỉ số (`_positions`, `_field_of`); `_field_of` không thể
`IndexError` vì `ai_reviewed_ids` duyệt đúng `SpatialLayer.entities()` = đúng bốn danh sách ấy
(`packages/domain/spatial/model.py:260`). `merge` chạy **lại** bước 2 trên lớp nó trả (`_next_layer:385`), có
test. `check_integrity` và `diff_layers` trả `list` (không generator, không tuple) nên `has_critical(issues)` +
`sum(...)` duyệt hai lần vẫn đúng và `changes += [...]` không vỡ kiểu. Hạng tỉ lệ K19 đúng
`human 3 > pipeline 2 > project_default 1 > none 0`, so bằng `<` nên hạng **bằng nhau** được ghi đè,
`pipeline` không bao giờ thành `human` (nguồn lấy từ `request.scale_source`), không gán tỉ lệ mặc định
(`target is None` → giữ nguyên tất cả), luật theo trang chỉ áp cho `merge` và khi `scale_page_key` khác NULL và
khác `page_key` — cả bốn ca có test riêng (`test_writer_scale.py:180,201,247,276`). `_page_of` đúng ba nhánh
([6] bước 6). `rescale_*` nhận `float`, `RescaleError` → 422 `field:"body.scaleMillimetresPerPixel"` ở **cả
hai** đường (lớp và kích thước). `areaM2` tính lại cho **mọi** phòng kể cả phòng đã duyệt (`_with_areas`, W18).
K21 đúng ba ca `ValueError`. `_remap_refs` theo `id_map`, `_drop_missing_refs` gỡ id đã mất. `remote_changes_since`
giữ mục **mới nhất** (`deque(maxlen=)` lấy cuối dãy đã sắp `(revision, id)` tăng) và chú thích đúng cạm bẫy
`[-0:]`; `removed` → `MISSING` chứ không `None`; `changed_at` là `timestamptz`.

**PERF** (ngoài finding 2) — Một lượt ghi là ~10 truy vấn hằng số, không N+1; nhật ký chèn **một lô**
`executemany`; `current_drawing` chỉ gọi khi tỉ lệ đổi **và** `scale_page_key` NULL. Số đo tầng lớn là số thật
(`time.perf_counter`, in ra): thân 1,28 MiB, p95 3,85 s, giữ khoá `merge` 0,31 s — đã đọc mã đo, không phải số
chép tay. Lịch gộp đi được index `(floor_pk, entity_id, field, revision)` đã có sẵn
(`packages/db/models/spatial.py:117-123`); mỗi lô một giao dịch, session đóng giữa các lô, không giữ khoá xuyên
lô, không sửa `floor_documents`, chỉ xoá dòng có dòng mới hơn `(revision, id)` cùng
`(floor_pk, entity_id, field)` nên dòng hiện hành của mỗi trường không bao giờ bị chọn. (Vòng lặp quét lại từ
đầu mỗi lô nên tổng công là bậc hai theo số lô — với việc nền 24 h và cửa sổ 30 ngày thì chấp nhận được; đường
nâng cấp là mang con trỏ `id > max(id đã xoá)` sang lô sau, an toàn vì các dòng đủ điều kiện được lấy theo đúng
thứ tự `id`.)

**RES** — 503 `DEPENDENCY_UNAVAILABLE` + `Retry-After: 1`, có trần `SPATIAL_WRITE_ATTEMPTS`, không 500 (test
khẳng định cả `code` lẫn header). Không nuốt ngoại lệ ở đâu.

**DB / API** — Không migration, không bảng mới, không seed: đúng `changes/B3-03.md` và `migrate_check` vẫn
đúng 1 head. Chỉ **thêm** một `put`, không đổi đường hay `operationId` nào đang có. Dây khớp từng khoá với zod
của AppFront (`src/api/schemas/spatialLayer.ts:104-147`): `FloorLayerWriteSchema` = `{baseVersion, body}`,
`FloorLayerWriteBodySchema` = `{layer?, scaleMillimetresPerPixel?}` với `.strict()` ↔ `extra="forbid"` và
refine "≥ 1 khoá" ↔ `_at_least_one_key`, `FloorLayerWriteResultSchema` = `{layer, revision}`; 409 dùng
`VersionConflictBodySchema` của `errors.ts` qua `VersionConflictError` (H1 chọn schema theo `code`;
`tools/contract/schema-map.ts:80` đã có `spatial_write_layer` nên `tools/` không bị sửa) — H1 đạt với 1232 mẫu.
Tỉ lệ `Decimal` 6 chữ số đúng `Numeric(12,6)`; A5 **không** ở tầng Pydantic (mô hình miền cố ý để nó qua để ra
đúng `REVIEW_BY_AI_FORBIDDEN` chứ không `VALIDATION`) — có test.
`route_options(versioned=True, body_limit=8 MiB, idempotency="off")` đúng [2], và `body_limit > 1 MiB` **buộc**
`idempotency="off"` ngay lúc nạp module (`routing.py`, đính chính §3) nên hai thứ không thể lệch nhau. Handler
**không** `commit` và **không** ghi `activity_log` (đã grep cả module: `.commit()` chỉ có ở `jobs.py:71`, đúng
chỗ — lõi lịch sở hữu giao dịch của nó).

**TEST** (ngoài finding 3) — Không mock session, không mock `write_layer` ở test route (K22/K23): `monkeypatch`
chỉ **bọc** `writer.load_document` để chen một lượt ghi **thật** ở session **thật** vào giữa bước 3 và 11, đúng
cách [8] tả; C14 là hai request HTTP song song. Ma trận case [8] đủ: 16 case GV + 5 case chung, và
`required_cases_for()` mà tác giả in ra khớp bảng `case_gate` của cổng, nên `cases.toml` thật sự không cần
(C21 không áp vì `body_mirrors_path=False`; C10/C22 không áp vì `versioned=True` + `idempotency='off'`). Lịch có
`__J01`, `__J06`, test khói gọi chính hàm lịch với `worker_sessionmaker()` thật, test lô nhỏ khớp một lô lớn,
test `remote_changes_since` bằng nhau với **mọi** `base` từ 0 tới revision hiện tại trước và sau gộp
(`_all_bases`), và test dòng trong cửa sổ còn nguyên. Ranh giới BE-00 §7 đủ **bốn** gói (`writer`, `changes`,
`errors`, `jobs`) bằng tiến trình con chặn `fastapi`/`starlette`/`jwt`/`argon2`, **và** lại bằng bước 4
`lint-imports`. Lịch được beat nhìn thấy mà không cần sửa `apps/worker`: `discover_jobs()` nhập mọi
`apps.api.*.jobs` (`packages/messaging/schedules.py:99-102`) — đã tự kiểm, không chỉ tin
`test_schedule_is_registered`.

**OBS** (ngoài finding 10) — `jobs.py` log một dòng có cấu trúc khi xong, không bí mật.

## Lệch khỏi prompt của tác giả: 12 mục, đã đối chiếu từng mục

- **W1** `load_document` trước `ensure_document` → **thành finding 5**: lý do "kết quả giống hệt, cùng cảnh đua"
  đúng cho đường thường nhưng **không** đúng cho đường `merge` khi tầng chưa có dòng tài liệu.
- **W2** `LAYER_INTEGRITY_BROKEN.count` = số lỗi **critical** → **nhận**: chính docstring của mã lỗi nói "toàn
  vẹn mức `critical`", và `warning` không chặn ghi nên đếm nó vào thì FE hiển thị một con số vô nghĩa. Bước 12
  đếm số id, đúng prompt.
- **W3** dòng `dimension`/`reference_ids` ghi ở **cả hai** đường kích thước → **nhận**: ngoặc đơn của prompt
  ("`body.dimensions` không sinh dòng") loại trừ **nội dung** kích thước, không loại trừ việc gỡ id ở bước 9;
  một tham chiếu thật sự bị gỡ là một thay đổi từ xa mà FE phải thấy ở 409. Ma trận case không đòi ngược lại.
- **W4** không helper 503 riêng → **nhận** (R-10: một chỗ ném duy nhất).
- **W5** hằng id riêng cho các ca tỉ lệ → **nhận**: 1000 → 2000 mm và 17,00 m² kiểm được bằng tay.
- **R1** tên lớp theo zod FE thay `…In`/`…Out` → **nhận**: hai đầu dây đọc cùng một tên, docstring nói rõ là cố ý.
- **R2** không dùng `wire.versioned()` → **nhận**, có tiền lệ `ProjectSettingsWriteIn` (B2-02): `versioned()` trả
  `type[WireRequest]` nên `body.body.layer` mất kiểu dưới `mypy --strict`. Đã kiểm guard 428 vẫn đúng vì nó ở
  tầng khung chứ không ở Pydantic (`__C09_missing` chốt).
- **R3** `get_floor(level_id=…)` → **nhận**, đúng `dinh-chinh.md` §1 (đính chính thắng prompt).
- **R4** "0 sau làm tròn → 422" bằng `Field(gt=0)` **sau** `BeforeValidator` → **nhận về nguyên tắc** (`0`,
  `0.0000004`, số âm cùng ra 422 kèm `field` — đã tự dựng lại và xác nhận), nhưng chính thứ tự "quantize trước,
  kiểm dải sau" là nguyên nhân finding 1.
- **R5** helper ở `_route_helpers.py` thay vì sửa `_helpers.py` → **thành finding 6**: ranh giới ấy là ranh giới
  của **DAG**, không phải luật sở hữu file — cả hai file đều thuộc B3-03.
- **R6** không tạo `cases.toml` → **nhận**, đã tự kiểm bằng bảng `case_gate` của cổng (16/16, thiếu 0).
- **J** không lệch → **đúng**, đã so với khuôn `apps/api/spatial_read/jobs.py`.

Đính chính `dinh-chinh.md` (9 mục) đều được tuân: `get_floor` §1 · `packages.domain.scale` §2 ·
`route_options` + ràng buộc `body_limit`/`idempotency` §3 · tên schema FE và `schema-map.ts` ở AppBack §4 ·
`claim_entity_ids` trả id **xung đột** (khác `MergeOutcome.id_map`) §5 · `FieldChange` ≠ `RemoteFieldChange`,
xoá → `value` NULL + `removed=true` §6 · tự viết C09/C09b/C14 theo CASE §2.3, dùng lại `race()`/`other_session()`
§7 · idempotency §8 · `openapi.json` do điều phối viên §9.

## Sổ nợ (R-34, R-35, R-38)

`DEBT.md` **không có dòng nào cho B3-03** (dòng cuối là NO-221 của B3-02). Ba mục mà báo cáo tác giả tự nêu, cộng
hai mục của review này, phải thành dòng `NO-<nnn>` trước khi merge:

1. MNT-05 của finding 4 (`➖ chấp nhận`, mẫu NO-216/NO-221).
2. Ghi chú test của R: test HTTP phải `await db_session.commit()` trước khi chạm đối tượng ORM (`rollback()` làm
   hết hạn instance → `MissingGreenlet`). Chủ là file ghi chú test chung của prompt khác → đúng ca K27: một dòng
   nợ + FIX cho đúng chủ, không im lặng.
3. `p95` tầng lớn lấy trên 5 mẫu (bằng mẫu chậm nhất, tức lượt đầu gánh 28.000 dòng nhật ký) — số trong báo cáo
   không so được với ngưỡng nào.
4. Finding 9 (openapi thiếu `project_id`) dùng chung với `put /api/projects/{project_id}/settings` → một dòng nợ
   cho cả hai.
5. Finding 2 nếu không sửa trong lượt này.

Không có nợ `P0`/`P1` nào đang **mở** trong `DEBT.md` chặn nhánh này (R-35, R-38).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 4 | 0,60 |
| LOG – Tính đúng đắn | 15 % | 1 | 0,15 |
| PERF – Hiệu năng | 10 % | 3 | 0,30 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 | 0,40 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |

Tổng: **3,75 / 5** · P0: 0 · P1: 1 · P2: 3 · P3: 5 · Nit: 2

## PHÁN QUYẾT: REQUEST CHANGES

Nhánh này làm đúng những chỗ khó nhất của B3-03, và làm có bằng chứng: thứ tự 15 bước của `write_layer` khớp
[6] từng bước kể cả thứ tự khoá BE-00 §7; SAVEPOINT được chốt bằng đúng cảnh prompt tả (bắt 422 rồi `commit`,
bản ghi và `floor_entity_ids` không đổi); C14 là hai giao dịch Postgres thật qua HTTP nên nó chốt luôn thứ tôi
nghi nhất — vòng thử lại có thật sự đọc lại bản ghi mới hay không; bốn ca hạng tỉ lệ K19 và luật theo trang mỗi
ca một test; ranh giới worker được kiểm hai lần (tiến trình con **và** `lint-imports`); `openapi.json` sau khi
so theo cấu trúc chỉ đổi đúng `put` của #35 và **không** một schema nào đang có. `apps/api/spatial_write` phủ
100 % dòng và 100 % nhánh, `case_gate` 16/16 thiếu 0, và mọi con số trong ba báo cáo tác giả tôi kiểm lại đều
khớp. Mười trong mười hai mục "Lệch khỏi prompt" có lý do đứng được.

Chặn merge vì **đúng một** lỗi. `_scale` làm tròn **trước** khi kiểm dải, nên một số hữu hạn ≥ `1e22` làm
`decimal` ném `InvalidOperation` — không phải `ValueError`, nên Pydantic không đổi nó thành 422 và nó rơi tới
chặng cuối của app thành **500 `INTERNAL`** kèm stack, thay cho 422 `VALIDATION` + `field` mà hợp đồng #35 hứa.
Đây không phải đầu vào giả tưởng: zod của FE (`spatialLayer.ts:59`) không có trần trên, nên chính UI gửi được
giá trị ấy. Lỗi ở **điều kiện biên**, trên đúng trường mà C02 tồn tại để bảo vệ, nên nó là P1 theo RULE §1 và
§3 LOG-02 — dù bản sửa chỉ là một `except`. Nguyên nhân gốc là finding 3: bộ test dừng ở `SCALE_MAX + 1` và
không bao giờ chạm biên độ lớn, nên 8 bước cổng xanh và 4864 test xanh vẫn không thấy.

Phải sửa để được `APPROVE`:

1. **(P1, finding 1)** Bọc `quantize` ở `schemas.py:41` — `InvalidOperation` → `ValueError`.
2. **(P2, finding 3)** Test đỏ trước xanh sau: `1e22` và `10**30` vào `test_scale_rejects_everything_outside_the_contract`,
   một dòng `huge_scale` vào `_bad_bodies` của C02.
3. **(P2, finding 2)** Đẩy phép cắt của `remote_changes_since` vào SQL, hoặc một dòng `DEBT.md` có lý do đứng được.
4. **(P2, finding 4)** Không phải tách nhánh — chỉ cần dòng `DEBT.md` theo mẫu NO-221.
5. **(R-34)** Năm dòng `NO-<nnn>` ở mục "Sổ nợ" trên.

Finding 5–9 (P3) và 10–11 (Nit) không chặn merge; finding 5 nên sửa trong lượt này vì bản sửa nằm trọn trong
`writer.py` của B3-03 và nó làm đúng lại một khẳng định mà báo cáo tác giả nói sai. Finding 6 + 7 đóng chung
bằng một lần hạ `slipping_load` xuống `_helpers.py`.

Phạm vi kiểm cho lượt 2 (R-33b): bản sửa finding 1 + 3 chạm `schemas.py` và test của module → **đích** là đủ
(bước 1–4 + `pytest apps/api/spatial_write`), **trừ khi** cũng sửa finding 2 hoặc 5 — hai chỗ ấy chạm
`changes.py`/`writer.py`, tức đường 409 và H1 của bước 7, nên khi đó phải chạy **đầy đủ** lại một lượt.
