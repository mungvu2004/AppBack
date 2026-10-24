# FIX-IT-OPENINGS — khép góc tường và gắn ô mở theo hộp (BUG-IT-001/003/004)

- `apps/worker/pipeline_build/geometry.py` 3b-b: chỗ giao được lố đầu vách vuông góc tối đa
  `max(bề dày vách, CORNER_OVERSHOOT_MM=150)`; vách kéo theo tới chân để góc khép (G2 lố 29 mm, 6/7 cửa rơi).
- Bước 4: gắn hộp vào tường khi **hộp** (không phải tâm) cách tim ≤ `bề dày/2 + 150`; nhiều tường thì chọn gần tâm nhất
  (bản vẽ xoay 45°, CubiCasa 5135).
- Rộng ô mở = hình chiếu hộp lên tim, kẹp ≤ chiều dài tường; hình chiếu < `OPENING_MIN_WIDTH_MM=300` mới dùng mặc định
  `LABEL_TARGETS` (hết `openingTooWide`/`openingOverlap` giả trên tường ngắn, cửa sổ kề nhau).
- Test: `apps/worker/pipeline_build/tests/test_geometry_openings.py`. Không đổi API, migration, hợp đồng FE (`widthMm` vẫn > 0).
