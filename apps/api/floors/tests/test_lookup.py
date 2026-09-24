"""Test `apps.api.floors.lookup` trên Postgres thật (K23): dựng `Floor`, khoá, `new_level_id`."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.core import extensions
from apps.api.floors.errors import FLOOR_ID_AMBIGUOUS, FLOOR_ID_TAKEN, FLOOR_LIMIT_REACHED, FLOOR_REORDER_MISMATCH
from apps.api.floors.lookup import floor_outs, floor_outs_by_project, get_floor, lock_project_floors, new_level_id
from apps.api.floors.settings import get_floors_settings, reset_floors_settings_cache
from apps.api.projects.parts import FLOOR_DRAWINGS, ViewPart
from apps.api.projects.summaries import set_layer_counts
from apps.api.projects.tests.sql_count import count_sql
from apps.api.projects.wire import DrawingOut
from packages.core.ids import is_spatial_id
from packages.testing.factories.auth import make_user
from packages.testing.factories.floors import make_floor
from packages.testing.factories.projects import make_project
from packages.testing.fixtures.clock import FakeClock


class _FakeApp:
    """`extensions.override` ghi `setattr` lên `app`; `object()` trần không có `__dict__`."""


DRAWING: Final = DrawingOut(
    id="drw_sample",
    name="Bản vẽ mẫu",
    url="https://appback.test/drw_sample.pdf",
    width_mm=1000,
    height_mm=2000,
    uploaded_at=datetime(2026, 1, 1, tzinfo=UTC),
    uploader_id="usr_sample",
)


async def test_floor_outs_orders_by_floor_order_then_pk_and_skips_soft_deleted(db_session: AsyncSession) -> None:
    """Thứ tự `(floor_order, pk)`; tầng xoá mềm không xuất hiện."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    first = await make_floor(db_session, project=project, order=0)
    second = await make_floor(db_session, project=project, order=1)
    tie_a = await make_floor(db_session, project=project, order=5)
    tie_b = await make_floor(db_session, project=project, order=5)
    deleted = await make_floor(db_session, project=project, order=2)
    deleted.deleted_at = datetime.now(UTC)
    await db_session.commit()

    floors = await floor_outs(db_session, project_id=project.id)

    assert [floor.id for floor in floors] == [first.level_id, second.level_id, tie_a.level_id, tie_b.level_id]


async def test_floor_outs_filters_by_floor_pks_in_sql(db_session: AsyncSession) -> None:
    """`floor_pks` lọc trong câu SQL, không phải sau khi tải hết về Python."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    kept = await make_floor(db_session, project=project, order=0)
    await make_floor(db_session, project=project, order=1)
    await db_session.commit()

    floors = await floor_outs(db_session, project_id=project.id, floor_pks=[kept.pk])

    assert [floor.id for floor in floors] == [kept.level_id]


async def test_floor_outs_area_m2_present_as_rounded_float_and_absent_when_null(db_session: AsyncSession) -> None:
    """`area_m2` `Decimal` → `float` làm tròn 2 chữ số; `NULL` → khoá `areaM2` vắng mặt."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    with_area = await make_floor(db_session, project=project, order=0)
    without_area = await make_floor(db_session, project=project, order=1)
    await set_layer_counts(
        db_session,
        project_id=project.id,
        floor_level_id=with_area.level_id,
        walls_total=5,
        walls_reviewed=5,
        area_m2=Decimal("48.60"),
    )
    await db_session.commit()

    floors = {floor.id: floor for floor in await floor_outs(db_session, project_id=project.id)}

    assert floors[with_area.level_id].area_m2 == 48.6
    assert isinstance(floors[with_area.level_id].area_m2, float)
    assert "areaM2" not in floors[without_area.level_id].model_dump(by_alias=True)


async def test_floor_outs_by_project_returns_every_id_asked_including_empty(db_session: AsyncSession) -> None:
    """Dự án không tầng nào → `[]`, không phải khoá vắng mặt."""
    user = await make_user(db_session)
    with_floor = await make_project(db_session, owner=user)
    empty = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=with_floor)
    await db_session.commit()

    result = await floor_outs_by_project(db_session, [with_floor.id, empty.id])

    assert result[empty.id] == []
    assert [row.id for row in result[with_floor.id]] == [floor.level_id]
    assert await floor_outs_by_project(db_session, []) == {}


async def test_floor_outs_calls_floor_drawings_view_part_once_for_whole_batch(
    db_session: AsyncSession, storage_env: None
) -> None:
    """Một lượt `view_part(FLOOR_DRAWINGS)` cho cả lô, khoá `str(pk)`; chưa cài → `[]`."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    with_drawing = await make_floor(db_session, project=project, order=0)
    without_drawing = await make_floor(db_session, project=project, order=1)
    await db_session.commit()

    calls: list[Sequence[str]] = []

    async def _load(db: AsyncSession, keys: Sequence[str]) -> Mapping[str, Sequence[DrawingOut]]:
        """`ViewPart.load` giả: ghi lại các khoá được hỏi, chỉ trả bản vẽ cho `with_drawing`."""
        calls.append(list(keys))
        return {str(with_drawing.pk): [DRAWING]}

    app = _FakeApp()
    extensions.override(app, "view_parts", [("apps.api.floors.tests.test_lookup", (ViewPart(FLOOR_DRAWINGS, _load),))])

    floors = {floor.id: floor for floor in await floor_outs(db_session, project_id=project.id, app=app)}

    assert len(calls) == 1
    assert sorted(calls[0]) == sorted([str(with_drawing.pk), str(without_drawing.pk)])
    assert [drawing.id for drawing in floors[with_drawing.level_id].drawings] == [DRAWING.id]
    assert floors[without_drawing.level_id].drawings == []


async def test_floor_outs_drawings_empty_when_nobody_installs_the_view_part(db_session: AsyncSession) -> None:
    """Không module nào cài `FLOOR_DRAWINGS` (B2-04 chưa tồn tại) → `drawings` luôn `[]`."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project)
    await db_session.commit()

    floors = await floor_outs(db_session, project_id=project.id)

    assert floors[0].id == floor.level_id
    assert floors[0].drawings == []


async def test_floor_outs_query_count_is_constant_for_3_and_30_floors(db_session: AsyncSession) -> None:
    """Số câu SQL của #12/`load_project_floors` không đổi theo số tầng (B2-03 [6])."""
    user = await make_user(db_session)
    small_project = await make_project(db_session, owner=user)
    for i in range(3):
        await make_floor(db_session, project=small_project, order=i)
    big_project = await make_project(db_session, owner=user)
    for i in range(30):
        await make_floor(db_session, project=big_project, order=i)
    await db_session.commit()

    with count_sql() as small_counter:
        await floor_outs(db_session, project_id=small_project.id)
    with count_sql() as big_counter:
        await floor_outs(db_session, project_id=big_project.id)

    assert small_counter.count == big_counter.count


async def test_get_floor_present_missing_and_soft_deleted(db_session: AsyncSession) -> None:
    """Tầng có thật → trả dòng; id lạ hoặc đã xoá mềm → `None`."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project)
    await db_session.commit()

    found = await get_floor(db_session, project_id=project.id, level_id=floor.level_id)
    assert found is not None
    assert found.pk == floor.pk

    assert await get_floor(db_session, project_id=project.id, level_id="L-0000000099") is None

    floor.deleted_at = datetime.now(UTC)
    await db_session.commit()
    assert await get_floor(db_session, project_id=project.id, level_id=floor.level_id) is None


async def test_get_floor_for_update_locks_the_row(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """`for_update=True` khoá dòng: lượt thứ hai với `lock_timeout` ngắn phải chờ rồi hỏng."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    floor = await make_floor(db_session, project=project)
    await db_session.commit()

    await get_floor(db_session, project_id=project.id, level_id=floor.level_id, for_update=True)

    async with db_sessionmaker() as second:
        await second.execute(text("SET LOCAL lock_timeout = '50ms'"))
        with pytest.raises(DBAPIError, match="timeout"):
            await get_floor(second, project_id=project.id, level_id=floor.level_id, for_update=True)
        await second.rollback()

    await db_session.commit()
    async with db_sessionmaker() as third:
        # Khoá đã nhả sau commit của phiên đầu — phiên này không phải chờ.
        row = await get_floor(third, project_id=project.id, level_id=floor.level_id, for_update=True)
        assert row is not None
        await third.commit()


async def test_lock_project_floors_blocks_second_session_until_first_commits(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Khoá tư vấn theo dự án: phiên hai chờ tới khi phiên một `commit` (BE-00 §7)."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    await db_session.commit()

    await lock_project_floors(db_session, project.id)

    async with db_sessionmaker() as second:
        await second.execute(text("SET LOCAL lock_timeout = '50ms'"))
        with pytest.raises(DBAPIError, match="timeout"):
            await lock_project_floors(second, project.id)
        await second.rollback()

    await db_session.commit()
    async with db_sessionmaker() as third:
        await lock_project_floors(third, project.id)  # không còn ai giữ khoá — trả ngay
        await third.commit()


def test_new_level_id_matches_is_spatial_id(fake_clock: FakeClock) -> None:
    """`new_level_id` sinh id đúng `is_spatial_id("level", …)` (dinh-chinh §7)."""
    level_id = new_level_id(fake_clock)
    assert is_spatial_id("level", level_id)


async def test_make_floor_writes_floor_row_and_summary_count(db_session: AsyncSession) -> None:
    """Khói factory: dòng `floors` và dòng đếm cùng ghi; `order=None` → đặt ở cuối."""
    user = await make_user(db_session)
    project = await make_project(db_session, owner=user)
    first = await make_floor(db_session, project=project, name="Tầng trệt", height_mm=2500)
    second = await make_floor(db_session, project=project)

    assert (first.name, first.height_mm, first.floor_order) == ("Tầng trệt", 2500, 0)
    assert second.floor_order == 1

    outs = await floor_outs(db_session, project_id=project.id)
    assert [row.id for row in outs] == [first.level_id, second.level_id]


def test_floors_settings_defaults_and_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mặc định đúng [5]; `FLOORS_MAX` đổi được qua biến môi trường + reset cache (C15)."""
    reset_floors_settings_cache()
    try:
        defaults = get_floors_settings()
        assert (defaults.floors_max, defaults.floor_restore_window_s) == (50, 600)
        assert (defaults.floor_purge_after_d, defaults.floor_purge_batch) == (30, 100)

        monkeypatch.setenv("FLOORS_MAX", "3")
        reset_floors_settings_cache()
        assert get_floors_settings().floors_max == 3
    finally:
        reset_floors_settings_cache()


def test_floor_errors_carry_the_right_status_and_field() -> None:
    """Bốn mã lỗi riêng (B2-03 [2]) đúng status và tham số `field`."""
    assert (FLOOR_ID_TAKEN.status, FLOOR_ID_TAKEN.error(field="id").params) == (409, {"field": "id"})
    assert FLOOR_ID_AMBIGUOUS.status == 409
    assert FLOOR_LIMIT_REACHED.status == 422
    assert (FLOOR_REORDER_MISMATCH.status, FLOOR_REORDER_MISMATCH.error(field="floorIds").params) == (
        422,
        {"field": "floorIds"},
    )
