# Review merge feature/b2-03-floors → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `0ec239309bd3`
- Base: `main` `34464a1` · 9 commit (4 merge, 4 feat/test của B2-03, 1 FIX-082) · 32 file / 4204 dòng thêm, 6 dòng xoá
- Phạm vi: `apps/api/floors/**`, `packages/db/models/floors.py`, revision `r20260923_b2_03`,
  `packages/testing/factories/floors.py`, `changes/B2-03.md` — **đúng** cột "Sở hữu" của B2-03; cộng commit
  FIX-082 (`43aa062`) chỉ chạm `apps/api/projects/tests/{test_parts,test_routes_write}.py`, được uỷ quyền ở
  `docs/fixes.md` mục FIX-082 trên `main` (ngoại lệ K27 như FIX-003..005)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** — chạy lại tại chỗ trong worktree review, **không** dùng
  lại log tác giả
- Độ phủ (`tools/coverage_gate` thật): tổng dòng 99,12% · nhánh 97,69%; `apps/api/floors` dòng 99,59% ·
  nhánh 100,00%; tập file bị chạm dòng 99,62% · nhánh 100,00%
- Loại task (RULE.md §6): **Nghiệp vụ có tranh chấp + migration + hợp đồng FE** — 5 route ghi/đọc có khoá,
  resolver đường phẳng, lịch dọn nền, bảng mới

## 1. Bảng cổng (E.10, mã thoát thật của phiên review)

| # | Bước | Trạng thái | Ghi chú |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | `apps.api.floors.jobs` không kéo `starlette` (nhờ `locks.py`) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | **3646 passed · 0 failed · 0 skipped · 4 deselected** (661 s) |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; `case_gate` 21 thao tác đã mount, 0 "HỎNG" |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, **đúng 1 head**; up/down/up, model khớp DB, tên CHECK khớp |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H1 628 mẫu response; H4 `không áp dụng` (B3-05 chưa hợp nhất — đúng BE-00 §12) |
| 8 | `openapi` | đạt | `/tmp/openapi.json` 49219 byte (nhánh feature, không ghi vào repo) |

`case_gate` cho 5 `op` của tầng đều `đạt`; `floors_delete_floor` và `floors_reorder_floors` thiếu C16 đúng
theo `waive` trong `cases.toml` (DELETE không thân / thân chỉ có id tầng — lý do đứng được). Task
`purge_deleted_floors` không có dòng "HỎNG task": `__J01`, `__J06` đều có mặt và đạt.

**Mọi con số tác giả báo đều khớp lần chạy độc lập này**, trừ hai sai lệch vô hại: tổng nhánh 97,69% (tác giả
ghi 97,65%) và 3646 passed (tác giả ghi 3644) — `main` đã tiến thêm một commit tài liệu kể từ lượt của tác giả.

## 2. Đối chiếu báo cáo tác giả (không tin, tự kiểm)

| Khẳng định của tác giả | Kết quả kiểm |
|---|---|
| 8/8 bước đạt, mã thoát 0 | **đúng** (chạy lại, EXIT=0) |
| `apps/api/floors` 99,59% dòng / 100% nhánh | **đúng** |
| C14 #10 → `{201, 409}`, một dòng sống | **đúng** — `test_floors_create_floor__C14` dùng **hai client thật** (`make_api_client` × 2, `asyncio.gather`), `live_floor_row` là `scalar_one_or_none` nên >1 dòng sẽ hỏng test |
| Số truy vấn #12 với 3 và 30 tầng bằng nhau | **đúng** — `count_sql` so hai lượt, một câu `floors ⟕ project_floor_summaries` |
| "Khoá tư vấn dùng chung qua `locks.py` thay vì chép" | **đúng** — `jobs.py:29` và `lookup.py:17` cùng nhập `apps.api.floors.locks`; R-07 đã giải quyết, không còn bản chép |
| "Không có nợ mới ngoài hai điểm đã đóng" | **sai một phần** → finding #2: nợ `new_ulid` mà chính mã và báo cáo nói "ghi nợ" **không có dòng nào** trong `DEBT.md` |
| NO-137 (C10/C22 với `access`) xanh có lý do | **đúng** — `_idempotency_guard` chạy sau dependency quyền và trước thân handler, nên `access.project_id` không bị đọc; C10/C22 của hai op đều đạt trong lượt này |
| FIX-082 "không nới, không xoá assert" | **gần đúng** → Nit #7: `test_default_app_falls_back_to_discover` vẫn bắt được lỗi fallback nhưng yếu hơn bản cũ; nhánh "không ai cài" vẫn được kiểm tường minh ở `test_routes_write.py` (`extensions.override(app, SUBMODULE, [])`) |

## 3. Soát trọng tâm (kết quả)

**K08 / §4 / §5 — đường phẳng, 404 trước 403:** đạt. `project_of_floor` kiểm mẫu `{floor_id}` trước
(`resolvers.py:57`) → 404 `resource:"floor"`; `_member_floor_projects` join `project_memberships` nên tầng của
dự án người gọi **không** là thành viên không được đếm (không lộ tồn tại) — có test cả hai chiều
(`__C06`, `__shared_id_resolves_to_the_only_member_project`); admin hệ thống ngoài dự án → 404;
`FLOOR_ID_AMBIGUOUS` đúng khi > 1 dự án; `project_of_floor_list` đọc `await request.json()` và bắt
`JSONDecodeError`/`UnicodeDecodeError`/`ValueError` → 422 `field:"floorIds"` (có test `Content-Type: text/plain`,
mảng trần, rỗng, trùng id); `viewer` → 403 ở cả 4 route ghi. Resolver chạy **một** truy vấn.

**CON-01 / CON-07 — khoá và bất biến:** đạt. Cả `create_floor`, `delete_floor`, `reorder_floors`,
`patch_floor` và `_delete_row` của lịch dọn đều mở bằng `lock_project_floors` rồi mới `FOR UPDATE` theo `pk`
→ `summaries.*` → `touch_project` cuối (BE-00 §7). Mọi bất biến (trùng id, trần tầng, tập tầng #13) kiểm **sau**
khoá tư vấn. `unique_violation` là hàng phòng thủ thứ hai của #10 → 409 (`_raise_taken_if_unique_violation`,
có test gọi thẳng `_insert_floor` hai lần). Reorder khoá mọi dòng `ORDER BY pk`, delete khoá một dòng, cả hai
sau cùng một khoá tư vấn → không deadlock; có test đua thật `__concurrent_with_delete_does_not_500`.

**LOG — khôi phục, làm tròn, chuẩn hoá:** đạt. Khôi phục trong `FLOOR_RESTORE_WINDOW_S` giữ `pk`, gọi
`register_floor(restored=True)`, bảng đếm `walls_total=5` giữ nguyên và hết `hidden` (test 9 phút / 11 phút);
khôi phục khi đủ trần → 422 (`_check_not_over_limit` chạy **trước** bước khôi phục). #34 `{}` hoặc giá trị trùng
→ 200, không ghi, không nhật ký, `projects.updatedAt` không đổi (có assert). `id` khác đường →
`PATH_BODY_MISMATCH`. `clean_mm` từ chối `bool`/chuỗi/`NaN`/`inf`, làm tròn khi lệch ≤ 0,01 và 422 khi lệch hơn;
`clean_name` NFC sau `strip`, cấm Cc và U+202A–202E / U+2066–2069; `areaM2` là `float(round(Decimal, 2))`
(48,60 → 48,6, `NULL` → vắng); `drawings` luôn có khoá.

**Hook #25:** đạt. `create_project_floors` kiểm **lại** tên và dải bằng đúng hai hàm thuần của `schemas.py`
(R-07, không tin bên gọi), lỗi → `floors.<i>.<khoá camelCase>` và rollback cả #25 — test đi qua HTTP #25 thật
với `view_parts.py` thật, xác nhận không còn dự án lẫn tầng nào. `new_level_id` = `"L-" + new_id("job", …)`
tách phần ULID: chấp nhận được (80 bit `secrets`, khớp `is_spatial_id`), đã có comment R-05 nêu đường nâng cấp
và được `dinh-chinh.md` §7 chốt — nhưng nợ kèm theo chưa ghi (finding #2).

**PERF-01/05/06:** đạt. `floor_outs`, `floor_outs_by_project`, `load_project_floors` dùng chung `_load_floor_outs`:
một truy vấn `floors ⟕ project_floor_summaries` cho cả lô + đúng một lượt `view_part(FLOOR_DRAWINGS)`; số câu
SQL không đổi theo số tầng (test) và theo số dự án (lô `project_ids`). `groupby` Python của resolver có trần:
`floorIds` bị chặn 1..`FLOORS_MAX` **trước** khi truy vấn, nên tập kết quả bị chặn theo số dự án chứa các id đó.

**Lịch dọn (K36):** đạt. Ba session ngắn, `delete_prefix` gọi **ngoài** mọi giao dịch; object chỉ xoá khi không
còn dòng anh em cùng `(project_id, level_id)`; `DELETE … AND deleted_at < :cutoff` nên tầng khôi phục giữa chừng
không bị xoá (có test); `purge_floor` trong **cùng** giao dịch sau khi tính lại cờ; `except AppError` (không
`except Exception`) giữ dòng và log `floor_purge_failed` kèm `pk` — test dùng MinIO thật rồi **dừng container**,
không mock; phân trang keyset `pk > after` nên không lặp vô hạn (đúng bài học NO-138).

**Migration (DB-01..05):** đạt. Expand thuần một bảng mới, FK CASCADE, 5 CHECK, `uq_floors_level` một phần và
đúng 3 index một phần theo [5]; `downgrade` có; `down_revision = r20260923_b1_03` giữ chuỗi tuyến tính, 1 head;
`migrate_check` chạy đủ up/down/up và "model khớp DB".

**RULE-CODE:** R-08 đạt (không hàm nào > 50 dòng); R-07 đạt (luật tên/mm dùng chung giữa `schemas.py` và
`view_parts.py`, khoá tư vấn dùng chung qua `locks.py`); `# noqa: S603` duy nhất có mã và lý do; **không** có
`pragma: no cover`, `type: ignore`, `skip`/`xfail`, không hạ ngưỡng. R-01 thiếu ở 7 hàm trợ giúp trong test
(finding #6). Mọi commit đúng mẫu Conventional Commits ≤ 72 ký tự, có trailer `Prompt:`; FIX-082 là commit riêng
mang cả `Prompt: B2-01` và `Fix: FIX-082` — vào `main` phải `--no-ff` để giữ trailer của cả hai prompt.

## 4. Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | API-04 · R-11 | `FloorReorderIn` khai là "chỉ cho OpenAPI" nhưng **không route nào tham chiếu** nó, nên `PATCH /api/floors/reorder` ra `openapi.json` **không có `requestBody`**: thân #13 của hợp đồng FE không được tài liệu hoá, và lớp này là dead code chỉ còn một test tự nuôi. Không cổng nào bắt (không cổng nào soi `requestBody`). | `apps/api/floors/schemas.py:114-117`, `apps/api/floors/router.py:52-60` | Nhận `body: FloorReorderIn` ở handler (an toàn: `dependencies`/`access` chạy trước nên lỗi resolver vẫn thắng) hoặc khai `openapi_extra`; nếu không dùng thì xoá cả lớp lẫn test |
| 2 | **P2** | MNT-03 · R-34 | Nợ được nêu trong **mã** (`"đường nâng cấp là thêm new_ulid vào B0-02 (ghi nợ)"`) và trong báo cáo, nhưng `DEBT.md` **không có dòng nào** của B2-03 | `apps/api/floors/lookup.py:110-116`; `DEBT.md` | Thêm `NO-<nnn>` (chủ B0-02: thêm `new_ulid`) trước khi merge; ghi luôn finding #3 |
| 3 | P3 | PERF-03 | Cờ "còn dòng anh em" của lịch dọn tra `(project_id, level_id)` **không lọc `deleted_at`**, nhưng cả ba index của bảng đều là index **một phần** → mỗi ứng viên là một seq scan `floors` (hai chỗ: cột phụ `EXISTS` của lô và lượt tính lại trong giao dịch xoá) | `apps/api/floors/jobs.py:56-65`, `:103-108` | Ghi nợ; revision sau thêm index đầy đủ `(project_id, level_id)`. **Không sửa ở nhánh này** — [5] chốt đúng 3 index |
| 4 | P3 | LOG-02 | `_restorable` lấy dòng **đầu tiên** còn trong cửa sổ chứ không phải dòng xoá **gần nhất** như [6] bước 4 yêu cầu; `_locked_rows` không có `ORDER BY` nên thứ tự do DB quyết | `apps/api/floors/service.py:30-33`, `:46-48` | `ORDER BY deleted_at DESC NULLS LAST, pk DESC` trong `_locked_rows`. Hôm nay chưa dựng được hai dòng cùng `(project_id, level_id)` cùng nằm trong cửa sổ, nên chưa phải lỗi thật — sửa để khỏi thành lỗi khi đổi `FLOOR_RESTORE_WINDOW_S` |
| 5 | P3 | MNT-04 | Hai tài liệu nói sai trạng thái nhánh đã gộp: `changes/B2-03.md` viết "**Chưa có** `router.py`/`schemas.py`/`service.py`… cổng case/golden của 5 `op` chưa áp dụng được"; docstring `_bodies.py` viết "Route, model, factory của B2-03 … **chưa tồn tại trên nhánh này**". Cả hai đều sai trên `0ec2393` (cổng đã chạy đủ cho 5 `op`). Không ảnh hưởng cổng — `tools/charter.py:merged_prompts` chỉ đọc **tên file**, không đọc nội dung | `changes/B2-03.md:6`, `apps/api/floors/tests/_bodies.py:3-7` | Viết lại hai đoạn cho khớp trạng thái đã gộp |
| 6 | P3 | TEST-02 · R-01 | 7 hàm trợ giúp trong test không có docstring, trong khi mọi hàm khác của nhánh (kể cả helper test như `_marker_key`, `_row_exists`) đều có | `test_jobs.py:52,69,79,280,307`; `test_lookup.py:123`; `test_schemas.py:21` | Thêm một câu cho mỗi hàm |
| 7 | Nit | TEST-02 | FIX-082: `test_default_app_falls_back_to_discover` nay so `resolve(None,…)` với `discover(…)` — vẫn hỏng nếu `resolve` không fallback (vì `discover()` giờ khác rỗng), nhưng sẽ thành rỗng nghĩa nếu về sau không module nào cài `view_parts.py` | `apps/api/projects/tests/test_parts.py:85-89` | Neo thêm một khẳng định (ví dụ `PROJECT_FLOORS` có trong kết quả `discover`) |
| 8 | Nit | TEST-02 | C14 của #10 chỉ khẳng định `{201, 409}`, không khẳng định `code == "FLOOR_ID_TAKEN"` cho lượt thua | `apps/api/floors/tests/test_routes_create.py` (`__C14`) | Thêm assert `code` |

Không có finding **P0** hay **P1**.

## 5. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 4 | 0,60 |
| PERF – Hiệu năng | 10% | 4 | 0,40 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 3 | 0,30 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,42 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1; điểm 4,42 ≥ 4,0. Cổng đầy đủ xanh 8/8 với mã thoát thật 0 trên chính sha `0ec2393`, độ phủ
mọi gói bị chạm và tổng đều vượt xa sàn 90/90. Nghiệp vụ khớp [6] ở mọi điểm tôi soát được: thứ tự khoá BE-00 §7
đúng ở cả 4 route ghi lẫn lịch dọn, bất biến kiểm sau khoá tư vấn, 404-trước-403 và "không lộ tồn tại" của đường
phẳng đúng K08, lịch dọn không giữ kết nối khi gọi kho và không lặp vô hạn, migration expand thuần một head.
Test là loại tốt: đua thật bằng hai client HTTP, MinIO thật bị dừng giữa chừng, đọc lại qua session mới, không
một mock dịch vụ nào. FIX-082 nằm đúng phạm vi được uỷ quyền, commit riêng, giữ được nhánh "không ai cài" ở
`test_routes_write.py`.

**Điều kiện kèm theo (không chặn merge, nhưng phải làm cùng lúc gộp):**

1. Ghi `DEBT.md` — finding #2 (nợ `new_ulid` cho B0-02, tác giả đã hứa trong mã), finding #1 (thân #13 vắng
   trong `openapi.json`), finding #3 (index `(project_id, level_id)` cho lịch dọn), finding #4, #5, #6.
   Nhánh này **không** có dòng `DEBT.md` nào, nên R-34 đang hở.
2. Vào `main` bằng `git merge --no-ff` để giữ trailer của **cả hai** prompt (`Prompt: B2-03` và
   `Prompt: B2-01` + `Fix: FIX-082`), đúng như `docs/fixes.md` mục FIX-082 đã chốt.
3. Sau merge, nhớ xuất `openapi.json` ra gốc repo trước khi chạy bước 8 của `main`.
