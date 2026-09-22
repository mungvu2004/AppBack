# Review merge fix/b0-04-layout-and-c11-debts → main

- Ngày: 2026-09-22 · Reviewer: phiên `/merge-review` **độc lập** (không phải phiên tác giả; mọi khẳng định trong commit, `DEBT.md` và báo cáo `W12-LAYOUT-C11.report.md` đều tự kiểm lại) · Commit đầu nhánh: `fe20d5265442`. Nhánh có 6 commit: `225b4dc` FIX-060 (B0-02), `2eaa822` FIX-061 (B0-02), `4bdbbbe` FIX-062 (B0-04), `e9d8f3f` FIX-063 (B5-01), `d1913ec` FIX-064 (B1-01), commit gộp `main` `fe20d52` (cha `d1913ec`, `67bf9bd`). Merge-base = `67bf9bd`; phạm vi = `git diff main...HEAD` (8 file: `DEBT.md`, `packages/core/{object_keys.py, tests/test_object_keys.py}`, `packages/storage/{keys.py, tests/test_keys.py}`, `packages/ml_contracts/{payloads.py, tests/test_payloads.py}`, `apps/api/auth/tests/test_refresh.py`; +239/−53 dòng). **`main` đã đi thêm** tới `5892c71` (sổ FIX-065..067) — chỉ đổi `DEBT.md` và `docs/fixes.md`. `git merge-tree --write-tree main HEAD`: **xung đột duy nhất ở `DEBT.md`** (một khối, NO-087..NO-090) — xem điều kiện merge 1.
- Cổng: `bash tools/verify/run.sh verify` **mã thoát 0**, lấy từ dòng `EXIT=0` của chính shell bọc (không bị cắt, nên không cần `docker wait`; container `appback-verify-appback-fix-storage-verify-run-1e2f02178f45` đã tự xoá) và khớp dòng `mã thoát: 0` cuối log host FIX-053. Lượt 05:52:44Z–05:57Z trên `fe20d5265442`; ngay trước đó `docker ps -q --filter name=verify-run | wc -l` = 1. Log host: `C:/Users/mxuan/orca/workspaces/appback-fix-storage/.cache/src-out/verify/20260922T055244Z-fe20d5265442.log` (git-ignore, để lại làm bằng chứng). Bước 5: **2134 passed, 0 failed, 10 skipped**, 1 deselected, 262,7 s; cả 10 skip là `apps/api/core/tests/test_common.py` (`ssssssssss` — tập tham số rỗng, chưa có route được bảo vệ), đúng ngoại lệ BE-00 §12, file không nằm trong diff.
- Độ phủ (in từ `tools.coverage_gate` của lượt trên, không lấy từ báo cáo tác giả):
  - tổng: dòng **99,35 %** · nhánh **97,53 %**
  - `packages/core`: dòng **100,00 %** · nhánh **100,00 %** · `packages/storage`: **99,63 %** · **98,25 %** · `packages/ml_contracts`: **99,90 %** · **99,56 %** · `apps/api/auth`: **98,61 %** · **92,65 %**
  - tập file bị chạm: dòng **100,00 %** · nhánh **100,00 %**. Không dòng nào rơi vào sai số NO-035 (file sản phẩm bị chạm không đi qua SQLAlchemy).

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt (329 file) |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt (281 file) |
| 4 | `lint-imports` | đạt (9 kept, 0 broken — gồm hợp đồng `packages.core` cô lập) |
| 5 | `coverage run -m pytest` → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf 1 passed; `auth_login` 7/7, `auth_logout` 2/2, `auth_refresh` 5/5; ba cảnh báo route hạ tầng có từ trước) |
| 6 | `lint_migrations` → `migrate_check` | đạt (4 revision; 10/10) |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt — H1 186 mẫu; H3/H4/H5 `không áp dụng` **hợp lệ** (B1-02, B3-05, B4-01 chưa hợp nhất) |
| 8 | openapi | đạt |

## Điều kiện dừng sớm (§2 của skill)

| Kiểm | Kết quả |
|---|---|
| `git status --porcelain` rỗng | đạt (đầu phiên và cuối phiên) |
| `changes/B0-02.md`, `changes/B0-04.md`, `changes/B5-01.md`, `changes/B1-01.md` tồn tại | đạt (có từ các prompt gốc; FIX không bắt buộc sửa mảnh) |
| Dòng đầu Conventional Commits ≤ 72 ký tự | đạt — 6 commit, dài nhất 65 ký tự; `fix`/`test`/`chore` đúng loại (FIX-064 chỉ đổi file test → `test(auth)`) |
| Trailer đọc được (R-36b) | đạt — `%(trailers:key=Prompt,valueonly)` ra `B0-02`, `B0-02`, `B0-04`, `B5-01`, `B1-01`, `B0-04`; năm commit FIX ra đúng `Fix: FIX-060` … `FIX-064`; commit gộp không `Fix:` |
| Mỗi commit chỉ đụng file trong [4] của FIX mình | đạt — `225b4dc`, `2eaa822`: `packages/core/{object_keys.py, tests/test_object_keys.py}`; `4bdbbbe`: `packages/storage/{keys.py, tests/test_keys.py}`; `e9d8f3f`: `packages/ml_contracts/{payloads.py, tests/test_payloads.py}`; `d1913ec`: `apps/api/auth/tests/test_refresh.py`; `DEBT.md` theo luật đoạn giao việc |
| Dòng `DEBT.md` đổi trong **chính** commit sửa | đạt — NO-088 `✅` trong `225b4dc` (FIX-060), NO-081 `✅` trong `e9d8f3f` (FIX cuối của bộ ba 061..063), NO-082 `✅` trong `d1913ec` (FIX-064) |
| Đụng `docs/charter/*`, `openapi.json`, `tools/contract/APPFRONT_SHA`, `uv.lock`, `pyproject.toml`, `.importlinter`, `conftest.py`, `tools/**` | không |
| `pragma` / `type: ignore` / `noqa` / `skip` / `xfail` mới / hạ ngưỡng | không (grep dòng `+` của diff: 0) |
| `conftest.py` lồng, file cấu hình công cụ riêng, thư viện mới | không (`object_keys.py` chỉ nhập thêm `packages.core.pipeline`, nội bộ lõi) |
| Nhánh > 400 dòng logic (MNT-05) | không — +239/−53 gồm test và `DEBT.md` |

Không có điều kiện dừng sớm nào kích hoạt.

## Công cụ kiểm tại chỗ

Probe chạy trong container verify (`run.sh shell < probe.sh`, bản sao `/tmp/w`, `python -m pytest -p no:cacheprovider -o addopts="" …`); file của commit cũ lấy bằng `git show <sha>:<file>` đặt tạm ở `.cache/rv-layoutc11/` (git-ignore), chép đè trong bản sao, **đã xoá** cuối phiên. Hai lượt probe: lượt 1 khởi chạy khi đếm `verify-run` = 1 (chính lượt verify của phiên này đang ở bước 5 → tối đa 2 container, đúng trần); lượt 2 khi đếm = 0. Cả hai `EXIT=0`.

- **P1 — đỏ trước / xanh sau từng FIX** (test HEAD chạy trên mã sản phẩm của commit cha, rồi trên HEAD):

  | FIX | Test chặn tái phát (HEAD) | Mã cũ đặt vào | Trước | Sau | Khớp dòng `DEBT.md`? |
  |---|---|---|---|---|---|
  | 060 | `test_object_keys.py -k upload_prefix_of` | `object_keys.py`, `storage/keys.py`, `payloads.py` @ `83a4391` | **8 failed**, 11 passed — đúng 8 ca mới/đổi: `""` ("khoá rỗng"), tiền tố trần, `…/../x`, `…/../../../../x`, `…/pages//0.png`, `…/pages/./0.png`, `…/pages/0 .png`, `…/x.meta.json` | 19 passed | ✓ "đỏ 8 failed → xanh 19 passed" |
  | 061 | `test_object_keys.py -k "run_prefix or model_prefix"` | cả ba file @ `225b4dc` | **16 failed** (`AttributeError`: lõi chưa có `run_prefix`/`model_prefix`) | 16 passed | ✓ "đỏ 16 failed → xanh 16 passed" |
  | 062 | `test_keys.py -k run_and_model_layout` | lõi HEAD, `storage/keys.py` + `payloads.py` @ `83a4391` | **2 failed** (cả file: 2 failed, 43 passed) | 2 passed; cả file 45 passed | ✓ "đỏ 2 failed → xanh 2 passed" |
  | 063 | `test_payloads.py -k "run_and_model_layout or id_rules_come_from_core"` | lõi + storage HEAD, `payloads.py` @ `83a4391` | **7 failed** (3 tên bố cục + 4 kiểu id; cả file: 7 failed, 90 passed) | 7 passed; cả file 97 passed | ✓ "đỏ 7 failed → xanh 7 passed" |
  | 064 | `test_refresh.py -k fail_limit_checker` | thân `_assert_exact_fail_limit` @ `83a4391` ghép (bằng `ast`) vào file test HEAD | **4 failed**, 2 passed — M1 `[401]×40/(7, 360)`, khoá vắng + 503, 22 lượt 401/`(1, 360)`, và chia đúng 20/20 với `(0, -2)` | 6 passed | ✓ "đỏ 4 failed → xanh 6 passed" |

- **P2 — đột biến trên HEAD** (test một nguồn của [6] có răng thật):
  - `runs/` → `run/` **trong nguồn lõi** `run_prefix`: **4 failed** — `storage::test_keys_follow_charter_layout` và `ml_contracts::{test_upload_layout_comes_from_core, test_run_and_model_layout_comes_from_core[run_prefix], test_infer_step_accepts}`: `storage` và `ml_contracts` cùng đỏ trên một đột biến ở lõi.
  - `MODELS_PREFIX = "ml/model/"` ở lõi: **6 failed** — `storage::test_keys_follow_charter_layout` và `ml_contracts::{…[model_prefix], …[MODELS_PREFIX], test_model_ref_forms_accept, test_evaluate_version_rules, test_training_finished_rules[changes0-True]}`.
  - Bỏ luật bước trong `run_prefix`: **4 failed** — ba ca "bước pipeline" của core và `storage::test_builders_reject_wrong_ids[bước pipeline]`: luật bước còn đúng một bản, cả hai gói chốt nó.
  - Bỏ `check_key` của `upload_prefix_of` (lùi FIX-060): **8 failed** ở core; `ml_contracts` xanh cả (người gọi duy nhất nhận `ObjectKey` đã kiểm — không đổi hành vi thấy được).
  - M5 bỏ vế `0 <` của FIX-064: **2 failed** (ca khoá vắng + 503, và `…passes_an_exact_split`). M6 bỏ vế `extra == counter[0]`: **2 failed** (ca M1 và ca 22/`(1, 360)`). Cả hai vế của điều kiện đều có test chốt.
- **P3 — tương đương hành vi payload** (`payloads.py` + `object_keys.py` @ `83a4391` nạp thành module riêng, so với HEAD): lưới **17 931** đầu vào — `ModelRef` 435 (3 họ × `version_id` {đúng, khác, `None`, sai mẫu} × 9 `weights_key` {dưới `ml/models/{vid}/`, dưới id khác, thiếu `/`, `…{vid}x/`, gốc trần, `ml/modelsX/`, `../`, `.pt`, `None`} × ghim × checksum), `InferStepPayload` 17 280 (3 họ × 6 bước gồm `preprocess`, `spatialDataBuild`, `sniff` × 12 `page_key` gồm tiền tố trần, `../`, `//`, `.meta.json`, tầng sai, `upl_bad`, `ml/models/…` × 4 `run_id` × 10 `artifact_prefix` × 2 dạng model), `TrainingFinishedPayload` 216: lệch nhận/từ chối **0**, ngoại lệ khác `ValidationError` **0**; lưới có ca nhận ở cả ba lớp (17 / 56 / 6).
- **P4 — C11_parallel thật (Postgres/Redis qua testcontainers) dưới đột biến mã sản phẩm:**
  - M1 `bump` đọc-rồi-ghi (`GET` rồi `SET`), ×3: bản nhánh **FAILED** cả ba với `tầng thất bại đếm sai (cuối loạt (giá trị, TTL) = (9, 360)): Counter({401: 40})` (rồi `(8, 360)`, `(9, 360)`). Bộ kiểm cũ (ghép lại) trên cùng đột biến: `assert 9 >= 20` ở kiểm "cửa sổ thứ hai" — đúng lỗi NO-082. **Đã sửa gốc.**
  - M7 `_denied` xoá khoá bộ đếm khi trả 429 (hạn mức tự mở lại — lỗi thật gần nhất với vùng pass nhánh nới, xem mục lệch #5), ×3: C11_parallel **FAILED** cả ba (`Counter({401: 37, 429: 3})`/`(15, 360)`, `{401: 36, 429: 4}`/`(14, 360)`, `{401: 30, 429: 10}`/`(6, 360)`, đều "đếm sai"); `test_auth_refresh__C11` và `__C11_total` (tuần tự) **xanh** — chỉ bản song song bắt được M7.
  - M2 lệch một ở `_denied` (`>` → `>=`): **FAILED** `Counter({429: 21, 401: 19})`/`(40, 360)`, "đếm sai".
  - Đối chứng không đột biến: `-k "C11 or fail_window or fail_limit"` **10 passed**.
- **P5 — người gọi mọi API nhánh đổi** (grep toàn cây sau khi gộp `main` @ `67bf9bd`, gồm B0-06, B0-07, B1-01, B3-01 mới vào): `upload_prefix_of` — chỉ `packages/ml_contracts/payloads.py:133`; `run_prefix`, `model_prefix` — `storage/keys.py:59`, `:71`, `payloads.py:111`, `:133`; `MODELS_PREFIX` — `payloads.py:297` (tên cũ `payloads.MODELS_PREFIX` vẫn còn, là **cùng** đối tượng của lõi). `storage.keys._STEP_IDS`, `payloads.is_id`, `payloads._id_of` — **0** người nhập ngoài chính module. `apps/ml/runtime/{loader.py, tasks_util.py}` dùng `ModelRef`/`InferStepPayload` — hành vi không đổi (P3), test `apps/ml` xanh trong cổng. `main` @ `5892c71` không thêm người gọi nào.
- **P6 — tĩnh:** mọi hàm mới/đổi có docstring (`run_prefix`, `model_prefix`, `_id_of`, `finished`, 9 hàm test mới, cộng docstring bù cho `test_upload_prefix_of_accepts`); hàm sản phẩm dài nhất trong diff 11 dòng (`run_prefix`), CC ≤ 2.

## Ranh giới `packages/core` sau nhánh (câu hỏi của người điều phối)

**Đứng được — luật bước pipeline thuộc lõi, không kéo miền ML xuống `core`; với điều kiện sổ (#1).**

- **Từ vựng bước đã ở lõi trước nhánh.** `packages/core/pipeline.py` (B0-02, `14ceca2`) giữ `PIPELINE_STEPS` — sáu bước khớp `PIPELINE_STAGES` của FE, gồm cả bước không-ML (`preprocess`, `spatialDataBuild`, `qualityCheck`) — và `packages/core/errors.py:47` đã dựng đúng tập đó để kiểm tham số `step` của sổ lỗi. `object_keys.py` nhập một module lõi khác, không nhập gói ngoài; hợp đồng lõi cô lập của `lint-imports` KEPT. Miền ML thật (`ModelFamily`, `FAMILY_STEP`, `BASE_MODELS`) vẫn ở `packages/ml_contracts/families.py`, `core` không biết họ model nào.
- **Luật bước là một phần của bố cục, cùng loại với luật id.** BE-00 §8 viết `…/runs/{run}/{bước}/…`; `run_prefix` kiểm `{bước}` ∈ `PIPELINE_STEPS` y như `upload_prefix` kiểm `{L-…}` bằng `is_spatial_id` và `{upl}` bằng `check_id`. Để luật bước lại `storage` thì lõi sẽ dựng được `…/runs/{run}/sniff/` mà `storage` từ chối — hai định nghĩa "tiền tố lượt chạy hợp lệ", đúng loại lặp NO-081 đang chữa. Luật bị **dời** chứ không chép: `storage.keys._STEP_IDS` đã xoá, và P2 (bỏ luật ở lõi → core **và** storage cùng đỏ) cho thấy còn đúng một bản. Với `ml_contracts` vế kiểm bước là thừa vô hại (`step: ModelFamily` ⊂ `PIPELINE_STEPS`, test `families` so hai bảng) — P3 xác nhận không đổi nhận/từ chối.
- **Luật đặt của FIX-056 giữ được.** Lõi thêm đúng hai tiền tố `ml_contracts` phải kiểm trong payload không tin (`artifact_prefix` ⇐ `run_prefix`, `weights_key` ⇐ `model_prefix`) và gốc `MODELS_PREFIX` (payload kết thúc huấn luyện chưa có id). Mọi hàm dựng khoá **đầy đủ** (`run_artifact`, `model_artifact`, `upload_original`, `upload_page`, `library_object`, `dataset_object`, `avatar`) và `server_chosen_kind` vẫn ở `storage.keys`; `run_prefix` nhận `upload_root` (kết quả `upload_prefix`/`upload_prefix_of`) vì `ml_contracts` chỉ có `page_key`, không có ba id rời — docstring ghi rõ điều kiện trước, đầu ra vẫn qua `check_prefix`.
- **`ml_contracts._id_of = AfterValidator(partial(check_id, prefix))`** đứng được: `check_id` là luật id của lõi (FIX-056), Pydantic chuyển `ValueError` của nó thành lỗi trường; thông báo nay kèm giá trị, nhưng `define_task` chỉ ghi `exc.error_count()` (`packages/messaging/tasks.py:202-203`), không ai khớp chuỗi này ngoài test (grep) — đóng Nit #5 của review `fix/b0-04-key-layout-debts`.
- **Rủi ro còn lại là sổ, không phải mã:** đường cắt "theo ai cần" nay đặt ở lõi tiền tố của 4/7 dạng khoá BE-00 §8 (original và pages qua `upload_prefix`; `runs/`; `ml/models/`). Việc dời nốt các hàm dựng thuần hay giữ nguyên là quyết định của NO-079 — nhưng dòng NO-079 vẫn chưa ghi ba tên nhánh thêm (#1).

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P3 | R-34 (sổ) | Nhánh thêm ba tên công khai vào lõi dùng chung — `run_prefix` (kèm luật bước pipeline), `model_prefix`, `MODELS_PREFIX` — báo cáo tác giả nói §2.2 cần ghi chúng ("Cho sổ NO-079"), nhưng dòng `DEBT.md` NO-079 (của người điều phối) vẫn chỉ liệt kê tên của FIX-043 và phần mở rộng FIX-054/056; báo cáo không phải sổ bền. Cùng loại finding #7 của review `fix/b0-04-key-layout-debts` | `DEBT.md:99` (NO-079); `packages/core/object_keys.py:21`, `:94-108` | Người điều phối bổ sung vào NO-079 (nhật ký quản trị, commit thẳng `main` được theo R-36) — văn bản đề xuất ở mục Sổ nợ |
| 2 | Nit | R-07 | Tập id bước được dựng hai lần trong cùng gói lõi, cùng chủ B0-02: `_STEP_IDS = frozenset(step for step, _ in PIPELINE_STEPS)` ở `errors.py:47` và (nhánh dời từ `storage` sang) `object_keys.py:26`. Số bản không tăng (trước là `storage` + `errors`), nguồn luật vẫn là `PIPELINE_STEPS`; chỉ là phép dựng lặp — lượt dời là dịp gộp | `packages/core/object_keys.py:26`, `packages/core/errors.py:47` | Một hằng công khai trong `packages/core/pipeline.py` (vd `STEP_IDS: Final = frozenset(step for step, _ in PIPELINE_STEPS)`), hai nơi nhập; hoặc giữ nguyên |

**P0: 0 · P1: 0 · P2: 0 · P3: 1 · Nit: 1**

## Những chỗ đã soi kỹ và **đạt**

- **Sửa gốc (R-19), mỗi FIX:** FIX-060 — `check_key(key)` là dòng đầu của `upload_prefix_of` (fail-closed), không phải kiểm riêng ở người gọi; P2 lùi FIX-060 → 8 ca core đỏ. FIX-061 — bố cục `runs/{run}/{step}/` và `ml/models/{mdl}/` chỉ còn **một** chuỗi dựng mỗi thứ (`object_keys.py:103`, `:108`; grep `runs/`, `ml/models` trong mã sản phẩm: ngoài lõi chỉ còn docstring và thông báo lỗi). FIX-062 — `run_artifact`/`model_artifact` dựng qua lõi (`is` đúng hàm lõi + đột biến tên → khoá đổi theo), `_STEP_IDS` riêng đã xoá. FIX-063 — `ml_contracts` kiểm qua `run_prefix`/`model_prefix`/`MODELS_PREFIX` của lõi, xoá hằng riêng và chuỗi dựng lại; P2 cho thấy đột biến **nguồn** lõi làm `storage` và `ml_contracts` cùng đỏ (đúng [6]). FIX-064 — điều kiện "cửa sổ thứ hai" đổi tại đúng bộ kiểm; P4 M1 nay báo "đếm sai".
- **Hành vi không đổi với khoá hợp lệ và với payload:** P3 lệch 0/17 931; `upload_prefix_of` chỉ thêm từ chối cho đầu vào không phải khoá (người gọi duy nhất đã lọc bằng `ObjectKey`); thứ tự kiểm của `run_artifact` đổi (id lượt tải lên trước bước) chỉ đổi **thông báo** khi có ≥ 2 trường sai, mỗi thông báo vẫn nêu đúng một trường sai thật.
- **Test một nguồn đúng [6]:** mỗi FIX có test `is`/đột biến đỏ trên mã cũ (P1), không test nào chỉ so giá trị trùng khít (thứ hai bản sao cũng qua). Test của `packages/core` là mẫu biên (6 bước, 7 ca sai, đột biến `ids.is_id`), test của hai gói gọi chỉ chốt "đúng hàm lõi".
- **C11 không yếu đi ở chỗ nào hợp đồng đòi:** assert đếm chính xác `statuses == [401] * limit + [429] * limit` giữ nguyên từng ký tự (chỉ thêm thông báo); M1, M2, M7 đều đỏ (P4). Điều kiện "cửa sổ thứ hai" lành với M1: `bump` mất cập nhật mà bộ đếm cuối < trần thì mọi lượt đều đọc < trần → đủ `2 × trần` lượt 401 → thừa = trần ≠ giá trị cuối, nên chữ ký không thể trùng (P4: 3/3 "đếm sai").
- **Không mock dịch vụ, không đồng hồ thật trong test mới:** bốn file test thuần (core, storage keys, ml_contracts, hai test bộ kiểm C11); `monkeypatch` chỉ vá luật thuần để chốt một nguồn. C11_parallel và test `DEL` dùng Postgres/Redis thật như trước.
- **Ba dòng nợ đóng nói đúng sự thật:** NO-081, NO-082, NO-088 `✅` kèm ngày đóng; mọi con số đỏ/xanh (8→19, 16→16, 2→2, 7→7, 4→6), tên test, số ca và mô tả sửa trong dòng khớp P1/P2 và diff. Cột "Chủ" của NO-081 đã có B0-02 (điều kiện của review trước, đã làm trên `main`).

## Tuyên bố "lệch khỏi prompt" của tác giả

| # | Tuyên bố | Kết luận |
|---|---|---|
| 1 | FIX-060 đổi hai ca test cũ: tiền tố trần dời từ `_accepts` sang `_rejects`; ca `""` nay khớp "khoá rỗng" | **Đứng được, không nới.** [5] đòi `check_key(key)` ở dòng đầu; tiền tố có `/` cuối có đoạn rỗng nên không phải khoá — ca "accepts" cũ chính là hành vi NO-088 đòi đóng (FIX.md luật 2: test chốt hành vi mà [3] gọi là lỗi). Ca `""` vẫn đòi `ValueError`, chỉ đổi `match` sang thông báo của kiểm chạy trước, cụ thể như cũ. Người gọi duy nhất không đổi (P2, P3) |
| 2 | FIX-061 dời luật bước pipeline cùng bố cục, không `ask` | **Đứng được** — xem mục Ranh giới lõi |
| 3 | `run_prefix(upload_root, run, step)` nhận tiền tố lượt tải lên, không nhận ba id | **Đứng được** — `ml_contracts` chỉ có `page_key`; điều kiện trước ghi ở docstring, đầu ra qua `check_prefix` |
| 4 | FIX-063 giữ luật "`weights_key` dưới `MODELS_PREFIX`" của `TrainingFinishedPayload`; thông báo id nay của `check_id` | **Đứng được** — P3 (216 ca) lệch 0; không ai khớp chuỗi thông báo ngoài test |
| 5 | FIX-064 thêm vế `0 <` ("chặt hơn chữ [5] một vế") | **Đứng được, nhưng chữ "chặt hơn" chỉ đúng với nhãn.** Tập pass của bộ kiểm đổi từ {không mở ∧ bộ đếm ≥ trần ∧ chia đúng} (bản cũ) thành {không mở ∧ chia đúng}: [5] tự bỏ vế bộ đếm cho giá trị 1..trần−1, còn `0 <` bỏ nốt cho giá trị 0 (theo chữ [5], chia đúng 20/20 với `(0, −2)` sẽ bị gọi "cửa sổ thứ hai" và **đỏ**). Điều đó không nới hợp đồng C11: assert đếm chính xác giữ nguyên; "cửa sổ thứ hai nhận 0 lượt" không phải cửa sổ nào; với cửa sổ 360 s và loạt vài giây, bộ đếm < trần sau một loạt chia đúng chỉ có thể do khoá mất **sau** loạt — không phải lỗi C11. Lỗi thật gần nhất (M7: 429 xoá bộ đếm) vẫn đỏ 3/3 (P4), và M5 chứng minh vế `0 <` có test chốt |
| 6 | Không gộp `main` @ `5892c71` để đầu nhánh là đúng commit đã verify | **Đứng được** — `5892c71` chỉ đổi `DEBT.md`, `docs/fixes.md`; xung đột chỉ ở `DEBT.md` (điều kiện 1) |
| 7 | Nit #2 của review trước (bọc lỗi id của `upload_prefix_of`) không làm | **Đúng phạm vi** (FIX.md luật 3); review đó ghi "không cần dòng" |

## Sổ nợ (`DEBT.md`)

| Kiểm theo R-34, R-35, R-38 | Kết quả |
|---|---|
| Nợ nhánh đóng nói đúng sự thật | đạt — NO-081, NO-082, NO-088 (xem mục "đạt") |
| Mọi nợ tác giả nêu đều có dòng | đạt một phần — tác giả khai "không nợ mới"; phần mở rộng NO-079 (ba tên mới của lõi) chỉ nằm trong báo cáo → #1 |
| Nợ P0/P1 còn `⬜`/`🔧` do nhánh này | không |
| Nợ do review này chỉ ra đã có dòng | **chưa** — xem dưới (phiên này **không** tự ghi `DEBT.md`) |

Dòng đề xuất:

- Bổ sung vào cuối cột trạng thái của **NO-079**: `· Mở rộng 2026-09-22 (review merge \`fix/b0-04-layout-and-c11-debts\` finding #1): FIX-061 thêm vào lõi dùng chung \`packages/core/object_keys.py\` \`run_prefix(upload_root, run, step)\` (kèm luật bước ∈ \`PIPELINE_STEPS\`, dời từ \`storage\`), \`model_prefix(model)\` và hằng \`MODELS_PREFIX\` — dòng §2.2 ghi thêm ba tên (chủ B0-02 · gọi: B0-04, B5-01). Lõi nay giữ tiền tố của 4/7 dạng khoá BE-00 §8 (original, pages qua \`upload_prefix\`; \`runs/\`; \`ml/models/\`); \`library/\`, \`ml/datasets/\`, \`users/…/avatar/\` và mọi hàm dựng khoá đầy đủ ở \`packages/storage/keys.py\` — dời nốt hay giữ đường cắt "theo ai cần" là quyết định của dòng này`
- Nit #2: tác giả/chủ B0-02 tự quyết, không cần dòng.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 (FIX-060 đóng lỗ kiểm nửa khoá; khoá dựng ra vẫn qua `check_key`/`check_prefix`) | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 (C11_parallel vẫn bắt M1, M2, M7) | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 (P3 lệch 0/17 931) | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 (không đổi HTTP, schema, dây payload) | 0,50 |
| TEST – Kiểm thử | 7 % | 5 (mỗi FIX đỏ trước/xanh sau; mọi vế mới có đột biến chốt) | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 (P3 #1; Nit #2) | 0,12 |

Tổng: 1,25 + 0,75 + 0,75 + 0,50 + 0,50 + 0,50 + 0,35 + 0,25 + 0,12 = **4,97 / 5**

## PHÁN QUYẾT: APPROVE

Cổng thoát 0 trên lượt chạy độc lập (`EXIT=0` của shell bọc, khớp `mã thoát: 0` của log host), `2134 passed, 0 failed, 10 skipped` (10 skip hợp lệ), độ phủ đạt ở mọi gói bị chạm (`packages/core` 100 % / 100 %, `packages/storage` 99,63 % / 98,25 %, `packages/ml_contracts` 99,90 % / 99,56 %, `apps/api/auth` 98,61 % / 92,65 %; tập file bị chạm 100 % / 100 %), không có P0/P1/P2, điểm 4,97 ≥ 4,0. Cả năm FIX sửa đúng gốc và đúng phạm vi [4]: `upload_prefix_of` kiểm cả khoá; bố cục `runs/…/` và `ml/models/…/` (cùng luật bước) mỗi thứ còn một nguồn ở lõi, `storage` và `ml_contracts` cùng gọi và cùng đỏ khi đột biến nguồn đó; `_id_of` dùng `check_id`; bộ kiểm C11 gọi đúng tên "đếm sai" cho `bump` không nguyên khối trên Redis thật. Đỏ trước/xanh sau tự tái hiện đủ 8/16/2/7/4 ca đúng như dòng `DEBT.md`; hành vi payload không đổi trên 17 931 mẫu; không người gọi nào vỡ. Luật bước pipeline thuộc lõi (từ vựng `PIPELINE_STEPS` vốn ở `packages/core`, không kéo họ model ML xuống), và cả hai lệch tác giả tự khai (hai ca test FIX-060, vế `0 <` FIX-064) đều không nới assert hợp đồng.

Điều kiện cho phiên merge:

1. **Xung đột `DEBT.md` với `main` @ `5892c71`** (duy nhất, `git merge-tree`, một khối NO-087..NO-090): lấy **nguyên dòng** NO-087, NO-089, NO-090 của `main` (`🔧`, đã ghi FIX-065..067); lấy dòng NO-088 `✅` của nhánh. Mọi dòng khác hai bên đã trùng. Không file mã nào xung đột; `main` từ `67bf9bd` không đổi file nào cổng đọc — lượt verify tích hợp thường lệ sau gộp là đủ.
2. **Trước khi merge** (R-38): người điều phối ghi phần bổ sung NO-079 ở mục Sổ nợ (#1). Nit #2 không chặn merge.
3. Gộp bằng `git merge --no-ff` (R-36: nhánh mang trailer của B0-02, B0-04, B5-01 **và** B1-01 cùng `Fix: FIX-060..064`), **không** squash.
4. Điền sha vào cột "Commit" của `docs/fixes.md`: FIX-060 `225b4dc`, FIX-061 `2eaa822`, FIX-062 `4bdbbbe`, FIX-063 `e9d8f3f`, FIX-064 `d1913ec` (`--no-ff` giữ nguyên các sha này).
