# Review merge feature/b6-04b-yolo-eval → main

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `fca664a347a1`
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1 — review lượt 1 của nhánh; cổng do lớp gộp chạy, reviewer không chạy lại);
  `bash tools/verify/run.sh verify` **mã thoát 0** (log: `backend/dieu-phoi/chay/B6-04b/M/gate-1.log` +
  `M/gate-1-tail.log`; sha trong `M/gate.sha` = `fca664a347a17b705465106cc5c037c9defd2b45`)
- Độ phủ: tổng **dòng 99,47 %** · **nhánh 98,02 %**; `apps/ml/ml_eval` 99,01 / 95,45; `apps/ml/training_yolo` 98,51 / 98,15;
  tập file bị chạm 98,75 / 96,67 (`coverage_gate: đạt`)

## Bảng cổng (E.10, từ mã thoát thật trong log)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | 1294 tệp |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | 1084 tệp |
| 4 | `lint-imports` | đạt | 10 contract kept, 0 broken |
| 5 | `pytest -n` + `coverage_gate` | đạt | 7686 passed / 632 s |
| 5b | `pytest -m perf` + `case_gate` | đạt | perf: 0 đơn vị bị chạm; 83 op mount, 3 cảnh báo cũ (NO-222) |
| 6 | `lint_migrations` + `migrate_check` | đạt | 21 revision, đúng 1 head |
| 7 | H1 H3 H4 H5 | đạt | |
| 8 | `openapi` | đạt | |

`mã thoát: 0`. Không bước nào "không áp dụng": nhánh không thêm thao tác HTTP nhưng cổng vẫn chạy đủ bước 7–8 trên hợp đồng cũ.

- Test của hai module: **86 passed, 1 deselected** (`gpu`) / 75,95 s; chậm nhất **13,80 s** (setup lượt CPU tí hon) → mọi test ≤ 120 s (`M/pre.log:146-160`).
- `case_gate` chỉ in dòng cho task khi **hỏng** (`tools/case_gate.py:557-558`); `case_gate: đạt` ⇒ `ml_eval_evaluate_version`
  có trong sổ task và đủ `J01, J06` (cổng tự đòi) + `J02, J03, J05, J08` (`cases.toml`).
- Lượt GPU: **chưa chạy** — container verify không có CUDA (`torch 2.14.0+cpu`); marker `gpu` bị `addopts` loại, không phải skip (K24 sạch).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | LOG-01 / R-19 | `_emit` suy ra split từ `map50 is None`, nên lời gọi `_emit(epoch, map50=None)` (epoch không có số đo validate) rơi vào nhánh `train`: log `training_metric_skipped` **hai lần với `metric="loss"`**, **không bao giờ** báo `map50` bị bỏ. Mất đúng tín hiệu dẫn tới `TRAINING_METRICS_MISSING`; không test nào soát log của ca này. | `apps/ml/training_yolo/trainer.py:173-179` (gọi ở `:162-163`) | Truyền tên số đo tường minh (`_emit(epoch, "loss", loss)` / `_emit(epoch, "map50", map50, high=1.0)`), bỏ suy luận `train = map50 is None`. |
| 2 | P2 | LOG-02 | `last_map50` chỉ đặt khi **cả** `loss` **và** `map50` trong miền. Epoch có `map50` hợp lệ nhưng `loss` không hữu hạn/thiếu → `last_map50` vẫn `None` → `_run` ném `TRAINING_METRICS_MISSING` và `finally` xoá sạch `out_dir`: mất cả lượt huấn luyện đã chạy xong. Khối [6] chỉ cho mã đó khi **không epoch nào có `map50`**. | `apps/ml/training_yolo/trainer.py:164-170` | `if _in_domain(map50, 1.0): self.last_map50 = map50`; log `training_epoch_finished` vẫn gác theo cả hai số. |
| 3 | P2 | MNT-01 / R-34 | Nợ tác giả tự nêu trong `bao-cao-B6-04b.md` ("Nợ": `apps.ml.runtime.loader._read_object` là hàm riêng tư, đề xuất B5-01 công khai) **không có dòng `NO-<nnn>` trong `DEBT.md`** (dòng cuối NO-318; không dòng nào về `_read_object`/`ml_eval`). | `apps/ml/ml_eval/tasks.py:28`; `DEBT.md` thiếu dòng | Thêm `NO-<nnn>` P2, chủ **B5-01**: công khai `read_model_object`; `ml_eval` đổi sang tên công khai. Giữ nhập riêng tư tới lúc đó (chép lại trần `MODEL_MAX_BYTES` sẽ tệ hơn). |
| 4 | P3 | TEST-01 | `assert os.getpid() > 0` không bao giờ hỏng, nhưng docstring coi nó là bằng chứng "cha còn sống" sau khi con chạm `RLIMIT_AS` (khối [8] đòi "worker còn sống"). | `apps/ml/ml_eval/tests/test_sandbox.py:57` | Kiểm thật: chạy tiếp `_run(const_yolo())` trong cùng tiến trình và đòi có số đo. |
| 5 | P3 | TEST-02 | `expected` tính bằng **chính** `map50` đang kiểm → test chứng minh nối dây, không phải "khớp tính tay" như khối [8] và docstring ghi (giá trị tay thật có ở `test_metrics.py`, nên tác động thấp). | `apps/ml/ml_eval/tests/test_evaluate.py:188-200` | Sửa docstring, hoặc ghim hằng tính tay cho 3 seed. |
| 6 | P3 | RES-01 | `_result` `json.loads` **toàn bộ** stdout của con. Một dòng lạ trên stdout con (banner thư viện) biến lượt đánh giá **đạt** thành `failed MODEL_FORMAT_UNSUPPORTED` — model tốt bị đánh dấu hỏng. | `apps/ml/ml_eval/tasks.py:97-100` | `json.loads(out.strip().splitlines()[-1])` — giao thức đã là "một dòng JSON". |
| 7 | P3 | TEST-03 | Khối [8] đòi heartbeat đúng nhịp "**cả lúc validate**". Test đơn vị chỉ kiểm ca **chưa** tới hạn qua `on_train_batch_end`; `on_val_batch_end` chỉ chạy trong lượt thật, nơi khẳng định duy nhất là `len(heartbeats) >= 2`. | `apps/ml/training_yolo/tests/test_trainer_units.py:32-45` | Gọi `on_val_batch_end` với `monotonic` giả vượt ngưỡng → đòi đúng một nhịp tim. |
| 8 | Nit | TEST-04 | `mkdtemp()` không ai xoá (test khác đều dùng `tmp_path`). | `apps/ml/ml_eval/tests/test_sandbox.py:276` | Nhận `tmp_path`. |
| 9 | Nit | MNT-02 | Ba nhánh phòng thủ không với tới từ đường chính (`map50` chỉ gọi `_ap_for_label` cho nhãn **có** đáp án) — đúng ba dòng duy nhất còn hở độ phủ. | `apps/ml/ml_eval/metrics.py:77-78, 92-93, 139-140` | Giữ nhưng ghi rõ là bất biến của người gọi, hoặc gọi thẳng trong test đơn vị. |
| 10 | Nit | MNT-03 | `else` cuối coi **mọi** họ khác là `dimensionReading`; thêm họ thứ tư sẽ lặng lẽ đi đường CER. `build_adapter(ref: Any)` mất kiểu dù `ModelRef` nhập được. | `apps/ml/ml_eval/evaluate.py:211,217`; `apps/ml/ml_eval/sandbox.py:199` | Nhánh tường minh theo `ModelFamily` (`assert_never`); `ref: ModelRef`. |
| 11 | Nit | PERF-01 | Bản storage: cha giữ **toàn bộ** bytes trong RAM (trần 4 GiB) rồi ghi thêm một bản ra `TemporaryDirectory`, con đọc lại — đỉnh ~2× cỡ model trong cgroup `ml` dùng chung với huấn luyện. Đây là thiết kế đã chốt (hộp cát không cầm client kho), chỉ ghi nhận. | `apps/ml/ml_eval/tasks.py:112-124` | Khi B5-01 công khai bộ đọc, cho nó **stream** thẳng ra đường dẫn thay vì trả `bytes`. |

Không có P0, không có P1.

## Đã tự đối chiếu (khẳng định của tác giả → bằng chứng trong mã)

- **Thứ tự K12:** `train()` kiểm `family`/`base_model` rồi `_pinned_pt` (so SHA theo khúc) **trước** `prepare_ultralytics()` — `trainer.py:271-274`; `_pinned_pt` chỉ nhập `errors`/`pinned`, không kéo `torch`. Test `test_rejects_foreign_spec`, `test_rejects_weights_with_wrong_sha` chặn cả `ultralytics.YOLO` và `torch.load`.
- **Ngoại tuyến:** cờ `YOLO_*` + `YOLO_CONFIG_DIR` 0700 đặt trước lần nhập đầu, `settings.update({"sync": False})`, `Arial.ttf` rỗng, `check_amp` thay ở **cả hai** module (`utils.checks` và `engine.trainer`) — `trainer.py:56-73`; chứng minh trong tiến trình **mới** bằng `test_offline_env_subprocess`.
- **Tham số `train`:** `batch` là `int`, `plots=False`, `deterministic=True`, `workers=0`; nhánh cuda `device=0`, `amp=True`, `batch` 16/8 — `trainer.py:346,368-385`, test `test_cuda_branch_uses_gpu_arguments`.
- **Xuất:** `export_yolo` (không `Model.export`), kiểm `onnx.checker` + `external_data` + dựng `YoloOnnxDetector` trên tệp vừa sinh; `finally` xoá `out_dir/ultralytics` và `work_dir`; `test_cpu_run_leaves_only_onnx` đòi `out_dir` chỉ còn `model.onnx` và không còn `yolo-*`.
- **Log:** `render_log` trả `None` khi thiếu/thừa tham số (`packages/messaging/payloads/training.py:141-155`), nên `test_log_templates_render` là kiểm hợp đồng thật; tham số không chứa `/`, `\`, `://`.
- **Dataset:** `load_raster(..., max_pixels=DEFAULT_MAX_PIXELS)` (K13), `objects_from_json`, không đọc `test/` (`test_does_not_read_test_split`), lưới `tile_windows`/`overlap_for` của B5-03, luật giữ hộp 10 % + cạnh ≥ 2 px (bốn test biên 10 %/5 %/1 px/2 px), lát nền 1/4 đếm riêng mỗi split, `yaml.safe_dump`, cắt hộp bằng numpy toàn mảng.
- **`ml_eval`:** AP viết lại bằng numpy, so `ultralytics.utils.metrics.compute_ap` trên 20 đường cong (`test_ap_matches_ultralytics_compute_ap`; `ultralytics` chỉ nhập **trong test**); dự đoán hoàn hảo = 0,995; `cer` NFKC/bỏ dấu/casefold; làm tròn `js_round(x×1e6)/1e6` ở **một** chỗ; `mask_iou` dùng lại `mask_overlap` của B5-02; luôn CPU — `load_onnx` tự dựng phiên CPU, `tasks.py` không nhập `gpu`/`resolve_device` (M04).
- **Hộp cát:** `setrlimit(RLIMIT_AS)` đặt **trước** mọi nhập nặng (`sandbox.py:252-254`; nhập nằm trong `_evaluate`), `start_new_session=True`, `os.killpg` khi quá hạn, phân loại `SIGKILL` ngoài → `DEPENDENCY_UNAVAILABLE` còn `MemoryError`/`SIGABRT`/`SIGSEGV`/thoát ≠ 0 → `MODEL_FORMAT_UNSUPPORTED`, không `multiprocessing`, env tối thiểu (`test_ml_eval_sandbox_child_env_is_minimal`).
- **K23:** Redis/Celery/`onnxruntime`/tiến trình con đều **thật**; bản giả chỉ là `Model.train` + `export_yolo` trong fixture `fake_run`. Không mock `onnxruntime` hay Celery ở bất kỳ test nào.
- **K24:** không `pragma`, không `skip`/`xfail` mới (lớp gộp **bỏ** một `skipif` của C), mọi `# noqa`/`# type: ignore` có mã + lý do, `gpu` chỉ gắn cho test GPU thật.
- **R-01/R-08:** mọi hàm (kể cả test và hàm lồng) có docstring; hàm dài nhất (`train`, `_fit`, `_process_split`) đều < 50 dòng.
- **R-27:** `git diff --name-only main...HEAD` ⊆ `apps/ml/training_yolo/**`, `apps/ml/ml_eval/**`, `changes/B6-04b.md` — không đụng file của prompt khác, không `docs/charter/*`, `uv.lock`, `openapi.json`, `tools/*`.
- **Commit:** 38 commit, dòng đầu đúng Conventional Commits + trailer `Prompt: B6-04b`; 6 commit `Merge branch …` được `.githooks/commit-msg` miễn tường minh và sẽ tan trong squash vào `main`.

## Sáu quyết định biết trước của điều phối — phán quyết

1. **Dataset vi mô 800×600 thay 640×480** — **chấp nhận**. `render_plan` ném `ValueError` ở 640×480 (`P/check.log`); khổ không ảnh hưởng điều kiện của khối [8] (seed 0..5, 4 train / 2 validation, rời `EVAL_SET_SEEDS`), ghi rõ ở `tests/support.py:370-372`.
2. **`data.yaml names = ARTIFACT_LABELS` (11) và kiểm xuất với `ARTIFACT_LABELS`** — **chấp nhận, và là lựa chọn đúng duy nhất**: `YoloOnnxDetector.__init__` đòi `expected_channels = 4 + len(labels)` (`apps/ml/objects/detector.py:444`) còn `labels_for(ref)` trả `ARTIFACT_LABELS` cho bản storage (`apps/ml/objects/labels.py:40-44`) → model 10 lớp bị từ chối ở cả pipeline lẫn `ml_eval`. Chỉ số lớp vẫn `OBJECT_LABELS.index` (0..9); lớp 10 `other` không bao giờ có hộp.
3. **`cases.toml` chỉ khai mã J** — **chấp nhận**. `tools/case_gate.py` chỉ khớp `J\d{2}` cho `[[task]]` (NO-256/NO-294) và `tools/**` nằm trong khối [12]; độ phủ case không giảm vì M01–M06 vẫn có test và cổng tự đòi J01/J06.
4. **`failed` gửi `metrics=None`** — **chấp nhận**: `EvaluationDonePayload` buộc `None` khi `status="failed"`; theo schema, không theo chữ `{}` của [6]. J03 đòi đúng `None`.
5. **Hộp cát: cha đọc object rồi con dựng `LocalDiskStorage` trên thư mục tạm** — **chấp nhận**: con không cầm khoá hay client kho nào, checksum và luật "ONNX không tin" vẫn do chính `load_onnx` kiểm trong con; J02 (kho lỗi tạm) đi qua cha và `test…__J02` đòi `flaky.attempts == 3`. Đỉnh RAM: xem Nit 11.
6. **Mã lỗi nhập từ `training_segformer.errors` (thuần), `training_runner.errors`, `runtime.errors`** — **chấp nhận**: `training_segformer.errors` chỉ có hằng chuỗi nên nhập ở mức module an toàn cho `discover_trainers()`; hai module kia nhập lười trong hàm, đúng lý do "không kéo `onnxruntime` vào tiến trình API".

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 3 | 0,45 |
| PERF – Hiệu năng | 10% | 4 | 0,40 |
| RES – Chịu lỗi | 10% | 4 | 0,40 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 4 | 0,28 |
| OBS, OPS – Vận hành | 5% | 4 | 0,20 |
| MNT – Bảo trì | 3% | 3 | 0,09 |
| **Tổng** | **100%** | | **4,32 / 5** |

## PHÁN QUYẾT: APPROVE

Không P0, không P1; cổng đầy đủ xanh thật (mã thoát 0) đúng sha `fca664a`, độ phủ dòng **và** nhánh của cả hai module ≥ 95 %, mọi test ≤ 13,8 s. Phần khó của prompt đều làm đúng và có bằng chứng: thứ tự "so SHA trước khi nhập `ultralytics`" (K12), vá `check_amp` ở cả hai module, ngoại tuyến chứng minh trong tiến trình mới, hộp cát đặt `RLIMIT_AS` trước lần nhập `onnxruntime`, AP trùng `compute_ap` tới 1e-9 mà không nhập `ultralytics`, và dịch vụ thật ở mọi đường chính (K23 sạch). Sáu quyết định biết trước của điều phối đều có lý do đứng được — quyết định 2 (`ARTIFACT_LABELS`) thực ra là lựa chọn duy nhất khớp `YoloOnnxDetector`.

Ba P2 không chặn merge nhưng **phải có dòng `DEBT.md`** trước khi gộp (P2-3 chính là dòng đang thiếu). Khuyến nghị giao một FIX nhỏ cho chủ B6-04b: P2-1 và P2-2 đều nằm trong `_RunCallbacks.on_fit_epoch_end`/`_emit`, sửa gọn trong ~10 dòng và đáng làm trước lượt GPU thật, vì P2-2 có thể huỷ một lượt huấn luyện đã chạy xong khi `loss` không hữu hạn.

Lượt GPU vẫn là **chưa chạy** (không có CUDA trong container verify) — không tính là hỏng theo khối [11] mục 4, nhưng số VRAM/`map50`/thời gian của khối [8] chưa ai đo.
