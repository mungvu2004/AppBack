"""Hai cổng đọc của bản vẽ: `floor.drawings` (`view_parts.py`) và `drawing_pages.PAGES`.

Trọng tâm là luật W24 (mm = pixel x tỉ lệ) và lời hứa "một truy vấn cho cả lô": số câu
SQL của cả hai cổng phải **không đổi** giữa 1 tầng và 20 tầng, nếu không thì N1 của
B2-01 thành N+1 ngay khi dự án có nhiều tầng.
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core import extensions
from apps.api.drawings import scales
from apps.api.drawings.drawing_pages import PAGES
from apps.api.drawings.runs import start_run
from apps.api.drawings.scales import load_scales
from apps.api.drawings.tests._drawing_helpers import make_drawing, png_bytes
from apps.api.drawings.tests._drawing_helpers import test_signer as test_signer
from apps.api.drawings.tests._helpers import Scene, make_scene
from apps.api.drawings.view_parts import PARTS, load
from apps.api.projects.parts import FLOOR_DRAWINGS
from apps.api.projects.tests.sql_count import count_sql
from apps.api.projects.wire import DrawingOut
from packages.db.models.drawings import DrawingRow
from packages.storage.local import LocalDiskStorage
from packages.testing.factories.drawings import make_complete_upload
from packages.testing.fixtures.clock import FakeClock

PNG = png_bytes(100, 50)
SCALE = Decimal("12.7")
"""Tỉ lệ giả của cổng `drawing_scales` trong test ([8] "Bản vẽ")."""


class _FakeScales:
    """Cổng tỉ lệ giả: chỉ biết những tầng test đưa vào, đúng hợp đồng `Mapping[int, Decimal]`."""

    def __init__(self, known: Mapping[int, Decimal]) -> None:
        """Ghi nhớ bảng tỉ lệ; tầng ngoài bảng vắng khoá như cổng thật của B3-02."""
        self.known = dict(known)

    async def load(self, db: object, floor_pks: Sequence[int]) -> Mapping[int, Decimal]:
        """Chỉ trả những tầng cổng biết — không bịa khoá cho tầng lạ."""
        return {pk: self.known[pk] for pk in floor_pks if pk in self.known}


def _use_scales(app: FastAPI, source: object | None) -> None:
    """Cài (hay gỡ) cổng `drawing_scales` cho **một** app test (`extensions.override`)."""
    items = (source,) if source is not None else ()
    extensions.override(app, scales.SUBMODULE, [("apps.api.drawings.tests.test_view_parts", items)])


async def _drawing(db: AsyncSession, storage: LocalDiskStorage, scene: Scene) -> DrawingRow:
    """Một tầng có bản vẽ 100x50 px đang dùng."""
    upload = await make_complete_upload(db, storage, project=scene.project, floor=scene.floor, data=PNG)
    return await make_drawing(db, storage, upload=upload, png=PNG)


async def _outs(db: AsyncSession, pks: Sequence[int], *, app: object | None) -> Mapping[str, Sequence[DrawingOut]]:
    """`load` rồi ép kiểu về `DrawingOut` (cổng khai `WireModel` cho mọi `ViewPart`)."""
    loaded = await load(db, [str(pk) for pk in pks], app=app)
    return {key: [item for item in value if isinstance(item, DrawingOut)] for key, value in loaded.items()}


def test_parts_declares_floor_drawings() -> None:
    """Cổng khai đúng một `ViewPart` và đúng `kind` mà `floors.lookup` tra."""
    assert [part.kind for part in PARTS] == [FLOOR_DRAWINGS]


async def test_load_without_scale_gate_uses_pixels(db_session: AsyncSession, local_storage: LocalDiskStorage) -> None:
    """Chưa module nào cài `drawing_scales` → mm bằng px (BE-00 §2.2, tỉ lệ 1)."""
    scene = await make_scene(db_session)
    drawing = await _drawing(db_session, local_storage, scene)
    out = await _outs(db_session, [scene.floor.pk], app=None)
    item = out[str(scene.floor.pk)][0]
    assert (item.width_mm, item.height_mm) == (100, 50)
    assert item.id == drawing.id
    assert item.scale is None
    assert item.uploader_id == drawing.uploader_id
    assert item.url


async def test_load_applies_scale_gate(
    db_session: AsyncSession, local_storage: LocalDiskStorage, api_app: FastAPI
) -> None:
    """Cổng tỉ lệ 12,7 mm/px → `widthMm = round(width_px x 12,7)` (W24)."""
    scene = await make_scene(db_session)
    await _drawing(db_session, local_storage, scene)
    _use_scales(api_app, _FakeScales({scene.floor.pk: SCALE}))
    out = await _outs(db_session, [scene.floor.pk], app=api_app)
    item = out[str(scene.floor.pk)][0]
    assert (item.width_mm, item.height_mm) == (round(100 * SCALE), round(50 * SCALE))


async def test_load_falls_back_when_gate_misses_floor(
    db_session: AsyncSession, local_storage: LocalDiskStorage, api_app: FastAPI
) -> None:
    """Cổng có mặt nhưng không biết tầng này → mm bằng px, không phải 0."""
    scene = await make_scene(db_session)
    await _drawing(db_session, local_storage, scene)
    _use_scales(api_app, _FakeScales({}))
    out = await _outs(db_session, [scene.floor.pk], app=api_app)
    item = out[str(scene.floor.pk)][0]
    assert (item.width_mm, item.height_mm) == (100, 50)


async def test_load_floor_without_drawing_is_absent(db_session: AsyncSession) -> None:
    """Tầng chưa có bản vẽ vắng khoá; `lookup.py` đọc khoá thiếu thành `[]`."""
    scene = await make_scene(db_session)
    assert await load(db_session, [str(scene.floor.pk)], app=None) == {}


async def test_load_empty_batch_is_empty(db_session: AsyncSession) -> None:
    """Lô rỗng → `{}` và **không** truy vấn nào."""
    with count_sql() as counter:
        assert await load(db_session, [], app=None) == {}
    assert counter.count == 0


async def test_load_scales_rejects_two_gates(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Hai phần tử cài cùng cổng → `RuntimeError` (BE-00 §2.2: 0-1 phần tử)."""
    extensions.override(
        api_app,
        scales.SUBMODULE,
        [("a", (_FakeScales({}),)), ("b", (_FakeScales({}),))],
    )
    with pytest.raises(RuntimeError, match="tối đa 1"):
        await load_scales(db_session, [1], app=api_app)


async def test_load_scales_empty_batch_skips_gate(db_session: AsyncSession, api_app: FastAPI) -> None:
    """Lô rỗng không gọi cổng: không có gì để hỏi."""
    _use_scales(api_app, _FakeScales({1: SCALE}))
    assert await load_scales(db_session, [], app=api_app) == {}


async def test_drawing_pages_returns_current_key(
    db_session: AsyncSession, local_storage: LocalDiskStorage, fake_clock: FakeClock
) -> None:
    """Hai tầng, một chưa có bản vẽ, một vừa đổi lượt tải → một khoá, và là khoá **mới**."""
    scene = await make_scene(db_session)
    empty = await make_scene(db_session)
    first = await _drawing(db_session, local_storage, scene)
    old_key = first.page_key
    second_upload = await make_complete_upload(
        db_session, local_storage, project=scene.project, floor=scene.floor, data=PNG
    )
    await start_run(db_session, upload_id=second_upload.id, clock=fake_clock)
    await db_session.delete(first)
    await db_session.flush()
    fresh = await make_drawing(db_session, local_storage, upload=second_upload, png=PNG)

    loaded = await PAGES[0].load(db_session, [scene.floor.pk, empty.floor.pk])
    assert loaded == {scene.floor.pk: fresh.page_key}
    assert fresh.page_key != old_key


async def test_drawing_pages_empty_batch(db_session: AsyncSession) -> None:
    """Lô rỗng → `{}` và không truy vấn."""
    with count_sql() as counter:
        assert await PAGES[0].load(db_session, []) == {}
    assert counter.count == 0


async def test_gates_query_count_is_constant_for_1_and_20_floors(
    db_session: AsyncSession, local_storage: LocalDiskStorage
) -> None:
    """Số câu SQL của cả hai cổng không đổi theo số tầng (R-20, mẫu `test_view_parts` B2-03)."""
    small = await make_scene(db_session)
    await _drawing(db_session, local_storage, small)
    big_scene = await make_scene(db_session)
    big_pks = [big_scene.floor.pk]
    await _drawing(db_session, local_storage, big_scene)
    for _ in range(19):
        extra = await make_scene(db_session)
        upload = await make_complete_upload(
            db_session, local_storage, project=extra.project, floor=extra.floor, data=PNG
        )
        await make_drawing(db_session, local_storage, upload=upload, png=PNG)
        big_pks.append(extra.floor.pk)

    with count_sql() as one_part:
        await load(db_session, [str(small.floor.pk)], app=None)
    with count_sql() as many_parts:
        await load(db_session, [str(pk) for pk in big_pks], app=None)
    assert one_part.count == many_parts.count

    with count_sql() as one_page:
        await PAGES[0].load(db_session, [small.floor.pk])
    with count_sql() as many_pages:
        await PAGES[0].load(db_session, big_pks)
    assert one_page.count == many_pages.count
