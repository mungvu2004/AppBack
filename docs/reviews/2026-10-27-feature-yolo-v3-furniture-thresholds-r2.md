# Review merge feature/yolo-v3-furniture-thresholds → main (lượt 2)

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review (lượt 2, độc lập) · Commit đầu nhánh: 09eadc2c6a10 (merge `origin/main` 4262b9f17f94 vào nhánh; base cũ b8feb82c)
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 6: base đổi từ b8feb82c sang 4262b9f1 kể từ lượt đầy đủ trước). `VERIFY_PYTEST_WORKERS=4 bash tools/verify/run.sh verify` tại 09eadc2c, chạy một mình trên máy (18:21:36 → 18:33:19): **mã thoát 0**, mọi bước 0–8 kể cả 5b đạt. Log client `F:/worktrees/AppBack/_logs/verify-yolo-v3-r2g.log` (`exit=0`), log trong container `F:/worktrees/AppBack/_logs/verify-yolo-v3-r2g-inner.log` (`mã thoát: 0`). Người điều phối chạy, reviewer đã đọc cả hai log. `-n 4` là núm có sẵn `VERIFY_PYTEST_WORKERS` (`steps.py` `pytest_workers`), không hạ ngưỡng nào.
- Độ phủ (`coverage_gate`, lượt đầy đủ trên): tổng dòng **99,48%** · nhánh **98,00%**; `apps/ml/objects` dòng 100,00% · nhánh 98,44%; tập file bị chạm dòng 100,00% · nhánh 97,83%.

## Bảng cổng (mã thoát thật, lượt r2g)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | ruff format --check | đạt | |
| 2 | ruff check | đạt | |
| 3 | mypy --strict | đạt | lượt đầu bước này chạy được trên nhánh; finding 1 lượt 1 đã đóng |
| 4 | lint-imports | đạt | |
| 5 | pytest -n 4 (cov) → coverage_gate | đạt | 8945 passed trong 607 s |
| 5b | pytest -m perf → case_gate | đạt | perf: 2 test |
| 6 | lint_migrations → migrate_check | đạt | 30 revision |
| 7 | H1 H3 H4 H5 | đạt | AppFront @ aa84d2e5 |
| 8 | openapi | đạt | |

**Các lượt trước không dùng làm bằng chứng.** Lượt r2d (`F:/worktrees/AppBack/_logs/verify-yolo-v3-r2d-inner.log`): 4 cổng đầy đủ chạy cùng lúc trong VM 12 GB, worker xdist gw0/gw3/gw4/gw5 chết ("node down: Not properly terminated"), pytest INTERNALERROR, 13 failed / 8760 passed, mã thoát 1. Các test đỏ (junit) đều ở module nhánh không chạm: `spatial_read`, `admin_ml_datasets`, `deploy/backup` (timeout 60 s), `api/core` middleware (kết nối asyncpg bị đóng), `streams`. Lượt r2f (chạy một mình, `-n 6`): 2 test chập chờn ở module không chạm (`streams …__S05`, `spatial_write …large_floor`), chạy lại riêng mỗi test 3/3 đạt (`F:/worktrees/AppBack/_logs/rerun-r2f.log`). Lượt r2g ở trên xanh trọn vẹn nên không cần viện dẫn chạy lại.

## Soát các mục phải sửa của lượt 1

| # lượt 1 | Mức | Trạng thái | Bằng chứng reviewer tự kiểm |
|---|---|---|---|
| 1 | P1 | **đóng** | `apps/ml/objects/tests/test_detector_postprocess.py:76-77`: `other: DetectionLabel = "other"` rồi `other_labels = (other,) * len(COCO_LABELS)`; `DetectionLabel` nhập ở dòng 21. Bước 3 mypy --strict đạt ở r2g. Ý định test giữ nguyên ("other" không có ngưỡng riêng → `CONFIDENCE_MIN`). |
| 2 | P3 | **đóng** | `git log -1 --format='%(trailers:key=Prompt)' 8751be20` → `Prompt: YOLO-V3` (c03f4f0f và 09eadc2c cũng vậy); khối trailer liền nhau, đúng R-36b. |
| 3 | Nit | **đóng** | `F:/App/docs/yolo-do-roi/cham-v3-final.md` mục "Kiểm lại ngưỡng trên tập test". Reviewer chạy lại `F:/runs/yolo-v3/thresh_sweep.py --name v3 --split test`: bàn 0,6 → P .854 R .833; ghế 0,5 → P .902 R .859; giường 0,8 → P .895 R .817, khớp từng số với bảng. |

## Phạm vi và điều kiện dừng sớm

- Cây sạch. `origin/main..HEAD`: 8751be20 (feat), c03f4f0f (review lượt 1), 09eadc2c (merge `origin/main`). Diff so với `origin/main`: 4 file, +84/−4; mã chỉ là `apps/ml/objects/detector.py` (+4/−3) và một test (+2/−1), cộng `changes/YOLO-V3.md` và file review lượt 1.
- Không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`. Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng.
- Merge `origin/main` vào nhánh: khi gộp vào `main` nên squash (một prompt, R-36) để lịch sử `main` không mang merge ngược; trailer `Prompt: YOLO-V3` có trên mọi commit nên cách gộp nào cũng tra được chủ.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | Nit | LOG / MNT | Docstring ghi "precision ≈ 0,9 mà recall còn 0,83 đến 0,89" theo validation. Trên tập test ở cùng ngưỡng thấp hơn chút: P 0,85–0,90, R 0,82–0,86 (bàn P .854, giường R .817). Không sai, chỉ chưa nói đây là số validation. | `apps/ml/objects/detector.py:50-51` | Lần sửa sau ghi "(validation; test: P 0,85–0,90, R 0,82–0,86)". Không chặn merge. |

Đã soát, không có finding: SEC (không có biên vào hay I/O mới), CON (hằng bất biến `MappingProxyType`), PERF (tra một dict mỗi nhãn), RES, DB/API (không đổi dây, schema, hợp đồng FE; bước 7, 8 đạt), TEST (mypy, test và độ phủ đạt), OBS/OPS (trailer đúng), MNT. Ngoài phạm vi như lượt 1: ngưỡng `stair` của v3 chưa quét.

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

Tổng: **5,00 / 5** · P0: 0 · P1: 0 · P2: 0 · P3: 0 · Nit: 1

## PHÁN QUYẾT: APPROVE

Ba mục phải sửa của lượt 1 đã đóng và reviewer đã tự kiểm từng mục. Cổng đầy đủ trên 09eadc2c thoát 0 ở mọi bước, độ phủ tổng và file bị chạm đều trên 90/90. Ngưỡng bàn 0,6, ghế 0,5, giường 0,8 khớp bằng chứng validation lẫn test. Còn một Nit về câu chữ docstring, không chặn merge. Việc gộp thuộc phiên gọi review; nên squash (R-36, một prompt).
