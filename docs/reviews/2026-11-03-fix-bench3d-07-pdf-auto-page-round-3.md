# Review merge fix/bench3d-07-pdf-auto-page → main (lượt 3)

- Ngày: 2026-11-03 · Reviewer: phiên /merge-review (agent độc lập, lượt 3) · Commit đầu nhánh: 5543b7c8ecdf (PR #37; vòng sửa `baddc5b0..5543b7c8`, một commit)
- Cổng: phạm vi đích — lượt 3 chỉ soát vòng sửa (R-33b); vòng sửa chỉ thêm một comment và trả docstring về như `main`, không chạm migration, phụ thuộc hay tệp cấm. Bằng chứng: CI GitHub Actions run 41564972881 (workflow CI, head `5543b7c8ecdf33d700ab7e6dc17739fe4513cb63` = đầu nhánh) kết luận `success`, mọi job `success`; trong job `typecheck`, `verify --steps 3,8` đạt, bước 8 `openapi` **đạt** (so `docs/contracts/openapi.json`). CodeQL 41564973006 `success`, Commits 41564973063 `success`. Reviewer không chạy cổng hay pytest tại chỗ.
- Độ phủ (job `coverage` của run 41564972881, `coverage_gate` đạt): tổng dòng 99,31% · nhánh 97,48% — `apps/api/drawings` 99,74% / 98,21%; `packages/vision` 99,27% / 96,85%; `packages/db` 97,59% / 95,90%. Tất cả ≥ 90/90.
- PR `MERGEABLE`, `mergeStateStatus` `CLEAN`.

## Phạm vi vòng sửa

- Cây sạch. Commit `5543b7c8 fix(drawings): keep the InitUploadBody docstring in sync with openapi`, đúng Conventional Commits, có `Prompt: BENCH3D-07`. 1 tệp (`apps/api/drawings/schemas.py`), +2/−3.
- Không chạm `docs/charter/*`, `openapi.json`, `docs/contracts/openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`. Không pragma, `noqa`, `type: ignore`, skip/xfail mới.

## Finding lượt 2

| # lượt 2 | Mức | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 API / cổng bước 8: docstring `InitUploadBody` làm lệch OpenAPI | P1 | **Đã giải** | Docstring lớp trùng byte với `origin/main` (`git diff origin/main...HEAD -- apps/api/drawings/schemas.py` chỉ còn một dòng comment `#` thêm vào). Ghi chú BENCH3D-07 nằm ở comment trên `page_index` (`schemas.py:101`), comment không vào schema. Bước 8 `openapi` đạt trên CI run 41564972881. |

Các finding lượt 1 (P1 trần điểm ảnh, hai P3) đã giải ở lượt 2 và vòng sửa này không chạm lại mã đó.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | MNT | Commit 5543b7c8 thiếu dòng `Co-Authored-By` mà các commit trước của nhánh có. Hook `commit-msg` và job Commits chỉ đòi `Prompt:`, nên không phải lỗi luật. | commit 5543b7c8 | Không cần đổi. |

Không P0/P1/P2/P3. Nợ còn lại: Nit "mở tài liệu hai lần" đã ghi ở `changes/BENCH3D-07.md`.

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 4,5 | 0,675 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB/API | 10% | 5 | 0,50 |
| TEST | 7% | 5 | 0,35 |
| OBS/OPS | 5% | 4,5 | 0,225 |
| MNT | 3% | 4,5 | 0,135 |
Tổng: 4,89 / 5

## PHÁN QUYẾT: APPROVE

Vòng sửa trả docstring `InitUploadBody` về đúng như `main` và chuyển ghi chú BENCH3D-07 thành comment, nên OpenAPI không đổi và bước 8 xanh lại. Toàn nhánh: tự chọn trang chỉ khi client vắng `pageIndex` và không `crop` (cờ `uploads.page_auto`, migration chỉ mở rộng), dò trang ngoài vòng sự kiện, dừng sớm, ảnh dò mực qua trần U06 1 MP, có log và test cho từng ca. CI run 41564972881 `success` trên đúng head 5543b7c8ecdf, độ phủ ≥ 90/90, PR `MERGEABLE`/`CLEAN`. Được merge.
