# Review merge feature/b5-03-objects-detection → main — lượt 2

- Ngày: 2026-09-29 · Reviewer: phiên /merge-review (cùng phiên đã làm lượt 1) · Commit đầu nhánh:
  `f432955659eb`
- Lượt 1: `docs/reviews/2026-09-29-feature-b5-03-objects-detection.md` (REQUEST CHANGES, 4,31/5) ·
  bản đầy đủ `backend/dieu-phoi/chay/B5-03/bao-cao-review-1.md`
- Phạm vi lượt này: **chỉ vòng sửa** `dc3c8e3e9b8a..f432955659eb` — 5 commit (`9672fd2` test nhãn/lát,
  `43c1cae` gộp nhánh `feature/b5-03-labels-tiles`, `aa73c21` xử finding lượt 1, `3c701d9` dấu nhân
  trong docstring, `f432955` tách ma trận nối theo nhóm nhãn), 10 tệp, +442 / −29 dòng. Vẫn chỉ trong
  `apps/ml/objects/**`, không tệp ngoài phạm vi, không tệp cấm, không tệp nhị phân. Cây sạch.
- Cổng: phạm vi **đầy đủ** (lớp gộp chạy lần 3 trên đúng `f432955…`, `D/gate-3.sha` khớp).
  Không chạy lại. Mã thoát thật: **xem bảng E.10**.
- Tái hiện tại chỗ, 1 container `run.sh shell` (đếm trước: 1 container `verify-run` của cổng lần 3 đang
  chạy → đúng trần 2): log `backend/dieu-phoi/chay/B5-03/R/counter2.log`.

## Bảng cổng lần 3 (E.10, mã thoát thật trong `D/gate-3.log`)

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

Dòng cuối log: `mã thoát: 0` · `EXIT=0` (dòng 511-512). Không bước nào "chưa chạy" hay
"không áp dụng".

- **Test**: 6 555 đạt / 12 ph 30 (lượt 1: 6 517 → **+38 test** của vòng sửa); `pytest -m perf`
  2 đạt.
- **Độ phủ**: tổng dòng **99,55 %** · nhánh **98,34 %**; `apps/ml/objects` dòng **100,00 %** ·
  nhánh **96,55 %**; tập tệp bị chạm 100,00 / 96,55. Lượt 1 là 99,39 / 94,44 → cả hai số đều tăng,
  dòng đạt trần. Không `pragma`, không hạ ngưỡng.
- `case_gate: đạt` (77 thao tác đã mount, 3 cảnh báo BE-BIND cũ của `files_read_object`,
  `health_live`, `health_ready` — không liên quan B5-03).

## Tái hiện

Chạy lại **chính phản ví dụ** của finding #2 lượt 1, thêm ba phép kiểm mới, trong container
(`/work/venv-b5-03-objects-detection/bin/python`):

```
PHAN-VI-DU: n = 1 -> mong doi 1
    [100.   0. 900. 100.] 0.9 0
TAT-DINH: True
NHAN: [(0, (100.0, 0.0, 900.0, 100.0), 0.9), (3, (100.0, 200.0, 900.0, 300.0), 0.6)]
PERF merge_candidates 3000 -> 2000 trong 0.778s (tran 2.0s)
66 passed, 8 warnings in 4.80s
```

- **Phản ví dụ lượt 1 giờ ra đúng một hộp** `[100,0,900,100]`, điểm 0,9 — vòng lặp tới điểm bất động
  bắt được cặp (AB, C) mà bản một lượt bỏ sót. Finding #2 **đã sửa thật**.
- **Tất định**: ba lượt `merge_candidates` trên cùng đầu vào ra hệt nhau (hộp, điểm, nhãn).
- **Nhãn của hộp sau nối**: hai nhóm nhãn (0 và 3) nối song song, mỗi nhóm giữ đúng nhãn và điểm max
  của nhóm mình, không lẫn sang nhau — việc tách ma trận theo nhãn (`f432955`) không đổi kết quả.
- 66 test của 6 tệp không cần Redis đạt, chạy với `-W error::RuntimeWarning`: `tiles` đặt `NaN` không
  sinh cảnh báo numpy nào.

## Finding lượt 1 → trạng thái

| # | Mức | Mô tả ngắn | Trạng thái | Bằng chứng |
|---|---|---|---|---|
| 1 | P1 | Thiếu hai nhóm case [8]: `labels`, `tile_windows` | ✅ **đã xử** | `test_tiles.py` mới (128 dòng): 4 khổ của [8] tham số hoá × phủ hết điểm ảnh / lát cuối sát mép / không trùng / hai lát kề chồng ≥ overlap / thứ tự hàng-rồi-cột, cạnh ≤ tile ra một vị trí, **6 case `ValueError`** (khổ 0, lát 0, overlap = tile, overlap > tile, overlap < 0), `overlap_for(640) == 160`. `test_labels.py` mới: `ARTIFACT_LABELS == DETECTION_LABELS`, `COCO_LABELS` 80 phần tử với đúng 6 chỉ số khác `None` (56/57/59/60/61/71), `labels_for` **hai nhánh** bằng `is`, `check_labels` cả hai chiều. Thêm `test_onnx_models.py` (không đòi ở [8]) phủ helper ONNX chạy thật |
| 2 | P2 | Nối hộp một lượt ≠ "lặp tới khi không còn cặp nào"; docstring khẳng định tương đương là sai | ✅ **đã xử, đã tái hiện** | `_merge_cut_boxes_to_fixed_point` (`detector.py:346-360`) lặp tới khi ma trận kề rỗng; `_union_round` gộp từng vòng; docstring `_connected_components`/`_union_round` viết lại đúng (nói rõ "hộp bao sau khi nối có diện tích khác hộp gốc, nên một lượt không đủ"). Có **test hồi quy đúng phản ví dụ của review**: `test_merge_candidates__joins_indirect_chain_through_intermediate_merge`. Tôi chạy lại phản ví dụ độc lập: 1 hộp (trước là 2) |
| 3 | P2 | ~27 hàm thiếu docstring (R-01) | ✅ **đã xử** | Docstring thêm cho toàn bộ danh sách lượt 1: 15 hàm `test_detector.py`, 10 `test_detector_postprocess.py`, `test_perf.py:29` `__init__`, `test_tasks.py:220` `timing_out`, hàm lồng `find` (`detector.py:301`), cộng `helpers.py` `read` và `test_tasks.py` `spying`. Soát tĩnh của điều phối trên `f432955` cũng cho 0 thiếu |
| 4 | P3 | Log `objects_model_inactive` không được test | ✅ **đã xử** | `test_tasks.py:404-423`: `caplog.at_level(logging.INFO, logger="apps.ml.objects.tasks")`, khẳng định có bản ghi `objects_model_inactive` **và** `record.run_id == payload.run_id` |
| 5 | P3 | Test "không gửi hai lần" trùng nguyên xi test họ sai | ✅ **đã xử** | Viết lại: gửi cả hai payload (họ sai → `PermanentError`, `_detect` quá hạn → `TASK_TIMEOUT`) trong một worker, đếm **đúng 1** thông điệp mỗi lượt. Lý do không spy `send_task` được nêu đúng: `run_step(… send: Send = send_task)` ràng buộc giá trị lúc định nghĩa, `monkeypatch.setattr` module không đổi được — đã tự kiểm chữ ký. Còn một Nit, xem #N2 |
| 6 | P3 | `MODEL_VERSION_FAMILY_MISMATCH` khai trùng lần ba | ⏳ **không phải việc nhánh này** | `apps/ml/runtime/**` nằm trong khối [12]; vẫn là nợ NO-285 của chủ B5-01. Không đổi, đúng như phán quyết lượt 1 |
| 7 | P3 | `decode_tile` nhận `input_px` không dùng | ✅ **đã xử** | `detector.py:138-141`: ba dòng docstring nói rõ tham số giữ cho hợp đồng [5], vùng đệm trừ bằng `window` |
| 8 | Nit | Điều kiện (b) không đòi hai lát kề | ⏳ **không xử** (đúng nguyên văn [6], không chặn) | Không đổi; vẫn là đề xuất sửa hiến chương, không phải lỗi nhánh |
| 9 | Nit | Hộp test nằm ngoài lát khai báo | ✅ **đã xử** | `test_detector_postprocess.py:66`: lát của hộp B đổi thành `(0,0,100,100)`, hộp `[10,10,40,40]` nằm trong lát của chính nó |
| 10 | Nit | Hai suppression thiếu lý do | 🔸 **xử một nửa** | `test_tasks.py` `# noqa: S603 — lệnh cố định, chạy chính Python của venv` ✅; `test_detector.py:141` `# type: ignore[arg-type]` vẫn không có lý do sau mã — có dòng `# cố ý sai kiểu để test check_labels ở runtime` ngay trên, nên ý đã rõ, chỉ là chưa đúng khuôn. Không chặn |

Không finding nào của lượt 1 bị "xử sai": mọi bản sửa đều đúng gốc vấn đề, không vá triệu chứng, không
hạ ngưỡng, không thêm `skip`/`xfail`/`pragma`.

## Finding mới lượt 2

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| N1 | Nit | OBS-02 | `_union_round` đặt `tiles = NaN` cho nhóm đã nối. Docstring giải thích tác dụng "luôn khác lát", nhưng **không nói tác dụng thứ hai**: trong `_cut_edge_touches`, `tile_x > 0` và `np.abs(x1 - tile_x) <= 2` với `NaN` đều là `False`, nên **điều kiện (b) không bao giờ áp dụng cho hộp đã nối** ở các vòng sau. Hệ quả này vô hại (chuỗi nối thuần (b) đã bị thành phần liên thông bắt hết ngay vòng 1) và khối [6] không định nghĩa "mép trong" của hộp bao, nhưng người đọc sau sẽ không đoán ra | `apps/ml/objects/detector.py:322-330` | Thêm một câu: từ vòng 2, hộp đã nối chỉ nối tiếp qua điều kiện (a) |
| N2 | Nit | TEST-07 | `time.sleep(0.2)` để "bắt một bản gửi lặp tới muộn": khẳng định phủ định phụ thuộc thời gian thật — một bản gửi lặp đến ở giây 0,3 vẫn lọt. Bị chặn trên 0,2 s nên không rung, nhưng không phải bằng chứng chắc | `apps/ml/objects/tests/test_tasks.py:447` | Hoặc bỏ `sleep` (phần đếm `== 1` sau khi worker đóng đã đủ), hoặc truyền `send` tường minh vào `run_step` để spy được thật |
| N3 | Nit | PERF | `MERGE_BUDGET_S` giữ 2,0 s là đúng, nhưng biên thật hẹp hơn báo cáo: báo cáo vòng sửa ghi 0,22 s (máy rỗi), tôi đo **0,778 s** khi có một container cổng chạy song song — biên 2,6× chứ không phải 9× | `apps/ml/objects/tests/test_perf.py:23` | Không cần sửa; ghi số đo dưới tải vào báo cáo để lần sau không tưởng trần rộng |

## Soát mới (yêu cầu của lượt 2)

- **Tách ma trận theo nhãn (`f432955`) vẫn đúng khối [6] bước 3–5.** `_merge_adjacency` luôn có
  `same_label` trong điều kiện, nên mọi cặp khác nhãn vốn đã là `False`: chia theo
  `np.unique(classes)` cho **đúng cùng tập cạnh**, chỉ bỏ phần tính phí cho cặp khác nhãn
  (`O(n²)` → `O(Σ mᵢ²)`). NMS (`_nms`) vẫn chạy trên toàn bộ ứng viên **trước** khi tách, đúng thứ
  tự bước 3 → 4. `_cap_and_sort` vẫn sau cùng (bước 5).
- **Nhãn của hộp sau nối**: `merged_label[inverse] = candidates.classes` — trong một nhóm mọi ứng viên
  cùng nhãn (giờ được **bảo đảm về cấu trúc** vì đã tách theo nhãn trước khi lặp), nên phép gán
  "người ghi cuối thắng" là đúng. Đã kiểm thực nghiệm với hai nhãn song song.
- **Tất định**: `np.lexsort` ổn định; thứ tự đầu vào của `_cap_and_sort` giờ theo nhóm nhãn nhưng là
  hàm thuần của đầu vào. Ba lượt chạy cho kết quả hệt nhau.
- **Điểm bất động có dừng**: mỗi vòng còn cạnh thì ≥ 1 nhóm co lại, nên số ứng viên giảm nghiêm ngặt;
  không cạnh thì `break`. Chặn trên bằng số ứng viên của nhãn.
- **numpy, không vòng Python theo điểm ảnh** (K28): vẫn đúng — vòng Python chỉ theo nhãn, theo vòng
  lặp điểm bất động, và theo cạnh của union-find.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 4 | 0,28 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 4 | 0,12 |
| **Tổng** | **100 %** | | **4,90 / 5** |

Không P0, không P1, không P2 còn lại; chỉ 3 Nit mới + 2 Nit cũ không chặn → điểm ≥ 4,0 → APPROVE.

## PHÁN QUYẾT: APPROVE

Cả ba việc bắt buộc của lượt 1 đã làm đúng và làm tới gốc. Finding **P1** (thiếu hai nhóm case của
khối [8]) được lấp bằng `test_tiles.py` và `test_labels.py` viết đủ chứ không viết cho đủ số: lưới lát
được kiểm ở cả bốn khổ hợp đồng trên năm bất biến (phủ hết điểm ảnh, lát cuối sát mép, không trùng,
chồng ≥ overlap, thứ tự hàng-rồi-cột) và sáu case `ValueError` — đúng chỗ B6-04b sẽ dựa vào để cắt
dataset. Finding **P2** về nối hộp được sửa đúng bản chất, không vá quanh: `_merge_cut_boxes` giờ lặp
tới điểm bất động, docstring bỏ hẳn lời khẳng định tương đương sai và nói thẳng vì sao một lượt không
đủ, và có test hồi quy mang đúng phản ví dụ của review. Tôi chạy lại phản ví dụ ấy độc lập: **một hộp**,
không phải hai. Finding P2 về R-01 và cả bốn P3 còn lại đều xong (trừ #6 vốn thuộc chủ B5-01).

Cổng đầy đủ lần 3 trên đúng `f432955…` thoát **0** với cả 10 bước đạt; độ phủ `apps/ml/objects` lên
**100 % dòng / 96,55 % nhánh** và tổng 99,55 / 98,34 — tăng ở cả hai chiều so với lượt 1, không nhờ
`pragma` hay hạ ngưỡng. Bản sửa hiệu năng thêm vào (`f432955`, tách ma trận kề theo nhãn) tôi đã kiểm
là **cùng tập cạnh** với bản một ma trận — `same_label` vốn đã là điều kiện bắt buộc trong
`_merge_adjacency` — nên nó chỉ bỏ phí tính cặp khác nhãn, không đổi kết quả; đã xác nhận thực nghiệm
với hai nhóm nhãn nối song song, và tất định qua ba lượt chạy.

Còn lại ba Nit mới (N1 docstring chưa nói `NaN` cũng tắt điều kiện (b) cho hộp đã nối; N2 `time.sleep(0.2)`
làm bằng chứng phủ định; N3 biên hiệu năng thật 0,778 s dưới tải chứ không phải 0,22 s) và hai Nit cũ
(#8 điều kiện (b) không đòi lát kề — đúng nguyên văn hiến chương; #10 một `# type: ignore` chưa có lý do
sau mã). **Không cái nào chặn merge.** Nợ duy nhất cần ghi là việc của người điều phối: cập nhật NO-285
để kể cả nơi khai trùng thứ ba `apps/ml/objects/tasks.py:33` (`apps/ml/runtime/**` nằm trong khối [12],
B5-03 không được sửa).

Được merge vào `main`.
