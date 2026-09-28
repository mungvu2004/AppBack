# Review merge `feature/b3-03-spatial-write` → main — lượt 2

- Ngày: 2026-09-28 · Reviewer: phiên `/merge-review` (độc lập, R-37) · Commit đầu nhánh: `dfc41eb3ff59`
- Lượt 1: **REQUEST CHANGES 3,75/5** (`e77875d`, sha nhánh `6fdbe1c`) · nợ lượt 1 đã ghi `main` `9cb1e22`
- Cổng: **Phạm vi kiểm: đầy đủ** — R-33b "nhánh có vòng sửa kiểm đích sau lượt đầy đủ → chạy đầy đủ **một
  lần** trước khi gộp"; tác giả chỉ chạy đích và tự ghi nhận món nợ ấy, lượt này trả nó.
  `bash tools/verify/run.sh verify` mã thoát **0** (một lượt, worktree review `--detach` đúng sha `dfc41eb`,
  chạy trong pane RUNNER; log `…/scratchpad/verify-r2.log`, dòng `EXIT=0`) — 8/8 bước `đạt`
- Test: **4868 passed, 0 failed**, 7 deselected (1175,62 s = 19:35)
- Độ phủ: tổng dòng **99,53 %** · nhánh **98,48 %** · `apps/api/spatial_write` **100,00 % / 100,00 %** ·
  tập file bị chạm **100,00 % / 100,00 %**

## Trạng thái cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | All checks passed |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | 4868 passed / 0 failed |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; **thiếu = 0** |
| 6 | `lint_migrations` → `migrate_check` | đạt | 12 revision, đúng 1 head |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | bảng con dưới |
| 8 | `openapi` | đạt | **155 769 byte — y hệt lượt 1** |

Bảng con bước 7 (AppFront `9cf0b0bfffbd`): Smoke đạt (23 module, 83 mục) · Bản đồ đủ đạt (83/83) ·
Thao tác đã mount đạt (53/83) · **H1 đạt — 1233 mẫu** (lượt 1: 1232) · H1 ngữ cảnh đạt (50 mẫu) ·
H3 đạt (10 khoá, 3 vai) · H4 **không áp dụng** đúng luật BE-00 §12 (B3-05 chưa hợp nhất) · H5 đạt (4 khung SSE).

`case_gate`: `spatial_write_layer` bắt buộc 16 case, **tìm thấy y hệt 16, thiếu 0**. Ba cảnh báo
`files_read_object`, `health_live`, `health_ready` có từ trước B3-02.

**Hai con số chốt vòng sửa không làm lệch hợp đồng, tự kiểm chứ không tin báo cáo:**
`openapi` sinh ra **155 769 byte**, bằng **đúng từng byte** lượt 1 → `_scale` thật sự chỉ đổi đường lỗi,
hình dạng dây không đổi; và `docs/contracts/openapi.json` không nằm trong diff. H1 **+1** mẫu (1232 → 1233)
đúng bằng một mẫu golden **thêm** cho `__C02[huge_scale]`, không mẫu nào đổi — khớp điều tác giả dự đoán.
`4868 − 4864 = +4` test khớp đúng bốn thứ đã thêm (hai tham số `test_schemas`, `huge_scale` của C02, một test
CON-04); module có 124 test như tác giả báo.

## Điều kiện dừng sớm (không vi phạm)

Cây sạch · 3 commit mới đúng Conventional Commits ≤ 72 ký tự, đủ trailer `Prompt: B3-03`
(`113bb9e`, `a79de6e`, `dfc41eb`) · `git merge-base main HEAD` = `9e37313`, không rebase (`main` tiến tới
`9cb1e22` chỉ là `DEBT.md`) · diff **11 file**, **tất cả** dưới `apps/api/spatial_write/`;
`git diff --name-status --diff-filter=ADR 6fdbe1c..dfc41eb` **rỗng** (không thêm/xoá/đổi tên file `.py`) ·
không đụng `docs/charter/*`, `docs/contracts/openapi.json`, `uv.lock`, `tools/**`, `packages/**`,
`conftest.py`, `.importlinter`, `DEBT.md` · không `pragma: no cover`/`no branch`, không `skip`/`xfail`,
không hạ ngưỡng, **không một** `# type: ignore`, đúng **một** `# noqa: S603` cũ có mã và lý do
(`tests/test_boundary.py:33`) · không `except Exception` rộng · tự quét lại R-01 + R-08 trên toàn module:
**0 vi phạm** (mọi module/lớp/hàm có docstring, 0 hàm > 50 dòng) — khớp khẳng định của tác giả.

## Nợ lượt 1 trên `main` (`9cb1e22`) — đã kiểm đủ và đúng

| dòng | nội dung | khớp yêu cầu lượt 1 |
|---|---|---|
| NO-234 ➖ | MNT-05 nhánh > 400 dòng, chấp nhận theo mẫu NO-216/NO-221 | mục 1 ✓ |
| NO-235 ⬜ | bẫy `commit()`/`MissingGreenlet` của fixture `db_session`, chủ **B0-03** (K27) | mục 2 ✓ |
| NO-236 ⬜ | hai `type` bí danh trùng tên làm OpenAPI đổi cả hai component, chủ B0-06/B0-01 | **thêm**, không phải tôi đòi — nợ thật do G phát hiện, ghi là đúng |
| NO-237 ⬜ | `PUT` khai thiếu tham số đường `project_id`, chủ B0-06 | mục 4 ✓ |
| NO-238 ➖ | p95 tầng lớn trên 5 mẫu, chấp nhận | mục 3 ✓ |

Mục 5 của lượt 1 ("finding 2 **nếu không sửa**") vắng đúng: finding 2 đã sửa. Không nợ `P0`/`P1` nào đang
**mở** chặn nhánh (R-35, R-38).

## Finding lượt 1 → trạng thái (tự kiểm từng mục trong diff)

| # | Mức | ID | Tác giả báo | Tôi kiểm | Bằng chứng |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-02 | fixed | **sửa, chưa trọn** → finding mới 1 | `schemas.py:36-51` bọc `quantize`, `InvalidOperation` → `ValueError`; `1e22`, `10**30`, `10**308` nay ra 422. Log đỏ-trước của tác giả (`R/bang-chung-do.log`) là thật và có đúng dòng `assert 500 == 422` — chốt lại chẩn đoán lượt 1. **Nhưng** `math.isfinite` chạy **trước** khối `try` |
| 2 | P2 | PERF-02 | fixed | **fixed** | `changes.py:33-68`: `DISTINCT ON` thành `.subquery()`, ngoài là `order_by(revision desc, id desc).limit(max(limit,0))`, `reversed(rows)` đưa về `(revision, id)` tăng; `_COLUMNS` 10 cột thay thực thể ORM. Hành vi không đổi: `test_remote_changes_since_truncates_to_newest` và `_all_bases` (bằng nhau với **mọi** `base` trước/sau gộp) đều xanh trong lượt đầy đủ. `limit=0` → `LIMIT 0` → rỗng, `limit` âm → `max(…,0)` (bản cũ `deque(maxlen=âm)` sẽ nổ) |
| 3 | P2 | TEST-02 | fixed | **fixed** | `test_schemas.py:31-34` thêm `1e22` + `10**30`; `test_routes.py:58` thêm `huge_scale` vào `_bad_bodies`, docstring C02 cập nhật. H1 +1 mẫu xác nhận case mới thật sự chạy qua route |
| 4 | P2 | MNT-05 | skipped | **bỏ có lý do** | NO-234 `➖` trên `main`, lý do đúng như lượt 1 chấp nhận |
| 5 | P3 | CON-04 | fixed | **mã fixed; test không bảo vệ** → finding mới 2 | `writer.py:290-307` `_current_document`: đường `merge` `ensure_document` **trước** rồi `load_document(for_update=True)`; đường thường giữ một truy vấn. Đúng thứ tự prompt bước 3 |
| 6 | P3 | R-07 | fixed | **fixed** | `layer_of` xoá khỏi `_route_helpers.py`, `simple_layer` nhận `furniture`; `slipping_load` thành factory ở `_helpers.py:190-227` cộng `reordered` tách riêng — gom luôn cả `_reordered` vốn lặp ở hai file |
| 7 | P3 | R-08 | fixed | **fixed** | tự quét: 0 hàm > 50 dòng trong module |
| 8 | P3 | R-01 | fixed | **fixed** | docstring cho `_seed`, `_count` (`test_jobs.py:191,198`); tự quét: 0 chỗ thiếu |
| 9 | P3 | API-05 | skipped | **bỏ có lý do** | NO-237 `⬜`, chủ B0-06, dọn cùng route `settings` |
| 10 | Nit | OBS-02 | fixed | **fixed** (một nhận xét nhỏ → finding mới 3) | `writer.py:212-219` `_log.warning("spatial_write_exhausted_attempts", …)` trước khi ném 503 |
| 11 | Nit | MNT-03 | fixed | **fixed** | `writer.py:160-164` docstring `body_sha256` nói rõ `Decimal("10")` ≠ `Decimal("10.000000")`, người gọi Python phải tự quantize |

**9 fixed · 2 skipped có `DEBT.md`** — khớp báo cáo tác giả, trừ hai chỗ tôi hạ mức "fixed" xuống (1 và 5).

## Finding mới của lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-02 | **Bản sửa P1 chưa trọn**: `try` chỉ bọc `quantize`, nhưng `math.isfinite(value)` chạy **trước** nó, và với một **số nguyên** JSON từ 310 chữ số (> `float` max ≈ 1,8e308) nó ném `OverflowError: int too large to convert to float` — cũng là `ArithmeticError`, cũng **không** phải `ValueError`, nên vẫn lọt `BeforeValidator`, vẫn rơi xuống `middleware.py:276` → `translate_unknown` → **500 `INTERNAL`** + log `unhandled_exception` có stack, thay cho 422 `VALIDATION` mà [2] hứa. Đã dựng lại trên đúng bản `dfc41eb`: `1e22` → 422 · `10**308` (309 chữ số) → 422 · `10**309` (310 chữ số) → **OverflowError không ai bắt** · số âm cùng cỡ → như trên. **Khác lượt 1 ở một điểm quyết định mức**: đường này **không** tới được từ FE — `JSON.stringify` của một `number` JS không bao giờ sinh literal nguyên 310 chữ số, và `1e400` thành `Infinity` rồi `null`; một `float` FE gửi được lớn nhất (≈ 1,8e308) đi qua `isfinite` rồi bị `quantize` chặn đúng cách. Vì thế **P2** chứ không P1: cần thân tự dựng (curl/script/client không phải JS), hậu quả là 500 + log stack, không mất dữ liệu, không vượt quyền | `apps/api/spatial_write/schemas.py:44-51` | Một trong hai, cùng một dòng: `except (InvalidOperation, OverflowError)`, hoặc đưa phép kiểm dải lên trước — `if not (0 < value <= SCALE_MAX): raise ValueError(...)` — rồi mới `isfinite`/`quantize` (cách sau đóng luôn mọi `ArithmeticError` tương lai và giữ nguyên luật "0 sau làm tròn → 422", vì `0.0000004` vẫn qua guard rồi mới quantize về 0). Kèm `10**310` vào tham số của `test_scale_rejects_everything_outside_the_contract` |
| 2 | P3 | TEST-02 | Test kèm bản sửa CON-04 **không bảo vệ** lỗi nó nói mình bảo vệ: nó **xanh trên mã trước khi sửa**. Tôi lùi `_attempt` về đúng một dòng của `6fdbe1c` trong bản chép của container rồi chạy test ấy **6 lượt**: `1 passed` cả 6 (log `…/scratchpad/probe.log`). Lý do: trên tầng **chưa có** dòng `floor_documents`, hai lượt ghi song song serialize ngay ở `INSERT … ON CONFLICT DO NOTHING` của `ensure_document` — bên tới sau chờ trên khoá chỉ mục của bên trước cho tới khi bên ấy `commit`, rồi đọc lại `revision` **mới**, nên `_bump` ăn dòng ngay lượt đầu và `merge.calls == 1` đúng ở **cả hai** bản mã. Nói cách khác, chính cảnh test dựng lại là cảnh duy nhất mà thiếu `FOR UPDATE` **không** gây hại (một dòng vừa `INSERT` đã bị giao dịch chèn nó khoá độc quyền). Khe hở thật của mã cũ hẹp hơn và cần **ba** bên: A (`merge`) đọc `None`, một bên thứ ba tạo dòng và `commit` vào đúng khoảng giữa, A `ensure_document` rơi vào `DO NOTHING` rồi đọc lại **không khoá**, B chen vào `UPDATE` trước A → A thử lại. Báo cáo tác giả khẳng định "`merge.calls == 1` **là phép kiểm**" — probe phủ định khẳng định ấy. **Bản sửa mã vẫn đúng** và vẫn tốt hơn hẳn (đường `merge` nay luôn giữ khoá tường minh); chỉ test là tautology | `apps/api/spatial_write/tests/test_writer_conflict.py:246-283` | Chốt trực tiếp bất biến thay vì dựng đua: bọc `writer.load_document` bằng một hàm ghi lại `(floor_pk, for_update)` rồi khẳng định trên tầng **chưa có** tài liệu, đường `merge` gọi nó với `for_update=True` **sau** `ensure_document` — tất định, không phụ thuộc thứ tự lịch. Giữ test đua hiện tại làm test khói cũng được, nhưng đừng để nó mang danh phép kiểm của CON-04 |
| 3 | Nit | OBS-02 | Dòng log 503 mới dùng khoá `floorPk` (camelCase), trong khi **cùng trường ấy** ở `apps/api/spatial_read/documents.py:90,96` là `floor_pk`. Repo chưa có quy ước thống nhất (`userId`, `projectId`, `routeTemplate` sống cạnh `task_id`, `project_id`, `token_id`), nên đây không phải vi phạm luật — nhưng một truy vấn log theo `floor_pk` sẽ **không** thấy dòng mới | `apps/api/spatial_write/writer.py:218` | `floor_pk` cho khớp hai chỗ đã có của cùng trường |
| 4 | Nit | MNT-03 | Hai con số trong báo cáo vòng sửa không khớp bằng chứng của chính nó, không ảnh hưởng kết luận nào: bảng R-33b điều kiện 2 ghi diff "**8 file**" (thực tế **11**; mục "Thay đổi file" tự liệt kê 10 và thiếu `tests/test_schemas.py`), và phần P1 ghi "**Ba** test đỏ" trong khi log được trích ghi `2 failed` | `bao-cao-fix1.md` (R-33b đk 2, mục "Thay đổi file", mục bằng chứng đỏ) | Đếm lại bằng `git diff --name-only … | wc -l`; kết luận "tất cả dưới `apps/api/spatial_write/`" vẫn đúng nên đánh giá **đích** không bị ảnh hưởng |

## Đã soát và không ra finding (chỉ phần diff chạm tới)

**PERF** — Bản sửa finding 2 đúng hướng và đúng ngữ nghĩa: `DISTINCT ON (entity_id, field)` giữ `ORDER BY`
bắt đầu bằng đúng hai biểu thức ấy (Postgres đòi vậy) nên subquery hợp lệ; lớp ngoài sắp `(revision, id)`
**giảm** rồi `LIMIT`, `reversed` đưa về tăng — cùng tập, cùng thứ tự với bản `deque` cũ, và `limit` nay chặn
**việc phải làm** ở Postgres chứ không chỉ thân trả về. `Row[Any]` làm mất kiểu tĩnh của dòng, nhưng không
cột nào trùng tên phương thức của `Row` (`count`, `index`) nên truy cập theo tên an toàn, và `mypy --strict`
xanh. Con số "7 cột" của lượt 1 là **tôi** đếm thiếu: `RemoteFieldChange` cần 7 trường nhưng phải có cả
`removed`, cộng `id` + `revision` cho `ORDER BY` ngoài = **10**; tác giả chọn đúng 10.

**CON** — `_current_document` đúng thứ tự prompt bước 3 cho đường `merge` và giữ tối ưu một truy vấn cho
đường thường. `or created` chỉ là cầu kiểu tĩnh và chú thích nói đúng lý do: `floors` đang `FOR SHARE` từ
bước 1 nên không ai xoá được tầng — và cascade dòng tài liệu — giữa hai câu. Giá phải trả: đường `merge` nay
chạy `INSERT … ON CONFLICT DO NOTHING` ở **mọi** lượt, không chỉ khi thiếu dòng — đúng cái prompt bước 3
mô tả, và `merge` là đường pipeline chứ không phải đường nóng, nên nhận.

**TEST** (ngoài finding 2) — Gom helper không làm mất phạm vi: `slipping_load` thành factory nhận
`(sessionmaker, floor, actor, clock)`, cờ `running` chặn đệ quy vẫn còn, vẫn **không** mock session và
**không** mock `write_layer` (K22/K23), hai chỗ gọi truyền đúng tham số cũ. `reordered` tách ra là chỗ lặp
thứ ba mà lượt 1 chỉ nói gộp gián tiếp. `_helpers.py` nhập `other_session` từ `spatial_read/tests` — cùng
kiểu nhập test-sang-test mà `_route_helpers.py` đã dùng với `projects/tests`, và bước 4 `lint-imports` xanh.
`test_large.py`/`test_routes*.py` đổi `layer_of` → `simple_layer` đúng từng chỗ; `simple_layer` mới bao trọn
hành vi cũ (`furniture` mặc định `()`).

**DB / API** — `openapi` sinh ra bằng đúng từng byte lượt 1; `docs/contracts/openapi.json` không trong diff;
H1 chỉ **thêm** một mẫu. Không route/`operationId` mới, không đổi hình dạng dây, không migration.

**R-33b** — Đánh giá "đích" của tác giả cho **vòng sửa** đứng được trên cả 7 điều kiện (tôi kiểm lại đk 2
và 3 bằng lệnh: 11 file nhưng **tất cả** dưới `apps/api/spatial_write/`, `--diff-filter=ADR` rỗng), và họ
**tự ghi nhận** món nợ "một lượt đầy đủ trước khi gộp" thay vì che nó — đúng tinh thần R-33b, không phải
finding. Lượt đầy đủ của review này trả xong món nợ ấy.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 3 | 0,45 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 4 | 0,40 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |

Tổng: **4,50 / 5** (lượt 1: 3,75) · P0: 0 · P1: **0** · P2: 1 · P3: 1 · Nit: 2

LOG còn 3 vì finding mới 1 là P2. DB/API giữ 4 vì P3 API-05 còn trong tài liệu của nhánh, chỉ hoãn sang
NO-237 (chủ B0-06). MNT lên 4: P2 MNT-05 đã được waive bằng NO-234 có lý do đứng được, ba P3 R-01/R-07/R-08
đã sửa hết.

## PHÁN QUYẾT: APPROVE

P1 của lượt 1 đã sửa đúng gốc và có bằng chứng hai phía: log đỏ-trước của tác giả mang đúng dòng
`assert 500 == 422`, và lượt đầy đủ của tôi xanh với `10**30` cùng `1e22` nay ra 422 kèm `field`. Hai P2 còn
lại của lượt 1 cũng xử lý đúng chỗ đau: phép cắt của `remote_changes_since` xuống Postgres nên
`SPATIAL_CONFLICT_CHANGES_MAX` lần đầu tiên chặn được **việc phải làm** chứ không chỉ thân trả về, và bộ test
biên nay chạm đúng chỗ `decimal` vỡ. Ba P3 bảo trì sửa sạch — tôi tự quét lại toàn module và không còn một
hàm nào thiếu docstring hay dài quá 50 dòng. Cổng đầy đủ thoát 0 với 8/8 bước, độ phủ module 100 %/100 %,
`case_gate` 16/16, và hai con số tôi dùng để bắt lệch hợp đồng — `openapi` 155 769 byte y hệt lượt 1 và H1
chỉ **+1** mẫu — chứng minh vòng sửa không làm dịch hợp đồng FE một byte nào.

Duyệt dù còn một P2 vì ba lẽ, và tôi nói rõ để lượt sau không phải đoán. Một, nó **không** cùng mức với P1
lượt 1: đường `OverflowError` chỉ tới được bằng thân tự dựng, còn đường FE thật sự dùng đã được bịt — chính
điều kiện làm P1 lượt 1 thành P1 nay không còn. Hai, ma trận RULE §5 ở 4,50 và **0** P0/P1 cho `APPROVE`.
Ba, đây là dạng lỗi rẻ nhất để đóng: một dòng, không chạm hợp đồng, không chạm `writer.py`/`changes.py`.

Theo RULE §1, một P2 phải **sửa trước merge hoặc có ticket lý do hợp lệ** — đó là điều kiện duy nhất tôi kèm
vào phán quyết này, không phải một cổng mới:

1. **(P2, finding mới 1)** Sửa `schemas.py:44-51` — tôi khuyên đưa phép kiểm dải lên **trước** `isfinite`
   thay vì thêm một lớp `except`, vì cách ấy đóng luôn mọi `ArithmeticError` về sau chứ không chỉ hai cái đã
   biết — cộng một tham số `10**310` vào test. **Hoặc** một dòng `NO-<nnn>` có lý do đứng được.
2. **(P3, finding mới 2)** Nên làm cùng lúc: đổi test CON-04 thành phép kiểm tất định (ghi lại
   `for_update`), vì hiện nó xanh trên cả mã lỗi. Không chặn merge, nhưng để nguyên thì lần sửa
   `_current_document` nào sau này cũng đi qua cổng xanh mà không ai biết.
3. Finding mới 3 và 4 là Nit, tác giả tự quyết.

**Phạm vi kiểm cho vòng sửa này (R-33b):** mục 1 và 2 chỉ chạm `schemas.py` cùng test của module, không chạm
route, `operationId`, hình dạng dây hay `cases.toml` (mẫu golden chỉ **thêm**), và không thêm/xoá/đổi tên
file `.py` → **đích** là đủ: `verify --steps 1,2,3,4` + `pytest apps/api/spatial_write` +
`coverage report` cho file đổi. Lượt đầy đủ **không** cần chạy lại: lượt này đã trả món nợ R-33b ở `dfc41eb`,
và một vòng sửa chỉ chạm đường lỗi của `schemas.py` không chạm điều kiện (2)–(7) nào. Nếu vòng sửa mở rộng
sang `writer.py` hay `changes.py` thì quay lại **đầy đủ**.

Sau khi mục 1 xong, nhánh **được merge** bằng squash vào `main` — không cần lượt review 3, chỉ cần dán mã
thoát của lượt đích vào báo cáo gộp.
