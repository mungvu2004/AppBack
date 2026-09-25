"""Nghiệp vụ quản trị người dùng #38-#46 (B1-05 [6]): đọc, và sáu thao tác ghi dưới khoá tập admin.

**Khoá tập admin** (`lock_admin_set`) là câu đầu tiên của mọi route ghi, cùng giao dịch ghi:
`SELECT ... FOR UPDATE` mọi admin `active` theo `id ASC` rồi đòi người thực hiện còn trong tập
(vai vừa bị hạ mà cache còn ≤ 5 s thì không được làm gì tiếp → 403). Vì mọi route ghi đều
nhường nhau ở đó, hai admin hạ vai nhau song song chỉ một bên thắng và hệ thống luôn còn ≥ 1
admin `active` (C14). Khoá người mục tiêu đến sau (`WriteScope`).

Quyết định (`if/raise`) đọc dữ liệu vừa `await` được tách vào hàm **đồng bộ** riêng `_require_*`
— coverage không đo được nhánh nằm ngay sau `await` của SQLAlchemy async (NO-130).
Mọi thư đi qua `issue_token` (sau commit, K17); module này không chạm SMTP.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache
from typing import Final, cast

from pydantic import PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import and_, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.auth.sessions import bump_token_version, revoke_sessions
from apps.api.auth_recovery.tokens import InvitationWindow, issue_token, latest_invitations, revoke_tokens
from apps.api.me.avatar import avatar_url
from apps.api.projects.memberships import (
    count_projects_of_users,
    list_projects_of_user,
    remove_user_from_all_projects,
)
from apps.api.users.errors import (
    USER_CONFIRM_EMAIL_MISMATCH,
    USER_EMAIL_TAKEN,
    USER_LAST_ADMIN,
    USER_NOT_PENDING,
    USER_SELF_MODIFICATION,
)
from apps.api.users.schemas import (
    AdminUserListOut,
    AdminUserOut,
    UserActivityOut,
    UserMembershipOut,
    UserRole,
    UserStatus,
)
from packages.core.clock import Clock
from packages.core.error_codes import FORBIDDEN, NOT_FOUND, VALIDATION
from packages.core.ids import new_id
from packages.core.text import nfc, normalize_email
from packages.db.hooks import on_after_commit
from packages.db.models.access import OBJECT_LABEL_MAX, ActivityLog
from packages.db.models.auth import NAME_MAX, User
from packages.storage.port import ObjectStorage

_log: Final = logging.getLogger(__name__)

_ACTIVE_ADMIN: Final = and_(User.role == "admin", User.status == "active", User.deleted_at.is_(None))
_LIVE_ROW: Final = text("deleted_at IS NULL")
"""Điều kiện của partial unique `uq_users_email` — `ON CONFLICT` phải nhắm đúng nó."""


class UsersSettings(BaseSettings):
    """Trần của #38-#40 và #44 (B1-05 [5]); mọi giá trị nguyên dương, test C15 đặt = 3."""

    model_config = SettingsConfigDict(extra="ignore", env_file=None)

    users_list_max: PositiveInt = 1000
    user_memberships_max: PositiveInt = 1000
    user_activity_max: PositiveInt = 200
    invite_batch_max: PositiveInt = 50


@cache
def get_users_settings() -> UsersSettings:
    """Cấu hình của tiến trình, đọc biến môi trường một lần (đọc lười như `projects/settings.py`)."""
    return UsersSettings()


def reset_users_settings_cache() -> None:
    """Chỉ cho test: đọc lại biến môi trường ở lần gọi sau."""
    get_users_settings.cache_clear()


# --------------------------------------------------------------------------- quyết định thuần


def _require_user(user: User | None) -> User:
    """`user`, hay 404 `resource:"user"` khi không có hoặc đã xoá mềm."""
    if user is None:
        raise NOT_FOUND.error(resource="user")
    return user


def _require_actor_in(admins: Sequence[str], actor_id: str) -> None:
    """Người thực hiện phải còn là admin `active` trong giao dịch ghi, không thì 403 (K34, BE-00 §5)."""
    if actor_id not in admins:
        raise FORBIDDEN.error()


def _require_pending(user: User) -> None:
    """#45: chỉ người `pending` mới được gửi lại lời mời."""
    if user.status != "pending":
        raise USER_NOT_PENDING.error()


def _require_confirm(user: User, confirm_email: str) -> None:
    """#46: `confirmEmail` so qua `normalize_email` (K20), sai → 422 `field:"confirmEmail"`."""
    if normalize_email(confirm_email) != user.email_normalized:
        raise USER_CONFIRM_EMAIL_MISMATCH.error(field="confirmEmail")


def _require_batch_size(emails: Sequence[str]) -> None:
    """#44: quá `INVITE_BATCH_MAX` email (đếm **trước** khi bỏ trùng) → 422 `VALIDATION` `field:"emails"`."""
    if len(emails) > get_users_settings().invite_batch_max:
        raise VALIDATION.error(field="emails")


def _require_none_taken(existing: dict[str, User]) -> None:
    """#44: mọi email có sẵn phải là người `pending`; `active`/`disabled` → `USER_EMAIL_TAKEN`."""
    if any(user.status != "pending" for user in existing.values()):
        raise USER_EMAIL_TAKEN.error(field="emails")


def _pending_or_taken(found: User | None) -> User:
    """Sau tranh chấp `uq_users_email`: người vừa đọc lại phải là `pending`, không thì `USER_EMAIL_TAKEN`.

    `None` (người biến mất giữa hai lệnh) chỉ có thể do một lượt xoá song song, mà lượt ấy
    cũng phải qua khoá tập admin ta đang giữ — coi như "đã bị chiếm" chứ không 500.
    """
    if found is None or found.status != "pending":
        raise USER_EMAIL_TAKEN.error(field="emails")
    return found


@dataclass(frozen=True, slots=True)
class WriteScope:
    """Người thực hiện, mục tiêu đã khoá và tập admin `active` đã khoá của một lượt ghi."""

    actor_id: str
    target: User
    admins: tuple[str, ...]

    def forbid_self(self) -> None:
        """#41, #42, #46: mục tiêu là chính người thực hiện → 422 `USER_SELF_MODIFICATION`."""
        if self.target.id == self.actor_id:
            raise USER_SELF_MODIFICATION.error()

    def forbid_last_admin(self) -> None:
        """Mục tiêu là admin `active` duy nhất → 422 `USER_LAST_ADMIN`.

        Người thực hiện luôn nằm trong tập nên với tập 1 người thì mục tiêu chính là họ và
        `forbid_self` đã chặn trước; đây là lớp chốt cuối nếu thứ tự kiểm đổi (C14).
        """
        if self.target.id in self.admins and len(self.admins) == 1:
            raise USER_LAST_ADMIN.error()


# --------------------------------------------------------------------------- khoá


async def lock_admin_set(db: AsyncSession, actor_id: str) -> tuple[str, ...]:
    """Khoá admin `active` (`id ASC`, thứ tự cố định chống deadlock) và đòi `actor_id` còn trong đó."""
    result = await db.execute(select(User.id).where(_ACTIVE_ADMIN).order_by(User.id).with_for_update())
    admins = tuple(result.scalars())
    _require_actor_in(admins, actor_id)
    return admins


async def _lock_user(db: AsyncSession, user_id: str) -> User | None:
    """Người chưa xoá mềm, `FOR UPDATE`; `populate_existing` bỏ bản đã nạp cũ trong session."""
    stmt = (
        select(User)
        .where(User.id == user_id, User.deleted_at.is_(None))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def open_scope(db: AsyncSession, actor_id: str, target_id: str) -> WriteScope:
    """Câu đầu của mọi route ghi #41-#46: khoá tập admin rồi khoá mục tiêu (404 nếu không có)."""
    admins = await lock_admin_set(db, actor_id)
    target = _require_user(await _lock_user(db, target_id))
    return WriteScope(actor_id=actor_id, target=target, admins=admins)


async def _log_activity(db: AsyncSession, scope: WriteScope, kind: ActivityKind, clock: Clock) -> None:
    """Một dòng nhật ký của thao tác lên `scope.target` (C18): `object_code` = id, nhãn = email."""
    await record_activity(
        db,
        actor_id=scope.actor_id,
        kind=kind,
        object_code=scope.target.id,
        object_label=scope.target.email[:OBJECT_LABEL_MAX],
        clock=clock,
    )


# --------------------------------------------------------------------------- dựng AdminUser


def _admin_view(user: User, *, count: int, invite: InvitationWindow | None, avatar: str | None) -> AdminUserOut:
    """`AdminUser` của một người; lời mời chỉ hiện với người `pending` có lời mời chưa dùng."""
    window = invite if user.status == "pending" else None
    return AdminUserOut(
        avatar_url=avatar,
        email=user.email,
        id=user.id,
        invited_at=None if window is None else window.invited_at,
        invite_expires_at=None if window is None else window.expires_at,
        last_active_at=user.last_active_at,
        name=user.name,
        project_count=count,
        role=cast("UserRole", user.role),
        status=cast("UserStatus", user.status),
    )


async def admin_views(db: AsyncSession, storage: ObjectStorage, users: Sequence[User]) -> list[AdminUserOut]:
    """`AdminUser` cho cả lô bằng **hai** truy vấn gộp (số dự án, lời mời); `avatar_url` không chạm DB."""
    ids = [user.id for user in users]
    counts = await count_projects_of_users(db, ids)
    invites = await latest_invitations(db, ids)
    return [
        _admin_view(
            user, count=counts[user.id], invite=invites.get(user.id), avatar=await avatar_url(storage, user.avatar_key)
        )
        for user in users
    ]


async def _view_of(db: AsyncSession, storage: ObjectStorage, user: User) -> AdminUserOut:
    """`AdminUser` của đúng một người."""
    return (await admin_views(db, storage, [user]))[0]


# --------------------------------------------------------------------------- đọc #38-#40


async def list_users(db: AsyncSession, storage: ObjectStorage) -> AdminUserListOut:
    """#38: người chưa xoá mềm `created_at ASC, id ASC`, tối đa `USERS_LIST_MAX`; `total` đếm đủ."""
    live = User.deleted_at.is_(None)
    page = select(User).where(live).order_by(User.created_at, User.id).limit(get_users_settings().users_list_max)
    users = list((await db.execute(page)).scalars())
    total = (await db.execute(select(func.count()).select_from(User).where(live))).scalar_one()
    return AdminUserListOut(total=total, users=await admin_views(db, storage, users))


async def _read_user(db: AsyncSession, user_id: str) -> User:
    """Người chưa xoá mềm (không khoá) cho các route đọc; không có → 404."""
    stmt = select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return _require_user((await db.execute(stmt)).scalar_one_or_none())


async def list_memberships(db: AsyncSession, user_id: str) -> list[UserMembershipOut]:
    """#39: dự án chưa xoá mềm của người này (`projectId ASC`); `role` là vai hệ thống hiện tại."""
    user = await _read_user(db, user_id)
    refs = await list_projects_of_user(db, user_id, limit=get_users_settings().user_memberships_max)
    role = cast("UserRole", user.role)
    return [UserMembershipOut(project_id=ref.id, project_name=ref.name, role=role) for ref in refs]


async def list_activity(db: AsyncSession, user_id: str) -> list[UserActivityOut]:
    """#40: nhật ký do người này thực hiện, mới nhất trước, tối đa `USER_ACTIVITY_MAX`."""
    await _read_user(db, user_id)
    stmt = (
        select(ActivityLog)
        .where(ActivityLog.actor_id == user_id)
        .order_by(ActivityLog.at.desc(), ActivityLog.id.desc())
        .limit(get_users_settings().user_activity_max)
    )
    rows = (await db.execute(stmt)).scalars()
    return [
        UserActivityOut(
            id=str(row.id), at=row.at, kind=row.kind, object_code=row.object_code, object_label=row.object_label
        )
        for row in rows
    ]


# --------------------------------------------------------------------------- ghi #41-#43


async def change_role(
    db: AsyncSession, storage: ObjectStorage, *, actor_id: str, user_id: str, role: UserRole, clock: Clock
) -> AdminUserOut:
    """#41: đổi vai; token cũ của người đó mất giá trị (`bump_token_version`). Không đổi → 200, không ghi gì."""
    scope = await open_scope(db, actor_id, user_id)
    scope.forbid_self()
    if scope.target.role != role:
        scope.forbid_last_admin()
        scope.target.role = role
        await bump_token_version(db, user_id)
        await _log_activity(db, scope, ActivityKind.USER_ROLE_CHANGE, clock)
    return await _view_of(db, storage, scope.target)


async def disable_user(
    db: AsyncSession, storage: ObjectStorage, *, actor_id: str, user_id: str, clock: Clock
) -> AdminUserOut:
    """#42: `disabled`, thu hồi mọi phiên và lời mời đang chờ. Đã `disabled` → 200, không ghi gì."""
    scope = await open_scope(db, actor_id, user_id)
    scope.forbid_self()
    if scope.target.status != "disabled":
        scope.forbid_last_admin()
        scope.target.status = "disabled"
        await revoke_sessions(db, user_id=user_id, reason="disabled", clock=clock)
        await bump_token_version(db, user_id)
        await revoke_tokens(db, user_id=user_id, clock=clock)
        await _log_activity(db, scope, ActivityKind.USER_DISABLE, clock)
    return await _view_of(db, storage, scope.target)


async def enable_user(
    db: AsyncSession, storage: ObjectStorage, *, actor_id: str, user_id: str, clock: Clock
) -> AdminUserOut:
    """#43: bật lại → `active` nếu đã có mật khẩu, không thì `pending` (cần gửi lại lời mời)."""
    scope = await open_scope(db, actor_id, user_id)
    if scope.target.status == "disabled":
        scope.target.status = "active" if scope.target.password_hash else "pending"
        await _log_activity(db, scope, ActivityKind.USER_ENABLE, clock)
    return await _view_of(db, storage, scope.target)


# --------------------------------------------------------------------------- mời #44, #45


def _display_name(email: str) -> str:
    """Tên tạm của người được mời: phần trước `@`, NFC, cắt ở `NAME_MAX` (CHECK `name_length`)."""
    return nfc(email.partition("@")[0])[:NAME_MAX]


async def _lock_by_emails(db: AsyncSession, keys: Sequence[str]) -> dict[str, User]:
    """Người chưa xoá mềm theo `email_normalized`, khoá `ORDER BY` nó (hai lô song song không deadlock)."""
    stmt = (
        select(User)
        .where(User.email_normalized.in_(keys), User.deleted_at.is_(None))
        .order_by(User.email_normalized)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return {user.email_normalized: user for user in (await db.execute(stmt)).scalars()}


async def _insert_pending(db: AsyncSession, *, email: str, key: str, role: UserRole, clock: Clock) -> User | None:
    """Chèn người `pending`; `None` khi thua cuộc đua `uq_users_email`.

    `ON CONFLICT DO NOTHING` nhắm đúng partial unique thay vì savepoint: trên bản SQLAlchemy/asyncpg
    của repo, `begin_nested()` bắn `after_commit` thật của cả phiên khi savepoint đóng nên thư
    có thể đi trước commit (K17) — cùng lý do và cùng cách với `issue_token` (B1-03).
    """
    stmt = (
        pg_insert(User)
        .values(
            id=new_id("usr", clock),
            email=email,
            email_normalized=key,
            name=_display_name(email),
            role=role,
            status="pending",
        )
        .on_conflict_do_nothing(index_elements=["email_normalized"], index_where=_LIVE_ROW)
        .returning(User)
    )
    return (await db.execute(stmt)).scalars().first()


async def _create_or_reuse(db: AsyncSession, *, email: str, key: str, role: UserRole, clock: Clock) -> User:
    """Người `pending` mới, hoặc — nếu thua tranh chấp email — người `pending` đã có (đọc lại `FOR UPDATE`)."""
    created = await _insert_pending(db, email=email, key=key, role=role, clock=clock)
    if created is not None:
        return created
    return _pending_or_taken((await _lock_by_emails(db, [key])).get(key))


async def _invite_one(
    db: AsyncSession, *, actor_id: str, email: str, key: str, role: UserRole, existing: User | None, clock: Clock
) -> User:
    """Mời một email: giữ/tạo người `pending`, đổi vai nếu khác, phát token `invite`, ghi `USER_INVITE`."""
    user = (
        existing if existing is not None else await _create_or_reuse(db, email=email, key=key, role=role, clock=clock)
    )
    if user.role != role:
        user.role = role
        await bump_token_version(db, user.id)
    await issue_token(db, user_id=user.id, purpose="invite", clock=clock)
    scope = WriteScope(actor_id=actor_id, target=user, admins=())
    await _log_activity(db, scope, ActivityKind.USER_INVITE, clock)
    return user


async def invite_users(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    actor_id: str,
    emails: Sequence[str],
    role: UserRole,
    clock: Clock,
) -> list[AdminUserOut]:
    """#44: tất cả hoặc không có gì; xử lý theo `email_normalized ASC`, trả theo thứ tự đầu vào.

    Lỗi bất kỳ (kể cả `USER_EMAIL_TAKEN` giữa chừng) làm `AppRoute` rollback cả giao dịch:
    không người nào được tạo và không callback gửi thư nào chạy (K17). Vòng lặp có `await`
    mỗi email vì `issue_token` là một lệnh riêng (trần `INVITE_BATCH_MAX`, mặc định 50).
    """
    _require_batch_size(emails)
    await lock_admin_set(db, actor_id)
    first_seen: dict[str, str] = {}
    for email in emails:
        first_seen.setdefault(normalize_email(email), email)  # bỏ trùng theo K20, giữ thứ tự đầu
    keys = {email: key for key, email in first_seen.items()}
    existing = await _lock_by_emails(db, list(keys.values()))
    _require_none_taken(existing)
    invited: dict[str, User] = {}
    for email, key in sorted(keys.items(), key=lambda pair: pair[1]):
        invited[key] = await _invite_one(
            db, actor_id=actor_id, email=email, key=key, role=role, existing=existing.get(key), clock=clock
        )
    return await admin_views(db, storage, [invited[key] for key in first_seen])


async def resend_invitation(
    db: AsyncSession, storage: ObjectStorage, *, actor_id: str, user_id: str, clock: Clock
) -> AdminUserOut:
    """#45: token `invite` mới thay token cũ; mục tiêu phải `pending`."""
    scope = await open_scope(db, actor_id, user_id)
    _require_pending(scope.target)
    await issue_token(db, user_id=user_id, purpose="invite", clock=clock)
    await _log_activity(db, scope, ActivityKind.USER_INVITE_RESEND, clock)
    return await _view_of(db, storage, scope.target)


# --------------------------------------------------------------------------- xoá #46


def _warn_orphans(project_ids: Sequence[str], user_id: str) -> None:
    """Log `project_orphaned` cho từng dự án không còn người sửa; không chặn xoá, không thêm admin (BE-00 §4)."""
    for project_id in project_ids:
        _log.warning("project_orphaned", extra={"projectId": project_id, "userId": user_id})


async def delete_user(
    db: AsyncSession, storage: ObjectStorage, *, actor_id: str, user_id: str, confirm_email: str, clock: Clock
) -> AdminUserOut:
    """#46: xoá **mềm** (email được giải phóng), trả `AdminUser` dựng **trước** khi xoá.

    Dự án mồ côi chỉ log **sau commit** (`on_after_commit`): giao dịch hỏng thì không có log giả.
    """
    scope = await open_scope(db, actor_id, user_id)
    _require_confirm(scope.target, confirm_email)
    scope.forbid_self()
    scope.forbid_last_admin()
    view = await _view_of(db, storage, scope.target)
    scope.target.deleted_at = clock.now()
    scope.target.status = "disabled"
    await revoke_sessions(db, user_id=user_id, reason="deleted", clock=clock)
    await bump_token_version(db, user_id)
    await revoke_tokens(db, user_id=user_id, clock=clock)
    orphans = await remove_user_from_all_projects(db, user_id, clock=clock)
    await _log_activity(db, scope, ActivityKind.USER_DELETE, clock)
    on_after_commit(db, lambda: _warn_orphans(orphans, user_id))
    return view
