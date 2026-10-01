"""Mã lỗi riêng của job huấn luyện (B6-03a [2]); mã lõi ở `packages.core.error_codes`.

Ba mã 422 của N33 và một mã 409 của N35. Mỗi 409 mang đúng mã vì F-12 rẽ theo `code`
(409 mặc định của FE là "tải lại"). `failureCode` của job là hằng chuỗi ở
`apps/worker/training_bridge/errors.py`, không qua `ERRORS.define`.
"""

from packages.core.errors import ERRORS

DATASET_VERSION_NOT_READY = ERRORS.define("DATASET_VERSION_NOT_READY", 422)
"""Phiên bản dataset chưa `ready` (`building` hay `failed`)."""

DATASET_FAMILY_MISMATCH = ERRORS.define("DATASET_FAMILY_MISMATCH", 422)
"""Dataset của phiên bản thuộc họ khác `family` của job."""

TRAINING_BASE_MODEL_MISMATCH = ERRORS.define("TRAINING_BASE_MODEL_MISMATCH", 422)
"""`baseModel` không thuộc `BASE_MODELS[family]`."""

TRAINING_JOB_NOT_CANCELLABLE = ERRORS.define("TRAINING_JOB_NOT_CANCELLABLE", 409)
"""N35 trên job `succeeded`/`failed`."""
