"""Ba task tiến trình (`heartbeat`, `metrics`, `log`) và `evaluation_done` (B6-03a [8]).

Postgres, Redis, kho đều **thật** (K23); lõi `run_*` nhận session factory và `Clock` tiêm vào
nên cửa sổ muộn lái được bằng `fake_clock` mà không phải chờ thật. Việc `define_task` phân loại
lỗi là hợp đồng B0-05 (test ở đó); ở đây chỉ kiểm nghiệp vụ của cầu nối.
"""

import logging
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.admin_ml_jobs.settings import reset_training_settings_cache
from apps.worker.training_bridge.tasks import (
    _on_evaluation_failed,
    _on_job_failed,
    dedupe_sha,
    run_record_model_evaluation,
    run_training_heartbeat,
    run_training_log,
    run_training_metrics,
)
from apps.worker.training_bridge.tests._helpers import (
    METRIC,
    heartbeat,
    log_line,
    metric_point,
    metrics,
    ms,
    read_job,
    seed_job,
)
from packages.db.models.admin_ml_jobs import TrainingLogRow, TrainingMetricRow
from packages.messaging.payloads.training import LOG_TEMPLATES, cancel_key
from packages.messaging.redis import safe_redis
from packages.ml_contracts.payloads import EvaluationDonePayload
from packages.testing.factories.admin_ml_registry import make_model_version
from packages.testing.fixtures.clock import FakeClock

pytestmark = pytest.mark.usefixtures("messaging_env")

LATE_WINDOW = timedelta(seconds=600)


def any_template() -> tuple[str, dict[str, str]]:
    """Một khoá mẫu log có thật + tham số đủ — `LOG_TEMPLATES` là hợp đồng của việc B."""
    template, spec = next(iter(LOG_TEMPLATES.items()))
    return template, {name: "x" for name in spec.params}


async def _count(db: AsyncSession, table: type[TrainingMetricRow] | type[TrainingLogRow], job_id: str) -> int:
    """Số dòng tiến trình của một job."""
    return int(await db.scalar(select(func.count()).select_from(table).where(table.job_id == job_id)) or 0)


async def _cancel_armed(job_id: str) -> bool:
    """`cancel_key` của job đã được đặt chưa (tín hiệu dừng của runner)."""
    return await safe_redis().get(cancel_key(job_id)) is not None


# ---------------------------------------------------------------------------
# heartbeat
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_training_heartbeat__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Nhịp tim đầu tiên đưa job `queued` sang `running` và ghi `started_at`, `current_epoch`."""
    job = await seed_job(db_session, status="queued")

    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=2))

    row = await read_job(db_session, job.id)
    assert (row.status, row.current_epoch) == ("running", 2)
    assert row.started_at == fake_clock.now()
    assert row.last_heartbeat_at == fake_clock.now()


@pytest.mark.asyncio
async def test_record_training_heartbeat__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Giao lặp và nhịp cũ tới sau: `current_epoch` chỉ tiến, không bao giờ lùi."""
    job = await seed_job(db_session, status="running", current_epoch=2)

    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=3))
    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=3))
    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=1))

    assert (await read_job(db_session, job.id)).current_epoch == 3


@pytest.mark.asyncio
async def test_heartbeat_out_of_range_epoch_is_ignored(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`epoch` > `epochs` là payload hỏng: không ghi gì."""
    job = await seed_job(db_session, status="running", epochs=3)

    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=4))

    row = await read_job(db_session, job.id)
    assert (row.current_epoch, row.last_heartbeat_at) == (None, None)


@pytest.mark.asyncio
async def test_heartbeat_of_missing_job_is_ignored(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Job không còn → bỏ im lặng, không ngoại lệ (thông điệp mồ côi sau khi job bị xoá)."""
    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat("job_01KB60100000000000000000ZZ"))


@pytest.mark.asyncio
async def test_heartbeat_after_finish_is_ignored_and_arms_cancel_key(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`finished` tới trước, `heartbeat` tới sau → bỏ, và `cancel_key` được đặt lại ([8])."""
    job = await seed_job(db_session, status="failed")

    await run_training_heartbeat(db_sessionmaker, fake_clock, heartbeat(job.id, epoch=1))

    assert (await read_job(db_session, job.id)).current_epoch is None
    assert await _cancel_armed(job.id)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_training_metrics__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Một lô hai điểm hai `split` được ghi đủ, với số đo của họ."""
    job = await seed_job(db_session)
    batch = metrics(
        job.id,
        metric_point(step=0, split="train", loss=0.4),
        metric_point(step=0, split="validation", map50=0.6),
    )

    await run_training_metrics(db_sessionmaker, fake_clock, batch)

    assert await _count(db_session, TrainingMetricRow, job.id) == 2


@pytest.mark.asyncio
async def test_record_training_metrics__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Gửi lại cùng lô: `(job_id, split, step)` chặn, số dòng không đổi."""
    job = await seed_job(db_session)
    batch = metrics(job.id, metric_point(step=5, loss=0.4))

    await run_training_metrics(db_sessionmaker, fake_clock, batch)
    await run_training_metrics(db_sessionmaker, fake_clock, batch)

    assert await _count(db_session, TrainingMetricRow, job.id) == 1


@pytest.mark.asyncio
async def test_record_training_metrics_m05(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """M05: mốc tương lai bị kẹp về `now`, và điểm mang số đo ngoài họ bị bỏ."""
    job = await seed_job(db_session)
    future = ms(fake_clock.now() + timedelta(hours=1))
    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=1, at_ms=future)))
    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=2, iou=0.5)))

    rows = (await db_session.execute(select(TrainingMetricRow).where(TrainingMetricRow.job_id == job.id))).scalars()
    recorded = {row.step: row.recorded_at for row in rows}
    assert list(recorded) == [1]
    assert recorded[1] == fake_clock.now()


@pytest.mark.asyncio
async def test_metrics_with_a_step_behind_the_maximum_are_still_inserted(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Lô lùi bước vẫn chèn (N36 lọc phần chưa đủ `split`), chỉ log `training_metric_late`."""
    job = await seed_job(db_session)
    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=9, loss=0.2)))

    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=4, loss=0.3)))

    assert await _count(db_session, TrainingMetricRow, job.id) == 2


@pytest.mark.asyncio
async def test_metrics_after_finish_inside_the_late_window_are_inserted(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Điểm tới sau khi job chốt, trong cửa sổ muộn → chèn, và `cancel_key` được đặt."""
    job = await seed_job(db_session, status="cancelled")
    assert job.ended_at is not None
    fake_clock.set(job.ended_at + LATE_WINDOW - timedelta(seconds=1))

    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id))

    assert await _count(db_session, TrainingMetricRow, job.id) == 1
    assert await _cancel_armed(job.id)


@pytest.mark.asyncio
async def test_metrics_past_the_late_window_are_dropped(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Quá cửa sổ muộn thì điểm bị bỏ — N36 đã ngừng trả hàng cho job này."""
    job = await seed_job(db_session, status="cancelled")
    assert job.ended_at is not None
    fake_clock.set(job.ended_at + LATE_WINDOW + timedelta(seconds=1))

    await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id))

    assert await _count(db_session, TrainingMetricRow, job.id) == 0


@pytest.mark.asyncio
async def test_metrics_above_the_point_cap_are_dropped(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trần điểm (hạ bằng biến môi trường) đạt rồi thì lô sau bị bỏ."""
    job = await seed_job(db_session)
    monkeypatch.setenv("TRAINING_MAX_METRIC_POINTS", "1")
    reset_training_settings_cache()
    try:
        await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=0, loss=0.1)))
        await run_training_metrics(db_sessionmaker, fake_clock, metrics(job.id, metric_point(step=1, loss=0.1)))
    finally:
        monkeypatch.delenv("TRAINING_MAX_METRIC_POINTS")
        reset_training_settings_cache()

    assert await _count(db_session, TrainingMetricRow, job.id) == 1


@pytest.mark.asyncio
async def test_metrics_stop_at_the_point_cap_in_the_middle_of_a_batch(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lô vượt trần giữa chừng: chèn tới trần rồi bỏ phần dư (review lượt 1, P3 #7).

    Một lô của runner tới 500 điểm, nên kiểm trần **một lần trước vòng lặp** sẽ cho cả lô
    vượt trần rồi mới chặn ở lô sau.
    """
    job = await seed_job(db_session)
    batch = metrics(
        job.id,
        metric_point(step=0, loss=0.1),
        metric_point(step=1, loss=0.2),
        metric_point(step=2, loss=0.3),
    )
    monkeypatch.setenv("TRAINING_MAX_METRIC_POINTS", "2")
    reset_training_settings_cache()
    try:
        await run_training_metrics(db_sessionmaker, fake_clock, batch)
    finally:
        monkeypatch.delenv("TRAINING_MAX_METRIC_POINTS")
        reset_training_settings_cache()

    assert await _count(db_session, TrainingMetricRow, job.id) == 2


@pytest.mark.asyncio
async def test_metrics_of_missing_job_are_ignored(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Lô của một job không còn → bỏ im lặng."""
    await run_training_metrics(db_sessionmaker, fake_clock, metrics("job_01KB60100000000000000000ZZ"))


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_training_log__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Dòng log đầu tiên có `seq = 0`, câu do `render_log` dựng, `dedupe_sha` của payload."""
    job = await seed_job(db_session)
    template, params = any_template()
    payload = log_line(job.id, template=template, params=params)

    await run_training_log(db_sessionmaker, fake_clock, payload)

    row = (await db_session.execute(select(TrainingLogRow).where(TrainingLogRow.job_id == job.id))).scalar_one()
    assert (row.seq, row.level, row.dedupe_sha) == (0, "info", dedupe_sha(payload))
    assert row.message


@pytest.mark.asyncio
async def test_record_training_log__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Gửi lại cùng payload: unique `(job_id, dedupe_sha)` chặn, một dòng duy nhất."""
    job = await seed_job(db_session)
    template, params = any_template()
    payload = log_line(job.id, template=template, params=params)

    await run_training_log(db_sessionmaker, fake_clock, payload)
    await run_training_log(db_sessionmaker, fake_clock, payload)

    assert await _count(db_session, TrainingLogRow, job.id) == 1


@pytest.mark.asyncio
async def test_log_with_an_unknown_template_is_dropped(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`render_log` trả `None` (khoá lạ) → bỏ dòng, không ghi văn bản của runner."""
    job = await seed_job(db_session)

    await run_training_log(db_sessionmaker, fake_clock, log_line(job.id, template="khoa_la_khong_co", params={}))

    assert await _count(db_session, TrainingLogRow, job.id) == 0


@pytest.mark.asyncio
async def test_log_after_finish_follows_the_late_window(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Log tới sau `finished`: trong cửa sổ chèn, quá cửa sổ bỏ."""
    job = await seed_job(db_session, status="cancelled")
    template, params = any_template()
    assert job.ended_at is not None
    fake_clock.set(job.ended_at + LATE_WINDOW - timedelta(seconds=1))
    await run_training_log(db_sessionmaker, fake_clock, log_line(job.id, template=template, params=params))
    fake_clock.advance(timedelta(seconds=2))

    late = log_line(job.id, template=template, params=params, level="error")
    await run_training_log(db_sessionmaker, fake_clock, late)

    assert await _count(db_session, TrainingLogRow, job.id) == 1


@pytest.mark.asyncio
async def test_log_above_the_line_cap_is_dropped(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    db_session: AsyncSession,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trần số dòng log (hạ bằng biến môi trường) đạt rồi thì dòng mới bị bỏ."""
    job = await seed_job(db_session)
    template, params = any_template()
    monkeypatch.setenv("TRAINING_MAX_LOG_LINES", "1")
    reset_training_settings_cache()
    try:
        await run_training_log(db_sessionmaker, fake_clock, log_line(job.id, template=template, params=params))
        await run_training_log(
            db_sessionmaker, fake_clock, log_line(job.id, template=template, params=params, level="warning")
        )
    finally:
        monkeypatch.delenv("TRAINING_MAX_LOG_LINES")
        reset_training_settings_cache()

    assert await _count(db_session, TrainingLogRow, job.id) == 1


@pytest.mark.asyncio
async def test_log_of_missing_job_is_ignored(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock
) -> None:
    """Dòng log của một job không còn → bỏ im lặng."""
    template, params = any_template()
    await run_training_log(
        db_sessionmaker, fake_clock, log_line("job_01KB60100000000000000000ZZ", template=template, params=params)
    )


# ---------------------------------------------------------------------------
# evaluation_done
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_model_evaluation__J01(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """`failed` mang `error_code` đi tới `set_evaluation` và được ghi lên bản model."""
    version = await make_model_version(db_session, family="openingAndFurnitureDetection", status="pending")
    payload = EvaluationDonePayload(version_id=version.id, status="failed", error_code="MODEL_EVAL_FAILED")

    await run_record_model_evaluation(db_sessionmaker, fake_clock, payload)

    await db_session.refresh(version)
    assert (version.evaluation_status, version.evaluation_error_code) == ("failed", "MODEL_EVAL_FAILED")


@pytest.mark.asyncio
async def test_record_model_evaluation__J06(
    db_sessionmaker: async_sessionmaker[AsyncSession], db_session: AsyncSession, fake_clock: FakeClock
) -> None:
    """Giao lặp `completed`: kết quả là bất biến, lượt sau trả `False` và không đổi số đo."""
    version = await make_model_version(db_session, family="openingAndFurnitureDetection", status="pending")
    payload = EvaluationDonePayload(version_id=version.id, status="completed", metrics={METRIC: 0.8})

    await run_record_model_evaluation(db_sessionmaker, fake_clock, payload)
    await run_record_model_evaluation(db_sessionmaker, fake_clock, payload)

    await db_session.refresh(version)
    assert (version.evaluation_status, version.metrics) == ("completed", {METRIC: 0.8})


@pytest.mark.asyncio
async def test_record_model_evaluation_of_missing_version_logs_info(
    db_sessionmaker: async_sessionmaker[AsyncSession], fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    """`set_evaluation` trả `False` là bình thường (lịch B6-01 gửi lại) → log mức `info`, không lỗi."""
    missing = "mdl_01KB60100000000000000000ZZ"
    payload = EvaluationDonePayload(version_id=missing, status="failed", error_code="BOOM_CODE")

    with caplog.at_level(logging.INFO):
        await run_record_model_evaluation(db_sessionmaker, fake_clock, payload)

    assert [record.levelno for record in caplog.records if record.message == "training_evaluation_skipped"] == [
        logging.INFO
    ]


# ---------------------------------------------------------------------------
# on_failed
# ---------------------------------------------------------------------------


def test_on_failed_hooks_only_log(caplog: pytest.LogCaptureFixture) -> None:
    """`on_failed` của cầu nối chỉ log: không ghi `training_logs`, không văn bản ngoại lệ thô ([9])."""
    with caplog.at_level(logging.ERROR):
        _on_job_failed(heartbeat("job_01KB60100000000000000000ZZ"), "INTERNAL")
        _on_evaluation_failed(
            EvaluationDonePayload(version_id="mdl_01KB60100000000000000000ZZ", status="completed", metrics={METRIC: 1}),
            "INTERNAL",
        )

    assert [record.message for record in caplog.records] == [
        "training_bridge_task_failed",
        "training_bridge_evaluation_failed",
    ]
