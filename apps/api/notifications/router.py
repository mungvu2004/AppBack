"""Bốn route thông báo #19-#22 (B4-02 [2], [7]); router **mỏng**, việc ở `service.py`.

Bảo vệ bằng `protected_router`, Khoá `—`: không dependency quyền, chỉ đọc và ghi dữ liệu của `principal.user_id`
(K05). #20, #21 trả 204 thân rỗng.
"""

from datetime import datetime
from typing import Annotated, Final

from fastapi import Query, Response

from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession
from apps.api.core.pagination import MAX_LIMIT, decode_cursor, encode_cursor
from apps.api.core.routing import protected_router
from apps.api.notifications import service
from apps.api.notifications.payload import notification_wire
from apps.api.notifications.schemas import (
    NotificationEmptyBody,
    NotificationMarkReadBody,
    NotificationOut,
)
from apps.api.notifications.settings import get_notifications_settings

router = protected_router(tags=["notifications"])
ROUTERS: Final = (router,)

LIST_OP: Final = "notifications_list"
"""`op` ký vào cursor của #19; cursor ký kèm `user` nên không dùng được cho người khác."""
NEXT_CURSOR_HEADER: Final = "X-Next-Cursor"


@router.get("/notifications")
async def notifications_list(
    principal: CurrentPrincipal,
    db: DbSession,
    response: Response,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int | None, Query(ge=1, le=MAX_LIMIT)] = None,
) -> list[NotificationOut]:
    """#19 — mảng trần các thông báo còn hiện của người gọi, mới nhất trước.

    Không tham số → y như cũ (tối đa `NOTIFICATIONS_LIST_MAX`). "Xem cũ hơn" (UIFIX-B7): còn dòng cũ hơn thì
    header `X-Next-Cursor` mang cursor cho lượt gọi sau; thân vẫn là mảng trần để FE cũ không vỡ.
    """
    cap = get_notifications_settings().notifications_list_max
    size = min(limit or cap, cap)
    after = None
    if cursor is not None:
        pos = decode_cursor(cursor, LIST_OP, {"user": principal.user_id})
        after = (datetime.fromisoformat(pos["at"]), str(pos["id"]))
    rows = await service.list_notifications(db, principal.user_id, limit=size + 1, after=after)
    if len(rows) > size:
        rows = rows[:size]
        last = rows[-1]
        response.headers[NEXT_CURSOR_HEADER] = encode_cursor(
            LIST_OP, {"user": principal.user_id}, {"at": last.created_at.isoformat(), "id": last.id}
        )
    return [NotificationOut.model_validate(notification_wire(row)) for row in rows]


@router.post("/notifications/read", status_code=204, response_class=Response, response_model=None)
async def notifications_mark_read(
    body: NotificationMarkReadBody, principal: CurrentPrincipal, db: DbSession, clock: ClockDep
) -> None:
    """#20 — đánh dấu đã đọc theo danh sách id; id lạ hoặc của người khác bị bỏ qua."""
    await service.mark_read(db, principal.user_id, body.ids, clock)


@router.post("/notifications/read-all", status_code=204, response_class=Response, response_model=None)
async def notifications_mark_all_read(
    body: NotificationEmptyBody, principal: CurrentPrincipal, db: DbSession, clock: ClockDep
) -> None:
    """#21 — mọi thông báo chưa đọc của người gọi thành đã đọc."""
    await service.mark_all_read(db, principal.user_id, clock)


@router.post("/notifications/{notification_id}/accept-invite")
async def notifications_accept_invite(
    notification_id: str, body: NotificationEmptyBody, principal: CurrentPrincipal, db: DbSession, clock: ClockDep
) -> NotificationOut:
    """#22 — xác nhận lời mời (idempotent); không đổi thành viên hay vai."""
    row = await service.accept_invite(db, principal.user_id, notification_id, clock)
    return NotificationOut.model_validate(notification_wire(row))
