"""Huấn luyện YOLO dò ô mở và đồ đạc (B6-04b): `trainer.TRAINER` cho họ `openingAndFurnitureDetection`.

Runner B6-03b tìm trainer qua `discover_trainers()` (B5-01), cấp thư mục dữ liệu đã kiểm
manifest, giữ khoá và đưa `reporter`; gói này lát dataset theo lưới suy luận của B5-03,
huấn luyện bằng `ultralytics` ngoại tuyến rồi xuất `out_dir/model.onnx` mà `YoloOnnxDetector`
nạp được. Nhập gói không nhập `ultralytics`, `torch`, `onnxruntime`.
"""
