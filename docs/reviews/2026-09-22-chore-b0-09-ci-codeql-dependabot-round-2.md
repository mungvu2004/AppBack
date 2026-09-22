# Review merge chore/b0-09-ci-codeql-dependabot → main (lượt 2)

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập**, lượt 2. Tôi không phải tác giả, không phải người điều phối, cũng không phải reviewer lượt 1. Phiên này không sửa mã và không merge. Mọi khẳng định trong `bao-cao-m-fix2.md` đều được kiểm lại bằng diff, cổng và probe tự chạy · Commit đầu nhánh: `70cf94674e42` · merge-base với `main` = `751d606`. `main` đã đi thêm tới `0a4d3dc`, nhưng chỉ đổi `DEBT.md` và phán quyết lượt 1; `git merge-tree --write-tree main HEAD` sạch. `git diff main...HEAD`: 23 tệp, +3 909 dòng, 0 xoá. Vòng sửa `16e2a5d..70cf946` gồm 6 commit: 10 tệp, +455/−66.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, chạy tại chỗ trên `70cf946` từ worktree `b0-09-m-merge`, sạch trước và sau. Lúc khởi động có 0 container `verify-run`. `MSYS_NO_PATHCONV=1 docker wait appback-verify-b0-09-m-merge-verify-run-17eb50d5e12e` = 0. Log host ở `.cache/src-out/verify/20260922T145244Z-70cf94674e42.log`, bản sao `docker logs -f` ở scratchpad của phiên. Kết quả `2467 passed, 10 skipped, 1 deselected` (313,3 s); `tools/ci/tests` xanh hết (test_workflows 29, test_audit 13, …).
- Độ phủ: tổng dòng **99,06 %** · nhánh **97,32 %**; `tools` 98,75 · 95,70; `packages/testing` 99,24 · 100; tập file bị chạm 98,93 · 96,32.

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (0 đơn vị perf bị chạm) |
| 6 | `lint_migrations` → `migrate_check` | đạt (5 revision, 9 kiểm) |
| 7 | H1 H3 H4 H5 | đạt. H4/H5 `không áp dụng` hợp lệ vì B3-05/B4-01 chưa hợp nhất (BE-00 §12) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill, áp cho toàn nhánh)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt: worktree trước, sau verify và sau mọi probe; `main` trước khi ghi tệp này |
| `changes/B0-09.md` | có, 11 dòng (thêm dòng bước 8 theo #12) |
| Dòng đầu Conventional Commits ≤ 72 | đạt: cả 16 commit không-merge qua đúng `.githooks/commit-msg`, dài nhất 71 ký tự (`827178b`). 6 commit mới dài 51–62 ký tự |
| Trailer `Prompt:` | 16/16 commit không-merge đọc được `B0-09` (`%(trailers:key=Prompt,valueonly)`). 4 commit merge mất khi squash (#17) |
| Đụng file cấm ([12], B0-01 [7]) | không: `git diff --name-only main...HEAD` ra 23 tệp, lọc theo `so_huu` thì còn lại rỗng |
| `pragma` / `type: ignore` không mã / `noqa` trần / `skip` / `xfail` / hạ ngưỡng / `continue-on-error` | không. Grep phần thêm của diff chỉ ra: `continue-on-error` trong assert của test; `--no-verify` trong fixture `test_commits.py` (`git commit` trên repo tạm `tmp_path` để dựng commit sai mẫu, không phải lách hook của repo). Mọi `noqa` đều có mã |
| `conftest.py` lồng, cấu hình công cụ riêng | không |

## Bằng chứng tự chạy (không dùng số của tác giả)

| Kiểm | Kết quả |
|---|---|
| actionlint `1.7.12@sha256:b1934ee5…` trên `ci.yml`, `codeql.yml` | **0 lỗi**, mã thoát 0 (`-verbose`: "Found 0 errors in 2 files") |
| SEC workflow | Không `run:` nào chứa `${{ … }}`; `github.event.*` chỉ vào `env:` (`ci.yml:233-240`). Không `pull_request_target`, `secrets.`, `environment:`, `continue-on-error`. `needs:` chỉ ở `coverage` (`ci.yml:255`), và job này không có `if:`. Ở `build`, `if: always()` chỉ đặt ở **bước** upload SARIF (`ci.yml:223-228`), không ở cấp job. `persist-credentials: false` có ở 12/12 `actions/checkout` của `ci.yml` |
| SHA action | Vòng sửa không thêm SHA nào mới: bước upload mới dùng lại `actions/upload-artifact@043fb46d…`, và `git ls-remote …/upload-artifact refs/tags/v7.0.1` ra đúng `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` (tag nhẹ). 7 SHA còn lại không đổi từ lượt 1, lượt đó đã khớp `ls-remote` |
| #1: 3 test mới đi qua `job.sh` + `uvx` giả | `pytest tools/ci/tests/test_workflows.py -k job_sh_pip_audit` → **3 passed** |
| #1: ca tôi tự thêm, qua `source job.sh; job_lint_audit` với `uvx` giả | rc=1, stdout **rỗng** → bước pip-audit `hỏng`, `tools.ci.audit` `chưa chạy`, `FAILED=1` ✔. rc=1, stdout không phải JSON → `tools.ci.audit` `hỏng` (JSONDecodeError), `FAILED=1` ✔. rc=124 (timeout) → `hỏng` ✔. rc=1, lỗ hổng chưa có bản sửa → đạt, chỉ in ✔ (đúng [6]). rc=0 sạch → đạt ✔. Biên: rc=1 với JSON `{}` → **đạt** (xem Nit N3) |
| #1 + #9: `job_lint_audit` **thật** trên `uv.lock` của nhánh (pip-audit 2.10.1 thật, OSV) | Lần 1 trong probe: bước pip-audit `hỏng`, JSON rỗng. Stderr bị bộ lọc của probe bỏ mất, nên chưa rõ nguyên nhân; có thể lỗi mạng tạm thời tới OSV ngay sau loạt truy vấn trước đó. Như vậy cổng đã fail-closed đúng, và trên CI `job.sh:152` in stderr. Lặp lại 2 lần thì đều **đạt**: qua `job.sh` 44 s (`uv export` đạt → pip-audit đạt → `tools.ci.audit: đạt`); gọi thẳng osv 54 s rc=0; dịch vụ PyPI mặc định 19 s rc=0. 141 dòng requirements, có `torch==2.14.0+cpu`, `torchvision==0.29.0+cpu` |
| #9: OSV có khớp bản local `+cpu`, và có trả `fix_versions` không | `torch==1.13.0+cpu` → rc=1, **30 lỗ hổng, 25 có `fix_versions`**, trùng khít `torch==1.13.0` (30/25). `jinja2==2.10` qua OSV → rc=1, 12/12 có `fix_versions`. Vậy đổi sang OSV không làm `audit.py` mù: lỗ hổng có bản sửa vẫn làm cổng hỏng |
| #8 trong đúng ngữ cảnh của README §6 (container verify, binary gitleaks) | Worktree có `.git` là tệp trỏ `F:/AppBack/.git/worktrees/…`, nên `git rev-list --count --all` lỗi. Chặn mới in `gitleaks: hỏng — git rev-list --count --all = 0 …`, `FAILED=1` ✔ (lượt 1 ở đây là xanh giả) |
| #13 | `python -m tools.ci.h2 x` → mã thoát **2** ✔ |
| #7 | `python -m tools.verify.steps verify --steps 0` đứng riêng → `0 làm ấm node_modules đạt`, rc=0. `steps.py:272-276` chỉ lọc theo tập số, nên `--steps 0` hợp lệ ✔ |
| `DEBT.md` trên `main` `0a4d3dc` | NO-102…NO-107 phủ đủ 6 mục nợ tác giả nêu (#5); NO-109 `➖` cho #6, có lý do (như NO-091). Thêm NO-108 (volume verify, B0-01) |
| NO-102 (P1, CVE `web`, chủ B0-08) | **Không tính vào nhánh này.** FIX-070 đang sửa ở nhánh riêng `fix/b0-08-web-openssl-cve`, có review riêng; nhánh đó hiện chưa có commit nào ngoài `main`. Xem điều kiện gộp ở cuối |

## Đối chiếu finding lượt 1

| # | Mức | Kết luận lượt 2 | Bằng chứng |
|---|---|---|---|
| 1 | P1 | **Đã sửa thật** | `tools/ci/job.sh:126-162`: `rc` lấy bằng `\|\| rc=$?`; `rc > 1` → hỏng; JSON rỗng → hỏng; rc 0 hay 1 đều chuyển cho `tools.ci.audit` (`job.sh:177-179`). Test chốt `test_workflows.py:243`, `:251`, `:258` nguồn thẳng `job.sh` với `uvx` giả, cộng 6 ca tôi tự chạy và một lượt pip-audit thật trên lock (bảng trên) |
| 2 | P2 | **Đã sửa thật** | `commits.py:59-69`: nhận `workflow_dispatch`; `BASE_SHA` rỗng → zero-SHA → chỉ kiểm `HEAD_SHA` (`commit_headers`, `:117-118`). Test `test_commits.py:243` (đạt), `:259` (sai mẫu → 1). Dư: xem Nit N4 |
| 3 | P2 | **Đã sửa thật** (đọc mã và test YAML; không chạy `job.sh build` vì máy thiếu RAM) | `job.sh:319-343` mount `${RUNNER_TEMP}/trivy` (hoặc `.cache/trivy`, đã ignore theo `.gitignore:13`) vào `/out`; `ci.yml:223-228` upload `trivy-sarif`, `if: always()` ở mức bước. Test `test_workflows.py:141`. Không có test đi qua `job_build_trivy` (xem N2) |
| 4 | P2 | **Đã sửa** phần có trong `so_huu` | `commits.py:199-200`: `dependabot/**` bỏ kiểm dòng đầu từng commit, vẫn kiểm tiêu đề PR. Mẫu test theo định dạng thật (`test_workflows.py:373`, `test_commits.py:273`, `:295`); README `:70-74`. Riêng hướng dẫn "rút tiêu đề PR" chưa làm check xanh được, xem **N1** |
| 5 | P2 | Đóng | Người điều phối ghi NO-102…NO-107 ở `0a4d3dc` |
| 6 | P2 | Đóng (chấp nhận) | NO-109 `➖`, lý do đứng được |
| 7 | P3 | **Đã sửa thật** | `job.sh:219` (integration), `:240` (contract, trước pytest sinh mẫu); đã chạy `--steps 0` thật |
| 8 | P3 | **Đã sửa thật** cho các đường README ghi | `job.sh:106-109`; đã chạy thật trong container. Dư: chặn chạy trên host, còn nhánh `docker run` quét trong container, nên chỉ đường không được README ghi (Git Bash + worktree) là còn lệch ngữ cảnh. Runner CI clone thường nên không dính. Không có test (N2) |
| 9 | P3 | **Đã sửa thật** | `job.sh:149-151` `--vulnerability-service osv`, đã xoá `--extra-index-url` chết; đo OSV khớp `+cpu` (bảng trên) |
| 10 | P3 | **Đã sửa** (test chống lệch) | `test_h2.py:226-233`; gốc ghi NO-106 |
| 11 | P3 | **Đã sửa** | `README.md:32-35` |
| 12 | P3 | **Đã sửa** | `changes/B0-09.md:9-11`; chú thích `ci.yml:65-68` trỏ đúng |
| 13 | Nit | **Đã sửa** | `h2.py:380`; `python -m tools.ci.h2 x` → 2 |
| 14 | Nit | **Đã sửa** | `h2.py:193-206` `try/finally` |
| 15 | Nit | **Đã sửa** ở `ci.yml` (đúng phạm vi lượt 1) | 12/12 checkout; test `test_workflows.py:131`. `codeql.yml:36` chưa có, xem N5 |
| 16 | Nit | Giữ, lý do đứng được | `codeql.yml:25-30` có chú thích nguồn |
| 17 | Nit | Mất khi squash | Không đổi |
| 18 | Nit | **Đã sửa** | `.gitleaks.toml:8-13` |

## Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | P3 | LOG-02 / OPS-02 | **Cách vòng qua của #4 ("người điều phối rút tiêu đề PR ≤ 72 trước khi squash") không làm check `commits` xanh lại.** `pull_request:` không khai `types`, nên chỉ nhận `opened`, `synchronize`, `reopened` (mặc định của GitHub). Sửa tiêu đề PR (`edited`) không kích hoạt lượt mới. "Re-run jobs" dùng lại payload của sự kiện gốc, nên `PR_TITLE` (`ci.yml:237`) vẫn là tiêu đề dài cũ. Vì vậy PR Dependabot hệ `docker` sẽ đỏ `commits` đến khi có push mới, mà push vào nhánh Dependabot thì Dependabot thôi quản nhánh đó. Chỉ còn đường admin bypass. Người sửa tiêu đề PR sai của người thường cũng gặp y như vậy. Mức tin: PLAUSIBLE, dựa trên hành vi đã công bố của GitHub (activity types mặc định, re-run giữ payload); chưa thể tái hiện vì repo chưa đẩy lên | `.github/workflows/ci.yml:9-10`, `:237`; `tools/ci/README.md:70-74` | Tách kiểm tiêu đề PR ra một workflow nhỏ `on: pull_request: types: [opened, edited, synchronize, reopened]`, hoặc thêm `edited` cho `ci.yml` (sẽ chạy lại cả 9 job khi sửa tiêu đề hay mô tả, nên cách tách rẻ hơn). Tối thiểu: README nói rõ phải có lượt kích hoạt mới, hoặc dùng bypass admin |
| N2 | P3 | TEST-01 | Hai nhánh mới của `job.sh` không có test chốt: chặn 0 commit của gitleaks (#8, `job.sh:106-109`) và mount SARIF của trivy (#3, `job.sh:326-342`; test chỉ quét YAML). Nếu ai đó xoá chặn gitleaks thì không test nào đỏ. `job.sh` đã source được, và mẫu `_run_job_lint_audit` sẵn có, nên thêm test chỉ tốn vài dòng | `tools/ci/tests/test_workflows.py` (thiếu) | Test nguồn `job.sh`, đặt `GIT_DIR=/nonexistent`, gọi `job_lint_gitleaks`, kỳ vọng `FAILED=1` và dòng `gitleaks … hỏng`. Với trivy: `docker` giả trên PATH ghi lại argv, kiểm có `-v <dir>:/out` và `--output /out/trivy-<img>.sarif` |
| N3 | Nit | LOG-04 (R-17) | pip-audit thoát 1 nhưng báo cáo là JSON hợp lệ không có `dependencies` (vd `{}`) thì **đạt**, vì `audit.py:67` đọc `report.get("dependencies", [])`. pip-audit 2.10.1 ghim bản không sinh ra dạng này (lỗi fatal thì không in JSON, ca đó đã bị chặn "JSON rỗng"), nên chỉ là phòng thủ chiều sâu | `tools/ci/audit.py:67`; `tools/ci/job.sh:153-161` | `audit.py` đòi `dependencies` là list, thiếu thì thoát 1 |
| N4 | Nit | LOG-02 / MNT-04 | Nới `BASE_SHA` rỗng → zero-SHA áp cho mọi sự kiện khác `pull_request`, tức cả `push`, trong khi chỉ `workflow_dispatch` cần. `github.event.before` luôn có với `push`, nên với `push` đây là nới fail-closed không cần thiết. Docstring module vẫn ghi `EVENT (pull_request\|push)` | `tools/ci/commits.py:64`, `:3-4` | `if event == "workflow_dispatch" and not base_sha:`; sửa docstring |
| N5 | Nit | SEC-09 | `codeql.yml` giữ mặc định `persist-credentials: true`, và token của job có `security-events: write`. `build-mode: none` không chạy mã của PR nên rủi ro rất thấp | `.github/workflows/codeql.yml:36` | `with: persist-credentials: false` cho đồng bộ với `ci.yml` |
| N6 | Nit | MNT-04 | Chú thích ghi `"<prefix>(deps): Bump …"`, còn test và README (sau #4) dùng `bump` chữ thường, đúng định dạng thật khi có `prefix` | `.github/dependabot.yml:5` | Sửa `Bump` → `bump` |

Không có P0, P1 hay P2 mới.

## Kiểm sổ nợ

- 6 mục nợ tác giả nêu ở lượt 1 đều có dòng: NO-102…NO-107. #6 là NO-109 `➖`, lý do đứng được.
- NO-102 là **P1 `mở`** (chủ B0-08, ngoài `so_huu` của B0-09). Nó đã có người xử lý: FIX-070 ở nhánh `fix/b0-08-web-openssl-cve`, review riêng. Theo R-35/R-38, nó chặn **thứ tự gộp**, không chặn phán quyết của nhánh này. Lý do: chưa sửa thì job `build` đỏ ngay lượt CI thật đầu tiên.
- N1 và N2 (P3) chưa có dòng `DEBT.md`. Người điều phối ghi hai dòng NO (R-34), hoặc giao FIX cho B0-09, trước hay cùng lúc gộp. Nit không bắt buộc.

## Điểm

Nit không trừ điểm (giữ cách chấm của lượt 1). MNT giữ 3 vì P2 MNT-05 (NO-109) được chấp nhận chứ không mất.

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (chỉ Nit #16, N5). Không nội suy; quyền tối thiểu; `persist-credentials: false` đủ 12/12; SHA/digest khớp; OSV vẫn bắt lỗ hổng có bản sửa, kể cả bản `+cpu` | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 4 (P3 N1; Nit N3, N4). P1 #1 và P2 #2, #3, #4 đã sửa thật | 0,60 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 (#7, #14 đã sửa; lỗi mạng tạm của pip-audit fail-closed đúng) | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 (P3 N2). Test #1 đi qua đúng `job.sh`; có test `workflow_dispatch`; mẫu Dependabot đúng định dạng thật | 0,28 |
| OBS, OPS – Vận hành | 5 % | 4 (P3 N1 ở phần hướng dẫn vận hành; SARIF đã sống) | 0,20 |
| MNT – Bảo trì | 3 % | 3 (P2 #6 chấp nhận, NO-109; Nit N4, N6) | 0,09 |

Tổng: 1,25 + 0,75 + 0,60 + 0,50 + 0,50 + 0,50 + 0,28 + 0,20 + 0,09 = **4,67 / 5**

## PHÁN QUYẾT: APPROVE

P1 duy nhất của lượt 1 (#1) đã được sửa ở gốc. Mã thoát 1 của pip-audit giờ chuyển cho `tools.ci.audit`, và bằng chứng có ba lớp: 3 test đi qua đúng `job.sh` với `uvx` giả; 6 ca tôi tự chạy, trong đó "rc=1, JSON rỗng" hỏng đúng; một lượt pip-audit thật trên `uv.lock` của nhánh đạt qua đủ ba bước. Đổi sang OSV (#9) đã được đo: vẫn trả `fix_versions`, và khớp bản local `+cpu` giống hệt bản thường. Cả 14 finding sửa được trong `so_huu` (#1–#4, #7–#15, #18) đều đã sửa thật; báo cáo tác giả ghi "15/18" là đếm dư một. #5, #6 người điều phối đã ghi sổ; #16 giữ có lý do; #17 mất khi squash. Cổng xanh (mã thoát 0, 8/8, 2 467 passed, 99,06 % / 97,32 %), actionlint 0 lỗi, không có P0/P1/P2 mới, điểm 4,67 ≥ 4,0.

**Điều kiện gộp (thứ tự, không phải điều kiện duyệt):**
1. **FIX-070 (NO-102, CVE `web`, P1, chủ B0-08) phải vào `main` trước** (R-38). Chưa có nó thì job `build` của B0-09 đỏ ngay lượt CI thật đầu tiên.
2. Gộp bằng **squash** (một prompt, R-36). Thân commit có khối trailer `Prompt: B0-09` (R-36b, #17).
3. Người điều phối ghi `DEBT.md` cho N1, N2 (P3), hoặc giao FIX cho B0-09. Nit N3–N6 tuỳ chọn.
4. Sau khi gộp: xuất `openapi.json` ra gốc repo rồi chạy verify tích hợp trên `main` như mọi lần gộp.
