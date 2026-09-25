"""Mã lỗi của module bản vẽ (B2-04 [2]); mã lõi (`VALIDATION`, `FILE_CORRUPT`, …) ở
`packages.core.error_codes`, mã pipeline không phải HTTP ở `packages.core.pipeline`.
"""

from typing import Final

from packages.core.errors import ERRORS

UPLOAD_NOT_RECEIVING = ERRORS.define("UPLOAD_NOT_RECEIVING", 422)
"""#6: khúc gửi vào lượt tải đã `complete` hoặc `rejected` — không còn nhận thêm byte."""

UPLOAD_CHUNKS_CHANGED = ERRORS.define("UPLOAD_CHUNKS_CHANGED", 409)
"""#7: khúc bị ghi đè giữa lúc kiểm và lúc nối tệp; FE thử lại (`src/lib/errors/kinds.ts:108`)."""

FLOOR_DELETED: Final = "FLOOR_DELETED"
"""`error` của lượt chạy gặp tầng quá cửa sổ khôi phục hay dự án đã xoá mềm (BE-00 §7).

Hằng chuỗi, **không** `ERRORS.define`: nó không bao giờ là status của một response, chỉ là
giá trị cột `pipeline_runs.error_code` và trường `error` của `Progress`.
"""

PIPELINE_STALLED: Final = "PIPELINE_STALLED"
"""`error` của lượt chạy đã hết trần quét bù (BE-00 §7); hằng chuỗi như `FLOOR_DELETED`."""
