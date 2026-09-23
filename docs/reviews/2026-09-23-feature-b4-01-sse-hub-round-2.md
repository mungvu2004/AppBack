# Review merge feature/b4-01-sse-hub → main — lượt 2 (vòng sửa)

- Ngày: 2026-09-23 · Reviewer: phiên `/merge-review` (độc lập, worktree `review-b4-01-r2`) · Commit đầu nhánh: `31e65fa837e6`
- Lượt 1: APPROVE 4,07/5 tại `f01ce1b05860` — `docs/reviews/2026-09-23-feature-b4-01-sse-hub.md`
- Phạm vi lượt này: **chỉ** `git diff f01ce1b..31e65fa` — 1 commit, 11 file, +216 / −51. Phần đã duyệt ngoài diff không chấm lại.
- Cổng: `bash tools/verify/run.sh verify` (8 bước, **không** `--steps`) mã thoát **0** — chạy tại chỗ, log `backend/dieu-phoi/chay/B4-01/review-b4-01-r2.log` (dòng `EXIT=0`)
- Test: **3289 qua / 0 hỏng / 4 deselected**, 580,26 s
- Độ phủ (lượt cổng của phiên review): tổng dòng **99,09 %** · nhánh **97,58 %**; `apps/api/streams` dòng **100,00 %** · nhánh **98,57 %**; `packages/testing` dòng 99,16 % · nhánh 97,37 %; tập file bị chạm dòng 99,45 % · nhánh 96,09 %

## Bảng cổng E.10 (trạng thái lấy từ mã thoát thật của lượt chạy này)

| bước | lệnh | trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (7 revision, 1 head) |
| 7 | `tools.contract.check` (H1 H3 H4 H5) | đạt — **H5 đạt**, 3 khung SSE |
| 8 | `openapi` | đạt |

`mã thoát: 0`. H4 `không áp dụng` đúng luật BE-00 §12 (B3-05 chưa hợp nhất, chưa có `apps.api.rules.catalog`).

`case_gate` hai op của prompt, nguyên văn lượt này:

```
streams_open_notifications | bắt buộc ['S01','S02','S03','S04','S05','S07','S09'] | tìm thấy [đủ] | đạt
streams_open_progress      | bắt buộc ['S01',…,'S09'] (9 case)                    | tìm thấy [đủ] | đạt
```

## Điều kiện dừng sớm — không cái nào kích hoạt

- `git status --porcelain` rỗng. Commit `31e65fa` dòng đầu `fix(streams): close the provider policy gap and the slot leak` (54 ký tự, đúng Conventional Commits), thân mang trailer `Prompt: B4-01`.
- Diff chỉ chạm `apps/api/streams/**` (3 file mã + 8 file test). **Không** chạm `docs/charter/*`, `openapi.json`, `uv.lock`, `tools/**`, `DEBT.md`, `packages/**` — đúng cột sở hữu của B4-01 (R-27).
- `changes/B4-01.md` có mặt.
- Không `# pragma: no cover`, `pragma: no branch`, `# type: ignore` trần, `# noqa` trần, `skip`/`xfail` mới, không hạ ngưỡng nào trong diff (quét `git diff | grep`).

## Từng finding lượt 1 — tự kiểm bằng mã, không tin báo cáo

| # | Mức lượt 1 | ID | Trạng thái | Bằng chứng tôi tự kiểm |
|---|---|---|---|---|
| 1 | **P2** | SEC-02 | **đã sửa đúng gốc** | `registry._check` (`registry.py:82-103`) nay ném `RuntimeError` khi `kind == upload_progress` mà `policy is None`, đối xứng luật `snapshot` — lỗ bị chặn ngay **lúc dò**, không vá ở chỗ dùng. `StreamKind` là `Literal["upload_progress","notifications"]` (`providers.py:30`) nên nhánh `return` sớm cho `kind != UPLOAD_PROGRESS` chỉ bỏ qua đúng luồng thông báo — luồng này được phép `policy=None` vì stream khoá cứng theo `principal.user_id`, không có tham số chọn người khác. `if provider.policy is not None` vẫn còn ở `sse.py:241` và `:327` nhưng nay **không** còn là đường fail-open: sổ không thể chứa provider `upload_progress` thiếu policy. Test: `test_progress_provider_without_policy_is_rejected` + `test_notifications_provider_without_policy_is_accepted` |
| 2 | **P2** | R-34 | **đã đóng ngoài nhánh** | `DEBT.md` trên `main` (`da80292`) có NO-154, NO-155, NO-156, NO-157. Đúng: spec worker cấm sửa `DEBT.md`, người điều phối đã ghi |
| 3 | P3 | RES-02 | **đã sửa đúng gốc** | `_close` (`sse.py:408-431`) bọc `try: … finally: stream_slots.release()` **bên trong** `CancelScope(shield=True)`, nên `aclose()` ném vẫn trả chỗ; `_log_closed` cũng vào `finally` nên dòng `stream_closed` không mất. Bộ đếm đổi sang `asyncio.BoundedSemaphore` (`router.py:63-65`) — trả dư ném `ValueError` thay vì âm thầm nới trần. Kiểm hết ba đường trả chỗ (`sse.py:193` khi `initialize()` hỏng, `:253` khi `resolve_start` hỏng, `:430` trong generator): loại trừ nhau, không đường nào trả hai lần. Test hồi quy: `test_cleanup_returns_the_slot_when_the_pool_release_fails` (ép `ConnectionPool.release` ném) |
| 4 | P3 | CON-06 | **để nợ, lý do đứng được** | NO-156 mở trên `main`. Lý do tác giả đúng: lớp con `StreamingResponse` không cứu được trường hợp `__call__` **không bao giờ** chạy, còn cách "ép generator bắt đầu trước response" đổi một lỗ hiếm lấy một `yield` khó hiểu trên đường nóng |
| 5 | P3 | MNT-02 | **đã sửa** | `build_stream_app` 66 → 15 dòng; năm app ASGI giả ra mức module (`_hang_endpoint`, `_ping_endpoint`, `stream_close`, `stream_crash`, `error_401`, `_fake_lifespan`), mọi hàm lồng còn lại trong file đã có docstring (R-01, R-08). Refactor thuần, không đổi hành vi test nào |
| 6 | Nit | MNT-03 | **để nợ, đúng ranh giới** | NO-157 mở. `packages/messaging/**` không thuộc B4-01 (K27) |
| 7 | Nit | TEST-05 | **đã sửa, sửa gốc** | Bỏ `flushdb` ở **cả hai** chỗ cùng mùi (`test_jobs.py:79` mà lượt 1 nêu **và** `test_lifecycle.py:50` mà lượt 1 bỏ sót) — R-19. Kiểm thêm: mỗi test chỉ tạo đúng một khoá, nên `client.delete(key)` là dọn **đủ**, không để rác lại cho test sau |
| 8 | Nit | OBS-04 | **đã sửa đúng gốc** | `_still_allowed` (`sse.py:328-332`) tách `DEPENDENCY_ERROR` khỏi `REVOKED`. Tự truy đường thật: `_load_snapshot` (`auth/sessions.py:588-597`) → `translate_db_error` (`packages/db/errors.py:57-70`) trả đúng `DEPENDENCY_UNAVAILABLE` cho SQLSTATE hạ tầng, `OperationalError`, `InterfaceError`, timeout và `connection_invalidated`. `ErrorCode` là dataclass tạo một lần trong `ERRORS` và `define` cấm trùng tên mã, nên so `is` vừa đúng vừa chặt. Test: `test_infrastructure_failure_closes_with_its_own_reason` |
| 9 | Nit | MNT-05 | không hành động | Đúng như lượt 1 kết luận |
| — | nợ nhánh | — | **đã đóng, có kiểm lại** | Nhánh `sse.py 325->330`: `test_notifications_stream_survives_rechecks_without_a_policy`. Tôi chạy lại độ phủ riêng cho `apps/api/streams` trong container (log `review-b4-01-r2-cov.log`): `sse.py` **239 lệnh, 0 thiếu; 36 nhánh, 0 riêng phần → 100 % dòng, 100 % nhánh**. Nợ này đóng thật |

## Finding mới của lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST-04 | **Một nhánh của `apps/api/streams` chỉ được phủ khi may**, nên con số báo cáo không lặp lại được: cổng của tác giả ghi `apps/api/streams … nhánh 100,00 %`, cổng của tôi trên **cùng** sha ghi **98,57 %**. Lượt đo độ phủ riêng cho gói khoanh đúng chỗ lệch: `jobs.py 91->85` (vòng `SCAN` quay thêm một lượt) là nhánh riêng phần duy nhất của cả gói. Nó chỉ chạy khi DB streams dùng chung còn đủ khoá để `SCAN` trả cursor khác 0 — tức phụ thuộc rác của test khác, mà vòng sửa này đụng đúng chỗ đó (bỏ `flushdb`). `BATCH = 3` với đúng 3 khoá seed **không** ép được nhiều lượt `SCAN` như docstring của nó nói: `COUNT` chỉ là gợi ý, keyspace nhỏ thì Redis trả hết trong một lượt | `apps/api/streams/jobs.py:85-91`; `apps/api/streams/tests/test_jobs.py:24` (`BATCH`), `:33-39` (`_seed`) | Seed nhiều khoá hơn `batch` một cách rõ ràng (ví dụ 10 khoá với `batch=3`) trong `_seed`, hoặc khẳng định thẳng số lượt `SCAN` bằng một client đếm lời gọi. Chưa sửa thì đừng trích con số `100 %` cho gói này — nó không lặp lại |
| 2 | Nit | MNT-01 | Luật "`upload_progress` bắt buộc có `policy`" chỉ áp cho **nhánh khai báo**: `build_registry` trả `{**default_providers(), **found}` (`registry.py:110-117`) nên bản mặc định không đi qua `_check`. Hôm nay đúng (mặc định là `DenyUploads` giữ cả hai vai, và `S06_no_provider` kiểm 404), nhưng bất biến vừa dựng lại có một cửa không ai gác | `apps/api/streams/registry.py:110-117` | Cho bản mặc định chạy qua `_check` luôn, hoặc một khẳng định một dòng trong test sổ: `default_providers()[UPLOAD_PROGRESS].policy is not None` |

Vòng sửa **không** mở lỗi mới nào ngoài hai mục trên. Đã kiểm và **không** thành finding:
`connections.release` bọc trong `soft_redis` nên không ném — đường "ZREM ném làm mất bước trả
kết nối pool" (đối xứng của finding 3) không tới được; `BoundedSemaphore` không có đường trả
dư nào trong mã hiện tại; `_log_closed` vào trong `CancelScope` không đổi ngữ nghĩa
`ContextVar` vì cancel scope không sao chép context; `monkeypatch` pool trong test mới chỉ
chạm app của chính test đó (mỗi test dựng pool riêng trong `lifespan`).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (finding 1 lượt 1 đã sửa đúng gốc, có test) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 4 (NO-156 còn mở, P3) | 0,60 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 (finding 3 đã sửa, có test hồi quy) | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (không migration; H1, H3, H5 đạt) | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (finding 1 lượt 2 + NO-155, đều P3) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 (finding 8 đã sửa) | 0,25 |
| MNT – Bảo trì | 3 % | 4 (finding 2 lượt 2 là Nit; NO-157 còn mở) | 0,12 |
| **Tổng** | **100 %** | | **4,75 / 5** |

Không có finding **P0**, không có **P1**, không có **P2** mới.

## PHÁN QUYẾT: APPROVE (4,75/5)

Vòng sửa làm đúng thứ lượt 1 đòi và làm ở đúng chỗ. Finding 1 (SEC-02) không được vá tại
điểm dùng mà bị chặn ngay lúc dò sổ, nên cái bẫy mà B2-04 có thể bước vào nay nổ lúc
`lifespan` chứ không lặng lẽ mở tiến độ của mọi lượt tải cho mọi người đã đăng nhập; và vì
`StreamKind` chỉ có hai giá trị, nhánh miễn trừ rộng đúng bằng luồng thông báo, không hơn
một ly. Finding 3 (RES-02) được sửa bằng `finally` **trong** vùng chắn huỷ cộng
`BoundedSemaphore`, có test ép `ConnectionPool.release` ném thật chứ không giả vờ. Finding 8
tôi truy ngược tới `translate_db_error` để chắc rằng `DEPENDENCY_UNAVAILABLE` đúng là mã mà
Postgres hỏng sinh ra, không phải một mã chọn cho vừa test. Finding 7 còn được sửa rộng hơn
lượt 1 yêu cầu: chỗ `flushdb` thứ hai mà lượt 1 bỏ sót cũng đi (R-19). Cổng 8/8 `đạt`, mã
thoát 0, H5 `đạt`, `case_gate` đủ 9 + 7 case, do chính phiên này chạy một lượt.

Hai điều đáng nói mà không chặn merge. Một, con số `100 %` nhánh cho `apps/api/streams` trong
báo cáo tác giả **không lặp lại** trên cùng sha: cổng của tôi ra 98,57 %, và lượt đo riêng
khoanh chỗ lệch vào `jobs.py 91->85`, một nhánh chỉ chạy khi DB dùng chung tình cờ còn khoá —
nên ghi nợ và đừng trích con số đó nữa. Riêng `sse.py` thì 100 % dòng và 100 % nhánh là thật,
tôi đo lại: nợ nhánh `325->330` đóng đúng. Hai, luật `policy` vừa dựng chưa áp cho bản mặc
định của chính sổ — hôm nay vô hại và đã có test 404 che, nhưng là một dòng để bất biến không
còn cửa sau.

Nợ nên ghi trước khi gộp: **NO-158** cho finding 1 lượt 2 (id kế tiếp còn trống — NO-155,
NO-156, NO-157 đã dùng ở `da80292`, khác với con số NO-155 mà spec của phiên này ghi).
NO-155, NO-156, NO-157 đang mở đều là P3 hoặc thấp hơn và đều có chủ, nên R-35/R-38 không
chặn gộp.

Không tự merge: việc gộp thuộc phiên gọi review này.
