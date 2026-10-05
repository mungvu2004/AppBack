"""NO-186: bước **sau** handler (`_finish`) ném thì session của request vẫn trả về pool.

Đo bằng pool thật của app (`checkedout()`), không bằng session giả (K23): kết nối còn
bị giữ sau khi response đã ra là session chưa rollback/close.
"""

import asyncio
from contextlib import suppress
from typing import Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import idempotency, routing
from apps.api.core.auth import Principal
from apps.api.core.tests.sample import sample_app, sample_client, sample_row_ids
from packages.db.models.idempotency import IdempotencyRecord
from packages.testing.fixtures.api import auth_headers

__all__ = ["sample_app", "sample_client"]

KEY: Final = "khoa-finish-01"


def _checked_out(app: FastAPI) -> int:
    """Số kết nối pool của request đang bị giữ (session nghiệp vụ, không tính pool nhận việc)."""
    return int(app.state.sessionmaker.kw["bind"].pool.checkedout())


async def _raise_after_commit(error: BaseException, monkeypatch: pytest.MonkeyPatch) -> None:
    """Thay `after_commit_idle` của `routing` bằng hàm ném `error` — bước cuối trong `try` của `_finish`."""

    async def boom(session: AsyncSession) -> None:
        """Ném sau khi commit đã chạy."""
        raise error

    monkeypatch.setattr(routing, "after_commit_idle", boom)


async def test_finish__after_commit_failure_returns_the_connection(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Giả thuyết 1: chờ callback sau commit ném `RuntimeError` → 500, kết nối đã về pool."""
    await _raise_after_commit(RuntimeError("callback hỏng"), monkeypatch)
    response = await sample_client.post(
        "/api/sample/projects/prj-1/items",
        json={"projectId": "prj-1", "name": "a"},
        headers=auth_headers(fake_principal),
    )
    assert response.status_code == 500
    assert _checked_out(sample_app) == 0
    assert await sample_row_ids(sample_app.state.sessionmaker) == ["prj-1"], "commit đã xong trước khi ném"


async def test_finish__cancelled_after_commit_returns_the_connection(
    sample_app: FastAPI, sample_client: httpx.AsyncClient, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Giả thuyết 2: request bị huỷ (`CancelledError`, `BaseException`) trong `_finish` → kết nối vẫn về pool."""
    await _raise_after_commit(asyncio.CancelledError(), monkeypatch)
    with suppress(asyncio.CancelledError):
        await sample_client.post(
            "/api/sample/projects/prj-1/items",
            json={"projectId": "prj-1", "name": "a"},
            headers=auth_headers(fake_principal),
        )
    assert _checked_out(sample_app) == 0


async def test_finish__discard_failure_after_close_returns_the_connection(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Giả thuyết 3: xoá dòng idempotency (bước **sau** `close`) ném → session đã đóng từ trước."""

    async def boom(*_: object) -> None:
        """Pool nhận việc hỏng đúng lúc dọn dòng của response 429."""
        raise RuntimeError("pool nhận việc hỏng")

    monkeypatch.setattr(idempotency, "discard", boom)
    response = await sample_client.post(
        "/api/sample/throttled",
        json={"name": "a"},
        headers={**auth_headers(fake_principal), idempotency.HEADER: KEY},
    )
    assert response.status_code == 500
    assert _checked_out(sample_app) == 0


async def test_abort__cancelled_rollback_still_closes_the_session(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Giả thuyết 4 (anh em của NO-186): `_abort` bị huỷ ngay sau `rollback()` thật → `close()` vẫn phải chạy.

    Rollback chạy thật trên Postgres; chỉ ép `CancelledError` tới đúng lúc nó trả về (client ngắt giữa chừng).
    """
    real_rollback = AsyncSession.rollback

    async def cancelled_rollback(session: AsyncSession) -> None:
        """Rollback thật, rồi bị huỷ."""
        await real_rollback(session)
        raise asyncio.CancelledError

    monkeypatch.setattr(AsyncSession, "rollback", cancelled_rollback)
    with suppress(asyncio.CancelledError):
        await sample_client.post("/api/sample/broken-tx", json={"name": "a"}, headers=auth_headers(fake_principal))
    assert _checked_out(sample_app) == 0


async def _claims(app: FastAPI) -> int:
    """Số dòng idempotency còn lại, đọc bằng session mới của pool nhận việc."""
    async with app.state.claim_sessionmaker() as session:
        return int((await session.execute(select(func.count()).select_from(IdempotencyRecord))).scalar_one())


async def test_abort__rollback_failure_still_discards_the_claim(
    sample_client: httpx.AsyncClient, sample_app: FastAPI, fake_principal: Principal, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`rollback()` ném (sau khi đã rollback thật) → `close` và `discard` vẫn chạy: không còn dòng claim mồ côi."""
    real_rollback = AsyncSession.rollback

    async def broken_rollback(session: AsyncSession) -> None:
        """Rollback thật rồi ném — như DB rớt đúng lúc trả lời."""
        await real_rollback(session)
        raise RuntimeError("rollback hỏng")

    monkeypatch.setattr(AsyncSession, "rollback", broken_rollback)
    response = await sample_client.post(
        "/api/sample/boom", json={"name": "a"}, headers={**auth_headers(fake_principal), idempotency.HEADER: KEY}
    )
    assert response.status_code == 500
    assert _checked_out(sample_app) == 0
    assert await _claims(sample_app) == 0
