"""Nhà cung cấp luồng SSE `notifications` — luồng S2 của hợp đồng (B4-02 [2]).

Trung tâm SSE (B4-01) dò file này; luồng thông báo chỉ đọc stream của chính người gọi nên không có `policy`
lẫn `snapshot`. Việc của module chỉ là siết mẫu sự kiện: khung lệch `NotificationOut` bị luồng bỏ.
"""

from typing import Final

from apps.api.notifications.schemas import NotificationOut
from apps.api.streams.providers import StreamProvider

PROVIDERS: Final = (StreamProvider(kind="notifications", event_model=NotificationOut),)
