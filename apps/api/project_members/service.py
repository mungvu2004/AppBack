"""Nghiệp vụ N3 thêm và N4 gỡ thành viên (B2-02 [6]); không nhập `fastapi`.

Thứ tự khoá cố định (BE-00 §7): N4 khoá tập người sửa (`lock_editor_ids`) **trước** mọi khoá
khác, rồi dòng membership, và `touch_project` luôn là lời khoá cuối. Nhờ vậy hai người sửa duy
nhất gỡ lẫn nhau chỉ một bên thắng (C14). N3 không khoá gì trước `ON CONFLICT DO NOTHING`, nên
hai lượt cùng email nối đuôi nhau: lượt sau chờ lượt trước commit rồi thấy `False`.

Quyết định đọc dữ liệu vừa `await` được tách vào hàm **đồng bộ** `_require_*` (NO-130: coverage
không đo được nhánh nằm ngay sau `await` của SQLAlchemy async).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.project_members.errors import MEMBER_LAST_EDITOR, MEMBER_USER_UNAVAILABLE
from apps.api.project_members.sinks import invite_sink
from apps.api.projects.memberships import add_member, lock_editor_ids, remove_member
from apps.api.projects.summaries import touch_project
from apps.api.projects.wire import UserOut, user_out
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.ids import is_id
from packages.core.text import normalize_email
from packages.db.models.access import OBJECT_LABEL_MAX
from packages.db.models.auth import User
from packages.db.models.projects import ProjectMembership
from packages.storage.port import ObjectStorage


def _require_available(user: User | None) -> User:
    """Người có thể được thêm: có tài khoản chưa xoá mềm và không `disabled`; `pending` được.

    Hai lý do từ chối cùng một mã và một thân để không lộ email nào có tài khoản (B2-02 [9]).
    """
    if user is None or user.status == "disabled":
        raise MEMBER_USER_UNAVAILABLE.error(field="email")
    return user


def _require_member(user: User | None) -> User:
    """N4: người không phải thành viên (hay đã xoá mềm) → 404 `resource:"member"`."""
    if user is None:
        raise NOT_FOUND.error(resource="member")
    return user


def _require_not_last_editor(editors: list[str], user_id: str) -> None:
    """N4: gỡ người sửa cuối → 422 `MEMBER_LAST_EDITOR`; tự gỡ khi còn người sửa khác thì được."""
    if editors == [user_id]:
        raise MEMBER_LAST_EDITOR.error()


def _require_wire_id(user_id: str) -> None:
    """N4: `{user_id}` sai mẫu `usr_<ULID>` → 404 `resource:"member"`, không truy vấn."""
    if not is_id("usr", user_id):
        raise NOT_FOUND.error(resource="member")


async def add_project_member(
    db: AsyncSession,
    storage: ObjectStorage | None,
    *,
    project_id: str,
    project_name: str,
    actor_id: str,
    email: str,
    clock: Clock,
    app: object | None,
) -> tuple[UserOut, bool]:
    """N3: thêm người theo email; trả `(UserOut, created)` — `created=False` là đã là thành viên (200).

    Chỉ khi thêm mới mới ghi nhật ký, gọi sink và đẩy `updated_at` (`touch_project` sau cùng).
    Sink ném thì lỗi nổi lên và giao dịch rollback cả lượt (không nuốt).
    """
    stmt = select(User).where(User.email_normalized == normalize_email(email), User.deleted_at.is_(None))
    user = _require_available((await db.execute(stmt)).scalar_one_or_none())
    created = await add_member(db, project_id=project_id, user_id=user.id, added_by=actor_id, clock=clock)
    if created:
        await record_activity(
            db,
            actor_id=actor_id,
            kind=ActivityKind.MEMBER_ADD,
            object_code=user.id,
            object_label=user.email[:OBJECT_LABEL_MAX],
            clock=clock,
            project_id=project_id,
        )
        await invite_sink(app=app).on_member_added(
            db, project_id=project_id, project_name=project_name, user_id=user.id, actor_id=actor_id, clock=clock
        )
        await touch_project(db, project_id=project_id, clock=clock)
    return await user_out(user, storage), created


async def remove_project_member(
    db: AsyncSession,
    storage: ObjectStorage | None,
    *,
    project_id: str,
    actor_id: str,
    user_id: str,
    clock: Clock,
) -> UserOut:
    """N4: gỡ một thành viên; trả `UserOut` dựng **trước** khi gỡ. Hiệu lực ngay, không cache."""
    _require_wire_id(user_id)
    editors = await lock_editor_ids(db, project_id)
    stmt = (
        select(User)
        .join(ProjectMembership, ProjectMembership.user_id == User.id)
        .where(ProjectMembership.project_id == project_id, User.id == user_id, User.deleted_at.is_(None))
        .with_for_update(of=ProjectMembership)
        .execution_options(populate_existing=True)
    )
    user = _require_member((await db.execute(stmt)).scalar_one_or_none())
    if user_id in editors:
        _require_not_last_editor(editors, user_id)
    out = await user_out(user, storage)
    await remove_member(db, project_id=project_id, user_id=user_id)
    await record_activity(
        db,
        actor_id=actor_id,
        kind=ActivityKind.MEMBER_REMOVE,
        object_code=user_id,
        object_label=user.email[:OBJECT_LABEL_MAX],
        clock=clock,
        project_id=project_id,
    )
    await touch_project(db, project_id=project_id, clock=clock)
    return out
