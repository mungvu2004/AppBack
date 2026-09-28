"""Tiện ích dùng chung của test `apps/api/notifications` (không phải file test)."""

import asyncio
import secrets
from collections.abc import Awaitable, Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Final, cast

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.auth import Principal
from apps.api.notifications.service import notify
from apps.api.notifications.settings import reset_notifications_settings_cache
from packages.core.clock import Clock
from packages.db.engine import GATE_CONNECT_TIMEOUT_S, create_engine, create_sessionmaker
from packages.db.hooks import after_commit_idle
from packages.db.models.auth import User
from packages.db.models.notifications import NotificationRow
from packages.db.models.projects import Project, ProjectMembership
from packages.db.settings import DatabaseSettings
from packages.domain.permissions import Role
from packages.messaging.redis import AsyncRedis
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.api import auth_headers

LIST_PATH: Final = "/api/notifications"
FLOOR = "L-0000000001"


def headers_of(user: User) -> dict[str, str]:
    """Header `Authorization` của `FakeTokenVerifier`; vai lấy từ cột `role` của người dùng."""
    principal = Principal(user_id=user.id, session_id=f"sid-{user.id[-8:]}", role=cast("Role", user.role))
    return auth_headers(principal)


def accept_path(notification_id: str) -> str:
    """`/api/notifications/{id}/accept-invite`."""
    return f"{LIST_PATH}/{notification_id}/accept-invite"


async def seed_project(db: AsyncSession, *, owner: User, members: Sequence[User] = (), **kwargs: Any) -> Project:
    """`make_project` rồi `commit`: route chạy trên session khác nên phải thấy dữ liệu này."""
    project = await make_project(db, owner=owner, members=members, **kwargs)
    await db.commit()
    return project


async def commit_notify(db: AsyncSession, clock: Clock, **kwargs: Any) -> NotificationRow | None:
    """`notify` rồi commit và chờ callback sau commit; mặc định `aiCompleted` ở `walls`."""
    fields: dict[str, Any] = {
        "kind": "aiCompleted",
        "place": "walls",
        "floor_level_id": FLOOR,
        "object_label": "Tường ngoài",
        "message": "hệ thống AI đã xử lý xong bản vẽ",
        "dedupe_key": f"test:{secrets.token_hex(8)}",
        "clock": clock,
    }
    fields.update(kwargs)
    row = await notify(db, **fields)
    await db.commit()
    await after_commit_idle(db)
    return row


async def rows_of(db: AsyncSession, user_id: str | None = None) -> list[NotificationRow]:
    """Mọi dòng `notifications` (của một người nếu cho), đọc lại từ DB, cũ trước."""
    stmt = select(NotificationRow).order_by(NotificationRow.created_at, NotificationRow.id)
    if user_id is not None:
        stmt = stmt.where(NotificationRow.user_id == user_id)
    return list((await db.execute(stmt.execution_options(populate_existing=True))).scalars())


async def remove_member(db: AsyncSession, project: Project, user: User) -> None:
    """Gỡ `user` khỏi `project` bằng SQL và commit (không qua N4: chỉ cần trạng thái sau)."""
    membership = await db.get(ProjectMembership, (project.id, user.id))
    assert membership is not None  # test dựng sai
    await db.delete(membership)
    await db.commit()


@contextmanager
def settings_env(monkeypatch: pytest.MonkeyPatch, **values: str) -> Iterator[None]:
    """Đặt `NOTIFICATIONS_*` (khoá viết thường, không tiền tố) rồi xoá cache cấu hình hai đầu."""
    with monkeypatch.context() as scoped:
        for name, value in values.items():
            scoped.setenv(f"NOTIFICATIONS_{name.upper()}", value)
        reset_notifications_settings_cache()
        try:
            yield
        finally:
            scoped.undo()
            reset_notifications_settings_cache()


async def get_list(client: httpx.AsyncClient, user: User) -> httpx.Response:
    """#19 với tư cách `user`."""
    return await client.get(LIST_PATH, headers=headers_of(user))


async def post_json(client: httpx.AsyncClient, user: User, path: str, body: object) -> httpx.Response:
    """POST JSON với tư cách `user`."""
    return await client.post(path, json=body, headers=headers_of(user))


async def on_fresh_engine[ResultT](db_url: str, work: Callable[[AsyncSession], Awaitable[ResultT]]) -> ResultT:
    """Chạy `work` trên engine riêng của vòng `asyncio.run` hiện tại (test khói là test đồng bộ)."""
    engine = create_engine(DatabaseSettings(database_url=db_url, db_connect_timeout_s=int(GATE_CONNECT_TIMEOUT_S)))
    try:
        async with create_sessionmaker(engine)() as session:
            return await work(session)
    finally:
        await engine.dispose()


def run(coro: Awaitable[Any]) -> Any:
    """`asyncio.run` cho test khói đồng bộ."""
    return asyncio.run(cast("Any", coro))


def at(base: datetime, **delta: float) -> datetime:
    """`base` lùi/tiến một khoảng (`at(now, minutes=-3)`)."""
    return base + timedelta(**delta)


async def stream_ids(client: AsyncRedis, stream: str) -> list[str]:
    """Id các mục của một stream, theo thứ tự (`XRANGE`)."""
    return [str(entry_id) for entry_id, _ in (await client.xrange(stream) or [])]
