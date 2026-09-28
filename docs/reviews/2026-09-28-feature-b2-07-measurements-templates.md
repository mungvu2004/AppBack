# Review merge feature/b2-07-measurements-templates → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `13e7ecb86eaa`
- Gốc nhánh: `6991e00` (`feat(library): merge b2-06`); commit sẽ vào main: `df5e0e4`, `05366c7`, `13e7ecb`
- Cổng: phạm vi **đầy đủ** — lượt đầu của nhánh đi review (R-33b điều kiện 1; diff còn thêm/xoá file `.py`, chạm
  `packages/db/**` và `docs/contracts/**`, và thêm route mới → thêm điều kiện 2, 3, 5).
  `bash tools/verify/run.sh verify` **mã thoát 0**
  (log: `F:/AppBack/backend/dieu-phoi/chay/B2-07/R/full-review.log`, tự chạy trong worktree review @ `13e7ecb`).
- Độ phủ (lượt đầy đủ, `coverage_gate` đạt): tổng dòng **99,54%** · nhánh **98,45%** ·
  `apps/api/measurements` 100,00%/96,15% · `apps/api/templates` 100,00%/100,00% ·
  `packages/db` 96,72%/95,76% · tập file bị chạm 100,00%/96,43%. Mọi con số ≥ 90/90.
- Test: **5300 passed, 0 failed, 7 deselected**, 1258 s. Không `pragma: no cover`, không `noqa` trần,
  không `type: ignore`, không `skip`/`xfail` mới, không hạ ngưỡng (K24 sạch).

## Bảng cổng (in từ mã thoát thật)

| Bước | Lệnh | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 5300 passed, 0 failed, 7 deselected, 1258 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; `case_gate: đạt` |
| 6 | `lint_migrations` → `migrate_check` | đạt | 14 revision, đúng 1 head (trên nhánh), model khớp DB, tên CHECK khớp model |
| 7 | `tools.contract.check` (H1 H3 H4 H5) | đạt | xem bảng con |
| 8 | `openapi` | đạt | |

Bảng con bước 7 (AppFront @ `9cf0b0bfffbd`): Smoke đạt (23 module, 83 mục) · Bản đồ đủ đạt (83/83) ·
Thao tác đã mount đạt (60/83) · **H1 đạt (1372 mẫu response)** · H1 ngữ cảnh đạt (50) · H3 đạt (10 khoá, 3 vai) ·
H4 **không áp dụng** (B3-05 chưa hợp nhất — đúng luật BE-00 §12, không phải "hỏng") · H5 đạt (4 khung SSE).

`case_gate` cho 5 `op` của B2-07 (trích nguyên log, thiếu = 0):

| op | bắt buộc | tìm thấy | thiếu |
|---|---|---|---|
| `measurements_list_records` | 10 | 10 | 0 |
| `measurements_create_record` | 16 (gồm C14) | 16 | 0 |
| `measurements_delete_record` | 12 | 11 | 0 — miễn đúng một C16 (`cases.toml`) |
| `templates_list_templates` | 10 | 10 | 0 |
| `templates_create_template` | 15 | 15 | 0 |

## Đối chiếu trọng tâm (tự kiểm trên diff, không lấy từ báo cáo tác giả)

- **Dây (K01/K02, W2–W4, W22).** `MeasurementRecord` = `{id, name, mode, points, rawValueMm}` khớp
  `AppFront/src/api/schemas/measurements.ts` `.strict()`; `PropertyTemplate` = 7 khoá đúng thứ tự
  `{id, name, projectId, createdAt, scope, objectKind, fields}` khớp `propertyTemplates.ts`. Không có
  `body_sha256`/`createdBy`/`updatedAt` trên dây (`service.py:63-73`, `templates/schemas.py:91-131`). `z` vắng thì
  vắng khoá (`WireModel._drop_none` cộng `_point` bỏ `z` khi `None`), `z: null` vào → 422 (`NullFreeModel`).
  `fields` vắng khoá nào vẫn vắng (`model_dump(exclude_none=True)` lúc lưu, model ra bỏ `None`). `createdAt` là
  `WireDatetime` → `.sssZ` (test chốt bằng regex). Hai danh sách là mảng trần. #18 khai `status_code=204`, trả
  `None`; test khẳng định `content == b""`.
- **Vào (`WireRequest`).** `extra="forbid"` ở mọi độ sâu (`points[i]`, `fields`) — có test cho gốc, `points[0]`,
  `fields`. Số thực `Annotated[float, Field(strict=True, allow_inf_nan=False)]`: nhận `1000` nguyên, từ chối
  `bool`/chuỗi/`NaN`/`Infinity`, **kể cả `NaN`/`Infinity` thô** gửi qua `post_raw`. mm của khuôn là
  `Annotated[int, Field(strict=True, …)]` (tương đương `StrictInt`: từ chối `bool`, `1.5`, `"100"`). `id` qua
  `is_measurement_id` (`^MS-[0-9]{4,15}$`, `fullmatch`) → 422 `field:"id"`; có test biên 15 chữ số nhận, 16 chữ số
  từ chối. `name` qua `clean_label`: `nfc(strip)`, 1–120, chặn Cc và U+202A–202E/U+2066–2069. `id`, `projectId`,
  `createdAt`, `scope` trong thân khuôn → 422. Union phân biệt theo `objectKind`.
- **Đồng thời & khoá (BE-00 §7).** `lock_project_scope` chạy
  `pg_advisory_xact_lock(hashtextextended('measurements:'|'templates:' || project_id, 0))` **trước** mọi kiểm trùng
  và mọi kiểm trần (`measurements/service.py:114`, `templates/service.py:54`); `SELECT … FOR UPDATE` cho dòng id
  (`measurements/service.py:120`); `touch_project` là lời ghi **cuối** và không chạy khi 200/409/422 — chốt bằng
  `projects.updated_at`, không mock. C14 dùng **hai client HTTP thật** cộng `asyncio.gather`: cùng thân →
  `{201, 200}` một dòng; khác thân → `{201, 409 MEASUREMENT_ID_TAKEN field:"id"}` một dòng. Khuôn có thêm
  `lock_before_count` → `{201, 422}` một dòng. Trần tổng điểm dùng `SUM(jsonb_array_length(points))`, gộp chung một
  câu với `COUNT(*)`. Nhánh 200 trả **trước** `_check_room` nên gửi lại bản đã lưu vẫn 200 kể cả khi đã chạm trần —
  có test riêng cho cả trần số lượng lẫn trần tổng điểm.
- **Chuẩn hoá thân.** Đúng một hàm `normalize()` dùng cho **cả** lưu lẫn so; `_real` đổi `-0.0` → `0.0` (có test
  dây: gửi `-0.0` rồi gửi `0` → 200, không 409); `body_sha256` dùng
  `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)`. NFD → lưu NFC, gửi lại
  bản NFC → 200 (C16).
- **Quyền.** #16/#28 `require_project()`, #17/#18/#29 `require_project("layer.edit")`. Người ngoài dự án **kể cả
  admin hệ thống** → 404 `resource:"project"` (một truy vấn, K08); `viewer` → 403; `MS-0001` của dự án khác → 404
  `resource:"measurement"` và dòng gốc còn nguyên; `created_by` lấy từ `principal.user_id`, `createdBy` trong thân
  là khoá lạ → 422 (K05).
- **Migration.** Đúng **một** revision `r20260928_b2_07`, expand thuần (chỉ `create_table`/`create_index`), khớp
  model: PK `(project_id, measurement_id)` **không** partial, FK `ON DELETE CASCADE`, 4 CHECK của `measurements`,
  2 CHECK cộng index `(project_id, created_at, id)` của `property_templates`; `raw_value` **không** đuôi `_mm` và
  khai `info={"float_reason": …}`. `down_revision = r20260928_b2_06` = head của `main` **lúc cắt nhánh**.
  Bước 6 chạy đủ upgrade/downgrade/upgrade lại và "model khớp DB": đạt.
- **Sở hữu file.** Diff chỉ chạm `apps/api/measurements/**`, `apps/api/templates/**`,
  `packages/db/models/{measurements,templates}.py`, revision mới, `changes/B2-07.md` và
  `docs/contracts/openapi.json`. Không đụng `apps/api/projects/**`, `packages/testing/**`, `conftest.py`,
  `pyproject.toml`, `.importlinter`, `tools/**`, `docs/charter/*`, `uv.lock`, `openapi.json` gốc,
  `tools/contract/APPFRONT_SHA`. Không `conftest.py` lồng, không file cấu hình công cụ riêng.
- **Openapi.** Đối chiếu `6991e00:docs/contracts/openapi.json` với bản trên nhánh: **thêm đúng 3 path**
  (`…/measurements`, `…/measurements/{measurement_id}`, `…/property-templates`) cộng 16 schema của chúng;
  **không path nào bị xoá, không schema cũ nào bị đổi**. Đúng giới hạn đã giao.
- **Luật mã.** Mọi module, lớp, hàm (kể cả test) có docstring nói *vì sao*, không kể lại code (R-01, R-02); không
  hàm nào quá 50 dòng, không hàm nào cyclomatic quá 10 (R-08); `clean_label` và `lock_project_scope` viết **một**
  nơi, `templates` nhập lại, mẫu id dùng `is_measurement_id` của `packages.core.ids` thay vì regex chép tay
  (R-06, R-07); không `except Exception`, không biến module giữ dữ liệu (K22 — cấu hình đọc lười qua `@cache`, có
  hàm `reset_*_cache` chỉ cho test); không mock Postgres, mọi test dịch vụ chạy container thật (K23).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | DB-01 / R-33b(6) | Gốc nhánh (`6991e00`) đã cũ hơn `main`: `main` có thêm `e91b283 feat(versions): merge b3-04`. Hệ quả lúc gộp: (a) `r20260928_b2_07` và `r20260928_b3_04` **cùng** `down_revision = r20260928_b2_06` → **hai head** alembic; (b) `docs/contracts/openapi.json` bị cả hai nhánh sửa → xung đột, và bản trên nhánh thiếu 5 path `/versions` của B3-04; (c) cây sau gộp khác cây đã qua lượt đầy đủ. Không phải lỗi của tác giả (đúng head lúc cắt nhánh), nhưng bỏ qua thì `main` không xanh. | `packages/db/migrations/versions/r20260928_b2_07_measure_tpl.py:23`; `docs/contracts/openapi.json` | Người điều phối, **sau** squash: `run.sh merge-heads <tên>` → `run.sh openapi` trên `main` rồi chép ra `docs/contracts/openapi.json` (bản hợp nhất phải có **cả** 3 path B2-07 lẫn 5 path `/versions`) → commit `docs(contract)` → verify tích hợp đầy đủ (bước 8 chạy chế độ `--compare`). Không giải xung đột bằng tay, sinh lại. |
| 2 | **P2** | R-34 | Nợ tác giả nêu trong báo cáo (tiền tố nhánh union trong `field` của #29) **chưa có dòng nào trong `DEBT.md`**; tác giả bị cấm sửa `DEBT.md` theo giao việc nên nợ đang treo không chủ. | `backend/dieu-phoi/chay/B2-07/bao-cao-B2-07.md` mục "Nợ và việc chưa làm"; `DEBT.md` | Người điều phối thêm `NO-246`…`NO-248` (nội dung ở mục "Nợ nên ghi" dưới) **trước** khi merge (R-38). |
| 3 | **P3** | TEST-04 | `assert elapsed < 2.0` là khẳng định theo **đồng hồ tường**, và test không mang mark `perf` nên chạy ở bước 5 cùng lúc với tối đa 2 container `verify-run` trên một máy (ENV §4) → có thể đỏ giả khi máy tải nặng. Prompt [8] đòi phép đo này nên không bỏ được. | `apps/api/measurements/tests/test_routes_read_delete.py:155` | Gắn `@pytest.mark.perf` để nó chạy ở bước 5b (đo riêng, `case_gate` vẫn đọc vết), hoặc nới trần kèm ngưỡng ghi trong docstring. Ghi `DEBT.md`. |
| 4 | **P3** | MNT-02 / R-10 | `lock_project_scope` là tiện ích khoá tư vấn **theo dự án nói chung** nhưng đặt trong `apps/api/measurements/`; `apps/api/templates/service.py:13` nhập chéo module anh em. Hai module cùng một prompt nên hôm nay chấp nhận được (tác giả đã ghi "Lệch khỏi prompt", lý do R-07 đứng vững), nhưng module thứ ba sẽ phải nhập từ một module không liên quan. | `apps/api/measurements/locks.py:7`; `apps/api/templates/service.py:13` | Khi có người dùng thứ ba: chuyển sang `packages/db/` (chủ B0-03), cập nhật BE-00 §2.2. Ghi `DEBT.md`. |
| 5 | Nit | API-03 | 422 của #29 mang tên nhánh union trong `field` (`wall.fields.heightMm`); `objectKind` lạ thì không có `field`. Đúng BE-00 §4 ("`field` = đường chấm của lỗi đầu tiên") nên **không** phải vi phạm, nhưng FE khó ánh xạ về ô nhập. | `apps/api/core/errors.py:104` (`field_of`) | Nợ của B0-06; tác giả nêu đúng và không sửa trong nhánh này (K27). Cùng lớp với `NO-236`, `NO-237`. |
| 6 | Nit | MNT-06 | `NAME_MAX = 120` lặp ở `apps/api/measurements/text.py:13`, `packages/db/models/measurements.py:21`, `packages/db/models/templates.py:18` và migration. Bản chép trong migration là **bắt buộc** (không nhập module model) và `packages/db` không được nhập `apps`, nên chỉ đúng một lần lặp là tránh được. | như trên | Không cần sửa; nếu muốn, `models/templates.py` nhập `NAME_MAX` từ `models/measurements.py`. |
| 7 | Nit | TEST-07 | Thứ tự `#28` (`created_at ASC, id ASC`) hoà nhau khi hai khuôn có **đúng** một `created_at` — chỉ xảy ra với đồng hồ giả đóng băng, vì `SystemClock.now()` có độ phân giải micro giây còn ULID của `new_id` chỉ sắp được theo mili giây. `13e7ecb` sửa đúng gốc của lỗi test (cho đồng hồ chạy), không nới assert. | `apps/api/templates/tests/test_routes.py:121`; `apps/api/templates/service.py:44` | Không cần sửa. Mọi test khuôn khẳng định thứ tự đều đã đẩy đồng hồ. |

Không có finding P0 hay P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 3 (P2 #1) | 0,30 |
| TEST – Kiểm thử | 7% | 4 (P3 #3) | 0,28 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 (P2 #2, P3 #4) | 0,09 |
| **Tổng** | **100%** | | **4,67 / 5** |

## Nợ nên ghi (`DEBT.md`, trước khi merge — R-38)

- `NO-246` — P3 — `apps/api/measurements/tests/test_routes_read_delete.py:155` khẳng định `elapsed < 2,0 s` theo
  đồng hồ tường ở bước 5 mà không mark `perf`; trần 2 container `verify-run` một máy làm nó có thể đỏ giả.
  Chủ: B2-07. Trạng thái: mở. Chữa: `@pytest.mark.perf` (chạy ở bước 5b) hoặc nới trần kèm ngưỡng trong docstring.
- `NO-247` — P3 — `lock_project_scope` (tiện ích khoá tư vấn theo dự án) nằm ở `apps/api/measurements/locks.py`,
  `apps/api/templates` nhập chéo module anh em. Chủ: B0-03 (`packages/db`). Trạng thái: mở, chấp nhận khi chỉ có
  hai module của cùng một prompt. Chữa: chuyển sang `packages/db/` khi có người dùng thứ ba.
- `NO-248` — P3 — 422 của thân union (#29) mang tiền tố nhánh trong `field` (`wall.fields.heightMm`), FE không ánh
  xạ được về ô nhập. Nguyên nhân gốc: `field_of` giữ nguyên `loc` của pydantic, mà pydantic chèn tag nhánh vào
  `loc`. Chủ: B0-06 (`apps/api/core/errors.py`). Trạng thái: mở. Cùng lớp với `NO-236`, `NO-237`.

## PHÁN QUYẾT: APPROVE (4,67 / 5)

Nhánh làm đúng và đủ những gì B2-07 đòi, và làm đúng ở đúng những chỗ dễ sai nhất: khoá tư vấn đặt **trước** mọi
kiểm trùng và kiểm trần rồi mới tới `FOR UPDATE`; `touch_project` là lời ghi cuối và im lặng ở nhánh 200 lẫn nhánh
lỗi; dấu vân tay thân dùng **một** hàm chuẩn hoá cho cả lưu lẫn so nên "gửi lại nguyên bản ghi" là 200 chứ không
409, kể cả khi dự án đã chạm trần. Cả ba điều đó được chốt bằng hai client HTTP thật trên Postgres thật, không mock.
Hợp đồng dây khớp từng khoá với zod `.strict()` của AppFront ở cả hai chiều: `z` và `fields` vắng vẫn vắng, không
`null` nào lọt ra, `createdAt` đúng `.sssZ`, #18 trả 204 thân rỗng. Xoá cứng, id tái dùng được sau khi xoá, và
`MS-0001` của dự án khác không xoá nhầm qua đường của dự án này. Cổng đầy đủ **tự chạy lại ở phiên review**: mã
thoát 0, 8/8 bước đạt, 5300 test xanh, độ phủ của mọi gói bị chạm lẫn tổng đều vượt 90/90 trên cả dòng lẫn nhánh.

Hai finding P2 còn lại **không phải lỗi mã** mà là việc phải làm lúc gộp, và đều thuộc người điều phối:

1. Sau squash: `run.sh merge-heads` (hai head, do B3-04 vào `main` sau khi nhánh này cắt ra), rồi làm mới
   `docs/contracts/openapi.json` bằng `run.sh openapi` **trên `main`** — bản hợp nhất phải có cả 3 path của B2-07
   lẫn 5 path `/versions` của B3-04 — rồi chạy verify tích hợp đầy đủ (R-33b: cây sau gộp khác cây đã qua lượt đầy
   đủ). Xung đột trên `docs/contracts/openapi.json` là bình thường: giải bằng cách sinh lại, không sửa tay.
2. Thêm `NO-246`…`NO-248` vào `DEBT.md` trước khi merge (R-38). Không nợ nào mức P0/P1 nên không nợ nào chặn merge.

Merge được. Việc merge thuộc phiên đã gọi review này, không thuộc phiên này.
