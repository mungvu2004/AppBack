# Review merge `feature/b2-05b-quality-api` → main — **lượt 2** (vòng sửa NO-226..229)

- Ngày: 2026-09-26 · Reviewer: phiên `/merge-review` độc lập (R-37) · Commit đầu nhánh: `b6fbe1e946e5`
- Lượt 1 (`73066fbddfae`) đã **APPROVE 4,65/5**, toàn nhánh, cổng đầy đủ xanh — `docs/reviews/2026-09-26-feature-b2-05b-quality-api.md`.
- Phạm vi lượt này: **chỉ** `git diff 73066fb..b6fbe1e` (8 file, +195 −25). Worktree review riêng
  `C:/Users/mxuan/orca/workspaces/AppBack/b2-05b-review`, `merge --ff-only b6fbe1e`, cây sạch, không sửa mã, không merge.

## Phạm vi kiểm: **đích** — lý do

`git diff --name-only 73066fb..b6fbe1e` chỉ gồm `apps/api/quality/**` (3 nguồn + 5 test):

```
apps/api/quality/assessments.py  geometry.py  service.py
apps/api/quality/tests/test_geometry.py  test_processing.py  test_read_view.py
apps/api/quality/tests/test_routes_corners.py  test_routes_scope.py (mới)
```

Không migration · không đổi dây / `cases.toml` / tên `test_<op>__<case>` · không đổi tên công khai module khác nhập
(`validate_corner_ratios` chỉ có một người gọi ngoài test: `apps/api/quality/service.py:338`; `_discard_orphan`,
`_findings_out` là riêng tư). Đủ điều kiện **đích** của R-33b (luật người dùng chốt 2026-09-26, thắng câu "không có log
thì tự chạy `run.sh verify`" của skill trong phiên này). Lượt 1 đã chạy **đầy đủ** và xanh ở `73066fb`; đây là delta.

Bốn lý do các bước 5–8 "chưa chạy" là an toàn, kiểm bằng mã chứ không suy đoán:

- **5b / `case_gate`** — `tools/case_gate.py:294-296,308,346`: `split_case_test_name` trả `None` cho tên không khớp và
  người gọi bỏ qua. Ba test mới (`…__page_key_without_ulid_uses_the_whole_key`,
  `…__orphan_delete_failure_keeps_the_real_error`, `test_floor_of_another_project_is_not_found_through_my_project`)
  không mang `__<caseid>` nên không thêm/bớt case bắt buộc; không test `perf` mới.
- **6** — 0 file dưới `packages/db/migrations/`.
- **7 / 8** — không route, không schema dây nào đổi. `_findings_out` chỉ đổi giá trị hậu tố `u` của `finding.id` cho
  khoá **không có ULID**; `FindingOut.id` là `str = Field(min_length=1)` (`schemas.py:39`) và bên FE
  `ImageQualityFindingSchema.id` là `idSchema = z.string().min(1)` (`AppFront/src/api/schemas/quality.ts:40,181`) —
  không mẫu regex, nên dấu `/` trong khoá rơi về **không** phá hợp đồng. `docs/contracts/openapi.json` không cần sinh lại.
- **5 / `coverage_gate`** — thay bằng một lượt `run.sh shell` đo riêng gói bị chạm (số ở dưới).

## Bảng cổng (mã thoát thật)

| bước | lệnh | trạng thái | ghi chú |
|---|---|---|---|
| 1 | `ruff format --check` | **đạt** | |
| 2 | `ruff check` | **đạt** | |
| 3 | `mypy --strict` | **đạt** | |
| 4 | `lint-imports` | **đạt** | 9 contract kept, 0 broken |
| 5 | `coverage run -m pytest` → `coverage_gate` | **chưa chạy — đích theo R-33b** | thay bằng lượt `run.sh shell` dưới đây |
| 5b | `pytest -m perf` → `case_gate` | **chưa chạy — đích theo R-33b** | không test `perf` mới; `case_gate` bỏ qua tên không có `__<caseid>` |
| 6 | `lint_migrations` → `migrate_check` | **chưa chạy — đích theo R-33b** | diff không chạm migration |
| 7 | H1 H3 H4 H5 | **chưa chạy — đích theo R-33b** | không đổi route/schema dây |
| 8 | `openapi` | **chưa chạy — đích theo R-33b** | như trên |

`bash tools/verify/run.sh verify --steps 1,2,3,4` → **mã thoát 0** (chạy tại chỗ trong worktree review, container
`appback-verify-b2-05b-review-verify-run-2246a1726679`; 0 container `verify-run` khác lúc bắt đầu, dưới trần 2).

`bash tools/verify/run.sh shell` (lượt riêng, thay bước 5 cho gói bị chạm) → **mã thoát 0**, container
`appback-verify-b2-05b-review-verify-run-77636afdcd3e`:

- `coverage run -m pytest -q apps/api/quality` → **130 passed, 3 deselected** (152,94 s), `PYTEST_EXIT=0`.
  Postgres, Redis, MinIO đều là container thật của `testcontainers` (log dựng đủ ba), không mock dịch vụ nào (K23).
- `coverage combine` (config `parallel = true`, `branch = true`) gộp 2 file dữ liệu.
- `coverage report --include='apps/api/quality/*' -m` → `COVREPORT_EXIT=0`:

| file | Stmts | Miss | Branch | BrPart | Cover |
|---|---|---|---|---|---|
| `__init__.py` | 2 | 0 | 0 | 0 | **100%** |
| `assessments.py` | 107 | 0 | 22 | 0 | **100%** |
| `errors.py` | 5 | 0 | 0 | 0 | **100%** |
| `geometry.py` | 63 | 0 | 18 | 0 | **100%** |
| `processing.py` | 80 | 0 | 8 | 0 | **100%** |
| `router.py` | 29 | 0 | 2 | 0 | **100%** |
| `schemas.py` | 45 | 0 | 0 | 0 | **100%** |
| `service.py` | 179 | 0 | 44 | 0 | **100%** |
| `settings.py` | 18 | 0 | 0 | 0 | **100%** |
| **TOTAL** | **528** | **0** | **94** | **0** | **100%** |

**Từng file 100% dòng và 100% nhánh**, trên ngưỡng 90/90 của BE-00 §12. Ba nhánh mới của vòng sửa đều nằm trong số đó:
`ulid = found[-1] if found else …` (cả hai phía), `sums[0] > min(sums) + eps` (cả hai phía), và `except (AppError, OSError)`
của `_discard_orphan` (hai lớp lỗi qua `parametrize`).

## Từng NO — bằng chứng, không tin báo cáo

### NO-226 (P3 LOG-03 lượt 1) — **đóng được**

`assessments.py:198-201`: `found = _ULID.findall(report["pageKey"])` rồi `ulid = found[-1] if found else report["pageKey"]`.
Docstring nêu đúng lý do và hệ quả. **Đỏ-trước là chắc chắn về mặt máy móc**: ở `73066fb` dòng đó là
`_ULID.findall(report["pageKey"])[-1]`, `findall` trả `[]` cho khoá `"pages/no-ulid.png"` → `IndexError` → 500; test mới
khẳng định 200 và `finding.id` kết thúc bằng cả khoá. Test `test_read_view.py:233-250` đặt khoá vào **cả**
`DrawingRow.page_key` lẫn `report["pageKey"]` nên đi đúng nhánh, và chạy trên Postgres thật.

### NO-227 (P3 LOG-01 lượt 1) — **đóng được**, đúng quyết định điều phối

`geometry.py:73-74`: `sums = [x + y for x, y in pts]` · `if sums[0] > min(sums) + eps: raise` — nhận đúng khi
`x + y` của điểm đầu ≤ `min(x + y)` + `eps`, **đúng** câu chốt của điều phối viên. Mọi luật còn lại giữ nguyên
(4 điểm, miền `[0,1]`, bốn tích có hướng cùng dấu dương, diện tích dây giày) — chỉ dòng chọn điểm đầu đổi.
`eps` đi vào như `min_area` (hàm vẫn thuần), người gọi duy nhất truyền `settings.quality_corner_eps`
(`service.py:341`, mặc định `0.002`, `settings.py:23`).

**Đỏ-trước chắc chắn**: luật cũ `min(range(4), key=lambda i: (x + y, x)) != 0` chọn `(0, 0.5)` cho hình thoi (hoà
`x+y = 0,5`, `x` nhỏ hơn), nên bộ bắt đầu ở `(0.5, 0)` bị 422; ngoài ra chữ ký cũ không có `eps` → `TypeError`.

**Đã soát riêng chuyện "sửa gốc hay vá triệu chứng" (R-19)** và kết luận là **sửa gốc**: người sinh thứ tự góc trong
repo là `packages/vision/preprocess/geometry.py:162-177` `order_corners`, sắp theo `x + y` nhỏ nhất (hoà thì `x` nhỏ
hơn). Luật kiểm cũ chép **cả** tie-break `x` nên chỉ chấp nhận đúng một trong hai đỉnh hoà — đó chính là điểm lệch.
Luật mới bỏ tie-break và thêm dung sai, tức khớp đúng quy ước của người sinh. Kiểm bằng phản ví dụ: hình vuông xoay
bất kỳ nội tiếp `(t,0) (1,t) (1−t,1) (0,1−t)` — `order_corners` luôn trả bộ có `sums[0] = min(sums)`, kể cả `t > 0,5`,
nên client theo quy ước repo không còn ca nào bị loại nhầm. Ba test mới phủ cả hai phía: hai cách bắt đầu hoà đều nhận,
bắt đầu ở đỉnh xa `(1, 0.5)` vẫn 422, và biên `eps` (`0.001` nhận / `0.0031` loại với `eps = 0.002`).

### NO-228 (P3 RES-04 lượt 1) — **đóng được kèm điều kiện** (xem finding 1)

`service.py:277-288` `_discard_orphan`: `try: await storage.delete(key)` / `except (AppError, OSError) as exc:` +
`_log.warning("quality_orphan_delete_failed", extra={"object_key": key}, exc_info=exc)`. Không `except Exception`,
lớp lỗi liệt kê tường minh, log có cấu trúc đúng khuôn của repo (`auth/sessions.py:459`, `core/app.py:112`), không lộ
bí mật. `_swap_page` finally gọi `_discard_orphan` thay cho `storage.delete` thẳng (`service.py:319`).

**Đỏ-trước chắc chắn**: ở `73066fb` `await storage.delete(new_key)` đứng trần trong `finally` của một request đang
thoát bằng 409, nên ngoại lệ tiêm vào thay hẳn lỗi thật → client nhận 503 (`DEPENDENCY_UNAVAILABLE`) hoặc 500
(`OSError`), không bao giờ 409.

Test `test_routes_corners.py:563-597` tham số hoá **cả hai** lớp lỗi, dùng `api_app.state.storage` thật
(`LocalDiskStorage`), khẳng định 409 + `code == "QUALITY_DRAWING_CHANGED"` + có bản ghi log
`quality_orphan_delete_failed`. Đủ cho đường local. Xem finding 1 cho đường S3.

### NO-229 (3 × Nit lượt 1) — **đóng được**

- `asyncio.sleep` cố định: **hết sạch** — `grep -rn "sleep" apps/api/quality/` không ra dòng nào. Khuôn mới
  (`test_processing.py:190-197`) lặp `asyncio.wait(..., timeout=20, return_when=FIRST_COMPLETED)` tới khi đủ
  `CALLS - workers` lời bị từ chối, có `assert done` chặn treo câm — đúng khuôn `test_queue.py:99` mà lượt 1 chỉ ra.
  Không lời nào đang giữ chỗ có thể "xong sớm" nhầm vào tập `refused`: chúng bị chặn trong `gate.wait(20)` cho tới
  `gate.set()` sau vòng lặp.
- Đọc thuộc tính riêng tư: **hết** — `processing._pool(3)._max_workers` đã bỏ; quét `apps/api/quality/tests/` không còn
  chỗ nào đọc `._<tên>` của mã sản phẩm.
- Test 404 `floor` dự án khác cho #30–#32: có, `tests/test_routes_scope.py` (file mới), tham số hoá đủ **ba** route
  qua `_call`, khẳng định `404` **và** `json()["resource"] == "floor"`. Test tự bảo vệ: nếu hai `make_stage` lỡ sinh
  trùng `level_id` thì lời gọi ra 200 và test đỏ, không âm thầm đúng.

## Luật viết mã trên diff

`except Exception` / `except BaseException`: **không có**. `# pragma: no cover` / `pragma: no branch`: **không có**.
`# type: ignore` trần: **không có** — hai dòng trong diff là `[arg-type]`, `[list-item]` có mã. `# noqa` trần: không có
(`test_boundary.py:15` `# noqa: S603` kèm lý do, không nằm trong diff). `skip` / `xfail` mới: không có. Không hạ ngưỡng.
**R-01 docstring**: quét cả 8 file — mọi hàm mới (`_discard_orphan`, `_call`, `refuse`, `broken_delete`, 4 test mới)
đều có docstring; docstring của `validate_corner_ratios`, `_findings_out`, `_saturate` đã cập nhật theo hành vi mới.
Diff không chạm file cấm nào (`docs/charter/*`, `openapi.json`, `uv.lock`, `conftest.py` gốc, `pyproject.toml` gốc,
`.importlinter`, `DEBT.md`, `changes/B2-05b.md`).
Commit `b6fbe1e` `fix(quality): close review round one debts NO-226..229` — 52 ký tự, đúng Conventional Commits,
trailer `Prompt: B2-05b` có.

## Finding (lượt 2)

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | RES-04 | `_discard_orphan` bắt `(AppError, OSError)` và docstring khẳng định đó là **toàn bộ** lỗi `ObjectStorage.delete` ném. Không đúng với bộ điều hợp S3: `packages/storage/s3.py:87-90` `_s3_errors` chỉ đổi `S3Error` **5xx** thành `AppError`, còn `S3Error` **4xx** (`AccessDenied`, `NoSuchBucket`) **ném nguyên vẹn** — không phải `AppError`, không phải `OSError`. Cấu hình least-privilege cho phép `PutObject` mà quên `DeleteObject` là ca có thật; khi đó lỗi 409/422 vẫn bị `S3Error` đè trong `finally` đúng như NO-228 mô tả. Test chỉ đi qua `LocalDiskStorage`, nơi `disk_errors` (`port.py:146-151`) bảo đảm chỉ còn `AppError`/`OSError`, nên cổng không thấy. | `apps/api/quality/service.py:281-287` | Sửa gốc nằm ở `packages/storage` (chủ B0-04), mà khối [12] cấm B2-05b chạm: cho `ObjectStorage.delete` một hợp đồng lỗi đóng (một `StorageError` gốc, hoặc `_s3_errors` bọc nốt `S3Error` 4xx), rồi `_discard_orphan` bắt đúng lớp đó. Trước mắt: một dòng `DEBT.md` mới (cùng khuôn `NO-225`) và sửa docstring cho khỏi khẳng định thừa. |
| 2 | P3 | TEST-05 | `assert 1 < len(names) <= workers` **không** chứng minh được điều docstring của test hứa ("hàng dựng lại theo số mới", 3 việc chạy đồng thời). Với `workers = 3` mà pool vẫn kẹt ở 2 luồng: 3 lời gọi vẫn qua semaphore (đã dựng lại), 2 chạy và chặn ở `gate`, lời thứ ba **xếp hàng** trong executor và chỉ vào `rectify` sau `gate.set()` — `threads.append` vẫn chạy đủ 3 lần nên `ran == 3`, còn `len(names) == 2` vẫn lọt `1 < 2 <= 3`. Tức bản thay cho `_pool(3)._max_workers` yếu hơn bản bị thay: nó chỉ còn kiểm nửa semaphore. | `apps/api/quality/tests/test_processing.py:234` | Siết thành `assert len(names) == workers` — tất định, vì khi pool đúng cỡ cả `workers` lời gọi cùng chặn trong `gate.wait` nên phải nằm trên `workers` luồng khác nhau (vòng `workers = 2` hiện đã ngầm đòi đúng thế). |
| 3 | Nit | MNT-02 | Docstring hàm lồng `scenario()` còn nói "5 lời gọi cùng lúc trên **hai** chỗ" sau khi `_saturate` đã tham số hoá `workers` (docstring hàm ngoài đã sửa đúng). | `apps/api/quality/tests/test_processing.py:185` | "trên `workers` chỗ". |

Không có finding **P0, P1 hay P2** ở lượt này. Bốn finding P3 và ba Nit của lượt 1 đã đóng đúng như mục "Từng NO" trên.

## Sổ nợ

| NO | Trạng thái đề nghị |
|---|---|
| NO-224 (MNT-05, nhánh > 400 dòng) | giữ nguyên `➖ Chấp nhận` — lượt sửa không đổi gì |
| NO-225 (R-07, bản thứ năm của `read_all_capped`) | **giữ mở** — việc của B0-04, vòng sửa này không đụng tới |
| NO-226 | **đóng** (`b6fbe1e`) |
| NO-227 | **đóng** (`b6fbe1e`) |
| NO-228 | **đóng** (`b6fbe1e`) **và** mở một dòng mới cho finding 1 (hợp đồng lỗi của `ObjectStorage.delete`, chủ B0-04) — không mở dòng mới thì phải để NO-228 mở, vì câu chữ của nó còn đúng trên đường S3 |
| NO-229 | **đóng** (`b6fbe1e`) |
| mới | finding 1 (P3 RES-04, chủ B0-04) và finding 2 (P3 TEST-05, chủ B2-05b) — mỗi cái một dòng trước khi merge (R-34) |

Phiên này **không** sửa `DEBT.md` (đúng lệnh điều phối); các dòng trên là việc của điều phối viên.

## Điểm

| Miền | Trọng số | Lượt 1 | Lượt 2 | Tích | Vì sao đổi |
|---|---|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 5 | 1,25 | thêm test phạm vi dự án cho cả ba route, bằng chứng IDOR mạnh hơn |
| CON – Concurrency & dữ liệu | 15% | 5 | 5 | 0,75 | không đổi |
| LOG – Tính đúng đắn | 15% | 4 | **5** | 0,75 | hai chốt chặn thiếu (NO-226, NO-227) đã đóng, mỗi cái có test đỏ-trước chắc chắn |
| PERF – Hiệu năng | 10% | 5 | 5 | 0,50 | không đổi |
| RES – Chịu lỗi | 10% | 4 | 4 | 0,40 | `finally` không còn đè lỗi trên đường local, nhưng đường S3 4xx vẫn hở (finding 1) |
| DB, API – Migration & contract | 10% | 5 | 5 | 0,50 | không chạm |
| TEST – Kiểm thử | 7% | 4 | **5** | 0,35 | hết `sleep` cố định, hết đọc thuộc tính riêng tư, có test 404 `floor` còn thiếu; trừ lại bởi finding 2 nhưng ròng vẫn tăng |
| OBS, OPS – Vận hành | 5% | 5 | 5 | 0,25 | thêm log `quality_orphan_delete_failed` đúng khuôn |
| MNT – Bảo trì | 3% | 4 | 4 | 0,12 | NO-224 chấp nhận, NO-225 còn mở, finding 3 |
| **Tổng** | **100%** | 4,65 | | **4,87 / 5** | |

## PHÁN QUYẾT: APPROVE

Không P0, không P1, không P2; 4,87 ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

Vòng sửa làm đúng việc được giao và làm bằng bằng chứng: ba trong bốn P3 và cả ba Nit của lượt 1 đóng thật, mỗi cái
kèm test mà tôi kiểm được là **phải đỏ** trên `73066fb` từ chính mã của diff, chứ không phải test viết vừa khít hành vi
sẵn có. NO-227 là chỗ dễ vá triệu chứng nhất và đã không bị vá: luật kiểm mới khớp đúng quy ước của `order_corners`,
người sinh thứ tự góc trong repo, nên cả họ tứ giác xoay — không chỉ hình thoi 45° trong ví dụ của lượt 1 — đều qua.
NO-229 không chỉ bỏ `asyncio.sleep` mà thay bằng khuôn `asyncio.wait` có `assert done` chặn treo câm.

Ba finding còn lại đều P3/Nit và **không chặn merge**: một hợp đồng lỗi hở ở `packages/storage` mà B2-05b bị cấm chạm,
một `assert` nới tay trong test, một dòng docstring cũ. Điều kiện kèm theo là hành chính: điều phối viên ghi dòng
`DEBT.md` cho finding 1 và finding 2 trước khi merge (R-34), và chỉ đóng NO-228 khi dòng mới của finding 1 đã có.

Phạm vi kiểm là **đích** theo R-33b: bước 1–4 chạy thật, mã thoát 0; bước 5–8 "chưa chạy" với lý do kiểm được bằng mã,
không phải bằng suy đoán. Merge thuộc phiên gọi review này — phiên review không tự merge.
