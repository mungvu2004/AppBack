"""Mã lỗi của trainer SegFormer: hằng chuỗi cho `PermanentError(code)` (B0-05), không `ERRORS.define`.

Runner B6-03b gửi chúng thành `failureCode`. `MODEL_CHECKSUM_MISMATCH`, `MODEL_FORMAT_UNSUPPORTED`
nhập từ `apps.ml.runtime.error_codes` (một nguồn, chỉ `typing` — không kéo `onnxruntime`, giữ luật
"nhập `trainer` không nhập `onnxruntime`" của khối [2]); `DATASET_SPLIT_EMPTY`
nhập từ `apps.ml.training_runner.errors` (cũng chỉ nhập `error_codes`).
"""

from typing import Final

from apps.ml.runtime.error_codes import MODEL_CHECKSUM_MISMATCH, MODEL_FORMAT_UNSUPPORTED
from apps.ml.training_runner.errors import DATASET_SPLIT_EMPTY

__all__ = [
    "DATASET_SAMPLE_INVALID",
    "DATASET_SPLIT_EMPTY",
    "MODEL_CHECKSUM_MISMATCH",
    "MODEL_EXPORT_MISMATCH",
    "MODEL_FORMAT_UNSUPPORTED",
    "TRAINING_BASE_MODEL_MISMATCH",
    "TRAINING_LOSS_NOT_FINITE",
]

TRAINING_BASE_MODEL_MISMATCH: Final = "TRAINING_BASE_MODEL_MISMATCH"
DATASET_SAMPLE_INVALID: Final = "DATASET_SAMPLE_INVALID"
TRAINING_LOSS_NOT_FINITE: Final = "TRAINING_LOSS_NOT_FINITE"
MODEL_EXPORT_MISMATCH: Final = "MODEL_EXPORT_MISMATCH"
