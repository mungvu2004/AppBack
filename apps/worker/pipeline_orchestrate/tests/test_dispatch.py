"""`queue_infer` (B5-06a [6] "queue_infer", [8] mục `queue_infer`).

Redis thật (K23); thông điệp đọc bằng `LRANGE` qua `queued_payloads` vì không worker nào
nghe hàng `ml.infer` trong test (BE-00 §7 "Test task"). `on_after_commit` chạy tại chỗ khi
không có vòng sự kiện chờ callback lên lịch xong — ở đây gọi `after_commit_idle` sau `commit`
đúng khuôn `test_runs.py` của B2-04.
"""

from collections.abc import Iterator
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.worker.pipeline_orchestrate.dispatch import INFER_TASKS, queue_infer
from apps.worker.pipeline_orchestrate.keys import run_prefix
from apps.worker.pipeline_orchestrate.pins import RunPins
from apps.worker.pipeline_orchestrate.tests._helpers import LEVEL_ID, ML_QUEUE
from packages.core.clock import SystemClock
from packages.core.ids import new_id
from packages.db.hooks import after_commit_idle
from packages.messaging.redis import SyncRedis, broker_redis_sync
from packages.ml_contracts.families import MODEL_FAMILIES, ModelFamily
from packages.storage.keys import upload_page
from packages.testing.factories.pipeline_orchestrate import classic_ref
from packages.testing.fixtures.messaging import queued_payloads


def _pins(*, run_id: str, used: dict[ModelFamily, str] | None = None) -> RunPins:
    """`RunPins` tối thiểu: ba họ cổ điển ghim, `used` theo tham số."""
    return RunPins(
        run_id=run_id,
        pinned={family: classic_ref(family) for family in MODEL_FAMILIES},
        used=used or {},
        persisted_revision=None,
        step_requeue_count=0,
    )


def _scene(run_id: str) -> tuple[str, str]:
    """`(run_prefix, page_key)` cùng dự án/tầng/lượt tải — `InferStepPayload` kiểm chéo hai khoá này."""
    clock = SystemClock()
    project_id, upload_id = new_id("prj", clock), new_id("upl", clock)
    prefix = run_prefix(project_id=project_id, level_id=LEVEL_ID, upload_id=upload_id, run_id=run_id)
    page_key = upload_page(project_id, LEVEL_ID, upload_id, 0)
    return prefix, page_key


@pytest.fixture
def broker(messaging_env: None) -> Iterator[SyncRedis]:
    """Client broker thật, hàng `ml.infer` sạch ở đầu và cuối test."""
    client = broker_redis_sync()
    client.delete(ML_QUEUE)
    yield client
    client.delete(ML_QUEUE)
    client.close()


async def test_queue_infer_sends_all_three_when_used_is_empty(db_session: AsyncSession, broker: SyncRedis) -> None:
    """`used` rỗng → ba thông điệp trên `ml.infer`, đúng `model`/`artifact_prefix`/`px_per_paper_mm`."""
    run_id = new_id("run", SystemClock())
    prefix, page_key = _scene(run_id)
    pins = _pins(run_id=run_id)
    queued = queue_infer(
        db_session,
        pins=pins,
        run_prefix=prefix,
        page_key=page_key,
        width_px=1600,
        height_px=1200,
        px_per_paper_mm=7.5,
    )
    assert set(queued) == set(MODEL_FAMILIES)
    await db_session.commit()
    await after_commit_idle(db_session)
    payloads = queued_payloads(broker, ML_QUEUE)
    assert len(payloads) == 3
    by_step = {item["step"]: item for item in payloads}
    for family in INFER_TASKS:
        item = by_step[family]
        assert item["artifact_prefix"] == f"{prefix}{family}/"
        assert item["px_per_paper_mm"] == 7.5
        assert cast("dict[str, object]", item["model"])["family"] == family


async def test_queue_infer_skips_families_already_used(db_session: AsyncSession, broker: SyncRedis) -> None:
    """`used` có tường (`wallSegmentation`) → hai thông điệp, không `ml.infer.walls.segment`."""
    run_id = new_id("run", SystemClock())
    prefix, page_key = _scene(run_id)
    pins = _pins(run_id=run_id, used={"wallSegmentation": "classic"})
    queued = queue_infer(
        db_session,
        pins=pins,
        run_prefix=prefix,
        page_key=page_key,
        width_px=1600,
        height_px=1200,
    )
    assert "wallSegmentation" not in queued
    assert len(queued) == 2
    await db_session.commit()
    await after_commit_idle(db_session)
    payloads = queued_payloads(broker, ML_QUEUE)
    assert len(payloads) == 2
    assert all(item["step"] != "wallSegmentation" for item in payloads)


async def test_queue_infer_rollback_leaves_queue_empty(db_session: AsyncSession, broker: SyncRedis) -> None:
    """Rollback sau `queue_infer` → không thông điệp nào tới hàng (J09)."""
    run_id = new_id("run", SystemClock())
    prefix, page_key = _scene(run_id)
    queue_infer(
        db_session,
        pins=_pins(run_id=run_id),
        run_prefix=prefix,
        page_key=page_key,
        width_px=1600,
        height_px=1200,
    )
    await db_session.rollback()
    await after_commit_idle(db_session)
    assert queued_payloads(broker, ML_QUEUE) == []
