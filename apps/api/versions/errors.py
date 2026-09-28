"""Mã lỗi riêng của module phiên bản (B3-04 [2]); mã lõi ở `packages.core.error_codes`.

Cả hai đều 422 vì lỗi nằm ở **dữ liệu yêu cầu trỏ tới**, không phải ở quyền hay định dạng:
FE hiện thông báo riêng cho từng mã (không còn nội dung để xem / chọn nhầm tầng).
"""

from packages.core.errors import ERRORS

VERSION_SNAPSHOT_PURGED = ERRORS.define("VERSION_SNAPSHOT_PURGED", 422)
"""Phiên bản không còn ảnh chụp, hoặc ảnh chụp lệch lược đồ / không giải được (HOP-DONG-MOI §5)."""

VERSION_FLOOR_MISMATCH = ERRORS.define("VERSION_FLOOR_MISMATCH", 422)
"""Phiên bản không thuộc tầng `floorId` yêu cầu; ném kèm `field` (`floorId` hoặc `body.floorId`)."""
