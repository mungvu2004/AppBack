# QT-FURN-TOGGLE — công tắc nhận diện đồ đạc theo dự án

- Cài đặt dự án (N5/N6) thêm `detectFurniture`, mặc định `false` (chủ dự án tắt nhận diện đồ từ 02/11/2026).
  PUT vắng khoá hay `null` = giữ giá trị đang lưu; khác boolean → 422.
- Migration `r20261102_qt_furn_toggle`: cột `project_settings.detect_furniture` NOT NULL DEFAULT false.
- `queue_build` mang cờ vào `BuildStepPayload.detect_furniture` (thông điệp cũ vắng → dựng đồ như trước);
  `build_layer(furniture=False)` không dựng đồ, không gợi ý mực dư. Hộp YOLO vẫn dùng cho ô mở, tỉ lệ theo cửa, nhãn phòng.
- Có hiệu lực từ lượt xử lý sau; đồ người dùng tự thêm không bị đụng.
