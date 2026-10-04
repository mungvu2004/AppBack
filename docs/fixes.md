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
| FIX-139 | 2026-10-04 | B0-01 | NO-306, NO-337 | DEBT-02 W2/C05b: cổng đầy đủ tin cache mypy ấm (NO-306); case_gate giữ bản tách tên test | `3e04636` (nhánh `fix/debt-02-w2-tools-layer`) |
| FIX-140 | 2026-10-04 | B0-07 | NO-337 | DEBT-02 W2/C05b: bộ ghi golden nhập tầng công cụ `tools.case_gate` | `9d79a1f` (nhánh `fix/debt-02-w2-tools-layer`) |
| FIX-141 | 2026-10-04 | B0-02 | NO-337 | DEBT-02 W2/C05b: nguồn tách tên test case dùng chung ở tầng thấp | `f726b60` (nhánh `fix/debt-02-w2-tools-layer`) |
| FIX-142 | 2026-10-04 | B3-04 | NO-258 | DEBT-02 W2/C06: `test_versions_list_versions__cursor_of_another_floor` đỏ ~1/1024 | `a439587` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-143 | 2026-10-04 | B0-05 | NO-211 | DEBT-02 W2/C06: `apps/api/auth_recovery/tests/test_e2e.py` chạy lẻ: worker thật `Received unregistered task 'default.auth_recovery.send_token_mail'`, không có thư trong 15 s | `71266df`, `4114c13` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-144 | 2026-10-04 | B4-01 | NO-298 | DEBT-02 W2/C06: `test_open_streams_do_not_hold_postgres_connections` đỏ `assert 9 == 0` (`pool.checkedout()`) ở cổng `-n 6` máy thiếu RAM (B5-06b, sha 363ca00); chạy lẻ xanh | `4eebaa1`, `65969ff` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-145 | 2026-10-04 | B1-05 | NO-340 | DEBT-02 W2/C06: `import apps.api.auth_recovery.jobs  # noqa: F401` ở `test_e2e.py:14`, chỉ có để đăng ký task với worker thật | `199a28b` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-146 | 2026-10-04 | B0-03 | NO-341 | DEBT-02 W2/C06: `test_conventions_catch_bad_columns` đỏ khi chạy lặp trong cùng một tiến trình: `ArgumentError: Column object 'score' already assigned to Table 'bad'` | `0b432f4`, `6fbdd5a` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-147 | 2026-10-04 | B2-05b | NO-264 | DEBT-02 W2/C06: dòng nợ ghi đỏ ~1/4 lượt dưới `-n 6`; không tái hiện được (C06: 3 giả thuyết; 0/22 lượt cổng đầy đủ từ 09-29 + 3 junit) | `7aef2e8`, `2c4cd0c` (nhánh `fix/debt-02-w2-flakes`) |
| FIX-148 | 2026-10-04 | B0-05 | NO-266 | DEBT-02 W2/C05: tham số parametrize sinh từ đồng hồ lúc thu thập (NO-266) + docstring R-01 thiếu | `971ae1f`, `959742d` (nhánh `fix/debt-02-w2-fixtures`) |
| FIX-149 | 2026-10-04 | B0-03 | NO-267, NO-277, NO-279 | DEBT-02 W2/C05: lượt dọn db_url mở kết nối mới mỗi test và đặt setval trước khi nạp seed | `bcb9572`, `15d1045` (nhánh `fix/debt-02-w2-fixtures`) |
| FIX-150 | 2026-10-04 | B0-01 | NO-277, NO-281, NO-282 | DEBT-02 W2/C05: container dịch vụ mồ côi khi pytest bị giết cứng (NO-281), docker chưa khai trong nhóm dev (NO-282), chú thích O_APPEND | `9c1e4c3`, `89d40ab`, `1308068` (nhánh `fix/debt-02-w2-fixtures`) |
| FIX-154 | 2026-10-04 | B6-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test K36 pool một kết nối chưa gắn perf | `802da8b` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `e9269bb` (nhánh `fix/debt-02-w2`) |
| FIX-155 | 2026-10-04 | B0-06 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test broker chết chưa gắn perf | `9b048e6` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-156 | 2026-10-04 | B2-04 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: test K36/K28 chưa perf, tên khớp mẫu case | `1d28348` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-157 | 2026-10-04 | B2-07 | NO-246 | DEBT-02 W2/C07: NO-246: test 1000x20 điểm khẳng định < 2 s chưa perf | `a64a1cc` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-158 | 2026-10-04 | B4-01 | NO-272 | DEBT-02 W2/C07: NO-272: 6 test S07 (mã case) khẳng định elapsed <= trần ở bước 5 (progress ×4 + notifications ×2, cùng chủ B4-01) | `4ab46e1`, `c0f355b` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-159 | 2026-10-04 | B7-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: wait_until 1,5 s sát TTL cache 1 s | `7720f0c` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `21c27fd` (nhánh `fix/debt-02-w2`) |
| FIX-160 | 2026-10-04 | B5-01 | NO-268 | DEBT-02 W2/C07: NO-268: test_export_onnx_deterministic 8–10 s kéo đuôi lượt loadfile | `3477820` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `c2fbb1a` (nhánh `fix/debt-02-w2`) |
| FIX-161 | 2026-10-04 | B6-02 | NO-278 | DEBT-02 W2/C07: NO-278: pytestmark perf cấp tệp, số đo chưa in bằng logging | `e706ecf` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-162 | 2026-10-04 | B0-03 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: 3 test J09 (mã case) khẳng định elapsed ở bước 5 | `f1357ae`, `087741d`, `ebc7495`, `cfd7797` (nhánh `fix/debt-02-w2-perf-marks`); NO-344 docstring: `84fa737`, `4559b4d` (nhánh `fix/debt-02-w2`) |
| FIX-163 | 2026-10-04 | B0-01 | NO-246, NO-268, NO-272, NO-278 | DEBT-02 W2/C07: thiếu lưới chặn tái phát cho trần đồng hồ chưa perf | `d84e7ad`, `9dbaa7a` (nhánh `fix/debt-02-w2-perf-marks`) |
| FIX-167 | 2026-10-04 | B5-03 | NO-312 | DEBT-02 W2/C08: test M04 vá ML_DEVICE=cuda làm bẩn cache get_ml_settings của cả tiến trình | `b11a258` (nhánh `fix/debt-02-w2-cache`) |
| FIX-168 | 2026-10-04 | B6-03b | NO-312 | DEBT-02 W2/C08: support.py định nghĩa lại fixture ml_settings_cache trùng bản dùng chung (R-02, NO-312) | `44db1f4`, `19ca19f` (nhánh `fix/debt-02-w2-cache`) |
| FIX-169 | 2026-10-04 | B2-04 | NO-265 | DEBT-02 W2/C08: signer() ăn kho cache cấp tiến trình của test khác | `0534cc9` (nhánh `fix/debt-02-w2-cache`) |
| FIX-170 | 2026-10-04 | B0-10 | NO-204 | DEBT-02 W2/C08: README kiểm ml.env dùng danh sách cấm hẹp (NO-204 nửa 2) | `4a45c6c` (nhánh `fix/debt-02-w2-cache`) |
| FIX-171 | 2026-10-04 | B5-01 | NO-322, NO-323 | DEBT-02 W2/C08: scan() bỏ tệp test nên import ultralytics trần tái sinh NO-322 | `df46a99` (nhánh `fix/debt-02-w2-cache`) |
| FIX-172 | 2026-10-04 | B2-03 | NO-265 | DEBT-02 W2/C08: test đếm SQL của `view_parts` chỉ xanh nhờ `_default_signer` do test khác làm ấm | `d3c8838` (nhánh `fix/debt-02-w2-cache`) |
| FIX-173 | 2026-10-04 | B5-06a | NO-218, NO-295, NO-339 | DEBT-02 W2/C14: đo RSS sai tiến trình (NO-339), J01 không qua đường gửi thật (NO-218), J06 khẳng định rỗng và dọn test | `fce473e`, `c2489b7` (nhánh `fix/debt-02-w2-pipeline`) |
| FIX-174 | 2026-10-04 | B5-06a | NO-339 | DEBT-02 W2/M cổng 1 đỏ (5b): con `spawn` đo `RUSAGE_SELF.ru_maxrss` mang theo RSS của cha pytest qua `execve` | `84ad46c` (nhánh `fix/debt-02-w2`) |

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
`assert 'down_revision: str | None = "r20260920_b0_03"' in body`. BE-00 §6.1 cho **mỗi prompt
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
- **[4 KHOANH VÙNG]** Sửa: apps/api/admin_ml_registry/tests/test_upload.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
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
- **[4 KHOANH VÙNG]** Sửa: tools/tests/test_perf_marks.py duy nhất. Cấm: mã sản phẩm, conftest, tools/verify.
- **[5 SỬA NHỎ NHẤT]** Test quét AST 15 tệp (trần cận trên thời gian thiếu perf / perf mang mã case — import _CASE_IN_NAME_RE từ steps.py / pytestmark perf cấp tệp) + tự kiểm 5 loại lỗi.
- **[6 TEST CHẶN TÁI PHÁT]** `tools/tests/test_perf_marks.py::test_scanned_files_mark_wall_clock_ceilings_perf[tools/tests/test_perf_marks.py]` — đỏ → xanh (`red.log` → `xanh.log`).
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
