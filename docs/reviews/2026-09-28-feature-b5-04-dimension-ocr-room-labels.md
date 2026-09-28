# Review merge feature/b5-04-dimension-ocr-room-labels → main

- Ngày: 2026-09-28 · Reviewer: phiên /merge-review (lượt 1, R-37) · Commit đầu nhánh: `36f6642abb3e`
- Cổng: **phạm vi dùng log cổng đầy đủ của lớp gộp** — người dùng chốt 2026-09-28 ngân sách 1 h/prompt và cấm phiên
  review chạy cổng đầy đủ; lớp gộp đã chạy `bash tools/verify/run.sh verify` trên **đúng sha này**
  (`.cache/src-out/verify/20260928T132158Z-36f6642abb3e.log`, chép ở
  `backend/dieu-phoi/chay/B5-04/C/verify1.log`), chạy lại là tốn thêm một container trong trần song song 2 (R-33b).
- Độ phủ: `packages/vision/dimensions` 100 % dòng / 100 % nhánh · `apps/ml/text` 98,3 % dòng / 96,3 % nhánh
  (`reader.py` thiếu 145, 321-322, 342) — cả hai ≥ 90/90. Tổng của cổng nằm ở `coverage_gate` bước 5.
- Phạm vi diff: 20 file mới, 2.520 dòng thêm, 0 xoá; đúng ba vùng sở hữu (`packages/vision/dimensions/**`,
  `apps/ml/text/**`, `changes/B5-04.md`). Cây sạch, ba commit đúng mẫu + trailer `Prompt: B5-04`.
- Báo cáo đầy đủ: `backend/dieu-phoi/chay/B5-04/bao-cao-review-1.md`.

## Trạng thái cổng (mã thoát thật; K25 — không báo "đạt" cho bước chưa chạy)

| # | Bước | Trạng thái | Bằng chứng |
|---|---|---|---|
| 1 | `ruff format --check` | đạt | `970 files already formatted` |
| 2 | `ruff check` | đạt | `All checks passed!` |
| 3 | `mypy --strict` | đạt | `Success: no issues found in 801 source files` |
| 4 | `lint-imports` | đạt | `Contracts: 9 kept, 0 broken.` |
| 5 | `coverage run -m pytest` + `coverage_gate` | chưa xong — đang chạy lúc ra phán quyết (73 % bộ test, 0 FAILED / 0 ERROR) | |
| 5b | `pytest -m perf` + `case_gate` | chưa chạy | |
| 6 | migration | chưa chạy | |
| 7 | H1/H3/H4/H5 | chưa chạy | |
| 8 | OpenAPI | chưa chạy | |

## Sáu "Lệch khỏi prompt" — phán rõ

| # | Lệch | Phán |
|---|---|---|
| 1 | `cases.toml` không khai M01–M04 | **Chấp nhận.** Tự đọc `tools/case_gate.py:296`: `_TEST_TASK_RE = ^test_(?P<fn>.+)__(?P<case>J\d{2})$` chỉ nhận `J\d{2}`; khai `M0x` ⇒ `task_missing` đỏ vĩnh viễn mà `tools/**` ngoài whitelist. Bốn test `test_text_read__M01`…`__M04` có đủ (`test_tasks.py:239,255,274,303`), chạy Redis + Celery thật, đúng BE-00 §7. |
| 2 | `WIDTH_ROUNDING_RATE = 0,90` (đo 15/16) thay cho "làm tròn `W` không đổi chuỗi nào" | **Finding P2-1** — không phải vì ngưỡng (lý do kỹ thuật đứng vững: `T` phụ thuộc `W`), mà vì **tên test nói ngược** điều nó khẳng định. |
| 3 | `1.234.567` → `parse_length_mm` `None` | **Chấp nhận.** [8] mâu thuẫn với [2]/[6] (`DIMENSION_MAX_MM = 1_000_000`); bất biến thắng ma trận case. Cả hai hành vi đều có test ghim (`parse_length_fraction` = 1234567, `parse_length_mm` = `None`). |
| 4 | `RoomUsage` khai lại `Literal` ở `rooms.py:15` | **Chấp nhận, không phải R-07.** `packages.domain.spatial` không xuất tên kiểu; bản sao không trôi được vì `test_rooms.py:39` chốt `set(ROOM_USAGE_NAMES) == set(get_args(Room.model_fields["usage"].annotation))`. |
| 5 | `from_session(pinned_name)` không có đường lùi; `_detect_tile` gọi nội bộ `TextDetector` | **Chấp nhận (Nit).** [6] chỉ cho đường lùi **có điều kiện**; model rec của wheel **có** metadata `character`, nên nhánh lùi là mã chết (R-10). Rủi ro nâng wheel được `test_reader_agrees_with_the_wheel_engine` và `test_real_detector_finds_the_answer_boxes` bắt hộ; chữ ký `pinned_name` là do [2] bắt buộc. |
| 6 | Tỉ lệ đọc 105/122 = 86,1 % (wheel `use_cls=False`: 114/122 = 93,4 %) | **Finding P2-2 + nợ.** Mọi ngưỡng của [8] đều đạt (recall 100 %, khớp wheel 95,4 %, 0,90 s), nhưng đây là khoảng lùi chất lượng thật và **không có test cố định nào giữ nó**. |

## Finding

| # | Mức | ID | Mô tả | Vị trí | Đề xuất |
|---|---|---|---|---|---|
| 1 | P2 | R-01/R-02 | `test_width_rounding_does_not_change_any_string` thực ra khẳng định `same >= 0,90 * checked`, tức cho phép 10 % vùng **đổi** chuỗi; dòng đầu docstring cũng lộn nghĩa. Người đọc tên test sẽ tin tiêu chí [8] còn đúng. | `apps/ml/text/tests/test_reader_real.py:109`, assert `:134` | Đổi tên `…_keeps_most_strings`, sửa dòng đầu docstring thành "≥ ngưỡng phần vùng **giữ nguyên** chuỗi"; giữ ngưỡng và đoạn Lệch ở `:112-116`. |
| 2 | P2 | LOG-04 | Đọc đúng 86,1 % chữ kích thước vs 93,4 % của `RapidOCR()` cùng `use_cls=False`; khoanh vùng ở Otsu/lát/tự xoay, không phải bộ dò (recall 100 %). Số do tác giả tự đo, không có test nào giữ. | `apps/ml/text/reader.py:219-229` | Không sửa vòng này ([6] bắt buộc Otsu). Mở `NO-…`, giao B6-04b: đo `cer`, thử Otsu có điều kiện theo tương phản. |
| 3 | P2 | R-34 | Hai nợ nêu trong báo cáo chưa có dòng `DEBT.md`; `NO-063` (`DEBT.md:83`) vẫn `⬜ mở`, chưa ghi số đo mới dù [6] giao B5-04 đo lại. | `DEBT.md:83` | Không phải lỗi tác giả — `spec-B.final.md:139-140`, `spec-C.md:41` cấm worker sửa `DEBT.md`. Điều kiện merge: người điều phối ghi 3 dòng ở mục "Nợ nên ghi". |
| 4 | P3 | TEST | Số đo bàn giao NO-063 chỉ là phép đo tay, không thành test, khác mọi số đo khác của prompt. | `test_reader_real.py` (thiếu) | Một phép đo 3 seed gắn `@pytest.mark.perf`, hoặc ghi rõ trong `DEBT.md` là chỉ đo lại ở B6-04b. |
| 5 | P3 | TEST | `test_width_rounding…` chỉ một seed, `checked >= 5` (đo thật 16); 2 chuỗi đổi là đỏ ngẫu nhiên. | `test_reader_real.py:119,133` | Lấy 2–3 seed, hoặc nâng trần `checked` và nói rõ đây là ngưỡng thô. |
| 6 | Nit | MNT | `_decode` của test thò vào `_session`/`_output`/`_characters`. | `test_reader_real.py:139` | Chấp nhận được; muốn sạch thì phơi `_run_tensor` cấp module. |
| 7 | Nit | — | Trailer `Co-Authored-By: Claude`, phiên yêu cầu `Claude Opus 5`. | ba commit | Không rewrite lịch sử; chỉnh từ prompt sau. |

Không có P0, không có P1.

## Điểm

| Miền | Trọng số | Điểm | Tích |
|---|---|---|---|
| SEC – Bảo mật | 25 % | 5 | 1,25 |
| CON – Concurrency & dữ liệu | 15 % | 5 | 0,75 |
| LOG – Tính đúng đắn | 15 % | 3 | 0,45 |
| PERF – Hiệu năng | 10 % | 5 | 0,50 |
| RES – Chịu lỗi | 10 % | 5 | 0,50 |
| DB, API – Migration & contract | 10 % | 5 | 0,50 |
| TEST – Kiểm thử | 7 % | 3 | 0,21 |
| OBS, OPS – Vận hành | 5 % | 5 | 0,25 |
| MNT – Bảo trì | 3 % | 3 | 0,09 |
| **Tổng** | **100 %** | | **4,50 / 5** |

## PHÁN QUYẾT: APPROVE (4,50/5)

Không P0, không P1; 4,50 ≥ 4,0. Một trong những nhánh chắc nhất của đợt: ngữ pháp số chép đúng `parse.ts` tới từng
ca trong 24 ca FE và không hề dùng `float()` trên chữ OCR; ghép tỉ lệ chạy thật trên cả 40 seed `EVAL_SET_SEEDS` ở
**hai** hình thái tường (liền và cắt tại mọi cửa), nên bước "nối tường qua khe" của [8] đúng là không cần viết;
OCR dùng dịch vụ và model thật ở mọi tầng (Redis Testcontainers, worker Celery, bộ dò wheel, model rec ghim), và
`test_boundary.py` còn có test chứng minh phép chặn import thật sự chặn. Mọi "Lệch khỏi prompt" đều kiểm lại được
và đều đứng vững, kể cả cái khó nhất (M01–M04) mà reviewer đã tự đọc `tools/case_gate.py:296` để xác nhận. Ba P2
đều là chuyện sổ sách và nhãn, không phải lỗi hành vi.

**Hai điều kiện merge:**

1. **Cổng.** Log cổng đầy đủ trên sha `36f6642` phải đóng với **mã thoát 0**. Lúc ra phán quyết, bước 1–4 đã đạt và
   bước 5 đang chạy ở 73 % với 0 FAILED / 0 ERROR; bước 5–8 chưa có mã thoát nên không được ghi "đạt" (K25). Log đỏ
   ⇒ phán quyết này mất hiệu lực và lượt 2 soát bước hỏng.
2. **Sổ nợ.** Người điều phối ghi 3 dòng dưới đây vào `DEBT.md` (worker bị spec cấm sửa file này).

## Nợ nên ghi (`DEBT.md`, người điều phối)

1. `NO-…` — `RapidOcrReader` đọc đúng 86,1 % (105/122) chữ kích thước seed 100–109 vs 93,4 % (114/122) của
   `RapidOCR()` cùng `use_cls=False`; khoanh vùng ở Otsu/lát/tự xoay, không phải bộ dò. P2, mở; giao B6-04b.
2. `NO-…` — ngưỡng tự chỉnh `WIDTH_ROUNDING_RATE = 0,90` thay cho "làm tròn `W` không đổi chuỗi nào" ([8]); đo
   15/16 trên seed 100. Nit, `chấp nhận` có lý do; kèm việc sửa tên test của finding 1.
3. Cập nhật `NO-063`: bàn giao đã làm (`use_cls=False`, tự xoay theo tin cậy); số đo mới 105/122 = 86,1 %; phần còn
   lại chuyển sang nợ 1.
