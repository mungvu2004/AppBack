# Review merge feature/b7-01-telemetry-flags-metrics → main

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` lượt 1 (độc lập, worktree `b7-01-review`) · Commit đầu nhánh: `304d3a80444b`
- Phạm vi: `git diff main...HEAD` — 2 commit (`040136f`, `304d3a8`), 20 file, +1971 dòng; một prompt (B7-01) → squash
- Loại task (RULE.md §6): **Endpoint công khai nhận input thô** (#37) + **Auth** (#9 theo vai) + **thư viện dùng chung** (`packages/observability`)
- Cổng: `bash tools/verify/run.sh verify` (8 bước, không `--steps`) mã thoát **1** — log `backend/dieu-phoi/chay/B7-01/review-verify-1.log`
- Test (bước 5): **1 hỏng / 3279 qua / 4 deselected**, 697,69 s
- Độ phủ (lượt thu hẹp `coverage run -m pytest apps/api packages/observability`, log `review-cov-case-1.log`; bước 5 đầy đủ hỏng nên `coverage_gate` chưa chạy):
  `apps/api/telemetry` dòng **98,5 %** (268/272) · nhánh **94,6 %** (70/74); `packages/observability` dòng **99,3 %** (273/275) · nhánh **98,6 %** (73/74)

## Bảng cổng (mã thoát thật, log của chính phiên review)

| bước | lệnh | trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | **hỏng** — `apps/api/core/tests/test_app.py::test_discover_routers_finds_real_modules` |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy |
| 7 | `tools.contract.check` (H1 H3 H4 H5) | chưa chạy — H1 cho #9, #37 **chưa có bằng chứng** |
| 8 | `openapi` | chưa chạy |

Lỗi bước 5 (nguyên văn):

```
>       assert names == sorted(set(names)) == on_disk
E       AssertionError: assert ['apps.api.au....router', ...] == ['apps.api.au...metry.router']
E         Left contains one more item: 'apps.api.telemetry.router'
apps/api/core/tests/test_app.py:158: AssertionError
```

`case_gate` (lượt thu hẹp ở trên, không phải bước 5b; nguyên văn hai op của prompt):

```
telemetry_ingest_batch       | bắt buộc ['C01','C11','C12'] | tìm thấy ['C01','C11','C12'] | đạt
telemetry_read_feature_flags | bắt buộc ['C01','C04','C05','C12','C13','C17','C25'] | tìm thấy [đủ] | đạt
```

Test riêng của prompt (`apps/api/telemetry` + `packages/observability`) chạy 3 lượt liền: 100 qua mỗi lượt (28,6 s / 27,0 s / 27,3 s).
Test 100 lô × 20 sự kiện: qua (trần 2 s, trong lượt đó); tác giả không in số đo.

## Tái hiện của reviewer (script `run.sh shell`, log `review-probe-1.log`)

Gọi thẳng `ingest()` của nhánh — mọi ngoại lệ không phải `AppError` thành 500 `INTERNAL` + log stack (`apps/api/core/errors.py:150`):

```
reason_list -> UNHANDLED TypeError unhashable type: 'list'
reason_dict -> UNHANDLED TypeError unhashable type: 'dict'
big_int_field -> UNHANDLED OverflowError int too large to convert to float
schemaVersion_true -> OK (204)
schemaVersion_1.0 -> OK (204)
```

Đo tác dụng của exporter lên test của module khác (`apps/api/{projects,health,files}`, 215 test, chạy lần lượt trong cùng container):
`METRICS_PORT` mặc định **98,77 s** · `METRICS_PORT=0` **62,12 s**. Lượt đầu có thể gánh thêm thời gian khởi container
dùng chung; bước 5 đầy đủ cũng lên 697,7 s so với 557,9 s ở review FIX-080 (tải máy không kiểm soát).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | SEC-05 · LOG-02 · R-17 | `reason` không băm được (`[]`, `{}`) → `raw_reason in REASONS` ném `TypeError` **ngoài** khối `except _EnvelopeError` → 500 `INTERNAL` + log stack trên route **công khai**, không xác thực; đúng ra 422 `VALIDATION(field=reason)` + nhãn `invalid` ([6] bước 3). Đã tái hiện. Ai cũng bắn được (120 lượt/phút/IP, không giới hạn số IP) → nhiễu log lỗi/alert. | `apps/api/telemetry/ingest.py:149`, `:157` | `isinstance(raw_reason, str) and raw_reason in REASONS` (một hàm nhỏ dùng cho cả hai dòng); thêm test `reason: []`, `reason: {}` → 422 `field=reason`, nhãn `invalid`. |
| 2 | P1 | SEC-05 · LOG-02 | Trường sự kiện là số nguyên JSON rất lớn (vd 400 chữ số, dưới trần 4300 chữ số của `int()`) → `math.isfinite(value)` ném `OverflowError` → 500 trên route công khai. Bước 5 phải **bỏ trường**. Đã tái hiện. | `apps/api/telemetry/ingest.py:236` | So dải trước (`0 <= value <= MAX_FIELD_NUMBER`), chỉ gọi `math.isfinite` cho `float`; thêm test số nguyên 400 chữ số → 204, trường bị bỏ. |
| 3 | P1 | R-33 · TEST | Cổng đỏ: bước 5 hỏng vì test của B0-06 khẳng định mỗi module dò ra **đúng một** router (`names == sorted(set(names))`), trong khi `discover_routers()` (`apps/api/core/app.py:89-96`) cố ý nhận `tuple[APIRouter, ...]` và B7-01 [6] **bắt buộc** hai router (#9 protected, #37 public, không lồng). Mã B7-01 đúng đặc tả; test của B0-06 chật hơn hợp đồng của chính nó. Tác giả không chạy bước 5 đầy đủ nên không thấy (REPORT: "chưa chạy — cổng đầy đủ ở reviewer"). | `apps/api/core/tests/test_app.py:158` (chủ B0-06) | Người điều phối giao FIX cho B0-06: `assert names == sorted(names)` và `assert sorted(set(names)) == on_disk` (giữ ý "không sót module"), cộng một test module có 2 router. Gộp FIX trước B7-01, hoặc cùng nhánh `--no-ff` (R-36). B7-01 **không** tự sửa (K27). |
| 4 | P2 | PERF-04 · TEST-02 | `metrics_lifespan` gắn vào router của telemetry nên chạy trong **mọi** app test của mọi module, gắn `0.0.0.0:9464` (mặc định) rồi `stop()` → `ThreadingHTTPServer.shutdown()` chặn tới `poll_interval` 0,5 s, **đồng bộ trong lifespan async** (chặn vòng sự kiện lúc tắt app). Đo: 215 test của module khác 98,8 s → 62,1 s khi `METRICS_PORT=0` (xem trên). | `packages/observability/exporter.py:81`, `:112`, `:134` | `serve_forever(poll_interval=0.05)` hoặc `await asyncio.to_thread(exporter.stop)` trong `metrics_lifespan`; ghi nợ B0-06 để `api_env` đặt `METRICS_PORT=0` (chỉ test lifespan của B7-01 bật cổng). Đo lại bước 5. |
| 5 | P2 | LOG-06 · LOG-02 | `data.get("schemaVersion") != 1` nhận `true` và `1.0` (đã tái hiện: 204). B7-01 [6]: "Ở bước 3–4, số nguyên là `int` và **không** phải `bool`". | `apps/api/telemetry/ingest.py:150` | `if not (_is_non_negative_int(v) and v == 1)`; thêm `schemaVersion: true`, `1.0` vào bảng tham số hoá 422. |
| 6 | P2 | LOG-03 · TEST-02 · R-18 | Xô token log đọc `time.time()` trực tiếp (không `Clock` tiêm được). `test_one_thousand_batches_respect_the_log_rate_limit` chạy 1.000 lô bằng giờ thật: nếu sang phút mới giữa chừng, xô đặt lại và số dòng log vượt `TELEMETRY_LOG_MAX_PER_MIN` → test chập chờn theo đồng hồ. | `apps/api/telemetry/ingest.py:253-254`; `apps/api/telemetry/tests/test_ingest_core.py:251` | Truyền nguồn thời gian (hàm `now_minute` hay `Clock` của repo) vào `_allow_log`; test ghim phút, thêm case sang phút → xô đặt lại. |
| 7 | P2 | TEST-01 · TEST-02 | Test yếu so với [8]: (a) bước 5 không có test nào khẳng định **đầu ra** của `_sanitize_fields` với tiếng Việt/email/`-1`/`1e9`/mảng — test PII chỉ kiểm không lọt log (vốn không bao giờ log giá trị trường), test `errorKind` chỉ đếm sự kiện; (b) C01 #37 qua route không kiểm `render()` (`events_total{name="ai.started"} 1.0`, `client_dropped_total 2.0`); (c) C11 không chứng minh thân chưa đọc (đếm lời gọi handler); (d) "theo phiên" chờ 3,0 s trong khi [8] đòi ≤ 1,5 s; (e) cổng bận không kiểm log `metrics_exporter_unavailable`. #1, #2 lọt vì thiếu case biên kiểu dữ liệu ở vỏ/trường. | `apps/api/telemetry/tests/test_ingest_core.py:190-229`; `test_telemetry_ingest_route.py:56-79`; `test_feature_flags_route.py:133`; `packages/observability/tests/test_exporter.py:80` | Khẳng định dict trả về của `_sanitize_fields` cho từng loại; thêm `reset_registry()` + so `render()` trong C01; đếm lời gọi handler ở C11/C12; `timeout_s=1.5`; `caplog` cho cổng bận. |
| 8 | P2 | MNT-05 | ~920 dòng mã không phải test (> 400). **Không đáng tách:** một prompt, hai khối gắn chặt (telemetry là khách đầu tiên của registry). | toàn nhánh | Không cần làm gì. |
| 9 | P3 | R-07 · lệch prompt | Khối kiểm `os.environ.get("APP_ENV") != "test"` chép ở hai nơi, và không dùng `get_core_settings().app_env` như [3]. Lý do của tác giả (test lõi không dựng đủ `PUBLIC_BASE_URL`/`SECRET_KEY`) đứng được cho việc đọc biến thô, **không** cho việc chép. | `packages/observability/metrics.py:266`; `apps/api/telemetry/ingest.py:266` | Một hàm `require_test_env(name)` trong `packages/observability`, `ingest.py` gọi lại. |
| 10 | P3 | R-07 | `_TS_ARRAY_RE` + `_read_ts_array` chép nguyên hai file test. | `apps/api/telemetry/tests/test_flags.py:17`; `test_ingest_core.py:24` | Một module helper test dùng chung trong `apps/api/telemetry/tests/`. |
| 11 | P3 | R-01 | Thiếu docstring ở ~20 hàm: `ingest.py` `_check_content_type`, `_decode_json`, `_is_non_negative_int`, `_sanitize_value`, `_allow_log`; `metrics.py` `_require`, `_admit`, `_bump_dropped`, `render` (method), `_render_counter`, `_render_histogram`, `_validate_*`, `_label_key`, `_escape`, `_labels`, `Counter.inc`, `Histogram.observe`; `exporter.py` `_serve_metrics`, `do_*`; `flags.py` `_valid_roles`; `settings.py` `_known_keys`. | các file trên | Thêm docstring 1 câu, nêu luật (vd `_decode_json`: vì sao bắt `RecursionError`). |
| 12 | P3 | LOG-02 | `_bump_dropped` đệ quy vô hạn khi chính `appback_metrics_series_dropped_total` chạm `METRICS_MAX_SERIES` (vd `METRICS_MAX_SERIES=1`, hai metric tràn) → `RecursionError` trong `inc()`. Mặc định 1000 thì cần > 1000 metric tràn — hiếm. | `packages/observability/metrics.py:113-117` | Miễn trần cho metric `series_dropped` (tập nhãn = tập tên metric, hữu hạn). |
| 13 | Nit | MNT-04 | `assert isinstance(raw_reason, str)  # noqa: S101` trong mã chạy thật chỉ để thu hẹp kiểu; `python -O` bỏ nó. | `apps/api/telemetry/ingest.py:171` | Gộp vào sửa #1 (hàm kiểm trả `TypeGuard[str]`). |

**Đã kiểm, đạt:** rate limit (`key_ip`, `store="cache"`, `on_error="open"`) và `reject_foreign_origin` là dependency nên chạy **trước** `await request.body()`; trần 64 KiB qua `route_options(body_limit=…)` (C12 cả `Content-Length` lẫn luồng); JSON sâu `[`×40.000 → 400; K11: log `telemetry_batch` chỉ có `reason` (tập hữu hạn) và số đếm theo tên/lý do, không thân/IP/UA/giá trị trường; OBS-02: mọi nhãn từ tập hữu hạn (`reason` 5, `result` 2, `cause` 2, `name` 12), tên lạ không tạo series, trần `METRICS_MAX_SERIES` + `series_dropped_total`; CON-06: registry dưới `RLock` (lý do tái nhập ghi ở docstring), test 8 luồng × 10.000; xô log chỉ chạy trên luồng vòng sự kiện; exporter đếm tham chiếu dưới `threading.Lock`, `metrics_lifespan` chỉ `stop()` bản nó nhận, cổng bận chỉ log; exporter không mount vào app `/api`; ranh giới import `packages/observability` (lint-imports + test tiến trình mới chặn `fastapi/starlette/sqlalchemy/celery/prometheus_client`); #9: `WireModel` bỏ `None` nên khoá chưa cấu hình vắng mặt, không `null`, tính theo `principal.role` mỗi request, `FEATURE_FLAGS` sai → `ValueError` lúc nạp; gương FE (`appfront_dir`) cho 12 tên, 13 `errorKind`, 5 khoá cờ; không `pragma`, `type: ignore`, `noqa` trần, `skip/xfail`; commit đúng mẫu + trailer `Prompt: B7-01`; `changes/B7-01.md` có; không chạm file cấm.

## Sổ nợ

- Nợ tác giả nêu (metric HTTP chung — B0-06; exporter cho Celery/`ml` — B0-05, B5-01; cổng 9464 + scrape — B0-08) **chưa** có dòng `DEBT.md` (R-34) — người điều phối ghi.
- Đề xuất dòng mới (id kế tiếp trên `main` là **NO-158**; NO-155..157 đã dùng ở review B4-01): #3 (FIX B0-06 test dò router), #4 phần `api_env` `METRICS_PORT=0` (B0-06), cộng ba nợ tác giả ở trên. #1, #2, #5, #6, #7 sửa ngay trong vòng sửa của B7-01, không cần dòng nợ.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25 % | 1 (P1 #1, #2) | 0,25 |
| CON | 15 % | 5 | 0,75 |
| LOG | 15 % | 3 (P2 #5, #6; P3 #12) | 0,45 |
| PERF | 10 % | 3 (P2 #4) | 0,30 |
| RES | 10 % | 5 | 0,50 |
| DB, API | 10 % | 5 (H1 chưa chạy — chấm lại lượt 2) | 0,50 |
| TEST | 7 % | 1 (P1 #3; P2 #7) | 0,07 |
| OBS, OPS | 5 % | 5 | 0,25 |
| MNT | 3 % | 3 (P2 #8; P3 #9–#11) | 0,09 |

Tổng: **3,16 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Ba P1 chưa waiver và cổng đỏ. Điều kiện để được duyệt ở lượt 2:

1. Sửa #1 và #2 (500 trên route công khai) kèm test hồi quy; sửa #5, #6; bổ sung test #7 (ít nhất (a), (b), (d)).
2. #3: FIX B0-06 cho `apps/api/core/tests/test_app.py:158` được gộp trước (hoặc cùng nhánh `--no-ff`) — B7-01 không tự sửa file đó.
3. #4: exporter không còn chặn vòng sự kiện tới 0,5 s lúc tắt (hoặc `api_env` tắt exporter qua FIX B0-06); bước 5 trở về quanh mức nền.
4. `bash tools/verify/run.sh verify` thoát 0, **8/8 đạt**, gồm `coverage_gate`, `case_gate` (5b) và H1 `đạt` cho #9, #37 ở bước 7.
5. Nợ tác giả nêu và các đề xuất ở "Sổ nợ" có dòng `DEBT.md`.

P3/Nit (#9–#13) nên sửa cùng lượt, không chặn.
