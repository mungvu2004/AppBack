"""Dựng cảnh cho mọi test của `pipeline_persist` (B5-06b [8] "Cách dựng").

Mọi test của prompt cần đúng một cảnh: một lượt chạy đứng ở `spatialDataBuild` với bốn bước
trước đã `completed`, cộng một `layer.json` trong kho. Gom vào đây để việc A và việc B không
dựng hai cảnh lệch nhau; không có mock nào ở đây (K23), tất cả là dòng thật trong Postgres.
"""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from tempfile import mkdtemp
from typing import Final, Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_registry.registry import active_versions
from apps.api.drawings.runs import record_step, start_run
from apps.worker.pipeline_build.build import BuiltLayer
from apps.worker.pipeline_build.constants import DROPPED_KEYS
from apps.worker.pipeline_orchestrate.pins import pin_models
from apps.worker.pipeline_persist.constants import LAYER_ARTIFACT, STEP
from packages.core.clock import Clock
from packages.db.hooks import after_commit_idle
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.domain.spatial.model import SpatialLayer
from packages.messaging.payloads.pipeline import RunStepPayload
from packages.storage.keys import run_artifact
from packages.storage.local import LocalDiskStorage
from packages.storage.port import ObjectStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.factories.spatial import sample_floor_dimensions, sample_floor_layer

PAGE_BYTES: Final = b"%PDF-1.4 fake page for uploads"
"""Nội dung tệp gốc: `make_complete_upload` chỉ cần vài byte thật, không ai đọc lại nó ở đây."""

DONE_STEPS: Final = ("preprocess", "wallSegmentation", "openingAndFurnitureDetection", "dimensionReading")
"""Bốn bước trước `spatialDataBuild`; ghi `completed` lần lượt để lượt đứng đúng chỗ ([8])."""

_TEMP_BASE_URL: Final = "http://localhost/objects"
"""URL nền của kho tạm; không ai ký URL trong các test này nên giá trị chỉ cần hợp lệ."""


@dataclass(frozen=True, slots=True)
class Arranged:
    """Mọi id của cảnh đã dựng; `payload` là thông điệp mà task thật sẽ nhận.

    `floor_id` và `level_id` là cùng một chuỗi (`floors.level_id`): `floor_id` là tên nó mang
    trong khoá kho (`run_artifact(project, floor, …)`), `level_id` là tên nó mang trên dây.
    """

    run_id: str
    upload_id: str
    floor_pk: int
    project_id: str
    floor_id: str
    level_id: str
    floor_name: str
    uploader_id: str
    payload: RunStepPayload


async def _scene(db: AsyncSession) -> tuple[Project, FloorRow]:
    """Chủ dự án, dự án, một tầng — nền tối thiểu của cảnh."""
    owner = await make_user(db)
    project = await make_project(db, owner=owner)
    return project, await make_floor(db, project=project)


async def open_run_at_build(
    maker: async_sessionmaker[AsyncSession], clock: Clock, *, storage: ObjectStorage | None = None
) -> Arranged:
    """Dựng cảnh và commit: lượt chạy đứng ở `spatialDataBuild`, model đã ghim, chưa có lớp nào.

    `storage` chỉ nhận các khúc của tệp gốc — lõi không bao giờ đọc lại chúng — nên mặc định
    là một kho đĩa thật trên thư mục tạm, để người gọi không phải truyền kho vào chỗ vô nghĩa.
    """
    store = storage if storage is not None else LocalDiskStorage(Path(mkdtemp()), clock, _TEMP_BASE_URL)
    async with maker() as db:
        project, floor = await _scene(db)
        upload = await make_complete_upload(
            db, store, project=project, floor=floor, data=PAGE_BYTES, file_name="plan.pdf"
        )
        uploader_id = upload.created_by
        await db.commit()
    async with maker() as db:
        run = await start_run(db, upload_id=upload.id, clock=clock)
        await pin_models(db, run_id=run.id, models=await active_versions(db))
        await record_step(db, run_id=run.id, step="preprocess", status="running", clock=clock)
        for step in DONE_STEPS:
            await record_step(db, run_id=run.id, step=step, status="completed", clock=clock)
        await db.commit()
    await after_commit_idle(db)
    return Arranged(
        run_id=run.id,
        upload_id=upload.id,
        floor_pk=floor.pk,
        project_id=project.id,
        floor_id=floor.level_id,
        level_id=floor.level_id,
        floor_name=floor.name,
        uploader_id=uploader_id,
        payload=RunStepPayload(schema_version=1, run_id=run.id),
    )


_AI_FIELDS: Final = {"source": "ai", "reviewed": False}
"""`merge_pipeline_result` từ chối lớp AI có mục đã duyệt hay nguồn khác — ép cả bốn danh sách."""


def ai_layer(level_id: str, *, id_suffix: str = "AI") -> SpatialLayer:
    """Lớp mẫu của tầng 0 đã ép về đúng hình dạng đầu ra pipeline ([8] "Cách dựng").

    `sample_floor_layer` để phòng mẫu nguyên trạng (phòng do người vẽ), nên phải ép thêm ở
    đây; không sửa factory vì `packages/testing` là của prompt khác.
    """
    layer = sample_floor_layer(0, level_id=level_id, id_suffix=id_suffix)
    return SpatialLayer(
        walls=tuple(item.model_copy(update=_AI_FIELDS) for item in layer.walls),
        openings=tuple(item.model_copy(update=_AI_FIELDS) for item in layer.openings),
        rooms=tuple(item.model_copy(update=_AI_FIELDS) for item in layer.rooms),
        furniture=tuple(item.model_copy(update=_AI_FIELDS) for item in layer.furniture),
    )


def sample_built(
    level_id: str,
    *,
    scale: Decimal = Decimal("12"),
    scale_source: Literal["pipeline", "project_default"] = "pipeline",
) -> BuiltLayer:
    """Kết quả dựng mẫu của B5-05: lớp tầng 0 mang hậu tố `AI`, mọi mục chưa duyệt ([8])."""
    return BuiltLayer(
        layer=ai_layer(level_id),
        dimensions=sample_floor_dimensions(0, level_id=level_id, id_suffix="AI"),
        scale_mm_per_px=scale,
        scale_source=scale_source,
        dropped=dict.fromkeys(DROPPED_KEYS, 0),
    )


async def put_layer(storage: ObjectStorage, arranged: Arranged, data: bytes) -> None:
    """Ghi `layer.json` của lượt vào kho, đúng khoá mà lõi sẽ đọc lại."""
    key = run_artifact(
        arranged.project_id, arranged.floor_id, arranged.upload_id, arranged.run_id, STEP, LAYER_ARTIFACT
    )
    await storage.put(key, data, content_type="application/json", max_bytes=len(data))
