"""`apps.api.spatial_read.documents` trên Postgres thật (B3-02 [8]).

Bốn việc: giải mã một dòng (kể cả dòng hỏng do lược đồ), đọc lô **một** truy vấn,
`ensure_document` chịu được hai lượt song song, và `has_human_geometry` năm case.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.projects.tests.sql_count import count_sql
from apps.api.spatial_read.codec import DocumentCorruptError
from apps.api.spatial_read.documents import (
    DOCUMENT_SCHEMA_VERSION,
    empty_document,
    ensure_document,
    has_human_geometry,
    load_document,
    load_documents,
    scan_corrupt,
)
from apps.api.spatial_read.settings import get_spatial_read_settings, reset_spatial_read_settings_cache
from apps.api.spatial_read.tests._helpers import make_scene, other_session, race
from packages.db.models.spatial import FloorDocumentRow
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock


async def _bump_schema_version(db: AsyncSession, floor_pk: int, version: int) -> None:
    """Ghi thẳng bằng SQL: model không cho đặt lược đồ lạ, nhưng một bản cũ trong DB thì có."""
    await db.execute(
        text("UPDATE floor_documents SET schema_version = :v WHERE floor_pk = :pk"),
        {"v": version, "pk": floor_pk},
    )


async def test_load_document_reads_back_what_was_written(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Đọc lại đúng lớp, bản ghi và tỉ lệ đã ghi; `Decimal` giữ nguyên, không thành `float` (K20)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=layer,
        revision=7,
        scale=Decimal("12.700000"),
        scale_source="human",
        clock=fake_clock,
    )

    document = await load_document(db_session, floor.pk)

    assert document is not None
    assert document.layer == layer
    assert document.revision == 7
    assert document.scale_mm_per_px == Decimal("12.700000")
    assert document.scale_source == "human"
    assert document.dimensions == ()


async def test_load_document_missing_row_is_none(db_session: AsyncSession) -> None:
    """Tầng chưa có tài liệu → `None`; route đọc đổi thành `empty_document`, không ghi gì."""
    scene = await make_scene(db_session)
    assert await load_document(db_session, scene.floors[0].pk) is None


async def test_load_document_for_update_locks_the_row(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`for_update=True` khoá dòng: cùng một dòng đọc lại trong giao dịch vẫn ra cùng kết quả."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)

    document = await load_document(db_session, floor.pk, for_update=True)

    assert document is not None
    assert document.revision == 0


async def test_load_document_rejects_foreign_schema_version(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`schema_version=2` → `DocumentCorruptError` **trước** khi chạm codec."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)
    await _bump_schema_version(db_session, floor.pk, DOCUMENT_SCHEMA_VERSION + 1)

    with pytest.raises(DocumentCorruptError):
        await load_document(db_session, floor.pk)


async def test_load_documents_rejects_foreign_schema_version(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Đọc lô dùng cùng đường giải mã nên cũng hỏng ở đúng dòng ấy."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)
    await _bump_schema_version(db_session, floor.pk, DOCUMENT_SCHEMA_VERSION + 1)

    with pytest.raises(DocumentCorruptError):
        await load_documents(db_session, [floor.pk])


async def test_load_documents_is_one_query_for_any_floor_count(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """1 tầng và 8 tầng tốn **cùng** số câu SQL (N15 không N+1)."""
    scene = await make_scene(db_session, floors=8)
    for index, floor in enumerate(scene.floors):
        await make_floor_document(
            db_session,
            floor_pk=floor.pk,
            layer=sample_floor_layer(index % 4, level_id=floor.level_id, id_suffix=f"S{index}"),
            clock=fake_clock,
        )
    pks = [floor.pk for floor in scene.floors]

    with count_sql() as one:
        assert len(await load_documents(db_session, pks[:1])) == 1
    with count_sql() as eight:
        assert len(await load_documents(db_session, pks)) == 8

    assert one.count == eight.count == 1


async def test_load_documents_empty_batch_runs_no_query(db_session: AsyncSession) -> None:
    """Lô rỗng trả `{}` mà không chạy câu nào — dự án chưa có tầng không đáng một vòng DB."""
    with count_sql() as counter:
        assert await load_documents(db_session, []) == {}
    assert counter.count == 0


async def test_load_documents_skips_floors_without_a_row(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tầng chưa có tài liệu vắng khoá (không phải `None`) — người gọi tự dựng `empty_document`."""
    scene = await make_scene(db_session, floors=2)
    await make_floor_document(db_session, floor_pk=scene.floors[0].pk, clock=fake_clock)

    documents = await load_documents(db_session, [floor.pk for floor in scene.floors])

    assert set(documents) == {scene.floors[0].pk}


def test_empty_document_is_revision_zero_and_unscaled() -> None:
    """`empty_document` không chạm DB và mô tả đúng "tầng chưa ghi lần nào"."""
    document = empty_document(42)

    assert document.floor_pk == 42
    assert document.revision == 0
    assert document.scale_source == "none"
    assert document.scale_mm_per_px is None
    assert document.updated_at is None
    assert document.layer.entities() == ()


async def test_ensure_document_creates_then_reuses_the_row(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt đầu tạo dòng, lượt sau trả lại dòng cũ — vẫn chỉ một dòng."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    first = await ensure_document(db_session, floor_pk=floor.pk, clock=fake_clock)
    second = await ensure_document(db_session, floor_pk=floor.pk, clock=fake_clock)

    assert first.revision == second.revision == 0
    assert first.scale_source == "none"
    assert await _document_count(db_session, floor.pk) == 1


async def test_ensure_document_is_safe_in_parallel_sessions(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
) -> None:
    """Hai session **thật** gọi cùng lúc → một dòng, không bên nào lỗi (`ON CONFLICT DO NOTHING`)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    async def claim(session: AsyncSession) -> int:
        """Một lượt `ensure_document` hoàn chỉnh, có commit — giao dịch riêng của session đó."""
        document = await ensure_document(session, floor_pk=floor.pk, clock=fake_clock)
        await session.commit()
        return document.revision

    async with other_session(db_sessionmaker) as left, other_session(db_sessionmaker) as right:
        results = await race(lambda: claim(left), lambda: claim(right))

    assert results == (0, 0)
    assert await _document_count(db_session, floor.pk) == 1


async def _document_count(db: AsyncSession, floor_pk: int) -> int:
    """Số dòng `floor_documents` của một tầng — dùng để khẳng định "đọc không ghi"."""
    stmt = select(func.count()).select_from(FloorDocumentRow).where(FloorDocumentRow.floor_pk == floor_pk)
    return (await db.execute(stmt)).scalar_one()


async def test_has_human_geometry_without_a_row(db_session: AsyncSession) -> None:
    """Tầng chưa có tài liệu → `False`."""
    scene = await make_scene(db_session)
    assert await has_human_geometry(db_session, scene.floors[0].pk) is False


async def test_has_human_geometry_with_human_scale(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tỉ lệ do người đặt là dấu tay người, dù lớp còn rỗng."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session, floor_pk=floor.pk, scale=Decimal("12.7"), scale_source="human", clock=fake_clock
    )
    assert await has_human_geometry(db_session, floor.pk) is True


async def test_has_human_geometry_with_reviewed_furniture(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tỉ lệ `pipeline` nhưng một đồ đạc đã duyệt → `True`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    furniture = (layer.furniture[0].model_copy(update={"reviewed": True, "source": "human"}),)
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=layer.model_copy(update={"furniture": furniture + layer.furniture[1:]}),
        scale=Decimal("12.7"),
        scale_source="pipeline",
        clock=fake_clock,
    )
    assert await has_human_geometry(db_session, floor.pk) is True


async def test_has_human_geometry_with_unreviewed_human_opening(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Một ô mở `source="human"` **chưa** duyệt vẫn là dấu tay người (mục vừa vẽ)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    opening = layer.openings[0].model_copy(update={"source": "human"})
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=layer.model_copy(update={"openings": (opening, *layer.openings[1:])}),
        scale=Decimal("12.7"),
        scale_source="pipeline",
        clock=fake_clock,
    )
    assert await has_human_geometry(db_session, floor.pk) is True


async def test_has_human_geometry_all_ai_is_false(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Mọi mục do máy phát hiện, chưa ai duyệt, tỉ lệ `pipeline` → `False` (và chỉ một truy vấn)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = sample_floor_layer(0, level_id=floor.level_id)
    ai_rooms = tuple(room.model_copy(update={"reviewed": False, "source": "ai"}) for room in layer.rooms)
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=layer.model_copy(update={"rooms": ai_rooms}),
        scale=Decimal("12.7"),
        scale_source="pipeline",
        clock=fake_clock,
    )

    with count_sql() as counter:
        assert await has_human_geometry(db_session, floor.pk) is False
    assert counter.count == 1


async def test_scan_corrupt_reports_only_broken_rows(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Hàm lô của CLI: chỉ nêu dòng hỏng, và trả `None` khi đã quét hết."""
    scene = await make_scene(db_session, floors=3)
    for index, floor in enumerate(scene.floors):
        await make_floor_document(
            db_session,
            floor_pk=floor.pk,
            layer=sample_floor_layer(index, level_id=floor.level_id, id_suffix=f"S{index}"),
            clock=fake_clock,
        )
    broken = scene.floors[1].pk
    await _bump_schema_version(db_session, broken, DOCUMENT_SCHEMA_VERSION + 1)

    corrupt, cursor = await scan_corrupt(db_session, after_pk=0, limit=100)

    assert corrupt == [broken]
    assert cursor is None


async def test_scan_corrupt_pages_by_cursor(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lô đầy trả con trỏ để CLI đi tiếp; lô sau bắt đầu **sau** `after_pk`, không lặp dòng."""
    scene = await make_scene(db_session, floors=3)
    for floor in scene.floors:
        await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)

    first, cursor = await scan_corrupt(db_session, after_pk=0, limit=2)
    assert first == []
    assert cursor == sorted(floor.pk for floor in scene.floors)[1]

    second, tail = await scan_corrupt(db_session, after_pk=cursor, limit=2)
    assert second == []
    assert tail is None


async def test_corrupt_document_column_is_reported(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lược đồ đúng nhưng jsonb lệch mô hình (khoá lạ) vẫn là `DocumentCorruptError`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)
    await db_session.execute(
        text("UPDATE floor_documents SET document = document || '{\"notes\": []}'::jsonb WHERE floor_pk = :pk"),
        {"pk": floor.pk},
    )

    with pytest.raises(DocumentCorruptError):
        await load_document(db_session, floor.pk)


async def test_scan_corrupt_finds_broken_document_column(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """CLI dùng cùng đường giải mã nên cũng bắt được dòng hỏng vì jsonb, không chỉ vì lược đồ."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, clock=fake_clock)
    await db_session.execute(
        text("UPDATE floor_documents SET document = document || '{\"notes\": []}'::jsonb WHERE floor_pk = :pk"),
        {"pk": floor.pk},
    )

    assert await scan_corrupt(db_session, after_pk=0, limit=10) == ([floor.pk], None)


def test_settings_defaults_and_cache_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định đúng [5], và `reset_spatial_read_settings_cache` cho phép test đổi bằng biến môi trường."""
    reset_spatial_read_settings_cache()
    defaults = get_spatial_read_settings()
    assert (defaults.spatial_recount_lookback_s, defaults.spatial_recount_batch) == (900, 200)

    monkeypatch.setenv("SPATIAL_RECOUNT_BATCH", "7")
    reset_spatial_read_settings_cache()
    assert get_spatial_read_settings().spatial_recount_batch == 7

    monkeypatch.delenv("SPATIAL_RECOUNT_BATCH")
    reset_spatial_read_settings_cache()
