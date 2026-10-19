# FIX-DETECTOR-CUT-FRAGMENTS — hậu xử lý YOLO: bỏ mảnh lát cắt trước NMS, nối chặt, ngưỡng theo nhãn

- `apps/ml/objects/detector.py`: mảnh chạm mép trong lát bị bỏ khi lát khác thấy trọn vật (trước NMS);
  luật nối cũ (điều kiện "chứa" + lặp điểm bất động, tiles=NaN) thay bằng nối chặt một lượt (hai lát kề,
  cùng phủ dải chồng); ngưỡng theo nhãn `LABEL_CONFIDENCE_MIN` (F1 tốt nhất trên 400 trang validation
  CubiCasa, yolo11m) + `min_confidence` ở `YoloOnnxDetector` để đánh giá mAP hạ 0,05.
- Đo (400 trang test, yolo11m, ngưỡng 0,05): mAP50 0,7455 (cũ @0,25) → 0,8504; validation 0,7252 → 0,8292.
- Test: `test_detector_postprocess.py` (bỏ 3 test khoá luật nối cũ, thêm bỏ mảnh/hồi quy xâu chuỗi/ngưỡng).
