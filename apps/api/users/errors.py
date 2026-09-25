"""Mã lỗi riêng của quản trị người dùng (B1-05 [2]); mã lõi ở `packages.core.error_codes`."""

from packages.core.errors import ERRORS

USER_SELF_MODIFICATION = ERRORS.define("USER_SELF_MODIFICATION", 422)
"""#41, #42, #46: người thực hiện tự đổi vai, tự vô hiệu, tự xoá chính mình."""

USER_LAST_ADMIN = ERRORS.define("USER_LAST_ADMIN", 422)
"""#41, #42, #46: hạ vai, vô hiệu hay xoá admin `active` cuối cùng (BE-00 §5)."""

USER_EMAIL_TAKEN = ERRORS.define("USER_EMAIL_TAKEN", 422)
"""#44: email đã thuộc người `active` hay `disabled`; ném kèm `field="emails"`."""

USER_NOT_PENDING = ERRORS.define("USER_NOT_PENDING", 422)
"""#45: gửi lại lời mời cho người không còn `pending`."""

USER_CONFIRM_EMAIL_MISMATCH = ERRORS.define("USER_CONFIRM_EMAIL_MISMATCH", 422)
"""#46: `confirmEmail` không khớp email người bị xoá; ném kèm `field="confirmEmail"`."""
