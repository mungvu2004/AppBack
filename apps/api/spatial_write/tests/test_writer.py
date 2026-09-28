"""`write_layer` trên Postgres thật: đường ghi thường, kiểm lớp, nhật ký, bảng đếm (B3-03 [8]).

Mọi test gọi thẳng `write_layer` (việc R lo phần HTTP): những bất biến ở đây - thứ tự
kiểm, dấu chạm, `areaM2` dẫn xuất, bước 12 rollback trong SAVEPOINT - không nhìn thấy
được qua mã trạng thái.
"""

import unicodedata
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.summaries import project_rollups
from apps.api.spatial_read.tests._helpers import make_scene, other_session
from apps.api.spatial_write.errors import LAYER_INTEGRITY_BROKEN, LAYER_LEVEL_MISMATCH, REVIEW_BY_AI_FORBIDDEN
from apps.api.spatial_write.settings import get_spatial_write_settings, reset_spatial_write_settings_cache
from apps.api.spatial_write.tests._helpers import (
    OPENING_ID,
    WALL_ID,
    RecordingMerge,
    log_count,
    log_rows,
    make_dimension,
    make_room,
    make_wall,
    owned_ids,
    reread,
    simple_layer,
    write,
)
from apps.api.spatial_write.writer import LayerWrite, body_sha256, write_layer
from packages.core.errors import SYSTEM_PIPELINE, AppError
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.db.models.projects import ProjectFloorSummary
from packages.db.models.spatial import FloorEntityIdRow
from packages.domain.spatial import Opening, SpatialLayer
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.factories.spatial import make_floor_document
from packages.testing.fixtures.clock import FakeClock

ROOM_AREA_M2 = 17.0
"""Phòng mẫu 4000 x 4250 mm; `write_layer` luôn tính lại con số này từ đường bao (W18)."""


def _opening(level_id: str, *, wall_id: str = WALL_ID, entity_id: str = OPENING_ID) -> Opening:
    """Ô mở gắn vào một tường; dùng để dựng tham chiếu hỏng của test toàn vẹn."""
    return Opening.model_validate(
        {
            "id": entity_id,
            "wallId": wall_id,
            "kind": "door",
            "offsetMm": 100,
            "widthMm": 900,
            "heightMm": 2100,
            "sillHeightMm": 0,
            "swing": "left",
            "confidence": 0.8,
            "source": "ai",
            "reviewed": False,
        }
    )


async def test_spatial_write_layer_creates_first_revision(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Tầng chưa có tài liệu: `baseVersion 0` → bản ghi 1, và session khác đọc đúng lớp ấy."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    result = await write(
        db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id)
    )
    await db_session.commit()

    assert (result.revision, result.applied) == (1, True)
    async with other_session(db_sessionmaker) as session:
        assert (await reread(session, floor.pk)).layer == result.layer


async def test_spatial_write_layer_rejects_unknown_floor(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bước 1 khoá `floors`: tầng không có (hay đã xoá mềm) → 404 `resource:"floor"`."""
    with pytest.raises(AppError) as caught:
        await write_layer(
            db_session,
            floor_pk=10**9,
            base_revision=0,
            body=LayerWrite(layer=None, scale_mm_per_px=Decimal("10")),
            actor_id="usr_00000000000000000000000000",
            actor_name="Không ai",
            clock=fake_clock,
        )

    assert caught.value.code.status == 404
    assert caught.value.params["resource"] == "floor"


async def test_spatial_write_layer_rejects_merge_with_layer(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`merge` và `body.layer` cùng có là lỗi của người gọi Python, không phải của dây (K21)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(floor.level_id)

    with pytest.raises(ValueError, match="loại trừ nhau"):
        await write(
            db_session,
            floor=floor,
            actor=scene.owner,
            clock=fake_clock,
            layer=layer,
            merge=RecordingMerge(lambda base: base),
        )


async def test_spatial_write_layer_rejects_pipeline_layer_without_merge(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Pipeline không được đè thẳng lớp: mọi ghi của nó phải đi qua `merge` (K21)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    with pytest.raises(ValueError, match="pipeline"):
        await write_layer(
            db_session,
            floor_pk=floor.pk,
            base_revision=0,
            body=LayerWrite(layer=simple_layer(floor.level_id), scale_mm_per_px=None),
            actor_id=SYSTEM_PIPELINE,
            actor_name="Pipeline",
            clock=fake_clock,
        )


@pytest.mark.parametrize(
    ("overrides", "level_of_other_floor"),
    [({"reviewed": True, "source": "human"}, False), ({}, True)],
    ids=["dimension-da-duyet", "dimension-tang-khac"],
)
async def test_spatial_write_layer_rejects_foreign_dimensions(
    db_session: AsyncSession, fake_clock: FakeClock, overrides: dict[str, object], level_of_other_floor: bool
) -> None:
    """`body.dimensions` chỉ nhận mục AI chưa duyệt **của tầng đang ghi** ([2])."""
    scene = await make_scene(db_session, floors=2)
    floor, other = scene.floors
    level_id = other.level_id if level_of_other_floor else floor.level_id
    dimension = make_dimension(level_id).model_copy(update=overrides)

    with pytest.raises(ValueError, match="AI chưa duyệt"):
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, dimensions=(dimension,))


async def test_spatial_write_layer_rejects_ai_reviewed_entity(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """A5 kiểm **trước** mọi luật khác, và `field` trỏ đúng mục đầu tiên vi phạm."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(
        floor.level_id,
        walls=(make_wall(floor.level_id), make_wall(floor.level_id, entity_id="W-TESTWALL02", reviewed=True)),
    )

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert caught.value.code is REVIEW_BY_AI_FORBIDDEN
    assert caught.value.params["field"] == "body.layer.walls.1.reviewed"


async def test_spatial_write_layer_rejects_ai_reviewed_room(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """A5 quét đủ bốn danh sách, không chỉ `walls`; `field` mang tên danh sách thật."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(floor.level_id, rooms=(make_room(floor.level_id, reviewed=True),))

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert caught.value.params["field"] == "body.layer.rooms.0.reviewed"


async def test_spatial_write_layer_rejects_merge_result_reviewed_by_ai(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Lớp của `merge` chạy lại đúng bước 2: B3-06 cũng không được phép vi phạm A5."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    bad = simple_layer(floor.level_id, walls=(make_wall(floor.level_id, reviewed=True),))

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, merge=RecordingMerge(lambda _: bad))

    assert caught.value.code is REVIEW_BY_AI_FORBIDDEN


async def test_spatial_write_layer_rejects_other_level(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`levelId` của một mục khác tầng đang ghi → mã riêng, không phải `VALIDATION` chung."""
    scene = await make_scene(db_session, floors=2)
    floor, other = scene.floors
    layer = simple_layer(floor.level_id, walls=(make_wall(other.level_id),))

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert caught.value.code is LAYER_LEVEL_MISMATCH
    assert caught.value.params["field"] == "body.layer.walls.0.levelId"


@pytest.mark.parametrize(
    ("build", "count"),
    [
        (lambda level_id: SpatialLayer(walls=(), openings=(_opening(level_id),), rooms=(), furniture=()), 1),
        (
            lambda level_id: SpatialLayer(
                walls=(make_wall(level_id), make_wall(level_id)), openings=(), rooms=(), furniture=()
            ),
            1,
        ),
        (
            lambda level_id: SpatialLayer(
                walls=(make_wall(level_id).model_copy(update={"opening_ids": (OPENING_ID,)}),),
                openings=(),
                rooms=(),
                furniture=(),
            ),
            1,
        ),
    ],
    ids=["o-mo-tro-tuong-khong-co", "id-lap", "openingIds-tro-o-mo-khong-co"],
)
async def test_spatial_write_layer_rejects_broken_integrity(
    db_session: AsyncSession, fake_clock: FakeClock, build: Callable[[str], SpatialLayer], count: int
) -> None:
    """Toàn vẹn mức `critical` chặn ghi; `count` là số lỗi `critical`, không kể cảnh báo."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=build(floor.level_id))

    assert caught.value.code is LAYER_INTEGRITY_BROKEN
    assert caught.value.params["count"] == count


async def test_spatial_write_layer_accepts_warning_only_issues(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Cảnh báo (phòng trỏ tường không có) không chặn ghi - chỉ `critical` mới chặn."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    room = make_room(floor.level_id).model_copy(update={"wall_ids": ("W-TESTWALL09",)})

    result = await write(
        db_session,
        floor=floor,
        actor=scene.owner,
        clock=fake_clock,
        layer=simple_layer(floor.level_id, rooms=(room,)),
    )

    assert result.applied is True


async def test_spatial_write_layer_recomputes_room_area(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`areaM2` client gửi lên bị bỏ: diện tích luôn tính lại từ đường bao (W18)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(floor.level_id, rooms=(make_room(floor.level_id, area_m2=999.123),))

    result = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert result.layer.rooms[0].area_m2 == ROOM_AREA_M2
    assert (await reread(db_session, floor.pk)).layer.rooms[0].area_m2 == ROOM_AREA_M2


async def test_spatial_write_layer_logs_writer_name_at_write_time(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`changed_by` là `sub`, `changed_by_name` là tên **lúc ghi**: đổi tên sau không sửa lịch sử."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    actor_id, actor_name = scene.owner.id, scene.owner.name
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))
    await db_session.execute(update(User).where(User.id == actor_id).values(name="Tên mới"))
    rows = await log_rows(db_session, floor.pk)

    assert {row.changed_by for row in rows} == {actor_id}
    assert {row.changed_by_name for row in rows} == {actor_name}


async def test_spatial_write_layer_logs_deletions_without_value(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xoá một tường → dòng `__deleted__` của tường **và** của hai đỉnh, đều `value` NULL, `removed`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    two = simple_layer(
        floor.level_id, walls=(make_wall(floor.level_id), make_wall(floor.level_id, entity_id="W-TESTWALL02"))
    )
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=two)

    await write(
        db_session,
        floor=floor,
        actor=scene.owner,
        clock=fake_clock,
        base_revision=1,
        layer=simple_layer(floor.level_id),
    )

    deleted = [row for row in await log_rows(db_session, floor.pk) if row.field == "__deleted__"]
    assert [(row.entity_id, row.value, row.removed) for row in deleted] == [
        ("W-TESTWALL02", None, True),
        ("V-W-TESTWALL02-start", None, True),
        ("V-W-TESTWALL02-end", None, True),
    ]


async def test_spatial_write_layer_logs_touch_when_diff_is_empty(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Duyệt một tường AI chỉ đổi trường ngoài bảng diff → vẫn phải có đúng một dấu chạm."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))
    approved = simple_layer(floor.level_id, walls=(make_wall(floor.level_id, source="human", reviewed=True),))

    result = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, base_revision=1, layer=approved)

    marks = [row for row in await log_rows(db_session, floor.pk) if row.revision == result.revision]
    assert [(row.entity_type, row.entity_id, row.field, row.value) for row in marks] == [
        ("wall", WALL_ID, "thickness_mm", 200)
    ]


async def test_spatial_write_layer_drops_dead_dimension_references(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Xoá tường mà kích thước trỏ tới → `referenceIds` bị gỡ và có dòng `dimension`/`reference_ids`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await write(
        db_session,
        floor=floor,
        actor=scene.owner,
        clock=fake_clock,
        layer=simple_layer(floor.level_id),
        dimensions=(make_dimension(floor.level_id, refs=(WALL_ID,)),),
    )

    result = await write(
        db_session,
        floor=floor,
        actor=scene.owner,
        clock=fake_clock,
        base_revision=1,
        layer=SpatialLayer(walls=(), openings=(), rooms=(), furniture=()),
    )

    assert (await reread(db_session, floor.pk)).dimensions[0].reference_ids == ()
    rows = [row for row in await log_rows(db_session, floor.pk) if row.revision == result.revision]
    assert ("dimension", "reference_ids", []) in [(row.entity_type, row.field, row.value) for row in rows]


async def test_spatial_write_layer_keeps_everything_when_nothing_changes(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bước 10: gửi lại đúng lớp đang có → cùng bản ghi, không dòng nhật ký, bảng đếm không đụng."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(floor.level_id)
    first = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)
    logged = await log_count(db_session, floor.pk)
    touched_at = (
        await db_session.execute(
            select(ProjectFloorSummary.updated_at).where(
                ProjectFloorSummary.project_id == scene.project.id,
                ProjectFloorSummary.floor_level_id == floor.level_id,
            )
        )
    ).scalar_one()
    fake_clock.advance(timedelta(minutes=5))

    again = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, base_revision=1, layer=layer)

    assert (again.revision, again.applied) == (first.revision, False)
    assert await log_count(db_session, floor.pk) == logged
    summary = (
        await db_session.execute(
            select(ProjectFloorSummary.updated_at).where(
                ProjectFloorSummary.project_id == scene.project.id,
                ProjectFloorSummary.floor_level_id == floor.level_id,
            )
        )
    ).scalar_one()
    assert summary == touched_at


async def test_spatial_write_layer_writes_counts_and_rollups(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Bảng đếm: tường tổng/đã duyệt, diện tích hai chữ số, và `project_rollups` thấy ngay sau commit."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(
        floor.level_id,
        walls=(
            make_wall(floor.level_id),
            make_wall(floor.level_id, entity_id="W-TESTWALL02", source="human", reviewed=True),
        ),
        rooms=(make_room(floor.level_id),),
    )

    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)
    await db_session.commit()

    async with other_session(db_sessionmaker) as session:
        row = (
            await session.execute(
                select(
                    ProjectFloorSummary.walls_total,
                    ProjectFloorSummary.walls_reviewed,
                    ProjectFloorSummary.area_m2,
                ).where(
                    ProjectFloorSummary.project_id == scene.project.id,
                    ProjectFloorSummary.floor_level_id == floor.level_id,
                )
            )
        ).one()
        assert (row.walls_total, row.walls_reviewed, row.area_m2) == (2, 1, Decimal("17.00"))
        rollups = await project_rollups(session, [scene.project.id])
        assert rollups[scene.project.id].area_m2 == Decimal("17.00")


async def test_spatial_write_layer_reports_no_area_without_rooms(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng không có phòng → `area_m2` là `None`, khác hẳn `0.00` (C17 của bảng đếm)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))

    area = (
        await db_session.execute(
            select(ProjectFloorSummary.area_m2).where(
                ProjectFloorSummary.project_id == scene.project.id,
                ProjectFloorSummary.floor_level_id == floor.level_id,
            )
        )
    ).scalar_one()
    assert area is None


async def test_spatial_write_layer_normalises_text_to_nfc(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tên phòng dạng NFD: tài liệu và `value` nhật ký đều NFC, và vân tay thân không đổi (C16)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    nfd = unicodedata.normalize("NFD", "Bếp")
    layer = simple_layer(floor.level_id, rooms=(make_room(floor.level_id, name=nfd),))

    result = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert result.layer.rooms[0].name == unicodedata.normalize("NFC", nfd)
    names = [row.value for row in await log_rows(db_session, floor.pk) if row.field == "name"]
    assert names == [unicodedata.normalize("NFC", nfd)]
    assert body_sha256(LayerWrite(layer=layer, scale_mm_per_px=None)) == body_sha256(
        LayerWrite(
            layer=simple_layer(floor.level_id, rooms=(make_room(floor.level_id, name="Bếp"),)), scale_mm_per_px=None
        )
    )


async def test_spatial_write_layer_rejects_id_owned_by_live_floor(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Id đã thuộc tầng khác trong cùng dự án → 422 kèm số id không nhận được (bước 12)."""
    scene = await make_scene(db_session, floors=2)
    floor, other = scene.floors
    await make_floor_document(db_session, floor_pk=other.pk, layer=simple_layer(other.level_id), clock=fake_clock)

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))

    assert caught.value.code is LAYER_INTEGRITY_BROKEN
    assert caught.value.params["count"] == 1


async def test_spatial_write_layer_rolls_back_failed_claim(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Người gọi bắt 422 rồi `commit`: SAVEPOINT đã gỡ cả `UPDATE`, nên bản ghi và id không đổi."""
    scene = await make_scene(db_session, floors=2)
    floor, other = scene.floors
    await make_floor_document(db_session, floor_pk=other.pk, layer=simple_layer(other.level_id), clock=fake_clock)
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, scale=Decimal("10"))
    before = await owned_ids(db_session, scene.project.id)

    with pytest.raises(AppError):
        await write(
            db_session,
            floor=floor,
            actor=scene.owner,
            clock=fake_clock,
            base_revision=1,
            layer=simple_layer(floor.level_id),
        )
    await db_session.commit()

    assert (await reread(db_session, floor.pk)).revision == 1
    assert await owned_ids(db_session, scene.project.id) == before


@pytest.mark.parametrize(
    ("minutes", "reclaimed"), [(5, False), (11, True)], ids=["trong-cua-so-khoi-phuc", "qua-cua-so-khoi-phuc"]
)
async def test_spatial_write_layer_respects_restore_window_of_deleted_floor(
    db_session: AsyncSession, fake_clock: FakeClock, minutes: int, reclaimed: bool
) -> None:
    """Tầng xoá mềm còn trong cửa sổ khôi phục (600 s) vẫn giữ id của nó; quá cửa sổ thì nhường."""
    scene = await make_scene(db_session, floors=2)
    floor, other = scene.floors
    await make_floor_document(db_session, floor_pk=other.pk, layer=simple_layer(other.level_id), clock=fake_clock)
    await db_session.execute(
        update(FloorRow).where(FloorRow.pk == other.pk).values(deleted_at=fake_clock.now() - timedelta(minutes=minutes))
    )

    if not reclaimed:
        with pytest.raises(AppError) as caught:
            await write(
                db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id)
            )
        assert caught.value.code is LAYER_INTEGRITY_BROKEN
        return

    result = await write(
        db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id)
    )
    assert result.applied is True
    owner = (
        await db_session.execute(select(FloorEntityIdRow.floor_pk).where(FloorEntityIdRow.entity_id == WALL_ID))
    ).scalar_one()
    assert owner == floor.pk


async def test_spatial_write_layer_allows_same_id_in_other_project(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Id chỉ duy nhất **trong một dự án** (W4): cùng id ở dự án khác không tranh chấp."""
    scene = await make_scene(db_session)
    other_owner = await make_user(db_session)
    other_project = await make_project(db_session, owner=other_owner)
    floor = scene.floors[0]
    await db_session.commit()
    other_floor = await make_floor(db_session, project=other_project)
    await make_floor_document(
        db_session, floor_pk=other_floor.pk, layer=simple_layer(other_floor.level_id), clock=fake_clock
    )

    result = await write(
        db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id)
    )

    assert result.applied is True


def test_spatial_write_settings_hold_the_limits_of_the_prompt() -> None:
    """Bốn hạn mức của [5]; `reset_…_cache` cho test đổi biến môi trường mà không rò sang test sau."""
    reset_spatial_write_settings_cache()
    settings = get_spatial_write_settings()

    assert (settings.spatial_write_attempts, settings.spatial_conflict_changes_max) == (3, 5000)
    assert (settings.spatial_log_compact_after_days, settings.spatial_log_compact_batch) == (30, 5000)
