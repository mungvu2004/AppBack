"""Runtime của `pipeline.quality.run`: task thật, Redis treo, K36 (B5-07 [8] "runtime").

Tách với test lõi (`test_service.py`): ở đây chỉ ca phải đi qua **dây** thật — hàm
task mỏng, `define_task`/`on_failed`, hàng `pipeline.cpu`, pool CSDL, client Redis — còn luật
nghiệp vụ từng bước của `run_quality` kiểm ở lõi. Cảnh dùng chung: `open_run_at_quality`
dựng lượt đứng ở `qualityCheck` trên cảnh `pipeline_persist` + lõi `run_persist` thật (K23:
Postgres, Redis, kho đĩa thật — không mock).
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterable, Callable, Coroutine
from typing import Final, NoReturn, cast

import pytest
import redis.exceptions
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.pool import QueuePool

from apps.api.drawings.progress import progress_wire
from apps.worker.pipeline_persist.errors import PIPELINE_RESULT_INVALID
from apps.worker.pipeline_quality import service, tasks
from apps.worker.pipeline_quality.report import QUALITY_ARTIFACT
from apps.worker.pipeline_quality.tests.helpers import Arranged, open_run_at_quality
from apps.worker.pipeline_quality.tests.helpers import process_env as process_env
from packages.db.engine import create_engine, create_sessionmaker
from packages.db.models.spatial import FloorDocumentRow
from packages.db.settings import DatabaseSettings
from packages.messaging.celery_app import send_task
from packages.messaging.redis import AsyncRedis, SyncRedis, streams_redis_sync
from packages.messaging.streams import FIELD, upload_stream
from packages.storage.keys import run_artifact
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectInfo
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.testing.fixtures.messaging import WorkerFactory

type Maker = async_sessionmaker[AsyncSession]

CPU_QUEUE: Final = "pipeline.cpu"
WAIT_S: Final = 30.0
"""Trần **chờ** chống treo cho các pha dùng `asyncio.Event` — không phải trần hiệu năng."""

_log = logging.getLogger(__name__)


def on_own_loop[T](db_url: str, work: Callable[[Maker], Coroutine[object, object, T]]) -> T:
    """Chạy `work` trên engine dựng riêng cho vòng `asyncio.run` này; khuôn `test_persist_runtime.py:99-116`."""

    async def main() -> T:
        """Dựng engine riêng cho vòng này, chạy `work`, rồi `dispose`."""
        engine = create_engine(DatabaseSettings(database_url=db_url))
        try:
            return await work(create_sessionmaker(engine))
        finally:
            await engine.dispose()

    return asyncio.run(main())


async def _progress(maker: Maker, upload_id: str) -> dict[str, object]:
    """`Progress` đọc lại trên session mới: trạng thái đã commit, không cache của session cũ."""
    async with maker() as db:
        return await progress_wire(db, upload_id)


type _StreamEntries = list[tuple[str, dict[str, str]]]


def _entries(raw: object) -> _StreamEntries:
    """Narrow kết quả `XREVRANGE`: stub redis-py khai kiểu lỏng dùng chung RESP2/RESP3."""
    return cast("_StreamEntries", raw)


def _read_stream_events(client: SyncRedis, stream: str, count: int) -> list[dict[str, object]]:
    """`count` sự kiện cuối của một stream, mới nhất trước, đã giải JSON thân `d`."""
    entries = _entries(client.xrevrange(stream, count=count))
    return [json.loads(fields[FIELD]) for _entry_id, fields in entries]


def _wait_completed_event(client: SyncRedis, stream: str, deadline: float) -> dict[str, object]:
    """Chờ tới `deadline` cho tới khi sự kiện mới nhất của stream là `completed`."""
    events = _read_stream_events(client, stream, 1)
    while time.monotonic() < deadline and (not events or events[0].get("status") != "completed"):
        time.sleep(0.05)
        events = _read_stream_events(client, stream, 1)
    assert events, "không thấy sự kiện nào trên stream trước hạn"
    assert events[0].get("status") == "completed", f"sự kiện cuối không phải completed: {events[0]}"
    return events[0]


def _wait_failed_progress(db_url: str, upload_id: str, deadline: float) -> dict[str, object]:
    """Chờ tới `deadline` cho tới khi `Progress` của lượt tải thành `failed`."""
    wire = on_own_loop(db_url, lambda maker: _progress(maker, upload_id))
    while time.monotonic() < deadline and wire.get("status") != "failed":
        time.sleep(0.1)
        wire = on_own_loop(db_url, lambda maker: _progress(maker, upload_id))
    return wire


async def _quality_bytes(storage: LocalDiskStorage, arranged: Arranged) -> bytes:
    """Đọc lại `quality.json` của lượt bằng `open_read` đúng khoá ([8])."""
    key = run_artifact(
        arranged.project_id, arranged.floor_id, arranged.upload_id, arranged.run_id, "qualityCheck", QUALITY_ARTIFACT
    )
    return b"".join([chunk async for chunk in storage.open_read(key)])


async def _completed_count(client: AsyncRedis, stream: str) -> int:
    """Số sự kiện `completed` trong tối đa 10 mục cuối của stream (K18: không bao giờ > 1)."""
    events = _entries(await client.xrevrange(stream, count=10))
    return sum(1 for _id, fields in events if json.loads(fields[FIELD]).get("status") == "completed")


@pytest.mark.asyncio(loop_scope="function")
async def test_check_pipeline_quality__J01(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Lõi → `completed`; `progress_wire` `completed`/100/`endedAt`; `quality.json` đọc lại được.

    Sự kiện cuối trên `upload_stream` là `completed` (lõi phát `Progress` sau khi đóng lượt).
    """
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)

    outcome = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )

    assert outcome == "completed"
    wire = await _progress(db_sessionmaker, arranged.upload_id)
    assert wire["status"] == "completed"
    assert wire["progressPercent"] == 100
    assert "endedAt" in wire
    body = await _quality_bytes(local_storage, arranged)
    report = json.loads(body)
    assert report["runId"] == arranged.run_id
    entries = _entries(await streams_client.xrevrange(upload_stream(arranged.upload_id), count=1))
    assert json.loads(entries[0][1][FIELD])["status"] == "completed"


@pytest.mark.usefixtures("process_env")
def test_check_pipeline_quality__J01_smoke(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    celery_worker_factory: WorkerFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`send_task` tới worker thật nghe `pipeline.cpu`: ≤ 5 s có sự kiện `completed` trên stream.

    Không gọi `after_commit_idle`: dây task + callback sau commit tự lo, test chỉ quan sát từ
    ngoài qua Redis. Không mang marker `perf` (luật 14): 5 s là điều kiện chờ chống treo.
    """
    monkeypatch.setattr(tasks._STORAGE, "_factory", lambda: local_storage)
    arranged = on_own_loop(db_url, lambda maker: open_run_at_quality(maker, local_storage, fake_clock))

    start = time.monotonic()
    with celery_worker_factory([CPU_QUEUE]):
        send_task(tasks.QUALITY_TASK, arranged.payload)
        stream_client = streams_redis_sync()
        try:
            event = _wait_completed_event(stream_client, upload_stream(arranged.upload_id), time.monotonic() + 5.0)
        finally:
            stream_client.close()
    _log.info("j01_smoke_elapsed_s=%.3f", time.monotonic() - start)

    assert event["status"] == "completed"


@pytest.mark.asyncio(loop_scope="function")
async def test_check_pipeline_quality__J06(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Giao lặp: lần hai `skipped`; `put` đúng một lần; một sự kiện `completed` trên stream."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)
    put_calls = 0
    original_put = local_storage.put

    async def counting_put(
        key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """`put` thật, chỉ thêm đếm số lượt gọi để test khẳng định không ghi đè lần hai."""
        nonlocal put_calls
        put_calls += 1
        return await original_put(key, data, content_type=content_type, max_bytes=max_bytes)

    local_storage.put = counting_put  # type: ignore[method-assign]  # vá thẳng instance cho test này

    first = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )
    second = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )

    assert first == "completed"
    assert second == "skipped"
    assert put_calls == 1
    assert await _completed_count(streams_client, upload_stream(arranged.upload_id)) == 1


@pytest.mark.usefixtures("process_env")
def test_check_pipeline_quality__J03(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    celery_worker_factory: WorkerFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tài liệu ghi `schema_version=2` (hỏng) → `failed` `PIPELINE_RESULT_INVALID`, không `endedAt`.

    `load_document` kiểm cột `schema_version` trước khi gọi codec ([4] "ĐỌC FILE NÀO" → B3-02),
    nên lượt tải tay bằng SQL đủ để dựng tài liệu "hỏng" không cần một bộ giải mã lỗi riêng.
    """
    monkeypatch.setattr(tasks._STORAGE, "_factory", lambda: local_storage)
    arranged = on_own_loop(db_url, lambda maker: open_run_at_quality(maker, local_storage, fake_clock))

    async def _corrupt(maker: Maker) -> None:
        """Ghi `schema_version` sai lược đồ trực tiếp bằng SQL để giả lập tài liệu hỏng."""
        async with maker() as db:
            await db.execute(
                update(FloorDocumentRow).where(FloorDocumentRow.floor_pk == arranged.floor_pk).values(schema_version=2)
            )
            await db.commit()

    on_own_loop(db_url, _corrupt)

    with celery_worker_factory([CPU_QUEUE]):
        send_task(tasks.QUALITY_TASK, arranged.payload)
        wire = _wait_failed_progress(db_url, arranged.upload_id, time.monotonic() + 30.0)

    assert wire["status"] == "failed"
    assert wire["error"] == PIPELINE_RESULT_INVALID
    assert "endedAt" not in wire


@pytest.mark.asyncio(loop_scope="function")
async def test_check_pipeline_quality__J10(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, streams_client: AsyncRedis
) -> None:
    """Lượt đầu commit xong rồi chết trước khi phát → gọi lại `skipped`, đúng một `completed`."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)

    with drop_after_commit():
        first = await service.run_quality(
            arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
        )
    assert first == "completed"
    before = await streams_client.xlen(upload_stream(arranged.upload_id))

    second = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )

    assert second == "skipped"
    assert await _completed_count(streams_client, upload_stream(arranged.upload_id)) == 1
    assert await streams_client.xlen(upload_stream(arranged.upload_id)) == before + 1


class _HangingXrevrange:
    """`xrevrange` không bao giờ trả lời: báo `started` rồi treo trên một `Event` không ai đặt.

    Lõi tự bọc lời gọi này trong `asyncio.wait_for(…, 1.0)` (`_XREVRANGE_TIMEOUT_S`), nên chính
    `wait_for` huỷ coroutine đang chờ sau 1 s — bọc này không cần tự thả, đúng hình dạng "Redis
    treo thật sự" (không ai trả lời) chứ không phải "trả lời chậm".
    """

    def __init__(self, started: asyncio.Event) -> None:
        """Giữ cờ báo cho test biết `xrevrange` đã được gọi."""
        self._started = started

    async def xrevrange(self, *args: object, **kwargs: object) -> NoReturn:
        """Treo vô hạn (chỉ `wait_for` ngoài huỷ được) để giả lập Redis không trả lời."""
        self._started.set()
        await asyncio.Event().wait()
        raise AssertionError("không tới đây: Event không ai đặt")


class _FailingXrevrange:
    """`xrevrange` ném `RedisError` ngay (nhánh lỗi, không treo) — tách khỏi nhánh `TimeoutError`."""

    async def xrevrange(self, *args: object, **kwargs: object) -> NoReturn:
        """Ném `RedisError` ngay lập tức, không treo."""
        raise redis.exceptions.RedisError("redis-broker giả lập hỏng")


@pytest.mark.perf
@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_quality_replay_redis_hang_skips(
    db_url: str,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`xrevrange` treo (Event không bao giờ đặt) → lõi trả `skipped` ≤ 2 s qua trần nội bộ 1 s.

    Lượt đã `completed` ở lần gọi trước, nên lần hai đi vào nhánh đọc Redis trước khi quyết định
    phát lại. Engine riêng của test (không phải `db_sessionmaker` của fixture) để đọc được
    `pool.checkedout()` — lõi không được giữ session nào trong lúc chờ Redis treo. `started` báo
    đúng lúc lõi đã vào lời gọi `xrevrange` để lần đọc pool không rơi vào lúc phiên đọc đầu còn mở.
    """
    settings = DatabaseSettings(database_url=db_url)
    engine = create_engine(settings)
    maker = create_sessionmaker(engine)
    try:
        arranged = await open_run_at_quality(maker, local_storage, fake_clock)
        first = await service.run_quality(arranged.payload, sessionmaker=maker, storage=local_storage, clock=fake_clock)
        assert first == "completed"

        started = asyncio.Event()
        monkeypatch.setattr(service, "streams_redis", lambda *a, **kw: _HangingXrevrange(started))

        start = time.monotonic()
        task = asyncio.create_task(
            service.run_quality(arranged.payload, sessionmaker=maker, storage=local_storage, clock=fake_clock)
        )
        await asyncio.wait_for(started.wait(), WAIT_S)
        assert cast("QueuePool", engine.pool).checkedout() == 0
        outcome = await asyncio.wait_for(task, WAIT_S)

        elapsed = time.monotonic() - start
        _log.info("redis_hang_elapsed_s=%.3f", elapsed)
        assert outcome == "skipped"
        assert elapsed <= 2.0
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_quality_replay_redis_error_skips(
    db_sessionmaker: Maker,
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`RedisError` khi đọc sự kiện cuối → `skipped` ngay, không ném ra ngoài (nhánh lỗi riêng)."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)
    first = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )
    assert first == "completed"

    monkeypatch.setattr(service, "streams_redis", lambda *a, **kw: _FailingXrevrange())

    outcome = await service.run_quality(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )

    assert outcome == "skipped"


class _GatedPut(LocalDiskStorage):
    """Kho đĩa thật, `put` báo `opened` rồi chờ `released` trước khi ghi thật (khuôn K36 của B5-06b)."""

    def __init__(self, base: LocalDiskStorage, *, opened: asyncio.Event, released: asyncio.Event) -> None:
        """Chép cấu hình của `base`; hai `Event` thuộc vòng sự kiện của test đang chạy."""
        self.__dict__.update(base.__dict__)
        self._opened = opened
        self._released = released

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Dừng ở ngưỡng cửa: test kiểm pool xong mới thả cho ghi thật."""
        self._opened.set()
        await self._released.wait()
        return await super().put(key, data, content_type=content_type, max_bytes=max_bytes)


@pytest.mark.asyncio(loop_scope="function")
@pytest.mark.usefixtures("messaging_env")
async def test_quality_holds_no_session_during_put(
    db_url: str, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Pool một kết nối: lúc `storage.put` đang chờ, `checkedout() == 0` (K36).

    Khuôn `apps/worker/pipeline_persist/tests/test_persist_k36.py`: pool một kết nối chứng minh
    lõi đã đóng session đọc trước khi chạm kho, không phải chỉ "tình cờ" không đụng pool khác.
    `messaging_env` vì bước 4 gửi gì cũng không ở đây — lượt đã ở `qualityCheck` nên lõi chỉ
    `record_step` và phát `Progress` qua broker thật sau commit.
    """
    settings = DatabaseSettings(database_url=db_url, db_pool_size=1, db_max_overflow=0, db_pool_timeout_s=1)
    engine = create_engine(settings)
    maker = create_sessionmaker(engine)
    try:
        arranged = await open_run_at_quality(maker, local_storage, fake_clock)
        opened, released = asyncio.Event(), asyncio.Event()
        gated = _GatedPut(local_storage, opened=opened, released=released)

        core = asyncio.create_task(
            service.run_quality(arranged.payload, sessionmaker=maker, storage=gated, clock=fake_clock)
        )
        try:
            await asyncio.wait_for(opened.wait(), WAIT_S)
            checked_out = cast("QueuePool", engine.pool).checkedout()
            _log.info("quality_k36_checkedout_while_put=%d", checked_out)
            assert checked_out == 0
            released.set()
            assert await asyncio.wait_for(core, WAIT_S) == "completed"
        finally:
            released.set()
            core.cancel()
    finally:
        await engine.dispose()
