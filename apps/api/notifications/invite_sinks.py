"""Cài `ProjectInviteSink` của B2-02 (B4-02 [6] "Sink lời mời"): người được thêm vào dự án nhận thông báo.

Sink chạy **trong** giao dịch của N3: rollback thì không dòng, không sự kiện (J09) vì XADD nằm ở callback sau
commit của `notify`. `apps/api/project_members/sinks.py` dò `SINKS` qua `extensions`.
"""

from datetime import UTC
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.notifications.messages import project_invite
from apps.api.notifications.service import notify
from packages.core.clock import Clock
from packages.db.models.auth import User
from packages.db.models.notifications import INVITE_PLACE


class ProjectInviteNotifier:
    """Gửi `projectInvite` cho người vừa được thêm, trừ khi họ tự thêm mình."""

    async def on_member_added(
        self,
        db: AsyncSession,
        *,
        project_id: str,
        project_name: str,
        user_id: str,
        actor_id: str,
        clock: Clock,
    ) -> None:
        """Khoá khử trùng theo **giờ UTC**: thêm-gỡ-thêm lặp trong một giờ chỉ ra một thông báo (chống spam)."""
        if user_id == actor_id:
            return
        actor_name = (
            await db.execute(select(User.name).where(User.id == actor_id, User.deleted_at.is_(None)))
        ).scalar_one_or_none()
        await notify(
            db,
            user_id=user_id,
            kind="projectInvite",
            place=INVITE_PLACE,
            project_id=project_id,
            project_name=project_name,
            object_label=project_name,
            message=project_invite(actor_name),
            dedupe_key=f"projectInvite:{project_id}:{user_id}:{clock.now().astimezone(UTC):%Y%m%d%H}",
            clock=clock,
        )


SINKS: Final = (ProjectInviteNotifier(),)
