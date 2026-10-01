"""Dựng sân khấu dùng chung cho test B5-06c: một lượt chạy thật đang ở bước ML ([8] "Cách dựng").

Dịch vụ thật (K23): Postgres, Redis, kho đĩa `local_storage`. Lượt chạy mở bằng đúng đường
sản xuất (`start_run` → lõi `run_pipeline_start` của B5-06a) thay vì `INSERT` tay, nên bản vẽ,
dòng ghim và tiền tố artifact đều đúng hình dạng mà lõi `step_done` sẽ kiểm lại dưới khoá.
"""

from dataclasses import dataclass
from typing import Any, Final, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import start_run
from apps.api.drawings.tests._helpers import make_scene
from apps.worker.pipeline_build.artifacts import input_key
from apps.worker.pipeline_orchestrate.keys import run_prefix
from apps.worker.pipeline_orchestrate.start import run_pipeline_start
from apps.worker.pipeline_steps.step_done import run_pipeline_step_done
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import DrawingRow, PipelineRunRow
from packages.messaging.payloads.drawings import PipelineStartPayload
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.messaging.streams import EventBus, upload_stream
from packages.ml_contracts.artifacts import (
    ObjectsResult,
    TextResult,
    WallsResult,
    objects_to_json,
    text_to_json,
    walls_to_json,
)
from packages.ml_contracts.families import FAMILY_STEP, ModelFamily
from packages.ml_contracts.payloads import StepResultPayload
from packages.ml_contracts.synthetic import render_plan
from packages.storage.port import ObjectStorage
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.fixtures.clock import FakeClock

type Maker = async_sessionmaker[AsyncSession]

ML_QUEUE: Final = "ml.infer"
CPU_QUEUE: Final = "pipeline.cpu"
PLAN_SEED: Final = 7
"""Seed trang tổng hợp; cố định để khổ trang (và `width_px` của `BuildStepPayload`) tất định."""

_ARTIFACT_BODY: Final = {
    "wallSegmentation": lambda: walls_to_json(WallsResult(walls=())),
    "openingAndFurnitureDetection": lambda: objects_to_json(ObjectsResult(detections=())),
    "dimensionReading": lambda: text_to_json(TextResult(items=())),
}
"""Thân JSON **rỗng nhưng hợp hợp đồng** của từng họ; `step_done` chỉ so khoá, không đọc nội dung."""


@dataclass(frozen=True, slots=True)
class Arranged:
    """Mọi id mà test cần sau khi lượt chạy đã vào bước ML; đông cứng để không test nào sửa."""

    run_id: str
    upload_id: str
    floor_pk: int
    project_id: str
    level_id: str
    run_prefix: str
    page_key: str
    width_px: int
    height_px: int


async def open_run_at_ml(maker: Maker, storage: ObjectStorage, clock: FakeClock, broker_client: SyncRedis) -> Arranged:
    """Lượt `running` ở `wallSegmentation`, ba họ đã ghim, `used` rỗng, hàng `ml.infer` đã xoá.

    Xoá hàng ở cuối là phần quan trọng: `run_pipeline_start` gửi ba `ml.infer.*`, mà mọi test
    sau đó đếm thông điệp của **mình** bằng `LLEN`/`LRANGE` trên hàng dùng chung cả phiên.
    """
    plan = render_plan(PLAN_SEED, width_px=800, height_px=600)
    async with maker() as db:
        scene = await make_scene(db)
        upload = await make_complete_upload(
            db, storage, project=scene.project, floor=scene.floor, data=plan.image_png, file_name="plan.png"
        )
        await db.commit()
    async with maker() as db:
        run = await start_run(db, upload_id=upload.id, clock=clock)
        await db.commit()
    await after_commit_idle(db)
    payload = PipelineStartPayload(run_id=run.id, upload_id=run.upload_id)
    await run_pipeline_start(payload, sessionmaker=maker, storage=storage, clock=clock)
    broker_client.delete(ML_QUEUE, CPU_QUEUE)
    async with maker() as db:
        drawing = (await db.execute(select(DrawingRow).where(DrawingRow.floor_pk == scene.floor.pk))).scalar_one()
        return Arranged(
            run_id=run.id,
            upload_id=upload.id,
            floor_pk=scene.floor.pk,
            project_id=scene.project.id,
            level_id=scene.floor.level_id,
            run_prefix=run_prefix(
                project_id=scene.project.id,
                level_id=scene.floor.level_id,
                upload_id=upload.id,
                run_id=run.id,
            ),
            page_key=drawing.page_key,
            width_px=drawing.width_px,
            height_px=drawing.height_px,
        )


async def put_ml_artifacts(storage: ObjectStorage, arranged: Arranged, family: ModelFamily) -> tuple[str, ...]:
    """Ghi artifact JSON đầu vào của một bước ML vào kho, trả đúng `artifact_keys` của bước đó."""
    body = _ARTIFACT_BODY[family]()
    key = input_key(arranged.run_prefix, family)
    await storage.put(key, body, content_type="application/json", max_bytes=len(body))
    return (key,)


def step_result(arranged: Arranged, step: str, **kw: object) -> StepResultPayload:
    """`StepResultPayload` của một bước; `kw` sai hợp đồng (mã lỗi xấu) → `model_construct`.

    `model_construct` là lệch khỏi prompt có chủ đích: `error_code` đã có `pattern` nên payload
    sai mẫu không qua nổi `model_validate`, mà [8] vẫn đòi kiểm nhánh phòng thủ của lõi.
    """
    fields: dict[str, object] = {"run_id": arranged.run_id, "step": step, "duration_ms": 10, **kw}
    fields.setdefault("status", "completed")
    fields.setdefault("artifact_keys", ())
    try:
        return StepResultPayload.model_validate(fields)
    except ValueError:
        return StepResultPayload.model_construct(schema_version=1, **cast("Any", fields))


@pytest.fixture
def cpu_queue(messaging_env: None) -> SyncRedis:
    """Hàng `pipeline.cpu` dùng chung cả phiên; xoá trước khi đếm (BE-00 §12)."""
    client = broker_redis_sync()
    client.delete(CPU_QUEUE)
    return client


async def deliver_ml(
    maker: Maker, storage: ObjectStorage, arranged: Arranged, family: ModelFamily, clock: FakeClock
) -> None:
    """Một lượt giao `step_done` `completed` cho bước ML của `family`, artifact đã nằm trong kho."""
    keys = await put_ml_artifacts(storage, arranged, family)
    payload = step_result(arranged, FAMILY_STEP[family], artifact_keys=keys)
    await run_pipeline_step_done(payload, sessionmaker=maker, clock=clock)


async def steps_seen(bus: EventBus, upload_id: str, *, after: int) -> list[tuple[object, object, object]]:
    """Khung `Progress` mới kể từ sự kiện thứ `after`, dạng `(status, step, progressPercent)`."""
    events = await bus.read_after(upload_stream(upload_id), "0-0")
    return [(e.data["status"], e.data["step"], e.data["progressPercent"]) for e in events[after:]]


async def run_row(maker: Maker, run_id: str) -> PipelineRunRow:
    """Dòng `pipeline_runs` đọc lại trên session mới — trạng thái đã commit, không phải cache."""
    async with maker() as db:
        return (await db.execute(select(PipelineRunRow).where(PipelineRunRow.id == run_id))).scalar_one()
