"""Tiện ích dùng chung của test `apps/api/auth` (không phải file test, pytest không thu thập)."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Final
from uuid import UUID

import httpx
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth.cookies import REFRESH_COOKIE
from packages.db.models.auth import RefreshSession, User
from packages.testing.fixtures.api import BASE_URL, ObservedClient
from packages.testing.fixtures.auth import ORIGIN, REFRESH_PATH

WAIT_S: Final = 8.0
POLL_S: Final = 0.05


def set_cookies(response: httpx.Response) -> dict[str, str]:
    """Tên cookie → nguyên dòng `Set-Cookie` của response."""
    return {header.split("=", 1)[0]: header for header in response.headers.get_list("set-cookie")}


def cookie_value(header: str) -> str:
    """Giá trị của một dòng `Set-Cookie` (trước dấu `;` đầu tiên)."""
    return header.split(";", 1)[0].split("=", 1)[1]


def refresh_cookie(response: httpx.Response) -> str:
    """Giá trị cookie refresh mà response đặt; không có là test hỏng."""
    return cookie_value(set_cookies(response)[REFRESH_COOKIE])


async def refresh_with(client: httpx.AsyncClient, value: str | None, *, origin: bool = True) -> httpx.Response:
    """`POST /api/auth/refresh` với **đúng** cookie cho trước (header tường minh thắng hũ cookie)."""
    headers = dict(ORIGIN) if origin else {}
    if value is not None:
        headers["Cookie"] = f"{REFRESH_COOKIE}={value}"
    else:
        client.cookies.clear()
    return await client.post(REFRESH_PATH, headers=headers)


def client_from(app: FastAPI, ip: str) -> httpx.AsyncClient:
    """Client thêm trên app đã chạy `lifespan`, đến từ IP khác (hạn mức theo IP)."""
    return ObservedClient(transport=httpx.ASGITransport(app=app, client=(ip, 40000)), base_url=BASE_URL)


async def session_row(db: AsyncSession, sid: str) -> RefreshSession:
    """Dòng phiên đọc mới từ DB (không lấy bản trong identity map)."""
    await db.rollback()
    row = (await db.execute(select(RefreshSession).where(RefreshSession.id == UUID(sid)))).scalar_one()
    await db.refresh(row)
    return row


async def user_row(db: AsyncSession, user_id: str) -> User:
    """Dòng người dùng đọc mới từ DB."""
    await db.rollback()
    row = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    await db.refresh(row)
    return row


async def wait_until(check: Callable[[], Awaitable[bool]], *, timeout_s: float = WAIT_S) -> None:
    """Chờ tới khi `check()` đúng (TTL của Redis chạy theo giờ thật); quá hạn là test hỏng."""
    deadline = time.monotonic() + timeout_s
    while not await check():
        if time.monotonic() > deadline:
            raise AssertionError(f"quá {timeout_s} s mà điều kiện chưa đúng")
        await asyncio.sleep(POLL_S)
