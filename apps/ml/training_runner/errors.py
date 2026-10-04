"""Mã kết thúc của job huấn luyện: hằng chuỗi gửi trong `TrainingFinishedPayload.error_code`.

Không khai bằng `ERRORS.define` (không lên dây HTTP, B6-03b [2]). `MODEL_FORMAT_UNSUPPORTED`,
`GPU_LOCK_LOST` lấy lại của `apps.ml.runtime.error_codes` (B5-01, nhập nhẹ — không kéo
`onnxruntime`, trainer SegFormer nhập được), không khai trùng.
`TRAINING_CLAIM_LOST`, `TRAINING_CANCELLED` chỉ là lý do dừng/log — không bao giờ gửi `finished`.
"""

from typing import Final

from apps.ml.runtime.error_codes import GPU_LOCK_LOST, MODEL_FORMAT_UNSUPPORTED

__all__ = [
    "DATASET_MANIFEST_MISMATCH",
    "DATASET_OBJECT_MISMATCH",
    "DATASET_SPLIT_EMPTY",
    "GPU_LOCK_LOST",
    "INTERNAL",
    "MODEL_FORMAT_UNSUPPORTED",
    "TRAINING_CANCELLED",
    "TRAINING_CLAIM_LOST",
    "TRAINING_DISK_FULL",
    "TRAINING_GPU_BUSY",
    "TRAINING_LAUNCH_FAILED",
    "TRAINING_METRICS_MISSING",
    "TRAINING_SLOT_BUSY",
    "TRAINING_SLOT_LOST",
    "TRAINING_TIMEOUT",
    "TRAINING_TRAINER_MISSING",
    "TrainingStopped",
]

TRAINING_LAUNCH_FAILED: Final = "TRAINING_LAUNCH_FAILED"
TRAINING_SLOT_BUSY: Final = "TRAINING_SLOT_BUSY"
TRAINING_GPU_BUSY: Final = "TRAINING_GPU_BUSY"
TRAINING_SLOT_LOST: Final = "TRAINING_SLOT_LOST"
TRAINING_DISK_FULL: Final = "TRAINING_DISK_FULL"
TRAINING_TRAINER_MISSING: Final = "TRAINING_TRAINER_MISSING"
TRAINING_TIMEOUT: Final = "TRAINING_TIMEOUT"
TRAINING_METRICS_MISSING: Final = "TRAINING_METRICS_MISSING"
DATASET_MANIFEST_MISMATCH: Final = "DATASET_MANIFEST_MISMATCH"
"""SHA-256 manifest lệch payload, hay manifest không giải được (`parse_manifest` ném)."""
DATASET_OBJECT_MISMATCH: Final = "DATASET_OBJECT_MISMATCH"
DATASET_SPLIT_EMPTY: Final = "DATASET_SPLIT_EMPTY"
INTERNAL: Final = "INTERNAL"
TRAINING_CLAIM_LOST: Final = "TRAINING_CLAIM_LOST"
TRAINING_CANCELLED: Final = "TRAINING_CANCELLED"


class TrainingStopped(Exception):  # noqa: N818 — tên do prompt B6-03b [2] đặt, trainer B6-04a/b ném đúng tên này
    """Trainer ném khi `reporter.cancelled()` đúng; lý do dừng của runner quyết kết quả."""
