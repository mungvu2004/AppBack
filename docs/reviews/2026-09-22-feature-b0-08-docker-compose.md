# Review merge feature/b0-08-docker-compose → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải tác giả; mọi khẳng định trong `bao-cao*.md`, `hop-dong.md`, `changes/B0-08.md` đều tự kiểm lại bằng diff, cổng và probe) · Commit đầu nhánh: `2b091ff4d041` (đã gộp `main` @ `8994352`; 18 commit trên `main..HEAD`). `main` đã đi thêm 2 commit (`b850ec2`, `900294a` — `packages/storage/keys.py`, không chạm `deploy/`); merge-base vẫn là `8994352`, nên `git diff main...HEAD` không đổi: 33 tệp, +3 081 dòng, 0 xoá.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trên `2b091ff`, worktree sạch; log giữ bằng `docker logs -f` ở scratchpad của phiên): `2153 passed, 10 skipped, 1 deselected` (331,9 s). 10 skip đều là `apps/api/core/tests/test_common.py` (tập tham số rỗng, có từ B0-06, nhánh không chạm). `deploy/tests` chạy đủ: compose 43, dockerfiles 32, env 3, minio 4, nginx 20, readers 6 — đều xanh.
- Độ phủ: tổng dòng **99,33 %** · nhánh **97,46 %** · tập file bị chạm 100 % / 100 %. (`deploy/` không nằm trong `[tool.coverage.run] source`, `deploy/tests/*` bị `omit` — đúng cấu hình B0-01.)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (339 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (281 file; `deploy/` ngoài `files` của mypy — xem Nit #12) |
| 4 | `lint-imports` | đạt (9 giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 | đạt (H3/H4/H5 `không áp dụng` hợp lệ — B1-02/B3-05/B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (cả trước và sau verify, sau mọi probe) |
| `changes/B0-08.md` | có, 9 dòng |
| Dòng đầu Conventional Commits ≤ 72 | đạt — 15 commit đúng mẫu; 3 commit `Merge branch '…'` do git sinh, hook `.githooks/commit-msg` cho phép |
| Trailer `Prompt:` | 13/15 commit không-merge đọc được `B0-08`; `bb6a459`, `c1eb231` có `Prompt: B0-08` nhưng tách đoạn khỏi `Co-Authored-By` → `%(trailers)` rỗng (Nit #11, R-36b). Nhánh một prompt → squash, không chặn |
| Đụng file cấm ([12] prompt, B0-01 [7]) | không — mọi tệp nằm trong `so_huu` (`.dockerignore`, `changes/B0-08.md`, `deploy/{__init__.py,tests,docker/{api,worker,ml,web}.Dockerfile,docker/web-context.sh,compose/{base,dev,ci,prod}.yml,compose/env.example,nginx,minio}`); `verify.Dockerfile`, `verify.yml`, `DEBT.md` không trong diff |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không — một `# noqa: S108` có mã và lý do (`test_compose.py:202`) |
| `conftest.py` lồng, file cấu hình công cụ riêng | không |

**AST** trên 10 tệp `.py` của diff (container `appback-api:dev`, worktree mount chỉ đọc): 0 hàm/lớp thiếu docstring, không hàm nào > 50 dòng; ≈ 1 319 dòng Python không trống/không comment.

## Đối chiếu khối [9] (cấm tuyệt đối)

| Luật | Kết quả |
|---|---|
| K15 `location` trỏ thư mục lưu trữ, `autoindex` | không có (`root` chỉ `/usr/share/nginx/html`; test `test_nginx_no_autoindex_anywhere`, `…_no_alias_directive`) |
| K29 `opencv-python` GUI | không — `uv.lock:28` override loại `opencv-python`, build `ml` tự khẳng định bằng `importlib.metadata` (`ml.Dockerfile:65-70`) |
| Root / `latest` / bí mật trong Dockerfile, compose, `env.example` | không — `USER 10001` tầng cuối cả 4 ảnh (probe `id -u` ảnh `api` = 10001); mọi `FROM` ghim tag + digest; `env.example` chỉ `change-me` |
| `packages/testing` trong ảnh chạy | không — probe `ls /app/packages` ảnh `api`, `ml`: không có `testing` |
| CORS cho `/api`, `proxy_intercept_errors on` | không |
| Sửa `verify.Dockerfile`, `verify.yml` | không |
| Đẩy ảnh lên registry | không có dấu vết |

## Probe tại chỗ

Chỉ lệnh đọc và container dùng xong xoá (`--rm`), một mạng tạm `rv-b008-net` đã xoá; không build, không push, không sửa repo. nginx chạy từ đúng ảnh nền của `web.Dockerfile` (`nginxinc/nginx-unprivileged:1.28.0-alpine@sha256:c97ff0bf…`), `--user 10001`, `deploy/nginx/` của nhánh mount chỉ đọc vào `/etc/nginx/appback`, `NGINX_ENVSUBST_TEMPLATE_DIR` như compose — ảnh `web` thật chỉ khác ở nội dung `/usr/share/nginx/html`.

- **Q1 — `default.conf` của ảnh nền còn nguyên.** `ls /etc/nginx/conf.d` → `app.conf default.conf`; `default.conf` = `listen 8080; server_name localhost; location / { root …; index index.html; }`.

  | `Host` | `/api/health` | `/projects/1` | `/` |
  |---|---|---|---|
  | `localhost:8080` | **404** (HTML) | **404** | 200, **không CSP** |
  | `127.0.0.1:8080` | 503 JSON W7 | 200 + CSP | 200 + CSP |
  | `app.example.com` | 503 JSON W7 | 200 + CSP | 200 + CSP |

  Sau `rm /etc/nginx/conf.d/default.conf` (uid 10001, gid 0 xoá được): `Host: localhost:8080` → `/api/health` 503 JSON, `/projects/1` 200 + CSP.
- **Q2 — token `/api/files/` vào error log.** Không có `api`: `GET /api/files/SECRETTOKEN0123456789` → 503 JSON đúng, nhưng `docker logs` có `[error] … api could not be resolved (2: Server failure), client: 127.0.0.1, server: , request: "GET /api/files/SECRETTOKEN0123456789 HTTP/1.1"`. Bản sao cấu hình trong scratchpad thêm `error_log /var/log/nginx/error.log crit;` vào `location /api/files/` → **0 dòng** chứa token, thân 503 không đổi.
- **Q3 — healthcheck `web` ở prod.** Template `prod`, chứng chỉ tự ký: lệnh compose `wget --spider -q http://127.0.0.1:8080/` → `Connecting to 127.0.0.1:8080` → `Connecting to 127.0.0.1 (127.0.0.1:443)` → `Connection refused`, **exit 1**. `HEALTHCHECK` của ảnh (`curl -fsS …/index.html`, không `-L`) exit 0 — nhưng compose đè nó.
- **Q4 — prod với `S3_PUBLIC_ENDPOINT` rỗng.** `/docker-entrypoint.sh nginx -t` → `minio.conf` ra `server_name ;` → `[emerg] invalid number of arguments in "server_name" directive`, **rc 1**.
- **Q5 — ảnh phiên M dựng (`appback-{api,worker,ml}:dev`).** uvicorn 0.53.0 `_TrustedHosts("192.168.200.0/24")` nhận `192.168.200.7`, từ chối `10.0.0.1` (lệch "IP tĩnh" của prompt [6] có lý do đúng); `/opt/models` của `ml` có `yolov8n.onnx`, `yolov8s.onnx`, `rapidocrRec.onnx`, `mitB0/`, `mitB1/`.

## Kiểm lời giải nợ chủ B0-08

| Nợ | Kết quả |
|---|---|
| `NO-006` (`STORAGE_*`, `S3_*`) | **đã giải** — `base.yml:83-98` (`&app-env`), `env.example:23-30` |
| `NO-021` (Redis + `CELERY_VISIBILITY_TIMEOUT_S`, `TASK_*`, `STREAM_MAXLEN`) | **giải một phần** — hai Redis tách đúng (`noeviction`+AOF / `allkeys-lru` 256mb), URL đã khai; ba nhóm biến tinh chỉnh chưa có chỗ khai ở dev/ci (#10) |
| `NO-062` (fetch/export ghim lúc build; biến `ML_*` + lõi) | **đã giải** — `ml.Dockerfile:60-61`; Q5 thấy bản ghim trong ảnh; `base.yml:162-175` khai `APP_ENV`, `PUBLIC_BASE_URL`, `SECRET_KEY`, `STORAGE_BACKEND=s3`, `ML_DEVICE`; `ML_MODELS_DIR` mặc định `/opt/models` khớp ảnh |
| `NO-083..NO-086` | có trên `main`, đủ cột, đúng các nợ báo cáo nêu (`public/models`, `ml` với S3 ngoài, `ml` cầm `SECRET_KEY`, SSE FE lệch BE-BIND) |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-06 · W19 | **Truy cập bằng `localhost` bị server mặc định của ảnh nền nuốt.** Ảnh `web` giữ `/etc/nginx/conf.d/default.conf` (`server_name localhost`, cùng `listen 8080`). nginx chọn server theo `server_name` trước `default_server`, nên mọi yêu cầu `Host: localhost[:cổng]` vào `default.conf`: `/api/*` 404 HTML, deep link SPA 404, `/` không CSP/`nosniff`/`frame-ancestors` (probe Q1). Đó đúng là URL tài liệu chọn: `PUBLIC_BASE_URL=http://localhost:8080` (`env.example:7`), e2e F-14 "vào `http://localhost:8080`" (`ci.yml:2`, prompt [6]). Healthcheck và các curl của báo cáo dùng `127.0.0.1` nên không lộ | `deploy/docker/web.Dockerfile:15-25` | Thêm `RUN rm /etc/nginx/conf.d/default.conf` ngay sau `FROM` (user 101 của ảnh nền sở hữu `conf.d`); test tĩnh: tầng cuối `web` xoá `default.conf`; chạy lại [8].3 bằng `curl http://localhost:<WEB_HTTP_PORT>` chứ không phải `127.0.0.1` |
| 2 | **P1** | SEC-13 · BE-00 §8 | **Token tệp vào log lỗi của nginx mỗi khi `api` không tới được** (DNS lỗi, `connect() failed`, timeout — tức mọi lúc `api` khởi động lại hay B0-10 đổi container). `error_log` ghi nguyên dòng `request: "GET /api/files/<token> …"` (probe Q2). BE-00 §8:387 "Token tệp không vào log"; kiểm [8].3 "`docker compose logs web` không chứa đường `/api/files/`" thực ra **không đạt**: `bao-cao-w.md` tự ghi "đã lọc dòng error_log riêng, chỉ còn dòng DNS-resolve-failure", rồi vẫn báo `đạt`. Map `$appback_access_log` chỉ chữa `access_log` | `deploy/nginx/snippets/app_locations.conf:32-35` | Thêm `error_log /var/log/nginx/error.log crit;` trong `location /api/files/` (probe Q2: 0 dòng lộ, 503 JSON giữ nguyên); test tĩnh: location `/api/files/` có `error_log … crit` (hoặc `alert`/`emerg`); sửa comment `:6-12` cho khớp |
| 3 | **P1** | OPS-04 · prompt [6] | **Healthcheck `web` ở prod luôn hỏng.** `base.yml` đè `HEALTHCHECK` của ảnh bằng `wget --spider -q http://127.0.0.1:8080/`; ở prod cổng 8080 trả 301 `https://127.0.0.1/`, busybox `wget` theo sang `127.0.0.1:443`, trong container nginx nghe `8443` → exit 1 (probe Q3). `web` ở prod vĩnh viễn `unhealthy`: `docker compose up --wait` và mọi bước chờ health của B0-10 hỏng. Báo cáo chỉ chạy `nginx -t` cho prod ([8].6), chưa từng dựng `web` prod. Hai định nghĩa healthcheck (ảnh: `curl /index.html`; compose: `wget /`) lệch nhau là gốc lỗi | `deploy/compose/base.yml:222-226`, `deploy/compose/prod.yml:168-185`, `deploy/docker/web.Dockerfile:31` | Giữ **một** nguồn: bỏ `healthcheck` của `web` khỏi `base.yml` (dev/ci dùng `HEALTHCHECK` của ảnh), và ở `prod.yml` đè `["CMD", "curl", "-kfsS", "-o", "/dev/null", "https://127.0.0.1:8443/index.html"]`; test tĩnh: healthcheck `web` ở prod không gọi `http://…:8080`; probe `docker inspect -f '{{.State.Health.Status}}'` = `healthy` với chứng chỉ tự ký |
| 4 | P2 | LOG-02 · OPS-02 | **Prod không dựng được `web` khi `S3_PUBLIC_ENDPOINT` rỗng** — cấu hình hợp lệ với `STORAGE_BACKEND=local` (settings không đòi `S3_*`; `prod.yml:99,118` mount `local-storage` cho đúng trường hợp này). Vhost MinIO nạp vô điều kiện dù prompt [6] nói "chỉ profile `minio`"; `server_name ${S3_PUBLIC_HOST};` ra `server_name ;` → `[emerg]`, `web` khởi động lại liên tục (probe Q4) | `deploy/nginx/templates/prod/minio.conf.template:16`, `deploy/nginx/docker-entrypoint.d/15-s3-public-host.envsh:10-12` | Trong `.envsh`: `[ -n "$S3_PUBLIC_HOST" ] \|\| S3_PUBLIC_HOST=_` (tên không khớp host nào, vhost thành vô hại), kèm comment; hoặc báo lỗi rõ và thoát. Probe `nginx -t` với biến rỗng |
| 5 | P2 | TEST-02 · K25 | **Bằng chứng nghiệm thu che mất #1–#3.** Bảng "Kiểm chạy thật" của `bao-cao.md` ghi `đạt` cho "log web không có `/api/files/`" dù việc W đã lọc bỏ dòng error log chứa token; mọi curl đi qua `127.0.0.1`; prod chỉ có `nginx -t`. 108 test tĩnh không bắt được lỗi nào trong ba lỗi, vì không test nào nhìn `default.conf` của ảnh nền, `error_log`, hay healthcheck của `web` | `deploy/tests/test_nginx.py`, `test_dockerfiles.py`, `test_compose.py`; báo cáo | Test tĩnh đi kèm từng sửa #1–#3 (ghi ở cột trên); chạy lại [8].3 đúng chữ (`stop api`, `GET /api/files/x`, rồi `docker compose logs web \| grep -c /api/files/` = 0, không lọc) và dán lệnh + kết quả |
| 6 | P2 | MNT-05 | Nhánh +3 081 dòng: ≈ 1 319 dòng Python (bộ đọc + test tĩnh) và ≈ 1 700 dòng Dockerfile/compose/nginx, vượt 400. **Không đáng tách:** một prompt; test tĩnh đọc chung cả bốn phần (ảnh, compose, nginx, MinIO), đã tách thành 4 nhánh con rồi mới gộp | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` (như `NO-039`, `NO-047`) |
| 7 | P3 | MNT-03 · R-07 | Biến thể CUDA ghim cứng `torch==2.14.0`, `torchvision==0.29.0` — chép lại `uv.lock:1789,1806`, không test nào đối chiếu. Lock nâng torch thì ảnh `cuda` lặng lẽ cài bản cũ (`--no-deps`, lệch ABI với torchvision/ultralytics) | `deploy/docker/ml.Dockerfile:39-44` | Test tĩnh: phiên bản trong `ml.Dockerfile` bằng `version` của `torch`/`torchvision` trong `uv.lock` (bỏ hậu tố `+cpu`) |
| 8 | P3 | LOG-02 | `minio-init` bỏ qua `mc admin user add` khi user `ml` đã có → đổi `S3_ML_SECRET_KEY` không bao giờ có hiệu lực; `ml` hỏng xác thực sau lần xoay khoá đầu tiên | `deploy/minio/init.sh:13-17` | Gọi `mc admin user add` vô điều kiện (MinIO ghi đè secret của user đã có — kiểm bằng một lượt chạy), bỏ nhánh `user info` |
| 9 | P3 | SEC-05 (least privilege) | `ml-policy.json` dùng `arn:aws:s3:::*/…`: năm tiền tố được cấp trên **mọi** bucket của MinIO, rộng hơn BE-00 §8. Lý do trong `hop-dong.md` ("ảnh mc không có sed") không đứng: `init.sh` đã chạy `sh`, heredoc với `${S3_BUCKET}` không cần sed | `deploy/minio/ml-policy.json:8-10,21-22` | `init.sh` sinh chính sách vào `/tmp` bằng heredoc (bucket thật), `mc admin policy create` từ đó; test giữ năm cặp (hành động, tiền tố) |
| 10 | P3 | OPS-02 · DEBT | `NO-021` mới giải một phần: `CELERY_VISIBILITY_TIMEOUT_S`, `TASK_*`, `STREAM_MAXLEN` không có trong `env.example` và không đi qua `&app-env` (danh sách khoá tường minh), nên dev/ci không chỉnh được nếu không sửa compose; prod thì được nhờ `env_file`. Tương tự `SECRET_KEY_PREVIOUS` (`env.example:9`) khai mà không truyền vào container dev/ci | `deploy/compose/base.yml:83-98`, `deploy/compose/env.example` | Người điều phối đóng `NO-021` kèm ghi chú này, hoặc thêm các khoá với `${…:-<mặc định>}` và dòng comment trong `env.example` |
| 11 | Nit | R-36b | `bb6a459`, `c1eb231`: `Prompt: B0-08` và `Co-Authored-By` cách nhau một dòng trống → `%(trailers:key=Prompt)` rỗng | lịch sử nhánh | Không cần sửa lịch sử: nhánh một prompt, gộp **squash** (R-36) với khối trailer đúng |
| 12 | Nit | TEST-02 | `deploy/` ngoài `files` của mypy (`pyproject.toml:81`, chủ B0-01), và `nginx_reader.walk`, `test_nginx._walk_with_ancestors`, `_locations_matching(predicate)` thiếu chú thích kiểu | `deploy/tests/nginx_reader.py:121`, `deploy/tests/test_nginx.py:58,71` | Thêm kiểu trả (`Iterator[Node]`, …); B0-01 cân nhắc đưa `deploy` vào mypy |
| 13 | Nit | K29 | `_OPENCV_BAD` và lệnh kiểm cuối tầng `ml` chỉ bắt `opencv-python`, không bắt `opencv-contrib-python` (cũng là bản GUI) | `deploy/tests/test_dockerfiles.py:22`, `deploy/docker/ml.Dockerfile:65-70` | Mở rộng regex/tập tên cấm |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #2; P3 #9) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 1 (P1 #1; P2 #4; P3 #8) | 0,15 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 (P2 #5; Nit #12, #13) | 0,21 |
| OBS, OPS – Vận hành | 5 % | 1 (P1 #3; P3 #10) | 0,05 |
| MNT – Bảo trì | 3 % | 3 (P2 #6; P3 #7; Nit #11) | 0,09 |

Tổng: 0,25 + 0,75 + 0,15 + 0,50 + 0,50 + 0,50 + 0,21 + 0,05 + 0,09 = **3,00 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Cổng xanh thật (mã thoát 0, 8/8, 2153 passed, độ phủ 99,33 % / 97,46 %), đúng phạm vi sở hữu, không vi phạm khối [9], và nhánh là lời giải thật của `NO-006`, `NO-062` (còn `NO-021` một phần). Nhưng có ba P1 chưa waiver, cả ba tái hiện được bằng chính ảnh nền và cấu hình của nhánh: `localhost` (URL mà dev và e2e dùng) không tới được `/api` và không có CSP; token `/api/files/` rơi vào log lỗi mỗi khi `api` gián đoạn; `web` ở prod không bao giờ `healthy`. R-37/R-38: không merge.

Việc phải làm để được duyệt (sửa trong file của chính B0-08, mỗi sửa vài dòng):

1. **#1** — `web.Dockerfile` xoá `/etc/nginx/conf.d/default.conf`; test tĩnh đi kèm.
2. **#2** — `error_log … crit;` trong `location /api/files/`; test tĩnh đi kèm.
3. **#3** — một nguồn healthcheck cho `web`; prod kiểm `https://127.0.0.1:8443/index.html` (`curl -k`); test tĩnh đi kèm.
4. **#4** — `.envsh` không để `server_name` rỗng (hoặc ghi `DEBT.md` một dòng P2 chủ B0-08 nói rõ prod + `STORAGE_BACKEND=local` chưa chạy được).
5. **#5** — chạy lại đúng chữ [8].3 qua `http://localhost:<cổng>` (health/ready, SPA có CSP, `stop api` → 503 rồi `logs web` không lọc gì mà không có `/api/files/`), cộng một lượt `web` prod với chứng chỉ tự ký tới `healthy`; dán lệnh + mã thoát vào báo cáo.
6. **#6** — ghi `DEBT.md` dòng `➖` MNT-05.
7. Gộp lại `main` hiện tại (`900294a`), chạy `bash tools/verify/run.sh verify`, xin `/merge-review` lượt 2.

P3 #7–#10 và Nit #11–#13 do tác giả quyết, không chặn; #10 nên ghi vào lúc người điều phối đóng `NO-021`. Khi đã `APPROVE`: gộp **squash** (một prompt, R-36), thân có `Prompt: B0-08` đúng khối trailer (R-36b).
