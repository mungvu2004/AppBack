"""Tiện ích dùng chung của test `apps/api/users` (không phải file test, pytest không thu thập).

Mẫu `apps/api/me/tests/support.py`: dựng `Principal` khớp một `User` thật (verifier giả của
`api_app`, vai lấy từ `Principal`), gọi route, bắt lô thư gửi sau commit và đặt trần bằng biến
môi trường (C15). Test cần verifier **thật** dùng `auth_client` + `signed_in` trực tiếp.
"""

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any, cast

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth_recovery import tokens
from apps.api.core.auth import Principal, Role, fake_token
from apps.api.users.service import reset_users_settings_cache
from packages.db.models.auth import User
from packages.db.models.auth_recovery import OneTimeToken
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.api import BASE_URL, ObservedClient

USERS = "/api/users"


def principal_of(user: User, *, session_id: str = "sid-thu-nghiem") -> Principal:
    """`Principal` khớp một `User` đã tạo; vai lấy từ `user.role` (test đổi vai trong DB thì `Principal` giữ vai cũ)."""
    return Principal(user_id=user.id, session_id=session_id, role=cast("Role", user.role))


def headers_of(user: User) -> dict[str, str]:
    """Header `Authorization: Bearer` mà `FakeTokenVerifier` nhận cho `user`."""
    return {"Authorization": f"Bearer {fake_token(principal_of(user))}"}


async def make_admin(db: AsyncSession, **kwargs: Any) -> User:
    """Một admin `active` đã commit."""
    return await make_user(db, role="admin", **kwargs)


async def send(client: httpx.AsyncClient, actor: User, method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Gọi route với tư cách `actor`; `kwargs` là `json=`/`headers=` thêm."""
    extra = kwargs.pop("headers", {})
    return await client.request(method, path, headers={**headers_of(actor), **extra}, **kwargs)


def capture_mail_batches(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Thay `send_task` của `tokens` bằng hàm ghi lại `token_ids` của từng lô — đếm thư mà không cần worker."""
    batches: list[list[str]] = []
    monkeypatch.setattr(tokens, "send_task", lambda _name, payload: batches.append(list(payload.token_ids)))
    return batches


async def count_tokens(db: AsyncSession, user_id: str, *, live_only: bool = False) -> int:
    """Số dòng `one_time_tokens` mục đích `invite` của một người (tuỳ chọn: chỉ token chưa bị thay/dùng)."""
    stmt = (
        select(func.count())
        .select_from(OneTimeToken)
        .where(OneTimeToken.user_id == user_id, OneTimeToken.purpose == "invite")
    )
    if live_only:
        stmt = stmt.where(OneTimeToken.superseded_at.is_(None), OneTimeToken.used_at.is_(None))
    return (await db.execute(stmt)).scalar_one()


@contextmanager
def users_limits(monkeypatch: pytest.MonkeyPatch, **limits: int) -> Iterator[None]:
    """Đặt trần `UsersSettings` (vd `users_list_max=3`) cho khối `with`, trả về mặc định khi ra khỏi khối.

    Cache cấu hình phải đọc lại **sau** khi biến môi trường được gỡ, nên gỡ tường minh ở `finally`.
    """
    names = [name.upper() for name in limits]
    for name, value in limits.items():
        monkeypatch.setenv(name.upper(), str(value))
    reset_users_settings_cache()
    try:
        yield
    finally:
        for name in names:
            monkeypatch.delenv(name)
        reset_users_settings_cache()


async def reload(db: AsyncSession, user_id: str) -> User:
    """Đọc lại một `User` từ DB (bỏ bản đã nạp trong session của test)."""
    stmt = select(User).where(User.id == user_id).execution_options(populate_existing=True)
    return (await db.execute(stmt)).scalar_one()


@asynccontextmanager
async def second_client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """Client thứ hai của **cùng** app (cookie riêng, không mở lại `lifespan`): một người đăng nhập thứ hai."""
    async with ObservedClient(transport=httpx.ASGITransport(app=app), base_url=BASE_URL) as client:
        yield client
