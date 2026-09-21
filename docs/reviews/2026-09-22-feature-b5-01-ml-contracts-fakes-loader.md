# Review merge feature/b5-01-ml-contracts-fakes-loader → main (lượt hai)

- Ngày: 2026-09-22 · Reviewer: phiên /merge-review — sub-agent độc lập (không mang ngữ cảnh tác giả; mọi khẳng định trong commit, báo cáo tác giả và phán quyết lượt một đều tự kiểm lại) · Commit đầu nhánh: `c61f8fa38f25` (gốc `5bb39de`; 2 commit: `4395ebb` feat B5-01, `c61f8fa` sửa theo review lượt một)
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0** (chạy tại chỗ trên worktree sạch; log `scratchpad/review2/verify.log`): `1817 passed, 10 skipped, 1 deselected` trong 165,66 s. 10 skip là `apps/api/core/tests/test_common.py` (có từ B0-06), 1 deselected là test `perf` chạy ở bước 5b.
- Độ phủ (in từ `tools.coverage_gate`):
  - tổng: dòng **99,45 %** · nhánh **97,56 %**
  - `apps/ml`: 100,00 % / 100,00 %
  - `apps/ml/runtime`: dòng 99,49 % · nhánh 97,95 %
  - `packages/ml_contracts`: dòng 99,91 % · nhánh 99,58 %
  - tập file bị chạm: dòng 99,76 % · nhánh 98,96 %

| # | Bước | Trạng thái |
|---|---|---|
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (1 test perf) |
| 6 | `lint_migrations` → `migrate_check` | đạt (2 revision; 9/9) |
| 7 | H1 H3 H4 H5 | đạt; H3/H4/H5 "không áp dụng" hợp lệ (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt (3 877 byte) |

Số cổng trùng khai báo của tác giả (1817 passed).

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt |
| `changes/B5-01.md` | đạt (7 dòng) |
| Dòng đầu commit | đạt: `feat(ml): …` (59 ký tự), `fix(ml): walk function attribute defaults in onnx checks` (56 ký tự) |
| Trailer `Prompt:` (R-36b) | đạt: cả hai commit `%(trailers:key=Prompt,valueonly)` → `B5-01` |
| File cấm | không đụng. Lượt sửa chạm 13 file: 12 trong `so_huu` + `DEBT.md` (dòng NO-064) |
| pragma / `type: ignore` trần / `noqa` trần / skip / xfail / hạ ngưỡng | không có cái mới. `type: ignore` mới trong test (`[import-untyped]`) có mã và lý do |

**Lưu ý gộp:** `main` đã đi thêm 16 commit (B1-01 đã gộp, NO-054..057). `git merge-tree --write-tree main HEAD` thoát 1 và xung đột **chỉ ở `DEBT.md`** (hai bên cùng nối cuối bảng). Id không trùng: `main` tới NO-057, nhánh dùng NO-060..064.

## Bằng chứng tự đo

Probe chạy trong container verify (`appback-verify-vendace-verify`, venv của worktree, onnx 1.22.0, onnxruntime 1.30.0), bản chép `/tmp/w`, `--network none`. Không chạm worktree. Log nằm ở `scratchpad/review2/`: `probe_r2.log`, `redold.log`, `bomb.log`, `bomb2.log`, `pinned.log`, `fncount.log`.

- **R1. Test mới có đỏ trên `4395ebb`?** Chép `loader.py` và `errors.py` của `4395ebb` đè vào bản sửa, rồi chạy 5 test mới hoặc đã sửa:
  - **đỏ 4:** `test_has_external_data_walks_every_tensor`, `test_structure_rules_see_function_attribute_defaults`, `test_load_onnx_m03_control_flow`, `test_ort_errors_are_every_real_onnxruntime_error`;
  - **xanh 1:** `test_load_onnx_runs_local_functions`. Đây là ca dương, xanh trên mã cũ là đúng.
  - Tác giả khai "5 test mới đỏ": khai sai số nhưng không ảnh hưởng. Trên mã mới, `test_loader.py` 15/15 xanh.
- **R2. Các đường vượt của lượt một, dạng lồng.** `Loop` nằm trong `If` nằm trong mặc định thuộc tính hàm; mặc định gọi hàm cục bộ khác có `Loop`: **đều bị từ chối** (`MODEL_FORMAT_UNSUPPORTED`). Tensor ngoài, sparse ngoài và đồ thị có initializer ngoài trong mặc định thuộc tính: `has_external_data` → `True`.
- **R3. Luật miền bị vượt bằng hàm cục bộ trùng id với op ORT đã đăng ký** (finding #9). Model khai một hàm cục bộ có cùng `(domain, tên)` với một op ORT đã đăng ký, rồi gọi op đó. Ba lần thử đều qua `_structure_allowed` và `_verify` dạng storage, và ORT chạy **kernel đã đăng ký** chứ không chạy thân hàm:

  | Ca | Model | Đo được | Ở `4395ebb` |
  |---|---|---|---|
  | `com.microsoft::Gelu` | 149 byte | ra 0,8413 = Gelu(1), không phải thân hàm | đã lọt |
  | `ai.onnx.ml::Binarizer` | 150 byte | ORT chạy kernel `ai.onnx.ml` | đã lọt |
  | hàm khai `overload` khác lời gọi | — | ORT vẫn chạy kernel contrib | **bị chặn**: bộ inline không inline nên node `com.microsoft` còn lại |

  Hàng thứ ba là **hồi quy do `c61f8fa`**: tập `local` so theo `(domain, name)` mà bỏ qua `overload`.
- **R4. Không có trần cho kích thước sau khi mở hàm cục bộ** (finding #10).
  - Hàm cục bộ gọi lồng nhau làm số node sau inline tăng theo cấp số nhân trong khi số byte của model gần như không đổi. Model **1 654 byte** mở ra **1 048 576 node**. Model đó **qua `_verify` dạng storage** sau 5,45 s với RSS 1 011 MiB; bộ nhớ gấp đôi sau mỗi bậc lồng.
  - Tạo phiên ORT trên các model này siêu tuyến tính:

    | Model | Số node (sau mở rộng) | Tạo phiên ORT |
    |---|---|---|
    | lồng 14 bậc | 16 384 | 3,8 s |
    | lồng 16 bậc | 65 536 | 65,9 s |
    | mốc: đồ thị phẳng, không hàm | 65 536 | 0,57 s |
    | mốc: đồ thị phẳng, không hàm | 262 144 | 3,1 s |

  - Tôi dừng đo ở đây, không đẩy thêm. Trần 512 MiB của `load_onnx` không chặn được đường này.
- **R5. Không chặn nhầm model hợp lệ.**
  - Ba bản ghim thật trong `/work/b5-01-models` nạp được qua `load_onnx` dạng ghim: `images (1,3,640,640)` ×2, rec `x`. Cả ba vẫn qua luật dạng storage (chỉ miền chuẩn).
  - `test_load_onnx_m03_exported_storage` xanh trong cổng.
  - Ba bản ghim và model do `export_onnx` xuất đều có **0 hàm cục bộ** (263/263/860/3 node). Điều này quyết định cách sửa đề xuất ở #9/#10.
- **R6. Đã soi, không ghi finding.**
  - `training_info` không được duyệt, nhưng ORT 1.30 bỏ qua nó: không chạy, không đọc tensor ngoài trong đó (model có tensor `EXTERNAL` ở đó vẫn nạp mà không lỗi đường dẫn). Danh sách của BE-00 §9 cũng không nêu nó.
  - `SequenceMap` (op chuẩn) chạy được. Số vòng bị chặn bởi độ dài chuỗi vào, tức là bởi dữ liệu, nên không thuộc luật `Loop`/`Scan` của hiến chương.

## Trạng thái finding lượt một

| # | Mức | Nội dung | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| 1 | P1 | Luật "ONNX không tin" bị vượt qua `FunctionProto.attribute_proto` | **Đã sửa phần `attribute_proto`; gốc chưa đóng** | `_parts` duyệt `attribute_proto` (đồ thị, tensor, sparse); R1, R2 xanh. Nhưng gốc của #1, "luật cấu trúc không nhìn đúng thứ ORT thực sự chạy", vẫn còn: luật miền vượt được bằng hàm cục bộ trùng id (#9), và bản sửa còn nới thêm một đường (`overload`). R-19 |
| 2 | P2 | MNT-05 kích thước nhánh | **Đã xử lý** | `NO-064` `➖`, đủ cột, lý do đứng được (như NO-039/NO-045) |
| 3 | P3 | TOCTOU `export_yolo` | **Đã sửa** | `export_yolo.py:299-304`: chép trước, băm bản chép, rồi mới nhập `ultralytics`; `test_export_yolo_checks_sha_first` xanh |
| 4 | P3 | Thiếu docstring | **Đã sửa** | `gpu.py:57`, `loader.py:48`, `pinned.py:150`, `payloads.py:61` |
| 5 | P3 | Ba bản gốc Pydantic | **Đã sửa** | `artifacts.py:73` `FrozenModel`; `payloads`/`datasets` nhập lại; không vòng nhập (`lint-imports`, `mypy --strict` đạt) |
| 6 | Nit | Docstring test "mọi độ sâu" | **Đã sửa** | `test_loader.py:334-340` |
| 7 | Nit | `ORT_ERRORS` thiếu 3 lớp | **Đã sửa** | 15 lớp; `test_ort_errors_are_every_real_onnxruntime_error` so với module thật (đỏ trên mã cũ, R1) |
| 8 | Nit | Bộ giả ném với dấu giả trên trang nhỏ | **Đã sửa** (kèm Nit #11) | `fakes.py:35-38`; test trang 300×300 |

## Finding mới

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 9 | **P1** | SEC-05 · R-17 · R-19 · BE-00 §9 | **Luật miền của "ONNX không tin" vẫn vượt được, và bản sửa làm rộng thêm.**<br><br>**Cơ chế.** `_node_allowed` cho qua mọi node có `(node.domain, node.op_type)` trùng một hàm cục bộ, với giả định "thân nó cũng bị duyệt". Nhưng khi `(domain, tên)` trùng một op đã đăng ký (`com.microsoft`, `ai.onnx.ml`…), ORT 1.30 chạy **kernel đã đăng ký**, không chạy thân hàm. Luật duyệt một thân hàm mà ORT không bao giờ dùng. Trên bản inline cũng mù: bộ inline của `onnx` thay thân hàm vào, nên chỉ còn op chuẩn (R3).<br><br>**Lịch sử.** Đường chính có từ `4395ebb` (review lượt một sót). Biến thể `overload` lệch thì `4395ebb` chặn, còn `c61f8fa` cho qua, vì `local` bỏ qua `FunctionProto.overload`/`NodeProto.overload`.<br><br>**Tác động.** Danh sách miền cho phép mà BE-00 §9 đặt ra mất tác dụng. Mọi kernel contrib/`ai.onnx.ml` của ORT (bề mặt C++ lớn hơn nhiều so với op chuẩn) tới được từ model dạng storage, là dữ liệu hiến chương xếp **không tin**. Lượt một đã xếp "op `com.microsoft` ẩn" vào #1 P1. Test mới `_hidden_microsoft_op` chỉ phủ đường mặc định thuộc tính, không phủ đường này. Xếp P1 cùng cơ sở với #1: vượt kiểm tra ở biên tin cậy | `apps/ml/runtime/loader.py:150-154` (`_node_allowed`), `:167-168` (`local` theo `(domain, name)`); test thiếu ở `apps/ml/runtime/tests/test_loader.py:314-331` | Đơn giản và fail-closed. **Dạng storage có `model.functions` khác rỗng thì từ chối.** R5 cho thấy mọi model hợp lệ của hệ thống (ba bản ghim, `export_onnx`, `export_yolo`) đều không có hàm cục bộ. Chặt hơn hiến chương là được phép, như lệch #9 ở lượt một. Cách này đóng luôn #1 và #10, bỏ được lượt inline. Sửa `test_load_onnx_runs_local_functions` thành ca **từ chối**, rồi thêm ca "hàm cục bộ trùng id op contrib / `ai.onnx.ml` / lệch `overload`": ba ca này phải đỏ trên `c61f8fa`.<br><br>Nếu phải giữ hàm cục bộ: chỉ nhận hàm có miền **không** thuộc miền chuẩn và **không** thuộc bất kỳ miền nào ORT đăng ký, so id theo `(domain, name, overload)`, và giữ luật trên cả bản gốc |
| 10 | **P1** | PERF-05 · SEC-05 · R-25 | **Không có trần cho kích thước sau khi mở hàm cục bộ.**<br><br>**Cơ chế.** Lời gọi hàm cục bộ lồng nhau mở ra theo cấp số nhân. `_structure_allowed` gọi `inline_local_functions` rồi dựng **cả hai** danh sách node (`(*iter_nodes(model), *iter_nodes(inlined))`) mà không đếm trước. R4: model 1 654 byte → 1 048 576 node, qua `_verify` sau 5,45 s với ~1 GiB RSS, bộ nhớ gấp đôi mỗi bậc. Qua được luật rồi thì ORT tạo phiên siêu tuyến tính: 65,9 s cho 65 536 node sau mở rộng, so với 0,57 s cho đồ thị phẳng cùng cỡ.<br><br>**Tác động.** Trần 512 MiB của M02 không chặn được. Một model tí hon có thể giữ luồng worker `ml` tới trần giờ cứng của task (3 600 s), hoặc đẩy tiến trình tới hết bộ nhớ ngay trong bước kiểm. Cùng loại hậu quả với #1 lượt một (treo worker). Có từ `4395ebb` | `apps/ml/runtime/loader.py:163-168` | Cách sửa của #9 (từ chối `model.functions` ở dạng storage) đóng luôn #10. Nếu giữ hàm cục bộ: trước khi inline, tính số node sau mở rộng bằng quy hoạch động có nhớ trên đồ thị gọi hàm (kể cả đồ thị con), vượt trần (ví dụ 100 000) thì từ chối; và duyệt bằng `itertools.chain` thay vì dựng tuple. Thêm test: model lồng vài chục bậc → `MODEL_FORMAT_UNSUPPORTED` trong thời gian ngắn |
| 11 | Nit | LOG-04 · R-16 | `answer_for` bắt mọi `ValueError` của `_plan`. `pydantic.ValidationError` là lớp con của `ValueError`, nên lỗi thật của `render_plan` (dựng `BoxPx`/`WallPx` sai) cũng thành "rỗng" thay vì nổi lên. Chỉ ở `ML_BACKEND=fake` | `packages/ml_contracts/fakes.py:35-38` | Kiểm khổ vẽ được trước (tách hàm `can_render(width, height)` từ `_layout`), hay bắt riêng lỗi "quá nhỏ" |

**P0: 0 · P1: 2 (mới) · P2: 0 mới (P2 #2 lượt một đã có `NO-064` ➖) · P3: 0 · Nit: 1**

## Những chỗ đã soi kỹ và **đạt**

- **Bản sửa #1, phần `attribute_proto`.** `_parts` là **một** lượt duyệt dùng chung cho `iter_nodes`, `iter_graphs`, `iter_tensors` (sửa gốc đúng chỗ, không vá từng caller).
  - `normalize_onnx` dùng `iter_graphs`/`iter_nodes` nên giờ cũng xoá `doc_string` trong đồ thị của mặc định thuộc tính. Vô hại: model xuất không có hàm.
  - Duyệt bằng ngăn xếp tường minh, không đệ quy; độ sâu đã bị protobuf giới hạn lúc giải.
- **`ORT_ERRORS`** đúng 15 lớp, có test tự đỏ khi nâng bản ORT có lớp mới.
- **`FrozenModel`.** Một gốc duy nhất; `datasets`/`payloads` → `artifacts` → `_png`, `families`, `labels`, không vòng. Hợp đồng `ml_contracts` không nhập `torch`/`onnxruntime`/`messaging`/`storage` vẫn giữ (`test_ml_contracts_boundary`, `lint-imports`).
- **Phần còn lại của diff `main...HEAD`.** Đọc lại `tasks_util`, `gpu`, `export*`, `pinned`, `payloads`, `celery_main`, `trainers`, `device`, `settings`, `fakes`. Các kết luận "đạt" của lượt một vẫn đúng: thứ tự `load_onnx`, "ghi rồi mới gửi", khoá GPU fail-closed, `fetch` có trần và xoá `.part`. Không thấy gì mới ngoài #9–#11.
- **`DEBT.md`.** NO-060..064 đủ chín cột, chủ đúng, mức hợp lý. `NO-064` `➖` có ngày đóng và lý do đứng được, trỏ về finding #2. Không nợ P0/P1 nào mở trên sổ. #9, #10 là P1 **mới** do review chỉ ra, nên phải **sửa**, không ghi nợ thay (R-38).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 1 (P1 #9) | 0,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (Nit #11) | 0,75 |
| PERF – Hiệu năng | 10 % | 1 (P1 #10) | 0,10 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (ca thiếu tính vào #9, #10) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 (P2 #2, đã chấp nhận `NO-064`) | 0,09 |

Tổng: 0,25 + 0,75 + 0,75 + 0,10 + 0,50 + 0,50 + 0,35 + 0,25 + 0,09 = **3,54 / 5**

## PHÁN QUYẾT: REQUEST CHANGES

Lượt sửa làm đúng và gọn phần lớn việc được giao:
- `attribute_proto` được duyệt ở một chỗ chung; test hồi quy đỏ trên `4395ebb` (4/5; ca thứ năm là ca dương);
- #2–#8 đều xử lý đúng, cổng thoát 0, độ phủ ≥ 97,9 % nhánh ở mọi đơn vị bị chạm;
- ba bản ghim thật vẫn nạp được.

**Nhưng** gốc của #1 lượt một là "luật cấu trúc phải thấy đúng thứ ORT chạy", và gốc đó chưa đóng.
- **#9:** một model 149 byte khai hàm cục bộ trùng id op `com.microsoft`/`ai.onnx.ml` vẫn qua `_verify` dạng storage, rồi ORT chạy kernel contrib. Biến thể `overload` lệch còn là hồi quy do chính bản sửa.
- **#10:** không có trần kích thước sau khi mở hàm cục bộ. Một model 1,6 KB đi qua bước kiểm với ~1 GiB bộ nhớ, rồi làm ORT tạo phiên siêu tuyến tính.

Cả hai là P1 chưa waiver, cùng cơ sở với #1 lượt một. Ma trận `RULE.md` §5 buộc `REQUEST CHANGES`; điểm 3,54 cũng dưới ngưỡng `APPROVE`. Sửa nằm gọn trong file của B5-01, không có lý do waiver.

**Phải làm để được duyệt:**

1. Sửa #9 và #10 ở `apps/ml/runtime/loader.py`. Đề xuất: dạng storage có `model.functions` khác rỗng → `MODEL_FORMAT_UNSUPPORTED`. Model hợp lệ của hệ thống không có hàm cục bộ (R5); cách này đóng cả hai finding và phần gốc còn lại của #1. Nếu giữ hàm cục bộ: so id theo `(domain, name, overload)`, cấm hàm trùng miền ORT đăng ký, và thêm trần số node sau mở rộng tính **trước** khi inline.
2. Test chặn tái phát: hàm cục bộ trùng id op contrib, `ai.onnx.ml`, lệch `overload`; lời gọi hàm lồng sâu. Các ca này phải đỏ trên `c61f8fa` và xanh sau khi sửa. Cập nhật `test_load_onnx_runs_local_functions` theo luật mới. Ba bản ghim thật vẫn phải nạp được.
3. Nit #11: tác giả tự quyết.
4. Rebase lên `main` hiện tại (xung đột chỉ ở `DEBT.md`: giữ cả dòng NO-054..057 của `main` lẫn NO-060..064 của nhánh). Chạy lại `bash tools/verify/run.sh verify` trên bản đã rebase, thoát 0.
5. Xin `/merge-review` lại ở **phiên mới** (R-37). Khi được duyệt: gộp bằng **squash**, nhánh chỉ mang trailer `Prompt: B5-01`.
