"""Luật của `step_done` theo [8] "Test đặt tên theo việc" (B5-06c việc A).

Bốn nhóm: **Không tin kết quả** (kết quả của `apps/ml` và B5-05 luôn bị kiểm lại dưới khoá),
**Bước hỏng**, **Cô lập** (hai tầng, lượt bị thay), **Đếm theo bước**, cộng `fail_pipeline_step_done`.
Dịch vụ thật (K23): Postgres, Redis, kho đĩa `local_storage`; mọi khẳng định đọc lại từ DB.
"""

from typing import Final

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import start_run
from apps.worker.pipeline_build.artifacts import input_key, layer_key
from apps.worker.pipeline_orchestrate.pins import load_pins, set_step_requeue
from apps.worker.pipeline_steps.errors import MODEL_PIN_MISMATCH, PIPELINE_RESULT_INVALID
from apps.worker.pipeline_steps.step_done import BUILD_STEP, fail_pipeline_step_done_core, run_pipeline_step_done
from apps.worker.pipeline_steps.tests import helpers
from apps.worker.pipeline_steps.tests.helpers import (
    CPU_QUEUE,
    Arranged,
    deliver_ml,
    open_run_at_ml,
    put_ml_artifacts,
    run_row,
    step_result,
)
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.hooks import after_commit_idle
from packages.db.models.pipeline_orchestrate import PipelineRunModelsRow
from packages.messaging.redis import SyncRedis
from packages.ml_contracts.families import FAMILY_STEP, ModelFamily
from packages.ml_contracts.payloads import ModelRef
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.pipeline_orchestrate import classic_ref, make_run_pins
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

type Maker = async_sessionmaker[AsyncSession]

WALLS: Final[ModelFamily] = "wallSegmentation"
OBJECTS: Final[ModelFamily] = "openingAndFurnitureDetection"
TEXTS: Final[ModelFamily] = "dimensionReading"
WALLS_STEP: Final = FAMILY_STEP[WALLS]
TEXTS_STEP: Final = FAMILY_STEP[TEXTS]

cpu_queue = helpers.cpu_queue
"""Fixture hàng `pipeline.cpu` của `helpers`, gán lại để pytest thấy nó trong module này (R-02)."""


async def repin(maker: Maker, run_id: str, family: ModelFamily, ref: ModelRef) -> None:
    """Ghim lại ba họ, đổi riêng `family` thành `ref` (`pin_models` giữ bản đầu nên phải xoá dòng).

    Chỉ test dùng: lượt thật luôn ghim đúng một lần ở `run_pipeline_start`.
    """
    models = {other: classic_ref(other) for other in (WALLS, OBJECTS, TEXTS)}
    models[family] = ref
    async with maker() as db:
        await db.execute(delete(PipelineRunModelsRow).where(PipelineRunModelsRow.run_id == run_id))
        await make_run_pins(db, run_id=run_id, models=models)
        await db.commit()


def storage_ref(family: ModelFamily) -> ModelRef:
    """`ModelRef` dạng storage (có `version_id`) để kiểm nhánh so `model_version_id`."""
    version = new_id("mdl", SystemClock())
    return ModelRef(
        version_id=version,
        family=family,
        weights_key=f"ml/models/{version}/model.onnx",
        pinned_name=None,
        checksum_sha256="a" * 64,
    )


async def deliver(maker: Maker, arranged: Arranged, step: str, clock: FakeClock, **kw: object) -> None:
    """Một lượt giao `step_done` với payload tuỳ ý (không ghi artifact trước)."""
    await run_pipeline_step_done(step_result(arranged, step, **kw), sessionmaker=maker, clock=clock)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_rejects_model_version_mismatch(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`model_version_id` dạng `mdl_` khác bản ghim (cổ điển) → `failed` `MODEL_PIN_MISMATCH`."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    keys = await put_ml_artifacts(local_storage, arranged, WALLS)

    await deliver(
        db_sessionmaker,
        arranged,
        WALLS_STEP,
        fake_clock,
        artifact_keys=keys,
        model_version_id=new_id("mdl", SystemClock()),
    )

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", MODEL_PIN_MISMATCH, WALLS_STEP)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_accepts_absent_model_version(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`model_version_id=None` cho bản ghim **có** id → nhận; `used` ghi id bản ghim."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    ref = storage_ref(WALLS)
    await repin(db_sessionmaker, arranged.run_id, WALLS, ref)

    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert pins.used == {WALLS: ref.version_id}


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_rejects_key_outside_run_prefix(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Một khoá nằm ngoài `f"{run_prefix}{step}/"` → `failed` `PIPELINE_RESULT_INVALID`."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    keys = await put_ml_artifacts(local_storage, arranged, WALLS)
    stranger = (*keys, f"{arranged.run_prefix}zz_other/walls.json")

    await deliver(db_sessionmaker, arranged, WALLS_STEP, fake_clock, artifact_keys=tuple(sorted(stranger)))

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code) == ("failed", PIPELINE_RESULT_INVALID)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_rejects_missing_input_artifact(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Thiếu `walls.json` (chỉ báo `walls.png`) → `failed` `PIPELINE_RESULT_INVALID`."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    mask_only = (f"{arranged.run_prefix}{WALLS_STEP}/walls.png",)

    await deliver(db_sessionmaker, arranged, WALLS_STEP, fake_clock, artifact_keys=mask_only)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code) == ("failed", PIPELINE_RESULT_INVALID)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_rewrites_malformed_error_code(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`error_code:"sai mã"` (dựng bằng `model_construct`) → lõi ghi `PIPELINE_RESULT_INVALID`.

    Lệch khỏi prompt có chủ đích: `StepResultPayload.error_code` đã có `pattern`, nên mã xấu
    không qua nổi `model_validate` — nhánh phòng thủ của lõi chỉ kiểm được qua `model_construct`.
    """
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)

    await deliver(db_sessionmaker, arranged, WALLS_STEP, fake_clock, status="failed", error_code="sai mã")

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code) == ("failed", PIPELINE_RESULT_INVALID)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_rejects_layer_of_another_run(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`layer.json` của **lượt khác** → `spatialDataBuild` `failed` `PIPELINE_RESULT_INVALID`."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    for family in (WALLS, OBJECTS, TEXTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)
    alien = layer_key(arranged.run_prefix.replace(arranged.run_id, new_id("run", SystemClock())))

    await deliver(db_sessionmaker, arranged, BUILD_STEP, fake_clock, artifact_keys=(alien,))

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", PIPELINE_RESULT_INVALID, BUILD_STEP)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_ignores_result_of_superseded_run(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Lượt A bị lượt B thay (cùng tầng) → kết quả A bị bỏ, B vẫn ở bước ML của mình ("Cô lập")."""
    first = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    async with db_sessionmaker() as db:
        second = await start_run(db, upload_id=first.upload_id, clock=fake_clock)
        await make_run_pins(db, run_id=second.id, used={WALLS: "classic"})
        await db.commit()
    await after_commit_idle(db)

    await deliver_ml(db_sessionmaker, local_storage, first, WALLS, fake_clock)

    async with db_sessionmaker() as db:
        pins_a = await load_pins(db, first.run_id)
        pins_b = await load_pins(db, second.id)
    assert pins_a is not None
    assert pins_a.used == {}
    assert pins_b is not None
    assert pins_b.used == {WALLS: "classic"}
    row = await run_row(db_sessionmaker, first.run_id)
    assert (row.status, row.superseded_by) == ("failed", second.id)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_ignores_late_failure_after_family_used(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`failed` cũ tới **sau** khi họ đã có trong `used` → DB không đổi (giao lặp, J06)."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)
    before = await run_row(db_sessionmaker, arranged.run_id)
    snapshot = (before.status, before.current_step, before.progress_percent, before.error_code)

    await deliver(db_sessionmaker, arranged, WALLS_STEP, fake_clock, status="failed", error_code="OCR_FAILED")

    after = await run_row(db_sessionmaker, arranged.run_id)
    assert (after.status, after.current_step, after.progress_percent, after.error_code) == snapshot


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_fails_run_on_ml_step_failure(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`dimensionReading failed OCR_FAILED` khi tường còn chạy → lượt `failed`, không `ended_at`.

    Kết quả tường tới sau bị bỏ: `lock_run` từ chối lượt đã kết thúc, nên `used` vẫn rỗng.
    """
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)

    await deliver(db_sessionmaker, arranged, TEXTS_STEP, fake_clock, status="failed", error_code="OCR_FAILED")
    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", "OCR_FAILED", TEXTS_STEP)
    assert row.ended_at is None
    assert pins is not None
    assert pins.used == {}


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_keeps_build_failure_code(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`spatialDataBuild failed PIPELINE_BUILD_INVALID` → lượt `failed` **cùng** mã của B5-05."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    for family in (WALLS, OBJECTS, TEXTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)

    code = "PIPELINE_BUILD_INVALID"
    await deliver(db_sessionmaker, arranged, BUILD_STEP, fake_clock, status="failed", error_code=code)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", code, BUILD_STEP)


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_marks_inactive_non_wall_family_none(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Họ chưa kích hoạt **không phải** tường → `used` ghi `"none"` (tường ghi `"classic"`)."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    # Sổ model của DB test có bản kích hoạt cho `dimensionReading`; ghim lại cổ điển để kiểm `"none"`.
    await repin(db_sessionmaker, arranged.run_id, TEXTS, classic_ref(TEXTS))

    for family in (WALLS, TEXTS):
        await deliver_ml(db_sessionmaker, local_storage, arranged, family, fake_clock)

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert pins.used == {WALLS: "classic", TEXTS: "none"}


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_isolates_two_floors_of_one_project(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Tầng 1 hỏng không chặn tầng 2: tầng 2 vẫn tới `spatialDataBuild` và gửi `pipeline.build.run`.

    Hai lượt dựng riêng (mỗi `open_run_at_ml` một sân khấu) — đủ cho bất biến cần kiểm là lõi
    không bao giờ đọc/ghi lượt nào ngoài `payload.run_id`.
    """
    broken = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    healthy = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)

    await deliver(db_sessionmaker, broken, TEXTS_STEP, fake_clock, status="failed", error_code="OCR_FAILED")
    for family in (WALLS, OBJECTS, TEXTS):
        await deliver_ml(db_sessionmaker, local_storage, healthy, family, fake_clock)

    assert (await run_row(db_sessionmaker, broken.run_id)).status == "failed"
    good = await run_row(db_sessionmaker, healthy.run_id)
    assert (good.status, good.current_step, good.progress_percent) == ("running", BUILD_STEP, 70)
    assert [m["run_id"] for m in queued_payloads(cpu_queue, CPU_QUEUE)] == [healthy.run_id]


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_resets_requeue_count_when_step_advances(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Đẩy được bước → `step_requeue_count` về 0 ("Đếm theo bước")."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    async with db_sessionmaker() as db:
        await set_step_requeue(db, run_id=arranged.run_id, count=2)
        await db.commit()

    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert pins.step_requeue_count == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_step_done_keeps_requeue_count_when_step_stays(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Kết quả **không** đẩy bước (`dimensionReading` về trước) → số đếm giữ nguyên 2."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    async with db_sessionmaker() as db:
        await set_step_requeue(db, run_id=arranged.run_id, count=2)
        await db.commit()

    await deliver_ml(db_sessionmaker, local_storage, arranged, TEXTS, fake_clock)

    async with db_sessionmaker() as db:
        pins = await load_pins(db, arranged.run_id)
    assert pins is not None
    assert pins.step_requeue_count == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_fail_pipeline_step_done_records_failure(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """`on_failed` của task: lượt còn sống, họ chưa có trong `used` → `failed` kèm mã của B0-05."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    payload = step_result(arranged, WALLS_STEP, artifact_keys=(input_key(arranged.run_prefix, WALLS),))

    await fail_pipeline_step_done_core(payload, "RETRY_EXHAUSTED", sessionmaker=db_sessionmaker, clock=fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("failed", "RETRY_EXHAUSTED", WALLS_STEP)


@pytest.mark.asyncio(loop_scope="function")
async def test_fail_pipeline_step_done_ignores_missing_run(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Lượt đã kết thúc → `on_failed` không ghi gì (mã của lượt trước được giữ nguyên)."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    await deliver(db_sessionmaker, arranged, TEXTS_STEP, fake_clock, status="failed", error_code="OCR_FAILED")
    payload = step_result(arranged, WALLS_STEP, artifact_keys=(input_key(arranged.run_prefix, WALLS),))

    await fail_pipeline_step_done_core(payload, "RETRY_EXHAUSTED", sessionmaker=db_sessionmaker, clock=fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code) == ("failed", "OCR_FAILED")


@pytest.mark.asyncio(loop_scope="function")
async def test_fail_pipeline_step_done_ignores_used_family(
    db_sessionmaker: Maker, local_storage: LocalDiskStorage, fake_clock: FakeClock, cpu_queue: SyncRedis
) -> None:
    """Họ đã có trong `used` (kết quả thật đã tới) → `on_failed` của lượt giao cũ không đánh hỏng lượt."""
    arranged = await open_run_at_ml(db_sessionmaker, local_storage, fake_clock, cpu_queue)
    await deliver_ml(db_sessionmaker, local_storage, arranged, WALLS, fake_clock)
    payload = step_result(arranged, WALLS_STEP, artifact_keys=(input_key(arranged.run_prefix, WALLS),))

    await fail_pipeline_step_done_core(payload, "RETRY_EXHAUSTED", sessionmaker=db_sessionmaker, clock=fake_clock)

    row = await run_row(db_sessionmaker, arranged.run_id)
    assert (row.status, row.error_code, row.current_step) == ("running", None, OBJECTS)
