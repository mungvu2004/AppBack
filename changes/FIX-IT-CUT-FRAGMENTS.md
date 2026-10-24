# FIX-IT-CUT-FRAGMENTS — bỏ mảnh lát cắt mỏng nằm trong hộp lớn cũng bị cắt (BUG-IT-002)

- `apps/ml/objects/detector.py` `_drop_cut_fragments`: thêm luật thứ hai, mảnh chạm mép trong bị bỏ khi
  có hộp cùng nhãn (lát bất kỳ, chạm mép cũng được) lớn ≥ `CUT_SLIVER_AREA_RATIO` (2,0) lần, phủ
  ≥ `CUT_COVER_MIN` diện tích mảnh và điểm ≥ mảnh. Luật cũ (lát khác thấy trọn) giữ nguyên.
- Nguyên nhân: vật rộng hơn độ chồng lát (160 px) không lát nào thấy trọn, mọi hộp phủ đều chạm mép,
  mảnh mỏng sót qua NMS vì IoU ~3% (CubiCasa G5, tủ bếp x 1440-1458).
- Test: `apps/ml/objects/tests/test_detector_postprocess.py` thêm 6 test (cùng lát, khác lát, ngưỡng tỉ lệ
  diện tích, phủ thấp, điểm thấp hơn, khác nhãn). Không đổi API, migration, hợp đồng FE.
