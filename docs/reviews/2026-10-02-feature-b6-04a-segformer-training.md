# Review merge `feature/b6-04a-segformer-training` → `main` (lượt 1)

- Ngày: 2026-10-02 (`date -u`) · Phiên độc lập (R-37), worktree riêng `C:/Users/mxuan/orca/workspaces/AppBack/b6-04a-review`
  ở `git switch --detach bce4d4b`; không sửa mã, không merge.
- **PHÁN QUYẾT: APPROVE (4,60/5)** — không P0/P1; 3 P2 + 7 P3, tất cả nằm trong mã test hoặc bảo trì, không chạm
  đường chạy production.

## 1. Phạm vi diff

`git diff --name-status main...bce4d4b` = **19 tệp, toàn bộ mới, +1999 −0**:
`apps/ml/training_segformer/{__init__,config,data,errors,export,loop,metrics,model,trainer}.py`,
`apps/ml/training_segformer/tests/{__init__,support,test_config,test_data,test_export,test_gpu,test_metrics,test_model,test_trainer}.py`,
`changes/B6-04a.md`. **Không tệp nào ngoài cột "Sở hữu"** của khối [10] / front-matter `so_huu`. Không đụng
`docs/charter/*`, `uv.lock`, `openapi.json`, `conftest.py`, `tools/**`, `deploy/**`, `pyproject.toml`, hay mã của
prompt khác.

## 2. Cổng (đọc log của lớp gộp, KHÔNG chạy lại)

`M/gate.sha` = `bce4d4b` — khớp sha đi review. Log `M/gate-1.log`.

Tiêu đề log ghim sha: `…/verify/20261002T072826Z-bce4d4b40ac4.log` — **`bce4d4b`**, đúng cây đi review.
Trạng thái dưới đây lấy từ bảng tổng kết cuối log cộng **`mã thoát: 0`** (`exit=0`), không từ phỏng đoán.

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | **đạt** | `/work/contract-node/3c583539a0314ecd` |
| 1 | `ruff format --check` | **đạt** | |
| 2 | `ruff check` | **đạt** | |
| 3 | `mypy --strict` | **đạt** | 1061 tệp nguồn, 0 lỗi |
| 4 | `lint-imports` | **đạt** | Contracts: 10 kept, 0 broken |
| 5 | `pytest -n` (cov) → `coverage_gate` | **đạt** | **7600 passed**, 0 failed, 553,49 s; `coverage_gate: đạt` |
| 5b | `pytest -m perf` → `case_gate` | **đạt** | `perf: 0 đơn vị bị chạm`; `case_gate: đạt` |
| 6 | `lint_migrations` → `migrate_check` | **đạt** | 21 revision; 10/10 kiểm của `migrate_check` đạt, đúng 1 head |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | **đạt** | AppFront `9cf0b0bf`; 83/83 bản đồ, 86 mount, 1890 mẫu response |
| 8 | `openapi` | **đạt** | ghi 255.271 byte |

Không bước nào `hỏng`, `chưa chạy` hay `không áp dụng`. Cổng **không** chạy lại trong phiên review.

### Độ phủ của cổng (`coverage_gate`, `M/gate-1.log:378-381`)

| Phạm vi | Dòng | Nhánh |
|---|---|---|
| Tổng (AppBack) | **99,48%** | **98,01%** |
| `apps/ml/training_segformer` | **99,76%** | **98,08%** |
| Tập file bị chạm | **99,76%** | **98,08%** |

Cả ba đều trên ngưỡng 90% dòng **và** 90% nhánh (hai số riêng).

**Phạm vi kiểm: đầy đủ** (R-33b điều kiện 1 — lượt đầu của nhánh đi review; và điều kiện 3 — 19 tệp `.py` mới).
Phiên review **không** khởi động container `verify-run` nào: cả ba finding P2 và các P3 đều tái hiện được tĩnh
(đọc `packages/ml_contracts/pinned.py`, `tests/support.py`) hoặc đã có bằng chứng số trong log độ phủ của lớp gộp,
nên không cần lượt đích.

### Độ phủ từng tệp (tiền kiểm `M/pre2.log:211-221`, cùng cây `bce4d4b` — chi tiết hoá số của cổng)

| Tệp | Dòng | Nhánh |
|---|---|---|
| `__init__.py` | 100% | — |
| `config.py` | 100% | 100% (6/6) |
| `data.py` | 100% | 100% (6/6) |
| `errors.py` | 100% | — |
| `export.py` | 98% (thiếu `:86`) | 90% (1/10 một phần) |
| `loop.py` | 100% | 100% (12/12) |
| `metrics.py` | 100% | 100% (8/8) |
| `model.py` | 100% | 100% (4/4) |
| `trainer.py` | 100% | 100% (6/6) |
| **TOTAL** | **99%** (412 câu, 1 thiếu) | **98%** (52 nhánh, 1 một phần) |

Mỗi tệp ≥ 90% dòng **và** ≥ 90% nhánh. Không `pragma: no cover`, không `skip`, không `xfail`, không hạ ngưỡng.

### Thời gian test (`M/pre2.log:170-206`) — trần [11].2 là 120 s/test

38 test không-`gpu` chạy **25,01 s** tổng. Chậm nhất: `test_train_happy_path` setup **2,14 s** (fixture `trained`,
lượt `train` thật dùng chung), `test_train_m06_reproducible` **1,91 s**, `test_export_and_check_real_model` **1,59 s**,
`test_export_rejects_external_data` **1,39 s**, `test_export_parity_mismatch` **1,36 s**. 80 test < 0,005 s.
**Cao nhất 2,14 s = 1,8% trần.** Không test nào mang marker `perf` (không test nào khẳng định trần đồng hồ tường),
`gpu` chỉ gắn đúng một test GPU thật (`1 deselected`).

## 3. "Lệch khỏi prompt" — đối chiếu từng mục của `bao-cao-B6-04a.md`

| # | Lệch | Phán |
|---|---|---|
| 1 | Dataset vi mô **800×600** thay 640×480 ([8]) | **Chấp nhận.** `render_plan(seed, width_px=640, height_px=480)` ném `ValueError` (đo 2026-10-02, `P/check.log`); 800×600 vẫn nằm trong một lát `TILE_PX=1024` nên không đổi hình học test. Ghi rõ tại `tests/support.py:27-29`. |
| 2 | `errors.py` khai lại 3 chuỗi thay vì nhập `apps.ml.runtime.errors` / `training_runner.errors` | **Chấp nhận — đã tự kiểm.** `apps/ml/runtime/errors.py:13` nhập `onnxruntime.capi.onnxruntime_pybind11_state` ở **mức module**, và `apps/ml/training_runner/errors.py:10` nhập lại từ đó → nhập một trong hai sẽ kéo `onnxruntime` vào tiến trình, trái bất biến [2]. `test_errors_match_runtime_and_runner_strings` (`test_model.py:171`) so từng chuỗi nên hai nơi không trôi được. |
| 3 | `trainer.py` nhập lười `loop`/`model`/`export`; `TrainingStopped` lấy từ `training_runner` | **Chấp nhận.** Cùng lý do; `loop.py:22` và `metrics.py:15` nhập `TrainingStopped` (→ kéo `onnxruntime`) nhưng cả hai chỉ được `trainer.train()` nhập lười. Bất biến được **chứng minh bằng tiến trình con**: `test_trainer_discovered` (`test_trainer.py:373-380`) chạy `python -c "import apps.ml.training_segformer.trainer"` rồi khẳng định `{'torch','onnxruntime'}` không có trong `sys.modules`. Đây là cách kiểm đúng, không phải khẳng định trên giấy. |
| 4 | Không dùng phương án lùi [11].3 | **Chấp nhận.** `apps/ml/runtime/export.py` đã truyền `external_data=False, dynamo=False` rồi `normalize_onnx` từ chối dữ liệu ngoài → gọi `export_onnx` là đúng, không gọi thẳng `torch.onnx.export`. |
| 5 | `_validate` dùng `evaluate_iou(...) or 0.0` | **Chấp nhận có ghi chú.** `trainer.train` đã loại split kiểm rỗng trước khi nạp model (`trainer.py:75-77`), nên `None` không tới được; viết `if` sẽ sinh nhánh không test được mà K24 cấm `pragma: no cover`. Đổi lại, nếu một ngày `_validate` được gọi từ chỗ khác thì `iou=0.0` sẽ **im lặng** thay vì nổ — đã có chú thích tại `loop.py:147`, chấp nhận, không ghi finding. |
| 6 | Tách đôi `test_train_m04_precision`, `test_train_j04_cancel` | **Chấp nhận** — mỗi test một mệnh đề, đúng hướng. Mệnh đề M04 "vòng CPU với scaler tắt vẫn đi `scale → step → update`" vẫn được phủ: `_CountingAdamW` (`test_trainer.py:87-98`) đếm `optimizer.step` thật và `test_train_j07_heartbeat:296` khẳng định `steps == 2`. |
| 7 | Ca huỷ / nhịp tim / 2 epoch dùng `_TinyNet` + `_CountingAdamW` | **Chấp nhận, không vi phạm K23.** `_TinyNet` là `nn.Module` thật (`nn.Conv2d` stride `LOGITS_STRIDE`, `cross_entropy` thật), `_CountingAdamW` là lớp con `torch.optim.AdamW` thật — không phải mock `torch`/`transformers`. Chỉ `segformer_model.load_pretrained` bị vá, đúng danh sách cho phép. |

Ngoài bảy mục đã khai, tôi tìm thêm **ba lệch chưa khai** → P2-2, P3-6, P3-10 dưới.

## 4. Soát trọng tâm — những gì đã kiểm và đạt

**Kiểm trước việc nặng (đúng thứ tự, có test chứng minh).** `trainer.train` kiểm họ + `base_model` **trước mọi
lần đọc tệp** (`trainer.py:71`), và `test_train_base_model_mismatch:332` khẳng định `not missing.exists()` — tức
`data_dir` chưa từng bị chạm. Kiểm split rỗng (`:75-77`) đặt **trước** lệnh `import loop/model/export`, nên hai lối
ra rẻ nhất không nạp torch. `model.load_pretrained` băm SHA-256 `model.safetensors` **trước** `from_pretrained`
(`model.py:48-55`), và `test_train_m02_pinned_checksum` vá `from_pretrained` thành một hàm *ném AssertionError* —
cách chứng minh mạnh hơn là chỉ so mã lỗi. Thiếu `model.safetensors` (kể cả khi có `pytorch_model.bin`) →
`MODEL_FORMAT_UNSUPPORTED` trước mọi lần mở tệp. `use_safetensors=True, local_files_only=True`, không
`trust_remote_code`, không `torch.load`/`pickle`/`joblib` — `test_train_m03_ast_no_pickle_load` quét AST toàn gói.
Lỗi `from_pretrained` bắt **đúng một lớp tường minh** `OSError` (`model.py:65`), không `except Exception`, và
`test_train_from_pretrained_error_is_format_unsupported` chứng minh bằng `config.json` sai JSON thật (transformers
bọc `JSONDecodeError` thành `OSError` trong `_get_config_dict`).

**Dữ liệu.** `read_sample` đọc ảnh **chỉ** qua `load_raster(..., max_pixels=DEFAULT_MAX_PIXELS)` (K13) và mask qua
`decode_mask(..., width_px, height_px)` lấy từ khổ ảnh thật, nên lệch khổ là lỗi chứ không phải đệm ngầm; bắt
`(OSError, VisionError, ValueError)` → `DATASET_SAMPLE_INVALID`. `sample_id` chỉ vào `_log.warning` của `logging`
(`data.py:47`), **không** vào `reporter.log` — đúng BE-00 §9 (bảng không có khoá nhận nó), và
`test_train_happy_path:154-155` quét mọi `params` không chứa `/` hay `\`. `test/` không hề được đọc: fixture
`trained` cố ý đặt một PNG cụt trong `data_dir/test/s9999` mà lượt vẫn đạt. Cắt/đệm/lật/xoay hoàn toàn bằng numpy
(`np.full` + gán lát, `np.flip`, `np.rot90` — K28, không vòng theo điểm ảnh); đệm ảnh `PAD_VALUE=255` và nhãn 0
giống `stitch_mask` lúc suy luận. RNG `np.random.default_rng((seed, epoch, index))` — `test_dataset_crop_augment`
khẳng định cùng khoá → cùng mảnh, `test_dataset_crop_matches_to_model_input` khẳng định epoch khác và seed khác →
mảnh khác, và **đầu vào khớp `to_model_input` của B5-02** bằng cách nghịch đảo chuẩn hoá ImageNet rồi so lại.

**Vòng.** Không rẽ nhánh theo thiết bị: `torch.autocast(device, dtype=…, enabled=autocast_dtype is not None)` và
`torch.amp.GradScaler(device, enabled=use_scaler)` luôn được dựng (`loop.py:115-119`, `:205`),
`test_train_m04_precision` chứng minh cả hai dựng được trên torch CPU và tự tắt. `reporter.cancelled()` được hỏi
**ở đầu** `_optimizer_step`, trước cả `batch.to(device)` (`loop.py:110`) — `test_train_j04_cancel:269` khẳng định
`net.forwards == 1`, tức bước 2 dừng trước khi chạm model; và `metrics.guarded` hỏi trước **mỗi lát** đánh giá lẫn
mỗi lát kiểm tương đương (`export.py:111-112,121`), có `test_train_j04_cancel_during_validation` và
`test_export_and_check_cancelled_during_parity_raises`. Nhịp tim: một nhịp đầu mỗi epoch cộng mỗi
`heartbeat_every_s` theo `monotonic` **tiêm được** — `test_train_j07_heartbeat` cho `advance=31` → `[1,1,1]`,
`advance=1` → `[1]`. `loss` không hữu hạn → `TRAINING_LOSS_NOT_FINITE` **trước** `backward` (`:121-122`), thử bằng
`_TinyNet(broken=True)` chứ không vá `transformers`. Số đo: `step` tăng chặt trong từng split, `epoch ≥ 1`, `train`
làm tròn 6, `validation` làm tròn 4 và **cùng `step`** với bước cuối epoch (`test_train_m05_metrics_monotonic:177`);
`recorded_at_ms = int(clock.now().timestamp()*1000)` từ `Clock` tiêm được, không `time.time()`; `RecordingReporter`
giải lại **mọi** điểm qua `MetricPoint.model_validate` nên một điểm sai luật làm test đỏ ngay. Một chi tiết tinh:
`metrics.torch_run_tile` chuyển chính model sang `eval()`, nên `run()` bật lại `model.train()` ở **đầu mỗi** epoch
và `test_train_two_epochs_stay_in_train_mode` khẳng định `net.train_modes == [True]*4` — đúng loại lỗi mà epoch 2
mới lộ ra, và họ đã nghĩ tới.

**Xuất.** `copy.deepcopy(model).to("cpu", torch.float32).eval()` — bản gốc không bị đổi trạng thái; `_LogitsOnly`
cho đồ thị đúng một tensor ra; mẫu `(1,3,1024,1024)` khớp `SegformerOnnxSegmenter` (đòi đúng `[1,3,1024,1024]` →
`[1,2,256,256]`, `segformer.py:68-85`). Sau xuất: `out_dir` chỉ còn `model.onnx` (`:76-78`),
`onnx.load(..., load_external_data=False)` + `onnx.checker.check_model` bắt `(DecodeError, ValidationError)`, rồi
`has_external_data`. Tương đương đo trên `parity_images=2` mẫu `validation` đầu, so mask ONNX với mask torch,
`< parity_min_agreement` → `MODEL_EXPORT_MISMATCH` — `test_export_parity_mismatch` đảo dấu `decode_head.classifier`
của **bản sao** rồi xuất thật, nên nó kiểm chính phép so chứ không kiểm một mock. `TrainResult.metrics = {"iou": …}`
đo **bằng ONNX** (`export.py:121`), làm tròn 4. `out_dir` sạch ở **mọi** lối ra không thành công: `try`/`finally` +
cờ `succeeded` (`trainer.py:82-105`), không `except Exception`; `test_train_j04_cancel` và
`test_train_loss_not_finite` cố ý đặt `out_dir/tam.bin` trước rồi khẳng định `list(out_dir.iterdir()) == []`.

**Log.** Chỉ 5 khoá của BE-00 §9 được dùng, tham số đúng bảng, không đường tệp, không văn bản ngoại lệ;
`test_log_templates_render` chạy **mọi** lời gọi `reporter.log` của lượt chung qua `render_log` của B6-03a và đòi
khác `None` — đây là cách duy nhất chống trôi mẫu log, và họ đã làm.

**Luật mã.** 13 `type: ignore`, **tất cả** có mã trong ngoặc **và** lý do sau dấu gạch; 1 `noqa: S603` có lý do.
Không `pragma: no cover`, không `skip`/`xfail`, không `except Exception`/`BaseException`, không gán `os.environ`
trong mã nguồn, không nhập `packages.db`/`sqlalchemy`/`fastapi`/`ultralytics`/`apps.api`, không `send_task`, không
lấy khoá GPU. Docstring đủ ở **mọi** module/lớp/hàm, kể cả hàm lồng (`run_tile`, `wrapped`, `onnx_tile`,
`optimizer_cls`, `monotonic`) và mọi test — `audit.py --wt … --base main` cho `đạt` (docstring, suppression,
dòng > 120, skip/xfail, file ngoài whitelist). Ma trận [8]: **18/18** mục có test mang tên nhận ra được.
Không `conftest.py` lồng, không tệp cấu hình công cụ riêng, không nhập `packages.testing`.

## 5. Finding

Không P0, không P1.

### P2-1 · TEST · `apps/ml/training_segformer/tests/test_gpu.py:129-130`

`models_dir = Path(PINNED["mitB1"].name)` rồi `load_pretrained(models_dir.parent, "mitB1", PINNED)`.
`PinnedWeights.name` là **tên bản ghim**, không phải đường dẫn (`packages/ml_contracts/pinned.py:65,104` →
`name="mitB1"`), nên `Path("mitB1").parent == Path(".")` và `load_pretrained` đi tìm `./mitB1/model.safetensors`
**tương đối cwd của pytest** (gốc repo), không phải `ML_MODELS_DIR`.

*Kịch bản hỏng:* trên máy có CUDA và có bản ghim thật trong `ML_MODELS_DIR`, `pytest -m gpu
apps/ml/training_segformer` ném `PermanentError(MODEL_FORMAT_UNSUPPORTED)` ở `model.py:50` vì
`weights_path.is_file()` sai — nghiệm thu [11].4 **không thể chạy** nếu không sửa. Không cổng nào bắt được: test
mang marker `gpu`, `addopts` loại nó khỏi verify.

*Đề xuất:* `models_dir = Path(get_ml_settings().ml_models_dir)` (nhập lười trong test như `test_settings_models_dir`
đã làm) rồi `load_pretrained(models_dir, "mitB1", PINNED)`.

### P2-2 · TEST · `apps/ml/training_segformer/tests/test_gpu.py:119,127`

Docstring và khối [8] đòi **64 ảnh 1.600 × 1.200**, nhưng `write_split` khoá cứng `MICRO_WIDTH_PX=800`,
`MICRO_HEIGHT_PX=600` (`tests/support.py:27-28,84`) và không nhận tham số khổ. Trần VRAM vì vậy được đo trên
dataset bằng **một phần tư** diện tích yêu cầu, còn docstring khẳng định một con số mà mã không tạo ra (R-02:
docstring không được nói sai). Với `crop_px=512` thì mảnh cắt — chứ không phải khổ ảnh — quyết định VRAM, nên phép
đo vẫn *có nghĩa*; nhưng ở 800 × 600 mọi mảnh 512 đều **đệm** ở mép, tức phân bố khác ảnh thật và số giây/bước in
ra không so được với ENV §1. Đây là **lệch chưa khai** trong "Lệch khỏi prompt".

*Đề xuất:* thêm `width_px`/`height_px` vào `write_split` (mặc định giữ nguyên MICRO) rồi gọi với 1600 × 1200 trong
`test_gpu.py`; hoặc khai lệch kèm lý do nếu cố ý.

### P2-3 · MNT · `apps/ml/training_segformer/export.py:54-124` (`export_and_check`)

Hàm dài **71 dòng** (thân `:70-124` = 55 dòng), vượt R-08 "hàm ≤ 50 dòng". Nó làm sáu việc liền mạch: xuất, kiểm
tệp phụ, kiểm proto + dữ liệu ngoài, dựng phiên ONNX, đo tương đương, đo IoU. Cyclomatic ≈ 9 (còn trong trần), nên
vấn đề là độ dài chứ không phải độ rẽ nhánh.

*Đề xuất:* tách `_check_exported_format(onnx_path, out_dir) -> bytes` (`:76-86`) và
`_parity_agreement(onnx_tile, torch_tile, validation_dir, config) -> float` (`:106-116`); phần còn lại xuống ~25
dòng và mỗi mảnh test được riêng.

### P3-4 · TEST · `apps/ml/training_segformer/export.py:85-86`

Nhánh `if has_external_data(onnx_model): raise _unsupported()` **chưa bao giờ chạy** — `M/pre2.log:215` ghi
`export.py 98% … Missing 86` cùng 1 nhánh một phần. Lý do: test đặt tên cho đúng nhánh đó
(`test_export_rejects_external_data_without_extra_file`, `test_export.py:145`) dựng ONNX có initializer `EXTERNAL`
mà **không** kèm `weights.bin`, nên `onnx.checker.check_model` đã từ chối trước ở `:82` → `ValidationError` → `:84`.
Hệ quả: yêu cầu [6] "có tensor `data_location == EXTERNAL` → `MODEL_FORMAT_UNSUPPORTED`" chưa được chứng minh; nếu
`has_external_data` có lỗi thì không test nào thấy.

*Đề xuất:* hoặc dựng ca mà `checker` đi qua được, hoặc nhận rằng `:85-86` dư sau `normalize_onnx` + `checker` và bỏ
nó đi cho hết nhánh chết.

### P3-5 · MNT (R-02) · `apps/ml/training_segformer/tests/test_export.py:38-52` và `:148-161`

Hai hàm dựng ONNX giả gần như trùng từng dòng, khác **đúng một dòng** (`:51` ghi thêm `weights.bin`), và như P3-4
cho thấy, cả hai cuối cùng đi vào **cùng một nhánh** production. `grep` trước khi viết sẽ thấy.

*Đề xuất:* một helper `_external_data_onnx(path, *, with_companion: bool)` hoặc
`@pytest.mark.parametrize("with_companion", [True, False])`.

### P3-6 · TEST · `apps/ml/training_segformer/tests/test_trainer.py:383-393`

`test_settings_models_dir` gọi `trainer._settings_models_dir()` → `get_ml_settings()` và gọi
`reset_ml_settings_cache()` hai lần. `chung.md` ("Dữ kiện đã tra") cấm đúng việc này: *"Test luôn tiêm `models_dir`
— không gọi `get_ml_settings()` (bài học B6-03b: cache cài đặt rò giữa module dưới xdist)"*. Rủi ro có hạn vì
`finally` trả cache về trạng thái sạch, nhưng đây là **lệch chưa khai** khỏi hợp đồng việc, và là đúng cái bẫy đã
làm B6-03b mất một lượt cổng. Test cũng chạm tên riêng tư (`trainer._settings_models_dir`).

*Đề xuất:* tiêm qua `monkeypatch.setattr(trainer, "_settings_models_dir", lambda: tmp_path)` và khẳng định `train`
dùng nó — không chạm cache dùng chung; hoặc khai lệch kèm lý do.

### P3-7 · MNT · `apps/ml/training_segformer/tests/test_trainer.py:248-249`

Hai `# type: ignore[arg-type]` **tự gây ra**: `_fake_monotonic` khai trả `-> "object"` (`:101`) thay vì
`Callable[[], float]`, và `train_model(optimizer_cls: type[AdamW])` (`loop.py:178`) hẹp hơn thứ thực sự được truyền
(một factory). Sửa hai annotation là mất cả hai suppression — tinh thần K24 là suppression phải *không tránh được*.

*Đề xuất:* `_fake_monotonic(...) -> Callable[[], float]`; `optimizer_cls: Callable[..., AdamW] = AdamW`.

### P3-8 · MNT · `apps/ml/training_segformer/tests/test_model.py:98`

`_FORBIDDEN_NAMES = frozenset({"load", "Unpickler"})` khai rồi **không dùng ở đâu** — hằng chết. Nó còn tố cáo một
lỗ: phép quét AST chỉ bắt `torch.load` khi gốc là `ast.Name` tên `torch` (`:142-145`), nên `from torch import load`
hay `import torch as t; t.load(...)` lọt qua cổng K12.

*Đề xuất:* dùng `_FORBIDDEN_NAMES` để chặn `ImportFrom(module="torch", names=["load"])` và `ast.Name` tên
`Unpickler`, hoặc bỏ hằng.

### P3-9 · PERF · `apps/ml/training_segformer/loop.py:92`

`generator=torch.Generator().manual_seed(self.spec.seed)` dựng lại với **cùng** seed mỗi epoch, nên thứ tự lô lặp y
nguyên qua các epoch (chỉ RNG mảnh cắt có `epoch`). Tái lập (M06) vẫn đúng; chỉ là đa dạng hoá kém hơn mức
`shuffle=True` ngụ ý. `manual_seed(self.spec.seed + epoch)` không tốn gì và vẫn tái lập.

### P3-10 · API · `apps/ml/training_segformer/trainer.py:48-61`

Khối [2] ghi `SegformerTrainer(*, models_dir=None, pinned=PINNED, config=SegformerTrainConfig(), clock=SystemClock(),
monotonic=time.monotonic)` — **keyword-only** — và `family = "wallSegmentation"` là thuộc tính cố định. Thực tế là
`@dataclass(frozen=True, slots=True)` **không** `kw_only=True`, thứ tự trường khác prompt (`config` trước
`models_dir`), và `family` thành một **trường tiêm được**: `SegformerTrainer(family="openingAndFurnitureDetection")`
dựng được và sẽ từ chối mọi spec. Thực tế vô hại (mọi chỗ gọi đều dùng keyword; `discover_trainers` lấy `TRAINER`),
nhưng là lệch hợp đồng chưa khai. `Trainer.family` của B5-01 là `@property`, nên một trường đọc-ghi vẫn thoả
protocol về cấu trúc.

*Đề xuất:* `@dataclass(frozen=True, slots=True, kw_only=True)` và chuyển `family` thành `ClassVar` hay `@property`.

### Tái hiện độc lập (một container `run.sh shell`, sau khi cổng đã kết thúc; `docker ps --filter name=verify-run` = 0 trước khi chạy)

```
P2-1  PINNED['mitB1'].name = 'mitB1'
P2-1  Path(name).parent    = PosixPath('.')  <- models_dir mà test_gpu truyền
P2-1  đường tìm trọng số   = mitB1/model.safetensors
P2-1  tệp đó tồn tại?      = False
P3-4  export.py:85 = 'if has_external_data(onnx_model):'
P3-4  export.py:86 = 'raise _unsupported()'
P2-3  export_and_check: dòng 54-124 = 71 dòng
```

P2-1 và P2-3 vì vậy là số đo, không phải suy luận; P3-4 khớp `Missing 86` của báo cáo độ phủ.

## 6. Nợ nên ghi (điều phối ghi `DEBT.md`, phiên review không sửa)

- **NO-xxx** — `test_gpu.py` không chạy được như đang viết: `models_dir` lấy từ `PinnedWeights.name` (P2-1) và
  dataset 800 × 600 thay 1600 × 1200 (P2-2). Nghiệm thu [11].4 vì vậy là `chưa chạy` **vừa** vì thiếu GPU **vừa** vì
  lỗi mã test. Chủ: B6-04a.
- **NO-xxx** — `export.py:85-86` nhánh `has_external_data` chết sau `onnx.checker` (P3-4); quyết định giữ-kèm-test
  hay bỏ. Chủ: B6-04a.
- `# ponytail:` `WallSegDataset` giữ cả split trong RAM (đã khai trong `bao-cao-B6-04a.md`) — giữ nguyên, có trần
  rõ ràng và lối nâng cấp.

## 7. Chấm điểm (RULE.md §5)

| Miền | Trọng số | Điểm | × |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 4 (P3-9) | 0,40 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 4 (P3-10) | 0,40 |
| TEST – Kiểm thử | 7% | 3 (P2-1, P2-2) | 0,21 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 3 (P2-3) | 0,09 |
| **Tổng** | **100%** | | **4,60 / 5** |

Không P0/P1, điểm ≥ 4,0 → **APPROVE**.

SEC được 5 vì ba lớp phòng thủ khép kín và đều có test *chứng minh bằng hành vi* chứ không bằng mã lỗi: checksum
trước `from_pretrained` (vá thành hàm ném), chỉ safetensors + `local_files_only` (chặn `socket.socket.connect` suốt
lượt train), và trần điểm ảnh + giải lỗi → mã. LOG được 5 vì những chỗ dễ sai nhất của một vòng huấn luyện —
`step` tăng chặt xuyên epoch, `validation` dính `step` cuối, `model.train()` sau khi `torch_run_tile` đã `eval()` —
đều có test riêng nhắm đúng vào chúng.

## 8. Kết luận

**APPROVE (4,60/5)** — được merge. Ba P2 đều nằm trong tệp test; P2-1 và P2-2 khiến nghiệm thu GPU [11].4 không
chạy được nên cần một FIX nhỏ (hai dòng ở `test_gpu.py` + một tham số ở `write_split`), nhưng chúng không chặn
`main`: tệp mang marker `gpu`, bị `addopts` loại khỏi mọi lượt verify, và không đường chạy production nào nhập nó.
P2-3 là độ dài hàm, sửa bằng tách hai helper. Mã production — bất biến nhập, thứ tự kiểm rẻ-trước-đắt, huỷ, dọn
`out_dir`, hợp đồng ONNX với B5-02 — tôi không tìm được lỗi nào.
