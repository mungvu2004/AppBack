# Review merge feature/b6-03a-training-jobs-api-bridge → main (lượt 2)

- Ngày: 2026-10-01 · Reviewer: phiên `/merge-review` lượt 2 (phiên độc lập, R-37) · Commit đầu nhánh: `89904c5bc7fe`
- Cổng: phạm vi **đầy đủ** (R-33b đk 1 + 3 — nhánh chưa có lượt đầy đủ xanh nào, vòng sửa chạm
  `packages/db/models/` và revision); không chạy lại, dùng log cổng đầy đủ của lớp gộp trên **đúng** sha
  `89904c5bc7fe`: `backend/dieu-phoi/chay/B6-03a/M/gate-5.log` (log trong container
  `.cache/src-out/verify/20261001T143737Z-89904c5bc7fe.log`), lệnh `bash tools/verify/run.sh verify`,
  **mã thoát 0**. Phiên review khởi động **0 container `verify-run`**.
- Độ phủ: tổng **dòng 99,51% · nhánh 98,13%**; mỗi gói bị chạm ≥ 90/90 —
  `apps/api/admin_ml_jobs` 100,00/100,00 · `apps/worker/training_bridge` 99,51/98,94 ·
  `packages/db` 97,36/95,76 · `packages/messaging` 100,00/100,00 · `packages/testing` 99,57/98,39;
  tập file bị chạm 99,76/99,32.
- Phạm vi soát: `git diff c8b69e6..8bf6485` (vòng sửa M2, 8 file) và `git diff 8bf6485..89904c5`
  (vòng sửa M3, 2 file). Nền nghiệp vụ đã soát ở lượt 1. Báo cáo đầy đủ:
  `backend/dieu-phoi/chay/B6-03a/bao-cao-review-2.md`.

## Bảng cổng (E.10 — lấy từ mã thoát thật trong `M/gate-5.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | `All checks passed!` |
| 3 | `mypy --strict` | đạt | `Success: no issues found in 1022 source files` |
| 4 | `lint-imports` | đạt | `Contracts: 10 kept, 0 broken.` |
| 5 | `pytest -n (cov)` → `coverage_gate` | đạt | `7475 passed, 183 warnings in 596.58s` |
| 5b | `pytest -m perf` → `case_gate` | đạt | `perf: 0 đơn vị bị chạm`; `case_gate: 83 thao tác đã mount, 3 cảnh báo` |
| 6 | `lint_migrations` → `migrate_check` | đạt | 21 revision; 10/10 hạng mục, gồm `model khớp DB` và `tên CHECK khớp model` |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | AppFront @ `9cf0b0bf`; H1 1890 mẫu response, H1 ngữ cảnh 64, H3 10 khoá/3 vai, H4 25 mã/26 khoá, H5 6 khung SSE |
| 8 | `openapi` | đạt | 255271 byte |

Mã thoát: **0**. Không bước nào `chưa chạy`, không bước nào `không áp dụng`.

`case_gate` đạt: sáu `op` của B6-03a (`ml_create_job` — có thêm `J09`, `ml_cancel_job`, `ml_read_job`,
`ml_list_jobs`, `ml_list_job_metrics`, `ml_list_job_logs`) đủ bộ case bắt buộc. Ba `CẢNH BÁO`
(`files_read_object`, `health_live`, `health_ready` đã mount nhưng không có dòng BE-BIND) là nợ sẵn có của
repo, không thuộc nhánh này. Log in bảng theo `op`, **không** in bảng riêng cho task/lịch; case `J` của
5 task và 3 lịch khai trong `cases.toml` và đã soát bằng mã ở lượt 1.

## Trạng thái finding của lượt 1

| # | Mức | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | P1 | **đã sửa** | cổng đầy đủ mã thoát 0, tám bước đạt |
| 2 | P1 | **đã sửa đúng gốc** | `except DEPENDENCY_ERRORS as exc` ×3, ba log có `error=type(exc).__name__`, không còn `except Exception` nào trong nhánh; test rollback đổi sang `RedisConnectionError`, thêm `test_sweep_lost_training_jobs_lets_a_non_dependency_error_surface` |
| 3 | P2 | **đã sửa** | bước 2 `All checks passed!` |
| 4 | P2 | **đã sửa** | `DEBT.md` `NO-305` trên `main` (`6c3b611`), P2, mở, chủ B6-03b + F-12 |
| 5 | P2 | **đã sửa** | `jobs.py` lấy `open_storage` từ `tasks.py`, bỏ phụ thuộc `apps.api.library.assets` |
| 6 | P3 | **đã sửa trong mã** | `arm_cancel_key` và `_claims_present` đóng client trong `finally`; an toàn vì `safe_redis()` dựng client mới mỗi lượt (`packages/messaging/redis.py:139`) |
| 7 | P3 | **đã sửa** | trần điểm kiểm theo từng điểm + test lô vượt trần giữa chừng |
| 8 | Nit | **đã sửa** | `_LOG_TEXT_MAX_CHARS` |
| 9 | Nit | bỏ qua đúng kế hoạch | squash vào `main` xoá hai commit gộp nhánh con |

## Finding của lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 13 | **P1** → **đã sửa** ở `89904c5` | DB-01, G-01 | `TrainingMetricRow`/`TrainingLogRow` thiếu `TimestampMixin` và ba cột `Float` thiếu `info['float_reason']` ⇒ `check_conventions` trả đúng bảy vi phạm, cổng `gate-4` thoát 1 ở bước 5. Revision cũng thiếu hai cột. **Không** do vòng sửa M2 gây ra (nằm sẵn từ `c8b69e6`); lần đầu lộ ra vì `gate-4` là lần đầu bước 5 chạy tới. | `packages/db/models/admin_ml_jobs.py:92,117,102-104`; `r20261001_b6_03a_training_jobs.py:115,142` | Đã sửa cả hai nửa: mixin cho hai lớp, `_METRIC_FLOAT` cho ba cột, `_time(..., now=True)` ×2 trong hai `op.create_table`. `migrate_check` `model khớp DB` đạt. |
| 10 | Nit | LOG-02 | `stored += 1` đếm cả điểm mà `on_conflict_do_nothing` không chèn; lô trộn điểm trùng tiêu hụt ngân sách trần nó không dùng. Vô hại: trần mặc định 200000 so với lô ≤ 500. | `apps/worker/training_bridge/tasks.py:204` | Tăng `stored` theo `rowcount` nếu có ngày trần hạ xuống cỡ lô. |
| 11 | Nit | R-08 | `run_training_metrics` dài 51 dòng, quá trần ≤ 50 một dòng. | `apps/worker/training_bridge/tasks.py:157` | Tách khối `insert` thành helper, hoặc gộp hai câu cuối của docstring. |
| 12 | Nit | TEST | Việc thu hẹp `except` của chính `_claims_present` chỉ có test gián tiếp (test mới monkeypatch `_claims_present`). Nhánh `except DEPENDENCY_ERRORS` có test (`__J07` giết Redis). | `apps/worker/training_bridge/tests/test_jobs.py:692` | Không bắt buộc. |
| 14 | Nit | MNT-04 | `info=_METRIC_FLOAT` truyền cùng một đối tượng dict cho ba cột nên `column.info` dùng chung. | `packages/db/models/admin_ml_jobs.py:105-107` | `info=dict(_METRIC_FLOAT)` nếu muốn chắc. |

Không P0; không P1 còn mở; không P2/P3 mới.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 (Nit #10, #11, #14) | 0,12 |
| **Tổng** | **100%** | | **4,97 / 5** |

## PHÁN QUYẾT: APPROVE

Nhánh được vào `main` ở sha `89904c5`. Hai vòng sửa đóng toàn bộ chín finding của lượt 1 cộng P1 #13 mà
lượt 1 không thể thấy, và đều sửa **đúng gốc** chứ không vá triệu chứng: #2 bắt đúng tập lỗi phụ thuộc đã
có trong repo rồi để lỗi lạ nổi lên, kèm test khoá hành vi đó; #6 đóng client trong `finally` thay vì ghi
nợ; #7 đổi hẳn luật trần sang từng điểm; #13 sửa cả model và revision nên `migrate_check` hạng mục
`model khớp DB` đạt. Hai `type: ignore` bị bỏ được thay bằng kiểu thật, không bằng cách che. Cổng đầy đủ
mã thoát 0 trên đúng sha phán quyết với tám bước `đạt`, độ phủ mọi gói bị chạm ≥ 90/90.

Bốn Nit (#10, #11, #12, #14) tác giả tự quyết, không chặn merge. Gộp bằng **squash** như BE-00 §13.2.
Phiên review không merge.
