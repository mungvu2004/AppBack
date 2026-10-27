# Review merge feature/yolo-v3-furniture-thresholds → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: a582ca08de68 (base `main` = `origin/main` b8feb82cbe58)
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1: lượt đầu của nhánh). Reviewer tự chạy `bash tools/verify/run.sh verify` tại a582ca08: **mã thoát 1** (bước 5 hỏng; bước 3, 5b, 6, 7, 8 `chưa chạy`). Client docker rớt giữa chừng (`error waiting for container: unexpected EOF`, client thoát 125, log `F:/worktrees/AppBack/_logs/verify-yolo-v3-r1.log`); container cổng vẫn chạy tới hết, `docker wait` trả **1**, bảng bước và mã thoát lấy từ log trong container (chép ra `F:/worktrees/AppBack/_logs/verify-yolo-v3-r1-inner.log`). Stack f14 chạy song song suốt lượt (không dừng, theo yêu cầu điều phối).
- Độ phủ: tổng **không đo** (bước 5 hỏng) — file đổi `apps/ml/objects/detector.py` 100% dòng (278/278) · 97,8% nhánh (45/46), đo bằng `run.sh shell` (`pytest apps/ml/objects --cov=apps/ml/objects --cov-branch`, log `F:/worktrees/AppBack/_logs/rerun2-yolo-v3.log`).

## Bảng cổng (mã thoát thật)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | ruff format --check | đạt | |
| 2 | ruff check | đạt | |
| 3 | mypy --strict | chưa chạy | trong lượt đầy đủ. Reviewer chạy riêng `python -m mypy <2 file đổi>` (cấu hình `pyproject.toml`: strict + pydantic) → **mã thoát 1**, xem finding 1 |
| 4 | lint-imports | đạt | |
| 5 | pytest -n (cov) | **hỏng** | 8923 passed, 2 failed, 1 error (21 phút 32 giây), xem "Bước 5 hỏng" |
| 5b | pytest -m perf → case_gate | chưa chạy | |
| 6 | lint_migrations → migrate_check | chưa chạy | |
| 7 | H1 H3 H4 H5 | chưa chạy | |
| 8 | openapi | chưa chạy | |

**Bước 5 hỏng, không do diff.** Ba test đỏ nằm ở module nhánh không chạm, đều là hết thời gian chờ hay chạy đua khi máy tải nặng:
`apps/worker/datasets/tests/test_tasks.py::test_build_dataset_version__cleans_up_when_finish_loses` (`('building', None) == ('failed', None)`),
`apps/ml/training_runner/tests/test_runner.py::test_main_ignores_override_outside_test_env` (`subprocess.TimeoutExpired` sau 110 s),
`apps/api/auth_recovery/tests/test_e2e.py::test_password_reset_e2e` (lỗi teardown `TimeoutError: timed out` ở socket).
Chạy lại riêng ba test đó trên cùng commit (`run.sh shell`, log `F:/worktrees/AppBack/_logs/rerun-yolo-v3.log`): **3 passed**, mã thoát 0. Diff chỉ đổi hằng số trong `apps/ml/objects/detector.py` và một test của nó. Tuy vậy cổng vẫn phải xanh trước khi merge, nên lượt sau phải chạy đầy đủ lại (diff vòng sửa đụng R-33b (6) nếu base đổi; kể cả không đổi, bước 3 chưa từng chạy trên nhánh).

## Phạm vi và điều kiện dừng sớm

- Cây sạch. Một commit `a582ca08 feat(ml): display thresholds for table, chair and bed (yolo v3)` (61 ký tự, đúng hook `.githooks/commit-msg`). Có `changes/YOLO-V3.md` (6 dòng). 3 file, +11/−4.
- Không chạm `docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`. Không `pragma`, `type: ignore`, `noqa`, `skip`/`xfail` mới, không hạ ngưỡng.
- `RULE.md`, `RULE-CODE.md`, `DEBT.md` đã rời repo ở 6b2e4d52 (2026-10-18); reviewer đọc bản tại `6b2e4d52^` (§3, §5, R-33b, R-36b).

## Reviewer tự kiểm

1. **Số trong mã khớp bằng chứng.** `F:/App/docs/yolo-do-roi/cham-v3-final.md` mục "Ngưỡng gợi ý": bàn 0,6 (P .90 R .83), ghế 0,5 (P .92 R .89), giường 0,8 (P .91 R .86). Mã: `"bed": 0.8, "chair": 0.5, "table": 0.6`. Docstring "precision ≈ 0,9, recall 0,83 đến 0,89" và "~70% ở `CONFIDENCE_MIN`" khớp bảng validation (P@app bàn .71, giường .70). Commit "test AP50 table .88, chair .89, bed .89" khớp bảng test (0.882/0.891/0.892).
2. **Không ảnh hưởng model khác.** `label_thresholds` bỏ `LABEL_CONFIDENCE_MIN` khi `labels is COCO_LABELS`, nên `yolov8n/s` vẫn dùng `COCO_CONFIDENCE_MIN` 0,5. Model miền v2 có AP50 = 0 cho bàn/ghế/giường, nên nâng ngưỡng chỉ cắt nhiễu. Đánh giá mAP truyền số (0,05) thì bảng bị bỏ qua. Không có bộ lọc độ tin cậy đồ đạc nào khác ở hạ nguồn (`git grep` trên `apps`, `packages`).
3. **Test sửa giữ đúng ý định.** Test cũ dùng nhãn COCO đã ánh xạ (chair/bed/table), nay có ngưỡng riêng ≥ 0,5 nên điểm 0,4 bị cắt. Thay bằng toàn `"other"` (rơi về `CONFIDENCE_MIN`) vẫn kiểm đúng "COCO chặt hơn mặc định". Chỉ sai kiểu, xem finding 1.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P1 | R-12 / R-33 (TEST) | Dòng test mới không qua `mypy --strict`: `other_labels: tuple[DetectionLabel, ...] = ("other",) * len(COCO_LABELS)`. mypy suy `("other",)` là `tuple[str]`, nhân ra `tuple[str, ...]` → `error: Incompatible types in assignment [assignment]`. Bước 3 sẽ hỏng ngay khi bước 5 xanh; `changes/YOLO-V3.md` ghi "Cổng áp dụng: lint/type" nhưng kiểu chưa được kiểm. Bản `origin/main` của dòng này (`tuple(label if … else "other" …)`) qua mypy ở lượt đầy đủ 3c3701b8; `apps/ml/objects` không đổi từ đó tới `origin/main`, nên lỗi do nhánh đưa vào. | `apps/ml/objects/tests/test_detector_postprocess.py:76` | `other: DetectionLabel = "other"` rồi `other_labels = (other,) * len(COCO_LABELS)` (hay `cast`). Chạy lại `run.sh verify` đầy đủ, mã thoát 0. |
| 2 | P3 | R-36b (OPS) | `Prompt: YOLO-V3` và `Co-Authored-By:` cách nhau một dòng trống, nên `git log -1 --format='%(trailers:key=Prompt,valueonly)' a582ca08` trả **rỗng**. Các lần gộp gần đây là merge `--no-ff` (b8feb82c), nên commit này sẽ vào `main` mà không tra được chủ. | thân commit a582ca08 | Lúc sửa finding 1: `git commit --amend` (hay commit sửa mới) với khối trailer liền nhau `Prompt: YOLO-V3` / `Co-Authored-By: …`. Hoặc gộp squash (nhánh một prompt, R-36) với khối trailer đúng. |
| 3 | Nit | LOG | Ngưỡng chọn trên validation (đúng cách). `cham-v3-final.md` chỉ ghi P/R ở ngưỡng mới cho validation, không có P/R của tập test ở 0,6/0,5/0,8 để xác nhận độc lập. | `F:/App/docs/yolo-do-roi/cham-v3-final.md` mục "Ngưỡng gợi ý" | Thêm một dòng P/R/F1 của tập test (400 trang) ở ngưỡng mới. Không chặn merge. |

Ngoài phạm vi, không phải finding: `stair` của v3 vẫn ở 0,25 (P .55 R .84 trên validation, "Cầu thang chưa quét"). Nên quét ngưỡng ở đợt sau.

Đã soát, không có finding: SEC (không có biên vào hay I/O mới), CON (hằng bất biến `MappingProxyType`), PERF (vẫn tra một dict cho mỗi nhãn), RES, DB/API (không đổi dây, schema, hợp đồng FE; `objects.json` chỉ ít hộp hơn), MNT (docstring ghi nguồn số và ngày).

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 1 | 0,07 |
| OBS, OPS | 5% | 4 | 0,20 |
| MNT | 3% | 5 | 0,15 |

Tổng: **4,67 / 5** · P0: 0 · P1: 1 · P2: 0 · P3: 1 · Nit: 1

## PHÁN QUYẾT: REQUEST CHANGES

Ngưỡng hợp lý và khớp bằng chứng, nhưng cổng đầy đủ thoát 1, và nhánh đưa vào một lỗi `mypy --strict` (P1). Lỗi này sẽ làm bước 3 hỏng kể cả khi ba test chập chờn ở bước 5 qua. Để được duyệt:
1. Sửa kiểu ở `apps/ml/objects/tests/test_detector_postprocess.py:76` theo finding 1.
2. Sửa khối trailer cho `Prompt: YOLO-V3` đọc được (finding 2), hay cam kết gộp squash với trailer đúng.
3. Chạy `bash tools/verify/run.sh verify` **đầy đủ**, mã thoát 0 ở mọi bước. Bước 5 đỏ vì test chập chờn thì phải có bằng chứng chạy lại (và chúng đỏ cả ở `origin/main` nếu có), không bỏ qua.
Sau đó xin review lượt 2.
