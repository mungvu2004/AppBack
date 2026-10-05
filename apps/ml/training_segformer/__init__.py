"""Huấn luyện SegFormer tách tường (B6-04a): `trainer.TRAINER` cho họ `wallSegmentation`.

Runner B6-03b tìm trainer qua `discover_trainers()` (B5-01), cấp thư mục dữ liệu đã kiểm
manifest, giữ khoá và đưa `reporter`; prompt này chỉ huấn luyện rồi xuất `out_dir/model.onnx`
mà `SegformerOnnxSegmenter` (B5-02) nạp được. Nhập gói không nhập `torch`, `onnxruntime`.
"""

import os
from typing import Final

_OFFLINE_ENV: Final = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
"""BE-00 §9: `transformers` không được chạm Hub. Đặt ở đây vì mọi đường nhập `training_segformer.*` đi qua
`__init__` trước, tức trước lần nhập `transformers` đầu tiên (cờ chỉ đọc lúc nhập)."""

os.environ.update(_OFFLINE_ENV)
