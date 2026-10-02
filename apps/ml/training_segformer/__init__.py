"""Huấn luyện SegFormer tách tường (B6-04a): `trainer.TRAINER` cho họ `wallSegmentation`.

Runner B6-03b tìm trainer qua `discover_trainers()` (B5-01), cấp thư mục dữ liệu đã kiểm
manifest, giữ khoá và đưa `reporter`; prompt này chỉ huấn luyện rồi xuất `out_dir/model.onnx`
mà `SegformerOnnxSegmenter` (B5-02) nạp được. Nhập gói không nhập `torch`, `onnxruntime`.
"""
