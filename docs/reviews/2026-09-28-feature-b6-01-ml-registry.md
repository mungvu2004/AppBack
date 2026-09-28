# Review merge feature/b6-01-ml-registry → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (độc lập, R-37) · Commit đầu nhánh: `44a91173a5cb`
- Phạm vi kiểm: **đích** — cổng đầy đủ đọc từ log việc gộp @`44a91173a5cb37cde9e07afea2509c73806dcade`
  (người dùng chốt: không chạy lại pytest đầy đủ).
- Cổng tự chạy: `bash tools/verify/run.sh verify --steps 1,2,3,4` trong worktree review @ cùng sha →
  **mã thoát 0** (log: pane RUNNER, `b601rev-v14`).
- Cổng đầy đủ (nguồn: `backend/dieu-phoi/chay/B6-01/E/full.log`, dòng cuối `EXIT=0 SHA=44a91173…dace` — khớp sha review):

  | # | Bước | Trạng thái | Nguồn |
  |---|---|---|---|
  | 0 | làm ấm node_modules | đạt | log gộp |
  | 1 | `ruff format --check` | đạt | **tự chạy** |
  | 2 | `ruff check` | đạt | **tự chạy** |
  | 3 | `mypy --strict` | đạt | **tự chạy** |
  | 4 | `lint-imports` (9 hợp đồng giữ) | đạt | **tự chạy** |
  | 5 | `coverage run -m pytest` → `coverage_gate` | đạt | log gộp |
  | 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) | log gộp |
  | 6 | `lint_migrations` → `migrate_check` | đạt | log gộp |
  | 7 | H1 H3 H4 H5 (`tools.contract.check`) @ AppFront `9cf0b0bfffbd` | đạt | log gộp |
  | 8 | `openapi` | đạt | log gộp |

- Test: **6002 qua / 0 hỏng**, 9 deselected (31 phút 38).
- Độ phủ (log gộp): tổng dòng **99,57 %** · nhánh **98,43 %**; `apps/api/admin_ml_registry`
  99,33 % / 95,24 %; `packages/db` 97,07 % / 95,76 %; `packages/testing` 99,51 % / 98,62 %;
  tập file bị chạm 99,41 % / 95,31 % — mọi gói ≥ 90/90.
- `case_gate`: 73 thao tác đã mount, **đạt**; 3 cảnh báo đều là thao tác cũ ngoài nhánh này
  (`files_read_object`, `health_live`, `health_ready` không có dòng BE-BIND).

## Đã đối chiếu (không tin báo cáo)

- Cây sạch; 8 commit, cả 8 đúng Conventional Commits ≤ 72 ký tự và có trailer `Prompt: B6-01`.
- `changes/B6-01.md` có mặt (12 dòng).
- Diff **chỉ thêm**: 26 tệp, 5069 thêm / 0 xoá. Không đụng `docs/charter/*`, `uv.lock`,
  `tools/contract/APPFRONT_SHA`, `pyproject.toml` gốc, `conftest.py` gốc.
- `docs/contracts/openapi.json`: thuần thêm, đúng **4** path `/api/admin/ml/model-families`,
  `/api/admin/ml/model-families/{family}/active`, `/api/admin/ml/model-versions`,
  `/api/admin/ml/model-versions/{model_version_id}` + schema của chúng.
- Không `# pragma: no cover`, không `skip`/`xfail`; một `# type: ignore[call-arg]` và một
  `# noqa: S603` — cả hai có mã và lý do.
- **N26** (`upload.py`): `await db.rollback()` là câu đầu handler; parser luồng
  `python_multipart.MultipartParser` trên `request.stream()` — không `UploadFile`/`form()`/`body()`;
  luật phần đúng (metadata ≤ 16 KiB trước, weights sau, phần thứ ba → 422 ngay ở header);
  9 byte đầu quyết định định dạng **trước** `storage.put` (`upload.py:295`); checksum lệch →
  `storage.delete` + 422 `MODEL_CHECKSUM_MISMATCH` (`upload.py:302-304`); lỗi sau `put` bắt hẹp
  `(SQLAlchemyError, ClientDisconnect, ValueError, AppError)` → `delete` rồi ném lại (`upload.py:306-310`);
  task đánh giá đăng ký **trong** giao dịch qua `on_after_commit` rồi `commit` (`upload.py:262-273`).
  Bộ nhớ phẳng có đo thật: `test_upload_version_keeps_the_pool_free_while_streaming`
  (64 MiB, `DB_POOL_SIZE=1`, `tracemalloc` peak < 32 MiB, `pool.checkedout() == 0`).
  Đính chính mục 3 của điều phối viên (đổi lỗi `put` thành 413) đúng là **sai**: `local.py:98`,
  `s3.py:135` đã ném `PAYLOAD_TOO_LARGE`; `upload.py` không bắt — đúng.
- **N24** (`service.py`): so revision **trong câu** `UPDATE … WHERE family AND revision = :base
  RETURNING` (`service.py:114-121`), không so trong Python; khoá `model_families` `FOR UPDATE` →
  `model_versions` `FOR SHARE` (BE-00 §9); `null` chỉ cho `wallSegmentation` (`service.py:151-152`);
  bốn mã 422 đúng điều kiện và đúng thứ tự (họ lệch → định dạng → chưa đánh giá); lượt lặp C09b và
  lượt đặt lại đúng bản đang kích hoạt đều trả hiện trạng, **không** tăng revision và **không** ghi
  nhật ký (`service.py:145-146`, `service.py:155-156`);
  `record_activity(MODEL_ACTIVATE, object_code=versionId | family, object_label=label | "đường cổ điển")`
  khớp đúng prompt [6] bước 5.
- **Dây** (K01/K02): `ModelVersionOut`/`ModelFamilyOut` khớp `adminMl.ts` strict — không `weightsKey`,
  `pinnedName`, `evaluationAttempts`, `evaluationErrorCode`; `WireModel` bỏ trường `None` nên trường
  vắng thì vắng; `metrics_out` đòi đúng **một** khoá `FAMILY_METRIC[family]` và ép `float`
  (`schemas.py:112-123`). N23 lấy thứ tự từ `MODEL_FAMILIES` = `pipeline.ts:50-52`, không `nextCursor`.
  N25 cursor `(created_at, id)` so bằng `tuple_(...) < (...)`, `family` ký vào cursor, trần 200.
- **registry/jobs/cli**: `set_evaluation` đủ luật (mã tạm → `False`; `completed` ghi đè `failed`;
  `running` không hồi sinh `failed`; `completed` bất biến); `register_trained_version` dùng
  `INSERT … ON CONFLICT DO NOTHING` + phân xử J06, tham số sai → `ValueError`; requeue lùi
  `after_s × 2^(attempts−1)` bằng SQL, `FOR UPDATE SKIP LOCKED`, hết lượt → `RETRY_EXHAUSTED`
  `UPDATE` thẳng dưới khoá đang giữ (`jobs.py:80-84`); purge theo lô, `_purge_chunk` gọi storage
  **ngoài** session; CLI mọi việc trong `main()`; `lint-imports` xanh (không `fastapi`/`torch`/`apps.ml`).
- **Migration + dữ liệu gốc**: CHECK/index khớp model 1-1; hai checksum bản gốc chép **đúng**
  `PINNED["yolov8n"].onnx_sha256` và `PINNED["rapidocrRec"].onnx_sha256`
  (`packages/ml_contracts/pinned.py:123,139`); id cố định `mdl_01KB60100000000000000000{01,02}`;
  `seed_rows` thuần, `"0"*64` → `failed` + `MODEL_NOT_PINNED` và họ **không** kích hoạt
  (`test_seed.py:64,78`); expand thuần (create table + index + bulk_insert), `metrics`
  `JSONB(none_as_null=True)` ở model.
- **Test**: Postgres/Redis/MinIO thật (`_CountingStorage` bọc kho thật, `broker_redis_sync`), không
  mock dịch vụ; đủ gạch khối [8]; `cases.toml` `extra = ["C16"]` cho `ml_upload_version`; hai lịch có
  `__J01`/`__J06`.
- **Lệch khỏi prompt** của bốn báo cáo (p/b/c/d): 14 mục, tất cả có lý do đứng được và đã được kiểm
  lại trên mã (không mục nào thành finding). `bao-cao-B6-01.md` của việc gộp E **chưa có** lúc review —
  không phải điều kiện dừng của skill, mọi khẳng định đã tự kiểm từ log + diff.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-34 / MNT-01 | `bao-cao-c.md` §6 nêu một nợ ("`dinh-chinh.md` mục 3 và `ghi-chu-hop-dong.md` §2.2/§2.5 lệch mã thật": `kinds.MODEL_UPLOAD` → `ActivityKind.MODEL_UPLOAD`, `MultipartCallbacks` chỉ có dưới `TYPE_CHECKING`, `put` đã tự ném 413) nhưng `DEBT.md` không có dòng `NO-…` nào. Việc C bị whitelist cấm sửa `DEBT.md`, nên đây là việc của người điều phối. | `DEBT.md` (thiếu dòng; dòng cuối là NO-258) | Thêm `NO-259` trước hoặc ngay sau lượt merge: sửa `backend/dieu-phoi/chay/B6-01/ghi-chu-hop-dong.md` §2.2/§2.5 và `dinh-chinh.md` mục 3 theo mã thật; không phải sửa mã. |
| 2 | P3 | PERF-02 / R-24 | Vòng requeue gọi `request_evaluation`, mà hàm này `SELECT … FOR UPDATE` lại **từng dòng** đã bị câu lô khoá sẵn: lô 100 dòng → 100 lượt đi-về DB thừa mỗi 5 phút. Docstring của `run_model_orphan_purge` tự nêu "không N+1" trong khi nhánh requeue lại N+1. | `apps/api/admin_ml_registry/jobs.py:79` (qua `registry.py:272`) | Tách lõi nhận `row` đã khoá (`_bump(row, clock)`) cho vòng lô dùng, giữ `request_evaluation` cho người gọi lẻ; hoặc thêm chú thích R-05 nói rõ vì sao chấp nhận lượt đọc lại. |
| 3 | P3 | R-08 | Hai hàm vượt trần 50 dòng: `register_trained_version` 59 dòng, `_create_model_versions` 68 dòng. Cả hai là thân **khai báo** (literal `.values(...)`, `op.create_table`), cyclomatic 1–2, nên không khó đọc — nhưng vẫn vượt luật. | `apps/api/admin_ml_registry/registry.py:105`, `packages/db/migrations/versions/r20260928_b6_01_ml_registry.py:142` | Tách phần literal ra hằng/`_columns()` ở lần chạm sau, hoặc ghi ngoại lệ có lý do. |
| 4 | Nit | R-01 | Sáu closure trong test không có docstring: `spy` (`test_jobs.py:283`), `record` (`test_registry.py:105`), `attempt` (`test_registry.py:174,192`), `receive`/`send` (`test_upload.py:388,391`). Đều 1–2 dòng bên trong một test đã có docstring. | như trên | Một câu mỗi cái, hoặc chốt trong `RULE-CODE.md` rằng closure trong test được miễn R-01. |

Không có P0, không có P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 4 | 0,40 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,84 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0/P1 và điểm 4,84 ≥ 4,0. Nhánh làm đúng ba chỗ khó nhất của prompt và làm có bằng chứng
đo được, không chỉ có lời: N26 nhận 512 MiB qua parser luồng với `db.rollback()` mở đầu, 9 byte đầu
chặn định dạng **trước** khi ghi một byte nào vào kho, và một test thật đo `pool.checkedout() == 0`
cùng đỉnh `tracemalloc` < 32 MiB trên tệp 64 MiB; N24 quyết thắng thua trong chính câu `UPDATE`
với thứ tự khoá `model_families` → `model_versions`; dữ liệu gốc chép đúng hai `onnx_sha256` đã ghim
và để họ chưa ghim ở `failed`/không kích hoạt. Dây khớp `adminMl.ts` strict, migration expand thuần,
`openapi.json` chỉ thêm 4 path đúng phạm vi, cổng đầy đủ của việc gộp xanh đúng sha này
(6002 test, tổng 99,57 %/98,43 %, mọi gói ≥ 90/90).

Bốn finding đều không chặn merge. **Điều kiện kèm theo (P2-1):** người điều phối thêm dòng `NO-259`
vào `DEBT.md` cho nợ mà `bao-cao-c.md` §6 đã nêu — nợ ấy nằm ở tài liệu điều phối, không ở mã, nên
không đòi vòng sửa trên nhánh. Finding 2–4 gom vào FIX kế tiếp chạm `apps/api/admin_ml_registry`.

Phiên này **không merge** — việc merge thuộc phiên gọi.
