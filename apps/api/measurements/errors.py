"""Mã lỗi riêng của module phép đo (B2-07 [2]); mã lõi ở `packages.core.error_codes`."""

from packages.core.errors import ERRORS

MEASUREMENT_ID_TAKEN = ERRORS.define("MEASUREMENT_ID_TAKEN", 409)
"""#17: cùng id, khác thân; ném kèm `field="id"`."""

MEASUREMENT_LIMIT_REACHED = ERRORS.define("MEASUREMENT_LIMIT_REACHED", 422)
"""#17: dự án đã đủ `MEASUREMENTS_MAX` phép đo, hoặc tổng điểm sẽ vượt `MEASUREMENT_POINTS_TOTAL_MAX`."""
