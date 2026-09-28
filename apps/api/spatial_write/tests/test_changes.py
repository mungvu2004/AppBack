"""`remote_changes_since` trên Postgres thật (B3-03 [8]).

Bốn bất biến của thân 409: một mục mỗi `(entity_id, field)` mang giá trị **mới nhất**,
thứ tự `(revision, id)`, cắt bớt thì bỏ mục cũ nhất, và trường bị gỡ ra `MISSING` chứ
không `None`.
"""

from datetime import UTC

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.tests._helpers import make_scene
from apps.api.spatial_write.changes import remote_changes_since
from packages.core.errors import MISSING
from packages.db.models.floors import FloorRow
from packages.domain.spatial import FieldChange
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
