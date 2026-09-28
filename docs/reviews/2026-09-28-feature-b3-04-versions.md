# Review merge feature/b3-04-versions → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `c7c903b4fb45`
- Cổng: phạm vi **đầy đủ** — lượt 1 của một nhánh đi review (`RULE-CODE.md` R-33b điều kiện 1);
  `bash tools/verify/run.sh verify` mã thoát **0**, 8/8 bước `đạt` (log: `verify-review-1.log`,
  worktree review, container `verify-run` riêng — đếm trước khi chạy: 1 container đang chạy < trần 2)
- Độ phủ (đo lại trong lượt này, không chép của tác giả): tổng dòng **99,54%** · nhánh **98,50%** ·
  `apps/api/versions` 100,00% / 100,00% · `packages/db` 96,66% / 95,76% · tập file bị chạm 100,00% / 100,00%
- Test: **5336 passed**, 7 deselected, 0 failed (24 ph 23 s); `apps/api/versions` 163 test
- `case_gate`: 5 `op` mới đều `đạt`, thiếu = **0** (`versions_restore_version` miễn C16 đúng `cases.toml`)
- Bước 7: H1 `đạt` 1377 mẫu · H1 ngữ cảnh `đạt` 59 mẫu · H3 `đạt` · H4 **không áp dụng** (B3-05 chưa hợp
  nhất, chưa có `apps.api.rules.catalog` — đúng luật BE-00 §12) · H5 `đạt`. Bước 6: `lint_migrations` 14
  revision, `migrate_check` 10/10 (kể cả `downgrade base` và "tên CHECK khớp model")

## Phạm vi đã đọc

`git diff main...HEAD` = 23 file, +3710 dòng, **0 dòng xoá**: `apps/api/versions/**` (975 dòng sản phẩm,
2227 dòng test), `packages/db/models/versions.py`, revision `r20260928_b3_04_versions.py`, `changes/B3-04.md`,
và commit `docs(contract)` của người điều phối làm mới `docs/contracts/openapi.json`.

8 commit, dòng đầu đúng Conventional Commits, mỗi thân có trailer `Prompt: B3-04`; cây sạch ở `c7c903b`.
Không file cấm nào bị worker sửa: `docs/charter/*`, `docs/contracts.toml`, `uv.lock`, `tools/**`,
`conftest.py` gốc, `apps/api/{core,spatial_read,spatial_write,floors,projects,access}/**`, `packages/**`
ngoài `models/versions.py` — tất cả nguyên vẹn. Không `pragma: no cover`, không `type: ignore`, không
`# noqa` trần (một `# noqa: S603` có mã + lý do ở `tests/test_boundary.py:29`), không `skip`/`xfail`,
không `except Exception` rộng, không hàm > 50 dòng, docstring đủ ở mọi hàm mức module.

**`docs/contracts/openapi.json`** là file chỉ người điều phối sửa (BE-00 §2). Đã đối chiếu từng hunk
thay vì tin commit message: 508 dòng thêm, **0 dòng xoá**, đúng 4 hunk chèn — `CursorPage_FloorVersionSummaryOut_`,
`FloorVersionSnapshotOut` + `FloorVersionSummaryOut`, `VersionLabelIn`/`VersionOut`/`VersionRestoreIn`/
`VersionRestoreTargetIn`, và khối 5 đường `/api/projects/{project_id}/versions…`. Không mục nào có sẵn bị
đổi. Đây là đường hợp lệ của BE-00 §12 bước 8 (người điều phối cập nhật trong chính lần gộp đổi API), không
phải worker sửa file cấm → **không** là điều kiện dừng sớm.

## Đối chiếu báo cáo tác giả

Mọi số trong `R/REPORT.md` và `bao-cao-r.md` đã tự kiểm lại bằng log của chính lượt verify này và khớp
đúng từng con số (mã thoát, 8/8, 5336 passed, 99,54 / 98,50, versions 100/100, case_gate thiếu 0,
H4 không áp dụng). Hai mục "Lệch khỏi prompt" — `rescale_*` ở `packages/domain/scale/rescale.py` chứ không
`packages/domain/spatial`, và `VersionsSettings` nằm trong `snapshots.py` chứ không có `settings.py` — đều
đúng `dinh-chinh.md` §1.1 và §1.2 (đính chính thắng prompt): **chấp nhận, không thành finding**.

## Soát trọng tâm (kết quả)

- **`create_version` / K18.** `lock_floor_document` (`snapshots.py:186`) khoá đúng thứ tự BE-00 §7:
  `floors … FOR SHARE` với `deleted_at IS NULL` (thiếu → `NOT_FOUND resource="floor"`) → `load_document(for_update=True)`
  → `None` thì `ensure_document` rồi khoá lại; chỉ sau đó mới chạm `versions`. Không chỗ nào khoá
  `floor_documents` trước `floors`. Bản mới nhất có `floor_revision == doc.revision` → trả bản đó, không chèn
  (`:238`). `sequence = max + 1` an toàn khi hai giao dịch đua trên tầng **chưa có** tài liệu: `ensure_document`
  dùng `ON CONFLICT DO NOTHING` nên lượt sau chặn ở unique index, rồi `load_document(for_update=True)` lần hai
  nối đuôi — test `test_create_version__parallel_on_floor_without_document` chạy hai giao dịch thật và ra một
  dòng duy nhất. Gỡ ảnh chụp đúng `sequence <= sequence - keep` và chỉ `SET snapshot = NULL` (`:279-290`),
  không câu nào xoá dòng `versions`. `ValueError` ở bước 1 (`_check_actor:202`) trước mọi truy vấn.
  `snapshots.py`, `messages.py`, `errors.py` nhập được khi `fastapi`/`starlette`/`jwt`/`argon2` bị chặn —
  `test_boundary.py` kiểm ở **tiến trình con**, đúng cách duy nhất phép kiểm này có nghĩa.
- **Ảnh chụp.** `snapshot_of` dựng JSON lồng của [5], `scaleMmPerPx` vắng khi NULL. `decode_snapshot`
  không `model_validate` tự chế: mọi giải mã đi qua `codec.document_from_json`; `schemaVersion` lệch, thiếu
  `document`, khoá lạ (`DocumentCorruptError`), `scaleMmPerPx` không phải chuỗi số dương hữu hạn → log
  `snapshot_schema_mismatch` kèm `version_id` rồi `None`; `raw is None` → `None` **không** log. Người gọi
  (`_load_snapshot`, `service.py:115`) đổi cả hai thành 422 `VERSION_SNAPSHOT_PURGED`, không đường nào ra 500.
- **N19 thứ tự bước 1–9.** Đúng từng bước: `require_project("layer.edit")` là dependency nên 428 và Pydantic
  chạy **sau** kiểm quyền; 404 `resource:"version"` → `VERSION_FLOOR_MISMATCH` `field:"body.floorId"` → khoá →
  **C09b trước kiểm ảnh chụp** (`_replayed:179`, đúng 4 điều kiện `restored_from_id`/`creator_id`/`floor_revision`/
  `restore_base_revision`, trả 200 qua `response.status_code`) → `baseVersion > doc.revision` → 422 `field:"baseVersion"`
  → PURGED → bản "trước" → tính lại tỉ lệ → `write_layer` → bản "sau" → nhật ký. Không tự so `baseVersion`
  rồi ghi (K07): `write_layer` giữ việc đó, `VersionConflictError` lan nguyên ra. Rollback cả bản "trước"
  được `AppRoute` bảo đảm (`core/routing.py:300-301` rollback trên ngoại lệ) và hai test đọc lại bằng session
  mới chứng minh (409 còn 2 bản, `RescaleError` còn 1 bản). Không câu nào tự `UPDATE floor_documents` hay chèn
  `floor_change_log`. `restored_from_id`/`restore_base_revision` chỉ xuất hiện ở bản "sau".
- **N17.** `summary_query()` không bao giờ chọn cột `snapshot` — chỉ `snapshot IS NOT NULL AS has_snapshot`;
  hai test chốt bằng `before_cursor_execute` trên SQL thật (một ở tầng truy vấn, một qua HTTP). Cursor ký
  `{"floorId": floor_id}` nên cursor tầng A dùng cho tầng B ra `CURSOR_INVALID`. `limit` 1..200 mặc định 50
  do `page_params(max_limit=200)`. `ORDER BY sequence DESC`, `nextCursor` chỉ khi còn dòng.
- **N20.** `normalize_label` NFC → `strip` → đo **đơn vị UTF-16** (`len(...encode("utf-16-le")) // 2`) như zod,
  chặn `Cc`/`Cf`; rỗng sau chuẩn hoá → `NULL`. `_locate(for_update=True)` khoá **chỉ** dòng `versions` (`of=`),
  không đảo thứ tự khoá. Nhãn không đổi → 200 không ghi, không nhật ký. Không sinh phiên bản, không đổi
  `revision`, không `touch_project` — có test đọc lại `floor_documents` và đếm dòng `versions`.
- **Dây (K01/K02).** So từng trường với `AppFront/src/api/schemas/versions.ts` và `VersionSchema` cũ
  (`index.ts:190-208`): `FloorVersionSummaryOut` khớp đủ 9 trường và miền (`label` 1–60, `note` ≥ 1,
  `floorRevision` ≥ 0, `sequence` > 0); `FloorVersionSnapshotOut` khớp `.strict()` ba khoá; `VersionRestoreIn`
  khớp `VersionedWriteSchema` (`baseVersion` int ≥ 0 + `body` + strict); `VersionLabelIn` khớp
  `z.string().trim().max(60)`; `VersionOut` **đúng sáu** trường cũ (`creatorId: z.string().min(1)` nên literal
  `system:pipeline` hợp lệ). Khoá tuỳ chọn vắng thật (C17 có test cho cả 4 op). K08 người ngoài → 404
  `resource:"project"`; `viewer` → 403 ở cả N19 và N20.
- **Model / revision.** CHECK đủ 6, FK `floors.pk` và `projects.id` đều `ON DELETE CASCADE`, unique
  `(floor_pk, sequence)`; `creator_id` **nhập lại** `CHANGED_BY_RE` chứ không chép regex. Revision expand
  thuần (một `create_table`), `downgrade` bỏ bảng, tên ràng buộc bọc `op.f(...)` nên không lặp tiền tố như
  NO-057; `migrate_check` xác nhận "tên CHECK khớp model". Miền DB chặt hơn miền dây ở đúng hướng an toàn:
  `char_length ≤ 60` (điểm mã) luôn nới hơn 60 đơn vị UTF-16, nên không có đường nào nhãn qua được service
  mà vỡ CHECK (không có 500 ẩn).
- **Test (K22/K23).** Postgres thật ở mọi test dịch vụ, không mock session, không mock `write_layer`.
  C14 là hai request **đồng thời thật** trên app thật (mỗi request một session/giao dịch riêng của
  `api_client`), kết quả `[201, 409]`, `revision` +1 đúng 1, đúng một bản "sau". Test lưu giữ và C09b sau khi
  bản nguồn bị chính lượt phục hồi đẩy khỏi trần đều có thật và khẳng định đúng thứ hai. C01 của #36 và N20
  là so **toàn thân** (`==` cả dict), không chỉ vài khoá.
- **R-01/R-07/MNT-01.** Docstring đủ, nói lý do chứ không kể lại code. Không hàm > 50 dòng, `ruff` (C901 trong
  bước 2) xanh. Helper test không có bản thứ hai của `make_scene`/`write`/`headers_of`/`spatial_write` —
  đều nhập lại của B3-02/B3-03.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | MNT-05 | Nhánh 975 dòng sản phẩm + 2227 dòng test > 400 dòng logic | cả nhánh | Chấp nhận như NO-221 (B3-02) và NO-234 (B3-03): khối [10] là một đơn vị bàn giao (7 module + model + revision + `cases.toml` + test) mà B5-06b và F-08 cùng chờ; tách ra sẽ để `create_version` và 5 route ở hai nhánh không tự kiểm được nhau. Đường nâng cấp: prompt cỡ này tách theo nhóm (lõi chụp ↔ route) ngay ở bản prompt. **Nên có một dòng `NO-<nnn>` trong `DEBT.md`** |
| 2 | P3 | API-02 | `RescaleError` → `VALIDATION.error(count=1)`: `count` được BE-00 §4 (dòng 201) và `ApiErrorBodySchema` của FE định nghĩa là **số lỗi Pydantic**, còn đây không phải lỗi Pydantic và không kèm `field` — FE nhận `{code: "VALIDATION", count: 1}` không chỉ được chỗ nào sai | `apps/api/versions/service.py:214` | `VALIDATION.error()` trần (đúng tiền lệ `apps/api/drawings/complete.py:181`), hoặc kèm `field` trỏ đúng chỗ. Không chặn merge: `count` là khoá tuỳ chọn nên zod của FE vẫn parse được |
| 3 | P3 | PERF-01 | Mỗi lần chèn phiên bản tốn một truy vấn `SELECT floors.project_id` riêng, trong khi `lock_floor_document` vừa đọc đúng dòng `floors` ấy (chỉ lấy `pk`) — một roundtrip thừa mỗi lượt chụp, không phải N+1 | `apps/api/versions/snapshots.py:244` (kèm `:192`) | Cho `lock_floor_document` trả luôn `project_id` (hoặc `select(FloorRow.pk, FloorRow.project_id)`) và truyền xuống `record_version` |

**Nit** (không chặn merge, không tính điểm):

- `snapshots.py:208` `if note is not None and note == ""` rút gọn được thành `if note == ""`. Ghi chú thêm:
  `note` chỉ có khoảng trắng (`"  "`) lọt qua bước 1 và được lưu; không người gọi nào trong repo gửi như thế,
  và prompt chỉ đòi "`note` rỗng", nên đây là nhận xét chứ không phải lệch spec.
- `tests/_helpers.py:56` `make_version_scene` và `tests/_route_helpers.py:154` `make_stage` đều là vỏ mỏng của
  `make_scene`. Trùng lặp có lý do đứng được: `dinh-chinh.md` §3 cấm R sửa `_helpers.py` của D, và hai vỏ này
  cần hai thứ khác nhau (tài liệu + tỉ lệ + tên người ghi ‖ nhiều tầng + thành viên).
- `test_routes_restore.py:369` và `test_routes_list.py:265` có `print(...)`. Đúng yêu cầu [11] mục 4 của prompt
  (in kết quả C14 và test lưu giữ), nên giữ.

Không finding P0, không finding P1. Không nợ `P0`/`P1` nào đang mở thuộc `apps/api/versions` hay
`packages/db/models` chặn nhánh này.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 4 | 0,40 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 4 | 0,40 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,74 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1, điểm 4,74 ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

Nhánh làm đúng phần khó nhất của prompt và làm đúng vì lý do đúng, không vì trùng hợp: thứ tự khoá
`floors FOR SHARE → floor_documents FOR UPDATE → versions` giữ nguyên ở cả `create_version` và N19; C09b đặt
**trước** kiểm ảnh chụp nên lượt gửi lại vẫn 200 kể cả khi chính lượt đầu đã đẩy bản nguồn khỏi trần lưu giữ
(có test dựng đúng tình huống đó); `baseVersion` để `write_layer` so chứ không so bằng Python (K07), nên 409
luôn mang `remoteChanges` ≥ 1 và bản "trước" biến mất cùng giao dịch; N17 không bao giờ kéo cột `snapshot` về
và điều đó được chốt bằng SQL thật chứ bằng lời hứa. Cổng đầy đủ xanh với mã thoát thật, độ phủ
`apps/api/versions` 100% dòng và 100% nhánh, `case_gate` thiếu 0 cho cả 5 `op`.

Ba finding còn lại không chặn merge: một là kích thước nhánh (đã có hai tiền lệ chấp nhận cho cùng lý do),
hai là chi tiết nhỏ có thể sửa trong một FIX gộp sau — `count=1` không sai hợp đồng (khoá tuỳ chọn) mà sai
ngữ nghĩa, và một truy vấn thừa mỗi lượt chụp. Đề nghị người điều phối ghi một dòng `DEBT.md` cho MNT-05
theo mẫu NO-221/NO-234 khi gộp.

Merge thuộc phiên gọi review này; phiên /merge-review không tự merge.
