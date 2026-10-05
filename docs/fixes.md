# FIXES — Sổ mã FIX

> `docs/charter/FIX.md` luật 5: mỗi FIX có mã `FIX-<nnn>` tăng dần, **không dùng lại**,
> ghi ở đây. Người điều phối giữ file này; worker chỉ đọc để biết mã kế tiếp.
> Thông điệp commit của FIX mang **hai** trailer: `Prompt: <mã prompt sở hữu file>` và
> `Fix: FIX-<nnn>` (BE-00 §13.2).

| Mã | Ngày | Cho prompt | Nợ | Một câu | Commit |
|---|---|---|---|---|---|
| FIX-001 | 2026-09-20 | B0-01 | NO-001 | `run.sh lock` hỏng `FileExistsError` vì thư mục ra là mount point | `c5bf22e` |
| FIX-002 | 2026-09-20 | B0-03 | NO-002 | Không có trần bắt tay tường minh nên cổng kết tội nhầm migration | `68cdebe` |
| FIX-003 | 2026-09-20 | B0-01 | NO-031 | Ba test của `case_gate` chốt "repo chưa có thao tác/task nào" làm bất biến | `cdee48c` |
| FIX-004 | 2026-09-20 | B0-03 | NO-032 | `test_new_revision` ghim head `r20260920_b0_03` làm hằng | `960dced` |
| FIX-005 | 2026-09-20 | B0-05 | NO-033 | Hai test của `messaging` chốt "sổ task và beat rỗng" | `c952c40`, `d032787` |
| FIX-006 | 2026-09-21 | B0-01 | NO-008 | `_clean_dir` nuốt lỗi xoá file trong thư mục ra | `a61b92c` |
| FIX-007 | 2026-09-21 | B0-01 | NO-042 | `test_services` bắt tay Postgres dùng chung với trần 5 s | `f3559f1` |
| FIX-008 | 2026-09-21 | B0-01 | NO-043 | Mẫu golden không được chép ra `contract-samples/` cuối lượt | `d1c72d5` |
| FIX-009 | 2026-09-21 | B0-01 | NO-007 | Chặng `host.docker.internal` tới testcontainers kẹt ~68 s | `3ca1463`, `caaf5ab` |
| FIX-010 | 2026-09-21 | B0-03 | NO-036 | `db_sessionmaker` dùng trần bắt tay 10 s của đường request | `e3f2598` |
| FIX-011 | 2026-09-21 | B0-04 | NO-009 | S3 5xx có thân XML lọt ra thành 500 thay vì 503 | `f070775` |
| FIX-012 | 2026-09-21 | B0-04 | NO-010 | `_delete_under` xoá từng object (N+1) | `6c256d4` |
| FIX-013 | 2026-09-21 | B0-04 | NO-011 | `signed_url(inline)` tốn `HEAD` cho khoá do server đặt tên | `f72590b` |
| FIX-014 | 2026-09-21 | B0-04 | NO-012 | `LocalDiskStorage.delete_prefix` nuốt lỗi xoá | `280dbd4` |
| FIX-015 | 2026-09-21 | B0-04 | NO-013 | `list_prefix` nạp cả danh sách vào RAM | `b298535` |
| FIX-016 | 2026-09-21 | B0-04 | NO-014 | `S3Storage.put` để lỗi đĩa của bộ đệm ra 500 | `1690533` |
| FIX-017 | 2026-09-21 | B0-04 | NO-015 | `ensure_bucket` nuốt mọi `S3Error` của CORS | `52ccb1b` |
| FIX-018 | 2026-09-21 | B0-04 | NO-016 | Hai test storage phụ thuộc đồng hồ thật | `e8890c5` |
| FIX-019 | 2026-09-21 | B0-04 | NO-017 | Phần B0-04 của NO-017: khẳng định test và chú thích `_message` | `5e0a831` |
| FIX-020 | 2026-09-21 | B0-05 | NO-022 | Chưa test đường giao lại thật khi worker chết | `b6c54ea` |
| FIX-021 | 2026-09-21 | B0-05 | NO-023 | Bộ đếm giao lại tốn hai lượt Redis, `EXPIRE` hỏng thì sống mãi | `382000c` |
| FIX-022 | 2026-09-21 | B0-05 | NO-024 | `asyncio.Runner` của worker không bao giờ đóng | `929fa9b` |
| FIX-023 | 2026-09-21 | B0-05 | NO-025 | `SafeLock.hold` không chặn được thân nuốt huỷ hay chạy đồng bộ dài | `befdf78` |
| FIX-024 | 2026-09-21 | B0-05 | NO-027 | Test khoá chốt hành vi bằng đồng hồ thật, biên 300 ms | `f3e3058` |
| FIX-025 | 2026-09-21 | B0-05 | NO-028 | `release` trong `finally` che ngoại lệ thật của thân | `970d779` |
| FIX-026 | 2026-09-21 | B0-05 | NO-029 | Bộ đếm rào `lock:{name}:fence` không có ngưỡng ghi rõ | `11084c1` |
| FIX-027 | 2026-09-21 | B0-05 | NO-030 | `_fail` ghi `repr` đầy đủ của ngoại lệ module khác | `aa60797` |
| FIX-028 | 2026-09-21 | B0-06 | NO-044 | Hai bộ khớp (method, đường) → thao tác trùng nhau | `d3b25b0` |
| FIX-029 | 2026-09-21 | B0-06 | NO-053 | Năm test lõi của B0-06 chốt "chưa có B1-01" (verifier DenyAll, đúng hai router, đúng ba thao tác) | `1e2d146` |
| FIX-030 | 2026-09-21 | B0-06 | NO-054 | `rate_limit` chỉ nhận hạn mức số nguyên, module có cấu hình đọc lười phải dựng limiter mỗi request | `971a1a1` |
| FIX-031 | 2026-09-21 | B0-06 | NO-055 | `api_env` không `FLUSHDB` DB an toàn giữa các test | `9f80576` |
| FIX-032 | 2026-09-22 | B0-01 | NO-048 | Lượt verify lạnh chạy `npm ci` (tải mạng) ngay trong bước 5 | `02f2b64` |
| FIX-033 | 2026-09-22 | B0-01 | NO-049 | `case_gate` chưa xuất hàm tách tên test công khai | `a21a0ac` |
| FIX-034 | 2026-09-22 | B0-07 | NO-049 | Bộ ghi golden nhập hằng riêng `_TEST_*_RE` của `case_gate` | `84fed27` |
| FIX-035 | 2026-09-22 | B0-07 | NO-052 | `tools.contract.check` không `--build-dir` để lại `/tmp/contract-*` | `1ca38e2` |
| FIX-036 | 2026-09-22 | B0-03 | NO-057 | `migrate_check` không so tên `CHECK` của DB với model | `593bcea` |
| FIX-037 | 2026-09-22 | B0-06 | NO-057 | Hai `CHECK` của `idempotency_records` lặp tiền tố tên | `4e8e2a5` |
| FIX-038 | 2026-09-22 | B0-01 | NO-058 | `lint_migrations` không miễn revision contract đã đăng ký: đường contract của BE-00 §6.1 không dùng được | `f37c52e` |
| FIX-039 | 2026-09-22 | B0-03 | NO-065 | `test_new_revision` đóng băng ngày lúc nhập, đỏ khi bộ test vắt qua nửa đêm UTC | `5ce33f0` |
| FIX-040 | 2026-09-22 | B0-03 | NO-069 | `migrate_check.run_checks` vượt R-08 (82 dòng, CC 13) | `646740e` |
| FIX-041 | 2026-09-22 | B0-03 | NO-070 | Bước "tên CHECK khớp model" đỏ giả với CHECK gắn kiểu | `eda31d6`, `3b4f01c` |
| FIX-042 | 2026-09-22 | B0-01 | NO-068 | `lint_migrations._lint_body` vượt R-08 (78 dòng, CC 28) | `76ec3fd` |
| FIX-043 | 2026-09-22 | B0-02 | NO-060 | Luật khoá object chưa có ở `packages/core` | `f6fb907` |
| FIX-044 | 2026-09-22 | B0-04 | NO-060 | `storage.keys` giữ bản riêng của luật khoá object | `59e9e32` |
| FIX-045 | 2026-09-22 | B5-01 | NO-060 | `ml_contracts.payloads` chép luật khoá object của `storage` | `4aad113` |
| FIX-046 | 2026-09-22 | B0-04 | NO-073 | `_SERVER_NAMED_RE` chép tay luật id tầng của `core/ids.py` | `09e4b21` |
| FIX-047 | 2026-09-22 | B0-04 | NO-072 | Test FIX-012 không chạm biên 1000 khoá/lượt `DeleteObjects` | `1bd891b` |
| FIX-048 | 2026-09-22 | B1-01 | NO-066 | `test_auth_refresh__C11_parallel` chập chờn (21×401 thay vì 20) | `b15a622` |
| FIX-049 | 2026-09-22 | B0-01 | NO-067 | Bộ lọc case của `_found_cases_by_op` chưa test nào chạm | `3cb7abf` |
| FIX-050 | 2026-09-22 | B0-05 | NO-074 | `SafeLock` chưa công khai đường trả khoá lặng lẽ | `7e56b05` |
| FIX-051 | 2026-09-22 | B5-01 | NO-074 | `gpu.py` chép logic trả khoá lặng lẽ của `SafeLock` | `f6ee1dc` |
| FIX-052 | 2026-09-22 | B0-01 | NO-075 | Chép mẫu golden hỏng thì mất bảng cổng, lượt đạt vẫn thoát 1 | `fc5da84` |
| FIX-053 | 2026-09-22 | B0-01 | NO-080 | Log cổng mất khi shell bọc `run.sh verify` bị cắt | `b8e896a` |
| FIX-054 | 2026-09-22 | B0-02 | NO-076 | `core/ids.py` chưa phơi hàm kiểm thân ULID không tiền tố | `b2864d9` |
| FIX-055 | 2026-09-22 | B0-04 | NO-076 | `storage.keys._ULID_RE` chép thân ULID của `core/ids.py` | `5c8586a` |
| FIX-056 | 2026-09-22 | B0-02 | NO-077 | Bố cục tiền tố lượt tải lên chưa có ở `packages/core` | `271382b` |
| FIX-057 | 2026-09-22 | B0-04 | NO-077 | `storage.keys.upload_prefix` giữ bản riêng của bố cục dùng chung | `318dc5b` |
| FIX-058 | 2026-09-22 | B5-01 | NO-077 | `ml_contracts._upload_prefix` dựng lại bố cục khoá của `storage` | `778c052` |
| FIX-059 | 2026-09-22 | B0-05 | NO-078 | Worker Celery thử để logger gốc ở ERROR sau test messaging | `81ac394` |
| FIX-060 | 2026-09-22 | B0-02 | NO-088 | `upload_prefix_of` chỉ kiểm phần đầu khoá | `225b4dc` |
| FIX-061 | 2026-09-22 | B0-02 | NO-081 | Bố cục `runs/…/` và `ml/models/…/` chưa có ở `packages/core` | `2eaa822` |
| FIX-062 | 2026-09-22 | B0-04 | NO-081 | `storage.keys` dựng `runs/…/`, `ml/models/…/` bằng bản riêng | `4bdbbbe` |
| FIX-063 | 2026-09-22 | B5-01 | NO-081 | `ml_contracts` dựng lại `runs/…/`, `ml/models/…/`; `_id_of` chép `check_id` | `e9d8f3f` |
| FIX-064 | 2026-09-22 | B1-01 | NO-082 | Bộ kiểm của C11 gọi lỗi đếm thật là "cửa sổ thứ hai" | `d1913ec` |
| FIX-065 | 2026-09-22 | B0-01 | NO-089 | Log cổng không có traceback, không "mã thoát" khi lượt verify ném lỗi | `aa18bd7`, `8a1cf3d` |
| FIX-066 | 2026-09-22 | B0-01 | NO-090 | Log cổng `.cache/src-out/verify/*.log` dồn mãi, không trần | `1b6bc06` |
| FIX-067 | 2026-09-22 | B0-05 | NO-087 | Worker Celery thử để dấu cấp tiến trình (env, `captureWarnings`) | `54e2e91` |
| FIX-068 | 2026-09-22 | B0-01 | NO-092 | Dọn log cổng cũ hỏng thì `run.sh verify` thoát trước khi chạy cổng | `2debb52` |
| FIX-069 | 2026-09-22 | B0-05 | NO-093 | Test FIX-067 không chốt phần `captureWarnings` của fixture worker | `47efe53` |
| FIX-070 | 2026-09-22 | B0-08 | NO-102, NO-112 | Ảnh `web` dính CVE OpenSSL CRITICAL và CVE nginx rewrite/map | `b232603` (nhánh `fix/b0-08-web-openssl-cve`) |
| FIX-071 | 2026-09-22 | B0-01 | — | Bước 5 chạy toàn bộ ~2 460 test ở mọi lượt verify của nhánh worker | `f18546a`, `5f254f7` (nhánh `fix/b0-01-fast-verify`, **không gộp** — review REQUEST CHANGES, vòng sửa bỏ dở) |
| FIX-072 | 2026-09-22 | B0-01 | NO-101, NO-108 | Khởi động container verify ~77 s; mỗi worktree một volume `appback-work` | `e73af37` (nhánh `fix/b0-01-fast-verify-startup`, **không gộp**; NO-101/NO-108 đóng sau bằng FIX-083) |
| FIX-073 | 2026-09-23 | B0-06 | NO-127, NO-134 | `test_common__C10` không đạt được với route ghi được bảo vệ; bản mồi để thân giả lọt kho golden | `68c872e`, `e2b791d`, `950a791` (squash `d461ec8`) |
| FIX-074 | 2026-09-23 | B0-08 | NO-126 | `node` 26 trong ảnh verify thoát 127 thiếu `libatomic.so.1` | `07bd7c1` (squash `d461ec8`) |
| FIX-075 | 2026-09-23 | B0-01 | NO-128, NO-133 | `load_bind_rows` giữ backtick ở cột Khoá; `tools/charter.py` phủ nhánh 83,33 % | `77acfb8`, `45f7747` (squash `d461ec8`) |
| FIX-076 | 2026-09-23 | B0-06 | NO-129 | `test_common__C05` parametrize kép nên `case_gate` tách sai op | `8a61c20` (squash `d461ec8`) |
| FIX-077 | 2026-09-23 | B0-03 | NO-131 | `test_new_revision` dùng mã prompt thật `B2-01` làm dữ liệu mẫu | `165d9fc` (squash `d461ec8`) |
| FIX-078 | 2026-09-23 | B0-09 | NO-132 | Admin giả của H2 không có dòng `users`, route ghi có FK tới `users` → 500 | `e44e791` (squash `d461ec8`) |
| FIX-079 | 2026-09-23 | — | — | không dùng — việc "C10 lọt kho golden" (NO-134) làm dưới FIX-073 ở `950a791` (`spec-m-luot2.md:10`, thân `d461ec8`); không commit nào mang `Fix: FIX-079` | — |
| FIX-080 | 2026-09-23 | B0-05, B0-06, B1-01 | NO-148 | `mypy --strict` đỏ 6 lỗi trên `main` sau Dependabot bump `redis` 6.4 → 8.1 | `dfc9a8b`, `0d73ade`, `58b932c`, `cc57a74` (gộp `a26ee15`) |
| FIX-081 | 2026-09-23 | B0-06 | NO-163 | Test dò router khẳng định mỗi module đúng một router | `f15437c` (gộp cùng B7-01 `--no-ff` ở `591eaf6`) |
| FIX-082 | 2026-09-24 | B2-01 | — | Hai test fallback của cổng `view_parts` giả định "chưa module nào cài", đỏ khi B2-03 cài thật | nhánh `feature/b2-03-floors` |
| FIX-083 | 2026-09-24 | B0-01 | NO-101, NO-164, NO-103, NO-106, NO-108, NO-130 | Nợ cổng verify: `tr` của `gc`, marker `ci_integration`, hằng ảnh ghim trong test, ảnh/volume verify theo worktree, `concurrency` coverage | `531c690`, `7eaa0f9`, `ebe32cc`, `7ff240a` (nhánh `fix/debt-01-tooling`) |
| FIX-084 | 2026-09-24 | B0-09 | NO-051, NO-106, NO-110, NO-111, NO-113, NO-153 | Nợ CI: `VERIFY_OUT_DIR`, ảnh ghim chép tay ở `h2.py`, `types` của `pull_request`, test `job.sh`, `nginx -v` của ảnh `web`, dependabot major | `844fea3`, `a99fabb`, `86b31b9` (nhánh `fix/debt-01-tooling`) |
| FIX-085 | 2026-09-24 | B0-05 | NO-153 | `redis` khai không ràng buộc phiên bản | `5579b09` (nhánh `fix/debt-01-tooling`) |
| FIX-086 | 2026-09-24 | B0-08 | NO-094, NO-095, NO-096, NO-141, NO-162, NO-118, NO-117, NO-083, NO-084, NO-085, NO-104 | Nợ triển khai: log token, `minio/init.sh`, biến thư, scrape `9464`, cổng host `ci.yml`, upstream nginx khi đổi phiên bản, biến thừa của `ml` | `47cdab2`, `0e1e709`, `b77af7c` |
| FIX-087 | 2026-09-24 | B0-10 | NO-120, NO-117 | Hai nguồn `APPBACK_API_SWAP_SETTLE_S`; phản hồi hỏng khi `deploy.sh` đổi phiên bản | `f363377`, `f672677` |
| FIX-088 | 2026-09-24 | B0-03 | NO-140 | `on_after_commit` chạy callback khi savepoint nhả dù transaction ngoài rollback | `3286027` |
| FIX-089 | 2026-09-24 | B0-05 | NO-151, NO-152, NO-157, NO-085, NO-161 | RESP3 ngầm, `retry` không tường minh, `event_id_key` chưa phơi, `REDIS_CACHE_URL` bắt buộc, worker chưa có `/metrics` | `19648c3`, `917ce5a` |
| FIX-090 | 2026-09-24 | B0-06 | NO-097, NO-137, NO-159, NO-160 | `auth.py` chép `Role`, `_grant_everything` sai kiểu, `api_env` giữ cổng metric, metric RED theo đường thật | `301bf67`, `b25530b` |
| FIX-091 | 2026-09-24 | B5-01 | NO-085, NO-104, NO-161 | `ml` đọc `SECRET_KEY` chỉ để lấy `APP_ENV`; tải mô hình ghim không thử lại/không nguyên tử; `ml` chưa có `/metrics` | `f7abc9f`, `c2f3c72` |
| FIX-092 | 2026-09-24 | B4-01 | NO-156, NO-157 | Rò ba tài nguyên SSE khi `_finish` ném; bản sao `event_id_key` | `99bc366` |
| FIX-093 | 2026-09-24 | B1-03 | NO-149 | Lỗi thư vĩnh viễn bị nuốt khi token sau ném `TransientError` | `19fbed6` |
| FIX-094 | 2026-09-24 | B2-01 | NO-142, NO-136, NO-135 | `UPDATE` không khoá thứ tự, thiếu test hai session `_checked(None)`, `user_out()` không ký URL avatar | `672b44b` |
| FIX-095 | 2026-09-24 | B2-05a | NO-125 | Thiếu ca `render` ném `PdfiumError` → `FILE_CORRUPT` | `c3e32b7` |
| FIX-096 | 2026-09-24 | B4-01 | NO-155, NO-158 | Test hạn hết giữa hai lượt kéo không tất định; seed ít khoá hơn `BATCH` | `6caadb8` |
| FIX-097 | 2026-09-24 | F-01b | NO-154 | Luồng SSE 401 lặp không refresh trước lần nối kế | **không gộp** — review lượt 2 bác; bàn giao F-01b (nhánh tham khảo `fix/debt-01-fe-with-fix-097`) |
| FIX-098 | 2026-09-24 | F-02 | NO-099 | 26 `kind` hoạt động thiếu nhãn tiếng Việt | AppFront `831be4b` |
| FIX-099 | 2026-09-24 | F-01b | NO-086 | SSE thông báo mở `/api/notifications/stream` thay vì `/api/streams/notifications` | AppFront `885556d` |
| FIX-100 | 2026-09-24 | B0-08 | NO-174 | Ảnh `web` không build vì ảnh node ghim bỏ `corepack` | `792e98b` (nhánh `fix/b0-08-web-openssl-cve`) |
| FIX-101 | 2026-09-24 | B0-01 | NO-105 | Bước 8 nhánh tích hợp so với `openapi.json` không được commit; nay so với `docs/contracts/openapi.json` | `ad9ecab` (nhánh `fix/debt-01-tooling`) |
| FIX-102 | 2026-09-24 | B0-01 | NO-175 | Ảnh verify không ghim bản uv nên `run.sh lock` đổi định dạng `uv.lock` | `17774f7` (nhánh `fix/debt-01-tooling`) |
| FIX-103 | 2026-09-24 | B1-01 | NO-097 | `cast` thừa ở `apps/api/auth/sessions.py:585` khi `ROLES` có kiểu `tuple[Role, ...]` (hệ quả FIX-090) | `e2ebeda` |
| FIX-104 | 2026-09-24 | B0-08 | NO-177 | Tầng chạy Python 3.14 không đọc được venv 3.12 của tầng dựng | `3f2e14d`, `777f895` |
| FIX-105 | 2026-09-24 | B0-04 | NO-085 | `StorageSettings` đọc `CoreSettings` (cần `SECRET_KEY`, `PUBLIC_BASE_URL`) nên `ml` không dựng được kho S3 khi đã bỏ hai biến đó | `2739918` |
| FIX-107 | 2026-09-25 | B4-01 | — | Test mặc định của sổ luồng giả định "chưa có B2-04", đỏ khi B2-04 cài provider `upload_progress` thật | `e9ef485` (gộp `9d2c95b`, nhánh `feature/b2-04-drawing-uploads`) |
| FIX-108 | 2026-09-26 | B0-03 | — | Test seed chốt "repo chưa có seed", đỏ khi B3-02 thêm seed `spatial` thật | `1ada889` (gộp `15d1f53`, nhánh `feature/b3-02-spatial-read`) |
| FIX-109 | 2026-09-28 | B2-02 | — | Test dò sink mời chốt "chưa module nào có `invite_sinks.py`", đỏ khi B4-02 cài `ProjectInviteNotifier` thật | (nhánh `feature/b4-02-notifications`) |
| FIX-110 | 2026-09-28 | B4-01 | — | Test mặc định luồng thông báo giả định "chưa có B4-02", đỏ khi B4-02 cài provider `notifications` thật | (nhánh `feature/b4-02-notifications`) |
| FIX-117 | 2026-10-03 | B0-01 | NO-205, NO-325, NO-299, NO-324, NO-185, NO-190, NO-306 | DEBT-02 W1/C01: `run.sh` (gc trên Git Bash, đường AppFront mặc định, stdin của `shell`, junit bước 5, cache ruff/mypy) và volume `appback-work` | `e462a86`, `2e23c58`, `bfc9451`, `cd63213` (nhánh `fix/debt-02-w1`) |
| FIX-118 | 2026-10-03 | B0-08 | NO-325 | DEBT-02 W1/C01: đường AppFront mặc định của `deploy/docker/web-context.sh` | `de9a61d` (nhánh `fix/debt-02-w1`) |
| FIX-119 | 2026-10-03 | B3-05 | NO-325 | DEBT-02 W1/C01: đường AppFront trong `apps/api/rules/catalog.py` | `ef08b8f` (nhánh `fix/debt-02-w1`) |
| FIX-120 | 2026-10-03 | B0-09 | NO-269, NO-181, NO-183, NO-191, NO-180 | DEBT-02 W1/C02: `tools/ci/job.sh` (xdist, sàn nginx theo nhánh, `cd` khi nạp) và test của nó | `59242c1`, `dfdd92c`, `9150899` (nhánh `fix/debt-02-w1`) |
| FIX-121 | 2026-10-03 | B0-08 | NO-180 | DEBT-02 W1/C02: cổng host `api` của `deploy/compose/ci.yml` | không dùng — `deploy/compose/ci.yml` trên `main` đã không còn publish cổng host `api` (C02 `quyet-dinh.md` P-5) |
| FIX-122 | 2026-10-03 | B0-09 | NO-178, NO-182, NO-183, NO-330, NO-179 | DEBT-02 W1/C03: Dependabot, trigger `edited`, miễn trừ gitleaks, test ảnh ghim trùng | `b5a87ca`, `b395b97`, `07660d0`, `dfdd92c` (nhánh `fix/debt-02-w1`) |
| FIX-123 | 2026-10-03 | B0-01 | NO-184 | DEBT-02 W1/C03: `packages/testing` nhập `tools.pinned_images` (đảo chiều tầng) | `a857c9c`, `10091a5`, `f4339c5`, `c80faa5` (nhánh `fix/debt-02-w1`) |
| FIX-124 | 2026-10-03 | B0-02 | NO-184 | DEBT-02 W1/C03: nơi mới của hằng ảnh ghim trong `packages/core` (nếu phương án chốt chọn) | `90e360f`, `19fc9e4` (nhánh `fix/debt-02-w1`) |
| FIX-125 | 2026-10-03 | B0-01 | NO-294, NO-256, NO-257, NO-309 | DEBT-02 W1/C04: `case_gate` nhận case task J/U/M và task của `apps/ml` | `9181628`, `1a16885`, `5caf86f`, `8860fa8`, `cd63213` (nhánh `fix/debt-02-w1`) |
| FIX-126 | 2026-10-03 | B5-04 | NO-257, NO-256 | DEBT-02 W1/C04: khai lại `[[task]] text_read` trong `apps/ml/text/cases.toml` | `e8a6e77` (nhánh `fix/debt-02-w1`) |
| FIX-127 | 2026-10-03 | B0-05 | NO-309 | DEBT-02 W1/C04: sổ case `docs/contracts.toml` biết task `apps/ml` (người điều phối sửa) | không dùng — sổ task đã dò `apps.ml` từ `3b7ebf4`, gốc NO-309 nằm ở `tools/case_gate.py` (C04 `quyet-dinh.md` P-5, P-6; FIX-125) |
| FIX-128 | 2026-10-03 | B5-06a | NO-294 | DEBT-02 W1/C04: thêm lại `U01`, `U02`, `U04`, `U06` vào `require` của `apps/worker/pipeline_orchestrate/cases.toml` | `20cd8a6` (nhánh `fix/debt-02-w1`) |
| FIX-129 | 2026-10-03 | B5-02 | NO-256 | DEBT-02 W1/C04: khai `M01`, `M02` trong `apps/ml/walls/cases.toml` | `1ece360` (nhánh `fix/debt-02-w1`) |
| FIX-130 | 2026-10-03 | B5-03 | NO-256 | DEBT-02 W1/C04: khai `M01`–`M04` trong `apps/ml/objects/cases.toml` | `684e36d` (nhánh `fix/debt-02-w1`) |
| FIX-131 | 2026-10-03 | B6-04b | NO-256 | DEBT-02 W1/C04: khai `M01`–`M04`, `M06` trong `apps/ml/ml_eval/cases.toml` | `b7ffa1e`, `2d56d91`, `fbdb883` (nhánh `fix/debt-02-w1`) |
| FIX-132 | 2026-10-03 | B5-06c | NO-256 | DEBT-02 W1/C04: chú thích "chỉ J" lỗi thời trong `apps/worker/pipeline_steps/cases.toml` | `695c947` (nhánh `fix/debt-02-w1`) |
| FIX-133 | 2026-10-03 | B6-03a | NO-256 | DEBT-02 W1/C04: chú thích "chỉ J" lỗi thời trong `apps/worker/training_bridge/cases.toml` | `d270199` (nhánh `fix/debt-02-w1`) |
| FIX-134 | 2026-10-03 | B6-03b | NO-256 | DEBT-02 W1/C04: chú thích task trong `apps/ml/training_runner/cases.toml` (commit `dad3628` ghi nhầm trailer `Fix: FIX-125`) | `dad3628` (nhánh `fix/debt-02-w1`); commit `dad3628` mang nhầm trailer `Fix: FIX-125` |
| FIX-135 | 2026-10-03 | B0-03 | NO-184 | DEBT-02 W1/C03: `packages/db/migrate_check.py` chép tay ảnh `postgres:16-alpine` thay vì nhập nguồn ghim chung | `5c6ddcd`, `f723d98` (nhánh `fix/debt-02-w1`) |
| FIX-136 | 2026-10-04 | B0-10 | NO-182 | DEBT-02 W1 vòng sửa review: `notify.yml` theo dõi workflow `Commits` tách mới (hỏng trên `main` phải báo như CI) | `9738dab` (nhánh `fix/debt-02-w1`) |
| FIX-137 | 2026-10-04 | B6-04b | — | DEBT-02 W1 cổng 2 đỏ (luật 47): exporter giả của `apps/ml/training_yolo/tests/test_trainer.py` lọt sang `apps/ml/runtime/tests/test_export.py` (digest `"sha"`) — test phụ thuộc thứ tự | `8e5cc8f`, `a84f143` (nhánh `fix/debt-02-w1`) |
| FIX-138 | 2026-10-04 | B5-01 | — | DEBT-02 W1 cổng 2 đỏ: phần `apps/ml/runtime` của cùng lỗi nếu gốc nằm ở `export_pinned`/`export_yolo` (dùng khi phương án chốt đòi) | không dùng — gốc lỗi nằm hẳn ở `apps/ml/training_yolo/tests/test_trainer.py` (B6-04b, FIX-137); `apps/ml/runtime` không đổi |
| FIX-139 | 2026-10-04 | B0-01 | NO-306, NO-337 | DEBT-02 W2/C05b: cổng đầy đủ tin cache mypy ấm (NO-306); case_gate giữ bản tách tên test | `3e04636` (nhánh `fix/debt-02-w2-tools-layer`); vòng sửa review W2 lượt 1: `40f80b0` (nhánh `fix/debt-02-w2`) |
| FIX-140 | 2026-10-04 | B0-07 | NO-337 | DEBT-02 W2/C05b: bộ ghi golden nhập tầng công cụ `tools.case_gate` | `9d79a1f` (nhánh `fix/debt-02-w2-tools-layer`) |
| FIX-141 | 2026-10-04 | B0-02 | NO-337 | DEBT-02 W2/C05b: nguồn tách tên test case dùng chung ở tầng thấp | `f726b60` (nhánh `fix/debt-02-w2-tools-layer`) |
| FIX-142 | 2026-10-04 | B3-04 | NO-258 | DEBT-02 W2/C06: `test_versions_list_versions__cursor_of_another_floor` đỏ ~1/1024 | `a439587` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-143 | 2026-10-04 | B0-05 | NO-211 | DEBT-02 W2/C06: `apps/api/auth_recovery/tests/test_e2e.py` chạy lẻ: worker thật `Received unregistered task 'default.auth_recovery.send_token_mail'`, không có thư trong 15 s | `71266df`, `4114c13` (nhánh `fix/debt-02-w2-flakes`); vòng sửa review W2 lượt 1: `a4033ed` (nhánh `fix/debt-02-w2`) |
| FIX-144 | 2026-10-04 | B4-01 | NO-298 | DEBT-02 W2/C06: `test_open_streams_do_not_hold_postgres_connections` đỏ `assert 9 == 0` (`pool.checkedout()`) ở cổng `-n 6` máy thiếu RAM (B5-06b, sha 363ca00); chạy lẻ xanh | `4eebaa1`, `65969ff` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-145 | 2026-10-04 | B1-05 | NO-340 | DEBT-02 W2/C06: `import apps.api.auth_recovery.jobs  # noqa: F401` ở `test_e2e.py:14`, chỉ có để đăng ký task với worker thật | `199a28b` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-146 | 2026-10-04 | B0-03 | NO-341 | DEBT-02 W2/C06: `test_conventions_catch_bad_columns` đỏ khi chạy lặp trong cùng một tiến trình: `ArgumentError: Column object 'score' already assigned to Table 'bad'` | `0b432f4`, `6fbdd5a` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-147 | 2026-10-04 | B2-05b | NO-264 | DEBT-02 W2/C06: dòng nợ ghi đỏ ~1/4 lượt dưới `-n 6`; không tái hiện được (C06: 3 giả thuyết; 0/22 lượt cổng đầy đủ từ 09-29 + 3 junit) | `7aef2e8`, `2c4cd0c` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-148 | 2026-10-04 | B0-05 | NO-266 | DEBT-02 W2/C05: tham số parametrize sinh từ đồng hồ lúc thu thập (NO-266) + docstring R-01 thiếu | `971ae1f`, `959742d` (nhánh `fix/debt-02-w2-fixtures`) |
| FIX-149 | 2026-10-04 | B0-03 | NO-267, NO-277, NO-279 | DEBT-02 W2/C05: lượt dọn db_url mở kết nối mới mỗi test và đặt setval trước khi nạp seed | `bcb9572`, `15d1045` (nhánh `fix/debt-02-w2-fixtures`); vòng sửa review W2 lượt 1: `a505ff7` (nhánh `fix/debt-02-w2`) |
| FIX-150 | 2026-10-04 | B0-01 | NO-277, NO-281, NO-282 | DEBT-02 W2/C05: container dịch vụ mồ côi khi pytest bị giết cứng (NO-281), docker chưa khai trong nhóm dev (NO-282), chú thích O_APPEND | `9c1e4c3`, `89d40ab`, `1308068` (nhánh `fix/debt-02-w2-fixtures`); vòng sửa review W2 lượt 1: `b58a413` (nhánh `fix/debt-02-w2`) |
| FIX-154 | 2026-10-04 | B6-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test K36 pool một kết nối chưa gắn perf | `802da8b` — chỉ phần `apps/api/admin_ml_registry/tests/test_upload.py` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `e9269bb` (nhánh `fix/debt-02-w2`); commit `802da8b` cũng tạo `tools/tests/test_perf_marks.py` của B0-01 — phần đó thuộc FIX-163 (K27, review W2 #4); vòng sửa review W2 lượt 1: `d366339` (nhánh `fix/debt-02-w2`) |
| FIX-155 | 2026-10-04 | B0-06 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test broker chết chưa gắn perf | `9b048e6` (nhánh `fix/debt-02-w2-perf-marks`); vòng sửa review W2 lượt 1: `720ae99` (nhánh `fix/debt-02-w2`) |
| FIX-156 | 2026-10-04 | B2-04 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test K36/K28 chưa perf, tên khớp mẫu case | `1d28348` (nhánh `fix/debt-02-w2-perf-marks`); vòng sửa review W2 lượt 1: `58a7204` (nhánh `fix/debt-02-w2`) |
| FIX-157 | 2026-10-04 | B2-07 | NO-246 | DEBT-02 W2/C07: NO-246: test 1000x20 điểm khẳng định < 2 s chưa perf | `a64a1cc` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-158 | 2026-10-04 | B4-01 | NO-272 | DEBT-02 W2/C07: NO-272: 6 test S07 (mã case) khẳng định elapsed <= trần ở bước 5 (progress ×4 + notifications ×2, cùng chủ B4-01) | `4ab46e1`, `c0f355b` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-159 | 2026-10-04 | B7-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: wait_until 1,5 s sát TTL cache 1 s | `7720f0c` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `21c27fd` (nhánh `fix/debt-02-w2`) |
| FIX-160 | 2026-10-04 | B5-01 | NO-268 | DEBT-02 W2/C07: NO-268: test_export_onnx_deterministic 8–10 s kéo đuôi lượt loadfile | `3477820` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `c2fbb1a` (nhánh `fix/debt-02-w2`); vòng sửa review W2 lượt 1: `58e3c99` (nhánh `fix/debt-02-w2`) |
| FIX-161 | 2026-10-04 | B6-02 | NO-278 | DEBT-02 W2/C07: NO-278: pytestmark perf cấp tệp, số đo chưa in bằng logging | `e706ecf` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-162 | 2026-10-04 | B0-03 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: 3 test J09 (mã case) khẳng định elapsed ở bước 5 | `f1357ae`, `087741d`, `ebc7495`, `cfd7797` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `84fa737`, `4559b4d` (nhánh `fix/debt-02-w2`); vòng sửa review W2 lượt 1: `cf9c848` (nhánh `fix/debt-02-w2`) |
| FIX-163 | 2026-10-04 | B0-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: thiếu lưới chặn tái phát cho trần đồng hồ chưa perf | `802da8b` (phần tạo `tools/tests/test_perf_marks.py`, commit mang nhầm trailer `Prompt: B6-01`/`Fix: FIX-154`), `d84e7ad`, `9dbaa7a` (nhánh `fix/debt-02-w2-perf-marks`); vòng sửa review W2 lượt 1: `40f80b0` (nhánh `fix/debt-02-w2`) |
| FIX-167 | 2026-10-04 | B5-03 | NO-312 | DEBT-02 W2/C08: test M04 vá ML_DEVICE=cuda làm bẩn cache get_ml_settings của cả tiến trình | `b11a258` (nhánh `fix/debt-02-w2-cache`) |
| FIX-168 | 2026-10-04 | B6-03b | NO-312 | DEBT-02 W2/C08: support.py định nghĩa lại fixture ml_settings_cache trùng bản dùng chung (R-02, NO-312) | `44db1f4`, `19ca19f` (nhánh `fix/debt-02-w2-cache`) |
| FIX-169 | 2026-10-04 | B2-04 | NO-265 | DEBT-02 W2/C08: signer() ăn kho cache cấp tiến trình của test khác | `0534cc9` (nhánh `fix/debt-02-w2-cache`); vòng sửa review W2 lượt 1: `40fe21b` (nhánh `fix/debt-02-w2`) |
| FIX-170 | 2026-10-04 | B0-10 | NO-204 | DEBT-02 W2/C08: README kiểm ml.env dùng danh sách cấm hẹp (NO-204 nửa 2) | `4a45c6c` (nhánh `fix/debt-02-w2-cache`) |
| FIX-171 | 2026-10-04 | B5-01 | NO-322, NO-323 | DEBT-02 W2/C08: scan() bỏ tệp test nên import ultralytics trần tái sinh NO-322 | `df46a99` (nhánh `fix/debt-02-w2-cache`); vòng sửa review W2 lượt 1: `03916a8` (nhánh `fix/debt-02-w2`) |
| FIX-172 | 2026-10-04 | B2-03 | NO-265 | DEBT-02 W2/C08: test đếm SQL của `view_parts` chỉ xanh nhờ `_default_signer` do test khác làm ấm | `d3c8838` (nhánh `fix/debt-02-w2-cache`) |
| FIX-173 | 2026-10-04 | B5-06a | NO-218, NO-295, NO-339 | DEBT-02 W2/C14: đo RSS sai tiến trình (NO-339), J01 không qua đường gửi thật (NO-218), J06 khẳng định rỗng và dọn test | `fce473e`, `c2489b7` (nhánh `fix/debt-02-w2-pipeline`); vòng sửa review W2 lượt 1: `a97ed0a` (nhánh `fix/debt-02-w2`) |
| FIX-174 | 2026-10-04 | B5-06a | NO-339 | DEBT-02 W2/M cổng 1 đỏ (5b): con `spawn` đo `RUSAGE_SELF.ru_maxrss` mang theo RSS của cha pytest qua `execve` | `84ad46c` (nhánh `fix/debt-02-w2`); vòng sửa review W2 lượt 1: `eddb457` (nhánh `fix/debt-02-w2`) |
| FIX-175 | 2026-10-04 | B5-04 | NO-254, NO-255, NO-343 | DEBT-02 W3/C09: bộ đọc OCR sàn rộng 80 px hụt chữ kích thước, test width nói ngược, trần bộ dò chưa `perf` | `6fd8dbf`, `a5b83e0`, `71a44e6` (nhánh `fix/debt-02-w3-ml-text`) |
| FIX-176 | 2026-10-04 | B5-01 | NO-349 | DEBT-02 W3/C09: thước chữ kích thước chép ở ba test OCR → `packages/testing/ocr_metrics.py` | `acc5669`, `c0bde6f` (nhánh `fix/debt-02-w3-ml-text`) |
| FIX-177 | 2026-10-04 | B5-02 | NO-283, NO-284, NO-286, NO-287, NO-288 | DEBT-02 W3/C10: ranh giới nhập, ca Khung, mặt nạ cổ điển k chẵn/cửa sổ, vectorize cắt vách mảnh ngắn | `e832f16`, `72a1ffb` (nhánh `fix/debt-02-w3-vision-walls`) |
| FIX-178 | 2026-10-04 | B5-02 | NO-348 | DEBT-02 W3/C10: mô tả đường lùi cổ điển; cụm nét song song cách đều không còn thành tường | `6db3829`, `5e86272` (nhánh `fix/debt-02-w3-vision-walls`) |
| FIX-179 | 2026-10-04 | B6-04a | NO-316, NO-317, NO-318, NO-333 | DEBT-02 W3/C11: test GPU segformer chạy được, tách `export_and_check`, seed mỗi epoch, ctor kw_only, `HF_HUB_OFFLINE` | `a99e642` (nhánh `fix/debt-02-w3-segformer`) |
| FIX-180 | 2026-10-04 | B6-04b | NO-318 | DEBT-02 W3/C11: ctor `YoloTrainer` keyword-only, `family` cố định | `391aafb` (nhánh `fix/debt-02-w3-segformer`) |
| FIX-181 | 2026-10-04 | B6-04b | NO-319, NO-320, NO-321 | DEBT-02 W3/C12: metric YOLO gắn theo tên, kết quả sandbox có khung, epoch nhịp tim không lùi | `5b23e15`, `b67e448` (nhánh `fix/debt-02-w3-yolo-eval`) |
| FIX-182 | 2026-10-04 | B5-01 | NO-319 | DEBT-02 W3/C12: `_read_object` riêng tư bị `ml_eval` nhập → `read_model_object` | `6e6e32c`, `b0fbeb9` (nhánh `fix/debt-02-w3-yolo-eval`) |
| FIX-184 | 2026-10-04 | B0-05 | NO-270 | DEBT-02 W3/C05c: `with_db` cộng độ lệch vai vào DB của URL để nhiều tiến trình chung một Redis | `24f1d11`, `6bf27cf`, `0d023e7` (nhánh `fix/debt-02-w3-redis-shared`) |
| FIX-185 | 2026-10-04 | B0-01 | NO-270 | DEBT-02 W3/C05c: Redis test một bản mỗi chính sách cho cả lượt xdist, mỗi tiến trình một khối DB | `adc1cd9`, `ac93def`, `0274d6f`, `e3fd234`, `bc52e86` (nhánh `fix/debt-02-w3-redis-shared`) |
| FIX-186 | 2026-10-04 | B4-01 | NO-270 | DEBT-02 W3/C05c: S05 đếm kết nối Redis theo DB Streams thay vì cả máy chủ | `026c5d6` (nhánh `fix/debt-02-w3-redis-shared`) |
| FIX-189 | 2026-10-04 | B5-07 | NO-343 | DEBT-02 W3/C34: trần 2 s của `test_quality_replay_redis_hang_skips` gắn `perf` | `5c34815` (nhánh `fix/debt-02-w3-perf-docs`) |
| FIX-190 | 2026-10-04 | B5-06c | NO-343 | DEBT-02 W3/C34: trần 2 s của `test_sweep_survives_unreadable_queue` gắn `perf`, docstring theo BE-00 §12 | `1a9bd7d` (nhánh `fix/debt-02-w3-perf-docs`) |
| FIX-191 | 2026-10-04 | B2-06 | NO-343 | DEBT-02 W3/C34: trần 1 s của `test_build_all_assets_under_one_second` gắn `perf` | `8830c4e` (nhánh `fix/debt-02-w3-perf-docs`) |
| FIX-192 | 2026-10-04 | B6-03b | NO-343 | DEBT-02 W3/C34: trần 10 s của `test_run_training_job_cancel_while_waiting` gắn `perf` | `5983d8f` (nhánh `fix/debt-02-w3-perf-docs`) |
| FIX-193 | 2026-10-04 | B0-10 | NO-343 | DEBT-02 W3/C34: assert đồng hồ của test script triển khai → hạn `timeout` subprocess | `2c81e69` (nhánh `fix/debt-02-w3-perf-docs`) |
| FIX-194 | 2026-10-04 | B0-01 | NO-343 | DEBT-02 W3/C34: `SCANNED` của `test_perf_marks` thêm bảy tệp có trần đồng hồ tường | `036e9e7` (nhánh `fix/debt-02-w3-perf-docs`), `e52aab4` (nhánh `fix/debt-02-w3`) |
| FIX-200 | 2026-10-04 | B5-07 | NO-312 | DEBT-02 W2 vòng sửa review #14: `tests/e2e/test_pipeline_e2e.py` còn gọi tay `reset_ml_settings_cache()` dù fixture autouse `ml_settings_cache` đã dọn | `df7baa5` (nhánh `fix/debt-02-w2`) |
| FIX-201 | 2026-10-04 | B3-06 | NO-251, NO-252 | DEBT-02 W4/C13: luật 2 chỉ đổi tường sửa được khi trùng id, chỉ mục tường chéo tuyến tính theo chiều dài | `dfaa3cb` (nhánh `fix/debt-02-w4-rules-ai`) |
| FIX-202 | 2026-10-04 | B5-06b | NO-296 | DEBT-02 W4/C13: test giữ khoá 20.000 tường có trần 30 s thay vì chỉ in số | `9089a97` (nhánh `fix/debt-02-w4-rules-ai`) |
| FIX-203 | 2026-10-04 | B3-03 | NO-296 | DEBT-02 W4/C13: `_write_log` ghi nhật ký bằng `INSERT … SELECT FROM unnest` theo khúc 20.000 thay executemany | `3422b8f` (nhánh `fix/debt-02-w4-rules-ai`) |
| FIX-204 | 2026-10-04 | B0-04 | NO-263, NO-215, NO-217, NO-203 | DEBT-02 W4/C15a: khoá mẫu nhiều đoạn, `upload_chunk`/`upload_page_revision`/`dataset_version_prefix`, kho S3 không ký URL khi thiếu `CoreSettings` | `45b5ece`, `cc6d289`, `2a2c28d` (nhánh `fix/debt-02-w4-storage-keys`) |
| FIX-205 | 2026-10-04 | B2-04 | NO-215, NO-217 | DEBT-02 W4/C15a: khoá khúc/trang qua `packages/storage/keys`, trang ký inline | `3bce219` (nhánh `fix/debt-02-w4-storage-keys`) |
| FIX-206 | 2026-10-04 | B6-02 | NO-263 | DEBT-02 W4/C15a: writer/tasks dataset dựng khoá qua `dataset_object`/`dataset_version_prefix` | `fd2d73e`, `5b5b182`, `592459a`, `bbdd004` (nhánh `fix/debt-02-w4-storage-keys`) |
| FIX-207 | 2026-10-04 | B6-03b | NO-263 | DEBT-02 W4/C15a: `sample_key` của runner dựng khoá qua `dataset_object` | `d3ee0cd` (nhánh `fix/debt-02-w4-storage-keys`) |
| FIX-209 | 2026-10-04 | B0-04 | NO-225, NO-230 | DEBT-02 W4/C15b: `read_all_capped`, `delete` S3 đổi 4xx thành `INTERNAL`, settings từ chối khoá mẫu và không lộ endpoint | `d9ee089`, `5e3968b`, `63e26fc`, `5e69146` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-210 | 2026-10-04 | B2-05b | NO-225, NO-230 | DEBT-02 W4/C15b: quality đọc trang qua `read_all_capped`, sửa docstring `_discard_orphan` | `2a93f90` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-211 | 2026-10-04 | B2-04 | NO-297 | DEBT-02 W4/C15b: công khai `restore_window_elapsed` nửa mở làm luật cửa sổ khôi phục duy nhất | `e406a51`, `3c885da`, `7454791` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-212 | 2026-10-04 | B5-01 | NO-225 | DEBT-02 W4/C15b: `read_model_object`, `_read_page` gọi `read_all_capped` | `01499b4` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-213 | 2026-10-04 | B5-06a | NO-225 | DEBT-02 W4/C15b: `preprocess._read_capped` gọi `read_all_capped` | `4bc7e34` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-214 | 2026-10-04 | B5-05 | NO-225 | DEBT-02 W4/C15b: `_read_artifact` là một lời gọi `read_all_capped` | `48ad5e6` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-215 | 2026-10-04 | B0-10 | NO-327, NO-332 | DEBT-02 W4/C16: backup chỉ chủ đọc được (umask 077), secret cảnh báo từ Environment `alerts` | `7fec0e1`, `6ecb19d` (nhánh `fix/debt-02-w4-security`) |
| FIX-216 | 2026-10-04 | B0-02 | NO-328, NO-329 | DEBT-02 W4/C16: từ chối `SECRET_KEY` mẫu ngoài dev, che mật khẩu trong URL của log | `5ee1710` (nhánh `fix/debt-02-w4-security`) |
| FIX-217 | 2026-10-04 | B6-03b | NO-326 | DEBT-02 W4/C16: tiến trình con huấn luyện nhận env theo danh sách cho phép | `206d3a0`, `3083920` (nhánh `fix/debt-02-w4-security`) |
| FIX-218 | 2026-10-04 | B0-08 | NO-331 | DEBT-02 W4/C16: thân 413/503 nginx mang bộ header nền (+ HSTS) | `aded39f`, `90ff075` (nhánh `fix/debt-02-w4-security`) |
| FIX-219 | 2026-10-04 | B0-03 | — (cùng họ SEC-041/NO-328) | DEBT-02 W4/C16: `DatabaseSettings` từ chối `DATABASE_URL` mẫu change-me ngoài dev, không in lại DSN | `ea01b17` (nhánh `fix/debt-02-w4-security`) |
| FIX-220 | 2026-10-04 | B0-05 | NO-329 | DEBT-02 W4/C16: lỗi `MessagingSettings` che mật khẩu URL Redis | `14623ee` (nhánh `fix/debt-02-w4-security`) |
| FIX-221 | 2026-10-04 | B5-01 | NO-326 | DEBT-02 W4/C16: hàm lọc env chung `allowlisted_env` ở `apps/ml/runtime/child_env.py` | `c91e1e7` (nhánh `fix/debt-02-w4-security`) |
| FIX-222 | 2026-10-04 | B0-01 | NO-350 | DEBT-02 W4/C36: `unit_of` coi `deploy/`, `tests/` là đơn vị để test perf của chúng vào bước 5b | `d052372`, `46f5711`, `5135c04` (nhánh `fix/debt-02-w4-gate-tools`) |
| FIX-223 | 2026-10-04 | B0-01 | NO-268 | DEBT-02 W4/C36: plugin xếp tệp OCR nặng lên đầu `--dist loadfile`, rồi bỏ vì A/B không nhanh hơn | `0a28980`, `3e6ddc2` (nhánh `fix/debt-02-w4-gate-tools`) |
| FIX-225 | 2026-10-04 | B0-08 | NO-197, NO-198, NO-199, NO-201, NO-212 | DEBT-02 W5/C17: access log không ghi token lỗi tiền-location, `init.sh` hỏng khi `mc` lỗi, target worker, Mailpit tắt rDNS | `4a2465b`, `5ab72a2`, `1d97706` (nhánh `fix/debt-02-w5-deploy`) |
| FIX-226 | 2026-10-04 | B0-10 | NO-189, NO-196, NO-200, NO-242 | DEBT-02 W5/C17: script triển khai/backup không cần `python3` host, README đủ biến SMTP, publish thư viện sau migrate, drill chọn kho | `b9a1984`, `b4b065f`, `144e3f6`, `f04ccda` (nhánh `fix/debt-02-w5-deploy`) |
| FIX-230 | 2026-10-04 | B5-01 | NO-308, NO-314, NO-285 | DEBT-02 W5/C18: một lõi khoá giữ chỗ `lease.py` cho GPU và slot huấn luyện, hằng/mã lỗi một nguồn (`error_codes`) | `94e3bd8`, `7ba91ad`, `e5025d8` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-231 | 2026-10-04 | B6-03b | NO-305, NO-308, NO-313, NO-314 | DEBT-02 W5/C18: runner dùng khoá job của payloads và lõi khoá chung | `07c0dde`, `20fc1ce` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-232 | 2026-10-04 | B5-02 | NO-285 | DEBT-02 W5/C18: `walls/tasks.py` nhập `MODEL_VERSION_FAMILY_MISMATCH` từ runtime | `4267320` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-233 | 2026-10-04 | B5-04 | NO-285 | DEBT-02 W5/C18: `text/tasks.py` nhập `MODEL_VERSION_FAMILY_MISMATCH` từ runtime | `41f7f2e` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-234 | 2026-10-04 | B0-02 | NO-168, NO-169, NO-213 | DEBT-02 W5/C19: `new_ulid`, `clean_text`, `first_forbidden_char` ở `packages/core` | `0440e0b`, `e5403d2`, `cea0b30` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-235 | 2026-10-04 | B1-04 | NO-168, NO-169 | DEBT-02 W5/C19: `me` dùng `new_ulid` và `clean_text` của core | `a7e6626` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-236 | 2026-10-04 | B1-03 | NO-169 | DEBT-02 W5/C19: `auth_recovery` kiểm `fullName` bằng `clean_text` của core | `d9bfd55` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-237 | 2026-10-04 | B2-03 | NO-168, NO-169 | DEBT-02 W5/C19: `floors` dùng `new_ulid` và `clean_text` của core | `952432f` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-238 | 2026-10-04 | B2-04 | NO-168, NO-169 | DEBT-02 W5/C19: `drawings` dùng `new_ulid` và `clean_text` của core | `48cab15` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-239 | 2026-10-04 | B2-01 | NO-213, NO-169 | DEBT-02 W5/C19: `projects.clean_text` là vỏ mỏng quanh `clean_text` của core | `16b9190` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-240 | 2026-10-04 | B2-02 | NO-213 | DEBT-02 W5/C19: ghi chú `project_settings` dùng `clean_text` của core | `4819631` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-241 | 2026-10-04 | B0-06 | NO-237, NO-236 | DEBT-02 W5/C20: OpenAPI khai mọi tham số đường, `document()` từ chối component trùng tên `apps__…` | `99b8236` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-242 | 2026-10-04 | B0-06 | NO-248 | DEBT-02 W5/C20: `field` của 422 bỏ tag nhánh union, tag lạ báo tên discriminator (đổi dây) | `e2ca37a` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-243 | 2026-10-04 | B0-05 | NO-187 | DEBT-02 W5/C20: vai Streams không thử lại hết giờ đọc, chặn XADD gửi hai lần | `e980edc` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-244 | 2026-10-04 | B2-01 | NO-236 | DEBT-02 W5/C20: bí danh `FloorName` của projects đổi thành `FloorDraftName` | `d37e82a` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-245 | 2026-10-04 | B0-06 | — (vết C20b) | DEBT-02 W5/C20: `_abort` chạy hết mọi bước dọn kể cả khi rollback ném, không để claim idempotency mồ côi | `49bae53` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-246 | 2026-10-04 | B6-04b | NO-326 | DEBT-02 W4/C16: `ml_eval` dùng hàm lọc env chung `allowlisted_env` | `bfde446` (nhánh `fix/debt-02-w4-security`) |
| FIX-247 | 2026-10-04 | B5-03 | NO-285 | DEBT-02 W5/C18: `objects/tasks.py` nhập `MODEL_VERSION_FAMILY_MISMATCH` từ runtime | `9dc704f` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-248 | 2026-10-04 | B1-04 | NO-170, NO-171 | DEBT-02 W6/C21: `avatar.py` bỏ gán cờ Pillow toàn cục, `exif_transpose(in_place=True)`, chỉ `convert` khi mode ≠ RGB/RGBA | `c498aad` (nhánh `fix/debt-02-w6-me-avatar`), `7e81312` (nhánh `fix/debt-02-w6-me-avatar`) |
| FIX-249 | 2026-10-04 | B2-01 | NO-194 | DEBT-02 W6/C21: `_storage_of` đọc thẳng `app.state.storage` thay vì nuốt thiếu, thêm test route `avatarUrl` | `52f03d7` (nhánh `fix/debt-02-w6-me-avatar`) |
| FIX-253 | 2026-10-04 | B2-01 | NO-193, NO-195 | DEBT-02 W6/C22: guard lô rỗng `count_projects_of_users`, test hai session `touch_projects`, `test_wire` dùng `local_storage` | `c9b7341` (nhánh `fix/debt-02-w6-users-projects`) |
| FIX-254 | 2026-10-04 | B1-03 | NO-195 | DEBT-02 W6/C22: log cô lập từng token đổi tên `token_mail_isolated`, `token_mail_failed` còn một bản ghi mỗi lô | `5428fa1` (nhánh `fix/debt-02-w6-users-projects`), `475b1a3` (nhánh `fix/debt-02-w6-users-projects`) |
| FIX-255 | 2026-10-04 | B2-02 | NO-214 | DEBT-02 W6/C22: `confidenceThreshold`/`scaleMmPerPx` kiểm dải trên số thô trước khi làm tròn, chuẩn hoá `-0.000` | `ad5569d` (nhánh `fix/debt-02-w6-users-projects`) |
| FIX-259 | 2026-10-04 | B2-03 | NO-172, NO-173, NO-223 | DEBT-02 W6/C23: docstring floors hết "chưa hợp nhất", thêm `floor_outs_with_pk` trả pk cạnh `FloorOut` | `ccf67ea` (nhánh `fix/debt-02-w6-floors-drawings`) |
| FIX-260 | 2026-10-04 | B2-04 | NO-219 | DEBT-02 W6/C23: bỏ nhánh chết `else b""`, fixture `latest_client` thừa; migration b2_04 đủ `Create Date` | `fad542c` (nhánh `fix/debt-02-w6-floors-drawings`), `3cba227` (nhánh `fix/debt-02-w6-floors-drawings`) |
| FIX-261 | 2026-10-04 | B3-02 | NO-223 | DEBT-02 W6/C23: N15 lấy pk từ `floor_outs_with_pk`, đọc bảng floors một lần | `45f1dda` (nhánh `fix/debt-02-w6-floors-drawings`) |
| FIX-262 | 2026-10-04 | B2-04 | NO-219 | DEBT-02 W6/C23: factory drawings nhập bảng đuôi tệp từ `uploads` thay vì chép | `9ca4ee4` (nhánh `fix/debt-02-w6-floors-drawings`) |
| FIX-264 | 2026-10-04 | B3-04 | NO-244, NO-245 | DEBT-02 W6/C24: N19 bỏ `count=1` sai nghĩa, lượt chụp bỏ `SELECT floors` thừa | `9276a03` (nhánh `fix/debt-02-w6-versions-rules`) |
| FIX-265 | 2026-10-04 | B3-05 | NO-250 | DEBT-02 W6/C24: lọc trường override lạ theo `RuleConfigOverrideOut.model_fields`, hết 500 ở N21/N22 | `0dc2edd` (nhánh `fix/debt-02-w6-versions-rules`) |
| FIX-266 | 2026-10-04 | B0-06 | NO-244 | DEBT-02 W6/C24: 422 khoá idempotency bỏ `count=1` sai nghĩa (R-19) | `1761a0f` (nhánh `fix/debt-02-w6-versions-rules`) |
| FIX-268 | 2026-10-04 | B4-02 | NO-253 | DEBT-02 W7/C25: notifications: `one_or_none` sau ON CONFLICT, trim chỉ xếp hạng người vượt trần, openapi #20 giữ ràng buộc | `af4a2c9` (nhánh `fix/debt-02-w7-notify-library`), `d4f5e62` (nhánh `fix/debt-02-w7-notify-library`), `b56c966` (nhánh `fix/debt-02-w7-notify-library`) |
| FIX-269 | 2026-10-04 | B2-06 | NO-239, NO-240 | DEBT-02 W7/C25: `_same_shas` chỉ so `model_sha256` (bỏ lệch zlib); bộ chặn nhập đủ 5 gói | `15f8cc2` (nhánh `fix/debt-02-w7-notify-library`), `4f9e037` (nhánh `fix/debt-02-w7-notify-library`) |
| FIX-273 | 2026-10-04 | B6-02 | NO-275, NO-276 | DEBT-02 W7/C26: CHECK chiều ngược `failure_code_failed` + backfill; 45 hàm test có docstring | `1ee1ae7` (nhánh `fix/debt-02-w7-ml-admin`) |
| FIX-274 | 2026-10-04 | B6-01 | NO-260, NO-261, NO-262 | DEBT-02 W7/C26: requeue khoá lô một lần, `register_trained_version` dưới 50 dòng, docstring closure test | `ddcefc9` (nhánh `fix/debt-02-w7-ml-admin`) |
| FIX-275 | 2026-10-04 | B6-03a | NO-307 | DEBT-02 W7/C26: test nhánh `rowcount == 0` của `_purge_one` (lịch đối thủ thắng dấu) | `3f2b213` (nhánh `fix/debt-02-w7-ml-admin`) |
| FIX-280 | 2026-10-04 | B2-05b | NO-231 | DEBT-02 W7/C27: assert đúng `len(names) == workers` sau reset pool | `3f01fc2` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-281 | 2026-10-04 | B5-03 | NO-289 | DEBT-02 W7/C27: ba Nit: docstring `_union_round`, bỏ `time.sleep`, lý do `type: ignore` | `f4d30fd` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-282 | 2026-10-04 | B5-05 | NO-291, NO-293 | DEBT-02 W7/C27: một vỏ bọc `build_layer` chung ở `tests/helpers.py`; bỏ `raw.size and`, sửa docstring `_checked` | `646f828` (nhánh `fix/debt-02-w7-test-quality`), `21b8e43` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-283 | 2026-10-04 | B5-06b | NO-300 | DEBT-02 W7/C27: helper test `pipeline_persist` về một bản, `fail_step` chờ after-commit | `6c772d5` (nhánh `fix/debt-02-w7-test-quality`), `bea761e` (nhánh `fix/debt-02-w7-test-quality`), `20f0a6b` (nhánh `fix/debt-02-w7-test-quality`), `d504083` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-284 | 2026-10-04 | B5-06c | NO-303, NO-301 | DEBT-02 W7/C27: test phân biệt `_IDLE_MARK`/`sweep_run_fresh`, dùng `queued_tasks` chung | `ed967cd` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-285 | 2026-10-04 | B5-07 | NO-304 | DEBT-02 W7/C27: docstring test sai sự thật, `_assert_pipeline_layer` keyword-only, `ProcessLocal.override` thay `_factory` | `9efc7b6` (nhánh `fix/debt-02-w7-test-quality`), `ce69412` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-286 | 2026-10-04 | B0-05 | NO-315 | DEBT-02 W7/C27: fixture `restored_task_ledger` chặn rò sổ `_TASKS` của test hồi quy FIX-115 | `fc6f890` (nhánh `fix/debt-02-w7-test-quality`), `da63ccc` (nhánh `fix/debt-02-w7-test-quality`), `c8d224e` (nhánh `fix/debt-02-w7-test-quality`), `e27bcea` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-287 | 2026-10-04 | B0-05 | NO-301 | DEBT-02 W7/C27: fixture messaging thêm `queued_tasks(client, queue)` trả tên task | `7ee8c97` (nhánh `fix/debt-02-w7-test-quality`), `8d47da8` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-288 | 2026-10-04 | B4-01 | NO-192 | DEBT-02 W7/C27: test `_pull` của fixture SSE khi app thoát không gửi thân | `fe3a06d` (nhánh `fix/debt-02-w7-test-quality`), `26014d1` (nhánh `fix/debt-02-w7-test-quality`), `9e97f1a` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-289 | 2026-10-04 | B3-01 | NO-220 | DEBT-02 W7/C27: hạ `document_to_json`/`layer_counts`/`entity_ids` xuống `packages/domain/spatial/document.py` | `9b0d0fd` (nhánh `fix/debt-02-w7-test-quality`), `55d92cd` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-290 | 2026-10-04 | B3-02 | NO-220 | DEBT-02 W7/C27: seed và codec/counts gọi helper miền chung thay vì bản sao | `73ddd39` (nhánh `fix/debt-02-w7-test-quality`), `97393a3` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-291 | 2026-10-04 | B0-05 | NO-304 | DEBT-02 W7/C27b: `ProcessLocal.override(factory)` cho test, trả factory cũ kể cả khi thân ném | `4e82c81`, `8231b00` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-292 | 2026-10-04 | B0-03 | NO-249, NO-235 | DEBT-02 W7/C28: mako in `down_revision` tuple, `migrate_check` hạ head merge theo cha thứ nhất; luật `db_session` rollback | `374c7ab` (nhánh `fix/debt-02-w7-db`) |
| FIX-293 | 2026-10-04 | B0-01 | NO-249 | DEBT-02 W7/C28: test `merge-heads` dùng template revision thật | `c672ed3` (nhánh `fix/debt-02-w7-db`) |
| FIX-295 | 2026-10-04 | B5-06b | NO-297 | DEBT-02 W4/C15b: `_read_built` gọi `read_all_capped`, `_floor_state` gọi `restore_window_elapsed` | `7c6a23e` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-296 | 2026-10-04 | B6-03b | — (R-16; mẫu NO-225) | DEBT-02 W4/C15b: dataset runner giữ kho 503 là lỗi thử lại được, manifest đọc có trần | `eab74bf` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-297 | 2026-10-04 | B2-03 | NO-297 | DEBT-02 W4/C15b: khôi phục tầng dùng biên cửa sổ chung `restore_window_elapsed` | `2a37034` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-298 | 2026-10-04 | B3-02 | NO-297 | DEBT-02 W4/C15b: nhận lại entity id dùng biên cửa sổ chung | `6bc4e7a` (nhánh `fix/debt-02-w4-storage-read`) |
| FIX-299 | 2026-10-04 | B6-04a | — (vết C18b, họ NO-285) | DEBT-02 W5/C18: `training_segformer/errors.py` nhập mã từ `runtime.error_codes`/`training_runner.errors` | `bc8b1e3` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-300 | 2026-10-04 | B6-04b | — (vết C18b, họ NO-285) | DEBT-02 W5/C18: `ml_eval/sandbox.py` nhập `MODEL_FORMAT_UNSUPPORTED` từ `runtime.error_codes` | `bd0ee00` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-301 | 2026-10-04 | B7-02 | — (vết C18b) | DEBT-02 W5/C18: ASVS B-20 trỏ lại dẫn chứng sang `lease.py`/`gpu.py` | `d9d67f7` (nhánh `fix/debt-02-w5-ml-runtime`) |
| FIX-302 | 2026-10-04 | B0-03 | NO-247 | DEBT-02 W5/C19: `lock_project_scope` dùng chung ở `packages/db/locks.py` | `1884b15` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-303 | 2026-10-04 | B0-06 | NO-188 | DEBT-02 W5/C19: `parse_role` công khai là bộ phân tích vai duy nhất | `2a14b64`, `238f149` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-304 | 2026-10-04 | B1-01 | NO-188 | DEBT-02 W5/C19: `models/auth.py` nhập `ROLES` của domain, `sessions.py` dùng `parse_role` | `12e0178`, `13a4e2c` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-305 | 2026-10-04 | B2-07 | NO-247, NO-169 | DEBT-02 W5/C19: measurements/templates khoá qua `packages.db.locks`, nhãn đo dùng `clean_text` | `9412e89` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-306 | 2026-10-04 | B3-01 | NO-169 | DEBT-02 W5/C19: `domain/spatial/model.py` lấy ký tự cấm từ `first_forbidden_char` của core | `619fd07` (nhánh `fix/debt-02-w5-core-text-ids`) |
| FIX-307 | 2026-10-04 | B2-04 | NO-187 | DEBT-02 W5/C20: khung `Progress` phát bằng `publish_once`, mất phản hồi không ghi khung thứ hai | `901a4d1` (nhánh `fix/debt-02-w5-api-core`) |
| FIX-308 | 2026-10-04 | B5-01 | NO-061 | DEBT-02 W8/C29: ghim bộ công cụ xuất YOLO (`YOLO_EXPORT_TOOLCHAIN`) và test khớp `uv.lock` | `0401f11` (nhánh `fix/debt-02-w8-ml-pins`) |
| FIX-310 | 2026-10-04 | người điều phối | NO-176 | DEBT-02 W8/C32: dựng lại mục lục và khối FIX-071…081 của sổ FIX | `c6d25b1` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-311 | 2026-10-04 | B7-02 | NO-336 | DEBT-02 W8/C32: năm Nit review kiểm toán bảo mật; trỏ lại dẫn chiếu `file:dòng` sau DEBT-02 | `44435a9` (nhánh `fix/debt-02-w8-charter-docs`), `55ec55b` (nhánh `fix/debt-02-w8-charter-docs`), `c6ec3af` (nhánh `fix/debt-02-w8-charter-docs`), `99646c4` (nhánh `fix/debt-02-tich-hop`) |
| FIX-312 | 2026-10-04 | dieu-phoi | NO-232, NO-233 | DEBT-02 W8/C32: R-33b theo sở hữu, đóng bốn chỗ hở R-33b/merge-review (bản nháp chờ duyệt) | `70eaccf` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-313 | 2026-10-04 | người điều phối | NO-335, NO-345 | DEBT-02 W8/C32: nợ hiến chương của B7-02, tách cận trên `perf` khỏi hạn chờ rộng (bản nháp chờ duyệt) | `10364ed` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-314 | 2026-10-05 | B0-08 | NO-335 | DEBT-02 W8/C32c: nginx `limit_conn` 30 luồng SSE mỗi IP ở `/api/streams/`, quá → 429 `RATE_LIMITED` | `f5eb942` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-315 | 2026-10-05 | B0-01 | NO-335 | DEBT-02 W8/C32c: `case_gate` đòi C11 cho N14, `_FIXED_EXTRA` khoá bằng test đối chiếu CASE.md | `ffb507d` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-316 | 2026-10-05 | B1-04 | NO-335 | DEBT-02 W8/C32c: test hạn mức avatar đổi tên `test_me_replace_avatar__C11` | `bab36ff`, `f6d0f68` (nhánh `fix/debt-02-w8-charter-docs`) |
| FIX-317 | 2026-10-04 | B0-01 | NO-352 | DEBT-02 W8/C37: hợp đồng `.importlinter` `api-cli-no-web` phủ `apps.api.*.cli` | `bf8aeab` (nhánh `fix/debt-02-w8-tooling`), `d69af81` (nhánh `fix/debt-02-w8-tooling`), `7fb6e30` (nhánh `fix/debt-02-w9-integ-fix`) |
| FIX-318 | 2026-10-04 | B0-01 | NO-353 | DEBT-02 W8/C37: hằng chung `packages/testing/boundary.py` + test quét bản chép tuple | `c3611b3` (nhánh `fix/debt-02-w8-tooling`) |
| FIX-319 | 2026-10-04 | nhiều chủ (24) | NO-353 | DEBT-02 W8/C37: test ranh giới từng module dùng hằng chung; dọn audit C37b | `de8b055`, `abc2242`, `b3c6282`, `38a116f`, `3c10a0f`, `04390f1`, `11abb4a`, `49af5f5`, `5b4c723`, `26680db`, `1840731`, `93e55f9`, `4f22904`, `fa217b2`, `1882c58`, `f88767a`, `da196d3`, `36c4b61`, `1710fbf`, `5445580`, `3425e8d`, `52fd33d`, `948f4e4`, `da3da85`, `835fd73`, `f5cd13f`, `daea0cb`, `0ba7a01`, `50dd55f`, `ad1f704`, `74eb1d3`, `5e17528`, `5210498` (nhánh `fix/debt-02-w8-tooling`) |
| FIX-320 | 2026-10-04 | B0-01 | NO-222 | DEBT-02 W8/C37: `case_gate` miễn cảnh báo ba op hạ tầng (`INFRA_OPS`); so xfail bằng `endswith` | `1f86393` (nhánh `fix/debt-02-w8-tooling`), `a7e3019` (nhánh `fix/debt-02-w8-tooling`) |
| FIX-321 | 2026-10-04 | B5-06a | NO-304 | DEBT-02 W7/C27b: smoke `start` của orchestrate dùng `ProcessLocal.override` thay monkeypatch `_factory` | `5599bec` (nhánh `fix/debt-02-w7-test-quality`) |
| FIX-322 | 2026-10-04 | B0-06 | NO-351 | DEBT-02 W9/C40: guard W21 dùng `param_convertors`, gắn cả route khai tham số đường qua dependency | `ac706aa` (nhánh `fix/debt-02-w9-api-guard`) |
| FIX-323 | 2026-10-04 | B1-05 | NO-206 | DEBT-02 W9/C40: admin duy nhất tự sửa mình nhận `USER_LAST_ADMIN`, bỏ `forbid_last_admin` chết | `2d06bc1` (nhánh `fix/debt-02-w9-api-guard`) |
| FIX-324 | 2026-10-04 | B2-07 | NO-351 | DEBT-02 W9/C40: test #29 kỳ vọng `PATH_BODY_MISMATCH` cho `projectId` lệch đường (hệ quả FIX-322) | `375d924` (nhánh `fix/debt-02-w9-api-guard`) |
| FIX-325 | 2026-10-04 | B1-03 | NO-150 | DEBT-02 W9/C41: `MAIL_REJECTED` ghi `failed_at`/`failure_code` thay vì `sent_at` | `df36de5` (nhánh `fix/debt-02-w9-tokens`) |
| FIX-326 | 2026-10-04 | B1-03 | NO-150 | DEBT-02 W9/C41: `latest_invitations` bỏ lời mời bị từ chối vĩnh viễn | `6f57c2e` (nhánh `fix/debt-02-w9-tokens`), `1de44b5` (nhánh `fix/debt-02-w9-tokens`), `c2425bc` (nhánh `fix/debt-02-w9-tokens`) |
| FIX-327 | 2026-10-04 | B0-04 | NO-207 | DEBT-02 W9/C42: `ObjectStorage.signed_urls` ký URL theo lô, S3 presign một luồng ngoài vòng sự kiện | `afda4ad` (nhánh `fix/debt-02-w9-sign-batch`), `ad0df9d` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-328 | 2026-10-04 | B1-04 | NO-207 | DEBT-02 W9/C42: ảnh đại diện ký theo lô | `2b29018` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-329 | 2026-10-04 | B1-05 | NO-207 | DEBT-02 W9/C42: danh sách người dùng admin ký ảnh đại diện theo lô | `e609547` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-330 | 2026-10-04 | B2-01 | NO-207 | DEBT-02 W9/C42: ảnh đại diện thành viên dự án ký theo lô | `36cc8c3` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-331 | 2026-10-04 | B2-04 | NO-207 | DEBT-02 W9/C42: URL bản vẽ ký theo lô qua `drawing_urls` | `91f744f` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-332 | 2026-10-04 | B2-06 | NO-207 | DEBT-02 W9/C42: URL mục thư viện ký theo lô | `719a7c0` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-333 | 2026-10-04 | B6-02 | NO-207 | DEBT-02 W9/C42: wrapper storage của test worker datasets uỷ `signed_urls` | `393c82c` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-334 | 2026-10-04 | B0-03 | NO-107 | DEBT-02 W9/C43: seed admin cố định `SEED_ADMIN_ID` cho dev/test/ci | `9f8813f` (nhánh `fix/debt-02-w9-db-seed`), `9db28f2` (nhánh `fix/debt-02-w9-db-seed`), `4a5002a` (nhánh `fix/debt-02-w9-db-seed`) |
| FIX-335 | 2026-10-04 | B0-09 | NO-107 | DEBT-02 W9/C43: H2 dùng id admin seed thay vì dựng admin ngẫu nhiên | `1400c01` (nhánh `fix/debt-02-w9-db-seed`), `d7958c5` (nhánh `fix/debt-02-w9-db-seed`) |
| FIX-336 | 2026-10-04 | B2-07 | NO-248 | DEBT-02 W9/C46: C02[unknown-kind] mong `field = "objectKind"` theo hành vi mới của `field_of` | `60ef453` (nhánh `fix/debt-02-w9-integ-fix`) |
| FIX-337 | 2026-10-04 | B2-05b | NO-207 | DEBT-02 W9/C42: `read_view` ký URL mọi tầng theo một lô | `4614a52` (nhánh `fix/debt-02-w9-sign-batch`) |
| FIX-338 | 2026-10-05 | B7-02 | NO-334 | DEBT-02 W10/C47: `docs/security` ghi thăm dò sống 18 mục (16 đạt, SEC-044/063), bỏ dòng "kiểm toán chưa đủ", đóng tồn dư B-22 | `5bb71c8`, `e2a9bb9` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-339 | 2026-10-04 | B0-10 | NO-334 | DEBT-02 W10/C47: `backup.sh` production thiếu `BACKUP_AGE_RECIPIENT` thoát 1 trước `pg_dump` (C-18, SEC-044) | `8aaf38f` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-340 | 2026-10-05 | B0-08 | NO-334 | DEBT-02 W10/C47: `ml.Dockerfile` chép thêm `packages/observability`, test COPY khép kín theo import | `486cd80` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-341 | 2026-10-05 | B0-10 | NO-334 | DEBT-02 W10/C47: `drill.sh` `snapshot()` đọc danh sách từ fd 3, hết so thiếu bảng/đối tượng | `554bbca` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-343 | 2026-10-04 | B6-02b | NO-334 | DEBT-02 W10/C47: hằng `SOURCE_LICENSE` CC BY-NC 4.0, in ở mọi báo cáo nhập CubiCasa5K (D-25, SEC-063) | `d4ec769` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-344 | 2026-10-05 | B0-02 | NO-334 | DEBT-02 W10/C47b: bộ che log chung che `KEY=value`/`KEY: value` và khoá hậu tố bí mật | `bdff809` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-345 | 2026-10-05 | B6-03b | NO-334 | DEBT-02 W10/C47b: crash `training_runner` đi qua bộ xử lý JSON đã che, giữ `excType` + `INTERNAL` | `5f7624d` (nhánh `fix/debt-02-w10-security-probe`) |
| FIX-346 | 2026-10-05 | F-01b | NO-208 | DEBT-02 W10/C45b: `run-playwright.mjs` làm ấm đồ thị module Vite trước bài đầu, lượt e2e lạnh hết đỏ | `f5332dc7` (AppFront, nhánh `fix/debt-02-w10-fe`) |
| FIX-348 | 2026-10-04 | F-01b | NO-154 | DEBT-02 W10/C45: luồng tiến độ xin refresh một lần mỗi chuỗi SSE chết | `9ce307a6` (AppFront, nhánh `fix/debt-02-w10-fe`) |
| FIX-349 | 2026-10-04 | F-01b | NO-209 | DEBT-02 W10/C45: `expiresIn` đọc theo giờ máy chủ như lịch hẹn | `09bffa11` (AppFront, nhánh `fix/debt-02-w10-fe`) |
| FIX-350 | 2026-10-05 | B0-01 | NO-271, NO-280 | DEBT-02 W10/C48: đo lại `-n` 4/6/8, giữ mặc định 6, docstring `pytest_workers()` theo số đo mới | `cf542eb`, `a681354`, `4870259` (nhánh `fix/debt-02-w10-gate-measure`) |
| FIX-351 | 2026-10-05 | B0-10 | — | DEBT-02 R1/RA: backup.sh ghi bản rõ ở staging/APP_ENV rỗng (review R1 F4, F21) | `19e6dd5`, `2d1184d`, `21a1a1d` (nhánh `fix/debt-02-r1-deploy-tools`) |
| FIX-352 | 2026-10-05 | B0-08 | NO-197 | DEBT-02 R1/RA: env.example thiếu hai biến sao lưu; test map nginx lỏng (review R1 F4, F12) | `6aecb51`, `a51986a`, `9960254` (nhánh `fix/debt-02-r1-deploy-tools`) |
| FIX-353 | 2026-10-05 | B0-01 | — | DEBT-02 R1/RA: case_gate nới xfail; coverage_gate in 100% giả (review R1 F7, F24) | `debb053`, `39cec55` (nhánh `fix/debt-02-r1-deploy-tools`) |
| FIX-354 | 2026-10-05 | B0-02 | — | DEBT-02 R1/RA: regex userinfo che cả host khi query có @ (review R1 F19) | `031f3a7`, `3ada64f` (nhánh `fix/debt-02-r1-deploy-tools`) |
| FIX-355 | 2026-10-05 | B0-04 | — | DEBT-02 R1/RA: assert lỏng + docstring sai ở test storage (review R1 F10, F22) | `9e5c81b`, `6b2569a`, `9612c27`, `2a54c11` (nhánh `fix/debt-02-r1-deploy-tools`) |
| FIX-357 | 2026-10-05 | B5-06c | — | DEBT-02 R1/RB: test sweep gắn perf cho test chức năng; tên test sai khuôn (F5, F21) | `8928b9d` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-358 | 2026-10-05 | B5-07 | NO-304 | DEBT-02 R1/RB: test chạm _STORAGE/_storage riêng tư; perf gắn nhầm test chức năng (F5, F6b) | `a3a6113` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-359 | 2026-10-05 | B6-03b | NO-263 | DEBT-02 R1/RB: huấn luyện: perf gắn nhầm, thiếu LOG_LEVEL/LOG_JSON trong env con, docstring cũ, tên test (F5, F17, F18, F21) | `27e4a49` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-360 | 2026-10-05 | B6-04b | — | DEBT-02 R1/RB: _result sập khi reply không phải dict / float() lỗi; dòng kết quả dính dòng lạ (F8, F9) | `8a1a8be` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-361 | 2026-10-05 | B5-04 | — | DEBT-02 R1/RB: test làm tròn bề rộng so mảng với chính nó (F11) | `c72b5e3` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-362 | 2026-10-05 | B5-06b | NO-296 | DEBT-02 R1/RB: docstring trần 30 s nhắc 'nợ ghi riêng' sai (F22) | `d9ab535` (nhánh `fix/debt-02-r1-ml-worker`) |
| FIX-364 | 2026-10-05 | B1-04 | — | DEBT-02 R1/RC: assert hành vi khoá avatar là ULID (review R1 F13) | `ff02ba7` (nhánh `fix/debt-02-r1-api`) |
| FIX-365 | 2026-10-05 | B2-07 | — | DEBT-02 R1/RC: assert danh tính lock_project_scope (review R1 F13) | `a518dd4` (nhánh `fix/debt-02-r1-api`) |
| FIX-366 | 2026-10-05 | B4-02 | — | DEBT-02 R1/RC: một nguồn mark_max + test dòng bị xoá giữa INSERT và SELECT (review R1 F14) | `a5bdb63` (nhánh `fix/debt-02-r1-api`) |
| FIX-367 | 2026-10-05 | B3-04 | — | DEBT-02 R1/RC: dùng count_sql và regex FROM\|JOIN floors (review R1 F16) | `f1d735c` (nhánh `fix/debt-02-r1-api`) |
| FIX-368 | 2026-10-05 | B2-01 | — | DEBT-02 R1/RC: đổi tên test theo hàm__điều kiện (review R1 F21) | `91e8ae7` (nhánh `fix/debt-02-r1-api`) |
| FIX-369 | 2026-10-05 | B4-01 | — | DEBT-02 R1/RC: đổi tên test (review R1 F21) | `f2e817e` (nhánh `fix/debt-02-r1-api`) |
| FIX-370 | 2026-10-05 | B2-06 | — | DEBT-02 R1/RC: docstring 5 WORKER_BLOCKED (review R1 F22) | `ee6a42f` (nhánh `fix/debt-02-r1-api`) |
| FIX-371 | 2026-10-05 | B2-04 | — | DEBT-02 R1/RC: hoàn docstring Create Date (review R1 F23) | `2a68539` (nhánh `fix/debt-02-r1-api`) |

> **Giao việc FIX-003..005.** Ba FIX này sửa test của prompt khác ngay trên nhánh B0-06 (ngoại lệ của K27):
> người điều phối chọn "Tôi FIX ngay trong phiên này" ngày 2026-09-20 khi cổng bước 5 đỏ vì chúng,
> và xác nhận lại ngày 2026-09-21 ("thực hiện sửa đi và merge"). Phạm vi mỗi FIX chỉ là file test ghi ở [4];
> mã sản phẩm của B0-01, B0-03, B0-05 không đổi. Nhánh mang nhiều prompt nên vào `main` bằng `--no-ff` (R-36).

---

## FIX-003 cho B0-01 — ba test của `case_gate` chốt trạng thái repo rỗng làm bất biến

**[1 TRIỆU CHỨNG]** `bash tools/verify/run.sh verify` bước 5 hỏng ngay khi B0-06 hợp nhất:

```
FAILED tools/tests/test_case_gate.py::test_real_operations_chưa_có_b0_06_trả_rỗng
FAILED tools/tests/test_case_gate.py::test_real_task_names - AssertionError: assert ['purge_expired_idempotency'] == []
FAILED tools/tests/test_case_gate.py::test_main_đạt_khi_chưa_có_thao_tác - assert 1 == 0
```

**[2 TÁI HIỆN]** Trên `feature/b0-06-api-framework` @ `eb40a3c`:
`pytest tools/tests/test_case_gate.py -k "real_operations or real_task_names or chưa_có_thao_tác"` → `3 failed`.

**[3 BẰNG CHỨNG]** `tools/tests/test_case_gate.py:472` `assert case_gate._real_operations() == []`;
`:478` `assert case_gate._real_task_names() == []`; `:485` `main() == 0` trong khi
`JUNIT_PATHS` bị trỏ đi nên `purge_expired_idempotency` báo thiếu `['J01','J06']`.
Ba khẳng định này trái CASE §2.3: `operations()` và `registered_tasks()` là **sổ thật của
tiến trình** và khác rỗng ngay khi có prompt đầu tiên mount route hay khai `@periodic`.

**[4 KHOANH VÙNG]** Sửa: `tools/tests/test_case_gate.py`. **Cấm sửa**: `tools/case_gate.py`
(logic cổng đúng, chỉ test sai), mọi file dưới `apps/`, `packages/`.

**[5 SỬA NHỎ NHẤT]** Dựng đầu vào tại chỗ thay vì đọc trạng thái repo: vắng mặt module dựng
bằng `sys.modules`, sổ task dựng bằng `monkeypatch`, `main()` chạy với `_real_operations`/
`_real_task_names` trả rỗng. Thêm một test khẳng định đường thật vẫn đọc được (`isinstance`),
ổn định với mọi số thao tác.

**[6 TEST CHẶN TÁI PHÁT]** `test_real_operations_khi_chủ_chưa_hợp_nhất_trả_rỗng`,
`test_real_operations_đọc_được_sổ_thật` — không khẳng định số lượng, nên prompt sau thêm route
không làm đỏ lại.

**[7 NGHIỆM THU]** `just verify` bước 1–6, 8 `đạt`; ba test đỏ → xanh.

---

## FIX-004 cho B0-03 — `test_new_revision` ghim head của cây revision làm hằng

**[1 TRIỆU CHỨNG]** `FAILED packages/db/tests/test_new_revision.py::test_creates_revision_with_charter_name`

**[2 TÁI HIỆN]** Trên cùng commit: `pytest packages/db/tests/test_new_revision.py -k charter_name` → `1 failed`.

**[3 BẰNG CHỨNG]** `packages/db/tests/test_new_revision.py:54`
`assert 'down_revision: str | None = "r20260920_b0_03"' in body` (annotation của mẫu lúc đó; từ FIX-292
`374c7ab`, `script.py.mako` sinh `down_revision: str | Sequence[str] | None = …` và test khẳng định chuỗi đó,
`test_new_revision.py:78`). BE-00 §6.1 cho **mỗi prompt
một revision**, nên head đổi sau mỗi lần hợp nhất; revision `r20260920_b0_06` của B0-06 là head
mới. Hằng này sẽ đỏ với B2-01, B2-03… y như vậy.

**[4 KHOANH VÙNG]** Sửa: `packages/db/tests/test_new_revision.py`. **Cấm sửa**:
`packages/db/new_revision.py` (hành vi đúng), `packages/db/migrations/**`.

**[5 SỬA NHỎ NHẤT]** Đọc head thật của bản sao cây revision bằng
`ScriptDirectory.from_config(...).get_heads()` **trước** khi tạo revision, rồi so với nó.

**[6 TEST CHẶN TÁI PHÁT]** Chính `test_creates_revision_with_charter_name` sau khi sửa: nó còn
khẳng định cây chỉ có **một** head (`assert len(heads) == 1`), nên hai head lọt vào cũng đỏ.

**[7 NGHIỆM THU]** `just verify` bước 6 `đạt` (`migrate_check` 9/9); test đỏ → xanh.

---

## FIX-005 cho B0-05 — hai test của `messaging` chốt "sổ task và beat rỗng"

**[1 TRIỆU CHỨNG]**

```
FAILED packages/messaging/tests/test_tasks.py::test_registered_tasks_leaves_out_tasks_declared_in_tests
FAILED packages/messaging/tests/test_worker_main.py::test_the_worker_process_is_ready_to_run_schedules
```

**[2 TÁI HIỆN]** `pytest packages/messaging/tests/test_tasks.py -k leaves_out`
và `pytest packages/messaging/tests/test_worker_main.py -k ready_to_run` → mỗi lệnh `1 failed`.

**[3 BẰNG CHỨNG]** `test_tasks.py:202` `assert registered_tasks() == []`;
`test_worker_main.py:56` `assert loaded["beat"] == []`. B0-06 khai
`@periodic("default.idempotency.purge_expired")` đúng bảng "Dọn rác" của BE-00 §7, dòng
"bản ghi idempotency hết hạn | B0-06". Mười lăm chủ khác trong bảng đó cũng sẽ khai lịch.

**[4 KHOANH VÙNG]** Sửa: `packages/messaging/tests/test_tasks.py`,
`packages/messaging/tests/test_worker_main.py`. **Cấm sửa**: `packages/messaging/tasks.py`,
`schedules.py`, `apps/worker/celery_main.py`.

**[5 SỬA NHỎ NHẤT]** Đổi khẳng định sang đúng bất biến mà docstring của hai test đã nói:
- sổ task **không chứa** task khai trong module test (thay cho "sổ rỗng");
- `app.conf.beat_schedule` của worker **bằng** sổ lịch dò lại **độc lập** trong cùng tiến trình
  con — `discover_jobs()` (idempotent) rồi `beat_schedule()` — thay cho "beat rỗng". Chứng minh
  "sổ được gắn đủ" mà không phụ thuộc số lịch.

**[6 TEST CHẶN TÁI PHÁT]** Hai test trên sau khi sửa: bỏ `discover_jobs()` khỏi `celery_main`
thì `beat` rỗng còn `beat_ledger` (dò lại độc lập) khác rỗng → đỏ; đưa task của module test vào sổ
→ đỏ.

> **Sửa lần hai (review 2026-09-21, finding #3).** Bản đầu tính `beat_ledger` bằng `beat_schedule()`
> **không** dò lại, nên khi `celery_main` quên `discover_jobs()` cả hai vế cùng rỗng và test vẫn qua —
> câu [6] ở trên khi đó là sai. Đã tái hiện: giả lập worker không dò → `beat = [] | beat_ledger = []`.
> Bản sửa gọi `discover_jobs()` trước khi tính vế phải; cùng giả lập đó nay cho
> `beat = [] ≠ beat_ledger = ['default.idempotency.purge_expired']`.

**[7 NGHIỆM THU]** `just verify` bước 5 `đạt`; hai test đỏ → xanh.

---

> **Giao việc FIX-006..FIX-028.** Người dùng yêu cầu ngày 2026-09-21: "thực hiện fix cho hết nợ đi".
> Mọi dòng `⬜` của `DEBT.md` sửa được bằng mã có một FIX; mỗi FIX sửa **đúng** file ở [4] của nó
> (ngoại lệ K27 do người điều phối giao). Ba nhánh chạy song song ở worktree riêng, theo chủ file:
> `fix/b0-01-gate-debts` (FIX-006..010), `fix/b0-04-storage-debts` (FIX-011..019),
> `fix/b0-05-messaging-debts` (FIX-020..027). FIX-028 nằm trên `feature/b0-07-contract-harness`
> vì cần `packages/testing/golden/recorder.py` của B0-07. Nhánh nhiều prompt vào `main` bằng `--no-ff`
> (R-36), mỗi nhánh qua `/merge-review` riêng (R-37).
> **Không có FIX:** NO-006, NO-021 (compose của app là deliverable của B0-08, prompt chưa chạy —
> sửa ở đây là viết việc của prompt khác); NO-018 (sửa là viết lại lịch sử đã được trỏ tới → chuyển `➖`).
>
> Luật chung cho mọi FIX dưới đây (FIX.md): test ở [6] **đỏ trên mã hiện tại trước khi sửa** (báo lệnh
> và mã thoát), không nới assert, không `skip`/`xfail`/retry để giấu (K24), không mock
> Postgres/Redis/MinIO (K23); không đổi hợp đồng HTTP; thấy lỗi khác thì ghi `DEBT.md`, không sửa.
> Dòng `DEBT.md` của nợ chuyển `✅` (hay `➖` kèm lý do đứng được) **trong chính commit sửa**.
> Nghiệm thu chung: `bash tools/verify/run.sh verify` thoát 0; commit
> `fix(<scope>): …` + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …` (R-36b).

## FIX-006 cho B0-01 — `_clean_dir` nuốt lỗi xoá (NO-008)

- **[1–3]** `tools/verify/steps.py:_clean_dir` gọi `shutil.rmtree(d, ignore_errors=True)`: file không xoá được bên trong thư mục ra bị bỏ qua, `merge-heads` có thể chép nhầm file cũ còn sót.
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** Duyệt và xoá từng mục con của `d` (giữ lại chính mount point, FIX-001), để lỗi xoá nổi lên.
- **[6]** Test: mục con không xoá được → `_clean_dir` ném; mount point vẫn giữ được như test của FIX-001.

## FIX-007 cho B0-01 — `test_services` dùng trần bắt tay 5 s cho Postgres dùng chung (NO-042)

- **[1–3]** `tools/tests/test_services.py:32-33` `asyncpg.connect(..., timeout=5)` cho cả bản **đã dừng** lẫn bản **dùng chung**; chặng `host.docker.internal` kẹt thì bản dùng chung đỏ giả (`45a73ad`, bước 5 `1 failed`).
- **[4]** Sửa: `tools/tests/test_services.py`.
- **[5]** Bản đã dừng giữ trần ngắn (lỗi kết nối tới ngay); bản còn chạy dùng `GATE_CONNECT_TIMEOUT_S` của `packages.db.engine`.
- **[6]** Test hàm chọn trần: bản dừng → ngắn, bản chạy → `GATE_CONNECT_TIMEOUT_S`.

## FIX-008 cho B0-01 — mẫu golden không được chép ra `contract-samples/` (NO-043)

- **[1–3]** ENV §2: `CONTRACT_SAMPLES_DIR=/tmp/contract-samples` "cuối lượt chép ra `/src-out/contract-samples`"; `steps.py`/`in_container.sh` không chép, thư mục của worktree luôn rỗng.
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** Sau `run_steps` của việc `verify` (kể cả khi có bước hỏng), chép nội dung `CONTRACT_SAMPLES_DIR` (nếu có) vào `OUT_DIR / "contract-samples"`; không xoá mount point.
- **[6]** Test: có mẫu → chép đủ cây; không có thư mục → không lỗi.

## FIX-009 cho B0-01 — chặng `host.docker.internal` kẹt ~68 s (NO-007)

- **[1–3]** NO-002, NO-036, NO-042: container verify nối testcontainers qua `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal` (cổng chuyển tiếp qua máy Windows); thỉnh thoảng kẹt ~68 s.
- **[4]** Sửa: `deploy/compose/verify.yml`, `tools/verify/in_container.sh`, `tools/verify/run.sh`, test dưới `tools/tests/`.
- **[5]** Worker tự tìm, **tái hiện trước** (R-35): đo độ trễ bắt tay lặp nhiều lượt qua `host.docker.internal` và qua đường không đi qua máy Windows (gateway của mạng `bridge`, hay IP container trên cùng mạng). Chỉ đổi khi số đo chứng minh; CI (ngoài container, không đặt biến override) không được đổi hành vi.
- **[6]** Không tái hiện được trong số lượt đã hẹn: ghi vào `DEBT.md` số lượt, giả thuyết đã loại và bằng chứng; **không sửa mò**.

## FIX-010 cho B0-03 — `db_sessionmaker` dùng trần 10 s (NO-036)

- **[1–3]** `packages/testing/fixtures/db.py:109` dựng `DatabaseSettings(...)` với `db_connect_timeout_s` mặc định 10 s của đường request.
- **[4]** Sửa: `packages/testing/fixtures/db.py`, test dưới `packages/db/tests/`.
- **[5]** `db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)` như `api_env` của B0-06.
- **[6]** Test: engine của `db_sessionmaker` mang trần bắt tay bằng `GATE_CONNECT_TIMEOUT_S`.

## FIX-011..FIX-019 cho B0-04 — `packages/storage` (NO-009..NO-017)

- **[4] chung:** Sửa `packages/storage/**` (mã + `tests/`). Cấm sửa file của prompt khác, kể cả `apps/api/files/`.
- **FIX-011 (NO-009):** `S3Error` có `response.status >= 500` → `DEPENDENCY_UNAVAILABLE` (503 + `Retry-After`); `AccessDenied`, `NoSuchBucket`… vẫn nổi lên. Test dùng MinIO **thật** đứng sau một proxy tiêm lỗi 5xx có thân XML (không mock MinIO, K23).
- **FIX-012 (NO-010):** `_delete_under` gom khoá qua `remove_objects` (≤ 1000/lượt), duyệt **và báo** mọi lỗi trả về. Test: xoá > 1 lô trên MinIO thật, đếm lượt gọi.
- **FIX-013 (NO-011):** `server_chosen_kind(key)` cho mọi khoá do server đặt tên sau khi đã kiểm magic bytes (ảnh đại diện, `…/pages/{i}.png`), vẫn cấm cho `original.<đuôi>`. Test: ký `inline` khoá trang không tốn `HEAD`; `original.png` vẫn phải đọc metadata.
- **FIX-014 (NO-012):** `delete_prefix` bản local: chỉ bỏ qua `FileNotFoundError`, lỗi khác qua `_disk_errors` → 503.
- **FIX-015 (NO-013):** `list_prefix` bơm theo lô, không `list(...)`/`sorted(rglob)` cả cây vào RAM (R-22); giữ thứ tự hợp đồng hiện có.
- **FIX-016 (NO-014):** tách bộ đổi lỗi đĩa lên `port.py`, `S3Storage.put` dùng chung (R-07): đĩa đầy khi đệm → 503.
- **FIX-017 (NO-015):** `ensure_bucket` chỉ nuốt `NotImplemented`; mã khác ghi `WARNING` kèm `code` hoặc ném.
- **FIX-018 (NO-016):** hai test lấy mốc từ `stat()` vừa đọc hoặc khẳng định quan hệ thứ tự, không trộn giờ thật với `fake_clock`.
- **FIX-019 (NO-017, phần B0-04):** finding #10 (khẳng định "không chứa khoá dạng thô") và #12 (chú thích `_message` ghi đúng bản tin 4 trường `k|e|d|n`). Phần B0-06 đã tuân (`eb40a3c`).

## FIX-020..FIX-027 cho B0-05 — `packages/messaging` (NO-022..NO-030)

- **[4] chung:** Sửa `packages/messaging/**` (mã + `tests/`). Không đổi tên task, hàng, payload.
- **FIX-020 (NO-022):** worker thật trong **tiến trình con** (`subprocess`), `SIGKILL` giữa task, khẳng định task được giao lại và lượt vượt trần thành `WORKER_LOST`.
- **FIX-021 (NO-023):** `INCR` + `EXPIRE` gộp một script Lua nguyên tử như `publish_once`.
- **FIX-022 (NO-024):** `worker_process_shutdown` đóng `Runner`; `reset_runner()` cho test.
- **FIX-023 (NO-025):** giới hạn là của `asyncio` (không ném được vào thân `@asynccontextmanager`): docstring của `hold` nêu người giữ khoá cho việc dài phải gọi `renew()` và kiểm giá trị; có test chứng minh `renew()` báo mất khoá. Nợ chuyển `➖` kèm lý do nếu không còn gì sửa được bằng mã.
- **FIX-024 (NO-027):** test khoá không đếm giờ thật với biên hẹp: khẳng định quan hệ (`EXISTS` trước/sau, token rào tăng) hoặc nới TTL lên vài giây.
- **FIX-025 (NO-028):** `release` trong `finally` bọc `try/except` ghi `WARNING` (TTL dọn hộ), không che ngoại lệ của thân. Test theo công thức tái hiện ghi ở NO-028.
- **FIX-026 (NO-029):** ghi ngưỡng + đường nâng cấp cạnh `FENCE_SUFFIX` (R-05) và ràng buộc bàn giao cho B6-03a; nợ chuyển `➖` nếu hiến chương vẫn cho phép.
- **FIX-027 (NO-030):** `_fail` chỉ ghi `type(exc).__name__` + ≤ 200 ký tự đầu của thông điệp.

## FIX-028 cho B0-06 — hai bộ khớp (method, đường) → thao tác (NO-044)

- **[1–3]** `packages/testing/fixtures/api.py:_op_matchers/operation_of` trùng việc với `packages/testing/golden/recorder.py:operation_resolver` (R-07).
- **[4]** Sửa: `packages/testing/fixtures/api.py`, test ở `packages/testing/golden/tests/test_recorder.py` (trên nhánh B0-07).
- **[5]** `operation_of` trả `.op` của `recorder.resolve_operation(method, path)`; xoá `_op_matchers`.
- **[6]** Test hiện có của `trace_case` (`apps/api/core/tests/test_fixtures.py`) giữ nguyên và xanh; thêm test khẳng định vết case và bộ ghi golden khớp **cùng** thao tác cho một request.

## FIX-029 cho B0-06 — năm test lõi chốt trạng thái "chưa có B1-01" (NO-053)

> Giao trong phiên B1-01 (ngoại lệ của K27, như FIX-003..005): người điều phối chọn "FIX here" ngày 2026-09-21
> khi cổng bước 5 của B1-01 đỏ vì chúng. Chỉ sửa file test ở [4]; mã sản phẩm của B0-06 không đổi.

- **[1 TRIỆU CHỨNG]** `bash tools/verify/run.sh verify` trên `feature/b1-01-auth-login-sessions` @ `4320e0e`, bước 5 `hỏng`:
  `test_app.py::test_deny_all_when_no_auth_module`, `::test_production_without_auth_module_refuses_to_start`,
  `::test_verifier_module_exists_is_false_today`, `::test_discover_routers_finds_real_modules`,
  `test_openapi.py::test_real_app_has_exactly_three_operations` (`5 failed, 1400 passed`).
- **[2 TÁI HIỆN]** `pytest apps/api/core/tests/test_app.py apps/api/core/tests/test_openapi.py` @ `4320e0e` → `5 failed, 38 passed`.
- **[3 BẰNG CHỨNG]** Các test đọc trạng thái repo làm bất biến: `_verifier_module_exists() is False`, `discover_routers() == [files, health]`,
  `operations() == ("files_read_object", "health_live", "health_ready")`; B1-01 thêm `apps/api/auth/verifier.py` và `router.py` theo đúng BE-00 §2.2.
- **[4 KHOANH VÙNG]** Sửa: `apps/api/core/tests/test_app.py`, `apps/api/core/tests/test_openapi.py`. Cấm: `apps/api/core/*.py`.
- **[5 SỬA NHỎ NHẤT]** Dựng đầu vào tại chỗ: vắng module auth bằng `monkeypatch` `_verifier_module_exists`/`importlib.util.find_spec`
  (gói cha thiếu và chỉ thiếu `verifier`); dò router so với `apps/api/*/router.py` trên đĩa; ba route lõi có mặt và công khai, mọi route công khai
  `idempotency == "off"` — không ghim tổng số.
- **[6 TEST CHẶN TÁI PHÁT]** Chính năm test đã viết lại (một test thành hai tham số). Đỏ 5/5 trước (`5 failed, 38 passed`), xanh sau (`44 passed`).
- **[7 NGHIỆM THU]** Bảng cổng của báo cáo B1-01; commit `test(api): …` + `Prompt: B0-06`, `Fix: FIX-029`.

## FIX-030, FIX-031 cho B0-06 — hạn mức đọc lười, DB an toàn sạch giữa các test (NO-054, NO-055)

> Giao trong phiên B1-01 như FIX-029: người điều phối yêu cầu "fix nợ" ngày 2026-09-21. Chỉ sửa file ở [4].

- **FIX-030 (NO-054).** [1–3] `apps/api/core/ratelimit.py:rate_limit` so `limit < 1` lúc khai, nên hạn mức đọc từ
  `AuthSettings` (lười: B0-06 nhập mọi module khi chưa có biến môi trường, test nâng hạn mức bằng `setenv`) buộc
  `apps/api/auth/router.py` dựng limiter mỗi request. [4] Sửa `apps/api/core/ratelimit.py`, `apps/api/core/tests/test_ratelimit.py`;
  cấm đổi hành vi của hạn mức số. [5] `limit`/`window_s` nhận `int | Callable[[], int]`: số kiểm lúc khai như cũ, hàm gọi
  và kiểm mỗi lượt. [6] `test_quota_can_be_read_at_request_time`, `test_lazy_quota_below_one_fails_at_request_time`:
  đỏ trước (`TypeError: '<' not supported between instances of 'function' and 'int'`), xanh sau.
- **FIX-031 (NO-055).** [1–3] `packages/testing/fixtures/api.py:api_env` phụ thuộc `cache_client` mà không phụ thuộc
  `safe_client`: bộ đếm `store="safe"` và khoá đăng nhập (mọi lượt ASGI từ `127.0.0.1`) rò sang test sau. [4] Sửa
  `packages/testing/fixtures/api.py`, `apps/api/core/tests/test_fixtures.py`. [5] `api_env` nhận thêm `safe_client`
  (`FLUSHDB` lúc dọn). [6] `test_api_env_flushes_both_redis_roles`: đỏ trước (thiếu `safe_client`), xanh sau.
- **[7]** Bảng cổng của báo cáo B1-01; mỗi FIX một commit `Prompt: B0-06` + `Fix: FIX-<nnn>`. Phía B1-01 (commit riêng,
  `Prompt: B1-01`): khai `_login_ip_limit`, `_refresh_total_limit` một lần bằng hàm hạn mức; `auth_app`/`probe_app`
  bỏ `FLUSHDB` thừa.

---

> **Giao việc FIX-032..FIX-037 và hợp nhất FIX-006..FIX-027.** Người dùng yêu cầu ngày 2026-09-22: "đọc DEBT.md và fix
> tất cả các nợ". Ba nhánh của đợt trước (`fix/b0-01-gate-debts`, `fix/b0-04-storage-debts`, `fix/b0-05-messaging-debts`)
> chưa từng qua `/merge-review`: mỗi nhánh **gộp `main` vào** (không rebase — giữ sha FIX-006..027 đã ghi ở bảng trên),
> chạy lại cổng, rồi qua review riêng. FIX mới chạy song song ở worktree riêng, theo vùng file (ngoại lệ K27 do người
> điều phối giao, như FIX-003..005): FIX-032 trên `fix/b0-01-gate-debts` (cùng `tools/verify/steps.py` với FIX-006, 008);
> FIX-033..035 trên `fix/b0-07-contract-tool-debts`; FIX-036, 037 trên `fix/b0-03-check-constraint-names` (phải vào
> cùng nhau: FIX-036 làm bước 6 đỏ trên `main` cho tới khi FIX-037 đổi tên). Người điều phối cho phép FIX-037 thêm tên
> revision của nó vào `docs/contracts.toml` (BE-00 §6.1).
> **Không có FIX:** NO-006, NO-021 (compose của app, deliverable của B0-08, prompt chưa chạy); NO-050 (hiến chương,
> người điều phối sửa sau khi FIX-009 vào `main`); NO-051 (ràng buộc bàn giao cho job CI của B0-09, prompt chưa chạy).
>
> Luật chung như đợt FIX-006..028 (đoạn giao việc ở trên): test [6] đỏ trước, xanh sau; không nới assert, không
> `skip`/`xfail`/retry (K24), không mock dịch vụ (K23), không đổi hợp đồng HTTP; dòng `DEBT.md` chuyển `✅` trong chính
> commit sửa; commit `fix(<scope>): …` + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …`.

## FIX-032 cho B0-01 — lượt verify lạnh tải `npm` trong bước 5 (NO-048)

- **[1–3]** Volume chưa có `$CONTRACT_NODE_DIR/<băm package-lock>`: fixture phiên `contract_build`
  (`packages/testing/fixtures/golden.py:47`) gọi `build_layout` → `ensure_node_modules` → `npm ci` từ `registry.npmjs.org`
  ngay trong pytest của bước 5 (bước 5 chạy trước bước 7). Trái "không tải mạng trong test".
- **[4]** Sửa: `tools/verify/steps.py` (hoặc `tools/verify/in_container.sh`), test dưới `tools/tests/`. Cấm sửa
  `tools/contract/**`, `packages/testing/**`.
- **[5]** Việc `verify` làm ấm `node_modules` ở pha chuẩn bị, **trước** bước 5: gọi
  `tools.contract.runner_client.ensure_node_modules(<đúng thư mục mà contract_build dùng>)`; lỗi làm ấm là lỗi hạ tầng của
  cổng, báo rõ, không nuốt. Không chạy khi `--steps` không gồm bước cần runner Node.
- **[6]** Test: chuỗi việc của `verify` gọi làm ấm trước bước 5 (theo lối `tools/tests/test_steps_commands.py`).

## FIX-033, FIX-034 cho B0-01, B0-07 — bộ ghi golden nhập tên riêng của `case_gate` (NO-049)

- **[1–3]** `packages/testing/golden/recorder.py:32` `from tools.case_gate import _TEST_COMMON_RE, _TEST_OP_CASE_RE`;
  B0-01 đổi tên hai hằng thì mọi phiên test hỏng lúc nhập (`packages/testing/fixtures/api.py` nhập `recorder`).
- **[4]** FIX-033 (`Prompt: B0-01`): `tools/case_gate.py`, `tools/tests/test_case_gate.py`. FIX-034 (`Prompt: B0-07`):
  `packages/testing/golden/recorder.py` và test của nó. Hai commit riêng.
- **[5]** `case_gate` xuất một hàm công khai tách tên test (mẫu chung xét trước mẫu riêng, như chính `case_gate`), và dùng
  lại nó ở chỗ của mình (R-07); bộ ghi gọi hàm đó. Hành vi tách tên không đổi.
- **[6]** Test hàm công khai (dạng riêng, dạng chung, tên không khớp); test chặn bộ ghi nhập tên `_…` của `case_gate`.

## FIX-035 cho B0-07 — `tools.contract.check` để lại thư mục dựng tạm (NO-052)

- **[1–3]** `tools/contract/check.py:main` không có `--build-dir` dựng vào `tempfile.mkdtemp()` và không dọn: mỗi lượt để
  lại ≈ 16 MB bản chép `src` của AppFront.
- **[4]** Sửa: `tools/contract/check.py`, `tools/contract/tests/test_check.py`.
- **[5]** Không `--build-dir` → `tempfile.TemporaryDirectory(prefix="contract-")`; có `--build-dir` → giữ lại để gỡ lỗi.
- **[6]** Test: `main` không `--build-dir` (thư mục tạm trỏ về `tmp_path`) không để lại `contract-*`.

## FIX-036, FIX-037 cho B0-03, B0-06 — tên `CHECK` lặp tiền tố (NO-057)

- **[1–3]** `r20260920_b0_06_idempotency.py:44-45` truyền `name=f"ck_{TABLE}_…"`; quy ước
  `ck_%(table_name)s_%(constraint_name)s` (`packages/db/base.py:17`) áp thêm lần nữa → DB có
  `ck_idempotency_records_ck_idempotency_records_state`, `…_key_format`, model sinh `ck_idempotency_records_state`.
  `migrate_check` "model khớp DB" (`compare_metadata`) không so tên `CHECK`, nên cổng không bắt.
- **[4]** FIX-036 (`Prompt: B0-03`): `packages/db/migrate_check.py`, `packages/db/tests/`. FIX-037 (`Prompt: B0-06`): một
  revision contract mới dưới `packages/db/migrations/versions/` (tạo bằng `python -m packages.db.new_revision`), dòng tên
  revision trong `docs/contracts.toml`. Cấm sửa revision đã hợp nhất (`r20260920_b0_06_idempotency.py`).
- **[5]** FIX-036: bước "model khớp DB" (hoặc bước ngay sau) so tập tên `CHECK` của mọi bảng trong `Base.metadata` (tên đã
  áp quy ước) với `pg_constraint` (`contype = 'c'`, chỉ bảng của metadata); lệch → bước hỏng, in tên lệch. FIX-037:
  revision `r20260921_b0_06_fix037 (tên `new_revision` sinh theo ngày UTC)` mang `# contract:` ở đầu, `upgrade` đổi tên hai ràng buộc về tên của model,
  `downgrade` đổi ngược.
- **[6]** Test FIX-036: DB có `CHECK` tên lặp tiền tố → bước hỏng (đỏ trước: bước đạt). Cổng bước 6 đỏ khi chỉ có
  FIX-036, xanh khi có cả FIX-037.

## FIX-038 cho B0-01 — `lint_migrations` chặn cả revision contract đã đăng ký (NO-058)

> Phát hiện trong FIX-037 (worker hỏi, người điều phối chọn sửa gốc ngày 2026-09-22). Cùng nhánh
> `fix/b0-03-check-constraint-names`, commit trước FIX-037.

- **[1–3]** `tools/lint_migrations.py:_lint_file` luôn gọi `_lint_body`: revision mang `# contract:` và đã có trong
  `docs/contracts.toml` vẫn bị báo "execute chuỗi SQL cấm" với `RENAME`/`DROP`, nên đường revision contract của
  BE-00 §6.1 không dùng được (FIX-037 cần `RENAME CONSTRAINT`).
- **[4]** Sửa: `tools/lint_migrations.py`, `tools/tests/test_lint_migrations*.py`.
- **[5]** Contract đã đăng ký chỉ được miễn các luật **phá huỷ** của expand (`drop_*`, `rename_table`, `alter_column`
  đổi tên/`nullable=False`/`type_`, chuỗi SQL `DROP|RENAME|SET NOT NULL|TRUNCATE|DELETE FROM|ALTER COLUMN … TYPE`,
  `add_column` NOT NULL không default). Vẫn kiểm: `execute`/`text`/`exec_driver_sql` với đối số không phải hằng,
  `batch_alter_table`, `create_index` thiếu `CONCURRENTLY`/ngoài `autocommit_block`, tên revision. Chưa đăng ký → như cũ.
- **[6]** Contract đã đăng ký có `RENAME`/`DROP` → đạt (đỏ trước); có `execute` chuỗi không hằng → vẫn hỏng; chưa đăng
  ký có `RENAME` → hỏng.

---

> **Giao việc FIX-039..FIX-051 (đợt 2).** Người dùng yêu cầu ngày 2026-09-22: "thực hiện fix tiếp, dùng orca, mỗi session 12 nợ
> kỹ thuật cho đến khi fix hết trong debt.md". Đợt 1 (FIX-006..038) đã vào `main` qua năm nhánh `fix/*`, mỗi nhánh một phiên
> `/merge-review` riêng. Đợt 2 nhận đúng 12 nợ còn sửa được: mười nợ mã dưới đây (NO-060, NO-065..NO-070, NO-072..NO-074) và hai
> dòng hiến chương của người điều phối (NO-050, NO-071 — người điều phối tự làm, không có FIX). Bốn worktree chạy song song theo
> vùng file (ngoại lệ K27 do người điều phối giao, như đợt 1), trần 2 lượt verify cùng lúc trên máy (RAM):
> `fix/b0-03-migration-tool-debts` (FIX-039..042), `fix/b0-04-object-key-debts` (FIX-043..047),
> `fix/b1-01-parallel-refresh-flake` (FIX-048), `fix/b0-05-quiet-release-case-filter` (FIX-049..051).
> **Không có FIX (chủ là prompt chưa chạy):** NO-006, NO-021, NO-062 (B0-08, `deploy/**`); NO-051 (job CI của B0-09);
> NO-061 (B6-01, checksum bản gốc seed); NO-063 (B5-04, ràng buộc bàn giao).
>
> Luật chung như đợt 1: test [6] đỏ trước, xanh sau; không nới assert, không `skip`/`xfail`/retry (K24), không mock dịch vụ
> (K23), không đổi hợp đồng HTTP; dòng `DEBT.md` chuyển `✅` trong chính commit sửa; commit `fix(<scope>): …` (hoặc
> `refactor(...)`/`test(...)` khi đúng loại) + trailer liền nhau `Prompt: <chủ>`, `Fix: FIX-<nnn>`, `Co-Authored-By: …`.

## FIX-039 cho B0-03 — `test_new_revision` đóng băng ngày lúc nhập (NO-065)

- **[1–3]** `packages/db/tests/test_new_revision.py` tính `TODAY = datetime.now(UTC)…` một lần lúc nhập; `new_revision.main`
  đọc `datetime.now(UTC)` lúc gọi (`packages/db/new_revision.py:66`). Bộ test vắt qua nửa đêm UTC → glob `r{TODAY}_…` rỗng,
  `test_creates_revision_with_charter_name`, `test_fix_revision_allowed_once` đỏ (`F.F` ở bước 5, `fix/b0-05-messaging-debts`
  @ `f4223f2`; tái hiện bằng lùi `TODAY` một ngày: `2 failed, 11 passed`).
- **[4]** Sửa: `packages/db/new_revision.py`, `packages/db/tests/test_new_revision.py`. Cấm: revision đã có, `tools/**`.
- **[5]** `new_revision` nhận ngày qua `Clock` của `packages/core/clock.py` (R-18; `main(argv, clock=SystemClock())` hoặc
  tương đương), test ghim bằng `fake_clock`. Không nới assert.
- **[6]** Test đặt đồng hồ giả qua nửa đêm giữa lúc dựng kỳ vọng và lúc gọi → tên revision theo ngày của đồng hồ tiêm vào; đỏ
  trên mã hiện tại.

## FIX-040 cho B0-03 — `run_checks` vượt R-08 (NO-069)

- **[1–3]** `packages/db/migrate_check.py:run_checks` 82 dòng, CC 13 (review `fix/b0-03-check-constraint-names` finding #1).
- **[4]** Sửa: `packages/db/migrate_check.py`, `packages/db/tests/test_migrate_check.py`.
- **[5]** Đưa từng bước lên mức module (nhận `engine`/`config`/`target` qua tham số), `run_checks` chỉ còn vòng lặp và dọn
  engine. Hành vi, tên bước, thứ tự bước, mã thoát không đổi.
- **[6]** Tái cấu trúc thuần: không có test đỏ; bằng chứng là `packages/db/tests` xanh trước và sau với cùng số test, và số
  dòng/CC mới của hàm ghi trong báo cáo (R-08).

## FIX-041 cho B0-03 — bước "tên CHECK khớp model" đỏ giả với CHECK gắn kiểu (NO-070)

- **[1–3]** `_check_name_drift` lấy mọi `CheckConstraint` của bảng. `Boolean(create_constraint=True)` làm bước ném
  `InvalidRequestError`; `Enum(…, create_constraint=True)` native làm bước báo "thiếu trong DB" (probe của review trên
  postgres:16-alpine). Chưa model nào dùng.
- **[4]** Sửa: `packages/db/migrate_check.py`, `packages/db/tests/test_migrate_check.py`.
- **[5]** Bỏ các ràng buộc mà DDL của dialect không phát ra (`_create_rule` trả `False` với DDL compiler), comment ghi ngưỡng
  vì dùng API riêng của SQLAlchemy (R-05). Không đổi cách so với CHECK mức bảng.
- **[6]** Metadata thử có `Boolean(create_constraint=True)` và `Enum(..., create_constraint=True)` → bước đạt (đỏ trước: ném /
  báo thiếu); CHECK mức bảng lệch tên vẫn hỏng.

## FIX-042 cho B0-01 — `_lint_body` vượt R-08 (NO-068)

- **[1–3]** `tools/lint_migrations.py:_lint_body` 78 dòng, CC 28, 25 nhánh; phân loại "phá huỷ hay không" giấu trong vòng lặp
  (`_BANNED_CALL_NAMES` trộn bốn thao tác phá huỷ với `batch_alter_table`, một `Report()` dùng để bỏ đi) — review
  `fix/b0-03-check-constraint-names` finding #1, #4.
- **[4]** Sửa: `tools/lint_migrations.py`, `tools/tests/test_lint_migrations*.py`.
- **[5]** Mỗi luật một hàm `_check_<luật>(node, …)`; hằng `_DESTRUCTIVE_CALL_NAMES` tách khỏi `batch_alter_table`; bỏ `Report()`
  dùng một lần. Hành vi (thông báo, luật miễn cho contract đã đăng ký của FIX-038) không đổi.
- **[6]** Tái cấu trúc thuần: `tools/tests/test_lint_migrations*.py` xanh trước/sau cùng số test; thêm một test chốt rằng tên
  thêm vào `_DESTRUCTIVE_CALL_NAMES` được miễn cho contract còn `batch_alter_table` thì không.

## FIX-043 cho B0-02, FIX-044 cho B0-04, FIX-045 cho B5-01 — luật khoá object có hai nguồn (NO-060)

- **[1–3]** `packages/ml_contracts/payloads.py:check_object_key` chép luật khoá của `packages/storage/keys.py:check_key`
  (`ml_contracts` không được nhập `storage`, [9] B5-01); test `test_check_object_key_matches_storage_rules` giữ hai bản khớp.
- **[4]** FIX-043: module mới dưới `packages/core/` (vd `object_keys.py`) + test dưới `packages/core/tests/`. FIX-044:
  `packages/storage/keys.py` + test của `packages/storage`. FIX-045: `packages/ml_contracts/payloads.py` + test của
  `packages/ml_contracts`. Cấm `.importlinter`.
- **[5]** Dời `check_key`/`check_prefix` (và hằng `MAX_KEY_BYTES`, đuôi metadata, `_SEGMENT_RE`) xuống `packages/core`;
  `storage` và `ml_contracts` cùng nhập, xoá bản chép (cả `payloads._prefix_key`). Vẫn ném `ValueError`; thông báo theo bản
  của `storage` (test nào của `ml_contracts` chốt chuỗi cũ thì đổi theo, ghi rõ). `packages/core` không thêm thư viện (BE-00 §13.1).
- **[6]** Test cũ khớp hai bản đổi thành test một nguồn: `payloads.check_object_key is object_keys.check_key` (hoặc gọi thẳng),
  đỏ trên mã hiện tại; bộ 12 mẫu biên chuyển về test của `packages/core`.

## FIX-046 cho B0-04 — `_SERVER_NAMED_RE` chép luật id tầng (NO-073)

- **[1–3]** `packages/storage/keys.py:30-34` chép tay `L-[0-9A-Z]{10,64}` của `packages/core/ids.py:60` (`is_spatial_id`).
- **[4]** Sửa: `packages/storage/keys.py` + test của `packages/storage`.
- **[5]** Tách khoá theo `/` và kiểm từng đoạn bằng `is_id`/`is_spatial_id` như hàm dựng khoá; bỏ regex chép.
- **[6]** Test khoá trang với id tầng dài 10 và 64 (đạt), 9 và 65 (không phải khoá do server đặt) và một id tầng mà luật của
  `core/ids.py` chấp nhận nhưng regex cũ từ chối (hoặc ngược lại) → đỏ trước; nếu hai luật trùng khít trên mọi mẫu thì test
  chốt một nguồn (đột biến luật ở `core` làm test storage đỏ), ghi rõ trong báo cáo.

## FIX-047 cho B0-04 — test FIX-012 không chạm biên lô (NO-072)

- **[1–3]** `packages/storage/tests/test_s3.py:186` `test_delete_prefix_deletes_in_batches` chỉ ghi 3 object; spec FIX-012 [6]
  đòi "xoá > 1 lô".
- **[4]** Sửa: `packages/storage/tests/test_s3.py`.
- **[5]** 1001 object ghi song song (có trần đồng thời), khẳng định đúng 2 lượt `POST ?delete`, 0 `DELETE`, tiền tố rỗng.
- **[6]** Test mới đỏ trên bản `_delete_under` trước FIX-012 (xoá từng object: 1001 `DELETE`) — dựng lại bản cũ trong `.cache/`.

## FIX-048 cho B1-01 — `test_auth_refresh__C11_parallel` chập chờn (NO-066)

- **[1–3]** Cổng bước 5 trên `fix/b0-05-messaging-debts` @ `22dee96`: `At index 20 diff: 401 != 429` (≥ 21 lượt 401 thay vì
  `REFRESH_FAIL_LIMIT` = 20). Không tái hiện trong 14 lượt. Giả thuyết: `soft_redis(bump…)` trả `None` (Redis chậm quá
  `CONNECT_TIMEOUT_S` = 2 s qua proxy cổng dưới tải) → lượt đó không đếm.
- **[4]** Sửa: `apps/api/auth/tests/test_refresh.py`; `apps/api/auth/router.py` chỉ khi gốc nằm ở đó. Cấm `packages/**`.
- **[5]** Tái hiện trước (R-35): chạy test dưới `coverage` nhiều lượt, song song tải CPU/verify khác; bắt log `rate_limit_open`.
  Gốc là Redis hỏng → test phải báo đúng tên nguyên nhân (không thành "đếm sai"), hoặc sửa đường đếm nếu gốc là mã. Không nới
  assert, không retry.
- **[6]** Test đỏ tất định dựng lại đúng điều kiện gốc (vd kết nối bị treo quá trần ở đúng một lượt), xanh sau sửa. Không tái
  hiện được sau số lượt đủ lớn → ghi `DEBT.md` số lượt, giả thuyết đã loại trừ và bằng chứng (R-35), `worker_done --outcome failed`.

## FIX-049 cho B0-01 — bộ lọc của `_found_cases_by_op` chưa test nào chạm (NO-067)

- **[1–3]** `tools/case_gate.py:347-348`: dòng `continue` chưa chạy lần nào; đột biến bỏ bộ lọc case chung vẫn `58 passed`
  (review `fix/b0-07-contract-tool-debts` finding #1).
- **[4]** Sửa: `tools/tests/test_case_gate.py`.
- **[5]** Test `evaluate` với `test_common__C01[x_create]` và `test_x_create_is_public` (`passed`, có vết `op="x_create"`,
  status 200) → `"C01"` không vào `found` của `x_create` và không vào case chung.
- **[6]** Đỏ trên `case_gate.py` đã đột biến (bỏ vế lọc) — ghi lệnh; xanh trên mã hiện tại.

## FIX-050 cho B0-05, FIX-051 cho B5-01 — trả khoá lặng lẽ có hai bản (NO-074)

- **[1–3]** "Trả khoá; Redis hỏng thì `WARNING` rồi bỏ qua (TTL dọn hộ), không che lỗi của thân" có ở
  `packages/messaging/locks.py:103` (`SafeLock._release_quietly`, riêng tư) và `apps/ml/runtime/gpu.py:129`
  (`_Keeper._release`).
- **[4]** FIX-050: `packages/messaging/locks.py` + test của `packages/messaging`. FIX-051: `apps/ml/runtime/gpu.py` + test của
  `apps/ml/runtime`.
- **[5]** B0-05 công khai `release_quietly(token)` (docstring nói rõ khi nào dùng thay `release`); B5-01 gọi
  `runner.run(lock.release_quietly(token))`, xoá bản chép. Tên sự kiện log giữ như test hiện có đòi hỏi, hoặc ghi rõ đổi.
- **[6]** Test B5-01: Redis hỏng lúc trả khoá GPU → một `WARNING` từ đúng một nguồn, thân không bị che; test chốt `gpu.py` không
  còn tự bắt lỗi trả khoá (AST hoặc đột biến) — đỏ trên mã hiện tại.

---

> **Giao việc FIX-052..FIX-059 (đợt 3).** Tiếp yêu cầu ngày 2026-09-22 ("mỗi session 12 nợ … cho đến khi fix hết"). Đợt 3 nhận
> các nợ mã do đợt 2 và các phiên review đợt 2 tìm ra: NO-075, NO-076, NO-077, NO-078, NO-080. Hai worktree:
> `fix/b0-04-key-layout-debts` (FIX-054..058, NO-076, NO-077) chạy ngay; `fix/b0-01-gate-log-debts` (FIX-052, 053, 059,
> NO-075, NO-078, NO-080) chạy sau khi `fix/b1-01-parallel-refresh-flake` (dòng NO-078) và `fix/b0-03-migration-tool-debts`
> (dòng NO-080) vào `main`. **Không có FIX:** NO-079 cùng NO-050, NO-071 (hiến chương/prompt — người điều phối, chờ người
> dùng quyết nơi sửa). Luật chung như đợt 1–2; trần 2 lượt verify cùng lúc.

## FIX-052 cho B0-01 — chép mẫu golden hỏng thì mất bảng cổng (NO-075)

- **[1–3]** `tools/verify/steps.py:267` `export_contract_samples()` chạy trước `_print_table` và không bắt lỗi: thư mục ra thiếu
  hay không ghi được → traceback, không có bảng, lượt 8/8 đạt vẫn thoát 1 (probe review: `VERIFY_OUT_DIR=/proc/rv`).
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** In bảng trước; lỗi `OSError` khi chép mẫu → một dòng lỗi rõ ra stderr (hoặc một dòng bảng "chép mẫu golden") và
  thoát 1. Không nuốt lỗi.
- **[6]** Test `VERIFY_OUT_DIR` không ghi được → bảng vẫn in đủ, có dòng lỗi chép mẫu, mã thoát 1; đỏ trên mã hiện tại.

## FIX-053 cho B0-01 — log cổng mất khi shell bọc bị cắt (NO-080)

- **[1–3]** Container `verify-run` AutoRemove, output chỉ đi qua stdout của client `docker compose run`; client chết → log
  bước 4–8 mất, chỉ còn mã thoát qua `docker wait` (W6-DBTOOLS, `e5d0247`).
- **[4]** Sửa: `tools/verify/in_container.sh` và/hoặc `tools/verify/steps.py`, `tools/verify/run.sh`; test dưới `tools/tests/`.
  Không đổi `deploy/compose/verify.yml` trừ khi cần mount mới (ghi lý do).
- **[5]** Toàn bộ output của lượt (bảng cổng, tóm tắt pytest, `coverage_gate`) đồng thời ghi ra file dưới thư mục mount host
  (`/src-out/…` → `.cache/src-out/…` của worktree), sống sót khi client compose chết; `run.sh` in đường dẫn file lúc bắt đầu.
- **[6]** Test: sau một lượt `verify` giả (bước rỗng/nhanh), file log trên thư mục ra có bảng cổng và mã thoát; đỏ trên mã hiện
  tại (không có file).

## FIX-054 cho B0-02, FIX-055 cho B0-04 — thân ULID có hai nguồn (NO-076)

- **[1–3]** `packages/storage/keys.py:26` `_ULID_RE` chép thân ULID của `packages/core/ids.py:35` `_ULID_BODY` (ảnh đại diện
  dùng ULID trần không tiền tố; `core/ids.py` chỉ phơi `is_id(prefix, value)`).
- **[4]** FIX-054: `packages/core/ids.py` + test của `packages/core`. FIX-055: `packages/storage/keys.py` + test của
  `packages/storage`.
- **[5]** B0-02 phơi hàm kiểm thân ULID không tiền tố (vd `is_ulid(value)`), `is_id` dùng lại nó; B0-04 dùng trong `avatar`,
  xoá `_ULID_RE`.
- **[6]** Test một nguồn (đột biến `_ULID_BODY` làm test storage đỏ, hoặc `keys` không còn hằng regex ULID) — đỏ trên mã hiện tại.

## FIX-056 cho B0-02, FIX-057 cho B0-04, FIX-058 cho B5-01 — bố cục tiền tố lượt tải lên có hai nguồn (NO-077)

- **[1–3]** `packages/ml_contracts/payloads.py:115` `_upload_prefix` dựng lại `projects/{prj}/floors/{L-…}/uploads/{upl}/` của
  `packages/storage/keys.py:64` `upload_prefix` (`ml_contracts` không được nhập `storage`).
- **[4]** FIX-056: `packages/core/object_keys.py` + test. FIX-057: `packages/storage/keys.py` + test. FIX-058:
  `packages/ml_contracts/payloads.py` + test.
- **[5]** Dời phần bố cục dùng chung (tiền tố lượt tải lên, dựng từ id đã kiểm) xuống `packages/core/object_keys.py`; `storage`
  và `ml_contracts` cùng gọi, xoá bản dựng lại. Nếu dời làm `core` phải biết quá nhiều về bố cục của `storage` (vd kéo theo
  mọi hàm dựng khoá), dừng và `ask` — phương án khác là `➖` kèm lý do.
- **[6]** Test một nguồn cho tiền tố lượt tải lên, đỏ trên mã hiện tại.

## FIX-059 cho B0-05 — worker Celery thử để logger gốc ở ERROR (NO-078)

- **[1–3]** `packages/testing/fixtures/messaging.py:149` `start_worker(...)` dùng `loglevel` mặc định `"error"`; `app.log.setup`
  chiếm logger gốc (thay handler, đặt mức 40) và không trả lại → `WARNING` của test chạy sau không vào báo cáo đỏ.
- **[4]** Sửa: `packages/testing/fixtures/messaging.py` + test của fixture (dưới `packages/testing/` hay `packages/messaging/tests/`).
- **[5]** Fixture không để lại dấu trên logger gốc: nối một receiver vào `celery.signals.setup_logging` cho app thử (Celery
  5.6.3 chỉ bỏ cấu hình logger gốc khi tín hiệu này có receiver — `worker_hijack_root_logger=False` KHÔNG đủ, logger gốc vẫn bị
  đặt mức 40; probe P9 của review `fix/b1-01-parallel-refresh-flake`), hoặc lưu mức + handler rồi trả lại khi worker dừng.
- **[6]** Test: mức và handler của logger gốc trước và sau fixture worker bằng nhau; đỏ trên mã hiện tại.

---

> **Giao việc FIX-060..FIX-064 (đợt 4).** Tiếp yêu cầu ngày 2026-09-22. Đợt 4 nhận các nợ mã do phiên review đợt 2–3 tìm ra:
> NO-081, NO-082, NO-088, trên một nhánh `fix/b0-04-layout-and-c11-debts` (một worker, tiết kiệm RAM). NO-087 (Nit, W10) vào đợt
> sau khi `fix/b0-01-gate-log-debts` hợp nhất. **Không có FIX ở đợt này:** NO-083..NO-086 (phiên B0-08 đang chạy song song ghi;
> chủ là AppFront/B0-09, B0-08 v2, B5-01·B0-05, FE/B4-01 — người điều phối xét sau khi B0-08 hợp nhất), NO-079 cùng NO-050,
> NO-071 (hiến chương/prompt — chờ người dùng). Luật chung như đợt 1–3; trần 2 lượt verify cùng lúc.

## FIX-060 cho B0-02 — `upload_prefix_of` chỉ kiểm phần đầu khoá (NO-088)

- **[1–3]** `packages/core/object_keys.py:74` `upload_prefix_of` (công khai, docstring "khoá không tin") trả tiền tố hợp lệ cho
  `…/uploads/{upl}/../../../../x` hay `…/pages//0.png` (probe P4 review `fix/b0-04-key-layout-debts`).
- **[4]** Sửa: `packages/core/object_keys.py` + test của `packages/core`.
- **[5]** `check_key(key)` ở dòng đầu (fail-closed); không đổi hành vi với khoá hợp lệ.
- **[6]** Ca `…/uploads/{upl}/../x` và `…//…` trong test từ chối — đỏ trên mã hiện tại.

## FIX-061 cho B0-02, FIX-062 cho B0-04, FIX-063 cho B5-01 — bố cục `runs/…/` và `ml/models/…/` có hai nguồn (NO-081)

- **[1–3]** `packages/storage/keys.py:63` (`runs/{run}/{step}/` trong `run_artifact`), `:75` (`ml/models/{mdl}/` trong
  `model_artifact`); `packages/ml_contracts/payloads.py:26` `MODELS_PREFIX`, `:110`, `:132`, `:297` dựng lại cùng bố cục.
- **[4]** FIX-061: `packages/core/object_keys.py` + test. FIX-062: `packages/storage/keys.py` + test. FIX-063:
  `packages/ml_contracts/payloads.py` + test.
- **[5]** Lõi giữ đúng phần bố cục mà `ml_contracts` phải kiểm (tiền tố lượt chạy của một bước, tiền tố model), theo cùng luật đặt
  của FIX-056 (lõi giữ bố cục mà gói không nhập `storage` được phải kiểm; hàm dựng khoá đầy đủ ở `storage`). `storage` dựng
  qua lõi; `ml_contracts` kiểm qua lõi, xoá `MODELS_PREFIX`/chuỗi dựng lại. Cùng lượt: `ml_contracts._id_of` dùng `check_id`
  của lõi (review `fix/b0-04-key-layout-debts` Nit #5).
- **[6]** Test một nguồn cho từng tiền tố (đột biến bố cục ở lõi làm test `storage` và `ml_contracts` cùng đỏ), đỏ trên mã hiện tại.

## FIX-064 cho B1-01 — bộ kiểm của C11 gọi lỗi đếm thật là "cửa sổ thứ hai" (NO-082)

- **[1–3]** `apps/api/auth/tests/test_refresh.py:503` `_assert_exact_fail_limit`: `bump` không nguyên khối (đột biến M1) →
  thông báo "bộ đếm mở cửa sổ thứ hai …, không phải đếm sai" dù thực là đếm sai (test vẫn đỏ, chỉ sai tên nguyên nhân).
- **[4]** Sửa: `apps/api/auth/tests/test_refresh.py`.
- **[5]** Chỉ báo cửa sổ thứ hai khi `counter[0] < trần` và `statuses.count(401) − trần == counter[0]`; còn lại báo đếm sai.
- **[6]** Ca thuần gọi thẳng bộ kiểm (`[401]×40`, không sự kiện mở, `(7, 360)`, 20) không được khớp "cửa sổ thứ hai" — đỏ trên mã
  hiện tại.

---

> **Giao việc FIX-065..FIX-067 (đợt 5).** Tiếp yêu cầu ngày 2026-09-22. Đợt 5 nhận ba nợ công cụ cổng/test do đợt 3 và review
> của nó tìm ra: NO-087, NO-089, NO-090, trên nhánh `fix/b0-01-gate-log-followups` (một worker, chạy song song đợt 4 vì khác
> vùng file). Luật chung như đợt 1–4; trần 2 lượt verify cùng lúc.

## FIX-065 cho B0-01 — log cổng không có traceback khi lượt verify ném lỗi (NO-089)

- **[1–3]** `tools/verify/steps.py:295` `with _tee_output(...)`: bước ném lỗi lạ → `_tee_output` trả fd 1/2 trong `finally` rồi
  ngoại lệ mới nổi lên; traceback ra stderr gốc, log host dừng ở dòng output cuối, không "mã thoát" (probe P3 review
  `fix/b0-01-gate-log-debts`).
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps*.py`.
- **[5]** Trong khối `with`: `except Exception` → in traceback (vào log), `rc = 1`, vẫn in "mã thoát". Không nuốt lỗi (mã thoát
  khác 0, traceback có trong log và stderr).
- **[6]** Test: bước ném `RuntimeError` → log có `Traceback` và "mã thoát: 1"; đỏ trên mã hiện tại.

## FIX-066 cho B0-01 — log cổng dồn mãi (NO-090)

- **[1–3]** `tools/verify/run.sh:93-97` tạo một file `.cache/src-out/verify/*.log` mỗi lượt, không dọn; `gc` không đụng tới;
  `in_container.sh` chép cả `.cache` vào `/tmp/w` mỗi lượt.
- **[4]** Sửa: `tools/verify/run.sh` (và `tools/verify/in_container.sh` nếu cần bỏ `.cache/src-out/verify` khỏi bản chép),
  test dưới `tools/tests/`.
- **[5]** Giữ N file mới nhất (vd 20) trước khi tạo file mới; hằng có tên và lý do. Không đụng file khác trong thư mục.
- **[6]** Test: thư mục có N+k file → sau khi dọn còn đúng N file mới nhất; đỏ trên mã hiện tại.

## FIX-067 cho B0-05 — worker Celery thử để dấu cấp tiến trình (NO-087)

- **[1–3]** Sau worker thử (kể cả sau FIX-059): `os.environ` giữ `CELERY_LOG_LEVEL`, `CELERY_LOG_FILE`, `_MP_FORK_LOGLEVEL_`,
  `_MP_FORK_LOGFILE_`, `_MP_FORK_LOGFORMAT_`; `logging.captureWarnings(True)`; bộ lọc `warnings` 'always'. Ảnh hưởng đọc được ~0.
- **[4]** Sửa: `packages/testing/fixtures/messaging.py` + test của fixture.
- **[5]** Fixture lưu và trả các khoá môi trường đó và trạng thái `captureWarnings`/bộ lọc khi worker dừng; hoặc `➖` kèm chứng minh
  vô hại (ghi rõ lý do đứng được).
- **[6]** Test trước = sau cho các khoá môi trường và `captureWarnings`; đỏ trên mã hiện tại.

---

> **Giao việc FIX-068..FIX-069 (đợt 6).** Tiếp yêu cầu ngày 2026-09-22. Hai nợ P3 do review `fix/b0-01-gate-log-followups` tìm
> ra: NO-092, NO-093, trên nhánh `fix/b0-01-gate-log-guard` (một worker). Luật chung như đợt 1–5; trần 2 lượt verify cùng lúc.

## FIX-068 cho B0-01 — dọn log cổng hỏng thì chặn cả cổng (NO-092)

- **[1–3]** `tools/verify/run.sh:101-102`: `find`/`rm` dọn log cũ (FIX-066) chạy dưới `set -euo pipefail`; `rm` gặp log đang bị giữ
  (Windows "Device or resource busy") → rc 123, docker không được gọi (probe P2x review `fix/b0-01-gate-log-followups`).
- **[4]** Sửa: `tools/verify/run.sh`, test dưới `tools/tests/`.
- **[5]** Dọn log là việc phụ: hỏng → một dòng cảnh báo ra stderr, cổng vẫn chạy, mã thoát là mã của cổng.
- **[6]** Test `rm` giả hỏng → docker (giả) vẫn được gọi, rc 0, có dòng cảnh báo; đỏ trên mã hiện tại.

## FIX-069 cho B0-05 — test FIX-067 không chốt phần `captureWarnings` (NO-093)

- **[1–3]** `packages/messaging/tests/test_tasks.py:539-561`: đột biến bỏ `captureWarnings(False)` hay bỏ điều kiện "showwarning đã
  đổi" trong `_restoring_process_logging` vẫn `2 passed` (probe P3m).
- **[4]** Sửa: `packages/messaging/tests/test_tasks.py`.
- **[5]** Kiểm hành vi: sau worker, ca clean — `captureWarnings(True)` phải còn đổi `warnings.showwarning` (tức logging không tự nhớ
  là đang bắt); ca preset — `captureWarnings(False)` phải trả đúng hàm gốc lưu trước khi bật.
- **[6]** Test mới đỏ dưới cả hai đột biến M1, M2 (bản đột biến chỉ trong `.cache/`), xanh trên mã hiện tại.

---

> **Giao việc FIX-082.** 2026-09-24, cổng đầy đủ bước 5 của B2-03 (`feature/b2-03-floors`) đỏ đúng hai test của B2-01. Người dùng
> chọn FIX ngay trên nhánh B2-03 (ngoại lệ K27 như FIX-003..005): commit riêng chỉ chạm hai file test của B2-01, trailer
> `Prompt: B2-01` + `Fix: FIX-082`; nhánh vào `main` bằng `--no-ff` để giữ trailer của cả hai prompt.

## FIX-082 cho B2-01 — test fallback phụ thuộc việc "chưa module nào cài" (không mã nợ)

- **[1–3]** `apps/api/projects/tests/test_parts.py::test_default_app_falls_back_to_discover` khẳng định `resolve(None, …) == []`, giờ thấy
  `['apps.api.floors.view_parts']`; `apps/api/projects/tests/test_routes_write.py::test_create_project_without_hook_ignores_floors` khẳng
  định `floors == []`, giờ hook `project.create_floors` của B2-03 tạo 1 tầng. Cả hai docstring tự ghi "hôm nay chưa module nào…".
- **[4]** Sửa: đúng hai file test trên. Cấm: mọi mã sản phẩm của B2-01.
- **[5]** Test tự dựng trạng thái "không ai cài" (`extensions.override(app, "view_parts", [])`) hoặc so với `discover` thay vì hằng rỗng;
  không xoá, không nới assert.
- **[6]** Hai test xanh cả trên `main` (chưa có `apps/api/floors`) lẫn trên nhánh B2-03 (đỏ trên nhánh trước khi sửa: bước 5 lượt 1).

## FIX-070 cho B0-08 — ảnh `web` dính CVE OpenSSL và CVE nginx (NO-102, NO-112)

- **[1]** Job `build` (B0-09) `trivy image web`: 2 CRITICAL có bản sửa (CVE-2026-31789, `libssl3`/`libcrypto3` 3.3.5-r0); nginx 1.28.0 trong dải CVE-2026-42945 (rewrite) và CVE-2026-42533 (map regex).
- **[2]** `docker build` ảnh `web` như `tools/ci/job.sh`, rồi `trivy … --severity CRITICAL --ignore-unfixed --exit-code 1` và `nginx -v` trên `main`.
- **[3]** Advisory nginx.org (đọc 2026-09-24, 63 mục): 1.30.5 là sàn cao nhất của dòng 1.30.x; 1.31.5 (mainline, dependabot `44b299f`) còn dính CVE-2026-90439.
- **[4]** Sửa: `deploy/docker/web.Dockerfile` dòng `FROM`. Cấm: mọi file khác.
- **[5]** Nền `nginxinc/nginx-unprivileged:1.30.5-alpine@sha256:4714e0b1…` (stable, digest tự tra `imagetools`); lượt 1 (1.29.8) bị REQUEST CHANGES vì 1.29 hết đời và còn trong dải CVE-2026-42945.
- **[6]** Không có test đơn vị (chỉ đổi ảnh nền): bằng chứng là trivy CRITICAL mã thoát 0 (0 lỗ hổng mọi mức), `nginx -v` = 1.30.5; test tĩnh ghim digest có sẵn ở `deploy/tests/test_dockerfiles.py`.
- **[7]** `fix(deploy): move web base image to nginx 1.30 stable` (`b232603`, `Prompt: B0-08`, `Fix: FIX-070`); review lượt 2 APPROVE 4,94/5, `run.sh verify` thoát 0 (3754 passed, tổng 99,06 % / 97,71 %).

---

> **Giao việc FIX-071..FIX-072.** 2026-09-22, phiên B0-09: người dùng duyệt cắt thời gian cổng verify (đo
> `backend/dieu-phoi/chay/B0-09/do-verify.log`). Hai worker song song, hai nhánh: FIX-071 `fix/b0-01-affected-tests`
> (`steps.py`, `affected.py`, `*gate*.py`), FIX-072 `fix/b0-01-fast-verify-startup` (`run.sh`, `in_container.sh`,
> `verify.yml`); hợp đồng chung `VERIFY_SCOPE` ∈ `affected|full`. Review gộp chung trên `fix/b0-01-fast-verify`.

## FIX-071 cho B0-01 — bước 5 chạy toàn bộ test ở mọi lượt worker (không mã nợ)

- **[1]** Bước 5 chạy ~2 460 test (~5,5–7 phút, đơn luồng) ở mọi lượt verify, kể cả nhánh chỉ sửa `tools/ci` (`spec-f071-affected-tests.md`).
- **[2]** `bash tools/verify/run.sh verify` trên `main` (2026-09-22); số đo từng bước ở `backend/dieu-phoi/chay/B0-09/do-verify.log`.
- **[3]** `tools/verify/steps.py` bước 5/5b luôn truyền cả cây test; không có khái niệm phạm vi.
- **[4]** Sửa: `tools/verify/affected.py` (mới), `tools/verify/steps.py`, `tools/coverage_gate.py`, `tools/case_gate.py` + test dưới `tools/tests/`. Cấm: `run.sh`, `in_container.sh`, `verify.yml` (của FIX-072).
- **[5]** `affected()` từ file bị chạm → thư mục test của đơn vị bị chạm + đơn vị import ngược (đồ thị `grimp`); file toàn cục/không ánh xạ được → chạy đủ; `integration` luôn `full`; `coverage_gate` bỏ ngưỡng tổng ở phạm vi `affected`; `case_gate` chỉ đòi case của op thuộc đơn vị đã chạy (fail-closed).
- **[6]** `tools/tests/test_affected.py` (mới) + test thêm ở `test_case_gate.py`, `test_coverage_gate*.py`, `test_steps_commands.py` (`f18546a`).
- **[7]** `fix(verify): run only affected tests on worker branches` (`f18546a`) và `docs(charter): describe affected-scope verify and shared work volume` (`5f254f7`), `Prompt: B0-01`, `Fix: FIX-071`. Review `docs/reviews/2026-09-22-fix-b0-01-fast-verify.md` REQUEST CHANGES 3,82/5: `run.sh verify --full` thoát 1 (8 failed — test không cô lập `VERIFY_SCOPE`), `affected()` bỏ sót nạp động của `apps/api` và đổi tên file (3 P1). Vòng sửa (`spec-f071-fix.md`) giao 2026-09-22 23:48, **không có commit**; nhánh không vào `main` (`git merge-base --is-ancestor f18546a main` sai).

## FIX-072 cho B0-01 — khởi động container verify chậm, volume theo worktree (NO-101, NO-108)

- **[1]** Từ lúc gọi `run.sh shell` tới lệnh đầu trong container 77 s; một prompt gọi ~99 lần (`spec-f072-fast-startup.md` §1). Mỗi worktree một volume `appback-verify-<tên>_appback-work` ~2 GB (NO-108); `run.sh gc` thoát 1 ở `tr` (NO-101).
- **[2]** Mốc thời gian tạm quanh build/`cp`/`chmod`/`uv sync`: lạnh 91,37 s, ấm 26,75 s, `cp -r /src` chiếm 62,27 s / 18,28 s (`bao-cao-fix072.md` §2.1).
- **[3]** `tools/verify/in_container.sh` chép cả `.cache` (1 356 file nhỏ) qua bind mount; `deploy/compose/verify.yml` khai `appback-work` không `name:`; `tools/verify/run.sh:150` `tr -c 'a-z0-9_-\n'`.
- **[4]** Sửa: `tools/verify/run.sh`, `tools/verify/in_container.sh`, `tools/verify/copy_work.sh` (mới), `deploy/compose/verify.yml`, `tools/tests/test_run_sh.py`, `tools/tests/test_copy_work.py` (mới). Cấm: file của FIX-071.
- **[5]** Chép bằng `tar` loại `.git`/`.cache`/`node_modules`/cache công cụ; build ảnh chỉ khi băm `verify.Dockerfile` đổi; volume `appback-work` tên cố định; `run.sh verify --full` → `VERIFY_SCOPE=full`; `tr -c 'a-z0-9_\n-'`; bỏ `git -C` hỏng dưới `MSYS_NO_PATHCONV`.
- **[6]** `test_copy_work.py`, test `--full`/`gc` trong `test_run_sh.py`: 18/18 qua; đo sau: lạnh 57,51 s, ấm 5,99 s (`bao-cao-fix072.md` §2.7). Bước 5–8 chưa chạy ở tác giả.
- **[7]** `perf(verify): cut container startup and share the work volume` (`e73af37`, `Prompt: B0-01`, `Fix: FIX-072`); review chung với FIX-071 REQUEST CHANGES 3,82/5 (finding #4, #5 P3 của FIX-072). Vòng sửa dừng giữa chừng, chỉ còn stash `a044496` ("FIX-072 vòng sửa review (dừng giữa chừng 2026-09-22): run.sh"); **không gộp**. NO-101, NO-108 đóng sau bằng FIX-083 (`531c690`).

---

> **Giao việc FIX-073..FIX-078.** 2026-09-23, phiên B2-01: B2-01 là prompt đầu tiên mount route ghi được bảo vệ và có cột
> Khoá khác rỗng ở BE-BIND, làm lộ sáu lỗi của chủ khác. Người dùng chọn gộp một nhánh `fix/verify-unblock-c10-node`
> (mỗi FIX một commit, trailer riêng); vào `main` bằng squash `d461ec8`. Review lượt 1 REQUEST CHANGES 4,69/5, lượt 2
> APPROVE 4,97/5 (`docs/reviews/2026-09-23-fix-verify-unblock-c10-node{,-round-2}.md`).

## FIX-073 cho B0-06 — C10 chung không đạt được, thân mồi lọt kho golden (NO-127, NO-134)

- **[1]** `test_common__C10[projects_create_project|projects_update_project|projects_delete_project]` đỏ (assert 202 lệch content). Sau bản mồi đầu: bước 7 H1 hỏng `createdAt` ở 3 mẫu `C10-*.json` (NO-134).
- **[2]** Worktree tạm `--detach` gộp `feature/b2-01-projects-summaries@2b5d28d`, `pytest apps/api/core/tests/test_common.py -k "C10 or C22"` với bản test cũ: 3 failed (`B2-01/log-fix-c10-before.log`).
- **[3]** `apps/api/core/tests/test_common.py:196-207` gửi `json={}` tới id mẫu → lượt đầu luôn lỗi, BE-00 §7 xoá dòng idempotency nên không có gì để phát lại (`DEBT.md` NO-127). Thân mồi `{"mau":"c10"}` status 201 bị bộ ghi golden lưu làm mẫu thành công của op (NO-134).
- **[4]** Sửa: `apps/api/core/tests/test_common.py`. Cấm: bộ ghi golden B0-07, mã sản phẩm.
- **[5]** Mồi sẵn dòng `completed` như C22 mồi `in_progress`, một hàm `_seed` chung, `state` kiểu `Literal["in_progress","completed"]`; trong C10 `monkeypatch.delenv(SAMPLES_ENV)` để lượt phát lại không ghi golden (C01 vẫn là nguồn mẫu 2xx).
- **[6]** Sau sửa `-k "C10 or C22"` 6 passed (`B2-01/log-fix-c10-worktree-check.log`); cổng lượt 2 bước 7 H1 đạt.
- **[7]** `68c872e` `test(core): seed a completed record in the common c10 case`, `e2b791d` `test(core): type the idempotency seed state` (finding 3 lượt 1), `950a791` `test(core): keep C10's fake replay body out of golden samples` (`Prompt: B0-06`, `Fix: FIX-073`); squash `d461ec8`; verify lượt 2 thoát 0, 8/8, 2796 qua.

## FIX-074 cho B0-08 — `node` 26 thiếu `libatomic1` trong ảnh verify (NO-126)

- **[1]** `main` đỏ bước 5: 13 failed + 66 errors (`tools/contract/tests/*`, `test_golden_issue_token__C01`), `node` thoát 127 `libatomic.so.1: cannot open shared object file`.
- **[2]** Verify tích hợp sau gộp B2-05a (`f797ba9`) trên `main`.
- **[3]** Dependabot PR #3 (`3c266b8`) nâng `node:20` → `node:26-bookworm-slim` ở `deploy/docker/verify.Dockerfile:4`; binary `node` chép sang nền Python không có `libatomic1` (`DEBT.md` NO-126).
- **[4]** Sửa: `deploy/docker/verify.Dockerfile`. Cấm: mọi file khác.
- **[5]** Thêm `libatomic1` vào `apt-get install` sẵn có, sửa chú thích "Node 20" (người dùng chọn giữ node 26).
- **[6]** Không có test đơn vị (đổi ảnh): `node --version` v26.10.0 thoát 0; `pytest tools/contract/tests packages/testing/golden/tests apps/api/core/tests` 395 passed, 0 failed (`B2-01/log-fix-shell-node-pytest.log`).
- **[7]** `fix(docker): install libatomic1 for node 26 in the verify image` (`07bd7c1`, `Prompt: B0-08`, `Fix: FIX-074`); squash `d461ec8`.

## FIX-075 cho B0-01 — cột Khoá giữ backtick, `charter.py` thiếu phủ nhánh (NO-128, NO-133)

- **[1]** `apps/api/core/tests/test_routes.py::test_permission_keys_match_bind_rows` đỏ (`'project.create' == '`project.create`'`), `apps/api/access/tests/test_deps.py::test_role_key_on_bind_route_fails_the_route_scan` đỏ. Sau sửa đầu: bước 5 review lượt 1 hỏng `[độ phủ nhánh tập file bị chạm < 90%] 83.33%`.
- **[2]** Bước 5 của B2-01; review lượt 1 `run.sh verify` @ `165d9fc` thoát 1.
- **[3]** `tools/charter.py:115` `lock=cells[col_lock].strip()` không `_strip_markdown`; `tools/charter.py` thiếu dòng 40, 57, 66, nhánh 46->48, 48->50 (`DEBT.md` NO-128, NO-133).
- **[4]** Sửa: `tools/charter.py`, `tools/tests/test_charter.py`.
- **[5]** `lock=_strip_markdown(cells[col_lock])` như cột op/chủ; 5 test đường lỗi phân tích bảng bằng `_write_table`; `test_khoá_bỏ_backtick` không ghim hàng 25 của BE-BIND thật.
- **[6]** `test_khoá_bỏ_backtick` + 5 test lỗi bảng; `tools/charter.py` 100 % dòng và nhánh (thân `45f7747`).
- **[7]** `77acfb8` `fix(tools): strip markdown from the bind lock column`, `45f7747` `test(tools): cover charter table parsing errors` (`Prompt: B0-01`, `Fix: FIX-075`); squash `d461ec8`.

## FIX-076 cho B0-06 — C05 parametrize kép làm `case_gate` tách sai op (NO-129)

- **[1]** `case_gate` báo thiếu C05 cho mọi op được bảo vệ dù test xanh.
- **[2]** Bước 5b của B2-01; id test `test_common__C05[chuoi-rac-projects_create_project]`.
- **[3]** `apps/api/core/tests/test_common.py:128-133` parametrize `token` × `operation`; `_TEST_COMMON_RE` ở `tools/case_gate.py:294` chỉ tách đúng op khi id là `test_common__C05[<op>]` (`DEBT.md` NO-129).
- **[4]** Sửa: `apps/api/core/tests/test_common.py`. Cấm: `tools/case_gate.py`.
- **[5]** Lặp `BAD_TOKENS` trong thân test, chỉ parametrize theo op.
- **[6]** `case_gate` trên worktree tạm gộp B2-01: 5 op `projects_*` đều "đạt" C05 (`B2-01/log-fix-c05-gate-check.log`); cổng lượt 2 bước 5b đạt.
- **[7]** `test(core): loop bad tokens in c05 body, not a second parametrize` (`8a61c20`, `Prompt: B0-06`, `Fix: FIX-076`); squash `d461ec8`.

## FIX-077 cho B0-03 — test `new_revision` dùng mã prompt thật (NO-131)

- **[1]** 4 test đỏ khi B2-01 có revision `r20260923_b2_01`: `test_creates_revision_with_charter_name`, `test_revision_date_read_from_clock_at_call_time`, `test_second_revision_for_same_prompt_is_rejected`, `test_fix_revision_allowed_once`.
- **[2]** Worktree tạm gộp `feature/b2-01-projects-summaries@2b5d28d`, bản test cũ: 4 failed + 10 passed (`B2-01/log-fix077-merged-before.log`).
- **[3]** `packages/db/tests/test_new_revision.py:65-107` dùng `B2-01` trên bản sao `versions` thật; luật một-revision-mỗi-prompt (BE-00 §6.1) (`DEBT.md` NO-131).
- **[4]** Sửa: `packages/db/tests/test_new_revision.py`.
- **[5]** Mã mẫu `B9-98` (cùng họ head mẫu `b9_99`), một hằng `CODE`/`CODE_LOWER` dùng chung.
- **[6]** Sau sửa 14 passed cả trên nhánh lẫn bản gộp B2-01 (`B2-01/log-fix077-branch.log`, `log-fix077-merged-after.log`).
- **[7]** `test(db): use an unused prompt code in new_revision tests` (`165d9fc`, `Prompt: B0-03`, `Fix: FIX-077`); squash `d461ec8`.

## FIX-078 cho B0-09 — admin giả của H2 không có dòng `users` (NO-132)

- **[1]** `tools/ci/tests/test_h2.py::test_main_real_app_passes` đỏ (`assert 1 == 0`), `ForeignKeyViolationError` trên `fk_project_memberships_user_id_users` → 500 ở `POST /api/projects` (cổng M của B2-01: 3014 qua / 1 hỏng).
- **[2]** Worktree tạm gộp B2-01, `pytest tools/ci/tests/test_h2.py::test_main_real_app_passes` → 1 failed (`B2-01/log-fix-round2-h2-before.log`).
- **[3]** `tools/ci/h2.py:336-340` `_admin_header` sinh `usr_<ULID>` không seed (`DEBT.md` NO-132; `B2-01/bao-cao-m-luot1.md` mục G).
- **[4]** Sửa: `tools/ci/h2.py`, `tools/ci/tests/test_h2.py`. Cấm: `apps/api/projects/service.py` (không bắt `IntegrityError` che lỗi).
- **[5]** Sinh `admin_id` một lần trong `main()`, `_migrate_and_seed()` chèn dòng `users` (vai admin, active) qua `_seed_admin_user`, `_admin_header()` dùng cùng id; sửa docstring.
- **[6]** `test_seed_admin_user_inserts_a_real_row`; `test_main_real_app_passes` qua sau sửa (`B2-01/log-fix-round2-h2-after.log`), chạy thật 8,4 s ở review lượt 2.
- **[7]** `fix(ci): seed the h2 fake admin as a real user row` (`e44e791`, `Prompt: B0-09`, `Fix: FIX-078`); squash `d461ec8`.

## FIX-079 — không dùng

Cấp ở `backend/dieu-phoi/chay/B2-01/bao-cao-m-luot1.md:118` cho lỗi "lượt phát lại C10 lọt kho golden" (NO-134), rồi người
điều phối gom vào FIX-073 (`spec-m-luot2.md:10`: "FIX-073 = C10 chung (NO-127, và NO-134)"); bản sửa là `950a791`
(`Fix: FIX-073`), thân squash `d461ec8` ghi "FIX-073 (B0-06, NO-127, NO-134)". Không commit nào mang `Fix: FIX-079`.

---

> **Giao việc FIX-080.** 2026-09-23, phiên B4-01: Dependabot gộp `redis` 6.4.0 → 8.1.0 (`d0bb175`, PR #5) thẳng trên GitHub,
> vào `main` qua `4f4f295`; bước 3 của mọi prompt đỏ. Một nhánh `fix/b0-05-redis8-mypy`, mỗi chủ một commit với trailer
> `Prompt:` của mình; gộp `--no-ff` `a26ee15`.

## FIX-080 cho B0-05, B0-06, B1-01 — `mypy --strict` đỏ sau bump redis-py 8 (NO-148)

- **[1]** Bước 3 `mypy --strict` trên `main`: 6 lỗi — `packages/messaging/streams.py:143` (3, `arg-type`/`index`), `packages/messaging/tests/test_locks.py:66` (`arg-type`), `apps/api/core/tests/test_internals.py:251` và `apps/api/auth/tests/test_units.py:180` (`redundant-cast`).
- **[2]** Xoá hết file B4-01 rồi chạy mypy trên `main`: vẫn đúng 6 lỗi (`B4-01/log-viec-a-tests-1.log`, mục BASELINE MYPY).
- **[3]** Stub redis-py 8 gộp kiểu trả `xread` RESP2/RESP3 (thêm nhánh `dict`) và đổi kiểu `Awaitable` của lệnh (`DEBT.md` NO-148, `B4-01/spec-fix-080.md` §1).
- **[4]** Sửa: B0-05 `packages/messaging/streams.py`, `tests/test_locks.py`, `tests/test_streams.py`; B0-06 `apps/api/core/tests/test_internals.py`; B1-01 `apps/api/auth/tests/test_units.py`. Cấm: `uv.lock`, `docs/charter/*`.
- **[5]** Thu hẹp kết quả `xread` ở một chỗ (`_stream_entries`, dạng không phải list → `TypeError`), không `type: ignore`/`cast` mù; bỏ `cast` thừa.
- **[6]** Test gọi thẳng `_stream_entries` cho hai nhánh `TypeError` (vòng sửa `B4-01/spec-fix-080-vs1.md`); mypy 6 → 0; `packages/messaging` 100 % / 100 %.
- **[7]** `dfc9a8b` `fix(messaging): narrow xread results for redis-py 8 stubs` (B0-05), `0d73ade` (B0-06), `58b932c` (B1-01), `cc57a74` `test(messaging): cover RESP3 guards of the xread narrowing` (B0-05), đều `Fix: FIX-080`; review `docs/reviews/2026-09-23-fix-b0-05-redis8-mypy.md` APPROVE 4,64/5, verify thoát 0, 8/8, 3029 qua; gộp `a26ee15`, đóng NO-148 ở `5ec6505`; nợ review NO-151..NO-153.

---

> **Giao việc FIX-081.** 2026-09-23, phiên B7-01: review lượt 1 B7-01 finding 3 (P1). Người dùng chọn FIX ngay trên nhánh
> B7-01 (ngoại lệ K27 như FIX-082): commit riêng chỉ chạm test của B0-06, trailer `Prompt: B0-06` + `Fix: FIX-081`; gộp `--no-ff`.

## FIX-081 cho B0-06 — test dò router giả định một router mỗi module (NO-163)

- **[1]** Bước 5 hỏng ở `apps/api/core/tests/test_app.py::test_discover_routers_finds_real_modules` khi `apps/api/telemetry` khai hai router (#9 bảo vệ, #37 công khai).
- **[2]** `run.sh verify` của review lượt 1 B7-01 (`docs/reviews/2026-09-23-feature-b7-01-telemetry-flags-metrics.md`, bảng cổng bước 5).
- **[3]** `apps/api/core/tests/test_app.py:158` `names == sorted(set(names))`, trong khi `discover_routers` (`apps/api/core/app.py:89-96`) nhận `ROUTERS: tuple[APIRouter, ...]` (`DEBT.md` NO-163).
- **[4]** Sửa: `apps/api/core/tests/test_app.py`. Cấm: mã sản phẩm của B0-06.
- **[5]** `assert names == sorted(names)` và `assert sorted(set(names)) == on_disk` (giữ ý "không sót module").
- **[6]** Test sửa xanh với module hai router thật (`apps/api/telemetry`); bước 5 review lượt 2 đạt.
- **[7]** `test(core): allow several routers per module in discovery test` (`f15437c`, `Prompt: B0-06`, `Fix: FIX-081`); review B7-01 lượt 2 APPROVE 4,84/5 (finding 3 đóng); gộp `--no-ff` `591eaf6`.

## FIX-100 cho B0-08 — ảnh `web` không build vì ảnh node ghim bỏ `corepack` (NO-174)

- **[1]** `docker build` ảnh `web` trên `main` thoát 1: `/bin/sh: 1: corepack: not found`, mã 127 ở tầng `build`.
- **[2]** `docker build -f deploy/docker/web.Dockerfile --build-context appfront=… .` trên `main` @ `9f11ddf`.
- **[3]** Dependabot `3c266b8` ghim `node:26-bookworm-slim@sha256:582460f6…` (node 26.9.0, npm 11.19.1): `/usr/local/bin` không có `corepack`.
- **[4]** Sửa: `deploy/docker/web.Dockerfile`, `deploy/tests/test_dockerfiles.py`. Cấm: mọi file khác.
- **[5]** `RUN npm install -g pnpm@9.4.0` (AppFront @ `9cf0b0bf` không khai `packageManager`; giữ đúng bản pnpm cũ).
- **[6]** `test_dockerfile_web_installs_pnpm_without_corepack`: đỏ trên `main` (AssertionError "tầng node #0 còn dùng corepack"), xanh sau sửa (36 passed); build web thoát 1 → 0.
- **[7]** `fix(deploy): install pnpm with npm instead of corepack` (`792e98b`, `Prompt: B0-08`, `Fix: FIX-100`); review lượt 2 APPROVE.

## FIX-102 cho B0-01 — uv base image không ghim làm `uv.lock` trôi định dạng (NO-175)

- **[1]** `bash tools/verify/run.sh lock` sau khi thêm ràng buộc `redis` (FIX-085) sinh diff 316 dòng thay đổi ngoài dòng ràng buộc `redis` trong `uv.lock` — mọi entry `{ name = ... }` thêm `marker = "platform_machine == 'x86_64' and sys_platform == 'linux'"`.
- **[2]** Trên `fc32836` (chưa ghim): `bash tools/verify/run.sh lock` → so `uv.lock` trước/sau, 632 dòng đổi (316 `-`/316 `+`).
- **[3]** `deploy/docker/verify.Dockerfile:6` `FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim` (tag trần, không digest): uv trong ảnh verify là `0.9.30`, đổi cách hiển thị marker so với bản đã sinh `uv.lock` hiện có trên `main`.
- **[4]** Sửa: `deploy/docker/verify.Dockerfile` (B0-01). Cấm: mọi file khác.
- **[5]** Ghim cả hai `FROM` (uv, node) theo tag+digest hiện tại (không đổi bản uv/node đang chạy — chỉ ngăn trôi tiếp).
- **[6]** `tools/tests/test_verify_dockerfile.py::test_every_from_line_pins_tag_and_digest` — đỏ trên `main` (`FROM` không có `@sha256:`), xanh sau sửa.
- **[7]** `run.sh lock` hai lượt sau khi ghim → diff rỗng (ổn định). Commit `17774f7` (`Prompt: B0-01`, `Fix: FIX-102`); review APPROVE 4,50/5, cổng đầy đủ thoát 0.

## FIX-083 cho B0-01 — NO-101, NO-164, NO-103, NO-106 (phần), NO-108, NO-130

- **[1]** Năm nợ cổng verify: `tr` sai dải ký tự chặn `gc` an toàn (NO-101/NO-164); test Testcontainers thật bị `--ci-split` xếp nhầm nhóm `unit` (NO-103); hằng ảnh ghim Postgres/Redis/MinIO chép tay giữa `services.py` và `h2.py` (NO-106 phần); mỗi worktree một ảnh/volume verify riêng (NO-108); coverage thiếu `greenlet` nên bỏ sót dòng/nhánh sau `await` async (NO-130).
- **[2]** Trên `main` (`fc32836`): `run.sh gc` thoát 1 ngay (lỗi `tr`); ghi đè 9 file sản xuất về `fc32836` rồi chạy đúng test của nhánh → 12 failed + 1 error (đo được ở review, xem §4.1 của `docs/reviews/2026-09-24-fix-debt-01-tooling.md`).
- **[3]** `tools/verify/run.sh:150`, `deploy/compose/verify.yml:40-41`, `packages/testing/fixtures/services.py:29-32` ↔ `tools/ci/h2.py:73-75`, `pyproject.toml:102-108` (gốc).
- **[4]** Sửa: `tools/verify/run.sh`, `tools/tests/test_run_sh.py`, `tools/tests/test_services.py`, `packages/testing/fixtures/services.py`, `tools/pinned_images.py` (mới), `tools/tests/test_pinned_images.py` (mới), `deploy/compose/verify.yml`, `tools/tests/test_verify_yml.py` (mới), `pyproject.toml` (gốc).
- **[5]** `tr -c 'a-z0-9_\n-' '-'` (đưa `-` về cuối tập); marker `@pytest.mark.ci_integration` tường minh; hằng ảnh dời sang `tools/pinned_images.py` (nguồn chung cho `services.py`/`h2.py`); `deploy/compose/verify.yml` ghim `image: appback-verify:local` + `volumes.appback-work.name: appback-work`; `pyproject.toml` thêm `concurrency = ["thread", "greenlet"]`.
- **[6]** `test_gc_lowercases_and_normalizes_worktree_names`, marker `ci_integration` trên test ephemeral, `tools/tests/test_pinned_images.py` (100% dòng+nhánh), `tools/tests/test_verify_yml.py` — đỏ trên `main`, xanh trên nhánh (114 passed, mục 3 của báo cáo tác giả).
- **[7]** Commit `531c690`, `7eaa0f9`, `ebe32cc`, `7ff240a` (`Prompt: B0-01`, `Fix: FIX-083`); review APPROVE 4,50/5, cổng đầy đủ thoát 0.

## FIX-101 cho B0-01 — NO-105 (phần `tools/verify/steps.py`)

- **[1]** CI chạy bước 8 (OpenAPI) ở chế độ xuất, không so với bản tham chiếu vì `openapi.json` gốc bị `.gitignore`.
- **[2]** `git show main:tools/verify/steps.py` dòng 220 vẫn `["--compare", "openapi.json"]`.
- **[3]** `tools/verify/steps.py::step_openapi`.
- **[4]** Sửa: `tools/verify/steps.py`, `tools/tests/test_steps_commands.py`.
- **[5]** `--compare docs/contracts/openapi.json` thay `openapi.json` (bản tham chiếu đã commit trên `main @ 280a22d`).
- **[6]** `test_bước_8_integration_so_với_bản_commit` — đỏ trên `main`, xanh trên nhánh; reviewer chạy lại `VERIFY_BRANCH=integration bash tools/verify/run.sh verify --steps 8` độc lập, mã thoát 0.
- **[7]** Commit `ad9ecab` (`Prompt: B0-01`, `Fix: FIX-101`); review APPROVE 4,50/5, cổng đầy đủ thoát 0.

## FIX-085 cho B0-05 — NO-153 (phần mã)

- **[1]** Dependabot có thể gộp thẳng bản major của `redis` vào `main` không qua cổng (gốc NO-148): `packages/messaging/pyproject.toml` khai `redis` không ràng buộc phiên bản.
- **[2]** Nguyên nhân gốc NO-148: bump `redis` 6.4.0 → 8.1.0 qua PR Dependabot gộp thẳng trên GitHub, không qua `verify`.
- **[3]** `packages/messaging/pyproject.toml:7`.
- **[4]** Sửa: `packages/messaging/pyproject.toml`; `uv.lock` chỉ qua `run.sh lock` (không sửa tay).
- **[5]** `redis>=8.1,<9`.
- **[6]** Không có test unit riêng (khai báo phụ thuộc tĩnh); bằng chứng: `uv.lock` sau `lock` có `{ name = "redis", specifier = ">=8.1,<9" }`, `uv sync --locked` không hỏng, và diff `uv.lock` ngoài dòng `redis` là 0 gói đổi bản (thuần định dạng của FIX-102).
- **[7]** Commit `5579b09` (`Prompt: B0-05`, `Fix: FIX-085`); review APPROVE 4,50/5, cổng đầy đủ thoát 0.

## FIX-084 cho B0-09 — NO-051, NO-105 (phần `job.sh`), NO-106 (phần `h2.py`), NO-110, NO-111, NO-113, NO-118 (phần `job.sh`), NO-153 (phần dependabot)

- **[1]** Tám nợ CI: `VERIFY_OUT_DIR` không ghi được ngoài container (NO-051); job `typecheck` không so OpenAPI với bản tham chiếu (NO-105 phần); `h2.py` chép tay hằng ảnh ghim (NO-106 phần); `pull_request` thiếu `types: [edited]` (NO-110); hai hành vi `job.sh` chưa có test (NO-111); trivy không thấy CVE nginx.org (NO-113); smoke CI dùng `API_HOST_PORT` đã bỏ (NO-118 phần); Dependabot gộp major không qua cổng (NO-153 phần dependabot).
- **[2]** Trên `main` (`fc32836`): ghi đè `tools/ci/h2.py`, `tools/ci/job.sh`, `.github/workflows/ci.yml`, `.github/dependabot.yml` về bản cũ rồi chạy đúng test của nhánh → phần lớn 16 test mới/sửa đỏ (đo được ở review §4.1).
- **[3]** `tools/ci/h2.py:73-75`, `tools/ci/job.sh` (nhiều hàm), `.github/workflows/ci.yml:9-10`, `.github/dependabot.yml:8-19`.
- **[4]** Sửa: `tools/ci/h2.py`, `tools/ci/job.sh`, `tools/ci/README.md`, `.github/workflows/ci.yml`, `.github/dependabot.yml`, `tools/ci/tests/test_workflows.py`.
- **[5]** `job_contract` tự đặt `VERIFY_OUT_DIR` ghi được cùng lúc với `CONTRACT_SAMPLES_DIR`; `job_typecheck` ép `VERIFY_BRANCH=integration`; `h2.py` nhập hằng ảnh từ `tools/pinned_images.py`; `pull_request.types` thêm `edited`; test mới chốt `job_lint_gitleaks`/`job_build_trivy`; `job_build_check_nginx_version` so `nginx -v` với `NGINX_MIN_VERSION=1.30.4`; smoke `/api/health`, `/api/ready` qua `WEB_HTTP_PORT`; `dependabot.yml` thêm `ignore` semver-major cho `uv`/`github-actions`/`docker`.
- **[6]** `test_job_contract_exports_writable_verify_out_dir`, `test_job_sh_typecheck_compares_committed_openapi_reference`, `test_ci_yml_pull_request_types_include_edited`, `test_job_lint_gitleaks_fails_closed_on_empty_git_history`, `test_job_build_trivy_mounts_host_sarif_dir`, `test_job_build_check_nginx_version_*`, `test_job_sh_smoke_uses_web_port_for_api_paths_not_api_host_port`, `test_dependabot_yml_ignores_semver_major_for_every_ecosystem` — đỏ trên `main`, xanh trên nhánh (114 passed).
- **[7]** Commit `844fea3`, `a99fabb`, `86b31b9` (`Prompt: B0-09`, `Fix: FIX-084`); review APPROVE 4,50/5, cổng đầy đủ thoát 0.

## FIX-088 cho B0-03 — savepoint nhả sớm kích `after_commit` (NO-140)

- **[1]** `on_after_commit` (`packages/db/hooks.py` `_on_commit`, nghe `Session.after_commit`) chạy callback khi một SAVEPOINT (`begin_nested`) được nhả, trước khi giao dịch ngoài commit — SQLAlchemy 2.0 bắn `after_commit` cả cho `SessionTransaction` lồng, `_on_commit` không phân biệt lồng/ngoài.
- **[2]** `packages/db/tests/test_hooks.py::test_on_after_commit__J09_savepoint_release_waits_for_the_outer_commit` trên `main`: mã thoát 1, `assert calls == ['trong']`.
- **[3]** `packages/db/hooks.py:_on_commit`.
- **[4]** Sửa: `packages/db/hooks.py`, `packages/db/tests/test_hooks.py`. Cấm: mọi file khác.
- **[5]** `_on_commit` bỏ qua lượt `after_commit` khi `session.get_nested_transaction()` còn trả về bản lồng (nghĩa là đang ở lượt release của savepoint); rollback ngoài sau đó vẫn bỏ được callback qua `after_soft_rollback` có sẵn.
- **[6]** `test_on_after_commit__J09_savepoint_release_waits_for_the_outer_commit` (Postgres thật, INSERT thật trong savepoint rồi rollback ngoài) — đỏ mã thoát 1 trên `main` → xanh trên nhánh.
- **[7]** Commit `3286027` (`Prompt: B0-03`, `Fix: FIX-088`); review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed).

## FIX-089 cho B0-05 — RESP3 ngầm, retry không tường minh, `event_id_key` chưa phơi, `REDIS_CACHE_URL` bắt buộc, worker/ml chưa có `/metrics` (NO-151, NO-152, NO-157, NO-085, NO-161)

- **[1]** Năm nợ messaging: docstring nói client streams "không đặt `protocol=3` nên luôn nhận RESP2" — sai sau bump redis-py 8.1 (NO-151); mỗi vai không đặt `retry` tường minh, đường trả response có thể chờ nhiều lượt hơn tưởng (NO-152); `_id_key` khai riêng ở `apps/api/streams/sse.py` trùng bản private của `packages/messaging/streams.py` (NO-157 nửa); `MessagingSettings.redis_cache_url` bắt buộc dù tiến trình `ml` không tới được `redis-cache` (NO-085 nửa); worker Celery và `ml` chưa có exporter `/metrics` (NO-161).
- **[2]** Trên `main`: `packages/messaging/tests/{test_redis,test_settings,test_streams,test_celery_app}.py` mới — mã thoát 2 (`ImportError` lúc thu thập: `ASYNC_RETRIES`, `event_id_key`, `start_metrics_exporter`).
- **[3]** `packages/messaging/{redis,settings,streams,celery_app}.py`.
- **[4]** Sửa: `packages/messaging/{redis,settings,streams,celery_app}.py` + test tương ứng. Cấm: mọi file khác.
- **[5]** Mọi client ghim `legacy_responses=True` tường minh; mỗi vai khai ngân sách retry riêng (`ASYNC_RETRIES=2`, `STREAM_RETRIES=1`, `SYNC_RETRIES=1`, backoff 0,05–0,2 s, `retry_on_error=[ConnectionError, TimeoutError]`); `streams.py` phơi `event_id_key` công khai; `redis_cache_url: str | None = None`, `cache_redis()`/`cache_redis_sync()` ném `RuntimeError` có tên biến khi thiếu; exporter `/metrics` gắn vào `worker_process_init` ở `celery_app.py` (dùng chung cho `apps/worker` và `apps/ml` qua `create_celery`). Vòng sửa round 2 (`917ce5a`): `messaging_env` đặt `METRICS_PORT=0` + xoá cache `ObservabilitySettings` hai đầu + receiver `worker_process_shutdown`, để không còn rò exporter thật vào tiến trình pytest (finding P1 lượt 1 của review core).
- **[6]** `test_streams_client_pins_the_legacy_list_form_of_xread`, `test_every_client_pins_the_retry_budget_of_its_role` + `test_a_dead_redis_costs_exactly_the_configured_number_of_retries` (Redis thật, `ephemeral_broker`, `admin.shutdown`), `test_event_id_key_orders_ids_by_milliseconds_then_sequence`, `test_a_process_without_the_cache_instance_loads_without_the_variable`, `test_every_celery_process_starts_the_metrics_exporter` + `test_a_test_worker_leaves_no_metrics_exporter_in_the_pytest_process` (round 2) — đỏ trên `main` → xanh.
- **[7]** Commit `19648c3`, vòng sửa `917ce5a` (`Prompt: B0-05`, `Fix: FIX-089`); review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed, tổng dòng 99,07 % / nhánh 97,72 %).

## FIX-090 cho B0-06 — `Role`/`ROLES` chép riêng, `_grant_everything` sai kiểu, `api_env` giữ cổng metric, chưa có metric RED (NO-097, NO-137, NO-159, NO-160)

- **[1]** `Role`/`ROLES` khai hai nơi (`apps/api/core/auth.py` vs `packages.domain.permissions`, NO-097); `_grant_everything` trả `None` thay vì `ProjectAccess` nên route đọc `ProjectAccess` qua tham số sẽ 500 (NO-137); fixture `api_env` để `METRICS_PORT` mặc định, mọi app test mở exporter thật (NO-159); chưa có metric HTTP chung kiểu RED (NO-160).
- **[2]** Trên `main`: `apps/api/core/tests/{test_permissions,test_common,test_fixtures,test_middleware}.py` mới — mã thoát 1 (7 failed) / `ImportError HTTP_DURATION_METRIC`.
- **[3]** `apps/api/core/{auth,middleware}.py`, `packages/testing/fixtures/api.py`, `apps/api/core/tests/test_common.py`.
- **[4]** Sửa: các file trên + test tương ứng. Cấm: mọi file khác (trừ FIX-103, xin phép riêng).
- **[5]** `apps/api/core/auth.py` nhập `Role`, `ROLES` từ `packages.domain.permissions`, xuất lại qua `__all__`; `_grant_everything(app, principal)` trả `ProjectAccess` thật; `api_env` đặt `METRICS_PORT=0`; `AccessLogMiddleware` ghi histogram `appback_http_request_duration_ms{route,method,status}`, `route` là mẫu đường qua `_route_label`. Vòng sửa round 2 (`b25530b`): `_red_count` khẳng định đúng một chuỗi nhãn trọn vẹn (bỏ phụ thuộc thứ tự chạy — finding P1 lượt 1) và kẹp nhãn `method` vào 9 method RFC 9110 + `-` (finding P2 lượt 1).
- **[6]** `test_core_auth_reuses_the_role_mirror_of_the_domain`, `test_grant_everything_overrides_with_a_typed_project_access`, `test_api_env_keeps_the_metrics_exporter_off`, `test_red_metric_labels_the_route_template_not_the_real_path` + `test_red_metric_folds_an_unknown_method_into_the_dash_label` (round 2) — đỏ trên `main` → xanh.
- **[7]** Commit `301bf67`, vòng sửa `b25530b` (`Prompt: B0-06`, `Fix: FIX-090`); review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed).

## FIX-091 cho B5-01 — `ml` đọc `SECRET_KEY` chỉ để lấy `APP_ENV`, tải mô hình ghim không thử lại (NO-085, NO-104, NO-161)

- **[1]** `apps/ml/celery_main.py` gọi `get_core_settings()` chỉ để đọc `APP_ENV`, buộc tiến trình `ml` nhận `SECRET_KEY`/`PUBLIC_BASE_URL` (NO-085 nửa); `packages/ml_contracts/pinned.py` tải mô hình ghim một lượt, không thử lại khi mạng chớp hay tệp tải dở (NO-104); `ml` chưa có exporter `/metrics` (NO-161 nửa).
- **[2]** Trên `main`: `apps/ml/runtime/tests/test_celery_main.py`, `packages/ml_contracts/tests/test_pinned.py` mới — mã thoát 1/2 (`ValidationError` / `ImportError FETCH_ATTEMPTS`).
- **[3]** `apps/ml/celery_main.py`, `apps/ml/runtime/settings.py`, `packages/ml_contracts/pinned.py`.
- **[4]** Sửa: các file trên + test tương ứng. Cấm: mọi file khác.
- **[5]** `MlEnvSettings` (đúng một trường `app_env`) thay `get_core_settings()`; `pinned.py` thêm `_fetch_file` thử lại `FETCH_ATTEMPTS=3` lượt, backoff nhân đôi từ `FETCH_BACKOFF_S=1,0` s trần `FETCH_BACKOFF_CAP_S=8,0` s cho cả lỗi mạng lẫn SHA lệch, lượt cuối chạy ngoài vòng lặp (R-14); `.part` + `os.replace` giữ nguyên (nguyên tử); `apps/ml` nhập điểm vào chung `create_celery` nên thừa hưởng exporter của FIX-089.
- **[6]** `test_celery_main_starts_without_the_signing_key[...]`, `test_fetch_retries_a_torn_download_until_the_sha_matches`, `test_fetch_gives_up_after_the_attempt_cap`, `test_fetch_backoff_grows_but_never_passes_the_cap`, `test_fetch_still_exits_2_when_the_pin_is_simply_wrong` (bộ mở giả `FlakyOpener`, không tải mạng) — đỏ trên `main` → xanh.
- **[7]** Commit `f7abc9f` (`Prompt: B5-01`, `Fix: FIX-091`); review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed).

## FIX-092 cho B4-01 — rò ba tài nguyên SSE khi `_finish` ném, bản sao `event_id_key` (NO-156, NO-157)

- **[1]** `AppRoute._finish` (idempotency → `commit()` → `after_commit_idle`) chạy **sau** khi handler đã trả `StreamingResponse`; nếu nó ném, generator `stream_body` không bao giờ chạy nên `finally` của nó (chỗ ZSET, chỗ toàn cục `stream_slots`, kết nối pool SSE) không bao giờ tới (NO-156); `apps/api/streams/sse.py` khai riêng `_id_key`, trùng bản của `packages/messaging/streams.py` (NO-157 nửa).
- **[2]** Trên `main`: `apps/api/streams/tests/test_sse.py` mới — mã thoát 1, 2 failed.
- **[3]** `apps/api/streams/{sse,router}.py`.
- **[4]** Sửa: hai file trên + `apps/api/streams/tests/test_sse.py`. Cấm: mọi file khác.
- **[5]** `open_stream` ghi `StreamContext` lên `request.state` ngay trước khi trả response, phơi `release_held(request)` idempotent; `StreamRoute(PublicRoute)` (mới, `router.py`) bọc `get_route_handler()`, gọi `release_held` khi bất kỳ bước nào sau handler ném; `sse.py` xoá `_id_key`, nhập `event_id_key` từ `packages.messaging.streams` (FIX-089).
- **[6]** `test_a_failure_after_the_handler_returns_every_held_resource` (`STREAM_MAX_GLOBAL=2`, 5 lượt mở liên tiếp, `_finish` ép ném, bắt được cả ba đường rò: 429 chỗ toàn cục, 503 pool cạn, `zcard` cuối khác 0), `test_sse_reuses_the_shared_event_id_key` — đỏ trên `main` → xanh.
- **[7]** Commit `99bc366` (`Prompt: B4-01`, `Fix: FIX-092`); review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed). Phần `AsyncSession` không rollback/close khi `_finish` ném vẫn mở: NO-186.

## FIX-103 cho B1-01 — `cast` thừa ở `apps/api/auth/sessions.py:585` (NO-097, hệ quả FIX-090)

- **[1]** FIX-090 làm `ROLES` thành `tuple[Role, ...]` nên `cast(Literal[...], ...)` ở `apps/api/auth/sessions.py:585` thành `redundant-cast`, `mypy --strict` đỏ.
- **[2]** Sau commit `301bf67` (FIX-090), trước khi sửa: `mypy --strict` mã thoát 1, `apps/api/auth/sessions.py:585 error: Redundant cast to "Literal['admin','engineer','viewer']"`.
- **[3]** `apps/api/auth/sessions.py:585`.
- **[4]** Sửa: `apps/api/auth/sessions.py` (1 dòng + 2 dòng comment). Cấm: mọi file khác — file thuộc B1-01, người điều phối cấp phép trước khi sửa (K27).
- **[5]** Bỏ `cast(...)` thừa; `x in ROLES` đã tự thu hẹp kiểu nhờ `ROLES: tuple[Role, ...]`.
- **[6]** Không test riêng (dọn kiểu tĩnh, không đổi hành vi); bằng chứng: `mypy --strict` đỏ → xanh (486 file).
- **[7]** Commit `e2ebeda` (`Prompt: B1-01`, `Fix: FIX-103`); commit riêng, đặt sau FIX-090, theo chỉ thị người điều phối. Review lượt 2 APPROVE `docs/reviews/2026-09-24-fix-debt-01-core-round-2.md` (4,77/5), cổng đầy đủ thoát 0 (3792 passed).

## FIX-093 cho B1-03 — lỗi thư vĩnh viễn bị nuốt khi token sau ném `TransientError` (NO-149)

- **[1]** `run_send_token_mail`: (a) `except MailRejectedError` không giữ `smtp_code` — log không phân biệt 550 với 554; (b) mã lỗi vĩnh viễn đầu tiên bị nuốt nếu token **sau** nó ném `TransientError`: lượt thử lại không còn thấy token đã cô lập (`sent_at`/`superseded_at` đã ghi) nên task "thành công", `on_failed` không bao giờ báo.
- **[2]** Trên `main`: `apps/api/auth_recovery/tests/test_jobs.py -k "logs_isolated_failure_before_later_transient or J03"` — mã thoát 1, 2 failed.
- **[3]** `apps/api/auth_recovery/jobs.py:65-78,131-134,152-166`.
- **[4]** Sửa: `apps/api/auth_recovery/jobs.py`, `apps/api/auth_recovery/tests/test_jobs.py`. Cấm: mọi file khác.
- **[5]** Log `token_mail_failed` (id + mã lỗi + `smtp_code`) ghi ngay lúc cô lập trong `_send_one`, không đợi cuối vòng; `mailer: Mailer` thay `Any`; `SELECT` lô thêm `ORDER BY created_at`.
- **[6]** `test_send_token_mail__logs_isolated_failure_before_later_transient`, `test_send_token_mail__J03` — đỏ mã thoát 1 trên `main` → xanh (2 passed).
- **[7]** Commit `19fbed6` (`Prompt: B1-03`, `Fix: FIX-093`); review APPROVE `docs/reviews/2026-09-24-fix-debt-01-modules.md` (4,78/5), cổng đầy đủ thoát 0 (3764 passed). Log trùng tên hai dạng (đếm đôi) + fixture thừa: NO-195 (mới).

## FIX-094 cho B2-01 — `UPDATE` không khoá thứ tự, thiếu test hai session `_checked(None)`, `user_out()` không ký URL avatar (NO-142, NO-136, NO-135)

- **[1]** `touch_projects` khoá các dòng `projects` bằng một `UPDATE … WHERE id IN (...)` theo thứ tự kế hoạch của Postgres chứ không theo `id` tăng dần như vòng lặp cũ — hai giao dịch gỡ người dùng cùng lúc có ≥ 2 dự án chung có thể deadlock lý thuyết (NO-142); `_checked(None)` khi dự án bị xoá mềm giữa cổng quyền và `UPDATE … RETURNING` không có test (NO-136); `UserOut.avatarUrl` luôn vắng vì đường ký URL thuộc B1-04 chưa cắm lúc viết (NO-135).
- **[2]** Trên `main`: `test_summaries.py -k touch_projects` mã thoát 1 (1 failed); `test_wire.py` mã thoát 1 (4/10 failed, đổi chữ ký `user_out`).
- **[3]** `apps/api/projects/{summaries,service,wire}.py`.
- **[4]** Sửa: ba file trên + test tương ứng. Cấm: mọi file khác (`apps/api/projects/memberships.py` ngoài whitelist T4, xem NO-193).
- **[5]** `touch_projects` thêm `SELECT … ORDER BY id FOR UPDATE` (id đã sắp) trước `UPDATE`; test hai session xen kẽ chốt nhánh `_checked(None)`; `user_out(row, storage)` ký `avatarUrl` qua `apps.api.me.avatar.avatar_url` (B1-04) khi có kho, `None` khi gọi thẳng không qua app.
- **[6]** `test_touch_projects_locks_then_updates_ids_in_sorted_order`, `test_write_changes_raises_not_found_when_deleted_between_gate_and_update`, `test_wire.py::test_user_out_*` — đỏ trên `main` → xanh (10/10, 2/2).
- **[7]** Commit `672b44b` (`Prompt: B2-01`, `Fix: FIX-094`); review APPROVE `docs/reviews/2026-09-24-fix-debt-01-modules.md` (4,78/5), cổng đầy đủ thoát 0 (3764 passed). Phần còn của NO-142 (guard lô rỗng): NO-193 (mới). Dây `avatarUrl` chưa có test route: NO-194 (mới).

## FIX-095 cho B2-05a — thiếu ca `render` ném `PdfiumError` → `FILE_CORRUPT` (NO-125)

- **[1]** Đường thân `with _open_page(...)` (`get_size`/`render`/`to_numpy` ném `PdfiumError`) không có test riêng; 100 % coverage không bắt vì dòng `except` đã phủ sẵn bởi ca mở trang hỏng.
- **[2]** Test coverage thuần (không sửa hành vi) — không có lượt đỏ theo nghĩa assert sai, chỉ thiếu ca gọi tới.
- **[3]** `packages/vision/preprocess/*.py` (`_open_page`).
- **[4]** Sửa: `packages/vision/preprocess/tests/test_pdf.py`, `packages/vision/preprocess/tests/test_geometry.py` (bọc lại dòng 132 ký tự). Cấm: mọi file khác.
- **[5]** `monkeypatch.setattr(pdfium.PdfPage, "render", …)` ném `PdfiumError` trong thân `with`, chốt nhánh `FILE_CORRUPT` cho lỗi trong thân chứ không chỉ lỗi mở trang.
- **[6]** `test_render_pdf_page_wraps_pdfium_error_raised_inside_open_page` — mới, xanh; `packages/vision` 100 %/100 % dòng+nhánh trong cổng.
- **[7]** Commit `c3e32b7` (`Prompt: B2-05a`, `Fix: FIX-095`); review APPROVE `docs/reviews/2026-09-24-fix-debt-01-modules.md` (4,78/5), cổng đầy đủ thoát 0 (3764 passed).

## FIX-096 cho B4-01 — test hạn hết không tất định, seed ít khoá hơn `BATCH` (NO-155, NO-158)

- **[1]** Bốn nhánh `TimeoutError` riêng của `next_frames`/`raw_until`/`wait_closed` (`packages/testing/fixtures/streams.py` dòng 156, 174, 187, 211) chưa có test (NO-155); `test_expire_stale_uploads__J01` seed 3 khoá với `BATCH=3` không ép được `SCAN` quay ≥ 2 lượt một cách chắc chắn, độ phủ nhánh dao động theo dữ liệu DB dùng chung; `registry.default_providers()` không đi qua `_check` nên luật bắt buộc `policy` chưa áp cho bản mặc định (NO-158).
- **[2]** Trên `main`: `test_registry.py -k default_providers_without_policy` mã thoát 1 (`DID NOT RAISE`).
- **[3]** `apps/api/streams/{jobs,registry}.py`, `packages/testing/fixtures/streams.py`.
- **[4]** Sửa: `apps/api/streams/tests/{test_fixture_streams,test_jobs,test_registry}.py`, `apps/api/streams/registry.py`. Cấm: mọi file khác (không sửa `packages/testing/fixtures/streams.py` — dòng 156 còn lại xem NO-192).
- **[5]** Ba ca mới (`raw_until`, hai nhánh `_await_start`) tất định qua monkeypatch `_OPEN_TIMEOUT_S` (khuôn `test_disconnect_times_out_when_the_app_never_exits` có sẵn); seed thêm 40 khoá đệm không hạn ép `SCAN` quay ≥ 2 lượt tất định; `default_providers()` nay đi qua `_check`.
- **[6]** `test_default_providers_without_policy_is_rejected_by_check` — đỏ mã thoát 1 (`DID NOT RAISE`) → xanh; ba ca `raw_until`/`_await_start` mới xanh (coverage thuần, không lượt đỏ theo nghĩa sửa lỗi).
- **[7]** Commit `6caadb8` (`Prompt: B4-01`, `Fix: FIX-096`); review APPROVE `docs/reviews/2026-09-24-fix-debt-01-modules.md` (4,78/5), cổng đầy đủ thoát 0 (3764 passed). Dòng 156 còn `Miss`: NO-192 (mới).

## FIX-086 cho B0-08 — nợ triển khai: log token qua nginx, khoá MinIO xoay không thu hồi, biến thư, scrape metric, cổng host `ci.yml`, nginx khi đổi phiên bản (NO-094, NO-095, NO-096, NO-141, NO-162, NO-118, NO-117, NO-083, NO-084)

- **[1]** Bảy nợ triển khai: token `/api/files/<token>` lọt `docker logs web` qua URI méo (NO-095) và qua server 301 prod (NO-094); xoay `S3_ACCESS_KEY`/`S3_ML_ACCESS_KEY` không thu hồi khoá cũ (NO-096); compose chỉ truyền `SMTP_URL` không ai đọc, hỏng lượt gửi thư đầu (NO-141); cổng exporter 9464 chưa ai scrape (NO-162); `api` của `ci.yml` publish cổng host cố định làm `--scale api=2` hỏng (NO-118); đổi phiên bản bằng `deploy.sh` đo được 7 phản hồi hỏng qua 2 lượt (NO-117).
- **[2]** Trên `main` @ `9f11ddf`: lùi các tệp sản xuất về `main`, giữ test mới → `11 failed, 22 passed`; riêng `minio/init.sh` lùi → `1 failed, 3 passed` (`test_minio_init.py`).
- **[3]** `deploy/nginx/templates/{dev,prod}/app.conf.template` (map `$request_uri`), `deploy/nginx/snippets/app_locations.conf`, `deploy/minio/init.sh`, `deploy/compose/base.yml:118` (`SMTP_URL`), `deploy/compose/ci.yml:87-88` (`ports` của `api`), `packages/mail/settings.py`, `packages/observability/settings.py:15`.
- **[4]** Sửa: `deploy/nginx/**`, `deploy/compose/{base,ci}.yml`, `deploy/compose/env.example`, `deploy/minio/init.sh`, `deploy/observability/prometheus.yml` (mới), `deploy/tests/**`. Cấm: `deploy/scripts/**`, `deploy/backup/**` (B0-10 — FIX-087), `tools/ci/job.sh` (B0-09 — FIX-084), ba biến `ml` trong `base.yml` (NO-085 chờ nhánh core).
- **[5]** `access_log off` chuyển từ mức server sang `location /api/files/` (trên `$uri` đã chuẩn hoá) + `error_page` riêng cũng tắt log; `access_log off` cho server 301 prod; `init.sh` thêm `revoke_stale_users()`; tám biến `MailSettings` thay `SMTP_URL` (`SMTP_HOST`/`MAIL_FROM` là `${…:?…}`); `prometheus.yml` mới khai job `api:9464`; `ci.yml` bỏ `ports:` của `api`; `proxy_common.conf` hạ `proxy_connect_timeout` xuống 1s + `proxy_next_upstream` (không dùng `upstream{}` — lý do nêu ra sai, xem nợ mới NO-198).
- **[6]** `test_nginx_files_location_disables_access_log`, `test_nginx_prod_redirect_server_disables_access_log`, `test_nginx_proxy_common_survives_api_container_swap`, `test_minio_init_revokes_identities_left_over_from_key_rotation`, `test_env_example_mail_vars_point_at_mailpit_for_dev_and_ci`, `test_compose_mail_required_vars_have_no_silent_default`, `test_compose_scrape_job_targets_api_metrics_port`, `test_compose_metrics_port_is_never_published`, `test_compose_ci_api_publishes_no_host_port` — đỏ trên `main`, xanh trên nhánh (241 qua, 0 hỏng; độ phủ `deploy/` 100 %/100 %). Probe thật: 7 URI méo × (dev 8080, prod 8443, prod 8080) → `grep -c <token>` = 0; `init.sh` ba lượt trên MinIO thật; `compose up --scale api=2` → 0; hai lượt `deploy.sh` đổi phiên bản, poll 100 ms qua `web` → 0 phản hồi hỏng (reviewer tự đo độc lập 517 mẫu, 0 phản hồi hỏng).
- **[7]** Commit `47cdab2` (`fix(deploy): scope file-token log rules to the normalized location`, `Prompt: B0-08`, `Fix: FIX-086`); review APPROVE WITH COMMENTS 4,45/5, cổng đầy đủ thoát 0.

## FIX-087 cho B0-10 — một nguồn cho `APPBACK_API_SWAP_SETTLE_S`, R3, R4 (NO-120, NO-117)

- **[1]** Test chốt `APPBACK_API_SWAP_SETTLE_S ≥ resolver valid + 1` (`test_deploy.py:303`) bắt nhầm dòng kế hoạch `--dry-run` (`lib.sh:86`) thay vì lệnh `sleep` thật (`lib.sh:120`): hạ mặc định của `sleep` mà cổng vẫn xanh; hằng `11` có ba bản (`lib.sh:86`, `lib.sh:120`, `README.md:272`).
- **[2]** Trên `main` @ `9f11ddf`, lùi `deploy/scripts/lib.sh` về `main`, chạy `test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl` với test mới → đỏ.
- **[3]** `deploy/scripts/lib.sh:86,120`, `deploy/scripts/README.md:272`, `deploy/scripts/tests/test_deploy.py:303`. Review gốc B0-10 vòng 3, R1–R4.
- **[4]** Sửa: `deploy/scripts/lib.sh`, `deploy/scripts/drill.sh`, `deploy/scripts/tests/{test_deploy,test_drill}.py`, `deploy/backup/tests/test_restore.py`. Cấm: `deploy/nginx/**`, `deploy/compose/**`, `deploy/minio/**` (B0-08 — FIX-086).
- **[5]** `: "${APPBACK_API_SWAP_SETTLE_S=11}"` khai đúng một lần đầu `lib.sh` (dùng `=`, không `:=` — bài học NO-114), hai chỗ dùng biến trần, test đọc đúng dòng khai và đối chiếu `README.md`; NO-118 phần B0-10: `drill.sh` bỏ `export API_HOST_PORT`. R3: `test_drill.py` đặt `FAKE_LOG` + khẳng định dương `compose down -v`. R4: annotation `monkeypatch: pytest.MonkeyPatch`.
- **[6]** `test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl` (siết), `_assert_cleanup_used_fake_docker` (hai test `test_drill.py`) — đỏ trên `main`, xanh trên nhánh (241 qua, 0 hỏng).
- **[7]** Commit `f363377` (`fix(deploy): single source for the api swap settle default`, `Prompt: B0-10`, `Fix: FIX-087`); review APPROVE WITH COMMENTS 4,45/5, cổng đầy đủ thoát 0.

## FIX-104 cho B0-08 — tầng chạy Python 3.14 không đọc được venv 3.12 của tầng dựng (NO-177)

- **[1]** `docker compose run --rm migrate` → `ModuleNotFoundError: No module named 'alembic'` dù `/opt/venv/bin/alembic` tồn tại; `docker build` vẫn thoát 0 nên không cổng nào đỏ lúc build, job `build` của CI chỉ đỏ muộn ở bước `import_all`.
- **[2]** Trên `main` @ `9f11ddf`: `docker build -t appback-api:x -f deploy/docker/api.Dockerfile .` → 0, rồi `python -V` → 3.14.7, `ls /opt/venv/lib` → `python3.12`; `docker compose run --rm migrate` → exit 1.
- **[3]** `deploy/docker/api.Dockerfile:34`, `worker.Dockerfile:31`, `ml.Dockerfile:74` — dependabot `44b299f` đổi tầng chạy `python:3.12-slim-bookworm` → `python:3.14-slim-bookworm`, trong khi tầng dựng ở `api:6`, `worker:6`, `ml:11` vẫn `uv:python3.12-bookworm-slim`; `pyproject.toml:5` ghim `requires-python = ">=3.12,<3.13"`, `uv.lock:3` ghi `==3.12.*`.
- **[4]** Sửa: `deploy/docker/{api,worker,ml}.Dockerfile` (dòng `FROM` tầng chạy + comment), `deploy/tests/test_dockerfiles.py`. Cấm: tầng dựng, `uv.lock`, `pyproject.toml`, `.github/dependabot.yml` (NO-178, chủ B0-09), mọi file ngoài `deploy/`.
- **[5]** Ba dòng `FROM` tầng chạy về `python:3.12-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e` — digest tự tra bằng `imagetools`, đúng bằng digest có trước `44b299f`; kèm comment ràng buộc "minor phải khớp tầng dựng và `requires-python`".
- **[6]** `test_dockerfile_python_minor_matches_across_stages_and_workspace` — quét mọi `deploy/docker/*.Dockerfile`, đòi minor của tầng chạy/tầng dựng bằng `requires-python` gốc, chốt số tầng soi được ≥ 7; đỏ trên `main` (AssertionError venv không đọc được), xanh sau sửa (`pytest deploy/tests` 153 passed).
- **[7]** Commit `3f2e14d` (`fix(deploy): pin python runtime stage back to the workspace minor`, `Prompt: B0-08`, `Fix: FIX-104`); reviewer đo độc lập: `python -V` = 3.12.14, `import alembic` đạt, `compose run --rm migrate` thoát 0; review APPROVE WITH COMMENTS 4,45/5, cổng đầy đủ thoát 0.

## FIX-098 cho F-02 — nhãn tiếng Việt thiếu cho 26 `kind` hoạt động (NO-099)

- **[1]** Màn quản trị người dùng hiện câu dự phòng cho mọi `kind` trừ `floor.upload`.
- **[2]** `src/screens/admin/UserManagement/useUserManagement.ts:174-186` trên AppFront `master` @ `9cf0b0b`.
- **[3]** `apps/api/access/kinds.py` khai 27 `ActivityKind`; bảng nhãn FE chỉ có 1.
- **[4]** Sửa: `useUserManagement.ts` + test mới `useUserManagement.test.ts`. Cấm: file khác.
- **[5]** Bảng nhãn đủ 27 `kind`, chép tĩnh kèm nguồn `kinds.py:<dòng>`.
- **[6]** Test khẳng định mọi `kind` có nhãn: đỏ trên `master` → xanh; reviewer tự đếm máy 27/27.
- **[7]** `fix(admin): label all 27 activity kinds in user management` (AppFront `831be4b`, `Prompt: F-02`, `Fix: FIX-098`); review lượt 1 ĐẠT.

## FIX-099 cho F-01b — SSE thông báo mở sai đường (NO-086)

- **[1]** FE mở `/api/notifications/stream`; BE-BIND S2 là `GET /api/streams/notifications`; nginx chỉ tắt đệm cho `/api/streams/`.
- **[2]** `src/api/endpoints.ts:10` (`NOTIFICATIONS_ROOT`) trên AppFront `master` @ `9cf0b0b`.
- **[3]** Cookie `appback_stream` có `Path=/api/streams` nên đường cũ không bao giờ mang được cookie.
- **[4]** Sửa: `src/api/endpoints.ts`, `src/api/__tests__/notifications.test.ts`. `endpoints.ts` không thuộc `so_huu` nào — người dùng chốt chủ F-01b.
- **[5]** Đổi đường luồng thông báo sang `/streams/notifications`.
- **[6]** `notifications.test.ts` khẳng định đường mới: đỏ trên `master` → xanh.
- **[7]** `fix(api): point notifications SSE at BE-BIND S2 /api/streams/notifications` (AppFront `885556d`, `Prompt: F-01b`, `Fix: FIX-099`); review lượt 1 ĐẠT. F-01b 4.8 sẽ thay dòng này bằng nhóm `streams`.

## FIX-105 cho B0-04 — `StorageSettings` đọc `CoreSettings` nên `ml` không dựng được kho S3 (NO-085)

- **[1]** Bỏ `SECRET_KEY`, `PUBLIC_BASE_URL` khỏi `ml` (NO-085) thì lượt suy luận đầu hỏng: `ValidationError ... StorageSettings: public_base_url, secret_key Field required`.
- **[2]** `StorageSettings()` với `APP_ENV=production`, `STORAGE_BACKEND=s3`, không `SECRET_KEY` (tiến trình mới).
- **[3]** `packages/storage/settings.py:59` `_backend_fields` gọi `get_core_settings()` để kiểm luật khác origin; `apps/ml/runtime/tasks_util.py:74` truyền `get_core_settings()` vào `create_storage`.
- **[4]** Sửa: `packages/storage/{settings,factory,local}.py` + test. Cấm: nơi gọi của chủ khác (không phải đổi).
- **[5]** Luật khác origin chuyển vào `create_storage` (`_check_public_origin`) khi được truyền `CoreSettings` — mọi nơi gọi của API (`apps/api/core/app.py`, `apps/api/{floors,me,projects}/jobs.py`) vẫn truyền; `core_settings=None` cho tiến trình không ký URL, `LocalDiskStorage` khi đó từ chối `signed_url`.
- **[6]** `apps/ml/runtime/tests/test_tasks_util.py::test_infer_context_builds_without_the_api_secrets` đỏ → xanh; ba test luật origin dời sang `packages/storage/tests/test_factory.py`, không nới assert.
- **[7]** `fix(storage): check the cross-origin rule where core settings exist` (`2739918`, `Prompt: B0-04`, `Fix: FIX-105`); cùng FIX-091 `c2f3c72` (B5-01). Review lượt 2 APPROVE 4,75/5, cổng đầy đủ thoát 0 (3840 passed).

## FIX-106 cho B0-01 — Mailpit tra rDNS mỗi kết nối, DNS máy chậm làm test thư hết giờ (NO-210)

- **[1]** Cổng đầy đủ (B2-02 lớp gộp và `main` `4f89245`) hỏng bước 5: `packages/mail/tests/test_fixtures.py`, `test_sender.py`, `apps/api/auth_recovery/tests/test_e2e.py` ×2, `tools/tests/test_services.py::test_mailpit_nhận_thư` — `smtplib.SMTPServerDisconnected: Connection unexpectedly closed: timed out`.
- **[2]** `docker run -p 11025:1025 axllent/mailpit:v1.20.0` rồi gửi 3 thư `smtplib` timeout 10 s: mỗi lượt ~10 s, 1/3 hỏng; `Resolve-DnsName 1.17.172.in-addr.arpa -Type PTR` trên máy chủ 11,6 s.
- **[3]** `packages/testing/fixtures/services.py:97-110` — `DockerContainer(MAILPIT_IMAGE)` không tắt rDNS; Mailpit tra PTR máy khách trước lời chào SMTP.
- **[4]** Sửa: `packages/testing/fixtures/services.py` (thêm `.with_env("MP_SMTP_DISABLE_RDNS", "true")`). Cấm: `packages/mail/**`, `SMTP_TIMEOUT_S`, mọi test (không nới timeout, không skip).
- **[5]** Tắt rDNS ở container Mailpit của test: test không còn phụ thuộc DNS của máy; cùng env đó thử tay 3/3 thư 0,03 s.
- **[6]** 5 test trên đỏ → xanh trên máy có DNS PTR chậm; không test nào khác đổi.
- **[7]** `fix(testing): disable mailpit rdns lookups in the test fixture` (squash của `5ac987b`, `Prompt: B0-01`, `Fix: FIX-106`); review lượt 1 APPROVE 4,9/5 (`bfe9889`), cổng đầy đủ thoát 0 (4011 passed). Nợ kèm: NO-211 (e2e phụ thuộc thứ tự, B1-03), NO-212 (compose còn rDNS, B0-08).

> **Giao việc FIX-107.** 2026-09-25, cổng đầy đủ bước 5 của B2-04 (`feature/b2-04-drawing-uploads`) đỏ đúng một test của B4-01.
> Người dùng chọn FIX ngay trên nhánh B2-04 (tiền lệ FIX-082): commit riêng chỉ chạm file test đó, trailer `Prompt: B4-01` +
> `Fix: FIX-107`; nhánh vào `main` giữ trailer của cả hai prompt.

## FIX-107 cho B4-01 — test mặc định của sổ luồng phụ thuộc việc "chưa có B2-04" (không mã nợ)

- **[1–3]** `apps/api/streams/tests/test_registry.py::test_missing_progress_provider_defaults_to_closed` khẳng định `build_registry(None)[UPLOAD_PROGRESS].policy` là `DenyUploads`; docstring tự ghi "Chưa có B2-04 → …". Nay `apps/api/drawings/stream_providers.py` có thật nên `discover` trả provider của B2-04.
- **[4]** Sửa: đúng file test trên. Cấm: mọi mã sản phẩm của B4-01 (`apps/api/streams/**` ngoài file đó).
- **[5]** Test tự dựng trạng thái "không ai cài" bằng helper `_app_with()` có sẵn trong file (`extensions.override(app, "stream_providers", ())`) thay vì `build_registry(None)`; không xoá, không nới assert.
- **[6]** Test xanh cả trên `main` (chưa có `apps/api/drawings`) lẫn trên nhánh B2-04 (đỏ trên nhánh trước khi sửa: bước 5 lượt 1 của việc gộp).
- **[7]** `test(streams): build the empty registry from an override` (`e9ef485`, `Prompt: B4-01`, `Fix: FIX-107`), gộp `--no-ff` trong `9d2c95b`; review B2-04 lượt 1 APPROVE 4,67/5 (`5e9b282`) soát riêng FIX-107, cổng đầy đủ thoát 0 (4395 passed).

---

> **Giao việc FIX-108.** 2026-09-26, khảo sát B3-02 (việc K) chỉ ra seed đầu tiên của repo (`packages/db/seeds/spatial.py`)
> làm đỏ đúng một test của B0-03. Người dùng chọn FIX ngay trên nhánh B3-02 (tiền lệ FIX-107): commit riêng chỉ chạm
> file test đó, trailer `Prompt: B0-03` + `Fix: FIX-108`; nhánh vào `main` bằng `--no-ff`, giữ trailer của cả hai prompt.

## FIX-108 cho B0-03 — test seed chốt trạng thái "repo chưa có seed" làm bất biến (không mã nợ)

- **[1–3]** `packages/db/tests/test_seeds_settings.py::test_repo_has_no_seeds_yet` khẳng định `load_seeds("ci") == ()`.
  Nay B3-02 thêm `packages/db/seeds/spatial.py` (`ENVS = {"dev", "ci"}`) nên `load_seeds("ci")` trả một phần tử.
- **[4]** Sửa: đúng file test trên. Cấm: mọi mã sản phẩm của B0-03 (`packages/db/**` ngoài file đó).
- **[5]** Không khẳng định danh sách seed cụ thể của prompt khác (lại thành bất biến giòn). Test kiểm bất biến thật của
  bộ dò trên repo: mọi seed nạp được, tên duy nhất, `ENVS` là `frozenset` con của tập môi trường hợp lệ, thứ tự theo
  `ORDER` ổn định; `load_seeds("production")` không có seed demo nào. Không xoá test, không nới assert.
- **[6]** Test xanh cả trên `main` (chưa có seed) lẫn trên nhánh B3-02.
- **[7]** `test(db): check discovered seeds instead of an empty repo` (`1ada889`, `Prompt: B0-03`, `Fix: FIX-108`) — sửa cả `test_repo_has_no_seeds_yet` lẫn `test_seeds_main_runs_with_no_seeds` cùng file, cùng nguyên nhân (lệch #6 của việc gộp B3-02, review chấp nhận); gộp `--no-ff` trong `15d1f53`; review B3-02 lượt 1 soát riêng FIX-108 (không finding), lượt 2 APPROVE 4,94/5 (`452f59f`), cổng đầy đủ thoát 0 (4590 passed).

---

> **Giao việc FIX-109, FIX-110.** 2026-09-28, điều phối B4-02 dự báo hai test của prompt khác đỏ khi B4-02 cắm sink mời
> và nhà cung cấp luồng `notifications` thật. Người dùng chọn FIX ngay trên nhánh B4-02 (tiền lệ FIX-107, FIX-108): mỗi FIX
> một commit riêng chỉ chạm đúng file test đó, trailer `Prompt: <chủ>` + `Fix: FIX-<nnn>`; commit gộp vào `main` giữ
> trailer của cả ba prompt.

## FIX-109 cho B2-02 — test dò sink mời chốt trạng thái "chưa có B4-02" (không mã nợ)

- **[1–3]** `apps/api/project_members/tests/test_sinks.py::test_invite_sink__no_override_discovers_real_modules` khẳng định
  `invite_sink()` (dò repo thật) là `_NoopSink`. Nay `apps/api/notifications/invite_sinks.py` có thật nên dò ra sink của B4-02.
- **[4]** Sửa: đúng file test trên. Cấm: mọi mã sản phẩm của B2-02 (`apps/api/project_members/**` ngoài file đó).
- **[5]** Không nhập module của B4-02 vào test B2-02. Test kiểm bất biến thật của lượt dò: `app=None` dò repo không lỗi và
  trả một sink có `on_member_added` gọi được, đến từ một module `apps.api.<module>.invite_sinks` (hoặc `_NoopSink` khi
  không ai cắm). Cảnh "không ai cắm" đã có test riêng bằng `extensions.override(..., [])`. Không xoá test, không nới assert.
- **[6]** Test xanh cả trên `main` (chưa có B4-02) lẫn trên nhánh B4-02.

## FIX-110 cho B4-01 — test mặc định luồng thông báo phụ thuộc việc "chưa có B4-02" (không mã nợ)

- **[1–3]** `apps/api/streams/tests/test_registry.py::test_missing_notifications_provider_defaults_to_open_schema` khẳng định
  `build_registry(None)[NOTIFICATIONS].event_model is AnyEvent`. Nay `apps/api/notifications/stream_providers.py` có thật.
- **[4]** Sửa: đúng file test trên. Cấm: mọi mã sản phẩm của B4-01 (`apps/api/streams/**` ngoài file đó).
- **[5]** Như FIX-107: dựng sổ từ `build_registry(_app_with())` (bảng override rỗng, helper có sẵn trong file) thay vì
  lượt dò repo thật; giữ nguyên ba assert (`AnyEvent`, không `policy`, không `snapshot`).
- **[6]** Test xanh cả trên `main` lẫn trên nhánh B4-02.

> **DEBT-02 đợt 1** (2026-10-03): khối 7 mục của từng cụm C01–C04, chép từ `dieu-phoi/chay/DEBT-02/W1/C0*/FIX-*.md`.

## FIX-117 cho B0-01 — DEBT-02 W1/C01: `run.sh` (gc trên Git Bash, đường AppFront mặc định, stdin của `shell`, junit bước 5, cache ruff/mypy) và volume `appback-work`

1. **Triệu chứng:** gc thoát 128 trên Git Bash; shell nuốt stdin; junit mất; cảnh báo volume; shell không tài liệu; F:/AppFront cũ
2. **Nguyên nhân gốc:** MSYS_NO_PATHCONV + git -C đường MSYS; run --build đọc stdin; container AutoRemove; volume nhãn project; mặc định cứng
3. **Sửa:** gc dùng cwd; build riêng trong run_container; export_junit + dọn mồ côi; external + volume create; cảnh báo stderr + README; helper appfront_repo.sh (--git-common-dir)
4. **Test chặn tái phát:** test_run_sh.py, test_verify_yml.py, test_steps_commands.py, test_web_context_sh.py (xem quyet-dinh.md)
5. **Bằng chứng đỏ→xanh:** tai-hien-NO-*.md tương ứng (red.log → green.log, 97 passed ở lượt cuối).
6. **Hợp đồng:** không đổi (đối số công khai của run.sh giữ nguyên; volume appback-work trong verify.yml nay external — README ghi).
7. **Nợ còn lại:** NO-306 không tái hiện (giữ mở); junit-perf.xml bước 5b không xuất; charter/ENV.md, HOP-DONG-MOI.md còn F:/AppFront (điều phối)

## FIX-118 cho B0-08 — DEBT-02 W1/C01: đường AppFront mặc định của `deploy/docker/web-context.sh`

1. **Triệu chứng:** mặc định F:/AppFront cũ
2. **Nguyên nhân gốc:** hằng cứng
3. **Sửa:** source tools/verify/appfront_repo.sh (--git-common-dir)
4. **Test chặn tái phát:** test_web_context_sh.py::test_web_context_sh__…
5. **Bằng chứng đỏ→xanh:** tai-hien-NO-*.md tương ứng (red.log → green.log, 97 passed ở lượt cuối).
6. **Hợp đồng:** không đổi (đối số công khai của run.sh giữ nguyên; volume appback-work trong verify.yml nay external — README ghi).
7. **Nợ còn lại:** không

## FIX-119 cho B3-05 — DEBT-02 W1/C01: đường AppFront trong `apps/api/rules/catalog.py`

1. **Triệu chứng:** docstring dẫn F:/AppFront cũ
2. **Nguyên nhân gốc:** chuyển thư mục
3. **Sửa:** đổi chú thích thành F:/App/AppFront
4. **Test chặn tái phát:** không có hành vi để test (docstring)
5. **Bằng chứng đỏ→xanh:** tai-hien-NO-*.md tương ứng (red.log → green.log, 97 passed ở lượt cuối).
6. **Hợp đồng:** không đổi (đối số công khai của run.sh giữ nguyên; volume appback-work trong verify.yml nay external — README ghi).
7. **Nợ còn lại:** không

## FIX-120 cho B0-09 — DEBT-02 W1/C02: `tools/ci/job.sh` (xdist, sàn nginx theo nhánh, `cd` khi nạp) và test của nó

- **[1]** Job CI unit/integration/ml chạy pytest tuần tự dưới `coverage run` (NO-269); sàn nginx một hằng cho mọi dòng phát hành (NO-183) và test dưới-sàn chỉ `!= 0` (NO-181); nhánh không-`RUNNER_TEMP` của `job_build_trivy` chưa có test (NO-191); assert cấm chữ `API_HOST_PORT` khoá cả comment (NO-180).
- **[2]** Trên cây chưa sửa chạy 2 tệp test mới/sửa → `14 failed, 9 passed` (red1.log).
- **[3]** `tools/ci/job.sh` (`job_test_group`, `nginx_floor_for_line`, `job_build_check_nginx_version`), `tools/ci/tests/test_workflows.py`, `tools/ci/tests/test_job_xdist.py`, `tools/ci/README.md`.
- **[4]** `pytest -n N --dist loadfile --cov --cov-report=` với `COVERAGE_FILE=.coverage.<nhóm>` (N=3, ml=2, `CI_PYTEST_WORKERS`); bảng sàn nginx 1.30→1.30.5, 1.31→1.31.6, dòng lạ hỏng kín (nguồn nginx.org advisories, 2026-10-03); assert theo dòng mã.
- **[5]** Không đổi ci.yml/merge_artifacts/hợp đồng artifact (glob `.coverage.*` khớp).
- **[6]** Test: test_job_xdist.py (5), test_workflows.py nginx (13 ca), trivy local, API_HOST_PORT.
- **[7]** Commit: xem `git log` nhánh `fix/debt-02-w1-ci-job` (`Prompt: B0-09`, `Fix: FIX-120`).

## FIX-122 cho B0-09 — DEBT-02 W1/C03: Dependabot, trigger `edited`, miễn trừ gitleaks, test ảnh ghim trùng

Mức: thấp

[1 TRIỆU CHỨNG]
Dependabot gộp minor ảnh nền, bỏ major docker; `edited` chạy chín job; gitleaks lịch sử đỏ; test ảnh ghim trùng lặp.

[2 TÁI HIỆN]
Xem tai-hien-NO-*.md (178/183/182/330/179): test chặn tái phát đỏ trên cây chưa sửa (`red.log`, `cov.log`), gitleaks thật đỏ 19 phát hiện (NO-330).

[3 BẰNG CHỨNG]
`quyet-dinh.md` (bảng P-1..P-8); `cov.log` 89 passed; `verify14.log` bước 1-4 đạt; `gitleaks-xanh.log` no leaks found.

[4 KHOANH VÙNG]
.github/dependabot.yml, .github/workflows/ci.yml, .gitleaks.toml, tools/ci/h2.py, tools/ci/tests/test_h2.py, tools/ci/tests/test_github_config.py (mới). Không sửa test_workflows.py (C02): test_workflows.patch cho M.

[5 SỬA NHỎ NHẤT]
ignore python/node minor, bỏ ignore major trần docker; if != edited tám job + nhóm concurrency tách edited; 12 SHA vào commits; xoá test trùng; h2.py nhập packages.core.pinned_images.

[6 TEST CHẶN TÁI PHÁT]
test_github_config.py: 5 test đầu + test_packages_sources__do_not_import_tools_pinned_images.

[7 NGHIỆM THU]
`verify --steps 1,2,3,4` đạt; test ở [6] đỏ→xanh; commit `fix(...)` + trailer Prompt/Fix. Cổng đầy đủ ở việc gộp M.

## FIX-123 cho B0-01 — DEBT-02 W1/C03: `packages/testing` nhập `tools.pinned_images` (đảo chiều tầng)

Mức: thấp

[1 TRIỆU CHỨNG]
packages/testing nhập tools.pinned_images (đảo chiều tầng).

[2 TÁI HIỆN]
Xem tai-hien-NO-*.md (184): test chặn tái phát đỏ trên cây chưa sửa (`red.log`, `cov.log`), gitleaks thật đỏ 19 phát hiện (NO-330).

[3 BẰNG CHỨNG]
`quyet-dinh.md` (bảng P-1..P-8); `cov.log` 89 passed; `verify14.log` bước 1-4 đạt; `gitleaks-xanh.log` no leaks found.

[4 KHOANH VÙNG]
packages/testing/fixtures/services.py; xoá tools/pinned_images.py, tools/tests/test_pinned_images.py (đã dời).

[5 SỬA NHỎ NHẤT]
services.py nhập packages.core.pinned_images; xoá nguồn cũ ở tools.

[6 TEST CHẶN TÁI PHÁT]
test_packages_sources__do_not_import_tools_pinned_images.

[7 NGHIỆM THU]
`verify --steps 1,2,3,4` đạt; test ở [6] đỏ→xanh; commit `fix(...)` + trailer Prompt/Fix. Cổng đầy đủ ở việc gộp M.

## FIX-124 cho B0-02 — DEBT-02 W1/C03: nơi mới của hằng ảnh ghim trong `packages/core` (nếu phương án chốt chọn)

Mức: thấp

[1 TRIỆU CHỨNG]
Hằng ảnh ghim chưa có nơi ở tầng thấp.

[2 TÁI HIỆN]
Xem tai-hien-NO-*.md (184): test chặn tái phát đỏ trên cây chưa sửa (`red.log`, `cov.log`), gitleaks thật đỏ 19 phát hiện (NO-330).

[3 BẰNG CHỨNG]
`quyet-dinh.md` (bảng P-1..P-8); `cov.log` 89 passed; `verify14.log` bước 1-4 đạt; `gitleaks-xanh.log` no leaks found.

[4 KHOANH VÙNG]
packages/core/pinned_images.py (mới), packages/core/tests/test_pinned_images.py (dời, dạng ghim K29).

[5 SỬA NHỎ NHẤT]
Ba hằng ảnh dời sang packages.core (không nhập gì, hợp đồng core-isolated giữ).

[6 TEST CHẶN TÁI PHÁT]
packages/core/tests/test_pinned_images.py (100% dòng+nhánh).

[7 NGHIỆM THU]
`verify --steps 1,2,3,4` đạt; test ở [6] đỏ→xanh; commit `fix(...)` + trailer Prompt/Fix. Cổng đầy đủ ở việc gộp M.

## FIX-125 cho B0-01 — DEBT-02 W1/C04: `case_gate` nhận case task J/U/M và task của `apps/ml`

- **[1 TRIỆU CHỨNG]** `[[task]] require` khai U/M luôn báo "thiếu" dù test có và qua → B5-06a bỏ U01/U02/U04/U06, B5-04 bỏ cả
  `[[task]] text_read` (J02/J03/J05/J08/M01–M04). Task đạt không in dòng nào → `start_training_runner` "không ra số" (NO-309).
- **[2 TÁI HIỆN]** `repro.sh` trong `run.sh shell` trên `1dcca7d` (log `repro-before.log`); test mới chạy trên `case_gate.py` của `1dcca7d` (khối ĐỎ của `cov.sh`).
- **[3 BẰNG CHỨNG]** `tools/case_gate.py:296` `_TEST_TASK_RE = ...(?P<case>J\d{2})$`; `main()` :556-557 chỉ in `task_missing`.
  `registered_tasks()` trong container: 43 task, gồm `start_training_runner` (`packages/messaging/tasks.py:173` dò `apps.ml` từ `3b7ebf4`) → vế "sổ chưa biết task apps/ml" của NO-309 sai sự kiện.
- **[4 KHOANH VÙNG]** `tools/case_gate.py`, `tools/tests/test_case_gate.py`. Cấm: `docs/charter/*`, `docs/contracts.toml`, `tools/verify/*`.
- **[5 SỬA NHỎ NHẤT]** `_TEST_TASK_RE` → `[JUM]\d{2}`, giữ đúng tên không hậu tố (CASE §2.3: hậu tố chỉ cho op; :105 `test_<task>__U01`).
  `GateResult.task_rows` + `main()` in mỗi task `fn | bắt buộc | tìm thấy | đạt/thiếu` như op. Không đổi hợp đồng (CASE đã đòi U, M).
- **[6 TEST CHẶN TÁI PHÁT]** `test_evaluate__task_require_u_m[U01]`, `[M03]`, `test_main__in_dòng_task_đạt` (đỏ trên cây cũ);
  `test_evaluate__task_case_có_hậu_tố_không_được_tính` (giữ luật).
- **[7 NGHIỆM THU]** verify bước 1–4, `cov.sh` (đỏ→xanh, độ phủ `tools/case_gate.py`), case_gate thật trên junit 3 thư mục; commit `9181628`, `1a16885`, `5caf86f`, `8860fa8` (id tham số `[...]` cho task, như op).

## FIX-126 cho B5-04 — DEBT-02 W1/C04: khai lại `[[task]] text_read` trong `apps/ml/text/cases.toml`

- **[1]** `apps/ml/text/cases.toml` rỗng → cổng chỉ đòi J01, J06 cho `text_read`.
- **[2]** `repro.sh` (log `repro-before.log`, dòng `text_read`).
- **[3]** Chú thích cũ dòng 5-23 của tệp; test có thật `apps/ml/text/tests/test_tasks.py:166-303` (J02, J03, J05, J08, M01–M04, đúng tên).
- **[4]** `apps/ml/text/cases.toml`. **[5]** `[[task]] fn="text_read" require=[J02,J03,J05,J08,M01,M02,M03,M04]` (cần FIX-125).
- **[6]** Dòng `text_read | ... | đạt` của case_gate thật (khối sau sửa của `cov.sh`); test cổng `test_evaluate__task_require_u_m[M03]`.
- **[7]** commit `e8a6e77`.

## FIX-128 cho B5-06a — DEBT-02 W1/C04: thêm lại `U01`, `U02`, `U04`, `U06` vào `require` của `apps/worker/pipeline_orchestrate/cases.toml`

- **[1]** `apps/worker/pipeline_orchestrate/cases.toml` thiếu U-case vì cổng không nhận U.
- **[2]** `repro.sh` (dòng `orchestrate_pipeline_start`), sau sửa: xoá tạm testcase U01 khỏi junit → dòng đỏ "thiếu U01".
- **[3]** test có thật `apps/worker/pipeline_orchestrate/tests/test_start_cases.py:300,314,340,357`.
- **[4]** tệp trên. **[5]** thêm U01, U02, U04, U06 vào `require` (cần FIX-125). **[6]** như [2]. **[7]** commit `20cd8a6`.
- Lưu ý: FIX-128 chưa có trong dải giữ chỗ `docs/fixes.md` (FIX-117..127) — điều phối thêm dòng.

## FIX-129 cho B5-02 — DEBT-02 W1/C04: khai `M01`, `M02` trong `apps/ml/walls/cases.toml`

- **[1]** `apps/ml/walls/cases.toml` bỏ M01,M02 vì `_TEST_TASK_RE` chỉ nhận J (chú thích "Lệch khỏi prompt" cũ của tệp).
- **[2]** `cov2.sh` (pytest thư mục test của tệp → `python -m tools.case_gate`), log `cov2.log`.
- **[3]** test có thật đúng tên trong `apps/ml/walls/tests/test_tasks.py` (collect-only trong `cov2.log`), không perf/gpu.
- **[4]** `apps/ml/walls/cases.toml`. **[5]** thêm M01,M02 vào `require`, bỏ chú thích lỗi thời (cần FIX-125).
- **[6]** dòng `segment_walls | ... | đạt` của case_gate thật. **[7]** commit `1ece360`.

## FIX-130 cho B5-03 — DEBT-02 W1/C04: khai `M01`–`M04` trong `apps/ml/objects/cases.toml`

- **[1]** `apps/ml/objects/cases.toml` bỏ M01–M04 vì `_TEST_TASK_RE` chỉ nhận J (chú thích "Lệch khỏi prompt" cũ của tệp).
- **[2]** `cov2.sh` (pytest thư mục test của tệp → `python -m tools.case_gate`), log `cov2.log`.
- **[3]** test có thật đúng tên trong `apps/ml/objects/tests/test_tasks.py` (collect-only trong `cov2.log`), không perf/gpu.
- **[4]** `apps/ml/objects/cases.toml`. **[5]** thêm M01–M04 vào `require`, bỏ chú thích lỗi thời (cần FIX-125).
- **[6]** dòng `objects_detect | ... | đạt` của case_gate thật. **[7]** commit `684e36d`.

## FIX-131 cho B6-04b — DEBT-02 W1/C04: khai `M01`–`M04`, `M06` trong `apps/ml/ml_eval/cases.toml`

- **[1]** `apps/ml/ml_eval/cases.toml` bỏ M01–M04,M06 vì `_TEST_TASK_RE` chỉ nhận J (chú thích "Lệch khỏi prompt" cũ của tệp).
- **[2]** `cov2.sh` (pytest thư mục test của tệp → `python -m tools.case_gate`), log `cov2.log`.
- **[3]** test có thật đúng tên trong `apps/ml/ml_eval/tests/test_tasks.py` (collect-only trong `cov2.log`), không perf/gpu.
- **[4]** `apps/ml/ml_eval/cases.toml`. **[5]** thêm M01–M04, M06 vào `require`, bỏ chú thích lỗi thời (cần FIX-125).
- **[6]** dòng `ml_eval_evaluate_version | ... | đạt` của case_gate thật. **[7]** commit `b7ffa1e` (M01–M04, M06), `2d56d91` (tạm bỏ M01: test parametrize → junit `__M01[...]`), `fbdb883` (thêm lại M01 sau khi FIX-125 `8860fa8` nhận id tham số cho task; log `cov4.log`).

## FIX-132 cho B5-06c — DEBT-02 W1/C04: chú thích "chỉ J" lỗi thời trong `apps/worker/pipeline_steps/cases.toml`

- **[1–3]** Chú thích viện dẫn `_TEST_TASK_RE` chỉ nhận `J\d{2}`; sau FIX-125 không còn đúng. Không có test U/M cho task của tệp → `require` giữ nguyên.
- **[4]** `apps/worker/pipeline_steps/cases.toml`. **[5]** bỏ chú thích. **[6]** dòng task của tệp vẫn đạt trong `cov2.log`. **[7]** commit `695c947`.

## FIX-133 cho B6-03a — DEBT-02 W1/C04: chú thích "chỉ J" lỗi thời trong `apps/worker/training_bridge/cases.toml`

- **[1–3]** Chú thích viện dẫn `_TEST_TASK_RE` chỉ nhận `J\d{2}`; sau FIX-125 không còn đúng. Không có test U/M cho task của tệp → `require` giữ nguyên.
- **[4]** `apps/worker/training_bridge/cases.toml`. **[5]** bỏ chú thích. **[6]** dòng task của tệp vẫn đạt trong `cov2.log`. **[7]** commit `d270199`.

## FIX-134 cho B6-03b — DEBT-02 W1/C04: chú thích task trong `apps/ml/training_runner/cases.toml` (commit `dad3628` ghi nhầm trailer `Fix: FIX-125`)

- **[1–3]** Chú thích dòng 4 viện dẫn NO-294 (`_TEST_TASK_RE` chỉ nhận J); sau FIX-125 không còn đúng. Task
  `start_training_runner` không có test U/M → `require` giữ `["J03","J04","J05","J08"]`; dòng case_gate thật `đạt` (`cov.log`, `cov2.log`).
- **[4]** `apps/ml/training_runner/cases.toml`. **[5]** bỏ câu "Chỉ khai mã J (NO-294)." **[6]** dòng `start_training_runner | ... | đạt`.
- **[7]** commit `dad3628`. **Commit dad3628 mang nhầm trailer FIX-125** (đúng là FIX-134); không viết lại lịch sử.

## FIX-135 cho B0-03 — DEBT-02 W1/C03: `packages/db/migrate_check.py` chép tay ảnh `postgres:16-alpine` thay vì nhập nguồn ghim chung

- **[1 TRIỆU CHỨNG]** `packages/db/migrate_check.py:42` chép tay ảnh `postgres:16-alpine`, lệch nguồn ghim chung (NO-184, nhánh B0-03).
- **[2 TÁI HIỆN]** C03b: test `test_migrate_check__uses_shared_pinned_image` được thêm cùng `5c6ddcd` (bằng chứng chạy: `C03/cov2.log`).
- **[3 BẰNG CHỨNG]** `C03/spec-C03b.md` mục (b); `C03/tai-hien-NO-184.md`.
- **[4 KHOANH VÙNG]** `packages/db/migrate_check.py`, `packages/db/tests/test_migrate_check.py`.
- **[5 SỬA NHỎ NHẤT]** nhập `POSTGRES_IMAGE` từ hằng ghim của `packages.core` (FIX-124) thay vì chuỗi chép tay.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_migrate_check.py::test_migrate_check__uses_shared_pinned_image`.
- **[7 NGHIỆM THU]** commit `5c6ddcd`, `f723d98` (docstring); cổng đầy đủ của nhánh gộp `fix/debt-02-w1`.

## FIX-136 cho B0-10 — DEBT-02 W1 vòng sửa review: `notify.yml` theo dõi workflow `Commits` tách mới (hỏng trên `main` phải báo như CI)

- **[1 TRIỆU CHỨNG]** Vòng sửa 1 tách job `commits` khỏi `CI` sang workflow `Commits` (chạy cả `push: main`); `notify.yml` chỉ nghe
  `[CI, Deploy, "Restore drill"]` → `commits` hỏng trên `main` không còn tin cảnh báo. `CodeQL` (cũng `push: main`) chưa bao giờ được nghe.
- **[2 TÁI HIỆN]** `deploy/scripts/tests/test_workflow_notify.py` mới chạy trên `notify.yml` cũ (`9150899`): đỏ (`M/pre-r1b.log`).
- **[3 BẰNG CHỨNG]** `.github/workflows/notify.yml:8` (danh sách), `:31` (nhánh `case`); `.github/workflows/commits.yml`, `codeql.yml` có `push: main`.
- **[4 KHOANH VÙNG]** `.github/workflows/notify.yml`, `deploy/scripts/tests/test_workflow_notify.py`.
- **[5 SỬA NHỎ NHẤT]** thêm `Commits`, `CodeQL` vào `workflow_run.workflows`; nhánh `CI | Commits | CodeQL)` gửi tin khi `failure` trên `main`
  (điều phối chọn thêm cả CodeQL: hỏng quét bảo mật trên `main` không được im lặng).
- **[6 TEST CHẶN TÁI PHÁT]** `test_notify_watches_every_workflow_running_on_push_to_main` (mọi workflow `push: main` ⊆ danh sách notify),
  `test_notify_watches_exact_names_of_watched_workflows`, `test_notify_send_decision_matches_prompt_table[Commits-…|CodeQL-…]`.
- **[7 NGHIỆM THU]** commit `9738dab`; cổng đầy đủ `M/gate-2.log` của nhánh `fix/debt-02-w1`.

## FIX-137 cho B6-04b — DEBT-02 W1 cổng 2 đỏ (luật 47): exporter giả của `test_trainer.py` lọt sang `test_export.py` (digest `"sha"`) — test phụ thuộc thứ tự

- **[1 TRIỆU CHỨNG]** Cổng 2 (`VERIFY_PYTEST_WORKERS=4`, `M/gate-2.log`) đỏ bước 5: `apps/ml/runtime/tests/test_export.py::test_export_all_missing_source_exits_3`
  — `ONNX của yolov8n lệch bản ghim: sha` (mong "thiếu tệp"). Cổng 1 (`-n 6`) không gặp vì hai tệp rơi vào hai worker khác nhau.
- **[2 TÁI HIỆN]** `pytest apps/ml/training_yolo/tests/test_trainer.py apps/ml/runtime/tests/test_export.py` một tiến trình: mã thoát 1, cùng
  thông điệp; `test_export.py` một mình: 14 passed (`M/repro-export.log`). Hai tệp và mã nguồn giống hệt `main` (lỗi có sẵn).
- **[3 BẰNG CHỨNG]** `fake_run` vá `export_yolo`/`Model.train` bằng `pytest.MonkeyPatch.context()`; `test_missing_metrics_fails_the_run` (`:298`) và
  `test_broken_export_is_rejected` (`:320`) vá đè cùng thuộc tính qua fixture `monkeypatch` — hai ngăn hoàn tác chạy lệch thứ tự, để lại
  `fake_export` (trả `"sha"`) sau test.
- **[4 KHOANH VÙNG]** `apps/ml/training_yolo/tests/test_trainer.py` (chỉ test; không đổi mã sản phẩm).
- **[5 SỬA NHỎ NHẤT]** `fake_run` trả thêm `patch` (context của nó); hai test vá đè qua `patch`, bỏ fixture `monkeypatch` — một ngăn hoàn tác duy nhất.
  Bản gốc chụp bằng fixture `originals` (`scope="module"`), không dict toàn cục — test chặn chạy lẻ vẫn đúng.
- **[6 TEST CHẶN TÁI PHÁT]** `test_zz_fake_run_restores_originals` (sau mọi test dùng `fake_run`, `export_yolo` và `Model.train` là bản gốc chụp
  trước lần vá đầu; chạy lẻ `-k test_zz` xanh); lệnh hai tệp một tiến trình: với `test_trainer.py` cũ đỏ (mã thoát 1) → xanh (31 passed,
  mã thoát 0, `M/fix137b.log`); `pytest -n 4 apps/ml` 453 passed (`M/fix137.log`).
- **[7 NGHIỆM THU]** commit `8e5cc8f`, `a84f143`; cổng đầy đủ `M/gate-3.log` (`-n 4`).

## FIX-139 cho B0-01 — cổng đầy đủ tin cache mypy ấm (NO-306); case_gate giữ bản tách tên test (NO-337)

- **[1 TRIỆU CHỨNG]** verify tích hợp `main` @ 30b78ae hỏng bước 3: `apps/ml/training_yolo/trainer.py:71: error: Call to untyped function "update" in typed context [no-untyped-call]`; `mypy --cache-dir=/dev/null` sạch (thoát 0).
- **[2 TÁI HIỆN]** `run.sh shell`: chép `/work/no306-evidence-mypy-appback` → `/tmp/c`; `mypy --cache-dir /tmp/c apps/ml/training_yolo/trainer.py` thoát 1, `--cache-dir /dev/null` thoát 0 (W2/C05b/repro306.log, probe306b.log).
- **[3 BẰNG CHỨNG]** `mypy -v`: `Updating mtime for apps.ml.training_yolo.trainer … meta …` (băm khớp → module tươi → phát lại lỗi lưu), 0 dòng `stale`; deploy/compose/verify.yml:37 `MYPY_CACHE_DIR=/work/mypy-${VERIFY_NAME}` dùng cho mọi lượt; tools/verify/steps.py `step_mypy` không chọn cache.
- **[4 KHOANH VÙNG]** tools/verify/steps.py, tools/verify/README.md, tools/tests/test_steps_commands.py, tools/case_gate.py, tools/tests/test_case_gate.py · cấm: verify.yml (giữ hợp đồng), .importlinter.
- **[5 SỬA NHỎ NHẤT]** `_run_verify`: cổng đầy đủ chạy các bước trong `_cold_mypy_cache()` (`MYPY_CACHE_DIR=os.devnull`, trả môi trường khi xong); `--steps`/`shell` giữ cache ấm (README: xem trước). case_gate nhập `split_case_test_name` từ `packages.core.case_names`, bỏ bản riêng; test tách tên chuyển sang packages/core/tests.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_steps_commands.py::test_verify__full_gate_runs_mypy_cold` — đỏ (FAILED [argv0-/dev/null]) → xanh.
- **[7 NGHIỆM THU]** `run.sh verify --steps 1,2,3,4` + cov.sh (steps.py 99%, case_gate.py 98%); commit 3e04636 `fix(verify): …` Prompt: B0-01, Fix: FIX-139. Cổng đầy đủ ở việc gộp M.

## FIX-140 cho B0-07 — bộ ghi golden nhập tầng công cụ `tools.case_gate` (NO-337)

- **[1 TRIỆU CHỨNG]** `packages/testing/golden/recorder.py:32` `from tools.case_gate import split_case_test_name` — gói hạ tầng test nhập tầng ngoài cùng.
- **[2 TÁI HIỆN]** `grep -rn "from tools" packages | grep -v /tests/` trên e5473c7 (W2/C05b/tai-hien-NO-337.md).
- **[3 BẰNG CHỨNG]** recorder.py:32; packages/testing/fixtures/golden.py:16 (runner_client — ➖ người dùng duyệt 2026-10-04, giữ).
- **[4 KHOANH VÙNG]** packages/testing/golden/recorder.py, tests/test_imports.py (mới), tests/test_recorder.py · cấm: fixtures/golden.py (giữ ngoại lệ), .importlinter.
- **[5 SỬA NHỎ NHẤT]** recorder nhập `packages.core.case_names.split_case_test_name`; test_recorder `test_recorder_imports_no_private_name_of_case_gate` đổi module lọc sang `packages.core.case_names` (giữ tên test cho truy vết NO-049).
- **[6 TEST CHẶN TÁI PHÁT]** `packages/testing/golden/tests/test_imports.py::test_packages_sources__do_not_import_tools` — đỏ → xanh.
- **[7 NGHIỆM THU]** cov.sh: recorder.py 100%; commit 9d79a1f `fix(testing): …` Prompt: B0-07, Fix: FIX-140.

## FIX-141 cho B0-02 — nguồn tách tên test case dùng chung ở tầng thấp (NO-337)

- **[1 TRIỆU CHỨNG]** `split_case_test_name` chỉ có ở `tools/case_gate.py`, buộc `packages.testing` nhập `tools`.
- **[2 TÁI HIỆN]** như FIX-140.
- **[3 BẰNG CHỨNG]** tools/case_gate.py:314-342 (e5473c7); hợp đồng `testing-only-from-tests` cấm `tools` nhập `packages.testing`, nên đích chỉ có thể là gói không phải testing; tiền lệ NO-184 `packages/core/pinned_images.py`.
- **[4 KHOANH VÙNG]** packages/core/case_names.py (mới, thuần `re`), packages/core/tests/test_case_names.py (mới, chuyển từ tools/tests/test_case_gate.py).
- **[5 SỬA NHỎ NHẤT]** dời `CaseTestName`, hai regex, `split_case_test_name` nguyên văn; không còn bản thứ hai (R-07).
- **[6 TEST CHẶN TÁI PHÁT]** `packages/core/tests/test_case_names.py::test_tách_tên_test_case` (7 tham số, chuyển nguyên) + test_imports ở FIX-140.
- **[7 NGHIỆM THU]** cov.sh: case_names.py 100%; commit f726b60 `fix(core): …` Prompt: B0-02, Fix: FIX-141.

## FIX-142 cho B3-04 — `test_versions_list_versions__cursor_of_another_floor` đỏ ~1/1024 (NO-258)

- **[1 TRIỆU CHỨNG]** `test_versions_list_versions__cursor_of_another_floor` đỏ ~1/1024 — cursor giả `cursor[:-2] + "xx"` được 200, `KeyError: 'code'`.
- **[2 NGUYÊN NHÂN GỐC]** MAC 32 byte = 43 ký tự base64url; ký tự cuối mang 2 bit đệm bị `_unb64` bỏ (`apps/api/core/pagination.py:74-76`); MAC thật đuôi `x[w-z]` giải ra cùng byte với `"xx"`.
- **[3 SỬA]** `apps/api/versions/tests/test_routes_list.py` — `_forged` lật một ký tự giữa MAC (đủ 6 bit dữ liệu); không đổi mã sản phẩm.
- **[4 TEST CHẶN TÁI PHÁT]** `test_forged__mac_ending_in_padding_bits` (tất định: dò cursor có MAC đuôi `x[w-z]`).
- **[5 BẰNG CHỨNG]** đỏ (đuôi `"xx"`) `1 failed` mã 1; xanh `2 passed` mã 0 — `tai-hien-NO-258.md`, `repro1.log`.
- **[6 PHẠM VI SOÁT]** `git grep '\[:-2\]\|cursor\['` apps/api/*/tests — chỉ chỗ này; `core/tests/test_pagination.py:51-57` lật `head[0]` (đúng).
- **[7 COMMIT]** `a439587` (Prompt B3-04).

## FIX-143 cho B0-05 — `apps/api/auth_recovery/tests/test_e2e.py` chạy lẻ: worker thật `Received unregistered task 'default.auth_recovery.send_token_mail'`, không có thư trong 15 s (NO-211)

- **[1 TRIỆU CHỨNG]** `apps/api/auth_recovery/tests/test_e2e.py` chạy lẻ: worker thật `Received unregistered task 'default.auth_recovery.send_token_mail'`, không có thư trong 15 s.
- **[2 NGUYÊN NHÂN GỐC]** `celery_test_app` dựng app trống; `shared_task` chỉ vào sổ khi module được nhập — phụ thuộc thứ tự test. Worker thật nạp ở `apps/worker/celery_main.py:19-20`.
- **[3 SỬA]** `register_tasks(app)` gọi `discover_submodules("apps.worker", "tasks")` + `discover_jobs()` (như worker thật); `celery_test_app` dùng nó → mọi test qua `celery_worker_factory`/`celery_worker` có sổ đầy đủ. Không nạp `apps.ml.*.tasks` (như ảnh worker). Điều phối duyệt phương án A (ask 06:17Z).
- **[4 TEST CHẶN TÁI PHÁT]** `packages/messaging/tests/test_celery_app.py::test_register_tasks__module_not_imported_before` (tiến trình con mới, tất định) + e2e chạy lẻ.
- **[5 BẰNG CHỨNG]** đỏ (thân `register_tasks` rỗng) 2 FAILED mã 1; xanh `3 passed` mã 0 — `tai-hien-NO-211.md`, `repro3.log`.
- **[6 RỦI RO ĐÃ XÉT]** 24 module nhập không có tác dụng phụ nặng/settings cấp module; `import_module` idempotent; không test nào đếm hàng `default`; import-linter không thấy nhập động.
- **[7 COMMIT]** `71266df` + `4114c13` docstring (Prompt B0-05).

## FIX-144 cho B4-01 — `test_open_streams_do_not_hold_postgres_connections` đỏ `assert 9 == 0` (`pool.checkedout()`) ở cổng `-n 6` máy thiếu RAM (B5-06b, sha 363ca00); chạy lẻ xanh (NO-298)

- **[1 TRIỆU CHỨNG]** `test_open_streams_do_not_hold_postgres_connections` đỏ `assert 9 == 0` (`pool.checkedout()`) ở cổng `-n 6` máy thiếu RAM (B5-06b, sha 363ca00); chạy lẻ xanh.
- **[2 NGUYÊN NHÂN GỐC]** test lấy mẫu `checkedout()` tại một thời điểm trong khi 20 luồng recheck mỗi 0,2 s (`apps/api/streams/sse.py:336-344`); cache phiên trượt (TTL 5 s, `soft_redis` nuốt Redis chậm, refresh xoá cache) → `_load_snapshot` mở phiên ngắn **hợp lệ** trên chính pool (`apps/api/auth/sessions.py:590-627`); Postgres chậm → nhiều phiên đang bay đúng lúc đo. Mã sản phẩm đúng K36.
- **[3 SỬA]** test đứng `sse.monotonic` (`monkeypatch.setattr(sse, "monotonic", repeat(frozen).__next__)`) → recheck/heartbeat/gia hạn chỗ không bao giờ tới hạn trong test; phép đo chỉ còn đếm kết nối bị giam. Không sleep, không nới assert, không đổi mã sản phẩm.
- **[4 TEST CHẶN TÁI PHÁT]** chính test đó; đầu dò Postgres chậm (`read_state` + `pg_sleep(0.3)`, cache luôn trượt) đỏ trên bản gốc.
- **[5 BẰNG CHỨNG]** đỏ `assert 15 == 0` mã 1; xanh `1 passed` mã 0 (`repro5.log`); bản sửa ×20 + `test_streams_open_progress.py` `-n 4`: 540 passed (`repro4.log`).
- **[6 RỦI RO CÒN LẠI]** rò phiên ở đường recheck/authorize không được test này bắt (phản biện P-9); đường đó đóng phiên bằng `async with maker()` (`sessions.py:593`) nên không có rò cấu trúc.
- **[7 COMMIT]** `4eebaa1` (Prompt B4-01).

  #### FIX-144 (tiếp) — NO-342 (B4-01): test đường recheck trả kết nối về pool (điều phối duyệt dùng lại mã)
  - **Test mới**: `apps/api/streams/tests/test_recheck_pool.py::test_recheck__returns_session_to_pool`. `SteppedClock` thay `sse.monotonic`; xoá `auth:principal:<sid>` để recheck phải đọc Postgres; `SignallingPolicy.authorize` (chạy sau `check_session`) bật sự kiện "recheck xong"; listener `checkout` của pool chứng minh có đọc DB; khẳng định `pool.checkedout() == 0`. Không có `sleep(`.
  - **Đỏ** (đột biến trong bản chép: `_load_snapshot` thành `db = maker()`, không đóng): `assert 1 == 0`, `1 failed`, mã 1 (`repro7.log`).
  - **Xanh**: mã thật `1 passed`, mã 0. Lặp `--rep 10 -n 4` cùng `test_no_db_hold.py`: 20 passed, mã 0.
  - Bản đầu dùng PING làm tín hiệu thì đỏ trên mã thật (`repro6.log`), vì heartbeat cùng vòng XREAD tới trước recheck. Đổi sang sự kiện trong `authorize`.
  - **Commit**: `65969ff` (Prompt B4-01).

## FIX-145 cho B1-05 — `import apps.api.auth_recovery.jobs  # noqa: F401` ở `test_e2e.py:14`, chỉ có để đăng ký task với worker thật (NO-340)

- **[1 TRIỆU CHỨNG]** `import apps.api.auth_recovery.jobs  # noqa: F401` ở `test_e2e.py:14`, chỉ có để đăng ký task với worker thật — giờ thừa.
- **[2 NGUYÊN NHÂN GỐC]** trước FIX-143, `celery_test_app` không nạp module task nào.
- **[3 SỬA]** bỏ dòng import đó.
- **[4 TEST CHẶN TÁI PHÁT]** `apps/api/users/tests/test_e2e.py::test_invited_user_can_accept_and_sign_in` chạy lẻ.
  5. **Bằng chứng** (`repro6.log`): chạy lẻ `1 passed` mã 0; làm rỗng thân `register_tasks` trong bản chép → `Received unregistered task 'default.auth_recovery.send_token_mail'`, `1 failed` mã 1 → test giờ dựa vào FIX-143, đúng ý.
- **[6 GHI CHÚ]** chủ là B1-05 (`tao_so_tra.py --chu`), không phải B2-02 như ô chủ của dòng nợ.
- **[7 COMMIT]** `199a28b` (Prompt B1-05).

## FIX-146 cho B0-03 — `test_conventions_catch_bad_columns` đỏ khi chạy lặp trong cùng một tiến trình: `ArgumentError: Column object 'score' already assigned to Table 'bad'` (NO-341)

- **[1 TRIỆU CHỨNG]** `test_conventions_catch_bad_columns` đỏ khi chạy lặp trong cùng một tiến trình: `ArgumentError: Column object 'score' already assigned to Table 'bad'`.
- **[2 NGUYÊN NHÂN GỐC]** `parametrize` giữ đối tượng `mapped_column(...)` ở cấp module; một `Column` chỉ gắn được vào một bảng, nên lượt thứ hai dùng lại thì hỏng.
- **[3 SỬA]** tham số đổi thành `(name, kind, problem)`; cột được dựng trong thân test bằng `mapped_column(name, kind())`. Thêm docstring có sẵn còn thiếu trong tệp (R-01, audit).
- **[4 TEST CHẶN TÁI PHÁT]** chính test đó, chạy `--rep 2` trong một tiến trình.
  5. **Bằng chứng** (`repro6.log`): bản gốc `--rep 2`: `3 failed, 3 passed`, mã 1; bản sửa `--rep 2` cả tệp: `24 passed`, mã 0.
- **[6 PHẠM VI]** không còn test nào khác giữ đối tượng `Column` cấp module trong `parametrize`.
- **[7 COMMIT]** `0b432f4`, `6fbdd5a` (docstring) — Prompt B0-03.

## FIX-147 cho B2-05b — dòng nợ ghi đỏ ~1/4 lượt dưới `-n 6`; không tái hiện được (C06: 3 giả thuyết; 0/22 lượt cổng đầy đủ từ 09-29 + 3 junit) (NO-264)

- **[1 TRIỆU CHỨNG]** dòng nợ ghi đỏ ~1/4 lượt dưới `-n 6`; không tái hiện được (C06: 3 giả thuyết; 0/22 lượt cổng đầy đủ từ 09-29 + 3 junit).
- **[2 NGUYÊN NHÂN GỐC]** chưa có. Phân 2 giữ / 3 bị 503 là tất định (`apps/api/quality/processing.py:83-93`).
- **[3 SỬA]** gộp các assert `:108-114` thành một khẳng định trên `(sorted (status, Retry-After, code) của 3 bên bị từ chối, sorted status của 2 bên được nhận, gate.calls, sorted counts)`; thông điệp khi đỏ in `(status, Retry-After, thân[:300])` của cả 5 lời gọi. Điều kiện giữ nguyên; helper `_summary` đọc `code` an toàn khi thân không phải object JSON.
- **[4 TEST]** `test_quality_set_corners__queue_capacity[1|2]`.
  5. **Bằng chứng** (`repro7.log`): `--rep 5 -n 4`: 15 passed, mã 0. Minh hoạ đỏ (bản chép, `quality_workers=1`): `AssertionError: [(503, '2', '{"code": "DEPENDENCY_UNAVAILABLE", …}'), …]` kèm diff 4×503 so với 3×503, mã 1.
- **[6 ĐỀ XUẤT CHO DÒNG NỢ]** `❌` — xem `tai-hien-NO-264.md` (C06b).
- **[7 COMMIT]** `7aef2e8`, `2c4cd0c` (độ dài dòng) — Prompt B2-05b.

## FIX-148 cho B0-05 — tham số parametrize sinh từ đồng hồ lúc thu thập (NO-266) + docstring R-01 thiếu

- **[1 TRIỆU CHỨNG]** `packages/messaging/tests/test_streams.py:154` `parametrize` chứa `datetime.now(UTC)`: giá trị khác nhau giữa các lần thu thập; đổi sang tham số vô hướng là xdist bỏ cả lượt ("Different tests were collected").
- **[2 TÁI HIỆN]** e5473c7: `run.sh shell < C05/do-do2.sh` → `pytest tools/tests/test_collection_stable.py` mã 1, `assert [{'at': datet...}] == [{'at': datet...}]`.
- **[3 BẰNG CHỨNG]** test_streams.py:154 (cũ); do-truoc.log.
- **[4 KHOANH VÙNG]** Sửa: packages/messaging/tests/test_streams.py, packages/testing/fixtures/messaging.py (chỉ docstring 4 fixture + `factory`; KHÔNG chạm celery_test_app — vùng của C06). Cấm: packages/messaging/{redis,locks}.py.
- **[5 SỬA NHỎ NHẤT]** Hằng `datetime(2026, 1, 1, tzinfo=UTC)`; thêm docstring R-01 cho 20 test thiếu trong test_streams.py và streams_client/safe_client/cache_client/event_bus/factory (theo điều phối + audit).
- **[6 TEST CHẶN TÁI PHÁT]** tools/tests/test_collection_stable.py::test_streams_parametrize__same_values_across_collections — đỏ (mã 1) trên e5473c7, xanh (cov.log, mã 0).
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 đạt (verify14.log, HEAD 1308068); cov.sh mã 0; commit 971ae1f, 959742d.

## FIX-149 cho B0-03 — lượt dọn db_url mở kết nối mới mỗi test và đặt setval trước khi nạp seed (NO-267, NO-277, NO-279)

- **[1 TRIỆU CHỨNG]** Teardown ~33 % tổng thời gian test (-n 4: 113,8 s / 348 s); `db_url` 47 ms/lượt teardown; bảng seed có Identity sẽ đụng khoá chính sau lượt dọn.
- **[2 TÁI HIỆN]** e5473c7: test tạm gọi 10 lần `_on_reset_connection` → `CONNECTS 10 ms/lượt 103.9` (do-truoc.log); NO-277: test_reset_plan trên db.py cũ → mã 1 `UniqueViolationError … Key (id)=(1) already exists` (do-sau2.log).
- **[3 BẰNG CHỨNG]** db.py:125-153 cũ (`create_async_engine` + `dispose` mỗi lượt); db.py:174-181 cũ (`setval(…,1,false)` trong `_RESET_SQL`, chạy trước `INSERT … SELECT` seed); số đo fixture: db_url 51,74 s/1096 → 15,07 s/1096.
- **[4 KHOANH VÙNG]** Sửa: packages/testing/fixtures/db.py, packages/db/tests/test_reset_plan.py (mới), packages/db/tests/test_fixture_timings.py. Cấm: changes/FIX-112.md (chú thích "một DB mỗi test" còn sai — ghi lệch).
- **[5 SỬA NHỎ NHẤT]** `SharedDb` (url, plan, vòng sự kiện riêng không đặt làm current, engine pool_size=1 + pool_pre_ping) — `db_url` gọi `shared_db.reset()`; `_RESEQUENCE_SQL` chạy sau nạp seed, `setval(seq, COALESCE(max(col),0)+1, false)`; docstring ghi phạm vi dọn (chỉ dòng). `shared_db` đổi kiểu trả (tuple → SharedDb) — không caller nào khác. `test_fixture_timings` đổi nhãn đường cũ + đo đường mới. Không thêm cờ bẩn (NO-279: quyet-dinh.md P-5).
- **[6 TEST CHẶN TÁI PHÁT]** packages/db/tests/test_reset_plan.py::test_reset_plan__identity_counter_follows_reloaded_seed (đỏ mã 1 → xanh), ::test_shared_db_reset__reuses_one_connection (đỏ: chưa có SharedDb, lỗi thu thập mã 4 + số đo 10/10 kết nối → xanh).
- **[7 NGHIỆM THU]** verify 1–4 đạt; cov.sh mã 0, db.py 99 % (nhánh 236->243 thiếu); -n 4 3 thư mục: 3002 passed, teardown 113,8 → 47,5 s, tường 115 → 108 s (n4-sau.log); commit bcb9572, 15d1045.

## FIX-150 cho B0-01 — container dịch vụ mồ côi khi pytest bị giết cứng (NO-281), docker chưa khai trong nhóm dev (NO-282), chú thích O_APPEND (NO-277)

- **[1 TRIỆU CHỨNG]** Ryuk tắt (FIX-114) → phiên bị giết để lại container; `docker` nhập trực tiếp mà chỉ có qua testcontainers; lập luận PIPE_BUF sai đối tượng.
- **[2 TÁI HIỆN]** e5473c7: `pytest tools/tests/test_dev_dependencies.py` mã 1 (`'docker==7.2.0' in dev` sai); `pytest tools/tests/test_orphan_sweep.py` mã 2 (ImportError OWNER_LABEL — không có nhãn chủ/đường dọn) (do-truoc.log).
- **[3 BẰNG CHỨNG]** services.py:57 `ryuk_disabled = True`; pyproject.toml:32-49; test_parallel_fixtures.py:8-10; hostname container verify = 12 hex đầu id (do-truoc.log).
- **[4 KHOANH VÙNG]** Sửa: packages/testing/fixtures/services.py, pyproject.toml (1 dòng dev), uv.lock (run.sh lock — chỉ 2 dòng khai báo, không đổi bản gói), tools/tests/{test_orphan_sweep,test_dev_dependencies,test_collection_stable}.py (mới), tools/tests/test_parallel_fixtures.py.
- **[5 SỬA NHỎ NHẤT]** `_start()` — mọi `.start()` của services.py đi qua: gắn nhãn `appback.test-owner=<hostname>:<pid điều khiển>` (gộp `_kwargs`), `sweep_orphans()` một lần/tiến trình: xoá khi cùng hostname mà pid chết, hoặc hostname 12-hex mà container không chạy; còn lại giữ (win32, nhãn hỏng, máy lạ → giữ). `docker==7.2.0` (ghim theo uv.lock, chủ ý theo DEBT; nâng docker phải sửa pyproject + lock cùng lượt).
- **[6 TEST CHẶN TÁI PHÁT]** tools/tests/test_orphan_sweep.py::test_sweep_orphans__removes_dead_owner_keeps_live, ::test_session_owner__xdist_worker_points_at_controller, ::test_start__labels_service_container_with_owner (Docker thật); tools/tests/test_dev_dependencies.py::test_dev_group__declares_docker_pinned_to_lock — đỏ → xanh.
- **[7 NGHIỆM THU]** verify 1–4 đạt; cov.sh mã 0, services.py 99 % (dòng 93 nhánh PermissionError — chạy root); -n 4: 0 container mang nhãn chủ còn sót sau phiên; commit 9c1e4c3, 89d40ab, 1308068.

## FIX-154 cho B6-01 — test K36 pool một kết nối chưa gắn perf

- **[1 TRIỆU CHỨNG]** apps/api/admin_ml_registry/tests/test_upload.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/admin_ml_registry/tests/test_upload.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/admin_ml_registry/tests/test_upload.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify. Commit `802da8b` cũng tạo `tools/tests/test_perf_marks.py` (B0-01) — phần đó ghi ở FIX-163 (K27 lệch, review W2 #4; nhánh gộp squash nên không viết lại lịch sử).
- **[5 SỬA NHỎ NHẤT]** Gắn @pytest.mark.perf cho test_upload_version_keeps_the_pool_free_while_streaming (đã in số đo bằng logging). Độ phủ luồng 64 MiB do test không-perf khác gánh (test_upload.py:464).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/admin_ml_registry/tests/test_upload.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-155 cho B0-06 — test broker chết chưa gắn perf

- **[1 TRIỆU CHỨNG]** apps/api/core/tests/test_routing.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/core/tests/test_routing.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/core/tests/test_routing.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Gắn perf cho test_response_is_not_blocked_by_a_dead_broker (log sẵn). Đo: dead_broker_elapsed 0.136s.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/core/tests/test_routing.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-156 cho B2-04 — test K36/K28 chưa perf, tên khớp mẫu case

- **[1 TRIỆU CHỨNG]** apps/api/drawings/tests/test_upload_flow.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/drawings/tests/test_upload_flow.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/drawings/tests/test_upload_flow.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Đổi tên bỏ hậu tố __K36/__K28 (steps.py:218 làm 5b hỏng khi perf mang mã case) → _k36/_k28, gắn perf, print → logging. Đo: K36 0,020 s (trần 1 s), K28 1,34 s (trần 15 s).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/drawings/tests/test_upload_flow.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-157 cho B2-07 — NO-246: test 1000x20 điểm khẳng định < 2 s chưa perf

- **[1 TRIỆU CHỨNG]** apps/api/measurements/tests/test_routes_read_delete.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/measurements/tests/test_routes_read_delete.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/measurements/tests/test_routes_read_delete.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Gắn perf, thêm _log.info số đo. Đo 0,896 s (trần 2,0 s giữ nguyên).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/measurements/tests/test_routes_read_delete.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-158 cho B4-01 — NO-272: 6 test S07 (mã case) khẳng định elapsed <= trần ở bước 5 (progress ×4 + notifications ×2, cùng chủ B4-01)

- **[1 TRIỆU CHỨNG]** apps/api/streams/tests/test_streams_open_progress.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/streams/tests/test_streams_open_progress.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/streams/tests/test_streams_open_progress.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Mỗi module: hàm _s07_close_elapsed(kịch bản) dùng chung; test case __S07* chỉ chạy kịch bản, log số đo, giữ wait_closed(WAIT_S) rộng (không đóng thì TimeoutError → đỏ); trần chuyển sang test perf tham số hoá (tên không mã case) giữ nguyên trần cũ (1,0/1,5 s). Đo: 0,18–0,37 s; disabled_user 1,013 s (trần 1,5 s).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/streams/tests/test_streams_open_progress.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-159 cho B7-01 — wait_until 1,5 s sát TTL cache 1 s

- **[1 TRIỆU CHỨNG]** apps/api/telemetry/tests/test_feature_flags_route.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/api/telemetry/tests/test_feature_flags_route.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/api/telemetry/tests/test_feature_flags_route.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Nâng hạn chờ 1,5 → 3,0 s (như auth/test_verifier.py). Chờ rộng, không phải trần đo; không đổi khẳng định.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/telemetry/tests/test_feature_flags_route.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-160 cho B5-01 — NO-268: test_export_onnx_deterministic 8–10 s kéo đuôi lượt loadfile

- **[1 TRIỆU CHỨNG]** apps/ml/runtime/tests/test_export.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/ml/runtime/tests/test_export.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/ml/runtime/tests/test_export.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Hai tiến trình xuất chạy song song (Popen + communicate) thay vì tuần tự; vẫn hai tiến trình lạnh, cùng khẳng định SHA. test_ocr (45,9 s đo) không sửa được trong whitelist: ngữ nghĩa tổng hợp 10 seed; đuôi thật cần xếp tệp lên đầu hàng đợi (tools/verify) → NO-268 chưa đóng hết.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/ml/runtime/tests/test_export.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-161 cho B6-02 — NO-278: pytestmark perf cấp tệp, số đo chưa in bằng logging

- **[1 TRIỆU CHỨNG]** apps/worker/datasets/tests/test_perf.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** apps/worker/datasets/tests/test_perf.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: apps/worker/datasets/tests/test_perf.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Bỏ pytestmark; perf chỉ cho test twenty_large_pages (+ _log.info 1,40 s, trần 20 s); test K22/K36 checkedout()==0 về bước 5; viết lại docstring.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/worker/datasets/tests/test_perf.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-162 cho B0-03 — 3 test J09 (mã case) khẳng định elapsed ở bước 5

- **[1 TRIỆU CHỨNG]** packages/db/tests/test_hooks.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** packages/db/tests/test_hooks.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: packages/db/tests/test_hooks.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Bỏ trần đồng hồ dư: timeout chứng minh bằng record after_commit_failed error bắt đầu bằng TimeoutError (hooks.py:131,139,149); does_not_block_event_loop giữ assert calls == [] (đã chứng minh vòng không bị chặn). Không cần test perf: case J09 không có trần số.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[packages/db/tests/test_hooks.py]` — đỏ → xanh (`red.log` → `xanh.log`).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-163 cho B0-01 — thiếu lưới chặn tái phát cho trần đồng hồ chưa perf

- **[1 TRIỆU CHỨNG]** tools/tests/test_perf_marks.py: khẳng định trần đồng hồ tường chạy ở bước 5 (`pytest-xdist -n 6`, ~1/6 CPU mỗi tiến trình) — có thể đỏ giả khi tải (BE-00 §12; DEBT NO-272/NO-246/NO-268/NO-278). `tools/tests/test_perf_marks.py` đỏ trên cây cũ (mã thoát 1, `red.log`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < red.sh` trên commit e5473c7 + test quét; xem `tai-hien-NO-272.md`.
- **[3 BẰNG CHỨNG]** tools/tests/test_perf_marks.py (dòng trong `tai-hien-NO-272.md`); BE-00.md:479-482; tools/verify/steps.py:218-246 (`perf_case_named`).
- **[4 KHOANH VÙNG]** Sửa: tools/tests/test_perf_marks.py duy nhất (tạo ở `802da8b` — commit mang nhầm trailer B6-01/FIX-154 — rồi sửa ở `d84e7ad`, `9dbaa7a`). Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Test quét AST 15 tệp (trần cận trên thời gian thiếu perf / perf mang mã case — import _CASE_IN_NAME_RE từ steps.py / pytestmark perf cấp tệp) + tự kiểm 5 loại lỗi.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/api/core/tests/test_routing.py]` (và mọi tham số khác của `SCANNED`) — đỏ → xanh (`red.log` → `xanh.log`); bản trước ghi nhầm tham số `[tools/tests/test_perf_marks.py]` không có trong `SCANNED` (review W2 #4).
- **[7 NGHIỆM THU]** `xanh.log` (test không-perf + perf mã thoát 0); `steps1234.log` bước 1-4; không đổi hợp đồng, không đổi trần; commit `fix(...)` + trailer Prompt/Fix.

## FIX-167 cho B5-03 — test M04 vá ML_DEVICE=cuda làm bẩn cache get_ml_settings của cả tiến trình (NO-312)

- **[1 TRIỆU CHỨNG]** test sau trong cùng worker thấy ml_device=cuda; B6-03b pre-6.log 6 test runner đỏ ML_DEVICE_UNAVAILABLE
- **[2 TÁI HIỆN]** pytest -p no:randomly text/test_tasks.py objects/test_tasks.py -k 'M04 or not_pinned' → mã thoát 1 AssertionError 'cuda' != 'cuda' (cây fix/debt-02-w2-prep; chi tiết: tai-hien-NO-312.md, red.log)
- **[3 BẰNG CHỨNG]** settings.py:42-45 @cache; objects/test_tasks.py:367, text/test_tasks.py:310, ml_eval/tests/test_tasks.py:280 (ngoài whitelist) đều setenv cuda; monkeypatch không trả cache
- **[4 KHOANH VÙNG]** Sửa: apps/ml/objects/tests/test_tasks.py, packages/testing/fixtures/ml_settings.py (mới) · CẤM sửa: file chủ khác (K27), DEBT.md, docs/fixes.md
- **[5 SỬA NHỎ NHẤT]** Fixture autouse toàn cục xoá cache trước/sau mọi test (conftest gốc tự nạp). Không đổi hợp đồng.
- **[6 TEST CHẶN TÁI PHÁT]** test_get_ml_settings__not_pinned_by_a_previous_test
- **[7 NGHIỆM THU]** Test ở [6] đỏ → xanh (log trong tai-hien-NO-312.md/cov.log); verify bước 1–4 + test đích; commit fix(...) + Prompt: B5-03, Fix: FIX-167

## FIX-168 cho B6-03b — support.py định nghĩa lại fixture ml_settings_cache trùng bản dùng chung (R-02, NO-312)

- **[1 TRIỆU CHỨNG]** Trùng lặp định nghĩa fixture sau khi có bản toàn cục
- **[2 TÁI HIỆN]** đọc mã (cây fix/debt-02-w2-prep; chi tiết: tai-hien-NO-312.md, red.log)
- **[3 BẰNG CHỨNG]** support.py:36-49 trùng packages/testing/fixtures/ml_settings.py
- **[4 KHOANH VÙNG]** Sửa: apps/ml/training_runner/tests/support.py · CẤM sửa: file chủ khác (K27), DEBT.md, docs/fixes.md
- **[5 SỬA NHỎ NHẤT]** Thay thân fixture bằng nhập lại (test_runner/test_runtime nhập tên này từ support).
- **[6 TEST CHẶN TÁI PHÁT]** Không thêm test riêng: bao phủ bởi test_get_ml_settings__not_pinned_by_a_previous_test + test training_runner chạy xanh
- **[7 NGHIỆM THU]** Test ở [6] đỏ → xanh (log trong tai-hien-NO-312.md/cov.log); verify bước 1–4 + test đích; commit fix(...) + Prompt: B6-03b, Fix: FIX-168

  C08b: support.py không còn nhập lại fixture; test_runner.py/test_runtime.py thôi nhập `ml_settings_cache` (autouse toàn cục lo); bỏ `reset_ml_settings_cache()` tay ở test_runtime.py (mỗi test gọi `m04.run` đúng một lần nên thừa); docstring :345 trỏ fixture toàn cục. Kiểm: b-verify.log bước 1–4 mã thoát 0; training_runner 86 passed mã thoát 0 (b-red.sh).
  ml_eval/tests/test_tasks.py:280: KHÔNG phải polluter — `context_of` thay `infer_context` bằng context riêng nên `get_ml_settings` không bị gọi; vô hiệu fixture rồi chạy ml_eval M04 + test nạn nhân vẫn `2 passed` (mã thoát 0), không cần sửa. Đính chính nhận định ở C08.

## FIX-169 cho B2-04 — signer() ăn kho cache cấp tiến trình của test khác (NO-265)

- **[1 TRIỆU CHỨNG]** 15 test floors chỉ xanh khi chạy sau drawings; signer() dựng kho theo env của test đầu tiên rồi nhớ
- **[2 TÁI HIỆN]** pytest -p no:randomly drawings/tests/test_drawings.py -k signer → mã thoát 1 (bản cũ: DID NOT RAISE; bản test cuối: stat None, xem red265b.log) (cây fix/debt-02-w2-prep; chi tiết: tai-hien-NO-265.md, red.log)
- **[3 BẰNG CHỨNG]** urls.py:20-26 @cache _default_signer; floors/lookup.py:26-36 → drawings/view_parts.py:40 gọi signer() cho mọi dự án có tầng, ~60 tệp test ngoài whitelist không cài kho → fail-closed bị bác
- **[4 KHOANH VÙNG]** Sửa: apps/api/drawings/urls.py, apps/api/drawings/tests/test_drawings.py, packages/testing/fixtures/signer.py · CẤM sửa: file chủ khác (K27), DEBT.md, docs/fixes.md
- **[5 SỬA NHỎ NHẤT]** reset_signer_cache() + fixture autouse signer_cache. Không nhánh APP_ENV=test trong mã sản phẩm; không đổi chữ ký.
- **[6 TEST CHẶN TÁI PHÁT]** test_signer__default_store_is_not_inherited_from_a_previous_test
- **[7 NGHIỆM THU]** Test ở [6] đỏ → xanh (log trong tai-hien-NO-265.md/cov.log); verify bước 1–4 + test đích; commit fix(...) + Prompt: B2-04, Fix: FIX-169

## FIX-170 cho B0-10 — README kiểm ml.env dùng danh sách cấm hẹp (NO-204 nửa 2)

- **[1 TRIỆU CHỨNG]** Lệnh kiểm in dòng theo danh sách cấm, bỏ lọt biến lạ
- **[2 TÁI HIỆN]** pytest deploy/scripts/tests/test_deploy.py -k readme_ml_env → mã thoát 1 (cây fix/debt-02-w2-prep; chi tiết: tai-hien-NO-204.md, red.log)
- **[3 BẰNG CHỨNG]** README.md:54 grep -E '^(SECRET_KEY|…)'; mẫu deploy/tests/test_env_example.py:216 dùng danh sách cho phép ML_/METRICS_. Nửa 1 (test_settings.py thiếu reset) ➖: storage_env_clean autouse :20-27
- **[4 KHOANH VÙNG]** Sửa: deploy/scripts/README.md, deploy/scripts/tests/test_deploy.py · CẤM sửa: file chủ khác (K27), DEBT.md, docs/fixes.md
- **[5 SỬA NHỎ NHẤT]** grep -vE '^(#|\$|ML_|METRICS_)'
- **[6 TEST CHẶN TÁI PHÁT]** test_readme_ml_env_check__uses_allowlist
- **[7 NGHIỆM THU]** Test ở [6] đỏ → xanh (log trong tai-hien-NO-204.md/cov.log); verify bước 1–4 + test đích; commit fix(...) + Prompt: B0-10, Fix: FIX-170

## FIX-171 cho B5-01 — scan() bỏ tệp test nên import ultralytics trần tái sinh NO-322 (NO-323)

- **[1 TRIỆU CHỨNG]** import ultralytics trần trong test vá PIL.Image.open toàn tiến trình, hỏng tuỳ xếp worker
- **[2 TÁI HIỆN]** pytest apps/ml/runtime/tests/test_imports.py → mã thoát 1 (red323.log) (cây fix/debt-02-w2-prep; chi tiết: tai-hien-NO-323.md, red.log)
- **[3 BẰNG CHỨNG]** test_imports.py: scan() 'if /tests/ not in rel'; H-02 thiếu docstring; H-03 tuple thiếu ultralytics_import
- **[4 KHOANH VÙNG]** Sửa: apps/ml/runtime/tests/test_imports.py · CẤM sửa: file chủ khác (K27), DEBT.md, docs/fixes.md
- **[5 SỬA NHỎ NHẤT]** scan() xét cả test: ultralytics cho phép khi tệp nhập prepare_ultralytics/import_ultralytics; luật pickle/torch.load chỉ mã sản phẩm; docstring; thêm ultralytics_import
- **[6 TEST CHẶN TÁI PHÁT]** test_scan__flags_bare_ultralytics_in_test_files
- **[7 NGHIỆM THU]** Test ở [6] đỏ → xanh (log trong tai-hien-NO-323.md/cov.log); verify bước 1–4 + test đích; commit fix(...) + Prompt: B5-01, Fix: FIX-171

## FIX-172 cho B2-03 — test đếm SQL của `view_parts` chỉ xanh nhờ `_default_signer` do test khác làm ấm (NO-265)

- **[1 TRIỆU CHỨNG]** Sau FIX-169 (cache `signer()` dọn quanh mỗi test), `apps/api/floors/tests/test_view_parts.py` không qua `api_env` nên không có `STORAGE_*`; `load_project_floors` ký URL bản vẽ qua `drawings.urls.signer()` và hỏng khi chạy lẻ.
- **[2 TÁI HIỆN]** Cụm C08 (W2/C08: `tai-hien-NO-265.md`, `quyet-dinh.md` P-1): `floors/lookup.py:26-36` → `drawings/view_parts.py:40` gọi `signer()` cho mọi dự án có tầng; test chỉ xanh khi chạy sau test drawings.
- **[3 BẰNG CHỨNG]** `quyet-dinh.md` C08 P-1; commit `d3c8838` (trailer `Prompt: B2-03`, `Fix: FIX-172`). Khối FIX này do việc gộp M soạn từ commit và `quyet-dinh.md` (cụm không để lại tệp `FIX-172.md`).
- **[4 KHOANH VÙNG]** `apps/api/floors/tests/test_view_parts.py` (B2-03), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Fixture autouse `_signer` khai thẳng phụ thuộc `drawing_signer`, cùng khuôn `test_lookup.py`/`test_service.py`; không đổi mã sản phẩm.
- **[6 TEST CHẶN TÁI PHÁT]** Các test của `test_view_parts.py` chạy lẻ (không còn dựa vào cache tiến trình), cùng `test_signer__default_store_is_not_inherited_from_a_previous_test` của FIX-169.
- **[7 NGHIỆM THU]** Cụm C08: verify bước 1–4 + test đích (`W2/C08/verify1234*.log`, `cov*.log`); cổng đầy đủ ở việc gộp M.

## FIX-173 cho B5-06a — đo RSS sai tiến trình (NO-339), J01 không qua đường gửi thật (NO-218), J06 khẳng định rỗng và dọn test (NO-295)

- **[1 TRIỆU CHỨNG]** Bước 5b tích hợp W1: `ru_maxrss 4616168 KiB > trần 1572864 KiB` ở `test_prepare_page_40mp_stays_under_memory_ceiling`
  (mã thoát 1, `W1/integ-verify-2.log`). Review B5-06a P2-01: J06 `walls["model"] != version.id` luôn đúng. NO-218: task
  `pipeline.orchestrate.start` "chưa ai khai".
- **[2 TÁI HIỆN]** e5473c7: `bash tools/verify/run.sh shell < W2/C14/repro.sh` — con béo 1,8 GiB rồi test 40 MP cùng tiến trình → đỏ;
  đột biến "ghim đè" → J06 cũ vẫn xanh; J01 xanh (task đã được khai ở c06c400).
- **[3 BẰNG CHỨNG]** `tests/test_start_runtime.py:165` đọc `RUSAGE_CHILDREN` (đỉnh mọi con đã reap); `tests/test_start_core.py:256` so dict với str;
  `tasks.py:47` (c06c400) đã khai task; J01 gửi bằng `apply_async` (`test_start_cases.py:178`) nên không kiểm tên gửi.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_orchestrate/**` (B5-06a). Không chạm `packages/testing/**`, `tools/**`, `DEBT.md`.
- **[5 SỬA NHỎ NHẤT]** Con tự đo `RUSAGE_SELF` và gửi qua hàng đợi; J01 dựa vào thông điệp `send_start_after_commit` (khẳng định trên `pipeline.cpu`
  rồi worker thật); J06 so `load_pins` với `active_versions` lúc giao lần một; test_pins ghim bộ khác lần hai; `tests/_helpers.py`
  gom helper/hằng trùng; xoá `reset_orchestrate_settings_cache`; trường settings chữ thường + `MIB: Final`; `PreparedPage`
  đối số tên; `preprocess._write_page` → `_put_rectified_page`. Không đổi hợp đồng (tên task/hàng/payload/env giữ nguyên).
- **[6 TEST CHẶN TÁI PHÁT]** `test_prepare_page_40mp_stays_under_memory_ceiling` (sau con béo), `test_orchestrate_pipeline_start__J06`,
  `test_pin_models_second_call_returns_false`, `test_orchestrate_pipeline_start__J01_smoke` — đỏ ở cây cũ/đột biến, xanh sau sửa
  (`tai-hien-NO-*.md`, `repro.log`, `cov.log`).
- **[7 NGHIỆM THU]** verify bước 1–4 (`verify14.log`); gói: 59 passed; độ phủ `preprocess.py` 100%/100%, `settings.py` 100%; commit fce473e
  `fix(pipeline-orchestrate): …`, trailer `Prompt: B5-06a`, `Fix: FIX-173`. Bước 5–8: cổng đầy đủ ở việc gộp M.

- **[C14b — NO-295 P3-04]** commit c2489b7 `fix(pipeline): assert the 5 s start smoke ceiling in a perf test`: test `perf` mới
  `test_orchestrate_start_smoke_stays_under_ceiling` dùng chung đường `_run_smoke` với `__J01_smoke`, khẳng định ≤ 5 s (B5-06a [8], trần đặc tả).
  Số đo 0,320 s (perf), 0,299 s (smoke), cả hai mã thoát 0 (`perf14.log`); verify bước 1–4 đạt (`verify14b.log`). Dòng `time.sleep(0.05)` trong
  diff là vòng chờ có sẵn của smoke, chỉ dời vào `_run_smoke`, không phải vòng chờ mới.

## FIX-174 cho B5-06a — con `spawn` đo `RUSAGE_SELF.ru_maxrss` mang theo RSS của cha pytest qua `execve` (NO-339)

- **[1 TRIỆU CHỨNG]** Cổng W2 `gate-1.log` (3ca726b, -n 4) bước 5b đỏ: `test_prepare_page_40mp_stays_under_memory_ceiling` — `ru_maxrss 4282204 KiB > trần 1572864 KiB`; mã thoát 1. Bước 1–5 đạt.
- **[2 TÁI HIỆN]** `run.sh shell < W2/M/rss2.sh`: con spawn không cấp phát gì của cha 1,8 GiB → `ru_maxrss 1859640 KiB`, `VmHWM 15420 KiB`; test 40 MP sau cha 1,8 GiB → `2002592 KiB > trần`, mã thoát 1 (`rss2.log`).
- **[3 BẰNG CHỨNG]** Linux giữ mức nước cao RSS của bộ nhớ cũ vào `signal->maxrss` khi `execve`, nên `RUSAGE_SELF` của con spawn ≥ RSS của cha lúc fork; cách đo của FIX-173 (`test_start_runtime.py` `_child_prepare_40mp`) chỉ đúng khi cha nhỏ (lượt kiểm C14 chạy test lẻ).
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_orchestrate/tests/test_start_runtime.py` (B5-06a), chỉ test.
- **[5 SỬA NHỎ NHẤT]** `_peak_rss_kib()` đọc `VmHWM` của `/proc/self/status` (đỉnh của ảnh sau exec; chỉ Linux, cổng chạy Linux); con 40 MP gửi số đó; bỏ `import resource`. Trần 1,5 GiB giữ nguyên (đặc tả [11] mục 3).
- **[6 TEST CHẶN TÁI PHÁT]** `test_peak_rss_kib__ignores_memory_of_the_parent` (không perf): cha giữ 768 MiB, con rỗng phải báo < 384 MiB. Đột biến về `RUSAGE_SELF` → `944744` đỏ, mã thoát 1; bản sửa → `95164` xanh. Test 40 MP sau cha 1,8 GiB → `980016 KiB`, mã thoát 0 (`fix174.log`).
- **[7 NGHIỆM THU]** Tiền kiểm đích + cổng 2 đầy đủ ở việc gộp M (`gate-2.log`).

## FIX-200 cho B5-07 — `tests/e2e/test_pipeline_e2e.py` còn gọi tay `reset_ml_settings_cache()` (NO-312)

- **[1 TRIỆU CHỨNG]** Review W2 lượt 1 finding #14 (Nit, R-07): fixture `e2e_env` gọi `reset_ml_settings_cache()` trước và sau lượt e2e, trong khi fixture autouse toàn cục `ml_settings_cache` (`packages/testing/fixtures/ml_settings.py`, FIX-167/168) đã dọn cache đó quanh mọi test.
- **[2 TÁI HIỆN]** `grep -n reset_ml_settings_cache tests/e2e/test_pipeline_e2e.py` trên `4e166ca` → dòng 100, 104.
- **[3 BẰNG CHỨNG]** `packages/testing/fixtures/ml_settings.py:17-18` `@pytest.fixture(autouse=True) def ml_settings_cache()`.
- **[4 KHOANH VÙNG]** `tests/e2e/test_pipeline_e2e.py` (B5-07). Phần `apps/ml/training_segformer/tests/test_trainer.py` của cùng finding chuyển W3/C11 (NO-318) theo quyết định điều phối.
- **[5 SỬA NHỎ NHẤT]** Bỏ hai lời gọi và lệnh nhập; `e2e_env` chỉ còn `reset_infer_context()`; docstring trỏ fixture autouse.
- **[6 TEST CHẶN TÁI PHÁT]** Không đổi hành vi; chính các test e2e chạy qua `e2e_env` (cổng đầy đủ, không `gpu`).
- **[7 NGHIỆM THU]** commit `df7baa5`; cổng đầy đủ lần 3 ở việc gộp M (`W2/M/gate-3.log`).

## FIX-175 cho B5-04 — bộ đọc OCR hụt 9 chữ kích thước so với wheel, test width nói ngược, trần bộ dò chưa `perf` (NO-254, NO-255, NO-343 phần `apps/ml/text`)

- **[1 TRIỆU CHỨNG]** `RapidOcrReader` đọc đúng 105/122 chữ kích thước seed 100-109, `RapidOCR()` wheel `use_cls=False` 114/122; không test giữ số (NO-254). `test_width_rounding_does_not_change_any_string` khẳng định ≥ 90 % giữ chuỗi, 1 seed (NO-255). `test_real_detector_finds_the_answer_boxes` khẳng định `elapsed < 20 s` mà không `perf` (NO-343, BE-00 §12).
- **[2 TÁI HIỆN]** `run.sh shell < W3/C09/red.sh` trên 77d7180: `assert 105 >= 114`, `assert 40 == 41`, pytest mã thoát 1 (`red.log`). Thí nghiệm bật/tắt `exp.sh`/`exp2.sh` (`tai-hien-NO-254.md`).
- **[3 BẰNG CHỨNG]** `apps/ml/text/reader.py:251-255` `_rec_widths` sàn 80 < `rec_img_shape [3, 48, 320]` của wheel; Otsu/xoay/INTER_CUBIC/lát không đổi số (105/122); sàn 320 → 114/122. `test_reader_real.py:109-134` (base).
- **[4 KHOANH VÙNG]** `apps/ml/text/reader.py`, `apps/ml/text/tests/test_reader.py`, `apps/ml/text/tests/test_reader_real.py` (B5-04). Thước trùng ở `apps/ml/runtime/**` chuyển FIX-176.
- **[5 SỬA NHỎ NHẤT]** `REC_MIN_WIDTH_PX = 320`; `padded = min(max(bội 80, 320), REC_MAX_WIDTH_PX)`. Test: ghim tỉ lệ 10 seed ≥ 0,90; đổi tên/docstring test width, 3 seed, so với `max(resized, 320)`; tách trần bộ dò sang `perf`. Lệch [6]/[8] của B5-04 ghi ở `W3/C09/quyet-dinh.md`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_reader_reads_dimension_texts` (đỏ 105 < 110 trên base → xanh 114); `test_width_rounding_keeps_most_strings` (tên cũ đỏ 40/41 ≠ 41 → xanh 41/41); `test_real_detector_page_time` (perf, 0,95–1,42 s / trần 20 s).
- **[7 NGHIỆM THU]** `xanh2.log`: `apps/ml/text/tests` 48 passed, perf 1 passed (mã thoát 0); độ phủ `reader.py` 98 % dòng; `steps1234.log` bước 1–4; commit `6fd8dbf`, `a5b83e0`, `71a44e6`. Cổng đầy đủ ở việc gộp `W3/M`.

## FIX-176 cho B5-01 — thước chữ kích thước (regex + 25 px) chép ở ba test OCR (NO-349)

- **[1 TRIỆU CHỨNG]** `DIMENSION_RE` định nghĩa ở `apps/ml/runtime/tests/test_ocr.py:16`, `apps/ml/text/tests/test_reader_real.py:43`, `packages/ml_contracts/tests/test_synthetic.py:36`; `NEAR` 25 px + vòng đếm chép ở hai tệp đầu (R-07).
- **[2 TÁI HIỆN]** `git grep -n 'DIMENSION_RE *=' -- apps packages` trên 6fd8dbf → 3 dòng (`W3/C09/tai-hien-NO-349.md`).
- **[3 BẰNG CHỨNG]** Ba dòng trên; phản biện P-10 lượt FIX-175.
- **[4 KHOANH VÙNG]** `packages/testing/ocr_metrics.py` (mới), `apps/ml/runtime/tests/test_ocr.py`, `packages/ml_contracts/tests/test_synthetic.py` (B5-01); phía `apps/ml/text/tests/test_reader_real.py` đi cùng FIX-175 (B5-04). Không chạm mã sản phẩm.
- **[5 SỬA NHỎ NHẤT]** Một tệp dùng cho test (`packages.testing`, import-linter cho `**.tests.** -> packages.testing.**`): `dimension_hits(found, answers) -> (đúng, tổng)`; ba test nhập lại.
- **[6 TEST CHẶN TÁI PHÁT]** `test_render_plan_ocr_readable`, `test_reader_reads_dimension_texts`, các test `test_synthetic` dùng thước chung xanh; `git grep` chỉ còn một định nghĩa.
- **[7 NGHIỆM THU]** `xanh349.log` (pytest + độ phủ `ocr_metrics.py`), `steps1234.log` bước 1–4; commit `acc5669`, `c0bde6f`.

## FIX-177 cho B5-02 — ranh giới nhập thiếu `ml_contracts`, thiếu ca Khung, mặt nạ cổ điển lệch khi k chẵn và mất cửa sổ, vectorize cắt nhầm vách mảnh ngắn (NO-283, NO-284, NO-286, NO-287, NO-288)

- **[1 TRIỆU CHỨNG]** NO-283: `test_boundary.py` không chặn `packages.ml_contracts` (chèn import vào `metrics.py`, test vẫn `9 passed`). NO-284: không test nào khẳng định `find_frame(render_plan(s)) is None`. NO-286: IoU trung bình 10 seed đầu 0,8152 (ngưỡng 0,80), seed 106 = 0,6999. NO-287: `classic_wall_mask` với k chẵn dời mặt nạ 1 px (5/5 ca đỏ). NO-288: vách 110 mm chạm tường 220 mm, ngắn ≤ 2·J, bị cắt như râu; vách ngắn qua bước 4 vẫn mất ở `_drop_short` (9/18 ca tay đỏ).
- **[2 TÁI HIỆN]** Cây 77d7180, `bash tools/verify/run.sh shell < W3/C10/red.sh | red2.sh`; lệnh, mã thoát: `W3/C10/tai-hien-NO-283/284/286/287/288.md`.
- **[3 BẰNG CHỨNG]** `packages/vision/walls/tests/test_boundary.py:14` `_BLOCKED` 4 tên; `classic.py:47-48` (cũ) `MORPH_OPEN` co/giãn cùng neo `k//2`; `packages/ml_contracts/synthetic.py:258-269` `_window`: 100 % FN của 40 seed nằm trong hộp cửa sổ; `vectorize.py:34,227-239` (cũ) `_SPUR_TIP_RATIO = 0.5` (vách thật T/J 0,40–0,417), `:455-476` `_drop_short` so `length < thickness` trước `_extend_leaves`.
- **[4 KHOANH VÙNG]** `packages/vision/walls/classic.py`, `vectorize.py`, `tests/*` (B5-02). Không chạm `packages/ml_contracts/synthetic.py`, không đổi ngưỡng test.
- **[5 SỬA NHỎ NHẤT]** `_open_square` neo phản chiếu cho k chẵn; `_bridge_windows` + `_closed_runs` đóng 1D vuông góc tường, chỉ giữ đoạn có tường ở cả hai đầu, mở lại k×k; `_SPUR_TIP_PX = 1.7` tuyệt đối; `_drop_short(segs, graph)` cộng `_leaf_reach`. Cùng chủ: docstring 18 test cũ, lý do sau `noqa`/`type: ignore`. Không đổi chữ ký công khai, không đổi `VectorizeResult`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_boundary.py::test_module_imports_with_ml_and_db_blocked[*]`, `::test_blocking_really_raises[packages.ml_contracts]`; `test_frame.py::test_find_frame__none_on_synthetic_page[seed]`; `test_classic.py::test_classic_wall_mask__even_kernel_keeps_band_in_place[k]`, `__window_gap_bridged_door_gap_kept`, `__single_line_between_walls_is_not_wall`; `test_quality.py::test_classic_wall_mask__window_gap_stays_wall[seed]`; `test_vectorize.py::test_vectorize__short_thin_wall_on_thick_wall_is_kept[...]`, `__very_thin_wall_on_very_thick_wall_is_kept[...]`. `test_spur_branch_is_pruned` đổi mẫu râu sang nét 1 px (lý do `W3/C10/vong1-*.md`), assert giữ nguyên.
- **[7 NGHIỆM THU]** Commit `e832f16`, `72a1ffb`. `fix2.log`: 204 passed, `classic.py` 100 % dòng/nhánh, `vectorize.py` 99 %. IoU mean10 0,8152 → 0,9843, không seed nào tụt. Bước 1–4: `verify14.log`.

## FIX-178 cho B5-02 — mô tả đường lùi cổ điển sau FIX-177 và cụm nét song song cách đều bị lấp thành tường (NO-348)

- **[1 TRIỆU CHỨNG]** Sau FIX-177 `classic_wall_mask` lấp khe cửa sổ nên mặt nạ có thể chứa điểm không có mực; tiêu đề `classic.py` và `apps/ml/walls/step.py:82` chưa nói. Đo trên CubiCasa5K thật: cầu thang, sàn ván, hatch vẽ nét dày ≥ k sống qua phép mở và bị `_bridge_windows` lấp (NO-348).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W3/C10/cc-measure.sh` (24 mẫu CubiCasa5K có Stairs/Railing, `cc-prep.py`) — `cc-measure.log`, mã thoát 0; C10c: ca tổng hợp ≥ 3 nét song song cách đều giữa hai vách đỏ trên `6db3829` (`c10c*.log`).
- **[3 BẰNG CHỨNG]** IoU tường 0,3793 → 0,4831 (tăng 21/24 mẫu) nhưng FP mới vùng cầu thang/lan can 491.717 px, 428.415 px ở 2 mẫu sàn ván (`look-hqa-10498.png`); bảng phương án `W3/C10/quyet-dinh.md` §C10b, §C10c.
- **[4 KHOANH VÙNG]** `apps/ml/walls/step.py` (docstring), `packages/vision/walls/classic.py` và test (B5-02). Không đổi `packages/ml_contracts/payloads.py` (B5-01), hợp đồng dữ liệu.
- **[5 SỬA NHỎ NHẤT]** C10b: sửa lời `step.py`/`classic.py`, ghi giới hạn đã đo vào docstring `_bridge_windows`. C10c (phương án C): dãy ≥ 4 nét dày cách đều rời mặt nạ tường; không bắc cầu qua các dãy đó hay dãy ≥ 5 nét mực cách đều.
- **[6 TEST CHẶN TÁI PHÁT]** `test_classic.py::test_classic_wall_mask__evenly_spaced_strokes_between_walls_are_not_wall`, `::test_classic_wall_mask__four_evenly_spaced_strokes_between_walls_are_not_wall`, `::test_classic_wall_mask__hollow_two_line_wall_is_filled` — đỏ trên `6db3829` → xanh.
- **[7 NGHIỆM THU]** Commit `6db3829`, `5e86272`. 24 mẫu CubiCasa: FP cầu thang/lan can −63 %, IoU tường 0,483 → 0,481; 40 seed tổng hợp IoU trung bình 0,9845 không đổi. `verify14b.log`, `verify14c.log`, `c10b-test.log`.

## FIX-179 cho B6-04a — `training_segformer`: test GPU không chạy được, `export_and_check` dài và nhánh chết, seed mỗi epoch, ctor, quét AST lọt, `HF_HUB_OFFLINE` chưa đặt (NO-316, NO-317, NO-318, NO-333)

- **[1 TRIỆU CHỨNG]** `test_gpu.py` không chạy được trên máy CUDA (đường model + khổ ảnh sai); `export_and_check` 71 dòng, nhánh `has_external_data` chết; lệch P3 (seed mỗi epoch, ctor, quét AST K12 lọt, 2 `type: ignore` tự gây, reset cache tay); `HF_HUB_OFFLINE` (BE-00 §9) không được đặt.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W3/C11/red.sh` trên cây chưa sửa: 5 failed, 11 passed, 1 error collect (mã thoát 1); `W3/C11/tai-hien-NO-316/317/318/333.md`.
- **[3 BẰNG CHỨNG]** `test_gpu.py:129-130` (`Path(name).parent == '.'`); `support.py:84` (800×600 cứng); `export.py:76-86` (nhánh chết sau checker, hàm 71 dòng); `loop.py:92` (cùng seed); `trainer.py:48-61`; `model.py:14` (`transformers` nhập mức module, không env).
- **[4 KHOANH VÙNG]** `apps/ml/training_segformer/{__init__,export,loop,trainer}.py` và `tests/{support,test_gpu,test_export,test_model,test_trainer,test_support}.py` (B6-04a). Lệch cùng loại của `YoloTrainer` ở FIX-180.
- **[5 SỬA NHỎ NHẤT]** NO-333: `os.environ.update` `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE` trong `__init__.py` của gói (lệch SEC-062 [5]: update thay setdefault vì BE-00 §9 là lệnh). NO-317: tách `_check_exported_format`/`_parity_agreement`, `has_external_data` trước `check_model`. NO-316: `write_split(width_px, height_px)` + `support.load_pinned_base` dùng `trainer._settings_models_dir()`. NO-318: `kw_only` + property `family`, `manual_seed(seed + epoch)`, `optimizer_cls: Callable[..., AdamW]`, `_violations` quét AST, bỏ reset cache tay.
- **[6 TEST CHẶN TÁI PHÁT]** `test_support.py::{test_write_split__custom_size, test_write_split__default_size_unchanged, test_load_pinned_base__reads_ml_models_dir}`; `test_export.py::{test_export_external_data__rejected_by_has_external_data, test_export_and_check__within_length_limit, test_export_rejects_invalid_graph}`; `test_trainer.py::{test_loader__generator_seed_differs_per_epoch, test_trainer__keyword_only_and_family_fixed}`; `test_model.py::{test_ast_scan__flags_every_unsafe_form, test_load_base_model__hf_offline_env_forced}`.
- **[7 NGHIỆM THU]** Đỏ → xanh theo `tai-hien-*.md`; `verify --steps 1,2,3,4` và độ phủ từng tệp (`W3/C11/cov.log`, `verify14.log`); commit `a99e642`. `test_train_gpu_mitb1_fits_6gb` chưa chạy — máy không CUDA.

## FIX-180 cho B6-04b — ctor `YoloTrainer` không keyword-only, `family` tiêm được (NO-318, cùng lệch P3-10 của segformer)

- **[1 TRIỆU CHỨNG]** `YoloTrainer("...")` theo vị trí và `YoloTrainer(family=...)` dựng được; hợp đồng [2] đòi ctor keyword-only, `family` cố định.
- **[2 TÁI HIỆN]** `W3/C11/red-yolo.log`: `run.sh shell < red-yolo.sh` → 1 failed (`test_trainer__keyword_only_and_family_fixed`), mã thoát 1.
- **[3 BẰNG CHỨNG]** `apps/ml/training_yolo/trainer.py:250-262` (`@dataclass(frozen=True, slots=True)`, `family: TrainableFamily = _FAMILY`); mọi caller đều keyword (`tests/test_gpu.py:39`, `tests/test_trainer.py:89`, `trainer.py:412`).
- **[4 KHOANH VÙNG]** `apps/ml/training_yolo/trainer.py` (chỉ ctor/decorator — khác hunk với `_tick`/`_emit` của FIX-181), `tests/test_trainer.py` (B6-04b).
- **[5 SỬA NHỎ NHẤT]** `kw_only=True` + `@property family` trả `_FAMILY` (khớp `Trainer.family` ở `ports.py:79-80`).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/training_yolo/tests/test_trainer.py::test_trainer__keyword_only_and_family_fixed`.
- **[7 NGHIỆM THU]** `green-yolo.log`: 38 passed, `trainer.py` 97 % dòng+nhánh, mã thoát 0; `verify14-yolo.log` `--steps 1,2,3,4` mã thoát 0; commit `391aafb`.

## FIX-181 cho B6-04b — `_emit` suy split từ giá trị, `last_map50` gác theo loss, stdout con đọc cả luồng, epoch nhịp tim lùi, test yếu (NO-319 phía gọi, NO-320, NO-321)

- **[1 TRIỆU CHỨNG]** NO-320: epoch không validate log `training_metric_skipped metric="loss"` hai lần; loss NaN + map50 hợp lệ ⇒ `TRAINING_METRICS_MISSING`. NO-321: một dòng lạ trên stdout con ⇒ `MODEL_FORMAT_UNSUPPORTED`. NO-319 (phía gọi): `ml_eval/tasks.py` nhập `_read_object`. C12b: nhịp tim pha final_eval báo epoch = epochs+1 rồi `_export` báo `spec.epochs` → số epoch lùi.
- **[2 TÁI HIỆN]** `W3/C12/tai-hien-NO-320-321-319.md`; `red.log`, `red2.log` (3 + 7 đỏ) trên 77d7180; `red3.log` (thoát 1): `test_heartbeat_epochs_never_decrease_nor_exceed_spec_epochs` FAILED.
- **[3 BẰNG CHỨNG]** `apps/ml/training_yolo/trainer.py` `_emit`/`on_fit_epoch_end`/`_tick`; `apps/ml/ml_eval/tasks.py` `_result`; `sandbox.py` `main`.
- **[4 KHOANH VÙNG]** `apps/ml/training_yolo/{trainer.py,tests/test_trainer_units.py}`, `apps/ml/ml_eval/{tasks.py,sandbox.py,tests/test_sandbox.py,tests/test_evaluate.py}` (B6-04b). `loader.py` thuộc FIX-182.
- **[5 SỬA NHỎ NHẤT]** `_emit(epoch, name, value, *, high)`; `last_map50` theo map50; `RESULT_PREFIX` + `_result` chỉ đọc dòng có tiền tố; assert RLIMIT_AS; expected AP tính tay 0,665; test nhịp tim pha val; `tasks.py` gọi `read_model_object`; `_tick` báo `min(epochs_done + 1, epochs)`. Không đổi hợp đồng (giao thức cha–con nội bộ).
- **[6 TEST CHẶN TÁI PHÁT]** `test_on_fit_epoch_end__epoch_without_validation_skips_map50_not_loss`, `test_on_fit_epoch_end__nan_loss_keeps_the_valid_map50`, `test_on_val_batch_end__sends_heartbeat_once_interval_passed`, `test_heartbeat_epochs_never_decrease_nor_exceed_spec_epochs`, `test_ml_eval_sandbox_result_ignores_foreign_stdout_lines`, `test_ml_eval_sandbox_result_without_metrics[...]`, `test_evaluate_family_object_detection_matches_hand_computed_ap`.
- **[7 NGHIỆM THU]** Đỏ → xanh (tệp tái hiện); `cov2.log` thoát 0, 41 passed, `trainer.py` 97 % dòng+nhánh; `verify --steps 1,2,3,4` thoát 0 (`verify14b.log`); commit `5b23e15`, `b67e448`.

## FIX-182 cho B5-01 — `_read_object` riêng tư bị `ml_eval` nhập; công khai thành `read_model_object` (NO-319)

- **[1 TRIỆU CHỨNG]** `apps/ml/ml_eval/tasks.py:28` nhập `_read_object` của `apps.ml.runtime.loader`.
- **[2 TÁI HIỆN]** `W3/C12/red.log`: `test_read_model_object__returns_bytes_and_maps_missing_to_model_not_found` đỏ (AttributeError).
- **[3 BẰNG CHỨNG]** `git grep _read_object`: chỉ `loader.py:193,249` và `tasks.py:28,161`.
- **[4 KHOANH VÙNG]** `apps/ml/runtime/loader.py`, `apps/ml/runtime/tests/test_loader.py` (B5-01); phía gọi `ml_eval` ở FIX-181.
- **[5 SỬA NHỎ NHẤT]** Đổi tên, giữ chữ ký, trần `MODEL_MAX_BYTES` và mã lỗi; không alias.
- **[6 TEST CHẶN TÁI PHÁT]** `test_read_model_object__returns_bytes_and_maps_missing_to_model_not_found`.
- **[7 NGHIỆM THU]** Đỏ → xanh; `loader.py` 99 %; commit `6e6e32c`, `b0fbeb9` (đứng trước commit FIX-181; nhánh gộp squash nên `main` không có điểm giữa đỏ).

## FIX-184 cho B0-05 — `with_db` ghi đè số DB của URL nên nhiều tiến trình không chung được một Redis (NO-270)

- **[1 TRIỆU CHỨNG]** `pytest -n 4`: mỗi tiến trình xdist dựng 2 Redis riêng — đỉnh 12 container, 9 Redis (`W3/C05c/n4-truoc-sau.log`); cổng xdist phải chạy một mình.
- **[2 TÁI HIỆN]** 1308068 + test mới: `bash tools/verify/run.sh shell < W3/C05c/do-n4.sh` → `test_with_db__two_processes_on_one_redis_keep_their_own_roles` FAILED, mã 1 (`n4-truoc.log`).
- **[3 BẰNG CHỨNG]** `packages/messaging/redis.py:115-118` (gốc) đặt path `/{db}` tuyệt đối, `:33-36` BROKER 0/STREAM 1/SAFE 2/CACHE 0; `celery_app.py:90,168` dùng URL nguyên trạng; `settings.py:23` (gốc) "đường dẫn bị bỏ qua".
- **[4 KHOANH VÙNG]** `packages/messaging/{redis.py,settings.py}`, `packages/messaging/tests/{test_redis.py,test_settings.py,test_streams.py}`, `packages/testing/fixtures/messaging.py` (`db_client_count`). Không chạm `deploy/*`, `celery_app.py`.
- **[5 SỬA NHỎ NHẤT]** `with_db` = DB gốc của URL (vắng = 0) + độ lệch vai — URL triển khai `/0` ⇒ hành vi production không đổi; validator từ chối path không phải số, có tên biến (R-17); `db_client_count` đếm `CLIENT LIST` theo DB.
- **[6 TEST CHẶN TÁI PHÁT]** `test_redis.py::test_with_db__two_processes_on_one_redis_keep_their_own_roles` (Redis thật + tiến trình thật), `::test_with_db_offsets_the_url_database_by_the_role`; `test_settings.py::test_redis_url__non_numeric_database_path_is_rejected_with_its_variable`, `::test_redis_url__empty_or_numeric_database_path_is_accepted` — đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `24f1d11`, `6bf27cf`, `0d023e7`; `W3/C05c/verify14.log`, `cov.log`.

## FIX-185 cho B0-01 — Redis test dựng một bản mỗi tiến trình xdist (NO-270)

- **[1 TRIỆU CHỨNG]** `-n 4`: 9 container Redis ở đỉnh (2/tiến trình + ephemeral), tổng 12 container, 96 s.
- **[2 TÁI HIỆN]** `W3/C05c/n4-truoc-sau.log` phần TRƯỚC (`redis.py` + `services.py` gốc), mã pytest 1.
- **[3 BẰNG CHỨNG]** `packages/testing/fixtures/services.py:251-268` (gốc) `redis_broker_url`/`redis_cache_url` `_start` thẳng; docstring `_shared_container` `:193-197` (gốc) loại Redis vì vai = số DB.
- **[4 KHOANH VÙNG]** `packages/testing/fixtures/services.py`, `tools/tests/test_shared_services.py` (B0-01). Không đổi `deploy/compose/verify.yml` (`--databases` ở lệnh container của fixture).
- **[5 SỬA NHỎ NHẤT]** Hai fixture qua `_shared_container` (`redis-<policy>`), URL `/<gwN × REDIS_ROLE_DBS>` (`redis_db_base`, dùng `with_db` của FIX-184); `--databases max(16, 3 × PYTEST_XDIST_WORKER_COUNT × 5)` — 5 mã `gwN` mỗi chỗ vì xdist thay tiến trình chết bằng mã tăng dần; ephemeral giữ 16. Gộp W3 giữ sửa NO-347 của `main` (`sweep_orphans`).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_shared_services.py::test_redis_db_base__each_worker_gets_its_own_block`, `::test_shared_redis__two_workers_share_one_container_on_their_own_blocks`; số đo `-n 4` sau: 5 container (2 Redis), 70 s, 3004 passed.
- **[7 NGHIỆM THU]** Commit `adc1cd9`, `ac93def`, `0274d6f`, `e3fd234`, `bc52e86`; cổng đầy đủ ở việc gộp `W3/M`.

## FIX-186 cho B4-01 — S05 đếm `CLIENT LIST` cả máy chủ, flaky khi Redis test dùng chung (NO-270)

- **[1 TRIỆU CHỨNG]** Sau FIX-185 mọi tiến trình xdist chung một Redis: `len(client_list())` gồm kết nối của tiến trình khác → `after - before <= 1` có thể đỏ ngẫu nhiên.
- **[2 TÁI HIỆN]** Không dựng được đỏ tất định (phụ thuộc lịch tiến trình khác); rủi ro chỉ bằng mã: `apps/api/streams/tests/test_streams_open_progress.py:236-244` đếm toàn máy chủ.
- **[3 BẰNG CHỨNG]** `CLIENT LIST` là lệnh phạm vi máy chủ; mỗi mục có trường `db`.
- **[4 KHOANH VÙNG]** `apps/api/streams/tests/test_streams_open_progress.py` (B4-01, 3 dòng; điều phối duyệt ngoài whitelist).
- **[5 SỬA NHỎ NHẤT]** Dùng `db_client_count(streams_client)` (FIX-184) — chỉ kết nối vào DB Streams của chính tiến trình.
- **[6 TEST CHẶN TÁI PHÁT]** Chính `test_streams_open_progress__S05` (đếm theo DB); `-n 4` sau sửa xanh.
- **[7 NGHIỆM THU]** Commit `026c5d6`.

## FIX-189 cho B5-07 — trần đồng hồ tường của `test_quality_replay_redis_hang_skips` chưa `perf` (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: `apps/worker/pipeline_quality/tests/test_runtime.py` khẳng định trần 2 s mà không `perf` (BE-00 §12); thêm tệp vào `SCANNED` của `tools/tests/test_perf_marks.py` → đỏ.
- **[2 TÁI HIỆN]** `run.sh shell < W3/C34/red.sh` trên 5ec9edb: 6 failed (một mỗi tệp mới quét), mã thoát 1 (`W3/C34/tai-hien-NO-343.md`, `red.log`).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` bảng P-1…P-8; số đo 1,009 s.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_quality/tests/test_runtime.py` (B5-07), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Gắn `@pytest.mark.perf`, log số đo. Trần 2,0 s giữ nguyên dù < 3× số đo: đó là trần thiết kế = timeout nội bộ 1 s (`service.py:52`) + mép, không phải trần đo (P-6, "Lệch khỏi prompt" của C34; reviewer phán).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[apps/worker/pipeline_quality/tests/test_runtime.py]` đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `5c34815`; bước 1–4 đạt (`W3/C34/verify-1-4.log`, mã thoát 0); cổng đầy đủ ở việc gộp `W3/M`.

## FIX-190 cho B5-06c — trần đồng hồ tường của `test_sweep_survives_unreadable_queue` chưa `perf`, docstring mâu thuẫn BE-00 §12 (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: `apps/worker/pipeline_steps/tests/test_sweep_rules.py` khẳng định trần 2 s mà không `perf`; docstring nói ngược BE-00 §12.
- **[2 TÁI HIỆN]** Như FIX-189 (`W3/C34/red.log`, mã thoát 1).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` P-1…P-8; số đo ~1,01 s.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_steps/tests/test_sweep_rules.py` (B5-06c), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Gắn `perf`, sửa docstring. Trần 2,0 s giữ nguyên (sàn thiết kế 1 s ở `sweep.py:46`, P-6), như FIX-189.
- **[6 TEST CHẶN TÁI PHÁT]** `test_scanned_files_mark_wall_clock_ceilings_perf[apps/worker/pipeline_steps/tests/test_sweep_rules.py]` đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `1a9bd7d`; bước 1–4 đạt (`verify-1-4.log`).

## FIX-191 cho B2-06 — trần đồng hồ tường của `test_build_all_assets_under_one_second` chưa `perf` (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: `packages/domain/library/tests/test_catalogue.py` khẳng định trần 1 s mà không `perf`.
- **[2 TÁI HIỆN]** Như FIX-189 (`W3/C34/red.log`, mã thoát 1).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` P-1…P-8; số đo 0,009 s.
- **[4 KHOANH VÙNG]** `packages/domain/library/tests/test_catalogue.py` (B2-06), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Gắn `perf`, log số đo.
- **[6 TEST CHẶN TÁI PHÁT]** `test_scanned_files_mark_wall_clock_ceilings_perf[packages/domain/library/tests/test_catalogue.py]` đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `8830c4e`; bước 1–4 đạt (`verify-1-4.log`).

## FIX-192 cho B6-03b — trần đồng hồ tường của `test_run_training_job_cancel_while_waiting` chưa `perf` (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: `apps/ml/training_runner/tests/test_runtime.py` khẳng định trần 10 s mà không `perf`.
- **[2 TÁI HIỆN]** Như FIX-189 (`W3/C34/red.log`, mã thoát 1).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` P-1…P-8; số đo 0,006 s.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/tests/test_runtime.py` (B6-03b), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Gắn `perf`, log số đo.
- **[6 TEST CHẶN TÁI PHÁT]** `test_scanned_files_mark_wall_clock_ceilings_perf[apps/ml/training_runner/tests/test_runtime.py]` đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `5983d8f`; bước 1–4 đạt (`verify-1-4.log`).

## FIX-193 cho B0-10 — assert đồng hồ tường trong test script triển khai thay bằng hạn `timeout` của subprocess (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: `deploy/scripts/tests/test_smoke.py`, `test_deploy.py` khẳng định thời gian chạy bằng đồng hồ tường, không `perf`.
- **[2 TÁI HIỆN]** Như FIX-189 (`W3/C34/red.log`, mã thoát 1).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` P-1…P-8: `tools/coverage_gate.py::unit_of` bỏ `deploy/`, nên test `perf` ở đây không được bước 5c chạy — `perf` không phải chỗ đúng.
- **[4 KHOANH VÙNG]** `deploy/scripts/tests/test_smoke.py`, `deploy/scripts/tests/test_deploy.py` (B0-10).
- **[5 SỬA NHỎ NHẤT]** Bỏ assert đồng hồ; hạn `timeout=` của subprocess (smoke 8 s, deploy 15 s) giữ cận trên.
- **[6 TEST CHẶN TÁI PHÁT]** `test_scanned_files_mark_wall_clock_ceilings_perf[deploy/scripts/tests/test_smoke.py]`, `[deploy/scripts/tests/test_deploy.py]` đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `2c81e69`; bước 1–4 đạt (`verify-1-4.log`).

## FIX-194 cho B0-01 — `SCANNED` của `test_perf_marks` thiếu bảy tệp có trần đồng hồ tường (NO-343)

- **[1 TRIỆU CHỨNG]** NO-343: quét `perf` (`tools/tests/test_perf_marks.py`) chỉ phủ các tệp C07 đã rà; bảy tệp có trần đồng hồ tường nằm ngoài `SCANNED`.
- **[2 TÁI HIỆN]** Thêm sáu tệp của FIX-189…193 vào `SCANNED` trên 5ec9edb → 6 failed, mã thoát 1 (`W3/C34/red.log`).
- **[3 BẰNG CHỨNG]** `W3/C34/quyet-dinh.md` P-1…P-8; tệp thứ bảy `apps/ml/text/tests/test_reader_real.py` sửa ở FIX-175 (C09).
- **[4 KHOANH VÙNG]** `tools/tests/test_perf_marks.py` (B0-01).
- **[5 SỬA NHỎ NHẤT]** Thêm sáu tệp vào `SCANNED` (C34); việc gộp W3 thêm `apps/ml/text/tests/test_reader_real.py` sau khi gộp C09 → NO-343 đủ 7/7.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[*]` cho cả bảy tệp.
- **[7 NGHIỆM THU]** Commit `036e9e7` (nhánh `fix/debt-02-w3-perf-docs`), `e52aab4` (nhánh `fix/debt-02-w3`); cổng đầy đủ ở việc gộp `W3/M`.

## FIX-201 cho B3-06 — luật 2 đổi tường người trùng id; chỉ mục tường chéo O(dài²) (NO-251, NO-252)

- **[1 TRIỆU CHỨNG]** Lớp có hai tường trùng id (AI + người): tường người thành `envelope`, tin cậy 0,5 (K21). Tường chéo 72 m vào ~2.700 ô lưới.
- **[2 TÁI HIỆN]** `run.sh shell < W4/C13/red.sh` trên bcb2301 (main 5ec9edb + test): 2 failed, pytest mã thoát 1 (`W4/C13/red.log`).
- **[3 BẰNG CHỨNG]** `post_rules.py` `_fix_windows` (`_envelope(w) if w.id in promoted`), `_WallIndex.__init__` nạp hộp bao nở; `reference.py:75` cùng lỗi.
- **[4 KHOANH VÙNG]** `packages/domain/rules_ai/{post_rules.py, tests/reference.py, tests/test_post_rules.py, tests/test_perf.py}`.
- **[5 SỬA NHỎ NHẤT]** `and _editable(w)`; `_band_cells` duyệt cột ô theo đường tim (siêu tập, nở 1 mm). Không đổi hợp đồng.
- **[6 TEST CHẶN TÁI PHÁT]** `test_apply_post_rules__duplicate_wall_id_human_copy_untouched`, `test_wall_index__diagonal_wall_cells_linear_in_length` (đỏ → xanh); thêm `…human_first_nothing_promoted`, `test_wall_index__vertical_and_negative_walls_match_full_scan`, perf `test_perf_apply_post_rules_on_long_diagonal_walls`.
- **[7 NGHIỆM THU]** `green.log` 4 passed / 261 passed; `post_rules.py` 100 % dòng+nhánh; verify bước 1–4 đạt; commit `dfaa3cb`.

## FIX-202 cho B5-06b — test giữ khoá 20.000 tường chỉ in số, không khẳng định (NO-296)

- **[1 TRIỆU CHỨNG]** `test_persist_lock_hold_20k_walls` không khẳng định gì; khoá floors 21,08 s không bị chặn thoái lui.
- **[2 TÁI HIỆN]** `W4/C13/prof.log`: `lock_hold_20k_walls_s=15.834` (cProfile), mã thoát 0 (chỉ in).
- **[3 BẰNG CHỨNG]** `test_persist_lock.py`: `BIG_HOLD_DEBT_S` chỉ dùng trong log.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_persist/tests/test_persist_lock.py`.
- **[5 SỬA NHỎ NHẤT]** `BIG_HOLD_CEILING_S = 30` (≥ 3 × 9,54 s, số đo lớn nhất sau FIX-203) + assert.
- **[6 TEST CHẶN TÁI PHÁT]** `test_persist_lock_hold_20k_walls` (perf) — không đỏ ở 21 s (30 > 21): là trần chống thoái lui, tái hiện thật ở FIX-203.
- **[7 NGHIỆM THU]** `W4/C13/c13b.log`: `-m perf` 2 passed, 20k = 9,538 s, mã thoát 0; verify bước 1–4 đạt; commit `9089a97`.

## FIX-203 cho B3-03 — `_write_log` executemany 140k dòng dưới khoá tầng (NO-296)

- **[1 TRIỆU CHỨNG]** `pipeline.persist.run` giữ khoá floors 15,8–21 s trên lớp 20.000 tường.
- **[2 TÁI HIỆN]** `W4/C13/prof.sh` (cProfile) — `_write_log` 12,9/15,8 s; `meas.log`/`meas2.log`: ORM 11,8 s, Core executemany 11,1 s, COPY 5,56 s, unnest 5,99 s.
- **[3 BẰNG CHỨNG]** `writer.py` `_write_log`: `db.execute(insert(FloorChangeLogRow), [140k dict])` → asyncpg executemany ~80 µs/dòng.
- **[4 KHOANH VÙNG]** `apps/api/spatial_write/{writer.py, tests/test_writer.py}` (điều phối mở whitelist, `W4/C13/ask296.log` "A").
- **[5 SỬA NHỎ NHẤT]** `INSERT … SELECT FROM unnest(4 mảng) WITH ORDINALITY ORDER BY`, chia khúc 20.000 (`statement_timeout` 10 s); Core, cùng session/SAVEPOINT; dữ liệu và thứ tự id như cũ.
- **[6 TEST CHẶN TÁI PHÁT]** `test_write_log__one_statement_per_chunk` (đỏ bằng assert trên writer gốc: "7 dòng nhật ký đi 1 câu, executemany=[True]", mã thoát 1 → xanh mã thoát 0, `c13b.log`); `test_write_log__chunked_rows_equal_diff_in_order` (so từng dòng, nhiều khúc).
- **[7 NGHIỆM THU]** `green.log`: 261 passed; `writer.py` 100 % dòng+nhánh; giữ khoá 20k 8,46 s; verify bước 1–4 đạt; commit `3422b8f`.

## FIX-204 cho B0-04 — `packages/storage` thiếu khoá khúc/trang/mẫu nhiều đoạn, `create_storage(s3, None)` vẫn ký URL (NO-263, NO-215, NO-217, NO-203)

- **[1 TRIỆU CHỨNG]** `dataset_object` từ chối `train/s1/image.png` (ValueError); không có `keys.upload_chunk`/`upload_page_revision`; `server_chosen_kind` không nhận `pages/{i}-{ULID}.png`; `create_storage(s3, None)` vẫn ký URL (DID NOT RAISE).
- **[2 TÁI HIỆN]** `run.sh shell < W4/C15a/red.sh` trên cây chưa sửa → mã thoát 1, 5 failed (`W4/C15a/red1.log`).
- **[3 BẰNG CHỨNG]** `keys.py` `_name` một đoạn; `factory.py:63-68` luôn dựng `public_client`.
- **[4 KHOANH VÙNG]** `packages/storage/{keys,factory}.py` + test. Cấm `s3.py`/`local.py`.
- **[5 SỬA NHỎ NHẤT]** `_path`, `upload_chunk`, `upload_page_revision`, nhánh mới `server_chosen_kind`, `_UnsignedS3Storage`; C15a-b thêm `dataset_version_prefix` làm gốc khoá dataset duy nhất (R-19, `W4/C15a/spec-C15a-b.md`).
- **[6 TEST CHẶN TÁI PHÁT]** `test_dataset_object__accepts_multi_segment_sample_path`, `test_upload_chunk__layout_and_rules`, `test_upload_page_revision__is_a_server_chosen_png`, `test_create_storage__s3_without_core_settings_refuses_to_sign`.
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C15a/gate14*.log`); `keys.py`, `factory.py` 100 % dòng+nhánh; commit `45b5ece`, `cc6d289` (docstring test), `2a2c28d` (`dataset_version_prefix`).

## FIX-205 cho B2-04 — khoá khúc dựng riêng ở `uploads.chunk_key`, `drawing_url` ký trang dạng attachment (NO-215, NO-217)

- **[1 TRIỆU CHỨNG]** Khoá khúc dựng ở `uploads.chunk_key`; `drawing_url` ký `attachment` cho trang.
- **[2 TÁI HIỆN]** `test_drawing_url__page_is_signed_inline_png` đỏ (`assert 'attachment' == 'inline'`) — `W4/C15a/red1.log`.
- **[3 BẰNG CHỨNG]** `uploads.py:92`, `drawings.py:44-49`.
- **[4 KHOANH VÙNG]** `apps/api/drawings/{uploads.py, drawings.py}`, test, `packages/testing/factories/drawings.py`.
- **[5 SỬA NHỎ NHẤT]** Xoá `chunk_key`, gọi `keys.upload_chunk`; `new_page_key` gọi `upload_page_revision`; `drawing_url` ký `inline` + kind khi `server_chosen_kind` có, khoá lạ giữ `attachment` (tránh stat → NOT_FOUND của quality NO-226). Hợp đồng FE–BE không đổi (URL vẫn là chuỗi URL ký).
- **[6 TEST CHẶN TÁI PHÁT]** `test_drawing_url__page_is_signed_inline_png`, `test_drawing_url__foreign_key_is_signed_attachment` (thay `test_drawing_url_is_signed_attachment`).
- **[7 NGHIỆM THU]** Như FIX-204; `drawings.py`, `uploads.py` 100 %; commit `3bce219`.

## FIX-206 cho B6-02 — writer dataset lách `dataset_object` bằng `_sample_key`, `version_prefix` tự dựng bố cục (NO-263)

- **[1 TRIỆU CHỨNG]** `apps/worker/datasets/writer.py` lách `dataset_object` bằng `_sample_key`; `apps/worker/datasets/tasks.py:154` `version_prefix` dựng f-string `ml/datasets/{id}/` không `check_id` (bản chép thứ ba bố cục, `W4/C15a/spec-C15a-b.md`).
- **[2 TÁI HIỆN]** Xem FIX-204 (hàm chung).
- **[3 BẰNG CHỨNG]** `writer.py:34-41` cũ; `tasks.py:154`.
- **[4 KHOANH VÙNG]** `apps/worker/datasets/{writer.py, tasks.py, jobs.py}`, `tests/{test_writer.py, test_smoke.py}`.
- **[5 SỬA NHỎ NHẤT]** Xoá `_sample_key`, gọi `dataset_object(version, rel_path)`; `version_prefix` và gốc purge lấy từ `packages/storage/keys.py` (`dataset_version_prefix`).
- **[6 TEST CHẶN TÁI PHÁT]** `test_add_sample_and_finish__manifest_matches_objects` (thêm assert stat theo `dataset_object`).
- **[7 NGHIỆM THU]** Như FIX-204; `writer.py` 100 %; commit `fd2d73e`, `5b5b182` (docstring test), `592459a` (version prefix, purge root), `bbdd004` (audit R-01).

## FIX-207 cho B6-03b — `sample_key` dựng khoá mẫu riêng, không qua `dataset_object` (NO-263)

- **[1 TRIỆU CHỨNG]** `sample_key` dựng khoá riêng bằng `check_key` + `check_id`, docstring nói "không qua dataset_object".
- **[2 TÁI HIỆN]** `test_sample_key__builds_through_dataset_object` đỏ trên cây cũ (monkeypatch thuộc tính `dataset_object` không tồn tại) — `W4/C15a/red2.log`.
- **[3 BẰNG CHỨNG]** `apps/ml/training_runner/keys.py:47-57` cũ.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/keys.py` + `tests/test_keys.py`.
- **[5 SỬA NHỎ NHẤT]** Sau khi kiểm ba đoạn + `sample_path`, trả `dataset_object(dsv, path)`; bỏ `check_key`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_sample_key__builds_through_dataset_object` (+ `test_sample_key_layout_and_rejects_bad_paths` giữ nguyên, xanh).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0; `keys.py` 100 % dòng+nhánh; commit `d3ee0cd`.

## FIX-209 cho B0-04 — kho object thiếu hàm đọc có trần, `delete` S3 để lọt `S3Error` 4xx, settings nhận khoá mẫu và lộ endpoint (NO-225, NO-230, SEC-041 phần storage)

- **[1 TRIỆU CHỨNG]** Sáu nơi tự viết lại vòng `async for … open_read: buf += chunk`; `delete` S3 ném `S3Error` thô; `StorageSettings` nhận `change-me-*` ở production và in `{url!r}`; `_UnsignedS3Storage` là lớp con thứ hai.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W4/C15b/red.sh` (và `red2.sh`) trên nhánh `fix/debt-02-w4-storage-read` trước khi sửa (`W4/C15b/tai-hien-NO-225.md`, `red-run.log`): `test_read_all_capped.py` lỗi thu thập (ImportError), mã pytest 2; placeholder/echo/delete 7 failed, 1 passed, mã thoát 1.
- **[3 BẰNG CHỨNG]** `packages/storage/port.py`, `s3.py`, `s3.py:75-90,195-199`, `settings.py:26`, `factory.py` (đã gộp từ nhánh C15a); `W4/C15b/quyet-dinh.md` P-1, P-7…P-10.
- **[4 KHOANH VÙNG]** `packages/storage/{port,s3,settings,factory}.py` và test. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** `read_all_capped` ở `port.py`; `delete` đổi `S3Error` 4xx thành `INTERNAL` (không đụng `_s3_errors`); `S3Storage(public_client=None)` thay lớp con; `app_env` + từ chối `change-me*`; thông điệp lỗi endpoint chỉ in scheme/host. Không đổi hợp đồng công khai (mã lỗi từng nơi giữ nguyên).
- **[6 TEST CHẶN TÁI PHÁT]** `test_read_all_capped__*` (có quét AST `apps/**`, mở rộng sang dạng `chunks.append`), `test_delete__missing_bucket_is_an_app_error`, `test_delete__denied_request_is_an_app_error`, `test_s3_placeholder_credentials__*`, `test_invalid_endpoint__error_does_not_echo_credentials`, `test_signed_url__without_a_public_client_is_refused`.
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0 (ruff, format, mypy sạch, 1272 passed, TOTAL 99 %); test ở [6] đỏ → xanh; commit `d9ee089`, `5e3968b` (docstring R-01), `63e26fc` (format), `5e69146` (quét AST dạng `chunks.append`).

## FIX-210 cho B2-05b — `_read_capped` lặp mẫu gom-tới-trần; docstring `_discard_orphan` khẳng định sai/thừa (NO-225, NO-230 phần docstring)

- **[1 TRIỆU CHỨNG]** `apps/api/quality/service.py:208-215`, `:277-283`: vòng gom-tới-trần tự viết; docstring `_discard_orphan` khẳng định sai/thừa.
- **[2 TÁI HIỆN]** Như FIX-209 (`W4/C15b/tai-hien-NO-225.md`: quét AST thấy `quality/service.py:211`).
- **[3 BẰNG CHỨNG]** `apps/api/quality/service.py`.
- **[4 KHOANH VÙNG]** `apps/api/quality/service.py`. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** `_read_capped` thành lời gọi `read_all_capped(..., too_large=IMAGE_TOO_LARGE.error)`; docstring nêu hợp đồng `delete` đã đóng (chỉ ném `AppError`/`OSError`). Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** Quét AST `test_read_all_capped__no_other_module_reimplements_the_accumulate_loop`; `apps/api/quality/tests` hiện có (422 `IMAGE_TOO_LARGE`, 404 giữ nguyên).
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0 (1272 passed); commit `2a93f90`.

## FIX-211 cho B2-04 — luật cửa sổ khôi phục chỉ có dạng riêng tư `_out_of_window` (NO-297 phần cửa sổ)

- **[1 TRIỆU CHỨNG]** `apps/api/drawings/runs.py:319-330` giữ luật cửa sổ ở hàm riêng tư; `pipeline_persist/service.py` viết lại.
- **[2 TÁI HIỆN]** `W4/C15b/red-run.log`: `test_restore_window_elapsed__boundary` FAILED (ImportError `restore_window_elapsed`).
- **[3 BẰNG CHỨNG]** `apps/api/drawings/runs.py` (+ test); `W4/C15b/quyet-dinh.md` P-5.
- **[4 KHOANH VÙNG]** `apps/api/drawings/runs.py`, `apps/api/drawings/tests/test_runs.py`. `complete.py` không đổi: `_read_head`/`_concat` đọc một phần/stream, không thuộc mẫu gom-tới-trần (P-3).
- **[5 SỬA NHỎ NHẤT]** Tách `restore_window_elapsed(deleted_at, clock)` công khai; `_out_of_window` gọi lại; docstring nêu nửa mở `[0, window)` (BE-00 §7). Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** `test_restore_window_elapsed__boundary`, `test_record_step_fails_the_run_exactly_at_the_window_edge` (`apps/api/drawings/tests/test_runs.py`).
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0; commit `e406a51`, `3c885da` (docstring `_snapshot`, R-01), `7454791` (docstring nửa mở + test biên).

## FIX-212 cho B5-01 — `loader.read_model_object` và `tasks_util._read_page` lặp vòng gom-tới-trần (NO-225)

- **[1 TRIỆU CHỨNG]** `apps/ml/runtime/loader.py:203`, `tasks_util.py:112` tự viết vòng gom-tới-trần.
- **[2 TÁI HIỆN]** Như FIX-209 (quét AST thấy `ml/runtime/loader.py:203`, `ml/runtime/tasks_util.py:112`).
- **[3 BẰNG CHỨNG]** `apps/ml/runtime/{loader,tasks_util}.py`.
- **[4 KHOANH VÙNG]** `apps/ml/runtime/{loader,tasks_util}.py`. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** Hai hàm gọi `read_all_capped`; `stat` tiền kiểm của loader giữ; `NOT_FOUND` → `PermanentError` như cũ. Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** Quét AST + `apps/ml/runtime/tests` hiện có (M02 size cap, object vanishes).
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0; commit `01499b4`.

## FIX-213 cho B5-06a — `preprocess._read_capped` lặp vòng gom-tới-trần (NO-225)

- **[1 TRIỆU CHỨNG]** `apps/worker/pipeline_orchestrate/preprocess.py:150-157` tự viết vòng gom-tới-trần.
- **[2 TÁI HIỆN]** Như FIX-209 (quét AST thấy `preprocess.py:153`).
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_orchestrate/preprocess.py`.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_orchestrate/preprocess.py`. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** Gọi `read_all_capped` với `too_large=PermanentError(IMAGE_TOO_LARGE.code)`, không `on_missing` (hành vi cũ). Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** Quét AST + test `pipeline_orchestrate` hiện có.
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0; commit `4bc7e34`.

## FIX-214 cho B5-05 — `_read_artifact` lặp vòng gom-tới-trần (NO-225)

- **[1 TRIỆU CHỨNG]** `apps/worker/pipeline_build/tasks.py:83-95` tự viết vòng gom-tới-trần.
- **[2 TÁI HIỆN]** Như FIX-209 (quét AST thấy `pipeline_build/tasks.py:87`).
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_build/tasks.py`.
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_build/tasks.py`. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** Giữ tên `_read_artifact` (test chủ khác gọi), thân là một lời gọi `read_all_capped`; `DEPENDENCY_UNAVAILABLE` lan nguyên (J02). Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** Quét AST + `pipeline_build/tests/test_tasks.py` hiện có.
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0; commit `48ad5e6`.

## FIX-215 cho B0-10 — `backup.sh` không đặt umask; `notify.yml` đọc secret cấp repo (NO-327, NO-332)

- **[1 TRIỆU CHỨNG]** SEC-040: `db.dump`/`objects.tar` 0644, thư mục 0755; SEC-061: `ALERT_WEBHOOK_URL` là secret repository. Mức trung bình/thấp.
- **[2 TÁI HIỆN]** Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red.sh` → pytest thoát 1 (`W4/C16/red-run.log`); đỏ: `test_backup__stage_dir_and_dump_are_owner_only`, `test_notify_workflow__secret_only_from_environment`.
- **[3 BẰNG CHỨNG]** `deploy/backup/backup.sh` (đặt thật, spec ghi `deploy/scripts/`), `notify.yml:16-25`; `docs/security/fixes/SEC-040.md`, `SEC-061.md`.
- **[4 KHOANH VÙNG]** `deploy/backup/backup.sh`, `deploy/backup/systemd/appback-backup.service`, `deploy/backup/tests/test_backup.py`, `.github/workflows/notify.yml`, `deploy/scripts/tests/test_workflow_notify.py`; C16b thêm `deploy/backup/restore.sh`, `deploy/backup/tests/test_restore.py`, `deploy/scripts/README.md`. Không chạm file chủ khác.
- **[5 SỬA NHỎ NHẤT]** `umask 077` sau `set -euo pipefail` + `UMask=0077`; thêm `environment: alerts` cho job notify (Environment `alerts` không protection rule, điều phối tạo — `W4/C16/gh-env.json`). Không `chmod -R`/umask trong container (tệp root, host không đọc được để băm); không thêm umask cho `restore.sh` (container uid 10001 cần đọc `objects.tar`). C16b: stream tar backup, chạy `mc` với người dùng host, README ghi Environment `alerts`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_backup__stage_dir_and_dump_are_owner_only`, `test_notify_workflow__secret_only_from_environment` — đỏ trước sửa, xanh sau (`cov-run.log`).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C16/verify-1234.log`), test + độ phủ `cov-run.log` (149 passed, mã thoát 0); commit `7fec0e1`, `6ecb19d` (C16b).

## FIX-216 cho B0-02 — `CoreSettings` nhận khoá mẫu `env.example` ở staging/production; log không che mật khẩu trong URL (NO-328, NO-329)

- **[1 TRIỆU CHỨNG]** SEC-041: `SECRET_KEY=change-me-32-bytes-minimum-please` (33 byte) qua kiểm độ dài; SEC-042: `postgresql://u:pw@h` trong chuỗi log nguyên văn. Mức trung bình/thấp.
- **[2 TÁI HIỆN]** Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red.sh` → pytest thoát 1 (`W4/C16/red-run.log`); đỏ: `test_secret_key_placeholder_rejected_outside_dev`, `test_mask_url_userinfo_password`.
- **[3 BẰNG CHỨNG]** `packages/core/settings.py:17-19,63-67`; `packages/core/logging.py:43-47`.
- **[4 KHOANH VÙNG]** `packages/core/settings.py`, `packages/core/logging.py`, `packages/core/tests/test_settings.py`, `packages/core/tests/test_logging.py`. Không chạm file chủ khác.
- **[5 SỬA NHỎ NHẤT]** `_https_outside_dev` từ chối `change-me` (casefold) ở `secret_key` và `secret_key_previous` khi staging/production; thêm mẫu regex `(?i)(\b[a-z][a-z0-9+.-]*://[^\s:/@]*:)[^\s/]+@` → `\g<1>***@` vào `_STR_PATTERNS` (mẫu của khối SEC-042 sai với mật khẩu chứa `@`, đã đổi).
- **[6 TEST CHẶN TÁI PHÁT]** `test_secret_key_placeholder_rejected_outside_dev`, `test_mask_url_userinfo_password` — đỏ trước sửa, xanh sau (`cov-run.log`).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C16/verify-1234.log`), test + độ phủ `cov-run.log` mã thoát 0; commit `5ee1710`.

## FIX-217 cho B6-03b — tiến trình con huấn luyện thừa hưởng toàn bộ env của ml (NO-326)

- **[1 TRIỆU CHỨNG]** SEC-020: `Popen` không `env=` nên con nhận `S3_SECRET_KEY` và mọi biến môi trường khác. Mức thấp.
- **[2 TÁI HIỆN]** Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red.sh` → pytest thoát 1 (`W4/C16/red-run.log`); đỏ: `test_start_training_runner_child_env_is_allowlisted`.
- **[3 BẰNG CHỨNG]** `apps/ml/training_runner/tasks.py:73-75`; mẫu `apps/ml/ml_eval/tasks.py:46-80`.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/tasks.py`, `apps/ml/training_runner/tests/test_tasks.py` (giả `Popen` nhận `env=`). Không chạm file chủ khác.
- **[5 SỬA NHỎ NHẤT]** `_child_env()`: danh sách cho phép (nền, `APP_ENV`, `REDIS_BROKER_URL`, `STORAGE_*`, tiền tố `PYTHON` `ML_` `TRAINING_` `S3_` `CELERY_` `TASK_` `COVERAGE_` `NVIDIA_` `CUDA_`), truyền `env=` cho `Popen`. `J01_smoke` kiểm lại con thật. Sau FIX-221 dùng hàm lọc env chung.
- **[6 TEST CHẶN TÁI PHÁT]** `test_start_training_runner_child_env_is_allowlisted` — đỏ trước sửa, xanh sau (`cov-run.log`).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C16/verify-1234.log`), test + độ phủ `cov-run.log` mã thoát 0; commit `206d3a0`, `3083920` (dùng hàm chung).

## FIX-218 cho B0-08 — thân 413/503 nginx tự sinh thiếu bộ header nền B0-06 (NO-331)

- **[1 TRIỆU CHỨNG]** SEC-060: 413/503 chỉ có `X-Request-Id`/`Retry-After`, thiếu `nosniff`, `Referrer-Policy`, `X-Frame-Options`, `no-store`. Mức thấp.
- **[2 TÁI HIỆN]** Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red.sh` → pytest thoát 1 (`W4/C16/red-run.log`); đỏ: `test_nginx_error_bodies__carry_base_security_headers`.
- **[3 BẰNG CHỨNG]** `deploy/nginx/snippets/error_413_body.conf:7`, `error_503_body.conf:5-6`.
- **[4 KHOANH VÙNG]** `deploy/nginx/snippets/error_*_body.conf`, `error_body_headers.conf` (mới), `deploy/tests/test_nginx.py`. Không chạm file chủ khác.
- **[5 SỬA NHỎ NHẤT]** Snippet thứ ba `error_body_headers.conf` (5 `add_header … always`) include từ hai snippet thân (không lặp, R-07); C16b thêm HSTS vào snippet này cho thân lỗi.
- **[6 TEST CHẶN TÁI PHÁT]** `test_nginx_error_bodies__carry_base_security_headers` — đỏ trước sửa, xanh sau (`cov-run.log`).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C16/verify-1234.log`), test + độ phủ `cov-run.log` mã thoát 0; commit `aded39f`, `90ff075` (HSTS, C16b).

## FIX-219 cho B0-03 — `DatabaseSettings` nhận `DATABASE_URL` mẫu change-me ở staging/production (cùng họ SEC-041/NO-328, vết C16b)

- **[1 TRIỆU CHỨNG]** DSN mẫu `postgresql+asyncpg://appback:change-me-pg@postgres:5432/appback` của `env.example` được chấp nhận khi `APP_ENV=staging|production`; `ValidationError` cũng in lại DSN. Mức thấp (phòng thủ chiều sâu).
- **[2 TÁI HIỆN]** Dựng `DatabaseSettings(database_url=<DSN mẫu>, app_env="production")` thành công trên cây chưa sửa. Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red2.sh` (hoặc `red3.sh`) → pytest thoát 1 (`W4/C16/red2-run.log`, `red3-run.log`).
- **[3 BẰNG CHỨNG]** `packages/db/settings.py` (validator chỉ kiểm tiền tố driver); `deploy/compose/env.example:12,16` (`change-me-pg`); `base.yml` anchor `app-env` bắt buộc `APP_ENV` cho mọi dịch vụ app (nên fail-closed ở compose); `PLACEHOLDER_MARKER` tái dùng từ `packages/core/settings.py` (R-07).
- **[4 KHOANH VÙNG]** `packages/db/settings.py`, `packages/db/tests/test_seeds_settings.py`. Không chạm file chủ khác (K27); `packages/storage` và khoá MinIO/S3 mẫu thuộc C15b.
- **[5 SỬA NHỎ NHẤT]** Thêm trường `app_env` tuỳ chọn (`APP_ENV`) và `model_validator` từ chối `DATABASE_URL` chứa `change-me` (casefold) khi staging/production; `hide_input_in_errors=True` để thông điệp không lặp DSN. Thiếu `APP_ENV` thì không kiểm (CLI dev). Không đổi hợp đồng FE, không đổi schema.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_seeds_settings.py::test_database_url_placeholder_rejected_outside_dev` — đỏ trước sửa (`red2-run.log`), xanh sau (`cov2-run.log`: 495 passed, mã thoát 0).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` mã thoát 0 (`W4/C16/verify-1234b.log`, `verify-1234c.log`); độ phủ tệp nguồn sửa ≥ 90 % dòng và nhánh (`cov2-run.log`); commit `ea01b17`.

## FIX-220 cho B0-05 — `ValidationError` của `MessagingSettings` in lại URL Redis kèm mật khẩu (NO-329 mở rộng)

- **[1 TRIỆU CHỨNG]** URL redis sai dạng (vd `http://:pw@broker`) làm thông điệp lỗi chứa `{value!r}` và `input_value=` nguyên văn, mật khẩu vào log/stderr. Mức thấp.
- **[2 TÁI HIỆN]** `MessagingSettings(redis_broker_url="http://:s3cr3tpw@broker:6379/0")` → `str(ValidationError)` chứa `s3cr3tpw`. Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red2.sh` (hoặc `red3.sh`) → pytest thoát 1 (`W4/C16/red2-run.log`, `red3-run.log`).
- **[3 BẰNG CHỨNG]** `packages/messaging/settings.py:26` (`{value!r}`); pydantic 2.13.5 in `input_value=` bất kể thông điệp (phản biện đo); hàm che `mask()` của FIX-216 ở `packages/core/logging.py` (R-07). `packages/storage/settings.py:26` cùng lớp lỗi — C15b.
- **[4 KHOANH VÙNG]** `packages/messaging/settings.py`, `packages/messaging/tests/test_settings.py`. Không chạm file chủ khác (K27).
- **[5 SỬA NHỎ NHẤT]** Thông điệp dùng `mask(value)` (che userinfo) và `model_config` `hide_input_in_errors=True`. Không đổi hợp đồng FE, không đổi schema.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/messaging/tests/test_settings.py::test_invalid_url_error_does_not_echo_the_password` — đỏ trước sửa (`red2-run.log`), xanh sau (`cov2-run.log`: 495 passed, mã thoát 0).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` mã thoát 0 (`W4/C16/verify-1234b.log`, `verify-1234c.log`); độ phủ tệp nguồn sửa ≥ 90 % dòng và nhánh (`cov2-run.log`); commit `14623ee`.

## FIX-221 cho B5-01 — mỗi tiến trình con của ml tự chép phép lọc env (NO-326 mở rộng, R-07)

- **[1 TRIỆU CHỨNG]** `ml_eval` và `training_runner` cùng lọc `os.environ` theo danh sách cho phép bằng hai đoạn mã giống nhau. Mức thấp.
- **[2 TÁI HIỆN]** `import apps.ml.runtime.child_env` thất bại (ModuleNotFoundError) trên cây chưa sửa — `test_child_env.py` lỗi thu thập (`W4/C16/red2-run.log` lần đầu). Cây 5ec9edb + test mới: `bash tools/verify/run.sh shell < W4/C16/red2.sh` (hoặc `red3.sh`) → pytest thoát 1.
- **[3 BẰNG CHỨNG]** `apps/ml/ml_eval/tasks.py:72-80`, `apps/ml/training_runner/tasks.py` (`_child_env`); `.importlinter` `ml-isolated` cho phép `apps.ml.runtime`.
- **[4 KHOANH VÙNG]** `apps/ml/runtime/child_env.py` (mới), `apps/ml/runtime/tests/test_child_env.py`. Không chạm file chủ khác (K27).
- **[5 SỬA NHỎ NHẤT]** Hàm `allowlisted_env(keep, prefixes)` trả biến khớp tên/tiền tố và đặt `PYTHONPATH` mặc định cwd; danh sách cho phép vẫn khai ở từng nơi gọi. Không đổi hợp đồng FE, không đổi schema.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/runtime/tests/test_child_env.py::test_allowlisted_env_keeps_names_and_prefixes_only`, `::test_allowlisted_env_does_not_override_an_existing_pythonpath` — đỏ trước sửa (`red2-run.log`), xanh sau (`cov2-run.log`: 495 passed, mã thoát 0).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` mã thoát 0 (`W4/C16/verify-1234b.log`, `verify-1234c.log`); độ phủ tệp nguồn sửa ≥ 90 % dòng và nhánh (`cov2-run.log`); commit `c91e1e7`.

## FIX-222 cho B0-01 — `unit_of` không có đơn vị cho `deploy/` (và `tests/`), test perf của chúng không vào bước 5b (NO-350)

- **[1 TRIỆU CHỨNG]** Test `perf` dưới `deploy/**/tests` không bao giờ chạy ở bước 5b lượt worker (chỉ ở integration, perf không giới hạn đường). `tools/tests/test_steps_commands.py::test_5b_deploy_bị_chạm_chạy_perf_của_deploy` và `test_coverage_gate.py::TestUnitOf::test_deploy_một_đơn_vị` đỏ, mã thoát 1 (`W4/C36/tai-hien-NO-350.md`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W4/C36/red.sh` trên dcc9153 + test mới.
- **[3 BẰNG CHỨNG]** `tools/coverage_gate.py:189-201` (`unit_of` → None); caller `coverage_gate.py:249,259`, `tools/verify/steps.py:65`; `pyproject.toml:94` (testpaths có `deploy`, `tests`), `:116` (coverage source không có `deploy`).
- **[4 KHOANH VÙNG]** `tools/coverage_gate.py`, `tools/tests/test_coverage_gate.py`, `tools/tests/test_steps_commands.py`. Cấm: `pyproject`, `conftest`, `steps.py`.
- **[5 SỬA NHỎ NHẤT]** `if parts[0] in ("tools","deploy","tests"): return parts[0]` + docstring. Không đổi hợp đồng: `deploy`/`tests` ngoài coverage source nên đơn vị rỗng = 100 % (Totals rỗng), cổng độ phủ không đỏ.
- **[6 TEST CHẶN TÁI PHÁT]** `TestUnitOf::test_deploy_một_đơn_vị`, `test_5b_deploy_bị_chạm_chạy_perf_của_deploy` — đỏ → xanh.
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0 (`W4/C36/steps1234.log`); `fin.log` `tools/tests` 353 passed, mã thoát 0; không nợ mới; commit `d052372`, `46f5711` (docstring R-01, C36b), `5135c04` (format).

## FIX-223 cho B0-01 — tệp test ML nặng (OCR ~46 s) vào hàng đợi `--dist loadfile` theo thứ tự thu thập, kéo dài đuôi bước 5 (NO-268 phần còn lại)

- **[1 TRIỆU CHỨNG]** `test_render_plan_ocr_readable` (`apps/ml/runtime/tests/test_ocr.py`) ~46 s một mình; với `--dist loadfile` tệp đứng muộn bắt đầu khi worker rảnh → đuôi lượt. `tools/tests/test_heavy_first.py` đỏ (ImportError, plugin chưa có).
- **[2 TÁI HIỆN]** `W4/C36/tai-hien-NO-268.md` + số đo `-n 4 apps/ml packages/vision` trước/sau trong `W4/C36/quyet-dinh.md`.
- **[3 BẰNG CHỨNG]** `tools/verify/steps.py:204` (`--dist loadfile`); `W2/C07/quyet-dinh.md` P-1 (`xdist_group` vô tác dụng); đo container pytest 9.1.1: truyền tệp trước thư mục bị nuốt (quyet-dinh P-4).
- **[4 KHOANH VÙNG]** Thêm `packages/testing/fixtures/heavy_first.py` (điều phối chọn A, ask), `tools/tests/test_heavy_first.py`. Cấm: conftest gốc, `steps.py`, `test_ocr.py`.
- **[5 SỬA NHỎ NHẤT]** Hook `pytest_collection_modifyitems(trylast)` đưa tệp trong `HEAVY_FIRST` lên đầu, ổn định; conftest gốc tự nạp. C36b đảo ngược: A/B xen kẽ 3 cặp (`W4/C36/ab.log`, 897 test) — trung vị không plugin 218 s, có plugin 328 s; test kết thúc cuối luôn là `training_yolo`, không bao giờ là tệp OCR → tiêu chí (nhanh hơn ≥ 10 % và đuôi do OCR) không đạt → xoá `heavy_first.py` + `test_heavy_first.py`; NO-268 phần còn lại đề xuất ❌.
- **[6 TEST CHẶN TÁI PHÁT]** `test_heavy_first__heavy_file_leads_rest_keep_order`, `test_heavy_first__same_set_as_without_plugin`, `test_heavy_first__listed_files_exist` — xoá cùng plugin ở `3e6ddc2`; sau đảo ngược không còn test chặn (không còn mã để chặn).
- **[7 NGHIỆM THU]** Bước 1–4 mã thoát 0; số đo bước 5 trước/sau và A/B trong `W4/C36/quyet-dinh.md`; không skip, assert OCR giữ nguyên; commit `0a28980` (thêm plugin), `3e6ddc2` (bỏ plugin theo A/B).

## FIX-225 cho B0-08 — nginx/minio/prometheus/mailpit: token vào access log, comment sai, `init.sh` nuốt lỗi, thiếu target worker, Mailpit bật rDNS (NO-197, NO-198, NO-199, NO-201, NO-212)

- **[1 TRIỆU CHỨNG]** NO-197: lỗi tiền-location (400/414) ghi nguyên token vào access log; NO-198: comment/assert sai "resolve chỉ có ở Plus"; NO-199: `init.sh` thoát 0 khi `mc admin policy entities` lỗi (không thu hồi khoá cũ); NO-201: `prometheus.yml` không có target worker; NO-212: Mailpit dev/ci bật rDNS.
- **[2 TÁI HIỆN]** Cây d81f493 + test mới: 12 failed / 118 passed (`W5/C17/red.log`). NO-199 chạy `init.sh` thật với `mc` giả: 2 failed (`W5/C17/green.log` phần ĐỎ).
- **[3 BẰNG CHỨNG]** `app_locations.conf` (`access_log off` chỉ ở location); `proxy_common.conf:18-21`; `init.sh` `users_with_policy` `2>/dev/null |`; `prometheus.yml` chỉ `api:9464`; `ci.yml`/`dev.yml` mailpit không `environment`. Probe nginx thật (1.30.5-alpine, template dev): 400 với header hỏng, `grep -c` token = 0.
- **[4 KHOANH VÙNG]** `deploy/nginx/**`, `deploy/minio/init.sh`, `deploy/observability/prometheus.yml`, `deploy/compose/{ci,dev}.yml`, `deploy/tests/{test_nginx,test_compose,test_minio_init}.py`. Không sửa file chủ khác.
- **[5 SỬA NHỎ NHẤT]** Snippet `access_log_files_map.conf` (`map $request_uri`, include từ hai template) + `access_log … if=` mức server; sửa comment `proxy_common`; `init.sh` bỏ ống, kiểm mã thoát + mốc "Query time:"; job `appback-worker` (9464, 9465; ml không khai vì ở mạng `ml-internal`); `MP_SMTP_DISABLE_RDNS`. Giới hạn: target worker tĩnh đúng với `WORKER_CONCURRENCY` mặc định 2.
- **[6 TEST CHẶN TÁI PHÁT]** `__no197`, `__no198` (2), `__no199` (3), `__no201[worker]`, `__no212[dev,ci]`; test cũ FIX-086 nới (cho phép map làm lớp thứ hai).
- **[7 NGHIỆM THU]** Báo cáo cụm ghi test `deploy/` xanh 278 passed (`green.log`) — log thực in 1 failed / 277 passed (`test_nginx_files_location_disables_access_log`, guard FIX-086, nới ở `5ab72a2`); sau C17b `W5/C17/c17b-final.log` 281 passed, mã thoát 0; bước 1–4 mã thoát 0 (`verify14.log`, `verify14b.log`); audit đạt; commit `4a2465b`, `5ab72a2` (nới test FIX-086), `1d97706` (noqa, dòng dài).

## FIX-226 cho B0-10 — scripts: smoke phụ thuộc python3, README thiếu biến SMTP, `sleep ""`, thư viện rỗng sau migrate, drill ép S3 (NO-189, NO-196, NO-200, NO-242)

- **[1 TRIỆU CHỨNG]** NO-189: `smoke.sh` dùng `python3` (shim Store thoát ≠ 0) → smoke hỏng; NO-196: README không liệt kê `SMTP_HOST`/`MAIL_FROM` bắt buộc; NO-200: `APPBACK_API_SWAP_SETTLE_S` rỗng → `sleep ""`; NO-242: thư viện `.glb` rỗng sau migrate; drill ép `APPBACK_STORAGE=s3` (vết C16b). C17b: `python3` còn ở `deploy/backup/backup.sh:42,125,154`, `restore.sh:51,77,78`, `deploy/scripts/healthcheck.sh:21` (cùng lỗi shim, `W5/C17/spec-C17b.md`).
- **[2 TÁI HIỆN]** Cây d81f493 + test mới: `test_smoke…__no189`, `test_readme…__no196`, `test_lib_empty…__no200`, `test_deploy_dry_run_publishes…__no242`, `test_drill_storage…__no_c16b` đỏ (`W5/C17/red.log`); C17b: 21 failed / 260 passed (`W5/C17/c17b-red.log`).
- **[3 BẰNG CHỨNG]** `smoke.sh:81`; README bảng + §12; `lib.sh:25` `=`; `deploy.sh` sau migrate; `drill.sh:33`.
- **[4 KHOANH VÙNG]** `deploy/scripts/{smoke,lib,deploy,drill,healthcheck}.sh`, `deploy/backup/{backup,restore}.sh`, `deploy/scripts/README.md`, `deploy/scripts/tests/*`.
- **[5 SỬA NHỎ NHẤT]** `grep -Eq '"code"[[:space:]]*:'`; `:=`; `run docker compose run --rm --no-deps api python -m apps.api.library.cli publish || cảnh báo` (không chí mạng, beat bù); README; `DRILL_STORAGE=s3|local` (local từ chối với `ci.yml`, helper object qua `exec api`). C17b: manifest, SHA-256, xoay vòng, payload cảnh báo bằng bash thuần (`json_escape`/`json_unescape` ở `lib.sh`); README ghi vì sao `restore.sh` không chạy `publish` thư viện.
- **[6 TEST CHẶN TÁI PHÁT]** Như [2]; C17b: `run_script` đặt shim `python3` hỏng lên `PATH` cho mọi test script, test quét cấm `python3` trong `deploy/**/*.sh`.
- **[7 NGHIỆM THU]** Test `deploy/` xanh (`W5/C17/c17b-final.log` 281 passed, mã thoát 0); bước 1–4 mã thoát 0 (`verify14b.log`); audit đạt. Drill local chưa chạy thật (không có ảnh `appback-api` trên máy) — chỉ test tĩnh/thoát 2. Đo `backup.sh`: ảnh `quay.io/minio/mc:RELEASE.2025-08-13`, `--user 1234:1234 -e MC_CONFIG_DIR=/tmp/.mc` tạo được `/tmp/.mc` (drwx------ 1234), `mc alias list` chạy. Commit `b9a1984`, `b4b065f` (noqa), `144e3f6` (bỏ `python3` host ở backup/restore/healthcheck, C17b), `f04ccda` (dòng dài).

## FIX-230 cho B5-01 — lõi khoá giữ chỗ và hằng của `apps/ml/runtime` có bản sao (NO-308, NO-314, NO-285 phần runtime)

- **[1 TRIỆU CHỨNG]** `gpu.py` (`_Keeper`) và `training_runner/slot.py` (`_RenewThread`, `_acquire`) là hai bản cùng thuật toán SET NX PX + gia hạn + `lost` + trả; `JOIN_TIMEOUT_S`/`ACQUIRE_*` hai nơi; `MODEL_VERSION_FAMILY_MISMATCH` không có ở `runtime/errors.py`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W5/C18/all.sh` (phần "TÁI HIỆN", cây chưa sửa khôi phục từ `.c18-orig`) trên d81f493: `test_single_source.py` 3 failed, mã thoát 1 (`W5/C18/all.log`; `tai-hien-NO-285.md`, `tai-hien-NO-308.md`, `tai-hien-NO-314.md`).
- **[3 BẰNG CHỨNG]** `apps/ml/runtime/gpu.py:29-137` (cũ), `apps/ml/training_runner/slot.py:30-155` (cũ), `watchdog.py:17`, `walls/tasks.py:32`, `text/tasks.py:33`, `objects/tasks.py:33`.
- **[4 KHOANH VÙNG]** `apps/ml/runtime/{lease.py (mới), gpu.py, errors.py, error_codes.py (mới, C18b)}`, `apps/ml/runtime/tests/{test_lease.py, test_single_source.py (mới), test_device_gpu.py, test_tasks_util.py}`. Cấm: `packages/messaging/*`, file chủ khác.
- **[5 SỬA NHỎ NHẤT]** `lease.py`: `held_lease(ops, …)` đồng bộ + `RenewThread` + `check_timing` + `LeaseOps[T]` (`try_acquire`/`renew`→`bool|None`/`release_quietly`); một nguồn `JOIN_TIMEOUT_S`, `ACQUIRE_*`. `gpu.py`: lớp vỏ `SafeLockOps` (vòng asyncio riêng trong luồng daemon, `run_coroutine_threadsafe`), `gpu_slot` = `check_timing` → `held_lease` → `ops.close()`. Tên khoá Redis không đổi (`lock:gpu:0` + fence qua `SafeLock`). `errors.py` khai `MODEL_VERSION_FAMILY_MISMATCH`; C18b tách hằng chuỗi sang `error_codes.py` (chỉ `typing`). Lệch: log `gpu_lock_lost` → `lease_lost` (`extra.lock`); thông điệp `TransientError` "GPU đang bận" → "khoá gpu:0 đang bận" (test cùng chủ sửa match). `test_tasks_util.py::test_infer_context_builds_without_the_api_secrets` so `isinstance(…, S3Storage)` (đỏ sẵn do `45b5ece`, `W5/C18/tai-hien-C18b.md`).
- **[6 TEST CHẶN TÁI PHÁT]** `test_single_source.py::test_runtime_constants__not_redeclared`, `::test_model_version_family_mismatch__declared_in_runtime_errors`, `::test_gpu_slot__holds_through_shared_lease`, `::test_error_codes__import_light`; `test_lease.py::test_held_lease__second_process_waits_for_first` (hai tiến trình, Redis thật), `::test_held_lease__late_renew_marks_lost`, `::test_renew_thread__crash_marks_lost`, `::test_safe_lock_ops__*`.
- **[7 NGHIỆM THU]** Đỏ → xanh (`all.log` → `W5/C18/green.log`: 164 passed, pytest/ruff mã thoát 0); `verify --steps 1,2,3,4` mã thoát 0 (`W5/C18/verify.log`, `verify-b.log`); độ phủ tệp đổi ≥ 90 % dòng + nhánh; cổng đầy đủ ở việc gộp M; commit `94e3bd8`, `7ba91ad` (`error_codes`, C18b), `e5025d8` (docstring test).

## FIX-231 cho B6-03b — runner khai lại khoá job và lõi khoá giữ chỗ (NO-305, NO-308, NO-313, NO-314 phía runner)

- **[1 TRIỆU CHỨNG]** `training_runner/keys.py` khai lại `trained_version_id`/`cancel_key`/`claim_key`; `test_runtime.py` khai lại `WEIGHTS_NAME_RE`; `slot.py` có vòng lấy/gia hạn riêng; `watchdog.py` giữ `JOIN_TIMEOUT_S`; `cancel_while_waiting` chạy `ML_DEVICE=cpu`.
- **[2 TÁI HIỆN]** `W5/C18/all.sh` phần "TÁI HIỆN": `test_training_keys__single_source`, `test_training_slot__holds_through_shared_lease` 2 failed, mã thoát 1 (`all.log`; `tai-hien-NO-305.md`, `tai-hien-NO-308.md`, `tai-hien-NO-313.md`).
- **[3 BẰNG CHỨNG]** `keys.py:21-33` (cũ) vs `packages/messaging/payloads/training.py:20-38`; `test_runtime.py:68,280` (cũ); `slot.py:55-108` (cũ); `.importlinter` không cấm `apps.ml → packages.messaging.payloads`.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/{keys.py, slot.py, watchdog.py, reporter.py, errors.py}`, `tests/{test_keys.py, test_slot.py, test_runtime.py}`. Cấm: `packages/messaging/payloads/training.py` (chỉ đọc), `apps/worker/*`.
- **[5 SỬA NHỎ NHẤT]** `keys.py` nhập lại ba hàm từ payloads (`__all__`); `slot.py` còn lớp vỏ `_SlotOps` trên `training:slot` + `held_lease`; `claim_lease` dùng `RenewThread` chung (lỗi lạ trong nhịp → `lost`, fail-closed — đổi hành vi, có test); `watchdog`/`reporter` nhập `JOIN_TIMEOUT_S` từ `apps.ml.runtime.lease`; test nhập `WEIGHTS_NAME_RE` từ payloads; `ml_device="auto"`. Tên khoá `training:slot`, `training:claim:*`, `training:cancel:*` không đổi (`test_training_keys_literal` giữ nguyên). Lệch: log `training_slot_lost` → `lease_lost`. C18b: `errors.py` nhập mã chung từ `runtime.error_codes`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_keys.py::test_training_keys__single_source`, `test_slot.py::test_training_slot__holds_through_shared_lease`, `test_slot.py::test_claim_lease_unexpected_error_marks_lost`; `test_runtime.py::test_run_training_job_cancel_while_waiting` (perf, `auto`).
- **[7 NGHIỆM THU]** Như FIX-230 (`green.log` perf 1 passed, mã thoát 0); commit `07c0dde`, `20fc1ce` (`error_codes`, C18b).

## FIX-232 cho B5-02 — `MODEL_VERSION_FAMILY_MISMATCH` khai cục bộ ở `apps/ml/walls/tasks.py` (NO-285)

- **[1 TRIỆU CHỨNG]** Hằng chuỗi khai riêng ở `apps/ml/walls/tasks.py` (một trong ba bản sao, R-07).
- **[2 TÁI HIỆN]** `W5/C18/all.sh` phần "TÁI HIỆN": `test_runtime_constants__not_redeclared` liệt kê `walls/tasks.py:MODEL_VERSION_FAMILY_MISMATCH`.
- **[3 BẰNG CHỨNG]** `apps/ml/walls/tasks.py:32-33` (cũ); nguồn mới `apps/ml/runtime/errors.py` (FIX-230).
- **[4 KHOANH VÙNG]** `apps/ml/walls/tasks.py`. Cấm: mọi file khác.
- **[5 SỬA NHỎ NHẤT]** Bỏ khai, `from apps.ml.runtime.errors import MODEL_VERSION_FAMILY_MISMATCH`, giữ trong `__all__` (test cũ dùng `tasks.MODEL_VERSION_FAMILY_MISMATCH`). Chuỗi mã không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/runtime/tests/test_single_source.py::test_runtime_constants__not_redeclared` (+ test task cũ của bước sai họ).
- **[7 NGHIỆM THU]** Như FIX-230; commit `4267320` (sau FIX-230, phụ thuộc hằng mới).

## FIX-233 cho B5-04 — `MODEL_VERSION_FAMILY_MISMATCH` khai cục bộ ở `apps/ml/text/tasks.py` (NO-285)

- **[1 TRIỆU CHỨNG]** Hằng chuỗi khai riêng ở `apps/ml/text/tasks.py` (một trong ba bản sao, R-07).
- **[2 TÁI HIỆN]** `W5/C18/all.sh` phần "TÁI HIỆN": `test_runtime_constants__not_redeclared` liệt kê `text/tasks.py:MODEL_VERSION_FAMILY_MISMATCH`.
- **[3 BẰNG CHỨNG]** `apps/ml/text/tasks.py:32-33` (cũ); nguồn mới `apps/ml/runtime/errors.py` (FIX-230).
- **[4 KHOANH VÙNG]** `apps/ml/text/tasks.py`. Cấm: mọi file khác.
- **[5 SỬA NHỎ NHẤT]** Bỏ khai, `from apps.ml.runtime.errors import MODEL_VERSION_FAMILY_MISMATCH`, giữ trong `__all__` (test cũ dùng `tasks.MODEL_VERSION_FAMILY_MISMATCH`). Chuỗi mã không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/runtime/tests/test_single_source.py::test_runtime_constants__not_redeclared` (+ test task cũ của bước sai họ).
- **[7 NGHIỆM THU]** Như FIX-230; commit `41f7f2e` (sau FIX-230, phụ thuộc hằng mới).

## FIX-234 cho B0-02 — `packages/core` không phơi ULID trần và không có hàm kiểm Cc/bidi, nên ba nơi cắt tiền tố, bảy nơi chép luật (NO-168, NO-169, NO-213)

- **[1 TRIỆU CHỨNG]** ULID trần bị cắt tiền tố ở 3 nơi (`me/router.py:258`, `floors/lookup.py:117`, `drawings/drawings.py:43`); luật Cc/bidi chép 7 bản.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W5/C19/red.sh` (cây chưa sửa, base `fix/debt-02-w3` + `w4-storage-keys`) → mã thoát 1: 11 failed, 60 passed, 1 error (ImportError `clean_text`; `new_ulid` AttributeError) (`W5/C19/red.log`, `red-run1.log`; `tai-hien-NO-168.md`, `tai-hien-NO-169.md`, `tai-hien-NO-213.md`).
- **[3 BẰNG CHỨNG]** Nguyên nhân gốc: `packages/core/ids.py` chỉ có `new_id`; `text.py` không có hàm kiểm Cc/bidi. `W5/C19/quyet-dinh.md` P-1 (grep 3 nơi cắt tiền tố), P-2 (bộ bidi hẹp ở me/auth_recovery/floors/drawings/measurements, rộng +200E/200F ở projects/project_settings).
- **[4 KHOANH VÙNG]** `packages/core/{ids.py, text.py}`, `packages/core/tests/{test_ids.py, test_text_clean.py}`.
- **[5 SỬA NHỎ NHẤT]** `new_ulid(clock)` (`new_id` gọi nó); `clean_text(value, *, bidi_marks, allow_controls)` (tham số tường minh, P-5 "một tập rộng không tham số" bị loại vì đổi dây); C19b phơi vị từ `first_forbidden_char` cho FIX-306. Hợp đồng không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `test_ids.py::test_new_ulid__bare_body_follows_clock`, `::test_new_ulid__rejects_time_before_epoch`; `test_text_clean.py::test_clean_text__trims_and_composes_nfc`, `::test_clean_text__rejects_cc_and_bidi_override`, `::test_clean_text__bidi_marks_only_when_asked`, `::test_clean_text__allow_controls_is_explicit`, `::test_first_forbidden_char__reports_first_or_none` (đỏ ImportError → xanh).
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed, ruff sạch), `ids.py`/`text.py` 100 %; nợ còn lúc ấy (`packages/domain/spatial/model.py:36` bản chép khác hợp đồng, không strip) đóng ở FIX-306; commit `0440e0b`, `e5403d2` (docstring), `cea0b30` (`first_forbidden_char`, C19b).

## FIX-235 cho B1-04 — `me` tự cắt tiền tố `new_id` và chép luật Cc/bidi (NO-168, NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/me/router.py:252-258` cắt tiền tố `new_id(...)` để lấy ULID trần; `apps/api/me/schemas.py:22-27` chép kiểm ký tự Cc/bidi.
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_me_schemas__reuses_core_text`, `test_me_router__reuses_core_new_ulid` FAILED (quét nguồn).
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-1 (`me/router.py:258`), P-2 (bộ bidi hẹp).
- **[4 KHOANH VÙNG]** `apps/api/me/{router.py, schemas.py}`, `apps/api/me/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `me` dùng `new_ulid` + `clean_text` của core; dây không đổi (422 chỉ mang `field` + `count`, P-3).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/me/tests/test_text_source.py::test_me_schemas__reuses_core_text`, `::test_me_router__reuses_core_new_ulid` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); `me/schemas.py` 98 % (dòng 64 là nhánh phone cũ); commit `a7e6626`.

## FIX-236 cho B1-03 — `auth_recovery` `_validate_full_name` chép luật Cc/bidi (NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/auth_recovery/router.py:64-73` chép kiểm ký tự Cc/bidi.
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_auth_recovery_router__reuses_core_text` FAILED (quét nguồn: còn tập 0x202A).
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-2 (bộ bidi hẹp).
- **[4 KHOANH VÙNG]** `apps/api/auth_recovery/router.py`, `apps/api/auth_recovery/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `_validate_full_name` gọi `clean_text` của core. Dây không đổi (P-3).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/auth_recovery/tests/test_text_source.py::test_auth_recovery_router__reuses_core_text` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); commit `d9bfd55`.

## FIX-237 cho B2-03 — `floors` tự cắt tiền tố `new_id` và chép luật Cc/bidi (NO-168, NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/floors/lookup.py` `new_level_id` cắt tiền tố `new_id(...)`; `apps/api/floors/schemas.py` chép kiểm ký tự Cc/bidi.
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_floors_schemas__reuses_core_text`, `test_floors_lookup__reuses_core_new_ulid` FAILED.
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-1 (`floors/lookup.py:117`), P-2.
- **[4 KHOANH VÙNG]** `apps/api/floors/{lookup.py, schemas.py}`, `apps/api/floors/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `new_level_id` dùng `new_ulid`, `clean_name` dùng `clean_text`. Dây không đổi (P-3).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/floors/tests/test_text_source.py::test_floors_schemas__reuses_core_text`, `::test_floors_lookup__reuses_core_new_ulid` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); commit `952432f`.

## FIX-238 cho B2-04 — `drawings` tự cắt tiền tố `new_id` và chép luật Cc/bidi (NO-168, NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/drawings/drawings.py:43` `new_page_key` cắt tiền tố `new_id(...)`; `apps/api/drawings/schemas.py:33-38` chép kiểm ký tự Cc/bidi.
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_drawings_schemas__reuses_core_text`, `test_drawings__page_key_reuses_core_new_ulid` FAILED.
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-1 (`drawings/drawings.py:43`), P-2.
- **[4 KHOANH VÙNG]** `apps/api/drawings/{drawings.py, schemas.py}`, `apps/api/drawings/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `new_page_key` dùng `new_ulid`; `clean_file_name` dùng `clean_text`, giữ tiền tố `'fileName:'` trong thông báo (`test_progress` khớp `'fileName'`). Dây không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/drawings/tests/test_text_source.py::test_drawings_schemas__reuses_core_text`, `::test_drawings__page_key_reuses_core_new_ulid` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); commit `48cab15`.

## FIX-239 cho B2-01 — `projects.clean_text` là bản chép luật bidi riêng (NO-213, NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/projects/schemas.py:30,34-47` giữ `_BIDI` + `clean_text` riêng (bản gốc mà `project_settings` chép).
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_projects_schemas__reuses_core_text` FAILED (quét nguồn: còn chuỗi ký tự định hướng).
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-2 (bộ rộng +200E/200F ở projects/project_settings).
- **[4 KHOANH VÙNG]** `apps/api/projects/schemas.py`, `apps/api/projects/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `projects.clean_text` là vỏ mỏng quanh core `clean_text(bidi_marks=True)`; `admin_ml_datasets` vẫn nhập được. Dây không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/projects/tests/test_text_source.py::test_projects_schemas__reuses_core_text` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); commit `16b9190`.

## FIX-240 cho B2-02 — `project_settings` chép `_BIDI` + `clean_text` của `projects` (NO-213)

- **[1 TRIỆU CHỨNG]** `apps/api/project_settings/schemas.py:22,26-36` chép `_BIDI` + `clean_text` của `apps/api/projects/schemas.py:30,34-47`.
- **[2 TÁI HIỆN]** Như FIX-234 (`W5/C19/red.log`): `test_project_settings_schemas__reuses_core_text` FAILED.
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-2.
- **[4 KHOANH VÙNG]** `apps/api/project_settings/schemas.py`, `apps/api/project_settings/tests/test_text_source.py`.
- **[5 SỬA NHỎ NHẤT]** `_clean_notes` gọi core `clean_text(bidi_marks=True, allow_controls='\n\t')`. Dây không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/project_settings/tests/test_text_source.py::test_project_settings_schemas__reuses_core_text`, `packages/core/tests/test_text_clean.py::test_clean_text__allow_controls_is_explicit` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov.log` mã thoát 0 (1403 passed); commit `4819631`.

## FIX-241 cho B0-06 — OpenAPI thiếu tham số đường do dependency đọc `request.path_params`; bước 8 không chặn component trùng tên `apps__…` (NO-237, NO-236)

- **[1 TRIỆU CHỨNG]** `docs/contracts/openapi.json`: 15 thao tác `/api/projects/{project_id}/…` không khai `project_id` trong `parameters` (dòng nợ chỉ nêu 2 PUT); component `apps__api__floors__schemas__FloorName`, `apps__api__projects__schemas__FloorName` đang có trong hợp đồng đã commit — bước 8 nhánh thường không `--compare` nên không ai thấy.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W5/C20/red.sh` trên `9c624bf` + test mới → mã thoát pytest 1 (`W5/C20/red.log`; `tai-hien-NO-236.md`, `tai-hien-NO-237.md`).
- **[3 BẰNG CHỨNG]** `apps/api/projects/access.py:30` đọc `request.path_params`; FastAPI 0.141 dựng `parameters` từ `_get_openapi_dependency_data(route.dependant)` (`probe.sh`). Pydantic đổi cả hai component sang tên module khi trùng tên (`apps__api__core__tests__test_openapi__Label__1`, `…__Label__2`).
- **[4 KHOANH VÙNG]** `apps/api/core/routing.py`, `apps/api/core/openapi.py`, test `apps/api/core/tests/test_openapi.py`, `apps/api/core/tests/test_routing_finish.py` (chặn tái phát NO-186, đề xuất ❌). Cấm: `openapi.json`, `docs/contracts/*` (điều phối làm mới), `apps/api/projects/access.py` (B2-01 — sửa ở lõi để route mới không quên lại).
- **[5 SỬA NHỎ NHẤT]** `AppRoute.__init__`: tham số của `param_convertors` mà `get_flat_dependant(self.dependant)` không khai → gắn một dependency rỗng `_path_declaration` (chữ ký `name: str` keyword-only) — không đổi dây, `str` không thể 422, không đổi `Operation`/case_gate. `document()` gọi `_check_component_names`: tên component khớp `[a-z][a-z0-9_]*?__` (đường module; tên ngắn là CapWords, generic lồng `CursorPage_list_X__` không khớp) → `ValueError` nêu tên → bước 8 (luôn gọi CLI) hỏng trên mọi nhánh. Đổi hợp đồng: `openapi.json` thêm `parameters` cho 15 thao tác (đúng hơn, không đổi đường/dây) và đổi tên component `FloorName` (cùng FIX-244); điều phối chạy `run.sh openapi`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_document__every_path_parameter_is_declared`, `test_document__refuses_two_aliases_with_one_name`, `test_document__real_app_has_only_short_component_names` — đỏ (mã thoát 1, `red.log`) → xanh (`cov3.log`).
- **[7 NGHIỆM THU]** `W5/C20/cov3.log` mã thoát 0 (801 passed); `verify --steps 1,2,3,4` mã thoát 0 (`W5/C20/verify.log`); cổng đầy đủ ở việc gộp M; commit `99b8236`.

## FIX-242 cho B0-06 — 422 thân union: tag nhánh lọt vào `field`, tag lạ không có `field` (NO-248) — đổi dây, commit riêng

- **[1 TRIỆU CHỨNG]** #29 `templates_create_template`: `field:"wall.fields.heightMm"`; `objectKind` lạ → không có `field`.
- **[2 TÁI HIỆN]** `W5/C20/red.sh` trên `9c624bf` + test → 4 test đỏ, mã thoát pytest 1 (`W5/C20/tai-hien-NO-248.md`).
- **[3 BẰNG CHỨNG]** `apps/api/core/errors.py:104` `field_of` giữ nguyên loc; pydantic chèn tag nhánh vào loc; `union_tag_invalid` có loc `("body",)`.
- **[4 KHOANH VÙNG]** `apps/api/core/errors.py`, `apps/api/core/tests/test_errors.py`. Người gọi khác `apps/api/admin_ml_registry/upload.py:90` không truyền thân → hành vi cũ.
- **[5 SỬA NHỎ NHẤT]** `field_of(loc, body)`: khi gốc là `body` và thân JSON là object/mảng, đi song song loc với thân (khớp alias hoặc tên snake_case — `populate_by_name` của `WireModel`); đoạn không có trong thân mà chưa phải đoạn cuối = tag nhánh → bỏ; đoạn cuối vắng = khoá vắng → giữ. `union_tag_invalid/not_found` → nối tên discriminator (`ctx`) vào loc. **Đổi dây** (điều phối duyệt A, `W5/C20/ask-NO-248.log`; người dùng duyệt trước khi gộp, bác thì revert riêng commit này): trước `wall.fields.heightMm` → sau `fields.heightMm`; tag lạ/vắng: trước không có `field` → sau `objectKind`; union thường: tên lớp trong loc (vd `WallIn`) trước lọt ra → nay bỏ. FE không đọc `field` của VALIDATION (grep `F:/App/AppFront/src`: chỉ chuyển tiếp ở `api/schemas/errors.ts:120`, `lib/errors/wireError.ts:97`); giá trị mới khớp regex HOP-DONG-MOI `^[A-Za-z][A-Za-z0-9]*(\.[A-Za-z0-9]+)*$`. Không đổi openapi. Ca biên đã biết: thân có khoá trùng đúng giá trị tag ở cùng mức (`{"objectKind":"wall","wall":…}`) → giữ tag.
- **[6 TEST CHẶN TÁI PHÁT]** `test_field_of__union_branch_tag_is_not_a_field`, `…__missing_key_inside_a_union_branch_keeps_its_name`, `…__unknown_union_tag_names_the_discriminator`, `…__union_inside_a_list_keeps_the_index`, `…__body_sent_by_field_name_still_drops_only_the_tag`, `…__without_a_json_body_keeps_the_loc`.
- **[7 NGHIỆM THU]** Như FIX-241; commit `e2ca37a`.

## FIX-243 cho B0-05 — vai Streams thử lại cả hết giờ đọc → `XADD` gửi hai lần (NO-187)

- **[1 TRIỆU CHỨNG]** `retry_on_error=[ConnectionError, TimeoutError]` cho mọi vai (`packages/messaging/redis.py:59,145,158`), kể cả `streams_redis`/`streams_redis_sync` — client của `EventBus.publish`/`SyncEventBus.publish` (XADD).
- **[2 TÁI HIỆN]** Redis thật `CLIENT PAUSE 10000 WRITE`, `streams_redis_sync().xadd` hết giờ 0,5 s → redis-py mở lại kết nối và gửi XADD lần hai: `reconnects == 1` (`W5/C20/tai-hien-NO-187.md`), mã thoát pytest 1.
- **[3 BẰNG CHỨNG]** redis-py 8.1 `Retry.__init__(…, supported_errors=(ConnectionError, TimeoutError, builtins.TimeoutError))` mặc định (`probe.sh`) — chỉ đổi `retry_on_error` không đủ, nó chỉ thêm vào danh sách.
- **[4 KHOANH VÙNG]** `packages/messaging/redis.py`, `packages/messaging/tests/test_redis.py`. Không sửa `streams.py`/caller.
- **[5 SỬA NHỎ NHẤT]** `_retry(retries, errors)` truyền `supported_errors` tường minh; vai Streams (async lẫn sync) dùng `WRITE_RETRYABLE_ERRORS = (RedisConnectionError, builtins.TimeoutError)` — giữ thử lại khi lỗi/hết giờ nối (chưa gửi gì), bỏ thử lại hết giờ đọc (`redis.exceptions.TimeoutError`, không kế thừa builtin — test khoá). Vai khác không đổi. Không đổi hợp đồng. Còn lại (ghi trong docstring): `ConnectionError` khi đọc phản hồi vẫn thử lại → giảm chứ không hết trùng (redis-py không tách pha gửi/đọc; phần này FIX-307 xử lý ở caller); đọc qua vai Streams (quét hết hạn, `XREVRANGE` pipeline_quality) mất lượt thử lại hết giờ đọc — đều tự chịu lỗi; SSE đọc pool riêng (`apps/api/streams/router.py`).
- **[6 TEST CHẶN TÁI PHÁT]** `test_streams_redis_sync__a_timed_out_write_is_not_sent_again`, `test_streams_clients__retry_only_connection_failures[streams_redis|streams_redis_sync]` — đỏ → xanh.
- **[7 NGHIỆM THU]** Như FIX-241; commit `e980edc`.

## FIX-244 cho B2-01 — `type FloorName` trùng tên với `apps/api/floors/schemas.py:77` (B2-03) làm OpenAPI đổi cả hai component sang `apps__…` (NO-236)

- **[1 TRIỆU CHỨNG]** `docs/contracts/openapi.json` có `apps__api__floors__schemas__FloorName`, `apps__api__projects__schemas__FloorName`.
- **[2 TÁI HIỆN]** `test_document__real_app_has_only_short_component_names` đỏ trên `9c624bf` (`W5/C20/tai-hien-NO-236.md`).
- **[3 BẰNG CHỨNG]** `apps/api/projects/schemas.py:62` `type FloorName = Annotated[CleanStr, StringConstraints(min_length=1)]`.
- **[4 KHOANH VÙNG]** Chỉ `apps/api/projects/schemas.py` (2 dòng). Không sửa `floors/schemas.py` (B2-03).
- **[5 SỬA NHỎ NHẤT]** Đổi tên bí danh → `FloorDraftName` (dùng ở `FloorDraftIn.name`). Không đổi dây; `openapi.json` đổi tên component (`$ref`) — FE không tham chiếu `apps__api__…` (grep rỗng). Commit trước FIX-241 để mọi commit của nhánh qua được bước 8.
- **[6 TEST CHẶN TÁI PHÁT]** Kiểm ở lõi (FIX-241: `test_document__real_app_has_only_short_component_names`) — xanh sau commit này.
- **[7 NGHIỆM THU]** Như FIX-241; commit `d37e82a`.

## FIX-245 cho B0-06 — `_abort`: rollback ném thì `close` và `idempotency.discard` bị bỏ → dòng claim mồ côi tới hết TTL (không có dòng NO — vết C20b)

- **[1 TRIỆU CHỨNG]** Request hỏng có `Idempotency-Key` mà rollback ném (DB rớt, huỷ) → dòng `in_progress` còn lại; lượt lặp cùng khoá bị từ chối `IDEMPOTENCY_IN_PROGRESS` tới hết TTL.
- **[2 TÁI HIỆN]** `W5/C20/red-b.sh` trên `e980edc` → `assert 1 == 0`, mã thoát pytest 1 (`W5/C20/tai-hien-C20b.md`, `red-b.log`).
- **[3 BẰNG CHỨNG]** `apps/api/core/routing.py:301-305` (trước sửa): `rollback` → `close` → `discard` tuần tự, không bảo vệ.
- **[4 KHOANH VÙNG]** `apps/api/core/routing.py`, `apps/api/core/tests/test_routing_finish.py`.
- **[5 SỬA NHỎ NHẤT]** Chạy lần lượt mọi bước dọn (rollback, close, discard nếu có claim), gom ngoại lệ, ném lại ngoại lệ đầu tiên sau khi dọn hết (`# noqa: BLE001` có lý do). Không đổi dây.
- **[6 TEST CHẶN TÁI PHÁT]** `test_abort__rollback_failure_still_discards_the_claim` — đỏ → xanh.
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` đạt (`W5/C20/verify-b.log`, mã thoát 0); pytest `apps/api/core apps/api/drawings packages/messaging` 1171 passed (`cov-b.log`, mã thoát 0); độ phủ `routing.py` 100 % dòng/nhánh; commit `49bae53`.

## FIX-246 cho B6-04b — `ml_eval` giữ bản sao riêng của phép lọc env, dùng hàm chung (NO-326 mở rộng)

- **[1 TRIỆU CHỨNG]** `apps/ml/ml_eval/tasks.py` giữ bản sao riêng của phép lọc env (trùng với `training_runner`). Mức thấp.
- **[2 TÁI HIỆN]** Đọc mã: `apps/ml/ml_eval/tasks.py:72-80` trước sửa; hành vi giữ nguyên, `test_ml_eval_sandbox_child_env_is_minimal` vẫn xanh. Đỏ của cả nhóm C16b: `bash tools/verify/run.sh shell < W4/C16/red2.sh` (hoặc `red3.sh`) → pytest thoát 1 (`W4/C16/red2-run.log`, `red3-run.log`).
- **[3 BẰNG CHỨNG]** `apps/ml/ml_eval/tasks.py:72-80`; test hiện có `apps/ml/ml_eval/tests/test_sandbox.py:119-127`.
- **[4 KHOANH VÙNG]** `apps/ml/ml_eval/tasks.py`. Không chạm file chủ khác (K27).
- **[5 SỬA NHỎ NHẤT]** `_child_env()` gọi `allowlisted_env(_ENV_KEEP, _ENV_PREFIX)` (FIX-221) rồi chặn luồng/arena như cũ. Không đổi hợp đồng FE, không đổi schema.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/ml_eval/tests/test_sandbox.py::test_ml_eval_sandbox_child_env_is_minimal` (giữ xanh; không đổi nội dung test); xanh sau (`cov2-run.log`: 495 passed, mã thoát 0).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` mã thoát 0 (`W4/C16/verify-1234b.log`, `verify-1234c.log`); độ phủ tệp nguồn sửa ≥ 90 % dòng và nhánh (`cov2-run.log`); commit `bfde446` (trailer đổi từ FIX-222 nhầm, C16c).

## FIX-247 cho B5-03 — `MODEL_VERSION_FAMILY_MISMATCH` khai cục bộ ở `apps/ml/objects/tasks.py` (NO-285)

- **[1 TRIỆU CHỨNG]** Hằng chuỗi khai riêng ở `apps/ml/objects/tasks.py` (một trong ba bản sao, R-07).
- **[2 TÁI HIỆN]** `W5/C18/all.sh` phần "TÁI HIỆN": `test_runtime_constants__not_redeclared` liệt kê `objects/tasks.py:MODEL_VERSION_FAMILY_MISMATCH`.
- **[3 BẰNG CHỨNG]** `apps/ml/objects/tasks.py:32-33` (cũ); nguồn mới `apps/ml/runtime/errors.py` (FIX-230).
- **[4 KHOANH VÙNG]** `apps/ml/objects/tasks.py`. Cấm: mọi file khác.
- **[5 SỬA NHỎ NHẤT]** Bỏ khai, `from apps.ml.runtime.errors import MODEL_VERSION_FAMILY_MISMATCH`, giữ trong `__all__` (test cũ dùng `tasks.MODEL_VERSION_FAMILY_MISMATCH`). Chuỗi mã không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/runtime/tests/test_single_source.py::test_runtime_constants__not_redeclared` (+ test task cũ của bước sai họ).
- **[7 NGHIỆM THU]** Như FIX-230; commit `9dc704f` (sau FIX-230, phụ thuộc hằng mới).

## FIX-248 cho B1-04 — `avatar.py` gán cờ Pillow toàn cục mỗi request và chép nguyên cỡ ảnh khi `convert`/`exif_transpose` (NO-170, NO-171)

- **[1 TRIỆU CHỨNG]** NO-170/NO-171: `apps/api/me/avatar.py` gán `ImageFile.LOAD_TRUNCATED_IMAGES` toàn cục mỗi request; `convert` + `exif_transpose` chép nguyên cỡ ảnh RGB/RGBA (RSS đỉnh ~201 MB cho 4096² RGBA).
- **[2 TÁI HIỆN]** Đỏ trước sửa không dựng được: `run.sh shell` chép worktree không kèm `.git` nên `git checkout HEAD --` trong container báo `fatal: not a git repository`, lượt "RED" thực chạy trên mã đã sửa (9 passed, không phải bằng chứng). Theo nới quy trình của người dùng (P3 cơ học, không đổi hợp đồng) không dựng lại đỏ (`W6/C21/tai-hien-NO-170-171.md`).
- **[3 BẰNG CHỨNG]** Dòng gán ở `avatar.py:192` trái BE-00 §11; `convert` áp mọi mode, `exif_transpose` không `in_place`. Số đo của phản biện (RSS 4096², container Linux): RGBA 201 → 137 MB khi bỏ `convert`, → 73 MB khi thêm `exif_transpose(in_place=True)` (`W6/C21/tai-hien-NO-170-171.md`, `quyet-dinh.md`).
- **[4 KHOANH VÙNG]** `apps/api/me/avatar.py`, `apps/api/me/tests/test_avatar_unit.py` (B1-04). Hợp đồng/dây không đổi (đầu ra vẫn RGB/RGBA, EXIF/ICC vẫn xoá bằng `info.clear()`).
- **[5 SỬA NHỎ NHẤT]** Xoá dòng gán và import `ImageFile`; `exif_transpose(in_place=True)`; chỉ `convert` khi mode ≠ RGB/RGBA đích.
- **[6 TEST CHẶN TÁI PHÁT]** `test_decode_and_reencode__does_not_write_truncated_flag`, `test_decode_and_reencode__converts_only_when_mode_is_not_rgb_rgba` (chưa có lượt đỏ, xem [2]).
- **[7 NGHIỆM THU]** Commit `c498aad`, `7e81312` (docstring test còn thiếu); `W6/C21/cov.sh`: me + projects 289 passed, mã thoát 0; `avatar.py` 99% dòng/100% nhánh (thiếu dòng 220, nhánh cũ). Bước 1–4 không ghi trong báo cáo cụm — lượt ghi lại ở `W6/C21/run-all.log` hỏng bước 2 `ruff check` (I001 ở `apps/api/projects/tests/test_routes_build.py`), mã thoát 1. Nợ còn lại: không.

## FIX-249 cho B2-01 — `_storage_of` nuốt thiếu `app.state.storage`, `avatarUrl` biến mất lặng lẽ (NO-194)

- **[1 TRIỆU CHỨNG]** NO-194: `_storage_of` nuốt thiếu `app.state.storage` → `avatarUrl` biến mất lặng lẽ, không có test route; docstring `test_routes_build` sai.
- **[2 TÁI HIỆN]** Đỏ tự nhiên chỉ ở `test_storage_of__raises_when_app_has_no_storage`, chưa chứng kiến (cùng lý do `.git` của FIX-248); test route xanh cả trước lẫn sau — không có đỏ tự nhiên cho dây (`W6/C21/tai-hien-NO-194.md`).
- **[3 BẰNG CHỨNG]** `getattr` hai tầng ở `apps/api/projects/service.py:107`.
- **[4 KHOANH VÙNG]** `apps/api/projects/service.py` + tests (B2-01). Hợp đồng không đổi (mọi app thật có lifespan đặt storage).
- **[5 SỬA NHỎ NHẤT]** `app is None` → `None`, ngược lại đọc thẳng `app.state.storage` (như `deps.storage`); thêm test route + 2 test đơn vị; sửa docstring.
- **[6 TEST CHẶN TÁI PHÁT]** `test_service.py::test_storage_of__raises_when_app_has_no_storage`, `::test_storage_of__none_without_app_and_returns_state_storage`; `test_routes_build.py::test_projects_list_members_carry_signed_avatar_url_from_app_storage` (hồi quy dây).
- **[7 NGHIỆM THU]** Commit `52f03d7`; cùng lượt `cov.sh` của FIX-248: 289 passed, mã thoát 0; `service.py` 100%/100%. Nợ còn lại: không. FIX-250…252 không dùng (NO-207 khi đó đề xuất ➖).

## FIX-253 cho B2-01 — `count_projects_of_users` thiếu guard lô rỗng; `test_wire` tự viết kho giả (NO-193, NO-195)

- **[1 TRIỆU CHỨNG]** NO-193: `apps/api/projects/memberships.py:115-126` `count_projects_of_users` không có `if not user_ids: return {}` (anh em `member_users` và `touch_projects` đều có) → lô rỗng vẫn chạy một câu `... IN ()` xuống Postgres; phần "hết khoá chéo" của `touch_projects` chưa có test hai session. Nit `test_wire` của NO-195: `apps/api/projects/tests/test_wire.py` tự viết `_FakeAvatarStorage`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C22/red.sh` trên cây chưa sửa: `test_count_projects_of_users__empty_batch_runs_no_query` FAILED; 12 failed/116 passed, mã thoát pytest 1 (`W6/C22/red.log`, `tai-hien-NO-193.md`). Test hai session xanh ngay trên cây chưa sửa (FIX-094 đã `ORDER BY id`) — không có đỏ tự nhiên, là test chặn hồi quy.
- **[3 BẰNG CHỨNG]** `W6/C22/quyet-dinh.md` P-1 (`memberships.py:115`, `red.log`); P-2 (bản đầu của test hai session là sleep trá hình sát `lock_timeout` 5 s, `packages/db/settings.py:32` → đổi sang poll `pg_stat_activity` 40×0,1 s, try/finally cancel); P-4 (bỏ `ORDER BY` thì test hai session chưa chắc đỏ → docstring nói thật, test hình dạng SQL bắt đột biến).
- **[4 KHOANH VÙNG]** `apps/api/projects/memberships.py`, `tests/test_memberships.py`, `tests/test_summaries.py`, `tests/test_wire.py` (B2-01). Không đổi hợp đồng dây/openapi/schema DB.
- **[5 SỬA NHỎ NHẤT]** `user_ids` rỗng trả `{}` không chạy câu nào; thêm test hai session thứ tự khoá `touch_projects`; `test_wire.py` dùng fixture `local_storage` (chữ ký thật, không kho giả).
- **[6 TEST CHẶN TÁI PHÁT]** `test_memberships.py::test_count_projects_of_users__empty_batch_runs_no_query` đỏ → xanh; `test_summaries.py::test_touch_projects__reverse_order_sessions_do_not_deadlock` (chặn hồi quy).
- **[7 NGHIỆM THU]** Commit `c9b7341`; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C22/verify.log`); `cov.sh` 482 passed, mã thoát 0 (`cov.log`); `memberships.py` 100%/100%. Nợ còn lại: không (NO-206, NO-150 ➖ do điều phối lúc đó).

## FIX-254 cho B1-03 — hai log `token_mail_failed` cùng tên khác dạng trường, một token hỏng sinh hai bản ghi (NO-195)

- **[1 TRIỆU CHỨNG]** NO-195: `apps/api/auth_recovery/jobs.py:67` (`on_failed`, trường `token_ids`) và `:78` (`_log_isolated_failure`, trường `token_id` + `smtp_code`) cùng tên `token_mail_failed`; đường `PermanentError` thoát khỏi `run_send_token_mail` → `on_failed` ⇒ một token hỏng sinh 2 bản ghi.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C22/red.sh`: J03, 149b và `test_send_token_mail__one_token_mail_failed_record_per_bad_token` FAILED trên cây chưa sửa. Ở lượt đó test mới/149b thiếu `memory_mailer` nên đỏ cũng vì env mail; sau khi trả fixture, đường đỏ thật là "2 bản ghi `token_mail_failed`" (`W6/C22/red.log`, `tai-hien-NO-195.md`).
- **[3 BẰNG CHỨNG]** `W6/C22/quyet-dinh.md` P-3: Nit "`memory_mailer` thừa" của review gốc SAI — fixture đặt env mail mà `get_mail_settings()` (`jobs.py:172`) đọc trước khi `create_mailer` bị thay (`cov.log` lần 1: `MailSettings` ValidationError khi bỏ) → giữ, kèm chú thích; P-7: tên log không ai đọc ngoài auth_recovery (grep `deploy/`, `tools/`, `docs/contracts*`: rỗng).
- **[4 KHOANH VÙNG]** `apps/api/auth_recovery/jobs.py`, `apps/api/auth_recovery/tests/test_jobs.py` (B1-03). Phần `test_wire` của NO-195 thuộc FIX-253 (B2-01). Không đổi hợp đồng dây/openapi/schema DB.
- **[5 SỬA NHỎ NHẤT]** Ghi cô lập từng token đổi tên `token_mail_isolated`; `token_mail_failed` còn một bản ghi mỗi lô hỏng; J03, 149b đổi theo tên mới. Commit thứ hai: docstring còn thiếu và lý do cho `type: ignore` trong `test_jobs.py` để audit phạm vi đạt.
- **[6 TEST CHẶN TÁI PHÁT]** `test_jobs.py::test_send_token_mail__one_token_mail_failed_record_per_bad_token` (đếm `token_mail_failed` == 1) đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `5428fa1`, `475b1a3`; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C22/verify.log`); `cov.sh` 482 passed, mã thoát 0; `test_jobs.py` 24 passed; `jobs.py` 99% dòng (nhánh thiếu 179->175, 222->231 có sẵn, không do sửa). Nợ còn lại: không.

## FIX-255 cho B2-02 — `confidenceThreshold`/`scaleMmPerPx` kiểm dải sau khi làm tròn, lọt `-0.0` ra dây (NO-214)

- **[1 TRIỆU CHỨNG]** NO-214: `apps/api/project_settings/schemas.py:36-47` `_rounded(places)` làm tròn trước; `Confidence = Annotated[Decimal, _rounded(3), Field(ge=0, le=1)]` (dòng 51) kiểm dải trên số đã làm tròn: `-0.0004` → `Decimal("-0.000")` lọt `ge=0` và CHECK DB ⇒ dây trả `-0.0`. Cùng khuyết tật ở cận trên (`1.0004` → `1.000`) và `ScaleMmPerPx` (`0.0099999` → `0.010000`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C22/red.sh`: 4 ca `test_body__range_is_checked_on_the_raw_number_not_the_rounded_one`, `test_body__negative_zero_is_normalized_to_zero`, 3 ca `test_settings_replace_settings__C02[override4-6]` FAILED, mã thoát pytest 1 (`W6/C22/red.log`, `tai-hien-NO-214.md`).
- **[3 BẰNG CHỨNG]** `W6/C22/quyet-dinh.md` P-5 (chọn dải thô, không chỉ dấu âm: openapi/zod FE kiểm số thô, AppFront `projectSettings.ts:40-41`), P-6 (`-0.0` thô → `-0.000` ra dây).
- **[4 KHOANH VÙNG]** `apps/api/project_settings/schemas.py`, `tests/test_units.py`, `tests/test_routes_replace.py` (B2-02). Dây: `1.0004`/`0.0099999` từ 200 → 422 — siết về đúng dải hợp đồng đã công bố, FE gửi đúng dải không đổi, openapi byte-y-nguyên; không đổi schema DB.
- **[5 SỬA NHỎ NHẤT]** `Before(_to_decimal)` → `Field(ge/le)` kiểm số thô → `After(quantize)` + chuẩn hoá `-0.000` → `0.000`. `Field` giữ nguyên nên openapi không đổi.
- **[6 TEST CHẶN TÁI PHÁT]** `test_units.py::test_body__range_is_checked_on_the_raw_number_not_the_rounded_one` (4 ca), `::test_body__negative_zero_is_normalized_to_zero`, `test_routes_replace.py::test_settings_replace_settings__C02` (3 ca mới) đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `ad5569d`; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C22/verify.log`); `cov.sh` 482 passed, mã thoát 0 (`cov.log`); `schemas.py` 100%/100%. Nợ còn lại: không.

## FIX-259 cho B2-03 — docstring route floors còn "chưa hợp nhất", `FloorReorderIn` mô tả sai, N15 phải đọc floors lần hai lấy pk (NO-172, NO-173, NO-223)

- **[1 TRIỆU CHỨNG]** NO-172: docstring 5 test route (`test_routes_{create,delete,list,patch,reorder}.py`) nói "chưa hợp nhất"; NO-173: `FloorReorderIn` nói resolver "luôn" thắng; NO-223 (phần lookup): N15 cần câu floors thứ hai để lấy pk.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C23/red.sh` trên cây chưa sửa: `test_floors_sources__no_stale_unmerged_claim` đỏ mã thoát 1 (5 vị trí); `test_floor_outs_with_pk__pairs_each_floor_with_its_row_pk` đỏ mã thoát 2 (ImportError `floor_outs_with_pk`) (`W6/C23/red.log`). NO-173 không có trạng thái đỏ tự nhiên: chỉ là câu mô tả sai, hành vi thật đã được `apps/api/core/tests/test_routing.py:160` phủ — không thêm test kiểm chữ (`tai-hien-NO-173.md`).
- **[3 BẰNG CHỨNG]** Mô tả viết mù trước khi gộp; `_load_floor_outs` bỏ `FloorRow.pk` dù đã đọc; câu sai của NO-173 đối chiếu `apps/api/core/routing.py:100-105` (`W6/C23/tai-hien-NO-172.md`, `tai-hien-NO-173.md`, `tai-hien-NO-223.md`).
- **[4 KHOANH VÙNG]** `apps/api/floors/**` (B2-03). Hợp đồng không đổi (chữ ký công khai cũ giữ nguyên).
- **[5 SỬA NHỎ NHẤT]** Viết lại docstring; thêm `floor_outs_with_pk`, `_load_floor_outs` trả `(pk, FloorOut)`.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/floors/tests/test_stale_prose.py::test_floors_sources__no_stale_unmerged_claim` (đỏ mã 1 → xanh), `apps/api/floors/tests/test_lookup.py::test_floor_outs_with_pk__pairs_each_floor_with_its_row_pk` (đỏ mã 2 → xanh).
- **[7 NGHIỆM THU]** Commit `ccf67ea`; `cov.log` 616 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C23/verify14.log`). Nợ còn lại: không.

## FIX-260 cho B2-04 — nhánh chết `else b""`, docstring test thiếu, fixture nạp router lần hai, migration thiếu `Create Date` (NO-219)

- **[1 TRIỆU CHỨNG]** NO-219 (phần trong whitelist): `else b""` chết ở `apps/api/drawings/complete.py:104`, 2 docstring `test_jobs`, fixture `latest_client` nạp router lần hai; bổ sung: dòng `Create Date` trong docstring migration `r20260925_b2_04_drawings.py`.
- **[2 TÁI HIỆN]** Không có trạng thái đỏ tự nhiên: `coverage run --branch` trên drawings/tests = 100% dòng, 100% nhánh trước và sau (biểu thức ba ngôi không là nhánh coverage); nạp router lần hai vô hại (route trùng) (`W6/C23/red.log`, `tai-hien-NO-219.md`).
- **[3 BẰNG CHỨNG]** Mọi `_END_MARKERS` dài ≥ 2 (`complete.py:58`) ⇒ `keep` ≥ 1 ⇒ nhánh chết suy ra tĩnh; gốc: sót khi trộn fragment router (`W6/C23/tai-hien-NO-219.md`).
- **[4 KHOANH VÙNG]** `apps/api/drawings/complete.py`, tests drawings (B2-04); commit bổ sung chỉ dòng `Create Date` của `r20260925_b2_04_drawings.py`. Hợp đồng không đổi.
- **[5 SỬA NHỎ NHẤT]** Bỏ nhánh chết + ghi lý do trong docstring; thêm docstring; xoá fixture `latest_client`, dùng `api_client`; bổ sung `Create Date` đầy đủ.
- **[6 TEST CHẶN TÁI PHÁT]** Không có trạng thái đỏ tự nhiên (coverage 100% nhánh trước và sau); commit migration: `test_migrate_check` + `lint_migrations` mã thoát 0 (`W6/C23/green2.log`).
- **[7 NGHIỆM THU]** Commit `fad542c`, `3cba227` (migration); `cov.log` mã thoát 0; `green2.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C23/verify14.log`). Nợ ngoài whitelist lúc đó (`factories/drawings.py` `_EXT_KIND` trùng) xử lý ở FIX-262.

## FIX-261 cho B3-02 — N15 đọc bảng floors hai lần để lấy `{level_id: pk}` (NO-223)

- **[1 TRIỆU CHỨNG]** NO-223 (phần graph): N15 chạy thêm câu `{level_id: pk}` — hai câu `FROM floors` (`_load_floor_outs` + `_floor_pks`).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C23/red.sh`: `test_spatial_read_graph__reads_floors_table_once` đỏ, mã thoát 1 (`W6/C23/red.log`, `tai-hien-NO-223.md`).
- **[3 BẰNG CHỨNG]** Gốc như FIX-259: `_load_floor_outs` bỏ `FloorRow.pk` dù đã đọc, nên graph phải đọc lại.
- **[4 KHOANH VÙNG]** `apps/api/spatial_read/graph.py` + tests (B3-02). Hợp đồng dây không đổi.
- **[5 SỬA NHỎ NHẤT]** `graph.py` dùng `floor_outs_with_pk` (FIX-259), bỏ `_floor_pks`; test race đổi kỳ vọng (đủ 2 tầng).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/spatial_read/tests/test_routes_graph.py::test_spatial_read_graph__reads_floors_table_once` (đếm câu `FROM floors` = 1) đỏ (mã 1) → xanh.
- **[7 NGHIỆM THU]** Commit `45f1dda`; `cov.log` 616 passed, mã thoát 0; `verify14.log` mã thoát 0. Nợ còn lại: không.

## FIX-262 cho B2-04 — factory drawings chép lại bảng đuôi tệp của `uploads` (NO-219)

- **[1 TRIỆU CHỨNG]** NO-219 (phần còn lại): `packages/testing/factories/drawings.py` chép `_EXT_KIND`/`_EXT_TYPE` trùng `uploads.EXT_KIND`/`KIND_MIME`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C23/red2.sh`: test chặn đỏ, mã thoát 1 (log đỏ không lưu riêng trong thư mục cụm).
- **[3 BẰNG CHỨNG]** Factory viết song song, không nhập từ `apps.api.drawings.uploads` (`W6/C23/tai-hien-NO-219.md` mục "ngoài whitelist").
- **[4 KHOANH VÙNG]** `packages/testing/factories/drawings.py` (B2-04). Hợp đồng không đổi.
- **[5 SỬA NHỎ NHẤT]** Nhập bảng đuôi từ `apps.api.drawings.uploads`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_drawings_factory__ext_maps_come_from_uploads` đỏ (mã 1, `red2.sh`) → xanh (mã 0, `W6/C23/green2.log`).
- **[7 NGHIỆM THU]** Commit `9ca4ee4`; `green2.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C23/verify14b.log`). Nợ còn lại: không.

## FIX-264 cho B3-04 — N19 trả `count=1` sai nghĩa, mỗi lượt chụp thừa một `SELECT floors` (NO-244, NO-245)

- **[1 TRIỆU CHỨNG]** NO-244: N19 trả `count=1` sai nghĩa (không phải lỗi Pydantic); NO-245: mỗi lượt chụp thừa một `SELECT floors`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C24/red.sh` (pytest -k trong container): 4 failed (cả 4 test của NO-244/245/250), 84 deselected, mã thoát pytest 1 (`W6/C24/red.log`).
- **[3 BẰNG CHỨNG]** `apps/api/versions/service.py:214` `VALIDATION.error(count=1)`; `snapshots.py:244` `SELECT floors.project_id` thừa sau `lock_floor_document:192` (`W6/C24/tai-hien-NO-244.md`, `tai-hien-NO-245.md`); `quyet-dinh.md` P-1 (`count`/`field` tuỳ chọn ở FE, AppFront `errors.ts:107`), P-3 (`lock_floor_document` chỉ 2 caller).
- **[4 KHOANH VÙNG]** `apps/api/versions/service.py`, `snapshots.py`, `tests/test_routes_restore.py`, `tests/test_snapshots.py` (B3-04). Hợp đồng không đổi (`count` tuỳ chọn). Rủi ro đã loại: sửa `FloorDocument` (spatial_read, K27), đổi schema DB.
- **[5 SỬA NHỎ NHẤT]** `VALIDATION.error()` trần; `lock_floor_document` trả `(project_id, doc)`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_routes_restore.py::test_versions_restore_version__rescale_that_breaks_the_model_is_422` (thêm assert `"count" not in body`), `test_snapshots.py::test_create_version__reads_floors_once` (đếm `SELECT … FROM floors` == 1) — đỏ (mã 1) → xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `9276a03`; `cov.sh` 231 passed, mã thoát 0 (`W6/C24/cov.log`); `verify --steps 1,2,3,4` mã thoát 0 (`verify.log`).

## FIX-265 cho B3-05 — trường lạ trong `rule_configs.overrides` làm N21/N22 trả 500 (NO-250)

- **[1 TRIỆU CHỨNG]** NO-250: dòng `rule_configs.overrides` có trường lạ → N21/N22 500.
- **[2 TÁI HIỆN]** Cùng lượt `W6/C24/red.sh` với FIX-264: 4 failed, mã thoát pytest 1 (`W6/C24/red.log`, `tai-hien-NO-250.md`).
- **[3 BẰNG CHỨNG]** `apps/api/rules/service.py:45-46` giữ trường lạ → WireModel `extra=forbid` → 500; `quyet-dinh.md` P-4 (không vòng import `rules.schemas` ↔ `service`).
- **[4 KHOANH VÙNG]** `apps/api/rules/service.py`, `tests/test_units.py`, `tests/test_routes_read.py` (B3-05). Hợp đồng không đổi.
- **[5 SỬA NHỎ NHẤT]** Lọc theo `RuleConfigOverrideOut.model_fields`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_units.py::test_filter_overrides__drops_unknown_override_field`, `test_routes_read.py::test_rules_read_config__unknown_override_field_filtered` — đỏ (mã 1) → xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `0dc2edd`; `cov.sh` 231 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W6/C24/verify.log`).

## FIX-266 cho B0-06 — 422 khoá idempotency mang `count=1` sai nghĩa (R-19, cùng lỗi NO-244)

- **[1 TRIỆU CHỨNG]** R-19 cùng lỗi NO-244: `apps/api/core/idempotency.py:82` `VALIDATION.error(field=KEY_FIELD, count=1)` — không phải lỗi Pydantic nên `count` sai nghĩa.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W6/C24/red2.sh`: 1 failed, mã thoát 1 (`W6/C24/red2.log`).
- **[3 BẰNG CHỨNG]** `idempotency.py:82`; `W6/C24/quyet-dinh.md` P-2 (nợ khác chủ — core). Grep mọi `VALIDATION.error(...count=...)` ngoài tests trong `apps/**`: chỉ chỗ này.
- **[4 KHOANH VÙNG]** `apps/api/core/idempotency.py`, `apps/api/core/tests/test_idempotency.py` (B0-06). Hợp đồng không đổi (`count` tuỳ chọn).
- **[5 SỬA NHỎ NHẤT]** Bỏ `count=1`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_check_key_rejects_short_key` (thêm assert `"count" not in params`) đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `1761a0f`; core tests 711 passed (`W6/C24/cov2.log`); `verify --steps 1,2,3,4` mã thoát 0 (`verify2.log`). FIX-267 không dùng.

## FIX-268 cho B4-02 — ba điểm P3 của notifications: đọc lại sau ON CONFLICT, trim xếp hạng cả bảng, openapi mất ràng buộc (NO-253)

- **[1 TRIỆU CHỨNG]** NO-253: (1) `scalar_one` sau ON CONFLICT thiếu chú thích/chịu xoá đồng thời; (2) trim xếp hạng cả bảng; (3) openapi #20 mất `minItems`/`maxItems`/`maxLength`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C25/redgreen.sh` trên `0fef850`: 4 test mới đỏ, mã thoát 1 (`W7/C25/redgreen2.log`).
- **[3 BẰNG CHỨNG]** `W7/C25/tai-hien-NO-253.md`, `quyet-dinh.md`.
- **[4 KHOANH VÙNG]** `apps/api/notifications/{service,jobs,schemas}.py`, `tests/test_boundaries.py`, `test_jobs.py`, `test_routes_mark.py` (B4-02). Cấm: `DEBT.md`, `openapi.json`, `.importlinter`, tệp chủ khác.
- **[5 SỬA NHỎ NHẤT]** `one_or_none` + chú thích R-05 (READ COMMITTED); `HAVING count > KEEP_MAX` trước `row_number`; `Annotated` `Field`/`StringConstraints` (validator before giữ `field:ids`); test ranh giới worker chặn thêm starlette và uvicorn. `openapi.json` cần tái sinh (cộng thêm) — việc điều phối; không đổi schema DB.
- **[6 TEST CHẶN TÁI PHÁT]** `test_notification_mark_read_body__openapi_keeps_bounds`, `test_run_notification_trim__overflow_ranks_only_over_cap_users` — đỏ (mã 1) → xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `af4a2c9`, `d4f5e62` (docstring test), `b56c966` (định dạng); độ phủ `service.py` 99% (nhánh 157->159), `jobs.py`, `schemas.py` 100%; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C25/verify14.log`).

## FIX-269 cho B2-06 — sha preview phụ thuộc bản zlib; bộ chặn nhập của test ranh giới thiếu starlette (NO-239, NO-240)

- **[1 TRIỆU CHỨNG]** NO-239: hai môi trường khác bản zlib put lại PNG và reset `published_at` mỗi lượt; NO-240: test ranh giới chặn 3/5 gói của hợp đồng `api-jobs-no-web`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C25/redgreen.sh` trên `0fef850`: 4 test mới đỏ, mã thoát 1 (`W7/C25/redgreen2.log`).
- **[3 BẰNG CHỨNG]** `W7/C25/tai-hien-NO-239.md`, `tai-hien-NO-240.md`, `quyet-dinh.md`.
- **[4 KHOANH VÙNG]** `apps/api/library/assets.py`, `tests/_helpers.py`, `test_assets.py`, `test_jobs_cli.py` (B2-06). Cấm: `DEBT.md`, `openapi.json`, `.importlinter`, tệp chủ khác.
- **[5 SỬA NHỎ NHẤT]** `_same_shas` chỉ so `model_sha256` (ảnh lệch được `_ensure` vá ở chu kỳ verify); `BLOCKED` đủ 5 gói + test quét `.importlinter` giữ đồng bộ; không đổi schema DB.
- **[6 TEST CHẶN TÁI PHÁT]** `test_run_library_publish__other_zlib_build_skips`, `test_blocked_covers_importlinter_jobs_contract` — đỏ (mã 1) → xanh (mã 0). (Test thứ hai về sau bị xoá ở FIX-319 vì trùng `test_worker_blocked__equals_importlinter_contract`.)
- **[7 NGHIỆM THU]** Commit `15f8cc2`, `4f9e037` (docstring helper lồng); `assets.py` 100%/100%; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C25/verify14.log`).

## FIX-273 cho B6-02 — CHECK `failure_code` chỉ chặn một chiều; 45 hàm test thiếu docstring (NO-275, NO-276)

- **[1 TRIỆU CHỨNG]** NO-275: dòng `failed` thiếu `failure_code` lọt DB (`DID NOT RAISE IntegrityError`); NO-276: 45 hàm thiếu docstring (admin_ml_datasets 28, worker/datasets 17).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C26/red.sh` trên `ab8ba73` + test mới: 6 failed, 2 passed, mã thoát 1 (`W7/C26/red.log`, `tai-hien-NO-275.md`, `tai-hien-NO-276.md`).
- **[3 BẰNG CHỨNG]** `packages/db/models/admin_ml_datasets.py:91-94`; `W7/C26/red.log`.
- **[4 KHOANH VÙNG]** Model, revision `r20261004_b6_02_fix273`, test/helper datasets (B6-02). Cấm: `DEBT.md`, `docs/*`, `changes/*`, tệp chủ khác.
- **[5 SỬA NHỎ NHẤT]** CHECK mới `failure_code_failed` (expand, không drop CHECK cũ do lint); backfill `UNKNOWN_FAILURE`; docstring. Không làm revision contract drop `ck_dataset_versions_failure_code` (review R1 F6a): CHECK cũ chặn cả "có mã ⇒ `failed`" lẫn **định dạng mã** (`failure_code ~ FAILURE_CODE_PATTERN`), CHECK mới chỉ chặn chiều có/không — bỏ CHECK cũ làm mất ràng buộc định dạng; phần chồng nhau vô hại. Câu "việc còn lại: drop" ở `W7/C26/quyet-dinh.md:14` chỉ là phương án gọn tên, không bắt buộc — `R/RC/tai-hien-F6a.md`.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/admin_ml_datasets/tests/test_versions.py::test_check_failed_requires_failure_code`; `test_docstrings.py[admin_ml_datasets|worker/datasets]` — đỏ (`red.log`) → xanh (`green.log`, mã thoát 0).
- **[7 NGHIỆM THU]** Commit `1ee1ae7`; `verify --steps 1,2,3,4` đạt (`W7/C26/verify1234.log`, mã thoát 0); `cov.sh` 295 passed, độ phủ 100%/99% (`cov.log`, mã thoát 0); `audit.py` đạt.

## FIX-274 cho B6-01 — lịch requeue khoá lại từng dòng đã khoá; `register_trained_version` 59 dòng; closure test thiếu docstring (NO-260, NO-261, NO-262)

- **[1 TRIỆU CHỨNG]** NO-260: 3 câu `FOR UPDATE` thay vì 1 trong lượt requeue; NO-261: `register_trained_version` 59 dòng > 50; NO-262: closure test thiếu docstring.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C26/red.sh` trên `ab8ba73` + test mới: mã thoát 1 (`W7/C26/red.log`); NO-260: `assert len(statements) == 1` thấy 3 (1 câu lô + 2 lần `_locked` trong `request_evaluation`).
- **[3 BẰNG CHỨNG]** `apps/api/admin_ml_registry/jobs.py:79` → `registry.py:272`; `registry.py:105` (`W7/C26/tai-hien-NO-260.md`, `-261.md`, `-262.md`). `_create_model_versions` của migration (68 dòng) đã hợp nhất, BE-00 §6.1 cấm sửa → đề xuất ➖.
- **[4 KHOANH VÙNG]** `apps/api/admin_ml_registry/**` (B6-01). Cấm: `DEBT.md`, `docs/*`, `changes/*`, tệp chủ khác.
- **[5 SỬA NHỎ NHẤT]** `request_evaluation_locked` dùng chung với lịch requeue; `_checked_values` trả dict (rút `register_trained_version` dưới 50 dòng); docstring closure; thêm test quét docstring/độ dài.
- **[6 TEST CHẶN TÁI PHÁT]** `test_jobs.py::test_requeue_pending_model_evaluations__locks_the_batch_once`; `test_docstrings.py::test_registry_functions_stay_within_the_line_ceiling`, `::test_every_function_has_a_docstring[apps/api/admin_ml_registry]` — đỏ (`red.log`) → xanh (`green.log`, mã thoát 0).
- **[7 NGHIỆM THU]** Commit `ddcefc9`; `verify --steps 1,2,3,4` đạt (`W7/C26/verify1234.log`, mã thoát 0); `cov.sh` 295 passed, độ phủ 100%/99% (`cov.log`, mã thoát 0); `audit.py` đạt.

## FIX-275 cho B6-03a — nhánh `rowcount == 0` của `_purge_one` chưa có test (NO-307)

- **[1 TRIỆU CHỨNG]** NO-307: không có triệu chứng chạy; thiếu test cho nhánh `rowcount == 0` (lịch khác ghi `artifacts_purged_at` giữa lúc xoá và UPDATE).
- **[2 TÁI HIỆN]** Không có trạng thái đỏ tự nhiên: dòng nợ là thiếu test, mã đúng — test xanh ngay; bằng chứng đỏ bằng đột biến `rowcount > 0` → `>= 0` trong `_purge_one` (`W7/C26/tai-hien-NO-307.md`, `green.log`). Lượt chung `bash tools/verify/run.sh shell < W7/C26/red.sh` trên `ab8ba73` + test mới: mã thoát 1, 6 failed, 2 passed (`red.log`).
- **[3 BẰNG CHỨNG]** `apps/worker/training_bridge/jobs.py:274`.
- **[4 KHOANH VÙNG]** `apps/worker/training_bridge/tests/test_jobs.py` (B6-03a). Cấm: `DEBT.md`, `docs/*`, `changes/*`, tệp chủ khác.
- **[5 SỬA NHỎ NHẤT]** Chỉ thêm test, không đổi mã nguồn.
- **[6 TEST CHẶN TÁI PHÁT]** `test_jobs.py::test_purge_training_job_artifacts__rival_beat_wins_the_mark` (đột biến → đỏ; mã thật → xanh, `green.log` mã thoát 0).
- **[7 NGHIỆM THU]** Commit `3f2b213`; `verify --steps 1,2,3,4` đạt (`W7/C26/verify1234.log`, mã thoát 0); `cov.sh` 295 passed, độ phủ 100%/99% (`cov.log`, mã thoát 0); `audit.py` đạt.

## FIX-280 cho B2-05b — assert số luồng pool sau reset quá lỏng, lọt pool kẹt (NO-231)

- **[1 TRIỆU CHỨNG]** NO-231: `apps/api/quality/tests/test_processing.py:234` `assert 1 < len(names) <= workers` không chứng minh pool đã dựng lại theo `quality_workers` mới (pool kẹt 2 luồng với workers=3 vẫn lọt); docstring hàm lồng `scenario()` (`:185`) sai.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh` (đột biến chỉ ở bản chép `/tmp/w`): đột biến `max_workers=min(workers, 2)` → assert cũ xanh (mã thoát 0, lỗ hổng), assert mới đỏ (mã thoát 1) (`W7/C27/mut.log`, `tai-hien-NO-231.md`).
- **[3 BẰNG CHỨNG]** `test_processing.py:234`, `:185`; `W7/C27/quyet-dinh.md` P-7 (`len(names) == workers` không flaky: gate chặn `workers` việc cùng lúc → đúng `workers` luồng).
- **[4 KHOANH VÙNG]** Chỉ tệp test của B2-05b. Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Assert `len(names) == workers`; sửa docstring `scenario()`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_reset_processing_state__applies_new_workers` — đột biến: đỏ (mã 1); mã thật: 1 passed (mã 0).
- **[7 NGHIỆM THU]** Commit `3f01fc2`; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`); `cov.log` 1147 passed, mã thoát 0.

## FIX-281 cho B5-03 — ba Nit review B5-03: docstring `_union_round`, `time.sleep` làm bằng chứng phủ định, `type: ignore` không lý do (NO-289)

- **[1 TRIỆU CHỨNG]** NO-289: (N1) docstring `_union_round` (`apps/ml/objects/detector.py:322-330`) không nói `tiles = NaN` cũng tắt điều kiện (b) cho hộp đã nối; (N2) `time.sleep(0.2)` làm bằng chứng phủ định trong test `apps/ml/objects`; (N3) `type: ignore` thiếu lý do.
- **[2 TÁI HIỆN]** Không có trạng thái đỏ: không có hành vi đổi; bỏ `sleep` vẫn kiểm đủ vì test đếm `== 1` sau khi worker đóng (`W7/C27/tai-hien-NO-289.md`).
- **[3 BẰNG CHỨNG]** `detector.py:322-330`; `W7/C27/tai-hien-NO-289.md`.
- **[4 KHOANH VÙNG]** Chỉ tệp của B5-03 (`apps/ml/objects`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Docstring `_union_round` nói về ô NaN; bỏ `sleep` trong test một-tin-hỏng; lý do sau `type: ignore`.
- **[6 TEST CHẶN TÁI PHÁT]** Không có test đỏ tự nhiên (Nit); `test_tasks.py`, `test_detector.py` xanh.
- **[7 NGHIỆM THU]** Commit `f4d30fd`; `cov.log` 1147 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-282 cho B5-05 — năm bản sao vỏ bọc `build_layer` trong test; điều kiện `raw.size and` thừa, docstring `_checked` cũ (NO-291, NO-293)

- **[1 TRIỆU CHỨNG]** NO-291: năm bản sao vỏ bọc `build_layer` (dựng `WallsResult`/`ObjectsResult`/`TextResult` từ `render_plan`, `level_id`, ảnh) + hằng lặp ở 5 tệp `apps/worker/pipeline_build/tests/test_*.py` (R-07). NO-293: (G1) `apps/worker/pipeline_build/build.py:173,175` điều kiện `raw.size and` thừa; (G2) `build.py:130-134` docstring `_checked` mô tả cũ.
- **[2 TÁI HIỆN]** Không có trạng thái đỏ tự nhiên: NO-291 là refactor, test cũ xanh cả trước lẫn sau; NO-293 G1 không đổi hành vi (mảng (0,6): `.all()` = True, `.any()` = False; fuzz có ca walls rỗng) (`W7/C27/tai-hien-NO-291.md`, `tai-hien-NO-293.md`).
- **[3 BẰNG CHỨNG]** `build.py:173,175`, `:130-134`; `W7/C27/quyet-dinh.md` P-2 (verify lần 1 bắt F821 thiếu import `build_wrapped` ở `test_build_scale.py:44,84` → commit thứ hai), P-6, P-12 (helper đặt ở `tests/helpers.py`, không ở `packages/testing/factories` — chủ ý theo whitelist).
- **[4 KHOANH VÙNG]** Chỉ tệp của B5-05 (`apps/worker/pipeline_build/**`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Một `build_wrapped`/`build_from_plan` + hằng ở `apps/worker/pipeline_build/tests/helpers.py`; bỏ `raw.size and`; sửa docstring `_checked`.
- **[6 TEST CHẶN TÁI PHÁT]** Không có test đỏ tự nhiên (refactor/Nit); toàn bộ `apps/worker/pipeline_build/tests` xanh (mã thoát 0).
- **[7 NGHIỆM THU]** Commit `646f828`, `21b8e43` (import còn thiếu); `cov.log` mã thoát 0, `build.py` 95% dòng+nhánh gộp; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-283 cho B5-06b — helper test trùng giữa bốn tệp của `pipeline_persist`; `fail_step` không chờ after-commit (NO-300)

- **[1 TRIỆU CHỨNG]** NO-300 (review B5-06b lượt 1, P3 R-07): helper test trùng giữa 4 tệp `apps/worker/pipeline_persist/tests/` dù đã có `tests/helpers.py` — `_arrange` ×4 (cases:78, rules:80, runtime:129, lock:97), `_persist_once`/`_persist` ×2, `CPU_QUEUE` ×2, `Maker` ×3, lớp vỡ ×2; `fail_step` không `await after_commit_idle(db)`.
- **[2 TÁI HIỆN]** Không có test đỏ tự nhiên cho phần R-07/LOG-07; RES-03 không có ca đỏ (an toàn nhờ `DB_AFTER_COMMIT_INLINE=1`) (`W7/C27/tai-hien-NO-300.md`).
- **[3 BẰNG CHỨNG]** Các dòng ở [1]; `W7/C27/quyet-dinh.md` P-1 (verify lần 1: ruff F821 `_persist` ở `test_persist_rules.py:342,345,473` → commit `persist_once`), P-8, P-9 (`fail_step` dùng `db` ngoài `async with` đúng khuôn `run_persist`/`_requeue_one`).
- **[4 KHOANH VÙNG]** Chỉ tệp của B5-06b (`apps/worker/pipeline_persist/**`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** `arrange`/`persist_once`/`broken_layer`/`CPU_QUEUE`/`Maker` về một bản trong `tests/helpers.py`; `fail_step` thêm `await after_commit_idle(db)`; thông điệp `RuntimeError` nêu cả ca thiếu dòng `pipeline_run_models`. Lượt C27b: test runtime dùng `ProcessLocal.override` thay vì gán `_factory` (NO-304 phía dùng).
- **[6 TEST CHẶN TÁI PHÁT]** Không có test đỏ tự nhiên; toàn bộ `pipeline_persist/tests` xanh.
- **[7 NGHIỆM THU]** Commit `6c772d5`, `bea761e` (định dạng import), `20f0a6b` (`persist_once` ở test rules), `d504083` (C27b, `ProcessLocal.override`); `cov.log` mã thoát 0, `service.py` 96%; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-284 cho B5-06c — nửa `_IDLE_MARK` và nhánh `sweep_run_fresh` không có test phân biệt (NO-303, NO-301)

- **[1 TRIỆU CHỨNG]** NO-303 (review B5-06c lượt 2, G1 P3): nửa `_IDLE_MARK` của F1 (`m.last_used_at` trong mốc im đọc lại dưới khoá) và nhánh `sweep_run_fresh` của `_requeue_body` không có test phân biệt được. NO-301 phía dùng: `pipeline_steps/tests/helpers.py` giữ bản `queued_tasks` riêng.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh`: đột biến bỏ `m.last_used_at` khỏi `_IDLE_MARK` → test cũ `family_just_finished` xanh (mã thoát 0); test mới đỏ (mã thoát 1) (`W7/C27/mut.log`, `tai-hien-NO-303.md`).
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_steps/sweep.py:168` (nhánh `sweep_run_fresh`, nay được phủ); `W7/C27/quyet-dinh.md` P-10 (test không assert `step_requeue_count`, đã có `read_count == 0`).
- **[4 KHOANH VÙNG]** Chỉ tệp của B5-06c (`apps/worker/pipeline_steps/tests`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Test `_requeue_one` với kết quả đổ về sau khi chọn lô; xoá bản `queued_tasks` riêng, nhập bản chung (FIX-287).
- **[6 TEST CHẶN TÁI PHÁT]** `test_requeue_one_keeps_run_whose_family_finished_after_selection` — đột biến: đỏ (mã 1); mã thật: 1 passed (mã 0).
- **[7 NGHIỆM THU]** Commit `ed967cd`; `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-285 cho B5-07 — docstring test sai sự thật, vết điều phối, test chạm `_factory` riêng tư (NO-304)

- **[1 TRIỆU CHỨNG]** NO-304 (review B5-07 lượt 1–2): docstring test sai sự thật (`apps/worker/pipeline_quality/tests/test_runtime.py:3` trỏ `test_rules.py` không tồn tại; `tests/e2e/test_pipeline_e2e.py:5-7`), vết `(B)`/`(C)`/F1/F3/C2/'việc A'; `_assert_pipeline_layer` không keyword-only; test chạm `tasks._storage`/`_STORAGE._factory` riêng tư.
- **[2 TÁI HIỆN]** Không có test đỏ tự nhiên (docstring/chữ ký test) (`W7/C27/tai-hien-NO-304.md`).
- **[3 BẰNG CHỨNG]** `test_runtime.py:3`, `:158,219`; `test_pipeline_e2e.py:5-7`; `W7/C27/quyet-dinh.md` P-11 (phần `_STORAGE._factory` để lại lượt đầu, làm ở C27b — `W7/C27/spec-C27b.md` mục 1).
- **[4 KHOANH VÙNG]** Chỉ tệp của B5-07 (`apps/worker/pipeline_quality/tests`, `tests/e2e`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Sửa docstring sai, bỏ vết điều phối và tham chiếu chết; `_assert_pipeline_layer` keyword-only; C27b: fixture `storage_override` dùng `ProcessLocal.override` thay vì gán `_factory`.
- **[6 TEST CHẶN TÁI PHÁT]** Không có test đỏ tự nhiên; `pipeline_quality/tests` + `tests/e2e` xanh.
- **[7 NGHIỆM THU]** Commit `9efc7b6`, `ce69412` (C27b, `ProcessLocal.override`); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-286 cho B0-05 — test hồi quy FIX-115 rò dòng sổ `_TASKS`, `import_module` sau ảnh chụp là no-op (NO-315)

- **[1 TRIỆU CHỨNG]** NO-315 (review FIX-115, P3): `packages/messaging/tests/test_tasks.py:653` `importlib.import_module` sau ảnh chụp `before` là no-op (gợi ý sai bước dựng); `:650` test hồi quy nhập `apps.ml.objects.tasks` mà không lưu/trả `_TASKS` → rò dòng task sang test sau.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh`: bỏ fixture (hành vi cũ) → sổ `_TASKS` sau test thừa `['ml.infer.objects.detect']` (pytest mã thoát 0, rò); rò chỉ thấy sau teardown nên đo bằng `/tmp/leak.py` (hook `collection_finish`) (`W7/C27/mut.log`, `tai-hien-NO-315.md`).
- **[3 BẰNG CHỨNG]** `packages/messaging/tests/test_tasks.py:650,653`.
- **[4 KHOANH VÙNG]** Chỉ tệp của B0-05 (`packages/messaging/tests`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Fixture `restored_task_ledger`, bỏ `import_module` no-op; thêm docstring còn thiếu; C27b (R-02): docstring nói điều mỗi test chứng minh thay vì kể lại tên.
- **[6 TEST CHẶN TÁI PHÁT]** `test_drop_new_ml_modules_keeps_modules_loaded_before_the_snapshot` (fixture `restored_task_ledger`) — có fixture: `LEAKED: []`.
- **[7 NGHIỆM THU]** Commit `fc6f890`, `da63ccc` (docstring), `c8d224e` (định dạng), `e27bcea` (C27b, R-02); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-287 cho B0-05 — fixture messaging thiếu `queued_tasks` trả tên task (NO-301)

- **[1 TRIỆU CHỨNG]** NO-301: `packages/testing/fixtures/messaging.py` chỉ có `queued_payloads` (trả `args[0]`), thiếu `queued_tasks(client, queue)` trả cả tên task (`headers.task`) — test đếm "đúng một `pipeline.build.run`/`ml.infer.*`" phải tự viết bản riêng.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh`: bỏ `queued_tasks` khỏi fixture (cây chưa sửa) → lỗi thu thập ImportError, mã thoát 2 (`W7/C27/mut.log`, `tai-hien-NO-301.md`).
- **[3 BẰNG CHỨNG]** `packages/testing/fixtures/messaging.py`; bản riêng ở `pipeline_steps/tests/helpers.py` (xoá ở FIX-284).
- **[4 KHOANH VÙNG]** Chỉ tệp của B0-05 (`packages/testing/fixtures/messaging.py`, test ở `test_celery_app`). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** `queued_tasks(client, queue)` trả tên task từ envelope kombu, mới nhất trước.
- **[6 TEST CHẶN TÁI PHÁT]** `test_queued_tasks__names_every_message_on_a_shared_queue_newest_first` — thiếu hàm: mã 2; có hàm: 1 passed (mã 0).
- **[7 NGHIỆM THU]** Commit `7ee8c97`, `8d47da8` (docstring ≤ 120 cột); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-288 cho B4-01 — nhánh `_pull` của fixture SSE (app thoát không gửi thân) chưa có test (NO-192)

- **[1 TRIỆU CHỨNG]** NO-192 (phần còn lại của NO-155, đóng một phần bởi FIX-096): `packages/testing/fixtures/streams.py:156` (`_pull`: app ASGI thoát mà không gửi thêm message → `RuntimeError`) chưa có test.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh`: đột biến `_pull` thôi ném `RuntimeError` (`streams.py:156` → `return None`) → test đỏ, mã thoát 1 (`W7/C27/mut.log`, `tai-hien-NO-192.md`).
- **[3 BẰNG CHỨNG]** `packages/testing/fixtures/streams.py:156` (nay được phủ).
- **[4 KHOANH VÙNG]** Chỉ tệp của B4-01. Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Thêm test app thoát sau `http.response.start` không gửi thân → `RuntimeError`; docstring probe observer (C27b, R-02).
- **[6 TEST CHẶN TÁI PHÁT]** `test_next_frames_raises_when_the_app_exits_without_sending_a_body` — đột biến: đỏ (mã 1); mã thật: 1 passed (mã 0).
- **[7 NGHIỆM THU]** Commit `fe3a06d`, `26014d1` (docstring), `9e97f1a` (C27b, R-02); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-289 cho B3-01 — seed spatial dựng lại hình dạng tài liệu, phép đếm và tập id thay vì dùng chung với API (NO-220)

- **[1 TRIỆU CHỨNG]** NO-220 (phần miền): `packages/db/seeds/spatial.py` (B3-02) dựng lại hình dạng `codec.document_to_json`, phép đếm `counts.layer_counts` và tập id `codec.entity_ids` bằng `packages.domain.spatial` (R-07, trùng lặp); các helper này chưa nằm ở miền nên seed không dùng chung được.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C27/mut.sh`: đột biến seed giữ bản sao riêng `document_to_json` → test đỏ, mã thoát 1 (`W7/C27/mut.log`, `tai-hien-NO-220.md`).
- **[3 BẰNG CHỨNG]** `packages/db/seeds/spatial.py`; điều phối chọn phương án B (mở whitelist) (`W7/C27/tai-hien-NO-220.md`).
- **[4 KHOANH VÙNG]** `packages/domain/spatial/document.py` + test (B3-01). Không chạm `graph.py`; không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** Hạ `document_to_json`/`LayerCounts`/`layer_counts`/`entity_ids` xuống `packages/domain/spatial/document.py`; tách assert ghép ở test (PT018).
- **[6 TEST CHẶN TÁI PHÁT]** `test_seed_shares_the_domain_helpers_with_the_api` — đột biến: đỏ (mã 1); mã thật: xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `9b0d0fd`, `55d92cd` (assert ghép); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`). FIX-291 dự trữ không dùng ở lượt này.

## FIX-290 cho B3-02 — `spatial_read` và seed gọi helper miền chung thay vì bản riêng (NO-220)

- **[1 TRIỆU CHỨNG]** NO-220 (phần spatial_read + seed): seed dựng lại hình dạng tài liệu, phép đếm và tập id (như FIX-289).
- **[2 TÁI HIỆN]** Như FIX-289 (`W7/C27/mut.log`, đỏ mã thoát 1).
- **[3 BẰNG CHỨNG]** `packages/db/seeds/spatial.py`; `W7/C27/quyet-dinh.md` P-5 (mypy: `seed_module.document_to_json` không xuất tường minh, `verify2.log` → đổi sang `vars(seed_module)[...]`), P-13.
- **[4 KHOANH VÙNG]** Chỉ tệp của B3-02 (`apps/api/spatial_read` codec/counts, `packages/db/seeds/spatial.py`, test seed). Không sửa `DEBT.md`, `docs/*`, `conftest.py`, `pyproject.toml`; không đổi hợp đồng FE–BE, schema DB.
- **[5 SỬA NHỎ NHẤT]** codec/counts chuyển tiếp helper miền qua `__all__`; seed bỏ các bản sao, gọi thẳng; test seed khẳng định việc dùng chung (đọc tên qua `vars`).
- **[6 TEST CHẶN TÁI PHÁT]** `test_seed_shares_the_domain_helpers_with_the_api` — đột biến: đỏ (mã 1); mã thật: xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `73ddd39`, `97393a3` (đọc tên qua `vars`); `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C27/verify3.log`).

## FIX-291 cho B0-05 — `ProcessLocal` thiếu cổng công khai cho test, test phải ghi đè `_factory` riêng tư (NO-304)

- **[1 TRIỆU CHỨNG]** NO-304 phần còn lại: test của orchestrate/persist/quality chạm `tasks._storage` / `_STORAGE._factory` riêng tư để thay nguồn tài nguyên; C27 đề xuất ➖ phần này vì `ProcessLocal` (`packages/messaging/redis.py`) nằm ngoài whitelist (`W7/C27/tai-hien-NO-304.md`, `quyet-dinh.md` P-11).
- **[2 TÁI HIỆN]** Không có test đỏ tự nhiên — lỗi là dạng mã test (chạm thuộc tính riêng tư); C27b mở whitelist cho tệp định nghĩa `ProcessLocal` (`W7/C27/spec-C27b.md` mục 1).
- **[3 BẰNG CHỨNG]** `W7/C27/quyet-dinh.md` P-11 (`test_runtime.py:158,219` chạm `_STORAGE._factory`); `tai-hien-NO-304.md` mục "CÒN DỞ".
- **[4 KHOANH VÙNG]** `packages/messaging/redis.py` + `packages/messaging/tests/test_redis.py` (B0-05); các test chuyển sang cổng mới là commit riêng của chủ chúng (FIX-283 persist, FIX-285 quality, FIX-321 orchestrate).
- **[5 SỬA NHỎ NHẤT]** Thêm context manager `ProcessLocal.override(factory)` ("chỉ cho test"): dưới khoá thay `_factory` và quên tài nguyên đang giữ, thoát khối (kể cả khi thân ném) trả factory cũ và quên tài nguyên lần nữa (`4e82c81`); `8231b00` sửa PT012 của test mới.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/messaging/tests/test_redis.py::test_process_local_override_restores_the_factory_even_when_the_body_raises`.
- **[7 NGHIỆM THU]** Commit `4e82c81`, `8231b00` (nhánh `fix/debt-02-w7-test-quality`); bước 1–4 đạt trên `8231b00` (`W7/C27/verify5.log`, mã thoát 0); pytest 6 tệp test đổi 142 passed (`last5.log`); cổng tích hợp `7ae1292` bước 5 8365 passed, mã thoát 0 (`tich-hop-gate-2.log`).

## FIX-292 cho B0-03 — template revision ép `down_revision` nhiều head thành chuỗi, `migrate_check` không qua head merge; luật đọc lại của `db_session` (NO-249, NO-235)

- **[1 TRIỆU CHỨNG]** NO-249 (P2): `run.sh merge-heads` hỏng `KeyError: "('a', 'b')"`; revision merge viết tay thì `migrate_check` hỏng `downgrade -1` (`Ambiguous walk`). NO-235 (P3): test HTTP `rollback()` rồi chạm `obj.pk` → `MissingGreenlet`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W7/C28/red.sh` trên `eefba60` + test mới: `test_run_checks__merge_revision_from_template_passes` FAILED (1 failed, 2 passed), mã thoát 1; thử nghiệm phụ với `down_revision` tuple thật: `downgrade -1` → `CommandError('Ambiguous walk')` (`W7/C28/red.log`, `tai-hien-NO-249.md`, `tai-hien-NO-235.md`).
- **[3 BẰNG CHỨNG]** `packages/db/migrations/script.py.mako:17` `'"{}"'.format(down_revision)` ép tuple nhiều head thành một chuỗi; `packages/db/migrate_check.py` bước "downgrade -1" dùng `-1` tương đối, không xác định từ revision hai cha. `Session.rollback` luôn hết hạn instance (không có cờ như `expire_on_commit`) — fixture không ghi luật.
- **[4 KHOANH VÙNG]** `packages/db/migrations/script.py.mako`, `packages/db/migrate_check.py`, docstring fixture `db_session`, `packages/db/tests/*` (B0-03). Hợp đồng không đổi — `merge-heads` giữ (BE-00 §6.1), `run_checks` vẫn 10 bước cùng tên; revision cũ giữ `str | None`.
- **[5 SỬA NHỎ NHẤT]** Mako in `down_revision: str | Sequence[str] | None = ${repr(down_revision).replace("'", '"')}`; `migrate_check._one_step_down` đi theo cha thứ nhất tới revision một cha rồi hạ xuống cha của nó (một cha: y như `-1` cũ; merge: gỡ merge + nhánh, `upgrade head` chạy lại revision thật). Docstring `db_session`: `commit()` + `refresh()`, không `rollback()`. `test_new_revision.py:78` theo annotation mới.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_migrate_check.py::test_run_checks__merge_revision_from_template_passes` (đỏ `KeyError` → xanh); `packages/db/tests/test_db_session_fixture.py::test_db_session__rollback_expires_loaded_instances`, `::test_db_session__commit_then_refresh_sees_foreign_write`.
- **[7 NGHIỆM THU]** Commit `374c7ab`; `cov.log`, `cov2.log` (73 passed) mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C28/verify14.log`).

## FIX-293 cho B0-01 — test `merge-heads` dùng mako tự chế, che lỗi của template thật (NO-249)

- **[1 TRIỆU CHỨNG]** NO-249 (phần lọt lỗi): `test_merge_heads_hai_head_ra_đúng_một_file` xanh trong khi `run.sh merge-heads` thật hỏng.
- **[2 TÁI HIỆN]** `W7/C28/cov.sh` đặt lại mako cũ trong bản chép container: `test_merge_heads_hai_head_ra_đúng_một_file` đỏ `KeyError: "('r20260921_b9_01', 'r20260921_b9_02')"`, mã thoát 1 (`W7/C28/cov.log`, `tai-hien-NO-249.md`).
- **[3 BẰNG CHỨNG]** `tools/tests/test_steps_commands.py:440-448` render bằng mako tự chế (`repr(down_revision)`), khác template của repo.
- **[4 KHOANH VÙNG]** `tools/tests/test_steps_commands.py` (B0-01). Chỉ test; không đổi `steps.py`.
- **[5 SỬA NHỎ NHẤT]** `_alembic_repo` chép `packages/db/migrations/script.py.mako` thật.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_steps_commands.py::test_merge_heads_hai_head_ra_đúng_một_file` — mako cũ đỏ (mã 1), mako mới xanh (`cov.log`).
- **[7 NGHIỆM THU]** Commit `c672ed3`; `cov.log` mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W7/C28/verify14.log`).

## FIX-295 cho B5-06b — `_read_built` lặp `_read_artifact`; `_floor_state` viết lại luật cửa sổ (NO-297)

- **[1 TRIỆU CHỨNG]** `apps/worker/pipeline_persist/service.py:76-110`: `_read_built` tự viết vòng gom-tới-trần, `_floor_state` viết lại luật cửa sổ khôi phục.
- **[2 TÁI HIỆN]** Như FIX-209 (`W4/C15b/tai-hien-NO-225.md`: quét AST thấy `pipeline_persist/service.py:84`).
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_persist/service.py`; `W4/C15b/quyet-dinh.md` P-5 (`.importlinter` không cấm worker nhập `apps.api.drawings.runs`).
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_persist/service.py`. Cấm: file của chủ khác.
- **[5 SỬA NHỎ NHẤT]** `_read_built` gọi `read_all_capped`; `_floor_state` gọi `restore_window_elapsed` của B2-04 (worker đã nhập `apps.api.drawings.runs`). Không đổi hợp đồng công khai.
- **[6 TEST CHẶN TÁI PHÁT]** Quét AST + `restore_window_elapsed` + test `pipeline_persist` hiện có.
- **[7 NGHIỆM THU]** `W4/C15b/cov-run.log` mã thoát 0; commit `7c6a23e` (trailer thay FIX-215 nhầm).

## FIX-296 cho B6-03b — kho 503 bị biến thành lỗi vĩnh viễn ở dataset (không có dòng NO — R-16; `_read_manifest` là bản thứ 7 của mẫu NO-225)

- **[1 TRIỆU CHỨNG]** `load_plan`/`download` ném `PermanentError` khi kho trả `DEPENDENCY_UNAVAILABLE`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W4/C15b/red3.sh` trước khi sửa (`W4/C15b/red3.log`: 5 failed, 1 passed, mã thoát 1).
- **[3 BẰNG CHỨNG]** `dataset.py:_read_manifest` bắt mọi `AppError`; `_download_one` bắt mọi `AppError`; `W4/C15b/quyet-dinh.md` P-4.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/dataset.py` + test. Cấm: file của chủ khác (C18 `slot/keys/tasks`, C19 `floors/{schemas,lookup}`).
- **[5 SỬA NHỎ NHẤT]** `_read_manifest` gọi `read_all_capped`; `_download_one` chỉ đổi `NOT_FOUND` thành `DATASET_OBJECT_MISMATCH`, vẫn xoá tệp dở rồi lan lỗi khác. Không đổi hợp đồng dây.
- **[6 TEST CHẶN TÁI PHÁT]** `test_load_plan__storage_unavailable_stays_retryable`, `test_download__storage_unavailable_stays_retryable`; quét AST mở rộng sang `chunks.append`.
- **[7 NGHIỆM THU]** `W4/C15b/cov2-run.log` mã thoát 0 (ruff, format, mypy, 1229 passed, độ phủ 100 % dòng+nhánh các file sửa); `verify --steps 1,2,3,4` mã thoát 0 (`verify-1234.log`); đỏ → xanh; commit `eab74bf`.

## FIX-297 cho B2-03 — biên cửa sổ khôi phục tầng lệch luật chung (NO-297)

- **[1 TRIỆU CHỨNG]** POST #10 khôi phục tầng xoá đúng `window` giây trước, trong khi pipeline coi là hết.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W4/C15b/red3.sh` trước khi sửa (`W4/C15b/red3.log`: 5 failed, 1 passed, mã thoát 1).
- **[3 BẰNG CHỨNG]** `floors/service.py:_restorable` so `deleted_at >= cutoff`; `W4/C15b/quyet-dinh.md` P-6.
- **[4 KHOANH VÙNG]** `apps/api/floors/service.py` + test. Cấm: file của chủ khác (C18 `slot/keys/tasks`, C19 `floors/{schemas,lookup}`).
- **[5 SỬA NHỎ NHẤT]** `_restorable` gọi `restore_window_elapsed` (nửa mở `[0, window)`, điều phối chốt phương án A). Không đổi hợp đồng dây.
- **[6 TEST CHẶN TÁI PHÁT]** `test_floors_create_floor__restore_exactly_at_window_gets_new_pk`.
- **[7 NGHIỆM THU]** `W4/C15b/cov2-run.log` mã thoát 0 (1229 passed, độ phủ 100 % dòng+nhánh các file sửa); `verify --steps 1,2,3,4` mã thoát 0 (`verify-1234.log`); đỏ → xanh; commit `2a37034`.

## FIX-298 cho B3-02 — biên cửa sổ khôi phục lệch ở nhận lại entity id (NO-297)

- **[1 TRIỆU CHỨNG]** id của tầng xoá đúng `window` giây trước còn bị coi là giữ chỗ.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W4/C15b/red3.sh` trước khi sửa (`W4/C15b/red3.log`: 5 failed, 1 passed, mã thoát 1).
- **[3 BẰNG CHỨNG]** `entity_ids.py:claim_entity_ids` so `deleted_at >= cutoff`; `W4/C15b/quyet-dinh.md` P-6.
- **[4 KHOANH VÙNG]** `apps/api/spatial_read/entity_ids.py` + test. Cấm: file của chủ khác (C18 `slot/keys/tasks`, C19 `floors/{schemas,lookup}`).
- **[5 SỬA NHỎ NHẤT]** Dùng `restore_window_elapsed`. Không đổi hợp đồng dây.
- **[6 TEST CHẶN TÁI PHÁT]** `test_soft_deleted_owner_exactly_at_window_is_reclaimed`.
- **[7 NGHIỆM THU]** `W4/C15b/cov2-run.log` mã thoát 0 (1229 passed, độ phủ 100 % dòng+nhánh các file sửa); `verify --steps 1,2,3,4` mã thoát 0 (`verify-1234.log`); đỏ → xanh; commit `6bc4e7a`.

## FIX-299 cho B6-04a — `training_segformer/errors.py` khai lại mã của `runtime`/`training_runner` (không có dòng NO — vết C18b, cùng họ NO-285)

- **[1 TRIỆU CHỨNG]** `MODEL_CHECKSUM_MISMATCH`, `MODEL_FORMAT_UNSUPPORTED`, `DATASET_SPLIT_EMPTY` khai lại (R-07) để tránh kéo `onnxruntime`.
- **[2 TÁI HIỆN]** `run.sh shell < W5/C18/b.sh` phần TÁI HIỆN (cây chưa sửa khôi phục từ `.c18-orig`) — `test_runtime_constants__not_redeclared` liệt kê `training_segformer/errors.py:*`, `test_error_codes__import_light` ModuleNotFoundError; 2 failed, mã thoát 1 (`W5/C18/b.log`, `tai-hien-C18b.md`).
- **[3 BẰNG CHỨNG]** `apps/ml/training_segformer/errors.py:23-25` (cũ).
- **[4 KHOANH VÙNG]** `apps/ml/training_segformer/errors.py`, `tests/test_model.py` (docstring). Cấm: file khác.
- **[5 SỬA NHỎ NHẤT]** Nhập `MODEL_*` từ `apps.ml.runtime.error_codes` (mới, chỉ `typing`), `DATASET_SPLIT_EMPTY` từ `apps.ml.training_runner.errors` (nay chỉ nhập `error_codes`). Chuỗi không đổi; luật "nhập trainer không kéo onnxruntime" giữ (`test_trainer_discovered`, `test_error_codes__import_light`).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/ml/runtime/tests/test_single_source.py::test_runtime_constants__not_redeclared`, `::test_error_codes__import_light`.
- **[7 NGHIỆM THU]** Đỏ → xanh (`b.log` → `b2.log`: `test_single_source` 4 passed; `b3.log` 293 passed, ruff/format mã thoát 0); verify 1–4 mã thoát 0 (`W5/C18/verify-b.log`); commit `bc8b1e3`.

## FIX-300 cho B6-04b — `ml_eval/sandbox.py` khai lại `MODEL_FORMAT_UNSUPPORTED` (không có dòng NO — vết C18b, cùng họ NO-285)

- **[1 TRIỆU CHỨNG]** Hằng lặp lại của `runtime.errors` vì module ấy kéo `onnxruntime` (trần `RLIMIT_AS` phải đặt trước).
- **[2 TÁI HIỆN]** `run.sh shell < W5/C18/b.sh` — `test_runtime_constants__not_redeclared` liệt kê `ml_eval/sandbox.py:MODEL_FORMAT_UNSUPPORTED`, mã thoát 1 (`W5/C18/b.log`).
- **[3 BẰNG CHỨNG]** `apps/ml/ml_eval/sandbox.py:27-28` (cũ).
- **[4 KHOANH VÙNG]** `apps/ml/ml_eval/sandbox.py`. Cấm: file khác.
- **[5 SỬA NHỎ NHẤT]** Nhập từ `apps.ml.runtime.error_codes` (chỉ `typing`): mức module vẫn không nhập `onnxruntime` trước trần bộ nhớ — `test_error_codes__import_light` khẳng định.
- **[6 TEST CHẶN TÁI PHÁT]** `test_single_source.py::test_runtime_constants__not_redeclared`, `::test_error_codes__import_light`; ca trần bộ nhớ có sẵn ở `apps/ml/ml_eval/tests/test_sandbox.py`.
- **[7 NGHIỆM THU]** Đỏ → xanh (`b.log` → `b2.log`, `b3.log` mã thoát 0); verify 1–4 mã thoát 0 (`W5/C18/verify-b.log`); commit `bd0ee00`.

## FIX-301 cho B7-02 — ASVS B-20 trỏ dòng `gpu.py` đã đổi sau FIX-230 (không có dòng NO — vết C18b)

- **[1 TRIỆU CHỨNG]** `docs/security/asvs-checklist.md:9` dẫn `gpu.py:140-149`, `:57`, `:43-45` — không còn đúng (lõi khoá về `lease.py`).
- **[2 TÁI HIỆN]** `wc -l apps/ml/runtime/gpu.py` = 114 < 140; `grep -n` các ký hiệu dẫn chứng (`W5/C18/tai-hien-C18b.md`).
- **[3 BẰNG CHỨNG]** `gpu.py:102-114` `gpu_slot`, `gpu.py:35-38` `GpuSlot.check`, `lease.py:103-106` `check_timing`, `lease.py:70-100` `RenewThread`, `lease.py:125-156` `held_lease`.
- **[4 KHOANH VÙNG]** Dòng B-20 của `docs/security/asvs-checklist.md`. Cấm: dòng khác; trạng thái "đạt" giữ nguyên (test dẫn chứng vẫn tồn tại, tên không đổi).
- **[5 SỬA NHỎ NHẤT]** Trỏ lại dẫn chứng theo dòng hiện tại.
- **[6 TEST CHẶN TÁI PHÁT]** Tài liệu — không có test tự động; kiểm bằng `grep -n`.
- **[7 NGHIỆM THU]** Commit docs riêng `d9d67f7`.

## FIX-302 cho B0-03 — `lock_project_scope` nằm ở `measurements`, `templates` nhập chéo module anh em (NO-247)

- **[1 TRIỆU CHỨNG]** `lock_project_scope` ở `apps/api/measurements/locks.py:7`, `apps/api/templates/service.py:13` nhập chéo module anh em; `packages/db` không có hàm khoá tư vấn theo dự án.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W5/C19/red2.sh` → mã thoát 1: 5 failed + 1 error (`packages/db/tests/test_locks.py` ImportError `packages.db.locks`) (`W5/C19/red2.log`, `tai-hien-NO-247.md`).
- **[3 BẰNG CHỨNG]** `apps/api/measurements/locks.py:7`, `apps/api/templates/service.py:13` (`W5/C19/spec.md` dòng NO-247).
- **[4 KHOANH VÙNG]** `packages/db/locks.py` (mới), `packages/db/tests/test_locks.py`.
- **[5 SỬA NHỎ NHẤT]** `packages/db/locks.py` `lock_project_scope` (khoá tư vấn theo dự án); hai module gọi lại ở FIX-305.
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_locks.py::test_lock_project_scope__holds_one_advisory_lock_until_commit` (Postgres thật).
- **[7 NGHIỆM THU]** `W5/C19/cov2.log` mã thoát 0 (1183 passed; ruff, mypy sạch; `locks.py` 100 %); `verify --steps 1,2,3,4` mã thoát 0 (`W5/C19/verify.log`); commit `1884b15` (trailer thay FIX-241 nhầm, C19b).

## FIX-303 cho B0-06 — hai hàm `_role` gần giống ở `core/auth.py` và `auth/sessions.py` (NO-188)

- **[1 TRIỆU CHỨNG]** `apps/api/core/auth.py` và `apps/api/auth/sessions.py` mỗi nơi một `_role` gần giống; `parse_role` công khai chưa có.
- **[2 TÁI HIỆN]** `W5/C19/red2.sh` → mã thoát 1: `test_parse_role__valid_and_unknown`, `test_sessions__reuses_core_parse_role` FAILED (`W5/C19/red2.log`, `tai-hien-NO-247.md`).
- **[3 BẰNG CHỨNG]** `W5/C19/spec.md` dòng NO-188 (`ROLES` gương, hai `_role`).
- **[4 KHOANH VÙNG]** `apps/api/core/auth.py`, `apps/api/core/tests/test_parse_role.py`.
- **[5 SỬA NHỎ NHẤT]** `parse_role` công khai thay `_role`; `sessions.py` gọi lại ở FIX-304.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/core/tests/test_parse_role.py::test_parse_role__valid_and_unknown`, `::test_sessions__reuses_core_parse_role`.
- **[7 NGHIỆM THU]** `W5/C19/cov2.log` mã thoát 0 (1183 passed; `core/auth.py` 100 %); `verify.log` bước 1–4 mã thoát 0; commit `2a14b64`, `238f149` (test kiểu an toàn) (trailer thay FIX-242 nhầm, C19b).

## FIX-304 cho B1-01 — `ROLES` gương ở `packages/db/models/auth.py` trùng domain, `sessions.py` có `_role` riêng (NO-188)

- **[1 TRIỆU CHỨNG]** `ROLES` gương ở `packages/db/models/auth.py:29` trùng `packages.domain.permissions.ROLES`; `apps/api/auth/sessions.py` có `_role` riêng.
- **[2 TÁI HIỆN]** `W5/C19/red2.sh` → mã thoát 1: `test_users_roles__is_the_permissions_mirror` FAILED (`ROLES` không phải cùng đối tượng với gương domain) (`W5/C19/red2.log`).
- **[3 BẰNG CHỨNG]** `packages/db/models/auth.py:29`, `apps/api/auth/sessions.py` (`W5/C19/spec.md` dòng NO-188).
- **[4 KHOANH VÙNG]** `packages/db/models/auth.py`, `apps/api/auth/sessions.py`, `packages/db/tests/test_roles_mirror.py`. Tệp test `packages/db/tests/test_roles_mirror.py` thuộc **B0-03** (kiểm `packages.db.models.auth.ROLES is packages.domain.permissions.ROLES` — hành vi model của `packages/db/**`), nằm trong commit `Prompt: B1-01` là lỗi K27 lịch sử; review R1 F2 xét: giữ nguyên, không dời, không hoàn (trên `main` tệp không tồn tại nên hoàn = xoá một test đúng của B0-03) — `R/RC/tai-hien-F2.md`.
- **[5 SỬA NHỎ NHẤT]** `models/auth.py` nhập `ROLES` từ domain; `sessions.py` dùng `parse_role` (FIX-303).
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_roles_mirror.py::test_users_roles__is_the_permissions_mirror`; `test_sessions__reuses_core_parse_role` (FIX-303).
- **[7 NGHIỆM THU]** `W5/C19/cov2.log` mã thoát 0 (1183 passed; `models/auth.py` 100 %, `sessions.py` 99 % — dòng 589 cũ); `verify.log` bước 1–4 mã thoát 0; commit `12e0178`, `13a4e2c` (test kiểu an toàn) (trailer thay FIX-243 nhầm, C19b).

## FIX-305 cho B2-07 — `measurements/locks.py` riêng, `templates` nhập chéo; `measurements/text.py` bản chép luật Cc/bidi thứ 5 (NO-247, NO-169)

- **[1 TRIỆU CHỨNG]** `apps/api/measurements/locks.py` giữ `lock_project_scope`, `apps/api/templates/service.py` nhập chéo; `apps/api/measurements/text.py` là bản chép luật Cc/bidi thứ 5.
- **[2 TÁI HIỆN]** `W5/C19/red2.sh` → mã thoát 1: `test_templates_service__lock_comes_from_packages_db`, `test_measurements__has_no_private_locks_module` FAILED (`W5/C19/red2.log`). Phần `text.py`: test riêng không ghi trong báo cáo cụm.
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-6 (`measurements/text.py` bản chép thứ 5 → làm trong commit B2-07).
- **[4 KHOANH VÙNG]** `apps/api/measurements/{locks.py (xoá), service.py, text.py}`, `apps/api/templates/service.py`, `apps/api/{measurements,templates}/tests/test_locks_source.py`.
- **[5 SỬA NHỎ NHẤT]** `measurements`/`templates` gọi `packages.db.locks` (FIX-302), xoá `measurements/locks.py`; `measurements/text.py` dùng `clean_text`.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/measurements/tests/test_locks_source.py::test_measurements__has_no_private_locks_module`, `apps/api/templates/tests/test_locks_source.py::test_templates_service__lock_comes_from_packages_db`.
- **[7 NGHIỆM THU]** `W5/C19/cov2.log` mã thoát 0 (1183 passed); `verify.log` bước 1–4 mã thoát 0; commit `9412e89` (trailer thay FIX-244 nhầm, C19b).

## FIX-306 cho B3-01 — `packages/domain/spatial/model.py` giữ bản chép tập ký tự Cc/bidi (NO-169 nhánh domain)

- **[1 TRIỆU CHỨNG]** `packages/domain/spatial/model.py:36,62` còn bản chép tập ký tự Cc/bidi (`_BIDI_CONTROLS`); hợp đồng ở đây từ chối chứ không strip.
- **[2 TÁI HIỆN]** `W5/C19/red3.sh` → `test_spatial_model__forbidden_chars_come_from_core_text` FAILED, 1 failed / 90 passed (`W5/C19/red3.log`).
- **[3 BẰNG CHỨNG]** `W5/C19/quyet-dinh.md` P-7 (`domain/spatial/model.py:62` hợp đồng khác, không strip); `W5/C19/spec-C19b.md` mục 2.
- **[4 KHOANH VÙNG]** `packages/domain/spatial/model.py`, `packages/domain/spatial/tests/test_model.py`.
- **[5 SỬA NHỎ NHẤT]** Bỏ `_BIDI_CONTROLS`, `_human_text` dùng core `first_forbidden_char` (FIX-234; vẫn từ chối, không trim).
- **[6 TEST CHẶN TÁI PHÁT]** `packages/domain/spatial/tests/test_model.py::test_spatial_model__forbidden_chars_come_from_core_text` — đỏ → xanh.
- **[7 NGHIỆM THU]** `W5/C19/cov3.log` mã thoát 0 (`text.py`, `model.py` 100 % dòng+nhánh); audit docstring không báo hàm thiếu (13 mục trước là tệp ngoài `so_huu` của scope); commit `619fd07`.

## FIX-307 cho B2-04 — khung `Progress` phát bằng `publish` (XADD trần): mất phản hồi sau khi máy chủ đã ghi → thử lại ghi khung thứ hai (NO-187 phần còn lại)

- **[1 TRIỆU CHỨNG]** NO-187 (FIX-243) chỉ bỏ thử lại hết giờ đọc; `ConnectionError` pha đọc phản hồi vẫn thử lại → FE thấy khung trùng.
- **[2 TÁI HIỆN]** `W5/C20/red-b.sh` trên `e980edc`, Redis thật qua proxy cắt phản hồi id sự kiện → `assert 2 == 1`, mã thoát pytest 1 (`W5/C20/red-b.log`).
- **[3 BẰNG CHỨNG]** `apps/api/drawings/runs.py:118` (trước sửa) `bus.publish(...)` — caller `publish` duy nhất còn lại ngoài test.
- **[4 KHOANH VÙNG]** `apps/api/drawings/runs.py`, `apps/api/drawings/tests/test_runs.py`. Không sửa `packages/messaging/streams.py`.
- **[5 SỬA NHỎ NHẤT]** `_publish` dùng `publish_once` (script Lua GET/XADD/SET) với khoá `progress:<upload_id>:<uuid4>` sinh lúc chụp khung (mỗi commit một khoá; lượt thử lại của cùng khung trùng khoá → trả id cũ), TTL `PROGRESS_DEDUPE_TTL_S = 300`. Không đổi dây (cùng nội dung khung, cùng stream).
- **[6 TEST CHẶN TÁI PHÁT]** `test_publish_progress_after_commit__a_lost_reply_publishes_one_frame` — đỏ → xanh.
- **[7 NGHIỆM THU]** Như FIX-245 (`verify-b.log`, `cov-b.log` mã thoát 0); độ phủ `runs.py` 98 % (dòng 166, 188, 229 — nhánh có sẵn, không thuộc thay đổi); commit `901a4d1` (kèm docstring `_snapshot` thiếu sẵn — audit R-01).

## FIX-308 cho B5-01 — `onnx_sha256` YOLO ghim không gắn với bản torch/ultralytics; lock đổi chỉ lộ lúc build ảnh ml (NO-061)

- **[1 TRIỆU CHỨNG]** NO-061: sinh lại `uv.lock` đổi torch/ultralytics/onnx thì `python -m apps.ml.runtime.export_pinned` (build ảnh ml) thoát 2; verify không báo gì.
- **[2 TÁI HIỆN]** Base `bbc8fd6`: `export_yolo` trên `yolov8n.pt` ghim với lock hiện tại (onnx 1.23.0) → SHA = PINNED (onnx không gây lệch); đột biến lock ultralytics 8.4.156 → `test_export.py` 14 passed, thoát 0 (cổng câm) (`W8/C29/tai-hien-NO-061.md`, `cov.log`).
- **[3 BẰNG CHỨNG]** `apps/ml/runtime/export_pinned.py` `export_all` so SHA chỉ sau khi xuất; `apps/ml/runtime/export.py:31-54` `normalize_onnx` trung hoà onnx; `loader.py:161-168` so SHA byte (nên không đổi sang parity).
- **[4 KHOANH VÙNG]** Sửa: `apps/ml/runtime/export_pinned.py`, `apps/ml/runtime/tests/test_export.py` (B5-01). Không sửa: `packages/ml_contracts/pinned.py`, revision B6-01, `uv.lock`.
- **[5 SỬA NHỎ NHẤT]** Hằng `YOLO_EXPORT_TOOLCHAIN = {"torch": "2.14.0+cpu", "ultralytics": "8.4.155"}` (bộ đã đo SHA, docstring ghi quy trình khi đỏ); SHA không đổi → không revision, không đổi hợp đồng.
- **[6 TEST CHẶN TÁI PHÁT]** `test_export_all__yolo_toolchain_matches_lock` — đọc `uv.lock` bằng `tomllib`; lock đột biến → đỏ (thoát 1), lock thật → xanh.
- **[7 NGHIỆM THU]** Commit `0401f11`; `verify --steps 1,2,3,4` đạt (`W8/C29/verify1234.log`, thoát 0); `test_export.py` 15 passed; `export_pinned.py` 100% dòng/nhánh. Bước 5–8 chưa chạy — cổng đầy đủ ở việc gộp.

## FIX-310 cho người điều phối — sổ FIX nhảy FIX-069 → FIX-082 (NO-176)

- **[1 TRIỆU CHỨNG]** NO-176: `docs/fixes.md` không có dòng mục lục, không có khối của FIX-071 … FIX-081 dù các mã đã phát và có commit; `docs/fixes.md:228` trích annotation `down_revision: str | None` mà mẫu mako đã đổi.
- **[2 TÁI HIỆN]** `bash F:/App/AppBack/backend/dieu-phoi/chay/DEBT-02/W8/C32/scan.sh` @ `976b3fa` (worktree tạm) → 22 dòng `ĐỎ NO-176`, mã thoát 1 (`W8/C32/tai-hien-NO-176.md`, `scan-do.txt`).
- **[3 BẰNG CHỨNG]** Người điều phối cấp mã trong phiên B0-09/B2-01/B4-01/B7-01 mà không ghi sổ (FIX.md luật 5); FIX-079 cấp ở `B2-01/bao-cao-m-luot1.md:118` rồi gom vào FIX-073 (`B2-01/spec-m-luot2.md:10`, `950a791` `Fix: FIX-073`).
- **[4 KHOANH VÙNG]** Sửa: `docs/fixes.md`. Cấm: mọi tệp khác.
- **[5 SỬA NHỎ NHẤT]** 11 dòng mục lục sau FIX-070; 10 khối 7 mục (FIX-071…078, 080, 081) + đoạn "không dùng" cho FIX-079, nguồn `W8/C32/fixes-071-081.md` (sha từng mã ở bảng cuối); FIX-071/072 ghi "không gộp"; chú thích FIX-292 `374c7ab` cạnh trích dẫn cũ.
- **[6 TEST CHẶN TÁI PHÁT]** `scan.sh` dòng NO-176 (mục lục + khối từng mã + chú thích mako): đỏ → xanh, mã thoát 0 (`W8/C32/scan-xanh.txt`).
- **[7 NGHIỆM THU]** Commit `c6d25b1` `docs(fixes): rebuild the FIX-071..081 ledger blocks` (`Prompt: DEBT-02`, `Fix: FIX-310`), nhánh chưa gộp. `W8/C32/steps1234.log`: bước 1 `ruff format --check` hỏng ở `deploy/tests/test_nginx.py:242` (ngoài phạm vi cụm), bước 2–4 chưa chạy, mã thoát 1.

## FIX-311 cho B7-02 — năm Nit review của kiểm toán bảo mật; dẫn chiếu `file:dòng` lệch sau DEBT-02 (NO-336)

- **[1 TRIỆU CHỨNG]** NO-336 (review B7-02 lượt 1 #6 + lượt 2 #1, #2): SEC-041 không lý do mức; [4] SEC-060 thiếu tệp test; B-22 `7.1.1` phủ một phần; B-08 dẫn test tham số không id; `README.md:45` ghi `7 %` cho 2/26 = 7,7 %.
- **[2 TÁI HIỆN]** `bash F:/App/AppBack/backend/dieu-phoi/chay/DEBT-02/W8/C32/scan.sh` @ `976b3fa` → 5 dòng `ĐỎ NO-336a…e`, mã thoát 1 (`W8/C32/tai-hien-NO-336.md`). C32b: `ref_drift.py` đỏ 125 dẫn chiếu lệch (`W8/C32/tai-hien-C32b.md`).
- **[3 BẰNG CHỨNG]** `docs/security/fixes/SEC-041.md:2`, `fixes/SEC-060.md:17`, `asvs-checklist.md:50,104`, `README.md:45`; giữ cây cổng 3 nên không sửa lúc review (`docs/reviews/2026-10-02-docs-b7-02-security-audit-round-2.md:26-27`).
- **[4 KHOANH VÙNG]** Sửa: `docs/security/**` (B7-02). Cấm: mọi tệp khác.
- **[5 SỬA NHỎ NHẤT]** Thêm `Lý do mức:`; [4] SEC-060 thêm `deploy/tests/test_nginx.py`; B-22 `7.1.1, 7.1.2` (7.1.2 = dữ liệu nhạy cảm khác); B-08 `…unsafe_names[../evil]` + 6 id (`a\b`, `a\x01b` đúng cách pytest thoát); `8 %` (làm tròn như các dòng khác). C32b: threat-model A-23/D trỏ `WriteScope.forbid_self` `users/service.py:148-157` (FIX-323); 61 dẫn chiếu trỏ lại tự động, 7 sửa tay, 57 giữ số dòng lịch sử ở `2a63cfc` (dòng `lỗ`/SEC, bản ghi thăm dò). Sau gộp tích hợp: áp lại B-22 ASVS 7.1.2 bị mất khi lấy phía tích hợp của các dòng thăm dò W10.
- **[6 TEST CHẶN TÁI PHÁT]** `scan.sh` NO-336a…e đỏ → xanh; `ref_drift.py` đỏ 125 → `ref_check.py` xanh 0.
- **[7 NGHIỆM THU]** Commit `44435a9` `docs(security): fix the five b7-02 review nits`, `55ec55b` `docs(security): repoint file:line evidence after debt-02 changes` (C32b), `c6ec3af` `docs(security): restore B-22 ASVS 7.1.2 lost in the merge` (2026-10-05); `Prompt: B7-02`, `Fix: FIX-311`; nhánh `fix/debt-02-w8-charter-docs`. Sau gộp ở việc gộp `DEBT-02/MF`: `99646c4` `docs(security): mark C-29 and charter debts 3 and 8 fixed` (C-29, "Nợ hiến chương" mục 3/8 → đã sửa FIX-314, FIX-316; nhánh `fix/debt-02-tich-hop`).

## FIX-312 cho dieu-phoi — R-33b theo sở hữu, bốn chỗ hở R-33b/merge-review (NO-232, NO-233) — BẢN NHÁP chờ người dùng duyệt

- **[1 TRIỆU CHỨNG]** NO-232/NO-233: R-33b (2) định nghĩa phạm vi là `apps/<app>/<module>/**`: prompt sở hữu gói luôn rơi vào "đầy đủ"; (7) một chiều; (3) chỉ bắt `.py` mới; `SKILL.md:41` không có ngoại lệ charter; (7) không kiểm được.
- **[2 TÁI HIỆN]** `bash F:/App/AppBack/backend/dieu-phoi/chay/DEBT-02/W8/C32/scan.sh` @ `976b3fa` → 7 dòng `ĐỎ NO-232/NO-233a…d`, mã thoát 1 (`W8/C32/tai-hien-NO-232.md`, `tai-hien-NO-233.md`).
- **[3 BẰNG CHỨNG]** `RULE-CODE.md:68` (viết từ ca B2-05b, `9e37313`); `.claude/skills/merge-review/SKILL.md:41` (`1478543`).
- **[4 KHOANH VÙNG]** Sửa: `RULE-CODE.md`, `.claude/skills/merge-review/SKILL.md`. Cấm: mọi tệp khác.
- **[5 SỬA NHỎ NHẤT]** Câu TRƯỚC/SAU: `W8/C32/ban-nhap-hien-chuong.md` §1–2 (sở hữu = `so_huu` qua `tao_so_tra.py --chu`, sàn cứng thắng, đích chạy test mọi thư mục nhập; (3) mypy/`no_type_check`/cấu hình cấm; (7) hai chiều + nhãn `[thứ tự chạy]`; ngoại lệ charter có trailer `Charter-Approved:`).
- **[6 TEST CHẶN TÁI PHÁT]** `scan.sh` NO-232 (2 kiểm, gồm sàn cứng) + NO-233a…d đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `70eaccf` `docs(repo): scope R-33b by ownership and close its four gaps` (`Prompt: dieu-phoi`, `Fix: FIX-312`), nhánh chưa gộp. Gộp chỉ sau khi người dùng duyệt câu chữ.

## FIX-313 cho người điều phối — nợ hiến chương của B7-02, luật perf vs hạn chờ rộng (NO-335, NO-345) — BẢN NHÁP chờ người dùng duyệt

- **[1 TRIỆU CHỨNG]** NO-335: `docs/security/README.md:244-273` liệt kê 17 chỗ hiến chương thiếu/mơ hồ; NO-345: `BE-00.md:480` bắt `timeout_s=` chờ điều kiện phải `perf` trong khi NO-272 giữ hạn chờ rộng ở bước 5.
- **[2 TÁI HIỆN]** `bash F:/App/AppBack/backend/dieu-phoi/chay/DEBT-02/W8/C32/scan.sh` @ `976b3fa` → 16 dòng `ĐỎ NO-335` (15 cụm BE-00 + CASE N14) + 2 `ĐỎ NO-345`, mã thoát 1 (`W8/C32/tai-hien-NO-335.md`, `tai-hien-NO-345.md`).
- **[3 BẰNG CHỨNG]** Hiến chương viết trước kiểm toán B7-02 và trước khi bước 5 chạy song song; K27 cấm kiểm toán sửa `docs/charter/*`.
- **[4 KHOANH VÙNG]** Sửa: `docs/charter/BE-00.md`, `docs/charter/CASE.md`. Cấm: mọi tệp khác (gồm AppFront `_charter` — điều phối chép sau duyệt).
- **[5 SỬA NHỎ NHẤT]** Mỗi mục một câu: đã sửa ở mã (W4/C16, sha trong `W8/C32/no335-nhap.md`) → câu khẳng định luật; chưa sửa → phương án A + chọn A/B; §12 tách cận trên (`_is_ceiling`) khỏi hạn chờ rộng.
- **[6 TEST CHẶN TÁI PHÁT]** `scan.sh` NO-335 (17 kiểm) + NO-345 (2 kiểm) đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `10364ed` `docs(charter): settle b7-02 charter debts and perf wait rule` (`Prompt: DEBT-02`, `Fix: FIX-313`), nhánh chưa gộp. Gộp chỉ sau duyệt + trailer `Charter-Approved:`; nếu duyệt C11-N14 → FIX B0-01 (`case_gate.py:162-164`) + B1-04 cùng lượt; `age` bắt buộc → FIX B0-10.

## FIX-314 cho B0-08 — nginx giới hạn luồng SSE mỗi IP ở `/api/streams/` (NO-335, phương án B người dùng duyệt 2026-10-05)

- **[1 TRIỆU CHỨNG]** `docs/security/README.md` "Nợ hiến chương" C3: nginx không có `limit_req`/`limit_conn`; một IP mở được hàng trăm luồng SSE giữ worker/pool Redis trước khi app đếm.
- **[2 TÁI HIỆN]** Tĩnh: `deploy/tests/test_nginx.py::test_nginx_streams_location_limits_conn_per_ip` trên cấu hình HEAD → FAILED (`W8/C32/red.log`, thoát 1). Sống: `bash F:/App/AppBack/backend/dieu-phoi/chay/DEBT-02/W8/C32/probe.sh` với `W=<worktree tạm @ HEAD>` (ảnh `appback-web:w10`, api giả giữ luồng) → `PROBE {'200 …': 35}`, thoát 1 (`W8/C32/probe-do.log`).
- **[3 BẰNG CHỨNG]** `deploy/nginx/snippets/app_locations.conf` location `/api/streams/` không có `limit_conn`; không template nào khai `limit_conn_zone`.
- **[4 KHOANH VÙNG]** Sửa: `deploy/nginx/snippets/{streams_conn_zone.conf (mới), app_locations.conf}`, `deploy/nginx/templates/{dev,prod}/app.conf.template`, `deploy/tests/test_nginx.py`. Cấm: `apps/**`, hợp đồng.
- **[5 SỬA NHỎ NHẤT]** `limit_conn_zone $binary_remote_addr zone=appback_streams_ip:1m` mức http; `/api/streams/`: `limit_conn appback_streams_ip 30` (6 luồng/người × ~5 người sau NAT), `limit_conn_status 429`, `error_page 429 /__errors/429` → JSON W7 `RATE_LIMITED` + `Retry-After: 10` + header nền.
- **[6 TEST CHẶN TÁI PHÁT]** Test tĩnh đỏ → xanh; thăm dò sống xanh `PROBE {'200 …': 30, '429 RATE_LIMITED Retry-After=10': 5}`, log nginx `limiting connections by zone "appback_streams_ip"` (`W8/C32/probe-xanh.log`, thoát 0); `pytest tools/tests deploy/tests apps/api/me/tests` 636 passed.
- **[7 NGHIỆM THU]** `fix(deploy): cap concurrent SSE streams per IP in nginx` (`f5eb942`, `Prompt: B0-08`, `Fix: FIX-314`); nhánh `fix/debt-02-w8-charter-docs`, gộp tích hợp ở `fix/debt-02-tich-hop`.

## FIX-315 cho B0-01 — `case_gate` đòi C11 cho N14, tập "case thêm cố định" khoá theo CASE.md (NO-335)

- **[1 TRIỆU CHỨNG]** CASE.md §2.2 (duyệt 2026-10-05) đưa N14 vào C11; `tools/case_gate.py:_FIXED_EXTRA` viết cứng, không có N14 — hai nguồn lệch im lặng.
- **[2 TÁI HIỆN]** `tools/tests/test_case_gate.py::test_fixed_extra_khớp_case_md` trên `case_gate.py` HEAD → FAILED (`W8/C32/red.log`, thoát 1).
- **[3 BẰNG CHỨNG]** `tools/case_gate.py:160-170` dict chép tay từ CASE.md, không test nào đối chiếu.
- **[4 KHOANH VÙNG]** Sửa: `tools/case_gate.py`, `tools/tests/test_case_gate.py`. Cấm: mọi tệp khác.
- **[5 SỬA NHỎ NHẤT]** Thêm `"N14": {"C11"}`; test đọc mục "Case thêm cố định" của CASE.md và đòi bằng đúng `_FIXED_EXTRA` (lệch sau này đỏ ngay).
- **[6 TEST CHẶN TÁI PHÁT]** Đỏ → xanh; `tools/tests` trong 636 passed; `case_gate.py` 98 % (dòng 332/336, nhánh 140/144).
- **[7 NGHIỆM THU]** `fix(tools): require C11 for N14 and pin fixed extras to CASE.md` (`ffb507d`, `Prompt: B0-01`, `Fix: FIX-315`); nhánh `fix/debt-02-w8-charter-docs`, gộp tích hợp ở `fix/debt-02-tich-hop`.

## FIX-316 cho B1-04 — test hạn mức avatar không mang mã C11 (NO-335)

- **[1 TRIỆU CHỨNG]** `test_me_replace_avatar_rate_limited` không có hậu tố `__C11` nên `case_gate` không đếm C11 của N14 (README "Nợ hiến chương" C8).
- **[2 TÁI HIỆN]** Sau FIX-315, N14 đòi C11: không test nào tên `test_me_replace_avatar__C11` → bước 7 sẽ thiếu case; cổng đầy đủ ở việc gộp `DEBT-02/MF`.
- **[3 BẰNG CHỨNG]** `apps/api/me/tests/test_replace_avatar_route.py:130`.
- **[4 KHOANH VÙNG]** Sửa: `apps/api/me/tests/test_replace_avatar_route.py`. Cấm: mọi tệp khác.
- **[5 SỬA NHỎ NHẤT]** Đổi tên → `test_me_replace_avatar__C11` (thân giữ nguyên: 11 lượt → 429 `RATE_LIMITED`); docstring cho `_put` (R-01, audit).
- **[6 TEST CHẶN TÁI PHÁT]** `apps/api/me/tests` trong 636 passed.
- **[7 NGHIỆM THU]** `test(me): name the avatar rate limit test with case C11` (`bab36ff`) + `test(me): document the avatar PUT helper` (`f6d0f68`), `Prompt: B1-04`, `Fix: FIX-316`.

## FIX-317 cho B0-01 — `.importlinter` không hợp đồng nào phủ `apps.api.*.cli` (NO-352)

- **[1 TRIỆU CHỨNG]** NO-352: ranh giới nhập của CLI chỉ được test riêng từng module chặn; chèn `import fastapi` vào `apps/api/library/cli.py` vẫn KEPT.
- **[2 TÁI HIỆN]** Đường thật `lint-imports` (bước 4) trong container verify; bỏ hợp đồng khỏi `.importlinter` → `pytest -k cli_blocked` 1 failed (KeyError `api-cli-no-web`), mã thoát 1 (`W8/C37/run2.log`, `tai-hien-NO-352.md`).
- **[3 BẰNG CHỨNG]** `.importlinter` chỉ có `api-jobs-no-web`, CLI không hợp đồng nào phủ; `W8/C37/quyet-dinh.md` P-1 (bản đầu cấm cả jwt/argon2 sẽ đỏ vì `auth.cli -> passwords -> argon2`).
- **[4 KHOANH VÙNG]** `.importlinter` (B0-01). Hợp đồng FE/DB không đổi.
- **[5 SỬA NHỎ NHẤT]** Hợp đồng `api-cli-no-web` (nguồn `apps.api.*.cli`, cấm fastapi/starlette/uvicorn; argon2 cho phép vì `auth.cli` băm mật khẩu). C37b: bỏ mẫu ignore thừa `tools.**.tests.**` → lint-imports hết cảnh báo "No matches". Sau gộp tích hợp: trả lại ignore `tools.**.tests` trong hợp đồng testing-only.
- **[6 TEST CHẶN TÁI PHÁT]** `test_cli_blocked__equals_importlinter_contract` (đồng bộ hằng) + lint-imports bước 4 (đột biến `import fastapi` vào `library/cli.py` → BROKEN `apps.api.library.cli -> fastapi (l.55)`, thoát 1, `run1.log`).
- **[7 NGHIỆM THU]** Commit `bf8aeab`, `d69af81` (C37b), `7fb6e30` (sửa sau gộp); `lint-imports` 11 kept, 0 broken, mã thoát 0 (`run1.log`); `verify --steps 1,2,3,4` mã thoát 0 (`W8/C37/verify.log`, `verify2.log`). Nợ còn lại: không.

## FIX-318 cho B0-01 — không có hằng chung cho bộ gói bị chặn của test ranh giới nhập (NO-353)

- **[1 TRIỆU CHỨNG]** NO-353: 28 module chép tuple gói bị chặn; nhiều bản thiếu `uvicorn` (NO-240/283).
- **[2 TÁI HIỆN]** Thêm lại một tuple chép vào `apps/api/access/tests/test_boundary.py` (mô phỏng cây chưa sửa) → `pytest -k copy` 1 failed, báo `…access/tests/test_boundary.py:37`, mã thoát 1 (`W8/C37/run2.log`, `tai-hien-NO-353.md`).
- **[3 BẰNG CHỨNG]** Không có hằng chung trong `packages/testing`; ~27 test tự gán tuple (vd `apps/api/access/tests/test_boundary.py:9`, bản thiếu `uvicorn`), thêm 3 bản chép chuỗi nhúng.
- **[4 KHOANH VÙNG]** `packages/testing/boundary.py`, `tools/tests/test_boundary_constants.py` (B0-01). Không đổi hợp đồng. Giữ nguyên bộ riêng (ml_contracts, observability, walls, dimensions, `apps/ml/objects`).
- **[5 SỬA NHỎ NHẤT]** `packages/testing/boundary.py` (`WORKER_BLOCKED`, `CLI_BLOCKED`, `PURE_BLOCKED`); `tools/tests/test_boundary_constants.py` (khớp hợp đồng + quét bản chép, cả chuỗi mã nhúng).
- **[6 TEST CHẶN TÁI PHÁT]** `test_boundary_tests__do_not_copy_blocked_tuple`, `test_worker_blocked__equals_importlinter_contract[×2]`, `test_cli_blocked__…`, `test_pure_blocked__subset_…` — đỏ → xanh (66 passed, mã thoát 0).
- **[7 NGHIỆM THU]** Commit `c3611b3`; `verify --steps 1,2,3,4` mã thoát 0 (`W8/C37/verify.log`); 243 test của các module bị chạm xanh, mã thoát 0 (`run1.log`).

## FIX-319 cho 24 chủ module — test ranh giới từng module đổi sang hằng chung; đợt dọn audit C37b (NO-353)

- **[1 TRIỆU CHỨNG]** NO-353 phía dùng: test ranh giới từng module tự định nghĩa tuple gói bị chặn (xem FIX-318); C37b: audit trên tệp đã chạm báo docstring thiếu, `type: ignore`/`noqa` không lý do, test trùng.
- **[2 TÁI HIỆN]** Xem FIX-318 mục [2] (`W8/C37/tai-hien-NO-353.md`).
- **[3 BẰNG CHỨNG]** Xem FIX-318 mục [3]; danh sách tệp C37b ở `W8/C37/FIX-319.md` và `spec-C37b.md`.
- **[4 KHOANH VÙNG]** Mỗi chủ một commit; chỉ thay định nghĩa tuple bằng `from packages.testing.boundary import …` (3 tệp thêm: notifications, project_members, `messaging/test_worker_main` vì chép dạng chuỗi nhúng). Chủ: B0-05, B0-06, B1-01, B1-02, B1-03, B1-04, B2-01, B2-02, B2-05a, B2-05b, B2-06, B3-01, B3-02, B3-03, B3-04, B3-06, B4-01, B4-02, B5-05, B5-06b, B6-01, B6-02, B6-02b, B6-03a.
- **[5 SỬA NHỎ NHẤT]** Hành vi: bộ chặn của ~20 test thêm `uvicorn` (đúng hợp đồng `.importlinter`). C37b: B1-03 `apps/api/auth_recovery/tests/test_jobs.py` docstring `_TransientMailer`/`send`/`_seed`/2 test lịch, lý do cho `type: ignore[attr-defined]`, bỏ `type: ignore` ở dòng dài bằng `getattr`, ruff format; B1-04 `apps/api/me/tests/test_jobs.py` docstring `_seed_object`, `test_purge_avatars_schedule_is_registered`; B0-06 `apps/api/core/tests/test_extensions.py`, B3-01 `packages/domain/spatial/tests/test_boundary.py` lý do cho `noqa: E402`; B2-06 `apps/api/library/tests/test_jobs_cli.py` xoá `test_blocked_covers_importlinter_jobs_contract` (trùng `test_worker_blocked__equals_importlinter_contract`) và `import configparser`.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_boundary_constants.py::test_boundary_tests__do_not_copy_blocked_tuple` (FIX-318) chặn bản chép mới; 243 test liên quan xanh.
- **[7 NGHIỆM THU]** Commit (33, một chủ mỗi commit): `de8b055`, `abc2242`, `b3c6282`, `38a116f`, `3c10a0f`, `04390f1`, `11abb4a`, `49af5f5`, `5b4c723`, `26680db`, `1840731`, `93e55f9`, `4f22904`, `fa217b2`, `1882c58`, `f88767a`, `da196d3`, `36c4b61`, `1710fbf`, `5445580`, `3425e8d`, `52fd33d`, `948f4e4`, `da3da85`, `835fd73`, `f5cd13f`, `daea0cb`, `0ba7a01`, `50dd55f`, `ad1f704`, `74eb1d3`, `5e17528`, `5210498`; `verify --steps 1,2,3,4` mã thoát 0 (`W8/C37/verify2.log`); `audit.py` đạt trên mọi tệp đã chạm.

## FIX-320 cho B0-01 — `case_gate` cảnh báo ba op hạ tầng không có dòng BE-BIND; so loại xfail bằng chuỗi literal (NO-222)

- **[1 TRIỆU CHỨNG]** NO-222: bước 5b in 3 CẢNH BÁO (`files_read_object`, `health_live`, `health_ready`). C37b: test dựng XML chứa chuỗi `pytest.xfail` (audit coi là skip/xfail).
- **[2 TÁI HIỆN]** Bỏ lọc `INFRA_OPS`: `pytest -k infra` → 3 failed, mã thoát 1 (`W8/C37/run2.log`, `tai-hien-NO-222.md`). Không chạy được `case_gate` thật đầu-cuối (cần junit bước 5); đỏ ở mức hàm `evaluate`.
- **[3 BẰNG CHỨNG]** `tools/case_gate.py` `evaluate()` nhánh `row is None` đẩy mọi op không có dòng BE-BIND vào `unmounted_warnings`.
- **[4 KHOANH VÙNG]** `tools/case_gate.py` + test (B0-01). Không đổi hợp đồng; op lạ khác vẫn cảnh báo (`test_op_mounted_không_có_be_bind_cảnh_báo`).
- **[5 SỬA NHỎ NHẤT]** `INFRA_OPS` trong `tools/case_gate.py`, bỏ qua cảnh báo cho ba op này. C37b: so loại xfail bằng `endswith(".xfail")`, test dựng XML không còn chuỗi `pytest.xfail`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_evaluate__infra_op_without_bind_row_no_warning[files_read_object|health_live|health_ready]`, `test_infra_ops__equal_h1_exempt` — đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `1f86393`, `a7e3019` (C37b); 66 passed, mã thoát 0; `case_gate.py` 98% dòng+nhánh (`run1.log`, dòng thiếu 207, 209, 287, 578 không thuộc diff); `verify --steps 1,2,3,4` mã thoát 0 (`W8/C37/verify.log`, `verify2.log`).

## FIX-321 cho B5-06a — smoke `start` của orchestrate ghi đè `_factory` riêng tư thay vì cổng `override` (NO-304)

- **[1 TRIỆU CHỨNG]** NO-304: helper smoke của `apps/worker/pipeline_orchestrate/tests/test_start_cases.py` monkeypatch `_factory` riêng tư của `ProcessLocal`.
- **[2 TÁI HIỆN]** Không có test đỏ tự nhiên — như FIX-291 (`W7/C27/spec-C27b.md` mục 1, grep `_STORAGE._factory\|\._factory =` trong `apps/**/tests`).
- **[3 BẰNG CHỨNG]** `W7/C27/quyet-dinh.md` P-11; `W7/C27/tai-hien-NO-304.md` ("mẫu dùng chung ở pipeline_orchestrate/persist/quality").
- **[4 KHOANH VÙNG]** `apps/worker/pipeline_orchestrate/tests/test_start_cases.py` (B5-06a), chỉ test.
- **[5 SỬA NHỎ NHẤT]** Helper smoke bọc lượt chạy trong `ProcessLocal.override(...)` của FIX-291 thay cho monkeypatch `_factory` (17 thêm / 22 bớt). B5-06a không có mã FIX trong dải C27 (FIX-280…291) nên cấp mã mới (`fix-cap.md`).
- **[6 TEST CHẶN TÁI PHÁT]** Không có test riêng; cổng `override` được FIX-291 chốt, các bài `test_orchestrate_pipeline_start__*` của tệp chạy qua nó.
- **[7 NGHIỆM THU]** Commit `5599bec` (nhánh `fix/debt-02-w7-test-quality`); bước 1–4 đạt trên `8231b00` (`W7/C27/verify5.log`, mã thoát 0); pytest `test_start_cases.py` cùng 5 tệp khác 142 passed (`last5.log`).

## FIX-322 cho B0-06 — guard W21 không gắn cho route chỉ khai tham số đường qua dependency (NO-351)

- **[1 TRIỆU CHỨNG]** NO-351: `projectId` lệch đường trong thân ở 5 route ghi → 422 `VALIDATION` (Pydantic `extra="forbid"`) thay vì 422 `PATH_BODY_MISMATCH` `field:"projectId"` (W21, BE-00).
- **[2 TÁI HIỆN]** `W9/C40/red.sh` qua `run.sh shell` trên WIP `3ba09f0` (base `262cd80` + test): 5 failed, mã thoát pytest 1 (`W9/C40/red.log`, `tai-hien-NO-351.md`).
- **[3 BẰNG CHỨNG]** `apps/api/core/routing.py:245` (trước sửa) `self.dependant.body_params and self.dependant.path_params` — chỉ tham số endpoint; route nhận `access: ProjectAccess` (`require_project` đọc `request.path_params`) có `path_params == []`. Route thiếu (đo): `measurements_create_record`, `members_add_member`, `settings_replace_settings`, `rules_replace_config`, `templates_create_template`. Dòng nợ ghi 8 route: `versions_restore_version`, `spatial_write_layer` đã có guard (endpoint khai tham số đường khác, guard so mọi `request.path_params`).
- **[4 KHOANH VÙNG]** `apps/api/core/routing.py`, `apps/api/core/tests/{sample.py,test_routing.py}` (B0-06).
- **[5 SỬA NHỎ NHẤT]** Điều kiện W21 dùng `self.param_convertors` (tham số của đường). Dây đổi (người dùng duyệt): 5 route trên, trước 422 `VALIDATION` → sau 422 `PATH_BODY_MISMATCH` `field:"projectId"`. `openapi.json` không đổi (guard không tham số; tham số đường đã khai từ NO-237); `case_gate` không đòi C21 mới (`body_mirrors_path` không đổi).
- **[6 TEST CHẶN TÁI PHÁT]** `test_path_body_guard__path_param_only_in_dependency`, `test_path_body_guard__every_real_write_with_path_params` — đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `ac706aa` (`Prompt: B0-06`, `Fix: FIX-322`); `verify --steps 1,2,3,4` đạt (`W9/C40/verify.log`, mã thoát 0); pytest 1296 passed (`cov.log`); `routing.py` 100%/100%.

## FIX-323 cho B1-05 — `USER_LAST_ADMIN` không phát được qua API (NO-206)

- **[1 TRIỆU CHỨNG]** NO-206: admin `active` duy nhất tự hạ vai/vô hiệu/xoá → 422 `USER_SELF_MODIFICATION`; `USER_LAST_ADMIN` không bao giờ ra dây, nhánh raise chỉ phủ bằng `WriteScope` không thể có (`tests/test_service.py:22-33` cũ).
- **[2 TÁI HIỆN]** `W9/C40/red.sh` trên WIP `3ba09f0`: 3 test API users đỏ (`USER_SELF_MODIFICATION` != `USER_LAST_ADMIN`), mã thoát pytest 1 (`W9/C40/red.log`, `tai-hien-NO-206.md`).
- **[3 BẰNG CHỨNG]** `apps/api/users/service.py:166-171` đòi actor ∈ admins ⇒ |admins|=1 ∧ target ∈ admins ⇒ target = actor; `forbid_self` gọi trước `forbid_last_admin` ở `:294`/`:308`/`:457`. Hợp đồng (`docs/charter`, openapi, AppFront) không ấn định thứ tự; prompt B1-05 [6] đặt `USER_LAST_ADMIN` ở bước 3 khoá tập admin.
- **[4 KHOANH VÙNG]** `apps/api/users/service.py`, `apps/api/users/tests/{test_service,test_state,test_delete}.py` (B1-05). Cấm: `docs/security/threat-model.md` (B7-02) → Nợ (trỏ lại ở FIX-311 C32b).
- **[5 SỬA NHỎ NHẤT]** `WriteScope.forbid_self`: tự sửa mình → `USER_LAST_ADMIN` khi `len(admins)==1`, không thì `USER_SELF_MODIFICATION`; xoá `forbid_last_admin` (chết) + 3 lời gọi. Dây: admin duy nhất tự sửa mình 422 `USER_SELF_MODIFICATION` → 422 `USER_LAST_ADMIN` (kể cả #41 sang vai đang có); còn admin khác giữ nguyên. Không đổi schema.
- **[6 TEST CHẶN TÁI PHÁT]** `test_users_change_role_last_admin_is_rejected`, `test_users_disable_user_twice_and_self`, `test_users_delete_user_last_admin_is_rejected`, `test_forbid_self_reports_last_admin_first` — đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `2d06bc1` (`Prompt: B1-05`, `Fix: FIX-323`); `verify --steps 1,2,3,4` đạt (`W9/C40/verify.log`, mã thoát 0); pytest 1296 passed; `service.py` 100%/100%.

## FIX-324 cho B2-07 — test C03 của #29 kỳ vọng `VALIDATION` cho `projectId` lệch đường (hệ quả FIX-322, NO-351)

- **[1 TRIỆU CHỨNG]** Sau FIX-322 (NO-351), `test_templates_create_template__C03[projectId]` (`projectId:"prj_x"`) nhận `PATH_BODY_MISMATCH`.
- **[2 TÁI HIỆN]** Phản biện vòng 1 chỉ ra (`W9/C40/vong1-phanbien.md`); không chạy riêng bản cũ; suy từ test mới: nhánh lệch ra `PATH_BODY_MISMATCH` (xanh sau FIX-322) ⇒ case cũ kỳ vọng `VALIDATION` phải đỏ.
- **[3 BẰNG CHỨNG]** `apps/api/templates/tests/test_routes.py:214` (trước sửa). Test sai so với hiến chương W21 (BE-00) — FIX luật 2.
- **[4 KHOANH VÙNG]** `apps/api/templates/tests/test_routes.py` (B2-07).
- **[5 SỬA NHỎ NHẤT]** Bỏ case `projectId` khỏi C03; test riêng `test_templates_create_template_project_id_in_body`: lệch → `PATH_BODY_MISMATCH` `field:"projectId"`, trùng → `VALIDATION` (khoá lạ vẫn bị chặn).
- **[6 TEST CHẶN TÁI PHÁT]** `test_templates_create_template_project_id_in_body`.
- **[7 NGHIỆM THU]** Commit `375d924` (`Prompt: B2-07`, `Fix: FIX-324`); pytest templates xanh (trong 1296 passed, `W9/C40/cov.log`).

## FIX-325 cho B1-03 — `sent_at` mang hai nghĩa: đã gửi và `MAIL_REJECTED` (NO-150)

- **[1 TRIỆU CHỨNG]** NO-150: token invite bị SMTP 550 vĩnh viễn có `sent_at` khác NULL → đọc "đã gửi lúc …" sai.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W9/C41/red.sh` (pytest -k J03, dịch vụ thật) trên `262cd80` + test đổi: `assert datetime(2026,1,1,tzinfo=utc) is None` tại `refreshed.sent_at is None`, mã thoát 1 (`W9/C41/tai-hien-NO-150.md`; log đỏ không lưu trong thư mục cụm).
- **[3 BẰNG CHỨNG]** `apps/api/auth_recovery/jobs.py:99` (`_mark_permanent_failure` ghi `sent_at=now` cho `MAIL_REJECTED`); grep: không endpoint nào trả `sent_at`, không đường đọc `sent_at` trong `apps/api/users/**`.
- **[4 KHOANH VÙNG]** Sửa: `packages/db/models/auth_recovery.py`, migration `r20261004_b1_03_fix325`, `apps/api/auth_recovery/jobs.py`, `tests/test_jobs.py` (B1-03). Cấm: `tokens.py` (`active_clause`), `users/**`, hợp đồng.
- **[5 SỬA NHỎ NHẤT]** +`failed_at`, +`failure_code` (CHECK cặp `failed_pair`), `MAIL_REJECTED` ghi cột mới; lọc `failed_at IS NULL` ở `run_send_token_mail` và `run_resend_unsent`; guard WHERE ở hai UPDATE đánh dấu. Dòng cũ không backfill (NULL; vẫn ngoài tập quét). Schema expand đã được spec cụm yêu cầu; không đổi hợp đồng FE.
- **[6 TEST CHẶN TÁI PHÁT]** `test_send_token_mail__J03` (assert đổi: `sent_at is None`, `failed_at`/`failure_code` được ghi, `run_resend_unsent == 0`) — đỏ (mã 1) → xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `df36de5`; `cov.sh` 249 passed (auth_recovery, users, `test_migrate_check`, `test_base`), mã thoát 0; `jobs.py` 99% dòng/18 of 20 nhánh, models 100%; migration chạy qua `test_migrate_check` (up/down). Kết quả `verify --steps 1,2,3,4`: không ghi trong báo cáo cụm.

## FIX-326 cho B1-03 — `latest_invitations` coi lời mời bị từ chối vĩnh viễn là lời mời sống (NO-150)

- **[1 TRIỆU CHỨNG]** Hệ quả NO-150: người `pending` có invite `failed_at` khác NULL vẫn hiện `invitedAt`/`inviteExpiresAt` ("đã mời") trên `GET /api/users`, dù thư chưa tới.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W9/C41/red2.sh` trên `df36de5` + test mới: 2 failed (`test_latest_invitations__excludes_failed`, `test_users_list_users__invite_bounced`), mã thoát 1 (`W9/C41/tai-hien-NO-150.md` phần 2).
- **[3 BẰNG CHỨNG]** `apps/api/auth_recovery/tokens.py:167-183` (không lọc `failed_at`); nơi dùng duy nhất `apps/api/users/service.py:228`.
- **[4 KHOANH VÙNG]** Sửa `tokens.py`, `tests/support.py` (seed `failed_at`), `tests/test_tokens.py` (B1-03); `users/tests/test_read.py` (B1-05, chỉ thêm test). Không đổi service/schema.
- **[5 SỬA NHỎ NHẤT]** Thêm `failed_at IS NULL` vào truy vấn. Không đổi dây: trước/sau cùng khoá `invitedAt`/`inviteExpiresAt` tuỳ chọn; invite hỏng → vắng khoá (như chưa mời), `resend_invitation` không đòi invite cũ nên admin gửi lại được. Không phơi trường mới (tránh đổi openapi).
- **[6 TEST CHẶN TÁI PHÁT]** `test_latest_invitations__excludes_failed`, `test_users_list_users__invite_bounced` — đỏ (mã 1) → xanh (mã 0).
- **[7 NGHIỆM THU]** Commit `6f57c2e`, `1de44b5` (test B1-05), `c2425bc` (docstring, lý do `noqa` ở `test_tokens`); `cov2.sh` 220 passed (auth_recovery, users), mã thoát 0; `tokens.py` 98% (dòng 109 có từ trước). Không đổi schema/openapi → không cần `--steps 8`. Kết quả `verify --steps 1,2,3,4`: không ghi trong báo cáo cụm.

## FIX-327 cho B0-04 — cổng `ObjectStorage` không có API ký URL theo lô, S3 presign chạy trên vòng sự kiện (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `packages/storage/s3.py` `signed_url` gọi `presigned_get_object(...)` đồng bộ ngay trong coroutine → HMAC-SHA256 CPU mỗi URL chạy trên luồng vòng sự kiện; người gọi lặp `await` từng URL (vd #38 của B1-05 với `USERS_LIST_MAX`=1000 ký 1000 URL trong một request).
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W9/C42/red.sh` (s3.py `signed_url` đưa về thân đồng bộ HEAD trong bản chép container): 1 failed `test_s3.py::test_signed_url__presigns_off_the_event_loop`, mã thoát 1 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, P-3 (lô rỗng trên S3 vẫn tốn `to_thread`/`RuntimeError` khi không có `public_client` → `if not requests: return []`), P-5, P-6; đo 1.000 URL (`W9/C42/bench.log`): trước 44,8 ms chặn liên tục vòng sự kiện; sau 64,1 ms tổng trên một luồng, vòng sự kiện stall tối đa 5,5 ms.
- **[4 KHOANH VÙNG]** `packages/storage/{port,s3,local}.py`, `packages/storage/tests/{test_s3,test_contract}.py` (B0-04). Không đổi hợp đồng FE/openapi (URL/`expires_at`/thứ tự giữ).
- **[5 SỬA NHỎ NHẤT]** `SignRequest` + `ObjectStorage.signed_urls`; S3 một `to_thread` cho cả lô, `signed_url` uỷ về lô (một đường); Local lặp `signed_url`. C42b: docstring còn thiếu ở `test_contract.py`, `local.py:59`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_s3.py::test_signed_url__presigns_off_the_event_loop`, `::test_signed_urls__signs_a_whole_batch_in_one_thread`; `test_contract.py::test_signed_urls_match_signed_url_one_by_one`, `::test_signed_urls_reject_inline_non_image` — đỏ → xanh.
- **[7 NGHIỆM THU]** Commit `afda4ad`, `ad0df9d` (C42b, docstring); `cov.sh` 826 passed, mã thoát 0 (`W9/C42/cov2.log`); `verify --steps 1,2,3,4` mã thoát 0 (`verify.log`).

## FIX-328 cho B1-04 — URL ảnh đại diện ký từng cái thay vì một lô (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `apps/api/me/avatar.py:237-247` gọi ký presigned URL đồng bộ, từng URL một.
- **[2 TÁI HIỆN]** Như FIX-327 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, chốt caller `avatar_urls`.
- **[4 KHOANH VÙNG]** `apps/api/me/avatar.py`, `apps/api/me/tests/test_avatar_unit.py` (B1-04). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** Ký URL theo lô qua `ObjectStorage.signed_urls` (một luồng).
- **[6 TEST CHẶN TÁI PHÁT]** `test_avatar_urls__keeps_order_and_none_slots`, `test_avatar_urls__one_signed_urls_call_for_the_whole_batch`.
- **[7 NGHIỆM THU]** Commit `2b29018`; `cov2.log` 826 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-329 cho B1-05 — danh sách người dùng của admin ký ảnh đại diện từng cái (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `apps/api/users/service.py` `admin_views` (#38, tới `USERS_LIST_MAX`=1000) lặp `await` từng URL.
- **[2 TÁI HIỆN]** Như FIX-327 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, chốt caller `user_outs`.
- **[4 KHOANH VÙNG]** `apps/api/users/service.py`, `apps/api/users/tests/test_read.py` (B1-05). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** Ký URL theo lô qua `ObjectStorage.signed_urls` (một luồng).
- **[6 TEST CHẶN TÁI PHÁT]** `test_users_list_users__signs_all_avatars_in_one_batch`.
- **[7 NGHIỆM THU]** Commit `e609547`; `cov2.log` 826 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-330 cho B2-01 — ảnh đại diện thành viên mọi dự án ký từng cái (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `apps/api/projects/service.py::_project_outs` (thành viên mọi dự án) lặp `await` từng URL.
- **[2 TÁI HIỆN]** Như FIX-327 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, chốt caller `avatar_urls`/`user_outs`.
- **[4 KHOANH VÙNG]** `apps/api/projects/service.py`, `wire.py`, `tests/test_service.py`, `tests/test_wire.py` (B2-01). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** Ký URL theo lô qua `ObjectStorage.signed_urls` (một luồng), chia lô đã ký về từng dự án.
- **[6 TEST CHẶN TÁI PHÁT]** `test_project_outs__splits_the_signed_batch_back_per_project`, `test_user_outs_signs_the_whole_batch_in_order`.
- **[7 NGHIỆM THU]** Commit `36cc8c3`; `cov2.log` 826 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-331 cho B2-04 — URL bản vẽ (N7, mọi tầng) ký từng cái (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `apps/api/drawings/latest.py` (N7, limit ≤ 200), `apps/api/drawings/view_parts.py` (mọi tầng) lặp `await` từng URL.
- **[2 TÁI HIỆN]** Như FIX-327 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, P-4 (wrapper `ObjectStorage` ở `drawings/tests/_upload_helpers.py` thiếu `signed_urls` làm mypy hỏng), chốt caller `drawing_urls`.
- **[4 KHOANH VÙNG]** `apps/api/drawings/{drawings,latest,view_parts}.py`, `tests/_upload_helpers.py`, `tests/test_drawings.py` (B2-04). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** `drawing_urls` ký URL theo lô qua `ObjectStorage.signed_urls` (một luồng); wrapper test thêm `signed_urls`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_drawing_urls__mixed_keys_follow_drawing_url_rules_in_order`.
- **[7 NGHIỆM THU]** Commit `91f744f`; `cov2.log` 826 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-332 cho B2-06 — URL mục thư viện ký từng cái, 2 URL/mục (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207: `apps/api/library/service.py::list_items` (2 URL/mục) lặp `await` từng URL.
- **[2 TÁI HIỆN]** Như FIX-327 (`W9/C42/red.log`, `tai-hien-NO-207.md`).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-1, chốt caller `library _to_outs`.
- **[4 KHOANH VÙNG]** `apps/api/library/service.py`, `tests/test_routes.py` (B2-06). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** Ký URL theo lô qua `ObjectStorage.signed_urls` (một luồng).
- **[6 TEST CHẶN TÁI PHÁT]** `test_library_list_items__signs_every_url_in_one_batch`.
- **[7 NGHIỆM THU]** Commit `719a7c0`; `cov2.log` 826 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-333 cho B6-02 — wrapper `ObjectStorage` của test worker datasets thiếu `signed_urls` (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207 hệ quả: wrapper bọc `ObjectStorage` ở `apps/worker/datasets/tests/_helpers.py` phải đủ method mới của cổng, thiếu thì mypy hỏng.
- **[2 TÁI HIỆN]** Không ghi trong báo cáo cụm (lỗi mypy suy ra từ `W9/C42/quyet-dinh.md` P-4).
- **[3 BẰNG CHỨNG]** `W9/C42/quyet-dinh.md` P-4 (worker datasets: điều phối duyệt phương án A).
- **[4 KHOANH VÙNG]** `apps/worker/datasets/tests/_helpers.py` (B6-02). Chỉ test.
- **[5 SỬA NHỎ NHẤT]** Wrapper uỷ `signed_urls` cho kho thật.
- **[6 TEST CHẶN TÁI PHÁT]** Không có test riêng; mypy bước 3 bắt wrapper thiếu method.
- **[7 NGHIỆM THU]** Commit `393c82c`; `verify --steps 1,2,3,4` mã thoát 0 (`W9/C42/verify.log`).

## FIX-334 cho B0-03 — không có seed admin cố định, H2 gửi id admin không có trong DB seed (NO-107)

- **[1 TRIỆU CHỨNG]** NO-107: không có seed người dùng; id admin H2 gửi không có trong DB seed.
- **[2 TÁI HIỆN]** `W9/C43/red.sh` (xoá `users.py` trong bản chép `/tmp/w` rồi pytest) qua `run.sh shell` trên `262cd80`: lỗi thu thập — `packages.db.seeds.users` không tồn tại, mã thoát pytest 2 (`W9/C43/red.log`, `tai-hien-NO-107.md`).
- **[3 BẰNG CHỨNG]** `packages/db/seeds` chỉ có `library.py`, `spatial.py`; H2 dựng admin riêng (ngẫu nhiên) (`W9/C43/tai-hien-NO-107.md`, `red.log`).
- **[4 KHOANH VÙNG]** `packages/db/seeds/users.py`, `packages/db/tests/test_seed_users.py` (B0-03). Hợp đồng/schema không đổi.
- **[5 SỬA NHỎ NHẤT]** `packages/db/seeds/users.py` (ORDER 10, ENVS dev/test/ci, `SEED_ADMIN_ID`, `ON CONFLICT (id) DO NOTHING`).
- **[6 TEST CHẶN TÁI PHÁT]** `packages/db/tests/test_seed_users.py` (4 test, gồm `test_seed__twice_keeps_one_admin` — seed hai lần không nhân bản).
- **[7 NGHIỆM THU]** Commit `9f8813f`, `9db28f2` (ngắt dòng dài), `4a5002a` (rút docstring); `cov.sh` 51 passed, mã thoát 0, `users.py` 100% (`W9/C43/cov.log`); `verify --steps 1,2,3,4` mã thoát 0 (`verify.log`). Nợ còn lại: không.

## FIX-335 cho B0-09 — H2 sinh id admin ngẫu nhiên và dựng tay dòng `users` thay vì dùng seed (NO-107)

- **[1 TRIỆU CHỨNG]** NO-107: H2 sinh `usr_` ngẫu nhiên + `_seed_admin_user` dựng tay — hai nguồn admin.
- **[2 TÁI HIỆN]** Cùng lượt `W9/C43/red.sh`: `h2._admin_header()` trên cây base TypeError (cần 1 đối số), `ERROR tools/ci/tests/test_h2.py`, mã thoát pytest 2 (`W9/C43/red.log`).
- **[3 BẰNG CHỨNG]** `tools/ci/h2.py` `main()` sinh `new_id("usr")` rồi `_seed_admin_user` chèn dòng `users` (NO-132) — không dùng seed (`W9/C43/tai-hien-NO-107.md`).
- **[4 KHOANH VÙNG]** `tools/ci/h2.py`, `tools/ci/tests/test_h2.py` (B0-09). Hợp đồng/schema không đổi.
- **[5 SỬA NHỎ NHẤT]** Bỏ `_seed_admin_user`/tham số `admin_id`; `_admin_header()` dùng `SEED_ADMIN_ID`; `_seed` chỉ `apply_seeds`.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/ci/tests/test_h2.py::test_admin_header__uses_seed_admin_id`, `::test_admin_header__id_exists_after_seeding`.
- **[7 NGHIỆM THU]** Commit `1400c01`, `d7958c5` (rút docstring); `cov.sh` 51 passed, mã thoát 0, `h2.py` 99% (dòng 376 vốn không phủ từ trước); `verify --steps 1,2,3,4` mã thoát 0 (`W9/C43/verify.log`). Nợ còn lại: không.

## FIX-336 cho B2-07 — tham số `unknown-kind` của C02 còn mong không có `field` sau khi NO-248 bỏ tag nhánh union (NO-248)

- **[1 TRIỆU CHỨNG]** Cổng tích hợp `262cd80` đỏ bước 5: `apps/api/templates/tests/test_routes.py::test_templates_create_template__C02[unknown-kind]` (2 failed / 8338 passed).
- **[2 TÁI HIỆN]** `tich-hop-gate-1.log` dòng 236–281, 498–500 (cổng đầy đủ trên `262cd80`).
- **[3 BẰNG CHỨNG]** NO-248 (W5/C20, "field_of bỏ tag nhánh") đổi hành vi: `objectKind` lạ nay trả `field = "objectKind"`, đường trường union không còn tiền tố; test vẫn khẳng định `"field" not in out` (`W9/C46/spec.md` mục 1, `timeline.md` 15:31Z).
- **[4 KHOANH VÙNG]** `apps/api/templates/tests/test_routes.py` (B2-07), chỉ test; mã sản phẩm đúng.
- **[5 SỬA NHỎ NHẤT]** Tham số `template_body("door")` mong `"objectKind"`; bỏ nhánh `field is None`, assert `out["field"].endswith(field)`; chú thích dòng ~206 viết lại theo NO-248.
- **[6 TEST CHẶN TÁI PHÁT]** `test_templates_create_template__C02[unknown-kind]` chính nó (đỏ ở cổng 1 → xanh).
- **[7 NGHIỆM THU]** Commit `60ef453` (nhánh `fix/debt-02-w9-integ-fix`); cổng tích hợp `7ae1292` bước 5 8365 passed, mã thoát 0 (`tich-hop-gate-2.log`). Mã thoát kiểm riêng của C46 không ghi trong báo cáo cụm (thư mục `W9/C46` chỉ có `spec.md`).

## FIX-337 cho B2-05b — `read_view` ký URL từng tầng thay vì một lô (NO-207)

- **[1 TRIỆU CHỨNG]** NO-207 (caller sót, ngoài whitelist lượt đầu): `apps/api/quality/assessments.py:276` còn `[await drawing_url(...) for row in rows]`.
- **[2 TÁI HIỆN]** `bash tools/verify/run.sh shell < W9/C42/red2.sh`: `test_read_view__signs_every_floor_in_one_batch` 1 failed, mã thoát 1 (`W9/C42/red2.log`).
- **[3 BẰNG CHỨNG]** `apps/api/quality/assessments.py:276`; `W9/C42/quyet-dinh.md` P-2 (grep `drawing_url(`), `spec-C42b.md` mục 1.
- **[4 KHOANH VÙNG]** `apps/api/quality/assessments.py`, `apps/api/quality/tests/test_read_view.py` (B2-05b). Không đổi hợp đồng.
- **[5 SỬA NHỎ NHẤT]** `read_view` ký URL mọi tầng qua `drawing_urls` (một lô).
- **[6 TEST CHẶN TÁI PHÁT]** `test_read_view__signs_every_floor_in_one_batch` đỏ (mã 1) → xanh.
- **[7 NGHIỆM THU]** Commit `4614a52`; `W9/C42/green2.log` 341 passed, mã thoát 0; `verify --steps 1,2,3,4` mã thoát 0 (`verify2.log`).

## FIX-338 cho B7-02 — `docs/security` còn 18 mục `chưa kiểm` và dòng "kiểm toán chưa đủ" (NO-334)

- **[1 TRIỆU CHỨNG]** NO-334: 18 mục checklist `chưa kiểm` (nhóm Giấy phép 100 %) chỉ chứng minh được qua `prod.yml` sống; `docs/security/README.md` mang dòng "kiểm toán chưa đủ".
- **[2 TÁI HIỆN]** Dựng ảnh `appback-{api,worker,web,ml}:w10` (`W10/C47/build.log`), chạy stack `prod.yml` cục bộ (`APP_ENV=production`, cert tự ký), thăm dò từng mục (`W10/C47/probe.log`, log thô L-01…L-09).
- **[3 BẰNG CHỨNG]** `probe.log`: 16 mục đạt, C-18 và D-25 là lỗ (SEC-044, SEC-063) vá cùng lượt bằng FIX-339, FIX-343; B-22 đạt kèm tồn dư `__main__:70` → FIX-344/345 (C47b).
- **[4 KHOANH VÙNG]** `docs/security/{README.md,asvs-checklist.md,threat-model.md,fixes/SEC-044.md,fixes/SEC-063.md}` (B7-02), chỉ tài liệu.
- **[5 SỬA NHỎ NHẤT]** Đổi trạng thái 18 mục theo bằng chứng, thêm SEC-044/SEC-063, bỏ dòng "kiểm toán chưa đủ" (`5bb71c8`); đóng tồn dư B-22 bằng FIX-344/345 (`e2a9bb9`).
- **[6 TEST CHẶN TÁI PHÁT]** Không có (tài liệu); mỗi mục trỏ lệnh thăm dò trong `probe.log`.
- **[7 NGHIỆM THU]** Commit `5bb71c8`, `e2a9bb9` (nhánh `fix/debt-02-w10-security-probe`); bước 1–4 đạt trên `5bb71c8` (`verify-1234.log`) và `e2a9bb9` (`c47b-verify-1234.log`), mã thoát 0.

## FIX-339 cho B0-10 — `backup.sh` ghi bản sao lưu rõ khi production thiếu `BACKUP_AGE_RECIPIENT` (NO-334)

- **[1 TRIỆU CHỨNG]** Mục C-18: `APP_ENV=production BACKUP_AGE_RECIPIENT='' backup.sh` thoát 0, ghi `db.dump` rõ (đầu tệp `PGDMP`), manifest `"encrypted": false` (SEC-044).
- **[2 TÁI HIỆN]** Thăm dò thật trên cây `d4ec769` (`W10/C47/backup-red.log`, rc=0); test `deploy/backup/tests/test_backup.py::test_backup__production_without_age_recipient_exits_1_before_dump` đỏ: 1 failed, 10 passed (`c18-red.log`).
- **[3 BẰNG CHỨNG]** `probe.log` mục C-18 [L-05]; nhánh có `age` thật mã hoá đúng, khoá sai thoát 1, `restore.sh` thiếu identity thoát 2 (`backup-red.log`).
- **[4 KHOANH VÙNG]** `deploy/backup/backup.sh`, `deploy/backup/tests/test_backup.py`, `deploy/scripts/README.md` (B0-10).
- **[5 SỬA NHỎ NHẤT]** `APP_ENV=production` mà `BACKUP_AGE_RECIPIENT` rỗng → thoát 1 trước `pg_dump`; README cập nhật.
- **[6 TEST CHẶN TÁI PHÁT]** `test_backup__production_without_age_recipient_exits_1_before_dump` đỏ → xanh (`pytest deploy` 283 passed, `c18-green.log`).
- **[7 NGHIỆM THU]** Commit `8aaf38f` (nhánh `fix/debt-02-w10-security-probe`); thăm dò lại rc=1, không tạo thư mục sao lưu (`probe.log` C-18); `pytest deploy` cuối 466 passed, mã thoát 0 (`pytest-deploy-final.log`). Mã thoát của `c18-red.log`/`c18-green.log` không ghi trong báo cáo cụm.

## FIX-340 cho B0-08 — `ml.Dockerfile` thiếu `COPY packages/observability`, ảnh ml không dựng được (NO-334)

- **[1 TRIỆU CHỨNG]** Lượt dựng ảnh của thăm dò NO-334: `docker build -f deploy/docker/ml.Dockerfile` rc=1 (cả `--network none` lẫn có mạng), `ModuleNotFoundError` `packages.observability` ở `export_pinned` tầng deps (`W10/C47/build.log`).
- **[2 TÁI HIỆN]** `build.log` hai lượt rc=1 trên cây `7ae1292`; test mới `deploy/tests/test_dockerfiles.py::test_dockerfile_copied_code_is_import_closed[ml]` đỏ: "thiếu COPY packages/observability (từ packages/messaging/celery_app.py)", 1 failed / 39 passed (`ml-red.log`).
- **[3 BẰNG CHỨNG]** `packages.messaging` nhập `packages.observability.exporter` mà `ml.Dockerfile` chỉ chép `messaging` (thân commit `486cd80`); `probe.log` mục "Ngoài 18 mục".
- **[4 KHOANH VÙNG]** `deploy/docker/ml.Dockerfile`, `deploy/tests/test_dockerfiles.py` (B0-08). Không có dòng nợ riêng — lỗi lộ ra khi chạy thật lượt NO-334.
- **[5 SỬA NHỎ NHẤT]** Thêm `COPY packages/observability` vào tầng cần; test tĩnh kiểm mọi tầng ảnh python chép một tập `packages/apps` khép kín theo import.
- **[6 TEST CHẶN TÁI PHÁT]** `test_dockerfile_copied_code_is_import_closed[*]` đỏ → xanh (40 passed, `ml-green.log`).
- **[7 NGHIỆM THU]** Commit `486cd80` (nhánh `fix/debt-02-w10-security-probe`); build ml lại rc=0, 162 s (`build.log`); `pytest deploy` 466 passed, mã thoát 0 (`pytest-deploy-final.log`).

## FIX-341 cho B0-10 — `drill.sh` `snapshot()` mất stdin vào `docker compose exec -T`, diễn tập chỉ so một bảng/một đối tượng (NO-334)

- **[1 TRIỆU CHỨNG]** Diễn tập kho `local` (việc chờ của W5/C17) chạy thật trong lượt NO-334 báo "diễn tập khớp cả hai pha", mã thoát 0, nhưng bảng so chỉ có 1 bảng + 1 đối tượng — xanh giả (`W10/C47/drill-local-truoc-FIX341.log`, cây `486cd80`).
- **[2 TÁI HIỆN]** Test mới `deploy/scripts/tests/test_drill.py::test_drill_snapshot_lists_every_table_and_object__w10` đỏ: `['alpha\t7'] == ['alpha\t7', 'beta\t7', 'gamma\t7']`, 1 failed / 3 passed (`drill-red.log`).
- **[3 BẰNG CHỨNG]** `docker compose exec -T` trong `while read … <<< "$list"` hút stdin của vòng lặp (thân commit `554bbca`); `probe.log` mục "Ngoài 18 mục".
- **[4 KHOANH VÙNG]** `deploy/scripts/drill.sh`, `deploy/scripts/tests/test_drill.py` (B0-10). Không có dòng nợ riêng.
- **[5 SỬA NHỎ NHẤT]** Hai vòng `snapshot()` đọc danh sách từ fd 3 thay cho stdin.
- **[6 TEST CHẶN TÁI PHÁT]** `test_drill_snapshot_lists_every_table_and_object__w10` đỏ → xanh (4 passed, `drill-green.log`).
- **[7 NGHIỆM THU]** Commit `554bbca` (nhánh `fix/debt-02-w10-security-probe`); diễn tập local lại trên `554bbca`: đủ bảng/đối tượng đều "có", "mã thoát drill: 0" (`drill-local.log`); `pytest deploy` 466 passed, mã thoát 0 (`pytest-deploy-final.log`).

## FIX-343 cho B6-02b — giấy phép CC BY-NC 4.0 của CubiCasa5K không được ghi ở đâu trong mã (NO-334)

- **[1 TRIỆU CHỨNG]** Mục D-25: `grep -rniE "licen|cc[ -]by" apps/worker/datasets_cubicasa apps/api/admin_ml_datasets` trên `7ae1292` rỗng; manifest, bản ghi dataset không có giấy phép (SEC-063).
- **[2 TÁI HIỆN]** `W10/C47/probe-code.log` mục D-25: bỏ dòng in license → `test_import_prints_report_and_exits_zero` đỏ, `exit=1`; mã thật → xanh, `exit=0`.
- **[3 BẰNG CHỨNG]** `probe-code.log` dòng 139–150; `probe.log` mục D-25 [L-08].
- **[4 KHOANH VÙNG]** `apps/worker/datasets_cubicasa/{importer.py,cli.py,tests/test_cli.py}` (B6-02b); không đổi schema, không migration.
- **[5 SỬA NHỎ NHẤT]** Hằng `SOURCE_LICENSE` cạnh `SOURCE` trong importer; `cli.py` in dòng `license: …` ở mọi báo cáo nhập.
- **[6 TEST CHẶN TÁI PHÁT]** `apps/worker/datasets_cubicasa/tests/test_cli.py::test_import_prints_report_and_exits_zero` khẳng định `license: CC-BY-NC-4.0 `.
- **[7 NGHIỆM THU]** Commit `d4ec769` (nhánh `fix/debt-02-w10-security-probe`); bước 1–4 đạt trên `d4ec769`, mã thoát 0 (`verify-code-1234.log`).

## FIX-344 cho B0-02 — bộ che log chung không che dạng `KEY=value` / `KEY: value` trong chuỗi tự do (NO-334)

- **[1 TRIỆU CHỨNG]** Tồn dư B-22 của thăm dò NO-334: `S3_SECRET_KEY=…`, `password=…` trong thông điệp ngoại lệ (pydantic lặp đầu vào) vào log nguyên văn; bộ che chỉ biết JWT, Bearer, token trên query, mật khẩu trong URL.
- **[2 TÁI HIỆN]** Test mới đỏ: `test_mask_key_value_in_free_text[*]` (5 tham số) và `test_mask_masks_secret_suffix_keys[S3_SECRET_KEY|SECRET_KEY|SMTP_PASSWORD|MINIO_ROOT_PASSWORD|claim_token]` — 11 failed / 1 passed cùng FIX-345 (`W10/C47/c47b-red.log`).
- **[3 BẰNG CHỨNG]** `probe.log` mục B-22 (tồn dư); `W10/C47/spec-C47b.md`.
- **[4 KHOANH VÙNG]** `packages/core/logging.py`, `packages/core/tests/test_logging.py` (B0-02) — hàm che chung mọi đường log đi qua (R-19).
- **[5 SỬA NHỎ NHẤT]** Một vị từ `_is_masked_key` phục vụ cả khoá dict lẫn cặp `KEY=`/`KEY:` trong chuỗi, nhận hậu tố bí mật (`…_SECRET_KEY`, `…_PASSWORD`, `…_token`); thêm `install_log_handler` cho tiến trình không có `CoreSettings`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_mask_key_value_in_free_text[*]`, `test_mask_masks_secret_suffix_keys[*]` đỏ → xanh (`pytest packages/core apps/ml/training_runner` 471 passed, `c47b-green.log`).
- **[7 NGHIỆM THU]** Commit `bdff809` (nhánh `fix/debt-02-w10-security-probe`); bước 1–4 đạt trên `e2a9bb9`, mã thoát 0 (`c47b-verify-1234.log`).

## FIX-345 cho B6-03b — crash của `training_runner` in traceback thô qua `logging.lastResort`, lộ bí mật trong thông điệp ngoại lệ (NO-334)

- **[1 TRIỆU CHỨNG]** Tồn dư B-22: tiến trình con huấn luyện không cấu hình logging, nên trình bắt crash cuối (`apps/ml/training_runner/__main__.py:70`) đi qua `logging.lastResort`, in nguyên traceback kèm giá trị bí mật.
- **[2 TÁI HIỆN]** `apps/ml/training_runner/tests/test_runner.py::test_main_crash_log_masks_secret_values` đỏ (`W10/C47/c47b-red.log`).
- **[3 BẰNG CHỨNG]** `probe.log` mục B-22 ("tồn dư: stack máy chủ __main__:70 in thông điệp ngoại lệ"); `spec-C47b.md`.
- **[4 KHOANH VÙNG]** `apps/ml/training_runner/__main__.py`, `apps/ml/training_runner/tests/test_runner.py` (B6-03b).
- **[5 SỬA NHỎ NHẤT]** `main()` cài bộ xử lý JSON đã che (`install_log_handler` của FIX-344); bản ghi crash giữ `excType` và mã `INTERNAL`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_main_crash_log_masks_secret_values` đỏ → xanh (`c47b-green.log`, 471 passed).
- **[7 NGHIỆM THU]** Commit `5f7624d` (nhánh `fix/debt-02-w10-security-probe`); bước 1–4 đạt trên `e2a9bb9`, mã thoát 0 (`c47b-verify-1234.log`).

## FIX-346 cho F-01b — lượt e2e lạnh đầu tiên đỏ `page.goto` hết 30 s vì máy chủ dev Vite chưa biên dịch xong (NO-208)

- **[1 TRIỆU CHỨNG]** Khi đo NO-208, lượt `pnpm e2e e2e/viewer3d.spec.ts` lạnh đầu tiên (không `node_modules/.vite`) đỏ 6 bài `page.goto` hết 30 s; bài về sau xanh.
- **[2 TÁI HIỆN]** `W10/C45/tai-hien-C45b-e2e-lanh.md`: trước sửa — NO-208 lượt 1 6 đỏ / 36, EXIT=1; lạnh #1 6 đỏ / 8, EXIT=1; lạnh + đốt 12 lõi `--repeat-each=2` 12 đỏ và 14 đỏ / 28, EXIT=1.
- **[3 BẰNG CHỨNG]** `run-playwright.mjs` chỉ chờ Vite trả `/`; đợt `page.goto` song song đầu gánh cả lượt tối ưu phụ thuộc lẫn biên dịch cây module; tiến trình Vite thứ hai (cache phụ thuộc có sẵn) xanh 42/42 (`tai-hien-C45b-e2e-lanh.md` mục "Gốc").
- **[4 KHOANH VÙNG]** AppFront `scripts/run-playwright.mjs`, `scripts/warm-dev-server.mjs` (mới), `scripts/__tests__/warm-dev-server.test.mjs`.
- **[5 SỬA NHỎ NHẤT]** Sau `waitForServer`, đi theo đồ thị module từ `/@vite/client` + `/src/main.tsx` (kể cả `import()` lười của route) tới khi một lượt trọn không gặp 5xx và tập URL đứng yên; trần `WARM_UP_TIMEOUT_MS = 180 000`, quá trần dừng. Không nâng timeout, không retry, không seed tour.
- **[6 TEST CHẶN TÁI PHÁT]** `scripts/__tests__/warm-dev-server.test.mjs` (bộ tách import, chạy trong `pnpm verify`); đo lạnh sau sửa 14/14 ×2 và 28/28 ×2 dưới tải 12 lõi, EXIT=0, làm ấm 21,4–85,3 s (891 module, 2 lượt).
- **[7 NGHIỆM THU]** Commit `f5332dc7` (AppFront, nhánh `fix/debt-02-w10-fe`); `pnpm verify` 7 bước đạt, `VERIFY_EXIT=0` (`W10/C45/verify-C45b.log`).

## FIX-348 cho F-01b — luồng tiến độ xử lý không xin refresh khi cookie luồng cũ nhận 401, SSE nối lại thất bại mãi (NO-154)

- **[1 TRIỆU CHỨNG]** NO-154: sau `bump_token_version`, cookie `appback_stream` cũ nhận 401 ở `GET /api/streams/*`; `EventSource` không đọc được status. Màn thông báo đã truyền `refreshAuth`, còn `createProgressStream` (`processingGateway.ts`) thì không — rơi về poll và thử SSE lại mỗi 60 s, mãi.
- **[2 TÁI HIỆN]** Hai test mới ở `src/lib/realtime/__tests__/progressStream.test.ts` trên mã chưa sửa: 2 failed / 4 passed ("expected spy to be called once, but got 0 times"), EXIT=1 (`W10/C45/tai-hien-NO-154.md`).
- **[3 BẰNG CHỨNG]** `progressStream` dựng kênh mới mỗi `SSE_RETRY_INTERVAL_MS`, nên chốt theo kênh thành 1 POST/60 s (R2-2 review DEBT-01 lượt 2: 29 POST/30 phút) — chốt phải sống ở luồng (`tai-hien-NO-154.md`).
- **[4 KHOANH VÙNG]** AppFront `src/lib/realtime/progressStream.ts`, `src/screens/pipeline/ProcessingScreen/processingGateway.ts`.
- **[5 SỬA NHỎ NHẤT]** Tuỳ chọn `refreshAuth`, chốt `refreshedSinceOpen` ở luồng (mở lại khi kênh `da-noi`): đủ `SSE_FAILURE_LIMIT` → poll + refresh một lần; refresh `true` mà còn poll → `startSse()` ngay. Gateway truyền `refreshSingleFlight({ source: 'local' })` như màn thông báo.
- **[6 TEST CHẶN TÁI PHÁT]** `refreshes auth once per dead SSE run and retries SSE right after a good refresh`, `keeps polling and waits the normal SSE retry when refresh fails` — đỏ → xanh (6 passed, EXIT=0).
- **[7 NGHIỆM THU]** Commit `9ce307a6` (AppFront, nhánh `fix/debt-02-w10-fe`); vitest `src/lib/realtime src/screens/pipeline` 276 passed, `tsc`/`eslint` EXIT=0 (`tai-hien-NO-154.md`); `pnpm verify` 7 bước đạt, `VERIFY_EXIT=0` (`W10/C45/verify.log`). Chưa thử với BE thật — chỉ test đơn vị.

## FIX-349 cho F-01b — `expiresIn` của thân refresh dựng trên đồng hồ cục bộ, lịch hẹn trên đồng hồ máy chủ (NO-209)

- **[1 TRIỆU CHỨNG]** NO-209: với đồng hồ máy khách nhanh 9 phút, quãng đời token đọc dài thêm 9 phút, lượt gia hạn tới sau khi token chết.
- **[2 TÁI HIỆN]** Test mới `src/lib/auth/__tests__/refresh.test.ts` › `reads expiresIn against the server clock too` trên mã chưa sửa: `expect(calls).toHaveLength(2)` nhận 1, EXIT=1 (`W10/C45/tai-hien-NO-209.md`).
- **[3 BẰNG CHỨNG]** Bản chưa sửa đọc quãng đời 600 + 540 = 1 140 s → hẹn gia hạn ở giây 1 080, sau lúc token chết (600) (`tai-hien-NO-209.md`).
- **[4 KHOANH VÙNG]** AppFront `src/lib/auth/refresh.ts`, `src/lib/auth/types.ts`.
- **[5 SỬA NHỎ NHẤT]** `readRefreshPayload` đưa `now = config.now() + serverOffsetMs` cho bộ đọc — cùng gốc với `remainingMs`; nhánh `expiresAt` không đổi; docblock `parseRefreshResponse` ghi `now` là giờ máy chủ.
- **[6 TEST CHẶN TÁI PHÁT]** `reads expiresIn against the server clock too` đỏ → xanh (1 passed, EXIT=0).
- **[7 NGHIỆM THU]** Commit `09bffa11` (AppFront, nhánh `fix/debt-02-w10-fe`); vitest `src/lib/auth` 54 passed, EXIT=0 (`tai-hien-NO-209.md`); `pnpm verify` 7 bước đạt, `VERIFY_EXIT=0` (`W10/C45/verify.log`).

## FIX-350 cho B0-01 — mặc định `-n` của bước 5 và docstring `pytest_workers()` dựa trên số đo đã hết hiệu lực (NO-271, NO-280)

- **[1 TRIỆU CHỨNG]** NO-271: chưa tách RAM container dịch vụ khỏi RAM tiến trình pytest nạp `torch` (ước tính FIX-112 là khoảng); NO-280: chưa đo `-n 8` sau FIX-114, docstring `tools/verify/steps.py::pytest_workers()` nêu lý do trần 6 đã hết hiệu lực.
- **[2 TÁI HIỆN]** Đo bước 5 một mình, `VERIFY_PYTEST_WORKERS=4/6/8`, 8383 test, lấy mẫu `docker stats` + PSS mỗi ~15 s (`W10/C48/sample.sh`, `run-n.sh`, `n{4,6,8}.log`, `sample-n{4,6,8}.csv`); cả ba lượt mã thoát 0.
- **[3 BẰNG CHỨNG]** `W10/C48/ram.md`: `-n 4` 571,0 s (đỉnh VM 8,67 GiB) · `-n 6` 504,5 s (8,47 GiB) · `-n 8` 513,4 s (10,14 GiB), không đỏ/chập chờn; ~10 container dịch vụ chỉ ~0,5 GiB, RAM tăng theo N là tiến trình pytest nạp `torch` (~2 GiB PSS đỉnh mỗi tiến trình).
- **[4 KHOANH VÙNG]** `tools/verify/steps.py`, `tools/tests/test_steps_commands.py` (B0-01). ENV.md §4 chỉ soạn nháp (`W10/C48/ban-nhap-env.md`).
- **[5 SỬA NHỎ NHẤT]** Giữ mặc định 6 (nhanh nhất, `-n 8` không nhanh hơn mà chỉ chừa ~1,4 GiB VM); docstring nêu số đo mới thay lý do cũ; test mặc định khẳng định `"6"`. `a681354`, `4870259` sửa dòng docstring cho ruff. Trailer commit ghi `Prompt: DEBT-02-W10-C48` thay vì chủ B0-01; `DEBT.md`, `changes/FIX-350.md` worker tự sửa bị bỏ khi gộp (`timeline.md` 18:30Z).
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_steps_commands.py::test_số_tiến_trình_bước_5_mặc_định`.
- **[7 NGHIỆM THU]** Commit `cf542eb`, `a681354`, `4870259` (nhánh `fix/debt-02-w10-gate-measure`); bước 1–4 đạt trên `4870259`, mã thoát 0 (`W10/C48/steps1234.log`); pytest `tools/tests/test_steps*.py` 94 passed, exit 0 (`pytest-steps.log`).

## FIX-351 cho B0-10 — backup.sh ghi bản rõ ở staging/APP_ENV rỗng (review R1 F4, F21)

- **[1 TRIỆU CHỨNG]** F4: staging hoặc APP_ENV rỗng thiếu BACKUP_AGE_RECIPIENT vẫn rc 0, bản rõ.
- **[2 TÁI HIỆN]** bash backup.sh với APP_ENV=staging, không recipient (`R/RA/tai-hien-F4.md`)
- **[3 BẰNG CHỨNG]** docs/reviews/2026-10-05-fix-debt-02-tich-hop.md F4; backup.sh:87-90
- **[4 KHOANH VÙNG]** deploy/backup/**, deploy/scripts/{drill.sh,README.md,tests/test_drill.py} · cấm sửa: tệp prompt khác, DEBT.md, docs/fixes.md, changes/*
- **[5 SỬA NHỎ NHẤT]** Chặn mọi env trừ BACKUP_ALLOW_PLAINTEXT=1; drill.sh tự đặt cờ khi thiếu age; README + đổi tên 2 test drill (F21).
- **[6 TEST CHẶN TÁI PHÁT]** test_backup__any_env_without_age_recipient_exits_1_before_dump[staging|dev|rỗng], …plaintext_opt_out_runs_without_recipient, …value_must_be_exactly_1
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 + cov.sh (xem `R/RA/cov.log`); test đỏ→xanh trong tai-hien-*.md; commit fix(B0-10)… + Prompt/Fix. Commit `19e6dd5`, `2d1184d`, `21a1a1d` (nhánh `fix/debt-02-r1-deploy-tools`).

## FIX-352 cho B0-08 — env.example thiếu hai biến sao lưu; test map nginx lỏng (review R1 F4, F12)

- **[1 TRIỆU CHỨNG]** F4 (env.example) + F12: không khai BACKUP_*; test NO-197 không kiểm map.
- **[2 TÁI HIỆN]** `R/RA/tai-hien-rest.md` (F12)
- **[3 BẰNG CHỨNG]** docs/reviews/2026-10-05-fix-debt-02-tich-hop.md F4, F12; deploy/tests/test_nginx.py:576
- **[4 KHOANH VÙNG]** deploy/compose/env.example, deploy/tests/test_nginx.py · cấm sửa: tệp prompt khác, DEBT.md, docs/fixes.md, changes/*
- **[5 SỬA NHỎ NHẤT]** Khai BACKUP_AGE_RECIPIENT/BACKUP_ALLOW_PLAINTEXT; assert cấu trúc map.
- **[6 TEST CHẶN TÁI PHÁT]** test_nginx_access_log_map_logs_by_default_and_drops_files_uris
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 + cov.sh (xem `R/RA/cov.log`); test đỏ→xanh trong tai-hien-*.md; commit fix(B0-08)… + Prompt/Fix. Commit `6aecb51`, `a51986a`, `9960254` (nhánh `fix/debt-02-r1-deploy-tools`).

## FIX-353 cho B0-01 — case_gate nới xfail; coverage_gate in 100% giả (review R1 F7, F24)

- **[1 TRIỆU CHỨNG]** F7: endswith('.xfail') + test né grep; F24: đơn vị 0 câu lệnh in 100%.
- **[2 TÁI HIỆN]** `R/RA/tai-hien-rest.md`
- **[3 BẰNG CHỨNG]** docs/reviews/2026-10-05-fix-debt-02-tich-hop.md F7, F24; case_gate.py:262, coverage_gate.py:291
- **[4 KHOANH VÙNG]** tools/case_gate.py, tools/coverage_gate.py, tools/tests/test_{case,coverage}_gate.py · cấm sửa: tệp prompt khác, DEBT.md, docs/fixes.md, changes/*
- **[5 SỬA NHỎ NHẤT]** Hoàn == 'pytest.xfail'; bỏ dòng khi num_statements == 0.
- **[6 TEST CHẶN TÁI PHÁT]** test_parse_junit_skipped_xfail (thêm ca other.xfail), test_đơn_vị_không_câu_lệnh_không_in_số_đo
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 + cov.sh (xem `R/RA/cov.log`); test đỏ→xanh trong tai-hien-*.md; commit fix(B0-01)… + Prompt/Fix. Commit `debb053`, `39cec55` (nhánh `fix/debt-02-r1-deploy-tools`).

## FIX-354 cho B0-02 — regex userinfo che cả host khi query có @ (review R1 F19)

- **[1 TRIỆU CHỨNG]** F19: redis://:pw@host?x=a@b che host.
- **[2 TÁI HIỆN]** `R/RA/tai-hien-rest.md`
- **[3 BẰNG CHỨNG]** docs/reviews/2026-10-05-fix-debt-02-tich-hop.md F19; logging.py:84
- **[4 KHOANH VÙNG]** packages/core/logging.py, packages/core/tests/test_logging.py · cấm sửa: tệp prompt khác, DEBT.md, docs/fixes.md, changes/*
- **[5 SỬA NHỎ NHẤT]** [^\s/]+@ → [^\s/?#]+@.
- **[6 TEST CHẶN TÁI PHÁT]** test_mask_url_userinfo_password[redis://:pw@host?x=a@b]
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 + cov.sh (xem `R/RA/cov.log`); test đỏ→xanh trong tai-hien-*.md; commit fix(B0-02)… + Prompt/Fix. Commit `031f3a7`, `3ada64f` (nhánh `fix/debt-02-r1-deploy-tools`).

## FIX-355 cho B0-04 — assert lỏng + docstring sai ở test storage (review R1 F10, F22)

- **[1 TRIỆU CHỨNG]** F10: pytest.raises(AppError) không khẳng định mã; docstring AccessDenied; F22 docstring 'không đọc tiếp'.
- **[2 TÁI HIỆN]** không cần đỏ — assert chặt hơn + docstring
- **[3 BẰNG CHỨNG]** docs/reviews/2026-10-05-fix-debt-02-tich-hop.md F10, F22; test_s3.py:279,290; test_read_all_capped.py:34
- **[4 KHOANH VÙNG]** packages/storage/tests/test_s3.py, test_read_all_capped.py · cấm sửa: tệp prompt khác, DEBT.md, docs/fixes.md, changes/*
- **[5 SỬA NHỎ NHẤT]** as exc + code is INTERNAL + retry_after None; sửa docstring.
- **[6 TEST CHẶN TÁI PHÁT]** chính hai test delete (siết assert)
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 + cov.sh (xem `R/RA/cov.log`); test đỏ→xanh trong tai-hien-*.md; commit fix(B0-04)… + Prompt/Fix. Commit `9e5c81b`, `6b2569a`, `9612c27`, `2a54c11` (nhánh `fix/debt-02-r1-deploy-tools`).

## FIX-357 cho B5-06c — test sweep gắn perf cho test chức năng; tên test sai khuôn (F5, F21)

- **[1 TRIỆU CHỨNG]** Review F5: `test_sweep_survives_unreadable_queue` mang `perf` nên luật `calls==2`, `checked_out==0` rời bước 5; trần 2,0 s với số đo 1,04 s (1,9x).
- **[2 TÁI HIỆN]** Đọc `test_sweep_rules.py` trước/sau; `run.sh shell < cov2.sh` mã thoát 0.
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_steps/tests/test_sweep_rules.py:245-290` (trước sửa)
- **[4 KHOANH VÙNG]** Sửa: `apps/worker/pipeline_steps/tests/test_sweep_rules.py`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** Tách helper `_sweep_with_hanging_llen`; test chức năng không đo giờ; `test_sweep_hang_returns_within_budget` (perf) trần 4,0 s (≥ 3x số đo 1,04-1,08 s); hạn chờ `ENTER_WAIT_S`; đổi tên hai test `test_requeue_one__…`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_sweep_survives_unreadable_queue[treo|connection_error]` (bước 5), `test_sweep_hang_returns_within_budget` (perf) — tái cấu trúc, không cần đỏ (`R/RB/tai-hien-F5.md`).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B5-06c`, `Fix: FIX-357`. Commit `8928b9d` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-358 cho B5-07 — test chạm _STORAGE/_storage riêng tư; perf gắn nhầm test chức năng (F5, F6b)

- **[1 TRIỆU CHỨNG]** NO-304 sót: test gọi `tasks._STORAGE.override`, `tasks._storage()`; `test_quality_replay_redis_hang_skips` mang `perf` với `elapsed <= 2.0` (số đo 1,009 s).
- **[2 TÁI HIỆN]** grep `_STORAGE\|\._storage` trong `pipeline_quality/tests` trước sửa.
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_quality/tests/test_runtime.py:54,293-330`; `test_service.py:322`
- **[4 KHOANH VÙNG]** Sửa: `apps/worker/pipeline_quality/tasks.py`, `apps/worker/pipeline_quality/tests/*`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** Mở `override_quality_storage` (context manager) và `open_storage` (đổi tên `_storage`) công khai; test dùng chúng. Tách `_replay_with_hanging_redis`; test chức năng không đo giờ, test perf trần 4,0 s (≥ 3x 1,015 s).
- **[6 TEST CHẶN TÁI PHÁT]** Tái cấu trúc/đổi tên, không cần đỏ; `test_quality_replay_redis_hang_skips` + `..._within_budget` (perf) xanh (`R/RB/tai-hien-F5.md`).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B5-07`, `Fix: FIX-358`. Commit `a3a6113` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-359 cho B6-03b — huấn luyện: perf gắn nhầm, thiếu LOG_LEVEL/LOG_JSON trong env con, docstring cũ, tên test (F5, F17, F18, F21)

- **[1 TRIỆU CHỨNG]** F17 con huấn luyện luôn JSON/INFO vì allowlist thiếu hai biến; F18 docstring `_download_one` sai từ NO-263; F21 tên test; F5 `test_run_training_job_cancel_while_waiting` mang `perf`.
- **[2 TÁI HIỆN]** `red.sh`/`R/RB/red.log`: `test_start_training_runner_child_env_is_allowlisted` đỏ (mã 1); xanh ở `R/RB/cov2.log`.
- **[3 BẰNG CHỨNG]** `apps/ml/training_runner/tasks.py:29-33`, `dataset.py:107`
- **[4 KHOANH VÙNG]** Sửa: `apps/ml/training_runner/**`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** Thêm `LOG_LEVEL`, `LOG_JSON` vào `_ENV_KEEP`; viết lại docstring; đổi tên `test_claim_lease__unexpected_error_marks_lost`; tách `_cancel_while_waiting` + test perf `CANCEL_BUDGET_S` 10 s (đo 0,007-0,017 s).
- **[6 TEST CHẶN TÁI PHÁT]** `test_start_training_runner_child_env_is_allowlisted` (đỏ mã 1 → xanh mã 0, `R/RB/tai-hien-F17.md`); docstring/tên không cần đỏ.
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B6-03b`, `Fix: FIX-359`. Commit `27e4a49` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-360 cho B6-04b — _result sập khi reply không phải dict / float() lỗi; dòng kết quả dính dòng lạ (F8, F9)

- **[1 TRIỆU CHỨNG]** `reply` là `null`/`[]`/`5` → AttributeError; `float("x")` → ValueError rơi ra ngoài; dòng lạ không xuống dòng nuốt tiền tố `ML_EVAL_RESULT`.
- **[2 TÁI HIỆN]** `R/RB/red.log`: 6 ca đỏ trong `test_sandbox.py` (mã 1).
- **[3 BẰNG CHỨNG]** `apps/ml/ml_eval/tasks.py:96-108`, `sandbox.py:87`
- **[4 KHOANH VÙNG]** Sửa: `apps/ml/ml_eval/**`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** `tasks._result`: reply không dict → `{}`; `float()` lỗi → `MODEL_FORMAT_UNSUPPORTED`. `sandbox.main` ghi `"\n" + RESULT_PREFIX …`.
- **[6 TEST CHẶN TÁI PHÁT]** 5 ca tham số `test_ml_eval_sandbox_result_without_metrics`, `test_ml_eval_sandbox_main__result_survives_unterminated_previous_line` (đỏ mã 1 → xanh mã 0, `R/RB/tai-hien-F8-F9.md`).
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B6-04b`, `Fix: FIX-360`. Commit `8a1a8be` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-361 cho B5-04 — test làm tròn bề rộng so mảng với chính nó (F11)

- **[1 TRIỆU CHỨNG]** `unrounded` bằng `padded_input` khi `resized <= REC_MIN_WIDTH_PX` → assert vô nghĩa.
- **[2 TÁI HIỆN]** `test_reader_real.py:177`; đo `checked`.
- **[3 BẰNG CHỨNG]** `apps/ml/text/tests/test_reader_real.py`
- **[4 KHOANH VÙNG]** Sửa: `apps/ml/text/tests/test_reader_real.py`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** Bỏ ca `resized <= REC_MIN_WIDTH_PX`; `WIDTH_SEEDS` 100-105 (còn 19 vùng thật, 19/19 giữ chuỗi); sàn `2 x len(WIDTH_SEEDS)`.
- **[6 TEST CHẶN TÁI PHÁT]** `test_width_rounding_keeps_most_strings` xanh (`checked=19 same=19`, `R/RB/tai-hien-F11.md`); siết test, không cần đỏ.
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B5-04`, `Fix: FIX-361`. Commit `c72b5e3` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-362 cho B5-06b — docstring trần 30 s nhắc 'nợ ghi riêng' sai (F22)

- **[1 TRIỆU CHỨNG]** Docstring `BIG_HOLD_CEILING_S` nói nợ ghi riêng, thực là NO-296 (➖ đã duyệt).
- **[2 TÁI HIỆN]** `test_persist_lock.py:52-56`.
- **[3 BẰNG CHỨNG]** `apps/worker/pipeline_persist/tests/test_persist_lock.py`
- **[4 KHOANH VÙNG]** Sửa: `apps/worker/pipeline_persist/tests/test_persist_lock.py`. Cấm: DEBT.md, docs/fixes.md, changes/*, charter, tệp của prompt khác.
- **[5 SỬA NHỎ NHẤT]** Viết lại câu docstring trỏ NO-296.
- **[6 TEST CHẶN TÁI PHÁT]** Chỉ docstring — không cần đỏ.
- **[7 NGHIỆM THU]** `verify --steps 1,2,3,4` (`R/RB/steps1234.log`); độ phủ ở cov*.log; commit `Prompt: B5-06b`, `Fix: FIX-362`. Commit `d9ab535` (nhánh `fix/debt-02-r1-ml-worker`).

## FIX-364 cho B1-04 — assert hành vi khoá avatar là ULID (review R1 F13)

- **[1 TRIỆU CHỨNG]** Review F13 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** me/tests/test_text_source.py:14 chỉ quét chuỗi nguồn
- **[4 KHOANH VÙNG]** chỉ apps/api/me/tests/test_text_source.py
- **[5 SỬA NHỎ NHẤT]** thêm test PUT /api/me/avatar kiểm tên khoá is_ulid
- **[6 TEST CHẶN TÁI PHÁT]** test_me_replace_avatar__stored_key_name_is_a_bare_ulid; đột biến router new_ulid→chuỗi sai: đỏ (`R/RC/cov.log` RED_EXIT=1) → xanh
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `ff02ba7` (nhánh `fix/debt-02-r1-api`).

## FIX-365 cho B2-07 — assert danh tính lock_project_scope (review R1 F13)

- **[1 TRIỆU CHỨNG]** Review F13 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** templates/tests/test_locks_source.py:8
- **[4 KHOANH VÙNG]** chỉ apps/api/templates/tests/test_locks_source.py
- **[5 SỬA NHỎ NHẤT]** thêm assert is
- **[6 TEST CHẶN TÁI PHÁT]** test_templates_service__lock_is_the_packages_db_function; đột biến bọc hàm: đỏ → xanh
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `a518dd4` (nhánh `fix/debt-02-r1-api`).

## FIX-366 cho B4-02 — một nguồn mark_max + test dòng bị xoá giữa INSERT và SELECT (review R1 F14)

- **[1 TRIỆU CHỨNG]** Review F14,15 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** notifications/service.py:152-158; schemas.py:41 max_length=200
- **[4 KHOANH VÙNG]** chỉ apps/api/notifications/**
- **[5 SỬA NHỎ NHẤT]** hằng MARK_MAX_DEFAULT ở settings.py dùng cho schemas; test hook before_cursor_execute xoá dòng
- **[6 TEST CHẶN TÁI PHÁT]** test_notify__row_trimmed_between_insert_and_select_returns_none (đột biến bỏ 'existing is not None': đỏ → xanh); test_mark_body__schema_max_items_is_the_settings_default (refactor, không cần đỏ)
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `a5bdb63` (nhánh `fix/debt-02-r1-api`).

## FIX-367 cho B3-04 — dùng count_sql và regex FROM|JOIN floors (review R1 F16)

- **[1 TRIỆU CHỨNG]** Review F16 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** versions/tests/test_snapshots.py:421-437
- **[4 KHOANH VÙNG]** chỉ apps/api/versions/tests/test_snapshots.py
- **[5 SỬA NHỎ NHẤT]** thay bộ nghe tự viết bằng count_sql
- **[6 TEST CHẶN TÁI PHÁT]** không cần đỏ — tái cấu trúc test
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `f1d735c` (nhánh `fix/debt-02-r1-api`).

## FIX-368 cho B2-01 — đổi tên test theo hàm__điều kiện (review R1 F21)

- **[1 TRIỆU CHỨNG]** Review F21 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** projects/tests/test_routes_build.py:166, test_wire.py:107
- **[4 KHOANH VÙNG]** chỉ hai tệp test
- **[5 SỬA NHỎ NHẤT]** đổi tên (grep: chỉ docs/fixes.md nhắc, ngoài whitelist)
- **[6 TEST CHẶN TÁI PHÁT]** không cần đỏ — tên
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `91e8ae7` (nhánh `fix/debt-02-r1-api`).

## FIX-369 cho B4-01 — đổi tên test (review R1 F21)

- **[1 TRIỆU CHỨNG]** Review F21 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** streams/tests/test_fixture_streams.py:394
- **[4 KHOANH VÙNG]** chỉ tệp test
- **[5 SỬA NHỎ NHẤT]** test_next_frames__raises_when_the_app_exits_without_sending_a_body
- **[6 TEST CHẶN TÁI PHÁT]** không cần đỏ — tên
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `f2e817e` (nhánh `fix/debt-02-r1-api`).

## FIX-370 cho B2-06 — docstring 5 WORKER_BLOCKED (review R1 F22)

- **[1 TRIỆU CHỨNG]** Review F22 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** library/tests/test_jobs_cli.py:117
- **[4 KHOANH VÙNG]** chỉ tệp test
- **[5 SỬA NHỎ NHẤT]** sửa docstring
- **[6 TEST CHẶN TÁI PHÁT]** không cần đỏ — docstring
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `ee6a42f` (nhánh `fix/debt-02-r1-api`).

## FIX-371 cho B2-04 — hoàn docstring Create Date (review R1 F23)

- **[1 TRIỆU CHỨNG]** Review F23 (docs/reviews/2026-10-05-fix-debt-02-tich-hop.md)
- **[2 TÁI HIỆN]** nhánh fix/debt-02-r1-api @ b017a58
- **[3 BẰNG CHỨNG]** r20260925_b2_04_drawings.py:5 (3cba227)
- **[4 KHOANH VÙNG]** chỉ revision
- **[5 SỬA NHỎ NHẤT]** git checkout main -- tệp
- **[6 TEST CHẶN TÁI PHÁT]** không cần đỏ — docstring
- **[7 NGHIỆM THU]** verify --steps 1,2,3,4 thoát 0; cov.sh (219 passed; notifications service/schemas/settings 100% dòng+nhánh); commit có trailer Prompt/Fix Commit `2a68539` (nhánh `fix/debt-02-r1-api`).
