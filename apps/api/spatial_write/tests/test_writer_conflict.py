"""Đua bản ghi của `write_layer`: W20, C09b, thua đua và tranh id (B3-03 [6] bước 4-5, 11-12).

Mọi test ở đây dùng **session thật thứ hai** (`other_session`) chứ không giả lập giao dịch:
luật "ai thắng, ai 409" chỉ đúng khi Postgres thật sự khoá và `UPDATE … WHERE revision`
thật sự ăn 0 dòng.
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.spatial_read.documents import FloorDocument, ensure_document, load_document
from apps.api.spatial_read.tests._helpers import make_scene, other_session, race
from apps.api.spatial_write.errors import LAYER_INTEGRITY_BROKEN
from apps.api.spatial_write.tests._helpers import (
    RecordingMerge,
    log_count,
    make_wall,
    reread,
    simple_layer,
    slipping_load,
    write,
)
from apps.api.spatial_write.writer import WriteResult
from packages.core.clock import Clock
from packages.core.errors import AppError, VersionConflictError
from packages.db.models.auth import User
from packages.db.models.floors import FloorRow
from packages.domain.spatial import SpatialLayer
from packages.testing.factories.auth import make_user
from packages.testing.factories.spatial import make_floor_document
from packages.testing.fixtures.clock import FakeClock

CONCURRENT_WRITES = 20
"""Số lượt ghi thường chạy song song với một lượt `merge` ([8])."""


def _two_walls(level_id: str, *, thickness: int = 200) -> SpatialLayer:
    """Lớp hai tường - đủ để một lượt ghi chỉ **đổi thứ tự** danh sách mà không sinh dòng nhật ký."""
    return simple_layer(
        level_id,
        walls=(
            make_wall(level_id, thickness=thickness),
            make_wall(level_id, entity_id="W-TESTWALL02", length=1500, thickness=thickness),
        ),
    )


async def _in_own_session(
    sessionmaker: async_sessionmaker[AsyncSession], work: Callable[[AsyncSession], Awaitable[WriteResult]]
) -> WriteResult:
    """Chạy một lượt ghi trong giao dịch riêng rồi `commit` - bên kia phải thấy được nó."""
    async with other_session(sessionmaker) as session:
        result = await work(session)
        await session.commit()
        return result


async def test_base_version_above_current_is_a_validation_error(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`baseVersion` lớn hơn bản ghi hiện tại là bản ghi không tồn tại, không phải xung đột."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]

    with pytest.raises(AppError) as caught:
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, base_revision=7, scale=Decimal("10"))

    assert caught.value.params["field"] == "baseVersion"


async def test_stale_write_reports_remote_changes(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Người thứ hai gửi bản ghi cũ → 409 mang bản ghi hiện tại và **ít nhất một** thay đổi (W20)."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    other = await make_user(db_session, name="Người thứ hai")
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))

    with pytest.raises(VersionConflictError) as caught:
        await write(db_session, floor=floor, actor=other, clock=fake_clock, layer=_two_walls(floor.level_id))

    assert caught.value.current_version == 1
    assert len(caught.value.remote_changes) >= 1


async def test_same_body_from_same_writer_is_accepted(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """C09b: lượt gửi lại của **cùng người, cùng thân, cùng `baseVersion`** là 200, không 409."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    layer = simple_layer(floor.level_id)
    first = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)
    logged = await log_count(db_session, floor.pk)

    again = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    assert (again.revision, again.applied) == (first.revision, False)
    assert await log_count(db_session, floor.pk) == logged


async def test_different_body_from_same_writer_conflicts(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Cùng người nhưng thân khác: đó là một lượt sửa mới trên bản ghi đã cũ → 409."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id))

    with pytest.raises(VersionConflictError):
        await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=_two_walls(floor.level_id))


async def test_same_body_from_other_writer_conflicts(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Thân giống hệt nhưng người khác gửi: không phải lượt lặp của transport, phải là 409."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    other = await make_user(db_session, name="Người thứ hai")
    layer = simple_layer(floor.level_id)
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, layer=layer)

    with pytest.raises(VersionConflictError):
        await write(db_session, floor=floor, actor=other, clock=fake_clock, layer=layer)


async def test_empty_remote_diff_accepts_the_write(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bản ghi mới mà **không** đổi trường nào (chỉ tỉ lệ, mọi mục đã duyệt) thì không chặn ai (W20).

    Và lượt gửi lại của chính người ấy vẫn là C09b, vì `last_base_revision` giữ đúng con số
    người dùng cầm chứ không phải bản ghi thực sự bị đè.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    other = await make_user(db_session, name="Người thứ hai")
    reviewed = simple_layer(floor.level_id, walls=(make_wall(floor.level_id, source="human", reviewed=True),))
    await make_floor_document(
        db_session,
        floor_pk=floor.pk,
        layer=reviewed,
        revision=1,
        scale=Decimal("10"),
        scale_source="human",
        clock=fake_clock,
    )
    await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, base_revision=1, scale=Decimal("20"))
    assert await log_count(db_session, floor.pk) == 0
    grown = simple_layer(
        floor.level_id,
        walls=(
            make_wall(floor.level_id, source="human", reviewed=True),
            make_wall(floor.level_id, entity_id="W-TESTWALL02"),
        ),
    )

    accepted = await write(db_session, floor=floor, actor=other, clock=fake_clock, base_revision=1, layer=grown)
    repeated = await write(db_session, floor=floor, actor=other, clock=fake_clock, base_revision=1, layer=grown)

    assert (accepted.revision, accepted.applied) == (3, True)
    assert (repeated.revision, repeated.applied) == (3, False)
    assert (await reread(db_session, floor.pk)).scale_mm_per_px == Decimal("20.000000")


async def test_two_floors_cannot_claim_the_same_entity_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai tầng cùng dự án thêm cùng một id song song: đúng một bên thắng, bên kia 422 (W4)."""
    scene = await make_scene(db_session, floors=2)
    first, second = scene.floors
    await db_session.commit()

    async def claim(floor: FloorRow) -> WriteResult:
        """Một lượt ghi trọn vẹn trên tầng `floor`, giao dịch riêng."""
        return await _in_own_session(
            db_sessionmaker,
            lambda session: write(
                session, floor=floor, actor=scene.owner, clock=fake_clock, layer=simple_layer(floor.level_id)
            ),
        )

    outcomes = await race(lambda: claim(first), lambda: claim(second))

    winners = [item for item in outcomes if isinstance(item, WriteResult)]
    losers = [item for item in outcomes if isinstance(item, AppError)]
    assert len(winners) == 1
    assert [error.code for error in losers] == [LAYER_INTEGRITY_BROKEN]


async def test_concurrent_writes_leave_exactly_one_winner(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai thân khác nhau trên cùng bản ghi: một 200, một 409 - không bao giờ cả hai cùng ghi."""
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    other = await make_user(db_session, name="Người thứ hai")
    await make_floor_document(db_session, floor_pk=floor.pk, revision=1, clock=fake_clock)
    await db_session.commit()

    async def attempt(actor: User, layer: SpatialLayer) -> WriteResult:
        """Ghi `layer` từ bản ghi 1 trong giao dịch riêng."""
        return await _in_own_session(
            db_sessionmaker,
            lambda session: write(session, floor=floor, actor=actor, clock=fake_clock, base_revision=1, layer=layer),
        )

    outcomes = await race(
        lambda: attempt(scene.owner, simple_layer(floor.level_id)),
        lambda: attempt(other, _two_walls(floor.level_id)),
    )

    assert len([item for item in outcomes if isinstance(item, WriteResult)]) == 1
    assert len([item for item in outcomes if isinstance(item, VersionConflictError)]) == 1
    assert (await reread(db_session, floor.pk)).revision == 2


async def test_losing_every_race_ends_in_dependency_unavailable(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thua đua `SPATIAL_WRITE_ATTEMPTS` lần liền → 503 + `Retry-After: 1`, không phải 500.

    Bên thắng (`slipping_load`) chỉ đổi thứ tự danh sách nên không sinh dòng nhật ký: lượt của
    ta vì thế luôn đi qua được bước 5 rồi mới chết ở `UPDATE`, đúng cảnh mà 503 sinh ra để mô tả.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session, floor_pk=floor.pk, layer=_two_walls(floor.level_id), revision=1, clock=fake_clock
    )
    await db_session.commit()
    loader = slipping_load(db_sessionmaker, floor=floor, actor=scene.owner, clock=fake_clock)
    monkeypatch.setattr("apps.api.spatial_write.writer.load_document", loader)

    with pytest.raises(AppError) as caught:
        await write(
            db_session,
            floor=floor,
            actor=scene.owner,
            clock=fake_clock,
            base_revision=1,
            layer=_two_walls(floor.level_id, thickness=250),
        )

    assert caught.value.code.status == 503
    assert caught.value.retry_after == 1


async def test_merge_locks_the_document_of_a_floor_without_one(
    db_session: AsyncSession, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tầng **chưa có** dòng `floor_documents`: đường `merge` khoá **sau** `ensure_document`.

    Chốt thẳng bất biến của bước 3 chứ không dựng đua: dựng đua trên tầng chưa có dòng không
    phân biệt được hai bản mã, vì `INSERT … ON CONFLICT DO NOTHING` của `ensure_document` đã
    tự serialize hai bên. Cái phải đúng là **thứ tự**: `ensure_document` tạo dòng trước, rồi
    `load_document(for_update=True)` khoá **dòng đã tồn tại**. Thứ tự ngược lại (bản trước
    `dfc41eb`) khoá một dòng chưa có, tức không khoá gì, nên `merge` có thể thua đua.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    assert await load_document(db_session, floor.pk) is None
    trace: list[str] = []
    real_load, real_ensure = load_document, ensure_document

    async def recording_load(db: AsyncSession, floor_pk: int, *, for_update: bool = False) -> FloorDocument | None:
        """Ghi lại mỗi lượt đọc kèm việc nó có khoá hay không."""
        trace.append(f"load(for_update={for_update})")
        return await real_load(db, floor_pk, for_update=for_update)

    async def recording_ensure(db: AsyncSession, *, floor_pk: int, clock: Clock) -> FloorDocument:
        """Ghi lại lượt tạo dòng để so thứ tự với lượt khoá."""
        trace.append("ensure")
        return await real_ensure(db, floor_pk=floor_pk, clock=clock)

    monkeypatch.setattr("apps.api.spatial_write.writer.load_document", recording_load)
    monkeypatch.setattr("apps.api.spatial_write.writer.ensure_document", recording_ensure)
    merge = RecordingMerge(lambda base: base.model_copy(update={"walls": (make_wall(floor.level_id),)}))

    result = await write(db_session, floor=floor, actor=scene.owner, clock=fake_clock, merge=merge)

    assert result.applied is True
    assert merge.calls == 1
    assert trace == ["ensure", "load(for_update=True)"]


async def test_merge_never_conflicts_with_concurrent_writes(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Một lượt `merge` chạy cùng 20 lượt ghi thường: không lượt nào ra `VersionConflictError`.

    `merge` khoá dòng tài liệu nên nó không bao giờ thua đua; ngược lại nó chỉ đổi thứ tự
    danh sách nên không để lại dòng nhật ký nào làm 20 lượt kia thành cũ.
    """
    scene = await make_scene(db_session)
    floor = scene.floors[0]
    await make_floor_document(
        db_session, floor_pk=floor.pk, layer=_two_walls(floor.level_id), revision=1, clock=fake_clock
    )
    await db_session.commit()

    async def merge_once() -> WriteResult:
        """Lượt gộp: đảo thứ tự tường, giữ nguyên mọi trường."""
        merge = RecordingMerge(lambda base: base.model_copy(update={"walls": base.walls[::-1]}))
        return await _in_own_session(
            db_sessionmaker,
            lambda session: write(session, floor=floor, actor=scene.owner, clock=fake_clock, merge=merge),
        )

    async def many_writes() -> WriteResult:
        """20 lượt #35 nối đuôi nhau, mỗi lượt đọc lại bản ghi hiện tại làm `baseVersion`."""
        result = None
        for index in range(CONCURRENT_WRITES):
            async with other_session(db_sessionmaker) as session:
                current = await load_document(session, floor.pk)
                assert current is not None
                result = await write(
                    session,
                    floor=floor,
                    actor=scene.owner,
                    clock=fake_clock,
                    base_revision=current.revision,
                    layer=_two_walls(floor.level_id, thickness=200 + index),
                )
                await session.commit()
        assert result is not None
        return result

    outcomes = await race(merge_once, many_writes)

    assert [type(item) for item in outcomes] == [WriteResult, WriteResult]
