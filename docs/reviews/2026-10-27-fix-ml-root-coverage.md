# Review merge fix/ml-root-coverage → main

- Ngày: 2026-10-27 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: d395134817e6 (base `origin/main` d51be309, đã `git fetch`, là tổ tiên)
- Cổng: phạm vi **đầy đủ** (R-33b (1): lượt đầu của nhánh; diff chạm `apps/ml/runtime/**`, thuộc sàn cứng). `VERIFY_PYTEST_WORKERS=4 bash tools/verify/run.sh verify` tại d395134817e6 mã thoát **0**, bước 0–8 đều `đạt`, 8.980 passed (log: `F:/worktrees/AppBack/_logs/verify-ml-coverage.log`, log cổng `.cache/src-out/verify/20261027T120128Z-d395134817e6.log`). Reviewer đã đọc log, không chạy lại lượt đầy đủ.
- Độ phủ: tổng dòng 99,49% · nhánh 98,02% (lượt đầy đủ trên). `coverage_gate` chế độ nhánh chỉ kiểm đơn vị bị chạm `apps/ml/runtime` (100% / 100%), **không** kiểm đơn vị gốc `apps/ml`, là đơn vị làm cổng tích hợp đỏ. Reviewer tự đo trong `run.sh shell`: `pytest --cov=apps.ml --cov-branch` trên `test_warmup.py` + `test_celery_main.py` + `test_loader_providers.py` → 24 passed (1 deselected là test `gpu` có sẵn). `apps/ml/warmup.py` 60 câu / 12 nhánh, 100% / 100%; `celery_main.py` 22 / 2, 100% / 100%; `__init__.py` rỗng. Đây là cận dưới (chỉ 3 tệp test), bộ đầy đủ chỉ phủ thêm → đơn vị `apps/ml` ≥ 90/90 ở cổng tích hợp.

## Điều kiện dừng sớm

Không có. Cây sạch; một commit `test(ml): cover warmup branches and fix mypy in loader tests` (≤ 72 ký tự, đúng mẫu), trailer `Prompt: PERF-03` liền với `Co-Authored-By:`; có `changes/PERF-03.md`. Diff chỉ chạm 2 tệp test, không tệp cấm. Không thêm `skip`/`xfail`/`noqa`/`pragma`/`type: ignore` (dòng `import onnxruntime as ort  # type: ignore[import-untyped]` của hai tệp test có từ trước, có mã).

## Đã soát, không có finding

- **Đích monkeypatch không đổi.** `loader.py:23` và `test_loader_providers.py:6` đều `import onnxruntime as ort`, cùng trỏ `sys.modules["onnxruntime"]`; `monkeypatch.setattr(ort, …)` vá đúng đối tượng mà `loader.select_providers`/`_session`/`_preload_cuda_dlls` tra lúc chạy (`ort.get_available_providers`, `ort.InferenceSession`, `ort.preload_dlls`). `monkeypatch` hoàn nguyên sau test như trước.
- **mypy.** `PINNED` nhập từ nơi định nghĩa `packages.ml_contracts.pinned`, cùng đối tượng `warmup.PINNED`. Log: `mypy --strict` "Success: no issues found in 1203 source files".
- **Test khẳng định hành vi, không chỉ chạy dòng.**
  - `test_warm_session_skips_non_float_inputs`: khẳng định `dummy_feed` trả `None` cho đầu vào `tensor(int64)`, và `run` giả ném `AssertionError` nên `_warm_session` lỡ gọi lượt giả là đỏ.
  - `test_warm_ocr_detector_runs_one_white_page`: khẳng định `_detect` nhận đúng đối tượng từ `_detector()`, ảnh `(64, 64, 3)` và `min == 255` (trắng toàn trang).
  - `test_worker_process_init_warms_up`: khẳng định receiver gọi `warm_up` đúng một lần (xem finding 1).
- Test không phụ thuộc thời gian thật, thứ tự hay mạng; không nạp mô hình thật (bộ dò OCR bị thay), chạy song song được. Docstring đủ mỗi hàm mới (R-01).

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | TEST | Tên và docstring nói kiểm "receiver `worker_process_init`", nhưng test gọi thẳng `warmup._warm_on_start(sender=None)`. Bỏ dòng `@worker_process_init.connect` ở `warmup.py:99` (worker hết làm ấm, mất mục tiêu PERF-03 P3) thì test vẫn xanh: test chỉ kiểm thân hàm một dòng, không kiểm việc gắn tín hiệu. | `apps/ml/runtime/tests/test_warmup.py:115-126` | Thêm một khẳng định đăng ký, không bắn tín hiệu thật (receiver của `packages/messaging/celery_app.py:123` cũng nghe `worker_process_init`): `assert warmup._warm_on_start in worker_process_init._live_receivers(sender=None)` (hoặc duyệt `worker_process_init.receivers`, gỡ `weakref` bằng `r()`; dạng phần tử tuỳ bản celery, kiểm lại khi viết). Không chặn merge. |
| 2 | Nit | TEST | `test_warm_ocr_detector_runs_one_white_page` không khẳng định `dtype == uint8` của trang giả (bộ dò OCR đọc ảnh 8 bit). | `apps/ml/runtime/tests/test_warmup.py:105-112` | Ghi thêm `page.dtype` vào bộ ghi rồi so `np.uint8`. Không cần sửa. |

## Điểm
| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 | 0,50 |
| TEST | 7% | 4 | 0,28 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: **4,93 / 5** · P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 1

## PHÁN QUYẾT: APPROVE

Nhánh chỉ thêm/sửa test, đóng đúng hai lý do cổng tích hợp đỏ: (1) đơn vị gốc `apps/ml` nay 100% dòng và nhánh (reviewer tự đo, cận dưới); (2) `mypy --strict` sạch nhờ nhập `PINNED`/`ort` trực tiếp, đích monkeypatch là cùng module `onnxruntime`. Lượt đầy đủ tại d395134817e6 thoát 0 ở mọi bước. Không P0/P1/P2, điểm 4,93 ≥ 4,0. Finding 1 (P3) nên làm ở đợt sửa kế, không chặn merge. Sau gộp, chạy verify tích hợp trên `main` (`VERIFY_BRANCH=integration`) để `coverage_gate` kiểm cả đơn vị `apps/ml`, vì lượt nhánh không kiểm đơn vị này.
