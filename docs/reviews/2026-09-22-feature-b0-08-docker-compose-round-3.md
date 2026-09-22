# Review merge feature/b0-08-docker-compose → main (lượt 3)

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, lượt 3 (không phải tác giả, không phải reviewer lượt 1–2; mọi khẳng định trong `bao-cao-f2-full.md` đều tự kiểm lại bằng diff, cổng và probe) · Commit đầu nhánh: `a8413c7211eb` (đã gộp `main` @ `4d3df23` ở `196322d`; `main` chưa đi thêm, merge-base = `4d3df23`). `git diff main...HEAD`: 36 tệp, +3 690 dòng, 0 xoá. Phạm vi soát kỹ lượt này: `git diff 6179f57..HEAD -- . ':!packages' ':!apps' ':!tools' ':!docs'` (16 tệp, +409/−94; `DEBT.md` và các tệp ngoài `deploy/` trong khoảng này chỉ là phần gộp `main`, `git diff main HEAD -- DEBT.md packages apps tools docs` rỗng).
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trên `a8413c7`, worktree sạch trước và sau; log host `.cache/src-out/verify/20260922T081739Z-a8413c7211eb.log`, bản sao `docker logs -f` của container `appback-verify-b0-08-m-merge-verify-run-53c2458553fa` ở scratchpad của phiên; `MSYS_NO_PATHCONV=1 docker wait` = 0; lúc khởi động có 0 container `verify-run`): `2285 passed, 10 skipped, 1 deselected` (375,3 s). `deploy/tests` 143 test đều xanh: compose 59, dockerfiles 35, entrypoint 2, env 5, minio_init 3, minio_policy 10, nginx 23, readers 6.
- Độ phủ: tổng dòng **99,35 %** · nhánh **97,54 %** · tập file bị chạm 100 % / 100 % (`deploy/` ngoài `[tool.coverage.run] source` — cấu hình B0-01, như lượt 1–2).

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (349 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (282 file) |
| 4 | `lint-imports` | đạt (9 giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 | đạt (H3/H4/H5 `không áp dụng` hợp lệ — B1-02/B3-05/B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill, toàn nhánh)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (trước, sau verify, sau mọi probe) |
| `changes/B0-08.md` | có, 10 dòng (thêm ý khoá app của F3) |
| Dòng đầu Conventional Commits ≤ 72 | đạt — 17 commit không-merge đúng mẫu (dài nhất 69) |
| Trailer `Prompt:` | 15/17 đọc được `B0-08` (`051d830`, `a8413c7`, merge `196322d` đều đọc được); `bb6a459`, `c1eb231` vẫn rỗng — Nit #11 lượt 1, gộp squash |
| Đụng file cấm ([12] prompt, B0-01 [7]) | không — `git diff --name-only main...HEAD` 36 tệp đều trong `so_huu` (tệp mới `deploy/minio/app-policy.json` thuộc `deploy/minio`); `verify.Dockerfile`, `verify.yml`, `DEBT.md`, `uv.lock` không trong diff |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | không — 5 `# noqa: S108`/`S603` đều có mã |
| `conftest.py` lồng, cấu hình công cụ riêng | không |

AST 14 tệp `.py` của `deploy/` (container `appback-api:dev`, worktree mount chỉ đọc): **0** hàm/lớp thiếu docstring, không hàm nào > 50 dòng; ≈ 1 710 dòng Python không trống/không comment.

## Đối chiếu khối [9] (cấm tuyệt đối)

| Luật | Kết quả |
|---|---|
| K15 `location` trỏ thư mục lưu trữ, `autoindex` | không có |
| K29 `opencv-python` GUI | không |
| Root / `latest` / bí mật trong Dockerfile, compose, `env.example` | không — `appback-web:dev` chạy `uid=10001 gid=0`; `env.example` chỉ placeholder `change-me-*` |
| `packages/testing` trong ảnh chạy | không |
| CORS cho `/api`, `proxy_intercept_errors on` | không |
| Sửa `verify.Dockerfile`, `verify.yml` | không |
| Đẩy ảnh lên registry | không có dấu vết |

## Probe tại chỗ (lượt 3)

Không build, không push, không sửa repo. Ảnh `appback-web:dev` (dựng 07:36Z) — `cmp` từng tệp `/etc/nginx/appback/**` và `15-s3-public-host.envsh` trong ảnh với `deploy/nginx/` của `a8413c7`: **trùng hết**; `/etc/nginx/conf.d` trống trước entrypoint; `HEALTHCHECK` có `StartInterval=2s`. Mạng tạm `rv3-b008-net`, volume chứng chỉ tự ký `rv3-b008-certs`, container `rv3-minio`, `rv3-web`, project compose `rv3-b008` — đã xoá hết (`docker ps -a`/`volume ls`/`network ls` không còn `rv3`).

- **P1 (#14, app-policy).** MinIO `RELEASE.2025-09-07T16-13-09Z` (alias mạng `minio`), `init.sh` + hai mẫu chính sách của nhánh mount chỉ đọc vào `mc RELEASE.2025-08-13T08-35-41Z`, ba khoá khác nhau: lượt 1 rc 0, lượt 2 rc 0. Khoá app: `ls`/`put users/1/a`/`cat projects/1/x.glb`/`rm` trên `appback` **đạt**; `put`/`cat`/`ls` bucket `otherbucket`, `mb newbucket`, `mc admin user list`, `mc admin policy list`, `mc anonymous set` → **bị từ chối**. Khoá `ml`: đọc `projects/…` và `admin user list` → bị từ chối. `web` prod (template `prod`, `S3_PUBLIC_ENDPOINT=https://s3.example.com:18443`, `server_name s3.example.com;`, `healthy`); URL ký bằng **khoá app** (`minio` 7.2.20 trong `appback-api:dev`, `presigned_get_object`, 2 giờ): GET qua vhost **200**, PUT 403, HEAD 403 (chữ ký cho GET); `docker stop` MinIO → GET **502**; `docker logs rv3-web | grep -c X-Amz-Signature` = **0**, `grep -c <chữ ký thật>` = **0**.
- **P2 (#16 và phần dư).** Server app prod 8443, không có `api`, mỗi đường một token riêng:

  | Đường (`--path-as-is`) | Kết quả | Token trong `docker logs` |
  |---|---|---|
  | `/api/files/…`, `//api/files/…`, `/api//files/…`, `/api/%66iles/…` | 503 JSON W7 | **0** |
  | `/api/./files/…`, `/api/x/../files/…`, `/%61pi/files/…`, `/api%2Ffiles/…` | 503 JSON W7 (vào `location /api/files/`: error log không có token) | **1** mỗi đường — dòng access log (finding #22) |
  | `/API/files/…` | 200 SPA (location `/`) | 0 |
- **P3 (cổng 8080 prod).** `http://app.example.com:18088/api/files/<token>` → 301, token **có** trong access log; URL ký đổi sang `http://s3.example.com:18088/…` → 301, chữ ký **có** trong access log (finding #21).
- **P4 (#15, #17, #20 — stack dev thật).** `env.example` sao nguyên xi, chỉ đổi hai cổng host bận (`WEB_HTTP_PORT=18080`, `POSTGRES_HOST_PORT=15432`; `netstat`: chỉ 8080 và 5432 bận) và điền `APPFRONT_CONTEXT`/`APPFRONT_SHA` (để trống theo thiết kế, `:?` bắt buộc cả khi không build). `docker compose -p rv3-b008 … -f deploy/compose/dev.yml up -d --no-build --pull never --wait` → **rc 0**: `minio-init` Exited **0** (log: thêm user `change-me-api-access`, `change-me-ml-access`, tạo và gắn `app-policy`, `ml-policy`), `migrate` Exited 0, `api`/`worker`/`web`/`postgres`/`redis-*`/`minio`/`mailpit` healthy (`web` healthy sau ≈ 17 s). `api` chạy với `S3_ACCESS_KEY=change-me-api-access` (không phải root); `GET http://localhost:18080/api/ready` → **200** `{"status":"ok"}`, `/api/health` 200, `/projects/1` 200 + CSP + `nosniff`. `run --rm --no-deps minio-init` lượt hai → rc **0**. `/api/files/RV3TOKENZZZ` → 0 dòng; `/api/./files/…`, `/%61pi/files/…` → 1 dòng mỗi đường (khớp P2). `down -v` → rc 0. `docker compose config --profile '*'` với cùng env: `ml`, `ml-gpu` ở dev/ci/prod đều có đủ 5 khoá `CELERY_VISIBILITY_TIMEOUT_S`/`TASK_*`/`STREAM_MAXLEN` với mặc định `7200/3600/3300/10,60,300/1000`; `ml` nhận `S3_ACCESS_KEY=change-me-ml-access` (khoá riêng), `minio-init` nhận đủ ba khoá và mount `app-policy.json`.
- **Đối chiếu `app-policy.json` với mã.** `packages/storage/s3.py` dùng `put_object` (kể cả multipart → `s3:PutObject`, lỗi → `s3:AbortMultipartUpload`), `stat_object`/`get_object` (`s3:GetObject`), `remove_object`/`remove_objects` (`s3:DeleteObject`), `list_objects` (`s3:ListBucket`), `presigned_get_object` (ký tại chỗ; `factory.py:25` truyền `region` nên không gọi `GetBucketLocation`). `ensure_bucket` (`CreateBucket`, `PutBucketCors`) không có lời gọi nào ngoài test — chính sách không cấp là đúng. Chỉ `Allow`, một bucket (`__BUCKET__` → `S3_BUCKET` qua `render_policy`), không `s3:*`, không `admin:*`.

## Kiểm từng finding lượt 2 (diff `6179f57..a8413c7` + probe)

| # | Mức | Kết quả | Bằng chứng |
|---|---|---|---|
| 14 | P1 | **đã sửa thật** | `minio.conf.template:33-34` `access_log off;` + `error_log … crit;` trong `location /` (kế thừa vào `limit_except`); test `test_nginx_minio_vhost_disables_access_log_and_elevates_error_log`; probe P1: 0 dòng chứa chữ ký (GET 200, GET 502 khi MinIO dừng, PUT 403). Đường `http://` qua cổng 8080 còn lộ — #21, P3 |
| 15 | P2 | **đã sửa thật** | `env.example:33-54` placeholder đôi một khác nhau + comment "ba khoá PHẢI khác nhau"; F3 `init.sh:41,45-46` cấp danh tính + `app-policy` cho khoá app (trước đó `/api/ready` chỉ 200 nhờ khoá app trùng root); test `test_env_example_secrets_use_distinct_placeholders`, `test_minio_init_*`, `test_minio_app_policy_*`; probe P4: stack dev lên, `minio-init` 0 (hai lượt), `/api/ready` 200 bằng khoá app |
| 16 | P3 | **đã sửa cho ba dạng nêu tên** | `dev/app.conf.template:27`, `prod/app.conf.template:26` regex `~*^/+api/+(?:f\|%66)…`; test `test_nginx_access_log_map_matches_malformed_files_paths`; probe P2: 3 dạng + dạng chuẩn = 0 dòng. Dạng khác vẫn lọt — #22, P3 |
| 17 | P3 | **đã sửa thật** | `base.yml:14-19` anchor `&celery-task-env`, dùng ở `&app-env` (`:108`) và `ml`/`ml-gpu` (`:186`, `:213`); test `test_compose_ml_env_has_celery_task_stream_vars`; probe P4 `compose config` |
| 18 | P3 | **đã sửa thật** | `test_minio_init.py:14` docstring; AST 0 hàm thiếu |
| 19 | Nit | **đã sửa thật** | `web.Dockerfile:20-23` comment đúng uid 101; test so từng lệnh `RUN` với `\brm\b` + `default.conf` |
| 20 | Nit | **đã sửa thật** | `web.Dockerfile:39` `--start-interval=2s` (ảnh: `StartInterval=2000000000`); test `test_dockerfile_web_healthcheck_has_start_interval`; probe P4 `web` healthy ≈ 17 s |

## Kiểm lời giải nợ chủ B0-08

| Nợ | Kết quả |
|---|---|
| `NO-006` | **đã giải** (như lượt 2) |
| `NO-021` | **đã giải đủ** — #17 đóng phần `ml`/`ml-gpu` còn thiếu ở lượt 2; người điều phối đóng khi hợp nhất |
| `NO-062` | **đã giải** (như lượt 1) |
| `NO-083..NO-086`, `NO-091` | có trên `main`, đủ cột; không nợ P0/P1 nào đang mở. Báo cáo F2/F3 không nêu nợ mới |

## Finding

Finding lượt 1–2 đã đóng xem bảng trên; dưới đây chỉ finding còn hiệu lực hoặc mới (đánh số tiếp từ #21).

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 21 | P3 | SEC-13 · BE-00 §8 | **Server chuyển hướng 8080 của prod ghi token và URL ký vào access log.** Server `listen 8080 default_server; return 301 …` dùng `access_log` mặc định của ảnh nền (`$request` nguyên văn), không qua map `$appback_access_log` và không có `access_log off` như vhost MinIO. Probe P3: `http://…/api/files/<token>` và URL ký đổi sang `http://s3-host/…?X-Amz-Signature=…` đều 301 và đều để lại token/chữ ký trong `docker logs web`. Chỉ xảy ra khi client gọi bằng `http://` (HSTS chặn phần lớn trình duyệt sau lượt đầu; `S3_PUBLIC_ENDPOINT` prod là `https`), nên không chặn | `deploy/nginx/templates/prod/app.conf.template:31-34` | `access_log off;` trong server 8080 (server chỉ trả 301, không có gì đáng ghi); test tĩnh: server `listen 8080` của template prod có `access_log off` |
| 22 | P3 | SEC-13 · R-19 | **Phần dư của #16: map trên `$request_uri` thô vẫn lọt dạng méo khác.** nginx chuẩn hoá `$uri` (giải `%XX`, gộp `/./`, `/../`) trước khi chọn location, nên `/api/./files/…`, `/api/x/../files/…`, `/%61pi/files/…`, `/api%2Ffiles/…` đều vào `location /api/files/` (probe P2: error log sạch, tức đúng location có `crit`) nhưng regex không khớp → access log ghi token (probe P2 và P4, 1 dòng mỗi đường). Đoán dạng URI thô bằng regex là vá triệu chứng: mỗi lượt lại có dạng mới. Cùng điều kiện với #16 (chỉ người giữ token tự gửi URL méo), nên không chặn | `deploy/nginx/templates/{dev,prod}/app.conf.template:25-28/24-27`, `deploy/nginx/snippets/app_locations.conf:17,37-41` | Quyết định ở mức location (đã chuẩn hoá) thay vì map: trong `location /api/files/` thêm `access_log off;` và `error_page 502 503 504 =503 /__errors/503-files;`, thêm `location = /__errors/503-files { internal; access_log off; … }` cùng thân W7 (tách thân 503 thành snippet để không lặp); khi đó bỏ map `$appback_access_log`. Probe lại bốn dạng trên + ba dạng #16 với `docker logs web \| grep -c` = 0 |
| 23 | P3 | SEC-09 · OPS-02 | **Đổi access key ID không thu hồi danh tính cũ.** `init.sh` chỉ `mc admin user add` + gắn chính sách cho khoá **hiện tại**; khi đổi `S3_ACCESS_KEY` (hay `S3_ML_ACCESS_KEY`) — cách xoay khoá thường gặp khi khoá bị lộ — user cũ vẫn còn trong IAM của MinIO với `app-policy` (đọc/ghi/xoá toàn bucket), secret cũ vẫn dùng được. F3 thêm danh tính quyền rộng nhất sau root nên hệ quả lớn hơn khoá `ml` | `deploy/minio/init.sh:41-50`; `deploy/compose/env.example:33-38` | Ít nhất: một dòng comment trong `env.example` ("đổi access key thì `mc admin user remove local <khoá cũ>`"); tốt hơn: `init.sh` gỡ user nào đang giữ `app-policy`/`ml-policy` mà không phải khoá hiện tại (`mc admin policy entities local --policy app-policy`) |
| 24 | Nit | MNT-04 | Docstring `test_dockerfile_web_healthcheck_has_start_interval` ghi "`docs/charter/ENV.md` §… đã đo nhận cờ này" — `ENV.md` không đo `--start-interval` (chỉ ghi Docker Desktop 29.6.1, dòng 19), và `§…` là chỗ trống. Cờ thật sự chạy (probe P4) | `deploy/tests/test_dockerfiles.py:231-232` | Sửa thành "Docker Engine ≥ 25 (máy đo: 29.6.1, `ENV.md`)" |
| 25 | Nit | least privilege | `app-policy.json` cấp `s3:GetBucketLocation`, `s3:ListBucketMultipartUploads`, `s3:ListMultipartUploadParts` mà không lời gọi nào của `packages/storage` dùng (`factory.py:25` truyền `region`; `put_object` của `minio` không liệt kê upload/part). Chỉ là đọc siêu dữ liệu trong chính bucket, vô hại | `deploy/minio/app-policy.json:6,16` | Bỏ ba hành động (và sửa hai test tập-bằng), hoặc ghi lý do giữ |

Finding lượt 1 còn hiệu lực: #6 P2 MNT-05 (đã chấp nhận `NO-091` `➖`; nhánh nay +3 690 dòng), #11 Nit.

## Điểm

Nit không trừ điểm; #6 tính là P2 đã có dòng `DEBT.md`.

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 (P3 #21, #22, #23) | 1,00 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 (#15, #17, #20 đã đóng) | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #6 đã chấp nhận; Nit #11, #24) | 0,09 |

Tổng: 1,00 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **4,69 / 5**

## PHÁN QUYẾT: APPROVE

Vòng sửa F2/F3 là thật: cổng xanh (mã thoát 0, 8/8, 2285 passed, 99,35 % / 97,54 %), P1 #14 tái hiện được là đã đóng (URL ký qua vhost MinIO: GET 200/502, PUT 403, 0 dòng lộ chữ ký), #15 đóng đến tận gốc (placeholder phân biệt **và** `minio-init` cấp danh tính + chính sách riêng một bucket, không quyền quản trị cho khoá app — stack dev từ `env.example` nguyên xi lên, `/api/ready` 200 bằng khoá app), #16–#20 đều sửa thật. Không P0/P1, điểm ≥ 4,0 → APPROVE theo RULE.md §5.

Không có điều kiện chặn merge. P3 #21–#23 và Nit #24–#25 do tác giả/người điều phối quyết: không sửa trước merge thì người điều phối ghi mỗi P3 một dòng `DEBT.md` chủ B0-08 (R-34). Khi merge: gộp **squash** (một prompt, R-36), thân có `Prompt: B0-08` đúng khối trailer (R-36b); đóng `NO-006`, `NO-021`, `NO-062` cùng lúc.
