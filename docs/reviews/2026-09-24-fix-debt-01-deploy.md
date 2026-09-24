# Review merge `fix/debt-01-deploy` → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worktree `review-debt-01-deploy`)
- Commit đầu nhánh: `66ce4d7a79ba` · Phạm vi review: `git diff 792e98b...HEAD` — 3 commit
  (`e4a9700` FIX-086 B0-08, `75a67da` FIX-087 B0-10, `66ce4d7` FIX-104 B0-08), 24 tệp, +555/−162.
- Nhánh xếp chồng lên `fix/b0-08-web-openssl-cve` @ `792e98b` (FIX-070, FIX-100 — đã APPROVE riêng,
  **không** review lại ở đây).
- Cổng: `bash tools/verify/run.sh verify` chạy tại chỗ, **mã thoát 0**
  (log `…/scratchpad/verify.log`, dòng `EXIT=0`).
- Độ phủ: tổng **dòng 99,06 % · nhánh 97,67 %**; tập tệp bị chạm **100,00 % / 100,00 %**.
  `3764 passed, 4 deselected` trong 757,89 s.

## 1. Điều kiện dừng sớm — không cái nào chạm

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` | rỗng |
| `changes/DEBT-01.md` | có (từ base, chủ là người điều phối) |
| Mẫu commit + trailer `Prompt:`/`Fix:` | cả 3 commit đúng (`fix(deploy): …` ≤ 72 ký tự, `Prompt: B0-08`/`B0-10`, `Fix: FIX-086/087/104`) |
| Tệp cấm (`docs/charter/*`, `openapi.json`, `uv.lock`, `APPFRONT_SHA`, `pyproject.toml`, `tools/verify/*`) | không đụng tệp nào — diff chỉ nằm trong `deploy/**` |
| `pragma: no cover` / `noqa` trần / `type: ignore` / `skip`/`xfail` mới / hạ ngưỡng | không có (chuỗi `# noqa: S104` duy nhất trong diff nằm **trong docstring** trích lại mã có sẵn) |
| Ranh giới sở hữu (R-27) | `deploy/**` thuộc B0-08/B0-10 — đúng chủ; không đụng `DEBT.md`, `docs/fixes.md` (chủ: người điều phối) |

## 2. Bảng cổng (E.10 — lấy từ mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm `node_modules` | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | tổng 99,06 % dòng / 97,67 % nhánh; tệp bị chạm 100 %/100 % |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; `case_gate`: 25 thao tác, 3 cảnh báo |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, 10/10 kiểm |
| 7 | `H1 H3 H4 H5` (`tools.contract.check`) | đạt | H4 **không áp dụng** — B3-05 chưa hợp nhất, đúng luật BE-00 §12 |
| 8 | `openapi` | đạt | |

**Mã thoát cổng: 0.**

## 3. Đo lại độc lập (không tin báo cáo tác giả)

Mọi con số dưới đây do phiên review tự chạy trên máy này ngày 2026-09-24.

### 3.1 NO-117 (P1) — đổi phiên bản không gián đoạn

Dựng thật `deploy/compose/ci.yml` (`COMPOSE_PROJECT_NAME=rvwswap`, cổng host 18080/15432/16379/16380/
19000/19001/11025/18025 để tránh Apache 8080 và Postgres 5432 của máy), 10 dịch vụ `healthy`
(`UP_EXIT=0`). Client poll chạy **trong container trên mạng compose**
(`curlimages/curl` → `http://web:8080/api/health`, `--max-time 5`, `sleep 0.1`), tức đúng đường đi của
trình duyệt qua `web`, không đi tắt vào `api`. Rồi `bash deploy/scripts/deploy.sh ci2`.

| Chỉ số | Số đo của phiên review |
|---|---|
| Mẫu poll trong suốt lượt đổi | **517** |
| Mã 200 | **517** |
| **Phản hồi hỏng (≠200 hoặc 000)** | **0** |
| Mẫu chậm > 0,5 s | **5**, tất cả trong dải 1,004–1,010 s, cụm liên tiếp 07:23:47–07:23:52 (đúng cửa sổ `swap_api` xoá container cũ) |

Năm mẫu ~1,00 s **chính là cơ chế mới đang làm việc**: nginx chạm địa chỉ đã chết,
`proxy_connect_timeout 1s` cắt, `proxy_next_upstream` thử địa chỉ còn lại và **vẫn trả 200**. Với
`proxy_connect_timeout 5s` cũ thì mỗi lần chạm như vậy là ~5 s treo. Kết luận: **NO-117 đạt trên máy
này** — kết quả của tôi (517/517) độc lập xác nhận hai lượt 387/398 của tác giả.

> **Lệch so với báo cáo tác giả:** `deploy.sh ci2` của tôi thoát **1**, hỏng ở kiểm smoke thứ 5
> (`hỏng /api/nope`). Nguyên nhân **thuộc môi trường, không thuộc nhánh**: `deploy/scripts/smoke.sh:80`
> dùng `python3` của **máy chủ**, mà `python3` trên máy Windows này là stub Microsoft Store
> (in "Python was not found", thoát ≠ 0) và lỗi bị `2>/dev/null` nuốt. Gọi tay cùng URL trả đúng
> `404 {"code": "NOT_FOUND", …}`. Lượt rollback sau đó không chạy ("không có previous_tag") nên
> không nhiễu số đo poll. Báo cáo tác giả ghi "smoke đạt cả 5 kiểm" — **tôi không tái hiện được**.
> Đây là điểm yếu **có sẵn** của `smoke.sh` (ngoài phạm vi diff): một VPS không có `python3` sẽ làm
> `deploy.sh` rollback một bản deploy hoàn toàn tốt. Đề nghị người điều phối ghi một dòng nợ mới.

### 3.2 NO-095 / NO-094 — token `/api/files/` trong log

Ảnh nền `nginxinc/nginx-unprivileged:1.30.5-alpine@sha256:4714e0b1…` chạy thật với `deploy/nginx`
của nhánh gắn vào (`api` không tồn tại → mọi `/api/*` đi qua `error_page`, đúng đường mà bản cũ để lọt),
bản dev và bản prod riêng; `nginx -t` đạt ở cả hai.

| URI (curl `--path-as-is`), token `SECRETTOKEN123456` | dev 8080 |
|---|---|
| `//api/files/<token>` · `/api//files/<token>` · `/api/%66iles/<token>` | 503 |
| `/api/./files/<token>` · `/api/x/../files/<token>` | 503 |
| `/%61pi/files/<token>` · `/api%2Ffiles/<token>` | 503 |

- `docker logs` (access **và** error — ảnh nền symlink ra stdout/stderr): **`grep -c <token>` = 0**.
- Đối chứng `/api/projects/1`: **2 dòng** — log vẫn hoạt động bình thường.
- Bản prod, token `PRODTOKEN555`: 8080 trả 301 cho cả bốn dạng, 8443 trả 503 cho cả ba dạng,
  **`grep -c <token>` = 0** (NO-094 + NO-095 cùng đạt).

**Cả bảy dạng méo đều được `location /api/files/` phục vụ — khẳng định cốt lõi của FIX-086 là đúng.**

### 3.3 NO-177 / FIX-104 — tầng chạy Python

- `docker build` `api`, `worker`, `web`: mã thoát **0** cả ba.
- `docker run --entrypoint sh appback-api:ci -c 'python -V; ls /opt/venv/lib; python -c "import alembic…"'`
  → `Python 3.12.14` · `python3.12` · `import ok 1.20.0`.
- `docker compose -f deploy/compose/ci.yml run --rm migrate` → **mã thoát 0**.
- Digest ghim tự tra lại bằng `docker buildx imagetools inspect` (2026-09-24):
  `python:3.12-slim-bookworm` = `sha256:392307d22300de…` — **khớp đúng digest trong ba Dockerfile**;
  `python:3.14-slim-bookworm` = `sha256:82bc3c539b88…` (digest mà dependabot đưa vào).
- `requires-python = ">=3.12,<3.13"` (pyproject gốc), `uv.lock` `==3.12.*`, tầng dựng `uv:python3.12`
  ở cả bốn Dockerfile → ngưỡng `checked >= 7` của test có căn cứ thật.

### 3.4 Các khẳng định còn lại

- `9464` không nằm trong `ports:` của bất kỳ dịch vụ nào ở dev/ci/prod — đọc lại bằng tay cả ba tệp.
- `ci.yml` dịch vụ `api` không còn `ports:`; `web` vẫn publish `${WEB_HTTP_PORT}` → `--scale api=2`
  chạy được (chính lượt đo §3.1 đã dùng).
- Không test nào trong diff tải mạng: toàn bộ là đọc tệp YAML/template/Dockerfile.
- Mặc định `SMTP_PORT=587`, `SMTP_TIMEOUT_S=10`, `SMTP_STARTTLS=true`, `MAIL_BACKEND=smtp` của
  `base.yml` khớp đúng `packages/mail/settings.py:26-31`.

## 4. Finding

| # | Mức | ID | Mô tả + bằng chứng | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P2** | OPS-01 | `SMTP_HOST`/`MAIL_FROM` thành `${…:?}`, mà `prod.yml` `extends` `base.yml` → **mọi** lệnh `docker compose` trên prod (`pull`, `run --rm migrate`, `swap_api`, `rollback.sh`) hỏng ngay lúc nội suy nếu `appback.env` của VPS chưa có hai biến. Bảng "Biến môi trường" của runbook **không có** hai dòng này, §12 "việc người phải làm trước M1" cũng không. Hỏng xảy ra ở lệnh đầu tiên nên **không** để lại trạng thái nửa vời (vì vậy không nâng lên P1), nhưng deploy của một host đang chạy sẽ đứng cho tới khi người vận hành tự đoán ra. | `deploy/compose/base.yml:125,131` · `deploy/scripts/README.md:260-275` | Thêm `SMTP_HOST`, `MAIL_FROM` (nên cả sáu biến còn lại) vào bảng biến môi trường + §12 của `deploy/scripts/README.md` (tệp B0-10). Nếu không làm trước khi gộp → **bắt buộc** một dòng `NO-<nnn>` mới trong `DEBT.md` (R-34). |
| 2 | P3 | SEC-06 / OBS-02 | Chuyển quyết định tắt log **hẳn** sang mức location làm mất lớp chắn cho lỗi **xảy ra trước khi chọn location**: nginx ghi nguyên `/api/files/<token>` vào access log mặc định. Đo thật trên **ảnh `appback-web:ci` trong stack đang chạy**: `GET /api/files/STACKLEAK400` kèm header hỏng → 400, `grep -c STACKLEAK400` trong `docker logs rvwswap-web-1` = **1** (`"GET /api/files/STACKLEAK400 HTTP/1.1" 400 157`); cùng lúc `/api/files/STACKOK` bình thường = **0**. Đối chứng trên cấu hình cũ `792e98b` (cùng ảnh nền): cùng probe 400 = **0** (map `$request_uri` mức server bắt được), nhưng `/api/./files/<token>` = **1** (đúng NO-095). 414 cũng lọt tương tự. Tức bản mới **đổi** một lớp rò lấy một lớp rò khác, chưa phải "sửa gốc" trọn vẹn như commit và báo cáo khẳng định. Cả hai lớp đều hẹp (đòi client tự gửi request méo) nên giữ đúng mức P3 mà NO-094/NO-095 đã được xếp. | `deploy/nginx/snippets/app_locations.conf:37-44`; `deploy/nginx/templates/{dev,prod}/app.conf.template` (bỏ `map`) | Giữ **cả hai** lớp: trả lại `access_log … if=$appback_access_log` mức server (map trên `$request_uri`) **bên cạnh** `access_log off` mức location, và nới `test_nginx_files_log_decision_is_location_scoped_not_request_uri` để cho phép map như lớp thứ hai thay vì cấm hẳn. Nếu hoãn → một dòng `NO-<nnn>` mới. |
| 3 | P3 | RES-02 / TEST-03 | Lý do bác `upstream{}` **sai với phiên bản đang dùng**. Tài liệu nginx (`nginx.org/en/docs/http/ngx_http_upstream_module.html`, đọc 2026-09-24): *"Prior to version 1.27.3, this parameter was available only as part of our commercial subscription"* — tức `resolve` **đã có ở nginx OSS từ 1.27.3**, còn `web.Dockerfile:22` ghim **nginx 1.30.5**. Lập luận sai được chép vào comment mã, docstring test **và** một `assert not find_directive(…, "upstream")` cấm mọi khối `upstream{}` trong `deploy/nginx/**` → khoá một phương án hợp lệ (`upstream` + `zone` + `server … resolve`) bằng tiền đề không đúng. Phương án đã chọn (biến + `resolver` + `proxy_next_upstream`) **vẫn đúng** và tôi đo được là hoạt động (§3.1) — đây là lỗi lập luận/test, không phải lỗi chạy. | `deploy/nginx/snippets/proxy_common.conf:18-21` · `deploy/tests/test_nginx.py:469-476,491-493` | Sửa comment + docstring cho đúng (OSS ≥ 1.27.3 có `resolve` nhưng cần `zone`; vẫn chọn biến + `resolver` vì đơn giản hơn và đã đo). Đổi assert thành: nếu có `upstream{}` thì **phải** kèm `zone` và `server … resolve`. |
| 4 | P3 | SEC-07 | `revoke_stale_users()` **hỏng ngầm theo hướng mở**: `mc admin policy entities … 2>/dev/null` không kiểm mã thoát và pipeline không có `pipefail`, nên mc lỗi / đổi định dạng / đổi tên cờ ⇒ `users_with_policy()` trả rỗng ⇒ không thu hồi gì, `init.sh` vẫn thoát 0 và không ai biết khoá cũ còn sống. Test `test_minio_init_revokes_identities_left_over_from_key_rotation` chỉ so khớp **văn bản tĩnh** nên không bắt được. Định dạng được đo thật (tốt), nhưng một biện pháp thu hồi quyền không nên im lặng khi mất hiệu lực. | `deploy/minio/init.sh:46-58,67-77` | Kiểm mốc: đòi thấy dòng `Policy -> Entity Mappings:` trong output (hoặc giữ mã thoát của `mc`), không thấy thì `exit 1`. |
| 5 | P3 | MNT-02 / R-02 | Docstring của `test_deploy_default_swap_settle_s_covers_nginx_resolver_ttl` vẫn viết "đối chiếu với mặc định `${APPBACK_API_SWAP_SETTLE_S:-N}` trích thẳng từ `lib.sh`", trong khi thân test nay **cấm** đúng dạng đó (`assert "APPBACK_API_SWAP_SETTLE_S:-" not in lib_sh`). Tài liệu mâu thuẫn với mã ngay trong cùng hàm. | `deploy/scripts/tests/test_deploy.py:299-300` | Sửa một dòng docstring. |
| 6 | Nit | RES-01 | `: "${APPBACK_API_SWAP_SETTLE_S=11}"` (dạng `=`, không `:=`) giữ nguyên **chuỗi rỗng**: `APPBACK_API_SWAP_SETTLE_S=` trong `appback.env` làm `sleep ""` hỏng **giữa** `swap_api` — đã `--scale api=2`, chưa xoá container cũ — rồi `set -e` bỏ dở. Trước đây `${…:-11}` biến rỗng thành 11. Lý do chọn `=` (bài học NO-114) chỉ cần cho giá trị `0`, mà `:=` **cũng** giữ nguyên `0`. | `deploy/scripts/lib.sh:25,126` | Thêm ngay sau dòng khai: `[ -n "$APPBACK_API_SWAP_SETTLE_S" ] || APPBACK_API_SWAP_SETTLE_S=11`. |
| 7 | Nit | MNT-01 | `66ce4d7` mang trailer `Fix: FIX-104` nhưng `docs/fixes.md` chỉ có FIX-086 và FIX-087 — thiếu dòng FIX-104. (`docs/fixes.md` không thuộc sở hữu của nhánh này.) | `docs/fixes.md:83-84` | Người điều phối thêm dòng FIX-104. |

Ngoài phạm vi diff, ghi nhận để người điều phối mở nợ: `deploy/scripts/smoke.sh:80` phụ thuộc
`python3` **trên máy deploy**; thiếu nó thì kiểm thứ 5 luôn hỏng và `deploy.sh` rollback một bản
deploy tốt (§3.1).

## 5. Sổ nợ

| NO | Mức | Đóng được khi gộp? | Căn cứ của phiên review |
|---|---|---|---|
| NO-094 | P3 | **Được ✅** | probe prod: `access_log off` trong server 301, `grep -c PRODTOKEN555` = 0 (§3.2) |
| NO-095 | P3 | **Được ✅** | 7 dạng URI méo đều tới `location /api/files/`, `grep -c` token = 0 ở cả dev và prod (§3.2). Lớp rò **mới** ở lỗi 400/414 là finding #2 — nợ **mới**, không phải NO-095 chưa đóng |
| NO-096 | P3 | **Được ✅** | `revoke_stale_users` gọi đúng một lần cho mỗi chính sách với khoá hiện tại làm ngoại lệ; kèm finding #4 (hỏng ngầm) |
| NO-117 | **P1** | **Được ✅** | **số đo của tôi: 517 mẫu poll 100 ms qua `web` trong lượt `deploy.sh ci2`, 517 mã 200, 0 phản hồi hỏng**; 5 mẫu 1,004–1,010 s đúng cửa sổ đổi container = `proxy_connect_timeout 1s` + `proxy_next_upstream` đang chuyển tiếp thành công. Lệch khỏi ô nợ (không dùng `upstream{}`) **chấp nhận được** — phương án thay thế đúng và đã đo; nhưng **lý do nêu ra thì sai** (finding #3), phải sửa comment/test chứ không phải đổi phương án |
| NO-118 (phần `deploy/**`) | P3 | **Được ✅ — có điều kiện** | `ci.yml` `api` không còn `ports:`. **Điều kiện gộp:** `fix/debt-01-tooling` (đã APPROVE) phải vào `main` **trước**, vì `tools/ci/job.sh:358,364-365` trên `main` hiện vẫn smoke qua `127.0.0.1:${API_HOST_PORT}` — gộp ngược thứ tự làm job `smoke` của CI đỏ |
| NO-120 | P3 | **Được ✅** | một khai báo duy nhất ở `lib.sh:25`, hai chỗ dùng biến trần, test neo đúng dòng khai + đối chiếu README. Kèm Nit #6 |
| NO-141 | P2 | **Được ✅ — kèm điều kiện** | tám biến khớp `MailSettings`; nhưng phải xử finding #1 (doc runbook) trước lần deploy prod tới |
| NO-162 | P2 | **Được ✅** | `prometheus.yml` khai job `api:9464`; test chốt 9464 không nằm trong `ports:` của cả ba env. Lưu ý: chưa có dịch vụ thu thập nào chạy tệp này — đúng phạm vi ô nợ, không phải thiếu sót |
| NO-177 | P1 | **Được ✅** | ba tầng chạy về `python:3.12-slim-bookworm` đúng digest sống; `python -V` = 3.12.14, `import alembic` đạt, `compose run --rm migrate` thoát 0 (§3.3) |
| NO-083 | P3 | **`➖` — đồng ý** | lý do đứng được (tệp bị `.gitignore` của AppFront; kéo Poly Haven trong build = tải mạng không ghim được, trái BE-00 §13.1), có đường nâng cấp cụ thể (CI dựng + ghim SHA-256 + `COPY`) |
| NO-084 | P3 | **`➖` — đồng ý** | `ml` chỉ nối `ml-internal` là **cố ý** (BE-00 §9); egress proxy là tính năng v2, có đường nâng cấp ghi rõ |
| NO-085 | P2 | **chưa** | phần compose chờ nhánh core — người điều phối đã duyệt trước, soát ở lượt sau |
| NO-104 | P3 | **chưa** | ảnh `ml` tải mô hình chập chờn — thuộc nhánh core, không phải nhánh này |

Nợ `P0`/`P1` còn mở liên quan tới nhánh: **không còn** sau khi gộp (NO-117 và NO-177 đều đóng được).
Hai dòng nợ **mới** cần người điều phối ghi trước khi gộp (R-34): finding #1 nếu không sửa runbook
ngay, và finding #2 (rò token qua lỗi 400/414).

## 6. Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 (P3 #2, #4) | 1,00 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (P3 #3, Nit #6) | 0,40 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 #3) | 0,28 |
| OBS, OPS – Vận hành | 5 % | 3 (**P2 #1**) | 0,15 |
| MNT – Bảo trì | 3 % | 4 (P3 #5, Nit #7) | 0,12 |
| **Tổng** | **100 %** | | **4,45 / 5** |

Không có P0, không có P1.

## PHÁN QUYẾT: APPROVE WITH COMMENTS

Nhánh này là công việc chất lượng cao: mỗi ô nợ được sửa **ở gốc** chứ không vá triệu chứng, mỗi
khẳng định đều kèm số đo, và ba khẳng định nặng nhất (NO-095, NO-117, NO-177) tôi **tự đo lại được
và ra cùng kết luận** — 517/517 mã 200 qua lượt đổi container, `grep -c` token = 0 trên cả bảy dạng
URI méo ở cả hai template, `migrate` thoát 0 trên ảnh 3.12. Cổng đầy đủ xanh (8/8, mã thoát 0), độ
phủ 99,06 % dòng / 97,67 % nhánh và 100 %/100 % trên tập tệp bị chạm. Không có P0/P1; điểm 4,45.

Cho phép gộp, **kèm ba điều kiện**:

1. **Thứ tự gộp:** `fix/debt-01-tooling` phải vào `main` **trước** nhánh này. `ci.yml` bỏ cổng host
   của `api`, nhưng `tools/ci/job.sh` trên `main` vẫn smoke qua `API_HOST_PORT` — gộp ngược thứ tự
   làm job `smoke` của CI đỏ.
2. **Finding #1 (P2)** phải được xử trước khi gộp: hoặc thêm `SMTP_HOST`/`MAIL_FROM` vào bảng biến
   môi trường của `deploy/scripts/README.md`, hoặc ghi một dòng `NO-<nnn>` mới trong `DEBT.md`
   (R-34 — P2 phải có ticket).
3. **Finding #2 (P3)** phải có một dòng `NO-<nnn>` mới: đổi một lớp rò log lấy một lớp rò khác là
   trạng thái đã biết, không được để không ghi sổ.

Finding #3, #4, #5 và hai Nit không chặn merge; nên gom vào một FIX nhỏ tiếp theo cho B0-08/B0-10
(#3 quan trọng nhất trong nhóm này vì một assert đang khoá phương án hợp lệ bằng tiền đề sai).

**Phiên này không merge.** Việc merge thuộc phiên gọi review (R-37).
