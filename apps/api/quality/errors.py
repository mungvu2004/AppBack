"""Mã lỗi riêng của module chất lượng ảnh (B2-05b [2]); mã lõi (`VALIDATION`,
`IMAGE_TOO_LARGE`, `DEPENDENCY_UNAVAILABLE`, …) ở `packages.core.error_codes`.
"""

from packages.core.errors import ERRORS

QUALITY_DRAWING_CHANGED = ERRORS.define("QUALITY_DRAWING_CHANGED", 409)
"""Bản vẽ của tầng đổi giữa lúc đọc và lúc ghi (hoặc homography đã lưu lệch trang); FE đọc lại rồi thử lại."""

QUALITY_LAYER_REVIEWED = ERRORS.define("QUALITY_LAYER_REVIEWED", 422)
"""Tầng đã có hình học người duyệt trên bản vẽ đang dùng.

422 chứ không 409: trạng thái này không tự hết, mà FE coi 409 là thử lại được
(`src/lib/errors/kinds.ts:108`) nên sẽ lặp vô ích.
"""
