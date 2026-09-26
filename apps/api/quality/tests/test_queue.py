"""Hàng xử lý của #31 (BE-00 §7) và K36 của #32 (B2-05b [8] "Hàng xử lý", "K36").

Ảnh chỉ chạy trên executor riêng sau khi giữ được chỗ của semaphore theo vòng sự kiện; ở đây
`rectify`/`deskew` được bọc bằng hàm chờ **sự kiện luồng** để giữ chỗ lâu tuỳ ý, còn mọi thứ
khác (DB, kho, HTTP) là thật.
"""

import asyncio
import threading
from collections.abc import Callable, Iterator
from typing import Any, Final

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core.app import create_app
from apps.api.core.auth import FakeTokenVerifier
from apps.api.quality import processing
from apps.api.quality.tests._route_helpers import (
    Stage,
    corners_body,
    corners_path,
    make_stage,
    read_path,
    run_count,
    straighten_path,
    tune,
)
from apps.api.quality.tests._route_helpers import (
    quality_env as quality_env,
)
from packages.core.settings import get_core_settings
from packages.db.settings import reset_database_settings_cache
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.api import make_api_client
from packages.testing.fixtures.clock import FakeClock
from packages.vision.preprocess import deskew as real_deskew
from packages.vision.preprocess import rectify as real_rectify

WAIT_S: Final = 20.0
INSET: Final = ((0.05, 0.05), (0.95, 0.05), (0.95, 0.95), (0.05, 0.95))


class Gate:
    """Bọc một hàm xử lý ảnh: đếm số lần vào và chặn (bằng `threading.Event`) tới khi `open()`."""

    def __init__(self, real: Callable[..., Any], *, expect: int) -> None:
        """`expect` lần vào thì `reached` bật; `real` là hàm B2-05a thật."""
        self._real = real
        self._expect = expect
        self._lock = threading.Lock()
        self.calls = 0
        self.reached = threading.Event()
        self._open = threading.Event()

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Chạy trong luồng executor: ghi nhận, chờ cổng mở, rồi gọi hàm thật."""
        with self._lock:
            self.calls += 1
            if self.calls >= self._expect:
                self.reached.set()
        self._open.wait(WAIT_S)
        return self._real(*args, **kwargs)

    def open(self) -> None:
        """Mở cổng cho mọi lời gọi (đang chờ và về sau)."""
        self._open.set()


@pytest.mark.parametrize("round_number", [1, 2])
async def test_quality_set_corners__queue_capacity(
    api_client: httpx.AsyncClient,
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
    round_number: int,
) -> None:
    """5 tầng, 5 #31 song song, 2 chỗ: 2 chạy `rectify`, 3 nhận 503 `Retry-After`, không việc nào chạy sau 503.

    Chạy hai lần trong hai vòng sự kiện khác nhau (tham số hoá): semaphore theo vòng không gây `RuntimeError`.
    """
    tune(monkeypatch, quality_workers=2, quality_queue_wait_s=0.3)
    gate = Gate(real_rectify, expect=2)
    monkeypatch.setattr(processing, "rectify", gate)
    stage = await make_stage(db_session, local_storage, floors=5)
    tasks = {
        asyncio.create_task(
            api_client.post(
                corners_path(stage.project.id, stage.level(index)), json=corners_body(INSET), headers=stage.headers
            )
        )
        for index in range(5)
    }
    try:
        rejected: set[asyncio.Task[httpx.Response]] = set()
        while len(rejected) < 3:
            done, _ = await asyncio.wait(tasks - rejected, timeout=WAIT_S, return_when=asyncio.FIRST_COMPLETED)
            assert done, "không có lời gọi nào trả lời trong hạn"
            rejected |= done
        assert await asyncio.to_thread(gate.reached.wait, WAIT_S)
    finally:
        gate.open()
    accepted = await asyncio.gather(*(tasks - rejected))

    assert sorted(t.result().status_code for t in rejected) == [503, 503, 503]
    assert {t.result().headers["Retry-After"] for t in rejected} == {"2"}
    assert {t.result().json()["code"] for t in rejected} == {"DEPENDENCY_UNAVAILABLE"}
    assert [r.status_code for r in accepted] == [200, 200]
    assert gate.calls == 2, "việc bị 503 không được chạy sau đó"
    counts = [await run_count(db_sessionmaker, drawn.floor.pk) for drawn in stage.floors]
    assert sorted(counts) == [0, 0, 0, 1, 1]


@pytest.fixture
def tiny_pool_app(api_env: None, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch) -> Iterator[FastAPI]:
    """App thật với `DB_POOL_SIZE=1`: một request giữ kết nối là mọi request khác chờ (K36)."""
    monkeypatch.setenv("DB_POOL_SIZE", "1")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DB_POOL_TIMEOUT_S", "1")
    reset_database_settings_cache()
    yield create_app(get_core_settings(), token_verifier=FakeTokenVerifier(), clock=fake_clock)
    reset_database_settings_cache()


async def test_quality_straighten__does_not_hold_the_pool__K36(
    tiny_pool_app: FastAPI,
    db_session: AsyncSession,
    local_storage: LocalDiskStorage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#32 đang xử lý ảnh → pool rỗng (`checkedout() == 0`) và #30 vẫn trả lời trên app chỉ có **một** kết nối."""
    gate = Gate(real_deskew, expect=1)
    monkeypatch.setattr(processing, "deskew", gate)
    stage: Stage = await make_stage(db_session, local_storage)
    async with make_api_client(tiny_pool_app) as client:
        straighten = asyncio.create_task(
            client.post(straighten_path(stage.project.id, stage.level()), json={}, headers=stage.headers)
        )
        try:
            assert await asyncio.to_thread(gate.reached.wait, WAIT_S)
            assert tiny_pool_app.state.engine.pool.checkedout() == 0
            read = await asyncio.wait_for(
                client.get(read_path(stage.project.id, stage.level()), headers=stage.headers), WAIT_S
            )
        finally:
            gate.open()
        done = await straighten

    assert read.status_code == 200, read.text
    assert done.status_code == 200, done.text
