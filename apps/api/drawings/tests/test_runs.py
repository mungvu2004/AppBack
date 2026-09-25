"""`start_run`, `record_step`, `lock_run` — mục "`Progress`" của B2-04 [8].

Postgres và Redis thật (K23). Test nào cần tác dụng **sau commit** (stream, hàng đợi) thì
tự mở session từ `db_sessionmaker` và `commit`; các test còn lại dùng `db_session` và không
commit, nên `on_after_commit` không chạy và không cần Redis.
"""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Final

import pytest
import pytest_asyncio
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.drawings.errors import FLOOR_DELETED
from apps.api.drawings.runs import fail_run, lock_run, record_step, start_run
from apps.api.drawings.tests._helpers import Scene, make_scene, read_run, sync_bus_reset
from apps.api.floors.settings import get_floors_settings
from apps.api.projects.summaries import unregister_floor
from packages.core.pipeline import PipelineCode
from packages.db.hooks import after_commit_idle
from packages.db.models.drawings import PipelineRunRow, UploadRow
from packages.db.models.projects import ProjectFloorSummary
from packages.messaging.redis import broker_redis_sync
from packages.messaging.streams import upload_stream
from packages.testing.factories.drawings import make_upload
from packages.testing.factories.floors import make_floor
from packages.testing.fixtures.clock import FakeClock
from packages.testing.fixtures.messaging import queued_payloads

PIPELINE_QUEUE: Final = "pipeline.cpu"
SUPERSEDED: Final = PipelineCode.PIPELINE_SUPERSEDED.value

__all__ = ["sync_bus_reset"]  # fixture nhập từ `_helpers`, pytest tìm theo tên trong module này


async def _complete_upload(db: AsyncSession, scene: Scene) -> UploadRow:
    """Lượt tải đã `complete` nhưng **không** có object nào — đủ cho mọi test của lượt chạy."""
    return await make_upload(db, project=scene.project, floor=scene.floor, status="complete")


async def _started_run(db: AsyncSession, clock: FakeClock) -> tuple[Scene, PipelineRunRow]:
    """Sân khấu + một lượt chạy `pending` vừa mở."""
    scene = await make_scene(db)
    upload = await _complete_upload(db, scene)
    row = await start_run(db, upload_id=upload.id, clock=clock)
    return scene, await read_run(db, row.id)


async def _summary(db: AsyncSession, scene: Scene) -> ProjectFloorSummary:
    """Dòng đếm của tầng, `refresh` sau khi `set_upload_state` ghi bằng một câu `UPDATE` thô."""
    stmt = select(ProjectFloorSummary).where(
        ProjectFloorSummary.project_id == scene.project.id,
        ProjectFloorSummary.floor_level_id == scene.floor.level_id,
    )
    row = (await db.execute(stmt)).scalar_one()
    await db.refresh(row)
    return row


@pytest_asyncio.fixture(loop_scope="function")
async def committing_db(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Session mà test tự `commit` — để callback sau commit thật sự chạy (J09, S08)."""
    async with db_sessionmaker() as session:
        yield session


# ---------------------------------------------------------------------------
# start_run
# ---------------------------------------------------------------------------


async def test_start_run_opens_a_pending_run_at_the_first_step(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt mới luôn bắt đầu ở `pending`/`preprocess`/0 và dòng đếm của tầng theo ngay."""
    scene, run = await _started_run(db_session, fake_clock)
    assert (run.status, run.current_step, run.progress_percent) == ("pending", "preprocess", 0)
    summary = await _summary(db_session, scene)
    assert (summary.has_upload, summary.pipeline_state) == (True, "pending")


async def test_start_run_supersedes_the_previous_live_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Tải lại cùng tầng: lượt cũ thành `failed` `PIPELINE_SUPERSEDED`, trỏ tới lượt mới."""
    scene, first = await _started_run(db_session, fake_clock)
    second_upload = await _complete_upload(db_session, scene)
    second = await start_run(db_session, upload_id=second_upload.id, clock=fake_clock)

    old = await read_run(db_session, first.id)
    assert (old.status, old.error_code, old.superseded_by) == ("failed", SUPERSEDED, second.id)
    assert old.ended_at is None


async def test_start_run_rejects_unknown_upload(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Không có dòng upload là lỗi lập trình: #7 đã tra nó dưới khoá trước khi gọi."""
    with pytest.raises(ValueError, match="không có lượt tải"):
        await start_run(db_session, upload_id="upl_00000000000000000000000000", clock=fake_clock)


async def test_start_run_publishes_progress_and_expires_the_superseded_stream(
    committing_db: AsyncSession,
    streams_client: AsyncRedis,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Lượt bị thay phát một khung `failed` rồi stream của nó được hẹn giờ xoá (BE-00 §7)."""
    scene = await make_scene(committing_db)
    first_upload = await _complete_upload(committing_db, scene)
    await start_run(committing_db, upload_id=first_upload.id, clock=fake_clock)
    await committing_db.commit()
    await after_commit_idle(committing_db)

    second_upload = await _complete_upload(committing_db, scene)
    await start_run(committing_db, upload_id=second_upload.id, clock=fake_clock)
    await committing_db.commit()
    await after_commit_idle(committing_db)

    stream = upload_stream(first_upload.id)
    events = await streams_client.xrange(stream)
    assert events is not None
    assert len(events) == 2, events
    ttl = await streams_client.ttl(stream)
    assert isinstance(ttl, int)
    assert ttl > 0


async def test_start_run_queues_nothing_when_the_transaction_rolls_back(
    committing_db: AsyncSession,
    messaging_env: None,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """J09: `pipeline.orchestrate.start` chỉ rời tiến trình sau commit; rollback → hàng rỗng."""
    broker = broker_redis_sync()
    broker.delete(PIPELINE_QUEUE)
    scene = await make_scene(committing_db)
    upload = await _complete_upload(committing_db, scene)
    await start_run(committing_db, upload_id=upload.id, clock=fake_clock)
    await committing_db.rollback()
    await after_commit_idle(committing_db)

    assert queued_payloads(broker, PIPELINE_QUEUE) == []
    broker.close()


async def test_start_run_queues_the_payload_after_commit(
    committing_db: AsyncSession,
    messaging_env: None,
    fake_clock: FakeClock,
    sync_bus_reset: None,
) -> None:
    """Commit xong thì đúng **một** thông điệp mang `run_id` và `upload_id` của lượt vừa mở."""
    broker = broker_redis_sync()
    broker.delete(PIPELINE_QUEUE)
    scene = await make_scene(committing_db)
    upload = await _complete_upload(committing_db, scene)
    run = await start_run(committing_db, upload_id=upload.id, clock=fake_clock)
    await committing_db.commit()
    await after_commit_idle(committing_db)

    assert queued_payloads(broker, PIPELINE_QUEUE) == [{"schema_version": 1, "run_id": run.id, "upload_id": upload.id}]
    broker.close()


# ---------------------------------------------------------------------------
# record_step — đối số sai
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("step", "status", "error_code"),
    [
        ("quality_check", "running", None),
        ("preprocess", "done", None),
        ("preprocess", "failed", None),
        ("preprocess", "failed", "khong phai upper snake"),
    ],
)
async def test_record_step_rejects_bad_arguments(
    db_session: AsyncSession, fake_clock: FakeClock, step: str, status: str, error_code: str | None
) -> None:
    """Bước lạ, `status` lạ, `failed` thiếu mã UPPER_SNAKE → `ValueError` trước khi chạm DB."""
    _, run = await _started_run(db_session, fake_clock)
    with pytest.raises(ValueError, match=r"lạ|UPPER_SNAKE"):
        await record_step(db_session, run_id=run.id, step=step, status=status, clock=fake_clock, error_code=error_code)


async def test_record_step_ignores_unknown_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt đã bị lịch dọn xoá: kết quả tới muộn rơi im lặng, không ném."""
    result = await record_step(
        db_session, run_id="run_00000000000000000000000000", step="preprocess", status="running", clock=fake_clock
    )
    assert result is None


# ---------------------------------------------------------------------------
# record_step — đường thường
# ---------------------------------------------------------------------------


async def test_record_step_running_then_completed_moves_forward(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`running` mở lượt ở phần trăm của các bước **trước**; `completed` đẩy sang bước kế."""
    _, run = await _started_run(db_session, fake_clock)
    first = await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock)
    assert first == {
        "id": run.upload_id,
        "status": "running",
        "step": "preprocess",
        "progressPercent": 0,
        "startedAt": "2026-01-01T00:00:00.000Z",
    }

    fake_clock.advance(timedelta(minutes=1))
    second = await record_step(db_session, run_id=run.id, step="preprocess", status="completed", clock=fake_clock)
    assert second is not None
    assert second["progressPercent"] == 5
    assert second["step"] == "wallSegmentation"
    assert (await read_run(db_session, run.id)).started_at is not None


async def test_record_step_last_step_completes_the_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bước cuối xong → lượt `completed`, 100, có `endedAt`; dòng đếm sang `completed`."""
    scene, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="qualityCheck", status="running", clock=fake_clock)
    wire = await record_step(db_session, run_id=run.id, step="qualityCheck", status="completed", clock=fake_clock)

    assert wire is not None
    assert wire["status"] == "completed"
    assert wire["progressPercent"] == 100
    assert "endedAt" in wire
    assert (await _summary(db_session, scene)).pipeline_state == "completed"


async def test_record_step_percent_never_goes_backwards(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Bước sau chạy trước rồi bước trước mới xong: phần trăm giữ giá trị lớn hơn."""
    _, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="dimensionReading", status="running", clock=fake_clock)
    assert (await read_run(db_session, run.id)).progress_percent == 55

    wire = await record_step(db_session, run_id=run.id, step="dimensionReading", status="completed", clock=fake_clock)
    assert wire is not None
    assert wire["progressPercent"] == 70


async def test_record_step_failed_keeps_percent_and_has_no_ended_at(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Lượt hỏng giữ phần trăm cuối, mang mã lỗi, **không** `endedAt` (K33)."""
    scene, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="wallSegmentation", status="running", clock=fake_clock)
    wire = await record_step(
        db_session,
        run_id=run.id,
        step="wallSegmentation",
        status="failed",
        clock=fake_clock,
        error_code="IMAGE_TOO_LARGE",
    )

    assert wire is not None
    assert wire["status"] == "failed"
    assert wire["error"] == "IMAGE_TOO_LARGE"
    assert "endedAt" not in wire
    assert (await read_run(db_session, run.id)).ended_at is None
    assert (await _summary(db_session, scene)).pipeline_state == "failed"


# ---------------------------------------------------------------------------
# record_step — giao muộn, giao lặp
# ---------------------------------------------------------------------------


async def test_record_step_ignores_a_step_behind_the_current_one(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Bước lùi (J06) không được phép ghi đè tiến độ đang có."""
    _, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="spatialDataBuild", status="running", clock=fake_clock)
    assert await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock) is None


async def test_record_step_ignores_a_duplicate_delivery(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Giao lặp cùng bước, cùng trạng thái: lượt thứ hai không đổi gì nên trả `None`."""
    _, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock)
    assert await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock) is None


async def test_record_step_ignores_a_superseded_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Kết quả của lượt đã bị thay bị bỏ, dù bước và trạng thái đều hợp lệ."""
    scene, first = await _started_run(db_session, fake_clock)
    second_upload = await _complete_upload(db_session, scene)
    await start_run(db_session, upload_id=second_upload.id, clock=fake_clock)

    assert await record_step(db_session, run_id=first.id, step="preprocess", status="running", clock=fake_clock) is None


# ---------------------------------------------------------------------------
# record_step — xoá mềm
# ---------------------------------------------------------------------------


async def test_record_step_writes_like_a_live_floor_inside_the_restore_window(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng vừa gỡ mà còn trong cửa sổ khôi phục: ghi bình thường (A8, BE-00 §7)."""
    scene, run = await _started_run(db_session, fake_clock)
    scene.floor.deleted_at = fake_clock.now()
    await unregister_floor(db_session, project_id=scene.project.id, floor_level_id=scene.floor.level_id)
    await db_session.flush()

    wire = await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock)
    assert wire is not None
    assert wire["status"] == "running"


async def test_record_step_fails_the_run_when_the_floor_is_gone_for_good(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Quá cửa sổ khôi phục → lượt `failed` `FLOOR_DELETED`, dòng đếm ẩn vẫn nhận `failed`."""
    scene, run = await _started_run(db_session, fake_clock)
    scene.floor.deleted_at = fake_clock.now()
    await unregister_floor(db_session, project_id=scene.project.id, floor_level_id=scene.floor.level_id)
    await db_session.flush()
    fake_clock.advance(timedelta(seconds=get_floors_settings().floor_restore_window_s + 1))

    assert await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock) is None
    stored = await read_run(db_session, run.id)
    assert (stored.status, stored.error_code, stored.ended_at) == ("failed", FLOOR_DELETED, None)
    summary = await _summary(db_session, scene)
    assert (summary.hidden, summary.pipeline_state) == (True, "failed")


async def test_record_step_leaves_the_counts_of_a_recreated_floor_alone(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Tầng tạo lại cùng `level_id` dùng chung dòng đếm — lượt của tầng cũ không được đè lên."""
    scene, run = await _started_run(db_session, fake_clock)
    scene.floor.deleted_at = fake_clock.now()
    await unregister_floor(db_session, project_id=scene.project.id, floor_level_id=scene.floor.level_id)
    await db_session.flush()
    fake_clock.advance(timedelta(seconds=get_floors_settings().floor_restore_window_s + 1))
    await make_floor(db_session, project=scene.project, level_id=scene.floor.level_id)

    assert await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock) is None
    assert (await read_run(db_session, run.id)).status == "failed"
    summary = await _summary(db_session, scene)
    assert (summary.hidden, summary.pipeline_state) == (False, "none")


async def test_record_step_fails_the_run_when_the_project_is_soft_deleted(
    db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dự án xoá mềm không có cửa sổ chờ: lượt hỏng ngay (BE-00 §7)."""
    scene, run = await _started_run(db_session, fake_clock)
    scene.project.deleted_at = fake_clock.now()
    await db_session.flush()

    assert await record_step(db_session, run_id=run.id, step="preprocess", status="running", clock=fake_clock) is None
    assert (await read_run(db_session, run.id)).error_code == FLOOR_DELETED


# ---------------------------------------------------------------------------
# lock_run
# ---------------------------------------------------------------------------


async def test_lock_run_returns_the_live_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt còn sống: ảnh chụp đông cứng đủ cho người gọi kiểm `upload_id` và bước."""
    _, run = await _started_run(db_session, fake_clock)
    locked = await lock_run(db_session, run_id=run.id)
    assert locked is not None
    assert (locked.id, locked.status, locked.superseded_by) == (run.id, "pending", None)


async def test_lock_run_returns_none_for_a_finished_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt đã xong không nhận thêm kết quả nào."""
    _, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="qualityCheck", status="completed", clock=fake_clock)
    assert await lock_run(db_session, run_id=run.id) is None


async def test_lock_run_returns_none_for_a_superseded_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt bị thay cũng bị từ chối, dù nó chưa kịp chạy bước nào."""
    scene, first = await _started_run(db_session, fake_clock)
    second_upload = await _complete_upload(db_session, scene)
    await start_run(db_session, upload_id=second_upload.id, clock=fake_clock)
    assert await lock_run(db_session, run_id=first.id) is None


async def test_lock_run_returns_none_for_an_unknown_run(db_session: AsyncSession) -> None:
    """Id lạ trả `None`, không ném — worker giao muộn không làm hỏng giao dịch của ai."""
    assert await lock_run(db_session, run_id="run_00000000000000000000000000") is None


# ---------------------------------------------------------------------------
# fail_run (lõi quét bù)
# ---------------------------------------------------------------------------


async def test_fail_run_marks_a_live_run_without_ended_at(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Hết trần quét bù: lượt `failed` `PIPELINE_STALLED`, dòng đếm theo, không `endedAt`."""
    scene, run = await _started_run(db_session, fake_clock)
    assert await fail_run(db_session, run_id=run.id, error_code="PIPELINE_STALLED", clock=fake_clock) is True
    stored = await read_run(db_session, run.id)
    assert (stored.status, stored.error_code, stored.ended_at) == ("failed", "PIPELINE_STALLED", None)
    assert (await _summary(db_session, scene)).pipeline_state == "failed"


async def test_fail_run_skips_a_run_that_already_ended(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Lượt đã kết thúc không bị ghi đè — quét bù chạy song song với worker cũng an toàn."""
    _, run = await _started_run(db_session, fake_clock)
    await record_step(db_session, run_id=run.id, step="qualityCheck", status="completed", clock=fake_clock)
    assert await fail_run(db_session, run_id=run.id, error_code="PIPELINE_STALLED", clock=fake_clock) is False
    assert (await read_run(db_session, run.id)).status == "completed"


async def test_fail_run_ignores_an_unknown_run(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Id lạ trả `False`, không ném."""
    unknown = "run_00000000000000000000000000"
    assert await fail_run(db_session, run_id=unknown, error_code="PIPELINE_STALLED", clock=fake_clock) is False


async def test_fail_run_rejects_a_non_upper_snake_code(db_session: AsyncSession, fake_clock: FakeClock) -> None:
    """Mã lỗi sai mẫu là lỗi lập trình: `error` của `Progress` luôn UPPER_SNAKE (BE-BIND §4)."""
    _, run = await _started_run(db_session, fake_clock)
    with pytest.raises(ValueError, match="UPPER_SNAKE"):
        await fail_run(db_session, run_id=run.id, error_code="stalled", clock=fake_clock)
