# Review merge feature/b5-03-objects-detection → main

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (lượt 1) · Commit đầu nhánh: `dc3c8e3e9b8a`
  (cây `2e2cd5e8e56cdea9fccfff0297429beebce4a21e`)
- Phạm vi: `git diff main...HEAD` = `apps/ml/objects/**` (14 tệp) + `changes/B5-03.md`, 1 751 dòng thêm,
  0 dòng xoá. Không tệp cấm, không `uv.lock`, không `docs/charter`, không tệp nhị phân. Cây sạch.
- Cổng: phạm vi **đầy đủ** (R-33b điều kiện 1 — review lượt 1 của nhánh). **Không chạy lại**: đọc log
  của lớp gộp `backend/dieu-phoi/chay/B5-03/D/gate.log`, `D/gate.sha` = `dc3c8e3e…` khớp sha review.
  Mã thoát thật ghi trong log: **`mã thoát: 0`**.
- Độ phủ (từ `coverage_gate` trong chính log ấy): tổng dòng **99,54 %** · nhánh **98,31 %**;
  `apps/ml/objects` dòng **99,39 %** · nhánh **94,44 %**; tập tệp bị chạm 99,39 / 94,44. 6 517 test đạt
  (17 ph 11), `pytest -m perf` 2 test đạt.
- Tái hiện tại chỗ (1 container `verify-run`, `run.sh shell`): phản ví dụ nối hộp — xem finding #2.

## Bảng cổng (E.10, lấy từ mã thoát thật trong `D/gate.log`)

| # | Bước | Trạng thái |
|---|---|---|
| 0 | làm ấm node_modules | đạt |
| 1 | `ruff format --check` | đạt |
| 2 | `ruff check` | đạt |
| 3 | `mypy --strict` | đạt |
| 4 | `lint-imports` | đạt |
| 5 | `pytest -n` (cov) → `coverage_gate` | đạt |
| 5b | `pytest -m perf` → `case_gate` | đạt (perf: 2 test) |
| 6 | `lint_migrations` → `migrate_check` | đạt |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt |
| 8 | `openapi` | đạt |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | **P1** | TEST-01 / R-33 | Thiếu **hai nhóm case bắt buộc** của khối [8] "Theo việc": không có tệp test nào cho `labels.py` và `tiles.py`. Không chỗ nào khẳng định `ARTIFACT_LABELS = OBJECT_LABELS + other`, `COCO_LABELS` 80 phần tử đúng 6 chỉ số khác `None`, `labels_for` hai nhánh, `overlap_for(640) == 160`; **không có test `tile_windows` tham số hoá** (64×64 lát 64; 100×64; 1 000×700; 7 745×5 164 — phủ hết điểm ảnh, lát cuối sát mép, không trùng, hai lát kề chồng ≥ overlap) và **không có test `overlap_px ≥ tile_px` → `ValueError`**. Độ phủ 94,44 % nhánh không bắt được vì `tiles.py` chỉ chạy gián tiếp qua `detector`. Cổng cũng không bắt được: tên "theo việc" không mang mã case nên `case_gate` không đòi. Khối [1] nói rõ **B6-04b cắt dataset bằng đúng hai hàm này** — lưới lát sai sẽ hỏng dataset huấn luyện mà không ai thấy | `apps/ml/objects/tests/` (thiếu `test_labels.py`, `test_tiles.py`); guard chưa chạy: `tiles.py:41-44` | Thêm `test_tiles.py` tham số hoá đúng 4 khổ của [8] + hai case `ValueError`, và `test_labels.py` cho bốn khẳng định nhãn của [8] |
| 2 | **P2** | LOG-01 / R-19 | Nối hộp bị lát cắt **không tương đương** khối [6] bước 4 "lặp tới khi không còn cặp nào": ma trận kề tính **một lần** trên hộp gốc rồi gộp theo thành phần liên thông. Docstring khẳng định tương đương ("cạnh chỉ phụ thuộc hộp gốc, không đổi qua các vòng nối") — **khẳng định này sai**: điều kiện (a) đọc *diện tích hộp*, mà hộp bao sau khi nối là hộp mới. Phản ví dụ đã chạy thật (`merge_candidates`, trang 1 000×1 000, 3 ứng viên cùng nhãn, 3 lát khác nhau): A `[100,0,500,100]` + B `[500,0,900,100]` nối qua (b) → AB `[100,0,900,100]`; C `[400,0,600,100]` có giao/dt-nhỏ với A = 0,50 và với B = 0,50 (< 0,70, không kề ở lượt gốc) nhưng với **AB = 1,00** (≥ 0,70). Bản này trả **2 hộp**, luật prompt trả **1**. `merge_candidates` là API công khai (`__init__.py:19`), B6-04b dùng lại | `apps/ml/objects/detector.py:288-308` (docstring sai ở `:293-294`), `:311-334` | Hoặc lặp thật tới điểm bất động (tính lại kề trên hộp bao, lát nguồn là hợp các lát), hoặc giữ một lượt nhưng **viết lại docstring cho đúng** là một xấp xỉ bảo thủ và xin waiver + một dòng `DEBT.md` |
| 3 | **P2** | R-01 | ~27 hàm thiếu docstring, gần như toàn bộ trong test: `test_detector.py:17,70,77,84,91,98,105,112,119,126,132,138,167,174,181`; `test_detector_postprocess.py:24,29,38,44,50,59,79,109,121,133`; `test_perf.py:29`; `test_tasks.py:220`; và hàm lồng `find` trong mã sản phẩm. Cùng lớp với NO-122 (đã chấm P2 ở B2-05a). Ruff không bắt vì `D` không nằm trong `select` | như trên; mã sản phẩm: `apps/ml/objects/detector.py:298` | Thêm docstring một dòng cho từng hàm |
| 4 | P3 | TEST-05 | Khối [6] bước 3 và [8] đòi log `objects_model_inactive` kèm `run_id` khi `ModelRef` không trỏ model. Mã có (`tasks.py:64`) nhưng **không test nào khẳng định** — test chỉ kiểm `completed` + artifact rỗng. Worker thử B0-05 chạy trong chính tiến trình pytest nên `caplog` bắt được | `apps/ml/objects/tests/test_tasks.py:402-411` | Thêm `caplog` khẳng định bản ghi `objects_model_inactive` có `run_id` |
| 5 | P3 | R-07 | `test_objects_detect_sends_one_failed_message_not_two` trùng **nguyên xi** `test_objects_detect_rejects_another_family` (cùng payload `step="wallSegmentation"`, cùng khẳng định). [8] đòi *spy `send_task` đếm đúng một `failed`* cho `PermanentError` **và** cho `TASK_TIMEOUT`; bản này chỉ dựa vào `(result,) = results(...)` | `test_tasks.py:414-429` vs `:392-399` | Gộp làm một, hoặc đổi thành spy `send_task` thật phủ cả hai loại lỗi |
| 6 | P3 | R-07 | `MODEL_VERSION_FAMILY_MISMATCH` khai cục bộ **lần thứ ba** (`walls`, `text`, nay `objects`). B5-03 **không được** sửa (`apps/ml/runtime/**` nằm trong khối [12]) → đây là **nợ**, không phải lỗi của nhánh. NO-285 đang mở nhưng chỉ kể hai nơi | `apps/ml/objects/tasks.py:33` | Người điều phối cập nhật NO-285 thêm `apps/ml/objects/tasks.py:33`; FIX thuộc chủ B5-01 |
| 7 | P3 | MNT-02 | `decode_tile` nhận `input_px` và **không dùng tới**. Chữ ký do khối [5] quy định nên giữ là đúng, nhưng người đọc tưởng vùng đệm được trừ bằng tham số này (thực ra trừ bằng `window`) | `apps/ml/objects/detector.py:127-167` | Một dòng docstring nói rõ tham số giữ cho hợp đồng [5], vùng đệm kẹp bằng `window` |
| 8 | Nit | LOG | Điều kiện (b) không đòi hai lát **kề nhau**: hộp chạm mép phải của lát k và hộp chạm mép trái của lát k+5, cùng nhãn, chiếu y IoU ≥ 0,7 → nối thành một hộp khổng lồ. Đúng nguyên văn [6] nên không tính là lệch | `apps/ml/objects/detector.py:273-282` | Nếu B5-05 thấy hộp quá khổ, thêm điều kiện khoảng cách ≤ overlap và sửa hiến chương |
| 9 | Nit | TEST | Hộp B `[10,10,40,40]` khai thuộc lát `(640,0,640,640)` — nằm hoàn toàn ngoài lát của chính nó, dữ liệu không thể có thật; test vẫn đúng ý (chỉ thử điều kiện (a)) nhưng dễ gây hiểu nhầm | `test_detector_postprocess.py:66-76` | Đặt hộp trong lát khai báo |
| 10 | Nit | R-12 | `# type: ignore[arg-type]` và `# noqa: S603` có mã nhưng thiếu lý do (lớp NO-122) | `test_detector.py:129`, `test_tasks.py:321` | Thêm lý do sau mã |

## Lệch khỏi prompt — phán quyết từng cái

| Lệch | Phán |
|---|---|
| `ModelRef` không trỏ model viết bằng `ModelRef.is_classic` | **Chấp nhận**. `payloads.py:92-94`: `is_classic` = `pinned_name is None and weights_key is None` — đúng nguyên văn [6] bước 3 |
| `cases.toml` không khai `M01`–`M04` | **Chấp nhận, đã tự kiểm mã cổng**. `tools/case_gate.py:296` `_TEST_TASK_RE` chỉ nhận mã dạng `J` hai chữ số cho test task; khai `M0x` sẽ thành `HỎNG task: … thiếu [M01…]` vĩnh viễn. `tools/**` nằm trong [12]. Tiền lệ `apps/ml/walls/cases.toml` + NO-256. Bốn test `test_objects_detect__M01`, `__M02`, `__M03`, `__M04` **có mặt và đạt** (`test_tasks.py:244,277,296,357`; 6 517 đạt). Ghi chú: `case_gate` chỉ in dòng task khi **hỏng**, nên không có dòng `objects_detect` trong log là đúng, không phải thiếu |
| `COCO_TO_LABEL` khoá theo tên → bảng chỉ số ở `labels.py`; `ARTIFACT_LABELS` làm phẳng `get_args`; `check_labels` ở `labels.py` | **Chấp nhận**. Cả ba là hệ quả bắt buộc của kiểu B5-01, `packages/ml_contracts` nằm trong [12]. Nhưng xem finding #1: đúng vì thế mà bảng nhãn **càng cần** test riêng |
| `tiles.py:36` do nhánh C sửa (RUF002) | **Chấp nhận**. Cùng prompt B5-03, cùng thư mục sở hữu — không vi phạm R-27 |
| Nối hộp một lượt union-find | **LỆCH THẬT** — xem finding #2, phản ví dụ đã tái hiện |
| `merge_candidates` nhận `page_w`/`page_h` tường minh | **Chấp nhận**. Cần thiết để điều kiện "mép trong" phân biệt được mép lát với mép trang |

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 3 | 0,45 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 1 | 0,07 |
| OBS, OPS – Vận hành | 5 % | 4 | 0,20 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,31 / 5** |

Điểm 4,31 nhưng có một finding **P1** chưa waiver → theo ma trận `RULE.md` §5, quyết định là
REQUEST CHANGES.

## PHÁN QUYẾT: REQUEST CHANGES

Chất lượng mã sản phẩm cao: model người dùng chỉ đi qua `load_onnx`, kiểm hình dạng vào/ra ngay ở
`__init__` trước khi đọc trang, không đọc metadata ONNX, không `except Exception`, không `torch`/
`ultralytics` (có test tiến trình con), hậu xử lý mảng hoá hoàn toàn (K28), suy luận luôn CPU và
`gpu_slot` có spy chặn, phân loại lỗi tạm/vĩnh viễn đúng, J06 khẳng định cùng bytes. Cổng xanh thật
(mã thoát 0), độ phủ trên ngưỡng ở cả hai chiều, không `pragma`/`skip`/`xfail`/hạ ngưỡng, không tệp
nhị phân, không đụng tệp cấm.

Chặn merge vì **finding #1**: hai nhóm case bắt buộc của khối [8] ("Nhãn" và "`tile_windows` tham số
hoá") không tồn tại — `apps/ml/objects/tests/` không có `test_labels.py` lẫn `test_tiles.py`. Không
cổng nào bắt được lỗ này (tên "theo việc" không mang mã case; độ phủ dòng cao vì `tiles.py` chạy gián
tiếp qua `detector`), mà chính hai hàm ấy là thứ B6-04b dùng để cắt dataset huấn luyện; guard
`overlap_px ≥ tile_px` chưa từng chạy một lần nào.

**Để được `APPROVE` ở lượt 2, cần đúng ba việc:**

1. Thêm `apps/ml/objects/tests/test_tiles.py` (tham số hoá 4 khổ của [8] + hai case `ValueError`) và
   `test_labels.py` (`ARTIFACT_LABELS`, `COCO_LABELS` 80 phần tử / 6 khác `None`, `labels_for` hai
   nhánh, `overlap_for`) — finding #1.
2. Xử finding #2: lặp tới điểm bất động, **hoặc** giữ một lượt nhưng sửa docstring
   `detector.py:293-294` cho đúng (xấp xỉ bảo thủ, không phải tương đương) và ghi một dòng `DEBT.md`.
3. Thêm docstring cho ~27 hàm ở finding #3.

Finding #4–#7 nên làm luôn trong cùng vòng sửa (rẻ); #8–#10 là Nit, không chặn. Finding #6 không phải
việc của B5-03: người điều phối cập nhật NO-285.
