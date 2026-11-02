"""Mã lỗi riêng của AI chọn phong cách; mã lõi (`NOT_FOUND`, `VALIDATION`) ở `packages.core.error_codes`.

Câu chữ cho người dùng (FE): `DESIGN_DIRECTOR_DISABLED` "Tính năng AI gợi ý nội thất đang tạm tắt.",
`DESIGN_DIRECTOR_QUOTA` "Dự án đã dùng hết lượt AI gợi ý nội thất hôm nay, vui lòng thử lại vào ngày mai."
"""

from typing import Final

from packages.core.errors import ERRORS

DESIGN_DIRECTOR_DISABLED = ERRORS.define("DESIGN_DIRECTOR_DISABLED", 503)
"""Công tắc tắt hoặc thiếu khoá service account."""

DESIGN_DIRECTOR_QUOTA = ERRORS.define("DESIGN_DIRECTOR_QUOTA", 429)
"""Chủ dự án đã dùng hết `DESIGN_DIRECTOR_DAILY_QUOTA` lượt trong ngày UTC."""

RETRY_AFTER_S: Final = 10
"""`Retry-After` của cả hai mã — W9 giới hạn 1-10 s; FE không tự thử lại hai mã này."""
