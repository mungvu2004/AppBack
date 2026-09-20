"""Dependency lấy tài nguyên của request (BE-00 §2.2).

Tất cả đọc từ `app.state` — nơi `lifespan` đặt engine, Redis và kho — chứ không tự
dựng: module nghiệp vụ không bao giờ đọc `DATABASE_URL` hay `REDIS_*` (BE-00 §2.1),
và test thay tài nguyên bằng cách dựng app khác chứ không vá biến toàn cục.

`db_session` trả **session của chính request**: `AppRoute` mở nó trước dependency
và commit sau handler, nên handler không tự `commit()` giữa chừng (BE-00 §7).
"""

from typing import Annotated, cast

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.auth import Principal, current_principal
from packages.core.clock import Clock
from packages.core.settings import CoreSettings
from packages.messaging.streams import EventBus
from packages.storage.port import ObjectStorage


def db_session(request: Request) -> AsyncSession:
    """Session của request; `AppRoute` giữ vòng đời (mở, commit, đóng)."""
    session = request.state.db_session
    assert isinstance(session, AsyncSession)  # noqa: S101 — AppRoute luôn đặt trước dependency
    return session


def event_bus(request: Request) -> EventBus:
    bus = request.app.state.event_bus
    assert isinstance(bus, EventBus)  # noqa: S101 — lifespan luôn đặt
    return bus


def storage(request: Request) -> ObjectStorage:
    return cast("ObjectStorage", request.app.state.storage)


def clock(request: Request) -> Clock:
    return cast("Clock", request.app.state.clock)


def core_settings(request: Request) -> CoreSettings:
    settings = request.app.state.settings
    assert isinstance(settings, CoreSettings)  # noqa: S101 — lifespan luôn đặt
    return settings


DbSession = Annotated[AsyncSession, Depends(db_session)]
Bus = Annotated[EventBus, Depends(event_bus)]
Storage = Annotated[ObjectStorage, Depends(storage)]
ClockDep = Annotated[Clock, Depends(clock)]
Settings = Annotated[CoreSettings, Depends(core_settings)]
CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
