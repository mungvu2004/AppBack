"""CHECK và CASCADE của ba bảng `packages/db/models/spatial.py` trên Postgres thật (B3-02 [8]).

Kiểm ở tầng DB chứ không ở tầng Python: những ràng buộc này là tầng phòng thủ **cuối** —
chúng phải đứng vững cả khi một lượt ghi tương lai quên kiểm ở tầng trên.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.spatial_read.codec import document_to_json, entity_ids
from apps.api.spatial_read.documents import EMPTY_LAYER
from apps.api.spatial_read.tests._helpers import make_scene
from packages.core.errors import MISSING
from packages.db.models.spatial import FloorChangeLogRow, FloorDocumentRow, FloorEntityIdRow
from packages.domain.spatial import FieldChange
from packages.testing.factories.spatial import make_change_rows, make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

WRITER = "usr_01J00000000000000000000000"


def _change(**overrides: object) -> dict[str, object]:
    """Một dòng nhật ký hợp lệ; test đổi đúng trường nó muốn phá."""
    return {
        "floor_pk": 0,
        "revision": 1,
        "entity_type": "wall",
        "entity_id": "W-WALL0000000",
        "field": "thickness_mm",
        "value": 220,
        "removed": False,
        "changed_at": func.now(),
        "changed_by": WRITER,
        "changed_by_name": "Người thử",
        **overrides,
    }


def _constraint(error: IntegrityError) -> str:
    """Tên ràng buộc bị vi phạm, lấy từ lỗi asyncpg gốc.

    `str(error)` không dùng được: `hide_parameters=True` cắt thông điệp, và tên ràng buộc
    nằm ở thuộc tính `constraint_name` của lỗi driver chứ không ở văn bản SQLAlchemy dựng.
    """
    cause: BaseException | None = error.orig
    while cause is not None:
        name = getattr(cause, "constraint_name", None)
        if name:
            return str(name)
        cause = cause.__cause__
    raise AssertionError(f"lỗi không nêu ràng buộc nào: {error}")


async def _fails(db: AsyncSession, row: object) -> str:
    """Thêm `row` và chờ DB từ chối; trả tên ràng buộc để assert nói rõ chỗ hỏng."""
    db.add(row)
    with pytest.raises(IntegrityError) as caught:
        await db.flush()
    await db.rollback()
    return _constraint(caught.value)


async def test_floor_documents_none_scale_rejects_value(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`scale_source='none'` mà vẫn có tỉ lệ → CHECK `scale_source_matches_scale`."""
    scene = await make_scene(db_session)
    row = FloorDocumentRow(
        floor_pk=scene.floors[0].pk,
        revision=0,
        schema_version=1,
        document=document_to_json(EMPTY_LAYER, (), ()),
        scale_mm_per_px=Decimal("12.700000"),
        scale_source="none",
        created_at=fake_clock.now(),
        updated_at=fake_clock.now(),
    )
    assert await _fails(db_session, row) == "ck_floor_documents_scale_source_matches_scale"


async def test_floor_documents_human_scale_requires_value(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Chiều ngược lại của cùng CHECK: nguồn khác `'none'` mà thiếu tỉ lệ cũng bị chặn."""
    scene = await make_scene(db_session)
    row = FloorDocumentRow(
        floor_pk=scene.floors[0].pk,
        revision=0,
        schema_version=1,
        document=document_to_json(EMPTY_LAYER, (), ()),
        scale_source="human",
        created_at=fake_clock.now(),
        updated_at=fake_clock.now(),
    )
    assert await _fails(db_session, row) == "ck_floor_documents_scale_source_matches_scale"


async def test_change_log_kept_value_requires_removed_false(db_session: AsyncSession) -> None:
    """`removed=false` kèm `value` NULL → CHECK `removed_matches_value`."""
    scene = await make_scene(db_session)
    row = FloorChangeLogRow(**_change(floor_pk=scene.floors[0].pk, value=None, removed=False))
    assert await _fails(db_session, row) == "ck_floor_change_log_removed_matches_value"


async def test_change_log_rejects_unknown_entity_type(db_session: AsyncSession) -> None:
    """`entity_type` ngoài bảng HOP-DONG-MOI §1.3 → CHECK `entity_type`."""
    scene = await make_scene(db_session)
    row = FloorChangeLogRow(**_change(floor_pk=scene.floors[0].pk, entity_type="ceiling"))
    assert await _fails(db_session, row) == "ck_floor_change_log_entity_type"


async def test_change_log_rejects_json_null_value(db_session: AsyncSession) -> None:
    """JSON `null` phải phân biệt được với SQL NULL → CHECK `value_not_json_null`."""
    scene = await make_scene(db_session)
    stmt = text(
        "INSERT INTO floor_change_log"
        " (floor_pk, revision, entity_type, entity_id, field, value, removed, changed_at, changed_by,"
        "  changed_by_name)"
        " VALUES (:pk, 1, 'wall', 'W-WALL0000000', 'kind', 'null'::jsonb, false, now(), :who, 'Người thử')"
    )
    with pytest.raises(IntegrityError) as caught:
        await db_session.execute(stmt, {"pk": scene.floors[0].pk, "who": WRITER})
    await db_session.rollback()
    assert _constraint(caught.value) == "ck_floor_change_log_value_not_json_null"


async def test_change_log_rejects_system_worker(db_session: AsyncSession) -> None:
    """Chỉ `usr_<ULID>` hoặc `system:pipeline` ghi được nhật ký → CHECK `changed_by_format`."""
    scene = await make_scene(db_session)
    row = FloorChangeLogRow(**_change(floor_pk=scene.floors[0].pk, changed_by="system:worker"))
    assert await _fails(db_session, row) == "ck_floor_change_log_changed_by_format"


async def test_change_log_rejects_empty_changed_by_name(db_session: AsyncSession) -> None:
    """Tên người ghi rỗng → CHECK `changed_by_name_not_empty` (F-08 hiện tên này)."""
    scene = await make_scene(db_session)
    row = FloorChangeLogRow(**_change(floor_pk=scene.floors[0].pk, changed_by_name=""))
    assert await _fails(db_session, row) == "ck_floor_change_log_changed_by_name_not_empty"


async def test_entity_ids_are_unique_per_project(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Hai tầng của cùng dự án không thể cùng giữ một id (W4) → PK `(project_id, entity_id)`."""
    scene = await make_scene(db_session, floors=2)
    now = fake_clock.now()
    db_session.add(
        FloorEntityIdRow(
            project_id=scene.project.id,
            entity_id="W-SHARED0001",
            floor_pk=scene.floors[0].pk,
            created_at=now,
            updated_at=now,
        )
    )
    await db_session.flush()
    duplicate = FloorEntityIdRow(
        project_id=scene.project.id,
        entity_id="W-SHARED0001",
        floor_pk=scene.floors[1].pk,
        created_at=now,
        updated_at=now,
    )
    assert await _fails(db_session, duplicate) == "pk_floor_entity_ids"


async def test_hard_delete_floor_cascades_all_three_tables(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Xoá cứng một tầng kéo theo dòng của cả ba bảng — lịch dọn chỉ cần một lệnh `DELETE`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    await make_floor_document(db_session, floor_pk=floor.pk, layer=layer, clock=fake_clock)
    db_session.add(FloorChangeLogRow(**_change(floor_pk=floor.pk, changed_at=fake_clock.now())))
    await db_session.flush()
    await db_session.execute(text("DELETE FROM floors WHERE pk = :pk"), {"pk": floor.pk})

    for model in (FloorDocumentRow, FloorChangeLogRow, FloorEntityIdRow):
        remaining = (
            await db_session.execute(select(func.count()).select_from(model).where(model.floor_pk == floor.pk))
        ).scalar_one()
        assert remaining == 0, model.__tablename__


async def test_make_floor_document_fills_entity_ids(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Factory điền đủ `floor_entity_ids` cho lớp nó ghi — đúng tập `codec.entity_ids`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)

    await make_floor_document(db_session, floor_pk=floor.pk, layer=layer, clock=fake_clock)

    stored = set(
        (
            await db_session.execute(select(FloorEntityIdRow.entity_id).where(FloorEntityIdRow.floor_pk == floor.pk))
        ).scalars()
    )
    assert stored == entity_ids(layer)


async def test_make_change_rows_marks_removed_fields(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`value is MISSING` → dòng `removed=true`, `value` SQL NULL (không phải JSON `null`)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    changes = (
        FieldChange(entity_id="W-WALL0000000", entity_type="wall", field="thickness_mm", value=220),
        FieldChange(entity_id="F-FURN0000000", entity_type="furniture", field="room_id", value=MISSING),
    )

    rows = await make_change_rows(
        db_session,
        floor_pk=floor.pk,
        revision=3,
        changes=changes,
        changed_by=WRITER,
        changed_by_name="Người thử",
        clock=fake_clock,
    )

    assert [(row.field, row.removed, row.value) for row in rows] == [
        ("thickness_mm", False, 220),
        ("room_id", True, None),
    ]
    stored = (
        await db_session.execute(
            select(func.count()).select_from(FloorChangeLogRow).where(FloorChangeLogRow.revision == 3)
        )
    ).scalar_one()
    assert stored == len(changes)
