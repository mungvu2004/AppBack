"""C14 của N3 và N4: hai client thật gọi song song trên Postgres thật (B2-02 [6], [8]).

Hai `httpx.AsyncClient` cùng một app, mỗi request một session DB riêng (khác `db_session` của
test), nên khoá hàng của Postgres là thứ duy nhất phân xử.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.kinds import ActivityKind
from apps.api.core import extensions
from apps.api.project_members.tests.support import (
    SINKS_SUBMODULE,
    RecordingSink,
    add,
    count_editors,
    member_ids,
    remove,
    seed_project,
)
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows
from packages.testing.fixtures.api import BASE_URL, ObservedClient


@asynccontextmanager
async def second_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client thứ hai của **cùng** app (không mở lại `lifespan`): một người gọi thứ hai."""
    async with ObservedClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as client:
        yield client


async def test_members_add_member__C14(
    api_client: httpx.AsyncClient,
    api_app: FastAPI,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Hai người sửa thêm **cùng email** song song → một 201, một 200; một membership, một nhật ký, một lượt sink."""
    sink = RecordingSink()
    extensions.override(api_app, SINKS_SUBMODULE, [("test", [sink])])
    first, second = await make_user(db_session, role="engineer"), await make_user(db_session, role="admin")
    target = await make_user(db_session, role="viewer")
    project = await seed_project(db_session, owner=first, members=[second])
    async with second_client(api_app) as other:
        results = await asyncio.gather(
            add(api_client, first, project, target.email), add(other, second, project, target.email)
        )
    statuses = sorted(response.status_code for response in results)
    memberships = (await member_ids(db_session, project.id)).count(target.id)
    logs = await activity_rows(db_sessionmaker, kind=ActivityKind.MEMBER_ADD)
    print(f"C14 members_add_member: status = {[r.status_code for r in results]}, membership = {memberships}")
    assert statuses == [200, 201]
    assert memberships == 1
    assert len(logs) == 1
    assert len(sink.calls) == 1


async def test_members_remove_member__C14(
    api_client: httpx.AsyncClient, api_app: FastAPI, db_session: AsyncSession
) -> None:
    """Hai người sửa duy nhất gỡ lẫn nhau song song → một 200, bên kia 422 `MEMBER_LAST_EDITOR`; còn 1 người sửa."""
    first, second = await make_user(db_session, role="engineer"), await make_user(db_session, role="admin")
    project = await seed_project(db_session, owner=first, members=[second])
    async with second_client(api_app) as other:
        results = await asyncio.gather(
            remove(api_client, first, project.id, second.id), remove(other, second, project.id, first.id)
        )
    statuses = sorted(response.status_code for response in results)
    editors = await count_editors(db_session, project.id)
    print(f"C14 members_remove_member: status = {[r.status_code for r in results]}, nguoi sua con lai = {editors}")
    assert statuses == [200, 422]
    assert next(r for r in results if r.status_code == 422).json()["code"] == "MEMBER_LAST_EDITOR"
    assert editors == 1
