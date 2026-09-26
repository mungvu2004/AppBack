"""`apps.api.spatial_read.counts` trên Postgres thật (B3-02 [8]).

`layer_counts` kiểm trên toà mẫu A14 để con số ở đây là con số FE cũng thấy;
`recount_floor` kiểm bốn nhánh: lệch → ghi, khớp → không ghi, tầng xoá → `False`,
chưa có tài liệu → `(0, 0, None)`.
"""

from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.projects.summaries import set_layer_counts
from apps.api.spatial_read.counts import layer_counts, recount_floor
from apps.api.spatial_read.tests._helpers import make_scene
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary
from packages.domain.spatial import sample_layer
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

LEVEL_1_WALLS = 12
"""48 tường mẫu rải đều cho 4 tầng."""
LEVEL_1_AREA_M2 = Decimal("68.00")
"""Bốn phòng 4000 x 4250 mm của tầng 1 = 4 x 17,00 m² (A14: `areaM2` khai 27,6 không được tin)."""


async def _summary(db: AsyncSession, project_id: str, level_id: str) -> tuple[int, int, Decimal | None]:
    """Dòng đếm hiện tại của một tầng, dạng bộ ba để so thẳng với `LayerCounts`."""
    row = (
        await db.execute(
            select(
                ProjectFloorSummary.walls_total,
                ProjectFloorSummary.walls_reviewed,
                ProjectFloorSummary.area_m2,
            ).where(
                ProjectFloorSummary.project_id == project_id,
                ProjectFloorSummary.floor_level_id == level_id,
            )
        )
    ).one()
    return row.walls_total, row.walls_reviewed, row.area_m2


def test_layer_counts_on_sample_level_1() -> None:
    """Tầng 1 toà mẫu: 12 tường, chưa duyệt tường nào, 68,00 m² từ bốn đường bao thật."""
    counts = layer_counts(sample_layer(1))

    assert counts.walls_total == LEVEL_1_WALLS
    assert counts.walls_reviewed == 0
    assert counts.area_m2 == LEVEL_1_AREA_M2


def test_layer_counts_without_rooms_has_no_area() -> None:
    """Không phòng nào → `None`, **không** phải `0.00`: "chưa đo" khác "đo ra 0" (C17)."""
    layer = sample_layer(1)
    assert layer_counts(layer.model_copy(update={"rooms": ()})).area_m2 is None


def test_layer_counts_counts_reviewed_walls() -> None:
    """Chỉ tường `reviewed=True` vào cột thứ hai."""
    layer = sample_layer(1)
    reviewed = (layer.walls[0].model_copy(update={"reviewed": True, "source": "human"}), *layer.walls[1:])

    counts = layer_counts(layer.model_copy(update={"walls": reviewed}))

    assert (counts.walls_total, counts.walls_reviewed) == (LEVEL_1_WALLS, 1)


async def test_recount_floor_writes_when_summary_drifts(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bảng đếm về 0 trong khi tài liệu có tường → đối chiếu ghi lại đúng số."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(1, level_id=floor.level_id)
    await make_floor_document(db_session, floor_pk=floor.pk, layer=layer, clock=fake_clock)

    assert await recount_floor(db_session, floor_pk=floor.pk, clock=fake_clock) is True
    assert await _summary(db_session, scene.project.id, floor.level_id) == (
        LEVEL_1_WALLS,
        0,
        LEVEL_1_AREA_M2,
    )


async def test_recount_floor_is_idempotent(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt thứ hai thấy khớp → không ghi (`False`), nên hai lượt bằng một lượt."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session, floor_pk=floor.pk, layer=sample_floor_layer(1, level_id=floor.level_id), clock=fake_clock
    )
    await recount_floor(db_session, floor_pk=floor.pk, clock=fake_clock)

    assert await recount_floor(db_session, floor_pk=floor.pk, clock=fake_clock) is False


async def test_recount_floor_without_a_document_zeroes_the_summary(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng chưa có tài liệu đếm ra `(0, 0, None)` — số cũ của một tài liệu đã mất vẫn phải về 0."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await set_layer_counts(
        db_session,
        project_id=scene.project.id,
        floor_level_id=floor.level_id,
        walls_total=9,
        walls_reviewed=3,
        area_m2=Decimal("12.00"),
    )

    assert await recount_floor(db_session, floor_pk=floor.pk, clock=fake_clock) is True
    assert await _summary(db_session, scene.project.id, floor.level_id) == (0, 0, None)


async def test_recount_floor_skips_deleted_floor(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tầng đã xoá mềm → `False`, không đụng dòng đếm (đang giữ số cho lượt khôi phục)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session, floor_pk=floor.pk, layer=sample_floor_layer(1, level_id=floor.level_id), clock=fake_clock
    )
    await db_session.execute(update(FloorRow).where(FloorRow.pk == floor.pk).values(deleted_at=fake_clock.now()))

    assert await recount_floor(db_session, floor_pk=floor.pk, clock=fake_clock) is False
    assert await _summary(db_session, scene.project.id, floor.level_id) == (0, 0, None)


async def test_recount_floor_skips_unknown_floor(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tầng không còn dòng nào → `False`, không ném: lịch đối chiếu chạy sau lịch dọn."""
    await make_scene(db_session)
    assert await recount_floor(db_session, floor_pk=-1, clock=fake_clock) is False
