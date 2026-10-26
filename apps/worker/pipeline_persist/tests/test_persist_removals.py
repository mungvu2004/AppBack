"""Lượt chạy lại tôn trọng việc người đã làm (FIX-P0-07, B5-06b [6] "make_merge").

Cảnh thật (K23): lượt một ghi lớp AI, người sửa qua chính `write_layer` (đường #35 dùng), rồi
lượt hai cùng `layer.json` giao lại. Bia mộ đọc bằng `human_removals` dưới khoá tầng; không có
mock nào.
"""

import logging

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import reset_sync_bus_cache
from apps.api.spatial_read.documents import FloorDocument, load_document
from apps.api.spatial_write.writer import LayerWrite, write_layer
from apps.worker.pipeline_persist.tests.helpers import Arranged, arrange, persist_once, restart_run
from packages.db.hooks import after_commit_idle
from packages.domain.spatial.model import SpatialLayer
from packages.storage.local import LocalDiskStorage
from packages.testing.fixtures.clock import FakeClock


@pytest.fixture(autouse=True)
def _clean_bus(messaging_env: None) -> None:
    """`publish_progress_after_commit` nhớ client Redis theo URL, mà URL đổi mỗi lượt chạy."""
    reset_sync_bus_cache()


async def _document(maker: async_sessionmaker[AsyncSession], arranged: Arranged) -> FloorDocument:
    """Tài liệu tầng hiện tại của cảnh; phải có (lượt một đã ghi)."""
    async with maker() as db:
        document = await load_document(db, arranged.floor_pk)
    assert document is not None
    return document


async def _human_write(
    maker: async_sessionmaker[AsyncSession], arranged: Arranged, clock: FakeClock, body: LayerWrite
) -> None:
    """Một lượt ghi của người tải lên (không phải `SYSTEM_PIPELINE`) trên revision hiện tại, rồi commit."""
    document = await _document(maker, arranged)
    async with maker() as db:
        await write_layer(
            db,
            floor_pk=arranged.floor_pk,
            base_revision=document.revision,
            body=body,
            actor_id=arranged.uploader_id,
            actor_name="Người sửa",
            clock=clock,
        )
        await db.commit()
    await after_commit_idle(db)


def _without_wall(layer: SpatialLayer, wall_id: str) -> SpatialLayer:
    """Lớp sau khi người xoá tường `wall_id`: bỏ cả ô mở của nó và gỡ id khỏi `wallIds` của phòng."""
    rooms = tuple(
        room.model_copy(update={"wall_ids": tuple(i for i in room.wall_ids if i != wall_id)}) for room in layer.rooms
    )
    return layer.model_copy(
        update={
            "walls": tuple(wall for wall in layer.walls if wall.id != wall_id),
            "openings": tuple(opening for opening in layer.openings if opening.wall_id != wall_id),
            "rooms": rooms,
        }
    )


async def _rerun(
    maker: async_sessionmaker[AsyncSession], storage: LocalDiskStorage, arranged: Arranged, clock: FakeClock
) -> FloorDocument:
    """Lượt hai cùng `layer.json` giao lại tới khi ghi xong; trả tài liệu sau lượt đó."""
    second = await restart_run(maker, storage, arranged, clock)
    assert await persist_once(maker, storage, second, clock) == "persisted"
    return await _document(maker, arranged)


@pytest.mark.asyncio(loop_scope="function")
async def test_run_persist_suppresses_user_deleted_wall(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Người xoá một tường AI → lượt chạy lại không đưa nó về, và log số mục bị chặn."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"
    before = await _document(db_sessionmaker, arranged)
    gone = before.layer.walls[0]
    gone_ids = {gone.id, *(opening.id for opening in before.layer.openings if opening.wall_id == gone.id)}
    dimensions = tuple(d for d in before.dimensions if not gone_ids & set(d.reference_ids))
    await _human_write(
        db_sessionmaker, arranged, fake_clock, LayerWrite(_without_wall(before.layer, gone.id), None, dimensions)
    )

    with caplog.at_level(logging.INFO, logger="apps.worker.pipeline_persist.service"):
        after = await _rerun(db_sessionmaker, local_storage, arranged, fake_clock)

    assert gone.id not in {wall.id for wall in after.layer.walls}
    counts = [getattr(r, "count", 0) for r in caplog.records if r.getMessage() == "pipeline_suppressed_by_removal"]
    assert counts
    assert counts[0] >= 1


@pytest.mark.asyncio(loop_scope="function")
async def test_run_persist_keeps_edited_unreviewed_wall(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Người sửa chiều cao một tường AI mà chưa duyệt → lượt chạy lại giữ bản người sửa (`edited`)."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"
    before = await _document(db_sessionmaker, arranged)
    target = before.layer.walls[0]
    edited_height = target.height_mm + 123
    walls = tuple(
        wall.model_copy(update={"height_mm": edited_height}) if wall.id == target.id else wall
        for wall in before.layer.walls
    )
    await _human_write(
        db_sessionmaker, arranged, fake_clock, LayerWrite(before.layer.model_copy(update={"walls": walls}), None)
    )

    after = await _rerun(db_sessionmaker, local_storage, arranged, fake_clock)

    kept = next(wall for wall in after.layer.walls if wall.id == target.id)
    assert (kept.height_mm, kept.edited, kept.reviewed, kept.source) == (edited_height, True, False, "ai")
    assert len(after.layer.walls) == len(before.layer.walls)


@pytest.mark.asyncio(loop_scope="function")
async def test_run_persist_keeps_overridden_dimension(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Người ghi đè giá trị một kích thước AI → lượt chạy lại giữ giá trị đó, không sinh bản trùng."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"
    before = await _document(db_sessionmaker, arranged)
    assert before.dimensions, "mẫu tầng 0 phải có kích thước"
    target = before.dimensions[0]
    override = target.value_mm + 100
    dimensions = tuple(
        d.model_copy(update={"override_value_mm": override}) if d.id == target.id else d for d in before.dimensions
    )
    await _human_write(db_sessionmaker, arranged, fake_clock, LayerWrite(None, None, dimensions))

    after = await _rerun(db_sessionmaker, local_storage, arranged, fake_clock)

    assert [d.override_value_mm for d in after.dimensions if d.id == target.id] == [override]
    assert len(after.dimensions) == len(before.dimensions)
