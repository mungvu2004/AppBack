"""Factory thông báo cho test (B4-02).

Ghi thẳng một dòng `notifications`, không qua `notify`: test cần dựng dòng cũ, dòng đã/chưa phát (`stream_id`), dòng
cùng `created_at`. Như `make_project`, hàm chỉ `flush` — test tự quyết lúc commit.
"""

import secrets
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.models.auth import User
from packages.db.models.notifications import NotificationRow
from packages.db.models.projects import Project

_MESSAGES = {
    "aiCompleted": "hệ thống AI đã xử lý xong bản vẽ",
    "violationFound": "phát hiện 2 vi phạm luật ở",
    "projectInvite": "bạn vừa được thêm vào dự án",
}


async def make_notification(
    db: AsyncSession,
    *,
    user: User,
    project: Project,
    kind: str = "aiCompleted",
    place: str = "walls",
    floor_level_id: str | None = "L-0000000001",
    created_at: datetime | None = None,
    is_read: bool = False,
    stream_id: str | None = "0-1",
) -> NotificationRow:
    """Một thông báo đã `flush`; `stream_id="0-1"` nghĩa là đã phát, `None` để thử quét bù."""
    clock = SystemClock()
    at = created_at if created_at is not None else clock.now()
    row = NotificationRow(
        id=new_id("ntf", clock),
        user_id=user.id,
        kind=kind,
        place=place,
        project_id=project.id,
        project_name=project.name,
        floor_level_id=floor_level_id,
        object_label="Tường ngoài" if kind != "projectInvite" else project.name,
        message=_MESSAGES[kind],
        is_read=is_read,
        dedupe_key=f"factory:{secrets.token_hex(8)}",
        stream_id=stream_id,
        created_at=at,
        updated_at=at,
    )
    db.add(row)
    await db.flush()
    return row
