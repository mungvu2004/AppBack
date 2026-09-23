"""Factory dự án cho test (B2-01).

Ghi thẳng `projects` + `project_memberships`, không qua API. Khác `make_user`, hàm này chỉ
`flush`: test thường tạo dự án rồi còn ghi tiếp (tầng, nhật ký) trong **cùng** giao dịch và
tự quyết lúc commit — `commit` ở đây sẽ cắt đôi những lượt ấy.

Không nhập `apps.api.projects.memberships` (chủ là prompt khác): một lượt chèn thẳng không
có luật nghiệp vụ để đi sai, và factory phải dùng được cả khi module ấy chưa tồn tại.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.core.text import nfc
from packages.db.models.auth import User
from packages.db.models.projects import Project, ProjectMembership

DEFAULT_NAME: Final = "Dự án thử"


async def make_project(
    db: AsyncSession,
    *,
    owner: User,
    members: Sequence[User] = (),
    name: str | None = None,
    code: str | None = None,
    address: str | None = None,
    deleted_at: datetime | None = None,
) -> Project:
    """Một dự án đã `flush`, `owner` và `members` đều là thành viên (`added_by` = id owner).

    `owner` nằm luôn trong `members` cũng không sao: id trùng bị bỏ trước khi chèn, vì PK
    `(project_id, user_id)` sẽ làm hỏng lượt thứ hai.
    """
    project = Project(
        id=new_id("prj", SystemClock()),
        name=nfc(name if name is not None else DEFAULT_NAME),
        code=code,
        address=address,
        created_by=owner.id,
        deleted_at=deleted_at,
    )
    db.add(project)
    seen: set[str] = set()
    for person in (owner, *members):
        if person.id in seen:
            continue
        seen.add(person.id)
        db.add(ProjectMembership(project_id=project.id, user_id=person.id, added_by=owner.id))
    await db.flush()
    return project
