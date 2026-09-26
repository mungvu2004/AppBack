"""Cài cổng `drawing_scales` (`apps.api.spatial_read.drawing_scales`) — B3-02 [8].

Hai lời hứa với B2-04: đúng **một** phần tử toàn hệ thống, và **một** truy vấn cho cả lô
(số câu SQL của 1 tầng và 8 tầng phải bằng nhau, nếu không N7 thành N+1).
"""

from collections.abc import Sequence
from decimal import Decimal
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.drawings.scales import load_scales
from apps.api.projects.tests.sql_count import count_sql
from apps.api.spatial_read.drawing_scales import SCALES
from apps.api.spatial_read.tests._helpers import make_scene
from packages.testing.factories.spatial import make_floor_document, sample_floor_layer
from packages.testing.fixtures.clock import FakeClock

SCALE = Decimal("12.700000")


def test_gate_declares_exactly_one_source() -> None:
    """`discover` thấy `apps.api.spatial_read` và đúng một phần tử (BE-00 §2.2)."""
    found = extensions.discover("drawing_scales", "SCALES")
    assert [name for name, _ in found] == ["apps.api.spatial_read.drawing_scales"]
    assert len(cast("Sequence[object]", found[0][1])) == 1


async def test_load_returns_only_floors_with_scale(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Ba tầng — có tỉ lệ, `none`, chưa có tài liệu — chỉ tầng đầu có khoá."""
    scene = await make_scene(db_session, floors=3)
    first, second, _third = scene.floors
    await make_floor_document(
        db_session,
        floor_pk=first.pk,
        layer=sample_floor_layer(0, level_id=first.level_id),
        scale=SCALE,
        scale_source="human",
        clock=fake_clock,
    )
    await make_floor_document(db_session, floor_pk=second.pk, clock=fake_clock)
    await db_session.commit()
    loaded = await SCALES[0].load(db_session, [floor.pk for floor in scene.floors])
    assert loaded == {first.pk: SCALE}
    assert float(loaded[first.pk]) == 12.7


async def test_load_uses_one_query_for_any_batch(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Số truy vấn với 1 và 8 tầng bằng nhau: một `IN (...)`, không vòng lặp."""
    scene = await make_scene(db_session, floors=8)
    for floor in scene.floors:
        await make_floor_document(db_session, floor_pk=floor.pk, scale=SCALE, scale_source="human", clock=fake_clock)
    await db_session.commit()
    with count_sql() as small:
        await SCALES[0].load(db_session, [scene.floors[0].pk])
    with count_sql() as large:
        await SCALES[0].load(db_session, [floor.pk for floor in scene.floors])
    assert small.count == large.count == 1


async def test_load_scales_of_b2_04_reaches_this_gate(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Đường thật của B2-04 (`load_scales`, không `app`) tìm được cổng qua `discover`."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(db_session, floor_pk=floor.pk, scale=SCALE, scale_source="pipeline", clock=fake_clock)
    await db_session.commit()
    assert await load_scales(db_session, [floor.pk]) == {floor.pk: SCALE}
