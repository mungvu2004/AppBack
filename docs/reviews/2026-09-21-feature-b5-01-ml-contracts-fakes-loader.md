# Review merge feature/b5-01-ml-contracts-fakes-loader → main

- Ngày: 2026-09-21 · Reviewer: phiên /merge-review — sub-agent độc lập (không mang ngữ cảnh tác giả; mọi khẳng định trong commit, `changes/B5-01.md` và báo cáo tác giả đều tự kiểm lại) · Commit đầu nhánh: `4395ebbf33cc` (gốc `5bb39de`, 1 commit `4395ebb` B5-01). `main` đi thêm `ef69c60`, chỉ thêm file phán quyết B1-01 (`docs/reviews/…b1-01…md`). `git merge-tree --write-tree main HEAD` thoát 0, không xung đột.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trên worktree sạch; log `verify-b5-01.log` trong scratchpad của phiên): `1813 passed, 10 skipped, 1 deselected` trong 256,85 s. 10 skip đều là `apps/api/core/tests/test_common.py` (tập tham số rỗng, có từ B0-06), đúng ngoại lệ BE-00 §12. Test bị bỏ chọn là test `perf` duy nhất, chạy ở bước 5b.
- Độ phủ (in từ `tools.coverage_gate`, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,45 %** · nhánh **97,56 %**
  - `apps/ml`: **100,00 %** / **100,00 %**
  - `apps/ml/runtime`: dòng **99,48 %** · nhánh **97,97 %**
  - `packages/ml_contracts`: dòng **99,91 %** · nhánh **99,58 %**
  - tập file bị chạm: dòng **99,76 %** · nhánh **98,96 %**

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt (277 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (247 file) |
| 4 | `lint-imports` | đạt (9 hợp đồng giữ, 0 vỡ; có hợp đồng `apps.ml` không nhập `packages.db`, `sqlalchemy`…) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (1 test `perf`: `test_render_plan_performance`) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt. AppFront @ `9cf0b0b`. H3/H4/H5 "không áp dụng" hợp lệ (B1-02, B3-05, B4-01 chưa có `changes/*.md`) |
| 8 | openapi | đạt (3 877 byte) |

Các số cổng và độ phủ trùng đúng báo cáo tác giả.

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B5-01.md` tồn tại, 3–10 dòng | đạt (7 dòng) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt: `feat(ml): add ml contracts, synthetic fakes and onnx loader` (59 ký tự) |
| Trailer đọc được (R-36b) | đạt. `%(trailers:key=Prompt,valueonly)` → `B5-01`; `Co-Authored-By` cùng khối |
| Đụng file cấm (`docs/charter/*`, `openapi.json`, `APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**`, gói khác) | không. 46 file: 45 file nằm trong cột `so_huu` (`packages/ml_contracts/**`, `apps/ml/runtime/**`, `apps/ml/celery_main.py`, `changes/B5-01.md`), cộng `DEBT.md` (+4 dòng NO-060..063, R-34) |
| `pragma` / `type: ignore` trần / `noqa` trần / `skip` / `xfail` mới / hạ ngưỡng | không. Mọi `type: ignore[...]` đều có mã và lý do (stub thiếu của `onnxruntime`, `protobuf`, `ultralytics`, `rapidocr`; cố ý truyền sai kiểu trong test). Mọi `noqa` đều có mã và lý do (`S311` cho `random.Random` tất định/jitter, `S310` cho URL ghim, `S603` cho tiến trình con). `print` chỉ nằm trong chuỗi mã của tiến trình con |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không |

Không điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (Python 3.12.12, venv của worktree), bản sao `/tmp/w`, **`--network none`** (trừ P1 dưới). Không chạm worktree. Script probe nằm trong scratchpad: `probe_fn_attr.py`, `probe_fn_graph_attr.py`, `probe_misc.py`, `probe_pinned_load.py`.

- **P1 — SHA ghim là số đo thật.**
  - `sha256sum` trên `/work/b5-01-models/*` và trên ONNX nhận dạng trong wheel `rapidocr_onnxruntime` đã khoá: cả 11 giá trị trùng từng ký tự với `PINNED`. Gồm `yolov8n.pt`/`yolov8s.pt`, `model.safetensors` và `config.json` của `mitB0`/`mitB1`, `rapidocrRec`, cùng hai ONNX `yolov8n`/`yolov8s` đã xuất.
  - Để không chỉ tin tệp tác giả để lại, tải lại **từ đúng URL ghim** trên máy chủ (không phải trong test):
    - `yolov8n.pt` (GitHub `assets` tag `v8.3.0`) → `f59b3d83…3b36`, 6 549 796 byte;
    - `mit-b0/…/model.safetensors` (commit `25ce79d`) → `3e5ad9cd…798a`;
    - `mit-b0/…/config.json` → `e2378ac7…ff91`;
    - `mit-b1/…/config.json` (commit `44575a0`) → `8fd62155…6eb1`.
  - Bốn giá trị này **khớp** `PINNED`. `yolov8s.pt` và safetensors của `mitB1` chỉ đối chiếu được với tệp trong volume.
- **P2 — tải ghim và xuất ghim chạy ngoại tuyến, hai lượt cùng SHA.** Hai thư mục chép riêng, hai tiến trình. Mỗi lượt: `python -m packages.ml_contracts.pinned fetch --dest` thoát 0 (có sẵn đúng SHA nên không mở mạng), rồi `python -m apps.ml.runtime.export_pinned --dest`. Cả hai lượt ra `yolov8n 1e252b73…`, `yolov8s c1a12672…`, `rapidocrRec 48fc40f2…`, trùng `onnx_sha256` ghim. `export_all` so digest với ghim nên không thể qua nếu lệch.
- **P3 — bản ghim thật nạp được.** `load_onnx` dạng ghim với `models_dir=/work/b5-01-models`: nạp được cả ba (`images (1,3,640,640)`, rec `x`), không dữ liệu ngoài. Ba ONNX này **cũng** qua luật cấu trúc dạng storage (chỉ miền chuẩn), nên ONNX YOLO do `export_yolo` sinh cho B6-04b nạp được ở dạng storage.
- **P4 — luật "ONNX không tin" bị vượt qua giá trị mặc định của thuộc tính hàm cục bộ** (`FunctionProto.attribute_proto`). Xem finding #1.
  - Hàm `F` có thuộc tính `body` kiểu GRAPH, giá trị mặc định là một đồ thị chứa `Loop`. Trong thân hàm, node `If` dùng `then_branch`/`else_branch` = `ref_attr_name: body`; đồ thị chính gọi `F` mà không truyền thuộc tính.
  - Kết quả:
    - `iter_nodes(model)` không thấy `Loop`;
    - `iter_nodes(inline_local_functions(model))` không thấy `Loop`;
    - `_structure_allowed` → `True`;
    - `_verify` dạng storage **không từ chối**;
    - ORT nạp được và **chạy Loop**: 5 vòng → `y = 6`; 10^5 vòng 0,08 s; 10^6 vòng 0,83 s (tuyến tính, ≈ 0,83 µs/vòng).
  - Cùng model với trip count `2^63 − 1` chỉ **578 byte** và vẫn qua `_verify`.
  - Cùng đường này, `TensorProto` có `data_location = EXTERNAL` đặt ở `attribute_proto` làm `has_external_data` trả `False` (đã thử ba kiểu `location`: tương đối, tuyệt đối, `../`), `_verify` cho qua. Riêng ORT 1.30 tự chặn (`model_path must not be empty`), nên lỗi này chỉ còn thành `MODEL_FORMAT_UNSUPPORTED` qua `ORT_ERRORS`.
- **P5 — ORT với model dị dạng qua `_structure_allowed` + `_session`.** Tám model dị dạng, gồm `ir_version=99`, opset 99, đầu vào treo, lệch kiểu, hai node cùng đầu ra, thiếu đầu ra, hàm sai số đối, miền hàm không khai opset, `ref_attr` không tồn tại: đều ra `MODEL_FORMAT_UNSUPPORTED`. Không lớp ngoại lệ nào lọt ngoài `ORT_ERRORS`. Hàm trùng tên bị luật cấu trúc từ chối. `onnxruntime_pybind11_state` 1.30 có 15 lớp lỗi; `ORT_ERRORS` khai 12, thiếu `DeviceReset`, `ModelLoaded`, `ModelRequiresCompilation` (Nit #7).
- **P6 — `decode_mask` toàn bộ lọc Paeth** (nhánh chậm có chủ ý, docstring nêu ngưỡng theo R-05): 4000×3000 0,7 s; 8000×5000 (sát trần 40 MP) **2,5 s** cho tệp 10,6 KB. Đúng mức docstring hứa ("vài giây"); không ghi finding.
- **P7 — bộ giả với dấu hợp lệ trên trang nhỏ.** Ảnh trắng 300×300 mang dấu có CRC đúng cho `(seed=1, 300, 300)`: `FakeWallSegmenter().segment` ném `ValueError("trang 300x300 quá nhỏ…")` thay vì trả rỗng (Nit #8).
- **P8 — AST trên 24 file sản phẩm.**
  - Không hàm nào > 50 dòng.
  - Thiếu docstring: `_Keeper.__init__`, `_Sessions.__init__`, `FetchError.__init__`, closure `check` trong `_id_of` (P3 #4). Không tính các stub `...` của `Protocol` trong `ports.py` và `Readable.read`, cũng như stub `@overload` ở các review trước.
  - Dòng logic (token mã, bỏ docstring, comment, dòng trống): **2 050** sản phẩm + **2 460** test.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | SEC-05 · R-17 · BE-00 §9 | **Luật "ONNX không tin" dạng storage bị vượt qua bằng `FunctionProto.attribute_proto`.** `iter_nodes` chỉ duyệt `function.node`, `graph.node` và đồ thị con trong `node.attribute`; `iter_tensors` cũng vậy. Không hàm nào đọc giá trị mặc định thuộc tính của hàm cục bộ (`attribute_proto`). `_structure_allowed` dựa vào `onnx.inliner.inline_local_functions`, mà bộ inline **không** thay giá trị mặc định vào (P4: sau inline vẫn không thấy `Loop`). ORT thì có thay, nên đồ thị ẩn vẫn được nạp và chạy. P4 đo được: một model 578 byte, trip count `2^63 − 1`, qua `_verify` dạng storage, ORT nạp được, và Loop chạy tuyến tính ≈ 0,83 µs/vòng, tức là không bao giờ xong. Mỗi lượt pipeline dùng phiên bản model đó giữ một luồng worker `ml` tới trần giờ cứng. Cùng lỗ hổng cho lọt op miền `com.microsoft` (luật miền) và tensor `EXTERNAL` (luật dữ liệu ngoài; phần này ORT 1.30 tự chặn). BE-00 §9 đòi từ chối mọi `op_type ∈ {Loop, Scan}`, mọi miền ∉ {`""`, `ai.onnx`} và duyệt mọi `TensorProto` "(… thuộc tính tensor, đồ thị con, `model.functions`)"; prompt [6] bước 5 lấy đúng luật này. Test `test_load_onnx_m03_control_flow` ghi "`Loop`/`Scan` ở mọi độ sâu" nhưng không có ca này. Người tải model storage là admin (N26) hay B6-04b; hiến chương vẫn xếp trọng số tải lên vào mức **không tin**. Xếp P1 như mức mặc định của SEC-05: vượt kiểm tra ở biên tin cậy, hệ quả là treo worker (DoS), không phải RCE hay mất dữ liệu | `apps/ml/runtime/loader.py:87-95` (`iter_nodes`), `:108-121` (`iter_tensors`), `:132-138` (`_structure_allowed`); test thiếu ở `apps/ml/runtime/tests/test_loader.py:283-298` | Fail-closed, đủ nhỏ. (a) `iter_nodes`/`iter_graphs`/`iter_tensors` duyệt thêm `function.attribute_proto` (`g`, `graphs`, `t`, `tensors`, `sparse_tensor(s)`), và `_structure_allowed` kiểm cả `iter_nodes(model)` gốc chứ không chỉ bản đã inline. Hoặc (b) đơn giản hơn: dạng storage có `attribute_proto` kiểu GRAPH(S)/TENSOR(S)/SPARSE_TENSOR(S) thì từ chối luôn (torch và ultralytics không sinh chúng; P3 cho thấy ONNX YOLO xuất ra vẫn qua). Thêm ca vào `test_load_onnx_m03_control_flow` (Loop ẩn trong mặc định GRAPH, op `com.microsoft` ẩn) và `test_load_onnx_m03_external_data` / `test_has_external_data_walks_every_tensor` (tensor `EXTERNAL` trong `attribute_proto`). Các ca này phải đỏ trên `4395ebb`, xanh sau khi sửa |
| 2 | P2 | MNT-05 | Nhánh thêm ≈ **2 050** dòng logic sản phẩm và ≈ 2 460 dòng test, gấp 5 lần trần 400. **Không đáng tách:** một prompt, `apps/ml/runtime` nhập hợp đồng của `packages/ml_contracts` (payload, artifact, ghim). Tách ra là đưa vào `main` một nửa hợp đồng [2]/[10] | toàn nhánh | Chỉ ghi nhận; ghi `DEBT.md` dạng `➖` như `NO-039`, `NO-045` |
| 3 | P3 | SEC-08 · K12 | `export_yolo` băm `pt_path` rồi mới **chép lại chính đường đó** sang thư mục tạm và đưa bản chép cho `ultralytics` (giải pickle). Giữa lúc băm và lúc chép, tệp có thể bị thay (TOCTOU), nên bản được giải không phải bản đã so SHA. Rủi ro thấp: đường này chỉ chạy lúc build và ở B6-04b trên tệp của chính mình | `apps/ml/runtime/export_yolo.py:55-59` | Chép trước, băm **bản chép** (`file_sha256(work_pt)`), rồi mới nhập `ultralytics`. Không tốn thêm gì, và SHA đúng là của byte được giải |
| 4 | P3 | R-01 | Bốn hàm không có docstring: `_Keeper.__init__`, `_Sessions.__init__`, `FetchError.__init__`, closure `check` của `_id_of` | `apps/ml/runtime/gpu.py:56`, `apps/ml/runtime/loader.py:47`, `packages/ml_contracts/pinned.py:149`, `packages/ml_contracts/payloads.py:60` | Mỗi cái một câu (vd `FetchError.__init__`: "`exit_code` là mã thoát CLI mà `main` trả") |
| 5 | P3 | R-07 · MNT-03 | Ba bản chép của cùng một gốc Pydantic (`extra="forbid"`, `frozen=True`): `_Frozen` hai lần và `_Artifact` | `packages/ml_contracts/payloads.py:79`, `datasets.py:31`, `artifacts.py:72` | Một lớp gốc duy nhất trong gói (vd `_png.py` hay một `_base.py` riêng), ba module cùng nhập |
| 6 | Nit | TEST-02 | Docstring `test_load_onnx_m03_control_flow` nói "`Loop`/`Scan` ở mọi độ sâu", trong khi thiếu ca `attribute_proto` (#1) | `apps/ml/runtime/tests/test_loader.py:284` | Sửa cùng #1 |
| 7 | Nit | LOG-04 | `ORT_ERRORS` khai 12/15 lớp lỗi thật của ORT 1.30, thiếu `DeviceReset`, `ModelLoaded`, `ModelRequiresCompilation`. B5-02…B5-04 bắt đúng bộ này, lỗi lọt ra sẽ thành `INTERNAL` thay vì `MODEL_FORMAT_UNSUPPORTED`. Hôm nay không tới được: CPU, và `EPContext` thuộc miền `com.microsoft` bị luật miền chặn ở dạng storage | `apps/ml/runtime/errors.py:40-53` | Thêm ba lớp; hoặc dựng tuple từ mọi lớp con `Exception` của `onnxruntime_pybind11_state`, kèm test so với danh sách thật |
| 8 | Nit | LOG-02 · M01 | Bộ giả gặp ảnh có dấu CRC đúng mà khổ nhỏ hơn bản vẽ tối thiểu (P7) thì ném `ValueError` (task ra `INTERNAL`) thay vì trả rỗng như [6] "còn lại → rỗng". CRC không bí mật nên ai cũng dựng được dấu này. Chỉ ở `ML_BACKEND=fake` (dev/test; `celery_main` cấm ở staging/production) | `packages/ml_contracts/fakes.py:25-31` | `answer_for`: bắt `ValueError` của `_plan` → `None`; hoặc `read_marker` từ chối khổ mà `render_plan` không vẽ được |

**P0: 0 · P1: 1 · P2: 1 · P3: 3 · Nit: 3**

## Những chỗ đã soi kỹ và **đạt**

- **Thứ tự `load_onnx` (M02, M03, K12).** Thứ tự đúng 1–6:
  - cổ điển → `ValueError`; cache LRU 3 phiên theo checksum, có `threading.Lock`;
  - đọc ≤ 512 MiB: ghim từ `models_dir/<pinned_name>.onnx` (tên chỉ có thể ∈ `PINNED`, không path traversal); storage `stat` rồi luồng đọc, dừng ngay khi vượt, kể cả khi kho khai sai cỡ (test sửa `.meta.json`);
  - SHA **tự tính** so với cả `ref.checksum_sha256` lẫn `onnx_sha256` ghim;
  - byte đầu `0x08`, nên pickle, zip, safetensors, rỗng có checksum **khớp** vẫn bị chặn, và test vá `pickle.load(s)`/`torch.load` để ném;
  - giải protobuf (`DecodeError`), luật dữ liệu ngoài và luật cấu trúc (ghim miễn luật cấu trúc, **không** miễn dữ liệu ngoài; lệch #7 an toàn hơn);
  - `InferenceSession` CPU, `ML_ORT_THREADS`, lỗi thật của ORT → `MODEL_FORMAT_UNSUPPORTED`.

  Việc CPU và đĩa (băm, giải, dựng phiên, đọc tệp) đều trong `asyncio.to_thread` (R-23). Ngoài lỗ #1, luật cấu trúc bắt đúng `Loop`/`Scan` trong đồ thị chính, trong `If`, trong thân hàm, cả khi hàm gọi vòng.
- **PNG viết tay (K13).**
  - Chữ ký; CRC mọi chunk; loại chunk 4 chữ cái; độ dài ≤ 2^31−1 và không vượt tệp; IHDR 13 byte là chunk đầu, phương pháp nén/lọc 0; IHDR phải **đúng** khổ người gọi hẹn.
  - Chỉ nhận xám 1 bit không đan xen. Chunk tới hạn lạ (gồm `PLTE`, `IHDR` thứ hai) → từ chối. IDAT phải liền nhau; rác sau `IEND` → từ chối.
  - `decompressobj` với `max_length = expected − len(out) + 1`: đã soát phần `unconsumed_tail`, chỉ khác rỗng khi `out` vượt trần, và khi đó bị từ chối ngay. Test bom zip 50 MB → dừng ở khổ 10×10. Đủ 5 bộ lọc, có Pillow làm bộ giải đối chứng.
  - Trang vào `run_step` kiểm IHDR `w × h` so với trần và khổ payload **trước** `cv2.imdecode`.
- **`run_step` (J01–J08).**
  - `prepare` chạy trên vòng sự kiện trước khi đọc trang. Trang ≤ 256 MiB. `NOT_FOUND` → `PIPELINE_ARTIFACT_MISSING`.
  - `fn` chạy trong luồng. Tên artifact ⊄ `STEP_ARTIFACTS` → `ValueError`, không gửi gì.
  - `put` ghi đè có `content_type`, `max_bytes` 64 MiB, và **ghi xong mới gửi**: J01 kiểm artifact đã nằm trong kho ngay tại lượt gọi `send`. Khoá gửi đi đã sắp.
  - `model_version_id` có ở mọi đường, cả `failed`. `PermanentError` ở mọi bước → một `failed` cùng mã, rồi trả bình thường.
  - Kho 503 và broker 503 → ném lại cho `define_task` thử lại. J02_broker: đúng một `step_done` sau lượt thử lại. J08: thông điệp độc mang cùng `run_id` mà không sinh `failed` nào.
  - J-test chạy worker Celery thật trên Redis thật, đọc `pipeline.cpu` bằng `LRANGE`, đúng BE-00 §7 "Test task".
- **Khoá GPU (M04, CON-05).**
  - Luồng daemon có `asyncio.Runner` riêng, client `safe_redis()` dựng mới **trong** vòng đó (`safe_redis` dựng client mới mỗi lần gọi, có timeout), nên không cần lệch "tự dựng client DB 2".
  - Lấy khoá: 1 s ± 20 % tới `wait_s` → `TransientError`. Gia hạn mỗi `renew_every_ms`. `renew` → `False` thì `lost`; Redis lỗi quá `ttl − renew` thì `lost`. Mọi lối thoát bất thường của luồng giữ khoá cũng bật `lost` (fail-closed).
  - Thoát khối: dừng luồng, trả khoá có token rào, `join(5)`; Redis chết lúc trả khoá thì không che lỗi thân khối.
  - Test trên Redis thật và Redis tạm có thể tắt (`ephemeral_broker`), đúng `ttl=600`, `renew=150`.
- **Bản ghim, `fetch`, xuất.**
  - URL `https://` ghim theo tag hay commit, SHA là số đo thật (P1). `fetch` luồng vào `.part`, băm khi đọc, trần 600 MiB, lệch → xoá, thoát 2; mạng/IO → thoát 3, `.part` luôn bị xoá; có sẵn đúng SHA thì không mở mạng; `source_url` rỗng → bỏ qua. `UNPINNED` → thoát 2 trước khi tải gì.
  - `pinned`, `families` chỉ dùng thư viện chuẩn (test tiến trình mới). `export_yolo` so SHA **trước** khi nhập `ultralytics` (test tiến trình mới: `ultralytics` không có trong `sys.modules`), cờ ngoại tuyến và thư mục cấu hình tạm có trả lại.
  - `normalize_onnx` bỏ `doc_string`, `producer_version`, `metadata_props`. `rapidocrRec` chép nguyên, giữ `character`. `export_pinned` tái lập ngoại tuyến (P2).
- **Payload, artifact, dataset.**
  - Mọi luật chéo trường ở [6] có một ca hỏng và một ca đạt. `ModelRef` đúng một dạng. `InferStepPayload`: trang và prefix cùng lượt tải lên, prefix đúng `runs/{run_id}/{step}/`. `StepResultPayload`: `failed` ⇔ mã, không khoá; khoá sắp ≤ 8. M05 tăng ngặt theo split.
  - Log huấn luyện: mẫu khoá BE-00 §9, ≤ 16 tham số in được. `*_from_json` chặn > 16 MiB **trước** khi parse. Manifest sắp, không trùng, trần dòng và byte. `split_for` băm SHA-256 theo nhóm.
  - Luật khoá object chép có test so với `packages.storage.keys.check_key` trên 12 mẫu (NO-060).
- **Bản vẽ tổng hợp và bộ giả (M01, M06).**
  - Một `random.Random(seed)`, không `numpy.random`. Tất định giữa hai tiến trình (so cả PNG). `EVAL_SET_SHA256` tính lại được.
  - Mặt nạ = tô lại `walls` trừ khe cửa đi, lệch 0 px; cửa sổ thuộc mặt nạ. Hộp chữ khớp mực 0 px. Luật hình học đúng: bề dày, 2–6 phòng, 1–3 đồ, ≥ 300 mm tới tim tường vuông góc. Hàng chữ đúng 3×/6× cao chữ. `infer_scale` của B3-01 suy lại tỉ lệ lệch ≤ 1 %. ≥ 5 % mực ngoài hộp trên 40 seed. 40 trang < 8 s (`perf`, 5b). OCR thật của wheel ≥ 80 % (test đạt trong cổng).
  - Mảng trả ra chỉ đọc (`setflags(write=False)`, có test), nên LRU dùng chung an toàn. Ảnh cắt 10 px → rỗng.
- **Ranh giới (R-28, [9]).**
  - `ml_contracts` nhập được mọi module khi `torch`, `onnxruntime`, `messaging`, `storage`, `apps` bị chặn (tiến trình mới).
  - `apps/ml/runtime` (trừ `export*.py`) không kéo `torch`, `transformers`, `ultralytics`, `packages.db`, `apps.api`, `apps.worker`. `torch` chỉ nhập trong hàm (`device.py`, `export.py`).
  - Test AST M03 bắt đủ `torch.load`, `pickle`, `joblib`, `ultralytics` ngoài hai chỗ cho phép, và có ca dương chứng minh bộ quét không rỗng giả. `lint-imports` đạt.
- **K23, K24, test.**
  - Redis thật cho khoá GPU và J-case, kho đĩa thật `local_storage`. Kho hỏng của J02 là đúng cách prompt chỉ định (vá `infer_context`).
  - Không `skip`/`xfail`, không marker `gpu`. `except Exception` chỉ có trong script probe của reviewer, không có trong diff.
  - Chờ bằng vòng hỏi có hạn, không bằng một nhịp ngủ cố định; ngoại lệ là `test_gpu_slot_m04_renew`, ngủ 2,5 TTL có chủ ý.
- **`celery_main`.** `create_celery("ml")`, dò `apps.ml.*.tasks` một cấp. `worker_init` kiểm `noeviction` trên Redis thật và cấm `ML_BACKEND=fake` ở staging/production. Test chạy tiến trình mới cho bốn tổ hợp.

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | `export_onnx` dùng thẳng `dynamo=False` | **Đứng được.** Hợp đồng là opset 17 tất định. Docstring nêu lý do (bộ xuất dynamo của torch 2.14 luôn ra opset 18) theo R-05. Test hai tiến trình cùng SHA, opset 17, không metadata |
| 2 | `render_plan` từ chối trang nhỏ hơn ~800×600 ("quá nhỏ") dù cạnh ≥ 256 | **Đứng được.** Fail-closed, lỗi rõ ràng, có test `(640, 480)`. Luật hình học của [6] không vẽ vừa trang nhỏ hơn |
| 3 | Tổng kiểm 16 bit = CRC-32 của `(seed, rộng, cao)` | **Đứng được.** Đây là cách hiện thực luật "dấu đúng **và** khổ khớp" ngay từ dấu. Tác dụng phụ ở Nit #8 |
| 4 | Test OCR gọi `RapidOCR()` mặc định với `use_cls=False` | **Đứng được, kèm ràng buộc bàn giao.** Không hạ ngưỡng 80 %, chỉ tắt bộ phân loại 180° vốn vô ích cho chữ thẳng trục. Có số đo 67 so với 114 trên 122. Đã chuyển thành `NO-063` cho B5-04 |
| 5 | `discover_trainers` đọc `TRAINER` | **Đứng được.** Prompt không đặt tên thuộc tính. Thiếu, họ lạ hay trùng họ → `RuntimeError` |
| 6 | `detect()`/`read()` trả tuple | **Đứng được.** Bất biến, và LRU dùng chung được |
| 7 | Luật dữ liệu ngoài áp cả cho bản ghim | **Đứng được.** An toàn hơn; BE-00 §9 chỉ miễn luật cấu trúc. P3: ba bản ghim thật vẫn qua |
| 8 | Trang > 256 MiB → `IMAGE_TOO_LARGE` | **Đứng được.** Prompt không nêu mã cho trường hợp này |
| 9 | Luật chặt hơn: `artifact_keys` tăng ngặt, khoá tham số log khớp mẫu, `weights_key` của `succeeded` dưới `ml/models/` | **Đứng được.** Ít phạm vi hơn, an toàn hơn (BE-00 §13.2) |
| 10 | SegFormer ghim theo commit PR safetensors của HF; license `other` | **Đứng được.** Commit SHA là bất biến. Tự tải lại cho đúng SHA (P1) |

**Lệch tác giả không khai:** `ORT_ERRORS` thiếu 3 lớp so với "lớp ngoại lệ thật" của prompt [2] (Nit #7). Bộ giả ném thay vì trả rỗng với dấu hợp lệ trên trang nhỏ (Nit #8). Luật "ONNX không tin" thiếu phần `attribute_proto` (#1) không phải lệch có chủ ý mà là lỗi. `test_export_onnx_deterministic` không tự khứ hồi qua `load_onnx` như [8] ghi, nhưng `test_load_onnx_m03_exported_storage` đã phủ đúng đường đó, nên không ghi finding.

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Mọi nợ tác giả nêu đều có dòng | đạt. `NO-060` (P3, B0-04), `NO-061` (P2, người điều phối · B6-01), `NO-062` (P2, B0-08), `NO-063` (Nit, B5-04): đủ chín cột, nguyên nhân gốc, chủ đúng. Mức hợp lý: `NO-061`/`NO-062` là việc thật mà thiếu thì bước ghim hỏng `MODEL_NOT_FOUND`/thoát 2, nhưng đều thuộc chủ khác và không chặn B5-01 |
| Nợ P0/P1 còn `⬜`/`🔧` | không có trên sổ. #1 là P1 **mới** do review chỉ ra → phải **sửa** trước merge, không ghi nợ thay cho sửa (R-38) |
| Nợ do review này chỉ ra đã có dòng | **chưa** |

Dòng đề xuất (lấy id `NO-<nnn>` kế tiếp còn trống lúc ghi; phiên này **không** tự ghi `DEBT.md`):

- `| ➖ | NO-<nnn> | 2026-09-21 | 2026-09-21 | Nhánh feature/b5-01-ml-contracts-fakes-loader vượt trần 400 dòng logic của MNT-05 (≈ 2 050 dòng sản phẩm, ≈ 2 460 dòng test) | Một prompt giao hai gói móc vào nhau: apps/ml/runtime nhập payload, artifact, ghim của packages/ml_contracts | B5-01 | P2 | Chấp nhận như NO-039, NO-045: tách là đưa vào main một nửa hợp đồng [2]. Review merge 2026-09-21 finding #2 |`
- Nếu #3, #4, #5 không sửa trong lượt sửa #1, mỗi cái một dòng P3 `⬜`, chủ B5-01, trỏ về finding tương ứng của review này.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #1; P3 #3) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (Nit #7, #8) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (Nit #6; ca thiếu tính vào #1) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #2; P3 #4, #5) | 0,09 |

Tổng: 0,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **3,94 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Phần lớn prompt làm rất chắc. Cổng thoát 0 trên lượt chạy độc lập, độ phủ mọi đơn vị ≥ 97,5 % nhánh, mọi case bắt buộc của [8] có thật và kiểm đúng ý. SHA ghim là số đo thật: tự tải lại bốn tệp từ URL ghim thì khớp, và `export_pinned` tái lập ngoại tuyến hai lượt cùng SHA. Thứ tự `load_onnx`, bộ giải PNG có trần giải nén, khuôn `run_step` "ghi rồi mới gửi", khoá GPU fail-closed đều đúng hợp đồng; 10/10 lệch tác giả khai đều đứng được. **Nhưng** #1 là P1 chưa waiver: một ONNX 578 byte giấu `Loop` trong giá trị mặc định thuộc tính của hàm cục bộ đi qua trọn luật "ONNX không tin" dạng storage, rồi ORT nạp và chạy nó không giới hạn. Đây chính là kiểm tra an ninh BE-00 §9 giao cho bộ nạp. Ma trận `RULE.md` §5 là tuyệt đối: có P1 chưa waiver thì `REQUEST CHANGES`. Điểm 3,94 cũng dưới ngưỡng `APPROVE`. Sửa nằm gọn trong file của chính B5-01, nên không có lý do waiver.

**Phải làm để được duyệt:**

1. Sửa #1 ở `apps/ml/runtime/loader.py`: duyệt `FunctionProto.attribute_proto` (đồ thị và tensor) trong luật cấu trúc và luật dữ liệu ngoài, hoặc từ chối dạng storage có `attribute_proto` kiểu GRAPH/TENSOR. Kèm test chặn tái phát (`Loop` ẩn, op `com.microsoft` ẩn, tensor `EXTERNAL` ẩn trong `attribute_proto`), đỏ trên `4395ebb` và xanh sau khi sửa. Ba bản ghim thật vẫn phải nạp được. `bash tools/verify/run.sh verify` thoát 0.
2. Ghi dòng `➖` cho #2 (MNT-05) vào `DEBT.md` trước khi merge (R-38).
3. Sửa #3, #4, #5 trong cùng lượt (mỗi cái 1–5 dòng), hoặc ghi mỗi cái một dòng P3 vào `DEBT.md`.
4. Nit #6 sửa cùng #1. Nit #7, #8 do tác giả tự quyết.
5. Xin `/merge-review` lại ở **phiên mới** (R-37). Khi được duyệt: gộp bằng **squash** (nhánh chỉ mang trailer `Prompt: B5-01`).
