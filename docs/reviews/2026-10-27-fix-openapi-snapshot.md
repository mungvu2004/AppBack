# Review merge fix/openapi-snapshot → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: 2f4242dbe1f1 (base `origin/main` 913e3fad, là tổ tiên)
- Cổng: phạm vi **đầy đủ** (R-33b (1): lượt đầu của nhánh; (2): diff chạm `docs/contracts/**`, thuộc sàn cứng). `VERIFY_BRANCH=integration VERIFY_PYTEST_WORKERS=4 bash tools/verify/run.sh verify` tại 2f4242dbe1f1 mã thoát **0**, bước 0–8 đều `đạt`, 8.980 passed, perf 40 passed (log: `F:/worktrees/AppBack/_logs/verify-openapi-snap3.log`, log cổng `.cache/src-out/verify/20261027T131104Z-2f4242dbe1f1.log`). Người điều phối chạy lượt này, reviewer chỉ đọc log, không chạy lại. Hai lượt trước (`verify-openapi-snap.log`: Docker `unexpected EOF` ở 87% pytest, `exit=125`; `verify-openapi-snap2.log`: Docker Desktop sập) hỏng vì hạ tầng, không tính làm bằng chứng.
- Độ phủ: tổng dòng 99,48% · nhánh 97,98% (lượt đầy đủ trên, `coverage_gate` đạt). Diff không chạm tệp `.py`.

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
| 7 | H1 H3 H4 H5 (tools.contract.check) | đạt |
| 8 | openapi (`--compare docs/contracts/openapi.json`) | đạt |

## Điều kiện dừng sớm

Không có điều kiện nào.

- Cây sạch. Có đúng một commit: `docs(contracts): refresh openapi snapshot after spatial ETag docstrings`, đúng mẫu và ≤ 72 ký tự. Khối trailer liền nhau: `Prompt: PERF-03` rồi `Co-Authored-By:`.
- Có `changes/PERF-03.md` và `changes/PERF-03-spatial-etag.md`.
- `docs/contracts/openapi.json` là tệp cấm, nhưng được **chấp nhận** vì người điều phối commit. Tiền lệ: `2026-10-27-fix-apt-rooms.md:12`, `2026-10-21-feature-fe3d-b-pascal-fields.md:14`. Bước 8 so bản tham chiếu đạt.
- Không có `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng.

## Đã soát, không có finding

- **Snapshot đúng bằng bản xuất.** `cmp .cache/src-out/openapi/openapi.json docs/contracts/openapi.json` cho thấy hai tệp trùng từng byte. Bước 8 của lượt cổng trên cũng đạt.
- **Chỉ đổi mô tả.** Reviewer so ngữ nghĩa JSON (duyệt đệ quy toàn cây) giữa `origin/main:docs/contracts/openapi.json` và HEAD. Có đúng 3 khác biệt, đều là `description`:
  - `GET /api/projects/{project_id}/spatial` (N15)
  - `GET /api/projects/{project_id}/floors/{floor_id}/spatial/layer` (N16)
  - `GET /api/projects/{project_id}/versions/{version_id}/snapshot` (N18)
  
  Không đổi path, `operationId`, tham số, response hay schema, nên AppFront không cần sửa. Bước 7 hợp đồng FE–BE đạt.
- **Chữ mới khớp nguồn.** Ba mô tả mới khớp docstring do ba11b8fc (PERF-03) thêm vào: `apps/api/spatial_read/router.py:83` (N15), `:96` (N16) và `apps/api/versions/router.py:64` (N18).
- **Sửa đúng gốc (R-19).** Cổng tích hợp trên main 913e3fad chỉ hỏng bước 8: `openapi: docs/contracts/openapi.json lệch với bản vừa xuất` (`F:/worktrees/AppBack/_logs/verify-main-913e3fad.log`). Snapshot cũ chưa được dựng lại sau ba11b8fc, và commit này dựng lại nó.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| — | — | — | Không có finding | — | — |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: **5,00 / 5** · P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 0

## PHÁN QUYẾT: APPROVE

Nhánh chỉ dựng lại `docs/contracts/openapi.json` theo docstring mà PERF-03 (ba11b8fc) đã sửa. Bản commit trùng từng byte với bản xuất từ mã, và chỉ khác main ở 3 chuỗi `description`, không đổi hợp đồng. Lượt cổng đầy đủ ở chế độ integration tại 2f4242dbe1f1 thoát 0, bước 0–8 đều đạt, kể cả bước 8 vốn đang làm main đỏ. Được merge vào `main`. Việc merge thuộc phiên gọi review.
