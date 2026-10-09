# Review merge chore/dependabot-15 → main

- Ngày: 2026-10-09 · Reviewer: phiên /merge-review (worktree `F:/App/.wt-deps2-be`, không sửa mã, không merge) · Commit đầu nhánh: `77bda7d47455`
- Base: `origin/main` `6574422d3f7c` · 4 commit (`3b8dc18e` dependabot #15, `2e97eb0b` merge, `d0f66e93` changes, `77bda7d4` FIX-723) · 4 file, +360/−343 (`uv.lock`, `changes/DEPS-2026-10-09b.md`, `docs/fixes.md`, `tools/ci/h2.py`)
- Cổng: phạm vi **đầy đủ** — lượt review 1 của nhánh (R-33b đk 1); `bash tools/verify/run.sh verify` mã thoát **0**, 8/8 `đạt` + 5b `đạt`
  (log: `F:/App/AppBack/backend/dieu-phoi/chay/QA-01c/verify-deps15-be-2.log`, dòng 1 trỏ `.cache/src-out/verify/20261009T110337Z-77bda7d47455.log` — đúng head; bắt đầu 11:03:37Z, sau commit 11:03:35Z; cuối log `mã thoát: 0` / `exit=0`). Pytest 8411 passed, 0 hỏng.
- Độ phủ: tổng dòng 99,48% · nhánh 98,02% — tập file bị chạm dòng 99,53% · nhánh 96,15%; `tools` 98,90% / 96,46%.

## Đã tự kiểm (không tin báo cáo tác giả)

- `git status --porcelain` rỗng; `HEAD` = `77bda7d4`, base = `6574422d`. Cả 4 dòng đầu commit qua `.githooks/commit-msg` (`3b8dc18e` đúng 72 ký tự).
- Lượt verify đầu (`verify-deps15-be.log`, @`d0f66e93`) hỏng bước 3 `tools/ci/h2.py:75 redundant-cast` — đúng triệu chứng FIX-723 ghi.
- **`uv.lock`**: không đổi `pyproject.toml`. Trong `run.sh shell` (uv 0.9.30): (a) `uv lock --check` trên lock nhánh: đạt (159 gói); (b) lock của `origin/main` cũng qua `--check`;
  (c) khôi phục lock `origin/main` rồi `uv lock -P filelock==4.0.12 -P onnx==1.23.2 -P pypdfium2==5.14.0 -P schemathesis==4.29.3` → **không byte-đúng** với lock nhánh: 652 dòng khác, **toàn bộ** là
  vế `platform_machine == 'x86_64' and sys_platform == 'linux'` trong `marker` mà lock của Dependabot bỏ đi (vế này chính là `[tool.uv] environments` của `pyproject.toml:10`, nên dư thừa về ngữ nghĩa).
  Sau khi chuẩn hoá vế đó: tập gói, bản, URL, hash giống hệt; chỉ 4 dòng gộp vế (`pycparser`, `cffi`, `librt`, `uvloop`) cùng loại. Bản nâng đúng 4 gói khai trong PR, torch/torchvision/ultralytics không đổi.
  Kết luận: lock do uv của Dependabot sinh, không có byte viết tay, uv của container chấp nhận (`--check` đạt) → **không** kích hoạt REJECT "sửa tay" (cùng lập luận tiền lệ `docs/reviews/2026-10-09-chore-dependabot-2026-10-09.md`). Chênh định dạng ghi ở finding 1.
- `tools/ci/h2.py`: bỏ `cast` chỉ cho `response_schema_conformance`; `cast` vẫn dùng cho `not_a_server_error` (import còn dùng). mypy --strict đạt ở cổng, hành vi `_CHECKS` không đổi (cùng hai hàm, cùng thứ tự). Sửa gốc đúng chỗ (R-19), không vá triệu chứng.
- ONNX: `YOLO_EXPORT_TOOLCHAIN` (`apps/ml/runtime/export_pinned.py:36-42`) chỉ ghim torch/ultralytics — cả hai không đổi, `test_export_all__yolo_toolchain_matches_lock` xanh trong cổng. onnx không được test gác (docstring: `normalize_onnx` trung hoà, đo 1.22.0 → 1.23.0); nếu 1.23.2 làm lệch SHA thì `export_pinned` ném `FetchError` lúc build ảnh `ml` — lỗi ồn, không âm thầm.
- Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới; không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `pyproject.toml`, `tools/verify/*`.
- `changes/DEPS-2026-10-09b.md` có. `DEBT.md`: không nợ P0/P1 `mở` mới; nhánh không nêu nợ mới.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | OPS | Lock của Dependabot khác định dạng với lock do uv của container sinh: bỏ vế `environments` trong 326 `marker`. Tương đương ngữ nghĩa, `uv lock --check` đạt, nhưng lần `run.sh lock`/`uv lock` kế tiếp trong container sẽ thêm lại ~650 dòng nhiễu (và PR Dependabot sau lại bỏ đi) — diff lock khó đọc, che thay đổi thật. | `uv.lock` (vd. dòng 35-37 `alembic`) | Không chặn. Hoặc (a) trước khi squash, sinh lại lock trong `run.sh shell` từ lock `main` bằng lệnh `uv lock -P …==…` ở trên rồi dùng bản đó (byte-đúng toolchain, cổng không cần chạy lại vì chỉ khác vế dư), hoặc (b) chấp nhận và ghi một câu vào `changes/` để người sau biết diff marker là nhiễu định dạng. |
| 2 | P3 | OPS (BE-00 §13.2) | Commit `3b8dc18e` (Dependabot) không có trailer `Prompt:`; `2e97eb0b` là merge commit. Các commit khác đủ trailer. | commit `3b8dc18e`, `2e97eb0b` | Gộp vào `main` **bằng squash** với dòng đầu ≤ 72 ký tự + `Prompt: DEPS-2026-10-09b` (+ `Fix: FIX-723`). Không fast-forward/merge-commit giữ nguyên hai commit này. |
| 3 | P3 | MNT | `changes/` ghi "Không đổi mã nguồn" nhưng nhánh có FIX-723 sửa `tools/ci/h2.py`. | `changes/DEPS-2026-10-09b.md:5` | Sửa câu thành "đổi `tools/ci/h2.py` (FIX-723, bỏ `cast` thừa)" — làm được trong commit squash. |
| 4 | Nit | OPS | FIX-723 mục [7] chỉ ghi "cổng đầy đủ … trên nhánh", thiếu mã thoát và đường log. | `docs/fixes.md` (cuối tệp, FIX-723 [7]) | Thêm "mã thoát 0, log `.cache/src-out/verify/20261009T110337Z-77bda7d47455.log`". |
| 5 | Nit | OPS | onnx 1.23.2 chưa được đo lại SHA ONNX YOLO (gác chỉ chạy lúc build ảnh `ml`). | `apps/ml/runtime/export_pinned.py:41` | Lần build ảnh `ml` kế tiếp xác nhận `export_pinned` không ném `FetchError`; không cần chặn merge. |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 5 | 0,35 |
| OBS, OPS – Vận hành | 5% | 4 | 0,20 |
| MNT – Bảo trì | 3% | 4 | 0,12 |

Tổng: 4,92 / 5

## PHÁN QUYẾT: APPROVE

Không P0/P1, điểm 4,92 ≥ 4,0. Lock do uv của Dependabot sinh, `uv lock --check` đạt trong container, tái lập từ lock `main` cho cùng tập gói/bản/hash (chỉ khác vế marker dư thừa) — không phải sửa tay; cổng đầy đủ mã thoát 0 trên đúng head `77bda7d4`; FIX-723 sửa gốc, đúng một dòng, không đổi hành vi. Điều kiện khi merge (phiên gọi làm): (1) **squash** với dòng đầu ≤ 72 ký tự + trailer `Prompt: DEPS-2026-10-09b` và `Fix: FIX-723` (finding 2); (2) nên sửa câu "Không đổi mã nguồn" trong `changes/` (finding 3) và chọn (a) hoặc (b) cho finding 1 — không chặn.
