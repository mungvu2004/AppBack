# Review merge fix/b0-08-web-openssl-cve → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải tác giả, không phải người điều phối). Phiên này không sửa mã, không merge. Mọi khẳng định trong `backend/dieu-phoi/chay/B0-09/bao-cao-fix070.md` và trong thân commit đều được tự kiểm lại · Commit đầu nhánh: `c43562135b3b` · merge-base `0a4d3dc`; `main` đã tới `2648add` nhưng chỉ đổi `DEBT.md` và `docs/reviews/`. `git diff main...HEAD`: 1 tệp, +1/−1 (`deploy/docker/web.Dockerfile:15`).
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, chạy tại chỗ trên `c435621` từ worktree `fix070-web-cve`. `MSYS_NO_PATHCONV=1 docker wait appback-verify-fix070-web-cve-verify-run-a6f90ee85d1b` = 0. Log host: `.cache/src-out/verify/20260922T155218Z-c43562135b3b.log` của worktree, bản `docker logs -f` ở scratchpad của phiên. Bước 5: `2353 passed, 10 skipped, 1 deselected` (340,5 s). Lúc khởi động có 1 container `verify-run` khác (trần 2).
- Độ phủ: tổng dòng **99,36 %** · nhánh **97,52 %**. Tập file bị chạm: 100 · 100 (nhánh không đụng Python).

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` hợp lệ vì B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt: worktree trước, sau verify và sau mọi probe; `main` trước khi ghi tệp này |
| `changes/B0-08.md` | có sẵn trên `main` (FIX không bắt buộc thêm) |
| Dòng đầu Conventional Commits ≤ 72 | đạt: `fix(deploy): bump web base image for openssl cve-2026-31789` (59 ký tự) |
| Trailer | `Prompt: B0-08`, `Fix: FIX-070`, `Co-Authored-By` liền khối. Reflog: `1eea544` được amend thành `c435621`, cây giống hệt (`e83200cf…`), chỉ bỏ dòng trống giữa các trailer |
| Đụng file cấm | không |
| `pragma` / `type: ignore` / `noqa` trần / `skip` / hạ ngưỡng | không (diff chỉ có một dòng `FROM`) |

## Bằng chứng tự chạy (không dùng số của tác giả)

| Kiểm | Kết quả |
|---|---|
| `MSYS_NO_PATHCONV=1 docker buildx imagetools inspect nginxinc/nginx-unprivileged:1.29.8-alpine` | mã thoát 0, `Digest: sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6`: **khớp** dòng `FROM` (index OCI 8 nền tảng) |
| Build ảnh web theo cách `tools/ci/job.sh` (nhánh `chore/b0-09-…`) làm | `web-context.sh 9cf0b0bf… <scratchpad>`, rồi `docker build --build-context appfront=… --build-arg APPFRONT_SHA=9cf0b0bf…` → mã thoát 0. Trong ảnh: `nginx/1.29.8`, apk `nginx-1.29.8-r1`, `libssl3-3.5.6-r0`, `curl-8.17.0-r1`, Alpine 3.23.4; có `dist/draco/draco_decoder.wasm` (192 420 B) |
| trivy `0.74.0@sha256:62b1e65e…` `--severity CRITICAL --ignore-unfixed --exit-code 1` | **mã thoát 0**, 0 lỗ hổng CRITICAL. NO-102 (CVE-2026-31789, `libssl3`/`libcrypto3`) đã hết. Đối chứng ảnh nền cũ `1.28.0@sha256:c97ff0bf…`: 2 CRITICAL đúng CVE-2026-31789 |
| trivy đủ mọi mức (thông tin, cổng không đòi) | ảnh web mới: **36 HIGH, 77 MEDIUM, 47 LOW, 4 UNKNOWN, tất cả đều có bản sửa** (curl/libcurl 8.17.0-r1 → 8.22.0-r0: 20 HIGH; libuuid 6; libexpat 4; `libssl3`/`libcrypto3` 3.5.6-r0: CVE-2026-45447 PKCS7_verify UAF → 3.5.7-r0, CVE-2026-14456 QUIC DoS → 3.5.8-r0; c-ares; libxml2). Nền cũ 1.28.0: 2 CRITICAL, 26 HIGH. trivy **không báo CVE nào của gói `nginx`** ở cả hai ảnh (xem nợ D1) |
| `docker run` như service `web` của `base.yml` (mạng tạm, `S3_PUBLIC_ENDPOINT=http://localhost:9000`, `PUBLIC_BASE_URL`, cổng host 18081) | `healthy` sau 3 s (HEALTHCHECK của ảnh); `nginx -t` **mã thoát 0**; master + worker chạy uid **10001**; `/` → 200, có CSP đủ `'wasm-unsafe-eval'` và gốc S3; `Host: localhost` → 200, có CSP (default.conf đã bị xoá); `/draco/draco_decoder.wasm` → **200**, `application/wasm`, 192 420 B; `/api/health` (không có api) → 503 `{"code":"DEPENDENCY_UNAVAILABLE",…}` + `Retry-After: 5` + `X-Request-Id`; `/api/files/<token>` và `/api/%66iles/<token>` → token **không** xuất hiện trong log |
| `S3_PUBLIC_ENDPOINT=` rỗng (mặc định `${S3_PUBLIC_ENDPOINT:-}` của base.yml) | `healthy`, `nginx -t` mã thoát 0 |
| Template prod (`NGINX_ENVSUBST_TEMPLATE_DIR=…/templates/prod`, chứng chỉ tự ký trong volume) | `nginx -t` mã thoát 0; healthcheck của `prod.yml` (`curl -kfsS … https://127.0.0.1:8443/index.html`) mã thoát 0; 8443 → 200 + HSTS; 8080 → 301; vhost MinIO: POST → 403 (`limit_except`), GET khi thiếu minio → 502 |
| Dọn | xoá hết container, mạng, volume, ảnh tạm; worktree vẫn sạch |

**Đánh giá rủi ro đổi dòng cấu hình** (theo yêu cầu của người điều phối): cấu hình `deploy/nginx/**` vẫn hợp lệ trên 1.29.8, dev lẫn prod. Không chạy root. Healthcheck của ảnh và của `prod.yml` đều đạt. CSP và wasm đúng. Về mặt cấu hình, việc bỏ dòng 1.28 **không** tạo finding. Finding #1 dưới đây nói về chuyện khác: **đích đến được chọn** không vá CVE nginx mà người điều phối nêu làm lý do duyệt, và đích đó là một dòng đã hết đời.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | SEC (G-06) · LOG-06 | **Nhánh không vá CVE-2026-42945, và dòng 1.29 được chọn đã hết đời nên không bao giờ vá được.** (a) Theo advisory của nginx.org và `CHANGES-1.30`, CVE-2026-42945 ("heap buffer overflow … ngx_http_rewrite_module, potentially resulting in arbitrary code execution") có dải bị ảnh hưởng **0.6.27–1.30.0**, chỉ vá ở **1.30.1+ / 1.31.0+**. 1.29.8 nằm trong dải đó. Thế mà thân commit `c435621` lại ghi "nginx 1.28.3-r7 vá CVE-2026-42945": ảnh chứa `nginx-1.29.8-r1`, và không có tag `1.28.3-alpine`. Người điều phối duyệt đổi dòng chính vì CVE này. Cấu hình có dùng rewrite module (`set`, `return` ở `snippets/app_locations.conf`, cả hai template). (b) 1.29.8 cũng nằm trong dải của CVE-2026-42533 (**major**, "map directive with regex matching", dải 0.9.6–1.31.2, vá 1.30.4+). Cấu hình có hai `map` regex trên đầu vào không tin cậy (`$http_x_request_id`, `$request_uri`), và `$appback_request_id` được chèn vào chuỗi `return 413/503 '…'`. Điều kiện kích hoạt ("sau một capture") thì tôi chưa chứng minh được, mức tin PLAUSIBLE. (c) 1.29 **không còn là mainline**. `mainline-alpine` = `1.31-alpine` (1.31.2), `stable-alpine` = `1.30-alpine` = `1.30.5-alpine` (dựng 2026-09-21). Không có `1.29.9-alpine`. `1.29-alpine` chính là digest đã ghim, dựng 2026-05-11 và không được dựng lại, nên đang mang 36 HIGH có bản sửa (bảng trên). Nhánh `main` (1.28.0) cũng dính (a) và (b), nên đây không phải hồi quy. Nhưng mục tiêu của FIX-070 và tiền đề của lần duyệt đổi dòng thì chưa đạt. Cổng trivy xanh cũng không nói gì về (a), (b), vì trivy không thấy CVE của gói nginx (D1) | `deploy/docker/web.Dockerfile:15`; thân commit `c435621` | Đổi một dòng thành `FROM nginxinc/nginx-unprivileged:1.30.5-alpine@sha256:04a3275f25d766cff8926d2e57b2ff34a783d6b12a702dc98bb82226d2d9a508`. Đây là dòng **stable** được hỗ trợ, đúng tinh thần của lựa chọn 1.28 ban đầu, và không thuộc dải của advisory nào trên nginx.org. **Tôi đã chạy thử** (Dockerfile tạm ở scratchpad, không đụng nhánh): imagetools ra đúng digest; trivy nền **0 lỗ hổng mọi mức** (Alpine 3.24.2); trivy CRITICAL ảnh web mã thoát 0; `nginx -t` dev 0 / prod 0; `healthy`; uid 10001; `/` 200 có CSP wasm; `.wasm` 200 `application/wasm`; `/api/health` 503 JSON; token không vào log; healthcheck prod 0. Sửa thân commit: bỏ câu "nginx 1.28.3-r7 vá CVE-2026-42945", ghi đúng phiên bản nginx và những CVE thật sự được vá |
| 2 | P3 | MNT-04 | Báo cáo tác giả trích commit `1eea544`, bản trước khi amend. Nhánh thật là `c435621` (cùng cây). Báo cáo cũng khẳng định tag 1.29 "đã có bản vá", mà điều đó chỉ đúng với OpenSSL | `backend/dieu-phoi/chay/B0-09/bao-cao-fix070.md` | Cập nhật sha. Tách rõ phần OpenSSL (đã vá) và phần nginx (chưa vá) |

## Nợ phát hiện ngoài diff (người điều phối ghi `DEBT.md`, R-34)

- **D1 (P2, chủ B0-09 `tools/ci/job.sh` `job_build_trivy`, ảnh chủ B0-08).** trivy 0.74.0 **không báo CVE nào của gói `nginx`** (gói nginx.org cài bằng apk) ở cả 1.28.0 lẫn 1.29.8. Theo advisory, hai bản đó nằm trong dải của hơn 10 CVE nginx năm 2026. Vì vậy job `build` xanh không chứng minh gì về CVE của chính nginx. Chữa: CI kiểm `nginx -v` của ảnh web không thấp hơn một bản tối thiểu được ghim, cập nhật theo advisory nginx.org; hoặc ghi rõ trong `tools/ci/README.md` rằng CVE nginx phải đối chiếu tay, và dựa vào Dependabot hệ `docker`.
- Nếu người điều phối vẫn merge 1.29.8 thì phải có dòng `DEBT.md` mức P1 cho CVE-2026-42945 (và 42533). Hiện `DEBT.md` chưa có dòng nào cho CVE nginx, NO-102 chỉ nói về OpenSSL.

## Kiểm sổ nợ

- NO-102 (P1, `mở`): phần OpenSSL CVE-2026-31789 **đã được nhánh này sửa thật** (trivy CRITICAL 0, tự chạy). Đóng được khi merge.
- Tác giả báo "không phát sinh nợ mới". Không đúng: CVE-2026-42945, lý do người điều phối nêu khi giao FIX-070, vẫn mở và chưa có dòng nào (xem #1, D1).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #1) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (LOG-06 của #1 đã tính ở SEC, không trừ hai lần) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #2) | 0,12 |

Tổng: **3,97 / 5** · P0: 0 · P1: 1 · P2: 0 (D1 nằm ngoài diff) · P3: 1

## PHÁN QUYẾT: REQUEST CHANGES

Nhánh sửa thật lỗ OpenSSL CRITICAL của NO-102: trivy CRITICAL 0, cổng verify mã thoát 0, cấu hình nginx dev/prod hợp lệ, không root, healthcheck, CSP và wasm đều đạt. Nhưng CVE-2026-42945 vẫn chưa được vá, dù đó là một trong hai lý do người điều phối duyệt bỏ dòng 1.28. 1.29.8 vẫn nằm trong dải bị ảnh hưởng, và dòng 1.29 đã hết đời (không có 1.29.9, ảnh không được dựng lại từ 2026-05-11). Thân commit còn khẳng định sai điều ngược lại. Đó là P1 không có waiver: waiver của người điều phối cho phép **đổi dòng**, không cho phép để lại CVE nginx. Để được duyệt, cần: (1) `deploy/docker/web.Dockerfile:15` → `nginxinc/nginx-unprivileged:1.30.5-alpine@sha256:04a3275f25d766cff8926d2e57b2ff34a783d6b12a702dc98bb82226d2d9a508` (reviewer đã chạy thử và đạt đủ các kiểm ở #1); (2) thân commit bỏ câu sai về CVE-2026-42945; (3) chạy lại trivy CRITICAL, smoke và `bash tools/verify/run.sh verify` rồi nộp mã thoát thật; (4) người điều phối ghi D1 vào `DEBT.md`. Nếu người điều phối quyết giữ 1.29.8 thì cần waiver P1 theo `RULE.md` §1 (ticket, chủ, hạn ≤ 1 sprint) và một dòng `DEBT.md` P1 cho CVE-2026-42945.
