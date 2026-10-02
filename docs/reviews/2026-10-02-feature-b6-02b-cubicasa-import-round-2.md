# Review merge feature/b6-02b-cubicasa-import → main — lượt 2 (chốt)

- Ngày: 2026-10-02 · Reviewer: phiên /merge-review (cùng phiên lượt 1) · Commit đầu nhánh: `6e87fa217936`
- Lượt 1: **REQUEST CHANGES 4,28/5** (`2026-10-02-feature-b6-02b-cubicasa-import.md`, sha `860554c`)
- **Phạm vi kiểm: đầy đủ.** Cổng `bash tools/verify/run.sh verify` **mã thoát 0**
  (`backend/dieu-phoi/chay/B6-02b/M/gate-2.log`; `M/gate.sha` = `sha=6e87fa2`, trùng sha đi review).
  `7868 passed` + `1 perf` (298 deselected), 599,18 s. Tiền kiểm `M/pre-7.log` → `PREFLIGHT OK 6e87fa2`.
- **Độ phủ (dòng `coverage_gate` của chính cổng, không phải tiền kiểm):** `coverage_gate: đạt` —
  tổng **dòng 99,45 % · nhánh 97,89 %**; `apps/worker/datasets_cubicasa` **dòng 99,01 % · nhánh 95,58 %**;
  tập file bị chạm dòng 98,80 % · nhánh 95,76 %. Mọi số ≥ 90/90.
- Phạm vi diff lượt này: `git diff b70558c 6e87fa2 -- apps/worker/datasets_cubicasa changes/B6-02b.md`
  = **3 tệp test, +18/−19** (net −1 dòng), đúng và chỉ đúng G-01. Phần còn lại của `b70558c..6e87fa2`
  là merge FIX-116 (`1861e91`, `dba678f`) — đã review riêng, **APPROVE 4,83/5**
  (`2026-10-02-fix-b6-04b-ultralytics-pil-open.md`), không chấm lại ở đây.

## Bảng E.10 (lấy từ mã thoát thật trong `M/gate-2.log`)

| # | Bước | Trạng thái | Chi tiết |
|---|---|---|---|
| 0 | làm ấm node_modules | đạt | |
| 1 | `ruff format --check` | đạt | |
| 2 | `ruff check` | đạt | |
| 3 | `mypy --strict` | đạt | |
| 4 | `lint-imports` | đạt | |
| 5 | `pytest -n (cov)` → `coverage_gate` | đạt | 7 868 qua / 0 hỏng; `coverage_gate: đạt` |
| 5b | `pytest -m perf` → `case_gate` | đạt | perf: 1 test |
| 6 | `lint_migrations` → `migrate_check` | đạt | |
| 7 | H1 H3 H4 H5 (`tools.contract.check`) | đạt | |
| 8 | `openapi` | đạt | 255 271 byte |

**mã thoát: 0** — không bước nào `hỏng` hay `chưa chạy`. Đây là lần đầu B6-02b có một bảng E.10 đầy đủ
toàn `đạt`: lượt 1 đỏ ở bước 5 vì NO-322 (ngoài phạm vi), nay đã khép bằng FIX-116 nằm trong cùng nhánh.

## G-01 — finding duy nhất còn lại của lượt 2

| Lượt 2 | Trạng thái | Bằng chứng tôi tự kiểm |
|---|---|---|
| G-01 P3 R-07: `_version` (`test_importer.py:93`) và `_version_row` (`test_runtime.py:63`) trùng logic, trái luật gom helper dùng chung vào `tests/fake_cubicasa.py` mà chính tác giả đặt | **ĐÓNG — đúng chỗ đã đề xuất** | Một `read_version(maker, version_id)` duy nhất ở `tests/fake_cubicasa.py:286-294`, **cả hai** bản riêng bị xoá, 4 chỗ gọi đổi sang helper chung (`test_importer.py:114, 383`; `test_runtime.py:158-159`). Diff **không nới một assert nào**: các dòng khẳng định của M06 (`manifest_sha256 is not None`, `first == second`) và của `test_import_storage_unavailable_fails_clean` (`.status == "failed"`) giữ nguyên từng ký tự, chỉ đổi tên hàm gọi. Dọn luôn `select`/`DatasetVersionRow` thành mồ côi ở `test_runtime.py` (`test_importer.py` vẫn cần chúng cho `_version_count`). Net **−1 dòng** — sửa trùng lặp mà diff ngắn hơn, đúng hướng R-07 |

Không còn finding mở nào. Để tránh đọc sai điểm 5,00 ở dưới: nó theo đúng thang mechanical của
`RULE.md` §5 ("5 = không finding" cho miền đó), **không** có nghĩa mã không còn gì cải thiện được. Những
chỗ tôi **chấp nhận có lý do** qua hai lượt, không tính là finding:

- **F-08** (thứ tự `ratio` trước `too_large` trong `safe_extract`): lý do an ninh của tác giả mạnh hơn
  thứ tự liệt kê của prompt [6] — một mục độc hại phải bị từ chối bằng `reason` của chính nó.
- **`_Beat` của `importer.py`** lặp ý `_Beat` riêng tư của `apps/worker/datasets/tasks.py`: quyết định
  biết trước của điều phối (#5), khác ngữ nghĩa và đã nói rõ vì sao trong docstring.
- **Trần `_MAX_NUM_CHARS = 64`** là một ngưỡng kinh nghiệm (float64 in ra ~24 ký tự): tầng hai có chủ ý,
  và tầng một (`_NUM_BODY` không mơ hồ) đã tự tuyến tính nên trần không phải chỗ dựa duy nhất.
- **Hai test ReDoS khoá hồi quy bằng `faulthandler_timeout`** thay vì khẳng định đồng hồ: đúng luật
  BE-00 §12 + `chung.md` (một test `perf` duy nhất cả prompt), không phải thiếu sót.
- `settings.py:21` (`_system_temp_dir`) chưa phủ — tệp thuộc nhánh prep, module vẫn 99,01/95,58.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 5 | 0,75 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 5 | 0,35 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 5 | 0,15 |
| **Tổng** | **100 %** | | **5,00 / 5** |

Tổng: 5,00 / 5

## PHÁN QUYẾT: APPROVE

Ba mục chặn của lượt 1 và finding duy nhất của lượt 2 đều đóng, cổng đầy đủ thoát 0, độ phủ module
99,01 % dòng · 95,58 % nhánh lấy từ chính `coverage_gate` của cổng chứ không từ tiền kiểm.

Điều đáng ghi nhận nhất qua hai lượt là **cách** sửa, không chỉ việc sửa:

- **F-01 (P1, ReDoS)** được truy về nguyên nhân thật — lượng từ mơ hồ `\d+\.?\d*` — và bỏ hẳn, nên khi
  tôi **tháo trần độ dài ra để đo riêng regex** thì vẫn tuyến tính (n=16 000: 5 367 ms → 0,745 ms,
  ~7 200×). Một bản vá chỉ chặn độ dài sẽ qua mọi test nhưng không đạt R-19; bản này đạt.
- **F-03 (P2, M06)** được khoá chặt **hơn** đề xuất của tôi: cả tập `(path, sha256)` của hai manifest
  **và** `manifest_sha256` trong DB, kèm chặn `None == None`.
- **F-04** sửa bằng cách cho nhánh một đường đi thật (`sizes` chỉ chứa ảnh có thật) thay vì xoá nhánh
  cho đẹp coverage — và cột "thiếu" của coverage xác nhận độc lập.
- **G-01** gom helper vào đúng chỗ, net −1 dòng, không nới assert nào.

Mỗi lượt, khai của tác giả tôi đều đo lại thay vì tin (31 ca đối chiếu ngôn ngữ regex cũ↔mới cho 0 lệch;
bốn regex còn lại của module tự đo đều tuyến tính; 8/8 chỗ nhập `ultralytics` của FIX-116 tự `grep`) —
không lần nào khai sai. Một khai **của prompt/spec** thì sai và tác giả xử đúng: `test_offline.py:18`
không phải import ở mức module.

Nợ cần đóng/ghi khi gộp: **NO-322** đóng được (FIX-116 đã trong nhánh, lệnh tái hiện xanh 30 qua ở
`M/pre-7.log`); **H-01 (P2)** của FIX-116 vẫn mở (cổng gác chokepoint `ultralytics` chưa phủ tệp test)
— một dòng `DEBT.md`, chủ B6-04b + B5-01.

Không tự merge: việc merge thuộc phiên gọi review này.
