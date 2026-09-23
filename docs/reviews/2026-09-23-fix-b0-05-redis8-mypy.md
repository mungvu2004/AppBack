# Review merge fix/b0-05-redis8-mypy → main

- Ngày: 2026-09-23 · Reviewer: phiên /merge-review (worktree riêng, không sửa mã, không merge)
- Commit đầu nhánh: `cc57a74180aa` · 4 commit trên `main` · diff 42+/11- trên 5 file
- Cổng: `bash tools/verify/run.sh verify` mã thoát **0**, 8/8 `đạt`
  (log: `backend/dieu-phoi/chay/B4-01/review-fix-080-r1.log`, dòng `EXIT=0` ở cuối)
- Test: 3029 qua, 0 hỏng, 4 deselect (9 phút 17)
- Độ phủ: tổng **dòng 99,09% · nhánh 97,67%**; `packages/messaging` 100,00% / 100,00%;
  `apps/api/core` 99,47% / 98,06%; `apps/api/auth` 98,49% / 91,91%; tập file bị chạm 100% / 100%

## Bảng cổng (mã thoát thật, không chép từ báo cáo tác giả)

| Bước | Nội dung | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (baseline NO-148 6 lỗi → 0) |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 0 đơn vị bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt |
| 8 | openapi | đạt (xuất `/tmp/openapi.json`, 29386 byte) |

H4/H5 báo `không áp dụng` đúng luật BE-00 §12 (B3-05 và B4-01 chưa hợp nhất), không phải `hỏng`.

## Đã tự kiểm (không tin báo cáo tác giả)

- Cây sạch, `HEAD` đúng `cc57a74`, 4 commit; trailer `Prompt:` + `Fix: FIX-080` của **cả bốn**
  commit đọc được bằng `git log --format='%(trailers:key=Prompt,valueonly)'` (R-36b đạt).
- Sở hữu file khớp đúng cột chủ sở hữu của NO-148: B0-05 (`packages/messaging/streams.py`,
  `tests/test_locks.py`, `tests/test_streams.py`), B0-06 (`apps/api/core/tests/test_internals.py`),
  B1-01 (`apps/api/auth/tests/test_units.py`). Không đụng file cấm, không sửa `uv.lock`,
  `docs/charter/*`, `openapi.json` (R-27 đạt).
- 6 lỗi baseline (`log-viec-a-tests-1.log`, mục BASELINE MYPY) ánh xạ 1-1 vào đúng 4 vị trí đã sửa:
  3 lỗi ở `streams.py:143` là **một** chỗ gọi, 3 lỗi còn lại mỗi file một chỗ. Không thừa, không thiếu.
- `grep` toàn bộ `streams.py`: chỉ **một** lời gọi `xread` (dòng 158); `SyncEventBus` chỉ `xadd`.
  Sửa ở đúng chỗ mọi đường đi qua, không vá triệu chứng (R-19 đạt cho phần mypy).
- Diff không có `# pragma: no cover`, `pragma: no branch`, `type: ignore`, `noqa`, `skip`, `xfail`,
  không hạ ngưỡng cổng nào (K24 đạt).
- `_stream_entries` được gọi **ngoài** `with redis_errors()`, nên `TypeError` của nó nổi lên thành
  500 `INTERNAL` chứ không bị xếp nhầm thành 503 — đúng R-16.
- `read_after` giữ nguyên hành vi: `[] if not streams else …` không đổi, `block=block_ms or None`
  không đổi. Hai nhánh `TypeError` đều có test (`test_streams.py:76`, `:82`); đường RESP2 thật vẫn
  do test Redis thật `test_read_after_returns_new_events_in_order_without_repeats` phủ.
- `test_locks.py:66` đổi `int(await …get())` thành gán + `assert … is not None` + `int(...)`:
  giữ nguyên ý nghĩa, assert chặt hơn chứ không nới.
- Import `_stream_entries` (tên riêng tư) trong test cùng gói là thông lệ sẵn có của repo
  (`test_internals.py:27`, `test_assess.py:16`, `test_refresh.py:21`…), không phải finding.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | MNT-04, R-02 | Docstring lý giải sai: "client Streams không đặt `protocol=3` nên **luôn** nhận RESP2". Sau chính cú bump này, redis-py 8.1 mặc định **RESP3 trên dây** (`redis/utils.py:283 DEFAULT_RESP_VERSION = 3`; 6.4.0 là `protocol: Optional[int] = 2`). Dạng list của `xread` còn giữ được **chỉ vì** `legacy_responses: bool = True` (`redis/connection.py:830`) — một cờ tương thích mà upstream ghi rõ là đích di trú (`legacy_responses=False`). Mã chạy đúng hôm nay, nhưng lý do viết trong docstring là sai, và người đọc tin nó sẽ kết luận "không thể xảy ra" | `packages/messaging/streams.py:81-82`; lặp lại ở `packages/messaging/tests/test_streams.py:77` | Sửa hai dòng docstring: nói đúng rằng client chạy RESP3 và dạng RESP2 đến từ `legacy_responses=True` mặc định; nêu hệ quả là đặt `legacy_responses=False` sẽ làm `read_after` ném `TypeError` |
| 2 | P2 | RES-02 | Bump đổi chính sách retry mặc định mà không test nào bắt: `Retry(ExponentialWithJitterBackoff(base=1, cap=10), retries=3)` (6.4.0) → `retries=10, base=0.01, cap=1` (8.1.0, `redis/_defaults.py:37-39`). `_async_client`/`_sync_client` không đặt `retry` tường minh, nên trần 0,5 s của `SYNC_TIMEOUT_S` — cố ý chọn vì chạy "ngay trên đường trả response" — thực tế là tới 11 lượt thử cộng backoff trước khi `redis_errors()` thấy `ConnectionError` và trả 503. Gap này có sẵn từ trước, cú bump làm nặng thêm | `packages/messaging/redis.py:119-127`, `:130-136` | Đặt `retry=Retry(...)` tường minh cho từng vai theo đúng ngân sách R-24 (sync 0,5 s thì 0-1 lượt), hoặc ghi rõ trong docstring vì sao chấp nhận mặc định của thư viện |
| 3 | P2 | R-19, OPS-02 | Dòng NO-148 tự ghi hai nửa chữa: (a) thu hẹp kiểu, (b) "chặn Dependabot gộp khi chưa qua `verify`". Nhánh chỉ làm (a). Nguyên nhân gốc vẫn nguyên: `packages/messaging/pyproject.toml:7` khai `"redis"` **không ràng buộc phiên bản**, và `.github/dependabot.yml` không có `ignore` cho `version-update:semver-major`, nên `d0bb175` (`update-type: version-update:semver-major`) vào thẳng `main` dù `ci.yml` có chạy trên `pull_request` | `packages/messaging/pyproject.toml:7`, `.github/dependabot.yml:8-19`, `DEBT.md:168` | Ngoài sở hữu của B0-05/B0-06/B1-01 → ghi nợ mới, giao B0-09 (dependabot/CI) + người điều phối (required status check trên `main`). Không chặn FIX này |
| 4 | Nit | R-01 | `test_stream_entries_rejects_entries_that_are_not_a_list` thiếu docstring trong khi hai test anh em ngay trên đều có. (File vốn đã có tiền lệ hàm riêng tư không docstring — `_decode`, `_id_key`, `_check_event_id` — nên chỉ là lệch phong cách trong chính khối mã mới) | `packages/messaging/tests/test_streams.py:82-84` | Thêm một dòng nêu bất biến được khẳng định |
| 5 | Nit | MNT-04 | Docstring `sync_result` vẫn nói redis-py khai kiểu trả của **mọi** lệnh là `Awaitable \| Any`; sau 8.0 điều đó chỉ còn đúng với client đồng bộ — chính hai `cast` bị xoá trong diff này là bằng chứng phía async đã được khai đúng | `packages/messaging/redis.py:104-110` | Một dòng sửa lại phạm vi (file thuộc B0-05, sửa được ngay trong nhánh này) |

Không có P0, không có P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 3 (finding 2) | 0,30 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 3 (finding 3) | 0,15 |
| MNT – Bảo trì | 3% | 3 (finding 1) | 0,09 |
| **Tổng** | **100%** | | **4,64 / 5** |

Không P0/P1 và điểm ≥ 4,0 → `APPROVE` theo ma trận `RULE.md` §5.

## PHÁN QUYẾT: APPROVE

Nhánh sửa đúng nguyên nhân gốc của NO-148 ở tầng kiểu: một helper `_stream_entries` thu hẹp kết quả
`xread` tại **chỗ gọi duy nhất**, ném `TypeError` rõ ràng cho dạng ngoài dự kiến thay vì nuốt, và
đứng ngoài `redis_errors()` nên không bị xếp nhầm thành 503. Ba chỗ còn lại chỉ bỏ `cast` đã thành
thừa sau khi redis-py 8 khai `@overload` tách sync/async — test giữ nguyên ý nghĩa, chỗ `test_locks.py`
còn chặt hơn trước. Cổng đầy đủ xanh 8/8 với mã thoát 0, độ phủ mọi gói bị chạm vượt xa ngưỡng 90/90,
sở hữu file và trailer đúng luật. Merge được.

**Ba việc phải làm sau merge (không chặn):**
1. Người điều phối đổi trạng thái NO-148 từ `mở` sang đã sửa (R-34: đổi trạng thái, **không xoá dòng**).
2. Ghi nợ mới (id kế tiếp `NO-151`) gộp finding 2 và finding 3: chính sách retry mặc định của redis-py 8
   so với ngân sách timeout R-24 (chủ: B0-05) và ràng buộc phiên bản `redis` + cổng chặn Dependabot
   major (chủ: B0-09 + người điều phối). Cả hai là P2, có dòng `DEBT.md` là đủ theo `RULE.md` §5.
3. Finding 1, 4, 5 đều là sửa docstring một dòng trong file B0-05 sở hữu — gom vào lượt chạm
   `packages/messaging` kế tiếp, không cần nhánh riêng.
