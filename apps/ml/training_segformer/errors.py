"""Mã lỗi của trainer SegFormer: hằng chuỗi cho `PermanentError(code)` (B0-05), không `ERRORS.define`.

Runner B6-03b gửi chúng thành `failureCode`. `MODEL_CHECKSUM_MISMATCH`, `MODEL_FORMAT_UNSUPPORTED`
cùng chuỗi với `apps.ml.runtime.errors`, `DATASET_SPLIT_EMPTY` cùng chuỗi với
`apps.ml.training_runner.errors`, nhưng **không** nhập lại từ đó: cả hai module nhập
`onnxruntime` lúc nạp, trái luật "nhập `trainer` không nhập `onnxruntime`" (khối [2]).
Test so từng chuỗi với bản gốc để hai nơi không trôi.
"""

from typing import Final

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
MODEL_CHECKSUM_MISMATCH: Final = "MODEL_CHECKSUM_MISMATCH"
MODEL_FORMAT_UNSUPPORTED: Final = "MODEL_FORMAT_UNSUPPORTED"
DATASET_SPLIT_EMPTY: Final = "DATASET_SPLIT_EMPTY"
DATASET_SAMPLE_INVALID: Final = "DATASET_SAMPLE_INVALID"
TRAINING_LOSS_NOT_FINITE: Final = "TRAINING_LOSS_NOT_FINITE"
MODEL_EXPORT_MISMATCH: Final = "MODEL_EXPORT_MISMATCH"
