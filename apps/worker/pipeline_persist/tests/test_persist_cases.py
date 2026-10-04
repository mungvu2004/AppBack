"""Ma trận case của lõi `run_persist` trên dịch vụ thật (B5-06b [8]; J01, J06).

Gọi thẳng lõi với `db_sessionmaker`, `local_storage`, `fake_clock` — ma trận task thật
(`__J01_smoke`, `__J03`, `__J09`, `__J10`) là việc B. Postgres, Redis, kho đĩa đều thật (K23):
không mock session, `write_layer`, `create_version`, `notify` hay Redis. Hàng `pipeline.cpu`
đọc bằng `LRANGE` (`queued_payloads`) vì không worker nào nghe hàng đó.
"""

import asyncio
import logging
from typing import Final

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.progress import progress_wire
from apps.api.drawings.runs import reset_sync_bus_cache
from apps.api.projects.summaries import project_rollups
from apps.api.spatial_read.documents import load_document
from apps.api.versions.messages import before_pipeline_note
from apps.worker.pipeline_orchestrate.pins import load_pins
from apps.worker.pipeline_persist.constants import SYSTEM_PIPELINE_NAME
from apps.worker.pipeline_persist.tests.helpers import CPU_QUEUE, Arranged, arrange, persist_once
from packages.core.errors import SYSTEM_PIPELINE
from packages.db.models.notifications import NotificationRow
from packages.db.models.versions import VersionRecord
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.streams import EventBus, upload_stream, user_stream
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

_log: Final = logging.getLogger(__name__)


@pytest.fixture
def cpu_queue(messaging_env: None) -> SyncRedis:
    """Client broker đã `DEL` hàng `pipeline.cpu`.

    `reset_sync_bus_cache()` kèm theo vì `publish_progress_after_commit` nhớ client theo URL,
    mà URL Redis đổi mỗi lượt chạy test.
    """
    reset_sync_bus_cache()
    client = broker_redis_sync()
    client.delete(CPU_QUEUE)
    return client


async def _versions(db: AsyncSession, floor_pk: int) -> list[VersionRecord]:
    """Mọi phiên bản của tầng theo thứ tự `sequence` tăng dần."""
    stmt = select(VersionRecord).where(VersionRecord.floor_pk == floor_pk).order_by(VersionRecord.sequence)
    return list((await db.execute(stmt)).scalars())


async def _notifications(db: AsyncSession, user_id: str) -> list[NotificationRow]:
    """Mọi thông báo của một người dùng (test chỉ dựng một lượt nên danh sách rất ngắn)."""
    stmt = select(NotificationRow).where(NotificationRow.user_id == user_id)
    return list((await db.execute(stmt)).scalars())


async def _wall_count(db: AsyncSession, project_id: str) -> int:
    """Số tường mà bảng đếm dự án thấy (`project_rollups`, B2-01)."""
    return (await project_rollups(db, [project_id]))[project_id].walls_total


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_result__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cpu_queue: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Đường sạch: lớp AI vào tài liệu, hai phiên bản, thông báo, bước sau đã xếp hàng.

    Đọc lại bằng session mới để khẳng định mọi thứ đã **commit** thật, không phải chỉ nằm
    trong session của lõi.
    """
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock, clear_queue=True)
    before = len(await event_bus.read_after(upload_stream(arranged.upload_id), "0-0"))

    outcome = await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert outcome == "persisted"
    async with db_sessionmaker() as db:
        document = await load_document(db, arranged.floor_pk)
        versions = await _versions(db, arranged.floor_pk)
        pins = await load_pins(db, arranged.run_id)
        wire = await progress_wire(db, arranged.upload_id)
        rows = await _notifications(db, arranged.uploader_id)
        walls = await _wall_count(db, arranged.project_id)
    assert document is not None
    assert document.layer.walls
    assert document.scale_source == "pipeline"
    assert [(v.floor_revision, v.note) for v in versions] == [(0, before_pipeline_note()), (1, None)]
    assert {v.creator_id for v in versions} == {SYSTEM_PIPELINE}
    assert {v.creator_name for v in versions} == {SYSTEM_PIPELINE_NAME}
    assert pins is not None
    assert pins.persisted_revision == 1
    assert (wire["status"], wire["step"], wire["progressPercent"]) == ("running", "qualityCheck", 90)
    assert len(rows) == 1
    assert (rows[0].kind, rows[0].place) == ("aiCompleted", "walls")
    assert (rows[0].floor_level_id, rows[0].object_label) == (arranged.level_id, arranged.floor_name)
    assert walls == len(document.layer.walls)
    progress = await event_bus.read_after(upload_stream(arranged.upload_id), "0-0")
    # Đúng **một** khung mới: `record_step` đã tự hẹn phát, lõi không phát lần thứ hai.
    assert len(progress) - before == 1
    assert (progress[-1].data["status"], progress[-1].data["step"]) == ("running", "qualityCheck")
    assert len(await event_bus.read_after(user_stream(arranged.uploader_id), "0-0")) == 1
    messages = queued_payloads(cpu_queue, CPU_QUEUE)
    assert [m["run_id"] for m in messages] == [arranged.run_id], messages


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_result__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cpu_queue: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Giao lặp tuần tự: lượt hai `replayed`, không phiên bản, thông báo hay mục stream thứ hai."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock, clear_queue=True)

    first = await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)
    second = await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert (first, second) == ("persisted", "replayed")
    await _assert_single_effect(db_sessionmaker, event_bus, arranged, revision=1)
    assert len(queued_payloads(cpu_queue, CPU_QUEUE)) == 2


async def _assert_single_effect(
    maker: async_sessionmaker[AsyncSession], bus: EventBus, arranged: Arranged, *, revision: int
) -> None:
    """K32: dù giao bao nhiêu lần, tầng chỉ có một revision, hai phiên bản, một thông báo."""
    async with maker() as db:
        document = await load_document(db, arranged.floor_pk)
        versions = await _versions(db, arranged.floor_pk)
        rows = await _notifications(db, arranged.uploader_id)
    assert document is not None
    assert document.revision == revision
    assert len(versions) == 2
    assert len(rows) == 1
    assert len(await bus.read_after(user_stream(arranged.uploader_id), "0-0")) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_result__J06_concurrent(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    cpu_queue: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Hai lõi chạy song song trên hai session thật: một `persisted`, một `replayed`, không deadlock.

    `lock_run` khoá `floors` trước mọi việc nên lượt thứ hai xếp hàng sau lượt đầu và thấy
    `persisted_revision` đã có — đúng nhánh phát lại, không phải một lượt ghi thứ hai.
    """
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock, clear_queue=True)

    outcomes = await asyncio.gather(
        persist_once(db_sessionmaker, local_storage, arranged, fake_clock),
        persist_once(db_sessionmaker, local_storage, arranged, fake_clock),
    )

    assert sorted(outcomes) == ["persisted", "replayed"]
    await _assert_single_effect(db_sessionmaker, event_bus, arranged, revision=1)
    async with db_sessionmaker() as db:
        versions = len(await _versions(db, arranged.floor_pk))
        notifications = len(await _notifications(db, arranged.uploader_id))
    stream_items = len(await event_bus.read_after(user_stream(arranged.uploader_id), "0-0"))
    _log.info(
        "j06_concurrent outcomes=%s versions=%d notifications=%d user_stream=%d quality_messages=%d",
        outcomes,
        versions,
        notifications,
        stream_items,
        len(queued_payloads(cpu_queue, CPU_QUEUE)),
    )
