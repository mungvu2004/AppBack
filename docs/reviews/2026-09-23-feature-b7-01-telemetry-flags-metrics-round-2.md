# Review merge feature/b7-01-telemetry-flags-metrics → main (lượt 2)

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (cùng phiên lượt 1, worktree `b7-01-review`) · Commit đầu nhánh: `9e90e40`
- Lượt 1: `docs/reviews/2026-09-23-feature-b7-01-telemetry-flags-metrics.md` — REQUEST CHANGES (3,16/5)
- Phạm vi lượt 2: `git diff 304d3a8..9e90e40` — ba phần:
  1. `f15437c` **FIX-081** (chủ B0-06, trailer `Prompt: B0-06` + `Fix: FIX-081`) — `apps/api/core/tests/test_app.py`;
  2. `c9fcff6` gộp `main` (`7759d46`, gồm B4-01 `c377aca`) — `git show --remerge-diff c9fcff6` **rỗng**: không chỉnh tay, không xung đột;
  3. `9e90e40` vòng sửa B7-01 — 14 file, +273/−68, đều trong `apps/api/telemetry/**`, `packages/observability/**`.
- **Nhánh mang 2 prompt (B7-01 + FIX-081 của B0-06) → gộp `--no-ff`** (R-36), giữ trailer `Prompt:` của cả hai.
- Cổng: `bash tools/verify/run.sh verify` (8 bước, không `--steps`) mã thoát **0** — log `backend/dieu-phoi/chay/B7-01/review-verify-2.log`
- Test (bước 5): **3416 qua / 0 hỏng / 4 deselected**, **528,48 s** (lượt 1: 697,69 s với 3280 test)
- Độ phủ (`coverage_gate`): tổng dòng **99,09 %** · nhánh **97,60 %**; `apps/api/telemetry` dòng **98,92 %** · nhánh **96,05 %**;
  `packages/observability` dòng **99,29 %** · nhánh **98,65 %**

## Bảng cổng (mã thoát thật, log của chính phiên review)

| bước | lệnh | trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (7 revision, 1 head) |
| 7 | `tools.contract.check` (H1 H3 H4 H5) | đạt |
| 8 | `openapi` | đạt |

Bảng con bước 7 (nguyên văn):

```
Smoke              | đạt           | 23 module schema, 83 mục bản đồ
Bản đồ đủ          | đạt           | 83 mục / 83 dòng BE-BIND không v2
Thao tác đã mount  | đạt           | 19 đã mount / 83 dòng BE-BIND
H1                 | đạt           | 542 mẫu response
H1 ngữ cảnh        | đạt           | 10 mẫu có luật ngữ cảnh
H3                 | đạt           | 10 khoá, 3 vai
H4                 | không áp dụng | B3-05 chưa hợp nhất — FE 25 mã; chưa có apps.api.rules.catalog
H5                 | đạt           | 3 khung SSE
```

Số thao tác đã mount lên 19 (B4-01 lượt duyệt: 17), tức có thêm #9 và #37. H1 đạt trên toàn bộ 542 mẫu, gồm cả hai op này.
H4 "không áp dụng" đúng BE-00 §12 (chủ B3-05 chưa hợp nhất).

`case_gate` (bước 5b, nguyên văn hai op của prompt):

```
telemetry_ingest_batch       | bắt buộc ['C01','C11','C12'] | tìm thấy ['C01','C11','C12'] | đạt
telemetry_read_feature_flags | bắt buộc ['C01','C04','C05','C12','C13','C17','C25'] | tìm thấy [đủ] | đạt
```

## Tái hiện lại (cùng script lượt 1, log `review-probe-2.log`)

```
reason_list        -> AppError VALIDATION 422 {'field': 'reason'}         (lượt 1: TypeError → 500)
reason_dict        -> AppError VALIDATION 422 {'field': 'reason'}         (lượt 1: TypeError → 500)
big_int_field      -> OK (204), trường bị bỏ                               (lượt 1: OverflowError → 500)
schemaVersion_true -> AppError VALIDATION 422 {'field': 'schemaVersion'}  (lượt 1: 204)
schemaVersion_1.0  -> AppError VALIDATION 422 {'field': 'schemaVersion'}  (lượt 1: 204)
```

PERF-04, 215 test của `apps/api/{projects,health,files}`: `METRICS_PORT` mặc định **61,46 s** · `METRICS_PORT=0` **59,69 s**
(lượt 1: 98,77 s / 62,12 s). Test riêng của prompt: 122 qua × 3 lượt liền (15,3 / 14,7 / 15,2 s).

## Finding lượt 1 → trạng thái

| # | Mức | ID | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| 1 | P1 | SEC-05 | **đóng** | `_is_valid_reason` (`isinstance(str)` trước `in REASONS`) dùng cho cả nhãn lẫn kiểm tra; test tham số hoá `reason-list`, `reason-dict` → 422, cộng test nhãn `invalid` 2.0; thăm dò → 422 |
| 2 | P1 | SEC-05 | **đóng** | `_sanitize_value` tách `int` (so dải trực tiếp) và `float` (`isfinite`); `test_huge_integer_field_is_dropped_not_500`; thăm dò → 204 |
| 3 | P1 | R-33 | **đóng** | FIX-081 `f15437c`: `names == sorted(names)` + `sorted(set(names)) == on_disk`, đúng đề xuất; bước 5 đạt |
| 4 | P2 | PERF-04 | **đóng** (phần B7-01) | `POLL_INTERVAL_S = 0.05`, `await asyncio.to_thread(exporter.stop)`; bước 5 528,5 s; phần tốn thêm do exporter còn 1,8 s / 215 test. Phần `api_env` `METRICS_PORT=0` → nợ B0-06 |
| 5 | P2 | LOG-06 | **đóng** | `_is_schema_version_one`; test `schema-version-bool`, `schema-version-float`; thăm dò → 422 |
| 6 | P2 | LOG-03 | **đóng** | `_allow_log(limit, clock)` đọc `clock.now()`, route tiêm `ClockDep`; test 1.000 lô ghim `FakeClock`; test mới sang phút thì xô đặt lại |
| 7 | P2 | TEST-01/02 | **đóng** | (a) `test_sanitize_value_output_per_type` 14 case; (b) C01 route kiểm `render()`; (c) C11 đếm lời gọi `ingest` = hạn mức; (d) `timeout_s=1.5`; (e) `caplog` cho `metrics_exporter_unavailable` |
| 8 | P2 | MNT-05 | chấp nhận | không đáng tách (lượt 1) |
| 9 | P3 | R-07 | **đóng** | `require_test_env()` duy nhất ở `packages/observability/settings.py`; lý do đọc `os.environ` ghi trong docstring |
| 10 | P3 | R-07 | **đóng** | `apps/api/telemetry/tests/mirror.py` `read_ts_array` dùng chung |
| 11 | P3 | R-01 | **đóng** | docstring cho các hàm private đã nêu (`ingest.py`, `metrics.py`, `exporter.py`, `flags.py`, `settings.py`) |
| 12 | P3 | LOG-02 | **đóng** | `series_dropped` miễn trần chính nó; test `METRICS_MAX_SERIES=1` × 5 metric |
| 13 | Nit | MNT-04 | **đóng** | bỏ `assert … # noqa: S101`, thay bằng `TypeGuard[str]` |

## Finding mới (soát vòng sửa)

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 14 | P3 | PERF-04 · OBS | Mọi app test của mọi module vẫn gắn `0.0.0.0:9464` qua `metrics_lifespan` (mặc định `METRICS_PORT`); tốn thêm nay chỉ ~1,8 s / 215 test. Việc tắt ở `api_env` thuộc B0-06 | `packages/testing/fixtures/api.py` (`api_env`, chủ B0-06) | Ghi nợ B0-06: `api_env` đặt `METRICS_PORT=0`; chỉ test lifespan của B7-01 bật cổng |
| 15 | Nit | R-05 | `ingest(…, clock=_SYSTEM_CLOCK)` đổi chữ ký lõi so với [2]/[6]; tác giả đã ghi "Lệch khỏi prompt": lõi vẫn thuần, không nhận `Request`. Chấp nhận | `apps/api/telemetry/ingest.py:119` | Không cần làm gì |

Không thấy lỗi mới trong vòng sửa:
- `_is_valid_reason` và `_is_schema_version_one` thu hẹp kiểu trước khi so. Mọi phép `in` với tập hằng đều qua `isinstance(str)`.
- Các số nguyên lớn còn lại (`sequence`, `atMs`, `sentAtMs`, `droppedCount`) chỉ so sánh, không đổi sang `float`.
- `asyncio.to_thread(stop)` vẫn giữ đếm tham chiếu dưới `threading.Lock`.
- Việc miễn trần cho `series_dropped` an toàn vì nhãn của nó là tập tên metric đã khai, hữu hạn.
- Test mới không phụ thuộc giờ thật.
- Không `pragma`, `type: ignore`, `noqa` trần hay `skip`/`xfail` mới. Commit `9e90e40` đúng mẫu, có trailer `Prompt: B7-01`.

## Sổ nợ

Id kế tiếp trên `main` là **NO-159**. Người điều phối ghi:
- NO-159 — `api_env` (B0-06) đặt `METRICS_PORT=0` (#14) — P3, chủ B0-06, mở.
- NO-160 — metric HTTP chung (móc ở B0-06) — P2, chủ B0-06, mở (nợ tác giả nêu).
- NO-161 — exporter cho worker Celery và `ml` — P2, chủ B0-05/B5-01, mở (nợ tác giả nêu).
- NO-162 — cổng 9464 không công bố + cấu hình scrape — P2, chủ B0-08, mở (nợ tác giả nêu).

Không có nợ P0/P1 mở.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25 % | 5 | 1,25 |
| CON | 15 % | 5 | 0,75 |
| LOG | 15 % | 5 | 0,75 |
| PERF | 10 % | 4 (P3 #14) | 0,40 |
| RES | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 (H1 đạt) | 0,50 |
| TEST | 7 % | 5 | 0,35 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT | 3 % | 3 (P2 #8 chấp nhận) | 0,09 |

Tổng: **4,84 / 5**

## PHÁN QUYẾT: APPROVE

Cả ba P1 lượt 1 đã đóng, có test hồi quy và tái hiện lại bằng thăm dò. Mọi P2/P3/Nit cũng đã đóng, trừ MNT-05 đã chấp nhận.
Cổng 8/8 đạt, mã thoát 0. `case_gate` đủ cho cả hai op, H1 đạt, độ phủ mỗi gói ≥ 96 % nhánh. Bước 5 nhanh hơn lượt 1 169 s.

Điều kiện gộp:
- Gộp `--no-ff`, vì nhánh mang B7-01 và FIX-081 (B0-06).
- Ghi NO-159..162 vào `DEBT.md` trước khi gộp (R-38).
