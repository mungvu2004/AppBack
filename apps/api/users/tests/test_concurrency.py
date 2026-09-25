"""C14 của #41, #42, #46: hai admin **đăng nhập thật** thao tác lên nhau cùng lúc (B1-05 [6], [8]).

Khoá tập admin làm hai lượt nối đuôi nhau: một bên thắng (200), bên kia bị chặn ở bước kiểm
"người thực hiện còn là admin `active`" (403) hoặc ngay ở verifier vì `token_version` vừa tăng
(401), không bao giờ 5xx, và hệ thống còn đúng một admin `active`.
"""

import asyncio
from collections.abc import Awaitable, Callable

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.users.tests.support import USERS, make_admin, second_client
from packages.db.models.auth import User
from packages.testing.fixtures.auth import SignIn

pytestmark = pytest.mark.usefixtures("auth_env")

type Call = Callable[[httpx.AsyncClient, dict[str, str], User], Awaitable[httpx.Response]]
"""Một lượt gọi: client, header của người thực hiện, người bị nhắm tới."""

LOSER_STATUSES = {401, 403, 422}


async def _active_admins(db: AsyncSession) -> int:
    """Số admin `active` chưa xoá mềm còn lại trong DB."""
    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.role == "admin", User.status == "active", User.deleted_at.is_(None))
    )
    return (await db.execute(stmt)).scalar_one()


async def _duel(
    name: str, auth_app: FastAPI, auth_client: httpx.AsyncClient, db: AsyncSession, signed_in: SignIn, call: Call
) -> None:
    """Hai admin thật gọi `call` lên nhau song song; kiểm một thắng một thua và còn đúng một admin `active`."""
    first, second = await make_admin(db), await make_admin(db)
    first_session = await signed_in(first)
    async with second_client(auth_app) as other:
        second_session = await signed_in(second, client=other)
        results = await asyncio.gather(
            call(auth_client, first_session.headers, second),
            call(other, second_session.headers, first),
        )
    statuses = sorted(response.status_code for response in results)
    remaining = await _active_admins(db)
    print(f"C14 {name}: status = {[r.status_code for r in results]}, admin active con lai = {remaining}")
    assert statuses[0] == 200
    assert statuses[1] in LOSER_STATUSES
    assert remaining == 1


async def test_users_change_role__C14(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, signed_in: SignIn
) -> None:
    """Hai admin hạ vai nhau song song → một bên 200, bên kia bị chặn, còn một admin."""

    async def call(client: httpx.AsyncClient, headers: dict[str, str], victim: User) -> httpx.Response:
        body = {"role": "viewer", "userId": victim.id}
        return await client.patch(f"{USERS}/{victim.id}/role", json=body, headers=headers)

    await _duel("users_change_role", auth_app, auth_client, db_session, signed_in, call)


async def test_users_disable_user__C14(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, signed_in: SignIn
) -> None:
    """Hai admin vô hiệu nhau song song → một bên 200, bên kia bị chặn, còn một admin `active`."""

    async def call(client: httpx.AsyncClient, headers: dict[str, str], victim: User) -> httpx.Response:
        return await client.post(f"{USERS}/{victim.id}/disable", json={}, headers=headers)

    await _duel("users_disable_user", auth_app, auth_client, db_session, signed_in, call)


async def test_users_delete_user__C14(
    auth_app: FastAPI, auth_client: httpx.AsyncClient, db_session: AsyncSession, signed_in: SignIn
) -> None:
    """Hai admin xoá nhau song song → một bên 200, bên kia bị chặn, còn một admin `active` chưa xoá."""

    async def call(client: httpx.AsyncClient, headers: dict[str, str], victim: User) -> httpx.Response:
        body = {"confirmEmail": victim.email, "userId": victim.id}
        return await client.request("DELETE", f"{USERS}/{victim.id}", json=body, headers=headers)

    await _duel("users_delete_user", auth_app, auth_client, db_session, signed_in, call)
