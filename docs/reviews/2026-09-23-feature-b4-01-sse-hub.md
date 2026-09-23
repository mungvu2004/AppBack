# Review merge feature/b4-01-sse-hub → main

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (độc lập, worktree `review-b4-01`) · Commit đầu nhánh: `f01ce1b05860`
- Loại task (RULE.md §6): **Auth, phân quyền** + **Consumer / việc nền**
- Cổng: `bash tools/verify/run.sh verify` (8 bước, **không** `--steps`) mã thoát **0** — chạy tại chỗ, log `backend/dieu-phoi/chay/B4-01/review-b4-01-r1.log`
- Test: **3284 qua / 0 hỏng / 4 deselected**, 554,46 s
- Độ phủ: tổng dòng **99,09 %** · nhánh **97,58 %**; `apps/api/streams` dòng **100,00 %** · nhánh **98,48 %**; `packages/testing` dòng 99,16 % · nhánh 97,37 %; tập file bị chạm dòng 99,44 % · nhánh 95,97 %

## Bảng cổng (mã thoát thật, log của chính phiên review)

| bước | lệnh | trạng thái |
|---|---|---|
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
Thao tác đã mount  | đạt           | 17 đã mount / 83 dòng BE-BIND
H1                 | đạt           | 407 mẫu response
H1 ngữ cảnh        | đạt           | 10 mẫu có luật ngữ cảnh
H3                 | đạt           | 10 khoá, 3 vai
H4                 | không áp dụng | B3-05 chưa hợp nhất — FE 25 mã; chưa có apps.api.rules.catalog
H5                 | đạt           | 3 khung SSE
```

`case_gate` (nguyên văn, hai op của prompt):

```
streams_open_notifications | bắt buộc ['S01','S02','S03','S04','S05','S07','S09'] | tìm thấy [đủ] | đạt
streams_open_progress      | bắt buộc ['S01','S02','S03','S04','S05','S06','S07','S08','S09'] | tìm thấy [đủ] | đạt
```

## Điều kiện dừng sớm — không cái nào kích hoạt

- `git status --porcelain` rỗng; `git log main..HEAD` = 7 commit, dòng đầu đúng Conventional Commits, **mọi** commit (kể cả hai merge) mang trailer `Prompt: B4-01`.
- `changes/B4-01.md` có mặt, 9 dòng.
- Diff (`git diff main...HEAD`, 24 file, +3568) **chỉ** chạm `apps/api/streams/**`, `packages/testing/fixtures/streams.py`, `changes/B4-01.md` — đúng cột "Sở hữu" của prompt. Không chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `deploy/**`, `DEBT.md`.
- Không `# pragma: no cover`, không `pragma: no branch`, không `skip`/`xfail` mới, không hạ ngưỡng. Hai chú thích ức chế duy nhất đều **có mã và có lý do**: `# noqa: S603 —` (`tests/test_lifecycle.py:22`) và `# type: ignore[import-untyped]` (`tests/test_redis_outage.py:20`) — hợp K24.

## Đã tự kiểm (không tin báo cáo tác giả)

Đọc toàn bộ diff nguồn, không chỉ file mới. Xác nhận bằng mã:

- **Thứ tự mở luồng [6]** đúng: `reject_foreign_origin` → cookie/`verify_stream_token`/`check_session` → mẫu `is_id` → `policy.authorize` → giữ chỗ người dùng (ZSET) → giữ chỗ toàn cục + kết nối pool → vị trí bắt đầu → `StreamingResponse` (`router.py:96-109`, `sse.py:232-254`).
- **K03**: `frame()` (`sse.py:71-78`) chỉ sinh `id:`/`data:`; heartbeat là `: ping`. Test khẳng định `b"event:" not in stream._raw`.
- **K11**: bốn lời gọi log của module (`sse.py:287,297,343,424`, `jobs.py:93`) không mang cookie, token hay `data`; `_error_marks` (`sse.py:97-99`) chỉ giữ `loc`/`type`. Test `S03_invalid_event` khẳng định chuỗi riêng tư **không** xuất hiện trong `caplog.text`.
- **K32**: luồng thông báo có `snapshot=None` → `resolve_start` trả `cursor=tail` (`sse.py:271-273`), không ảnh chụp, không phát lại. Kiểm thêm đường lách: `?lastEventId=0-0` bị `is_trimmed` bắt → vẫn về `tail`, không phát lại được.
- **K36**: `check_session` và nhà cung cấp dùng `app.state.sessionmaker` (phiên ngắn); `_load_snapshot` (`auth/sessions.py:588-598`) mở/đóng phiên riêng. Test đo `engine.pool.checkedout() == 0` với 20 luồng đang mở.
- **S05 / CancelScope**: `_close` (`sse.py:405-426`) chạy dưới `anyio.CancelScope(shield=True)`, `ZREM` dưới `move_on_after(1)`, trả kết nối đứng ngoài trần — lý do tách được viết đúng và có test hồi quy (`test_cleanup_returns_the_slot_when_the_cache_is_down`, 5 lượt với `STREAM_MAX_GLOBAL=2`).
- **Pool SSE có trần**: `ConnectionPool.from_url(..., max_connections=STREAM_MAX_GLOBAL)` (`router.py:41-55`) + `asyncio.Semaphore(STREAM_MAX_GLOBAL)`; `_take_slot` không chờ (`sse.py:170-179`) nên hết chỗ là 429 ngay. Chỗ semaphore được trả **sau** khi kết nối về pool — không có cửa sổ pool cạn mà bộ đếm báo còn trống. Lệch 1 của báo cáo là đúng và có lý do đứng được (redis-py 8.1 không phân biệt "pool hết chỗ" với "Redis chết").
- **S07 ≤ 5 s**: ràng buộc kiểm lúc nạp (`settings.py:39-48`); đo thật trong log cổng: revoke 0,3–0,4 s, `status='disabled'` không xoá cache 1,1 s (trần 1,5 s).
- **Lỗ quyền khi chưa có `StreamAccessPolicy` thật**: **không có**. Sổ mặc định `DenyUploads` (`registry.py:38-71`) fail-closed → mọi yêu cầu `upload_progress` 404, có test (`S06_no_provider`). Dependency đánh dấu `@permission_dependency(ANY_MEMBER)` (`router.py:76-84`) chỉ `setattr` khoá rồi ghi sổ (`core/permissions.py:24-35`) — nó không cấp quyền gì. Xem finding 1 cho rủi ro **tương lai**.
- **`extensions.override` chỉ ở test**: gác bằng `APP_ENV != "test" → RuntimeError` (`core/extensions.py:70-76`); `registry.build_registry` gọi `resolve` nên chính sách thật không thay được ở môi trường thật.
- **`lifecycle.py` / `jobs.py` không nhập `fastapi`**: xác nhận bằng mã nguồn và bằng test chạy trình thông dịch con với `fastapi`/`jwt`/`argon2` bị chặn trong `sys.modules`.
- **Timeout**: `STREAM_READ_TIMEOUT_S = 30 s` >> trần `STREAM_READ_BLOCK_MS` (≤ 5 s theo validator) — `XREAD BLOCK` không thể chạm socket timeout.
- **Test dùng dịch vụ thật (K23)**: Postgres, hai Redis, cookie do chính `POST /api/auth/refresh` cấp; "Redis chết" dựng bằng `RedisContainer.stop()` thật và cổng không ai nghe, không `fakeredis`, không mock.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | SEC-02 | Cổng nhà cung cấp **fail-open theo quyền**: `_check` bắt buộc `snapshot` cho `upload_progress` nhưng **không** bắt buộc `policy`, còn `open_stream`/`_still_allowed` bỏ qua hẳn bước kiểm quyền khi `provider.policy is None`. Một `StreamProvider(kind="upload_progress", event_model=…, snapshot=…)` của B2-04 quên `policy` sẽ qua được lượt dò, và **mọi người đã đăng nhập đọc được luồng tiến độ của mọi lượt tải** (IDOR). Không khai thác được trên nhánh này (mặc định `DenyUploads` fail-closed, chưa có nhà cung cấp thật), nhưng lỗ nằm ở cổng do chính B4-01 sở hữu và chỉ lộ ra khi B2-04 hợp nhất — lúc đó không cổng nào bắt | `apps/api/streams/registry.py:81-86`; `apps/api/streams/sse.py:241-242`, `:325-326` | Thêm luật đối xứng với luật `snapshot`, một dòng trong `_check`: `if provider.kind == UPLOAD_PROGRESS and provider.policy is None: raise RuntimeError(...)` + một test cạnh `test_progress_provider_without_snapshot_is_rejected`. (Luồng thông báo **được** phép `policy=None` — stream đã khoá theo `principal.user_id`.) |
| 2 | **P2** | R-34 | Ba nợ tác giả nêu trong báo cáo (`bao-cao-B4-01.md` mục "Nợ và việc chưa làm") **không có dòng nào trong `DEBT.md`**; báo cáo còn ghi rõ "Không chạm `DEBT.md`". R-34 đòi mỗi nợ một dòng `NO-<nnn>` trước khi phiên kết thúc | `DEBT.md` (thiếu dòng) | Người điều phối ghi **NO-154** (cookie luồng cũ 401 sau `bump_token_version` tới khi FE refresh — chủ F-01), **NO-155** (nhánh riêng phần `sse.py:325->330`: recheck với nhà cung cấp không `policy` — chủ B4-01), **NO-156** (4 nhánh `TimeoutError` đua hiếm của `packages/testing/fixtures/streams.py` — chủ B4-01). Thêm **NO-157** cho finding 1 nếu không sửa trước khi merge |
| 3 | P3 | RES-02 | `stream_slots.release()` nằm **ngoài** khối `CancelScope(shield=True)`: nếu `ctx.client.aclose()` ném (ví dụ `ConnectionPool.release` gặp kết nối không còn trong `_in_use_connections` lúc app dừng), chỗ toàn cục rò **vĩnh viễn** trong vòng đời tiến trình — mỗi lần rò là một luồng nữa không ai mở được | `apps/api/streams/sse.py:417-421` | Bọc `try: … finally: ctx.app.state.stream_slots.release()`. Cân nhắc `asyncio.BoundedSemaphore` để một lượt trả nhầm hai lần kêu to thay vì âm thầm nới trần |
| 4 | P3 | CON-06 | Ba tài nguyên (chỗ semaphore, kết nối pool SSE, mục ZSET) được **giữ** trong `open_stream` nhưng chỉ được **trả** trong `finally` của `stream_body`. Async generator chưa chạy dòng nào thì `finally` không tồn tại: nếu `AppRoute._finish` ném sau khi handler trả `StreamingResponse` (`core/routing.py:245`, `:316-317` commit / `after_commit_idle`), response bị bỏ đi mà không ai lặp — rò cả ba. Hôm nay gần như không chạm tới (route GET công khai không đụng `request.state.db_session`, nên `commit()` là no-op), nhưng quyền sở hữu đang gửi gắm vào một đối tượng mà khung **không** cam kết sẽ tiêu thụ | `apps/api/streams/sse.py:254` ↔ `apps/api/core/routing.py:236-245` | Ghi `DEBT.md`. Hướng sửa rẻ nhất khi cần: gọi `_close` từ một lớp con `StreamingResponse` của B4-01, để không phải sửa `AppRoute` (file của B0-06) |
| 5 | P3 | MNT-02 | `build_stream_app` dài **66 dòng** (R-08: ≤ 50) và 14 hàm ASGI lồng trong cùng file không có docstring (R-01) | `apps/api/streams/tests/test_fixture_streams.py:55-120`, `:237,251,278,306` | Tách 5 app ASGI giả thành các hàm mô-đun cấp cao, mỗi cái một docstring một câu |
| 6 | Nit | MNT-03 | `_id_key` trùng nguyên văn với `packages/messaging/streams.py:93` (R-07). Bản kia là private nên không nhập được — trùng lặp là hệ quả của ranh giới sở hữu, không phải cẩu thả | `apps/api/streams/sse.py:81-84` | Khi B0-05 có lượt sửa: phơi `event_id_key` công khai rồi cả hai chỗ dùng chung |
| 7 | Nit | TEST-05 | `test_expire_stale_uploads_smoke` gọi `client.flushdb()` trong `finally` — xoá sạch DB streams dùng chung. An toàn vì bộ test chạy tuần tự, nhưng sẽ vỡ ngay nếu một ngày nào đó bật `pytest-xdist`; `ephemeral_redis` (B0-05) có sẵn cho đúng việc này | `apps/api/streams/tests/test_jobs.py:78` | Đổi sang `ephemeral_redis`, hoặc xoá đúng khoá mình tạo thay vì `flushdb` |
| 8 | Nit | OBS-04 | Postgres hỏng giữa luồng được `_load_snapshot` dịch thành `AppError` 503, rồi `_still_allowed` bắt bằng `except AppError` và ghi `stream_closed reason="revoked"`. Một sự cố hạ tầng vì thế hiện lên log như một sự kiện thu hồi quyền — gây nhiễu khi truy vết | `apps/api/streams/sse.py:327-329` | Tách `DEPENDENCY_UNAVAILABLE` ra lý do `dependency_error` riêng |
| 9 | Nit | MNT-05 | Nhánh vượt mốc 400 dòng logic (≈ 979 dòng mã nghiệp vụ trong 9 file + 445 dòng fixture). **Không đáng tách**: prompt định nghĩa đúng một deliverable và một lượt squash ([10], [11].5), và việc chia nhỏ đã xảy ra ở mức commit (ba nhánh con A/B/C) | `apps/api/streams/**` | Không hành động |

Quan sát ngoài finding: nhịp recheck mặc định (`STREAM_RECHECK_S=3`) cộng `AUTH_PRINCIPAL_CACHE_TTL_S=5` nghĩa là ở trần 500 luồng, khoảng 100 truy vấn Postgres/giây chỉ để giữ quyền (`sse.py:310-330`). Đây là hành vi **do hiến chương quy định**, không phải lỗi của nhánh này; ghi lại để lúc đo tải thật có số mà so.

Không có finding **P0** và không có finding **P1**.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 3 (finding 1, P2) | 0,75 |
| CON – Concurrency & dữ liệu | 15 % | 4 (finding 3, 4 — P3) | 0,60 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (finding 3) | 0,40 |
| DB, API – Migration & contract | 10 % | 5 (không migration; H1, H3, H5 đạt) | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (finding 7) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 4 (finding 8) | 0,20 |
| MNT – Bảo trì | 3 % | 3 (finding 2, P2) | 0,09 |
| **Tổng** | **100 %** | | **4,07 / 5** |

## PHÁN QUYẾT: APPROVE (4,07/5)

Nhánh này làm đúng việc khó nhất của một trung tâm SSE và làm cẩn thận: vị trí bắt đầu chốt
**trước** byte đầu nên không mất sự kiện giữa `tail_id` và ảnh chụp; phần dọn được chắn huỷ
nên chỗ giữ không rò khi client rớt (đo thật: 20 lượt mở–đóng, `CLIENT LIST` không tăng);
generator không giam kết nối Postgres nào (`pool.checkedout() == 0` với 20 luồng); pool Redis
của SSE có trần riêng nên vài nghìn luồng không thể cướp `maxclients` của `redis-broker`
dùng chung với Celery. Bộ test không có chỗ nào giả vờ: Redis thật bị `stop()` giữa luồng,
cookie luồng do chính `POST /api/auth/refresh` cấp, K11 được kiểm bằng cách khẳng định chuỗi
riêng tư vắng mặt trong log. Cổng 8/8 `đạt` với mã thoát thật do phiên review tự chạy, H5 `đạt`,
`case_gate` đủ 9 + 7 case, `apps/api/streams` 100 % dòng · 98,48 % nhánh.

Hai finding P2 không chặn merge theo ma trận RULE.md §5 (không P0/P1, điểm ≥ 4,0), nhưng **phải
có dòng `DEBT.md` trước khi gộp** (finding 2 chính là việc đó). Finding 1 là thứ đáng sửa ngay
hơn là ghi nợ: nó là một dòng trong `registry._check` cộng một test, và nó đóng đúng cái bẫy mà
B2-04 — prompt kế tiếp cắm vào cổng này — có thể bước vào mà không cổng nào kêu. Nếu người điều
phối muốn gộp ngay, ghi NO-157 và giao FIX cho B4-01 trước khi B2-04 bắt đầu; nếu chờ được một
lượt sửa ngắn thì sửa rồi gộp là sạch hơn.

Không tự merge: việc gộp thuộc phiên gọi review này.
