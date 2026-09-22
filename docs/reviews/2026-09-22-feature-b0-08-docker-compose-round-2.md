# Review merge feature/b0-08-docker-compose → main (lượt 2)

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, lượt 2 (không phải tác giả, không phải reviewer lượt 1; mọi khẳng định trong `bao-cao-f-full.md` đều tự kiểm lại bằng diff, cổng và probe) · Commit đầu nhánh: `6179f57ec9e7` (đã gộp `main` @ `24b0027`). `main` đã đi thêm 4 commit (`2debb52`, `47efe53`, `9cb9f6a`, `9a7ec9b` — `tools/verify/run.sh`, fixture messaging, `DEBT.md`, phán quyết; không chạm `deploy/`); `git merge-tree main HEAD` sạch; `git diff main...HEAD`: 35 tệp, +3 375 dòng, 0 xoá.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trên `6179f57`, worktree sạch trước và sau; log host `.cache/src-out/verify/20260922T065757Z-6179f57ec9e7.log`, bản sao `docker logs -f` ở scratchpad của phiên; `docker wait` = 0): `2271 passed, 10 skipped, 1 deselected` (316,5 s). `deploy/tests` 130 test đều xanh: compose 56, dockerfiles 34, entrypoint 2, env 4, minio_init 2, minio_policy 5, nginx 21, readers 6.
- Độ phủ: tổng dòng **99,35 %** · nhánh **97,54 %** · tập file bị chạm 100 % / 100 % (`deploy/` ngoài `[tool.coverage.run] source` — cấu hình B0-01, như lượt 1).

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (347 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (282 file) |
| 4 | `lint-imports` | đạt (9 giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 | đạt (H3/H4/H5 `không áp dụng` hợp lệ — B1-02/B3-05/B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (trước, sau verify, sau mọi probe) |
| `changes/B0-08.md` | có, 9 dòng |
| Dòng đầu Conventional Commits ≤ 72 | đạt — 15 commit không-merge đúng mẫu |
| Trailer `Prompt:` | 13/15 đọc được `B0-08` (3 commit mới `0db20d0`, `29a59eb`, `6179f57` đều đọc được); `bb6a459`, `c1eb231` vẫn rỗng — Nit #11 lượt 1, gộp squash |
| Đụng file cấm ([12] prompt, B0-01 [7]) | không — 35 tệp đều trong `so_huu`; `verify.Dockerfile`, `verify.yml`, `DEBT.md` không trong diff |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / `xfail` / hạ ngưỡng | không — 3 `# noqa: S108`/`S603` có mã và lý do |
| `conftest.py` lồng, cấu hình công cụ riêng | không |

AST 14 tệp `.py` của `deploy/` (container `appback-api:dev`, worktree mount chỉ đọc): không hàm nào > 50 dòng; **1** hàm thiếu docstring (`_script_text`, finding #18); ≈ 1 513 dòng Python không trống/không comment.

## Đối chiếu khối [9] (cấm tuyệt đối)

| Luật | Kết quả |
|---|---|
| K15 `location` trỏ thư mục lưu trữ, `autoindex` | không có |
| K29 `opencv-python` GUI | không — kiểm cuối tầng `ml` nay chặn cả `opencv-contrib-python` |
| Root / `latest` / bí mật trong Dockerfile, compose, `env.example` | không — `USER 10001` tầng cuối cả 4 ảnh; `appback-web:dev` chạy `uid=10001 gid=0`; `env.example` chỉ `change-me` |
| `packages/testing` trong ảnh chạy | không |
| CORS cho `/api`, `proxy_intercept_errors on` | không |
| Sửa `verify.Dockerfile`, `verify.yml` | không |
| Đẩy ảnh lên registry | không có dấu vết |

## Probe tại chỗ (lượt 2)

Không build, không push, không sửa repo. Ảnh `appback-web:dev` (dựng 13:45, sau `0db20d0` 13:30) — đã `cmp` từng tệp `/etc/nginx/appback/**` và `15-s3-public-host.envsh` trong ảnh với `deploy/nginx/` của `6179f57`: **trùng hết**. Mạng tạm `rv2-b008-net`, volume chứng chỉ tự ký `rv2-b008-certs`, cổng host 18091 — đã xoá hết.

- **R1 (#1).** `/etc/nginx/conf.d` của ảnh chỉ còn trống trước entrypoint (không `default.conf`). Không có `api`:

  | `Host` | `/api/health` | `/projects/1` | `/` |
  |---|---|---|---|
  | `localhost:18091` | 503 JSON W7 + `Retry-After: 5` | 200 + CSP + `nosniff` | 200 + CSP + `nosniff` |
  | `127.0.0.1:18091` | 503 JSON W7 | 200 + CSP | 200 + CSP |
- **R2 (#2).** `GET /api/files/SECRETAAA…` → 503 JSON; `docker logs` **0** dòng chứa token (error log `crit` giữ). Nhưng các dạng không chuẩn vẫn vào đúng `location /api/files/` (503 qua proxy) mà **access log** ghi nguyên token: `//api/files/SECRETBBB…`, `/api//files/SECRETDDD…`, `/api/%66iles/SECRETCCC…` — 3 dòng `"GET …SECRET… HTTP/1.1" 503` (finding #16).
- **R3 (#3, #4).** Template `prod`, chứng chỉ tự ký, health-cmd đúng `prod.yml` (`curl -kfsS -o /dev/null https://127.0.0.1:8443/index.html`): `S3_PUBLIC_ENDPOINT=https://s3.example.com` → `healthy`, `server_name s3.example.com;`; `S3_PUBLIC_ENDPOINT=` rỗng → `nginx -t` đạt, `server_name _;`, `healthy`, `RestartCount=0`. `:8080` → 301 `https://127.0.0.1/`. Dev: HEALTHCHECK của ảnh → `healthy`. `docker compose … config` với `env.example` (điền `APPFRONT_*`) đạt cả dev/ci/prod; `web` prod ra healthcheck `curl` 8443, dev/ci không khai (dùng của ảnh).
- **R4 (#8, #9).** MinIO `RELEASE.2025-09-07T16-13-09Z` + `mc RELEASE.2025-08-13T08-35-41Z` (`sh` = bash 5.1.8), `init.sh`/`ml-policy.json` của nhánh mount chỉ đọc, chạy hai lượt với hai `S3_ML_SECRET_KEY`: cả hai rc 0. Khoá cũ → đọc `pages/0.png` **bị từ chối**; khoá mới: đọc `pages/*` đạt, ghi `runs/*`, `ml/models/*` đạt; ghi `…/original.png`, đọc `users/…`, đọc/ghi bucket `otherbucket`, xoá `runs/*` → **bị từ chối**.
- **R5 (mới).** Vhost MinIO prod, `GET https://s3.example.com:8443/appback/projects/1/x.glb?X-Amz-Signature=SIGSECRET123&X-Amz-Credential=AKIA` → `docker logs` **2** dòng chứa chữ ký: dòng access log `"GET /appback/…?X-Amz-Signature=SIGSECRET123&X-Amz-Credential=AKIA HTTP/2.0" 502` và dòng `[error] … minio could not be resolved … request: "GET …X-Amz-Signature=…"`. Bản sao cấu hình ở scratchpad thêm `access_log off;` + `error_log /var/log/nginx/error.log crit;` vào `location /` của vhost → `nginx -t` đạt, GET 502/PUT 403 như cũ, **0** dòng chứa chữ ký (finding #14).

## Kiểm từng finding lượt 1 (diff `2b091ff..6179f57` + probe)

| # | Mức | Kết quả | Bằng chứng |
|---|---|---|---|
| 1 | P1 | **đã sửa thật** | `web.Dockerfile:22` `RUN rm /etc/nginx/conf.d/default.conf`; test `test_dockerfile_web_removes_base_image_default_server`; probe R1 |
| 2 | P1 | **đã sửa thật** (cho đường chuẩn) | `app_locations.conf:38` `error_log … crit`; test `test_nginx_files_location_elevates_error_log_level`; probe R2 — còn đường không chuẩn qua access log (#16, P3) |
| 3 | P1 | **đã sửa thật** | `base.yml:231-233` bỏ healthcheck `web`; `prod.yml:179-187` `curl -kfsS https://127.0.0.1:8443/index.html`; test `test_compose_web_healthcheck_single_source`; probe R3 `healthy` |
| 4 | P2 | **đã sửa thật** | `15-s3-public-host.envsh:11-20` rỗng → `_`; test chạy thật script bằng `sh`; probe R3 |
| 5 | P2 | **đã sửa** | mỗi sửa #1–#4 có test tĩnh; `bao-cao-f-full.md` dán lại [8].3 qua `http://localhost:18080` và `web` prod tới `healthy`; probe R1–R3 của phiên này khớp |
| 6 | P2 | **đã ghi** | `NO-091` `➖` trên `main` (`621fc3e`) |
| 7 | P3 | **đã sửa thật** | `test_dockerfile_ml_cuda_torch_versions_match_uv_lock` đối chiếu `uv.lock` |
| 8 | P3 | **đã sửa thật** | `init.sh:19` `mc admin user add` vô điều kiện; probe R4 khoá cũ bị từ chối |
| 9 | P3 | **đã sửa thật** | `ml-policy.json` giữ chỗ `__BUCKET__`, `init.sh:24-26` sinh bản thật vào `/tmp`; probe R4 bucket khác bị từ chối |
| 10 | P3 | **sửa phần lớn** | `base.yml:93-98` + `env.example:21-27` cho `migrate`/`api`/`worker`/`beat`; `ml`, `ml-gpu` vẫn không nhận (#17) |
| 11 | Nit | giữ nguyên (đúng phán quyết lượt 1) | gộp squash |
| 12 | Nit | **đã sửa** | kiểu trả `Iterator[Node]`, `Callable[[Node], bool]` |
| 13 | Nit | **đã sửa** | `_OPENCV_BAD` + `ml.Dockerfile:71-72` chặn `opencv-contrib-python` |

## Kiểm lời giải nợ chủ B0-08

| Nợ | Kết quả |
|---|---|
| `NO-006` | **đã giải** — `base.yml:99-106` (`&app-env`), `env.example` nhóm lưu trữ |
| `NO-021` | **giải gần đủ** — hai Redis tách đúng; `CELERY_VISIBILITY_TIMEOUT_S`, `TASK_*`, `STREAM_MAXLEN` có mặc định khớp `packages/messaging/settings.py` (validator `NoDecode` nhận `10,60,300`; `SECRET_KEY_PREVIOUS` rỗng → `()`), tới `migrate`/`api`/`worker`/`beat`; `ml`/`ml-gpu` ở dev/ci chưa nhận (#17). Người điều phối đóng kèm ghi chú #17 hoặc chờ sửa |
| `NO-062` | **đã giải** (như lượt 1) |
| `NO-083..NO-086`, `NO-091` | có trên `main`, đủ cột; không nợ P0/P1 nào đang mở |

## Finding

Các finding lượt 1 đã đóng xem bảng trên; dưới đây chỉ finding còn mở hoặc mới (đánh số tiếp từ #14).

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 14 | **P1** | SEC-13 · BE-00 §8 | **URL ký S3 (quyền đọc tệp 2 giờ) vào log của nginx ở prod.** Vhost MinIO không đổi `access_log`, nên log `main` của ảnh nền ghi nguyên `$request` kèm query `X-Amz-Signature`/`X-Amz-Credential` cho **mỗi** lượt GET; khi `minio` không tới được, error log cũng ghi lại (probe R5: 2 dòng). Đây là cùng một khả năng như token `/api/files/` — cùng cổng `ObjectStorage.signed_url`, cùng `SIGNED_URL_TTL = 2h` (`packages/storage/port.py:32`) — mà BE-00 §8:387 cấm vào log và lượt 1 đã xếp P1 (#2) cho biến thể hiếm hơn (chỉ khi `api` gián đoạn). MinIO tự chạy là cấu hình v1 bắt buộc cho `ml` (BE-00 §9), nên mọi lượt xem tệp ở prod đều để lại một URL dùng được 2 giờ trong `docker logs web`. Lượt 1 bỏ sót | `deploy/nginx/templates/prod/minio.conf.template:25-33` | Trong `location /` của vhost: `access_log off;` (hoặc `log_format` riêng không có `$request`/`$args`) và `error_log /var/log/nginx/error.log crit;` — probe R5: `nginx -t` đạt, 0 dòng lộ, GET/PUT giữ hành vi; test tĩnh trong `test_nginx.py`: location của vhost MinIO có `access_log off` và `error_log` mức `crit`/`alert`/`emerg`; sửa comment đầu template |
| 15 | P2 | OPS-02 · R-34 | **Sao `env.example` nguyên xi thì `minio-init` hỏng và dev/ci không lên.** `S3_ML_ACCESS_KEY`, `MINIO_ROOT_USER` cùng `change-me` → `mc admin user add` bị MinIO từ chối ("Credential is not allowed to be same as admin access key"), `api`/`worker`/`ml` đợi `service_completed_successfully` nên đứng mãi. Tác giả tự thấy và ghi trong báo cáo ("Lệch khỏi prompt") nhưng gọi là "quan sát, không phải nợ" và không có dòng `DEBT.md`; lý do "mọi placeholder phải như nhau theo K" không đứng — K chỉ cấm bí mật thật, placeholder khác nhau vẫn là placeholder | `deploy/compose/env.example:36,41,45`; `deploy/minio/init.sh:19` | Placeholder phân biệt (`change-me-api`, `change-me-ml`, `change-me-root`, mật khẩu ≥ 8 ký tự) và một dòng comment "ba khoá phải khác nhau"; test tĩnh `S3_ML_ACCESS_KEY != MINIO_ROOT_USER`. Không sửa thì ghi `DEBT.md` (R-34) |
| 16 | P3 | SEC-13 | `map $request_uri $appback_access_log` chỉ khớp chữ `^/api/files/`; `//api/files/…`, `/api//files/…`, `/api/%66iles/…` vẫn vào `location /api/files/` (nginx chuẩn hoá `$uri`) nhưng access log ghi token (probe R2: 3 dòng). uvicorn giải mã `%66` nên dạng cuối còn được `api` phục vụ. Chỉ xảy ra khi chính người giữ token gửi URL méo, nên không chặn | `deploy/nginx/templates/dev/app.conf.template:20-23`, `…/prod/app.conf.template:19-22` | Nới regex: `"~*^/+api/+(?:f|%66)(?:i|%69)(?:l|%6c)(?:e|%65)(?:s|%73)(?:/|%2f)" 0;` và thêm 3 dạng trên vào test tĩnh của map |
| 17 | P3 | OPS-02 · NO-021 | `ml`, `ml-gpu` gọi `create_celery("ml")` (đọc `celery_visibility_timeout_s`, `task_time_limit_s`) nhưng danh sách `environment` tường minh của chúng không có các khoá #10; ở dev/ci chỉnh `CELERY_VISIBILITY_TIMEOUT_S` trong `.env` chỉ tới `worker`, còn BE-00 §7:320 lấy giá trị **nhỏ nhất** giữa các app dùng chung broker. Prod không bị (có `env_file`) | `deploy/compose/base.yml:171-184,197-210` | Thêm 5 khoá `${…:-mặc định}` vào `ml`/`ml-gpu` (hoặc anchor nhỏ dùng chung); mở rộng `test_compose_app_env_has_celery_task_stream_and_secret_previous` sang `ml` |
| 18 | P3 | R-01 | `_script_text()` không có docstring (hàm mới duy nhất thiếu, AST) | `deploy/tests/test_minio_init.py:13` | Một câu docstring |
| 19 | Nit | MNT-04 · TEST-02 | Comment "Xoá lúc còn root (trước USER 10001)" sai: `USER` của ảnh nền là `101` (`docker inspect`), lệnh chạy được vì 101 sở hữu `conf.d`. Test đi kèm chỉ `assert "rm" in run_text` — khớp mọi chữ chứa "rm" | `deploy/docker/web.Dockerfile:20-21`; `deploy/tests/test_dockerfiles.py:224` | Sửa comment ("chạy bằng uid 101 của ảnh nền, chủ `conf.d`"); assert `rm` và đường `default.conf` trong **cùng** một lệnh `RUN` |
| 20 | Nit | OPS-04 | Bỏ healthcheck `web` khỏi `base.yml` làm dev/ci dùng `HEALTHCHECK --interval=30s` của ảnh (trước là 5 s): `docker compose up --wait` và e2e F-14 chờ `web` ≥ 30 s | `deploy/docker/web.Dockerfile:38-39` | Thêm `--start-interval=2s` vào `HEALTHCHECK` của ảnh (vẫn một nguồn) |

Finding lượt 1 còn hiệu lực: #6 P2 MNT-05 (đã chấp nhận `NO-091` `➖`), #11 Nit.

## Điểm

Nit không trừ điểm; #6 tính là P2 đã có dòng `DEBT.md`.

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #14; P3 #16) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #19) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 3 (P2 #15; P3 #17; Nit #20) | 0,15 |
| MNT – Bảo trì | 3 % | 3 (P2 #6 đã chấp nhận; P3 #18; Nit #11, #19) | 0,09 |

Tổng: 0,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,15 + 0,09 = **3,84 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Vòng sửa là thật: cổng xanh (mã thoát 0, 8/8, 2271 passed, 99,35 % / 97,54 %), cả ba P1 lượt 1 (#1 `localhost`, #2 token trong error log, #3 healthcheck prod) và #4, #7–#10, #12, #13 đều tái hiện được là đã sửa bằng probe trên đúng ảnh và cấu hình của `6179f57`. Nhưng soát lại toàn nhánh thấy một P1 mới cùng loại với #2: vhost MinIO ghi URL ký S3 (quyền đọc tệp 2 giờ) vào log nginx ở **mỗi** lượt xem tệp trên prod. Theo ma trận RULE.md §5, còn P1 chưa waiver thì không merge (R-37/R-38).

Việc phải làm để được duyệt (chỉ trong file của B0-08):

1. **#14** — `access_log off;` + `error_log /var/log/nginx/error.log crit;` trong `location /` của `templates/prod/minio.conf.template`; test tĩnh đi kèm; dán probe: GET có `?X-Amz-Signature=…` qua vhost rồi `docker logs web | grep -c X-Amz-Signature` = 0.
2. **#15** — placeholder phân biệt trong `env.example` (+ test), **hoặc** một dòng `DEBT.md` (R-34) nếu không sửa.
3. Gộp `main` hiện tại (`9a7ec9b`), chạy `bash tools/verify/run.sh verify`, xin `/merge-review` lượt 3 — lượt 3 chỉ cần soát diff từ `6179f57` và probe #14.

P3 #16–#18, Nit #19–#20 do tác giả quyết, không chặn (khuyên làm #17 cùng lúc để đóng hẳn `NO-021`). Khi đã `APPROVE`: gộp **squash** (một prompt, R-36), thân có `Prompt: B0-08` đúng khối trailer (R-36b).
