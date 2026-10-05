"""Model dây của #19-#22 (B4-02 [2]): `NotificationOut` (response) và ba thân strict.

`NotificationOut` gương `NotificationSchema` của FE: `floorId`, `excerpt` vắng khi rỗng (W2); không có
`userId`, `dedupeKey`, `streamId` (K01). Cùng lớp này là `event_model` của luồng S2 nên sự kiện lệch mẫu bị bỏ.
"""

from typing import Annotated, Any, Final

from pydantic import Field, StringConstraints, field_validator

from apps.api.core.wire import WireDatetime, WireModel, WireRequest
from apps.api.notifications.settings import MARK_MAX_DEFAULT, get_notifications_settings
from packages.db.models.notifications import NotificationKind, NotificationPlace

ID_MAX_LEN: Final = 64


class NotificationOut(WireModel):
    """Một `Notification` của FE."""

    id: str
    kind: NotificationKind
    place: NotificationPlace
    project_id: str
    project_name: str
    floor_id: str | None = None
    object_label: str
    message: str
    excerpt: str | None = None
    is_read: bool
    created_at: WireDatetime


class NotificationMarkReadBody(WireRequest):
    """#20: `{ids}`, 1-`NOTIFICATIONS_MARK_MAX` id, mỗi id 1-64 ký tự; sai bất kỳ điểm nào → `field:"ids"`."""

    # Ràng buộc chỉ để `openapi.json` phơi `minItems`/`maxItems`/`maxLength` (số theo mặc định của settings);
    # lỗi vẫn do validator `before` ném trước nên `field` luôn là `ids`.
    ids: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=ID_MAX_LEN)]],
        Field(min_length=1, max_length=MARK_MAX_DEFAULT),
    ]

    @field_validator("ids", mode="before")
    @classmethod
    def _bounded_ids(cls, value: Any) -> Any:
        """Kiểm cả mảng ở một chỗ để `field` luôn là `ids` (không `ids.3`)."""
        limit = get_notifications_settings().notifications_mark_max
        if not isinstance(value, list) or not 1 <= len(value) <= limit:
            raise ValueError(f"ids phải là mảng 1-{limit} phần tử")
        if not all(isinstance(item, str) and 1 <= len(item) <= ID_MAX_LEN for item in value):
            raise ValueError(f"mỗi id phải là chuỗi 1-{ID_MAX_LEN} ký tự")
        return value


class NotificationEmptyBody(WireRequest):
    """#21, #22: thân `{}`; khoá lạ → 422 (C03), mảng → 422 (C02)."""
