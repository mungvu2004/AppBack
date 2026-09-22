"""Test `record_activity` (B1-02 [6], [8]): giao dịch của người gọi, kiểm trước khi ghi (C18)."""

import unicodedata
from typing import Final

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.access.activity import SYSTEM_PIPELINE, record_activity
from apps.api.access.kinds import ActivityKind
from packages.core.ids import new_id
from packages.db.models.access import OBJECT_CODE_MAX, ActivityLog
from packages.testing.factories.auth import make_user
from packages.testing.fixtures.access import activity_rows, assert_one_activity
from packages.testing.fixtures.clock import FakeClock

_OTHER_PREFIX_ID: Final = "prj_" + "0" * 26


async def _count(sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Số dòng `activity_log` hiện có, đọc trên session mới."""
    async with sessionmaker() as session:
        return int((await session.execute(select(func.count()).select_from(ActivityLog))).scalar_one())


async def test_record_activity_writes_all_columns_with_project_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Ghi đúng mọi cột, `at` theo `fake_clock`, `project_id` có giá trị."""
    user = await make_user(db_session)
    project_id = new_id("prj", fake_clock)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.PROJECT_CREATE,
        object_code="prj_test",
        object_label="Dự án thử",
        clock=fake_clock,
        project_id=project_id,
    )
    await db_session.commit()
    row = await assert_one_activity(
        db_sessionmaker, actor_id=user.id, kind=ActivityKind.PROJECT_CREATE, object_code="prj_test"
    )
    assert row.object_label == "Dự án thử"
    assert row.project_id == project_id
    assert row.at == fake_clock.now()


async def test_record_activity_project_id_defaults_to_none(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`project_id` không truyền → lưu `NULL`."""
    user = await make_user(db_session)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.USER_DISABLE,
        object_code=user.id,
        object_label=user.email,
        clock=fake_clock,
    )
    await db_session.commit()
    row = await assert_one_activity(
        db_sessionmaker, actor_id=user.id, kind=ActivityKind.USER_DISABLE, object_code=user.id
    )
    assert row.project_id is None


async def test_record_activity_accepts_system_pipeline(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`SYSTEM_PIPELINE` là `actor_id` hợp lệ cho việc chạy nền."""
    await record_activity(
        db_session,
        actor_id=SYSTEM_PIPELINE,
        kind=ActivityKind.TRAINING_CANCEL,
        object_code="job_abc",
        object_label="Model A",
        clock=fake_clock,
    )
    await db_session.commit()
    await assert_one_activity(
        db_sessionmaker, actor_id=SYSTEM_PIPELINE, kind=ActivityKind.TRAINING_CANCEL, object_code="job_abc"
    )


async def test_record_activity_rollback_leaves_no_row(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Rollback của người gọi xoá cả dòng chưa commit (C18)."""
    user = await make_user(db_session)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.PROJECT_DELETE,
        object_code="prj_x",
        object_label="Dự án X",
        clock=fake_clock,
    )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


@pytest.mark.parametrize(
    "actor_id",
    ["usr_" + "!" * 26, _OTHER_PREFIX_ID, ""],
    ids=["garbage-body", "wrong-prefix", "empty"],
)
async def test_record_activity_rejects_bad_actor_id(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, actor_id: str
) -> None:
    """`actor_id` sai mẫu (rác, tiền tố khác, rỗng) → `ValueError`, không dòng nào được ghi."""
    with pytest.raises(ValueError, match="actor_id"):
        await record_activity(
            db_session,
            actor_id=actor_id,
            kind=ActivityKind.PROJECT_CREATE,
            object_code="prj_x",
            object_label="Dự án X",
            clock=fake_clock,
        )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


@pytest.mark.parametrize(
    "project_id",
    ["rác", "", "prj_123", "usr_" + "0" * 26],
    ids=["garbage-body", "empty", "too-short", "wrong-prefix"],
)
async def test_record_activity_rejects_bad_project_id(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    project_id: str,
) -> None:
    """`project_id` sai mẫu (rác, rỗng, thiếu ULID, tiền tố khác) → `ValueError`, không dòng nào được ghi."""
    user_id = new_id("usr", fake_clock)
    with pytest.raises(ValueError, match="project_id"):
        await record_activity(
            db_session,
            actor_id=user_id,
            kind=ActivityKind.PROJECT_CREATE,
            object_code="prj_x",
            object_label="Dự án X",
            clock=fake_clock,
            project_id=project_id,
        )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


async def test_record_activity_rejects_lowercase_string_kind(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Chuỗi thường trùng giá trị enum vẫn bị từ chối: phải truyền đúng thành viên `ActivityKind`."""
    user_id = new_id("usr", fake_clock)
    with pytest.raises(ValueError, match="kind"):
        await record_activity(
            db_session,
            actor_id=user_id,
            kind="floor.upload",  # type: ignore[arg-type]  # cố tình sai kiểu để thử CHECK
            object_code="L-1",
            object_label="Tầng 1",
            clock=fake_clock,
        )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


@pytest.mark.parametrize(
    "object_label",
    ["", "   ", "a" * 201],
    ids=["empty", "whitespace-only", "too-long"],
)
async def test_record_activity_rejects_bad_object_label(
    db_session: AsyncSession,
    db_sessionmaker: async_sessionmaker[AsyncSession],
    fake_clock: FakeClock,
    object_label: str,
) -> None:
    """`object_label` rỗng, chỉ khoảng trắng, hoặc 201 ký tự → `ValueError`, không dòng nào được ghi."""
    user_id = new_id("usr", fake_clock)
    with pytest.raises(ValueError, match="object_label"):
        await record_activity(
            db_session,
            actor_id=user_id,
            kind=ActivityKind.FLOOR_CREATE,
            object_code="L-1",
            object_label=object_label,
            clock=fake_clock,
        )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


async def test_record_activity_allows_object_label_at_max_length(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`object_label` đúng 200 ký tự (trần) vẫn được chấp nhận."""
    user_id = new_id("usr", fake_clock)
    label = "a" * 200
    await record_activity(
        db_session,
        actor_id=user_id,
        kind=ActivityKind.FLOOR_CREATE,
        object_code="L-1",
        object_label=label,
        clock=fake_clock,
    )
    await db_session.commit()
    row = await assert_one_activity(
        db_sessionmaker, actor_id=user_id, kind=ActivityKind.FLOOR_CREATE, object_code="L-1"
    )
    assert row.object_label == label


async def test_record_activity_rejects_object_code_too_long(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`object_code` 121 ký tự (quá `OBJECT_CODE_MAX`) → `ValueError`, không dòng nào được ghi."""
    user_id = new_id("usr", fake_clock)
    with pytest.raises(ValueError, match="object_code"):
        await record_activity(
            db_session,
            actor_id=user_id,
            kind=ActivityKind.FLOOR_CREATE,
            object_code="a" * (OBJECT_CODE_MAX + 1),
            object_label="Tầng 1",
            clock=fake_clock,
        )
    await db_session.rollback()
    assert await _count(db_sessionmaker) == 0


async def test_record_activity_normalizes_object_label_to_nfc(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """`object_label` dạng NFD (dấu tách rời) được lưu dưới dạng NFC."""
    user_id = new_id("usr", fake_clock)
    composed = "Tầng 1"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed  # tự kiểm: mẫu thử thật sự tách dấu
    await record_activity(
        db_session,
        actor_id=user_id,
        kind=ActivityKind.FLOOR_CREATE,
        object_code="L-1",
        object_label=decomposed,
        clock=fake_clock,
    )
    await db_session.commit()
    row = await assert_one_activity(
        db_sessionmaker, actor_id=user_id, kind=ActivityKind.FLOOR_CREATE, object_code="L-1"
    )
    assert row.object_label == composed


async def test_activity_rows_reads_all_rows_without_filters(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Không lọc `actor_id`/`kind` → trả mọi dòng đã commit."""
    user = await make_user(db_session)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.PROJECT_CREATE,
        object_code="prj_all",
        object_label="Dự án A",
        clock=fake_clock,
    )
    await db_session.commit()
    rows = await activity_rows(db_sessionmaker)
    assert any(row.object_code == "prj_all" for row in rows)


async def test_activity_rows_filters_by_actor_id_only(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lọc theo `actor_id`, không lọc `kind` → chỉ trả dòng của actor đó, mọi kind."""
    user = await make_user(db_session)
    other = await make_user(db_session)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.PROJECT_CREATE,
        object_code="prj_1",
        object_label="Dự án 1",
        clock=fake_clock,
    )
    await record_activity(
        db_session,
        actor_id=other.id,
        kind=ActivityKind.PROJECT_CREATE,
        object_code="prj_2",
        object_label="Dự án 2",
        clock=fake_clock,
    )
    await db_session.commit()
    rows = await activity_rows(db_sessionmaker, actor_id=user.id)
    assert {row.actor_id for row in rows} == {user.id}


async def test_activity_rows_filters_by_kind_only(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lọc theo `kind`, không lọc `actor_id` → trả mọi actor có `kind` đó."""
    user = await make_user(db_session)
    await record_activity(
        db_session,
        actor_id=user.id,
        kind=ActivityKind.PROJECT_UPDATE,
        object_code="prj_upd",
        object_label="Cập nhật",
        clock=fake_clock,
    )
    await db_session.commit()
    rows = await activity_rows(db_sessionmaker, kind=ActivityKind.PROJECT_UPDATE)
    assert {row.kind for row in rows} == {ActivityKind.PROJECT_UPDATE.value}


async def test_assert_one_activity_fails_when_no_rows_match(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Không dòng nào khớp → `AssertionError` nêu số dòng thấy (0)."""
    with pytest.raises(AssertionError, match="thấy 0"):
        await assert_one_activity(
            db_sessionmaker, actor_id=new_id("usr", fake_clock), kind=ActivityKind.PROJECT_CREATE, object_code="prj_x"
        )


async def test_assert_one_activity_fails_when_two_rows_match(
    db_session: AsyncSession, db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Hai dòng cùng khớp `(actor_id, kind, object_code)` → `AssertionError` liệt kê cả hai."""
    user_id = new_id("usr", fake_clock)
    for _ in range(2):
        await record_activity(
            db_session,
            actor_id=user_id,
            kind=ActivityKind.PROJECT_CREATE,
            object_code="prj_dup",
            object_label="Dự án trùng",
            clock=fake_clock,
        )
    await db_session.commit()
    with pytest.raises(AssertionError, match="thấy 2"):
        await assert_one_activity(
            db_sessionmaker, actor_id=user_id, kind=ActivityKind.PROJECT_CREATE, object_code="prj_dup"
        )
