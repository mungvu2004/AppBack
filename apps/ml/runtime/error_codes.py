"""Mã lỗi chuỗi của worker `ml` — chỉ `typing`, nhập không kéo `onnxruntime`/`torch` (C18b).

Một nguồn cho mọi nơi trong `apps/ml`: `apps.ml.runtime.errors` nhập lại (kèm `ORT_ERRORS`, nhập
`onnxruntime`), còn trainer SegFormer và hộp cát đánh giá — hai nơi phải nhập nhẹ trước trần bộ
nhớ hay trước khi biết có cần `onnxruntime` — nhập thẳng từ đây thay vì khai lại chuỗi.
"""

from typing import Final

__all__ = [
    "GPU_LOCK_LOST",
    "ML_DEVICE_UNAVAILABLE",
    "MODEL_CHECKSUM_MISMATCH",
    "MODEL_FORMAT_UNSUPPORTED",
    "MODEL_NOT_FOUND",
    "MODEL_VERSION_FAMILY_MISMATCH",
    "PIPELINE_ARTIFACT_MISSING",
]

MODEL_CHECKSUM_MISMATCH: Final = "MODEL_CHECKSUM_MISMATCH"
MODEL_FORMAT_UNSUPPORTED: Final = "MODEL_FORMAT_UNSUPPORTED"
MODEL_NOT_FOUND: Final = "MODEL_NOT_FOUND"
MODEL_VERSION_FAMILY_MISMATCH: Final = "MODEL_VERSION_FAMILY_MISMATCH"
"""Payload trỏ bước hay họ model khác bộ chạy của task (B5-02…B5-04 dùng chung, NO-285)."""
ML_DEVICE_UNAVAILABLE: Final = "ML_DEVICE_UNAVAILABLE"
GPU_LOCK_LOST: Final = "GPU_LOCK_LOST"
PIPELINE_ARTIFACT_MISSING: Final = "PIPELINE_ARTIFACT_MISSING"
"""Trang vào của bước không còn trong kho (lượt bị dọn giữa chừng) — B5-06c đánh hỏng lượt."""
