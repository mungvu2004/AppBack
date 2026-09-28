"""Mã lỗi riêng của cấu hình luật (B3-05 [2]); đều 422 và `field` trỏ `body.overrides` (trừ `GENERAL`)."""

from packages.core.errors import ERRORS

RULE_CODE_UNKNOWN = ERRORS.define("RULE_CODE_UNKNOWN", 422)
"""Mã đúng mẫu nhưng không thuộc 25 mã và không phải `GENERAL`."""

RULE_THRESHOLD_UNKNOWN = ERRORS.define("RULE_THRESHOLD_UNKNOWN", 422)
"""Khoá ngoài 26 khoá, hoặc khoá nằm dưới mã khác mã mà spec của nó thuộc về."""

RULE_THRESHOLD_OUT_OF_RANGE = ERRORS.define("RULE_THRESHOLD_OUT_OF_RANGE", 422)
"""Giá trị ngoài `[min, max]` của spec."""

RULE_GENERAL_NOT_TOGGLEABLE = ERRORS.define("RULE_GENERAL_NOT_TOGGLEABLE", 422)
"""`GENERAL` mang `enabled` hoặc `severity`; `field` là `body.overrides.GENERAL.enabled` (hoặc `.severity`)."""
