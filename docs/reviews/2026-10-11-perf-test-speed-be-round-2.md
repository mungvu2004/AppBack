# Review merge perf/test-speed-be → main (lượt 2)

- Ngày: 2026-10-11 · Reviewer: phiên /merge-review (độc lập) · Commit đầu nhánh: 7c87614556ee · Lượt 1: `2026-10-11-perf-test-speed-be.md` (@ 981e0e95)
- Phạm vi soát: diff vòng sửa `git diff 981e0e95 7c876145` (7 tệp, +39/−37): efad5db3 (F1–F5), 0c2285f6 (`remove(..., v=True)`), bdcbf1fa (trap dọn tar giữ mã thoát).
  Cây sạch; 3 commit đúng mẫu, `%(trailers:key=Prompt)` = `PERF-01` cả 3; không pragma/noqa/type: ignore/skip/xfail mới; không chạm tệp cấm.
- Cổng: Phạm vi kiểm: đầy đủ — diff chạm `tools/**`, `packages/testing/**` (R-33b (2)); đọc log cổng của việc gộp, không chạy lại.
  `bash tools/verify/run.sh verify` mã thoát 0 (log: `backend/dieu-phoi/chay/PERF-01/do-cuoi/be-sua3.log` = `<wt>/.cache/src-out/verify/20261010T203117Z-7c87614556ee.log`,
  sha khớp HEAD, container/venv `perf-be`); 10/10 bước đạt; `8427 passed` (+1 = `test_remove_container__drops_anonymous_volume`).
- Độ phủ: tổng dòng 99,47% · nhánh 98,02%; mọi gói bị chạm ≥ 90/90 (thấp nhất `apps/worker/pipeline_persist` 98,48/90,62); tập file bị chạm 99,21/97,30.

## Đối chiếu finding lượt 1
| # | Trạng thái | Bằng chứng |
|---|---|---|
| F1 (P2) | đã sửa | `repo` vá `MYPY_LOG` (`test_steps_commands.py:102-104`); log cổng dòng 480-481 nay có `--- mypy (nền) ---` / `Success: no issues found in 1156 source files` (lượt 1 rỗng). |
| F2 (P3) | đã sửa | `--ignore-failed-read` (`run.sh:71`); reviewer thử GNU tar 1.35: tệp thiếu → cảnh báo, rc=0, tar chứa tệp còn lại. |
| F3 (P3) | đã sửa | `mktemp -d .cache/src-tar/run.XXXXXX` mỗi lượt, mount đúng thư mục đó, `trap … EXIT` xoá (`run.sh:68-72,115`). Reviewer thử: trap có lệnh hỏng vẫn giữ mã thoát 0/3 của script. |
| F4 (P3) | đã sửa | Trả về đúng `assert scan(REPO_ROOT) == []` như main — bỏ cache theo mtime. |
| F5 (P3) | chấp nhận có ghi | Docstring ghi trần ~300 MB/worker, nhả cuối tệp (`test_tasks.py:59-60`) — đúng phương án đề xuất. |
| F6 (Nit) | còn mở | Không đổi; Nit không chặn. |
| F7 (Nit) | còn áp dụng | Thông điệp squash phải theo R-36b. |

Thay đổi mới: `services._remove_container` thêm `v=True` — chỉ xoá volume **ẩn danh** của container, không đụng volume có tên; có test thật trên Docker
(`test_orphan_sweep.py:189-200`, tạo container `REDIS_IMAGE`, khẳng định volume `/data` biến mất). Đúng gốc (R-19), không đổi phép kiểm nào.

## Finding
| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | Nit | OPS | `--ignore-failed-read` nuốt cả lỗi đọc khác "đã xoá" (quyền, tệp bị khoá) → tệp vắng khỏi `/tmp/w` mà cổng vẫn chạy; dấu vết duy nhất là cảnh báo của tar trên stderr. | `tools/verify/run.sh:71` | Tuỳ chọn: trừ `git ls-files -d` thay vì cờ, để lỗi đọc thật vẫn làm hỏng lượt. |
| N2 | Nit | MNT | Lượt bị giết cứng (SIGKILL) để lại `.cache/src-tar/run.*` (~13 MB); `gc` không dọn. | `tools/verify/run.sh:68-70` | Tuỳ chọn: `gc` xoá `run.*` cũ hơn 1 ngày. |

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

Tổng: 5,0 / 5

## PHÁN QUYẾT: APPROVE
F1–F4 đã sửa ở gốc, F5 được chấp nhận và có ghi trần bộ nhớ. Cổng đầy đủ trên đúng 7c876145 thoát 0 với 8.427 test, độ phủ giữ ngưỡng. Không có P0–P3 mới,
nên không phát sinh dòng `DEBT.md` bắt buộc. Gộp bằng squash; khối trailer theo R-36b (`Prompt: PERF-01` liền `Co-Authored-By`, kiểm bằng `%(trailers:key=Prompt,valueonly)`).
