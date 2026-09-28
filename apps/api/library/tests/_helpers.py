"""Hàm dùng chung của test thư viện .glb: đường dẫn, header, seed + phát hành, đếm lời gọi storage."""

from collections.abc import Awaitable, Callable
from typing import Any, Final

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.auth import Principal
from apps.api.library.assets import PublishReport, run_library_publish
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.db.models.auth import User
from packages.db.seeds.library import seed
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage
from packages.testing.fixtures.api import auth_headers
from packages.testing.fixtures.clock import FakeClock

LIST_PATH: Final = "/api/library"
FILES_PATH: Final = "/api/files/"
BLOCKED: Final = ("fastapi", "jwt", "argon2")


def item_path(item_id: str) -> str:
    """`/api/library/{item_id}`."""
    return f"{LIST_PATH}/{item_id}"


def headers_of(user: User) -> dict[str, str]:
    """Header `Authorization` cho một dòng `users` đã mồi."""
    return auth_headers(Principal(user_id=user.id, session_id=f"sid-{user.id[-8:]}", role="admin"))


def token_of(url: str) -> str:
    """Token cuối của URL `/api/files/{token}` (test gọi qua app, không qua `PUBLIC_BASE_URL`)."""
    return url.rsplit("/", 1)[-1]


async def seed_and_publish(
    db: AsyncSession,
    sessionmaker: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    clock: FakeClock,
    *,
    batch: int = 100,
) -> PublishReport:
    """Seed thật rồi một lượt `run_library_publish` — đúng đường triển khai (không factory)."""
    await seed(db)
    await db.commit()
    return await run_library_publish(sessionmaker, storage, clock, batch=batch)


def spy(monkeypatch: pytest.MonkeyPatch, storage: LocalDiskStorage, name: str) -> list[str]:
    """Bọc `storage.<name>` (`put`/`stat`); trả danh sách khoá đã được gọi, theo thứ tự."""
    real: Callable[..., Awaitable[Any]] = getattr(storage, name)
    keys: list[str] = []

    async def wrapper(key: str, *args: Any, **kwargs: Any) -> Any:
        keys.append(key)
        return await real(key, *args, **kwargs)

    monkeypatch.setattr(storage, name, wrapper)
    return keys


def fail_put(monkeypatch: pytest.MonkeyPatch, storage: LocalDiskStorage) -> None:
    """Mọi `put` sau đó ném `DEPENDENCY_UNAVAILABLE` (storage sập)."""

    async def broken(*_args: Any, **_kwargs: Any) -> Any:
        raise DEPENDENCY_UNAVAILABLE.error(retry_after=5)

    monkeypatch.setattr(storage, "put", broken)
