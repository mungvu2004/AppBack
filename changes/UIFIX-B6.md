# UIFIX-B6 · G3-35: đo méo hình thang, không báo "Tốt" khi chưa đo được

- `packages/vision/preprocess/geometry.py`: `SkewEstimate` thêm `perspective_deg` (độ hội tụ: chênh góc nửa trái/phải của đoạn gần dọc, nửa trên/dưới của đoạn gần ngang) và thuộc tính `is_measured`. `angle_deg` giữ nguyên nghĩa và giá trị.
- `packages/vision/quality/thresholds.py`: `PERSPECTIVE_GOOD_DEG = 1.0`, `PERSPECTIVE_ATTENTION_DEG = 5.0`, `classify_perspective`.
- `packages/vision/quality/assess.py`: `QUALITY_CODES` nối thêm `SKEW_NOT_MEASURED` (attention, cả ảnh) và `PERSPECTIVE_DETECTED` (attention/poor, vùng hộp bao đoạn). Năm mã cũ giữ thứ tự và chỉ số.
- Wire: không thêm trường `measurement` (zod FE `.strict()`); chỉ thêm hai giá trị `code` mới, FE nhận mã lạ mà không hỏng.
- Test: `packages/vision/quality/tests/test_perspective.py` (thẳng, xoay 3°, hình thang, trang trắng, biên ngưỡng); `test_boundary.py` đổi số mã 5 → 7.
