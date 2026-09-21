"""Mã lỗi của worker `ml`: hằng chuỗi cho `PermanentError(code)`, không `ERRORS.define`.

Mã đi vào trạng thái hỏng của bước/job (J03), không lên dây HTTP; hai mã đầu B6-01 khai
thành lỗi HTTP ở N26 bằng chính chuỗi này. Đọc trang dùng lại `FILE_CORRUPT`,
`IMAGE_TOO_LARGE` của lõi (U-case).

`ORT_ERRORS` là các lớp ngoại lệ **thật** `onnxruntime` ném khi nạp hay chạy phiên: bộ
chạy B5-02…B5-04 bắt đúng bộ này, không `except Exception` (R-16).
"""

from typing import Final

from onnxruntime.capi.onnxruntime_pybind11_state import (  # type: ignore[import-untyped]  # module C++ không có stub
    DeviceReset,
    EngineError,
    EPFail,
    Fail,
    InvalidArgument,
    InvalidGraph,
    InvalidProtobuf,
    ModelLoadCanceled,
    ModelLoaded,
    ModelRequiresCompilation,
    NoModel,
    NoSuchFile,
    NotFound,
    NotImplemented,
    RuntimeException,
)

from packages.core import error_codes

MODEL_CHECKSUM_MISMATCH: Final = "MODEL_CHECKSUM_MISMATCH"
MODEL_FORMAT_UNSUPPORTED: Final = "MODEL_FORMAT_UNSUPPORTED"
MODEL_NOT_FOUND: Final = "MODEL_NOT_FOUND"
ML_DEVICE_UNAVAILABLE: Final = "ML_DEVICE_UNAVAILABLE"
GPU_LOCK_LOST: Final = "GPU_LOCK_LOST"
FILE_CORRUPT: Final = error_codes.FILE_CORRUPT.code
IMAGE_TOO_LARGE: Final = error_codes.IMAGE_TOO_LARGE.code
PIPELINE_ARTIFACT_MISSING: Final = "PIPELINE_ARTIFACT_MISSING"
"""Trang vào của bước không còn trong kho (lượt bị dọn giữa chừng) — B5-06c đánh hỏng lượt."""

ORT_ERRORS: Final[tuple[type[Exception], ...]] = (
    DeviceReset,
    EngineError,
    EPFail,
    Fail,
    InvalidArgument,
    InvalidGraph,
    InvalidProtobuf,
    ModelLoadCanceled,
    ModelLoaded,
    ModelRequiresCompilation,
    NoModel,
    NoSuchFile,
    NotFound,
    NotImplemented,
    RuntimeException,
)
