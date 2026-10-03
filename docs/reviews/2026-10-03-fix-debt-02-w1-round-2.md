# Review merge fix/debt-02-w1 → main — lượt 2 (DEBT-02 đợt 1)

- Ngày: 2026-10-03 · Reviewer: cùng phiên /merge-review của lượt 1 (R-37) · Commit đầu nhánh: `0395bea9be3c`
- Lượt 1: `docs/reviews/2026-10-03-fix-debt-02-w1.md`, REQUEST CHANGES 3,85.
- Phạm vi: diff vòng sửa `3cb77b1eb753..0395bea9be3c`. Merge hiến chương `7768151` (CASE.md §2.3 bản 7), `dfdd92c`, `cd63213`, `9150899` (finding #1–#9), `9738dab` + `c69ef27` (FIX-136, B0-10), `8e5cc8f` + `a84f143` (FIX-137, B6-04b), sổ `49289a0`, `292746d`, `0395bea`.
- Cổng: phạm vi **đầy đủ** do việc gộp chạy. Diff chạm `.github/workflows`, `CASE.md` và FIX-137 sinh ra từ cổng 2 đỏ — R-33b điều kiện (2)–(7). Kết quả: `bash tools/verify/run.sh verify` (`VERIFY_PYTEST_WORKERS=4`, người dùng duyệt vì RAM), **mã thoát 0**. Log: `backend/dieu-phoi/chay/DEBT-02/W1/M/gate-3-container.log` và `debt02-c04/.cache/src-out/verify/20261003T180823Z-0395bea9be3c.log`, sha khớp. Kết quả: 7929 passed; 5b perf 6 passed; `case_gate: đạt`. junit cạnh log có 7929 / 6 `<testcase>`.
- Cổng 2 (`9150899`) đỏ ở bước 5 vì một lỗi có sẵn trên `main` (exporter giả rò sang `test_export.py`, phụ thuộc thứ tự). Lỗi này đã thành FIX-137 trong đợt, không ghi nợ (luật 47).
- Độ phủ: tổng dòng 99,45% · nhánh 97,85%. Gói bị chạm thấp nhất: `apps/ml/training_runner` 98,62/94,00, `packages/db` 97,36/95,76. Mọi gói ≥ 90/90.

## E.10 (gate-3, mã thoát thật)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict | đạt |
| 4 | lint-imports | đạt |
| 5 | pytest -n (cov) → coverage_gate | đạt |
| 5b | pytest -m perf → case_gate | đạt |
| 6 | lint_migrations → migrate_check | đạt |
| 7 | H1 H3 H4 H5 | đạt |
| 8 | openapi | đạt |

## Tự kiểm bằng lệnh đích (một container)

Lệnh: `VERIFY_NAME=debt02-c02 bash tools/verify/run.sh shell < backend/dieu-phoi/chay/DEBT-02/W1/R/r2.sh`. Log: `W1/R/r2.log`, run.sh thoát 0. Không chạy `run.sh gc`.

| Kiểm | Kết quả |
|---|---|
| Xanh `0395bea`: test notify, github_config, workflows, run_sh, case_gate | 164 passed, rc 0 |
| #2 đột biến: thêm SHA `ffff…` vào `[allowlist] commits` | `test_gitleaks_toml__history_findings_allowlisted_by_commit` **đỏ**, rc 1 |
| #1 đỏ: `ci.yml` của `3cb77b1` (có `edited` + `if`), bỏ `commits.yml` | 6 failed, rc 1 |
| #1 đột biến: thêm lại `if: github.event.action != 'edited'` vào `lint` | `test_ci_yml__no_job_gated_on_event_action` **đỏ**, rc 1 |
| FIX-136 đỏ: `notify.yml` của `9150899` | 4 failed (`watches_every_workflow_running_on_push_to_main`, quyết định gửi của Commits/CodeQL), rc 1 |
| FIX-137 xanh: `test_trainer.py` + `test_export.py` một tiến trình | 31 passed, rc 0 |
| FIX-137 đỏ: `test_trainer.py` của `c69ef27` | `test_export_all_missing_source_exits_3` **đỏ**, rc 1 |

## Soát từng finding lượt 1

| # | Lượt 1 | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | P2 check `skipped` trùng tên | **đã sửa** | `commits` ở `.github/workflows/commits.yml` (push main + PR có `edited`, `contents: read`, SHA ghim, concurrency `commits-<ref>`). `ci.yml` bỏ `edited`, bỏ 8 `if:`, concurrency `ci-<ref>`. Luật workflow (ghim SHA, quyền, `pull_request_target`, nội suy, `persist-credentials`, `continue-on-error`, `job.sh`) giờ áp cho cả hai tệp. Tên check `commits` không đổi. |
| 2 | P1 allowlist nới `>=` | **đã sửa** | Một nguồn, so `==` 14 SHA + không trùng; đột biến đỏ (bảng trên). Test trùng ở `test_workflows.py` đã xoá. |
| 3 | P3 CASE.md §2.3 | **đã sửa** | Bản 7, câu chữ người dùng duyệt (dòng NO-338). Chú thích `_TEST_TASK_RE` và docstring `_task_found` trỏ về bản 7. |
| 4 | P3 docstring R-02 | **đã sửa** | Diff không còn docstring dạng `Kiểm: <tên>`. Docstring mới nêu bất biến và lý do. |
| 5 | P3 docstring test gc | **đã sửa** | `test_gc__git_chạy_ở_cwd_không_truyền_đường`, docstring khớp thân test. |
| 6–9 | Nit | **đã sửa** | `.gitleaks.toml:3,6` + `description` "14 commit"; `ci.yml:15` mất cùng #1; `job.sh:418`; `steps.py` chú thích xuống sau docstring. |

Phần mới của vòng sửa:
- **FIX-136 (B0-10)** sửa đúng hồi quy của #1: `Commits` tách khỏi `CI` khiến lỗi trên `main` không còn được báo. `notify.yml` giờ nghe `CI | Commits | CodeQL`. Test bất biến mới: mọi workflow chạy trên `push: main` đều nằm trong danh sách. Thêm `CodeQL` là do chính bất biến đó đòi (codeql chạy trên push main), nên chấp nhận.
- **FIX-137 (B6-04b)** sửa đúng gốc lỗi: hai đối tượng vá (`MonkeyPatch.context` của `fake_run` và fixture `monkeypatch`) hoàn tác lệch thứ tự. Giờ chỉ còn một ngăn, `fake_run` kiểm bản gốc lúc dựng. Grep lời gọi anh em (tệp có cả `MonkeyPatch.context()` lẫn fixture `monkeypatch`): `training_segformer/tests/test_trainer.py` và `library/tests/test_assets.py` không vá đè cùng thuộc tính bằng hai đối tượng — không còn chỗ hỏng.
- **K27:** mỗi commit một chủ (`tao_so_tra.py --chu`). Trailer `Prompt:`/`Fix:` khớp `docs/fixes.md`.
- **[11].3:** không có marker mới; không `sleep(`; không `noqa`/`type: ignore` mới.

## Finding

| # | Mức | ID | Mô tả + bằng chứng | Vị trí | Đề xuất sửa |
|---|---|---|---|---|---|
| R2-1 | P3 | DOC / OPS (NO-153) | Tài liệu bật required check lệch sau khi tách `commits`. `:27-29` ghi "chọn **mọi** job của `ci.yml` (`lint`, …, `commits`, `coverage`)", nhưng `commits` giờ nằm ở `commits.yml`. `:74-77` ghi "`ci.yml` khai `pull_request.types` gồm `edited`", trong khi `ci.yml` đã bỏ `edited` (#1). Người làm NO-153 đọc trang này sẽ tìm sai chỗ. | `tools/ci/README.md:27-29`, `:74-77` | `:27` → "mọi job của `ci.yml` (`lint`, `typecheck`, `unit`, `integration`, `ml`, `contract`, `build`, `coverage`), job `commits` của `commits.yml` và job `analyze` của `codeql.yml`". `:74` → "`commits.yml` khai `pull_request.types` gồm `edited` (NO-110); `ci.yml` thì không (NO-182: check `skipped` trùng tên)". |
| R2-2 | Nit | DOC | Chú thích đầu tệp chỉ nhắc `ci.yml` gọi script, nhưng `commits.yml` cũng gọi `job.sh commits`. | `tools/ci/job.sh:4` | "`.github/workflows/ci.yml` và `commits.yml` chỉ gọi script này". |
| R2-3 | Nit | MNT | Dòng chú thích dài 128 ký tự, ngắt câu giữa hai ý. | `.github/workflows/notify.yml:5` | Ngắt sau "danh sách dưới." rồi xuống dòng cho "Không checkout…". |
| R2-4 | Nit | TEST-07 | Tên test chỉ nhắc ba workflow, nhưng thân test so cả năm (`CI_YML, DEPLOY_YML, RESTORE_DRILL_YML, COMMITS_YML, CODEQL_YML`). | `deploy/scripts/tests/test_workflow_notify.py:62` | Đổi thành `test_notify_watches_exact_names_of_watched_workflows`. |

## Điểm (RULE.md §5)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 4 (P3 R2-1) | 0,20 |
| MNT | 3% | 4 (Nit) | 0,12 |

Tổng: **4,92 / 5**

## PHÁN QUYẾT: APPROVE

Mọi finding #1–#9 của lượt 1 đã sửa đúng gốc và có test chặn đỏ → xanh tự đo. Hai FIX phát sinh trong vòng sửa (FIX-136: hồi quy của #1 — notify mất cảnh báo `Commits`; FIX-137: lỗi có sẵn trên `main` mà cổng 2 phát hiện) cũng sửa đúng gốc. Cổng đầy đủ trên `0395bea9be3c` thoát 0. Không có P0/P1/P2.

Theo [6] D.3, R2-1…R2-4 vẫn phải sửa trên nhánh trước khi gộp, không ghi nợ. Cả bốn chỉ là tài liệu, chú thích và tên test (B0-09: README + job.sh; B0-10: notify.yml + tên test). Phán quyết này giữ nguyên với điều kiện diff sửa chỉ chạm đúng bốn vị trí trên. Khi đó (R-33b, lượt đích) đủ kiểm `verify --steps 1,2,3,4` cùng `deploy/scripts/tests/test_workflow_notify.py`, không cần thêm lượt review hay cổng đầy đủ. Diff vượt ra ngoài bốn vị trí đó thì phải qua lượt 3.
