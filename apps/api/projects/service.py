"""Nghiệp vụ của sáu thao tác dự án (B2-01 [6]): dựng dây theo lô và ba lượt ghi.

`router.py` chỉ dịch HTTP ↔ Python; mọi luật nằm ở đây, nên B2-02…B5 gọi lại được mà
không phải đi vòng qua HTTP. Bốn điều dễ sai mà module này gánh thay người gọi:

- **dựng `ProjectOut` theo lô.** Một lô 1 dự án và một lô 500 dự án chạy **cùng** số câu
  SQL: `member_users` + `project_rollups` + đúng một lần `load` của cổng `project.floors`
  (B2-01 [9] cấm N+1 ở #23 và N1). Vì vậy `build_project` cũng đi qua `build_projects`;
- **không `commit`.** `AppRoute` commit khi handler *trả về* và rollback khi handler *ném*
  (`apps/api/core/routing.py`), nên lỗi nghiệp vụ ở đây luôn **ném**: hook `#25` ném giữa
  chừng thì dự án, membership và nhật ký cùng biến mất (BE-00 §7);
- **`UPDATE … WHERE deleted_at IS NULL RETURNING`.** Kiểm-rồi-ghi thành hai câu là một cửa
  sổ đua với lượt xoá mềm song song; ghi có điều kiện rồi đếm dòng trả về là một câu;
- **quyết định nằm trong hàm đồng bộ.** `coverage.py` không ghi được những dòng chạy ngay
  sau một `await` của SQLAlchemy async (greenlet), nên mọi nhánh (`if`) được tách ra hàm
  thường — vừa đo đúng, vừa để luật đọc thành một khối liền (báo cáo của việc A).
"""

from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.access.activity import record_activity
from apps.api.access.kinds import ActivityKind
from apps.api.core.auth import Principal
from apps.api.core.pagination import CursorPage, PageParams, decode_cursor, encode_cursor
from apps.api.core.wire import WireModel
from apps.api.projects.memberships import add_member, member_users
from apps.api.projects.parts import PROJECT_CREATE_FLOORS, PROJECT_FLOORS, create_hook, view_part
from apps.api.projects.schemas import ProjectCreateIn, ProjectUpdateIn, floor_drafts
from apps.api.projects.settings import get_projects_settings
from apps.api.projects.summaries import project_rollups, touch_project
from apps.api.projects.wire import (
    FloorOut,
    ProjectOut,
    ProjectRollup,
    ProjectSummaryOut,
    project_summary_out,
    user_out,
)
from packages.core.clock import Clock
from packages.core.error_codes import NOT_FOUND
from packages.core.ids import new_id
from packages.db.models.auth import User
from packages.db.models.projects import Project, ProjectMembership
from packages.storage.port import ObjectStorage

LIST_SUMMARIES_OP: Final = "projects_list_summaries"
"""`operationId` của N1 — cursor mang theo tên này, nên cursor của danh sách khác không dùng lại được."""

CURSOR_POSITION: Final = "id"
"""Khoá vị trí trong cursor N1: trang sắp `id ASC` nên đọc tiếp là `id >` giá trị này."""

EDITABLE_FIELDS: Final = ("name", "code", "address")
"""Ba trường #26 được đổi; `null` đã bị `ProjectUpdateIn` chặn nên `None` ở đây là "không gửi"."""


def _checked[RowT](found: RowT | None) -> RowT:
    """Kết quả một câu đã lọc `deleted_at IS NULL`; không có dòng nào → 404 `resource:"project"`.

    Dùng chung cho lượt đọc và hai lượt `UPDATE … RETURNING`: cả ba đều có nghĩa "dự án
    không còn" và phải trả **cùng một** câu trả lời, kể cả cho admin hệ thống (K08).
    """
    if found is None:
        raise NOT_FOUND.error(resource="project")
    return found


def _member_projects(user_id: str) -> Select[tuple[Project]]:
    """Dự án **chưa xoá mềm** mà `user_id` là thành viên — gốc chung của #23 và N1."""
    return (
        select(Project)
        .join(ProjectMembership, ProjectMembership.project_id == Project.id)
        .where(ProjectMembership.user_id == user_id, Project.deleted_at.is_(None))
    )


async def _live_project(db: AsyncSession, project_id: str) -> Project:
    """Dòng `projects` chưa xoá mềm, hay 404.

    `require_project` đã kiểm cùng điều kiện ở cổng dependency; lượt đọc này kiểm lại vì
    giữa hai bước có thể có một lượt xoá mềm của người khác.
    """
    found = (
        await db.execute(select(Project).where(Project.id == project_id, Project.deleted_at.is_(None)))
    ).scalar_one_or_none()
    return _checked(found)


async def _floor_parts(
    db: AsyncSession, project_ids: Sequence[str], *, app: object | None
) -> Mapping[str, Sequence[WireModel]]:
    """Một lần `load` của cổng `project.floors` cho cả lô; chưa ai cắm cổng → không dự án nào có tầng."""
    part = view_part(PROJECT_FLOORS, app=app)
    return await part.load(db, project_ids) if part is not None else {}


def _storage_of(app: object | None) -> ObjectStorage | None:
    """Kho object của app hiện tại, hay `None` khi gọi thẳng service không qua app (NO-135).

    Cùng nguồn `app.state.storage` mà `apps.api.core.deps.storage` đọc (`lifespan` dựng một
    lần) — không tự đọc `STORAGE_BACKEND` ở đây (BE-00 §2.1: module nghiệp vụ không đọc biến
    môi trường kho trực tiếp).
    """
    storage = getattr(getattr(app, "state", None), "storage", None)
    return cast("ObjectStorage", storage) if storage is not None else None


async def _project_outs(
    projects: Sequence[Project],
    members: Mapping[str, list[User]],
    rollups: Mapping[str, ProjectRollup],
    floors: Mapping[str, Sequence[WireModel]],
    storage: ObjectStorage | None,
) -> list[ProjectOut]:
    """Ba mảnh đã tải theo lô → `ProjectOut`; dự án vắng khoá trong `floors` nghĩa là `[]` (B2-01 [6])."""
    outs = []
    for project in projects:
        member_outs = [await user_out(row, storage) for row in members[project.id]]
        outs.append(
            ProjectOut(
                id=project.id,
                name=project.name,
                code=project.code,
                address=project.address,
                created_at=project.created_at,
                updated_at=project.updated_at,
                status=rollups[project.id].legacy_status,
                # `ViewPart.load` khai `Sequence[WireModel]` cho mọi cổng; cổng `project.floors`
                # khai `FloorOut` (`parts.py`), khai sai kiểu thì hỏng ngay ở test của B2-03.
                floors=cast("list[FloorOut]", list(floors.get(project.id, ()))),
                members=member_outs,
            )
        )
    return outs


async def build_projects(db: AsyncSession, projects: Sequence[Project], *, app: object | None) -> list[ProjectOut]:
    """`ProjectOut` của cả lô bằng ba lượt đọc, bất kể lô có 1 hay 500 dự án (B2-01 [9])."""
    ids = [project.id for project in projects]
    members = await member_users(db, ids)
    rollups = await project_rollups(db, ids)
    floors = await _floor_parts(db, ids, app=app)
    return await _project_outs(projects, members, rollups, floors, _storage_of(app))


async def build_project(db: AsyncSession, project: Project, *, app: object | None) -> ProjectOut:
    """`ProjectOut` của một dự án — cùng đường dựng lô, để luật `floors`/`members` chỉ có một bản."""
    return (await build_projects(db, [project], app=app))[0]


async def list_projects(db: AsyncSession, principal: Principal, *, app: object | None) -> list[ProjectOut]:
    """#23: dự án mình là thành viên, `updated_at DESC, id DESC`, tối đa `PROJECTS_LIST_MAX`.

    Trần đọc **lúc gọi** (không phải lúc nhập module): C15 đổi nó bằng biến môi trường rồi
    xoá cache của `ProjectsSettings` ngay trong một lượt test.
    """
    stmt = (
        _member_projects(principal.user_id)
        .order_by(Project.updated_at.desc(), Project.id.desc())
        .limit(get_projects_settings().projects_list_max)
    )
    projects = list((await db.execute(stmt)).scalars().all())
    return await build_projects(db, projects, app=app)


async def read_project(db: AsyncSession, project_id: str, *, app: object | None) -> ProjectOut:
    """#24: một dự án mình là thành viên (`require_project` đã kiểm quyền ở cổng)."""
    project = await _live_project(db, project_id)
    return await build_project(db, project, app=app)


def _summaries_stmt(user_id: str, page: PageParams, filters: Mapping[str, object]) -> Select[tuple[Project]]:
    """Câu đọc một trang N1: `id ASC`, `limit + 1` dòng (dòng dư = còn trang sau), lọc từ cursor.

    Cursor ký kèm `filters` (`{"user": sub}`), nên cursor của người khác dừng ngay ở
    `decode_cursor` với 422 `CURSOR_INVALID` — không lộ dự án nào của họ.
    """
    stmt = _member_projects(user_id).order_by(Project.id).limit(page.limit + 1)
    if page.cursor is None:
        return stmt
    after = decode_cursor(page.cursor, LIST_SUMMARIES_OP, filters)[CURSOR_POSITION]
    return stmt.where(Project.id > str(after))


def _summary_page(
    items: Sequence[Project],
    rollups: Mapping[str, ProjectRollup],
    members: Mapping[str, list[User]],
    filters: Mapping[str, object],
    *,
    has_more: bool,
) -> CursorPage[ProjectSummaryOut]:
    """Một trang N1; `nextCursor` chỉ có khi còn dòng phía sau (W2: hết trang thì vắng khoá)."""
    return CursorPage(
        items=[project_summary_out(project, rollups[project.id], members[project.id]) for project in items],
        next_cursor=encode_cursor(LIST_SUMMARIES_OP, filters, {CURSOR_POSITION: items[-1].id}) if has_more else None,
    )


async def list_summaries(db: AsyncSession, principal: Principal, page: PageParams) -> CursorPage[ProjectSummaryOut]:
    """N1: một trang tóm tắt dự án của mình, `id ASC`, ba lượt đọc cho cả trang."""
    filters: dict[str, object] = {"user": principal.user_id}
    rows = list((await db.execute(_summaries_stmt(principal.user_id, page, filters))).scalars().all())
    items = rows[: page.limit]
    ids = [project.id for project in items]
    members = await member_users(db, ids)
    rollups = await project_rollups(db, ids)
    return _summary_page(items, rollups, members, filters, has_more=len(rows) > page.limit)


async def _run_create_hook(
    db: AsyncSession,
    project_id: str,
    body: ProjectCreateIn,
    principal: Principal,
    clock: Clock,
    *,
    app: object | None,
) -> None:
    """Cổng `project.create_floors` — chỉ chạy khi có tầng nháp **và** B2-03 đã cắm cổng.

    Chạy trong giao dịch của #25, sau khi dòng `projects` đã `flush` (hook `SELECT` thấy
    nó); hook ném thì `AppRoute` rollback cả lượt. Chưa ai cắm → `floors` bị bỏ qua lặng lẽ.
    """
    hook = create_hook(PROJECT_CREATE_FLOORS, app=app)
    if body.floors and hook is not None:
        await hook.run(db, project_id, floor_drafts(body.floors), principal, clock)


async def create_project(
    db: AsyncSession, body: ProjectCreateIn, principal: Principal, clock: Clock, *, app: object | None
) -> ProjectOut:
    """#25: dự án mới + người tạo là thành viên + (nếu có cổng) tầng nháp, **một** giao dịch.

    `created_by` lấy từ `sub` của phiên, không từ thân (K05). Không có luật tên duy nhất:
    hai lượt cùng tên đều 201, không route nào của module này trả 409.
    """
    project = Project(
        id=new_id("prj", clock),
        name=body.name,
        code=body.code,
        address=body.address,
        created_by=principal.user_id,
    )
    db.add(project)
    await db.flush()
    await add_member(db, project_id=project.id, user_id=principal.user_id, added_by=principal.user_id, clock=clock)
    await _run_create_hook(db, project.id, body, principal, clock, app=app)
    await _log(db, principal, ActivityKind.PROJECT_CREATE, project.id, project.name, clock)
    await touch_project(db, project_id=project.id, clock=clock)
    await db.refresh(project)
    return await build_project(db, project, app=app)


def _changed_fields(project: Project, body: ProjectUpdateIn) -> dict[str, Any]:
    """Trường #26 gửi lên mà **khác** giá trị đang có; rỗng nghĩa là không phải ghi gì cả."""
    return {
        field: value
        for field in EDITABLE_FIELDS
        if (value := getattr(body, field)) is not None and value != getattr(project, field)
    }


async def _write_changes(
    db: AsyncSession, project: Project, changes: dict[str, Any], principal: Principal, clock: Clock
) -> None:
    """Ghi các trường đã đổi của #26 rồi ghi nhật ký; dự án vừa bị xoá mềm → 404."""
    written = (
        await db.execute(
            update(Project)
            .where(Project.id == project.id, Project.deleted_at.is_(None))
            .values(**changes)
            .returning(Project.id)
        )
    ).first()
    _checked(written)
    await _log(db, principal, ActivityKind.PROJECT_UPDATE, project.id, changes.get("name", project.name), clock)
    await touch_project(db, project_id=project.id, clock=clock)
    await db.refresh(project)


async def update_project(
    db: AsyncSession,
    project_id: str,
    body: ProjectUpdateIn,
    principal: Principal,
    clock: Clock,
    *,
    app: object | None,
) -> ProjectOut:
    """#26 (last-write-wins): chỉ ghi những trường **thật sự khác** giá trị hiện tại.

    Thân `{}` — và thân gửi lại đúng giá trị đang có — đều là 200 dự án hiện tại, **không**
    nhật ký và **không** đẩy `updated_at`: FE lưu nút "Lưu" cả khi người dùng chưa đổi gì,
    và mỗi lượt như thế mà ghi một dòng nhật ký thì sổ hoạt động thành vô dụng.
    """
    project = await _live_project(db, project_id)
    changes = _changed_fields(project, body)
    if changes:
        await _write_changes(db, project, changes, principal, clock)
    return await build_project(db, project, app=app)


async def delete_project(
    db: AsyncSession, project_id: str, principal: Principal, clock: Clock, *, app: object | None
) -> ProjectOut:
    """#27 (xoá mềm): thân trả về là trạng thái **ngay trước** khi xoá.

    Dựng dây trước rồi mới ghi `deleted_at`: membership và bảng đếm còn nguyên cho lịch dọn,
    nhưng #23/N1/`is_member` đã loại dự án ngay — thân phải là ảnh chụp cũ, không phải mới.
    """
    project = await _live_project(db, project_id)
    snapshot = await build_project(db, project, app=app)
    written = (
        await db.execute(
            update(Project)
            .where(Project.id == project_id, Project.deleted_at.is_(None))
            .values(deleted_at=clock.now())
            .returning(Project.id)
        )
    ).first()
    _checked(written)
    await _log(db, principal, ActivityKind.PROJECT_DELETE, project_id, snapshot.name, clock)
    return snapshot


async def _log(
    db: AsyncSession, principal: Principal, kind: ActivityKind, project_id: str, label: str, clock: Clock
) -> None:
    """Một dòng `activity_log` cho thao tác trên dự án; `object_code` và `project_id` cùng là id dự án."""
    await record_activity(
        db,
        actor_id=principal.user_id,
        kind=kind,
        object_code=project_id,
        object_label=label,
        clock=clock,
        project_id=project_id,
    )
