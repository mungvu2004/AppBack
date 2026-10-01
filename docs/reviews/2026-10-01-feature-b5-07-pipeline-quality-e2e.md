# Review merge feature/b5-07-pipeline-quality-e2e → main

- Ngày: 2026-10-01 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `889b6031f174` (cây `86976a585c9e`)
- Phạm vi kiểm: **đầy đủ** (R-33b điều kiện 1 — review lượt 1 của một nhánh). Không chạy lại cổng: đọc log cổng đầy đủ
  của lớp gộp `backend/dieu-phoi/chay/B5-07/M/gate-1.log`, `M/gate.sha` = `889b603` — đúng sha đang review.
- Diff: 14 file, +1755/−0, đúng khối sở hữu [10] (`apps/worker/pipeline_quality/**`, `tests/__init__.py`, `tests/e2e/**`,
  `changes/B5-07.md`). Không chạm `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`,
  `conftest.py`, `pyproject.toml`, `tools/**`, `packages/**`, `apps/api/**`, `apps/ml/**` — khối [12] sạch.
  `git status --porcelain` rỗng. Dòng đầu mọi commit đúng Conventional Commits, thân có trailer `Prompt: B5-07`.
  Không `pragma: no cover`/`no branch`, không `skip`/`xfail`, không `# noqa` trần; đúng một `# type: ignore[method-assign]`
  có **mã và lý do** (`apps/worker/pipeline_quality/tests/test_runtime.py:191`) — K24 sạch.
- 1755 dòng nhưng chỉ ~330 dòng là mã sản phẩm (`report.py` 85, `service.py` 180, `tasks.py` 56, `__init__.py` 6,
  `cases.toml` 6) → không áp MNT-05.

## Cổng — bảng E.10 (mã thoát thật, log lớp gộp `M/gate-1.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 10 hợp đồng giữ, 0 vỡ |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt | 7264 passed, 462,44 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; case_gate 77 thao tác, 3 cảnh báo (có từ trước: `files_read_object`, `health_live`, `health_ready` — không thuộc B5-07) |
| 6 | `lint_migrations` → `migrate_check` | đạt | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | H1 1772 mẫu response; AppFront @ `9cf0b0bfffbd` |
| 8 | `openapi` | đạt | 236965 byte |

**Mã thoát: 0.**

- Độ phủ: tổng dòng **99,49%** · nhánh **98,05%**; `apps/worker/pipeline_quality` dòng **98,81%** · nhánh **92,86%**;
  tập file bị chạm dòng 98,81% · nhánh 92,86% — cả bốn con số ≥ 90/90 ([11].2 đạt).
- `case_gate` đạt. **Bảng task `check_pipeline_quality` (J01 J03 J06 J10) không được in trong log này** — case_gate chỉ in
  bảng thao tác HTTP. Suy ra từ "case_gate: đạt" + `cases.toml` khai `require = ["J03", "J10"]` (J01, J06 tự đòi): nếu
  thiếu một case J thì bước 5b đã hỏng. [11].3 chưa có bảng in; không báo "đạt" cho thứ chưa thấy.
- Bước 7 nói "H1 đạt, 1772 mẫu" nhưng **không liệt tên mẫu**, nên log này **không** chứng minh được mẫu
  `spatial_read_layer/C01_pipeline` có mặt. Đã tái hiện bằng lệnh đích — xem "Tái hiện finding 1" dưới: mẫu **không** có.
- [11].4 (dòng junit của test e2e) không in được từ log này (xdist chỉ in dấu chấm). `tests` nằm trong `testpaths` và
  7264 test đều qua, nên bốn test `tests/e2e` đã chạy và qua; thời gian từng test chỉ có trong báo cáo tác giả
  (C01_pipeline ~2 s, rerun_keeps_reviewed 2,0 s, rerun_rescales_page 2,2 s) — **chưa tự kiểm**.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | TEST-03 / API-03 | **E2E không sinh mẫu golden nào.** Test dựng client bằng `httpx.AsyncClient` thô. Bộ ghi golden `record_response` **chỉ** được gọi từ `ObservedClient.request` qua sổ `API_RESPONSE_OBSERVERS` (`packages/testing/fixtures/api.py:109-121`, một chỗ gọi duy nhất); client thô không đi qua observer nào, nên mẫu `spatial_read_layer/C01_pipeline` **không** được ghi và không có vết case. Cái tên `test_spatial_read_layer__C01_pipeline` tồn tại **chỉ** để bộ ghi lưu mẫu cho H1 giải thân N16 bằng `FloorLayerDocumentSchema` ([6] "tên để bộ ghi golden lưu N16 và H1 giải") — mục đích duy nhất của cái tên không xảy ra. Hệ quả hợp đồng: lớp **do pipeline sinh** chưa bao giờ bị FE schema kiểm (mẫu C01 hiện có trong H1 là của B3-02, dữ liệu dựng tay). Đồng thời `changes/B5-07.md:5` ("e2e sinh thêm mẫu golden N16 `spatial_read_layer/C01_pipeline`") và [11].1 ("bước 7: H1 đạt **gồm mẫu** `spatial_read_layer/C01_pipeline`") là khẳng định không có bằng chứng — cổng vẫn xanh vì bước 7 chỉ kiểm những mẫu **có mặt**. | `tests/e2e/test_pipeline_e2e.py:96-102` (client), `:217-220` (gọi N16); đối chiếu `packages/testing/fixtures/api.py:109-130`, `packages/testing/golden/recorder.py:167-190` | Đổi một dòng: `ObservedClient(transport=httpx.ASGITransport(app=e2e_app), base_url="https://appback.test")` thay `httpx.AsyncClient(...)` (giữ `base_url` vì `PUBLIC_BASE_URL` của `process_env`; `make_api_client` ghim `https://testserver`). Rồi chạy lại cổng và **chứng minh** mẫu có mặt (`SAMPLES` dir hoặc bước 7 in tên) — hoặc sửa `changes/B5-07.md:5` và xin điều phối waiver cho [11].1. |
| 2 | P2 | MNT-01 / R-08 | Ba hàm test e2e vượt trần 50 dòng: `test_spatial_read_layer__C01_pipeline` **131 dòng**, `test_pipeline_e2e_rerun_rescales_page` **83**, `test_pipeline_e2e_rerun_keeps_reviewed` **67**. R-08 không miễn cho test. | `tests/e2e/test_pipeline_e2e.py:192`, `:394`, `:325` | Tách helper như finding 3 — một đợt sửa đóng cả hai. |
| 3 | P2 | MNT-03 / R-07 | Trùng lặp giữa ba test e2e: `_read_doc` **trùng từng byte** (`:343-348` và `:418-423`); khối dựng `layer_wire` bốn danh sách + `model_copy({"reviewed": True, "source": "human"})` (`:352-359` và `:428-434`); khối mở màn `_engineer_scene` → `_user_row` → `sign_in` → `_upload_png` → `_poll_progress` lặp **ba** lần. Đúng cạm bẫy đã ghi cho hai prompt trước (NO-295, NO-300). | `tests/e2e/test_pipeline_e2e.py:343`, `:418`, `:352`, `:428`, `:199-208`, `:332-341`, `:407-416` | Nâng `_read_doc(maker, floor_pk)` lên cấp module (một bản); thêm `_run_pipeline(client, headers, project_id, level_id, png) -> dict` và `_review_first_wall(client, headers, project_id, level_id, doc, *, scale=None) -> int`. |
| 4 | P2 | TEST-02 | **Ma trận [8] thiếu một gạch.** [8] đòi ca `build_report`: "tường AI 0,5 **và** 0,9, tường `human` 0,3, tường `human` `reviewed` 0,2; ngưỡng 0,7 → `walls` 1". Test chỉ dựng **một** tường AI 0,5. Hai điều kiện loại trừ của `report.py:67` (`entity.source == "ai"`, `entity.reviewed is False`) không test nào đi qua nhánh sai — xoá cả hai khỏi `_low_confidence_count` thì không test nào đổ (nhánh 92,86% còn chỗ vì vậy). Bằng chứng tác giả biết gạch này: tham số `_wall(..., extra=...)` dựng sẵn để truyền `source="human"`/`reviewed=True` nhưng **không người gọi nào truyền** → mã chết (R-11). | `apps/worker/pipeline_quality/tests/test_report.py:113` (`extra` chết), `:128-132` (ca thiếu); nhánh `apps/worker/pipeline_quality/report.py:66-68` | Dựng đúng bốn tường của [8] trong `test_build_report__ai_below_threshold_counts_as_low_confidence` (dùng `extra`) và khẳng định `walls == 1`; nếu vẫn không dùng `extra` thì xoá tham số. |
| 5 | P3 | MNT-02 / [9] | `tests/helpers.py` nhập `apps.ml.runtime.settings` và `apps.ml.runtime.tasks_util`. [9] cấm nhập `apps.ml` **trong `apps/worker/pipeline_quality`**; ngoại lệ chỉ cấp cho e2e ([6] "ngoại lệ … e2e được nhập `apps.ml`"). `import-linter` không có hợp đồng chặn hướng `apps.worker → apps.ml` nên bước 4 xanh, nhưng lệch vẫn là lệch và không báo cáo nào khai. `reset_infer_context` chỉ e2e cần. | `apps/worker/pipeline_quality/tests/helpers.py:17-18`, `:39` | Bỏ `reset_infer_context` khỏi `_TASK_RESETS`; trong `tests/e2e/test_pipeline_e2e.py` thêm fixture `e2e_env` phụ thuộc `process_env` rồi tự gọi `reset_ml_settings_cache`/`reset_infer_context` — phần ML về đúng nơi được miễn, phần còn lại vẫn dùng chung (giữ R-07). |
| 6 | P3 | MNT-03 / R-11 | Nhánh không tới được: `if fields is None: return True`. `redis-py` `xrevrange` trả `list[tuple[str, dict]]`; phần tử thứ hai không bao giờ `None`, nên nhánh này không test nào đi qua và **không thể** đi qua (R-14: "nhánh không test được thì đừng viết nhánh đó"). | `apps/worker/pipeline_quality/service.py:72-73` | Xoá hai dòng. |
| 7 | P3 | TEST-02 | Docstring hứa nhiều hơn phần khẳng định: `test_run_quality__closed_but_not_completed_skips_without_redis` nói "không soát Redis (F2)" nhưng chỉ kiểm `outcome == "skipped"`. Xoá hẳn chặn `status == "completed"` ở `service.py:128` thì test này vẫn xanh (test chị em `before_persist` có đếm sự kiện stream, test này không). | `apps/worker/pipeline_quality/tests/test_service.py:176-190` | Thêm đếm sự kiện `upload_stream` trước/sau như `test_service.py:145,153`, hoặc `monkeypatch` `service.streams_redis` thành vật ném nếu bị gọi. |
| 8 | Nit | TEST-02 | `assert before_rerun["floorRevision"] == revision_after_review` là hằng đúng theo cách `before_rerun` được chọn ngay dòng trên. Phần kiểm thật là `next(...)` ném `StopIteration` khi không có bản nào — đúng ý [6] (bản "trước" của lượt hai mang `floorRevision` sau #35, và chỉ bản đó mang revision ấy vì `snapshots.py:238` chống trùng revision), nhưng nên viết cho rõ. | `tests/e2e/test_pipeline_e2e.py:381-382` | `assert any(v["floorRevision"] == revision_after_review for v in version_items), version_items`. |
| 9 | Nit | MNT-04 | Hai test chạm nội bộ module khác: `tasks._storage()` và `tasks._STORAGE._factory`. Hợp lý cho test, nhưng đổi nội bộ `ProcessLocal` sẽ làm hỏng test của B5-07. | `apps/worker/pipeline_quality/tests/test_service.py:307`; `tests/test_runtime.py:158`, `:219` | Để sau; nếu `packages/messaging/redis.py` công khai một `override()` thì dùng (chủ B0-05). |
| 10 | Nit | MNT-04 | Docstring **mã sản phẩm** mang vết điều phối nội bộ ("chủ: việc A", "F1", "F2", "F3", "(C2)") — người đọc `main` sau này không tra được. | `apps/worker/pipeline_quality/service.py:125`, `:139`, `:178`; `tests/helpers.py:47`, `:50` | Thay bằng trích hiến chương/prompt đã có (`[6]`, `K33`, `K36`) hoặc số `NO-`. |

### Tái hiện finding 1 (lệnh đích, một container `verify-run`)

Script `backend/dieu-phoi/chay/B5-07/R/golden-probe.sh`, log `R/golden-probe.log`: đặt `CONTRACT_SAMPLES_DIR=/tmp/samples`
rồi chạy **hai** test trong cùng một tiến trình — test e2e đang bàn và một test **đối chứng** của B3-02 đã biết là sinh mẫu:

```
$ CONTRACT_SAMPLES_DIR=/tmp/samples pytest -q -p no:randomly \
    tests/e2e/test_pipeline_e2e.py::test_spatial_read_layer__C01_pipeline \
    apps/api/spatial_read/tests/test_routes_layer.py::test_spatial_read_layer__C01
2 passed, 9 warnings in 11.25s
$ find /tmp/samples -type f
/tmp/samples/spatial_read_layer/C01-1.json
```

**Đúng một** tệp mẫu, của test đối chứng (`stem` = `C01`). Mẫu của e2e phải là
`/tmp/samples/spatial_read_layer/C01_pipeline-1.json` (`split_test_name` trả `stem` = `C01_pipeline`,
`write_sample(root / op, stem, …)`) — **không tồn tại**. Test đối chứng chứng minh cơ chế ghi mẫu hoạt động bình thường
trong đúng môi trường đó, nên nguyên nhân chỉ còn là client: e2e qua `httpx.AsyncClient`, đối chứng qua `ObservedClient`.
Finding 1 không phải suy diễn.

### Đã đối chiếu và **chấp nhận** (không thành finding)

1. **J10 đọc `PipelineRunRow.status` không khoá** (`service.py:87-91`, F2). Đúng: đọc trong `session_scope` **riêng**, sau khi
   pha 1 đã đóng session (`service.py:140-145` → `_handle_early_exit`), không giữ khoá nào. K33 cấm *ghi* `pipeline_runs`
   ngoài `record_step`, không cấm đọc. Đua xấu nhất: bỏ một lần phát bù cho lượt vừa đổi trạng thái — lần giao sau bù.
2. **Pha 3 không `rollback` khi `record_step` trả `None`** (`service.py:159-162`, F1). Đúng và cần: `record_step` đã tự
   `_abandon(FLOOR_DELETED)` (`apps/api/drawings/runs.py:417-418`), `rollback` sẽ xoá chính bản ghi hỏng đó. Có test đường
   thật (`test_service.py:224-247`) khẳng định lượt thành `failed`/`FLOOR_DELETED`. Comment nêu đúng lý do (R-05).
3. **`low_confidence` không có nhánh "thiếu `confidence`"**: `confidence` là trường bắt buộc của mọi thực thể
   `SpatialLayer`, nhánh đó không tồn tại; docstring `report.py:60-65` đã khai lệch khỏi prompt.
4. **`pins.used` khoá theo tên bước ML, không theo tên họ.** E2E kiểm đúng mã thật
   `{wallSegmentation, openingAndFurnitureDetection, dimensionReading}` (`tests/e2e/test_pipeline_e2e.py:320`).
5. **`process_env` phải `reset_infer_context()` giữa các test** — lỗi test, không phải lỗi B5-02…B5-04. Chấp nhận; chỗ
   **đặt** lời gọi là finding 5, không phải bản thân việc reset.
6. **Lệch của `bao-cao-runtime.md`:** tách "Redis treo" thành hai test (`TimeoutError` qua `wait_for` / `RedisError` tức
   thời) — **tốt hơn** spec, mỗi nhánh một khẳng định rõ. Engine riêng để đọc `pool.checkedout()` — đúng khuôn K36 của
   B5-06b. `STEP = LAST_STEP` — đúng, dùng lại hằng của B2-04 thay vì bản sao thứ hai.
7. **Nợ "ca tỉ lệ gắn trang" của `bao-cao-e2e2.md` đã đóng trong cùng nhánh** (`6fe0dab`,
   `test_pipeline_e2e_rerun_rescales_page`) → không còn nợ mở, không cần dòng `DEBT.md` (R-34 không vỡ).
   Nợ "3 ca hỏng ở `test_report`/`test_service`" của cùng báo cáo cũng đã đóng (`c3cbcfd`, `8c61a9c`): cổng 7264 passed.
8. **Ba test e2e thay vì hai** ([6] viết ca tỉ lệ như "ca thêm" của test rerun). Tách riêng tốt hơn: một test hỏng không
   che test kia; mỗi test vẫn < 120 s.
9. **Thứ tự [6] bước 1–4 của `run_quality`** khớp từng gạch: `load_context` → `lock_run` → `load_pins` → `load_document`
   → `read_settings` → `rollback` và đóng session → `build_report` → `put` ngoài mọi session → session mới `lock_run` →
   `record_step(completed)` → commit → `after_commit_idle`. K36 có test pool-một-kết-nối (`test_runtime.py:375-409`);
   K18 có hai test đếm `completed` (`test_runtime.py:203`, `:260`); `persisted_revision` NULL → `skipped` không ghi gì
   (`test_service.py:131-154`); `PermanentError(PIPELINE_RESULT_INVALID)` cho tài liệu vắng và hỏng
   (`test_service.py:158-172`, `test_runtime.py:207-238`); `wait_for` 1 s, `TimeoutError`/`RedisError` → `skipped`;
   không `notify`, không `violationFound` (`test_service.py:273-276`); `record_step` là đường ghi duy nhất; không
   `except Exception`; `after_commit_idle(db)` ngoài `async with` — đúng khuôn `pipeline_persist/service.py:259`.
10. **`quality.json`**: khoá đúng [2], `sort_keys=True`, `separators=(",",":")`, `ensure_ascii=False`,
    `confidenceThreshold` là `float`, `refId` vắng hẳn khi `None`, trần 8 MiB truyền vào `put`. Có test tất định và test
    kiểu (`test_report.py:164-173`).
11. **`cases.toml`** chỉ khai case J (`J03`, `J10`) — đúng NO-294 (`_TEST_TASK_RE` chỉ nhận `J\d{2}`). Test mang mã case
    không gắn `perf` (bước 5b: "perf: 0 đơn vị bị chạm"); trần 5 s / 30 s / 120 s là chặn treo, có comment nói rõ.
12. **K23 ở e2e**: Postgres, hai Redis, kho đĩa, Celery `pool="solo"` nghe cả `QUEUES`, `ML_BACKEND=fake`, task dò bằng
    `discover_submodules` như `celery_main`. Không `task_always_eager`, không mock DB/Redis/storage/task/`write_layer`,
    không `pytest.skip`. Hai bọc `put` của test (`_BlockingPut`, `_GatedPut`, `counting_put`) đều **gọi `put` thật**.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 1 | 0,10 |
| TEST – Kiểm thử | 7% | 3 | 0,21 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,40 / 5** |

## PHÁN QUYẾT: REQUEST CHANGES

Mã sản phẩm của `pipeline_quality` là phần mạnh nhất của nhánh: ba pha K36 đúng khuôn `pipeline_persist`, K18 và K33 có
test đường thật trên Postgres/Redis/kho đĩa, nhánh J10 soát sự kiện cuối đủ cẩn thận (trần 1 s, treo và `RedisError` đều
về `skipped`, mỗi nhánh một test riêng), `quality.json` tất định và đúng hợp đồng [2]. Ba quyết định lệch biết trước
(F1, F2, "không có `confidence`") đều đứng được và đã khai trong mã. Cổng đầy đủ của lớp gộp xanh ở đúng sha `889b603`
(mã thoát 0), độ phủ 98,81% dòng / 92,86% nhánh cho gói bị chạm. Không có P0; không tìm thấy lỗ bảo mật, đua, hay rò
session.

Chặn merge vì **một** việc, finding 1 — đã tái hiện bằng lệnh đích, không phải suy diễn: e2e dựng client `httpx` thô nên
bộ ghi golden không bao giờ chạy (chạy chung với một test đối chứng của B3-02 thì chỉ test đối chứng sinh mẫu). Cái tên
`test_spatial_read_layer__C01_pipeline` tồn tại chỉ để H1 giải thân N16 **do pipeline sinh** bằng
`FloorLayerDocumentSchema`; với client hiện tại mẫu không được ghi, nên mục nghiệm thu [11].1 và dòng
`changes/B5-07.md:5` là khẳng định không có bằng chứng — và bước 7 xanh không phủ nhận được điều đó, vì nó chỉ kiểm
những mẫu có mặt. Mốc M3 ("BE v1 đủ khi e2e pipeline chạy thật") mất đúng phần kiểm hợp đồng mà e2e được viết để mang lại.

**Để được APPROVE:**
1. Finding 1 — đổi client sang `ObservedClient` rồi **chứng minh** mẫu `spatial_read_layer/C01_pipeline` có mặt ở lượt
   cổng sau; hoặc sửa `changes/B5-07.md:5` và xin điều phối waiver tường minh cho [11].1.
2. Finding 4 — dựng đủ bốn tường của [8] để hai điều kiện loại trừ của `_low_confidence_count` có test đi qua.
3. Finding 2 và 3 (R-07/R-08 trong `tests/e2e`) nên sửa cùng vòng vì chung một đợt tách helper; nếu để sau thì mỗi
   finding một dòng `DEBT.md` trước khi merge.

Finding 5–10 ghi `DEBT.md` là đủ, không chặn merge. Vòng sửa chỉ chạm `tests/e2e/test_pipeline_e2e.py`,
`tests/helpers.py`, `test_report.py`, `test_service.py` và hai dòng `service.py` → lượt verify sau có thể là **đích**
(R-33b: diff vòng sửa không chạm migration, hợp đồng, hay ranh giới nhập), trừ finding 1 phải kiểm bước 7 nên cần
bước 5 + 7.
