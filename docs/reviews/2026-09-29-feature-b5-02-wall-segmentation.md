# Review merge feature/b5-02-wall-segmentation → main

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `2000d17f63c0`
  (cây `233333e176cd`) — chỉ review đúng sha này, vòng sửa sau do lượt 2 soát.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1, lượt 1) — `bash tools/verify/run.sh verify`
  mã thoát **0**, 8/8 bước `đạt`
  (log: `F:/AppBack/backend/dieu-phoi/chay/B5-02/E/gate.log`, `E/gate.sha` = `2000d17f63c0…`).
  Reviewer **không** chạy lại cổng đầy đủ; tự tái hiện hai nghi vấn bằng lệnh đích trong
  `run.sh shell` (1 container mỗi lượt, không quá 2 đồng thời).
- Độ phủ (từ `coverage_gate` của chính lượt cổng đó): tổng dòng 99,55% · nhánh 98,36%;
  `apps/ml/walls` 99,42%/96,15%; `packages/vision` 99,63%/98,68%; tập file bị chạm
  98,97%/96,32%. Test: **6472 passed** (`pytest -n`, 632 s) + **5 passed** ở lượt `-m perf`.

## Bảng cổng (E.10, mã thoát thật)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | ruff format --check | đạt |
| 2 | ruff check | đạt |
| 3 | mypy --strict | đạt |
| 4 | lint-imports | đạt |
| 5 | pytest -n (cov) → coverage_gate | đạt |
| 5b | pytest -m perf → case_gate | đạt (perf: 5 test) |
| 6 | lint_migrations → migrate_check | đạt |
| 7 | H1 H3 H4 H5 (tools.contract.check) | đạt |
| 8 | openapi | đạt |

Mã thoát cuối: **0**.

## Phạm vi diff

`git diff main...HEAD` = 27 file, 2419 dòng thêm, **0 dòng xoá**, tất cả trong
`packages/vision/walls/**`, `apps/ml/walls/**`, `changes/B5-02.md`. Không file nhị phân
(`--numstat` không có dòng `-`), không đụng file cấm ([12], B0-01 [7]), cây làm việc sạch.

## Đối chiếu các "Lệch khỏi prompt" đã khai

| # | Lệch | Phán |
|---|---|---|
| 1 | `ModelRef.is_classic` thay `version_id is None and pinned_name is None` | **chấp nhận** — `packages/ml_contracts/payloads.py:92` định nghĩa `is_classic` = `pinned_name is None and weights_key is None`, và `_one_form` (dòng 96–103) buộc dạng cổ điển có `version_id is None`; hai vế tương đương, dùng thuộc tính là một nguồn sự thật (R-07) |
| 2 | `cases.toml` chỉ `require = ["J03","J08"]`, bỏ M01/M02 | **chấp nhận** — `tools/case_gate.py:296` `_TEST_TASK_RE` chỉ nhận `J\d{2}`; khai M01/M02 sẽ đòi một case cổng không bao giờ thấy. `tools/**` nằm trong [12]. NO-256 đã mở (`DEBT.md:277`). Kiểm: `test_segment_walls__M01`, `__M02` **có thật** (`apps/ml/walls/tests/test_tasks.py:189,206`) và nằm trong 6472 test qua. Lý do ghi ngay trong `cases.toml:3-10` |
| 3 | `MODEL_VERSION_FAMILY_MISMATCH` khai cục bộ (`apps/ml/walls/tasks.py:32`), trùng `apps/ml/text/tasks.py:33` | **nợ, không chặn** — `apps/ml/runtime/errors.py` thuộc B5-01, K27 cấm sửa file prompt khác; đã ghi chú ngay trong docstring hằng. Thiếu dòng `NO-<nnn>` trong `DEBT.md` → finding #3 |
| 4a–4d | Việc A tự chỉnh vector hoá (`_SPUR_TIP_RATIO`, DP khép kín cho vòng, hấp thụ đoạn vát góc, đo "ngắn hơn bề dày" trước bước kéo dài) | **chấp nhận cả bốn** — mỗi cái có lý do đo được trong `bao-cao-A.md` và có chú thích tại chỗ (`vectorize.py:36-43`, docstring `_branch_segments`, docstring `_drop_short`). (b) và (d) là điều kiện cần để hai ca bắt buộc của [8] đúng (khung 4 đoạn/4 góc; ô 12×12 cô lập → 0 đoạn, `short == 1`). (a) là hằng đo trên một seed — hạn chế đã tự khai; đo lại 10 seed ở `test_opening_gaps.py` vẫn đạt |
| 5 | `RgbImage` của preprocess có `.pixels`; `run_id` thêm vào `segment_page`; `decode_mask` cần `width_px`/`height_px` | **chấp nhận** — cả ba là chữ ký **thật** của mã đã hợp nhất, prompt nói rõ lệch với B5-01/B2-05a thì theo mã thật. `CheckedRgbImage(image)` (`step.py:94`) chỉ bọc view chỉ đọc, không chép điểm ảnh, và `RgbImage.__post_init__` đặt `writeable=False` trên **view**, không sửa mảng của `run_step` |
| 6 | Việc B: IoU đường lùi trung bình 0,8152 (ngưỡng 0,80); `test_boundary.py` từng có `pytest.skip` | **skip đã bỏ thật** — `packages/vision/walls/tests/test_boundary.py` không còn `pytest.skip`, `_MODULES` liệt đủ 5 module con, commit `2000d17` nói đúng việc đó (K24 sạch). IoU 0,8152 là biên hẹp → nợ, xem finding #3 |

## Tự tái hiện (lệnh đích, `run.sh shell`)

1. **Nghi vấn vòng lặp vô hạn ở `_resolve`** (`packages/vision/walls/vectorize.py:388`): hai đoạn
   của một vòng kín 2 đỉnh về lý thuyết có thể đặt `alias[k1]=k0` và `alias[k0]=k1`. Dựng thẳng ca
   đó + 5 mặt nạ vành khuyên (`cv2.circle` r=10,14,18,24,30) với `SIGALRM` 5–20 s: **không treo** —
   `_resolve` chỉ chạy trên danh sách `keep`, mà hai khoá của vòng kín là riêng của nhánh đó nên
   không đoạn giữ lại nào chạm tới chúng. Không phải finding.
2. **Hai ô trống của ma trận [8]** (finding #1, #2): chặn `packages.ml_contracts` rồi nhập
   `packages.vision.walls{,.vectorize,.classic}` trong tiến trình con → **thoát 0**;
   `find_frame(RgbImage(render_plan(s).pixels))` trên seed 0–9 **và** toàn bộ `EVAL_SET_SEEDS`
   → **không seed nào khác `None`**. Tức hai ô thiếu là **thiếu test**, không phải lỗi mã;
   bổ sung là việc rẻ và an toàn.

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | TEST-01 / R-01 | Ca "Ranh giới" của [8] đòi nhập `packages.vision.walls` khi **`packages.ml_contracts`** (ngoài `torch`, `onnxruntime`, `celery`, `sqlalchemy`) bị chặn. `_BLOCKED` thiếu đúng mục ấy, trong khi docstring `_run` khẳng định "với `ml_contracts` bị chặn" — docstring sai sự thật (R-01). Ranh giới thực tế vẫn kín (tự kiểm, thoát 0), nên đây là ô trống + docstring lệch | `packages/vision/walls/tests/test_boundary.py:14`, `:37` | Thêm `"packages.ml_contracts"` vào `_BLOCKED` (nó tự vào cả `test_blocking_really_raises`), sửa docstring cho khớp danh sách |
| 2 | P2 | TEST-01 | Ca "Khung" của [8] (`find_frame` trên `RgbImage` dựng từ `render_plan(s).pixels` trả `None` với seed 0–9 — có seed 7 của e2e B5-07 — và mọi `EVAL_SET_SEEDS`) **không có** trong nhánh: không file nào trong diff nhắc `find_frame`. Đây là hàng rào chống hồi quy cho B5-07; tự kiểm hôm nay đạt nhưng không ai giữ | thiếu ở `packages/vision/walls/tests/` (ví dụ `test_frame.py`) | Thêm một test tham số hoá seed 0–9 + `EVAL_SET_SEEDS`, assert `find_frame(...) is None` |
| 3 | P2 | MNT-07 / R-34 | Mọi nợ tác giả nêu trong báo cáo đều **chưa** có dòng `DEBT.md`: (a) `MODEL_VERSION_FAMILY_MISMATCH` khai trùng ở `apps/ml/walls/tasks.py:32` và `apps/ml/text/tasks.py:33`, nên về `apps/ml/runtime/errors.py` (chủ B5-01); (b) IoU đường lùi trung bình 0,8152 chỉ cách ngưỡng 0,80 ~0,015, seed 104/106/107 chỉ 0,70–0,75 — `synthetic.py` đổi là cổng đỏ; (c) `cv2` lệch tâm 1 px khi `MORPH_RECT` k chẵn (test né bằng k=11 lẻ, có chú thích `test_classic.py:12`) | `DEBT.md` (ngoài whitelist của worker → việc của người điều phối) | Thêm 3 dòng `NO-<nnn>` lúc merge; riêng (b) để P2 vì đó là cổng có thể đỏ do prompt khác |
| 4 | P3 | MNT-05 | 4 commit merge trên nhánh (`ef4837c`, `aa51347`, `1614f49`, `4a07e35`) có dòng đầu `Merge branch …`, không theo Conventional Commits. Không chặn: người điều phối gộp vào `main` bằng **squash** nên `main` chỉ nhận một dòng đầu đúng mẫu; 7 commit thường đều đúng mẫu và đều có trailer `Prompt: B5-02` | `git log main..HEAD` | Giữ nguyên; chỉ cần bảo đảm merge là squash |

Không có P0, không có P1.

## Những chỗ đã soát và **đạt**

- **Vector hoá [6] bước 1–11**: đủ cả 11 bước ở `vectorize.py` (đồ thị 8 hướng `_neighbours`/
  `_label_nodes`, gộp cụm giao bằng `connectedComponents` + trọng tâm; `_prune_spurs` lặp tới ổn định;
  ε = `max(1.5, 0.25 × trung vị bề dày)`; bề dày = `2 × trung vị distance`; `_snap_axis` ≤ 5°;
  `_collinear` ≤ 2° và ≤ ½ bề dày; `_place_shared` đặt lại **mọi** đầu mút dùng chung; `_extend_leaves`
  kéo dài đầu bậc 1 thêm distance; `_clamp`; `short`; `_finalise` làm tròn 2/2/3 chữ số, `start ≤ end`,
  sắp theo `(start, end)`). Tất định: không random, không thứ tự phụ thuộc hash trong đường quyết định.
  Không vòng Python theo điểm ảnh (K28) — mọi vòng đi theo **nhánh**/**điểm xương**, phần nặng là
  numpy/cv2; đo thật 1,36 s cho trang 40 M điểm.
- **Mask cổ điển**: BT.601 qua `cv2.cvtColor(COLOR_RGB2GRAY)` → `THRESH_BINARY_INV + THRESH_OTSU` →
  `MORPH_OPEN` `MORPH_RECT` k×k; `min_thickness_px < 1` → `ValueError`; công thức
  `default_min_thickness_px` đúng cả hai nhánh, ba giá trị hợp đồng (3, 11, 5) có test.
  Không sửa ảnh vào (test khẳng định `array_equal` trước/sau). IoU 10 seed **0,8152 ≥ 0,80** đo thật,
  ngưỡng `_MIN_MEAN_IOU = 0.80` không bị hạ, từng số in bằng `logging`.
- **Ghép lát**: `__init__` kiểm số lượng + `type == "tensor(float)"` + hình vào `[1,3,1024,1024]`,
  ra `[1,2,256,256]`, **không** dựa tên (`self._input`/`self._output` chỉ lấy sau khi đã kiểm);
  `tile_origins` đúng `(0,)`, `(0,)`, `(0,896,976)`; đệm `PAD_VALUE = 255`; hiệu logit `lớp 1 − lớp 0`
  phóng ×4 `INTER_LINEAR`; `accum/counts > 0`; `ORT_ERRORS` (không `except Exception`) →
  `MODEL_FORMAT_UNSUPPORTED`. `spec.py` chỉ numpy (có test tiến trình con chặn `onnxruntime`+`torch`).
  ONNX tí hon dựng bằng `onnx.helper` trong `tests/onnx_fixtures.py` — không commit nhị phân.
- **Lõi/task**: `_prepare` kiểm `payload.step` **trước** `run_step` nên trang chưa bị đọc
  (`test_prepare_rejects_a_payload_of_another_family` + ca task đầu-cuối); chọn fake > classic > onnx
  đúng thứ tự; mask khác khổ → `MODEL_FORMAT_UNSUPPORTED`; `keep_longest` + khoá `cap` luôn có
  (kể cả khi bằng 0); `_capped` kẹp `confidence ≤ 0,5` **chỉ** nhánh classic; artifact tất định
  (J06 so từng byte, M01 hai lượt); log `walls_segmented` có `run_id`/`used`/`walls`/`dropped`/3 mốc
  thời gian và **không** có `page_key`/`artifact_prefix` (có test khẳng định); `on_failed=step_failed`.
  Ma trận J01, J01_onnx, J03, J06, J08, M01, M02 đủ, Redis thật + `celery_worker_factory(["ml.infer"])`
  + `local_storage` + `LRANGE pipeline.cpu`, không mock broker/kho/phiên ONNX (K23).
- **Ranh giới nhập**: `packages/vision/walls/*` chỉ nhập `cv2`, `numpy`, `skimage`,
  `packages.vision.preprocess.types` — không `ml_contracts`/`messaging`/`storage`/`db`/`apps.*`,
  không đọc biến môi trường; `lint-imports` (bước 4) đạt.
- **R-01/R-07/K24**: docstring có ở **mọi** hàm và lớp (kiểm từng file); hàm dài nhất
  (`segment_page`, 47 dòng) dưới trần 50; không `pragma: no cover`, không `skip`/`xfail`,
  `# noqa: S603` và `# type: ignore[...]` đều có mã + lý do; không hạ ngưỡng nào.
- **SEC**: bước không có endpoint, không đọc DB, không `send_task` ngoài `run_step`/`on_failed`;
  ảnh chỉ qua `run_step`, model chỉ qua `load_onnx` (M02 chứng minh `_session` không được dựng khi
  checksum lệch); mã lỗi không tiết lộ chi tiết model (`_unsupported()` trơ).

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25% | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15% | 5 | 0,75 |
| LOG – Tính đúng đắn | 15% | 5 | 0,75 |
| PERF – Hiệu năng | 10% | 5 | 0,50 |
| RES – Chịu lỗi | 10% | 5 | 0,50 |
| DB, API – Migration & contract | 10% | 5 | 0,50 |
| TEST – Kiểm thử | 7% | 3 | 0,21 |
| OBS, OPS – Vận hành | 5% | 5 | 0,25 |
| MNT – Bảo trì | 3% | 4 | 0,12 |
| **Tổng** | **100%** | | **4,83 / 5** |

Ma trận `RULE.md` §5: không P0, không P1, điểm ≥ 4,0 → **APPROVE**.

## PHÁN QUYẾT: APPROVE

Nhánh đạt cổng đầy đủ thật (mã thoát 0, 8/8 bước, 6472 test, độ phủ mọi gói bị chạm ≥ 96%
dòng **và** nhánh), diff nằm trọn trong quyền sở hữu của B5-02, và cả sáu "Lệch khỏi prompt"
đều có lý do đứng được — bốn chỉnh sửa thuật toán của việc A là điều kiện cần để chính ma trận
[8] đúng, ba "lệch" còn lại chỉ là bám theo chữ ký thật của B5-01/B2-05a. Hai nghi vấn nặng
nhất của lượt này (vòng lặp vô hạn ở `_resolve`; ranh giới nhập có thật sự kín không) đã tự
tái hiện bằng lệnh đích và **không** thành finding. Ba P2 còn lại đều là ô trống về **bằng
chứng**, không phải lỗi hành vi: hai ca của [8] thiếu test (đã tự kiểm là đang đúng) và ba nợ
chưa có dòng `DEBT.md`.

Điều kiện khi merge (không chặn `APPROVE`, nhưng phải làm):
1. Người điều phối thêm ba dòng `NO-<nnn>` cho finding #3 vào `DEBT.md` — riêng (b) IoU 0,8152
   nên để P2 vì nó là cổng có thể đỏ khi prompt khác đổi `synthetic.py`.
2. Giao FIX cho chủ `packages/vision/walls/tests/` bổ sung finding #1 và #2 (hai test, ~20 dòng).
3. Merge bằng **squash** để `main` chỉ nhận một dòng đầu đúng mẫu (finding #4).
