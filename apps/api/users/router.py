"""Chín route `/api/users` #38-#46 (B1-05 [2], [7]); router **mỏng**: mọi việc ở `service.py`.

Mọi route đòi `user.manage` (chỉ `admin`, C07). Người thực hiện lấy từ `Principal` (K05); `userId`
trong thân chỉ để guard W21 của khung so với đường (K09). #44 và #45 chia **một** hạn mức
`users_invite` (30 lượt/giờ/người thực hiện, kho an toàn, fail-closed). Route tĩnh
`/users/invitations` khai trước các route `{user_id}` cho khỏi bị nuốt.
"""

from typing import Final

from fastapi import Depends

from apps.api.access.deps import require_permission
from apps.api.core.deps import ClockDep, CurrentPrincipal, DbSession, Storage
from apps.api.core.ratelimit import key_user, rate_limit
from apps.api.core.routing import protected_router
from apps.api.users import service
from apps.api.users.schemas import (
    AdminUserListOut,
    AdminUserOut,
    DeleteUserBody,
    EmptyBody,
    InviteBody,
    RoleChangeBody,
    UserActivityOut,
    UserMembershipOut,
)

router = protected_router(tags=["users"])
ROUTERS: Final = (router,)

INVITE_RATE_LIMIT: Final = 30
INVITE_RATE_WINDOW_S: Final = 3600

_invite_limit: Final = rate_limit(
    "users_invite",
    limit=INVITE_RATE_LIMIT,
    window_s=INVITE_RATE_WINDOW_S,
    key=key_user,
    store="safe",
    on_error="closed",
)
"""Dùng chung cho #44 và #45: cùng tên, cùng khoá `key_user`, nên cùng một xô đếm."""

_MANAGE: Final = [Depends(require_permission("user.manage"))]
_MANAGE_INVITE: Final = [*_MANAGE, Depends(_invite_limit)]


@router.get("/users", dependencies=_MANAGE)
async def users_list_users(db: DbSession, storage: Storage) -> AdminUserListOut:
    """#38 — danh sách người chưa xoá mềm kèm `total`."""
    return await service.list_users(db, storage)


@router.post("/users/invitations", status_code=201, dependencies=_MANAGE_INVITE)
async def users_invite_users(
    body: InviteBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> list[AdminUserOut]:
    """#44 — mời một lô email vào cùng một vai (201); thư đi sau commit qua `issue_token`."""
    return await service.invite_users(
        db, storage, actor_id=principal.user_id, emails=body.emails, role=body.role, clock=clock
    )


@router.post("/users/invitations/{user_id}/resend", dependencies=_MANAGE_INVITE)
async def users_resend_invitation(
    user_id: str, body: EmptyBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> AdminUserOut:
    """#45 — gửi lại lời mời cho người `pending`; token cũ mất hiệu lực."""
    return await service.resend_invitation(db, storage, actor_id=principal.user_id, user_id=user_id, clock=clock)


@router.get("/users/{user_id}/memberships", dependencies=_MANAGE)
async def users_list_memberships(user_id: str, db: DbSession) -> list[UserMembershipOut]:
    """#39 — dự án người này là thành viên."""
    return await service.list_memberships(db, user_id)


@router.get("/users/{user_id}/activity", dependencies=_MANAGE)
async def users_list_activity(user_id: str, db: DbSession) -> list[UserActivityOut]:
    """#40 — nhật ký hoạt động của người này, mới nhất trước."""
    return await service.list_activity(db, user_id)


@router.patch("/users/{user_id}/role", dependencies=_MANAGE)
async def users_change_role(
    user_id: str, body: RoleChangeBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> AdminUserOut:
    """#41 — đổi vai; `userId` trong thân chỉ để guard W21."""
    return await service.change_role(
        db, storage, actor_id=principal.user_id, user_id=user_id, role=body.role, clock=clock
    )


@router.post("/users/{user_id}/disable", dependencies=_MANAGE)
async def users_disable_user(
    user_id: str, body: EmptyBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> AdminUserOut:
    """#42 — vô hiệu: thu hồi phiên và lời mời đang chờ."""
    return await service.disable_user(db, storage, actor_id=principal.user_id, user_id=user_id, clock=clock)


@router.post("/users/{user_id}/enable", dependencies=_MANAGE)
async def users_enable_user(
    user_id: str, body: EmptyBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> AdminUserOut:
    """#43 — bật lại người bị vô hiệu."""
    return await service.enable_user(db, storage, actor_id=principal.user_id, user_id=user_id, clock=clock)


@router.delete("/users/{user_id}", dependencies=_MANAGE)
async def users_delete_user(
    user_id: str, body: DeleteUserBody, principal: CurrentPrincipal, db: DbSession, storage: Storage, clock: ClockDep
) -> AdminUserOut:
    """#46 — xoá mềm, có thân xác nhận (W13); trả trạng thái ngay trước khi xoá."""
    return await service.delete_user(
        db,
        storage,
        actor_id=principal.user_id,
        user_id=user_id,
        confirm_email=body.confirm_email,
        clock=clock,
    )
