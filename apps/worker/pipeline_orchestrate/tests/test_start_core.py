"""Lõi `run_pipeline_start` trên dịch vụ thật (B5-06a [8], việc C).

Gọi thẳng `run_pipeline_start` với `local_storage` thay vì qua Celery: ma trận task thật
(`__J01_smoke`, `__J02`, `__J08`) là việc D. Postgres, Redis, kho đĩa đều thật (K23); điểm
dừng giữa việc chậm dựng bằng một lớp kho con gọi hook ở `put` đầu tiên, không mock DB.
Hàng `ml.infer` đọc bằng `queued_payloads` (LRANGE) vì không worker nào nghe hàng đó.
"""

import asyncio
import logging
from collections.abc import AsyncIterable, Awaitable, Callable
from pathlib import Path
from typing import Final, cast

import pytest
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.registry import active_versions
from apps.api.drawings.runs import RunRow, reset_sync_bus_cache, start_run
from apps.api.quality.assessments import load_assessment
from apps.worker.pipeline_orchestrate.pins import load_pins
from apps.worker.pipeline_orchestrate.settings import OrchestrateSettings
from apps.worker.pipeline_orchestrate.start import fail_pipeline_start_core, run_pipeline_start
from packages.db.hooks import after_commit_idle
from packages.db.models.admin_ml_registry import ModelFamilyRow
from packages.db.models.drawings import DrawingRow, PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.db.models.projects import Project
from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.streams import EventBus, upload_stream
from packages.ml_contracts.families import ModelFamily
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectInfo
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.db import drop_after_commit
from packages.testing.fixtures.messaging import queued_payloads
from packages.vision.preprocess.tests.synthetic import make_pdf

_log: Final = logging.getLogger(__name__)

ML_QUEUE: Final = "ml.infer"
_A4_RECT: Final = ((60.0, 60.0, 475.0, 722.0, (0.1, 0.1, 0.1)),)
"""Một khung chữ nhật đậm trên khổ A4 để `find_frame` có cái mà bắt (đường (iii))."""


@pytest.fixture
def ml_queue(messaging_env: None) -> SyncRedis:
    """Client broker đã `DEL` hàng `ml.infer` — hàng dùng chung cả phiên nên phải dọn (BE-00 §12).

    `reset_sync_bus_cache()` kèm theo vì `publish_progress_after_commit` nhớ client theo URL,
    mà URL Redis đổi mỗi lượt chạy test.
    """
    reset_sync_bus_cache()
    client = broker_redis_sync()
    client.delete(ML_QUEUE)
    return client


class HookedStorage(LocalDiskStorage):
    """Kho đĩa thật kèm một hook chạy **trước** `put` đầu tiên — điểm dừng giữa việc chậm.

    Dùng thay cho mock: J09/J10 cần đổi trạng thái DB đúng lúc `prepare_page` đang ghi trang
    mới, mà `prepare_page` không có chỗ móc nào khác. Hook chỉ chạy một lần.
    """

    def __init__(self, base: LocalDiskStorage, hook: Callable[[], Awaitable[None]]) -> None:
        """Mượn nguyên cấu hình của `local_storage`, chỉ thêm hook (không dựng kho thứ hai)."""
        self.__dict__.update(base.__dict__)
        self._hook: Callable[[], Awaitable[None]] | None = hook

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Chạy hook một lần rồi ghi thật."""
        hook, self._hook = self._hook, None
        if hook is not None:
            await hook()
        return await super().put(key, data, content_type=content_type, max_bytes=max_bytes)


class GatedStorage(LocalDiskStorage):
    """Kho đĩa thật chặn **sau** khi ghi trang mới cho tới khi test nhả cổng.

    Dùng cho J06 song song: giữ một lượt giao đứng giữa việc chậm để lượt kia commit trước,
    rồi thả ra và xem GD2 của bên thua bị từ chối và trang mới của nó bị xoá.
    """

    def __init__(self, base: LocalDiskStorage, reached: asyncio.Event, release: asyncio.Event) -> None:
        """Mượn cấu hình của `local_storage`; `reached` báo đã tới cổng, `release` mở cổng."""
        self.__dict__.update(base.__dict__)
        self._reached = reached
        self._release = release

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Ghi thật; riêng trang **mới** (`{i}-{ULID}.png`) thì dừng ở cổng sau khi ghi xong."""
        info = await super().put(key, data, content_type=content_type, max_bytes=max_bytes)
        if "-" in key.rsplit("/", 1)[-1]:
            self._reached.set()
            await self._release.wait()
        return info


async def _progress(bus: EventBus, upload_id: str) -> list[tuple[object, object, object]]:
    """`(status, step, percent)` của mọi sự kiện `Progress` trên luồng của một lượt tải."""
    events = await bus.read_after(upload_stream(upload_id), "0-0")
    return [(e.data["status"], e.data["step"], e.data["progressPercent"]) for e in events]


def _new_pages(root: Path) -> list[Path]:
    """Trang **mới** còn sót lại dưới `root`: tên `{i}-{ULID}.png`; `pages/{i}.png` không có dấu gạch."""
    return sorted(root.rglob("*-*.png"))


async def _scene(db: AsyncSession) -> tuple[Project, FloorRow]:
    """Chủ dự án, dự án, một tầng — nền tối thiểu cho mọi test của module."""
    owner = await make_user(db)
    project = await make_project(db, owner=owner)
    return project, await make_floor(db, project=project)


async def _pdf_upload(
    db: AsyncSession, storage: LocalDiskStorage, project: Project, floor: FloorRow, *, page_index: int = 1
) -> UploadRow:
    """Lượt tải PDF hai trang đã `complete`; `page_index=1` để test đúng trang thứ hai."""
    data = make_pdf(2, rects=_A4_RECT)
    return await make_complete_upload(
        db, storage, project=project, floor=floor, data=data, file_name="plan.pdf", page_index=page_index
    )


async def _activate(db: AsyncSession, family: str, version_id: str) -> None:
    """Đặt bản kích hoạt của một họ bằng `UPDATE` thẳng — đường HTTP của B6-01 không thuộc test này."""
    await db.execute(update(ModelFamilyRow).where(ModelFamilyRow.family == family).values(active_version_id=version_id))


async def _open_run(maker: async_sessionmaker[AsyncSession], upload_id: str, clock: FakeClock) -> RunRow:
    """Mở một lượt chạy và commit (task `start` chỉ chạy sau khi B2-04 đã ghi dòng lượt)."""
    async with maker() as db:
        run = await start_run(db, upload_id=upload_id, clock=clock)
        await db.commit()
    await after_commit_idle(db)
    return run


async def _start(
    maker: async_sessionmaker[AsyncSession],
    storage: LocalDiskStorage,
    run: RunRow,
    clock: FakeClock,
    *,
    settings: OrchestrateSettings | None = None,
) -> None:
    """Một lượt giao `pipeline.orchestrate.start` cho `run`, gọi thẳng lõi."""
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    await run_pipeline_start(payload, sessionmaker=maker, storage=storage, clock=clock, settings=settings)


async def _drawings(db: AsyncSession, floor_pk: int) -> list[DrawingRow]:
    """Mọi dòng `drawings` của tầng (một tầng nhiều nhất một dòng — test khẳng định điều đó)."""
    return list((await db.execute(select(DrawingRow).where(DrawingRow.floor_pk == floor_pk))).scalars())


async def _run_row(db: AsyncSession, run_id: str) -> PipelineRunRow:
    """Dòng lượt chạy đọc lại từ DB (không qua ảnh chụp `RunRow`)."""
    row = (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()
    await db.refresh(row)
    return row


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Đường sạch: hai sự kiện `Progress`, một bản vẽ, một dòng đo, ba thông điệp `ml.infer`.

    PDF `pageIndex: 1` nên trang dựng là trang **thứ hai**; `model` của cả ba thông điệp phải
    đúng bằng `pinned`, tức đúng `active_versions` lúc GD1 chạy.
    """
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        pinned = await active_versions(db)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)

    await _start(db_sessionmaker, local_storage, run, fake_clock)

    messages = queued_payloads(ml_queue, ML_QUEUE)
    assert len(messages) == 3, messages
    for message in messages:
        # `step` trên dây là tên họ model, nên tra thẳng vào `pinned` được.
        family = cast("ModelFamily", message["step"])
        assert message["model"] == pinned[family].model_dump(mode="json")
    async with db_sessionmaker() as db:
        drawings = await _drawings(db, floor.pk)
        assessment = await load_assessment(db, floor.pk)
        row = await _run_row(db, run.id)
    assert len(drawings) == 1
    assert assessment is not None
    assert row.current_step == "wallSegmentation"
    # Sự kiện đầu (`pending preprocess 0`) là của `start_run`, không phải của task này.
    assert (await _progress(event_bus, upload.id))[1:] == [
        ("running", "preprocess", 0),
        ("running", "wallSegmentation", 5),
    ]
    _log.info("j01_px_per_paper_mm=%s", messages[0].get("px_per_paper_mm"))


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """Giao lại cùng lượt: vẫn một dòng `drawings`, lần hai không gửi `ml.infer.*`.

    Lần hai lượt đã ở `wallSegmentation` nên GD1 dừng ngay ([6] bước 1); đổi bản kích hoạt
    giữa hai lần cũng không đổi `pinned` vì `pin_models` chỉ ghi lần đầu.
    """
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)
    await _start(db_sessionmaker, local_storage, run, fake_clock)
    first = queued_payloads(ml_queue, ML_QUEUE)

    async with db_sessionmaker() as db:
        version = await make_model_version(db, family="wallSegmentation")
        await _activate(db, "wallSegmentation", version.id)
        await db.commit()
    ml_queue.delete(ML_QUEUE)
    await _start(db_sessionmaker, local_storage, run, fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    async with db_sessionmaker() as db:
        assert len(await _drawings(db, floor.pk)) == 1
    walls = next(m for m in first if m["step"] == "wallSegmentation")
    assert walls["model"] != version.id


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J09(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
    tmp_path: Path,
) -> None:
    """`start_run` thay lượt giữa việc chậm: không `ml.infer.*`, không bản vẽ, trang mới bị xoá."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)

    async def supersede() -> None:
        """Mở lượt mới cho cùng lượt tải → lượt cũ thành `superseded`, GD2 phải từ chối."""
        await _open_run(db_sessionmaker, upload.id, fake_clock)

    storage = HookedStorage(local_storage, supersede)
    ml_queue.delete(ML_QUEUE)
    await _start(db_sessionmaker, storage, run, fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    async with db_sessionmaker() as db:
        assert await _drawings(db, floor.pk) == []
    pages = _new_pages(tmp_path)
    assert pages == [], pages


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__J10(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
    event_bus: EventBus,
) -> None:
    """Callback sau commit rơi quanh GD2: dữ liệu bền vững nhưng không thông điệp ML.

    Giao lại sau đó vẫn không gửi `ml.infer.*` (lượt đã ở `wallSegmentation`); quét bù của
    B5-06c mới là chỗ gửi lại, nên `step_requeue_count` phải còn 0.
    """
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)

    with drop_after_commit():
        await _start(db_sessionmaker, local_storage, run, fake_clock)
    await _start(db_sessionmaker, local_storage, run, fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    async with db_sessionmaker() as db:
        row = await _run_row(db, run.id)
        pins = await load_pins(db, run.id)
    assert row.current_step == "wallSegmentation"
    assert pins is not None
    assert pins.step_requeue_count == 0
    assert (await _progress(event_bus, upload.id))[-1] == ("running", "wallSegmentation", 5)


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__rerun_keeps_page_31(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """Chạy lại sau #31: lượt đã có bản vẽ + đo khớp → đường (i), không trang mới, ML nhận trang cũ."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    first = await _open_run(db_sessionmaker, upload.id, fake_clock)
    await _start(db_sessionmaker, local_storage, first, fake_clock)
    async with db_sessionmaker() as db:
        page_key = (await _drawings(db, floor.pk))[0].page_key
        first_assessment = await load_assessment(db, floor.pk)
        assert first_assessment is not None
        report = first_assessment.report

    second = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)
    await _start(db_sessionmaker, local_storage, second, fake_clock)

    messages = queued_payloads(ml_queue, ML_QUEUE)
    assert len(messages) == 3, messages
    assert {m["page_key"] for m in messages} == {page_key}
    async with db_sessionmaker() as db:
        again = await load_assessment(db, floor.pk)
    assert again is not None
    assert again.report == report


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__ignores_unknown_run(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """`run_id` không có dòng nào và `upload_id` lệch: GD1 dừng im, không thông điệp nào."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)

    missing = PipelineStartPayload(run_id="run_00000000000000000000000000", upload_id=upload.id)
    await run_pipeline_start(missing, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)
    other = PipelineStartPayload(run_id=run.id, upload_id="upl_00000000000000000000000000")
    await run_pipeline_start(other, sessionmaker=db_sessionmaker, storage=local_storage, clock=fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    async with db_sessionmaker() as db:
        assert await _drawings(db, floor.pk) == []


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__fail_marks_preprocess_failed(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """`on_failed` khi lượt còn ở `preprocess` → bước `failed` mang đúng mã lỗi."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)

    await fail_pipeline_start_core(payload, "TASK_TIMEOUT", sessionmaker=db_sessionmaker, clock=fake_clock)

    async with db_sessionmaker() as db:
        row = await _run_row(db, run.id)
    assert row.status == "failed"
    assert row.error_code == "TASK_TIMEOUT"


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__fail_skips_run_past_preprocess(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """Lượt đã sang bước ML (J05): `on_failed` của một lượt giao cũ **không** được ghi `failed`."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    await _start(db_sessionmaker, local_storage, run, fake_clock)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)

    await fail_pipeline_start_core(payload, "TASK_TIMEOUT", sessionmaker=db_sessionmaker, clock=fake_clock)

    async with db_sessionmaker() as db:
        row = await _run_row(db, run.id)
    assert row.current_step == "wallSegmentation"
    assert row.status != "failed"


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__resumes_run_already_running(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """Lượt đã `running` ở `preprocess` (thử lại sau khi worker chết): GD1 đi tiếp, không ghi lại bước."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(update(PipelineRunRow).where(PipelineRunRow.id == run.id).values(status="running"))
        await db.commit()
    ml_queue.delete(ML_QUEUE)

    await _start(db_sessionmaker, local_storage, run, fake_clock)

    assert len(queued_payloads(ml_queue, ML_QUEUE)) == 3
    async with db_sessionmaker() as db:
        assert len(await _drawings(db, floor.pk)) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__drops_page_when_pins_vanish(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
    tmp_path: Path,
) -> None:
    """Dòng ghim biến mất giữa việc chậm (lượt bị xoá CASCADE): GD2 rollback và xoá trang mới."""
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)

    async def drop_pins() -> None:
        """Xoá dòng `pipeline_run_models` của lượt trong một giao dịch khác."""
        async with db_sessionmaker() as db:
            await db.execute(delete(PipelineRunModelsRow).where(PipelineRunModelsRow.run_id == run.id))
            await db.commit()

    ml_queue.delete(ML_QUEUE)
    await _start(db_sessionmaker, HookedStorage(local_storage, drop_pins), run, fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    assert _new_pages(tmp_path) == []


@pytest.mark.asyncio(loop_scope="function")
async def test_start_concurrent_delivery_deletes_loser_page(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
    tmp_path: Path,
) -> None:
    """J06 song song: hai lượt giao cùng `run_id` chồng việc chậm, bên commit sau bị từ chối.

    Bên thua vẫn đã ghi một trang mới, nên GD2 của nó phải `delete` trang ấy: kho chỉ còn
    đúng một trang mới (của bên thắng), một dòng `drawings` và ba thông điệp `ml.infer`.
    """
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    ml_queue.delete(ML_QUEUE)

    reached, release = asyncio.Event(), asyncio.Event()
    gated = GatedStorage(local_storage, reached, release)
    loser = asyncio.create_task(_start(db_sessionmaker, gated, run, fake_clock))
    await asyncio.wait_for(reached.wait(), timeout=30)
    await _start(db_sessionmaker, local_storage, run, fake_clock)
    release.set()
    await loser

    assert len(queued_payloads(ml_queue, ML_QUEUE)) == 3
    assert len(_new_pages(tmp_path)) == 1
    async with db_sessionmaker() as db:
        assert len(await _drawings(db, floor.pk)) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_orchestrate_pipeline_start__abandons_run_on_deleted_project(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    local_storage: LocalDiskStorage,
    fake_clock: FakeClock,
    ml_queue: SyncRedis,
) -> None:
    """Dự án xoá mềm trước khi giao: `record_step(running)` bỏ lượt (`FLOOR_DELETED`) nên GD1 dừng.

    `lock_run` lần hai trả `None` — đúng nhánh "`None` → commit, dừng" của [6] bước 1.
    """
    async with db_sessionmaker() as db:
        project, floor = await _scene(db)
        upload = await _pdf_upload(db, local_storage, project, floor)
        await db.commit()
    run = await _open_run(db_sessionmaker, upload.id, fake_clock)
    async with db_sessionmaker() as db:
        await db.execute(update(Project).where(Project.id == project.id).values(deleted_at=fake_clock.now()))
        await db.commit()
    ml_queue.delete(ML_QUEUE)

    await _start(db_sessionmaker, local_storage, run, fake_clock)

    assert queued_payloads(ml_queue, ML_QUEUE) == []
    async with db_sessionmaker() as db:
        assert await _drawings(db, floor.pk) == []
        assert (await _run_row(db, run.id)).status == "failed"
