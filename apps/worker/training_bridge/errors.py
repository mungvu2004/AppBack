"""`failureCode` của job huấn luyện do cầu nối và lịch ghi (B6-03a [6]).

Hằng chuỗi, **không** `ERRORS.define`: chúng chỉ là giá trị cột `failure_code` của job
`failed`, không bao giờ là thân lỗi HTTP (cùng lý do `admin_ml_datasets/errors.py`). Mã
`PermanentError` của runner, trainer, B5-01, B0-05 (`DATASET_SPLIT_EMPTY`, …) đi thẳng từ
`finished.error_code`, không khai lại ở đây.
"""

from typing import Final

from apps.api.admin_ml_registry.errors import MODEL_CHECKSUM_MISMATCH as _CHECKSUM

MODEL_CHECKSUM_MISMATCH: Final = _CHECKSUM.code
"""`finished(succeeded)`: khoá trọng số sai mẫu/tiền tố, object thiếu, quá trần hay `sha256` lệch."""

TRAINING_METRICS_MISSING: Final = "TRAINING_METRICS_MISSING"
"""`finished(succeeded)`: `metrics` không đúng một khoá `FAMILY_METRIC[family]`."""

TRAINING_HEARTBEAT_LOST: Final = "TRAINING_HEARTBEAT_LOST"
"""`sweep_lost_training_jobs`: job `running` mất nhịp tim quá hạn và claim vắng (J07)."""

TRAINING_DISPATCH_STALLED: Final = "TRAINING_DISPATCH_STALLED"
"""`requeue_training_jobs`: gửi lại hết trần (`requeue_count` = 6) mà job vẫn `queued`."""
