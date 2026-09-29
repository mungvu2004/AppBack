"""Dựng tầng nguồn **thật** cho test task dựng dataset (B6-02 việc C, [8] "Task").

Một tầng "đạt" cần bốn thứ rời nhau trong DB: tài liệu có tỉ lệ người đặt, một lượt tải đã
`complete`, bản vẽ đang dùng, và **một** dòng `floor_change_log` của người ghi **sau** lúc ảnh
được tải ([6] bước 5, `drawing_after_review`). `approved_floor` dựng đủ bốn qua factory sẵn có
— không chèn thẳng SQL — nên test hỏng khi đường đọc thật đổi luật, đúng ý K23.

Lớp nhãn dựng tay (`wall_layer`) thay vì `sample_floor_layer`: mẫu A14 đặt tường ở toạ độ mm
bất kỳ, còn test cần biết **chắc** pixel nào là tâm tường trên trang 800 x 600.
"""

from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.errors import DATASET_EMPTY
from apps.api.admin_ml_datasets.versions import fail_version, finish_version, start_version
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.db.models.auth import User
from packages.db.models.drawings import DrawingRow, PipelineRunRow, UploadRow
from packages.db.models.floors import FloorRow
from packages.db.models.projects import Project
from packages.domain.spatial.diff import FieldChange
from packages.domain.spatial.model import (
    BoundingBox,
    Furniture,
    Opening,
    Point,
    Room,
    Segment,
    SpatialLayer,
    Wall,
)
from packages.messaging import safe_redis
from packages.storage.port import CHUNK_SIZE, Disposition, ObjectInfo, ObjectStorage, SignedUrl
from packages.storage.sniff import ImageKind
from packages.testing.factories.admin_ml_datasets import make_dataset
from packages.testing.factories.auth import make_user
from packages.testing.factories.drawings import make_complete_upload, make_drawing, png_bytes
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.factories.spatial import make_change_rows, make_floor_document
from packages.testing.fixtures.clock import FakeClock

WIDTH = 800
HEIGHT = 600
MM_PER_PX = Decimal("10")
"""10 mm/px: tường dài 1.000 mm dày 200 mm → vùng 120 x 20 px, vừa trong trang 800 x 600."""

WALL_START = (500, 1000)
WALL_END = (1500, 1000)
WALL_THICKNESS = 200
DOOR_OFFSET_MM = 400
DOOR_WIDTH_MM = 200
SEED_USER = "usr_seed"


def entity_ids_of(level_id: str) -> tuple[str, str, str, str]:
    """Id (tường, cửa, đồ, phòng) riêng cho một tầng, suy từ `level_id` của chính nó.

    `floor_entity_ids` có PK `(project_id, entity_id)`, nên hai tầng **cùng dự án** không được
    dùng chung id — id cố định sẽ làm mọi test nhiều tầng vỡ ở lượt `flush` thứ hai.
    """
    tail = level_id.split("-", 1)[1]
    return f"W-{tail}", f"D-{tail}", f"F-{tail}", f"R-{tail}"


LayerOf = Callable[[str], SpatialLayer]
"""Dựng lớp nhãn từ `level_id` thật của tầng — chỉ biết được sau khi tầng đã `flush`."""


@dataclass(frozen=True, slots=True)
class Floors:
    """Chủ dự án và dự án dùng chung của một test (`created_by` của mọi dòng)."""

    owner: User
    project: Project


def wall_layer(
    level_id: str,
    *,
    reviewed: bool = True,
    source: Literal["ai", "human"] = "human",
    walls: bool = True,
    furniture: bool = False,
) -> SpatialLayer:
    """Một tường ngang + cửa (+ đồ) dựng tay, mọi thực thể cùng `source`/`reviewed`.

    `walls=False` bỏ tường và cửa nhưng giữ phòng: tầng như thế **không** có nhãn của cả hai họ
    (`no_labels`) mà vẫn có thực thể để neo dòng nhật ký của người.
    """
    review = {"confidence": 1.0, "source": source, "reviewed": reviewed}
    wall_id, door_id, furniture_id, room_id = entity_ids_of(level_id)
    wall = Wall(
        id=wall_id,
        level_id=level_id,
        centreline=Segment(start=Point(x=WALL_START[0], y=WALL_START[1]), end=Point(x=WALL_END[0], y=WALL_END[1])),
        thickness_mm=WALL_THICKNESS,
        height_mm=2700,
        kind="loadBearing",
        opening_ids=(door_id,),
        **review,
    )
    opening = Opening(
        id=door_id,
        wall_id=wall_id,
        kind="door",
        offset_mm=DOOR_OFFSET_MM,
        width_mm=DOOR_WIDTH_MM,
        height_mm=2100,
        sill_height_mm=0,
        swing="left",
        **review,
    )
    item = Furniture(
        id=furniture_id,
        level_id=level_id,
        kind="table",
        centre=Point(x=3000, y=3000),
        bounding_box=BoundingBox(min=Point(x=2800, y=2800), max=Point(x=3200, y=3200)),
        rotation_deg=0.0,
        **review,
    )
    room = Room(
        id=room_id,
        level_id=level_id,
        name="Phòng mẫu",
        usage="livingRoom",
        outline=(Point(x=0, y=0), Point(x=4000, y=0), Point(x=4000, y=4000)),
        area_m2=16.0,
        wall_ids=(wall_id,) if walls else (),
        **review,
    )
    return SpatialLayer(
        walls=(wall,) if walls else (),
        openings=(opening,) if walls else (),
        rooms=(room,),
        furniture=(item,) if furniture else (),
    )


def ai_layer(level_id: str) -> SpatialLayer:
    """Lớp mà mọi nhãn do AI đặt và chưa ai duyệt (`labels_unapproved`)."""
    return wall_layer(level_id, reviewed=False, source="ai")


def rooms_only_layer(level_id: str) -> SpatialLayer:
    """Lớp chỉ có phòng — không nhãn của họ nào (`no_labels`)."""
    return wall_layer(level_id, walls=False)


def with_furniture_layer(level_id: str) -> SpatialLayer:
    """Lớp đủ ô mở và đồ đạc (họ cửa-đồ)."""
    return wall_layer(level_id, furniture=True)


async def make_scene(db: AsyncSession) -> Floors:
    """Chủ `admin` và một dự án của người đó."""
    owner = await make_user(db, role="admin")
    return Floors(owner=owner, project=await make_project(db, owner=owner))


async def other_project(db: AsyncSession, scene: Floors, *, name: str = "Dự án hai") -> Floors:
    """Dự án thứ hai của cùng chủ — M06 chia theo dự án nên đây là một **nhóm** khác."""
    return Floors(owner=scene.owner, project=await make_project(db, owner=scene.owner, name=name))


async def approved_floor(
    db: AsyncSession,
    storage: ObjectStorage,
    scene: Floors,
    clock: FakeClock,
    *,
    layer_of: LayerOf = wall_layer,
    scale: Decimal | None = MM_PER_PX,
    width: int = WIDTH,
    height: int = HEIGHT,
    page: bytes | None = None,
    drawing: bool = True,
    human_write: bool = True,
) -> FloorRow:
    """Một tầng có đủ điều kiện thành mẫu; mỗi tham số tắt đúng một điều kiện cho ca bỏ tầng.

    `drawing=False` → `no_drawing`; `scale=None` → `no_scale` (K19); `human_write=False` →
    `drawing_after_review`; `layer_of=ai_layer` → `labels_unapproved`.
    """
    floor = await make_floor(db, project=scene.project)
    await make_floor_document(
        db,
        floor_pk=floor.pk,
        layer=layer_of(floor.level_id),
        scale=scale,
        scale_source="human" if scale is not None else "none",
        clock=clock,
    )
    if not drawing:
        return floor
    png = page if page is not None else png_bytes(width, height)
    upload = await make_complete_upload(db, storage, project=scene.project, floor=floor, data=png, file_name="p.png")
    row = await make_drawing(db, storage, upload=upload, png=png)
    if human_write:
        await add_human_write(db, floor, scene, clock, at=row.uploaded_at + timedelta(seconds=1))
    return floor


async def add_human_write(
    db: AsyncSession, floor: FloorRow, scene: Floors, clock: FakeClock, *, at: datetime | None = None
) -> None:
    """Một dòng nhật ký của **người** (`usr_…`); `at` là mốc `changed_at` muốn ghi."""
    if at is not None:
        clock.set(at)
    await make_change_rows(
        db,
        floor_pk=floor.pk,
        revision=1,
        changes=[
            FieldChange(entity_id=entity_ids_of(floor.level_id)[0], entity_type="wall", field="thicknessMm", value=200)
        ],
        changed_by=scene.owner.id,
        changed_by_name=scene.owner.name,
        clock=clock,
    )


async def page_key_of(db: AsyncSession, floor: FloorRow) -> str:
    """Khoá object của trang đã nắn của bản vẽ đang dùng."""
    stmt = select(DrawingRow.page_key).where(DrawingRow.floor_pk == floor.pk)
    return (await db.execute(stmt)).scalar_one()


async def add_pending_run(db: AsyncSession, floor: FloorRow, clock: FakeClock) -> None:
    """Một lượt `pipeline_runs` còn `running` cho lượt tải của bản vẽ hiện tại (`pipeline_pending`)."""
    stmt = (
        select(UploadRow.id)
        .join(DrawingRow, DrawingRow.upload_id == UploadRow.id)
        .where(DrawingRow.floor_pk == floor.pk)
    )
    upload_id = (await db.execute(stmt)).scalar_one()
    now = clock.now()
    db.add(
        PipelineRunRow(
            id=f"run_{floor.pk:026d}",
            upload_id=upload_id,
            floor_pk=floor.pk,
            status="running",
            current_step="wallSegmentation",
            progress_percent=10,
            created_at=now,
            updated_at=now,
        )
    )
    await db.flush()


async def move_drawing_after_review(db: AsyncSession, floor: FloorRow, clock: FakeClock) -> None:
    """Đẩy `uploaded_at` của bản vẽ lên sau mọi dòng nhật ký — ảnh mới hơn lượt duyệt."""
    stmt = (
        update(DrawingRow).where(DrawingRow.floor_pk == floor.pk).values(uploaded_at=clock.now() + timedelta(hours=1))
    )
    await db.execute(stmt)
    await db.flush()


async def open_building_version(
    maker: async_sessionmaker[AsyncSession],
    clock: FakeClock,
    *,
    family: str = "wallSegmentation",
    project_ids: list[str] | None = None,
    dataset_id: str | None = None,
) -> str:
    """Một phiên bản `building` đã commit (kèm dataset mới nếu chưa truyền `dataset_id`).

    Đi qua `start_version` thật chứ không chèn dòng tay: `sequence`, khoá `FOR UPDATE` và unique
    partial `WHERE status='building'` do đó được test đúng như đường N31 dùng chúng.
    """
    async with maker() as db:
        if dataset_id is None:
            dataset_id = (await make_dataset(db, family=family, created_by=SEED_USER)).id
        row = await start_version(
            db,
            dataset_id=dataset_id,
            source="approvedFloors",
            project_ids=project_ids,
            created_by=SEED_USER,
            clock=clock,
        )
        assert row is not None
        version_id = row.id
        await db.commit()
    return version_id


async def read_version(maker: async_sessionmaker[AsyncSession], version_id: str) -> DatasetVersionRow:
    """Đọc lại một dòng phiên bản bằng session riêng (không dùng lại session đã ghi)."""
    async with maker() as db:
        stmt = select(DatasetVersionRow).where(DatasetVersionRow.id == version_id)
        return (await db.execute(stmt)).scalar_one()


class AtPutStorage:
    """Kho thật, nhưng ở lượt `put` thứ `at_put` làm thêm **một** việc rồi thôi.

    Không phải kho giả (K23): mọi phương thức uỷ thẳng cho kho thật, và lượt `put` sau lượt
    được đánh dấu cũng ghi thật. `error` để tiêm lỗi phụ thuộc (J02, J05); `hook` để đổi trạng
    thái hay xoá khoá Redis đúng lúc lượt dựng đang ở giữa (mất khoá, bản bị chốt hỏng).
    """

    def __init__(
        self,
        inner: ObjectStorage,
        *,
        at_put: int,
        error: BaseException | None = None,
        hook: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._inner = inner
        self._at_put = at_put
        self._error = error
        self._hook = hook
        self.puts = 0

    async def put(
        self, key: str, data: bytes | AsyncIterable[bytes], *, content_type: str, max_bytes: int
    ) -> ObjectInfo:
        """Đếm lượt `put`; tới lượt đã hẹn thì ném `error` hoặc chạy `hook` trước khi ghi."""
        self.puts += 1
        if self.puts == self._at_put:
            self._at_put = -1
            if self._error is not None:
                raise self._error
            if self._hook is not None:
                await self._hook()
        return await self._inner.put(key, data, content_type=content_type, max_bytes=max_bytes)

    async def stat(self, key: str) -> ObjectInfo | None:
        """Uỷ cho kho thật."""
        return await self._inner.stat(key)

    def open_read(self, key: str, *, chunk_size: int = CHUNK_SIZE) -> AsyncIterator[bytes]:
        """Uỷ cho kho thật."""
        return self._inner.open_read(key, chunk_size=chunk_size)

    async def delete(self, key: str) -> None:
        """Uỷ cho kho thật."""
        await self._inner.delete(key)

    async def delete_prefix(self, prefix: str) -> None:
        """Uỷ cho kho thật."""
        await self._inner.delete_prefix(prefix)

    def list_prefix(self, prefix: str, *, older_than: datetime | None = None) -> AsyncIterator[ObjectInfo]:
        """Uỷ cho kho thật."""
        return self._inner.list_prefix(prefix, older_than=older_than)

    async def signed_url(
        self,
        key: str,
        *,
        disposition: Disposition,
        filename: str | None = None,
        kind: ImageKind | None = None,
    ) -> SignedUrl:
        """Uỷ cho kho thật (lượt dựng không ký URL; có ở đây để đủ cổng `ObjectStorage`)."""
        return await self._inner.signed_url(key, disposition=disposition, filename=filename, kind=kind)


async def set_failed(maker: async_sessionmaker[AsyncSession], version_id: str, *, clock: FakeClock) -> None:
    """Chốt `failed` từ một session khác — giả một lịch quét chen vào giữa lượt dựng."""
    async with maker() as db:
        await fail_version(db, version_id=version_id, failure_code=DATASET_EMPTY, clock=clock)
        await db.commit()


async def steal_lock(version_id: str) -> None:
    """Xoá khoá dựng trong Redis: lượt `renew` kế tiếp của task trả `False` (mất khoá)."""
    await safe_redis().delete(f"lock:datasets:build:{version_id}")


async def set_ready(maker: async_sessionmaker[AsyncSession], version_id: str, *, clock: FakeClock) -> None:
    """Chốt `ready` từ một session khác — giả một lượt dựng song song về đích trước."""
    async with maker() as db:
        await finish_version(
            db,
            version_id=version_id,
            manifest_sha256="b" * 64,
            split_counts={"train": 1, "validation": 0, "test": 0},
            clock=clock,
        )
        await db.commit()
