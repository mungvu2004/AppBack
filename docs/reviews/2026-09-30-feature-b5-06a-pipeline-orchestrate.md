# Review merge feature/b5-06a-pipeline-orchestrate → main — lượt 1

- Ngày: 2026-09-30 (`date -u` 2026-09-30T04:26Z) · Reviewer: phiên `/merge-review` lượt 1, độc lập tác giả
  · Sha review: `1bfa85091a69326e682fdba98c4e949104f87f70` (`^{tree}` = `4165150f30283761de119427612659c2d4faed42`)
  · Worktree riêng `b5-06a-review` ở `--detach 1bfa850`, không sửa mã, không merge.
- **PHÁN QUYẾT: ✅ APPROVE — 4,73/5.** Không finding `P0`/`P1`. Hai `P2` (cả hai nằm trong test, miền TEST)
  phải có ticket `DEBT.md` trước khi đóng; bốn `P3` không chặn merge.
- Phạm vi: `git diff main...1bfa850` — **21 file, +2806/−0**, đúng mục sở hữu:
  `apps/worker/pipeline_orchestrate/**` (16), `packages/db/models/pipeline_orchestrate.py`,
  `packages/db/migrations/versions/r20260930_b5_06a_run_models.py`,
  `packages/testing/factories/pipeline_orchestrate.py`, `changes/B5-06a.md`. Không file nào khác:
  không `docs/charter/*`, `docs/contracts.toml`, `openapi.json`, `uv.lock`, `tools/**`, `conftest.py` gốc,
  `pyproject.toml`, `.importlinter`, `DEBT.md`. Không endpoint, không thư viện mới → khối [12] không chạm.
- `1bfa850` là **đầu** nhánh `feature/b5-06a-pipeline-orchestrate` và cũng là `HEAD` của worktree gộp
  `b5-06a-merge` — không commit nào sau sha review (`git log 1bfa850..feature/…` rỗng).

## Cổng (E.10 — lấy từ mã thoát thật, **không** chạy lại)

`Phạm vi kiểm: đầy đủ` (R-33b) — prompt mới cả một app + một revision, lớp gộp đã chạy 8 bước.
Reviewer **không** chạy thêm container `verify-run` nào: mọi finding dưới đây là tĩnh (đọc mã, đọc
kiểu của `InferStepPayload`), không cần tái hiện bằng test.

Log: `backend/dieu-phoi/chay/B5-06a/M/gate3.log`, `M/gate.sha` = `1bfa85091a69326e682fdba98c4e949104f87f70`;
log trong container `20260930T040907Z-1bfa85091a69.log` → **đúng sha**. Cây worktree review khớp
`1bfa850^{tree}`, `git status --porcelain` rỗng.

|  # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | **7137 passed**, 0 failed, 508,26 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf 2 test (8,77 s); `case_gate: đạt`, 77 thao tác, 3 cảnh báo cũ |
| 6 | `lint_migrations` → `migrate_check` | đạt | 20 revision, 1 head, 10/10 mục `migrate_check` |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | 83/83 bản đồ, 80 mount, H1 1772 mẫu, H5 6 khung SSE |
| 8 | `openapi` | đạt | |

**Mã thoát: `EXIT=0`.** Không bước nào "không áp dụng", không bước nào "chưa chạy".

**Độ phủ** (`coverage_gate: đạt`, ngưỡng 90/90): tổng dòng 99,50% · nhánh 98,13% ·
`apps/worker/pipeline_orchestrate` 97,60% / 97,22% · `packages/db` 97,22% / 95,76% ·
`packages/testing` 99,56% / 97,58% · tập file bị chạm 97,80% / 94,87%. Không `# pragma: no cover`,
không `skip`, không `xfail` trong phạm vi (K24 — đã grep toàn bộ 21 file).

**Bước 5b, `orchestrate_pipeline_start`:** `case_gate` chỉ in dòng `[[task]]` khi **hỏng**; log không có
dòng `HỎNG`/`task` nào và kết `case_gate: đạt`. `cases.toml` khai `require = ["J02","J03","J05","J08","J09","J10"]`,
công cụ tự đòi thêm `J01`, `J06`; sáu + hai hàm đều có đúng tên (`test_start_cases.py`, `test_start_core.py`).

## Đối chiếu "Lệch khỏi prompt" (7 lệch biết trước — đã phán)

| # | Lệch | Phán |
|---|---|---|
| 1 | `run_pipeline_start(..., settings=None)` thêm tham số | **Chấp nhận.** `start.py:213-220` ghi rõ lý do; test hạ trần (`J03`, `U06`) không phải đổi biến môi trường của cả tiến trình → không đua giữa các worker xdist. Mặc định `get_orchestrate_settings()` nên đường chạy thật không đổi. |
| 2 | Chữ ký nội bộ `preprocess.py` (`PageSource`, `PagePlan`, `PreparedPage`, `choose_path`, `prepare_page`) | **Chấp nhận** — điều phối định, prompt [6] không khai chữ ký nội bộ. `choose_path` là hàm thuần, `prepare_page` không nhận session: đó chính là cách giữ K36 kiểm được (`test_start_runtime.py:68`). |
| 3 | `OrchestrateSettings` đọc từ biến môi trường, không `ClassVar` | **Chấp nhận** — [5] chỉ khai giá trị mặc định; `BaseSettings` là khuôn nhà (`packages/storage/settings.py:30`). Tên trường lệch kiểu chữ → `P3-05`. |
| 4 | `cases.toml` bỏ `U01, U02, U04, U06` khỏi `require` | **Chấp nhận** — người dùng chốt, `NO-294` đã ghi. Kiểm lại: bốn test `test_orchestrate_pipeline_start__U01/U02/U04/U06` **có thật** (`test_start_cases.py`) và **chạy đạt** ở bước 5 (`gate3.log:333` bắt `__U02`). Sổ của `case_gate` mất, phép kiểm không mất. |
| 5 | `__J01_smoke` bỏ marker `perf` (`4b63871`) | **Chấp nhận việc bỏ marker, ghi finding cho phần mất kèm** → `P3-04`. Bỏ marker là **bắt buộc** (`case_gate` cấm test `perf` mang mã case) và marker chưa bao giờ là thứ kiểm trần. Nhưng trần 5 s của [8] **hiện không được kiểm ở đâu cả**: `J01_WAIT_S = 30.0` chỉ là trần chờ chống treo, thời gian chỉ `logging`, không `assert`. |
| 6 | B: vượt trần byte bản gốc → `IMAGE_TOO_LARGE`; `put(upload_page)` luôn ghi PNG của `encode_png`; trang có sẵn đọc với trần `PIPELINE_PAGE_MAX_BYTES` | **Chấp nhận.** [6] không định mã cho ca vượt byte; `IMAGE_TOO_LARGE` là mã gần nhất và vẫn là `PermanentError` (không thử lại vô ích). Luôn ghi PNG đã chuẩn hoá là **điều kiện** để `U01` (EXIF xoay), `U02` (PNG 16-bit alpha, JPEG CMYK) đúng: `pages/{i}.png` phải là RGB 8-bit. Trang có sẵn là PNG do chính ta ghi nên đo bằng trần trang, không trần bản gốc. |
| 7 | Hai nhánh `None` của `upsert_drawing`/`save_assessment` (`start.py:125`, `:140`) không phủ được; `fail_pipeline_start_core` tách khỏi `on_failed` đồng bộ | **Chấp nhận.** `upsert_drawing` tự `lock_run` lại chính lượt GD2 đang giữ (`apps/api/drawings/drawings.py`), nên trong GD2 nó không thể trả `None`; giữ nhánh là phòng thủ đúng chỗ, và `coverage_gate` vẫn đạt nên không cần `pragma`. Tách lõi async là **bắt buộc**: `on_failed` của `define_task` đồng bộ, `runner().run(...)` cần một coroutine (`tasks.py:37-44`). |

## Soát trọng tâm — đạt

- **K36.** GD1 (`_gd1`) đọc dưới `lock_run` rồi `session_scope` **thoát** ở `start.py:221-223`;
  `prepare_page` không nhận session; GD2 mở session mới (`_commit_gd2:196`). `after_commit_idle(db)` gọi sau
  **mọi** commit: `start.py:223` (GD1), `:201` (GD2), `:248` (`fail_…_core`). Bất biến có test thật, không
  mock: `test_start_runtime.py:68` chặn `render_pdf_page` bằng `threading.Event` rồi đọc
  `engine.pool.checkedout() == 0`.
- **Gửi task chỉ qua `on_after_commit`.** `dispatch.py:63` là lời gọi `send_task` **duy nhất**; không
  `send_task` trực tiếp ở đâu trong gói. Rollback bỏ callback đang chờ (`packages/db/hooks.py:5`) nên nhánh
  `False` của `_gd2` không để lại thông điệp mồ côi — `test_dispatch.py` `…rollback_leaves_queue_empty`
  và `__J09` khẳng định hàng rỗng.
- **J06.** `run.current_step != STEP` → `publish_progress_after_commit(db, run.upload_id)`, commit, dừng;
  **không** `queue_infer`, không `ml.infer.*` (`start.py:83-86`), đúng [6] và đúng `step_done` của B5-06c.
- **Thứ tự [6].** GD1: `lock_run` → mismatch → bước khác → `load_pins`/`pin_models(active_versions)` →
  `pending` → `record_step(running)` → `lock_run` lại → đọc `upload`, `level_id`, `current_drawing`,
  `load_assessment` **sau** khoá. GD2: `lock_run` → `upsert_drawing` → `save_assessment` →
  `record_step(completed)` → `set_step_requeue(0)` → `load_pins` → `queue_infer`. Khớp từng bước.
- **Dọn trang khi hỏng.** `_commit_gd2` đặt `committed = True` **sau** khi `session_scope` thoát, nên
  commit hỏng cũng dẫn tới `storage.delete(page.created_key)`; `finally` không bắt ngoại lệ (lỗi vẫn nổi
  lên cho `define_task`). `created_key` chỉ được đặt khi `done.png is not None`, tức chỉ với khoá
  `new_page_key` — **không bao giờ** là `pages/{i}.png` (`preprocess.py:278-280`, `:240-257`).
  `__J09` kiểm bằng `_new_pages(tmp_path) == []` trên kho đĩa thật.
- **`fail_pipeline_start`.** `start.py:244` chỉ ghi khi `run is not None and run.current_step == STEP`;
  hai test (`__fail_marks_preprocess_failed`, `__fail_skips_run_past_preprocess`) phủ cả hai ngả.
- **Ba đường (i)/(ii)/(iii).** `choose_path` (`preprocess.py:132-139`) đúng ba điều kiện #31/#32, kể cả ca
  "upload mới trên tầng đã nắn tay" → về (iii) (`drawing.upload_id != source.upload_id`), có test riêng.
- **K13 `max_pixels`.** Có ở **mọi** lời gọi: `render_pdf_page` (`:169`), `load_raster` (`:172`, `:211`),
  `rectify` (`:194`). Mọi việc ảnh qua `_offload` → `asyncio.to_thread`; `VisionError` → `PermanentError`
  cùng mã (`:142-147`). Loại tệp lạ hoặc thiếu `original_key` → `PermanentError("FILE_TYPE_MISMATCH")` (`:214`).
- **`px_per_paper_mm`.** `effective_dpi(*size_pt, PDF_DPI, MAX_PIXELS) / 25.4 * k` (`:283-284`);
  `k = homography.width_px / max(|TR−TL|, |BR−BL|)` của quad **nguồn** (`_quad_scale:181`, đúng hai cạnh
  trên/dưới); `identity` → `1.0` (`:193`); raster, đường (i), trang có sẵn → `None`. Ba test riêng.
- **`pins` "một lần" nguyên tử.** `pin_models` `ON CONFLICT DO NOTHING … RETURNING` (`:44-50`);
  `record_used` `UPDATE … WHERE NOT (used ? :family)` + `rowcount` (`:55-61`); `mark_persisted`,
  `mark_artifacts_purged` `WHERE <cột> IS NULL` + `rowcount`. **Không** đọc-rồi-ghi ở đâu (lần `load_pins`
  trước `pin_models` ở `start.py:87` chỉ là đường tắt, tính đúng nằm ở `ON CONFLICT`). `ValueError` đúng ba
  ca (thiếu họ, revision < 0, count < 0); `mark_persisted` đưa `step_requeue_count` về 0.
- **Model ↔ revision.** Cột, hai `CHECK`, FK `ON DELETE CASCADE`, chỉ mục một phần
  `(run_id) WHERE artifacts_purged_at IS NULL` khớp từng dòng giữa
  `packages/db/models/pipeline_orchestrate.py` và `r20260930_b5_06a_run_models.py`; expand thuần
  (`create_table` + `create_index`), `down_revision = r20260929_b6_02` → một head; `downgrade` bỏ bảng.
  `migrate_check` 10/10 gồm "model khớp DB" và "tên CHECK khớp model". Test CASCADE có thật.
- **`queue_infer`.** Không commit; closure bắt giá trị bằng **tham số mặc định** (`dispatch.py:59`), không
  bắt muộn biến vòng lặp (K18); bỏ họ đã có trong `pins.used` (`:46`). Không `chord`/`group`/`chain` (K34).
- **Ma trận [8] đủ.** 57 test. `J01`, `J01_smoke`, `J02`, `J03`, `J05`, `J06`, `J08`, `J09`, `J10`, `U01`,
  `U02`, `U04`, `U06` + mọi nhóm "theo việc" ([8]): `px_per_paper_mm` ×3, `queue_infer` ×3, chạy lại sau #31
  ×2, khoá ×1, `pins` ×8, K36 ×1, bộ nhớ ×1, ranh giới AST ×1. Dịch vụ **thật** (K23): Postgres,
  Redis (`LRANGE` qua `queued_payloads`), kho đĩa `LocalDiskStorage`; không `fakeredis`, không
  `task_always_eager`, không SQLite. Hai test `perf` có marker + `logging` số đo.
- **Luật mã.** R-01: **mọi** hàm/lớp/hàm lồng có docstring (quét AST 21 file — 0 thiếu). Hàm dài nhất 50
  dòng, không hàm nào vượt; không hàm nào có nhánh sâu quá `C901` của bước 2. Bốn `# type: ignore` đều có
  mã **và** lý do sau mã; không `# noqa`; không `except Exception`.

## Finding

### `P2-01` · TEST · `apps/worker/pipeline_orchestrate/tests/test_start_core.py:256` — khẳng định rỗng, `J06` không thật sự kiểm "`pinned` giữ bản đầu"

```python
assert walls["model"] != version.id
```

`InferStepPayload.model` là `ModelRef` (`packages/ml_contracts/payloads.py:125`) nên trên dây nó là một
**object JSON**: cùng file, `:208` so `message["model"] == pinned[family].model_dump(mode="json")`, tức
`dict`. Vế phải `version.id` là `str`. `dict != str` **luôn đúng** — khẳng định này đạt kể cả khi
`pin_models` ghi đè bản kích hoạt mới, đúng cái mà [8] `__J06` đòi kiểm ("đổi kích hoạt giữa hai lần →
`pinned` giữ bản đầu"). `mypy --strict` không bắt được vì giá trị trong `dict[str, object]` là `object`.

Ca hỏng: nếu ai đó đổi `pin_models` thành `ON CONFLICT DO UPDATE`, `__J06` vẫn xanh.

Đề xuất (khuôn đã có ở `test_dispatch.py:85`):

```python
assert cast("dict[str, object]", walls["model"])["version_id"] != version.id
```

### `P2-02` · TEST · trùng lặp helper giữa các file test (R-02, R-07)

- `_open_run` **giống nhau từng byte** (thân + docstring) ở `tests/test_start_core.py:146` và
  `tests/test_start_cases.py:59`.
- `_run_row` cùng truy vấn + `refresh` ở `test_start_core.py:173` và `test_start_cases.py:82`;
  `_drawings` (`core:168`) / `_drawing_of` (`cases:90`) cùng `select(DrawingRow).where(floor_pk==)`.
- Hằng `"ml.infer"` khai **ba** lần: `test_dispatch.py:27`, `test_start_cases.py:52`, `test_start_core.py:49`.
- Hằng `"L-ABCDEFGHIJ"` khai hai lần: `test_dispatch.py:28`, `test_preprocess.py:35`.

Ca hỏng: đổi tên hàng ML hay luật `start_run` phải sửa 2–3 chỗ; bỏ sót một chỗ thì test vẫn xanh trên
đường cũ. Đúng khuôn của `NO-291` (B5-05, cùng nguyên nhân: nhiều việc viết song song, không có file
helper chung).

Đề xuất: gộp `_open_run`, `_run_row`, `_drawings`, `ML_QUEUE`, `LEVEL_ID` vào
`packages/testing/factories/pipeline_orchestrate.py` (file đã thuộc prompt này) hoặc một
`tests/_helpers.py` theo khuôn `apps/api/drawings/tests/_helpers.py`, các file test nhập từ đó.

### `P3-03` · MNT · `apps/worker/pipeline_orchestrate/settings.py:33` — `reset_orchestrate_settings_cache` không có người gọi

Docstring nói "Chỉ cho test và CLI", nhưng grep toàn repo: **không** test nào, **không** CLI nào gọi. Test
hạ trần bằng tham số `settings=` (lệch #1) nên hàm này chết từ lúc viết; thân hàm cũng chưa được phủ.
Đề xuất: bỏ hàm, hoặc thêm nó vào bộ `caches` của `test_start_cases.py:129` nếu `__J01_smoke` cần trần khác.

### `P3-04` · PERF · trần 5 s của `__J01_smoke` ([8]) không được kiểm ở đâu

`test_start_cases.py:53` `J01_WAIT_S = 30.0` là trần **chờ** (chống treo); `:176` `_log.info("j01_elapsed_s=…")`
chỉ ghi số, không `assert`; hai test `perf` ở `test_start_runtime.py` kiểm pool và bộ nhớ, không kiểm độ trễ.
Bỏ marker `perf` là đúng và bắt buộc, nhưng khẳng định thời gian không cần marker — nó bị bỏ kèm.
Đề xuất: `assert elapsed <= J01_WAIT_S` (hoặc một trần rộng có biên cho xdist) để test hỏng khi task treo
vòng chờ, thay vì lặng lẽ đếm đủ 3 ở giây thứ 29; nếu chọn giữ nguyên thì ghi `DEBT.md`.

### `P3-05` · MNT · `settings.py:9,21-24` — tên trường lệch khuôn nhà

`OrchestrateSettings` dùng tên trường **CHỮ HOA** (`PIPELINE_MAX_PIXELS`), trong khi mọi `BaseSettings`
khác của repo dùng chữ thường (`packages/storage/settings.py:32` `storage_backend`,
`packages/db/settings.py`, `packages/core/settings.py`) — pydantic-settings không phân biệt hoa/thường khi
đọc biến môi trường nên cả hai chạy, nhưng `limits.PIPELINE_MAX_PIXELS` đọc như hằng module chứ không như
thuộc tính cấu hình. `MIB` (`:9`) thiếu `: Final` (hai bản khác trong repo đều có, ví dụ
`apps/api/drawings/tests/test_upload_flow.py:49`).

### `P3-06` · MNT · `apps/worker/pipeline_orchestrate/preprocess.py:270` — dựng `PreparedPage` bằng 8 đối số vị trí

```python
return PreparedPage(key, width_px, height_px, None, None, None, None, None)
```

Năm `None` liền nhau cho năm trường khác kiểu; lối ra kia (`:285-294`) dùng từ khoá. Đặt sai chỗ một `None`
vẫn qua `mypy`. Đề xuất: viết bằng từ khoá như lối ra còn lại.

### `Nit` · hai hàm khác nhau cùng tên `_write_page`

`start.py:108` (ghi `drawings` + `quality_assessments`) và `preprocess.py:240` (ghi object PNG lên kho) —
cùng gói, cùng tên, hai việc khác hẳn. Đề xuất `_write_rows` / `_put_rectified_page`.

## Nợ nên ghi (người điều phối ghi `DEBT.md`, reviewer không sửa file đó)

| Mã đề xuất | Nội dung | P |
|---|---|---|
| `NO-295` | `test_start_core.py:256` khẳng định rỗng (`dict != str`) → `__J06` không kiểm "`pinned` giữ bản đầu"; sửa thành `cast(...)["version_id"] != version.id` | P2 |
| `NO-296` | Trùng lặp helper test `pipeline_orchestrate` (`_open_run` giống từng byte ở 2 file, `_run_row`/`_drawings`, `"ml.infer"` ×3, `"L-ABCDEFGHIJ"` ×2) — gộp vào `packages/testing/factories/pipeline_orchestrate.py`; cùng nguyên nhân `NO-291` | P2 |
| — | `P3-03`…`P3-06` + Nit: gộp một dòng nợ P3/P4 cho vòng dọn `apps/worker/pipeline_orchestrate` | P3 |

## Chấm điểm

| Miền | Trọng số | Điểm | × |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 4 (`P3-04`) | 0,40 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 3 (`P2-01`, `P2-02`) | 0,21 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 (`P3-03`, `P3-05`, `P3-06`, Nit) | 0,12 |
| **Tổng** | **100%** | | **4,73 / 5** |

Không `P0`/`P1`, điểm ≥ 4,0 → ✅ **APPROVE** (RULE.md §5). Hai `P2` nằm trọn trong test, không ảnh hưởng
đường chạy thật, và phải có ticket `DEBT.md` (`NO-295`, `NO-296`) trước khi merge theo §5.
