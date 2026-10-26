"""`remote_changes_since` và `human_removals` trên Postgres thật (B3-03 [8], H2 Phase 0).

Bốn bất biến của thân 409: một mục mỗi `(entity_id, field)` mang giá trị **mới nhất**,
thứ tự `(revision, id)`, cắt bớt thì bỏ mục cũ nhất, và trường bị gỡ ra `MISSING` chứ
không `None`. Bia mộ: chỉ xoá của người, xoá rồi ghi lại thì không còn, và sống qua gộp.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.changes import human_removals, remote_changes_since
from apps.api.spatial_write.jobs import run_change_log_compaction
from packages.core.errors import MISSING, SYSTEM_PIPELINE
from packages.db.models.floors import FloorRow
from packages.domain.rules_ai import Removed
from packages.domain.spatial import DELETED, FieldChange, Point, Segment, vertex_id
from packages.testing.factories.auth import make_user
from packages.testing.factories.spatial import make_change_rows, make_floor_document
from packages.testing.fixtures.clock import FakeClock

WALL = "W-WALL0000001"
ROOM = "R-ROOM0000001"


async def _floor_with_history(db: AsyncSession, clock: FakeClock) -> tuple[FloorRow, str]:
    """Một tầng có bốn bản ghi nhật ký: cùng trường đổi hai lần, một trường bị gỡ."""
    scene = await make_scene(db)
    floor = scene.floors[0]
    await make_floor_document(db, floor_pk=floor.pk, revision=4, clock=clock)
    writer = await make_user(db, name="Người ghi")
    for revision, changes in (
        (1, [FieldChange(WALL, "wall", "thickness_mm", 100)]),
        (2, [FieldChange(WALL, "wall", "thickness_mm", 200), FieldChange(ROOM, "room", "name", "Bếp")]),
        (3, [FieldChange(ROOM, "room", "__deleted__", MISSING)]),
        (4, [FieldChange(WALL, "wall", "height_mm", 2800)]),
    ):
        await make_change_rows(
            db,
            floor_pk=floor.pk,
            revision=revision,
            changes=changes,
            changed_by=writer.id,
            changed_by_name=writer.name,
            clock=clock,
        )
    return floor, writer.id


async def test_remote_changes_since_keeps_latest_value_per_field(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Một mục mỗi `(entity_id, field)`; `thickness_mm` giữ giá trị của bản ghi 2, không phải 1."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    changes = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=0, limit=50)

    assert [(change.entity_id, change.field, change.value) for change in changes] == [
        (WALL, "thickness_mm", 200),
        (ROOM, "name", "Bếp"),
        (ROOM, "__deleted__", MISSING),
        (WALL, "height_mm", 2800),
    ]


async def test_remote_changes_since_sorts_by_revision_then_id(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Sắp lại theo `(revision, id)` sau `DISTINCT ON`, không theo `(entity_id, field)`."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    changes = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=0, limit=50)

    assert [change.field for change in changes] == ["thickness_mm", "name", "__deleted__", "height_mm"]


async def test_remote_changes_since_truncates_to_newest(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`limit` giữ mục **mới nhất**: mục của bản ghi 2 bị bỏ trước mục của bản ghi 4."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    changes = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=0, limit=3)

    assert [change.field for change in changes] == ["name", "__deleted__", "height_mm"]


async def test_remote_changes_since_reports_removed_field_as_missing(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dòng `removed` ra `MISSING`; `RemoteFieldChange` cấm `None` nên đây là khác biệt thật."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    changes = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=0, limit=50)

    deleted = [change for change in changes if change.field == "__deleted__"]
    assert deleted[0].value is MISSING


async def test_remote_changes_since_returns_utc_instants(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`changed_at` có múi giờ và là UTC — cột là `timestamptz`, không phải giờ địa phương."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    changes = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=0, limit=50)

    assert all(change.changed_at.utcoffset() == UTC.utcoffset(None) for change in changes)
    assert changes[0].changed_at == fake_clock.now()


async def test_remote_changes_since_ignores_older_revisions(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`base_revision` là bản ghi người gọi đang cầm: chỉ mục **sau** nó mới là thay đổi của người khác."""
    floor, _ = await _floor_with_history(db_session, fake_clock)

    assert await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=4, limit=50) == ()
    later = await remote_changes_since(db_session, floor_pk=floor.pk, base_revision=3, limit=50)
    assert [change.field for change in later] == ["height_mm"]


_OUTLINE = ({"x": 0, "y": 0}, {"x": 4000, "y": 0}, {"x": 4000, "y": 3000}, {"x": 0, "y": 3000})


def _wall_created(start: tuple[int, int], end: tuple[int, int]) -> list[FieldChange]:
    """Mục nhật ký của tường mới như `diff_layers` ghi: một trường của tường rồi bốn mục đỉnh."""
    return [
        FieldChange(WALL, "wall", "thickness_mm", 100),
        FieldChange(vertex_id(WALL, "start"), "vertex", "x", start[0]),
        FieldChange(vertex_id(WALL, "start"), "vertex", "y", start[1]),
        FieldChange(vertex_id(WALL, "end"), "vertex", "x", end[0]),
        FieldChange(vertex_id(WALL, "end"), "vertex", "y", end[1]),
    ]


_ROOM_CREATED = [FieldChange(ROOM, "room", "name", "Bếp"), FieldChange(ROOM, "room", "outline", list(_OUTLINE))]
_DELETIONS = [
    FieldChange(WALL, "wall", DELETED, MISSING),
    FieldChange(vertex_id(WALL, "start"), "vertex", DELETED, MISSING),
    FieldChange(vertex_id(WALL, "end"), "vertex", DELETED, MISSING),
    FieldChange(ROOM, "room", DELETED, MISSING),
]


async def _floor_with_log(
    db: AsyncSession, clock: FakeClock, batches: Sequence[tuple[Sequence[FieldChange], bool]]
) -> int:
    """Một tầng có mỗi lượt ghi một bản ghi; cờ `True` = lượt của pipeline, `False` = của người."""
    scene = await make_scene(db)
    floor = scene.floors[0]
    await make_floor_document(db, floor_pk=floor.pk, revision=len(batches), clock=clock)
    person = await make_user(db, name="Người xoá")
    for revision, (changes, by_pipeline) in enumerate(batches, start=1):
        await make_change_rows(
            db,
            floor_pk=floor.pk,
            revision=revision,
            changes=changes,
            changed_by=SYSTEM_PIPELINE if by_pipeline else person.id,
            changed_by_name="Pipeline" if by_pipeline else person.name,
            clock=clock,
        )
    return floor.pk


_EXPECTED = Removed(
    walls=((WALL, Segment(start=Point(x=0, y=0), end=Point(x=5000, y=0))),),
    rooms=((ROOM, tuple(Point(x=p["x"], y=p["y"]) for p in _OUTLINE)),),
)


async def test_human_removals_lists_user_deleted_wall(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tường và phòng người xoá ra bia mộ, mang đường tâm và đường bao cuối cùng."""
    floor_pk = await _floor_with_log(
        db_session, fake_clock, [([*_wall_created((0, 0), (5000, 0)), *_ROOM_CREATED], True), (_DELETIONS, False)]
    )

    assert await human_removals(db_session, floor_pk=floor_pk) == _EXPECTED


async def test_human_removals_ignores_pipeline_deletions(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt pipeline xoá mục AI của chính nó không phải ý người dùng: không có bia mộ."""
    floor_pk = await _floor_with_log(
        db_session, fake_clock, [([*_wall_created((0, 0), (5000, 0)), *_ROOM_CREATED], True), (_DELETIONS, True)]
    )

    assert await human_removals(db_session, floor_pk=floor_pk) == Removed()


async def test_human_removals_ignores_restored_id(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Xoá rồi ghi lại đúng id (khôi phục phiên bản): dòng mới nhất không còn là `__deleted__`."""
    floor_pk = await _floor_with_log(
        db_session,
        fake_clock,
        [
            ([*_wall_created((0, 0), (5000, 0)), *_ROOM_CREATED], True),
            (_DELETIONS, False),
            ([*_wall_created((0, 0), (5000, 0)), *_ROOM_CREATED], False),
        ],
    )

    assert await human_removals(db_session, floor_pk=floor_pk) == Removed()


async def test_human_removals_survives_compaction(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Sau lịch gộp với mọi dòng ngoài cửa sổ, bia mộ còn nguyên và mang toạ độ đỉnh mới nhất.

    `spatial_log_compact_after_days` là số dương nên "cửa sổ 0 ngày" dựng bằng dòng ghi
    31 ngày trước và đồng hồ ở hiện tại: mọi dòng đều đủ tuổi để gộp.
    """
    now = datetime.now(UTC)
    fake_clock.set(now - timedelta(days=31))
    floor_pk = await _floor_with_log(
        db_session,
        fake_clock,
        [
            ([*_wall_created((0, 0), (4000, 0)), *_ROOM_CREATED], True),
            ([FieldChange(vertex_id(WALL, "end"), "vertex", "x", 5000)], False),
            (_DELETIONS, False),
        ],
    )
    await db_session.commit()
    fake_clock.set(now)

    deleted = await run_change_log_compaction(db_sessionmaker, fake_clock, batch=100)

    assert deleted == 1
    assert await human_removals(db_session, floor_pk=floor_pk) == _EXPECTED
