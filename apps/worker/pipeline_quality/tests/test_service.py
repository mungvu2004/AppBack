"""Test tích hợp của `service.run_quality`/`fail_quality` trên dịch vụ thật (B5-07 [8]).

Postgres, Redis, kho đĩa đều thật (K23): không mock session, `load_document`, `record_step`
hay Redis. Phần J01/J03/J06/J10/K36/Redis treo là của việc B — ở đây chỉ phần của việc A theo
checklist [8].
"""

import asyncio
import json
from datetime import timedelta
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import reset_sync_bus_cache, start_run
from apps.api.floors.settings import get_floors_settings
from apps.worker.pipeline_build.build import BuiltLayer
from apps.worker.pipeline_build.constants import DROPPED_KEYS
from apps.worker.pipeline_persist.errors import PIPELINE_RESULT_INVALID
from apps.worker.pipeline_persist.service import run_persist
from apps.worker.pipeline_persist.tests.helpers import ai_layer, open_run_at_build, put_layer
from apps.worker.pipeline_quality.report import QUALITY_ARTIFACT
from apps.worker.pipeline_quality.service import fail_quality, run_quality
from apps.worker.pipeline_quality.tests.helpers import Arranged, open_run_at_quality
from packages.core.ids import new_id
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.db.models.notifications import NotificationRow
from packages.db.models.spatial import FloorDocumentRow
from packages.domain.spatial.model import Opening
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.messaging.redis import broker_redis_sync
from packages.messaging.tasks import PermanentError
from packages.storage.keys import run_artifact
from packages.storage.port import ObjectStorage
from packages.testing.factories.spatial import sample_floor_dimensions
from packages.testing.fixtures.clock import FakeClock

CPU_QUEUE: Final = "pipeline.cpu"
STEP: Final = "qualityCheck"


@pytest.fixture
def quality_env(messaging_env: None) -> None:
    """`messaging_env` + cache bus đồng bộ sạch giữa test (URL Redis đổi mỗi lượt, như B5-06b)."""
    reset_sync_bus_cache()


async def _run_row(maker: async_sessionmaker[AsyncSession], run_id: str) -> tuple[str, str, str | None]:
    """`(status, current_step, error_code)` hiện tại của một lượt, đọc bằng session mới."""
    async with maker() as db:
        row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()
        return row.status, row.current_step, row.error_code


def _quality_key(arranged: Arranged) -> str:
    """Khoá `quality.json` của một lượt đã dựng."""
    return run_artifact(
        arranged.project_id, arranged.level_id, arranged.upload_id, arranged.run_id, STEP, QUALITY_ARTIFACT
    )


def _broken_built(level_id: str) -> BuiltLayer:
    """Kết quả dựng mang một ô mở trỏ tới tường không tồn tại — lỗi `missingReference` `critical`."""
    layer = ai_layer(level_id)
    dangling = Opening(
        id="D-DANGLE00000000001",
        wall_id="W-GHOST00000000001",
        kind="door",
        offset_mm=0,
        width_mm=800,
        height_mm=2000,
        sill_height_mm=0,
        swing="left",
        source="ai",
        reviewed=False,
        confidence=0.9,
    )
    return BuiltLayer(
        layer=layer.model_copy(update={"openings": (*layer.openings, dangling)}),
        dimensions=sample_floor_dimensions(0, level_id=level_id, id_suffix="AI"),
        scale_mm_per_px=Decimal("12"),
        scale_source="pipeline",
        dropped=dict.fromkeys(DROPPED_KEYS, 0),
    )


class _BlockingPut:
    """Bọc một `ObjectStorage` để tạm dừng ngay sau `put` thật (giữa pha 2 và khoá lại pha 3).

    Không mock `put` (K23): hàm trong vẫn ghi object thật, chỉ chèn một điểm dừng để test
    tranh thủ thay lượt chạy trước khi lõi khoá lại.
    """

    def __init__(self, inner: ObjectStorage, started: asyncio.Event, release: asyncio.Event) -> None:
        self._inner = inner
        self._started = started
        self._release = release

    async def put(self, *args: object, **kwargs: object) -> object:
        """`put` thật rồi báo đã bắt đầu và chờ tín hiệu tiếp tục."""
        result = await self._inner.put(*args, **kwargs)  # type: ignore[arg-type]
        self._started.set()
        await self._release.wait()
        return result

    def __getattr__(self, name: str) -> object:
        """Mọi phương thức khác (`open_read`, `stat`, …) chuyển thẳng cho kho thật."""
        return getattr(self._inner, name)


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__missing_run_skips(
    db_sessionmaker: async_sessionmaker[AsyncSession], local_storage: ObjectStorage, fake_clock: FakeClock
) -> None:
    """Lượt không tồn tại (id hợp mẫu nhưng không có dòng) → `skipped` ngay, không chạm Redis."""
    payload = RunStepPayload(run_id=new_id("run", fake_clock))
    outcome = await run_quality(payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    assert outcome == "skipped"


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__before_persist_skips_without_writing(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """`persisted_revision` còn NULL (chưa qua B5-06b) → `skipped`, bước và kho không đổi."""
    arranged = await open_run_at_build(db_sessionmaker, fake_clock, storage=local_storage)
    broker_redis_sync().delete(CPU_QUEUE)

    outcome = await run_quality(arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)

    assert outcome == "skipped"
    status, step, _ = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status, step) == ("running", "spatialDataBuild")
    assert await local_storage.stat(_quality_key(arranged)) is None


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__missing_document_is_permanent_error(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """Tài liệu tầng biến mất sau khi ghi (hỏng dữ liệu) → `PermanentError(PIPELINE_RESULT_INVALID)`."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(delete(FloorDocumentRow).where(FloorDocumentRow.floor_pk == arranged.floor_pk))
        await db.commit()

    with pytest.raises(PermanentError) as excinfo:
        await run_quality(arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    assert excinfo.value.code == PIPELINE_RESULT_INVALID


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__superseded_before_closing_step_skips_safely(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """Lượt bị thay đúng giữa `put` (pha 2) và khoá lại (pha 3) → `skipped`, lượt cũ `failed`.

    Báo cáo đã `put` đè vô hại (B5-07 [6]): không mock, `storage.put` vẫn ghi object thật.
    """
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)
    started, release = asyncio.Event(), asyncio.Event()
    wrapped = _BlockingPut(local_storage, started, release)
    task = asyncio.create_task(
        run_quality(arranged.payload, sessionmaker=db_sessionmaker, storage=wrapped, clock=fake_clock)
    )
    await started.wait()

    async with db_sessionmaker() as db:
        await start_run(db, upload_id=arranged.upload_id, clock=fake_clock)
        await db.commit()
    release.set()
    outcome = await task

    assert outcome == "skipped"
    status, _, error_code = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status, error_code) == ("failed", "PIPELINE_SUPERSEDED")


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__floor_deleted_past_window_fails_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """Tầng xoá mềm quá cửa sổ trước bước 4 → `skipped`, lượt `failed` `FLOOR_DELETED`."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)
    window = get_floors_settings().floor_restore_window_s
    async with db_sessionmaker() as db:
        await db.execute(update(FloorRow).where(FloorRow.pk == arranged.floor_pk).values(deleted_at=fake_clock.now()))
        await db.commit()
    fake_clock.advance(timedelta(seconds=window + 1))

    outcome = await run_quality(arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)

    assert outcome == "skipped"
    status, _, error_code = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status, error_code) == ("failed", "FLOOR_DELETED")


@pytest.mark.asyncio(loop_scope="function")
async def test_run_quality__completes_with_critical_issue_and_no_extra_notification(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """Đường sạch: `completed`; lớp có lỗi `critical` → `hasCritical` true, không `violationFound`.

    Không `notify` (K rule): bảng `notifications` chỉ có đúng dòng `aiCompleted` của B5-06b.
    """
    arranged = await open_run_at_build(db_sessionmaker, fake_clock, storage=local_storage)
    await put_layer(local_storage, arranged, _broken_built(arranged.level_id).to_json())
    persist_outcome = await run_persist(
        arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock
    )
    assert persist_outcome == "persisted"
    broker_redis_sync().delete(CPU_QUEUE)

    outcome = await run_quality(arranged.payload, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)

    assert outcome == "completed"
    status, step, _ = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status, step) == ("completed", "qualityCheck")
    body = bytearray()
    async for chunk in local_storage.open_read(_quality_key(arranged)):
        body += chunk
    assert json.loads(bytes(body))["hasCritical"] is True
    async with db_sessionmaker() as db:
        stmt = select(NotificationRow).where(NotificationRow.user_id == arranged.uploader_id)
        rows = (await db.execute(stmt)).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_fail_quality__records_failed_and_noops_when_run_gone(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: ObjectStorage,
    fake_clock: FakeClock,
    quality_env: None,
) -> None:
    """Ghi `failed` với mã đã cho; lượt đã kết thúc rồi gọi lại → không ghi gì, không ném."""
    arranged = await open_run_at_quality(db_sessionmaker, local_storage, fake_clock)

    await fail_quality(arranged.payload, "QUALITY_BOOM", sessionmaker=db_sessionmaker, clock=fake_clock)
    status, _, error_code = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status, error_code) == ("failed", "QUALITY_BOOM")

    await fail_quality(arranged.payload, "QUALITY_BOOM_AGAIN", sessionmaker=db_sessionmaker, clock=fake_clock)
    status2, _, error_code2 = await _run_row(db_sessionmaker, arranged.run_id)
    assert (status2, error_code2) == ("failed", "QUALITY_BOOM")


def test_boundary__pipeline_quality_imports_cleanly() -> None:
    """Ranh giới gói: `report`, `service`, `tasks` nhập được, hằng chốt đúng giá trị (BE-00 §2)."""
    import apps.worker.pipeline_quality.report as report
    import apps.worker.pipeline_quality.service as service
    import apps.worker.pipeline_quality.tasks as tasks

    assert report.QUALITY_ARTIFACT == "quality.json"
    assert service.STEP == "qualityCheck"
    assert tasks.QUALITY_TASK == "pipeline.quality.run"
