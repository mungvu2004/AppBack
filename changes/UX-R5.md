# UX-R5 — đợt sửa UX vòng 5 (AppBack/AI)

## be-ocr — UX-02: kích thước đọc được thành `Dimension`

- Nguyên nhân gốc (đo trên 14 ca bench, mã `main` 89064a64): OCR trên f14 chạy model thật (`rapidocrRec`,
  `ML_BACKEND=onnx`) và đọc được số; ch-03 có 10 mẫu chuỗi, suy đúng 13,915 mm/px (đáp án 13,918). Nhưng bước 7
  của `build_layer` chỉ dựng `Dimension` từ mẫu ghép tường (`t…-w…`), bỏ qua mẫu chuỗi — mà mẫu chuỗi mới là thứ
  quyết tỉ lệ. Kết quả 11/14 ca có 0 `Dimension` → FE (`dimensionCount === 0`) báo "Không đọc được số kích thước nào".
- `apps/worker/pipeline_build/build.py` `_chain_dimensions`: chữ chỉ có mẫu chuỗi, trong ngưỡng 2 % của `s`, chưa có
  `Dimension` ghép tường → một `Dimension` `linear`, `referenceIds` rỗng, đoạn dài `span_px` giữa hộp chữ theo chiều dài
  hộp; xét mọi mẫu chuỗi (kể cả < 3 mẫu khi `s` đến từ ghi chú `TL 1:N` của PDF). Tỉ lệ, tường, phòng không đổi (bảng `F:/runs/r5-be-ocr/KET-QUA.txt`): ca có `Dimension` 3/14 → 8/14.
- Chưa sửa: ch-04/ch-05/ch-08 chữ số cao ~3 px trên ảnh 1290 px (phóng 2-4× vẫn 0 số dò được), không đọc nổi bằng OCR;
  ghi chú "TL: 1/100" đọc được nhưng ảnh raster không biết khổ giấy (ch-04: 1/100 + A3 cho 32,6 mm/px, đáp án 14,6).
- PDF: ghi chú tỉ lệ đã chạy trên f14 (`vector-apt.pdf` đọc "TL 1:50" → 6,35 mm/px = đúng 1:50 ở 200 DPI;
  `two-page-ch04.pdf` → 12,7 mm/px). Ở `vector-apt.pdf` hai số 7000/9000 đọc được nhưng `span_px` = `None` (không đo được
  đoạn kích thước) nên vẫn 0 `Dimension`. Việc FE vẫn khoá "Xác nhận tỷ lệ" khi tỉ lệ đã có nguồn `pipeline` là cổng FE.
- UX-38 (ảnh không phải bản vẽ báo sớm) chưa làm: hết giờ.

## be-rooms (UX-04, UX-14)

- UX-14 `apps/worker/pipeline_build/rooms.py` `relabel_by_size`: YOLO báo `bed` trong phòng `_NO_BED_USAGES` (khách, bếp, WC, hành lang, lô gia) → `other` + `variant="rug"` (FE vẽ thảm `rectangular-carpet`). Đo 14 ca với objects.json của YOLO đang chạy (`F:/runs/walls-tidy/cases`): 3 giường đổi — ch-11 thảm hoa văn phòng khách (đúng ca K-02), ch-06 món hẹp 33×186 px trong phòng khách (không phải giường), ch-14 một món trong "phòng khách"; giường trong phòng ngủ không đổi; số phòng không đổi.
- UX-04 diện tích thông thuỷ: KHÔNG sửa đợt này. FE tính diện tích hiển thị từ `outline` (`computeArea`, bước Phòng, `graphSelectors`) và `rescale` tính lại `areaM2` từ đường bao, nên đổi riêng `areaM2` ở worker không tới người dùng và lệch hợp đồng. Đo (outline trừ thân tường, 34 phòng có nhãn diện tích): sai số tuyệt đối TB 16,0 % → 10,2 %, trung vị +9,2 % → −4,2 %, nhưng ch-12 xấu đi rõ (5,0 % → 17,6 %). Muốn làm cần quyết định hợp đồng: đường bao phòng theo mặt tường trong (ảnh hưởng `wallIds`, luật FE, 3D) hoặc trường `netAreaM2` mới.
- UX-04 tách phòng: `rooms.py` `_split_by_labels`/`_best_cut` — vùng chứa ≥ 2 nhãn tên phòng (OCR, `match_room_label`) được cắt dọc đường tim một tường kéo dài tới biên, chọn vết cắt có phần hở (không tường) ngắn nhất ≤ 2,5 m mà mỗi mảnh còn nhãn và ≥ `MIN_ROOM_AREA_M2`; lặp tới khi mỗi mảnh một nhãn. Một nhãn thì không cắt. Bench 14 ca (`.bench/run.py`): riêng 76 → 79, gộp 27 → 24, công năng 68 → 70 / 109; ch-05 tách bếp/khách, ch-09 tách tiền sảnh; không ca nào xấu đi. Ngưỡng 2,5 m chọn một lần, không dò; không có bộ giữ riêng có nhãn OCR ngoài 14 ca.
- Không đổi API, DB, migration, hợp đồng FE–BE. Test: `apps/worker/pipeline_build/tests/test_relabel.py`, `test_rooms.py` (614 đạt cả thư mục `apps/worker/pipeline_build/tests`).

## be-join (WALL-DANGLING-END hụt 71–113 mm)

- Đồ thị thật (`F:/runs/r5-rules` H-04/H-11a/H-12, cùng một bản vẽ): 9 đầu "hụt" thuộc 3 tường. Hai mẩu ngắn (306–456 mm,
  dày 90–111) chạy **song song** sát mặt tường bao dày 270–333, mặt cách 71–96 mm (nét bậu/nét kép), nên kéo theo trục không
  chạm được; đầu thứ ba là chuỗi thẳng hàng nhìn ra khe ~2 m (lối thông) — để nguyên. Kéo vuông góc đã có ở 3b-d (R4).
- `apps/worker/pipeline_build/geometry.py`: bước 3b (e) `_drop_hugging_stubs` sau 3b-d — bỏ mẩu ≤ 600 mm song song (≤ 10°)
  với tường dày hơn, hai đầu chiếu vào thân tường đó, mặt-tới-mặt ≤ 150 mm, có đầu không chạm tường thứ ba, không cắt hộp
  ô mở nào. Đếm vào `isolatedBlock` (khoá `dropped` giữ nguyên).
- Đo 14 ca (`F:/runs/r5-be-join/KET-QUA.txt`): đầu tự do 54 → 50 (ch-04 9 → 6, ch-10 8 → 7), đầu cách mặt tường 50–150 mm
  16 → 12; xiên, không chuẩn, ô mở, phòng, chồng: không ca nào đổi. H-xx không chạy lại được từ JSON.
- Test: 2 test `test_build_walls__*hugging*` trong `test_geometry_openings.py`; 617 test `apps/worker/pipeline_build/tests` đạt.
  ruff/mypy và cổng đầy đủ (8 bước, 9290 test) đạt 01/11. Còn mở: review P2 — `_drop_hugging_stubs` quét mọi tường cho mỗi mẩu (O(n·m)), nên dùng `neighbours`.
