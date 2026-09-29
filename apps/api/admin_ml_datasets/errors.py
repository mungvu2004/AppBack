"""Mã lỗi riêng của dataset ML (B6-02 [2]); mã lõi ở `packages.core.error_codes`.

Hai mã tranh chấp tên/khoá (409, K18): tên đã dùng, hay đang có bản đang dựng. Bốn hằng
`failureCode` **không** qua `ERRORS.define` — chúng không bao giờ là thân lỗi HTTP, chỉ là
giá trị cột `failure_code` của một bản `failed` (`versions.fail_version`), nên không cần
đăng ký vào `ErrorRegistry` (khác `MODEL_VERSION_NOT_EVALUATED` của B6-01, thứ luôn là lỗi
của một request).
"""

from typing import Final

from packages.core.errors import ERRORS

DATASET_NAME_TAKEN = ERRORS.define("DATASET_NAME_TAKEN", 409)
"""`name_key` (`casefold` của `name` NFC) đã có dataset khác dùng."""

DATASET_BUILD_IN_PROGRESS = ERRORS.define("DATASET_BUILD_IN_PROGRESS", 409)
"""Dataset đã có một bản `building`; `versions.start_version` trả `None`."""

DATASET_EMPTY: Final = "DATASET_EMPTY"
"""`failureCode`: lượt dựng không tìm được mẫu nào."""

DATASET_TOO_LARGE: Final = "DATASET_TOO_LARGE"
"""`failureCode`: vượt `DATASET_MAX_SAMPLES` hay `SampleWriter.max_bytes`."""

DATASET_FAMILY_UNSUPPORTED: Final = "DATASET_FAMILY_UNSUPPORTED"
"""`failureCode`: họ `dimensionReading` (ống xử lý dạng đọc, không có mẫu ảnh dựng được)."""

DATASET_BUILD_TIMEOUT: Final = "DATASET_BUILD_TIMEOUT"
"""`failureCode`: lịch quét (`sweep_dataset_version_builds`) đóng bản không tiến triển."""
