kiểm toán chưa đủ — nhóm Giấy phép (V14) 100 % chưa kiểm

# Kiểm toán bảo mật B7-02

- Commit đã soát: `2a63cfc5420f` (cây mã = `main` `096e870`).
- Chuẩn: OWASP ASVS 4.0.3, cấp 2, chương V1–V14.
- Tệp: `asvs-checklist.md`, `threat-model.md`, `fixes/SEC-*.md` (số theo dải của từng việc soát, có khoảng trống — chủ ý).

## Bảng tổng

| kết quả | số mục |
|---|---|
| đạt | 100 |
| lỗ | 8 |
| không áp dụng | 0 |
| chưa kiểm | 18 |
| **tổng** | 126 |

| mức | số `SEC-*` |
|---|---|
| nghiêm trọng | 0 |
| cao | 0 |
| trung bình | 2 |
| thấp | 6 |

- `SEC-020` (thấp): FIX SEC-020 cho B6-03b — tiến trình con huấn luyện thừa hưởng toàn bộ môi trường của `ml` (gồm `S3_SECRET_KEY` khoá riêng của ml và URL Redis), không lọc như `ml_eval`.
- `SEC-040` (trung bình): FIX SEC-040 cho B0-10 — `backup.sh` không đặt `umask`: `db.dump` và `objects.tar` (dạng rõ khi không có `BACKUP_AGE_RECIPIENT`) sinh ra với quyền 0644, thư mục 0755, mọi tài khoản trên máy đọc được.
- `SEC-041` (trung bình): FIX SEC-041 cho B0-02 — `CoreSettings` nhận khoá mẫu công khai `change-me-32-bytes-minimum-please` làm `SECRET_KEY` ở `staging`/`production`, nên một VPS dựng từ `env.example` chưa sửa ký token bằng khoá ai cũng biết.
- `SEC-042` (thấp): FIX SEC-042 cho B0-02 — bộ che log không che bí mật nhúng trong URL kết nối (`scheme://user:mật-khẩu@host`) của chuỗi tự do, nên thông điệp lỗi của driver chứa DSN vào log nguyên văn.
- `SEC-043` (thấp): FIX SEC-043 cho B0-09 — `gitleaks detect --log-opts=--all` trên toàn lịch sử báo 11 phát hiện `generic-api-key`, đều là chuỗi giả trong test (Idempotency-Key, mật khẩu giả, SECRET_KEY giả) chưa được miễn, nên cổng quét lịch sử không xanh.
- `SEC-060` (thấp): FIX SEC-060 cho B0-08 — thân 413/503 do chính nginx sinh ra không mang bộ header nền B0-06 (nosniff, Referrer-Policy, X-Frame-Options, no-store)
- `SEC-061` (thấp): FIX SEC-061 cho B0-10 — `ALERT_WEBHOOK_URL` của notify.yml là secret cấp repository, không nằm ở GitHub Environment
- `SEC-062` (thấp): FIX SEC-062 cho B6-04a — `HF_HUB_OFFLINE=1` mà BE-00 §9 đòi cho transformers không được đặt ở đâu trong mã hay compose

Nhóm theo 10 dòng "Phạm vi bắt buộc" của khối [6]; dòng V14 chia theo nội dung: D-24, D-25 → Giấy phép; D-13 (`/metrics`) → Chuỗi cung ứng, triển khai; C-22 (`compare_digest`, K16) → Dữ liệu, bí mật; V14 còn lại → Giao tiếp, cấu hình.

| nhóm (khối [6]) | mục | `chưa kiểm` | tỉ lệ |
|---|---|---|---|
| Xác thực, phiên (V2, V3) | 18 | 0 | 0 % |
| Quyền (V4) | 7 | 0 | 0 % |
| Đầu vào, tệp (V5, V12) | 19 | 0 | 0 % |
| Lỗi, log (V7) | 11 | 3 | 27 % |
| Dữ liệu, bí mật (V6, V8) | 12 | 3 | 25 % |
| Giao tiếp, cấu hình (V9, V14) | 11 | 4 | 36 % |
| Giới hạn, API (V11, V13) | 26 | 2 | 7 % |
| Chuỗi cung ứng, triển khai (V10, V14) | 11 | 2 | 18 % |
| ML, việc nền (V1) | 9 | 2 | 22 % |
| Giấy phép (V14) | 2 | 2 | 100 % |

## Giới hạn

- Phương án (a), người dùng chốt 2026-10-02: trên máy không có ảnh `appback-api:dev`, `appback-worker:dev`, `appback-web` và ảnh nền để build; khối [5]/[9] cấm tải. Thăm dò chạy ở **tầng ứng dụng** (app FastAPI thật `create_app`, Postgres/Redis/MinIO thật của container verify, token thật qua `signed_in`), **không qua nginx**. Mục chỉ chứng minh được qua nginx/`prod.yml` (CSP/HSTS sống, 443, cổng metrics từ máy chủ, S3 khác origin sống) ghi `chưa kiểm — thiếu ảnh`.
- Bằng chứng "test đạt": `run.sh` không đưa `junit.xml` ra khỏi container; thay bằng log cổng 1 (`gate-1.log`, bảng E.10, bước 5 đạt, `7868 passed` ở dòng 383, `mã thoát: 0`) cộng danh sách thu thập `collect.txt` (7868 nodeid), cùng sha. Cổng cấm skip/xfail.

## Tái lập thăm dò

Mỗi việc chạy script `dieu-phoi/chay/B7-02/<việc>/probe-<n>.sh` qua `export APPFRONT_REPO=F:/App/AppFront; bash tools/verify/run.sh shell < <script>`; script sinh test tạm ở `/tmp/w/b7_02_probe/` (bản chép trong container, không commit) và in dòng `PROBE`. Lệnh và đầu ra rút gọn (bí mật che `***`):

### Việc A

**A/L-01** — thăm dò tầng app, không qua nginx (thiếu ảnh `appback-web`/`appback-api`; luật chung phương án (a)).
App thật `create_app` qua `auth_app`/`auth_client`, verifier thật, token thật qua `signed_in`, Postgres/Redis/MinIO thật
của container verify, sha `2a63cfc5420f`. Script `dieu-phoi/chay/B7-02/A/probe-1.sh` sinh `/tmp/w/b7_02_probe/test_a_1.py`
(bản chép trong container, không commit), log `A/probe-1.log`.

```
$ export APPFRONT_REPO=F:/App/AppFront
$ bash tools/verify/run.sh shell < .../B7-02/A/probe-1.sh > .../B7-02/A/probe-1.log 2>&1   # 16:41Z, 1 verify-run khác đang chạy
mã thoát: 0
PROBE P1 refresh Origin=evil -> 403 ORIGIN_MISMATCH
PROBE P1 refresh no Origin -> 403 ORIGIN_MISMATCH
PROBE P2 login remember=True  Set-Cookie: appback_refresh=***; HttpOnly; Max-Age=604800; Path=/api/auth; SameSite=strict; Secure
PROBE P2 login remember=True  Set-Cookie: appback_stream=***; HttpOnly; Max-Age=600; Path=/api/streams; SameSite=strict; Secure
PROBE P2 login remember=False Set-Cookie: appback_refresh=***; HttpOnly; Path=/api/auth; SameSite=strict; Secure
PROBE P2 refresh status=200   Set-Cookie: appback_refresh=***; HttpOnly; Path=/api/auth; SameSite=strict; Secure
PROBE P2 refresh status=200   Set-Cookie: appback_stream=***; HttpOnly; Max-Age=600; Path=/api/streams; SameSite=strict; Secure
PROBE P3 engineer GET /api/admin/ml/model-families -> 403 FORBIDDEN
PROBE P3 viewer GET /api/admin/ml/model-families -> 403 FORBIDDEN
PROBE P3 admin GET /api/admin/ml/model-families -> 200
PROBE P4 engineer-outsider GET layer -> 404 NOT_FOUND resource=project
PROBE P4 admin-outsider GET layer -> 404 NOT_FOUND resource=project
PROBE P4 member GET layer -> 200
PROBE P5 other user's notification accept-invite -> 404 NOT_FOUND
PROBE P6 victim GET /api/me before -> 200
PROBE P7 W21 PATCH /api/users/{victim}/role body userId=<khác> -> 422 PATH_BODY_MISMATCH
PROBE P6 admin disable victim -> 200
PROBE P6 victim GET /api/me right after disable -> 401 SESSION_REVOKED
PROBE P6 victim refresh after disable -> 401 SESSION_REVOKED
PROBE P6 admin-to-demote GET admin/ml before -> 200
PROBE P6 demote admin->engineer -> 200
PROBE P6 demoted GET admin/ml immediately -> 401 SESSION_REVOKED
PROBE P6 demoted GET admin/ml after 5.2 s -> 401 SESSION_REVOKED
PROBE P8 40 sequential refreshes of a live session (in grace) -> [200] count429= 0
6 passed, 4 warnings in 16.92s
```

Ánh xạ: P1 → A-10; P2 → A-09; P3 → A-22; P4 → A-19; P5 → A-21; P6 → A-14 (vô hiệu), A-15 (hạ vai: 401 ngay vì
`bump_token_version`, C25 cho phép 401 hoặc 403); P7 → A-23; P8 → A-11. Thăm dò 5 của spec (dùng lại ngoài ân hạn) thay
bằng test ở A-08.

**A/L-02** — mỗi mục đích khoá HKDF dùng ở đâu (A-12).

```
$ git grep -nE "(current_key|verification_keys)\(" -- apps packages ':!*/tests/*' | grep -v packages/core/keys.py
apps/api/auth/emails.py:47:            current_key("lookup")
apps/api/auth/sessions.py:374,401,475: verification_keys("refresh") / current_key("refresh")
apps/api/auth/tokens.py:67,76:         current_key(audience) / verification_keys(audience)   # access | stream
apps/api/auth_recovery/jobs.py:150:    verification_keys("token")
apps/api/auth_recovery/tokens.py:78:   current_key("token")
apps/api/core/pagination.py:92,102:    current_key("cursor") / verification_keys("cursor")
packages/storage/local.py:183,199:     current_key("file") / verification_keys("file")
mã thoát: 0 (12 dòng; mỗi mục đích đúng một module, không mục đích nào dùng chung hai việc)
```

**A/L-03** — module dựng route công khai và module có đường `/admin` (A-20, A-22).

```
$ git grep -l "public_router(" -- apps/api ':!*/tests/*'
apps/api/auth/router.py  apps/api/auth_recovery/router.py  apps/api/core/routing.py (định nghĩa)
apps/api/files/router.py  apps/api/health/router.py  apps/api/streams/router.py  apps/api/telemetry/router.py
mã thoát: 0
$ grep -rln '"/admin' apps/api --include=*.py | grep -v /tests/
apps/api/admin_ml_datasets/router.py  apps/api/admin_ml_jobs/router.py  apps/api/admin_ml_registry/router.py
mã thoát: 0 (cả ba gắn `Depends(require_admin)` ở cấp router: :27, :30, :31)
```

### Việc B

Mọi lệnh chạy trong worktree `docs/b7-02-input-ml` ở `2a63cfc`: `git grep -n -E '<mẫu>' -- apps packages tools deploy` (mã thoát 0 khi có trúng, 1 khi 0 trúng). Cột số: `tổng/trong test` (test = `*/tests/*`).

| L | mẫu | tổng/test | trúng ngoài test và kết luận |
|---|---|---|---|
| B/L-01 | `shell=True` | 0/0 | không có |
| B/L-02 | `pickle` | 50/42 | `upload.py:12,99`, `export_yolo.py:4,5,59`, `runner.py:112`, `trainer.py:8` — docstring/chú thích cấm hoặc băm trước khi nhập, không lời gọi (B-14) |
| B/L-03 | `torch\.load` | 11/9 | `upload.py:11`, `runner.py:113` — chú thích "không bao giờ" |
| B/L-04 | `yaml\.load\(` | 0/0 | không có |
| B/L-05 | `text\(f` | 18/10 | `projects/jobs.py:74,75` hằng `int` (B-13); `migrate_check.py:78` tên bảng catalog (`noqa: S608`); `training_runner/runner.py:232`, `pipeline_persist/service.py:249` trùng chuỗi `enter_context(`/`load_context(` không phải SQL; `packages/testing/fixtures/db.py:214,217,233` fixture test |
| B/L-06 | `eval\(` | 11/1 | `model.eval()` PyTorch (`runtime/export.py:83`, `training_segformer/export.py:44,70`, `loop.py:73,76`, `metrics.py:30,34`) và `redis.eval` Lua cố định (`redis_sync.py:36,41`, `messaging/tasks.py:248`) |
| B/L-07 | `exec\(` | 0/0 | không có |
| B/L-08 | `verify=False` | 0/0 | không có |
| B/L-09 | `extractall\(` | 0/0 | không có (`archive.py:116` ghi rõ không dùng) |
| B/L-10 | `MAX_IMAGE_PIXELS` | 3/1 | `avatar.py:9`, `raster.py:5` — chú thích cấm gán toàn cục (B-06) |
| B/L-11 | `exclude_unset` | 2/0 | `wire.py:6,109` — chú thích cấm (K02) |
| B/L-12 | `urlopen` | 8/3 | `pinned.py:173` (https cố định + SHA, B-17); `base.yml:162`, `api.Dockerfile:71` healthcheck `127.0.0.1`; `packages/testing/fixtures/mail.py:60,67` URL cục bộ của fixture |
| B/L-13 | `httpx\.` | 1161/1129 | 32 trúng ngoài test đều là kiểu/fixture trong `packages/testing/**` (`fixtures/api.py`, `auth.py`, `streams.py`, `golden/recorder.py`); không có trong mã sản xuất |
| B/L-14 | `requests\.` | 4/4 | chỉ test |
| B/L-15 | `except Exception` | 23/0 | 18 mã: `auth/services.py:58`, `auth/sessions.py:595`, `core/middleware.py:276`, `core/ratelimit.py:130`, `health/router.py:116`, `training_runner/__main__.py:69`, `db/hooks.py:140,150`, `db/migrate_check.py:191`, `mail/sender.py:97`, `messaging/locks.py:190`, `messaging/redis.py:242`, `messaging/tasks.py:261,311`, `tools/ci/h2.py:148`, `tools/ci/import_all.py:50,68`, `tools/verify/steps.py:330` — chặng cuối hoặc phân loại rồi ném lại, hầu hết `noqa` kèm lý do; 5 docstring (`runtime/errors.py:8`, `ultralytics_import.py:4`, `text/reader.py:293`, `training_yolo/trainer.py:223`, `walls/segformer.py:65`). Thuộc B và chạm dữ liệu tệp/ML: `training_runner/__main__.py:69` (handler cuối tiến trình: báo job hỏng, không nuốt) |
| B/L-16 | `Popen\(` | 5/3 | `ml_eval/tasks.py:133`, `training_runner/tasks.py:73` (B-15) |
| B/L-17 | `subprocess` | 236/215 | 21 ngoài test: hai tệp trên (`ml_eval/tasks.py:15,83,133-143`, `training_runner/tasks.py:9,24,71-74`), `tools/ci/commits.py:14,87,104`, `tools/contract/runner_client.py:24,94,97`, `tools/verify/steps.py:13,54,56`, `tools/coverage_gate.py:173` — đối số danh sách, không shell |
| B/L-18 | `tarfile` | 5/4 | `deploy/backup/backup.sh:121` đếm mục của bản sao lưu hệ thống (`getmembers`, không giải nén) |
| B/L-19 | `zipfile` | 29/23 | ngoài test chỉ `datasets_cubicasa/archive.py:13,58,85,100,115,145` (B-08) |

### Thăm dò

| L | lệnh | mã thoát | đầu ra rút gọn |
|---|---|---|---|
| B/L-20 | `bash tools/verify/run.sh shell < dieu-phoi/chay/B7-02/B/probe-1.sh` (pytest `b7_02_probe/test_b_1.py`, hàm thật, Linux container) | 0 | `3 passed`. `PROBE zip dotdot/nested_dotdot/absolute -> REJECT path; escaped=False`; `zip symlink -> REJECT symlink`; `zip bomb (900 KB số 0, deflate) -> REJECT ratio`; `discover symlink dir -> ['1'] {'unsafe_path': 1}`; `read_regular symlink -> UnsafePathError`; `read_regular fifo -> UnsafePathError in 0.00s`; `png 50000x50000 / 9000x6000 / 200000x200000 -> VisionError IMAGE_TOO_LARGE` (≤ 0,06 s); `pillow globals before/after: (89478485, False) (89478485, False)`; `payload extra_field -> REJECT extra_forbidden`; `schema_v2 -> REJECT literal_error`; `check_key` từ chối `projects/../etc/passwd`, `ml/models/../x`, `a//b`, `a/./b`, `x
y`, `/abs`, chấp nhận `ok/key.png`. Lượt đầu có lỗi probe (zip không nén nên bom không bị coi là bom) đã sửa và chạy lại; log `B/probe-1.log` là lượt sau. |

| B/L-21 | `bash tools/verify/run.sh shell < dieu-phoi/chay/B7-02/B/probe-2.sh` (pytest `b7_02_probe/test_b_2.py`, fixture `local_storage`) | 0 | `3 passed`. `PROBE local_storage '<khoá xấu>' -> {put, stat, open_read, delete: ValueError}` cho 6 khoá (`../escape.png`, `projects/../../escape.png`, `a/./b.png`, `/abs.png`, CRLF, `a//b`); `escaped files: []`; `put over max_bytes -> AppError ; object_left: None`; `Popen apps/ml/training_runner/tasks.py:73 env_kwarg=False`; `Popen apps/ml/ml_eval/tasks.py:133 env_kwarg=True`. Lượt đầu `put` báo `TypeError` vì thiếu `max_bytes` (lỗi probe), đã sửa và chạy lại; `B/probe-2.log` là lượt sau. |

### Việc C

Các lệnh dưới đây chạy ngày 2026-10-02 trên commit `2a63cfc5420f`; thăm dò chạy bằng `bash tools/verify/run.sh shell < C/probe-1.sh` (container verify, app FastAPI thật qua `create_app`, Postgres/Redis thật, kho `LocalDiskStorage`).

**C/L-01 — gitleaks cả lịch sử (V6; C-11, C-12)**

```
$ MSYS_NO_PATHCONV=1 bash backend/dieu-phoi/chay/B7-02/C/gitleaks.sh
  (docker run --rm -v F:/App/AppBack:/repo:ro -w /repo --entrypoint sh appback-verify:local -c "git config --global --add safe.directory /repo; gitleaks detect --source=. --redact -v --config=.gitleaks.toml --log-opts=--all")
commits(all): 1086 · HEAD: 096e8703f884 · gitleaks 8.30.1
INF 919 commits scanned. · scanned ~16802850 bytes in 11.4s
WRN leaks found: 11     (RuleID generic-api-key ×11, bảy vị trí, đều trong file test — danh sách ở SEC-043)
gitleaks exit: 1        (mã thoát của script bọc: 0)
```

Đầu vào chỉ đọc (`:ro`). Kết quả: 11 phát hiện, đã đọc từng dòng → chuỗi giả của test; gom thành `SEC-043`. Hai commit đã miễn (`eb40a3c`, `1b97b24`) không xuất hiện trong phát hiện.

**C/L-02 — thăm dò tầng app, một container (V7, V8, V11, V13)**

```
$ export APPFRONT_REPO=F:/App/AppFront
$ bash tools/verify/run.sh shell < backend/dieu-phoi/chay/B7-02/C/probe-1.sh > C/probe-1.log 2>&1      # mã thoát 0; "6 passed"
PROBE telemetry 65537B -> 413 {"code": "PAYLOAD_TOO_LARGE", "requestId": "***"}
PROBE telemetry no Authorization header, first batch -> 204
PROBE telemetry log keys: [accepted, dropped, durationMs, level, logger, method, msg, reason, requestId, routeTemplate, status, ts] ; any ip-like value: False ; records: 364
PROBE telemetry first non-204 at request 121 -> 429 Retry-After= 10 {"code": "RATE_LIMITED", "requestId": "***"}      (dừng ở lượt 429 đầu)
PROBE files good token -> 200 private, max-age=600 nosniff
PROBE files 1 byte flipped in MAC -> 404 NOT_FOUND | in body -> 404
PROBE signed_url('..') refused: ValueError
PROBE files forged-with-valid-MAC key '..' -> 404 {'code': 'NOT_FOUND'}
PROBE signed at 2026-01-01T00:59:30+00:00 -> valid minutes: 60.5   ·   signed at 00:00:00 -> 120.0 phút
PROBE files after 121 min -> 404
PROBE log records: 10 ; token in any record: True   <- chỉ logger httpx của client thử (chạy lại, C/probe-2.log: "loggers with token: ['httpx'] ; app loggers with token: False")
PROBE access-log routeTemplate: ['/api/files/{token}', '/api/files/{token}'] keys: [durationMs, level, logger, method, msg, requestId, routeTemplate, status, ts]
PROBE 500 -> 500 {'code': 'INTERNAL', 'requestId': 'probe-rid-0001'} x-request-id: probe-rid-0001 xcto: nosniff
PROBE 500 body leaks stack/exception text: False
PROBE mask: {"url": "…X-Amz-Signature=***&token=***", "authorization": "***", "confirmEmail": "***", "msg": "tok {'password': '***', 'Set-Cookie': '***', 'chunk': '***', 'contentBase64': '***', 'nested': [{'refreshToken': '***', 'x': 'Bearer ***"}
PROBE mask-free-text: connect postgresql://appback:s3cr3tpw@postgres:5432/appback failed      <- KHÔNG che (SEC-042)
PROBE mask-free-text: redis://:r3dispw@redis-broker:6379/0 refused                            <- KHÔNG che
PROBE settings: production accepts env.example SECRET_KEY placeholder, bytes = 33 production  <- (SEC-041)
PROBE settings: short key refused: ValidationError
PROBE route (op | limiter | body_limit | idem): auth_login [auth_login_ip] 1048576 off · auth_refresh [] (limiter gọi trực tiếp ở router.py:246; test C11 phủ) · auth_request_password_reset/auth_confirm_password_reset/auth_accept_invitation [recovery_ip] · me_change_password [me_password] · me_replace_avatar [me_avatar] · drawings_init_upload [drawings_init] · users_invite_users và users_resend_invitation [users_invite] · members_add_member [members_add] · telemetry_ingest_batch [telemetry_ingest] 65536 off · health_ready [health_ready]
PROBE routes with body_limit > 1MiB: drawings_upload_chunk 8388608 off · ml_upload_version 536870912 off · spatial_write_layer 8388608 off
PROBE age binary: none / none
```

Lưu ý: dòng log có `"requestId": null` là do thăm dò định dạng bản ghi sau khi request kết thúc (ContextVar đã reset), không phải lỗi của app.

**C/L-03 — grep có kết luận (`git -C <worktree> grep -n …`, commit `2a63cfc5420f`)**

```
git grep -n "umask\|chmod" -- deploy/backup                         -> exit 1 (không trúng) -> C-17, SEC-040
git grep -n "BACKUP_AGE_RECIPIENT" -- deploy .github                 -> exit 0: backup.sh:13,24,132,134,140,142; deploy/scripts/README.md:94,182-183,257,262,283; env.example không có
git grep -n "access_log off" -- deploy/nginx                         -> exit 0: app_locations.conf:39,87,92; templates/prod/app.conf.template:25; minio.conf.template:33
git grep -n "no-access-log" -- deploy                                -> exit 0: base.yml:151, api.Dockerfile:73
git grep -n "limit_req\|limit_conn" -- deploy/nginx                  -> exit 1 (nginx không giới hạn tốc độ/kết nối; chỉ app) -> Nợ hiến chương
git grep -n "change-me" -- deploy ':!*/tests/*'                      -> exit 0: chỉ env.example (dòng 8: SECRET_KEY 33 byte) -> SEC-041
git grep -n "include_input" -- apps packages                         -> một trúng ngoài test: apps/api/streams/sse.py:101
git grep -n "compare_digest" -- apps packages ':!*/tests/*'          -> auth/sessions.py:376-430, core/pagination.py:103, storage/local.py:200
```

Không chạy được (thiếu ảnh/compose): nginx sống (C-08, C-39), `backup.sh` thật (C-18), `age` thật (C-16).

### Việc D

- **D/L-01** `bash tools/verify/run.sh shell < dieu-phoi/chay/B7-02/D/probe-1.sh` (hàm `test_routes`, `operations(auth_app)`) → mã thoát 0. Đầu ra: `PROBE OPSCOUNT 86`; 86 dòng `PROBE OP {...}`; so với BE-BIND bằng bản phân tích trên host: 83 khớp khoá, 0 lệch; 12 route `protected=false` (liệt kê ở D-26).
- **D/L-02** cùng lệnh (hàm `test_headers`, `signed_in` thật, `auth_client`), mã thoát 0, `2 passed`. Rút gọn:
  - `200 feature-flags` / `404 /api/khong-co-route` / `401 /api/me` ẩn danh: `x-content-type-options: nosniff`, `referrer-policy: same-origin`, `x-frame-options: DENY`, `cache-control: no-store`.
  - `413 POST /api/telemetry` 64 KiB+1: `{"code": "PAYLOAD_TOO_LARGE"}`, đủ bốn header.
  - `OPTIONS /api/auth/login` `Origin: https://evil.example` → 404, không có `access-control-allow-origin`.
  - `POST /api/auth/refresh` `Origin` lạ → 403 `ORIGIN_MISMATCH`; `GET /api/streams/notifications` `Origin` lạ → 403 `ORIGIN_MISMATCH`.
  - `GET /api/streams/notifications` không `Origin` + token → luồng mở (hết giờ 4 s đợi thân), không 403.
  - `429` ở lượt login thứ 30: `{"code": "RATE_LIMITED"}`, `retry-after: 10`, đủ bốn header (dừng ở lượt 429 đầu).
  - 503 không dựng → D-04. App không phát `content-security-policy`/`strict-transport-security` (đúng: đặt ở nginx).
- **D/L-03** `grep -n "uses:" .github/workflows/*.yml` → mã thoát 0; 45 dòng; `grep -h "uses:" .github/workflows/*.yml | grep -vcE "uses: [^@]+@[0-9a-f]{40} #"` → 1 (dòng chú thích `ci.yml:3`); 44 action đều ghim SHA 40 hex.
- **D/L-04** `grep -n "^USER\|^FROM\|HEALTHCHECK" deploy/docker/*` → mã thoát 0: `USER 10001` ở api, worker, ml, web; mọi `FROM` kèm `@sha256:`. `git grep -n "CORSMiddleware\|allow_origins" -- apps packages` → mã thoát 1 (0 trúng).
- **D/L-05** `grep -n -i opencv uv.lock` → mã thoát 0: `uv.lock:28` override `opencv-python` marker `sys_platform == 'never'`; `uv.lock:1229` `opencv-python-headless`; không có `opencv-python` đứng riêng.
- **D/L-06** `grep -n "environment:\|secrets\." .github/workflows/*.yml` → mã thoát 0: `deploy.yml:99,145,180,227` có `environment:`; `notify.yml:23` `secrets.ALERT_WEBHOOK_URL`, không `environment:`.
- **D/L-07** `git grep -n "HF_HUB_OFFLINE"` → mã thoát 0: một dòng, `docs/charter/BE-00.md:407`; không có trong `apps`, `packages`, `deploy`.
- **D/L-08** `git grep -n "license" -- apps packages ':!*tests*'` và `git grep -n "\.license" -- apps packages` → chỉ `packages/ml_contracts/pinned.py` khai `license`; 0 chỗ đọc.
- **D/L-09** `sed -n 380,479p dieu-phoi/chay/B7-02/P/gate-1.log | grep -c "| đạt"` → 83; dòng không `đạt` trong bảng: 0; `gate-1.log:479` `case_gate: đạt`; `gate-1.log:523` `mã thoát: 0`.

## Nợ hiến chương

### Việc A

- **N-A1** — BE-00 §5 không có xác thực bước hai cho vai `admin` (ASVS 4.0.3 V2 cấp 2 khuyến nghị cho tài khoản đặc
  quyền). Đề xuất: ghi rõ trong BE-00 §5 là "ngoài phạm vi v1" kèm rủi ro tồn dư, hoặc thêm một prompt MFA cho admin.

### Việc B

- **Môi trường của tiến trình con huấn luyện** (BE-00 §7 "Tiến trình huấn luyện", dòng 326): hiến chương không nói con huấn luyện chạy với env tối thiểu như `ml_eval`; `training_runner/tasks.py:73` thừa hưởng cả `S3_ML_SECRET_KEY` và URL Redis (B-23). Đề xuất: thêm một câu "con nhận env lọc theo danh sách cho phép (`S3_*` của `ml`, `REDIS_*`, `TRAINING_*`, `ML_*`)". Lỗ code ứng với nợ này đã mở `SEC-020`.
- **Công bằng hàng ML giữa các dự án** (BE-00 §7, hàng `ml.infer`/`ml.training`, B-26): hiến chương không đặt hạn mức/hàng theo dự án; chỉ có `rate_limit` khởi tạo theo người dùng. Đề xuất: ghi mục tiêu "dự án A không làm đói dự án B" thành luật có số đo (hạn mức lượt dở/dự án) hoặc ghi rõ chấp nhận ở v1.
- **Redis ACL** (BE-00 §7, dòng "Không tin `apps/ml`": "Redis ACL để v2"): `ml` dùng chung Redis với mọi dịch vụ không giới hạn khoá. Đã là lỗ có chủ ý của v1, ghi nhận ở STRIDE (api → hàng đợi → worker · S), không mở `SEC-*`.

### Việc C

1. **Sao lưu mã hoá không bắt buộc ở production.** `backup.sh:24` mặc định `BACKUP_AGE_RECIPIENT` rỗng và ghi bản rõ; "bắt buộc mã hoá" chỉ nằm trong runbook (`deploy/scripts/README.md:283`, B0-10 [6]); BE-00 không nhắc `age`. Đề xuất: BE-00 §13 thêm luật "ở `staging`/`production`, `backup.sh` thoát 2 khi thiếu `BACKUP_AGE_RECIPIENT` (trừ khi đặt cờ cho phép bản rõ tường minh)" và khai biến trong `env.example`. (C-18)
2. **BE-00 §11 không ghi hạn mức cho N3, #5, #44, #45, #37, SSE, `health_ready`** (chỉ có số cho N8–N10, N13, N14, đăng nhập, refresh). Mã đang dùng 60/3600 s, 60/600 s, 30/3600 s, 120/60 s, 6 và 500 kết nối, 60/60 s. Đề xuất: thêm bảng số liệu vào §11. (C-30..C-37)
3. **Không hạn mức tầng nginx.** Không có `limit_req`/`limit_conn` (C/L-03); chống lạm dụng chỉ ở app, `/api/files/{token}` và các GET công khai không có hạn mức. Đề xuất: hiến chương ghi rõ quyết định, hoặc thêm `limit_conn` cho `/api/streams/`.
4. **Bộ che log chỉ phủ khoá dict + ba mẫu chuỗi.** BE-00 §11 không đòi che bí mật nhúng trong chuỗi tự do (URL kết nối, `password=…`); đề xuất mở rộng luật, `SEC-042` thực thi phần URL. (C-06)
5. **`env.example` có giá trị mẫu hợp lệ về độ dài** (`SECRET_KEY` 33 byte): hiến chương §5/§13 nên cấm khoá mẫu ngoài dev (→ `SEC-041`).
6. **W23 "≥ 60 phút, làm tròn theo giờ"** thực tế cho 60–120 phút (đo 60,5 phút lúc 00:59:30); đề xuất ghi "60–120 phút". (C-19)
7. **Chính sách miễn `.gitleaks.toml`** theo SHA cố định: mỗi test mới có chuỗi giống khoá lại làm cổng lịch sử đỏ (11 phát hiện, `SEC-043`); đề xuất chọn một cách miễn thống nhất (dòng `gitleaks:allow`).
8. **Tên test C11 của N14** (`test_me_replace_avatar_rate_limited`) không mang mã `C11` nên `case_gate` không đếm; đề xuất CASE §2 nhắc quy ước đặt tên cho test hạn mức. (C-29; chủ B1-04)

### Việc D

- BE-00 §11 nên ghi rõ ai chịu header B0-06 trên phản hồi do nginx tự sinh (413/503): hiện luật chỉ nói "header B0-06" mà không giao snippet lỗi của nginx (dẫn D-05, SEC-060).
- BE-00 §9 đòi `HF_HUB_OFFLINE=1` nhưng không nói đặt ở đâu (mã hay compose); đề xuất ghi "đặt trong mã `training_segformer` như `_OFFLINE_ENV` của YOLO" (D-21).
- BE-00 thiếu luật ngưỡng `trivy` (hiện CRITICAL + `--ignore-unfixed` do B0-09 tự chọn) và luật "secret CI chỉ ở Environment" áp cho workflow chỉ gửi thông báo (D-17, D-22).
- BE-00 thiếu luật mang giấy phép dataset/bản ghim tới phiên bản kích hoạt (D-24, D-25).
