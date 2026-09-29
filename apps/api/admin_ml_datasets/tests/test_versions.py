"""Bốn hàm của `versions.py` (B6-02 [2], [9]): Postgres thật (K23), không HTTP.

`test_start_version__C14` là ca của khối [8]: hai lượt gọi song song (hai session thật)
cho cùng dataset → đúng một dòng `building`, không hai.
"""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_datasets.versions import fail_version, finish_version, start_version, touch_version
from packages.db.models.admin_ml_datasets import DatasetVersionRow
from packages.testing.factories.admin_ml_datasets import make_dataset, make_dataset_version
from packages.testing.fixtures.clock import FakeClock

SPLIT_COUNTS = {"train": 8, "validation": 1, "test": 1}
MANIFEST = "a" * 64


async def _building_count(sessionmaker: async_sessionmaker[AsyncSession], dataset_id: str) -> int:
    async with sessionmaker() as db:
        stmt = (
            select(func.count())
            .select_from(DatasetVersionRow)
            .where(DatasetVersionRow.dataset_id == dataset_id, DatasetVersionRow.status == "building")
        )
        return (await db.execute(stmt)).scalar_one()


async def _start(
    db: AsyncSession, *, dataset_id: str, clock: FakeClock, created_by: str, project_ids: list[str] | None = None
) -> DatasetVersionRow | None:
    return await start_version(
        db, dataset_id=dataset_id, source="approvedFloors", project_ids=project_ids, created_by=created_by, clock=clock
    )


async def _start_and_commit(
    sessionmaker: async_sessionmaker[AsyncSession], *, dataset_id: str, clock: FakeClock, created_by: str
) -> DatasetVersionRow | None:
    async with sessionmaker() as db:
        row = await _start(db, dataset_id=dataset_id, clock=clock, created_by=created_by)
        await db.commit()
        return row


# ---------------------------------------------------------------------------
# start_version
# ---------------------------------------------------------------------------


async def test_start_version__sequence_increments(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bản đầu `sequence=1`; sau khi bản đó `ready`, bản kế `sequence=2`."""
    dataset = await make_dataset(db_session, family="wallSegmentation")

    first = await _start(db_session, dataset_id=dataset.id, clock=fake_clock, created_by="usr_a")
    assert first is not None
    assert first.sequence == 1
    assert first.status == "building"
    await db_session.commit()
    assert await finish_version(
        db_session, version_id=first.id, manifest_sha256=MANIFEST, split_counts=SPLIT_COUNTS, clock=fake_clock
    )
    await db_session.commit()

    second = await _start(
        db_session, dataset_id=dataset.id, clock=fake_clock, created_by="usr_a", project_ids=["prj_a"]
    )
    assert second is not None
    assert second.sequence == 2
    assert second.project_ids == ["prj_a"]


async def test_start_version__none_when_already_building(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Cùng session: gọi lần hai trong khi bản đầu còn `building` → `None`, không tạo dòng thứ hai."""
    dataset = await make_dataset(db_session, family="wallSegmentation")
    first = await _start(db_session, dataset_id=dataset.id, clock=fake_clock, created_by="usr_a")
    assert first is not None

    second = await _start(db_session, dataset_id=dataset.id, clock=fake_clock, created_by="usr_b")

    assert second is None


async def test_start_version__dataset_missing_is_value_error(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Dataset không tồn tại là lỗi của người gọi (N31 đã kiểm 404 trước khi gọi), không `None`."""
    with pytest.raises(ValueError, match="dataset không tồn tại"):
        await _start(db_session, dataset_id="dst_MISSING", clock=fake_clock, created_by="usr_a")


async def test_start_version__C14(db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock) -> None:
    """Hai `start_version` song song (hai session Postgres thật) → đúng một dòng `building`."""
    async with db_sessionmaker() as db:
        dataset = await make_dataset(db, family="wallSegmentation")

    results = await asyncio.gather(
        _start_and_commit(db_sessionmaker, dataset_id=dataset.id, clock=fake_clock, created_by="usr_a"),
        _start_and_commit(db_sessionmaker, dataset_id=dataset.id, clock=fake_clock, created_by="usr_b"),
    )

    winners = [row for row in results if row is not None]
    losers = [row for row in results if row is None]
    print(f"C14 start_version: winners={len(winners)}, losers={len(losers)}")
    assert len(winners) == 1
    assert len(losers) == 1
    assert await _building_count(db_sessionmaker, dataset.id) == 1


# ---------------------------------------------------------------------------
# touch_version / finish_version / fail_version
# ---------------------------------------------------------------------------


async def test_touch_finish_fail__building_true_else_false(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """`touch`/`finish`/`fail` trên `building` → `True`; lặp lại trên bản đã kết thúc → `False`."""
    dataset = await make_dataset(db_session, family="wallSegmentation")
    version = await make_dataset_version(db_session, dataset=dataset, status="building")

    assert await touch_version(db_session, version_id=version.id, clock=fake_clock)
    assert await finish_version(
        db_session, version_id=version.id, manifest_sha256=MANIFEST, split_counts=SPLIT_COUNTS, clock=fake_clock
    )

    # Bản đã `ready`: mọi hàm ghi tiếp trả `False`, không sửa bản `ready` ([9]).
    assert not await touch_version(db_session, version_id=version.id, clock=fake_clock)
    assert not await finish_version(
        db_session, version_id=version.id, manifest_sha256=MANIFEST, split_counts=SPLIT_COUNTS, clock=fake_clock
    )
    assert not await fail_version(db_session, version_id=version.id, failure_code="DATASET_EMPTY", clock=fake_clock)


async def test_fail_version__building_to_failed(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    dataset = await make_dataset(db_session, family="wallSegmentation")
    version = await make_dataset_version(db_session, dataset=dataset, status="building")

    assert await fail_version(db_session, version_id=version.id, failure_code="DATASET_EMPTY", clock=fake_clock)
    await db_session.commit()
    await db_session.refresh(version)
    assert version.status == "failed"
    assert version.failure_code == "DATASET_EMPTY"

    # Đã `failed`: gọi lại không đổi gì.
    assert not await fail_version(db_session, version_id=version.id, failure_code="DATASET_TOO_LARGE", clock=fake_clock)


async def test_touch_version__unknown_id_is_false(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    assert not await touch_version(db_session, version_id="dsv_MISSING", clock=fake_clock)


# ---------------------------------------------------------------------------
# CHECK của DB (lưới an toàn cuối, phòng khi mã nghiệp vụ lệch)
# ---------------------------------------------------------------------------


async def test_check_ready_requires_manifest_and_split_counts(db_session: AsyncSession) -> None:
    dataset = await make_dataset(db_session, family="wallSegmentation")
    row = DatasetVersionRow(
        id="dsv_01ARZ3NDEKTSV4RRFFQ69G5FAV",
        dataset_id=dataset.id,
        sequence=1,
        status="ready",
        source="approvedFloors",
        created_by="usr_a",
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_check_failed_requires_failure_code_format(db_session: AsyncSession) -> None:
    dataset = await make_dataset(db_session, family="wallSegmentation")
    row = DatasetVersionRow(
        id="dsv_01ARZ3NDEKTSV4RRFFQ69G5FAW",
        dataset_id=dataset.id,
        sequence=1,
        status="failed",
        source="approvedFloors",
        failure_code="lowercase-not-allowed",
        created_by="usr_a",
    )
    db_session.add(row)
    with pytest.raises(IntegrityError):
        await db_session.flush()
