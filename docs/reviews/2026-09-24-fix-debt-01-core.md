# Review merge `fix/debt-01-core` → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worktree `review-debt-01-core`) · Commit đầu nhánh: `99bc366edcb4`
- Phạm vi: `git diff 361db93...99bc366` — 6 commit, 27 file, +879/−64.
  FIX-088 (B0-03), FIX-089 (B0-05), FIX-090 (B0-06), FIX-103 (B1-01), FIX-091 (B5-01), FIX-092 (B4-01).
- Cổng: `bash tools/verify/run.sh verify` (một lượt, đầy đủ) — **mã thoát 1**
  (log: `.cache/src-out/verify/20260924T*-99bc366edcb4.log`, bản sao
  `C:/Users/mxuan/AppData/Local/Temp/claude/review-debt01/verify.log`)
- Độ phủ: **chưa đo** — bước 5 hỏng nên `coverage_gate` không chạy. Số trong báo cáo tác giả
  (§4, "TỔNG 99%") đo bằng một lượt `pytest` thu hẹp, không phải cổng, nên không dùng được.

## Bảng E.10 — từ mã thoát thật

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 0 contract hỏng |
| 5 | `coverage run -m pytest` → `coverage_gate` | **hỏng** | 5 failed, 12 errors, 3780 passed, 642 s |
| 5b | `pytest -m perf` → `case_gate` | chưa chạy | sau bước hỏng |
| 6 | `lint_migrations` → `migrate_check` | chưa chạy | sau bước hỏng |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | chưa chạy | sau bước hỏng |
| 8 | `openapi` | chưa chạy | sau bước hỏng — reviewer chạy riêng, xem §"Kiểm độc lập" |

Mã thoát cổng: **1**.

## Kiểm độc lập (không dựa vào báo cáo tác giả)

Chạy trong container cổng (`run.sh shell`), hoàn nguyên **chỉ** file sản phẩm về `361db93`
rồi chạy chính test mới — đây là bằng chứng "đỏ" thật (assert đỏ), mạnh hơn `ImportError`
lúc thu thập mà báo cáo §1.1 dùng cho phần lớn FIX.

| Nợ | Lệnh | Đỏ trên mã `361db93` | Xanh trên nhánh |
|---|---|---|---|
| NO-140 | `test_hooks.py::…savepoint_release_waits_for_the_outer_commit` | mã thoát **1**, 1 failed (`calls == ['trong']`) | mã thoát 0 |
| NO-156/157 | `apps/api/streams/tests/test_sse.py` | mã thoát **1**, 2 failed | mã thoát 0 |
| NO-085 (nửa `ml`) | `test_celery_main.py::…starts_without_the_signing_key` | mã thoát **1**, 2 failed | mã thoát 0 |
| NO-151/152 | `packages/messaging/tests/test_{redis,settings,streams}.py` | mã thoát **2** (chỉ `ImportError` lúc thu thập) | — |
| — | `GREEN` bốn test mục tiêu trên nhánh | — | **mã thoát 0** |

- **K23**: không mock Postgres/Redis. `test_a_dead_redis_costs_exactly_the_configured_number_of_retries`
  dùng `ephemeral_broker` (testcontainers Redis thật, `admin.shutdown(nosave=True)`), chỉ thay
  `AbstractBackoff` bằng bản đếm — đúng cách.
- **NO-104 không tải mạng**: `FlakyOpener` là bộ mở giả theo kịch bản; `test_pinned.py` không mở socket nào.
- **Hợp đồng không đổi**: `python -m apps.api.core.openapi --out /tmp/oa.json --compare docs/contracts/openapi.json`
  → **mã thoát 0**. Không op/schema/route mới, không revision mới.
- **NO-152, ô "Nguyên nhân gốc" của `DEBT.md`**: tác giả nói ô đó sai. **Đo lại, tác giả đúng.**
  redis-py 8.1.0 trong venv cổng:

  ```
  sync  from_url: 'retry' in connection_kwargs = False ; connection.retry.get_retries() = 0 (NoBackoff)
  async from_url: 'retry' in connection_kwargs = False ; connection.retry.get_retries() = 0 (NoBackoff)
  sync  ctor    : connection.retry.get_retries() = 10
  async ctor    : connection.retry.get_retries() = 10
  ```

  Cơ chế: `Redis.from_url()` dựng `ConnectionPool.from_url(url, **kwargs)` rồi truyền
  `connection_pool=` vào `Redis.__init__`, nên khối `if not connection_pool:` (chỗ duy nhất
  bơm `Retry(ExponentialWithJitterBackoff, DEFAULT_RETRY_COUNT=10)` vào `connection_kwargs`,
  `redis/client.py:396-415`) **không chạy**. `Connection.__init__` nhận `retry=None`,
  `retry_on_error=SENTINEL` → `Retry(NoBackoff(), 0)` (`redis/connection.py:910`).
  Mặc định 10 lượt chỉ có trên đường `Redis(host=…)`, mà repo không dùng.
  **Việc cho người điều phối**: sửa ô "Nguyên nhân gốc" của NO-152 khi đóng dòng —
  triệu chứng "trần 0,5 s thực tế là 11 lượt" không tái hiện được.
- **NO-161, một dây nối chung ở `packages/messaging/celery_app.py`**: người điều phối đã duyệt
  cách làm. Kiểm cả hai tiến trình: `apps/worker/celery_main.py` và `apps/ml/celery_main.py`
  đều dựng app bằng `create_celery`, nên cả hai nhập module đó và nhận receiver. Nhưng cách
  gắn vào `worker_process_init` gây finding #1 và #3 dưới đây.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | TEST-05 / R-14 | Receiver `worker_process_init` mở exporter **thật** ngay trong tiến trình pytest và không ai tắt nó. Pool `solo` của Celery bắn `worker_process_init` **trong tiến trình gọi** (`celery/concurrency/solo.py:20`), mà `celery_worker_factory` dựng worker thử bằng `pool="solo"`; `messaging_env` để `METRICS_PORT` mặc định 9464. Từ `packages/messaging/tests/test_tasks.py` trở đi, `packages.observability.exporter._instance` giữ một `MetricsExporter` sống. Fixture `_clean` của B7-01 vì thế đỏ ở teardown của **cả 12** test `test_exporter.py`, 3 test hỏng hẳn, cộng `test_telemetry_ingest_route.py::test_exporter_answers_during_lifespan_and_stops_after`. Đây là nguyên nhân chính làm bước 5 hỏng. | `packages/messaging/celery_app.py:103-121` ↔ `packages/testing/fixtures/messaging.py:160` ↔ `packages/observability/tests/test_exporter.py:22` | Không mở exporter chỉ vì nhận `worker_process_init`: gắn ở **điểm vào** của `apps/worker`/`apps/ml` (chỗ biết chắc tiến trình là worker thật), hoặc thêm receiver `worker_process_shutdown` trả tham chiếu **và** cho `messaging_env` đặt `METRICS_PORT=0` như `api_env` (NO-159). Sửa xong phải chạy lại cổng đầy đủ. |
| 2 | **P1** | TEST-05 | Test RED metric phụ thuộc thứ tự chạy: `assert len(counts) == 1` đọc registry **toàn tiến trình**, mà `reset_registry()` chỉ đưa mẫu về 0 chứ **không xoá chuỗi nhãn** (`packages/observability/metrics.py` `Registry.reset`). Trong cổng đầy đủ đã có sẵn `{route="-",method="POST",status="404"}` từ module khác nên danh sách có 2 dòng: `['…{route="-",method="GET",status="404"} 2.0', '…{route="-",method="POST",status="404"} 0.0']`. Đo lại: chạy riêng `test_middleware.py` → 16 passed; chạy cả `apps/api/core/tests` → 358 passed; chỉ cổng đầy đủ mới đỏ — nên lượt đo thu hẹp của tác giả không thể thấy. | `apps/api/core/tests/test_middleware.py:200` (và cùng dạng ở `:172`, `:189`) | Lọc bỏ chuỗi có giá trị 0, hoặc khẳng định thẳng vào chuỗi nhãn mong đợi thay vì đếm số dòng. |
| 3 | **P2** | OBS-02 | NO-161 chỉ phơi metric của **một** tiến trình con. `worker` chạy `--concurrency ${WORKER_CONCURRENCY:-2}` với pool prefork, mà prefork bắn `worker_process_init` ở **mỗi** con (`celery/concurrency/prefork.py:82`) và `_REGISTRY` là của từng tiến trình. Hai con cùng bind một `METRICS_PORT`: con đầu thắng, con sau chỉ log `metrics_exporter_unavailable` và không phơi gì. `/metrics` của container `worker` vì vậy báo số của một con ngẫu nhiên. (`ml`/`ml-gpu` chạy `--concurrency 1` nên không dính.) | `packages/messaging/celery_app.py:104-121` ↔ `deploy/compose/base.yml:155` | Mở exporter ở tiến trình **chính** của worker (`worker_init`/`worker_ready`) với một registry gộp nhiều tiến trình, hoặc cấp cổng riêng cho từng con và khai đủ target khi làm NO-162. |
| 4 | **P2** | OBS-01 / R-16 | Nhãn `method` không được kẹp như `route`. Chính docstring `_route_label` nói mẫu dài hơn `MAX_LABEL_VALUE_LEN` sẽ làm `observe` ném **giữa** request và "một metric không bao giờ được làm hỏng lượt phục vụ", nhưng `method` đi thẳng từ scope ASGI vào `observe`; `_label_key` ném `ValueError` với mọi giá trị > 64 ký tự (`packages/observability/metrics.py:205`), và lời gọi nằm trong `finally` — tức là **sau** khi response đã ra dây. Hôm nay không khai thác được vì uvicorn dùng httptools (chỉ nhận method trong bảng cố định), nhưng bảo đảm đó nằm ở bộ phân tích HTTP chứ không ở mã: uvicorn tự rơi về `h11` (nhận mọi token RFC 9110) khi thiếu httptools. Kèm theo đó, `method` không chặn cũng là một trục nở chuỗi nhãn không do ta kiểm soát. | `apps/api/core/middleware.py:149,155` (so với `:72-80`) | `method=_route_label(method)`, hoặc ánh xạ method ngoài danh sách đã biết về `-`. |
| 5 | P3 | CON-04 | Cùng đường hỏng mà NO-156 nói tới, `AsyncSession` vẫn rò: `except BaseException: await _abort(...)` chỉ bọc `original(request)`, còn `_finish` ném thì session không rollback, không close. FIX-092 trả được ba tài nguyên SSE trên đường đó; phần session vẫn mở. Chính test mới ép `_finish` ném 5 lượt nên đường này có thật. | `apps/api/core/routing.py:238-245` | Chủ B0-06: bọc cả `_finish` vào `try/except` gọi `_abort`. Mở dòng nợ. |
| 6 | P3 | CON-03 | `retry_on_error=[ConnectionError, TimeoutError]` áp cho **mọi** vai, kể cả `streams_redis` — client mà `EventBus.publish` dùng để `XADD`. Một lệnh hết giờ có thể đã chạy xong ở server; lượt thử lại ghi thêm một mục với id mới, FE thấy sự kiện hai lần (`STREAM_RETRIES=1` nên tối đa một bản dư). Không phải hồi quy (mặc định thư viện trước đó là 0 lượt, xem §Kiểm độc lập), nhưng khi ngân sách đã là của ta thì nên chọn theo **loại lệnh** (đọc/ghi) chứ không theo vai. | `packages/messaging/redis.py:59,145,158` | Tách client chỉ-đọc (thử lại cả timeout) khỏi đường ghi (chỉ thử lại lỗi kết nối). Mở dòng nợ. |
| 7 | Nit | R-07 | Sau NO-097 vẫn còn **gương vai thứ ba**: `ROLES: Final = ("admin","engineer","viewer")` ở `packages/db/models/auth.py:29`, trùng `packages.domain.permissions.ROLES`. Báo cáo §6.2 nêu cặp `_role` trùng nhau nhưng không nêu dòng này. | `packages/db/models/auth.py:29` | Mở dòng nợ Nit chung với đề nghị §6.2 của tác giả. |
| 8 | Nit | TEST-08 | Test chọc vào trạng thái riêng tư của module khác: `exporter_module._instance` bị đọc và bị `stop()` trong vòng `while` (`packages/messaging/tests/test_celery_app.py`), `pool.make_connection()` dựng một `Connection` rồi bỏ (`packages/messaging/tests/test_streams.py:100`). | như trên | Phơi một hàm chỉ-test ở `packages/observability/exporter.py`; dùng `connection_kwargs["protocol"]` thay cho `make_connection()`. |

Không tìm thấy: file cấm bị đụng (`docs/charter/*`, `openapi.json`, `uv.lock`, `pyproject.toml`,
`tools/contract/APPFRONT_SHA`, `DEBT.md`) · `conftest.py` lồng · file cấu hình công cụ riêng ·
`# pragma: no cover` · `type: ignore` trần · `skip`/`xfail` mới · hạ ngưỡng · `--no-verify`.
Hai `# noqa: S603` đều có mã và lý do, theo đúng lối đã dùng sẵn trong file. Cây làm việc sạch;
6 dòng đầu commit đúng Conventional Commits, đủ trailer `Prompt:`/`Fix:`. `changes/DEBT-01.md` có.
FIX-103 chạm `apps/api/auth/sessions.py` — người điều phối đã duyệt trước, commit riêng đúng chủ (K27 ok).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---:|---:|---:|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 4 | 0,60 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 1 | 0,07 |
| OBS, OPS – Vận hành | 5% | 3 | 0,15 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,44 / 5** |

Điểm cao nhưng có **2 finding P1 chưa waiver** → theo ma trận `RULE.md` §5, quyết định là
REQUEST CHANGES bất kể tổng điểm.

## Nợ

Nợ mới cần một dòng trong `DEBT.md` (người điều phối mở, chủ ghi trong ngoặc):

1. **P3** — `AppRoute._finish` ném thì `AsyncSession` không rollback/close (finding 5, B0-06).
2. **P3** — ngân sách thử lại Redis áp cho cả đường ghi `XADD` (finding 6, B0-05).
3. **Nit** — gương vai thứ ba ở `packages/db/models/auth.py:29`, gộp với đề nghị §6.2 của tác giả
   (hai `_role` gần giống nhau) (finding 7, B0-06 + B1-01).
4. **Tài liệu** — ô "Nguyên nhân gốc" của NO-152 mô tả sai hành vi thật của redis-py 8.1 trên
   đường `from_url` (đo ở §Kiểm độc lập); sửa khi đóng dòng.

Finding 1–4 **không** ghi thành nợ: 1 và 2 chặn merge nên phải sửa trong nhánh này; 3 và 4 là
P2, nếu tác giả không sửa trong lượt tới thì mới mở dòng nợ kèm lý do chấp nhận.

### Từng dòng nợ trong phạm vi — có đóng được khi merge không

| NO | Đóng được? | Lý do |
|---|---|---|
| NO-140 | **có** | Sửa gốc ở `_on_commit`; đỏ→xanh reviewer tự kiểm trên Postgres thật. |
| NO-151 | **có** | `legacy_responses=True` ghim tường minh cho mọi client; test khẳng định cả cờ lẫn `protocol == 3`. |
| NO-152 | **có** (mã) | Ngân sách theo vai + test đếm lượt trên Redis thật. Kèm điều kiện: sửa ô "Nguyên nhân gốc" của dòng nợ. |
| NO-157 | **có** | `event_id_key` công khai, bản chép ở `sse.py` đã xoá, test chặn tái phát hai phía. |
| NO-097 | **có** (theo đúng chữ của dòng nợ) | `apps/api/core/auth.py` hết khai riêng. Còn gương thứ ba ở `packages/db` → nợ Nit mới, không chặn. |
| NO-137 | **có** | `_grant_everything` trả `ProjectAccess` đúng kiểu. |
| NO-159 | **có** | `api_env` đặt `METRICS_PORT=0`, có test. (Xem finding 1: `messaging_env` thì chưa.) |
| NO-104 | **có** | Thử lại có backoff và trần; `.part` + `os.replace` giữ nguyên; 4 test, không tải mạng. |
| NO-156 | **có** | `StreamRoute` + `release_held`; reviewer tự dựng lại cảnh đỏ (2 failed) rồi xanh. Phần session DB là nợ mới, chủ khác. |
| NO-085 | **không** (chưa trọn) | Nửa mã xong và đo được (tiến trình mới chạy không cần `SECRET_KEY`/`PUBLIC_BASE_URL`/`REDIS_CACHE_URL`), nhưng `deploy/compose/base.yml` vẫn truyền cả ba cho `ml`/`ml-gpu`. Chỉ đóng khi T2 (`fix/debt-01-deploy`, B0-08) gỡ xong. |
| NO-160 | **không** (chưa) | Mã đúng hướng, nhưng test của nó là finding 2 (P1). Đóng sau khi test hết phụ thuộc thứ tự và cổng xanh. |
| NO-161 | **không** | Finding 1 (P1: rò exporter vào tiến trình test) và finding 3 (P2: chỉ một tiến trình con phơi metric). Cách gắn phải đổi trước. |

## PHÁN QUYẾT: REQUEST CHANGES

Sáu commit đều đúng chủ, đúng mẫu, sửa **gốc** chứ không vá triệu chứng, và 10/12 dòng nợ trong
phạm vi được giải quyết đàng hoàng — reviewer dựng lại được cảnh đỏ cho NO-140, NO-156, NO-085 và
xác nhận xanh trên nhánh, hợp đồng OpenAPI không đổi, bước 1–4 của cổng đều xanh. Nhưng **cổng đầy
đủ thoát 1**: bước 5 hỏng với 5 test đỏ và 12 lỗi teardown, và nguyên nhân nằm trong chính nhánh
này — receiver `worker_process_init` mới mở một exporter thật trong tiến trình pytest (pool `solo`
của Celery bắn tín hiệu đó ngay trong tiến trình gọi) rồi không ai tắt, làm hỏng toàn bộ
`packages/observability/tests/test_exporter.py` của B7-01; cộng thêm một test RED metric phụ thuộc
thứ tự chạy. Cả hai không thể thấy bằng lượt đo thu hẹp mà tác giả dùng (`apps/api/core/tests` chạy
riêng: 358 passed).

Để được `APPROVE`, cần đúng ba việc:

1. **Sửa finding 1** — đổi cách gắn exporter để không tiến trình test nào mở nó, và/hoặc trả tham
   chiếu ở `worker_process_shutdown` + `messaging_env` đặt `METRICS_PORT=0`.
2. **Sửa finding 2** — bỏ phụ thuộc thứ tự chạy trong ba assert của `test_middleware.py`.
3. **Chạy lại `bash tools/verify/run.sh verify` đầy đủ, thoát 0**, và dán bảng E.10 + độ phủ
   (tổng và từng gói bị chạm, dòng **và** nhánh) từ mã thoát thật — lần này chưa có số nào đo được.

Finding 3 và 4 (P2) nên sửa trong cùng lượt; nếu hoãn thì phải có dòng `DEBT.md` kèm lý do. Finding
5–8 không chặn merge. NO-085, NO-160, NO-161 chưa đóng được trong lượt này.
