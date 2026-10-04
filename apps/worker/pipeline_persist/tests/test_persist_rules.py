"""Luật nghiệp vụ của lõi `run_persist` (B5-06b [8] "Test đặt tên theo việc").

Dịch vụ thật (K23): mọi điều kiện được dựng bằng dòng thật — tầng xoá mềm bằng `deleted_at`,
lượt bị thay bằng `start_run` lần hai, tỉ lệ người bằng `make_floor_document`. Chỗ duy nhất
`monkeypatch` chạm vào là `service.mark_persisted` (một tình huống "không thể xảy ra" dưới
khoá, không có đường dữ liệu nào dựng được) và một lớp kho con ném `DEPENDENCY_UNAVAILABLE`.
"""

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.registry import active_versions
from apps.api.drawings.runs import record_step, reset_sync_bus_cache, start_run
from apps.api.floors.settings import get_floors_settings
from apps.api.spatial_read.documents import load_document
from apps.api.spatial_write.errors import LAYER_INTEGRITY_BROKEN
from apps.worker.pipeline_build.errors import PIPELINE_ARTIFACT_INVALID, PIPELINE_ARTIFACT_MISSING
from apps.worker.pipeline_orchestrate.pins import load_pins, pin_models
from apps.worker.pipeline_persist import service
from apps.worker.pipeline_persist.context import PersistContext, load_context
from apps.worker.pipeline_persist.errors import PIPELINE_RESULT_INVALID
from apps.worker.pipeline_persist.service import run_persist
from apps.worker.pipeline_persist.tests.helpers import (
    DONE_STEPS,
    Arranged,
    arrange,
    broken_layer,
    open_run_at_build,
    persist_once,
    put_layer,
    sample_built,
)
from packages.core.error_codes import DEPENDENCY_UNAVAILABLE
from packages.core.errors import AppError
from packages.core.ids import new_id
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.notifications import NotificationRow
from packages.db.models.projects import Project, ProjectMembership
from packages.domain.scale.rescale import rescale_unreviewed
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.tasks import PermanentError
from packages.storage.local import LocalDiskStorage
from packages.storage.port import CHUNK_SIZE
from packages.testing.factories.drawings import make_drawing, png_bytes
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

PNG: Final = png_bytes(800, 600)
"""Trang đã nắn của lượt tải; nội dung không quan trọng, chỉ cần một `page_key` thật."""


class BrokenStorage(LocalDiskStorage):
    """Kho đĩa thật nhưng `open_read` luôn báo phụ thuộc chết — không phải mock DB.

    Dùng để dựng nhánh `DEPENDENCY_UNAVAILABLE` lan ra (B0-05 thử lại), tình huống mà kho
    đĩa cục bộ không bao giờ tự sinh ra.
    """

    def __init__(self, base: LocalDiskStorage) -> None:
        """Mượn nguyên cấu hình của `local_storage`, không dựng kho thứ hai."""
        self.__dict__.update(base.__dict__)

    def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Luôn ném `DEPENDENCY_UNAVAILABLE` ngay khi người gọi mở luồng."""
        raise AppError(DEPENDENCY_UNAVAILABLE, retry_after=1)


@pytest.fixture(autouse=True)
def _clean_bus(messaging_env: None) -> None:
    """`publish_progress_after_commit` nhớ client Redis theo URL, mà URL đổi mỗi lượt chạy."""
    reset_sync_bus_cache()


async def _drawing_page_key(
    maker: async_sessionmaker[AsyncSession], storage: LocalDiskStorage, arranged: Arranged
) -> str:
    """Đặt bản vẽ đang dùng của tầng từ lượt tải của cảnh và trả `page_key` của nó."""
    async with maker() as db:
        upload = (await db.execute(select(UploadRow).where(UploadRow.id == arranged.upload_id))).scalar_one()
        drawing = await make_drawing(db, storage, upload=upload, png=PNG)
        await db.commit()
    return drawing.page_key


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_keeps_reviewed_entities(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """K21: tường đã duyệt giữ nguyên từng trường; tham chiếu của phần AI còn lại vẫn trỏ đúng."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    reviewed = sample_floor_layer(0, level_id=arranged.level_id, reviewed=True)
    async with db_sessionmaker() as db:
        await make_floor_document(db, floor_pk=arranged.floor_pk, layer=reviewed, clock=fake_clock)
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        document = await load_document(db, arranged.floor_pk)
    assert document is not None
    kept = {wall.id: wall for wall in document.layer.walls}
    for wall in reviewed.walls:
        assert kept[wall.id] == wall
    ids = {entity.id for entity in document.layer.entities()}
    for dimension in document.dimensions:
        assert set(dimension.reference_ids) <= ids


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_keeps_human_scale_on_same_page(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tỉ lệ người 10 trên **cùng** trang thắng: nguồn `human`, lớp AI bị đưa về 10 (K19)."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    page_key = await _drawing_page_key(db_sessionmaker, local_storage, arranged)
    async with db_sessionmaker() as db:
        await make_floor_document(
            db,
            floor_pk=arranged.floor_pk,
            scale=Decimal("10"),
            scale_source="human",
            scale_page_key=page_key,
            clock=fake_clock,
        )
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        document = await load_document(db, arranged.floor_pk)
    assert document is not None
    assert (document.scale_mm_per_px, document.scale_source) == (Decimal("10"), "human")
    expected = rescale_unreviewed(sample_built(arranged.level_id).layer, 12.0, 10.0)
    stored = {wall.id: wall for wall in document.layer.walls}
    for wall in expected.walls:
        assert stored[wall.id] == wall


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_ai_scale_wins_on_another_page(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tỉ lệ người 10 gắn trang **khác** → hạng cũ coi như `none`: tỉ lệ AI 12 thắng."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    await _drawing_page_key(db_sessionmaker, local_storage, arranged)
    async with db_sessionmaker() as db:
        await make_floor_document(
            db,
            floor_pk=arranged.floor_pk,
            scale=Decimal("10"),
            scale_source="human",
            scale_page_key="projects/x/floors/y/uploads/z/pages/0-OTHERPAGE00.png",
            clock=fake_clock,
        )
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        document = await load_document(db, arranged.floor_pk)
    assert document is not None
    assert (document.scale_mm_per_px, document.scale_source) == (Decimal("12"), "pipeline")


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_pipeline_scale_beats_project_default(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tầng đang ở `project_default` 1 → tỉ lệ `pipeline` 12 của lượt dựng thắng."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await make_floor_document(
            db, floor_pk=arranged.floor_pk, scale=Decimal("1"), scale_source="project_default", clock=fake_clock
        )
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        document = await load_document(db, arranged.floor_pk)
    assert document is not None
    assert (document.scale_mm_per_px, document.scale_source) == (Decimal("12"), "pipeline")


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_skips_superseded_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`start_run` lần hai thay lượt cũ → lõi bỏ qua, không phiên bản, không thông báo."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await start_run(db, upload_id=arranged.upload_id, clock=fake_clock)
        await db.commit()
    await after_commit_idle(db)

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        assert await load_document(db, arranged.floor_pk) is None
        assert await _notification_count(db, arranged.uploader_id) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_skips_completed_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lượt đã `completed` là lượt đã kết thúc: `lock_run` trả `None`, lõi bỏ qua."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(update(PipelineRunRow).where(PipelineRunRow.id == arranged.run_id).values(status="completed"))
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        assert await load_document(db, arranged.floor_pk) is None


async def _notification_count(db: AsyncSession, user_id: str) -> int:
    """Số dòng `notifications` của một người dùng."""
    return len(list((await db.execute(select(NotificationRow).where(NotificationRow.user_id == user_id))).scalars()))


async def _soft_delete_floor(maker: async_sessionmaker[AsyncSession], arranged: Arranged, at: datetime | None) -> None:
    """Đặt `floors.deleted_at` thẳng bằng `UPDATE` — đường HTTP xoá tầng không thuộc test này."""
    async with maker() as db:
        await db.execute(update(FloorRow).where(FloorRow.pk == arranged.floor_pk).values(deleted_at=at))
        await db.commit()


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_defers_while_floor_is_restorable(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tầng vừa gỡ, còn trong cửa sổ → hoãn: lượt giữ nguyên bước; khôi phục rồi giao lại → ghi."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    await _soft_delete_floor(db_sessionmaker, arranged, fake_clock.now())

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == arranged.run_id))).scalar_one()
        assert (row.current_step, row.error_code) == ("spatialDataBuild", None)
    await _soft_delete_floor(db_sessionmaker, arranged, None)

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_fails_step_when_floor_is_past_window(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tầng xoá quá cửa sổ khôi phục → bước `failed` `FLOOR_DELETED` ngay, không ghi lớp."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    window = get_floors_settings().floor_restore_window_s
    await _soft_delete_floor(db_sessionmaker, arranged, fake_clock.now() - timedelta(seconds=window + 1))

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == arranged.run_id))).scalar_one()
        assert row.error_code == "FLOOR_DELETED"
        assert await load_document(db, arranged.floor_pk) is None


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_fails_step_when_project_is_deleted(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Dự án xoá mềm không có cửa sổ: bước `failed` `FLOOR_DELETED` ngay."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(update(Project).where(Project.id == arranged.project_id).values(deleted_at=fake_clock.now()))
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == arranged.run_id))).scalar_one()
    assert row.error_code == "FLOOR_DELETED"


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_skips_notification_for_removed_member(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Người tải đã bị gỡ khỏi dự án → không dòng `notifications`, bước vẫn `completed` ([7])."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(
            delete(ProjectMembership).where(
                ProjectMembership.project_id == arranged.project_id,
                ProjectMembership.user_id == arranged.uploader_id,
            )
        )
        await db.commit()

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        assert await _notification_count(db, arranged.uploader_id) == 0
        row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == arranged.run_id))).scalar_one()
    assert row.current_step == "qualityCheck"


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_second_run_marks_same_revision(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lượt hai với cùng `layer.json`: `applied=False` nhưng `persisted_revision` vẫn là revision đó."""
    first = await arrange(db_sessionmaker, local_storage, fake_clock)
    assert await _persist(db_sessionmaker, local_storage, first, fake_clock) == "persisted"
    second = await _restart(db_sessionmaker, local_storage, first, fake_clock)

    assert await _persist(db_sessionmaker, local_storage, second, fake_clock) == "persisted"

    async with db_sessionmaker() as db:
        document = await load_document(db, first.floor_pk)
        pins = await load_pins(db, second.run_id)
        notifications = await _notification_count(db, first.uploader_id)
    assert document is not None
    assert pins is not None
    assert pins.persisted_revision == document.revision
    assert notifications == 2


async def _restart(
    maker: async_sessionmaker[AsyncSession], storage: LocalDiskStorage, arranged: Arranged, clock: FakeClock
) -> Arranged:
    """Mở lượt chạy thứ hai cho cùng lượt tải, đưa nó tới `spatialDataBuild` và ghi `layer.json`."""
    async with maker() as db:
        run = await start_run(db, upload_id=arranged.upload_id, clock=clock)
        await pin_models(db, run_id=run.id, models=await active_versions(db))
        await record_step(db, run_id=run.id, step="preprocess", status="running", clock=clock)
        for step in DONE_STEPS:
            await record_step(db, run_id=run.id, step=step, status="completed", clock=clock)
        await db.commit()
    await after_commit_idle(db)
    later = Arranged(
        run_id=run.id,
        upload_id=arranged.upload_id,
        floor_pk=arranged.floor_pk,
        project_id=arranged.project_id,
        floor_id=arranged.floor_id,
        level_id=arranged.level_id,
        floor_name=arranged.floor_name,
        uploader_id=arranged.uploader_id,
        payload=RunStepPayload(schema_version=1, run_id=run.id),
    )
    await put_layer(storage, later, sample_built(later.level_id).to_json())
    return later


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_leaves_used_untouched(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`used` của `pipeline_run_models` là sổ của B5-06c; lõi này không bao giờ chạm vào."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        before = await load_pins(db, arranged.run_id)

    await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    async with db_sessionmaker() as db:
        after = await load_pins(db, arranged.run_id)
    assert before is not None
    assert after is not None
    assert dict(after.used) == dict(before.used)


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_maps_rescale_failure_to_result_invalid(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Tỉ lệ đích quá nhỏ làm `rescale_unreviewed` hỏng thực thể → `PIPELINE_RESULT_INVALID`."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    page_key = await _drawing_page_key(db_sessionmaker, local_storage, arranged)
    async with db_sessionmaker() as db:
        await make_floor_document(
            db,
            floor_pk=arranged.floor_pk,
            scale=Decimal("0.000001"),
            scale_source="human",
            scale_page_key=page_key,
            clock=fake_clock,
        )
        await db.commit()

    with pytest.raises(PermanentError) as caught:
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert caught.value.code == PIPELINE_RESULT_INVALID
    async with db_sessionmaker() as db:
        assert await _notification_count(db, arranged.uploader_id) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_reports_missing_artifact(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`layer.json` chưa có trong kho → `PIPELINE_ARTIFACT_MISSING` (mã của B5-05)."""
    arranged = await open_run_at_build(db_sessionmaker, fake_clock, storage=local_storage)

    with pytest.raises(PermanentError) as caught:
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert caught.value.code == PIPELINE_ARTIFACT_MISSING


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_reports_broken_artifact(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """`layer.json` không phải JSON hợp đồng B5-05 → `PIPELINE_ARTIFACT_INVALID`."""
    arranged = await open_run_at_build(db_sessionmaker, fake_clock, storage=local_storage)
    await put_layer(local_storage, arranged, b"{khong-phai-json")

    with pytest.raises(PermanentError) as caught:
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert caught.value.code == PIPELINE_ARTIFACT_INVALID


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_lets_dependency_failure_propagate(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Kho chết → `DEPENDENCY_UNAVAILABLE` lan nguyên để B0-05 thử lại, không thành lỗi vĩnh viễn."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)

    with pytest.raises(AppError) as caught:
        await _persist(db_sessionmaker, BrokenStorage(local_storage), arranged, fake_clock)

    assert caught.value.code is DEPENDENCY_UNAVAILABLE


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_raises_when_mark_persisted_refuses(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`mark_persisted` trả `False` dưới khoá là bất khả; lõi phải nổ chứ không lặng lẽ đi tiếp."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)

    async def refuse(db: AsyncSession, *, run_id: str, revision: int) -> bool:
        """Bản giả của `pins.mark_persisted` luôn từ chối (tình huống không dựng được bằng dữ liệu)."""
        return False

    monkeypatch.setattr(service, "mark_persisted", refuse)

    with pytest.raises(RuntimeError):
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_skips_unknown_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Không có dòng lượt nào → `skipped` ngay ở session đầu, không đụng kho."""
    payload = RunStepPayload(schema_version=1, run_id=new_id("run", fake_clock))

    outcome = await run_persist(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)

    assert outcome == "skipped"


class TinyArtifactLimit:
    """Cấu hình B5-05 với trần byte 1: dựng ca "artifact vượt trần" không cần 16 MiB thật."""

    PIPELINE_ARTIFACT_MAX_BYTES = 1


def _tiny_limit() -> TinyArtifactLimit:
    """Bản thay `get_pipeline_build_settings` cho lõi; chỉ đổi trần, không đụng dịch vụ nào."""
    return TinyArtifactLimit()


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_rejects_oversized_artifact(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`layer.json` vượt `PIPELINE_ARTIFACT_MAX_BYTES` → `PIPELINE_ARTIFACT_INVALID`, không đọc hết."""
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    monkeypatch.setattr(service, "get_pipeline_build_settings", _tiny_limit)

    with pytest.raises(PermanentError) as caught:
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert caught.value.code == PIPELINE_ARTIFACT_INVALID


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_propagates_layer_integrity_error(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
) -> None:
    """Lớp AI có ô mở trỏ tường không có → mã của `write_layer` lan **nguyên** vào `Progress.error`."""
    arranged = await open_run_at_build(db_sessionmaker, fake_clock, storage=local_storage)
    await put_layer(local_storage, arranged, broken_layer(arranged.level_id))

    with pytest.raises(PermanentError) as caught:
        await persist_once(db_sessionmaker, local_storage, arranged, fake_clock)

    assert caught.value.code == LAYER_INTEGRITY_BROKEN.code
    async with db_sessionmaker() as db:
        assert await load_document(db, arranged.floor_pk) is None


@pytest.mark.asyncio(loop_scope="function")
async def test_persist_skips_when_context_vanishes_under_lock(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dòng liên quan biến mất giữa hai lượt đọc → rollback, `skipped`, không ghi gì.

    Lượt đọc **thứ hai** (dưới khoá) mới trả `None`: lượt đầu phải thành công thì lõi mới đi
    tới giao dịch. Không dựng được bằng dữ liệu vì FK giữ `uploads`/`floors`/`projects` sống
    chừng nào còn dòng lượt, nên thay chính `load_context` của lõi.
    """
    arranged = await arrange(db_sessionmaker, local_storage, fake_clock)
    seen = 0

    async def once(db: AsyncSession, run_id: str) -> PersistContext | None:
        """Lượt đầu trả thật, mọi lượt sau trả `None`."""
        nonlocal seen
        seen += 1
        return await load_context(db, run_id) if seen == 1 else None

    monkeypatch.setattr(service, "load_context", once)

    assert await persist_once(db_sessionmaker, local_storage, arranged, fake_clock) == "skipped"

    async with db_sessionmaker() as db:
        assert await load_document(db, arranged.floor_pk) is None
