# Review merge `fix/debt-01-tooling` → main

- Ngày: 2026-09-24 · Reviewer: phiên `/merge-review` (worktree `review-debt-01-tooling`, độc lập với tác giả)
- Nhánh: `fix/debt-01-tooling`, HEAD **`86b31b9c9600`**, 10 commit trên `main @ fc32836`
- Prompt: DEBT-01 việc T1 — FIX-083 (B0-01), FIX-084 (B0-09), FIX-085 (B0-05), FIX-101 (B0-01), FIX-102 (B0-01)
- Nợ trong phạm vi: NO-051, 101, 103, 105, 106, 108, 110, 111, 113, 118 (phần `job.sh`), 130, 153 (phần mã), 164, 175
- Diff: 21 file, +704 / −346. Trừ `uv.lock` (632 dòng, thuần định dạng — §2) còn ≈ 190 dòng mã/cấu hình + ≈ 280 dòng test.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (log `.cache/src-out/verify/20260924T04*-86b31b9c9600.log`, chạy tại chỗ trong RUNNER)
- Độ phủ: tổng **dòng 99,41 % · nhánh 98,19 %**

## 1. Điều kiện dừng sớm — không có

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` | rỗng |
| `changes/DEBT-01.md` | có (đã trên `main`, 6 dòng, nêu bước cổng nào áp dụng) |
| Conventional Commits + trailer `Prompt:` | 10/10 commit đạt; 5 commit có thêm `Fix:` |
| File cấm (`docs/charter/*`, `openapi.json` gốc, `APPFRONT_SHA`, `docs/contracts.toml`) | không chạm |
| `uv.lock` sửa tay | không — sinh bằng `run.sh lock` (§2) |
| K27 — mỗi commit một chủ | đạt: `17774f7`/`531c690`/`ad9ecab`/`ebe32cc`/`7eaa0f9`/`7ff240a` = B0-01 · `844fea3`/`a99fabb`/`86b31b9` = B0-09 · `5579b09` = B0-05 |
| K24 — `pragma: no cover`, `type: ignore` trần, `noqa` trần, `skip`/`xfail` mới, hạ ngưỡng | không có. 10/10 `# noqa` đều có mã (`S603`, `S607`) |

## 2. `uv.lock` — hai điều kiện người điều phối yêu cầu kiểm

Người điều phối đã duyệt trước việc commit `uv.lock` đầy đủ; reviewer kiểm lại hai điểm:

1. **Không gói nào đổi bản.** `git show fc32836:uv.lock | grep -E '^name = |^version = '` so với bản trên nhánh:
   311 dòng ↔ 311 dòng, `diff` **rỗng** (mã thoát 0). Thay đổi duy nhất mang nghĩa là
   `{ name = "redis", specifier = ">=8.1,<9" }`; 632 dòng còn lại là
   `marker = "platform_machine == 'x86_64' and sys_platform == 'linux'"` do uv 0.9.30 đổi cách in marker.
2. **Lock ổn định.** Chạy lại `VERIFY_NAME=lock-probe bash tools/verify/run.sh lock` trên nhánh này →
   `diff` với `uv.lock` đang commit **rỗng**, sha256 giống hệt (`1dbb6afb7f19…`). Worktree được phục hồi
   (`git checkout -- uv.lock`), `git status` rỗng. FIX-102 (ghim `verify.Dockerfile` theo tag+digest) đúng
   là gốc của NO-175.

## 3. Bảng E.10 — trạng thái từ mã thoát thật

`bash tools/verify/run.sh verify` (một lượt, RUNNER, trần 2 container `verify-run` được tôn trọng) — **mã thoát 0**:

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | đạt | 611 file |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | 9 hợp đồng, 0 vi phạm |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt | **3769 passed**, 4 deselected, 917 s |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 0 đơn vị bị chạm; 25 op đủ case |
| 6 | `lint_migrations` → `migrate_check` | đạt | 8 revision, 10/10 kiểm |
| 7 | H1 H3 H4 H5 | đạt | H4 `không áp dụng` (B3-05 chưa hợp nhất — đúng luật BE-00 §12) |
| 8 | `openapi` | đạt | |

**Bước 8 chạy thêm ở chế độ SO SÁNH thật.** Nhánh worker → `run.sh` đặt `VERIFY_BRANCH=worker`, nên lượt
cổng trên chỉ chạy bước 8 ở *chế độ xuất*: nó **không** chứng minh đường mới của FIX-101. Reviewer chạy
riêng `VERIFY_BRANCH=integration bash tools/verify/run.sh verify --steps 8`:

```
$ python -m apps.api.core.openapi --out /tmp/openapi.json --compare docs/contracts/openapi.json
openapi: đã ghi /tmp/openapi.json (58526 byte)
  8 | openapi | đạt      →  mã thoát 0
```

Bản tham chiếu đã commit **khớp** OpenAPI hiện tại, nên job `typecheck` của CI (giờ ép
`VERIFY_BRANCH=integration`) và bước 8 của nhánh tích hợp sẽ xanh sau khi gộp.

### Độ phủ — nghiệm thu NO-130 ([11].3)

| | Test | Tổng dòng | Tổng nhánh |
|---|---|---|---|
| **Trước** (`main @ 9f11ddf`, chưa có `concurrency`) | 3753 passed | 99,07 % | 97,74 % |
| **Sau** (`fix/debt-01-tooling @ 86b31b9`) | **3769 passed** | **99,41 %** | **98,19 %** |
| Δ | +16 | **+0,34 pp** | **+0,45 pp** |

Đúng như NO-130 dự đoán: `concurrency = ["thread", "greenlet"]` làm coverage ghi được dòng/nhánh chạy sau
`await` của SQLAlchemy async — không dòng nào *mất* phủ, chỉ có dòng trước đây bị tính khuyết nay được ghi.

Từng gói bị chạm (ngưỡng 90 % dòng **và** 90 % nhánh):

| Gói | Dòng | Nhánh |
|---|---|---|
| `packages/messaging` | 100,00 % | 100,00 % |
| `packages/testing` | 99,26 % | 97,37 % |
| `tools` | 98,90 % | 96,42 % |
| tập file bị chạm | 99,67 % | 97,27 % |

## 4. Kiểm riêng của reviewer (không tin báo cáo tác giả)

### 4.1 Test đỏ trên `main` rồi xanh trên nhánh (FIX.md luật 1) — đo thật, không suy diễn

Trong container verify: chép `/src` → `/tmp/w`, ghi đè **9 file nguồn** bằng bản `fc32836`
(`tools/verify/run.sh`, `tools/verify/steps.py`, `tools/ci/job.sh`, `tools/ci/h2.py`,
`packages/testing/fixtures/services.py`, `deploy/compose/verify.yml`, `deploy/docker/verify.Dockerfile`,
`.github/workflows/ci.yml`, `.github/dependabot.yml`), xoá `tools/pinned_images.py`, **giữ nguyên test của
nhánh**, rồi chạy 16 test mới/sửa. Kết quả: **12 failed, 3 passed, 1 error** — vượt yêu cầu "ít nhất 3 cái
rủi ro nhất".

| Nợ | Test | Trên `main` | Bằng chứng |
|---|---|---|---|
| NO-101/164 | `test_gc_lowercases_and_normalizes_worktree_names` | **đỏ** | `tr: range-endpoints of '_-\012' are in reverse collating sequence order`, `run.sh gc` thoát 1 |
| NO-106 | `test_pinned_images.py` | **đỏ** | `ImportError: cannot import name 'pinned_images'` |
| NO-108 | `test_verify_yml_volume_has_fixed_shared_name` / `..._service_has_fixed_non_latest_image` | **đỏ** | `TypeError: 'NoneType' object is not subscriptable` / `KeyError: 'image'` |
| NO-175 | `test_every_from_line_pins_tag_and_digest` | **đỏ** | `FROM chưa ghim tag+digest: node:26-bookworm-slim` |
| NO-105 | `test_bước_8_integration_so_với_bản_commit` | **đỏ** | `'openapi.json' != 'docs/contracts/openapi.json'` |
| NO-105 | `test_job_sh_typecheck_compares_committed_openapi_reference` | **đỏ** | `'docs/contracts/openapi.json' not in job.sh` |
| NO-110 | `test_ci_yml_pull_request_types_include_edited` | **đỏ** | `KeyError: 'types'` |
| NO-118 | `test_job_sh_smoke_uses_web_port_for_api_paths_not_api_host_port` | **đỏ** | `'API_HOST_PORT' is contained here` |
| NO-051 | `test_job_contract_exports_writable_verify_out_dir` | **đỏ** | `python giả không được gọi với VERIFY_OUT_DIR đã đặt` |
| NO-113 | `..._passes_at_minimum`, `test_job_build_calls_nginx_version_check` | **đỏ** | `job_build_check_nginx_version: command not found` (127) |
| NO-153 | `test_dependabot_yml_ignores_semver_major_for_every_ecosystem` | **đỏ** | `AssertionError: uv` |
| NO-111 | `..._gitleaks_fails_closed_on_empty_git_history`, `..._trivy_mounts_host_sarif_dir` | **xanh** | đúng kỳ vọng — NO-111 là nợ *thiếu test*, hành vi đã đúng từ trước |
| NO-113 | `..._fails_below_minimum` | **xanh** | **không đúng kỳ vọng** → finding F3 |

Trên nhánh: cả 16 test nằm trong 3769 passed của bước 5.

### 4.2 NO-108 — hai lượt verify song song, một ảnh, một volume (đo thật)

Chạy **đồng thời** hai container `verify-run` (đúng trần máy 2, đếm trước = 0 rồi mới phóng cái thứ hai):
`appback-verify-review-debt-01-tooling-verify-run-*` (cổng đầy đủ, đang ở bước 5) và
`appback-verify-parallel-probe-verify-run-*` (`VERIFY_NAME=parallel-probe`, mô phỏng worktree thứ hai).

- **Một ảnh:** cả hai build ra `appback-verify:local`; lượt thứ hai `CACHED` toàn bộ layer. `docker images`
  trước fix có 6 ảnh `appback-verify-<worktree>-verify:latest` 662 MB mỗi cái; nhánh này sinh **một** ảnh 662 MB.
- **Một volume:** `docker volume ls` — `appback-work` (tên cố định) bên cạnh 5 volume
  `appback-verify-<worktree>_appback-work` cũ của các worktree chưa có fix. `df -h /work` trong cả hai
  container cùng trỏ `/dev/sdd` 1007 G, 36 G đã dùng.
- **Không giẫm nhau:** `/work` chứa `venv-review-debt-01-tooling` và `venv-parallel-probe` riêng, `mypy-<tên>`
  riêng (nhờ `UV_PROJECT_ENVIRONMENT=/work/venv-${VERIFY_NAME}`), dùng chung `uv-cache` và
  `contract-node/3c583539a0314ecd`. `uv sync --locked` của lượt probe hoàn tất trong khi lượt cổng đang chạy
  pytest; cả hai thoát 0, bước 5 của cổng vẫn 3769 passed. **Đạt.**
- Phần thưởng của NO-101/164: `/work` còn `venv-fix-b0-01-fast-verify`, `venv-fix072-fast-startup`,
  `venv-debt-01-tooling` của worktree đã xoá — nay `run.sh gc` chạy được nên dọn được.

### 4.3 Các kiểm khác

- **NO-101/164 hết lỗi `tr`:** `run.sh gc` trong test thoát 0 và truyền `VERIFY_VALID_NAMES` chứa
  `b7-01_extra` (hoa → thường, giữ cả `_` và `-`). Đúng bản chữa mà dòng nợ đề xuất.
- **NO-113 không cần T2 mới xanh:** `deploy/docker/web.Dockerfile:15` ghim
  `nginxinc/nginx-unprivileged:1.31.5-alpine` → 1.31.5 > 1.30.4, và `job_build_one_image` gắn tag
  `appback-web:ci` đúng tên mà `job_build_check_nginx_version` gọi. Job `build` của CI không đỏ vì bước mới này.
- **NO-051 khoanh đúng vùng:** `CONTRACT_SAMPLES_DIR` chỉ được đặt ở job `contract` (`ci.yml:173`) và trong
  `job_contract`; `OUT_DIR` của `steps.py` đọc `VERIFY_OUT_DIR` ở mức module, nên `export` trước khi gọi
  `python -m tools.verify.steps` là chỗ sửa đúng, không job nào khác bị ảnh hưởng.
- **NO-110 thật sự có tác dụng:** `commits` đọc tiêu đề qua `PR_TITLE: ${{ github.event.pull_request.title }}`
  (`ci.yml:240`) — payload của `edited` mang tiêu đề mới, nên chạy lại là có nghĩa (không phải no-op).
- **`.importlinter`:** `root_packages = packages, apps` — không xét `tools`, nên
  `packages.testing → tools.pinned_images` không sinh vi phạm; bước 4 đạt. Xem F6 về mặt thiết kế.

## 5. Finding

Không có P0, P1, P2.

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| F1 | P3 | MNT-05 | `test_pinned_service_images_match_packages_testing` giờ **trùng lặp theo cấu trúc** (hai vế cùng đọc `tools.pinned_images`) nên không chặn được gì, nhưng docstring vẫn khẳng định "R-28 … nên không tự gom về một chỗ được" — điều FIX-083 vừa chứng minh là sai. Test đọc như một cổng còn hiệu lực trong khi nó đã rỗng nghĩa. | `tools/ci/tests/test_h2.py:243-250` | Xoá test (NO-106 nay là bảo đảm cấu trúc) hoặc đổi thành kiểm hai nơi *nhập* cùng một module, và viết lại docstring. |
| F2 | P3 | OPS-03 | `job_build_smoke` bỏ `export API_HOST_PORT="${API_HOST_PORT:-18000}"` trong khi `deploy/compose/ci.yml:87` **trên nhánh này** vẫn publish `127.0.0.1:${API_HOST_PORT:-8000}:8000` (việc bỏ là của T2, nhánh khác). Tới khi T2 gộp, `bash tools/ci/job.sh build` bind cổng host 8000 — đúng lớp xung đột cổng mà các override 18080/15432 tồn tại để tránh (máy này: Apache giữ 8080, Postgres giữ 5432). Test lại chốt `assert "API_HOST_PORT" not in text`, khoá luôn cách vá an toàn. | `tools/ci/job.sh:378-386`; `tools/ci/tests/test_workflows.py:189-191` | Gộp T2 trước (ghi rõ thứ tự), hoặc giữ `export API_HOST_PORT="${API_HOST_PORT:-18000}"` (vô hại sau khi T2 bỏ `ports:`) và nới assert thành "không `curl` nào dùng `API_HOST_PORT`". |
| F3 | P3 | TEST-04 | `..._fails_below_minimum` chỉ khẳng định `returncode != 0`, nên **xanh trên `main`** nơi hàm chưa tồn tại (đo được: thoát 127 `command not found`). Nó không chứng minh phép so phiên bản thật sự từ chối nginx cũ. | `tools/ci/tests/test_workflows.py:456-458` | `assert result.returncode == 1` (phán quyết của `sort -C`) — sẽ đỏ trên `main`. |
| F4 | P3 | PERF-07 | `types: [..., edited]` chạy lại **cả chín job** (kể cả `build` timeout 45 phút, `integration`/`contract` 30 phút) mỗi lần sửa tiêu đề *hoặc thân* PR, trong khi NO-110 chỉ cần job `commits`. Không job nào có `if:`. Dòng nợ đã nêu phương án rẻ hơn ("hoặc chạy `commits` bằng workflow riêng nghe `edited`"). Repo public nên không tốn phí phút (`ci.yml:37`) — thiệt hại là độ trễ phản hồi và nhiễu. | `.github/workflows/ci.yml:14` | `if: github.event.action != 'edited'` cho tám job còn lại, hoặc tách `commits` sang workflow riêng. |
| F5 | P3 | SEC-11 | `NGINX_MIN_VERSION` là **một** sàn duy nhất so bằng `sort -V`, nhưng ảnh chạy nhánh **mainline** 1.31.5 còn sàn là số của nhánh **stable** 1.30.4. Nếu một bản vá ra đồng thời ở 1.30.5 và 1.31.6 mà ảnh còn 1.31.5, `sort -V` kết luận 1.31.5 > 1.30.5 → **xanh giả** đúng lúc cần chặn. Đây là biện pháp bù cho một nợ P2, nên lỗ này đáng ghi. | `tools/ci/job.sh:36-40, 356-363` | Ghim sàn **theo từng nhánh phát hành** (map `1.30 → 1.30.4`, `1.31 → 1.31.x`), hoặc buộc ảnh `web` ở nhánh stable để một sàn có nghĩa. |
| F6 | P3 | MNT-04 | `packages/**` nay nhập `tools/**` — đảo chiều tầng (tooling là lớp ngoài cùng). `.importlinter` chỉ có `root_packages = packages, apps`, nên **không gì** giữ cho `tools.pinned_images` khỏi mọc phụ thuộc. Dòng NO-106 đã đề nghị `packages/core` chính vì lẽ đó. | `packages/testing/fixtures/services.py:29-31`; `tools/pinned_images.py` | Dời ba hằng sang `packages/core`, hoặc thêm `tools` vào `root_packages` kèm một hợp đồng `forbidden`. Không chặn merge: module chỉ có 3 hằng, `PYTHONPATH` = gốc repo ở mọi nơi chạy. |

### Nit (không chặn merge)

- **N1** `deploy/compose/verify.yml:47-50` — mọi lượt verify từ nay in
  `volume "appback-work" already exists but was created for project "appback-verify-concurrency-test-a"`
  (đo được ở cả log cổng và log probe): volume mang nhãn project của phép thử dùng-một-lần của tác giả.
  Vô hại nhưng là cảnh báo vĩnh viễn trong mọi log cổng, dễ bị đọc thành lỗi. Xoá `appback-work` một lần
  khi không còn lượt verify nào đang chạy, hoặc khai `external: true` và tạo volume tường minh.
- **N2** Hai lý giải trong chú thích không khớp số đo: `verify.yml:44-46` nói volume riêng mỗi worktree
  "làm `UV_LINK_MODE=hardlink` mất tác dụng" — hardlink vẫn chạy tốt *trong* mỗi volume riêng; thứ mất là
  việc **dùng lại cache giữa các worktree**. `tools/tests/test_run_sh.py:104-106` nói lỗi `tr` xảy ra
  "ngay khi tên worktree có cả `_` lẫn `-`" — đo được: nó hỏng **vô điều kiện**, mọi lượt `gc`, bất kể tên.
  Bản sửa vẫn đúng; chỉ lý giải cần chỉnh.
- **N3** `tools/tests/test_pinned_images.py` chỉ khẳng định "không phải `:latest`" và "có dấu `:`" — yếu hơn
  `test_verify_dockerfile.py` (đòi tag+digest) dù cùng mục đích K29.
- **N4** `tools/ci/job.sh:358` `grep -oE … | head -n1` dưới `pipefail`; `grep -m1` gọn hơn và không tạo
  trạng thái 141 tiềm năng (ở đây vô hại vì `run_step` gọi hàm trong điều kiện `if` nên `errexit` đã tắt).
- **N5** Tên test mới dùng `test_<snake_case>` thay vì dạng dự phòng `test_<hàm>__<điều kiện>` của prompt [8].
  Khớp với các test `tools/` có sẵn, nhưng độ lệch này không được ghi vào "Lệch khỏi prompt" của báo cáo.

## 6. Sổ nợ

### 6.1 Từng NO trong phạm vi — đóng được khi merge hay không

| NO | Đóng được? | Lý do |
|---|---|---|
| NO-051 | **✅ được** | Sửa đúng chỗ (`job_contract` export `VERIFY_OUT_DIR` cùng lúc với `CONTRACT_SAMPLES_DIR`); test đỏ trên `main`; không job nào khác bị ảnh hưởng (§4.3). |
| NO-101 | **✅ được** | Đo đỏ→xanh; đúng bản chữa dòng nợ đề xuất. |
| NO-103 | **✅ được** | `@pytest.mark.ci_integration` gắn đúng test mà dòng nợ nêu tên; `_explicit_group_marker` ưu tiên marker tường minh. |
| NO-105 | **✅ được** | Bước 8 chế độ so sánh chạy thật → đạt (§3); job `typecheck` ép `VERIFY_BRANCH=integration`. Người dùng đã duyệt bản tham chiếu. |
| NO-106 | **✅ được** | Một nguồn duy nhất, lệch là không thể theo cấu trúc. Kèm F1 + F6 thành nợ mới. |
| NO-108 | **✅ được** | Đo hai lượt song song, một ảnh, một volume, venv/mypy tách (§4.2) — đúng phép kiểm dòng nợ đòi. Kèm N1. |
| NO-110 | **✅ được** | `edited` có tác dụng thật (§4.3). Kèm F4 thành nợ mới. |
| NO-111 | **✅ được** | Hai test đi qua đúng `job.sh` với `git`/`docker` giả. Xanh trên `main` là **đúng** cho nợ thiếu-test. |
| NO-113 | **✅ được** | Kiểm nối vào `job_build`, tên ảnh khớp, 1.31.5 > 1.30.4. Kèm F5 thành nợ mới. |
| NO-118 | **🔧 chưa** | Chỉ nửa `tools/ci/job.sh`. Chủ mà dòng nợ nêu là **B0-08 (`deploy/compose/ci.yml`)** và triệu chứng gốc (`--scale api=2` trùng cổng) vẫn còn trên nhánh này. Giữ 🔧 tới khi T2 gộp; xem F2 về rủi ro cổng 8000 trong khoảng giữa. |
| NO-130 | **✅ được** | Đo trước/sau: 99,07 → 99,41 % dòng, 97,74 → 98,19 % nhánh (§3). |
| NO-153 | **🔧 chưa** | Hai lớp mã xong (`redis>=8.1,<9` + `ignore` semver-major). Nửa "bật required status check cho `main`" là thao tác GitHub — **cổng người** (prompt [7]), chưa làm. Giữ 🔧. Xem F5 về tác dụng phụ của `ignore` trần. |
| NO-164 | **✅ được** | Cùng một bản sửa với NO-101. |
| NO-175 | **✅ được** | Ghim tag+digest; lock tất định, đo lại = 0 diff (§2). |

### 6.2 Nợ mới (người điều phối chép vào `DEBT.md`)

1. F1 — `test_pinned_service_images_match_packages_testing` rỗng nghĩa + docstring đã sai. Chủ B0-09. P3.
2. F2 — `job.sh` smoke bỏ `API_HOST_PORT` trước khi `ci.yml` bỏ `ports:` của `api`; test khoá luôn cách vá
   an toàn. Chủ B0-09 (+ B0-08 cho nửa `ci.yml`). P3. Tự hết khi T2 gộp, nhưng assert cần nới.
3. F3 — `..._fails_below_minimum` assert quá yếu, xanh trên `main` vì hàm không tồn tại. Chủ B0-09. P3.
4. F4 — `pull_request: edited` chạy lại cả chín job thay vì riêng `commits`. Chủ B0-09. P3.
5. F5 — `ignore` semver-major trần cho cả ba hệ: hệ `docker` **không có** kênh security-update, nên bản
   major của ảnh nền (vd `node:26` → `27`) sẽ không bao giờ được đề xuất nữa, mà digest lại vừa bị ghim
   cứng → cũ đi một cách vô hình. Kèm lỗ sàn nginx một-nhánh-phát-hành. Chủ B0-09. P3.
6. F6 — `packages/**` nhập `tools/**`, `.importlinter` không xét `tools`. Chủ B0-01. P3.
7. (tác giả nêu, chưa có dòng `DEBT.md`) `tools/ci/job.sh` luôn `cd "$REPO_ROOT"` khi được `source` → nhánh
   "máy cục bộ, không có `RUNNER_TEMP`" của `job_build_trivy` không kiểm cô lập được bằng
   `subprocess(cwd=…)`. Chủ B0-09. P3, giới hạn test chứ không phải lỗi hành vi.
8. (tác giả nêu, chưa có dòng `DEBT.md`) `docs/contracts/openapi.json` phải đồng bộ tay với
   `apps/api/core/openapi.py`; không có cơ chế nào báo khi nó cũ, ngoài chính bước 8 trên nhánh tích hợp.
   Chủ người điều phối. P3 — và giờ đây nó là **cổng CI**, nên bản cũ làm job `typecheck` đỏ cho mọi PR.
9. N1 — volume `appback-work` mang nhãn project `appback-verify-concurrency-test-a` nên mọi lượt verify in
   cảnh báo. Chủ B0-01. Nit.

Tác giả không mở dòng `DEBT.md` nào cho mục 7–8 theo chỉ đạo của người điều phối (nợ mới ghi trong phán
quyết, người điều phối chép sang). Đây là lệch quy trình so với R-34 nhưng **có chỉ đạo**, nên không tính
là finding.

Không có nợ `P0`/`P1` nào còn `mở` thuộc phạm vi nhánh này → không có điều kiện chặn merge theo R-35/R-38.

## 7. Điểm

| Miền | Trọng số | Điểm | Tích | Ghi chú |
|---|---|---|---|---|
| SEC – Bảo mật | 25 % | 4 | 1,00 | F5 (P3). Nhánh này *tăng* thế bảo mật: ghim digest, sàn nginx, chặn major tự gộp. |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 | Đo hai lượt verify song song trên volume dùng chung: không giẫm nhau. |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 | `tr`, `sort -C -V`, `VERIFY_OUT_DIR` đều đúng ở mọi case đã thử. |
| PERF – Hiệu năng | 10 % | 4 | 0,40 | F4 (P3). |
| RES – Chịu lỗi | 10 % | 5 | 0,50 | `job_lint_gitleaks` hỏng-an-toàn đã có test; timeout giữ nguyên. |
| DB, API – Migration & contract | 10 % | 5 | 0,50 | Bước 6 và bước 8 (chế độ so sánh thật) đều đạt; không revision mới. |
| TEST – Kiểm thử | 7 % | 4 | 0,28 | F1, F3 (P3). Mặt khác: 12/16 test đo được đỏ trên `main`. |
| OBS, OPS – Vận hành | 5 % | 4 | 0,20 | F2 (P3). |
| MNT – Bảo trì | 3 % | 4 | 0,12 | F6 (P3). |
| **Tổng** | **100 %** | | **4,50 / 5** | |

## 8. PHÁN QUYẾT: APPROVE

Nhánh làm đúng việc T1: mười hai trong mười bốn dòng nợ đóng được ngay, cổng đầy đủ tám bước xanh với mã
thoát 0, và — điểm quan trọng nhất — **luật 1 của FIX.md được chứng minh bằng số đo, không bằng lời**: ghi
đè chín file nguồn về bản `fc32836` rồi chạy lại đúng bộ test của nhánh cho 12 failed + 1 error, mỗi cái
khớp đúng triệu chứng mà dòng nợ tương ứng ghi. Phép kiểm mà NO-108 đòi và tác giả bỏ lại cho reviewer
(hai lượt verify song song trên một volume chung) đã chạy thật và đạt: một ảnh `appback-verify:local`, một
volume `appback-work`, `venv-<tên>`/`mypy-<tên>` tách theo `VERIFY_NAME`, `uv-cache` và
`contract-node/<băm>` dùng chung mà không tranh chấp. `uv.lock` đạt cả hai điều kiện người điều phối đặt:
không gói nào đổi bản, và `run.sh lock` chạy lại cho diff rỗng — FIX-102 đúng là gốc của NO-175. NO-130 có
số đo hai đầu và đi đúng hướng (+0,34 pp dòng, +0,45 pp nhánh). Tôi cũng tự bịt lỗ mà bảng E.10 không nói:
bước 8 trên nhánh worker chạy chế độ *xuất*, nên tôi chạy riêng chế độ *so sánh* — đạt, nghĩa là job
`typecheck` của CI và nhánh tích hợp sẽ xanh sau khi gộp.

Sáu finding đều P3 và không cái nào chạm đường chạy thật của sản phẩm: bốn cái là chất lượng test/cấu hình
CI, một cái là lỗ trong biện pháp bù CVE nginx khi bản vá ra đồng thời trên hai nhánh phát hành, một cái là
chiều phụ thuộc tầng. Không P0/P1/P2 → không có gì phải sửa trước khi gộp.

**Hai điều người điều phối phải làm khi gộp** (không phải điều kiện của APPROVE, nhưng bỏ sót sẽ sai sổ):
NO-118 và NO-153 **giữ `🔧`, không đóng `✅`** — NO-118 vì nửa `deploy/compose/ci.yml` thuộc T2, NO-153 vì
nửa "bật required status check cho `main`" là cổng người ở prompt [7] và chưa ai làm. Và nên gộp T2 trước
hoặc cùng đợt (F2): khoảng giữa hai lần gộp là khoảng `job.sh build` bind cổng host 8000.
