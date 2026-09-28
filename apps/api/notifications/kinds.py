"""Loại và nơi dẫn tới của thông báo (B4-02 [2]); nguồn duy nhất nằm ở model để CHECK, dây và mã dùng chung.

Không nhập `fastapi`, `jwt`, `argon2`: B5-06b (worker) gọi `notify` qua module này.
"""

from packages.db.models.notifications import FLOOR_PLACES, KINDS, PLACES, NotificationKind, NotificationPlace

__all__ = ["FLOOR_PLACES", "KINDS", "PLACES", "NotificationKind", "NotificationPlace"]
