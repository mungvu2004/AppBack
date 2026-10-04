# Review merge fix/debt-02-w2 → main (DEBT-02 đợt 2, lượt 2)

- Ngày: 2026-10-04 · Reviewer: cùng phiên /merge-review của lượt 1 (R-37) · Commit đầu nhánh: `faccceb7828d`
- Phạm vi: `git diff 4e166ca..faccceb`, gồm 20 commit và 27 file (+550/−202). Đây là vòng sửa MR1 cho 21 finding của lượt 1 (`2026-10-04-fix-debt-02-w2.md`), cộng gốc **NO-347** (W3/C05c-b). Bảng finding ↔ commit ↔ test nằm ở `backend/dieu-phoi/chay/DEBT-02/W2/M/mr1.md`.
- Cổng: phạm vi **đầy đủ**, vì vòng sửa chạm fixture dùng chung `packages/testing/fixtures/*` (R-33b). Lượt cổng do việc gộp chạy:
  - Lệnh `bash tools/verify/run.sh verify`, **mã thoát 0**.
  - Log: `W2/M/gate-3.log` + `gate-3-container.log`, trỏ tới `debt02-w2-pipeline/.cache/src-out/verify/20261004T094031Z-faccceb7828d.log`. Tên log khớp sha.
  - 7971 passed, khớp 7971 `<testcase>` trong `.junit.xml`. Perf 25 passed, khớp 25 trong `.perf.junit.xml`. `case_gate: đạt`.
- Độ phủ: tổng dòng 99,45% · nhánh 97,87%. Tập file bị chạm 99,41/97,69.
  - Thấp nhất: `apps/api/admin_ml_registry` 99,33/95,24, `apps/ml/training_runner` 98,87/95,33, `packages/db` 97,36/95,76.
  - Mọi gói ≥ 90/90.

## E.10 (cổng 3, từ mã thoát thật)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict (nguội) | đạt |
| 4 | lint-imports | đạt |
| 5 | pytest -n (cov) → coverage_gate | đạt |
| 5b | pytest -m perf → case_gate | đạt |
| 6 | lint_migrations → migrate_check | đạt |
| 7 | H1 H3 H4 H5 | đạt |
| 8 | openapi | đạt |

## Tự tái hiện đỏ → xanh (một container)

- Lệnh: `VERIFY_NAME=debt02-w2-pipeline bash tools/verify/run.sh shell < backend/dieu-phoi/chay/DEBT-02/W2/R/do-xanh-r2.sh`. Log ở `W2/R/do-xanh-r2.log`, run.sh thoát 0.
- Cách làm đỏ: thay file bằng bản `@4e166ca` (base64 của `git show`), hoặc đảo đúng phần sửa. Test của `faccceb` giữ nguyên.

| Finding | Test | Đỏ | Xanh |
|---|---|---|---|
| NO-347 | `test_orphan_sweep.py::test_sweep_orphans__container_removed_while_listing` | `services.py @4e166ca` (`containers.list` → `get`): `404 … /containers/<id>/json`, rc 1 | 1 passed, rc 0 |
| P2 #2 | `test_orphan_sweep.py::test_remove_container__concurrent_removal_both_succeed` ×3 lượt | `services.py @4e166ca` (chỉ nuốt `NotFound`): **409 Conflict** cả 3/3 lượt, rc 1 | 3/3 passed, rc 0 |
| P3 #5 | `test_hooks.py::test_on_after_commit__J09_slow_callback_times_out` | đột biến `hooks.py:149` bỏ `wait_for` (idle chờ callback xong): `assert not True` (`finished` đã đặt), rc 1 | 1 passed, rc 0 |
| Nit #19 | `test_view_parts.py::test_load__floors_without_drawings_need_no_signer` | bỏ `if not rows: return {}`: `ValidationError storage_backend Field required`, rc 1 | 1 passed, rc 0 |
| P3 #8 | `test_steps_commands.py::test_verify__full_gate_runs_mypy_cold` | đột biến `full_gate = wanted is None`: `[argv2-/dev/null]` `['/work/mypy-x'] == ['/dev/null']`, rc 1 | 3 passed, rc 0 |

Các đột biến #3, #7, #13, #18 do tác giả chạy (`W2/M/pre3.log:524-545`, cả 8 dòng "mã thoát: 1 (mong 1)"). Phiên này không chạy lại các đột biến đó, chỉ đối chiếu với mã.

## Đối chiếu 21 finding của lượt 1

| # | Kết luận | Bằng chứng |
|---|---|---|
| 1 P2 | **đã sửa đúng đề xuất** | Theo khuôn FIX-158, mỗi tệp tách thành hai test:<br>- `test_upload.py:488-538`: helper `_k36_upload`; test không perf giữ `201`, `checked_out == 0`, `peak <`; test perf `…_get_beats_the_deadline_while_streaming` chỉ giữ trần.<br>- `test_upload_flow.py:289-343`: tách tương tự.<br>- `test_routing.py:239-290`: tách tương tự.<br>Test perf mới không mang mã case. Mỗi chủ một commit. |
| 2 P2 | **đã sửa, cả hai vế** | - `_remove_container` nuốt riêng 409, mã khác vẫn ném.<br>- `_sweep_once` chạy dưới `FileLock` + tệp chủ phiên.<br>- Lệch đề xuất: khoá đặt ở `tempfile.gettempdir()` chứ không ở basetemp, vì `_start` còn được gọi từ `ephemeral_*` không có `tmp_path_factory` (`services.py:71-73`). Lý do đứng được: phiên khác ghi đè chủ chỉ làm quét thêm một lượt, và việc xoá trùng đã vô hại.<br>- Đỏ→xanh ở trên. |
| NO-347 | **đã sửa đúng gốc** | - `sweep_orphans` liệt kê bằng một lời gọi `client.api.containers(all=True, filters=…)`, lấy id và nhãn, không inspect từng container.<br>- `_owner_alive` (anh em cùng khe hở, `tai-hien-NO-347.md`) cũng đổi sang `client.api.containers`.<br>- Grep `containers.list` trong `packages/testing` không còn chỗ nào.<br>- Test chặn tất định trên Docker thật: vá `ContainerCollection.get` để xoá thật container ngay trước lúc đọc. |
| 3 P3 | đã sửa | `_is_time` nhận `ast.Name`. Hàm phụ có trần bị bắt khi không có test gọi, hoặc có test gọi mà thiếu `perf`. Thêm 5 mẫu tự kiểm. Quét rộng lộ ra `test_device_gpu.py::wait_for`; chỗ này đã đổi thành `raise TimeoutError`, đúng nghĩa hạn chờ. |
| 4 P3 | đã sửa (sổ) | FIX-154 [4] / FIX-163 ghi `802da8b`. FIX-163 [6] dẫn tham số có thật. Không viết lại lịch sử, theo tiền lệ FIX-134. |
| 5 P3 | đã sửa đúng đề xuất | Callback chặn trên `release.wait(10)`, sau idle khẳng định `not finished.is_set()`, không đồng hồ. `finally: release.set()`. Đỏ→xanh ở trên. |
| 6 P3 | đã sửa | `try/finally: kill(); wait()`. `kill` trên tiến trình đã reap là no-op. |
| 7 P3 | đã sửa | `_module_level` đi vào if/try/with/class, bỏ qua thân hàm. Có 2 mẫu đỏ mới. Nit mới N1 ở dưới. |
| 8 P3 | đã sửa | `full_gate = wanted is None or wanted ⊇ mọi bước`. README ghi rõ cần cả `5b`. Đỏ→xanh ở trên. |
| 9, 10 P3 | đã sửa (tệp điều phối / báo cáo) | `C08/tai-hien-NO-265.md` đã viết lại. `M/bao-cao.md` ghi cả teardown −58% và thời gian tường −6%. Ô đóng `DEBT.md` của NO-279 do điều phối ghi khi đóng. |
| 11 Nit | đã sửa | `discover_worker_tasks()` ở `packages/messaging/schedules.py`, gọi từ `celery_main.py` và `register_tasks`. Cùng chủ B0-05. Nit mới N2 ở dưới. |
| 12, 13 Nit | đã sửa | `CASE_IN_NAME_RE` công khai. `_cold_mypy_cache` chỉ trả `MYPY_CACHE_DIR`, và xoá biến nếu trước đó chưa có. |
| 14 Nit | e2e đã sửa (FIX-200, B5-07) | Phần `training_segformer/tests/test_trainer.py:383-393` nằm trong dòng nợ **có sẵn** NO-318 (⬜, 2026-10-02, chủ B6-04a), xếp W3/C11. Đây không phải nợ mới, nên chấp nhận. |
| 15 Nit | đã sửa | Ba đường trỏ/chú thích. `9fc85da` cắt một dòng 122 ký tự có sẵn. |
| 16 Nit | đã sửa | - Chụp seed và nạp lại nằm trong PL/pgSQL `format('%I')`.<br>- Bỏ `_has_rows` cùng hai `noqa: S608` trên tên bảng.<br>- Còn hai `noqa: S608` (`_RESET_SQL`, `_SNAPSHOT_SQL`) chỉ chèn hằng module. Có mã và lý do. |
| 17 Nit | đã sửa | `OverflowError` cùng test. |
| 18 Nit | đã sửa | Test so `pg_backend_pid()` qua 3 lượt dọn. Engine dựng trong `try`, `loop.close()` ở `finally`. |
| 19 Nit | đã sửa | Return sớm trước `signer()`. Đỏ→xanh ở trên. |
| 20, 21 Nit | đã sửa | `assert len(rows) == 1, rows`; `b"\x01"`. |

## Soát cơ học (diff vòng sửa)

- Cây sạch.
- K27: kiểm từng commit bằng `tao_so_tra.py --chu`. Mọi commit chỉ chạm tệp của một chủ, trailer khớp. `49856e9` là sổ FIX của điều phối.
  - Mã FIX dùng lại theo đúng chủ: 139, 143, 149, 150, 154–156, 160, 162, 163, 169, 171, 173, 174.
  - FIX-200 là mã mới cho B5-07.
- [11].3: `git diff 4e166ca..faccceb -- apps packages tools deploy .github tests | grep -nE '^\+.*(TODO|FIXME|XXX|ponytail:|pragma: no cover|xfail|pytest\.skip|skipif|sleep\()'` → **rỗng**.
- `noqa`/`type: ignore` thêm vào đều có mã và lý do: `S608` ×1, `import-untyped` ×1. Thêm vào đó, một `arg-type` có sẵn chỉ được rút ngắn chú thích.
- R-01: quét AST mọi `.py` thêm/sửa của vòng sửa, gồm cả hàm lồng → 0 hàm thiếu docstring.

## Finding mới (sửa trong vòng sửa, không ghi nợ)

| # | Mức | ID | Mô tả + bằng chứng | Vị trí | Đề xuất sửa |
|---|---|---|---|---|---|
| N1 | Nit | TEST / LOG | Luật mới báo **hai lần** cùng một vi phạm cho một lệnh `from ultralytics import YOLO`. Nguyên nhân: `names` gồm cả `node.module` lẫn `module.alias`. Test còn ghim chính bản trùng: `test_module_try.py` xuất hiện hai dòng y hệt. | `apps/ml/runtime/tests/test_imports.py:47`, `:55-62`, `:119-120` | Mỗi nút import chỉ báo một lần luật `ultralytics`, ví dụ xét `top == "ultralytics"` một lần trên tập `{n.split(".")[0] for n in names}`. Sửa danh sách mong đợi về một dòng. |
| N2 | Nit | TEST-04 | Test phụ thuộc thứ tự chạy: `pipeline.orchestrate.start` là `shared_task`, nên đã có trong `current_app.tasks` khi bất kỳ test nào trước đó trong cùng tiến trình xdist đã nhập `apps.worker.pipeline_orchestrate.tasks`. Khi đó đột biến "`discover_worker_tasks` không làm gì" vẫn xanh. | `packages/messaging/tests/test_schedules.py:152-156` | Kiểm trong tiến trình con mới như `test_register_tasks__module_not_imported_before`: khẳng định module chưa nhập, gọi `discover_worker_tasks()`, rồi khẳng định tên task có trong sổ. |

## Điểm (RULE.md §5)

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC | 25% | 5 | 1,25 |
| CON | 15% | 5 (P2 #2 + NO-347 đã sửa, đỏ→xanh tự chạy) | 0,75 |
| LOG | 15% | 5 | 0,75 |
| PERF | 10% | 5 | 0,50 |
| RES | 10% | 5 | 0,50 |
| DB, API | 10% | 5 (không đổi schema/openapi) | 0,50 |
| TEST | 7% | 4 (Nit N1, N2) | 0,28 |
| OBS, OPS | 5% | 5 | 0,25 |
| MNT | 3% | 5 | 0,15 |

Tổng: **4,93 / 5**

## PHÁN QUYẾT: APPROVE

Theo ma trận: không có P0/P1/P2/P3 mới, điểm 4,93 ≥ 4,0.
- Cả 21 finding của lượt 1 đã sửa, hoặc lệch đề xuất với lý do đứng được (#2 vị trí khoá; #14 phần segformer thuộc NO-318 có sẵn).
- NO-347 đã sửa đúng gốc, có test chặn tất định.
- Cổng 3 trên `faccceb` thoát 0.
- Năm finding hành vi đã được tự tái hiện đỏ→xanh.

Theo DEBT-02 [6] D.3, hai Nit mới (N1, N2) phải sửa trước khi gộp, không ghi nợ. Cả hai chỉ chạm tệp test:
- N1: một commit B5-01.
- N2: một commit B0-05.

Phạm vi kiểm cho phần sửa này là **đích**: chạy hai test đó + bước 1–4. R-33b không đòi cổng đầy đủ vì không chạm fixture dùng chung hay mã sản phẩm. Nếu reviewer soát đích hai commit này và xác nhận, không cần thêm lượt review đầy đủ.
