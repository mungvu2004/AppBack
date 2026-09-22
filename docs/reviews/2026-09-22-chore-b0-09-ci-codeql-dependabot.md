# Review merge chore/b0-09-ci-codeql-dependabot → main (lượt 1)

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, lượt 1. Phiên này không viết mã và không làm merge. Mọi khẳng định trong `bao-cao-B0-09.md` và `bao-cao-m-fix.md` đều được kiểm lại bằng diff, cổng và probe tự chạy · Commit đầu nhánh: `16e2a5d7a052` · merge-base với `main` = `751d606` (`main` chưa đi thêm; `git merge-tree --write-tree main HEAD` sạch). `git diff main...HEAD`: 23 tệp, +3 520 dòng, 0 xoá. Riêng mã không phải test (`.github/`, `tools/ci/*.py`, `job.sh`, `ci_split.py`) là 1 797 dòng.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, chạy tại chỗ trên `16e2a5d` từ worktree `b0-09-m-merge`, sạch trước và sau. Lúc khởi động có 0 container `verify-run`. `MSYS_NO_PATHCONV=1 docker wait` = 0. Log host ở `.cache/src-out/verify/20260922T135850Z-16e2a5d7a052.log`, bản sao `docker logs -f` của `appback-verify-b0-09-m-merge-verify-run-3a704f2f8581` ở scratchpad của phiên. Kết quả `2456 passed, 10 skipped, 1 deselected` (340,8 s). `tools/ci/tests` có 103 test, đều xanh, không `skip`: audit 13, ci_split 13, commits 16, h2 21 (có `test_main_real_app_passes`, dựng Testcontainers thật, 7,2 s), import_all 7, merge_artifacts 10, workflows 23.
- Độ phủ: tổng dòng **99,06 %** · nhánh **97,31 %**; `tools` 98,70 · 95,53; `packages/testing` 99,24 · 100; tập file bị chạm 98,77 · 95,70.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (388 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (315 file) |
| 4 | `lint-imports` | đạt (9 giữ, 0 vỡ) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (10/10) |
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` hợp lệ vì B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt: worktree trước, sau verify và sau mọi probe; `main` trước khi ghi tệp này |
| `changes/B0-09.md` | có, 8 dòng |
| Dòng đầu Conventional Commits ≤ 72 | đạt: 10 commit không-merge qua đúng `.githooks/commit-msg`, dài nhất 71 ký tự (`827178b`). 4 commit `Merge branch '…'` do git sinh, hook cho qua |
| Trailer `Prompt:` | 10/10 commit không-merge đọc được `B0-09`. 4 commit merge rỗng, sẽ mất khi squash (Nit #17, tiền lệ review B0-08) |
| Đụng file cấm ([12], B0-01 [7]) | không: `git diff --name-only main...HEAD` ra 23 tệp, đều thuộc `so_huu`. Không có `tools/verify/**`, `tools/tests/**`, `deploy/**`, `.githooks/**`, `uv.lock`, `pyproject.toml` |
| `pragma` / `type: ignore` không mã / `noqa` trần / `skip` / `xfail` / hạ ngưỡng / `continue-on-error` | không: grep phần thêm của diff ra rỗng. `continue-on-error` chỉ xuất hiện trong assert của test |
| `conftest.py` lồng, cấu hình công cụ riêng | không |

## Bằng chứng tự chạy (không dùng số của tác giả)

| Kiểm | Kết quả |
|---|---|
| `git ls-remote` cả 8 action | **đều khớp**. `actions/checkout` v7.0.1 `3d3c42e5…`, `astral-sh/setup-uv` v10.2.0 `c18668ad…`, `actions/setup-node` v7.0.0 `82076278…`, `actions/upload-artifact` v7.0.1 `043fb46d…`, `actions/download-artifact` v8.0.1 `3e5f45b2…`, `docker/setup-buildx-action` v4.4.1 `f87e5991…`, `crazy-max/ghaction-github-runtime` v4.0.0 `04d248b8…` đều là tag nhẹ, SHA commit bằng SHA ghim. `github/codeql-action` v4.38.1 là tag có chú thích: `refs/tags/v4.38.1` = `c23de5a8…` (đối tượng tag), còn `refs/tags/v4.38.1^{}` = `1c5b675653bb5c22dbe9b12b556ec555138e09fd` = SHA ghim |
| `docker buildx imagetools inspect` | `aquasec/trivy:0.74.0` → `sha256:62b1e65e…1969`; `zricethezav/gitleaks:v8.30.1` → `sha256:c00b6bd0…bb7f`; `rhysd/actionlint:1.7.12` → `sha256:b1934ee5…5667`. Cả ba khớp bản ghim |
| actionlint `1.7.12@sha256:b1934ee5…` trên `ci.yml`, `codeql.yml` | **0 lỗi**, mã thoát 0 |
| SEC workflow | Không có `run:` nào chứa `${{ … }}`; `github.event.*` chỉ đi vào `env:` (`ci.yml:209-213`). Không có `pull_request_target`, `secrets.`, `environment:`. `permissions: contents: read` ở mức workflow; `codeql.yml` chỉ job `analyze` có thêm `security-events: write`. `commits.py` gọi `subprocess` bằng danh sách đối số, không qua shell. `job.sh` không `eval`, mọi biến ngoài đều được trích dẫn |
| `.gitleaks.toml`: hai commit được miễn | Quét lại `main` bằng ảnh gitleaks ghim, cấu hình **bỏ** `commits`: 209 commit, đúng 3 phát hiện, cả 3 nằm trong hai SHA được miễn và đều là bí mật giả trong test: `eb40a3c` `apps/api/core/tests/test_common.py:55` (JWT `…chu-ky-ngau-nhien`), `1b97b24` `packages/storage/tests/test_settings.py:27` (`secret-du-dai-cho-cau-hinh-b0-04`), `test_local.py:24` (`secret-sau-khi-xoay-khoa-cua-b0-04`). Miễn hẹp, đứng được. Ảnh chạy bằng root, có `safe.directory=*`, nên runner không vướng lỗi "dubious ownership" |
| pip-audit 2.10.1 có trả mã khác 0 khi có lỗ hổng không | **Có.** Chạy trong container verify: `jinja2==2.10` → **thoát 1** (12 lỗ hổng, JSON vẫn ghi đủ); cùng lệnh thêm `--ignore-vuln` một id → vẫn **1**; `six==1.16.0` → 0. Đây là nguồn của finding #1 |
| Luật [9] | `needs:` chỉ ở `coverage` (`ci.yml:227`); không `continue-on-error`; không tag trôi; `coverage` không có `if: always()`; `integration` và `contract` chạy Testcontainers thật (`h2._provision`, fixture dịch vụ). Không bước verify nào bị bỏ: 1,2,4 ở `lint`; 3,8 ở `typecheck`; 5 do unit/integration/ml và `coverage` đảm nhận; 5b ở `coverage`; 6 ở `integration`; 7 ở `contract` |
| Bước 8 ở CI chỉ xuất (hop-dong §4, đã duyệt) | Chú thích lý do có ở `ci.yml:62-65`. Không tính là finding. Riêng `job.sh:156` trỏ tới `changes/B0-09.md` như nơi đã ghi, nhưng tệp đó không có dòng nào về chuyện này (#12) |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | LOG-06 (R-19) | **Trong CI, danh sách miễn `pip-audit` không bao giờ được dùng.** `run_step` chạy `uvx pip-audit … --format json > /tmp/ci-pip-audit.json`, mà pip-audit thoát **1** mỗi khi có lỗ hổng, kể cả lỗ hổng chưa có bản sửa và lỗ hổng đã ghi miễn (đã đo, xem bảng trên). Bước đó thành "hỏng", nên `tools.ci.audit` thành "chưa chạy". Vì vậy `audit-allowlist.toml`, luật `expires`/`reason` và luật "chưa có bản sửa thì chỉ in" của [6] đều là mã chết trên runner. Phán quyết thật của `lint` thành "0 lỗ hổng bất kỳ", khác với [2] ("0 lỗ hổng có bản sửa ngoài danh sách miễn"). Test của `audit.py` chỉ gọi module đó riêng, không đi qua `job.sh`, nên không bắt được | `tools/ci/job.sh:142-146` | Chỉ coi bước pip-audit hỏng khi mã thoát > 1 hoặc JSON rỗng/không đọc được; mã 0 và 1 đều chuyển tiếp cho `tools.ci.audit` quyết. Ví dụ: `uvx … > json; rc=$?; [ "$rc" -le 1 ] && [ -s json ]`. Thêm test đi qua đúng đường `job.sh lint` với một `uvx` giả trên `PATH`: thoát 1, JSON có lỗ hổng đã miễn → đạt; lỗ hổng có bản sửa, chưa miễn → hỏng; thoát 2 → hỏng |
| 2 | P2 | LOG-02 | **Mọi lượt chạy tay (`workflow_dispatch`) đều đỏ ở job `commits`.** `ci.yml` khai trigger `workflow_dispatch` và đặt `EVENT=${{ github.event_name }}`. `load_inputs` chỉ nhận `pull_request`/`push`, và với sự kiện này `BASE_SHA` (`base.sha \|\| event.before`) rỗng. `test_unknown_event_fails_closed` chốt đúng hành vi đó cho `EVENT=release`, nhưng `workflow_dispatch` là trigger do chính workflow khai | `ci.yml:11`, `ci.yml:209-212`; `tools/ci/commits.py:52-61` | Với `workflow_dispatch`, chỉ kiểm dòng đầu của `HEAD_SHA` (như `push` có `BASE_SHA` toàn 0), hoặc in "không áp dụng" rồi thoát 0. Thêm test cho `EVENT=workflow_dispatch`, `BASE_SHA=""` |
| 3 | P2 | LOG-06 / OBS | **SARIF của trivy bị mất; prompt [6] đòi "SARIF tải lên artifact".** Mỗi lượt `trivy` ghi `--output /tmp/trivy-<ảnh>.sarif` bên trong `docker run --rm` không mount thư mục nào, nên container xoá là tệp mất theo. Job `build` cũng không có bước `upload-artifact`. Khi `build` đỏ, log chỉ còn bảng đếm, không có CVE nào để tra | `tools/ci/job.sh:269-275`; `ci.yml:183-201` | Mount một thư mục host (`${RUNNER_TEMP:-/tmp}/trivy`) vào container, ghi SARIF vào đó, rồi thêm `actions/upload-artifact@043fb46d… # v7.0.1` với `if: always()` vào job `build`. Test trong `test_workflows.py` kiểm job `build` có upload SARIF |
| 4 | P2 | LOG-02 | **PR Dependabot hệ `docker` sẽ đỏ ở `commits` vì dòng đầu dài quá 72 ký tự.** Với thư mục khác `/`, Dependabot nối thêm ` in /deploy/docker` vào tiêu đề PR và dòng đầu commit. Ví dụ PR gom: `build(deps): bump the docker-patches group in /deploy/docker with 2 updates` dài 75 ký tự. PR một ảnh: `build(deps): bump nginxinc/nginx-unprivileged from 1.28.0-alpine to 1.29.1-alpine in /deploy/docker` dài khoảng 99. Hook chặn mọi dòng > 72, và `commits.py` kiểm cả tiêu đề PR lẫn từng commit. Mẫu trong test (`Bump python from 3.12-slim-bookworm …`) thiếu hậu tố thư mục, nên không bắt được. Mức tin: PLAUSIBLE, dựa trên định dạng tiêu đề của Dependabot; xác nhận ở lượt Dependabot thật đầu tiên | `.github/dependabot.yml:34-44`; `.githooks/commit-msg:20`; `tools/ci/tests/test_workflows.py:236-256` | Với `dependabot/**`, bỏ kiểm dòng đầu từng commit (squash lấy tiêu đề PR), đồng thời `README.md` ghi rõ người điều phối rút tiêu đề PR xuống ≤ 72 ký tự trước khi squash. Sửa mẫu test theo định dạng thật (chữ thường `bump`, có ` in /deploy/docker`) |
| 5 | P2 | R-34 | 6 mục nợ tác giả nêu (xem "Kiểm sổ nợ") **chưa có dòng nào** trong `DEBT.md` | `DEBT.md` (trên `main`) | Người điều phối ghi trước khi gộp (R-38), đúng như đã cam kết |
| 6 | P2 | MNT-05 | 1 797 dòng mã không phải test (> 400). **Không đáng tách:** là một prompt, đã dựng từ 5 nhánh worker tách theo `so_huu`, và workflow cùng `job.sh` gọi chéo mọi module | toàn nhánh | Ghi `DEBT.md` dạng `➖`, như `NO-091` |
| 7 | P3 | R-29 / TEST-02 | Job `integration` và `contract` chạy pytest mà không làm ấm `node_modules` trước (bước 0 của cổng, bản sửa NO-048). Fixture `contract_build` → `build_layout` → `ensure_node_modules` sẽ chạy `npm ci` ngay trong test khi runner còn lạnh, trái luật "không tải mạng trong test". Cache npm của `setup-node` giảm nhẹ, nhưng không bỏ được | `tools/ci/job.sh:166-195`; `tools/contract/runner_client.py:175` | Gọi `runner_client.ensure_node_modules(runner_client.node_dir_from_env())` (hoặc `verify --steps 0` nếu B0-01 cho phép) trước pytest ở hai job này |
| 8 | P3 | LOG-04 | gitleaks xanh giả khi không đọc được lịch sử git. Đã tái hiện: chạy ảnh ghim trên worktree (`.git` là tệp trỏ ra đường host) thì in "0 commits scanned … no leaks found" và thoát 0. `m-job-checks.log` của tác giả cũng có một lượt "0 commits scanned". Checkout của runner là bản clone thường nên CI không dính, nhưng đường chạy tại chỗ trong README §6 thì có | `tools/ci/job.sh:110-125` | Trước khi quét, kiểm `git rev-list --count --all` > 0 trong đúng ngữ cảnh chạy gitleaks; bằng 0 thì đánh "hỏng" |
| 9 | P3 | G-04 | `torch` và `torchvision` (bản `+cpu`) không bao giờ được audit: `m-lint-3.log:129-130` ghi "Dependency not found on PyPI and could not be audited". `--extra-index-url …/whl/cpu` không có tác dụng khi đã `--no-deps --disable-pip`, trái với chú thích nói nó để tra torch | `tools/ci/job.sh:136-146` | Dùng `--vulnerability-service osv`, hoặc bỏ phần `+cpu` trước khi audit; xoá cờ và chú thích chết. Gói bị bỏ qua nên phải có mục miễn tường minh, không chỉ in dòng thông báo |
| 10 | P3 | R-07 | Bản ghim ảnh của H2 chép tay từ `services.py:29-32` (mục nợ #5 của tác giả). R-28 cấm `h2.py` nhập `packages.testing`, nên muốn gom về một chỗ thì phải sửa ngoài `so_huu`. Nhưng một **test chống lệch** thì làm được ngay trong `so_huu`, vì test được phép nhập `packages.testing` | `tools/ci/h2.py:73-75` | Thêm test trong `tools/ci/tests/test_h2.py` so `h2.POSTGRES_IMAGE`/`REDIS_IMAGE`/`MINIO_IMAGE` với `packages.testing.fixtures.services` |
| 11 | P3 | OPS-02 | README §1 bảo bật "Require a pull request before merging" nhưng không nói tới danh sách bypass. Khi bật ruleset, ngoại lệ hẹp của R-36 (commit `DEBT.md`, `docs/reviews/*` thẳng lên `main`) sẽ bị chặn | `tools/ci/README.md:20` | Ghi thêm: thêm "Repository admin" vào bypass list cho ngoại lệ R-36, hoặc nói rõ các commit đó cũng phải đi qua PR |
| 12 | P3 | MNT-04 | Chú thích ở `job.sh:156` nói chỗ lệch bước 8 "đã ghi ở changes/B0-09.md", nhưng tệp này (8 dòng) không có dòng nào về bước 8 | `tools/ci/job.sh:154-157`; `changes/B0-09.md` | Thêm một dòng vào `changes/B0-09.md`, hoặc sửa chú thích cho trỏ về `hop-dong.md §4` |
| 13 | Nit | LOG-02 | Khối `__main__` gọi `main()` không truyền argv, nên `python -m tools.ci.h2 x` chạy như không có đối số; chốt "không nhận tham số" chỉ có tác dụng khi test gọi thẳng | `tools/ci/h2.py:350-352, 366-367` | `raise SystemExit(main(sys.argv[1:]))` |
| 14 | Nit | RES-06 | `shutdown_lifespans()` nằm ngoài `finally`: `_operations_of` ném lỗi thì lifespan không được tắt (tiến trình thoát ngay sau, nên vô hại) | `tools/ci/h2.py:189-197` | `try/finally` |
| 15 | Nit | SEC-09 | `actions/checkout` để mặc định `persist-credentials: true`, nên token chỉ-đọc nằm trong `.git/config` suốt các bước chạy mã của PR. Artifact chỉ tải tệp cụ thể nên không lộ `.git`; rủi ro thấp | `ci.yml` (mọi `actions/checkout`) | `with: persist-credentials: false` |
| 16 | Nit | SEC | `actions: read` ở `codeql.yml:30` vượt [7], nhưng có lý do (mẫu của GitHub) và chỉ cần cho repo private | `.github/workflows/codeql.yml:25-30` | Giữ hay bỏ đều được; repo public thì không cần |
| 17 | Nit | R-36b | 4 commit merge không có trailer `Prompt:` | `a4f49a7`, `8a48ce4`, `7006a90`, `0e4c6ec` | Gộp squash, thân commit có `Prompt: B0-09` |
| 18 | Nit | MNT-04 | `[allowlist]` số ít là dạng cũ (gitleaks 8.x mới dùng `[[allowlists]]`). Bản 8.30.1 vẫn đọc được, nhưng chú thích "`[[allowlist]]` mảng lỗi" chỉ là đã thử sai tên khoá | `.gitleaks.toml:16`, chú thích `:9-10` | Sửa chú thích, hoặc chuyển sang `[[allowlists]]` |

## Kiểm sổ nợ (6 mục tác giả nêu)

| Mục nợ | Mức | Thuộc B0-09? | Lý do |
|---|---|---|---|
| trivy `web` `CVE-2026-31789` (`libssl3`/`libcrypto3` `3.3.5-r0` → `3.3.7-r0`) | P1 | **ngoài `so_huu`** (B0-08, `deploy/docker/web.Dockerfile`; [12] cấm `deploy/**`) | Có trong `m-trivy.log:609`. Ảnh đã có trên `main` từ trước; B0-09 chỉ làm lộ ra, không gây ra. Là **P1**, nên theo R-35/R-38 người điều phối phải ghi `DEBT.md` và giao FIX cho B0-08 (hoặc waiver đủ ticket/owner/deadline) thì mới gộp. Chưa sửa thì `build` đỏ ngay lượt CI thật đầu tiên |
| `tools/tests/test_services.py` xếp nhầm nhóm `unit` | P2 | **ngoài `so_huu`** (B0-01; [12] cấm `tools/tests/**`) | `ci_split.py` đã có lối thoát là marker tường minh (`_explicit_group_marker`). Chủ tệp chỉ cần gắn `@pytest.mark.ci_integration`. Runner có Docker nên job `unit` vẫn chạy được, chỉ sai nhóm |
| Tải model ảnh `ml` không thử lại | P2 | **ngoài `so_huu`** (`packages/ml_contracts/pinned.py`, `deploy/docker/ml.Dockerfile`) | Lộ ra do `docker builder prune -f` sau mỗi ảnh, và việc prune đó do [6] bắt. Trên CI, cache `type=gha` giữ được lớp này, nên chủ yếu hỏng khi chạy tại chỗ |
| Bước 8 CI chỉ xuất | P2 | **ngoài B0-09** (quyết định đã duyệt, hop-dong §4; gốc là BE-00 §13.2 cấm commit `openapi.json` và `steps.py` của B0-01) | Chú thích lý do có ở `ci.yml:62-65`. Xem thêm #12 |
| Ảnh H2 chép tay từ `services.py` | P3 | **một phần thuộc B0-09** | Muốn gom về một chỗ thì phải sửa ngoài `so_huu` (R-28). Test chống lệch thì làm được trong `so_huu`, xem #10 |
| Seed thật chưa có | P3 | **ngoài `so_huu`** (`packages/db/seeds`) | `h2._migrate_and_seed` đã gọi `apply_seeds(APP_ENV)`, nên sẽ tự nạp seed khi có |

Hiện `DEBT.md` chưa có dòng nào cho 6 mục này (#5).

## Điểm

Nit không trừ điểm.

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 (P3 #9; Nit #15, #16). Không nội suy, quyền tối thiểu, SHA/digest đều đúng, miễn gitleaks hẹp và đã kiểm | 1,00 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 2 (P1 #1; P2 #2, #3, #4; P3 #8) | 0,30 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 4 (P3 #7; Nit #14) | 0,40 |
| DB, API – Migration & contract | 10 % | 5 (H2 dùng dịch vụ thật, không danh sách miễn, có kiểm "chỉ 401") | 0,50 |
| TEST – Kiểm thử | 7 % | 3 (không test nào đi qua đường `job.sh lint` thật; mẫu Dependabot không thật; thiếu test `workflow_dispatch`) | 0,21 |
| OBS, OPS – Vận hành | 5 % | 3 (SARIF mất, #3; P3 #11) | 0,15 |
| MNT – Bảo trì | 3 % | 3 (P2 #6; P3 #10, #12; Nit #18) | 0,09 |

Tổng: 1,00 + 0,75 + 0,30 + 0,50 + 0,40 + 0,50 + 0,21 + 0,15 + 0,09 = **3,90 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Phần lớn nhánh là việc thật: cổng xanh (mã thoát 0, 8/8, 2456 passed, 99,06 % / 97,31 %), actionlint 0 lỗi, mọi SHA/digest khớp bằng chứng tự chạy, không lỗ SEC nào, H2 chạy trên hạ tầng thật, ma trận [8] có đủ test. Còn **một P1 chưa waiver (#1)**: trong CI, `pip-audit` thoát 1 thì bước đó hỏng trước khi `tools.ci.audit` kịp đọc danh sách miễn. Cơ chế miễn của [2]/[6] vì vậy không bao giờ chạy trên runner, và lỗ hổng đầu tiên (kể cả chưa có bản sửa) sẽ làm `lint` đỏ trên mọi PR mà không có cách miễn nào. Theo RULE.md §5, có P1 chưa waiver thì là REQUEST CHANGES.

Để được duyệt ở lượt 2:
1. **Sửa #1** trong `tools/ci/job.sh`, kèm test đi qua đúng đường `job.sh lint` (bắt buộc).
2. Sửa #2, #3, #4 (đều trong `so_huu`, mỗi mục vài dòng, kèm test), **hoặc** ghi mỗi mục một dòng `DEBT.md` có lý do đứng được.
3. Người điều phối ghi `DEBT.md` cho 6 mục nợ của tác giả (#5) và dòng `➖` cho #6. Riêng P1 CVE `web` (B0-08): giao FIX cho B0-08 hoặc waiver đủ ticket/owner/deadline, theo R-35/R-38.
4. P3 #7–#12 và Nit #13–#18 do tác giả/người điều phối quyết. P3 nào không sửa thì ghi một dòng `DEBT.md`.

Khi gộp: **squash** (một prompt, R-36), thân commit có khối trailer `Prompt: B0-09` đúng R-36b.
