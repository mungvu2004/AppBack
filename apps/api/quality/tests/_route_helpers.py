"""Sân khấu và tiện ích cho test route #30-#32 (việc R): ảnh **thật**, dữ liệu đã commit.

Route chạy trên session khác nên mọi thứ phải `commit` (K22). Khác `_helpers.py` của việc D
(PNG chỉ có IHDR+IEND), mỗi tầng ở đây có tệp gốc và trang đang dùng là ảnh giải mã được,
dựng bằng numpy từ `_images.py`; số đo lấy từ `assess` thật, ghi qua `save_assessment`.
"""

import asyncio
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Final

import httpx
import numpy as np
import pytest
from numpy.typing import NDArray
from redis import Redis as SyncRedis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.runs import reset_sync_bus_cache, start_run
from apps.api.projects.tests.test_routes_common import headers_of
from apps.api.quality.assessments import AssessmentRow
from apps.api.quality.processing import reset_processing_state
from apps.api.quality.settings import reset_quality_settings_cache
from apps.api.quality.tests._helpers import DrawnFloor, make_drawn_floor, measure_floor
from apps.api.quality.tests._images import desk_shot, png_bytes
from packages.core.clock import Clock
from packages.db.hooks import after_commit_idle
from packages.db.models.auth import User
from packages.db.models.drawings import PipelineRunRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.messaging import broker_redis_sync
from packages.messaging.settings import get_messaging_settings
from packages.storage.keys import upload_prefix
from packages.storage.port import ObjectInfo, ObjectStorage
from packages.testing.factories.auth import make_user
from packages.testing.factories.projects import make_project
from packages.testing.factories.spatial import make_floor_document
from packages.vision.preprocess import RgbImage
from packages.vision.quality import assess

CPU_QUEUE: Final = "pipeline.cpu"
SHOT_W, SHOT_H = 600, 420
"""Cỡ tờ giấy của `desk_shot` cho test route: nhỏ để mỗi lượt xử lý dưới nửa giây."""


def corners_path(project_id: str, level_id: str) -> str:
    """Đường #31."""
    return f"/api/projects/{project_id}/floors/{level_id}/quality/corners"


def straighten_path(project_id: str, level_id: str) -> str:
    """Đường #32."""
    return f"/api/projects/{project_id}/floors/{level_id}/quality/straighten"


def read_path(project_id: str, level_id: str) -> str:
    """Đường #30."""
    return f"/api/projects/{project_id}/floors/{level_id}/quality"


def corners_body(points: Sequence[Sequence[float]]) -> dict[str, Any]:
    """Thân #31 từ bốn cặp `(x, y)` tỉ lệ."""
    return {"corners": [{"xRatio": x, "yRatio": y} for x, y in points]}


FULL_PAGE: Final = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
"""Bốn góc toàn trang (theo chiều kim đồng hồ từ trên-trái)."""


@dataclass(frozen=True, slots=True)
class Stage:
    """Chủ dự án (engineer), một viewer cùng dự án và các tầng đã có bản vẽ thật."""

    owner: User
    viewer: User
    project: Project
    floors: list[DrawnFloor] = field(default_factory=list)

    @property
    def headers(self) -> dict[str, str]:
        """Header của chủ dự án."""
        return headers_of(self.owner)

    @property
    def viewer_headers(self) -> dict[str, str]:
        """Header của viewer (không có `floor.upload`)."""
        return headers_of(self.viewer)

    def level(self, index: int = 0) -> str:
        """`level_id` của tầng thứ `index`."""
        return self.floors[index].floor.level_id


async def make_image_floor(
    db: AsyncSession,
    storage: ObjectStorage,
    *,
    project: Project,
    pixels: NDArray[np.uint8],
    order: int | None = None,
    name: str | None = None,
    file_name: str = "ban-ve.png",
    original: bytes | None = None,
) -> DrawnFloor:
    """Tầng có bản vẽ đang dùng là ảnh `pixels` thật (tệp gốc cũng là ảnh đó, trừ khi có `original`)."""
    return await make_drawn_floor(
        db,
        storage,
        project=project,
        order=order,
        name=name,
        png=png_bytes(pixels),
        original=original,
        file_name=file_name,
    )


async def make_stage(
    db: AsyncSession, storage: ObjectStorage, *, floors: int = 1, pixels: NDArray[np.uint8] | None = None
) -> Stage:
    """Dự án có `floors` tầng, mỗi tầng một ảnh `desk_shot` (khung ngoài mép giấy → chưa tìm thấy khung)."""
    owner = await make_user(db)
    viewer = await make_user(db, role="viewer")
    project = await make_project(db, owner=owner, members=[viewer])
    stage = Stage(owner, viewer, project)
    pixels = desk_shot(SHOT_W, SHOT_H).pixels if pixels is None else pixels
    for index in range(floors):
        stage.floors.append(await make_image_floor(db, storage, project=project, pixels=pixels, order=index + 1))
    await db.commit()
    return stage


async def measure_real(
    db: AsyncSession,
    clock: Clock,
    drawn: DrawnFloor,
    pixels: NDArray[np.uint8],
    *,
    homography: Mapping[str, Any] | None = None,
) -> AssessmentRow:
    """Đo ảnh `pixels` bằng `assess` thật rồi ghi qua `save_assessment` (lượt `pending` mới), commit.

    `homography` mặc định là ma trận đơn vị của ảnh; test cố ý đưa homography lệch cỡ để thử 409.
    """
    height, width = pixels.shape[:2]
    _, saved = await measure_floor(
        db, clock, drawn, assess(RgbImage(pixels)), width_px=width, height_px=height, homography=homography
    )
    await db.commit()
    await after_commit_idle(db)
    return saved


async def run_count(sessionmaker: async_sessionmaker[AsyncSession], floor_pk: int) -> int:
    """Số dòng `pipeline_runs` của một tầng, đọc bằng session mới."""
    async with sessionmaker() as session:
        stmt = select(func.count()).select_from(PipelineRunRow).where(PipelineRunRow.floor_pk == floor_pk)
        return int((await session.execute(stmt)).scalar_one())


async def runs_of(sessionmaker: async_sessionmaker[AsyncSession], floor_pk: int) -> list[PipelineRunRow]:
    """Các lượt chạy của tầng, cũ trước mới sau."""
    async with sessionmaker() as session:
        stmt = (
            select(PipelineRunRow)
            .where(PipelineRunRow.floor_pk == floor_pk)
            .order_by(PipelineRunRow.created_at, PipelineRunRow.id)
        )
        return list((await session.execute(stmt)).scalars())


async def floor_of(sessionmaker: async_sessionmaker[AsyncSession], level_id: str) -> FloorRow:
    """Dòng tầng theo `level_id` (session mới)."""
    async with sessionmaker() as session:
        return (await session.execute(select(FloorRow).where(FloorRow.level_id == level_id))).scalar_one()


def floor_view(response: httpx.Response, level_id: str) -> dict[str, Any]:
    """Phần tử `floors` của response ứng với `level_id`."""
    (found,) = [item for item in response.json()["floors"] if item["floorId"] == level_id]
    return dict(found)


@pytest.fixture(autouse=True)
def quality_env() -> Iterator[None]:
    """Mỗi test bắt đầu với cấu hình chất lượng và hàng xử lý mới (executor, semaphore theo vòng)."""
    reset_sync_bus_cache()
    reset_quality_settings_cache()
    reset_processing_state()
    yield
    reset_processing_state()
    reset_quality_settings_cache()
    reset_sync_bus_cache()


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Client Redis của broker; hàng `pipeline.cpu` dọn trước và sau vì broker dùng chung cả phiên."""
    client = broker_redis_sync(get_messaging_settings())
    client.delete(CPU_QUEUE)
    yield client
    client.delete(CPU_QUEUE)
    client.close()


def tune(monkeypatch: pytest.MonkeyPatch, **values: str | int | float) -> None:
    """Đặt biến môi trường `QUALITY_*` (khoá viết thường) rồi nạp lại cấu hình và hàng xử lý."""
    for name, value in values.items():
        monkeypatch.setenv(name.upper(), str(value))
    reset_quality_settings_cache()
    reset_processing_state()


async def mark_reviewed(db: AsyncSession, clock: Clock, drawn: DrawnFloor) -> None:
    """Tầng có hình học người duyệt (tỉ lệ `human`) và lượt của upload bản vẽ `completed`, commit."""
    await make_floor_document(db, floor_pk=drawn.floor.pk, scale=Decimal("12.5"), scale_source="human", clock=clock)
    if await run_count_in(db, drawn.floor.pk) == 0:
        await start_run(db, upload_id=drawn.upload.id, clock=clock)
    await db.execute(
        update(PipelineRunRow).where(PipelineRunRow.upload_id == drawn.upload.id).values(status="completed")
    )
    await db.commit()
    await after_commit_idle(db)


async def run_count_in(db: AsyncSession, floor_pk: int) -> int:
    """Như `run_count` nhưng trên session đang có."""
    stmt = select(func.count()).select_from(PipelineRunRow).where(PipelineRunRow.floor_pk == floor_pk)
    return int((await db.execute(stmt)).scalar_one())


async def page_objects(storage: ObjectStorage, drawn: DrawnFloor) -> list[str]:
    """Khoá mọi object dưới `…/uploads/{upload}/pages/` — bằng chứng "không object mới / mồ côi"."""
    prefix = upload_prefix(drawn.project.id, drawn.floor.level_id, drawn.upload.id) + "pages/"
    return sorted([item.key async for item in storage.list_prefix(prefix)])


class HookedStorage:
    """Kho thật, nhưng `put` của trang mới (`…/pages/…`) dừng lại tới khi test mở cổng.

    Không phải mock: mọi lời gọi đi thẳng xuống kho thật (`__getattr__`), `put` cũng ghi thật;
    chỉ thêm một chỗ chờ đúng lúc request đã xử lý xong ảnh mà chưa mở giao dịch cuối. Đủ
    `parties` lượt `put` đang chờ thì `entered` bật; test làm việc rồi `release.set()`.
    """

    def __init__(self, inner: ObjectStorage, *, parties: int = 1) -> None:
        """Bọc `inner`; `parties` = số request phải cùng tới cổng trước khi `entered` bật."""
        self._inner = inner
        self._parties = parties
        self._waiting = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def put(self, key: str, data: bytes, *, content_type: str, max_bytes: int) -> ObjectInfo:
        """Khoá trang thì chờ cổng; rồi ghi thật."""
        if "/pages/" in key:
            self._waiting += 1
            if self._waiting >= self._parties:
                self.entered.set()
            await self.release.wait()
        return await self._inner.put(key, data, content_type=content_type, max_bytes=max_bytes)

    def __getattr__(self, name: str) -> Any:
        """Mọi phương thức khác đi thẳng xuống kho thật."""
        return getattr(self._inner, name)
