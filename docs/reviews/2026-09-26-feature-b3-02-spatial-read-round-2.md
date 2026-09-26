# Review merge `feature/b3-02-spatial-read` → main — lượt 2

- Ngày: 2026-09-26 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `faf7b9879fd9`
- Lượt 1: **REQUEST CHANGES 4,27/5** tại sha `d95e79c` — `docs/reviews/2026-09-26-feature-b3-02-spatial-read.md` (`9bdcf07`)
- Phạm vi lượt 2: `git diff d95e79c..faf7b98` — **một** commit `faf7b98`
  `fix(spatial): guard N15 against a floor deleted mid-request`, 8 file, +91 / −20. Phần đã soát xong ở lượt 1
  không review lại trừ chỗ diff chạm tới.
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0** (chạy tại chỗ, worktree review ở đúng sha `faf7b98`,
  một lượt, 8/8 bước đạt; log `b3-02-review-verify-r2.log`, dòng `EXIT=0`)
- Test: **4590 passed, 0 failed**, 4 deselected (1075,24 s) — đúng **+2** so với 4588 của lượt 1, khớp hai test mới
- Độ phủ: tổng dòng **99,50 %** · nhánh **98,40 %** · `apps/api/spatial_read` dòng **100,00 %** · nhánh **100,00 %**
  · `packages/db` 96,33 % / 95,69 % · `packages/testing` 99,48 % / 98,57 % · tập file bị chạm 100,00 % / 100,00 %

## Trạng thái cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4590 passed / 0 failed |
| 5b | `pytest -m perf` → `case_gate` | đạt | **thiếu = 0**; 46 thao tác đã mount, 3 cảnh báo cũ (NO-222) |
| 6 | `lint_migrations` → `migrate_check` | đạt | 11 revision, **đúng 1 head**, seed ci hai lần |
| 7 | H1 H3 H4 H5 | đạt | H1 **1122 mẫu** · H1 ngữ cảnh **50 mẫu** · H3 10 khoá/3 vai · H4 không áp dụng đúng luật (B3-05 chưa hợp nhất) · H5 4 khung SSE |
| 8 | `openapi` | đạt | |

`case_gate` cho ba op vẫn `C01 C04 C05 C06 C08 C12 C13 C17 C25` — bắt buộc = tìm thấy, thiếu 0.
**Bước 8 đạt là đúng, không phải may:** diff không chạm `wire.py` nên `openapi.json` phải y nguyên byte —
chữ ký đổi (`assemble.level_out`) là hàm nội bộ, không phải model response.

**Mọi số tác giả báo ở `bao-cao-fix1.md` đều tự kiểm lại và khớp** (mã thoát 0 · 4590 passed ·
`apps/api/spatial_read` 100/100 · case_gate thiếu 0 · bước 8 đạt).

## Finding lượt 1 → trạng thái

| # | Mức | ID | Trạng thái | Bằng chứng trong diff |
|---|---|---|---|---|
| 1 | **P1** | LOG-02 | **FIXED** | `graph.py:86-87` `pairs = [(floor, pk_of[floor.id]) for floor in floors if floor.id in pk_of]`, `pks = [pk for _, pk in pairs]`; `docs` (`:92`), `levels` (`:93-96`), `layers` (`:97`), `revisions` (`:109-111`) đều dài bằng `pairs` nên **song ánh `levels ↔ floorRevisions`** mà `SpatialGraphDocumentSchema.refine` đòi vẫn đúng. Test `test_spatial_read_graph_when_floor_vanishes_mid_request` (`test_routes_graph.py:206-226`) |
| 4 | P3 | MNT-03 (R-07) | **FIXED** | `factories/spatial.py:23` nhập `DOCUMENT_SCHEMA_VERSION`, `EMPTY_LAYER`; `:118` và `:123` dùng chúng thay vì `1` và `SpatialLayer(...)` chép tay |
| 5 | P3 | MNT-04 | **FIXED** | `cases.toml:8-10` — chú thích mới trỏ đúng `tools/case_gate.py:493-499` |
| 6 | P3 | TEST-02 | **FIXED** | `test_routes_layer.py:253-282` `test_spatial_read_layer_corrupt_document_is_500`: 500, `code == "INTERNAL"`, `"schema_version" not in response.text`, `caplog` record của `apps.api.spatial_read.documents` mang `floor_pk` |
| 8 | Nit | MNT-03 | **FIXED** | `assemble.py:56` `level_out(floor, doc, scale_source)`; `router.py:78` tính `source` một lần cho cả `level` và `scale_status`; `graph.py:94` gọi tại chỗ |
| 7 | Nit | PERF-01 | **BỎ QUA có lý do — nhận** | Gốc là `floor_outs` của B2-03 không trả `pk`; đã thành **NO-223** (chủ B2-03). Số truy vấn vẫn hằng số, `test_spatial_read_graph_query_count_is_flat` vẫn xanh |
| 2 | P2 | MNT-05 | **NHẬN (waiver có sổ)** | **NO-221** trên `main` (`fd62657`), dấu `➖` đã đóng cùng ngày, lý do "khối [10] là một đơn vị bàn giao mà B3-03/B3-04 cùng chờ", đúng mẫu NO-216 |
| 3 | P2 | MNT-03 (R-34) | **FIXED** | `DEBT.md` trên `main` (`fd62657`) có **NO-220** (seed lặp `codec`/`counts` — cột chủ ghi đúng **B3-01** như lượt 1 yêu cầu), **NO-221**, **NO-222** (3 cảnh báo `case_gate`, B0-06), **NO-223**. FIX-108 [7] còn "(mở — nhánh `feature/b3-02-spatial-read`)" ở `docs/fixes.md:105` — đúng sổ của nó, không phải `DEBT.md` |

**8/8 finding đã xử lý.** Không còn P0/P1/P2 mở: hai P2 lượt 1 một cái FIXED, một cái nhận có dòng `DEBT.md`
đóng kèm lý do đứng được.

## Kiểm lại vòng sửa (không tin báo cáo)

**P1 đúng gốc, không vá triệu chứng (R-19).** Lỗi là "hai câu lệnh, hai snapshot `read committed`, tra `dict`
trần"; bản sửa lọc ngay tại chỗ hợp hai nguồn thay vì bọc `try/except KeyError` hay đổi thứ tự hai câu lệnh
(đổi thứ tự chỉ dịch cuộc đua sang chiều ngược: tầng **mới tạo** sẽ có trong `pk_of` mà thiếu trong `floors`).
Chiều ngược ấy nay vô hại vì vòng lặp đi theo `floors`. Đáp án 200-thiếu-một-tầng là đúng cho N15 (đồ thị là
một ảnh chụp, không có tầng nào là chủ thể của request), khác #33/N16 nơi 404 mới đúng.

**Test P1 là test đua thật và tất định.** `delete_floor_mid_request` bắn sau câu lệnh **đầu tiên** chứa
`" floors"`; trong N15 đó chắc chắn là `SELECT … FROM floors LEFT OUTER JOIN project_floor_summaries` của
`floor_outs` — `require_project` và `select(Project.name, …)` không chạm bảng `floors`, và chuỗi
`project_floor_summaries` **không** khớp `" floors"` (có gạch dưới, không có dấu cách). Nên bộ nghe rơi đúng
khe hở giữa `floor_outs` và `_floor_pks`, không phải một chỗ ngẫu nhiên. Tác giả báo đỏ-trước với `KeyError`
nguyên văn tại `graph.py:83` — **khớp chính xác** dòng và lớp lỗi mà lượt 1 dự đoán từ mã, trước khi có báo
cáo này.

**Đổi chữ ký `level_out` không phá hợp đồng.** `[2] "Hàm cho prompt sau"` của `assemble.py` chỉ công bố
`level_reviewed`, `scale_status`, `effective_scale_source` — `level_out` **không** nằm trong đó, và `grep` cho
đúng hai call site (`graph.py:94`, `router.py:82`), cả hai đã đổi. Hành vi **y nguyên**: trước là
`level_reviewed(doc.layer, effective_scale_source(doc, page_key))` tính bên trong, nay người gọi truyền chính
giá trị ấy vào. Đã cân nhắc và **không** ra finding chuyện `ScaleSource` không phân biệt "nguồn thô" với
"nguồn đã chấm hạng" nên kiểu không chặn được lượt gọi sai: hai call site nằm cùng một module, docstring
`assemble.py:58-62` nói rõ, và dựng một `NewType` cho hai chỗ gọi là thừa (R-10).

**Diff không gây lỗi mới.** `test_assemble.py` chỉ đổi theo chữ ký (`None` → `"human"`/`"none"`, đúng giá trị
mà `effective_scale_source` trả trên chính tài liệu ấy), không nới assert nào. `effective_scale_source` vẫn có
bốn test riêng nên bỏ lời gọi trong `level_out` không làm mất phủ. Không thêm `pragma`, `noqa`, `type: ignore`,
`skip`/`xfail`; không hạ ngưỡng. `test_spatial_read_layer_corrupt_document_is_500` còn chốt thêm hai thứ lượt 1
không đòi: thân lỗi **không lộ** `schema_version` (SEC-12) và `code == "INTERNAL"`.

**Phạm vi sửa hợp lệ.** 8 file đều trong `so_huu` của B3-02 (`apps/api/spatial_read/**` +
`packages/testing/factories/spatial.py`); không đụng `DEBT.md`, `docs/charter/*`, `docs/contracts/openapi.json`,
`uv.lock`, `conftest.py`, `tools/**`. Cây sạch, dòng đầu commit đúng Conventional Commits, có trailer
`Prompt: B3-02`, không `--no-verify`.

**Lệch khỏi prompt mới ở vòng này:** đúng một mục (chữ ký `level_out`), tác giả khai và có lý do đứng được —
đó là một trong hai cách lượt 1 đề nghị ở finding 8. Không thành finding.

## Finding mới

Không có. Zero P0 · P1 · P2 · P3 · Nit phát sinh từ diff `d95e79c..faf7b98`.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |

Tổng: **4,94 / 5** · P0: 0 · P1: 0 · P2: 0 mở (1 nhận có sổ) · P3: 0 · Nit: 0

LOG lên 5 (P1 đã sửa đúng gốc, có test đua đỏ-trước-xanh-sau). TEST lên 5 (hai lỗ hổng lượt 1 — test đua N15
và test 500 mức route — đã bịt). MNT giữ 3 vì MNT-05 vẫn là P2, đúng tiền lệ review B2-04 lượt 1 (APPROVE
4,67/5 với NO-216 cùng hình dạng).

## PHÁN QUYẾT: APPROVE

Vòng sửa gọn và đúng chỗ: một commit, 8 file, chỉ chạm những gì lượt 1 nêu, và điểm nặng nhất được sửa ở
**gốc** — lọc tại chỗ hợp hai nguồn dữ liệu, chứ không bắt `KeyError` hay xoay thứ tự hai câu lệnh để dịch
cuộc đua sang chiều khác. Test đi kèm là test đua thật, tất định, và tác giả chứng minh nó đỏ trên mã cũ với
đúng lớp lỗi mà lượt 1 chỉ ra. Bốn finding P3/Nit còn lại sửa đủ, hai mục bỏ qua đều có dòng `DEBT.md` với chủ
đúng (NO-221 B3-02 `➖`, NO-223 B2-03). Cổng đầy đủ tôi tự chạy một lượt: mã thoát 0, 8/8 bước đạt, 4590 passed
(+2 đúng bằng hai test mới), `apps/api/spatial_read` 100 %/100 % dòng và nhánh, `case_gate` thiếu 0, một head.

**Được merge vào `main`.** Việc merge thuộc phiên gọi review, không thuộc phiên này. Sau merge, người điều
phối còn hai việc sổ sách: đóng FIX-108 [7] ở `docs/fixes.md:105` (điền sha squash, đổi "(mở — nhánh …)"), và
làm mới `docs/contracts/openapi.json` chỉ khi có prompt sau thêm route — vòng này `openapi.json` không đổi nên
bản trên nhánh vẫn đúng.
